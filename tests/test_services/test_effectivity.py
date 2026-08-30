"""Kiểm cơ chế hiệu lực 3 mức (spec 5.2) — phép kiểm thứ tư của verifier tầng 1.

Hai nhóm test:

  * **Đơn vị** — hàm thuần, không cần Postgres. Ghim từng nhánh của `danh_gia`
    và từng bẫy tiếng Việt của `cung_chu_de`.
  * **Tích hợp** (`@pytest.mark.integration`) — đọc DB thật. Test chấp nhận là
    `test_CHAP_NHAN_sau_nghi_dinh_luong_toi_thieu`: sáu nghị định lương tối
    thiểu trong corpus, `as_of = 2026-08-29`, phán quyết phải khớp SỰ THẬT
    pháp lý chứ không khớp `tinh_trang` của MOJ — MOJ đánh sai 4/6 dòng.
"""

import logging
import unicodedata
from datetime import date

import pytest
from sqlalchemy import text

from src.services.db import get_engine
from src.services.effectivity import EffectivityVerdict as V
from src.services.effectivity import cung_chu_de, danh_gia, danh_gia_theo_id, nap_ngu_canh

HOM_NAY = date(2026, 8, 27)
# Ngày Kenz dùng khi tự đo tập chấp nhận trên DB — giữ nguyên để so được.
NGAY_CHAP_NHAN = date(2026, 8, 29)


def _doc(**kw) -> dict:
    base = {"id": "x", "so_ky_hieu": "1/2020/NĐ-CP", "ten": "Nghị định thử",
            "ngay_hieu_luc": date(2020, 1, 1), "ngay_het_hieu_luc": None, "tinh_trang": "CHL"}
    return base | kw


# ─────────────────────────── Mức 1: ngày hết hiệu lực ───────────────────────────

def test_muc_1_effTo_da_qua_thi_het_hieu_luc_tin_cay_cao():
    r = danh_gia(_doc(ngay_het_hieu_luc=date(2025, 1, 1)), [], HOM_NAY)
    assert r.verdict is V.het_hieu_luc and r.tin_cay == "cao"


def test_muc_1_effTo_tuong_lai_thi_chua_het():
    r = danh_gia(_doc(ngay_het_hieu_luc=date(2030, 1, 1)), [], HOM_NAY)
    assert r.verdict is not V.het_hieu_luc


def test_muc_1_thang_muc_2_khi_ca_hai_dung():
    doc = _doc(ngay_het_hieu_luc=date(2025, 1, 1), ten="Nghị định lương tối thiểu")
    canh = [{"loai": 12, "from_ten": "Nghị định lương tối thiểu",
             "from_ngay_hieu_luc": date(2024, 1, 1), "from_so_ky_hieu": "a"}]
    assert danh_gia(doc, canh, HOM_NAY).verdict is V.het_hieu_luc


# ────────────────────── Mức 2a: cạnh đồ thị nói "bị thay thế" ──────────────────────

def test_muc_2_bat_duoc_loi_MOJ_ND_90_2019():
    """MOJ đánh 'CHL' nhưng có cạnh Thay thế từ văn bản CÙNG chủ đề đã hiệu lực."""
    doc = _doc(id="139094", ten="Nghị định về mức lương tối thiểu vùng", tinh_trang="CHL")
    canh = [{"loai": 12, "from_ten": "Nghị định quy định mức lương tối thiểu",
             "from_ngay_hieu_luc": date(2024, 7, 1), "from_so_ky_hieu": "74/2024/NĐ-CP"}]
    r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is V.bi_thay_the and r.tin_cay == "cao"
    assert "74/2024" in r.ly_do


def test_muc_2_GUARD_canh_thay_the_KHAC_CHU_DE_thi_khong_ket_luan():
    """Luật Việc làm 'thay thế' Luật BHXH — gần chắc là lỗi dữ liệu MOJ.
    Guard phải hạ xuống cần đối chiếu tay, KHÔNG kết luận hết hiệu lực."""
    doc = _doc(id="175027", ten="Luật Bảo hiểm xã hội", tinh_trang="HHL")
    canh = [{"loai": 12, "from_ten": "Luật Việc làm",
             "from_ngay_hieu_luc": date(2026, 1, 1), "from_so_ky_hieu": "74/2025/QH15"}]
    r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is V.can_doi_chieu_tay
    assert r.tin_cay == "thap"


