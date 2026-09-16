"""GĐ2 của node `hieu_tai_lieu`: TRÍCH DỮ KIỆN và PHÉP TÍNH
(plan `tai-lieu-tong-quat.md` S4, FR-005/006/011/012/013).

File này khoá bốn điều:

1. Một `truong` mô hình trả về chỉ thành dữ kiện khi `trich` của nó tra ngược
   được về đúng tài liệu đã đọc — y hệt một `quan_sat`, y hệt `rut_du_kien`.
   Không neo được thì biến mất, và chỉ còn là một con số trong `traces`.
2. Dữ kiện mang theo tài liệu nó đến từ đâu (`tai_lieu_id`) và HẠNG bằng chứng
   (`nguon`), vì `luu_du_kien` ghi theo việc đọc chứ không theo hội thoại, và
   ràng buộc `ck_du_kien_do_tin` chỉ cho `do_tin` sống với `tai_lieu_ocr`.
3. `ket_qua_code` KHÔNG BAO GIỜ đến từ mô hình: node tự chạy `tinh` trên biểu
   thức rồi đặt cạnh con số tài liệu tự ghi. Đây là toàn bộ điểm của FR-013.
4. Vòng ghi ở `graph_tra_cuu` ghi đúng dữ kiện mới, đọc lại cả tập của hội
   thoại, và chỉ trả ra dòng của những tài liệu đã đi vào lượt này.
"""

import pytest

from src.agents.nodes import hieu_tai_lieu as h
from src.services.doc_tai_lieu import DonViVanBan, NguonChu
from src.services.neo_du_kien import LyDoNeo, Neo
from tests.test_agents.test_hieu_tai_lieu import _LLM, A_ID, B_ID, MOT, ST, TL, TL_BANG, _ra

HT_ID = "cccccccc-0000-0000-0000-000000000003"
SUB = "dddddddd-0000-0000-0000-000000000004"


def _truong(khoa, nhan, gia_tri, trich):
    return {"khoa": khoa, "nhan": nhan, "gia_tri": gia_tri, "trich": trich}


# ───────────────────────────────────────────────────────────── trích dữ kiện


def test_truong_co_neo_thanh_du_kien_moi():
    llm = _LLM(_ra(muc_dich="trich_du_kien", truong=[
        _truong("diem_toi_da", "Điểm tối đa", "10", "Tổng điểm tối đa là 10"),
    ]))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert len(ra["tai_lieu_du_kien_moi"]) == 1
    d = ra["tai_lieu_du_kien_moi"][0]
    assert d["key"] == "diem_toi_da" and d["nhan"] == "Điểm tối đa" and d["gia_tri"] == "10"
    assert d["trich"] == "Tổng điểm tối đa là 10" and d["nguon"] == "tai_lieu"
    assert d["tai_lieu_id"] == A_ID
    assert d["neo"].ly_do is LyDoNeo.ok and d["neo"].chi_so_don_vi == 1 and d["neo"].trang == 1
    assert ra["traces"]["hieu_tai_lieu_so_truong_giu"] == 1


def test_truong_khong_neo_duoc_bi_bo_va_dem():
    llm = _LLM(_ra(truong=[
        _truong("diem", "Điểm", "99", "Tổng điểm tối đa là 99 cho bốn tiêu chí"),
        _truong("ngan", "Ngắn", "10", "10"),
        _truong("rong", "Rỗng", "10", ""),
    ]))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert ra["tai_lieu_du_kien_moi"] == []
    assert ra["traces"]["hieu_tai_lieu_so_truong_bo"] == 3
    assert ra["traces"]["hieu_tai_lieu_so_truong_giu"] == 0


def test_truong_khong_co_gia_tri_bi_bo_KHONG_bia_gia_tri():
    """Tài liệu không nói thì dữ kiện không tồn tại — không có dòng rỗng."""
    llm = _LLM(_ra(truong=[_truong("ho_ten", "Họ tên", "  ", "Tổng điểm tối đa là 10")]))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert ra["tai_lieu_du_kien_moi"] == []


def test_khoa_duoc_chuan_hoa_thanh_snake_case_khong_dau():
    llm = _LLM(_ra(truong=[_truong("Họ tên sinh viên", "Họ tên", "10", "Tổng điểm tối đa là 10")]))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert ra["tai_lieu_du_kien_moi"][0]["key"] == "ho_ten_sinh_vien"


def test_tran_20_truong():
    llm = _LLM(_ra(truong=[
        _truong(f"k{i}", f"n{i}", str(i), "Tổng điểm tối đa là 10") for i in range(30)
    ]))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert len(ra["tai_lieu_du_kien_moi"]) == h.TOI_DA_TRUONG == 20


