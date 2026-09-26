"""Endpoint `/tai-lieu` chạm DB thật (spec 2026-09-15).

Bốn điều chỉ chứng minh được bằng một request thật:

1. Dữ kiện đi hết đường từ tệp tải lên tới bảng `du_kien_tai_lieu`, và mỗi dòng
   ra tới người dùng đều mang neo.
2. Ranh giới tài khoản: việc đọc của người khác là 404, không phân biệt được với
   một id không có thật.
3. Sửa một dữ kiện giữ trích gốc và đổi nhãn nguồn — FR-015 ở tầng HTTP, nơi
   người dùng thật chạm vào.
4. Bàn giao sang soạn thảo trả đúng hình dạng `POST /soan-thao` nhận.
"""

import json
import pathlib
import uuid
import zipfile
from io import BytesIO

import pytest
from sqlalchemy import text

from src.api import routes_tai_lieu as rtl
from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine, run_migrations
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer
from tests.test_services.test_dung_trang import pdf_trang

pytestmark = pytest.mark.integration

_DUNG_PDF_THAT = rtl.dung_trang.dung_pdf


@pytest.fixture(autouse=True)
def _dung_pdf_gia(monkeypatch):
    """`_docx` dưới đây là zip tối thiểu bộ đọc của KLAW nhận nhưng LibreOffice
    KHÔNG nạp được, nên dựng trang thật sẽ từ chối nó. Mọi test ở đây không
    hỏi về trang thì nhận một PDF A4 một trang; test hỏi về trang xin lại
    LibreOffice thật bằng fixture `dung_that`."""
    run_migrations("036")
    monkeypatch.setattr(rtl.dung_trang, "dung_pdf", lambda docx: pdf_trang((595.0, 842.0)))

LOAI = "hdld"
DONG_LUONG = "Lương chính thức: 20.000.000 đồng/tháng"
DONG_THU_VIEC = "Thời gian thử việc: 60 ngày"


def _docx(*dong: str) -> bytes:
    return _docx_tho("".join(f"<w:p><w:r><w:t>{d}</w:t></w:r></w:p>" for d in dong))


def _docx_tho(than: str) -> bytes:
    """DOCX với `w:body` cho sẵn — dùng khi cần bảng chứ không chỉ đoạn."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{than}</w:body></w:document>",
        )
    return buf.getvalue()


class _Usage:
    token_in, token_out, cost_usd = 10, 20, 0.0005


class _LLM:
    """Trả một dữ kiện KHỚP và một dữ kiện BỊA, để kiểm đúng cái bị loại."""

    def chat(self, model, messages, json_schema=None):
        from src.agents.nodes.gom_du_kien import truong_cua

        ra = {t["key"]: {"gia_tri": "", "trich": ""} for t in truong_cua(LOAI)}
        ra["luong_chinh_thuc"] = {"gia_tri": "20000000", "trich": DONG_LUONG}
        ra["thoi_gian_thu_viec_ngay"] = {"gia_tri": "60", "trich": "Thời gian thử việc: 99 ngày"}
        return json.dumps(ra), _Usage()


@pytest.fixture
def llm_gia(monkeypatch):
    monkeypatch.setattr(rtl.llm_svc, "from_settings", lambda: _LLM())
    monkeypatch.setattr(rtl.llm_svc, "generate_model", lambda: "gia-lap")


@pytest.fixture
def hai_nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    yield a, b
    with get_engine().begin() as c:
        for s in (a, b):
            c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": s})


async def _tai_len(client, headers, phien, tep=None, ten="hd.docx"):
    return await client.post(
        "/api/v1/tai-lieu",
        headers=headers,
        files={"tep": (ten, tep if tep is not None else _docx(DONG_LUONG, DONG_THU_VIEC))},
        data={"hoi_thoai_id": phien, "loai": LOAI},
    )


@pytest.mark.asyncio
async def test_tai_len_ra_du_kien_CO_NEO_va_loai_du_kien_BIA(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")

    r = await _tai_len(client, ha, phien)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["trang_thai"] == "xong" and d["chay_nen"] is False

    khoa = {x["khoa"] for x in d["du_kien"]}
    assert khoa == {"luong_chinh_thuc"}, "dữ kiện có trích bịa phải bị loại"
    dk = d["du_kien"][0]
    assert dk["nguon"] == "tai_lieu" and dk["trich"] == DONG_LUONG and dk["trang"] == 1


@pytest.mark.asyncio
async def test_viec_cua_nguoi_khac_la_404(client, khoa_ky, hai_nguoi, llm_gia):
    a, b = hai_nguoi
    ha, hb = _bearer(khoa_ky, a), _bearer(khoa_ky, b)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _tai_len(client, ha, phien)).json()["id"]

    assert (await client.get(f"/api/v1/tai-lieu/{viec}", headers=ha)).status_code == 200
    assert (await client.get(f"/api/v1/tai-lieu/{viec}", headers=hb)).status_code == 404


@pytest.mark.asyncio
async def test_sua_du_kien_GIU_trich_goc_va_doi_nguon(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    dk_id = (await _tai_len(client, ha, phien)).json()["du_kien"][0]["id"]

    r = await client.patch(f"/api/v1/tai-lieu/du-kien/{dk_id}", headers=ha, json={"gia_tri": "25000000"})
    assert r.status_code == 200
    d = r.json()
    assert d["gia_tri"] == "25000000"
    assert d["nguon"] == "nguoi_dung_sua"
    assert d["trich_goc"] == DONG_LUONG
    assert d["trich"] is None, "trích chứng minh giá trị CŨ, không được để cạnh giá trị mới"


@pytest.mark.asyncio
async def test_xoa_mot_du_kien_va_xoa_het_theo_hoi_thoai(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _tai_len(client, ha, phien)).json()
    dk_id = viec["du_kien"][0]["id"]

    assert (await client.delete(f"/api/v1/tai-lieu/du-kien/{dk_id}", headers=ha)).status_code == 204
    assert (await client.get(f"/api/v1/tai-lieu/{viec['id']}", headers=ha)).json()["du_kien"] == []
    assert (await client.delete(f"/api/v1/tai-lieu/hoi-thoai/{phien}", headers=ha)).status_code == 204
    assert (await client.get(f"/api/v1/tai-lieu/{viec['id']}", headers=ha)).status_code == 404


@pytest.mark.asyncio
async def test_ban_giao_sang_soan_thao(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    await _tai_len(client, ha, phien)

    r = await client.get(f"/api/v1/tai-lieu/hoi-thoai/{phien}/du-kien?loai={LOAI}", headers=ha)
    assert r.status_code == 200
    d = r.json()
    assert d["facts"] == {"luong_chinh_thuc": "20000000"}
    thieu = {t["key"] for t in d["con_thieu"]}
    assert "luong_chinh_thuc" not in thieu, "trường đã có dữ kiện không được nằm trong phần thiếu"
    assert "luong_thang" in thieu, "trường không có dữ kiện phải để trống chứ không suy đoán"


@pytest.mark.asyncio
async def test_dinh_dang_khong_ho_tro_la_422_noi_ro_dinh_dang(client, khoa_ky, hai_nguoi, llm_gia):
    """`.png` KHÔNG còn nằm ở đây — ảnh nay đọc được bằng OCR."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    r = await _tai_len(client, ha, phien, tep=b"PK\x03\x04", ten="bang-tinh.xlsx")
    assert r.status_code == 422 and "PDF" in r.json()["detail"]


