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

import re
import unicodedata
from collections import defaultdict

from sqlalchemy import Engine, text

from src.config import Settings
from src.services.embedding import EmbeddingClient

# Hư từ tiếng Việt — danh sách nhỏ, tự viết, CHỈ áp lên truy vấn (corpus không
# đụng tới). Viết KHÔNG DẤU vì so khớp sau khi bỏ dấu, giống `unaccent()` của
# Postgres. Cố ý BỎ QUA những từ mà bản không dấu đụng độ với từ nội dung pháp
# lý ("tai" ← tại/tài sản, "trong" ← trong/trọng tài, "ban" ← bạn/văn bản,
# "can" ← cần/căn cứ, "the" ← thế/có thể, "hoi" ← hỏi/hội đồng, "dang" ←
# đang/đăng ký, "boi" ← bởi/chửi bới): lọc nhầm chúng là mất từ khoá thật.
HU_TU = frozenset(
    "a bao cac cho chua co cua cung da duoc em gi hay hoac khi khong la luon ma"
    " minh mot muon nay nen neu nhe nhieu nhung phai rat roi sao se thi toi vay"
    " ve voi xin".split()
)

_TU = re.compile(r"\w+", re.UNICODE)


def _bo_dau(s: str) -> str:
    """'Nếu' → 'neu', 'Điều' → 'dieu'. `đ` không phải ký tự tổ hợp nên NFD không
    tách được — phải thay tay, đúng như `unaccent.rules` của Postgres làm."""
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def loc_hu_tu(q: str) -> str:
    r"""Bỏ hư từ khỏi truy vấn. Giữ số hiệu Điều/Khoản — `\w` bao cả chữ số.

    Truy vấn TOÀN hư từ thì trả nguyên câu: chuỗi rỗng cho tsquery rỗng, tức
    bm25 trả [] cho một câu hỏi thật — thà xếp hạng tệ còn hơn im lặng trả rỗng.
    """
    giu = [w for w in _TU.findall(q) if _bo_dau(w).lower() not in HU_TU]
    return " ".join(giu) or q


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


def chuan_linh_vuc(s: str | None) -> str:
    """`rewrite_query.v2` trả mã snake ("lao_dong"); `documents.linh_vuc` là nhãn
    có dấu từ metadata.parquet ("Lao động"). So bằng cùng một khuôn: bỏ dấu,
    thường hoá, khoảng trắng/gạch → `_`.
    # ponytail: so bằng chuẩn hoá chuỗi; nhãn DB dạng "Hôn nhân và gia đình" sẽ
    # không khớp "hon_nhan_gia_dinh" — thêm bảng ánh xạ khi đo được ca lệch."""
    if not s:
        return ""
    return "_".join(_bo_dau(s).lower().replace("-", " ").split())


def cong_diem_linh_vuc(
    provision_ids: list[int], linh_vuc_cua: dict[int, str | None], linh_vuc: str | None, bonus: float
) -> list[int]:
    """Spec 2026-09-06 §6 — sau RRF, KHÔNG loại ai. `provision_ids` chỉ có thứ
    tự, không có điểm, nên điểm dựng lại từ vị trí: 1/(hạng+1); cộng `bonus`
    cho provision cùng lĩnh vực; `sorted` ổn định nên bằng điểm giữ thứ tự cũ."""
    if not linh_vuc or bonus <= 0:
        return list(provision_ids)
    muc = chuan_linh_vuc(linh_vuc)
    diem = {
        pid: 1.0 / (hang + 1) + (bonus if chuan_linh_vuc(linh_vuc_cua.get(pid)) == muc else 0.0)
        for hang, pid in enumerate(provision_ids)
    }
    return sorted(provision_ids, key=lambda pid: -diem[pid])


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
        # `ts_rank` gọi không có tham số normalization = mặc định 0 = KHÔNG chuẩn
        # hoá theo độ dài tài liệu → top-k toàn chunk dài (đo được: trung bình
        # 695 token trong khi corpus trung bình 269). Nay lấy từ Settings, giá
        # trị mặc định chọn theo bảng đo, không đoán. Cùng lý do đó:
        # `bm25_strip_stopwords` bỏ hư từ khỏi truy vấn. Hai biến ĐỘC LẬP để đo
        # tách bạch được — xem `eval/results/report.md`.
        topk = topk or self.s.retrieve_bm25_topk
        if self.s.bm25_strip_stopwords:
            q = loc_hu_tu(q)
        with self.engine.connect() as c:
            rows = c.execute(
                text(
                    "WITH q AS ("
                    "  SELECT replace(plainto_tsquery('simple', unaccent(:q))::text, '&', '|')::tsquery AS tq"
                    ") SELECT c.id FROM chunks c, q"
                    " WHERE c.embedding_model = :m"
                    "   AND q.tq::text <> ''"
                    "   AND c.tsv @@ q.tq"
                    " ORDER BY ts_rank(c.tsv, q.tq, CAST(:norm AS integer)) DESC"
                    " LIMIT :k"
                ),
                {"q": q, "k": topk, "m": self.embedder.model, "norm": self.s.bm25_rank_normalization},
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

    def linh_vuc_cua(self, provision_ids: list[int]) -> dict[int, str | None]:
        """`provisions.id → documents.linh_vuc` (migration 018) cho tập ứng viên."""
        if not provision_ids:
            return {}
        with self.engine.connect() as c:
            rows = c.execute(
                text(
                    "SELECT p.id, d.linh_vuc FROM provisions p"
                    " JOIN documents d ON d.id = p.document_id WHERE p.id = ANY(:ids)"
                ),
                {"ids": provision_ids},
            ).all()
        return dict(rows)

    def hybrid_provisions(self, q: str) -> list[int]:
        """Như .hybrid() nhưng trả provisions.id — xem .provision_ids()."""
        return self.provision_ids(self.hybrid(q))
