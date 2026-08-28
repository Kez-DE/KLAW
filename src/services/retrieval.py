"""Hybrid retrieval: BM25 (tsvector) ⊕ dense (pgvector) → RRF.

RRF: score(d) = Σ 1/(k + rank(d)), rank bắt đầu từ 1.
k=60 là giá trị thường dùng — CHƯA xác minh nguồn gốc, không trích trong khóa
luận cho tới khi tra được. k lớn làm khoảng cách điểm giữa các rank hẹp lại,
tức tin vào thứ hạng ít hơn.

Citation neo vào `provisions.id`, KHÔNG vào `chunks.id` (bảng `chunks` bị
DROP/CREATE lại nhiều lần khi ablation nên id của nó không ổn định). Vì vậy,
ngoài `.hybrid()` trả `chunks.id` theo đúng interface gốc, `Retriever` có
`.provision_ids(chunk_ids)` — khử trùng + giữ thứ tự rank — và `.hybrid_provisions()`
là tiện ích gọi `.provision_ids(self.hybrid(q))`. Task 9 (eval) gọi thẳng
`.provision_ids()` trên từng nhánh đơn (bm25/dense) khi nhánh kia bị tắt
(bm25_only/dense_only), để khớp kiểu với `golden_qa.yaml` (provision_ids) và
metrics Task 7 trong cả ba preset ablation, không chỉ hybrid.
"""

from collections import defaultdict

from sqlalchemy import Engine, text

from src.config import Settings
from src.services.embedding import EmbeddingClient


def rrf(rankings: list[list[int]], k: int) -> list[tuple[int, float]]:
    score: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            score[item] += 1.0 / (k + rank)
    return sorted(score.items(), key=lambda kv: kv[1], reverse=True)


def _dedup_giu_hang_tot_nhat(chunk_ids: list[int], provision_cua: dict[int, int]) -> list[int]:
    """chunk_ids đã xếp hạng → provision_ids, khử trùng, giữ hạng của chunk TỐT
    NHẤT (chunk đứng trước trong chunk_ids) cho mỗi provision.

    Điều dài bị cắt theo Khoản nên nhiều chunk có thể cùng một provision;
    provision xuất hiện đúng một lần, ở vị trí của chunk tốt nhất của nó.
    """
    seen: set[int] = set()
    out: list[int] = []
    for cid in chunk_ids:
        pid = provision_cua.get(cid)
        if pid is None or pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    return out


class Retriever:
    def __init__(self, engine: Engine, embedder: EmbeddingClient, settings: Settings) -> None:
        self.engine = engine
        self.embedder = embedder
        self.s = settings

    def bm25(self, q: str, topk: int | None = None) -> list[int]:
        # plainto_tsquery nối lexeme bằng AND — một câu hỏi tự nhiên gần như
        # không bao giờ chứa ĐỦ mọi từ của điều luật, nên AND luôn cho rỗng
        # trên truy vấn thật và làm hybrid() thoái hoá thành dense thuần.
        # Chuyển '&' → '|' (OR) và để ts_rank lo xếp hạng theo số lexeme khớp.
        # Guard `tq::text <> ''`: truy vấn không sinh lexeme (rỗng/toàn ký tự
        # lạ) cho tsquery rỗng — nối OR trên nó vẫn hợp lệ về cú pháp nhưng
        # không được khớp bừa, phải trả [] thay vì raise hay khớp mọi dòng.
        topk = topk or self.s.retrieve_bm25_topk
        with self.engine.connect() as c:
            rows = c.execute(
                text(
                    "WITH q AS ("
                    "  SELECT replace(plainto_tsquery('simple', unaccent(:q))::text, '&', '|')::tsquery AS tq"
                    ") SELECT c.id FROM chunks c, q"
                    " WHERE c.embedding_model = :m"
                    "   AND q.tq::text <> ''"
                    "   AND c.tsv @@ q.tq"
                    " ORDER BY ts_rank(c.tsv, q.tq) DESC"
                    " LIMIT :k"
                ),
                {"q": q, "k": topk, "m": self.embedder.model},
            ).all()
        return [r[0] for r in rows]

    def dense(self, q: str, topk: int | None = None) -> list[int]:
        topk = topk or self.s.retrieve_dense_topk
        # embed_query lỗi phải nổ ở đây, KHÔNG bắt — một nhánh chết âm thầm sẽ
        # làm hybrid tụt về BM25 thuần mà bảng ablation Task 9 không biết.
        vec = self.embedder.embed_query(q)
        with self.engine.connect() as c:
            rows = c.execute(
                text(
                    "SELECT id FROM chunks"
                    " WHERE embedding_model = :m AND embedding IS NOT NULL"
                    " ORDER BY embedding <=> CAST(:v AS vector)"
                    " LIMIT :k"
                ),
                {"v": str(vec), "k": topk, "m": self.embedder.model},
            ).all()
        return [r[0] for r in rows]

    def hybrid(self, q: str) -> list[int]:
        fused = rrf([self.bm25(q), self.dense(q)], k=self.s.rrf_k)
        return [cid for cid, _ in fused[: self.s.retrieve_final_topk]]

    def provision_ids(self, chunk_ids: list[int]) -> list[int]:
        """chunk_ids đã xếp hạng (từ bm25/dense/hybrid) → provisions.id, ĐÃ
        KHỬ TRÙNG, GIỮ THỨ TỰ RANK. Dùng chung cho mọi preset Task 9 — kể cả
        bm25_only/dense_only (chỉ MỘT nhánh, không qua .hybrid()) — nên vẫn
        khớp kiểu với golden_qa.provision_ids dù nhánh kia bị tắt (topk=0).

        Nhiều chunk có thể cùng một provision (Điều dài bị cắt theo Khoản);
        provision giữ thứ hạng của chunk TỐT NHẤT của nó.
        """
        if not chunk_ids:
            return []
        with self.engine.connect() as c:
            rows = c.execute(
                text("SELECT id, provision_id FROM chunks WHERE id = ANY(:ids)"),
                {"ids": chunk_ids},
            ).all()
        provision_cua = dict(rows)
        return _dedup_giu_hang_tot_nhat(chunk_ids, provision_cua)

    def hybrid_provisions(self, q: str) -> list[int]:
        """Như .hybrid() nhưng trả provisions.id — xem .provision_ids()."""
        return self.provision_ids(self.hybrid(q))
