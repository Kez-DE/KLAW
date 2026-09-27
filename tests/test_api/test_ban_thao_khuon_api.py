"""`/ban-thao` trên khuôn gốc (P4a) — trang đã điền, tải về, lưu ô điền.

Kế hoạch `docs/plans/active/khuon-goc-dien-tai-cho.md` (API), quyết định
2026-09-26. Mọi route: người khác 404, không đăng nhập 401. Test chạy ở mọi máy
giả LibreOffice/pdftoppm và bắt đúng bytes đưa vào dựng; test mang
`can_soffice`/`can_poppler` chạy công cụ thật trên biểu mẫu thật hoặc PDF dựng.
"""

import base64
import logging
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from src.api import routes_ban_thao as rbt
from src.services import ban_thao, bao_ve, dung_trang, hoi_thoai
from src.services import tai_lieu as tl
from src.services.db import get_engine, run_migrations
from src.services.doc_tai_lieu import ChuyenDoiKhongSanSang, KhongDocDuoc, LoaiHong, doc
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer
from tests.test_services.test_ban_thao_khuon import _d, _ket, _viec
from tests.test_services.test_dung_trang import co_png, pdf_trang

pytestmark = pytest.mark.integration

_TEN = "Nguyễn Văn Ánh"
_DOCX_KIEU = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_KHO_MAU = Path.home() / "giấy tờ thực tập"
_BM_M05 = _KHO_MAU / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx"
can_soffice = pytest.mark.skipif(
    not all(shutil.which(x) for x in ("soffice", "pdftoppm", "pdftotext")), reason="cần LibreOffice + poppler"
)
can_poppler = pytest.mark.skipif(
    not all(shutil.which(x) for x in ("pdftoppm", "pdftotext")), reason="cần pdftoppm + pdftotext (poppler)"
)


@pytest.fixture
def hai_nguoi(cai_dat, khoa_ky):
    run_migrations("036")
    run_migrations("037")
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    yield a, b
    with get_engine().begin() as c:
        for s in (a, b):
            c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": s})


@pytest.fixture
def dung_gia(monkeypatch):
    """LibreOffice và pdftoppm GIẢ: ghi lại đúng bytes route đưa vào dựng."""
    vao: list[bytes] = []

    def _pdf(docx: bytes) -> bytes:
        vao.append(docx)
        return pdf_trang((595.0, 842.0))

    monkeypatch.setattr(dung_trang, "dung_pdf", _pdf)
    monkeypatch.setattr(dung_trang, "anh_trang", lambda pdf: [b"\x89PNG-gia"])
    return vao


def _chu(docx: bytes) -> str:
    return "\n".join(d.noi_dung for d in doc("x.docx", docx).don_vi)


def _pdftotext(pdf: bytes) -> str:
    return subprocess.run(
        ["pdftotext", "-", "-"], input=pdf, capture_output=True, check=True, timeout=60
    ).stdout.decode()


def _ban_thao(sub: str, phep: list | None = None) -> tuple[str, str]:
    phien = hoi_thoai.tao_phien(sub, "biểu mẫu")
    viec = _viec(sub, phien)
    bt = ban_thao.tao(sub, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec, phep or [_d(0, 0, _TEN)]))
    return bt["id"], viec


# ─────────────────────────────────────────── chi tiết, lịch sử, lưu ô điền


