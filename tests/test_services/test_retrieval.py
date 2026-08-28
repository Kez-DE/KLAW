import httpx
import pytest
from sqlalchemy import text

from src.config import Settings
from src.services.db import get_engine
from src.services.embedding import EmbeddingClient
from src.services.retrieval import Retriever, _dedup_giu_hang_tot_nhat, rrf


def test_rrf_item_dung_dau_ca_hai_nhanh_thang():
    out = rrf([[1, 2, 3], [1, 3, 2]], k=60)
    assert out[0][0] == 1


def test_rrf_hop_nhat_item_chi_xuat_hien_o_mot_nhanh():
    out = rrf([[1, 2], [3, 4]], k=60)
    assert {i for i, _ in out} == {1, 2, 3, 4}


def test_rrf_diem_dung_cong_thuc_1_tren_k_cong_rank():
    out = dict(rrf([[7]], k=60))
    assert abs(out[7] - 1 / 61) < 1e-9, "rank bắt đầu từ 1, không từ 0"


def test_rrf_sap_giam_dan_theo_diem():
    out = rrf([[1, 2, 3], [2, 1, 3]], k=60)
    assert [s for _, s in out] == sorted((s for _, s in out), reverse=True)


def test_rrf_nhanh_rong_khong_lam_no():
    assert rrf([[], [1]], k=60)[0][0] == 1


def test_rrf_k_lon_lam_khoang_cach_diem_hep_lai():
    gan = dict(rrf([[1, 2]], k=1000))
    xa = dict(rrf([[1, 2]], k=1))
    assert (gan[1] - gan[2]) < (xa[1] - xa[2])


# ---------------------------------------------------------------------------
# Retriever — hàm thuần & xử lý lỗi, KHÔNG cần DB (bm25/dense bị monkeypatch
# hoặc lỗi được ném ra trước khi engine từng được chạm tới).
# ---------------------------------------------------------------------------


def _settings(**overrides) -> Settings:
    return Settings(
        retrieve_bm25_topk=20,
        retrieve_dense_topk=20,
        rrf_k=60,
        retrieve_final_topk=10,
        **overrides,
    )


def _embedder_loi(status: int = 500) -> EmbeddingClient:
    """EmbeddingClient thật, transport giả luôn trả lỗi — tái dùng logic retry
    đã được test_embedding.py kiểm rồi, không viết lại."""

    def h(_req):
        return httpx.Response(status, text="server error")

    c = EmbeddingClient(api_key="k", base_url="https://x/api/v1", model="retrieval-test", dim=4)
    c._http = httpx.Client(transport=httpx.MockTransport(h))
    c.retry_backoff_base = 0
    return c


def test_dense_khong_nuot_loi_embedding():
    r = Retriever(engine=None, embedder=_embedder_loi(), settings=_settings())
    with pytest.raises(httpx.HTTPStatusError):
        r.dense("truy vấn")


def test_hybrid_khong_nuot_loi_tu_nhanh_dense():
    r = Retriever(engine=None, embedder=_embedder_loi(), settings=_settings())
    r.bm25 = lambda q, topk=None: [1, 2, 3]  # bỏ qua DB, nhánh bm25 không phải điểm cần test
    with pytest.raises(httpx.HTTPStatusError):
        r.hybrid("truy vấn")


def test_hybrid_dung_duoc_khi_bm25_rong():
    r = Retriever(engine=None, embedder=None, settings=_settings())
    r.bm25 = lambda q, topk=None: []
    r.dense = lambda q, topk=None: [5, 6, 7]
    assert r.hybrid("toàn stopword") == [5, 6, 7]


def test_hybrid_hop_nhat_hai_nhanh_theo_rrf():
    r = Retriever(engine=None, embedder=None, settings=_settings())
    r.bm25 = lambda q, topk=None: [1, 2, 3]
    r.dense = lambda q, topk=None: [2, 1, 3]
    ky_vong = [cid for cid, _ in rrf([[1, 2, 3], [2, 1, 3]], k=60)]
    assert r.hybrid("q") == ky_vong