def test_muc_2_van_ban_thay_CHUA_hieu_luc_thi_chua_ket_luan():
    doc = _doc(ten="Nghị định về lương tối thiểu")
    canh = [{"loai": 12, "from_ten": "Nghị định về lương tối thiểu",
             "from_ngay_hieu_luc": date(2030, 1, 1), "from_so_ky_hieu": "9/2030/NĐ-CP"}]
    assert danh_gia(doc, canh, HOM_NAY).verdict is not V.bi_thay_the


def test_muc_2_canh_thay_the_sap_toi_van_duoc_NEU_TEN_trong_ly_do():
    """Không kết luận, nhưng cũng không được im lặng nuốt tín hiệu."""
    doc = _doc(ten="Nghị định về lương tối thiểu")
    canh = [{"loai": 21, "from_ten": "Nghị định về lương tối thiểu",
             "from_ngay_hieu_luc": date(2030, 1, 1), "from_so_ky_hieu": "9/2030/NĐ-CP"}]
    r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is V.con_hieu_luc
    assert "9/2030/NĐ-CP" in r.ly_do and "2030-01-01" in r.ly_do


def test_muc_2_GUARD_NGAY_canh_tu_van_ban_hieu_luc_TRUOC_khong_the_thay_the():
    """Bất biến: không văn bản nào bị thay bởi văn bản hiệu lực TRƯỚC chính nó.

    Đây là ca 92898 thu nhỏ — cạnh đi vào duy nhất của NĐ 122/2015 là từ NĐ
    103/2014, tức chiều "tôi khai tử anh", không phải "anh khai tử tôi".
    """
    doc = _doc(ngay_hieu_luc=date(2016, 1, 1), ten="Nghị định về mức lương tối thiểu vùng")
    canh = [{"loai": 21, "from_ten": "Nghị định về mức lương tối thiểu vùng",
             "from_ngay_hieu_luc": date(2015, 1, 1), "from_so_ky_hieu": "103/2014/NĐ-CP"}]
    r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is not V.bi_thay_the
    assert "103/2014" not in r.ly_do, "không được vu cho văn bản cũ là kẻ thay thế"


def test_muc_2_canh_loai_22_KHONG_phai_tin_hieu_khai_tu():
    """`loai` 22/23 đi vào nghĩa là "TÔI làm văn bản kia hết hiệu lực".

    Đo trên cả 46 cạnh: loai 20/21 luôn từ văn bản hiệu lực SAU, loai 22/23
    luôn từ văn bản hiệu lực TRƯỚC. Coi 22/23 là tín hiệu khai tử sẽ tuyên
    NĐ 293/2025 — luật hiện hành — là đã chết.
    """
    doc = _doc(ngay_hieu_luc=date(2026, 1, 1), ten="Nghị định về mức lương tối thiểu")
    canh = [{"loai": 22, "from_ten": "Nghị định về mức lương tối thiểu",
             "from_ngay_hieu_luc": date(2024, 7, 1), "from_so_ky_hieu": "74/2024/NĐ-CP"}]
    assert danh_gia(doc, canh, HOM_NAY).verdict is not V.bi_thay_the


def test_muc_2a_canh_DI_RA_loai_22_LA_bang_chung_khai_tu_truc_tiep():
    """Cạnh `from=tôi, to=Y, loai=22` nghĩa là "Y quy định TÔI hết hiệu lực".
    Đọc theo chiều đi ra, 18 cạnh này thành bằng chứng đồ thị trực tiếp cho
    văn bản bị khai tử — `cao`, chứ không phải suy luận `trung_binh`."""
    doc = _doc(ngay_hieu_luc=date(2006, 1, 1), ten="Bộ luật Hàng hải Việt Nam")
    canh = [{"loai": 22, "chieu": "di_ra", "from_ten": "Bộ luật Hàng hải",
             "from_ngay_hieu_luc": date(2017, 7, 1), "from_so_ky_hieu": "95/2015/QH13"}]
    r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is V.bi_thay_the and r.tin_cay == "cao"
    assert "95/2015/QH13" in r.ly_do
    assert "bị 95/2015/QH13 thay thế" not in r.ly_do, (
        "cạnh đi ra nói 'Y QUY ĐỊNH tôi hết hiệu lực', câu chữ phải đúng chiều")