def test_du_kien_mang_dung_tai_lieu_khi_co_hai_tai_lieu():
    llm = _LLM(_ra(truong=[_truong("so_hd", "Số hợp đồng", "12/2026", "Hợp đồng lao động số 12/2026")]))
    ra = h.hieu_tai_lieu(ST, TL, llm, "m")
    assert ra["tai_lieu_du_kien_moi"][0]["tai_lieu_id"] == B_ID


def test_nguon_ocr_giu_do_tin_de_qua_rang_buoc_db():
    dv = [DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Tổng điểm tối đa là 10 cho bốn tiêu chí",
                      nguon_chu=NguonChu.ocr, do_tin=0.9)]
    llm = _LLM(_ra(truong=[_truong("diem", "Điểm", "10", "Tổng điểm tối đa là 10")]))
    ra = h.hieu_tai_lieu(ST, [{"id": A_ID, "ten_tep": "anh.pdf", "don_vi": dv}], llm, "m")
    d = ra["tai_lieu_du_kien_moi"][0]
    assert d["nguon"] == "tai_lieu_ocr" and d["neo"].do_tin == 0.9


def test_du_kien_trong_ket_qua_van_rong_khi_chua_ghi():
    """Node THUẦN không chạm DB: `du_kien` chỉ được điền ở vòng ghi của graph."""
    llm = _LLM(_ra(truong=[_truong("diem", "Điểm", "10", "Tổng điểm tối đa là 10")]))
    assert h.hieu_tai_lieu(ST, MOT, llm, "m")["tai_lieu_ket"]["du_kien"] == []


def test_muc_dich_trich_du_kien_khong_con_bi_ha_thanh_hoi():
    ra = h.hieu_tai_lieu(ST, MOT, _LLM(_ra(muc_dich="trich_du_kien")), "m")
    assert ra["tai_lieu_ket"]["muc_dich"] == "trich_du_kien"


# ────────────────────────────────────────────────────────────────── phép tính


def _pt(bieu_thuc, ket_qua, trich="Tổng điểm tối đa là 10"):
    return {"bieu_thuc": bieu_thuc, "ket_qua_tai_lieu": ket_qua, "trich": trich}


def test_phep_tinh_khop_ket_qua_do_MA_tinh():
    llm = _LLM(_ra(muc_dich="phan_tich", phep_tinh=[_pt("2,0 + 2,0 + 2,0 + 4,0", "10")]))
    ket = h.hieu_tai_lieu(ST, MOT, llm, "m")["tai_lieu_ket"]
    assert ket["phep_tinh"] == [{
        "bieu_thuc": "2,0 + 2,0 + 2,0 + 4,0",
        "ket_qua_code": "10",
        "ket_qua_tai_lieu": "10",
        "khop": True,
        "neo": ket["phep_tinh"][0]["neo"],
    }]
    assert ket["phep_tinh"][0]["neo"]["chi_so_don_vi"] == 1


def test_phep_tinh_lech_bao_khong_khop_chu_KHONG_sua_so_tai_lieu():
    llm = _LLM(_ra(phep_tinh=[_pt("2,0 + 2,0 + 2,0 + 4,0", "9")]))
    pt = h.hieu_tai_lieu(ST, MOT, llm, "m")["tai_lieu_ket"]["phep_tinh"][0]
    assert pt["khop"] is False and pt["ket_qua_code"] == "10" and pt["ket_qua_tai_lieu"] == "9"


def test_phep_tinh_khong_tinh_duoc_bi_bo():
    llm = _LLM(_ra(phep_tinh=[_pt("__import__('os')", "10"), _pt("10 / 0", "10")]))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert ra["tai_lieu_ket"]["phep_tinh"] == []
    assert ra["traces"]["hieu_tai_lieu_so_phep_tinh_bo"] == 2


def test_phep_tinh_khong_neo_duoc_bi_bo_va_dem():
    llm = _LLM(_ra(phep_tinh=[_pt("2 + 3", "5", "câu này không có trong tài liệu đâu nhé")]))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert ra["tai_lieu_ket"]["phep_tinh"] == []
    assert ra["traces"]["hieu_tai_lieu_so_phep_tinh_bo"] == 1
    assert ra["traces"]["hieu_tai_lieu_so_phep_tinh"] == 0


def test_phep_tinh_neo_ve_hang_bang():
    """Con số của một phép tính nằm trong một HÀNG bảng — cùng phép neo với quan sát."""
    llm = _LLM(_ra(phep_tinh=[_pt("2,0 + 2,0 + 2,0 + 4,0", "10", "Tổng\n10")]))
    ket = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")["tai_lieu_ket"]
    assert ket["phep_tinh"][0]["neo"]["chi_so_don_vi"] == 10 and ket["phep_tinh"][0]["khop"] is True


