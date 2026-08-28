"""Sweep hai biến ĐỘC LẬP của nhánh BM25, in bảng markdown (H1, review-final-p2).

Con số `0.1299` của bảng ablation đầu tiên KHÔNG đo "BM25 trên văn bản pháp luật
Việt Nam yếu"; nó đo "`to_tsvector('simple')` + OR + `ts_rank` KHÔNG chuẩn hoá độ
dài thì yếu" — hai chuyện khác nhau, và khóa luận không được kết luận nhầm về bản
chất phương pháp. Script này tách bạch hai nguyên nhân:

1. `bm25_rank_normalization` — bitmask của `ts_rank` (0 = mặc định, không chuẩn
   hoá; 1 = chia 1+log(len); 2 = chia len; 4 = mean harmonic distance;
   32 = rank/(rank+1); 33 = 1|32).
2. `bm25_strip_stopwords` — bỏ hư từ tiếng Việt khỏi truy vấn.

KHÔNG thêm thư viện tách từ (pyvi/underthesea) ở vòng này: hai biến trên rẻ hơn
nhiều bậc và phải chứng minh là không đủ trước đã.

Chỉ đọc DB (`dense_topk=0` nên không gọi OpenRouter) — chạy bao nhiêu lần cũng $0.

    python -m scripts.sweep_bm25
"""

from eval.run import _METRIC_FNS, _load_golden_qa, _run_items, overlay_settings
from src.services.db import get_engine
from src.services.embedding import EmbeddingClient
from src.services.retrieval import Retriever

NORMALIZATIONS = (0, 1, 2, 4, 33)
_KEYS = ("recall@5", "mrr@5", "ndcg@5", "recall@10")


def _do(norm: int, loc: bool) -> dict:
    s = overlay_settings(
        {
            "retrieve_bm25_topk": 20,
            "retrieve_dense_topk": 0,
            "retrieve_final_topk": 10,
            "bm25_rank_normalization": norm,
            "bm25_strip_stopwords": loc,
        }
    )
    # embedder chỉ dùng để lọc `embedding_model` trong SQL — dense_topk=0 nên
    # không có lệnh gọi API nào.
    e = EmbeddingClient(
        api_key="", base_url=s.openrouter_base_url,
        model=s.openrouter_embedding_model_name, dim=s.openrouter_embedding_dim,
    )
    per_item, n_ok = _run_items(Retriever(get_engine(), e, s), _load_golden_qa(s), s)
    ok = [it for it in per_item if "error" not in it]
    return {k: round(sum(it[k] for it in ok) / n_ok, 4) for k in _METRIC_FNS} | {"n_ok": n_ok}


def render() -> str:
    lines = [
        "| normalization | lọc hư từ | Recall@5 | MRR@5 | nDCG@5 | Recall@10 |",
        "|---|---|---|---|---|---|",
    ]
    for norm in NORMALIZATIONS:
        for loc in (False, True):
            m = _do(norm, loc)
            lines.append(
                f"| {norm} | {'có' if loc else 'không'} | "
                + " | ".join(str(m[k]) for k in _KEYS)
                + " |"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    print(render())