def test_muc_2a_canh_DI_RA_loai_23_chi_khai_tu_MOT_PHAN():
    doc = _doc(ngay_hieu_luc=date(2025, 7, 1), ten="Nghị định về phân quyền, phân cấp")
    canh = [{"loai": 23, "chieu": "di_ra", "from_ten": "Nghị định về mức lương tối thiểu",
             "from_ngay_hieu_luc": date(2026, 1, 1), "from_so_ky_hieu": "293/2025/NĐ-CP"}]
    r = danh_gia(doc, canh, date(2026, 8, 29))
    assert r.verdict is V.mot_phan_khong_xac_dinh
    assert "293/2025/NĐ-CP" in r.ly_do


def test_CUNG_loai_22_doc_hai_chieu_ra_hai_ket_qua_NGUOC_nhau():
    """Cùng một `loai=22`, chỉ khác `chieu` — đây là toàn bộ lý do bảng
    `TAC_DONG` phải khoá theo cặp (chiều, loai) chứ không theo loai."""
    ten = "Nghị định quy định mức lương tối thiểu"
    canh_ra = {"loai": 22, "chieu": "di_ra", "from_ten": ten,
               "from_ngay_hieu_luc": date(2026, 1, 1), "from_so_ky_hieu": "293/2025/NĐ-CP"}
    doc = _doc(ngay_hieu_luc=date(2024, 7, 1), ten=ten)
    assert danh_gia(doc, [canh_ra], date(2026, 8, 29)).verdict is V.bi_thay_the
    assert danh_gia(doc, [canh_ra | {"chieu": "di_vao"}], date(2026, 8, 29)).verdict is not V.bi_thay_the


def test_canh_DI_RA_ngay_MAU_THUAN_bi_bo_qua_VA_dem(caplog):
    """`to` phải hiệu lực SAU `from`. Nếu không, dữ liệu bẩn: bỏ qua và ĐẾM
    bằng log cảnh báo, không im lặng và cũng không tin."""
    doc = _doc(ngay_hieu_luc=date(2020, 1, 1), ten="Nghị định về mức lương tối thiểu")
    canh = [{"loai": 22, "chieu": "di_ra", "from_ten": "Nghị định về mức lương tối thiểu",
             "from_ngay_hieu_luc": date(2015, 1, 1), "from_so_ky_hieu": "103/2014/NĐ-CP"}]
    with caplog.at_level(logging.WARNING, logger="src.services.effectivity"):
        r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is not V.bi_thay_the
    assert "103/2014" not in r.ly_do
    canh_bo = [x for x in caplog.records if "ngày mâu thuẫn" in x.getMessage()]
    assert len(canh_bo) == 1, "cạnh bẩn phải được đếm, không được nuốt im lặng"


def test_muc_2c_canh_SUA_DOI_lam_khong_xac_dinh_chu_khong_khai_tu():
    doc = _doc(ten="Bộ luật Lao động", tinh_trang="CHL")
    canh = [{"loai": 20, "from_ten": "Luật sửa đổi, bổ sung một số điều của Bộ luật Lao động",
             "from_ngay_hieu_luc": date(2025, 1, 1), "from_so_ky_hieu": "99/2024/QH15"}]
    r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is V.mot_phan_khong_xac_dinh
    assert "99/2024/QH15" in r.ly_do


# ─────────────── Mức 2b: suy luận cùng chủ đề khi đồ thị im lặng ───────────────

def test_muc_2b_suy_luan_cung_chu_de_khi_KHONG_co_canh_nao():
    """Ca 139094 thu nhỏ: đồ thị im, nhưng có văn bản cùng chủ đề hiệu lực sau."""
    doc = _doc(ngay_hieu_luc=date(2020, 1, 1), ten="Nghị định quy định mức lương tối thiểu vùng")
    ung_vien = [{"so_ky_hieu": "74/2024/NĐ-CP", "ten": "Nghị định quy định mức lương tối thiểu",
                 "ngay_hieu_luc": date(2024, 7, 1)}]
    r = danh_gia(doc, [], HOM_NAY, ung_vien)
    assert r.verdict is V.bi_thay_the
    assert r.tin_cay == "trung_binh", "suy luận yếu hơn cạnh đồ thị"
    assert "74/2024/NĐ-CP" in r.ly_do


