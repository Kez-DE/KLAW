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
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration

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
