"""Eval harness một lệnh: python -m eval.run --config hybrid|lexical_only|dense_only|all

Mọi tham số đến từ preset YAML (`eval/configs/*.yaml`), không hardcode — nhờ
vậy mỗi dòng ablation là MỘT FILE, tái lập được, và config_name/commit_hash đi
thẳng vào kết quả (yêu cầu #2, #5).

`--config all` chạy cả ba preset và ghi `eval/results/report.md` — đây là câu
lệnh sinh bảng ablation cho chương kết quả khóa luận.

golden_qa.yaml đang 100% `da_review: false` (Task 8, chưa ai duyệt tay) — mọi
kết quả ở đây mang cảnh báo `canh_bao`/`golden_qa_da_review` (yêu cầu #4): CHỈ
BÁO, không phải kết quả công bố được.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Engine, text

from eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k
from src.config import Settings, get_settings
from src.services.db import get_engine
from src.services.embedding import EmbeddingClient
from src.services.retrieval import Retriever, rrf

CONFIG_DIR = Path("eval/configs")

# k baked vào từng metric qua partial — thêm/bớt entry ở đây là đủ để đổi bảng
# ablation, không phải sửa vòng lặp evaluate().
_METRIC_FNS: dict[str, Any] = {
    "recall@5": partial(recall_at_k, k=5),
    "recall@10": partial(recall_at_k, k=10),
    "mrr@5": partial(mrr_at_k, k=5),
    "mrr@10": partial(mrr_at_k, k=10),
    "ndcg@5": partial(ndcg_at_k, k=5),
    "ndcg@10": partial(ndcg_at_k, k=10),
}

_CANH_BAO_CHUA_DUYET = (
    "golden_qa.yaml CHƯA được người duyệt tay (da_review: false trên toàn bộ {n} câu, "
    "Task 8) — con số dưới đây là CHỈ BÁO cho hướng phát triển, KHÔNG phải kết quả công bố được."
)


def _chan_key_la(cfg: dict, nguon: str) -> None:
    """Key không khớp field nào của Settings phải NỔ. `rrf_K: 5` từng cho ra một
    hàng ablation giống hệt mặc định — không warning, không lỗi, đúng kịch bản
    sweep `rrf_k`: một lần gõ nhầm là bốn hàng bằng nhau và kết luận sai."""
    la = set(cfg) - set(Settings.model_fields)
    if la:
        raise ValueError(f"{nguon}: key không khớp field nào của Settings: {sorted(la)}")


def load_config(name: str) -> dict:
    p = CONFIG_DIR / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"không có preset {name!r} tại {p}")
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    _chan_key_la(cfg, str(p))
    return cfg


def overlay_settings(overrides: dict) -> Settings:
    """Settings mới với override — KHÔNG sửa instance toàn cục đã cache (get_settings
    dùng @lru_cache; mọi nơi khác trong app tin instance đó không đổi giữa chừng)."""
    _chan_key_la(overrides, "overlay_settings")
    base = get_settings().model_dump()
    base.update(overrides)
    return Settings(**base)


def _ten_file_ket_qua(config_name: str, model: str, n: int) -> str:
    """Tên file PHẢI mang model. `compare_embeddings` gọi `evaluate("dense_only")`
    một lần cho MỖI model; tên chỉ theo `config_name` làm lần chạy sau GHI ĐÈ
    `per_item` của lần trước — đã thực sự xảy ra, mất toàn bộ bằng chứng cấp
    item của một model. Slug hoá `/` cho an toàn với tên file."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", model)
    return f"{config_name}-{slug}-{n}.json"


def _commit_hash() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=repo_root
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _retrieve(r: Retriever, q: str, s: Settings) -> list[int]:
    branches: list[list[int]] = []
    if s.retrieve_bm25_topk > 0:
        branches.append(r.bm25(q, s.retrieve_bm25_topk))
    if s.retrieve_dense_topk > 0:
        branches.append(r.dense(q, s.retrieve_dense_topk))
    if not branches:
        raise ValueError("cả hai nhánh retrieval đều tắt (topk=0) — config sai")
    fused = rrf(branches, k=s.rrf_k)
    chunk_ids = [c for c, _ in fused[: s.retrieve_final_topk]]
    return r.provision_ids(chunk_ids)