def test_muc_2b_ung_vien_KHAC_chu_de_khong_kich_hoat():
    doc = _doc(ngay_hieu_luc=date(2020, 1, 1), ten="Nghị định quy định mức lương tối thiểu vùng")
    ung_vien = [{"so_ky_hieu": "12/2022/NĐ-CP",
                 "ten": "Nghị định quy định xử phạt vi phạm hành chính trong lĩnh vực lao động",
                 "ngay_hieu_luc": date(2022, 1, 17)}]
    assert danh_gia(doc, [], HOM_NAY, ung_vien).verdict is V.con_hieu_luc


def test_muc_2b_van_ban_SUA_DOI_khong_duoc_coi_la_ke_thay_the():
    """"Luật sửa đổi, bổ sung một số điều của Bộ luật Tố tụng hình sự" trùng
    danh từ chính với chính Bộ luật đó (Jaccard 1.0) nhưng nó SỬA, không THAY."""
    doc = _doc(ngay_hieu_luc=date(2018, 1, 1), ten="Bộ luật Tố tụng hình sự", tinh_trang="HHL1P")
    ung_vien = [{"so_ky_hieu": "02/2021/QH15",
                 "ten": "Luật sửa đổi, bổ sung một số điều của Bộ luật Tố tụng hình sự",
                 "ngay_hieu_luc": date(2021, 12, 1)}]
    assert danh_gia(doc, [], HOM_NAY, ung_vien).verdict is not V.bi_thay_the


def test_muc_2b_GUARD_THU_BAC_nghi_dinh_khong_thay_the_duoc_bo_luat():
    """NĐ 145/2020 hướng dẫn Bộ luật Lao động — cùng chủ đề, hiệu lực sau, và
    KHÔNG được phép thay thế nó. Thiếu guard này thì BLLĐ, văn bản trung tâm
    của cả corpus, bị tuyên là đã chết."""
    doc = _doc(loai_van_ban="Bộ luật", ngay_hieu_luc=date(2021, 1, 1), ten="Bộ Luật lao động")
    ung_vien = [{"so_ky_hieu": "145/2020/NĐ-CP", "loai_van_ban": "Nghị định",
                 "ten": "Nghị định quy định chi tiết một số điều của Bộ luật Lao động "
                        "về điều kiện lao động và quan hệ lao động",
                 "ngay_hieu_luc": date(2021, 2, 1)}]
    r = danh_gia(doc, [], HOM_NAY, ung_vien)
    assert r.verdict is not V.bi_thay_the
    assert "145/2020" not in r.ly_do


def test_muc_2b_GUARD_THU_BAC_cung_loai_thi_van_kich_hoat():
    doc = _doc(loai_van_ban="Nghị định", ngay_hieu_luc=date(2020, 1, 1),
               ten="Nghị định quy định mức lương tối thiểu vùng")
    ung_vien = [{"so_ky_hieu": "74/2024/NĐ-CP", "loai_van_ban": "Nghị định",
                 "ten": "Nghị định quy định mức lương tối thiểu",
                 "ngay_hieu_luc": date(2024, 7, 1)}]
    assert danh_gia(doc, [], HOM_NAY, ung_vien).verdict is V.bi_thay_the


def test_muc_2b_chon_ung_vien_GIONG_NHAT_chu_khong_phai_som_nhat():
    """Giống nhất trước, hoà thì lấy sớm nhất — nếu chỉ lấy sớm nhất thì
    "Bộ luật Tố tụng hình sự 2003" (Jaccard 0.5) sẽ bị vu là kẻ thay thế
    "Bộ luật Hình sự 1999" thay vì "Bộ luật Hình sự 2015" (Jaccard 1.0)."""
    doc = _doc(ngay_hieu_luc=date(2000, 7, 1), ten="Bộ luật Hình sự")
    ung_vien = [
        {"so_ky_hieu": "19/2003/QH11", "ten": "Bộ luật Tố tụng hình sự",
         "ngay_hieu_luc": date(2004, 7, 1)},
        {"so_ky_hieu": "100/2015/QH13", "ten": "Bộ luật Hình sự",
         "ngay_hieu_luc": date(2018, 1, 1)},
    ]
    r = danh_gia(doc, [], HOM_NAY, ung_vien)
    assert r.verdict is V.bi_thay_the
    assert "100/2015/QH13" in r.ly_do and "19/2003" not in r.ly_do


