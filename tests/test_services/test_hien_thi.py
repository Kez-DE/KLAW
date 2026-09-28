"""Quy tắc hiển thị (quyết định 2026-09-28 mục 8–10) — phần THUẦN, 0 DB, 0 LLM.

Một văn bản được hiện khi đồng thời: tình trạng Bộ Tư pháp là CHL/HHL1P, phán
quyết `effectivity` còn sống, và có link chính thống đã kiểm. Người đọc chỉ thấy
nhãn và một câu thường — không mã nội bộ, không "độ tin cậy", không ngày ISO,
không bao giờ "Chưa xác định"/"Không rõ".
"""

import re
from datetime import date

import pytest

from src.agents.nodes.assemble import ResultType, gan_van_ban_khong_hien_thi
from src.services.effectivity import Effectivity, VanBanNeu, ap_sua_doi, danh_gia
from src.services.effectivity import EffectivityVerdict as V
from src.services.hien_thi import (
    THONG_DIEP_HET,
    canh_bao,
    cau_van_ban_an,
    duoc_hien,
    hieu_luc_ra,
    mo_ta,
    thong_diep_an,
)

VBPL = "https://vbpl.vn/van-ban/chi-tiet/139264"
CP = "https://vanban.chinhphu.vn/?pageid=27160&docid=198540"
AS_OF = date(2026, 9, 28)

# Mã và chữ không bao giờ được tới mắt người đọc (mục 10 + luật "không bao giờ
# Chưa xác định/Không rõ").
_CAM = re.compile(
    r"MOJ|CHL|HHL|đồ thị|corpus|độ tin cậy|tín hiệu|chưa xác định|không rõ|\d{4}-\d{2}-\d{2}", re.IGNORECASE
)


def _vb(**kw) -> dict:
    return {"tinh_trang": "CHL", "link_vbpl": VBPL, "link_chinhphu": None} | kw


def _e(verdict, **kw) -> Effectivity:
    return Effectivity(verdict, "thap", "tình trạng MOJ = 'chua_xac_dinh' — độ tin cậy: thấp", **kw)


# ─────────────────────────────────────────────────────────── vị từ hiển thị


@pytest.mark.parametrize(
    ("van_ban", "e", "hien"),
    [
        (_vb(), _e(V.con_hieu_luc), True),
        (_vb(tinh_trang="HHL1P", link_vbpl=None, link_chinhphu=CP), _e(V.mot_phan_khong_xac_dinh), True),
        (_vb(), _e(V.chua_hieu_luc), True),
        (_vb(), _e(V.bi_sua_doi), True),
        (_vb(tinh_trang="HHL"), _e(V.het_hieu_luc), False),
        (_vb(tinh_trang="HHL"), _e(V.con_hieu_luc), False),
        (_vb(tinh_trang="chua_xac_dinh"), _e(V.con_hieu_luc), False),
        (_vb(tinh_trang="chua_hieu_luc"), _e(V.chua_hieu_luc), False),
        (_vb(), _e(V.bi_thay_the), False),
        (_vb(), _e(V.chua_xac_dinh), False),
        (_vb(), _e(V.can_doi_chieu_tay), False),
        (_vb(), None, False),
        (_vb(link_vbpl=None), _e(V.con_hieu_luc), False),
        (_vb(link_vbpl="https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=1"), _e(V.con_hieu_luc), False),
        (_vb(link_vbpl="http://vbpl.vn/van-ban/chi-tiet/1"), _e(V.con_hieu_luc), False),
    ],
    ids=[
        "CHL",
        "HHL1P-chinhphu",
        "chua_hieu_luc",
        "bi_sua_doi",
        "HHL",
        "HHL-verdict-song",
        "status-chua-xac-dinh",
        "status-chua-hieu-luc-khong-phai-ma-gateway",
        "bi_thay_the",
        "verdict-chua-xac-dinh",
        "can_doi_chieu_tay",
        "khong-phan-quyet",
        "khong-link",
        "link-mau-cu",
        "link-http",
    ],
)
def test_duoc_hien_can_du_ba_dieu_kien(van_ban, e, hien):
    assert duoc_hien(van_ban, e) is hien


# ─────────────────────────────────────────────────────────── lời cho người đọc


def test_mo_ta_theo_tung_phan_quyet():
    sua = (VanBanNeu("1", "19/2023/QH15"), VanBanNeu(None, "113/2025/QH15"))
    assert mo_ta(_e(V.mot_phan_khong_xac_dinh, van_ban=sua)) == (
        "Đã được sửa đổi, bổ sung bởi 19/2023/QH15, 113/2025/QH15."
    )
    assert mo_ta(_e(V.bi_sua_doi, van_ban=sua[1:])) == "Đã được sửa đổi, bổ sung bởi 113/2025/QH15."
    assert mo_ta(_e(V.mot_phan_khong_xac_dinh)) is None, "không có văn bản làm chứng thì không nêu gì"
    assert mo_ta(_e(V.chua_hieu_luc, tu_ngay=date(2026, 7, 1))) == "Có hiệu lực từ ngày 01/07/2026."
    assert mo_ta(_e(V.con_hieu_luc)) is None
    assert mo_ta(_e(V.chua_xac_dinh)) is None