def _run_items(r: Retriever, items: list[dict], s: Settings) -> tuple[list[dict], int]:
    """Chạy retrieval + tính metric cho từng câu golden_qa.

    Lỗi retrieval được GHI RÕ vào per_item (error_type, error) và KHÔNG cộng
    vào n_ok — khác hẳn Recall=0 (yêu cầu #3). Gộp chung hai thứ này sẽ làm
    bảng ablation trông như retrieval kém trong khi thực ra nó đã crash.
    """
    per_item: list[dict] = []
    n_ok = 0
    for it in items:
        gold = set(it["provision_ids"])
        try:
            got = _retrieve(r, it["cau_hoi"], s)
        except Exception as e:  # noqa: BLE001 - cố ý bắt rộng để KHÔNG làm sập cả batch, xem docstring
            print(f"[eval] LỖI câu {it['id']!r}: {type(e).__name__}: {e}", file=sys.stderr)
            per_item.append(
                {
                    "id": it["id"],
                    "cau_hoi": it["cau_hoi"],
                    "provision_ids_dung": it["provision_ids"],
                    "duong_dan_dung": it["duong_dan"],
                    "error_type": type(e).__name__,
                    "error": str(e),
                }
            )
            continue
        m = {name: fn(got, gold) for name, fn in _METRIC_FNS.items()}
        n_ok += 1
        per_item.append(
            {
                "id": it["id"],
                "cau_hoi": it["cau_hoi"],
                **m,
                "provision_ids_dung": it["provision_ids"],
                "duong_dan_dung": it["duong_dan"],
                "retrieved": got[:10],
            }
        )
    return per_item, n_ok