def test_traces_phep_tinh_va_truong_chi_mang_con_so():
    llm = _LLM(_ra(
        phep_tinh=[_pt("2,0 + 8,0", "10")],
        truong=[_truong("diem", "Điểm", "10", "Tổng điểm tối đa là 10")],
    ))
    t = h.hieu_tai_lieu(ST, MOT, llm, "m")["traces"]
    assert t["hieu_tai_lieu_so_phep_tinh"] == 1 and t["hieu_tai_lieu_so_truong_giu"] == 1
    for v in t.values():
        assert "Tổng điểm" not in str(v), "traces không được mang chữ của tài liệu"


# ─────────────────────────────────────────────────── vòng ghi ở graph_tra_cuu


def _hang_db(khoa="diem", viec_id=A_ID):
    return {"id": "eeeeeeee-0000-0000-0000-000000000005", "viec_id": viec_id, "hoi_thoai_id": HT_ID,
            "khoa": khoa, "nhan": "Điểm", "gia_tri": "10", "nguon": "tai_lieu",
            "trich": "Tổng điểm tối đa là 10", "trich_goc": None, "chi_so_don_vi": 1, "trang": 1,
            "offset_dau": 50, "do_tin": None, "tao_luc": None, "xoa_luc": None}


def _state_co_du_kien(**ghi_de):
    st = {
        "user_sub": SUB,
        "hoi_thoai_id": HT_ID,
        "tai_lieu_ket": {"du_kien": [], "tai_lieu_da_dung": [{"id": A_ID, "ten_tep": "phieu.docx", "nhan": "A"}]},
        "tai_lieu_du_kien_moi": [{
            "key": "diem", "nhan": "Điểm", "gia_tri": "10", "trich": "Tổng điểm tối đa là 10",
            "nguon": "tai_lieu", "tai_lieu_id": A_ID,
            "neo": Neo(LyDoNeo.ok, chi_so_don_vi=1, trang=1, offset_dau=50),
        }],
    }
    st.update(ghi_de)
    return st


def test_ghi_du_kien_goi_luu_theo_tung_tai_lieu(monkeypatch):
    from src.agents import graph_tra_cuu as g

    da_ghi = []
    monkeypatch.setattr(g.tl, "luu_du_kien",
                        lambda e, v, ht, dk: da_ghi.append((v, ht, dk)) or len(dk))
    monkeypatch.setattr(g.tl, "du_kien_cua_hoi_thoai", lambda e, ht, u: [_hang_db()])
    ra = g._ghi_du_kien_tai_lieu(None, _state_co_du_kien())
    assert [(v, ht) for v, ht, _ in da_ghi] == [(A_ID, HT_ID)]
    assert da_ghi[0][2][0]["key"] == "diem"
    assert ra["tai_lieu_du_kien_moi"] == [], "đã ghi thì không còn chờ ghi"


def test_ghi_du_kien_tra_ve_dong_DuKienOut_cua_tai_lieu_trong_luot(monkeypatch):
    from src.agents import graph_tra_cuu as g

    monkeypatch.setattr(g.tl, "luu_du_kien", lambda e, v, ht, dk: len(dk))
    monkeypatch.setattr(g.tl, "du_kien_cua_hoi_thoai",
                        lambda e, ht, u: [_hang_db(), _hang_db("khac", viec_id=B_ID)])
    du_kien = g._ghi_du_kien_tai_lieu(None, _state_co_du_kien())["tai_lieu_ket"]["du_kien"]
    assert [d["khoa"] for d in du_kien] == ["diem"], "tài liệu ngoài lượt không đi ra"
    assert set(du_kien[0]) == {"id", "khoa", "nhan", "gia_tri", "nguon", "trich", "trich_goc",
                               "trang", "chi_so_don_vi", "do_tin"}
    assert isinstance(du_kien[0]["id"], str)


def test_ghi_du_kien_bo_qua_khi_khach_chua_dang_nhap(monkeypatch):
    from src.agents import graph_tra_cuu as g

    def no(*a, **k):
        raise AssertionError("không được chạm DB khi chưa có chủ")

    monkeypatch.setattr(g.tl, "luu_du_kien", no)
    monkeypatch.setattr(g.tl, "du_kien_cua_hoi_thoai", no)
    st = _state_co_du_kien(user_sub=None)
    assert g._ghi_du_kien_tai_lieu(None, st) is st


def test_ghi_du_kien_bo_qua_khi_khong_co_du_kien_moi(monkeypatch):
    from src.agents import graph_tra_cuu as g

    def no(*a, **k):
        raise AssertionError("không có gì để ghi thì không đọc lại")

    monkeypatch.setattr(g.tl, "luu_du_kien", no)
    monkeypatch.setattr(g.tl, "du_kien_cua_hoi_thoai", no)
    st = _state_co_du_kien(tai_lieu_du_kien_moi=[])
    assert g._ghi_du_kien_tai_lieu(None, st) is st


