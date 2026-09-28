"""Test scripts/build_chunks.py.

CHI PHÍ: ba test đầu **$0** — thứ chúng kiểm là logic DELETE+INSERT và ràng buộc
DB, không phải chất lượng embedding, nên chúng chạy trên một tập con nhỏ với
embedder giả. Chỉ `test_run_that_tren_toan_corpus_TON_TIEN` gọi API thật.

Trước đây cả ba test đều gọi `run()` thật: mỗi lần `pytest -m integration` là
~$0,027 embed lại toàn corpus, âm thầm, không ai báo.
"""

import pytest
from sqlalchemy import text

from scripts import build_chunks as bc
from scripts.build_chunks import run
from src.services.db import get_engine

# Model sentinel: `run()` xoá theo `WHERE embedding_model = :m`, nên tên giả giữ
# cho test KHÔNG bao giờ chạm vào bộ `baai/bge-m3` / `voyageai/voyage-4-lite` thật.
_MODEL_GIA = "test-subset"
_DIM = 1024


@pytest.fixture
def corpus_nho(monkeypatch):
    """300 provision đầu + embedder giả → `run()` chạy hết đường ống, $0."""
    that = bc.load_provisions
    monkeypatch.setattr(bc, "load_provisions", lambda e: that(e)[:300])

    class EmbedderGia:
        def __init__(self, **kw) -> None:
            self.dim = kw.get("dim", _DIM)
            self.batch = 0

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.1] * self.dim for _ in texts]

    monkeypatch.setattr(bc, "EmbeddingClient", EmbedderGia)
    yield _MODEL_GIA
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM chunks WHERE embedding_model = :m"), {"m": _MODEL_GIA})


def _dem(model: str) -> int:
    with get_engine().connect() as c:
        return c.execute(
            text("SELECT count(*) FROM chunks WHERE embedding_model = :m"), {"m": model}
        ).scalar_one()


@pytest.mark.integration
def test_dry_run_khong_ghi_gi_va_bao_so_chunk():
    with get_engine().connect() as c:
        before = c.execute(text("SELECT count(*) FROM chunks")).scalar_one()
    r = run(dry_run=True)
    with get_engine().connect() as c:
        after = c.execute(text("SELECT count(*) FROM chunks")).scalar_one()
    assert before == after
    assert r["chunks"] > 0


@pytest.mark.integration
def test_chay_lai_cung_model_thi_thay_the_khong_nhan_doi(corpus_nho):
    run(model=corpus_nho)
    n1 = _dem(corpus_nho)
    run(model=corpus_nho)
    n2 = _dem(corpus_nho)
    assert n1 > 0
    assert n1 == n2, "chạy lại phải DELETE bộ cũ rồi ghi lại, không cộng dồn"


@pytest.mark.integration
def test_moi_chunk_co_provision_id_ton_tai_va_co_embedding(corpus_nho):
    run(model=corpus_nho)
    with get_engine().connect() as c:
        orphan = c.execute(text(
            "SELECT count(*) FROM chunks ch"
            " WHERE NOT EXISTS (SELECT 1 FROM provisions p WHERE p.id = ch.provision_id)"
        )).scalar_one()
        thieu = c.execute(text(
            "SELECT count(*) FROM chunks WHERE embedding IS NULL AND embedding_model = :m"
        ), {"m": corpus_nho}).scalar_one()
    assert orphan == 0
    assert thieu == 0, "có chunk không có vector — embed thất bại mà không báo"


@pytest.mark.integration
def test_chi_moi_chi_embed_chunk_chua_co_va_xoa_chunk_thua(corpus_nho, monkeypatch):
    """Nạp thêm văn bản không được embed lại cả corpus: chunk cũ giữ nguyên id
    và vector (số đo trước/sau vẫn so được), chỉ chunk chưa có mới gọi API, và
    chunk không còn khớp chunker (vd `mo_dau` của hàng vừa lên deep) bị xoá."""
    run(model=corpus_nho)
    with get_engine().begin() as c:
        ids = sorted(r[0] for r in c.execute(
            text("SELECT id FROM chunks WHERE embedding_model = :m"), {"m": corpus_nho}))
        c.execute(text("DELETE FROM chunks WHERE id = :i"), {"i": ids[0]})
        c.execute(text(
            "INSERT INTO chunks (provision_id, noi_dung_embed, embedding_model, embedding_dim)"
            " SELECT provision_id, '__thua__', embedding_model, embedding_dim FROM chunks"
            " WHERE id = :i"), {"i": ids[1]})

    goi: list[int] = []

    class EmbedderDem:
        def __init__(self, **kw) -> None:
            self.dim = kw.get("dim", _DIM)
            self.batch = 0

        def embed(self, texts: list[str]) -> list[list[float]]:
            goi.append(len(texts))
            return [[0.2] * self.dim for _ in texts]

    monkeypatch.setattr(bc, "EmbeddingClient", EmbedderDem)
    info = run(model=corpus_nho, chi_moi=True)

    assert (info["moi"], info["thua"]) == (1, 1), info
    assert sum(goi) == 1, "chỉ chunk vừa thiếu mới được embed"
    with get_engine().connect() as c:
        sau = {r[0] for r in c.execute(
            text("SELECT id FROM chunks WHERE embedding_model = :m"), {"m": corpus_nho})}
        thua = c.execute(text(
            "SELECT count(*) FROM chunks WHERE embedding_model = :m AND noi_dung_embed = '__thua__'"),
            {"m": corpus_nho}).scalar_one()
    assert set(ids[1:]) <= sau, "chunk cũ bị ghi lại — id đổi"
    assert len(sau) == len(ids) and thua == 0


@pytest.mark.integration
def test_run_that_tren_toan_corpus_TON_TIEN():
    """TỐN TIỀN: embed lại TOÀN BỘ corpus qua OpenRouter — ~891.772 token,
    **~$0,009** với `baai/bge-m3` ($0,010/1M).

    Đây là test DUY NHẤT gọi API thật. Nó tồn tại vì ba test trên dùng embedder
    giả nên không chứng minh được đường ống thật (auth, kích thước lô, số vector
    trả về, chiều vector) còn chạy.

    Bỏ qua khi không cần: `pytest -m integration -k "not TON_TIEN"`.
    """
    info = run()
    assert info["chunks"] == _dem(info["model"]), "số chunk ghi vào DB lệch với số chunk dựng ra"
    with get_engine().connect() as c:
        thieu = c.execute(text(
            "SELECT count(*) FROM chunks WHERE embedding IS NULL AND embedding_model = :m"
        ), {"m": info["model"]}).scalar_one()
    assert thieu == 0