def _duong_dan_map(engine: Engine, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    with engine.connect() as c:
        rows = c.execute(text("SELECT id, duong_dan FROM provisions WHERE id = ANY(:ids)"), {"ids": list(ids)}).all()
    return dict(rows)


def _gan_duong_dan_he_thong(engine: Engine, per_item: list[dict]) -> list[dict]:
    """Gắn duong_dan (đọc được, vd '45/2019/QH14 > Điều 127') cho top-3 provision
    hệ thống TRẢ VỀ — golden_qa đã có sẵn duong_dan ĐÚNG, không cần tra DB lại,
    nhưng câu trả lời SAI thì chỉ có provision_id, phải tra mới đọc được trong report.md."""
    ids = {pid for it in per_item for pid in it.get("retrieved", [])[:3]}
    m = _duong_dan_map(engine, ids)

    def _giau(it: dict) -> dict:
        if "retrieved" not in it:
            return it
        nhan = [m.get(pid, f"(id {pid} không có trong provisions)") for pid in it["retrieved"][:3]]
        return it | {"duong_dan_tra_ve_top3": nhan}

    return [_giau(it) for it in per_item]


def _load_golden_qa(s: Settings) -> list[dict]:
    p = Path(s.eval_dataset_dir) / "golden_qa.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))["items"]


def evaluate(config_name: str) -> dict:
    s = overlay_settings(load_config(config_name))
    items = _load_golden_qa(s)

    embedder = EmbeddingClient(
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        model=s.openrouter_embedding_model_name,
        dim=s.openrouter_embedding_dim,
    )
    r = Retriever(get_engine(), embedder, s)

    per_item, n_ok = _run_items(r, items, s)
    per_item = _gan_duong_dan_he_thong(r.engine, per_item)

    n = len(items)
    summary: dict = {
        key: round(sum(it[key] for it in per_item if "error" not in it) / n_ok, 4) if n_ok else 0.0
        for key in _METRIC_FNS
    }
    summary |= {
        "n_queries": n,
        "n_ok": n_ok,
        "n_errors": n - n_ok,
        "config_name": config_name,
        "embedding_model": s.openrouter_embedding_model_name,
        # Hai knob này quyết định nhánh BM25 mạnh hay yếu (xem docs/bm25-tuning.md)
        # — ghi vào summary để mỗi hàng ablation tự mô tả được, không phải suy
        # ra từ mặc định của Settings ở thời điểm đọc lại file.
        "bm25_rank_normalization": s.bm25_rank_normalization,
        "bm25_strip_stopwords": s.bm25_strip_stopwords,
        "commit_hash": _commit_hash(),
        "ts": datetime.now(UTC).isoformat(),
        "golden_qa_da_review": False,
        "canh_bao": _CANH_BAO_CHUA_DUYET.format(n=n),
    }

    res_dir = Path(s.eval_result_dir)
    res_dir.mkdir(parents=True, exist_ok=True)
    f = res_dir / _ten_file_ket_qua(config_name, s.openrouter_embedding_model_name, n)
    f.write_text(
        json.dumps({"summary": summary, "per_item": per_item}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    out = dict(summary)
    out["result_file"] = str(f)
    out["per_item"] = per_item
    return out


# ---------------------------------------------------------------------------
# report.md — so sánh 3 preset, phát hiện nhánh chết, liệt kê câu tệ nhất
# ---------------------------------------------------------------------------

_BANG_METRIC_KEYS = ("recall@5", "recall@10", "mrr@5", "mrr@10", "ndcg@5", "ndcg@10")


def _nhanh_chet(results: dict[str, dict]) -> list[str]:
    """So lexical_only/dense_only với hybrid trên mọi metric. Nếu MỘT preset khớp
    hybrid TUYỆT ĐỐI, đó là dấu hiệu nhánh còn lại trong hybrid không đóng góp
    gì — nhánh chết (yêu cầu #1). Phải báo, không được lặng lẽ ghi vào bảng
    như một hàng ablation đáng tin."""
    canh_bao: list[str] = []
    hybrid = results.get("hybrid")
    if not hybrid:
        return canh_bao
    for name in ("lexical_only", "dense_only"):
        other = results.get(name)
        if other and all(other.get(k) == hybrid.get(k) for k in _BANG_METRIC_KEYS):
            canh_bao.append(
                f"`{name}` cho ĐÚNG con số như `hybrid` trên mọi metric — nghi ngờ nhánh còn lại "
                f"trong hybrid không đóng góp gì (nhánh chết). Kiểm tra rrf_k và xem nhánh kia có "
                f"luôn trả rỗng không, TRƯỚC khi tin bảng ablation này."
            )
    return canh_bao


def _cau_hoi_te_nhat(per_item: list[dict], n: int = 10) -> list[dict]:
    """Worst-N theo recall@5 rồi mrr@5, tăng dần. Loại câu lỗi — lỗi đã được
    báo riêng (yêu cầu #3), không phải một điểm "tệ" để xếp hạng cùng."""
    danh_gia_duoc = [it for it in per_item if "error" not in it]
    return sorted(danh_gia_duoc, key=lambda it: (it["recall@5"], it["mrr@5"]))[:n]


def write_report(results: dict[str, dict]) -> str:
    """Sinh nội dung report.md từ evaluate() của (thường là) cả 3 preset. Hàm
    THUẦN — không đụng DB/file — để test được _nhanh_chet/_cau_hoi_te_nhat mà
    không cần Postgres."""
    lines: list[str] = [
        "# Eval Report — Retrieval Ablation (Plan 2, Task 9)",
        "",
        "> **CẢNH BÁO:** `golden_qa.yaml` (77 câu) toàn bộ đang `da_review: false` — "
        "chưa ai, kể cả chủ dự án, duyệt tay từng câu (Task 8). Mọi con số dưới đây là "
        "**CHỈ BÁO cho hướng phát triển**, KHÔNG phải kết quả công bố được trong khóa luận "
        "cho tới khi review xong.",
        "",
    ]

    canh_bao = _nhanh_chet(results)
    if canh_bao:
        lines.append("## Cảnh báo nhánh chết")
        lines.append("")
        lines.extend(f"- {c}" for c in canh_bao)
        lines.append("")

    lines.append("## 1. Bảng ablation (77 câu golden_qa)")
    lines.append("")
    mau = next((r for r in results.values() if "bm25_rank_normalization" in r), None)
    if mau:
        lines.append(
            f"`lexical_only` là **truy hồi từ vựng bằng `tsvector` + `ts_rank` của PostgreSQL** "
            f"(config `simple` + `unaccent`, truy vấn OR, chuẩn hoá độ dài "
            f"`normalization={mau['bm25_rank_normalization']}`, lọc hư từ "
            f"{'có' if mau['bm25_strip_stopwords'] else 'không'}) — **không phải BM25**: `ts_rank` "
            "không có tham số `k1`/`b` và không dùng IDF. Hai tham số trên chọn theo đo, không theo "
            "mặc định của Postgres; bảng sweep đầy đủ và lý do ở `docs/bm25-tuning.md` (tái lập: "
            "`python -m scripts.sweep_bm25`)."
        )
        lines.append("")
    lines.append("| Config | Recall@5 | Recall@10 | MRR@5 | MRR@10 | nDCG@5 | nDCG@10 | n_ok/n_queries |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name in ("hybrid", "lexical_only", "dense_only"):
        r = results.get(name)
        if not r:
            continue
        loi = f" ({r['n_errors']} lỗi)" if r.get("n_errors") else ""
        lines.append(
            f"| {name} | {r['recall@5']} | {r['recall@10']} | {r['mrr@5']} | {r['mrr@10']} | "
            f"{r['ndcg@5']} | {r['ndcg@10']} | {r['n_ok']}/{r['n_queries']}{loi} |"
        )
    lines.append("")

    lines.append("## 2. Tái lập")
    lines.append("")
    for name in ("hybrid", "lexical_only", "dense_only"):
        r = results.get(name)
        if not r:
            continue
        lines.append(
            f"- `{name}`: commit `{r.get('commit_hash', '?')}`, model embedding "
            f"`{r.get('embedding_model', '?')}`, n={r.get('n_queries', '?')}, ts={r.get('ts', '?')}"
        )
    lines.append("")

    hybrid = results.get("hybrid")
    if hybrid and "per_item" in hybrid:
        te_nhat = _cau_hoi_te_nhat(hybrid["per_item"], n=10)
        lines.append("## 3. 10 câu tệ nhất (config `hybrid`)")
        lines.append("")
        for it in te_nhat:
            dung = "; ".join(it.get("duong_dan_dung", [])) or "(không có)"
            tra_ve = "; ".join(it.get("duong_dan_tra_ve_top3", [])) or "(rỗng)"
            lines.append(f"### `{it['id']}` — recall@5={it['recall@5']}, mrr@5={it['mrr@5']}")
            lines.append(f"- Câu hỏi: {it['cau_hoi']}")
            lines.append(f"- Điều luật đúng: {dung}")
            lines.append(f"- Hệ thống trả về (top 3): {tra_ve}")
            lines.append("")

        loi_items = [it for it in hybrid["per_item"] if "error" in it]
        if loi_items:
            lines.append(f"## 4. Câu lỗi retrieval — {len(loi_items)} câu (KHÔNG tính vào metric, không phải Recall=0)")
            lines.append("")
            for it in loi_items:
                lines.append(f"- `{it['id']}` ({it['cau_hoi']}): {it['error_type']}: {it['error']}")
            lines.append("")

    return "\n".join(lines)


def _ghi_report(results: dict[str, dict]) -> Path:
    p = Path(get_settings().eval_result_dir) / "report.md"
    p.write_text(write_report(results), encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--config", default="hybrid", help="tên preset trong eval/configs/, hoặc 'all' để chạy cả 3 + ghi report.md"
    )
    a = ap.parse_args()

    if a.config == "all":
        results = {name: evaluate(name) for name in ("hybrid", "lexical_only", "dense_only")}
        p = _ghi_report(results)
        print(f"đã ghi {p}")
        goc = {name: {k: v for k, v in r.items() if k != "per_item"} for name, r in results.items()}
        print(json.dumps(goc, ensure_ascii=False, indent=2))
        return

    r = evaluate(a.config)
    print(json.dumps({k: v for k, v in r.items() if k != "per_item"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