# ───────────────────────────────────────────────── vùng trống của biểu mẫu
# Đo trên tệp mẫu 2026-09-16: `ho_ten_sinh_vien = "………………………………"`. Một biểu mẫu
# CHƯA ĐIỀN có đầy những dòng chấm, và chép chúng thành giá trị là dựng một
# bảng dữ kiện trông như đã điền — sai kiểu nguy hiểm nhất, vì nó đi thẳng vào
# một bản thảo (FR-011: trường chưa có nguồn thì để trống hoặc thành câu hỏi).

DV_MAU = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0,
                noi_dung="Họ và tên sinh viên: ………………………………………. Mã số: ……………….."),
    DonViVanBan(chi_so=1, trang=1, offset_dau=70,
                noi_dung="Thời gian thực tập: từ ngày … / … /20 … đến ngày … / … /20 …"),
    DonViVanBan(chi_so=2, trang=1, offset_dau=140, noi_dung="Địa điểm thực tập: Công ty TNHH Phenikaa"),
]
TL_MAU = [{"id": A_ID, "ten_tep": "phieu.docx", "don_vi": DV_MAU}]


@pytest.mark.parametrize(
    "gia_tri",
    ["……………………………………….", "...............", "…/…/20…", "— ", "___________", "… / … /20 …"],
)
def test_vung_trong_chua_dien_KHONG_thanh_du_kien(gia_tri):
    llm = _LLM(_ra(muc_dich="trich_du_kien", truong=[
        {"khoa": "ho_ten_sinh_vien", "nhan": "Họ và tên sinh viên", "gia_tri": gia_tri,
         "trich": "Họ và tên sinh viên: ………………………………………. Mã số: ……………….."},
    ]))
    ra = h.hieu_tai_lieu(ST, TL_MAU, llm, "m")
    assert ra["tai_lieu_du_kien_moi"] == []
    assert ra["traces"]["hieu_tai_lieu_so_truong_bo"] == 1


def test_gia_tri_THAT_van_di_qua():
    llm = _LLM(_ra(muc_dich="trich_du_kien", truong=[
        {"khoa": "dia_diem_thuc_tap", "nhan": "Địa điểm thực tập", "gia_tri": "Công ty TNHH Phenikaa",
         "trich": "Địa điểm thực tập: Công ty TNHH Phenikaa"},
    ]))
    ra = h.hieu_tai_lieu(ST, TL_MAU, llm, "m")
    assert [d["gia_tri"] for d in ra["tai_lieu_du_kien_moi"]] == ["Công ty TNHH Phenikaa"]


def test_so_co_dau_cham_lung_ben_canh_van_di_qua():
    """"20.000.000" không phải vùng trống dù có dấu chấm."""
    dv = [DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Lương chính thức: 20.000.000 đồng/tháng")]
    llm = _LLM(_ra(muc_dich="trich_du_kien", truong=[
        {"khoa": "luong", "nhan": "Lương", "gia_tri": "20.000.000",
         "trich": "Lương chính thức: 20.000.000 đồng/tháng"},
    ]))
    ra = h.hieu_tai_lieu(ST, [{"id": A_ID, "ten_tep": "hd.docx", "don_vi": dv}], llm, "m")
    assert [d["gia_tri"] for d in ra["tai_lieu_du_kien_moi"]] == ["20.000.000"]


def test_traces_TACH_ly_do_loai_truong():
    """Ba lý do, ba con số — cùng lý lẽ `LyDoNeo` không gộp nhãn: "biểu mẫu chưa
    điền" và "mô hình trích một câu không có thật" đòi hai cách sửa khác nhau."""
    llm = _LLM(_ra(muc_dich="trich_du_kien", truong=[
        {"khoa": "ho_ten", "nhan": "Họ tên", "gia_tri": "………………",
         "trich": "Họ và tên sinh viên: ………………………………………. Mã số: ……………….."},
        {"khoa": "noi_thuc_tap", "nhan": "Nơi thực tập", "gia_tri": "Công ty X",
         "trich": "Câu này không có trong tài liệu"},
        {"khoa": "", "nhan": "", "gia_tri": "", "trich": ""},
        {"khoa": "dia_diem_thuc_tap", "nhan": "Địa điểm", "gia_tri": "Công ty TNHH Phenikaa",
         "trich": "Địa điểm thực tập: Công ty TNHH Phenikaa"},
    ]))
    tr = h.hieu_tai_lieu(ST, TL_MAU, llm, "m")["traces"]
    assert tr["hieu_tai_lieu_so_truong_giu"] == 1
    assert tr["hieu_tai_lieu_so_truong_bo"] == 3
    assert tr["hieu_tai_lieu_truong_bo_vung_trong"] == 1
    assert tr["hieu_tai_lieu_truong_bo_khong_neo"] == 1
    assert tr["hieu_tai_lieu_truong_bo_sai_hinh_dang"] == 1
