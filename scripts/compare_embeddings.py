"""So sánh embedding model trên chính golden_qa của dự án (Task 10, Plan 2).

RÀNG BUỘC CỨNG: cột `chunks.embedding` là `vector(1024)` cố định
(`migrations/001_init.sql`). Model trả về chiều khác 1024 KHÔNG nhét được — script dò
chiều THẬT của từng model bằng một lệnh gọi API rẻ (`probe_dim`) TRƯỚC khi embed cả
corpus, rồi bỏ qua CÓ BÁO CÁO model chiều khác, KHÔNG truncate/pad (bịa dữ liệu) và
KHÔNG tự thêm cột/migration (cần quyết định của chủ dự án).

Đo bằng cấu hình `dense_only`, KHÔNG phải `hybrid`: hybrid trộn thêm nhánh từ vựng
(Recall@5 0.3117 sau khi chuẩn hoá độ dài + lọc hư từ, xem docs/bm25-tuning.md) nên
chất lượng embedding bị nhiễu bởi một biến không liên quan — dense thuần là nơi nó
hiện ra rõ nhất (Task 9).

VN-MTEB không benchmark model thương mại (OpenAI/Google/Voyage) trên tiếng Việt, nên
bảng này — dù nhỏ — là số liệu CHƯA từng công bố cho các model đó trên văn bản pháp
luật Việt Nam.

golden_qa.yaml đang 100% `da_review: false` (Task 8) — mọi con số dưới đây là CHỈ BÁO
cho hướng phát triển, KHÔNG phải kết quả công bố được cho tới khi review xong.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from sqlalchemy import Engine, text

from eval.run import evaluate
from scripts.build_chunks import run as build
from src.config import get_settings
from src.services.db import get_engine

FIXED_COL_DIM = 1024  # chunks.embedding vector(1024) — xem migrations/001_init.sql

# (model, giá $/1M token) — tra catalog OpenRouter /api/v1/models?output_modalities=embeddings.
# Chiều dò THẬT qua probe_dim(), không tin theo mô tả catalog (mô tả không ghi chiều
# cho vài model, và với model Matryoshka như voyage-4-lite, chiều mặc định qua API
# mới là chiều thật sẽ được embed — không phải chiều lớn nhất model hỗ trợ).
CANDIDATES: list[tuple[str, float]] = [
    ("baai/bge-m3", 0.010),
    ("openai/text-embedding-3-small", 0.020),
    ("qwen/qwen3-embedding-8b", 0.010),
    ("google/gemini-embedding-001", 0.150),
    ("voyageai/voyage-4-lite", 0.020),
]

MAX_MODELS = 3  # trần chi phí — kể cả model đã có sẵn trong DB

_CANH_BAO_CHUA_DUYET = (
    "golden_qa.yaml CHƯA được người duyệt tay (da_review: false trên toàn bộ câu, Task 8) — "
    "con số dưới đây là CHỈ BÁO cho hướng phát triển, KHÔNG phải kết quả công bố được."
)


def probe_dim(model: str) -> int:
    """Một lệnh gọi API rẻ (1 câu ngắn) để biết chiều THẬT trước khi embed cả corpus."""
    s = get_settings()
    with httpx.Client(
        base_url=s.openrouter_base_url,
        timeout=60,
        headers={"Authorization": f"Bearer {s.openrouter_api_key}", "Content-Type": "application/json"},
    ) as c:
        r = c.post("/embeddings", json={"model": model, "input": ["xin chào"]})
        r.raise_for_status()
        return len(r.json()["data"][0]["embedding"])


def _kiem_tra_chieu(dim: int) -> str | None:
    """None nếu chiều khớp cột `chunks.embedding vector(1024)`; nếu không, thông báo rõ
    lý do bỏ qua — KHÔNG được để nó fail âm thầm ở bước INSERT giữa chừng."""
    if dim == FIXED_COL_DIM:
        return None
    return f"không so được vì chiều {dim} ≠ {FIXED_COL_DIM} (chunks.embedding vector({FIXED_COL_DIM}) cố định)"


def _da_co_trong_db(engine: Engine, model: str) -> dict | None:
    """None nếu model chưa có chunk nào; dict {"chunks", "tokens"} nếu đã embed sẵn —
    dùng để KHÔNG embed lại (trần chi phí của Task 10)."""
    with engine.connect() as c:
        chunks, tokens = c.execute(
            text("SELECT count(*), coalesce(sum(token_count), 0) FROM chunks WHERE embedding_model = :m"),
            {"m": model},
        ).one()
    return {"chunks": chunks, "tokens": tokens} if chunks > 0 else None


def _dat_model_hien_hanh(model: str) -> None:
    """evaluate() đọc model embedding từ get_settings() (cached), không nhận qua tham
    số — đổi qua env var rồi xoá cache để lần get_settings() kế tiếp thấy model mới."""
    os.environ["OPENROUTER_EMBEDDING_MODEL_NAME"] = model
    get_settings.cache_clear()


def compare(dry_run: bool = False, max_models: int = MAX_MODELS) -> list[dict]:
    rows: list[dict] = []
    da_dung = 0
    engine = get_engine()

    for model, gia in CANDIDATES:
        print(f"\n=== {model} ===")
        if da_dung >= max_models:
            msg = f"vượt trần {max_models} model (kiểm soát chi phí)"
            rows.append({"model": model, "bo_qua": msg})
            print(" ", msg)
            continue

        try:
            dim = probe_dim(model)
        except Exception as e:  # noqa: BLE001 - lỗi probe không được làm dừng cả sweep
            rows.append({"model": model, "loi": str(e)[:300]})
            print("  LỖI probe dim:", str(e)[:300])
            continue

        skip_msg = _kiem_tra_chieu(dim)
        if skip_msg:
            rows.append({"model": model, "dim": dim, "bo_qua": skip_msg})
            print(" ", skip_msg)
            continue

        da_dung += 1
        _dat_model_hien_hanh(model)
        san = _da_co_trong_db(engine, model)

        try:
            if san:
                info, ghi_chu, chi_phi = san, "đã có sẵn trong DB — không embed lại", 0.0
            elif dry_run:
                info = build(model=model, dry_run=True)
                ghi_chu = "DRY RUN — ước tính, chưa embed"
                chi_phi = round(info["tokens"] / 1e6 * gia, 4)
            else:
                info = build(model=model)
                ghi_chu = "embed mới"
                chi_phi = round(info["tokens"] / 1e6 * gia, 4)
        except Exception as e:  # noqa: BLE001 - model lỗi giữa chừng phải hiện ra, không dừng sweep
            rows.append({"model": model, "dim": dim, "loi": str(e)[:300]})
            print("  LỖI embed:", str(e)[:300])
            continue

        row = {
            "model": model,
            "dim": dim,
            "$/1M": gia,
            "chunks": info["chunks"],
            "tokens": info["tokens"],
            "chi_phi": chi_phi,
            "ghi_chu": ghi_chu,
        }

        if dry_run:
            rows.append(row)
            print(f"  DRY RUN: chunks={info['chunks']} tokens={info['tokens']:,} chi_phi_uoc=${chi_phi}")
            continue

        m = evaluate("dense_only")
        row |= {
            "recall@5": m["recall@5"],
            "mrr@5": m["mrr@5"],
            "ndcg@5": m["ndcg@5"],
            "commit_hash": m["commit_hash"],
            "n_ok": m["n_ok"],
            "n_queries": m["n_queries"],
        }
        rows.append(row)
        print(f"  recall@5={m['recall@5']} mrr@5={m['mrr@5']} ndcg@5={m['ndcg@5']} chi_phi=${chi_phi}")

    return rows


def render_markdown(rows: list[dict]) -> str:
    lines = [
        "# So sánh embedding model trên golden_qa (Task 10, Plan 2)",
        "",
        f"> **CẢNH BÁO:** {_CANH_BAO_CHUA_DUYET}",
        "",
        "Đo bằng cấu hình **`dense_only`**, không phải `hybrid`: hybrid trộn thêm nhánh từ vựng "
        "(Recall@5 0,3117 sau khi chuẩn hoá độ dài `ts_rank` và lọc hư từ — xem "
        "`docs/bm25-tuning.md` và `eval/results/report.md`), nên chất lượng embedding bị nhiễu bởi "
        "một biến không liên quan. Dense thuần là nơi nó hiện ra rõ nhất.",
        "",
        "VN-MTEB không benchmark model thương mại (OpenAI/Google/Voyage) trên tiếng Việt — bảng "
        "dưới đây, dù nhỏ, là số liệu CHƯA từng công bố cho các model đó trên văn bản pháp luật "
        "Việt Nam.",
        "",
        f"Cột `chunks.embedding` là `vector({FIXED_COL_DIM})` cố định (`migrations/001_init.sql`) "
        f"— model trả về chiều khác {FIXED_COL_DIM} KHÔNG nhét được. Script dò chiều thật của từng "
        "model bằng một lệnh gọi API rẻ TRƯỚC khi embed cả corpus; model chiều khác bị BỎ QUA có "
        "báo cáo, KHÔNG bị truncate/pad (làm vậy là bịa dữ liệu), và không làm dừng các model còn "
        "lại trong sweep.",
        "",
        "## Bảng so sánh",
        "",
        "| Model | Chiều | $/1M token | Chunks | Token | Chi phí | Recall@5 | MRR@5 | nDCG@5 | Ghi chú |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for r in rows:
        if "loi" in r:
            lines.append(f"| {r['model']} | {r.get('dim', '?')} | — | — | — | — | — | — | — | **LỖI**: {r['loi']} |")
            continue
        if "bo_qua" in r:
            lines.append(
                f"| {r['model']} | {r.get('dim', '?')} | — | — | — | — | — | — | — | **BỎ QUA**: {r['bo_qua']} |"
            )
            continue
        lines.append(
            f"| {r['model']} | {r['dim']} | {r['$/1M']} | {r['chunks']} | {r['tokens']} | "
            f"${r['chi_phi']} | {r['recall@5']} | {r['mrr@5']} | {r['ndcg@5']} | {r['ghi_chu']} |"
        )
    lines.append("")

    do_duoc = [r for r in rows if "recall@5" in r]
    if do_duoc:
        tong_chi_phi = round(sum(r["chi_phi"] for r in do_duoc), 4)
        thang = max(do_duoc, key=lambda r: r["recall@5"])
        commit = do_duoc[0].get("commit_hash", "?")
        lines += [
            f"Tổng chi phí embed thật đã tiêu **trong lần chạy so sánh này**: **${tong_chi_phi}**. "
            "Model ghi `đã có sẵn trong DB` tính $0 ở đây vì corpus của nó đã được embed ở một lần "
            "chạy `build_chunks` trước — chi phí đã trả ở lần đó, không phải miễn phí.",
            "",
            f"Model tốt nhất theo Recall@5 trong lần đo này: `{thang['model']}` ({thang['recall@5']}).",
            "",
            f"Đo tại commit `{commit}`.",
            "",
        ]

    return "\n".join(lines)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    ket_qua = compare(dry_run=dry)
    print("\n" + json.dumps(ket_qua, ensure_ascii=False, indent=2))
    if not dry:
        Path("docs/embedding-comparison.md").write_text(render_markdown(ket_qua), encoding="utf-8")
        print("\nđã ghi docs/embedding-comparison.md")