@pytest.mark.parametrize("verdict", list(V))
@pytest.mark.parametrize("van_ban", [(), (VanBanNeu("2", "74/2024/NĐ-CP"),)])
def test_moi_cau_cho_nguoi_doc_KHONG_mang_ma_noi_bo(verdict, van_ban):
    e = _e(verdict, van_ban=van_ban, tu_ngay=date(2027, 1, 1))
    for cau in (mo_ta(e), canh_bao("90/2019/NĐ-CP", e)):
        assert cau is None or not _CAM.search(cau), (verdict, cau)
    c = canh_bao("90/2019/NĐ-CP", e)
    assert c is None or c.startswith("90/2019/NĐ-CP "), "giao diện ghép cảnh báo theo tiền tố '<số hiệu> '"
    assert (c is None) is (verdict == V.con_hieu_luc), "chỉ còn hiệu lực trọn vẹn mới im lặng"


def test_hieu_luc_ra_giu_ly_do_cho_eval_va_neu_dung_van_ban_cua_mo_ta():
    sua = VanBanNeu("1", "19/2023/QH15")
    dan = {sua: {"doc_id": None, "so_ky_hieu": "19/2023/QH15", "ten_van_ban": "Luật sửa đổi", "lien_ket": VBPL}}
    ra = hieu_luc_ra(_e(V.mot_phan_khong_xac_dinh, van_ban=(sua,)), dan)
    assert ra["ly_do"].startswith("tình trạng MOJ"), "ly_do ở lại API cho độ chính xác và eval"
    assert ra["mo_ta"] == "Đã được sửa đổi, bổ sung bởi 19/2023/QH15."
    assert ra["van_ban_lien_quan"] == [dan[sua]]
    assert hieu_luc_ra(_e(V.chua_hieu_luc, tu_ngay=date(2027, 1, 1)), {})["van_ban_lien_quan"] == []


def test_thong_diep_an_chi_noi_khong_con_hieu_luc_khi_van_ban_that_su_da_chet():
    """Văn bản ẩn vì thiếu link hay chưa rõ tình trạng có thể ĐANG SỐNG: nói nó
    "không còn hiệu lực" là nói sai."""
    nd = {
        "so_ky_hieu": "90/2019/NĐ-CP",
        "loai_van_ban": "Nghị định",
        "ten": "Nghị định 90/2019/NĐ-CP",
        "tinh_trang": "CHL",
    }
    assert thong_diep_an(nd, _e(V.bi_thay_the)) == THONG_DIEP_HET.format("Văn bản này")
    assert thong_diep_an(nd, _e(V.bi_thay_the), goi_ten=True) == (
        "Nghị định số 90/2019/NĐ-CP không còn hiệu lực nên không có trong phạm vi tra cứu."
    )
    assert thong_diep_an({**nd, "tinh_trang": "HHL"}, _e(V.chua_xac_dinh)).startswith("Văn bản này không còn")
    thieu_link = thong_diep_an(nd, _e(V.con_hieu_luc))
    assert "không còn hiệu lực" not in thieu_link and not _CAM.search(thieu_link), thieu_link
    assert cau_van_ban_an("X không còn hiệu lực.", ["74/2024/NĐ-CP"]) == (
        "X không còn hiệu lực. Văn bản thay thế: 74/2024/NĐ-CP."
    )


# ─────────────────────────────────────── bằng chứng đích danh của phán quyết


def _doc(**kw) -> dict:
    return {
        "id": "x",
        "so_ky_hieu": "90/2019/NĐ-CP",
        "loai_van_ban": "Nghị định",
        "ten": "Nghị định quy định mức lương tối thiểu vùng",
        "ngay_hieu_luc": date(2020, 1, 1),
        "ngay_het_hieu_luc": None,
        "tinh_trang": "CHL",
    } | kw


_THAY = {
    "loai": 21,
    "chieu": "di_vao",
    "from_document_id": "154245",
    "from_so_ky_hieu": "38/2022/NĐ-CP",
    "from_ten": "Nghị định quy định mức lương tối thiểu",
    "from_ngay_hieu_luc": date(2022, 7, 1),
}


def test_danh_gia_neu_van_ban_thay_the_theo_do_thi_ca_khi_het_han_bang_ngay():
    assert danh_gia(_doc(), [_THAY], AS_OF).van_ban == (VanBanNeu("154245", "38/2022/NĐ-CP"),)
    het = danh_gia(_doc(ngay_het_hieu_luc=date(2022, 7, 1)), [_THAY], AS_OF)
    assert het.verdict == V.het_hieu_luc and het.van_ban == (VanBanNeu("154245", "38/2022/NĐ-CP"),)
    # Cạnh khác chủ đề là nghi lỗi dữ liệu — không được nêu tên như kẻ thay thế.
    khac = {**_THAY, "from_ten": "Luật Việc làm"}
    assert danh_gia(_doc(ngay_het_hieu_luc=date(2022, 7, 1)), [khac], AS_OF).van_ban == ()