def test_muc_2b_ung_vien_CHUA_hieu_luc_khong_kich_hoat():
    doc = _doc(ngay_hieu_luc=date(2026, 1, 1), ten="Nghị định quy định mức lương tối thiểu")
    ung_vien = [{"so_ky_hieu": "9/2030/NĐ-CP", "ten": "Nghị định quy định mức lương tối thiểu",
                 "ngay_hieu_luc": date(2030, 1, 1)}]
    assert danh_gia(doc, [], HOM_NAY, ung_vien).verdict is V.con_hieu_luc


# ───────────────────────────── Mức 3 và mặc định ─────────────────────────────

def test_muc_3_HHL1P_tra_khong_xac_dinh_tin_cay_thap():
    r = danh_gia(_doc(tinh_trang="HHL1P"), [], HOM_NAY)
    assert r.verdict is V.mot_phan_khong_xac_dinh and r.tin_cay == "thap"
    assert "cấp điều khoản" in r.ly_do


def test_chua_hieu_luc_khi_ngay_hieu_luc_o_tuong_lai():
    r = danh_gia(_doc(ngay_hieu_luc=date(2030, 1, 1)), [], HOM_NAY)
    assert r.verdict is V.chua_hieu_luc and r.tin_cay == "cao"


def test_mac_dinh_con_hieu_luc_thi_tin_cay_chi_THAP():
    """Brief ghim `trung_binh`; ruling 2026-08-30 của chủ đề tài ghi đè xuống
    `thap`. Phán quyết này chỉ dựa vào `tinh_trang` của MOJ — nguồn ĐO ĐƯỢC là
    sai 4/6 trên chuỗi lương tối thiểu — trong khi suy luận cùng chủ đề (đúng
    6/6) mang `trung_binh`. Cùng nhãn là nói dối về chất lượng bằng chứng.
    ĐỪNG sửa ngược lại cho khớp brief."""
    r = danh_gia(_doc(), [], HOM_NAY)
    assert r.verdict is V.con_hieu_luc and r.tin_cay == "thap"


def test_tin_cay_xep_hang_dung_theo_nguon_bang_chung():
    """cạnh đồ thị > suy luận cùng chủ đề > chỉ đọc `tinh_trang` của MOJ."""
    ten = "Nghị định quy định mức lương tối thiểu vùng"
    do_thi = danh_gia(
        _doc(ten=ten),
        [{"loai": 21, "from_ten": ten, "from_ngay_hieu_luc": date(2024, 7, 1),
          "from_so_ky_hieu": "74/2024/NĐ-CP"}], HOM_NAY)
    suy_luan = danh_gia(_doc(ten=ten), [], HOM_NAY, [
        {"so_ky_hieu": "74/2024/NĐ-CP", "ten": ten, "ngay_hieu_luc": date(2024, 7, 1)}])
    chi_moj = danh_gia(_doc(ten=ten), [], HOM_NAY)
    assert (do_thi.tin_cay, suy_luan.tin_cay, chi_moj.tin_cay) == ("cao", "trung_binh", "thap")


# ─────────────── Không nuốt lỗi: mọi ca "không biết" phải nói ra ───────────────

def test_KHONG_NUOT_thieu_ngay_hieu_luc_tra_chua_xac_dinh():
    r = danh_gia(_doc(ngay_hieu_luc=None), [], HOM_NAY)
    assert r.verdict is V.chua_xac_dinh and r.tin_cay == "thap"
    assert "ngày hiệu lực" in r.ly_do


def test_KHONG_NUOT_tinh_trang_la_chua_xac_dinh_thi_KHONG_bao_con_hieu_luc():
    """36 dòng chỉ-metadata trong `documents` mang đúng trạng thái này."""
    r = danh_gia(_doc(tinh_trang="chua_xac_dinh"), [], HOM_NAY)
    assert r.verdict is V.chua_xac_dinh and r.tin_cay == "thap"