# ---------------------------------------------------------------------------
# hybrid_provisions — khử trùng, giữ thứ tự rank (hàm thuần, không cần DB)
# ---------------------------------------------------------------------------


def test_provision_ids_rong_khong_cham_db():
    # engine=None: nếu code chạm DB trên input rỗng, test này sẽ nổ AttributeError
    r = Retriever(engine=None, embedder=None, settings=_settings())
    assert r.provision_ids([]) == []


def test_dedup_provision_giu_hang_cua_chunk_tot_nhat_khong_lap():
    # chunk 10 (hạng 1) và chunk 20 (hạng 2) cùng thuộc provision 5;
    # chunk 30 (hạng 3) thuộc provision 7 → provision 5 phải đứng trước 7,
    # và 5 chỉ xuất hiện một lần dù có hai chunk.
    out = _dedup_giu_hang_tot_nhat([10, 20, 30], {10: 5, 20: 5, 30: 7})
    assert out == [5, 7]


# ---------------------------------------------------------------------------
# Integration — cần Postgres thật đang chạy. Chèn vài dòng chunks rồi dọn.
# EmbeddingClient dùng transport giả (không gọi OpenRouter thật, không tốn tiền).
# ---------------------------------------------------------------------------


def _embedder_gia(vectors: dict[str, list[float]]) -> EmbeddingClient:
    import json

    def h(req):
        body = json.loads(req.content)
        texts = body["input"]
        data = [{"index": i, "embedding": vectors[t]} for i, t in enumerate(texts)]
        return httpx.Response(200, json={"data": data})

    c = EmbeddingClient(api_key="k", base_url="https://x/api/v1", model="retrieval-test", dim=1024)
    c._http = httpx.Client(transport=httpx.MockTransport(h))
    return c


def _vec(index_mot: int) -> list[float]:
    v = [0.0] * 1024
    v[index_mot] = 1.0
    return v


@pytest.fixture
def hai_provisions():
    eng = get_engine()
    with eng.connect() as c:
        rows = c.execute(text("SELECT id FROM provisions LIMIT 2")).all()
    return [r[0] for r in rows]


@pytest.fixture
def chunks_that(hai_provisions):
    """Chèn 3 chunk thật vào DB (2 chunk cùng provision đầu, 1 chunk provision
    thứ hai), dọn sạch sau khi test xong dù test có fail."""
    p1, p2 = hai_provisions
    eng = get_engine()
    rows = [
        (p1, "thời gian thử việc tối đa theo quy định", _vec(0), "retrieval-test"),
        (p1, "một nội dung khác không liên quan đến từ khóa", _vec(1), "retrieval-test"),
        (p2, "chấm dứt hợp đồng lao động trước thời hạn", _vec(2), "retrieval-test"),
        (
            p2,
            "người lao động đơn phương chấm dứt hợp đồng lao động phải báo trước ít nhất 45 ngày",
            _vec(3),
            "retrieval-test",
        ),
    ]
    ids: list[int] = []
    with eng.begin() as c:
        for provision_id, noi_dung, vec, model in rows:
            cid = c.execute(
                text(
                    "INSERT INTO chunks (provision_id, noi_dung_embed, embedding, embedding_model, embedding_dim)"
                    " VALUES (:p, :n, CAST(:v AS vector), :m, 1024) RETURNING id"
                ),
                {"p": provision_id, "n": noi_dung, "v": str(vec), "m": model},
            ).scalar_one()
            ids.append(cid)
    try:
        yield {"ids": ids, "p1": p1, "p2": p2}
    finally:
        with eng.begin() as c:
            c.execute(text("DELETE FROM chunks WHERE id = ANY(:ids)"), {"ids": ids})


@pytest.mark.integration
def test_bm25_khop_tsv_va_loc_theo_embedding_model(chunks_that):
    settings = _settings()
    embedder = _embedder_gia({})
    r = Retriever(engine=get_engine(), embedder=embedder, settings=settings)
    out = r.bm25("thu viec")
    assert out[0] == chunks_that["ids"][0]
    assert chunks_that["ids"][1] not in out


