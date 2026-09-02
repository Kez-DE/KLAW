"""Sweep các knob hợp nhất (fusion) và in CẢ ĐƯỜNG CONG, không chỉ điểm tốt nhất.

Trong repo này **không có `alpha`**: `retrieval.rrf` cộng `1/(k + rank)` trên mọi
nhánh với TRỌNG SỐ BẰNG NHAU. Ba knob duy nhất của hợp nhất là mỗi nhánh góp bao
nhiêu ứng viên (`retrieve_bm25_topk`, `retrieve_dense_topk`) và `rrf_k`. Hạ
`retrieve_bm25_topk` xuống 0 CHÍNH LÀ preset `dense_only`, nên bảng dưới đây phủ
trọn đoạn giữa `hybrid` và `dense_only` — trả lời được câu "chỉnh lại trọng số thì
`hybrid` có vượt `dense_only` không" bằng số, không bằng lập luận.

Mỗi nhánh chỉ xếp hạng MỘT LẦN cho mỗi câu rồi dùng lại cho mọi điểm sweep:
`LIMIT k` là tiền tố của `LIMIT 20` với cùng `ORDER BY`, nên nhánh topk ≤ 20 là
một lát của danh sách đã cache. Cả bảng tốn đúng 77 lệnh gọi embedding.

    python -m scripts.sweep_fusion
"""

from sqlalchemy import text

from eval.run import _METRIC_FNS, _load_golden_qa, overlay_settings
from src.services.db import get_engine
from src.services.embedding import EmbeddingClient
from src.services.retrieval import Retriever, _dedup_giu_hang_tot_nhat, rrf

TOPK_MAX = 20
BM25_TOPK = (0, 1, 2, 3, 5, 8, 12, 16, 20)
RRF_K = (5, 10, 20, 30, 60, 120, 240)
_KEYS = ("recall@5", "recall@10", "mrr@5", "ndcg@5")


def _chuan_bi() -> tuple:
    s = overlay_settings(
        {"retrieve_bm25_topk": TOPK_MAX, "retrieve_dense_topk": TOPK_MAX, "retrieve_final_topk": 10}
    )
    engine = get_engine()
    e = EmbeddingClient(
        api_key=s.openrouter_api_key, base_url=s.openrouter_base_url,
        model=s.openrouter_embedding_model_name, dim=s.openrouter_embedding_dim,
    )
    r = Retriever(engine, e, s)
    items = _load_golden_qa(s, engine)
    cache = {
        it["id"]: (r.bm25(it["cau_hoi"], TOPK_MAX), r.dense(it["cau_hoi"], TOPK_MAX))
        for it in items
    }
    moi_chunk = sorted({c for b, d in cache.values() for c in (*b, *d)})
    with engine.connect() as conn:
        provision_cua = dict(
            conn.execute(
                text("SELECT id, provision_id FROM chunks WHERE id = ANY(:ids)"),
                {"ids": moi_chunk},
            ).all()
        )
    return items, cache, provision_cua, s


def _do(items, cache, provision_cua, bm25_topk: int, dense_topk: int, rrf_k: int) -> dict:
    tong = dict.fromkeys(_METRIC_FNS, 0.0)
    for it in items:
        b, d = cache[it["id"]]
        nhanh = [x[:n] for x, n in ((b, bm25_topk), (d, dense_topk)) if n > 0]
        if not nhanh:
            raise ValueError("cả hai nhánh đều tắt")
        fused = rrf(nhanh, k=rrf_k)
        pids = _dedup_giu_hang_tot_nhat([c for c, _ in fused[:10]], provision_cua)
        gold = set(it["provision_ids"])
        for ten, fn in _METRIC_FNS.items():
            tong[ten] += fn(pids, gold)
    return {ten: round(v / len(items), 4) for ten, v in tong.items()}


def render() -> str:
    items, cache, provision_cua, _ = _chuan_bi()
    out = [
        f"Đường cong A — số ứng viên nhánh TỪ VỰNG góp vào (dense_topk={TOPK_MAX}, rrf_k=60), n={len(items)}",
        "",
        "| bm25_topk | Recall@5 | Recall@10 | MRR@5 | nDCG@5 | ghi chú |",
        "|---|---|---|---|---|---|",
    ]
    for bt in BM25_TOPK:
        m = _do(items, cache, provision_cua, bt, TOPK_MAX, 60)
        ghi = "= `dense_only`" if bt == 0 else ("= `hybrid`" if bt == TOPK_MAX else "")
        out.append(f"| {bt} | " + " | ".join(str(m[k]) for k in _KEYS) + f" | {ghi} |")

    out += [
        "",
        f"Đường cong B — `rrf_k` (bm25_topk={TOPK_MAX}, dense_topk={TOPK_MAX})",
        "",
        "| rrf_k | Recall@5 | Recall@10 | MRR@5 | nDCG@5 | ghi chú |",
        "|---|---|---|---|---|---|",
    ]
    for k in RRF_K:
        m = _do(items, cache, provision_cua, TOPK_MAX, TOPK_MAX, k)
        out.append(
            f"| {k} | " + " | ".join(str(m[key]) for key in _KEYS) + f" | {'= `hybrid`' if k == 60 else ''} |"
        )
    return "\n".join(out)


def demo() -> None:
    """Tự kiểm: bm25_topk=0 phải cho ĐÚNG `dense_only`, và cắt tiền tố phải đúng."""
    items, cache, provision_cua, _ = _chuan_bi()
    chi_dense = _do(items, cache, provision_cua, 0, TOPK_MAX, 60)
    # rrf trên MỘT nhánh là phép biến đổi đơn điệu của thứ hạng → phải giữ nguyên
    # thứ tự của chính nhánh đó, tức trùng khít preset dense_only.
    tong = dict.fromkeys(_METRIC_FNS, 0.0)
    for it in items:
        pids = _dedup_giu_hang_tot_nhat(cache[it["id"]][1][:10], provision_cua)
        for ten, fn in _METRIC_FNS.items():
            tong[ten] += fn(pids, set(it["provision_ids"]))
    thang = {ten: round(v / len(items), 4) for ten, v in tong.items()}
    assert chi_dense == thang, f"rrf một nhánh đổi thứ hạng: {chi_dense} != {thang}"
    print("demo OK:", chi_dense)


if __name__ == "__main__":
    import sys

    demo() if "--demo" in sys.argv else print(render())