def test_danh_gia_suy_luan_cung_chu_de_KHONG_nen_ten_ai():
    """Mức 2b là phỏng đoán từ tiêu đề, không có văn bản làm chứng."""
    ung_vien = [
        {
            "so_ky_hieu": "74/2024/NĐ-CP",
            "loai_van_ban": "Nghị định",
            "ten": "Nghị định quy định mức lương tối thiểu",
            "ngay_hieu_luc": date(2024, 7, 1),
        }
    ]
    r = danh_gia(_doc(), [], AS_OF, ung_vien)
    assert r.verdict == V.bi_thay_the and r.van_ban == ()


def test_danh_gia_sua_doi_chi_neu_van_ban_SUA_khong_neu_van_ban_khai_tu_mot_phan():
    sua = {
        "loai": 20,
        "chieu": "di_vao",
        "from_document_id": "a",
        "from_so_ky_hieu": "19/2023/QH15",
        "from_ten": "Luật sửa đổi",
        "from_ngay_hieu_luc": date(2024, 7, 1),
    }
    mot_phan = {
        "loai": 23,
        "chieu": "di_ra",
        "from_document_id": "b",
        "from_so_ky_hieu": "12/2022/NĐ-CP",
        "from_ten": "Nghị định xử phạt",
        "from_ngay_hieu_luc": date(2022, 1, 17),
    }
    r = danh_gia(_doc(ten="Bộ luật Lao động", loai_van_ban="Bộ luật", tinh_trang="HHL1P"), [mot_phan, sua], AS_OF)
    assert r.verdict == V.mot_phan_khong_xac_dinh
    assert r.van_ban == (VanBanNeu("a", "19/2023/QH15"),)


def test_chua_hieu_luc_mang_ngay_va_ap_sua_doi_mang_van_ban_sua():
    assert danh_gia(_doc(ngay_hieu_luc=date(2027, 1, 1)), [], AS_OF).tu_ngay == date(2027, 1, 1)
    goc = Effectivity(V.con_hieu_luc, "thap", "x")
    ban_ghi = [
        {
            "vi_tri": "Điều 139 > Khoản 1",
            "sua_boi_so_ky_hieu": "113/2025/QH15",
            "sua_boi_duong_dan": None,
            "tu_ngay": date(2026, 7, 1),
            "nguon": "congbao",
            "do_tin_cay": "cao",
        }
    ]
    assert ap_sua_doi(goc, ban_ghi, AS_OF).van_ban == (VanBanNeu(None, "113/2025/QH15"),)


# ──────────────────────────── câu hỏi nêu tên văn bản ẩn (assemble, 0 token)

_AN = {
    "ma": "khong_hien_thi",
    "so_ky_hieu": "90/2019/NĐ-CP",
    "ten_van_ban": "Nghị định 90/2019/NĐ-CP",
    "thong_diep": "Nghị định số 90/2019/NĐ-CP không còn hiệu lực nên không có trong phạm vi tra cứu.",
    "thay_the": [
        {"doc_id": "183939", "so_ky_hieu": "293/2025/NĐ-CP", "ten_van_ban": "Nghị định 293/2025", "lien_ket": CP}
    ],
}


@pytest.mark.parametrize("rt", [ResultType.answer, ResultType.abstain, ResultType.partial_coverage])
def test_van_ban_an_duoc_nhac_len_coverage_warnings_va_truong_co_link(rt):
    ket = {"result_type": rt, "warnings": ["293/2025/NĐ-CP còn hiệu lực một phần."], "coverage_note": "Đuôi hỏi."}
    ra = gan_van_ban_khong_hien_thi(ket, [_AN])
    cau = (
        "Nghị định số 90/2019/NĐ-CP không còn hiệu lực nên không có trong phạm vi tra cứu. "
        "Văn bản thay thế: 293/2025/NĐ-CP."
    )
    assert ra["warnings"] == [cau, "293/2025/NĐ-CP còn hiệu lực một phần."]
    assert ra["coverage_note"] == f"{cau}\n\nĐuôi hỏi."
    assert ra["van_ban_khong_hien_thi"] == [_AN] and ra["van_ban_khong_hien_thi"][0]["thay_the"][0]["lien_ket"] == CP


def test_van_ban_an_KHONG_chen_vao_luot_khong_phai_tra_cuu():
    for rt in (ResultType.hoi_ve_kho, ResultType.gioi_thieu, ResultType.ban_thao, ResultType.out_of_scope):
        ket = {"result_type": rt, "warnings": [], "coverage_note": None}
        assert gan_van_ban_khong_hien_thi(ket, [_AN]) is ket
    ket = {"result_type": ResultType.answer, "warnings": [], "coverage_note": None}
    assert gan_van_ban_khong_hien_thi(ket, []) is ket