@pytest.mark.asyncio
async def test_khong_dang_nhap_la_401(client, hai_nguoi):
    r = await _tai_len(client, {}, str(uuid.uuid4()))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_ghi_du_kien_vao_trang_thai_soan_thao_cua_hoi_thoai(client, khoa_ky, hai_nguoi, llm_gia):
    """FR-020 ở chỗ nó thật sự có hiệu lực: lượt trò chuyện sau đã biết tài liệu nói gì."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    await _tai_len(client, ha, phien)

    r = await client.get(f"/api/v1/tai-lieu/hoi-thoai/{phien}/du-kien?loai={LOAI}&ghi=true", headers=ha)
    assert r.status_code == 200 and r.json()["da_ghi_vao_hoi_thoai"] is True

    from src.services import hoi_thoai as ht

    st = ht.soan_thao_cua_phien(a, phien)
    assert st["loai"] == LOAI
    assert st["facts"]["luong_chinh_thuc"] == "20000000"
    assert st["du"] is False, "còn trường bắt buộc trống thì chưa đủ để soạn"


@pytest.mark.asyncio
async def test_du_kien_NGUOI_DUNG_da_nhap_KHONG_bi_tai_lieu_de_len(client, khoa_ky, hai_nguoi, llm_gia):
    """Tài liệu bổ sung vào chỗ trống, không ghi đè thứ người dùng tự khẳng định."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    await _tai_len(client, ha, phien)

    from src.services import hoi_thoai as ht

    ht.ghi_soan_thao(a, phien, {"loai": LOAI, "facts": {"luong_chinh_thuc": "31000000"}})
    await client.get(f"/api/v1/tai-lieu/hoi-thoai/{phien}/du-kien?loai={LOAI}&ghi=true", headers=ha)

    assert ht.soan_thao_cua_phien(a, phien)["facts"]["luong_chinh_thuc"] == "31000000"