@pytest.mark.asyncio
async def test_chi_tiet_va_luu_o_dien_tra_khuon_va_phien_ban_moi(client, khoa_ky, hai_nguoi, caplog):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    id_, viec = _ban_thao(a)

    r = await client.get(f"/api/v1/ban-thao/{id_}", headers=ha)
    assert r.status_code == 200, r.text
    k = r.json()["khuon"]
    assert (k["viec_id"], k["dinh_dang"], k["so_trang"]) == (viec, "docx", 1)
    assert k["cho_trong"][0] == {"don_vi": 0, "so": 0, "kieu": "cham", "nhan": "Họ và tên:", "gia_tri": _TEN}

    caplog.set_level(logging.DEBUG)
    r = await client.patch(
        f"/api/v1/ban-thao/{id_}/o-dien",
        headers=ha,
        json={"phien_ban": 1, "gia_tri": [{"don_vi": 1, "cho_trong": 1, "gia_tri": "a@b.vn"}]},
    )
    assert r.status_code == 200, r.text
    moi = r.json()
    assert moi["phien_ban"] == 2 and moi["audit_report"]["sua_tay"] is True
    gia_tri = {(o["don_vi"], o["so"]): o["gia_tri"] for o in moi["khuon"]["cho_trong"]}
    assert gia_tri == {(0, 0): _TEN, (1, 0): None, (1, 1): "a@b.vn"}
    assert (await client.get(f"/api/v1/ban-thao/{id_}", headers=ha)).json()["khuon"] == moi["khuon"]

    cu = await client.get(f"/api/v1/ban-thao/{id_}/phien-ban/1", headers=ha)
    assert cu.status_code == 200 and cu.json()["khuon"]["cho_trong"][2]["gia_tri"] is None
    assert "a@b.vn" not in caplog.text and _TEN not in caplog.text


@pytest.mark.asyncio
async def test_luu_o_dien_422_voi_phien_ban_cu_gia_tri_nhieu_dong_ban_thao_HTML(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    id_, _ = _ban_thao(a)
    html = ban_thao.tao(a, hoi_thoai.tao_phien(a, "x"), ban_thao.LOAI_TONG_QUAT, {}, _ket(None, None))

    async def _luu(bt_id: str, phien_ban: int, gia_tri: str):
        return await client.patch(
            f"/api/v1/ban-thao/{bt_id}/o-dien",
            headers=ha,
            json={"phien_ban": phien_ban, "gia_tri": [{"don_vi": 0, "cho_trong": 0, "gia_tri": gia_tri}]},
        )

    for bt_id, pb, v, loi in [
        (id_, 7, "Bình", ban_thao.LOI_PHIEN_BAN_DA_DOI),
        (id_, 1, "A\nB", ban_thao.LOI_GIA_TRI_DIEN),
        (html["id"], 1, "A", ban_thao.LOI_KHONG_PHAI_KHUON),
    ]:
        r = await _luu(bt_id, pb, v)
        assert (r.status_code, r.json()["detail"]) == (422, loi)
    r = await client.patch(f"/api/v1/ban-thao/{id_}/o-dien", headers=ha, json={"phien_ban": 1, "gia_tri": []})
    assert r.status_code == 422


# ─────────────────────────────────────────────────── trang đã điền


@pytest.mark.asyncio
async def test_trang_dung_BAN_DA_DIEN_cua_dung_phien_ban(client, khoa_ky, hai_nguoi, dung_gia, caplog):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    id_, _ = _ban_thao(a)
    ban_thao.sua_o_dien(a, id_, 1, [{"don_vi": 1, "cho_trong": 1, "gia_tri": "a@b.vn"}])
    caplog.set_level(logging.DEBUG)

    r = await client.get(f"/api/v1/ban-thao/{id_}/trang", headers=ha)
    assert r.status_code == 200, r.text
    assert r.json() == {"kho": [[595.0, 842.0]], "trang": [base64.b64encode(b"\x89PNG-gia").decode()]}
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "private, no-store", "bản đang sống đổi sau mỗi lần lưu"
    assert _TEN in _chu(dung_gia[-1]) and "a@b.vn" in _chu(dung_gia[-1])

    r = await client.get(f"/api/v1/ban-thao/{id_}/trang?phien_ban=1", headers=ha)
    assert r.status_code == 200 and r.headers["cache-control"] == "private, max-age=3600"
    assert _TEN in _chu(dung_gia[-1]) and "a@b.vn" not in _chu(dung_gia[-1])
    assert len(dung_gia) == 2, "mỗi request dựng đúng một lần"

    assert (await client.get(f"/api/v1/ban-thao/{id_}/trang?phien_ban=99", headers=ha)).status_code == 404
    assert _TEN not in caplog.text and "a@b.vn" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("loi", "ma"),
    [
        (ChuyenDoiKhongSanSang("qua_tai"), 503),
        (ChuyenDoiKhongSanSang("khong_co_cong_cu"), 503),
        (KhongDocDuoc(LoaiHong.tep_hong, "x"), 422),
    ],
)
async def test_trang_loi_dung_di_qua_anh_xa_cua_tai_lieu(client, khoa_ky, hai_nguoi, monkeypatch, loi, ma):
    a, _ = hai_nguoi
    id_, _ = _ban_thao(a)

    def _hong(docx):
        raise loi

    monkeypatch.setattr(dung_trang, "dung_pdf", _hong)
    r = await client.get(f"/api/v1/ban-thao/{id_}/trang", headers=_bearer(khoa_ky, a))
    assert r.status_code == ma, r.text


