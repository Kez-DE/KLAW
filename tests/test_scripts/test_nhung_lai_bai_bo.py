"""`scripts.nhung_lai_bai_bo` — nhúng lại chunk còn mang chữ điều khoản bị bãi bỏ (quyết định
2026-09-30 mục 9(e)). $0: engine, seed và embedder đều giả; không DB, không mạng."""

from datetime import date

import pytest

from scripts import nhung_lai_bai_bo as nl


def _p(i, dd, parent=None, cap="dieu", doc="A", noi_dung=None):
    return {
        "id": i,
        "document_id": doc,
        "parent_id": parent,
        "cap": cap,
        "so_hieu_cap": "",
        "noi_dung": noi_dung or f"{dd.rsplit(' > ', 1)[-1]}. Nội dung {i}.",
        "duong_dan": f"1/2020/NĐ-CP > {dd}",
        "depth": "deep",
    }


PROV = [
    _p(1, "Điều 1"),
    _p(2, "Điều 1 > Khoản 1", 1, "khoan"),
    _p(3, "Điều 1 > Khoản 2", 1, "khoan", noi_dung="2. Chữ đã bãi bỏ."),
    _p(4, "Điều 1 > Khoản 2 > Điểm a", 3, "diem"),
    _p(5, "Điều 2"),
]
SEED = [{"van_ban_id": "A", "dieu_khoan": ["Điều 1 > Khoản 2"], "tu_ngay": date(2025, 1, 1)}]


def test_an_tu_seed_cung_luat_bai_bo_tai_va_hau_due_theo_duong_dan():
    assert nl.an_tu_seed(PROV, SEED, date(2026, 1, 1)) == {3, 4}
    assert nl.an_tu_seed(PROV, SEED, date(2024, 12, 31)) == set(), "chưa tới ngày thì còn nguyên"
    khac = [dict(p, document_id="B") for p in PROV]
    assert nl.an_tu_seed(khac, SEED, date(2026, 1, 1)) == set(), "cùng đường dẫn, văn bản khác"


class _Engine:
    """Đủ cho `run`: SELECT chunk hiện có; UPDATE ghi lại, trả rowcount 1."""

    def __init__(self, co):
        self.co, self.ghi = co, []
        test = self

        class _Conn:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                if str(sql).startswith("SELECT"):
                    return test.co
                test.ghi.append((str(sql).split()[0], params))
                return type("R", (), {"rowcount": 1})()

        self.connect = self.begin = _Conn


def _gan(monkeypatch, co, an_bang, goi):
    e = _Engine(co)

    class Embedder:
        def __init__(self, **kw):
            self.dim, self.batch = kw["dim"], 0

        def embed(self, texts):
            goi.append(texts)
            return [[0.1] * self.dim for _ in texts]

    monkeypatch.setattr(nl, "get_engine", lambda: e)
    monkeypatch.setattr(nl, "load_provisions", lambda eng: PROV)
    monkeypatch.setattr(nl, "doc_seed", lambda: SEED)
    monkeypatch.setattr(nl, "dieu_khoan_an", lambda eng, as_of: frozenset(an_bang))
    monkeypatch.setattr(nl, "EmbeddingClient", Embedder)
    return e


def _co_hien_tai():
    """Chunk đang có trong DB: dựng bởi chunker KHÔNG biết bãi bỏ."""
    return [(100 + c.provision_id, c.provision_id, c.noi_dung_embed) for c in nl.build_chunks(PROV, 1500)]


def test_dry_run_liet_ke_dung_chunk_doi_khong_goi_api_khong_ghi(monkeypatch):
    goi: list = []
    e = _gan(monkeypatch, _co_hien_tai(), {3, 4}, goi)
    info = nl.run(ghi=False)
    ((i, cu, moi),) = info["viec"]
    assert (i, cu.provision_id) == (101, 1)
    assert "Chữ đã bãi bỏ" in cu.noi_dung_embed and "Chữ đã bãi bỏ" not in moi.noi_dung_embed
    assert "Nội dung 2." in moi.noi_dung_embed and "Nội dung 4." not in moi.noi_dung_embed
    assert info["token"] == moi.token_count and info["usd"] > 0 and info["usd_tran"] >= info["usd"]
    assert info["khop_bang"] and goi == [] and e.ghi == []


def test_ghi_chi_nhung_chunk_doi_va_update_tai_cho_giu_id(monkeypatch):
    goi: list = []
    e = _gan(monkeypatch, _co_hien_tai(), {3, 4}, goi)
    info = nl.run(ghi=True)
    ((_, _, moi),) = info["viec"]
    assert goi == [[moi.noi_dung_embed]], "chỉ chunk đổi chữ mới gọi API"
    ((lenh, p),) = e.ghi
    assert lenh == "UPDATE" and (p["i"], p["t"], p["n"]) == (101, moi.noi_dung_embed, moi.token_count)
    assert "Chữ đã bãi bỏ" in p["cu"], "UPDATE chỉ khớp khi chữ cũ còn nguyên"


def test_ghi_lan_hai_khong_lam_gi(monkeypatch):
    goi: list = []
    moi = {c.provision_id: c.noi_dung_embed for c in nl.build_chunks(PROV, 1500, frozenset({3, 4}))}
    co = [(100 + p, p, moi[p]) for _, p, _ in _co_hien_tai()]
    e = _gan(monkeypatch, co, {3, 4}, goi)
    info = nl.run(ghi=True)
    assert (info["viec"], info["da_xong"]) == ([], 1) and goi == [] and e.ghi == []


def test_ghi_tu_choi_khi_bang_bai_bo_lech_seed(monkeypatch):
    """Bảng chưa nạp seed: app còn hiện Khoản 2 mà chunk đã mất chữ của nó — dừng trước khi trả tiền."""
    goi: list = []
    e = _gan(monkeypatch, _co_hien_tai(), set(), goi)
    assert nl.run(ghi=False)["khop_bang"] is False
    with pytest.raises(ValueError, match="nap_bai_bo_dieu_khoan --ghi"):
        nl.run(ghi=True)
    assert goi == [] and e.ghi == []


def test_ghi_tu_choi_khi_chunk_trong_db_lech_chunker(monkeypatch):
    goi: list = []
    e = _gan(monkeypatch, [(101, 1, "chữ lạ")], {3, 4}, goi)
    assert nl.run(ghi=False)["lech"] == [1]
    with pytest.raises(ValueError, match="lệch"):
        nl.run(ghi=True)
    assert goi == [] and e.ghi == []