@pytest.mark.integration
def test_bm25_khong_tra_chunk_cua_embedding_model_khac(chunks_that):
    """Nhiều bộ embedding cùng tồn tại trong `chunks` khi ablation — bm25 lọc
    theo embedding_model của chính Retriever, không được rò rỉ chunk của bộ khác."""
    settings = _settings()
    embedder_khac = _embedder_gia({})
    embedder_khac.model = "mot-model-khac-khong-ton-tai"
    r = Retriever(engine=get_engine(), embedder=embedder_khac, settings=settings)
    assert r.bm25("thu viec") == []


@pytest.mark.integration
def test_bm25_cau_hoi_tu_nhien_khop_dieu_luat_qua_or_khong_and(chunks_that):
    """plainto_tsquery mặc định AND toàn bộ lexeme — một câu hỏi tự nhiên gần
    như không bao giờ chứa đủ MỌI từ của điều luật, nên bm25() luôn rỗng với
    truy vấn thật và hybrid() thoái hoá thành dense thuần. Phải chuyển sang OR
    (ts_rank lo xếp hạng) để câu hỏi tự nhiên khớp được điều luật thật."""
    ids = chunks_that["ids"]
    r = Retriever(engine=get_engine(), embedder=_embedder_gia({}), settings=_settings())
    out = r.bm25("nghỉ việc thì phải báo trước bao nhiêu ngày")
    assert ids[3] in out


@pytest.mark.integration
def test_bm25_xep_hang_chunk_khop_nhieu_lexeme_hon_len_truoc(chunks_that):
    ids = chunks_that["ids"]
    r = Retriever(engine=get_engine(), embedder=_embedder_gia({}), settings=_settings())
    out = r.bm25("báo trước ít nhất 45 ngày chấm dứt hợp đồng lao động")
    # ids[3] khớp gần hết lexeme của truy vấn; ids[2] chỉ khớp một phần
    assert ids[2] in out and ids[3] in out
    assert out.index(ids[3]) < out.index(ids[2])


@pytest.mark.integration
def test_bm25_truy_van_khong_sinh_lexeme_tra_ve_rong_khong_exception(chunks_that):
    r = Retriever(engine=get_engine(), embedder=_embedder_gia({}), settings=_settings())
    assert r.bm25("!!!???...") == []
    assert r.bm25("") == []


@pytest.mark.integration
def test_dense_xep_hang_theo_khoang_cach_cosine(chunks_that):
    ids = chunks_that["ids"]
    settings = _settings()
    # vector truy vấn trùng khớp tuyệt đối với chunk thứ hai (_vec(1))
    embedder = _embedder_gia({"q": _vec(1)})
    r = Retriever(engine=get_engine(), embedder=embedder, settings=settings)
    out = r.dense("q")
    assert out[0] == ids[1]


@pytest.mark.integration
def test_hybrid_dung_ket_qua_dense_khi_bm25_that_su_rong(chunks_that):
    """Truy vấn không khớp tsv chunk nào (bm25 rỗng thật trên DB thật), nhưng
    dense vẫn tìm ra — hybrid không được vỡ theo Yêu cầu #2. Chuỗi vô nghĩa,
    không lexeme nào của nó trùng bất kỳ chunk nào (kể cả từng từ rời sau khi
    bm25 chuyển sang OR — khác "tu_khoa_..." lúc trước, "khoa" trong đó vô tình
    trùng chunk[1])."""
    ids = chunks_that["ids"]
    settings = _settings()
    embedder = _embedder_gia({"zzzxxxqqq wwwyyykkk": _vec(2)})
    r = Retriever(engine=get_engine(), embedder=embedder, settings=settings)
    assert r.bm25("zzzxxxqqq wwwyyykkk") == []
    out = r.hybrid("zzzxxxqqq wwwyyykkk")
    assert ids[2] in out