@pytest.mark.asyncio
async def test_KHONG_ghi_khi_khong_yeu_cau(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    await _tai_len(client, ha, phien)

    from src.services import hoi_thoai as ht

    r = await client.get(f"/api/v1/tai-lieu/hoi-thoai/{phien}/du-kien?loai={LOAI}", headers=ha)
    assert r.json()["da_ghi_vao_hoi_thoai"] is False
    assert ht.soan_thao_cua_phien(a, phien) is None


@pytest.mark.asyncio
async def test_het_han_muc_ngay_la_429_noi_ro_con_so(client, khoa_ky, hai_nguoi, llm_gia, monkeypatch):
    """FR-004 — cổng chạy TRƯỚC khi phân tích tệp, và 429 nói được mốc mở lại."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    monkeypatch.setattr(rtl.tl, "han_muc_ngay", lambda goi: 1)

    assert (await _tai_len(client, ha, phien)).status_code == 201
    r = await _tai_len(client, ha, phien)
    assert r.status_code == 429
    assert "1/1" in r.json()["detail"] and "mở lại" in r.json()["detail"]


@pytest.mark.asyncio
async def test_tep_hong_VAN_tinh_vao_han_muc(client, khoa_ky, hai_nguoi, llm_gia, monkeypatch):
    """Không đếm tệp hỏng thì gửi tệp rác liên tục là đường vòng qua hạn mức."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    monkeypatch.setattr(rtl.tl, "han_muc_ngay", lambda goi: 1)

    assert (await _tai_len(client, ha, phien, tep=b"khong phai zip")).status_code == 422
    assert (await _tai_len(client, ha, phien)).status_code == 429


@pytest.mark.asyncio
async def test_tep_3MB_toi_duoc_bo_doc(client, khoa_ky, hai_nguoi, llm_gia):
    """Trần body 2 MB chung từng chặn mọi tệp trên 2 MB dưới giao diện hứa 20 MB
    (quyết định 2026-09-26). 422 của bộ đọc = đã qua mọi cổng kích thước."""
    a, _ = hai_nguoi
    phien = hoi_thoai.tao_phien(a, "hợp đồng")

    r = await _tai_len(client, _bearer(khoa_ky, a), phien, tep=b"x" * (3 * 1024 * 1024))
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_dau_van_ban_nhan_ra_hai_lan_gui_CUNG_mot_tep(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    id1 = (await _tai_len(client, ha, phien)).json()["id"]
    id2 = (await _tai_len(client, ha, phien)).json()["id"]

    from sqlalchemy import text as _t

    with get_engine().connect() as c:
        dau = [
            r[0]
            for r in c.execute(
                _t("SELECT dau_van_ban FROM viec_doc_tai_lieu WHERE id = ANY(CAST(:ids AS uuid[]))"),
                {"ids": [id1, id2]},
            ).all()
        ]
    assert len(set(dau)) == 1, "cùng một tệp phải cho cùng một dấu vân"


@pytest.mark.asyncio
async def test_du_kien_tu_ANH_mang_nguon_tai_lieu_ocr_va_do_tin(client, khoa_ky, hai_nguoi, monkeypatch):
    """Hạng bằng chứng đi hết đường từ tesseract tới dòng trong DB."""
    import shutil

    from src.services.doc_tai_lieu import co_ocr

    if not co_ocr() or not shutil.which("pdftoppm"):
        pytest.skip("cần tesseract + poppler")

    anh = pathlib.Path("tests/fixtures/tieng-viet-scan.png")
    if not anh.exists():
        pytest.skip("chưa dựng ảnh thử — chạy test_doc_tai_lieu_ocr.py trước")

    class _LLMAnh:
        def chat(self, model, messages, json_schema=None):
            from src.agents.nodes.gom_du_kien import truong_cua

            ra = {t["key"]: {"gia_tri": "", "trich": ""} for t in truong_cua(LOAI)}
            ra["luong_thang"] = {"gia_tri": "20000000", "trich": "Mức lương: 20.000.000 đồng/tháng"}
            return json.dumps(ra), _Usage()

    monkeypatch.setattr(rtl.llm_svc, "from_settings", lambda: _LLMAnh())
    monkeypatch.setattr(rtl.llm_svc, "generate_model", lambda: "gia-lap")

    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    r = await _tai_len(client, ha, phien, tep=anh.read_bytes(), ten="scan.png")
    assert r.status_code == 201, r.text

    dk = r.json()["du_kien"]
    assert len(dk) == 1
    assert dk[0]["nguon"] == "tai_lieu_ocr", "dữ kiện đọc từ ảnh KHÔNG được mang nhãn như chữ thật"
    assert 0 < dk[0]["do_tin"] <= 1


@pytest.mark.asyncio
async def test_TU_NHAN_RA_loai_van_ban_khong_hoi_nguoi_dung(client, khoa_ky, hai_nguoi, llm_gia):
    """Đây là chỗ KLAW thôi hỏi và bắt đầu suy luận."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    tep = _docx("HỢP ĐỒNG LAO ĐỘNG", DONG_LUONG, DONG_THU_VIEC)

    r = await client.post(
        "/api/v1/tai-lieu", headers=ha,
        files={"tep": ("hd.docx", tep)},
        data={"hoi_thoai_id": phien},   # KHÔNG gửi `loai`
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["loai"] == "hdld"
    assert d["loai_tu_doan"] is True
    assert "HỢP ĐỒNG LAO ĐỘNG" in d["loai_can_cu"], "phải nêu chỗ nó đọc được"
    assert d["trang_thai"] == "xong"


@pytest.mark.asyncio
async def test_KHONG_NHAN_RA_loai_thi_VAN_DOC_XONG_chu_khong_be_tac(client, khoa_ky, hai_nguoi, llm_gia):
    """Ca thật từ người dùng: giấy tiếp nhận thực tập, ngoài 29 loại.

    Trước 2026-09-16 đây là ngõ cụt `can_chon_loai`: người dùng phải chọn một
    trong 29 mẫu hoặc không đi tiếp được. Giờ tài liệu vẫn được đọc xong và
    biểu diễn của nó ở lại để hỏi tiếp — cái mất đi chỉ là bộ trường của một
    checklist, không phải cả tài liệu.
    """
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    tep = _docx("GIẤY TIẾP NHẬN THỰC HÀNH, THỰC TẬP", "Kính gửi: Trường Đại học Phenikaa")

    r = await client.post(
        "/api/v1/tai-lieu", headers=ha,
        files={"tep": ("bm-m05.docx", tep)},
        data={"hoi_thoai_id": phien},
    )
    assert r.status_code == 201
    d = r.json()
    assert d["trang_thai"] == "xong", "không nhận ra loại KHÔNG còn là ngõ cụt"
    assert d["loai"] is None
    assert d["du_kien"] == [], "không đoán được loại thì không được rút bừa dữ kiện"
    assert d["so_don_vi"] == 2, "đã đọc được gì thì phải nói ra số đơn vị"
    assert d["ten_tep"] == "bm-m05.docx"

    # Biểu diễn ở lại để lượt sau còn neo vào.
    dv = (await client.get(f"/api/v1/tai-lieu/{d['id']}/don-vi", headers=ha)).json()
    assert [u["noi_dung"] for u in dv["don_vi"]] == [
        "GIẤY TIẾP NHẬN THỰC HÀNH, THỰC TẬP", "Kính gửi: Trường Đại học Phenikaa"
    ]
    assert dv["ten_tep"] == "bm-m05.docx" and dv["id"] == d["id"]
    assert {u["vung"] for u in dv["don_vi"]} == {"than"}
    assert (await client.get(f"/api/v1/tai-lieu/{d['id']}", headers=ha)).json()["so_don_vi"] == 2


@pytest.mark.asyncio
async def test_don_vi_cua_NGUOI_KHAC_la_404(client, khoa_ky, hai_nguoi, llm_gia):
    a, b = hai_nguoi
    ha, hb = _bearer(khoa_ky, a), _bearer(khoa_ky, b)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _tai_len(client, ha, phien)).json()["id"]

    assert (await client.get(f"/api/v1/tai-lieu/{viec}/don-vi", headers=ha)).status_code == 200
    assert (await client.get(f"/api/v1/tai-lieu/{viec}/don-vi", headers=hb)).status_code == 404
    assert (await client.get(f"/api/v1/tai-lieu/{uuid.uuid4()}/don-vi", headers=ha)).status_code == 404


@pytest.mark.asyncio
async def test_bang_trong_docx_ra_don_vi_co_TOA_DO(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    bang = (
        "<w:tbl><w:tr>"
        "<w:tc><w:p><w:r><w:t>Tiêu chí</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>Điểm</w:t></w:r></w:p></w:tc>"
        "</w:tr></w:tbl>"
    )
    r = await _tai_len(client, ha, phien, tep=_docx_tho(bang), ten="phieu.docx")
    viec = r.json()["id"]

    dv = (await client.get(f"/api/v1/tai-lieu/{viec}/don-vi", headers=ha)).json()["don_vi"]
    assert [(u["noi_dung"], u["bang"]) for u in dv] == [("Tiêu chí", [0, 0, 0]), ("Điểm", [0, 0, 1])]


@pytest.mark.asyncio
async def test_XOA_HOI_THOAI_don_sach_bieu_dien_tai_lieu(client, khoa_ky, hai_nguoi, llm_gia):
    """Xoá MỀM cuộc hội thoại không làm cascade nổ, nên nếu không dọn tay thì
    nội dung tài liệu của bên thứ ba ở lại vô thời hạn."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _tai_len(client, ha, phien)).json()["id"]
    assert (await client.get(f"/api/v1/tai-lieu/{viec}/don-vi", headers=ha)).json()["don_vi"]

    assert (await client.delete(f"/api/v1/hoi-thoai/{phien}", headers=ha)).status_code == 204

    with get_engine().connect() as c:
        con = c.execute(
            text("SELECT count(*) FROM viec_doc_tai_lieu WHERE hoi_thoai_id = CAST(:h AS uuid)"),
            {"h": phien},
        ).scalar_one()
    assert con == 0, "xoá cuộc hội thoại phải xoá theo biểu diễn tài liệu"


@pytest.mark.asyncio
async def test_loai_NGUOI_DUNG_gui_thang_van_thang_suy_doan(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    tep = _docx("HỢP ĐỒNG LAO ĐỘNG", DONG_LUONG)

    r = await client.post(
        "/api/v1/tai-lieu", headers=ha,
        files={"tep": ("hd.docx", tep)},
        data={"hoi_thoai_id": phien, "loai": "hop_dong_thu_viec"},
    )
    assert r.json()["loai"] == "hop_dong_thu_viec"
    assert r.json()["loai_tu_doan"] is False


@pytest.mark.asyncio
async def test_tai_len_vao_phien_cua_nguoi_khac_la_404_va_khong_ghi_gi(client, khoa_ky, hai_nguoi, llm_gia):
    """Tài liệu chỉ gắn được vào cuộc hội thoại CỦA MÌNH. Mọi đường đọc và dọn
    (`don_vi_cua`, `tai_lieu_cua_hoi_thoai`, `xoa_theo_hoi_thoai`) khoá theo
    `(hoi_thoai_id, user_sub)`, nên một dòng nhét vào phiên người khác là một
    dòng không ai dọn được nữa — FR-024 hỏng im lặng."""
    a, b = hai_nguoi
    hb = _bearer(khoa_ky, b)
    phien_a = hoi_thoai.tao_phien(a, "hợp đồng")

    r = await _tai_len(client, hb, phien_a)
    assert r.status_code == 404, r.text
    with get_engine().connect() as c:
        n = c.execute(
            text("SELECT count(*) FROM viec_doc_tai_lieu WHERE hoi_thoai_id = CAST(:h AS uuid)"),
            {"h": phien_a},
        ).scalar_one()
    assert n == 0, "không được tạo việc đọc trước khi kiểm chủ phiên"


@pytest.mark.asyncio
async def test_DINH_KEM_KHONG_CAN_PHIEN_CO_SAN_may_chu_mo_ho(client, khoa_ky, hai_nguoi, llm_gia):
    """Kẹp một tệp vào đoạn chat CHƯA mở phải đi được (quyết định 2026-09-17).

    Phiên chỉ sinh ra sau câu hỏi đầu, nên đòi `hoi_thoai_id` ở đây bắt người
    dùng hỏi một câu vu vơ trước khi được đưa tờ giấy họ đang cầm — đúng ngõ cụt
    người dùng gặp: "khi upload thì lại không chat được".
    """
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)

    r = await client.post(
        "/api/v1/tai-lieu", headers=ha,
        files={"tep": ("hd.docx", _docx("HỢP ĐỒNG LAO ĐỘNG", DONG_LUONG))},
        data={},  # KHÔNG gửi `hoi_thoai_id`
    )
    assert r.status_code == 201, r.text
    phien = r.json()["hoi_thoai_id"]
    assert hoi_thoai.lay_phien(a, phien) is not None, "phiên vừa mở phải thuộc người tải lên"
    assert r.json()["trang_thai"] == "xong"


@pytest.mark.asyncio
async def test_DINH_KEM_KHONG_GOI_MO_HINH_khi_khong_ai_chon_loai(
    client, khoa_ky, hai_nguoi, monkeypatch
):
    """Đính kèm là một cử chỉ, không phải một lệnh chạy (quyết định 2026-09-17).

    Phần hiểu tài liệu xảy ra ở `hieu_tai_lieu`, trong lượt hỏi kế tiếp. Rút dữ
    kiện ngay lúc tải lên là trả tiền mô hình lần thứ hai cho cùng một tờ giấy,
    trước khi người dùng kịp nói họ muốn gì với nó.
    """
    class _No:
        def chat(self, *a, **k):
            raise AssertionError("đính kèm KHÔNG được gọi mô hình")

    monkeypatch.setattr(rtl.llm_svc, "from_settings", lambda: _No())
    monkeypatch.setattr(rtl.llm_svc, "generate_model", lambda: "gia-lap")

    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")

    r = await client.post(
        "/api/v1/tai-lieu", headers=ha,
        files={"tep": ("hd.docx", _docx("HỢP ĐỒNG LAO ĐỘNG", DONG_LUONG, DONG_THU_VIEC))},
        data={"hoi_thoai_id": phien},  # KHÔNG gửi `loai`
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["loai"] == "hdld", "vẫn tự nhận ra loại — đó là tra bảng, 0 token"
    assert d["du_kien"] == [], "chưa ai hỏi gì thì chưa rút dữ kiện nào"
    assert d["so_don_vi"] > 0, "nguyên văn vẫn phải đọc và lưu, để lượt hỏi sau dùng"


@pytest.mark.asyncio
async def test_HET_HAN_MUC_khong_de_lai_phien_ma(client, khoa_ky, hai_nguoi, llm_gia, monkeypatch):
    """Mở phiên hộ phải đứng SAU cổng hạn mức, vì nó là một lần GHI.

    `hoi_thoai.danh_sach` không lọc phiên rỗng và không có việc dọn nào cho
    chúng, nên một 429 mở phiên hộ để lại một dòng mang tên tệp nằm mãi trong
    thanh bên của người dùng.
    """
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    monkeypatch.setattr(rtl.tl, "han_muc_ngay", lambda goi: 0)
    _, truoc = hoi_thoai.danh_sach(a, 50, 0)

    r = await client.post(
        "/api/v1/tai-lieu", headers=ha,
        files={"tep": ("hd.docx", _docx("HỢP ĐỒNG LAO ĐỘNG", DONG_LUONG))},
        data={},  # KHÔNG gửi `hoi_thoai_id`
    )
    assert r.status_code == 429, r.text

    _, sau = hoi_thoai.danh_sach(a, 50, 0)
    assert sau == truoc, "hết hạn mức thì không được mở phiên nào"


@pytest.mark.asyncio
async def test_hoi_thoai_id_RONG_mo_phien_moi_chu_khong_404(client, khoa_ky, hai_nguoi, llm_gia):
    """Khoá rỗng và khoá vắng mặt phải đi cùng một đường.

    `Form(None)` chỉ trả `None` khi khoá VẮNG MẶT. Một người gọi gửi
    `hoi_thoai_id=""` (thử lại, client khác, gọi tay) mà nhận 404 là một câu trả
    lời sai về một yêu cầu hợp lệ.
    """
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)

    r = await client.post(
        "/api/v1/tai-lieu", headers=ha,
        files={"tep": ("hd.docx", _docx("HỢP ĐỒNG LAO ĐỘNG", DONG_LUONG))},
        data={"hoi_thoai_id": ""},
    )
    assert r.status_code == 201, r.text
    assert hoi_thoai.lay_phien(a, r.json()["hoi_thoai_id"]) is not None


@pytest.mark.asyncio
async def test_tai_len_loai_tong_quat_doc_XONG_khong_rut_du_kien(client, khoa_ky, hai_nguoi, llm_gia):
    """`tong_quat` KHÔNG có checklist, nên tải lên với loại đó phải ĐỌC XONG.

    Hồi quy thật, chủ dự án báo 2026-09-17: chọn "Bản thảo tổng quát" rồi tải
    tệp lên thì việc đọc bị ghi `hong`/`loi_he_thong`. `rut_du_kien` gọi
    `load_checklist_cached('tong_quat')` và `duong_dan_checklist` ném
    `ValueError: loai không có checklist`. Tệp đọc hoàn toàn bình thường — chỉ
    checklist là không tồn tại — nên hỏng ở đây là hỏng SAI CHỖ, và người dùng
    chỉ thấy "không phân tích được".

    Bản thảo tổng quát rút dữ kiện ở `hieu_tai_lieu`, không ở cửa tải lên.
    """
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    r = await client.post(
        "/api/v1/tai-lieu",
        headers=ha,
        files={"tep": ("mau.docx", _docx(DONG_LUONG, DONG_THU_VIEC))},
        data={"hoi_thoai_id": phien, "loai": "tong_quat"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["trang_thai"] == "xong", body
    assert body["loai"] == "tong_quat"
    assert body["du_kien"] == []
    assert body["chay_nen"] is False


# ═══ Ảnh đã tách — quyết định 2026-09-18, migration 035 ══════════════════════

_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IENDaE\x82"
)


def _docx_co_anh() -> bytes:
    """Biểu mẫu có LOGO trong đầu trang — đúng chỗ một logo letterhead thật
    nằm, và là ca `word/document.xml` một mình không thấy."""
    ns = " ".join(
        (
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"',
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"',
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"',
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"',
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"',
        )
    )
    rels = (
        '<?xml version="1.0"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/image" Target="media/logo.png"/></Relationships>'
    )
    anh = (
        '<w:p><w:r><w:drawing><wp:inline><wp:extent cx="1733550" cy="537039"/>'
        "<a:graphic><a:graphicData><pic:pic><pic:blipFill>"
        '<a:blip r:embed="rId1"/></pic:blipFill></pic:pic></a:graphicData></a:graphic>'
        "</wp:inline></w:drawing></w:r></w:p>"
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr(
            "word/document.xml",
            f"<w:document {ns}><w:body>"
            f"<w:p><w:r><w:t>{DONG_LUONG}</w:t></w:r></w:p>"
            f"<w:p><w:r><w:t>{DONG_THU_VIEC}</w:t></w:r></w:p>"
            "</w:body></w:document>",
        )
        z.writestr("word/header1.xml", f"<w:hdr {ns}>{anh}</w:hdr>")
        z.writestr("word/_rels/header1.xml.rels", rels)
        z.writestr("word/media/logo.png", _PNG)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_anh_tach_duoc_phat_lai_dung_bytes_va_dung_kieu(client, khoa_ky, hai_nguoi, llm_gia):
    """Logo đi hết đường: tệp tải lên → `word/media/` → bảng `anh_tai_lieu` →
    một request thật của chính chủ. Kèm hai tiêu đề an toàn: `nosniff` để
    trình duyệt không tự đoán lại kiểu và chạy nội dung tệp người lạ như
    HTML/SVG, và `private` để một proxy dùng chung không phát con dấu của
    người này cho người khác."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _tai_len(client, ha, phien, tep=_docx_co_anh(), ten="co-logo.docx")).json()["id"]

    r = await client.get(f"/api/v1/tai-lieu/{viec}/anh/logo.png", headers=ha)

    assert r.status_code == 200
    assert r.content == _PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "private" in r.headers["cache-control"]


@pytest.mark.asyncio
async def test_anh_cua_NGUOI_KHAC_la_404(client, khoa_ky, hai_nguoi, llm_gia):
    """Con dấu và chữ ký quét là dữ liệu cá nhân của BÊN THỨ BA. B biết đúng
    `viec_id` và đúng tên tệp của A — và vẫn không lấy được một byte nào; 404
    y hệt một ảnh không tồn tại, không tiết lộ rằng tài liệu đó có thật."""
    a, b = hai_nguoi
    ha, hb = _bearer(khoa_ky, a), _bearer(khoa_ky, b)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _tai_len(client, ha, phien, tep=_docx_co_anh(), ten="co-logo.docx")).json()["id"]

    assert (await client.get(f"/api/v1/tai-lieu/{viec}/anh/logo.png", headers=ha)).status_code == 200
    assert (await client.get(f"/api/v1/tai-lieu/{viec}/anh/logo.png", headers=hb)).status_code == 404
    assert (
        await client.get(f"/api/v1/tai-lieu/{uuid.uuid4()}/anh/logo.png", headers=ha)
    ).status_code == 404
    # Không đăng nhập thì 401, không phải 404 im lặng.
    assert (await client.get(f"/api/v1/tai-lieu/{viec}/anh/logo.png")).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ten",
    [
        "..%2f..%2fdocument.xml",
        "%2e%2e%2f%2e%2e%2fword%2fdocument.xml",
        "logo.png%00.txt",
        "khong-co.png",
    ],
)
async def test_ten_anh_LA_la_404_khong_doc_duoc_part_nao_khac(
    client, khoa_ky, hai_nguoi, llm_gia, ten
):
    """Endpoint chỉ nhận TÊN TỆP trần rồi tự ghép `word/media/`, nên không có
    đường nào để một tên dựng sẵn đọc ra một part khác của zip."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _tai_len(client, ha, phien, tep=_docx_co_anh(), ten="co-logo.docx")).json()["id"]

    r = await client.get(f"/api/v1/tai-lieu/{viec}/anh/{ten}", headers=ha)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_xoa_hoi_thoai_mang_CON_DAU_di_cung(client, khoa_ky, hai_nguoi, llm_gia):
    """Điều khoản đánh đổi của quyết định 2026-09-18: ảnh nằm trong Postgres
    ĐÚNG BẰNG đời cuộc hội thoại. Đo ở tầng HTTP, nơi người dùng thật bấm nút
    xoá — không chỉ ở tầng service."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _tai_len(client, ha, phien, tep=_docx_co_anh(), ten="co-logo.docx")).json()["id"]
    assert (await client.get(f"/api/v1/tai-lieu/{viec}/anh/logo.png", headers=ha)).status_code == 200

    assert (
        await client.delete(f"/api/v1/tai-lieu/hoi-thoai/{phien}", headers=ha)
    ).status_code == 204

    assert (await client.get(f"/api/v1/tai-lieu/{viec}/anh/logo.png", headers=ha)).status_code == 404
    with get_engine().connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM anh_tai_lieu WHERE viec_id = CAST(:v AS uuid)"),
                {"v": viec},
            ).scalar_one()
            == 0
        )


# ═══ Khuôn gốc — quyết định 2026-09-26, migration 036 ══════════════════════
# Tệp tải lên được giữ theo hội thoại để hiện ĐÚNG như bản tải lên; số trang là
# số trang dàn thật, trần 10; tệp đi cùng cuộc hội thoại và cùng tài khoản.

import base64  # noqa: E402
import shutil  # noqa: E402

from tests.test_services.test_dung_trang import co_png, docx_that  # noqa: E402

_KHO_MAU = pathlib.Path.home() / "giấy tờ thực tập"
_CO_SOFFICE = shutil.which("soffice") is not None
_CO_PDFTOPPM = shutil.which("pdftoppm") is not None
can_soffice = pytest.mark.skipif(not _CO_SOFFICE, reason="cần LibreOffice")
can_pdftoppm = pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")


@pytest.fixture
def dung_that(monkeypatch):
    """LibreOffice THẬT thay cho PDF giả của `_dung_pdf_gia`."""
    monkeypatch.setattr(rtl.dung_trang, "dung_pdf", _DUNG_PDF_THAT)


def _pdf_co_chu(*kho: tuple[float, float]) -> bytes:
    """PDF có LỚP CHỮ (bộ đọc không phải OCR), mỗi trang một khổ."""
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf)
    for i, k in enumerate(kho, start=1):
        c.setPageSize(k)
        c.drawString(72, k[1] - 72, f"Trang {i}: {DONG_LUONG}")
        c.showPage()
    c.save()
    return buf.getvalue()


async def _dinh_kem(client, headers, phien, tep: bytes, ten: str):
    """Đính kèm KHÔNG chọn loại — không gọi mô hình."""
    return await client.post(
        "/api/v1/tai-lieu", headers=headers, files={"tep": (ten, tep)}, data={"hoi_thoai_id": phien}
    )


def _dem(sql: str, **p) -> int:
    with get_engine().connect() as c:
        return c.execute(text(sql), p).scalar_one()


def _kiem_trang(body: dict, so_trang: int) -> None:
    """Đúng `so_trang` PNG, và cỡ từng ảnh đi theo khổ của CHÍNH trang đó."""
    assert len(body["kho"]) == len(body["trang"]) == so_trang
    for (rong, cao), anh in zip(body["kho"], body["trang"], strict=True):
        w, h = co_png(base64.b64decode(anh))
        assert abs(w - rong * 110 / 72) <= 2 and abs(h - cao * 110 / 72) <= 2


@can_soffice
@can_pdftoppm
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ten", "so_trang", "kho_dau"),
    [
        ("BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx", 2, None),
        ("Evaluation Form.docx", 4, [612.0, 792.0]),
        ("Report_instruction.docx", 3, None),
    ],
)
async def test_bieu_mau_THAT_ra_dung_so_trang_dan_that(client, khoa_ky, hai_nguoi, dung_that, ten, so_trang, kho_dau):
    """Evaluation Form đọc theo ngắt trang khai báo ra 1 trang; dàn thật là 4,
    và nó là khổ Letter — hiện ra vẫn phải là Letter."""
    tep = _KHO_MAU / ten
    if not tep.exists():
        pytest.skip("kho mẫu ngoài repo không có trên máy này")
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")

    r = await _dinh_kem(client, ha, phien, tep.read_bytes(), ten)
    assert r.status_code == 201, r.text
    assert (r.json()["so_trang"], r.json()["co_khuon_goc"]) == (so_trang, True)
    assert (await client.get(f"/api/v1/tai-lieu/{r.json()['id']}", headers=ha)).json()["so_trang"] == so_trang

    trang = await client.get(f"/api/v1/tai-lieu/{r.json()['id']}/trang", headers=ha)
    assert trang.status_code == 200, trang.text
    _kiem_trang(trang.json(), so_trang)
    if kho_dau:
        assert trang.json()["kho"][0] == kho_dau


@can_soffice
@pytest.mark.asyncio
async def test_DOCX_11_trang_bi_tu_choi_neu_10_trang_va_KHONG_tru_han_muc(
    client, khoa_ky, hai_nguoi, dung_that, monkeypatch
):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    monkeypatch.setattr(rtl.tl, "han_muc_ngay", lambda goi: 1)

    r = await _dinh_kem(client, ha, phien, docx_that(DONG_LUONG, ngat_trang=10), "dai.docx")
    assert r.status_code == 422, r.text
    assert "10 trang" in r.json()["detail"]
    assert (
        _dem(
            "SELECT count(*) FROM khuon_goc k JOIN viec_doc_tai_lieu v ON v.id = k.viec_id"
            " WHERE v.hoi_thoai_id = CAST(:h AS uuid)",
            h=phien,
        )
        == 0
    )

    r = await _dinh_kem(client, ha, phien, docx_that(DONG_LUONG, ngat_trang=9), "du.docx")
    assert r.status_code == 201, "tài liệu bị từ chối vì trần trang không được tiêu lượt của ngày"
    assert r.json()["so_trang"] == 10


@pytest.mark.asyncio
async def test_PDF_11_trang_bi_tu_choi_TRUOC_khi_doc_va_KHONG_tru_han_muc(client, khoa_ky, hai_nguoi, monkeypatch):
    """Bản scan 11 trang bị đếm trang trước khi OCR — không tốn công đọc từng
    trang cho một tài liệu sẽ bị từ chối."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    monkeypatch.setattr(rtl.tl, "han_muc_ngay", lambda goi: 1)
    doc_that = rtl.doc

    def _khong_doc(*a, **k):
        raise AssertionError("PDF vượt trần trang không được đi tới bộ đọc")

    monkeypatch.setattr(rtl, "doc", _khong_doc)
    r = await _dinh_kem(client, ha, phien, pdf_trang(*[(595.0, 842.0)] * 11), "scan.pdf")
    assert r.status_code == 422, r.text
    assert "10 trang" in r.json()["detail"]

    monkeypatch.setattr(rtl, "doc", doc_that)
    r = await _dinh_kem(client, ha, phien, _pdf_co_chu((595.0, 842.0)), "mot.pdf")
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_thieu_LibreOffice_la_503_va_KHONG_tru_han_muc(client, khoa_ky, hai_nguoi, monkeypatch):
    from src.services.doc_tai_lieu import ChuyenDoiKhongSanSang

    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    monkeypatch.setattr(rtl.tl, "han_muc_ngay", lambda goi: 1)

    def _thieu(docx):
        raise ChuyenDoiKhongSanSang("khong_co_cong_cu")

    monkeypatch.setattr(rtl.dung_trang, "dung_pdf", _thieu)
    r = await _dinh_kem(client, ha, phien, _docx(DONG_LUONG), "hd.docx")
    assert r.status_code == 503, r.text
    assert ".doc" not in r.json()["detail"].replace(".docx", ""), "câu cũ chỉ nói về .doc"

    r = await _dinh_kem(client, ha, phien, _pdf_co_chu((595.0, 842.0)), "mot.pdf")
    assert r.status_code == 201, r.text


@can_pdftoppm
@pytest.mark.asyncio
async def test_trang_cua_PDF_la_chinh_tep_giu_tung_kho(client, khoa_ky, hai_nguoi):
    """Không có LibreOffice ở đường này: PDF là khuôn gốc của chính nó."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    r = await _dinh_kem(client, ha, phien, _pdf_co_chu((595.0, 842.0), (612.0, 792.0)), "hai.pdf")
    assert (r.status_code, r.json()["so_trang"], r.json()["co_khuon_goc"]) == (201, 2, True)

    t = await client.get(f"/api/v1/tai-lieu/{r.json()['id']}/trang", headers=ha)
    assert t.status_code == 200
    assert t.json()["kho"] == [[595.0, 842.0], [612.0, 792.0]]
    _kiem_trang(t.json(), 2)
    assert t.headers["x-content-type-options"] == "nosniff"
    assert "private" in t.headers["cache-control"]


@pytest.mark.asyncio
async def test_ANH_khong_co_khuon_goc_trang_la_404(client, khoa_ky, hai_nguoi, monkeypatch):
    """Ảnh giữ đường OCR hôm nay (ngoài phạm vi quyết định): không có gì để hiện
    "như bản tải lên", nên `/trang` nói không có — giao diện lùi về bản xem HTML."""
    from src.services.doc_tai_lieu import DonViVanBan, TaiLieuDaDoc

    tl_gia = TaiLieuDaDoc(
        don_vi=[DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung=DONG_LUONG)], so_trang=1, so_ky_tu=len(DONG_LUONG)
    )
    monkeypatch.setattr(rtl, "doc", lambda ten, du_lieu: tl_gia)
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "ảnh")
    r = await _dinh_kem(client, ha, phien, b"\xff\xd8\xff\xe0", "chup.jpg")
    assert (r.status_code, r.json()["co_khuon_goc"]) == (201, False)
    assert (await client.get(f"/api/v1/tai-lieu/{r.json()['id']}/trang", headers=ha)).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("duong", ["tai_lieu_hoi_thoai", "hoi_thoai", "tai_khoan"])
async def test_khuon_goc_di_cung_hoi_thoai_va_tai_khoan(client, khoa_ky, hai_nguoi, duong):
    """Điều khoản đánh đổi của quyết định: tệp nằm trong Postgres ĐÚNG BẰNG
    đời cuộc hội thoại — cả ba đường xoá người dùng thật có."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    viec = (await _dinh_kem(client, ha, phien, _docx(DONG_LUONG), "hd.docx")).json()["id"]
    dem = "SELECT count(*) FROM khuon_goc WHERE viec_id = CAST(:v AS uuid)"
    assert _dem(dem, v=viec) == 1

    if duong == "tai_lieu_hoi_thoai":
        assert (await client.delete(f"/api/v1/tai-lieu/hoi-thoai/{phien}", headers=ha)).status_code == 204
    elif duong == "hoi_thoai":
        assert (await client.delete(f"/api/v1/hoi-thoai/{phien}", headers=ha)).status_code == 204
    else:
        with get_engine().begin() as c:
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": a})
    assert _dem(dem, v=viec) == 0


@pytest.mark.asyncio
async def test_trang_va_doc_lai_cua_NGUOI_KHAC_la_404_khong_dang_nhap_la_401(client, khoa_ky, hai_nguoi, llm_gia):
    a, b = hai_nguoi
    ha, hb = _bearer(khoa_ky, a), _bearer(khoa_ky, b)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _dinh_kem(client, ha, phien, _docx(DONG_LUONG), "hd.docx")).json()["id"]

    for id_ in (viec, str(uuid.uuid4()), "khong-phai-uuid"):
        assert (await client.get(f"/api/v1/tai-lieu/{id_}/trang", headers=hb)).status_code == 404
        r = await client.post(f"/api/v1/tai-lieu/{id_}/doc-lai", headers=hb, json={"loai": LOAI})
        assert r.status_code == 404
    assert (await client.get(f"/api/v1/tai-lieu/{viec}/trang")).status_code == 401
    assert (await client.post(f"/api/v1/tai-lieu/{viec}/doc-lai", json={"loai": LOAI})).status_code == 401
    assert (await client.get(f"/api/v1/tai-lieu/{viec}", headers=ha)).json()["du_kien"] == [], (
        "B gọi rút lại trên việc của A không được chạy gì"
    )


@pytest.mark.asyncio
async def test_DOC_LAI_rut_theo_loai_tren_CHINH_viec_da_luu_khong_tru_han_muc(
    client, khoa_ky, hai_nguoi, llm_gia, monkeypatch
):
    """Chọn loại sau khi đính kèm từng là TẢI LÊN LẠI: một việc mới và một lượt
    hạn mức mỗi lần đổi ý. Giờ tệp đã ở lại, nên rút lại chạy trên chính việc cũ."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    monkeypatch.setattr(rtl.tl, "han_muc_ngay", lambda goi: 1)
    viec = (await _dinh_kem(client, ha, phien, _docx(DONG_LUONG, DONG_THU_VIEC), "hd.docx")).json()

    for _ in range(2):  # hạn mức 1 đã dùng hết cho lần tải lên — rút lại vẫn đi
        r = await client.post(f"/api/v1/tai-lieu/{viec['id']}/doc-lai", headers=ha, json={"loai": LOAI})
        assert r.status_code == 200, r.text
    d = r.json()
    assert (d["id"], d["loai"], d["trang_thai"], d["co_khuon_goc"]) == (viec["id"], LOAI, "xong", True)
    assert {x["khoa"] for x in d["du_kien"]} == {"luong_chinh_thuc"}
    assert _dem("SELECT count(*) FROM viec_doc_tai_lieu WHERE hoi_thoai_id = CAST(:h AS uuid)", h=phien) == 1


@pytest.mark.asyncio
async def test_DOC_LAI_loai_LA_la_422_viec_chua_doc_xong_la_409(client, khoa_ky, hai_nguoi, llm_gia):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _dinh_kem(client, ha, phien, _docx(DONG_LUONG), "hd.docx")).json()["id"]
    r = await client.post(f"/api/v1/tai-lieu/{viec}/doc-lai", headers=ha, json={"loai": "../../etc"})
    assert r.status_code == 422
    assert (await client.get(f"/api/v1/tai-lieu/{viec}", headers=ha)).json()["trang_thai"] == "xong", (
        "một loại lạ không được đẩy việc đang tốt sang `hong`"
    )

    assert (await _dinh_kem(client, ha, phien, b"khong phai zip", "hong.docx")).status_code == 422
    with get_engine().connect() as c:
        hong = c.execute(
            text("SELECT id FROM viec_doc_tai_lieu WHERE hoi_thoai_id = CAST(:h AS uuid) AND trang_thai = 'hong'"),
            {"h": phien},
        ).scalar_one()
    r = await client.post(f"/api/v1/tai-lieu/{hong}/doc-lai", headers=ha, json={"loai": LOAI})
    assert r.status_code == 409


@can_soffice
@can_pdftoppm
@pytest.mark.asyncio
async def test_chuoi_BI_MAT_trong_tep_KHONG_vao_traces_luot_hoi_thoai_hay_log(
    client, khoa_ky, hai_nguoi, llm_gia, dung_that, caplog
):
    """Khuôn gốc chỉ nằm ở `khuon_goc` (FR-027): tải lên, xem trang và rút lại
    đều không để một mẩu chữ của tài liệu rơi vào traces, lượt hội thoại hay log."""
    bi_mat = f"BI-MAT-KHUON-GOC-{uuid.uuid4().hex}"
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")

    with caplog.at_level("DEBUG", logger="src"):
        r = await _dinh_kem(client, ha, phien, docx_that(DONG_LUONG, f"Bên B: {bi_mat}"), "hd.docx")
        assert r.status_code == 201, r.text
        viec = r.json()["id"]
        assert (await client.get(f"/api/v1/tai-lieu/{viec}/trang", headers=ha)).status_code == 200
        r = await client.post(f"/api/v1/tai-lieu/{viec}/doc-lai", headers=ha, json={"loai": LOAI})
        assert r.status_code == 200, r.text

    assert bi_mat not in caplog.text
    for bang in ("traces", "luot_hoi_thoai"):
        assert _dem(f"SELECT count(*) FROM {bang} t WHERE t::text LIKE :s", s=f"%{bi_mat}%") == 0, bang


@pytest.mark.asyncio
async def test_DOC_LAI_sau_lan_rut_hong_thi_xong_va_KHONG_mang_ly_do_hong_cu(client, khoa_ky, hai_nguoi, llm_gia):
    """Rút lại là THỬ LẠI được: một việc hỏng vì mô hình lỗi mà rút lại thành
    công phải ra `xong` sạch, không `xong` kèm lý do hỏng của lần trước."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    phien = hoi_thoai.tao_phien(a, "hợp đồng")
    viec = (await _dinh_kem(client, ha, phien, _docx(DONG_LUONG), "hd.docx")).json()["id"]
    rtl.tl.dat_trang_thai(get_engine(), viec, a, "hong", ly_do_hong="loi_mo_hinh")

    r = await client.post(f"/api/v1/tai-lieu/{viec}/doc-lai", headers=ha, json={"loai": LOAI})
    assert r.status_code == 200, r.text
    assert (r.json()["trang_thai"], r.json()["ly_do_hong"]) == ("xong", None)