def test_KHONG_NUOT_tinh_trang_la_ma_la_thi_KHONG_bao_con_hieu_luc():
    r = danh_gia(_doc(tinh_trang="XYZ"), [], HOM_NAY)
    assert r.verdict is V.chua_xac_dinh and r.tin_cay == "thap"
    assert "XYZ" in r.ly_do


def test_KHONG_NUOT_canh_tro_toi_van_ban_khong_ton_tai():
    """LEFT JOIN trả cạnh có `from_*` toàn None khi văn bản nguồn đã biến mất."""
    canh = [{"loai": 21, "from_ten": None, "from_ngay_hieu_luc": None,
             "from_so_ky_hieu": None, "from_document_id": "999999"}]
    r = danh_gia(_doc(), canh, HOM_NAY)
    assert r.verdict is V.chua_xac_dinh and r.tin_cay == "thap"
    assert "999999" in r.ly_do


def test_KHONG_NUOT_as_of_truoc_moi_ngay_hieu_luc():
    r = danh_gia(_doc(ngay_hieu_luc=date(2020, 1, 1)), [], date(1990, 1, 1))
    assert r.verdict is V.chua_hieu_luc


# ───────────────────────────── `cung_chu_de` ─────────────────────────────

def test_cung_chu_de_so_theo_danh_tu_chinh():
    assert cung_chu_de("Nghị định về mức lương tối thiểu vùng",
                       "Nghị định quy định mức lương tối thiểu") is True
    assert cung_chu_de("Luật Việc làm", "Luật Bảo hiểm xã hội") is False


def test_cung_chu_de_biet_noi_KHONG_voi_hai_linh_vuc_khac_han():
    assert cung_chu_de("Nghị định quy định mức lương tối thiểu vùng đối với người lao động",
                       "Nghị định quy định về hợp đồng lao động điện tử") is False
    assert cung_chu_de("Bộ luật Hàng hải Việt Nam", "Bộ luật Lao động") is False


def test_cung_chu_de_DAU_DE_khac_nhau_thi_KHONG_cung_chu_de():
    """Chỉ Jaccard thôi thì "Bộ luật Tố tụng dân sự" vs "Bộ luật Dân sự" ra 0.5
    — ĐÚNG BẰNG cặp cùng chủ đề thật thấp nhất trong corpus (122/2015 vs
    153/2016). Không ngưỡng nào tách được; danh từ đầu đề thì tách sạch."""
    assert cung_chu_de("Bộ luật Tố tụng dân sự", "Bộ luật Dân sự") is False
    assert cung_chu_de("Bộ luật Hình sự", "Bộ luật Tố tụng hình sự") is False
    assert cung_chu_de("Luật An toàn, vệ sinh lao động", "Bộ luật Lao động") is False


def test_cung_chu_de_BO_QUA_so_hieu_va_nam_trong_tieu_de():
    """Tiêu đề corpus nhúng cả số ký hiệu ("Nghị định số 122/2015/NĐ-CP ...").
    Không lọc thì hai văn bản chả liên quan cùng năm 2015 sẽ "cùng chủ đề"."""
    assert cung_chu_de("Bộ luật Dân sự số 91/2015/QH13",
                       "Bộ luật Hàng hải Việt Nam số 95/2015/QH13") is False


def test_cung_chu_de_D_U00D0_va_chu_HOA_khong_lam_truot():
    """`Ð` (U+00D0) khác `Đ` (U+0110) nhưng nhìn y hệt — có thật trong corpus."""
    assert "Ð" in "Bộ luật Lao Ðộng" and "Đ" not in "Bộ luật Lao Ðộng"
    assert cung_chu_de("Bộ luật Lao Ðộng", "BỘ LUẬT LAO ĐỘNG") is True


def test_cung_chu_de_corpus_khong_thuan_NFC_van_khop():
    """96117 mang 'ư' + U+0323 thay vì 'ự' precomposed."""
    phan_ra = unicodedata.normalize("NFD", "Nghị định về tiền lương thực tế")
    assert phan_ra != "Nghị định về tiền lương thực tế"
    assert cung_chu_de(phan_ra, "Nghị định về tiền lương thực tế") is True