@pytest.mark.integration
def test_provision_ids_dung_cho_ca_nhanh_don_bm25_only_dense_only(chunks_that):
    """Task 9 (eval) dùng .provision_ids() trực tiếp trên chunk_ids của MỘT
    nhánh (bm25 hoặc dense khi nhánh kia bị tắt topk=0) — không chỉ qua
    .hybrid(). Phải khử trùng + giữ thứ tự rank giống hệt hybrid_provisions."""
    ids = chunks_that["ids"]
    p1, p2 = chunks_that["p1"], chunks_that["p2"]
    r = Retriever(engine=get_engine(), embedder=_embedder_gia({}), settings=_settings())
    out = r.provision_ids([ids[0], ids[1], ids[2]])
    assert out == [p1, p2]


@pytest.mark.integration
def test_hybrid_provisions_khu_trung_giu_thu_tu_rank_tren_db_that(chunks_that):
    ids = chunks_that["ids"]
    p1, p2 = chunks_that["p1"], chunks_that["p2"]
    settings = _settings()
    # vector truy vấn trùng chunk[0] (provision p1) hơn chunk[2] (provision p2)
    embedder = _embedder_gia({"q": _vec(0)})
    r = Retriever(engine=get_engine(), embedder=embedder, settings=settings)
    r.bm25 = lambda q, topk=None: [ids[0], ids[1], ids[2]]  # cả 2 chunk của p1 đứng trước p2
    out = r.hybrid_provisions("q")
    assert out == [p1, p2], "p1 phải xuất hiện đúng một lần, đứng trước p2"


# ---------------------------------------------------------------------------
# H1 (review-final-p2) — 'simple' không có stopword list tiếng Việt nên mọi hư
# từ thành lexeme; nối OR biến truy hồi thành xếp hạng gần như cả corpus.
# ---------------------------------------------------------------------------


def test_loc_hu_tu_bo_hu_tu_giu_tu_noi_dung():
    from src.services.retrieval import loc_hu_tu

    ra = loc_hu_tu("Nếu sếp em cứ chửi bới, xúc phạm em trước mặt mọi người thì có được không ạ?")
    con = set(ra.split())
    assert {"sếp", "chửi", "xúc", "phạm"} <= con, "từ nội dung bị bỏ nhầm"
    assert con.isdisjoint({"Nếu", "em", "thì", "có", "được", "không", "ạ"})


def test_loc_hu_tu_giu_so_hieu_dieu_khoan():
    from src.services.retrieval import loc_hu_tu

    assert "35" in loc_hu_tu("khoản 2 Điều 35 của Bộ luật Lao động").split()


def test_loc_hu_tu_truy_van_toan_hu_tu_giu_nguyen_khong_tra_rong():
    """Rỗng → tsquery rỗng → bm25 trả [] cho một câu hỏi thật. Thà xếp hạng tệ."""
    from src.services.retrieval import loc_hu_tu

    assert loc_hu_tu("có được không ạ") == "có được không ạ"


def test_settings_co_tham_so_normalization_cho_ts_rank():
    from src.config import Settings

    assert Settings(_env_file=None, bm25_rank_normalization=2).bm25_rank_normalization == 2


@pytest.mark.integration
def test_normalization_do_dai_lam_top10_bot_thien_lech_ve_chunk_dai():
    """`ts_rank` mặc định normalization=0 = KHÔNG chuẩn hoá độ dài → top-k toàn
    chunk dài. Chuẩn hoá (2 = chia độ dài) phải kéo độ dài trung bình xuống."""
    q = "Nếu sếp em cứ chửi bới, xúc phạm em trước mặt mọi người thì có được không ạ?"
    e = EmbeddingClient(api_key="k", base_url="https://x/api/v1", model="baai/bge-m3", dim=1024)

    def _dai_tb(norm: int) -> float:
        s = _settings(bm25_rank_normalization=norm, bm25_strip_stopwords=False)
        ids = Retriever(get_engine(), e, s).bm25(q, topk=10)
        with get_engine().connect() as c:
            n = c.execute(
                text("SELECT avg(token_count) FROM chunks WHERE id = ANY(:ids)"), {"ids": ids}
            ).scalar_one()
        return float(n)

    assert _dai_tb(2) < _dai_tb(0)