@pytest.mark.asyncio
async def test_BO_AP_chay_TRONG_luot_cua_tai_khoan_o_moi_route_dung(client, khoa_ky, hai_nguoi, dung_gia, monkeypatch):
    """Bộ áp là việc CPU trên khuôn gốc tới 20 MB, và bản đang sống là `no-store`
    (trình duyệt không giữ): nó chạy TRONG lượt dựng của tài khoản, không trước
    lượt. Đang giữ lượt thì cả ba đường áp là 503 `qua_tai` và bộ áp không chạy."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    id_, _ = _ban_thao(a)
    ap: list[str] = []
    that = ban_thao.ap_phep_sua
    monkeypatch.setattr(ban_thao, "ap_phep_sua", lambda *x: (ap.append(x[0]), that(*x))[1])
    duong = [f"/api/v1/ban-thao/{id_}/{d}" for d in ("trang", "tai-xuong?dang=docx", "tai-xuong?dang=pdf")]

    with dung_trang._mot_luot(a):
        for d in duong:
            assert (await client.get(d, headers=ha)).status_code == 503, d
    assert ap == [], "không một lần áp nào ngoài lượt của tài khoản"
    for d in duong:
        assert (await client.get(d, headers=ha)).status_code == 200, d
    assert ap == ["docx"] * 3


@pytest.mark.asyncio
async def test_ban_thao_HTML_va_khuon_da_xoa_khong_co_trang(client, khoa_ky, hai_nguoi, dung_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    html = ban_thao.tao(a, hoi_thoai.tao_phien(a, "x"), ban_thao.LOAI_TONG_QUAT, {}, _ket(None, None))
    assert (await client.get(f"/api/v1/ban-thao/{html['id']}/trang", headers=ha)).status_code == 404
    id_, viec = _ban_thao(a)
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM viec_doc_tai_lieu WHERE id = CAST(:v AS uuid)"), {"v": viec})
    r = await client.get(f"/api/v1/ban-thao/{id_}", headers=ha)
    assert (r.status_code, r.json()["khuon"]) == (200, None), "bản thảo vẫn mở được như văn bản"
    assert (await client.get(f"/api/v1/ban-thao/{id_}/trang", headers=ha)).status_code == 404
    assert (await client.get(f"/api/v1/ban-thao/{id_}/tai-xuong?dang=docx", headers=ha)).status_code == 404


# ─────────────────────────────────────────────────────────── tải về


@pytest.mark.asyncio
async def test_tai_xuong_DOCX_la_khuon_goc_da_dien_ten_tep_theo_ban_tai_len(client, khoa_ky, hai_nguoi, dung_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    id_, _ = _ban_thao(a)

    r = await client.get(f"/api/v1/ban-thao/{id_}/tai-xuong?dang=docx", headers=ha)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == _DOCX_KIEU
    assert r.headers["content-disposition"] == (
        'attachment; filename="Giay tiep nhan - da dien.docx"; '
        "filename*=UTF-8''Gi%E1%BA%A5y%20ti%E1%BA%BFp%20nh%E1%BA%ADn%20-%20%C4%91%C3%A3%20%C4%91i%E1%BB%81n.docx"
    )
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "private, no-store"
    assert _TEN in _chu(r.content)

    r = await client.get(f"/api/v1/ban-thao/{id_}/tai-xuong?dang=pdf", headers=ha)
    assert (r.status_code, r.headers["content-type"]) == (200, "application/pdf")
    assert r.content == pdf_trang((595.0, 842.0)) and _TEN in _chu(dung_gia[-1])
    assert r.headers["content-disposition"].startswith('attachment; filename="Giay tiep nhan - da dien.pdf"')

    assert (await client.get(f"/api/v1/ban-thao/{id_}/tai-xuong?dang=odt", headers=ha)).status_code == 422
    assert (await client.get(f"/api/v1/ban-thao/{id_}/tai-xuong", headers=ha)).status_code == 422


@pytest.mark.parametrize(
    ("ten", "dang", "ra"),
    [
        (
            "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx",
            "docx",
            'attachment; filename="BM.M05. Giay tiep nhan thuc hanh. thuc tap (1) - da dien.docx"; '
            "filename*=UTF-8''BM.M05.%20Giay%20tiep%20nhan%20thuc%20hanh.%20thuc%20tap%20%281%29%20-%20"
            "%C4%91%C3%A3%20%C4%91i%E1%BB%81n.docx",
        ),
        (
            "Đơn cũ.doc",
            "docx",
            "attachment; filename=\"Don cu - da dien.docx\"; filename*=UTF-8''%C4%90%C6%A1n%20c%C5%A9"
            "%20-%20%C4%91%C3%A3%20%C4%91i%E1%BB%81n.docx",
        ),
        (
            '..\\x/a"b\r\n;c.pdf',
            "pdf",
            "attachment; filename=\"a_b;c - da dien.pdf\"; filename*=UTF-8''a%22b%3Bc"
            "%20-%20%C4%91%C3%A3%20%C4%91i%E1%BB%81n.pdf",
        ),
        (
            "",
            "pdf",
            "attachment; filename=\"ban-thao - da dien.pdf\"; filename*=UTF-8''ban-thao%20-%20"
            "%C4%91%C3%A3%20%C4%91i%E1%BB%81n.pdf",
        ),
    ],
    ids=["bm_m05", "doc_ve_docx", "ten_doc_hai", "rong"],
)
def test_ten_tai_ve_ASCII_du_phong_va_RFC_5987(ten, dang, ra):
    assert rbt._tai_ve_dau(ten, dang) == ra


@can_poppler
@pytest.mark.asyncio
async def test_khuon_PDF_tai_ve_PDF_da_dien_va_tu_choi_DOCX(client, khoa_ky, hai_nguoi):
    """Report_sample-like: PDF có lớp chữ, nhãn + dãy chấm. Tải lên qua API thật
    (bộ đọc ghi `hop` từng chỗ trống), điền một ô, tải về bằng bộ áp PDF."""
    from tests.test_services.test_dien_khuon_pdf import _pdf

    a, b = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "báo cáo")
    r = await client.post(
        "/api/v1/tai-lieu", headers=ha, files={"tep": ("Report_sample.pdf", _pdf())}, data={"hoi_thoai_id": phien}
    )
    assert (r.status_code, r.json()["co_khuon_goc"]) == (201, True), r.text
    viec = r.json()["id"]
    (ho_ten,) = [d for d in tl.don_vi_cua(get_engine(), viec, a) if d.noi_dung.startswith("Ho ten")]
    bt = ban_thao.tao(a, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec, [_d(ho_ten.chi_so, 0, _TEN)]))
    assert bt["khuon"]["dinh_dang"] == "pdf" and any(o["gia_tri"] == _TEN for o in bt["khuon"]["cho_trong"])

    r = await client.get(f"/api/v1/ban-thao/{bt['id']}/tai-xuong?dang=pdf", headers=ha)
    assert (r.status_code, r.headers["content-type"]) == (200, "application/pdf")
    # Lớp phủ CHE dãy chấm chứ không xoá (docstring `dien_khuon_pdf`): pdftotext
    # xen chữ cũ vào giữa các từ của giá trị, nên kiểm từng từ.
    assert all(tu in _pdftotext(r.content) for tu in _TEN.split())
    assert r.headers["content-disposition"].startswith('attachment; filename="Report_sample - da dien.pdf"')
    r = await client.get(f"/api/v1/ban-thao/{bt['id']}/tai-xuong?dang=docx", headers=ha)
    assert (r.status_code, r.json()["detail"]) == (422, rbt.LOI_PDF_KHONG_CO_DOCX)

    t = await client.get(f"/api/v1/ban-thao/{bt['id']}/trang", headers=ha)
    assert t.status_code == 200 and len(t.json()["trang"]) == 1
    assert (await client.get(f"/api/v1/ban-thao/{bt['id']}/trang", headers=_bearer(khoa_ky, b))).status_code == 404


@can_soffice
@pytest.mark.asyncio
async def test_BM_M05_THAT_trang_hai_PNG_co_gia_tri_va_tai_ve_mo_lai_duoc(client, khoa_ky, hai_nguoi, monkeypatch):
    if not _BM_M05.exists():
        pytest.skip("kho mẫu ngoài repo không có trên máy này")
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    r = await client.post(
        "/api/v1/tai-lieu",
        headers=ha,
        files={"tep": (_BM_M05.name, _BM_M05.read_bytes())},
        data={"hoi_thoai_id": phien},
    )
    assert (r.status_code, r.json()["so_trang"], r.json()["co_khuon_goc"]) == (201, 2, True), r.text
    viec = r.json()["id"]
    o = ban_thao.cho_trong_khuon("docx", _hang(viec), [])[0]
    bt = ban_thao.tao(a, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec, [_d(o["don_vi"], o["so"], _TEN)]))

    ve: list[bytes] = []
    that = dung_trang.dung_pdf

    def _giu(docx: bytes) -> bytes:
        ve.append(that(docx))
        return ve[-1]

    monkeypatch.setattr(dung_trang, "dung_pdf", _giu)
    t = await client.get(f"/api/v1/ban-thao/{bt['id']}/trang", headers=ha)
    assert t.status_code == 200, t.text
    assert len(t.json()["trang"]) == len(t.json()["kho"]) == 2
    assert all(co_png(base64.b64decode(p))[0] > 800 for p in t.json()["trang"])
    assert _TEN in _pdftotext(ve[-1]), "trang dựng từ CHÍNH bản đã điền"

    d = await client.get(f"/api/v1/ban-thao/{bt['id']}/tai-xuong?dang=docx", headers=ha)
    assert d.status_code == 200 and _TEN in _chu(d.content), "bộ đọc P2b mở lại được bản tải về"
    p = await client.get(f"/api/v1/ban-thao/{bt['id']}/tai-xuong?dang=pdf", headers=ha)
    assert p.status_code == 200 and _TEN in _pdftotext(p.content)
    assert "filename*=UTF-8''BM.M05." in d.headers["content-disposition"]


def _hang(viec: str) -> list[dict]:
    with get_engine().connect() as c:
        return c.execute(
            text("SELECT don_vi FROM viec_doc_tai_lieu WHERE id = CAST(:v AS uuid)"), {"v": viec}
        ).scalar_one()


# ─────────────────────────────────────────────────── chủ sở hữu, đăng nhập


@pytest.mark.asyncio
async def test_NGUOI_KHAC_404_va_KHONG_DANG_NHAP_401_o_moi_route(client, khoa_ky, hai_nguoi, dung_gia):
    a, b = hai_nguoi
    hb = _bearer(khoa_ky, b)
    id_, _ = _ban_thao(a)
    body = {"phien_ban": 1, "gia_tri": [{"don_vi": 0, "cho_trong": 0, "gia_tri": "X"}]}
    for method, duong, kw in [
        ("get", f"/api/v1/ban-thao/{id_}/trang", {}),
        ("get", f"/api/v1/ban-thao/{id_}/tai-xuong?dang=docx", {}),
        ("patch", f"/api/v1/ban-thao/{id_}/o-dien", {"json": body}),
    ]:
        assert (await getattr(client, method)(duong, headers=hb, **kw)).status_code == 404, duong
        assert (await getattr(client, method)(duong, **kw)).status_code == 401, duong
        la = duong.replace(id_, "khong-phai-uuid")
        assert (await getattr(client, method)(la, headers=hb, **kw)).status_code == 404, la
    assert dung_gia == [], "không một lần dựng nào cho người không phải chủ"
    assert ban_thao.chi_tiet(a, id_)["phien_ban"] == 1