def test_cung_chu_de_tieu_de_rong_tra_False_chu_khong_no():
    assert cung_chu_de("", "Bộ luật Lao động") is False
    assert cung_chu_de(None, None) is False
    assert cung_chu_de("Nghị định của Chính phủ", "Luật số 12/2020/QH14") is False


# ══════════════════════════ Tích hợp: DB thật ══════════════════════════

SAU_NGHI_DINH = ["92898", "126319", "132862", "139094", "168670", "183939"]

# Sự thật pháp lý Kenz tự đo, KHÔNG phải `tinh_trang` của MOJ (MOJ sai 4/6).
SU_THAT = {
    "92898": V.bi_thay_the,    # 122/2015 — MOJ nói CHL
    "126319": V.bi_thay_the,   # 141/2017 — MOJ nói CHL
    "132862": V.bi_thay_the,   # 157/2018 — MOJ nói CHL
    "139094": V.bi_thay_the,   # 90/2019  — MOJ nói CHL, đồ thị cũng im lặng
    "168670": V.het_hieu_luc,  # 74/2024
    "183939": V.con_hieu_luc,  # 293/2025 — hiện hành
}


@pytest.mark.integration
def test_CHAP_NHAN_sau_nghi_dinh_luong_toi_thieu():
    """Test chấp nhận của Task 2: cả sáu dòng phải đúng với `as_of=2026-08-29`."""
    engine = get_engine()
    sai = []
    for doc_id in SAU_NGHI_DINH:
        r = danh_gia_theo_id(engine, doc_id, NGAY_CHAP_NHAN)
        if r.verdict is not SU_THAT[doc_id]:
            sai.append(f"{doc_id}: mong {SU_THAT[doc_id]}, nhận {r.verdict} ({r.ly_do})")
    assert not sai, "\n".join(sai)


@pytest.mark.integration
def test_CHAP_NHAN_ly_do_neu_dich_danh_van_ban_ke_nhiem():
    """`ly_do` hiện ra trong câu trả lời cho người dùng — phải nêu đích danh."""
    engine = get_engine()
    ke_nhiem = {"92898": "153/2016/NĐ-CP", "126319": "157/2018/NĐ-CP",
                "132862": "90/2019/NĐ-CP", "139094": "74/2024/NĐ-CP"}
    for doc_id, so_ky_hieu in ke_nhiem.items():
        r = danh_gia_theo_id(engine, doc_id, NGAY_CHAP_NHAN)
        assert so_ky_hieu in r.ly_do, f"{doc_id}: {r.ly_do}"


@pytest.mark.integration
def test_CHAP_NHAN_tin_cay_phan_anh_nguon_phan_quyet():
    """Cạnh đồ thị → cao; suy luận cùng chủ đề → trung_binh."""
    engine = get_engine()
    mong = {"126319": "cao", "132862": "cao", "168670": "cao",
            "92898": "trung_binh", "139094": "trung_binh"}
    thuc = {d: danh_gia_theo_id(engine, d, NGAY_CHAP_NHAN).tin_cay for d in mong}
    assert thuc == mong


@pytest.mark.integration
def test_ND_293_2025_hien_hanh_KHONG_bi_chinh_ke_bi_no_thay_the_khai_tu():
    """183939 là `to_document_id` của 2 cạnh loai 22/23 — tức nó là KẺ khai tử,
    không phải nạn nhân. Đọc đúng chiều thì nó có 0 tín hiệu chấm dứt."""
    engine = get_engine()
    with engine.connect() as c:
        tho = c.execute(text(
            'SELECT count(*) FROM "references"'
            " WHERE to_document_id = '183939' AND loai IN (22, 23)")).scalar()
    assert tho == 2, "dữ liệu đổi — xem lại giả định của test này"
    doc, canh, _ = nap_ngu_canh(engine, "183939", NGAY_CHAP_NHAN)
    assert canh == [], "2 cạnh đó phải được đọc từ phía 74/2024 và 128/2025, không phải phía này"
    assert danh_gia(doc, canh, NGAY_CHAP_NHAN).verdict is V.con_hieu_luc


