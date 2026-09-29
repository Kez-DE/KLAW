"""Eval harness một lệnh: python -m eval.run --config hybrid|lexical_only|dense_only|all

Mọi tham số đến từ preset YAML (`eval/configs/*.yaml`), không hardcode — nhờ
vậy mỗi dòng ablation là MỘT FILE, tái lập được, và config_name/commit_hash đi
thẳng vào kết quả (yêu cầu #2, #5).

`--config all` chạy cả ba preset và ghi `eval/results/report.md` — đây là câu
lệnh sinh bảng ablation cho chương kết quả khóa luận.

Cờ `golden_qa_da_review` và cảnh báo `canh_bao` ĐỌC TỪ DỮ LIỆU (`duyet_boi`
trong golden_qa.yaml), không hardcode: một cờ hằng số chỉ đúng ở một phía của
cái mốc nó mô tả. Trước 2026-09-02 nó là `False` cứng, nên sau khi chủ dự án
duyệt xong 77 câu thì mọi báo cáo vẫn in "CHƯA được người duyệt tay" — một câu
sai sự thật in vào đúng chương đánh giá (yêu cầu #4).
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
from src.config import Settings, as_of_hieu_luc, get_settings
from src.services.db import get_engine
from src.services.embedding import EmbeddingClient
from src.services.hien_thi import hien_thi_luc
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

def da_nguoi_duyet(items: list[dict]) -> bool:
    """Toàn bộ tập đã qua mắt NGƯỜI chưa (`duyet_boi == "nguoi"`).

    Hàm THUẦN để test được không cần Postgres. Ba mặc định an toàn:
    - MỘT câu chưa người duyệt ⇒ cả tập chưa duyệt. "Công bố được" là một bit,
      không phải một tỉ lệ, nên không có ngưỡng "gần đủ".
    - THIẾU trường ⇒ chưa duyệt. Cùng quy tắc cả repo: không biết thì mặc định
      là chưa kiểm chứng, không bao giờ mặc định là hợp lệ.
    - Tập RỖNG ⇒ chưa duyệt. `all()` trên tập rỗng trả True, và "không có câu
      nào" mà báo là "đã duyệt hết" là đúng cái bẫy `all()` hay gài.
    """
    return bool(items) and all(i.get("duyet_boi") == "nguoi" for i in items)


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


def _retrieve(r: Retriever, q: str, s: Settings, hien: frozenset[str] | None = None) -> list[int]:
    branches: list[list[int]] = []
    if s.retrieve_bm25_topk > 0:
        branches.append(r.bm25(q, s.retrieve_bm25_topk, hien))
    if s.retrieve_dense_topk > 0:
        branches.append(r.dense(q, s.retrieve_dense_topk, hien))
    if not branches:
        raise ValueError("cả hai nhánh retrieval đều tắt (topk=0) — config sai")
    fused = rrf(branches, k=s.rrf_k)
    chunk_ids = [c for c, _ in fused[: s.retrieve_final_topk]]
    return r.provision_ids(chunk_ids)


def _run_items(
    r: Retriever, items: list[dict], s: Settings, hien: frozenset[str] | None = None
) -> tuple[list[dict], int]:
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
            got = _retrieve(r, it["cau_hoi"], s, hien)
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


def phan_giai_gold(engine: Engine, items: list[dict]) -> list[dict]:
    """Ground truth của golden_qa là `duong_dan`, KHÔNG phải `provisions.id`.

    `provisions.id` là BIGSERIAL và `scripts.ingest` xoá-rồi-chèn mỗi document
    có checksum đổi, nên mọi id dịch sau một lần sửa parser hay một lần mở rộng
    corpus. Khi id ghi cứng trong YAML chết đi, `_run_items` KHÔNG nổ — nó tính
    Recall trên một tập gold không tồn tại và trả về 0,0. Bảng số liệu khoá luận
    tụt mà không một dòng lỗi nào chỉ ra vì sao. Đó là lý do id được PHÂN GIẢI ở
    đây, ngay trước khi chạy, và mọi `duong_dan` không phân giải được là một
    ValueError — không phải một câu Recall=0 im lặng.

    `duong_dan` là khoá canonical của dự án: unique index
    `ux_provisions_neo_trich_dan` (migration 004) bắt nó duy nhất ở cấp trích
    dẫn được, và nó cũng chính là chuỗi người đọc thấy trong trích dẫn.
    """
    can = sorted({dd for it in items for dd in it["duong_dan"]})
    with engine.connect() as c:
        m = dict(c.execute(
            text("SELECT duong_dan, id FROM provisions WHERE duong_dan = ANY(:dd)"),
            {"dd": can}).all())
    thieu = [dd for dd in can if dd not in m]
    if thieu:
        raise ValueError(
            f"{len(thieu)}/{len(can)} duong_dan trong golden_qa.yaml KHÔNG có trong DB — "
            f"corpus chưa nạp, hoặc neo đã đổi: {thieu[:5]}")
    return [it | {"provision_ids": [m[dd] for dd in it["duong_dan"]]} for it in items]


def _load_golden_qa(s: Settings, engine: Engine) -> tuple[list[dict], bool]:
    """Trả (items đã phân giải, đã-người-duyệt).

    Cờ đọc từ items THÔ, trước `phan_giai_gold` — hàm đó dựng lại bản ghi cho
    mục đích tính metric và không có hợp đồng nào buộc nó giữ `duyet_boi`. Đọc
    sau khi biến đổi là đặt một khẳng định về xuất xứ dữ liệu lên một hàm không
    hứa gì về nó.
    """
    p = Path(s.eval_dataset_dir) / "golden_qa.yaml"
    items = yaml.safe_load(p.read_text(encoding="utf-8"))["items"]
    return phan_giai_gold(engine, items), da_nguoi_duyet(items)


def evaluate(config_name: str, loc_hien: bool = True) -> dict:
    """`loc_hien` (mặc định): chỉ truy hồi trong tập văn bản được HIỆN tại mốc
    hiệu lực, đúng như đường trả lời (`graph_tra_cuu.n_retrieve`) — quyết định
    2026-09-28 mục 17: đo cái người dùng thấy. `False` tái lập số thô cũ trên
    toàn kho, kể cả văn bản ẩn; file kết quả mang hậu tố `-khong-loc`."""
    s = overlay_settings(load_config(config_name))
    engine = get_engine()
    items, da_duyet = _load_golden_qa(s, engine)
    as_of = as_of_hieu_luc(s.as_of_date)
    hien = hien_thi_luc(engine, as_of) if loc_hien else None

    embedder = EmbeddingClient(
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        model=s.openrouter_embedding_model_name,
        dim=s.openrouter_embedding_dim,
    )
    r = Retriever(engine, embedder, s)

    per_item, n_ok = _run_items(r, items, s, hien)
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
        "loc_hien": loc_hien,
        "as_of_hien": str(as_of) if loc_hien else None,
        "so_van_ban_hien": len(hien) if hien is not None else None,
        "commit_hash": _commit_hash(),
        "ts": datetime.now(UTC).isoformat(),
        "golden_qa_da_review": da_duyet,
        # Cảnh báo BIẾN MẤT khi đã duyệt, không chỉ đổi chữ: nó tồn tại để chặn
        # việc trích một con số chưa ai xác nhận, và giữ nó lại sau khi đã xác
        # nhận thì lần sau không ai còn tin cảnh báo nào nữa.
        "canh_bao": None if da_duyet else _CANH_BAO_CHUA_DUYET.format(n=n),
    }

    res_dir = Path(s.eval_result_dir)
    res_dir.mkdir(parents=True, exist_ok=True)
    ten = config_name if loc_hien else f"{config_name}-khong-loc"
    f = res_dir / _ten_file_ket_qua(ten, s.openrouter_embedding_model_name, n)
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
    lines: list[str] = ["# Eval Report — Retrieval Ablation (Plan 2, Task 9)", ""]

    # Cảnh báo dựng từ CỜ TRONG SUMMARY, và dùng lại ĐÚNG MỘT bản của câu chữ
    # (`_CANH_BAO_CHUA_DUYET`). Trước bản này câu ấy nằm hardcode ở HAI nơi —
    # summary và report — nên khi trạng thái thật đổi, cả hai đều sai và không
    # chỗ nào đọc chỗ nào. Hai bản sao của một khẳng định về dữ liệu là cách
    # chắc chắn nhất để chúng lệch nhau.
    #
    # Thiếu khoá ⇒ coi như CHƯA duyệt: file summary ghi trước 2026-09-02 không
    # có khoá đó, và đọc lại chúng phải ra "chưa duyệt", không phải "đã duyệt".
    mau_co = next(iter(results.values()), {})
    if not mau_co.get("golden_qa_da_review", False):
        lines += [
            "> **CẢNH BÁO:** "
            + _CANH_BAO_CHUA_DUYET.format(n=mau_co.get("n_queries", "?"))
            + " Chưa ai, kể cả chủ dự án, duyệt tay từng câu.",
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
    lines.append(
        "> **Sai số tái lập:** nhánh dense KHÔNG tất định tuyệt đối. Vector truy vấn do OpenRouter "
        "trả về đôi khi lệch tới ~2,7e-4 mỗi chiều giữa hai lần gọi CÙNG một câu (đo được: 1/4 lần "
        "gọi lệch), đủ để đảo thứ tự vài láng giềng sát nhau. Chạy `dense_only` ba lần cho Recall@10 "
        "0,7727 / 0,7792 / 0,7727: giữa hai lần đầu, 5/77 câu đổi thứ tự ở **hạng 7–10** và 1 câu "
        "đổi metric → biên độ Recall@10 ±0,0065, nDCG@10 ±0,0023. "
        "**Top-5 không đổi** ở cả hai lần, nên Recall@5/MRR@5/nDCG@5 ổn định; @10 phải đọc kèm sai "
        "số này. Nhánh từ vựng thì tất định tuyệt đối (0/77 câu lệch qua nhiều lần chạy)."
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
    ap.add_argument(
        "--khong-loc-hien",
        action="store_true",
        help="đo trên toàn kho, kể cả văn bản ẩn (số thô trước quyết định 2026-09-28 mục 17)",
    )
    a = ap.parse_args()
    loc_hien = not a.khong_loc_hien

    if a.config == "all":
        results = {name: evaluate(name, loc_hien) for name in ("hybrid", "lexical_only", "dense_only")}
        p = _ghi_report(results)
        print(f"đã ghi {p}")
        goc = {name: {k: v for k, v in r.items() if k != "per_item"} for name, r in results.items()}
        print(json.dumps(goc, ensure_ascii=False, indent=2))
        return

    r = evaluate(a.config, loc_hien)
    print(json.dumps({k: v for k, v in r.items() if k != "per_item"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