@pytest.mark.integration
def test_canh_DI_RA_nang_tin_cay_len_CAO_tren_du_lieu_that():
    """Bộ luật Hàng hải 40/2005 — không có cạnh đi vào nào, trước đây phải suy
    luận (`trung_binh`). Cạnh đi ra loai=22 tới Bộ luật Hàng hải 95/2015 là bằng
    chứng đồ thị trực tiếp → `cao`."""
    engine = get_engine()
    doc, canh, uv = nap_ngu_canh(engine, "18131", NGAY_CHAP_NHAN)
    assert [c["chieu"] for c in canh] == ["di_ra"]
    r = danh_gia(doc, canh, NGAY_CHAP_NHAN, uv)
    assert r.verdict is V.bi_thay_the and r.tin_cay == "cao"
    assert "95/2015/QH13" in r.ly_do
    # Bỏ cạnh đi ra đi thì tụt về suy luận — đó chính là phần cạnh này đóng góp.
    khong_di_ra = danh_gia(doc, [], NGAY_CHAP_NHAN, uv)
    assert khong_di_ra.tin_cay == "trung_binh"


@pytest.mark.integration
def test_KHONG_canh_22_23_nao_trong_DB_co_ngay_mau_thuan(caplog):
    """Đo lại trên cả 57 văn bản: 0 cạnh bị bỏ vì ngày mâu thuẫn. Test đỏ nếu
    một parquet mới mang dữ liệu bẩn vào — lúc đó phải xem lại, không nuốt."""
    engine = get_engine()
    with engine.connect() as c:
        ids = [r[0] for r in c.execute(text("SELECT id FROM documents")).all()]
    with caplog.at_level(logging.WARNING, logger="src.services.effectivity"):
        for doc_id in ids:
            danh_gia_theo_id(engine, doc_id, NGAY_CHAP_NHAN)
    assert [r.getMessage() for r in caplog.records if "ngày mâu thuẫn" in r.getMessage()] == []


@pytest.mark.integration
def test_ND_90_2019_that_su_KHONG_co_canh_nao_de_dua_vao():
    """Ghim tiền đề của Mức 2b: phán quyết cho 139094 là do SUY LUẬN, không
    phải do đồ thị. Test đỏ nếu ai đó nạp parquet mới có cạnh cho ca này —
    lúc đó `test_CHAP_NHAN_tin_cay...` cũng phải đổi sang "cao"."""
    _, canh, _ = nap_ngu_canh(get_engine(), "139094", NGAY_CHAP_NHAN)
    assert canh == []


@pytest.mark.integration
def test_KHONG_van_ban_nao_TRONG_CORPUS_bi_tuyen_bua_la_da_chet():
    """Quét cả 21 văn bản deep. Bản suy luận Mức 2b ĐẦU TIÊN tuyên nhầm 4 văn
    bản còn sống là đã bị thay thế — Bộ luật Lao động 45/2019 (bởi chính NĐ
    145/2020 hướng dẫn nó), Luật An toàn vệ sinh lao động 84/2015, Bộ luật Tố
    tụng dân sự 92/2015 (bởi Bộ luật Dân sự 91/2015) và Thông tư 09/2020.
    Guard thứ bậc + guard đầu đề dọn sạch cả bốn. Test này giữ chúng đã chết."""
    engine = get_engine()
    with engine.connect() as c:
        ids = [r[0] for r in c.execute(text(
            "SELECT id FROM documents WHERE depth <> 'metadata' ORDER BY id")).all()]
    chet = set()
    for doc_id in ids:
        doc, canh, ung_vien = nap_ngu_canh(engine, doc_id, NGAY_CHAP_NHAN)
        r = danh_gia(doc, canh, NGAY_CHAP_NHAN, ung_vien)
        if r.verdict is V.bi_thay_the:
            chet.add(doc_id)
            assert doc["so_ky_hieu"] not in r.ly_do, (
                f"{doc_id} bị tuyên là tự thay thế chính mình: {r.ly_do}")
    assert chet & {"139264", "70811", "96115", "152670"} == set(), (
        f"tuyên nhầm văn bản còn sống là đã bị thay thế: {sorted(chet)}")
    # Chỉ chuỗi lương tối thiểu mới thực sự bị thay trong corpus này.
    assert chet == {"92898", "126319", "132862", "139094"}, sorted(chet)
