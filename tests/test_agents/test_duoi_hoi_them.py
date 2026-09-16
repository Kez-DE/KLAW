"""Đuôi hỏi thêm ở cuối một câu trả lời ĐÃ CÓ luận điểm, và abstain không còn
liệt kê văn bản trước khi hỏi lại — Task 14, brief 2026-09-09 §14.

HỢP ĐỒNG ĐỔI 2026-09-16 (spec `2026-09-16-tra-loi-ngan-dung-muc-tieu` §FR-011):
đuôi KHÔNG còn hỏi mọi chiều hồ sơ còn trống. Nó chỉ xuất hiện khi CHÍNH LƯỢT ĐÓ
vừa suy ra một giả định, và chỉ hỏi đúng chiều vừa suy ra.

Vì sao hẹp lại: ba chiều `MAC_DINH` được hỏi bất kể chúng có làm đổi kết luận hay
không — đúng hành vi máy móc mà `cai_thien.md` §4.2.7 đo được. Vì sao KHÔNG bỏ
hẳn: quyết định 2026-09-09 ("giả định có kiểm soát") mua bằng bằng chứng cái vế
"nêu giả định rồi hỏi đúng dữ kiện đó", và `eval/run_mo_ho` chấm đúng vế ấy.
"""

from src.agents.nodes import assemble as as_mod
from src.agents.nodes import hoi_lai


def test_khong_co_gia_dinh_moi_thi_khong_hoi_gi_du_ho_so_trong_rong():
    """Hồ sơ trống KHÔNG còn là lý do để hỏi: không chứng minh được rằng ba chiều
    đó làm đổi kết luận của chính câu vừa trả lời."""
    assert hoi_lai.duoi_hoi_them({}, None) == ""
    assert hoi_lai.duoi_hoi_them({}, "") == ""


def test_vua_suy_ra_vai_thi_hoi_dung_vai_va_chi_mot_cau():
    duoi = hoi_lai.duoi_hoi_them({"chu_the": {"gia_tri": "người lao động", "nguon": "suy_dien"}},
                                 "người lao động")
    assert duoi.startswith(hoi_lai.CAU_DAN_DUOI)
    assert duoi.count("\n- ") == 1 and "phía nào" in duoi
    assert "thời hạn thế nào" not in duoi and "khoảng thời gian nào" not in duoi


def test_gia_dinh_mang_sang_tu_luot_truoc_khong_mo_lai_cau_hoi():
    """`suy_dien` chỉ suy khi hồ sơ CÒN TRỐNG vai, nên một giá trị `suy_dien` có
    sẵn mà lượt này không sinh ra thì tín hiệu rỗng — và đuôi phải im."""
    ho_so = {"chu_the": {"gia_tri": "người lao động", "nguon": "suy_dien"}}
    assert hoi_lai.duoi_hoi_them(ho_so, None) == ""


def test_nguoi_dung_da_noi_vai_thi_khong_hoi_lai():
    ho_so = {"chu_the": {"gia_tri": "công ty", "nguon": "nguoi_noi"}}
    assert hoi_lai.duoi_hoi_them(ho_so, None) == ""


def test_duoi_vuot_tran_ky_tu_thi_bo_han_khong_xen():
    """Cắt một câu hỏi làm đôi tệ hơn là không hỏi (spec §FR-021)."""
    goc = hoi_lai.CHIEU["chu_the"]
    try:
        hoi_lai.CHIEU["chu_the"] = "x" * (hoi_lai.TRAN_DUOI + 1)
        assert hoi_lai.duoi_hoi_them({}, "người lao động") == ""
    finally:
        hoi_lai.CHIEU["chu_the"] = goc


def test_duoi_dat_tran_thi_van_hoi():
    assert len(hoi_lai.duoi_hoi_them({}, "người lao động")) <= hoi_lai.TRAN_DUOI


def test_toi_da_hoi_lai_la_2():
    assert hoi_lai.TOI_DA == 2 and hoi_lai.HOI_LAI_SCHEMA["properties"]["chieu"]["maxItems"] == 2


def test_ngo_cut_khong_liet_ke_van_ban():
    class LlmNo:
        def chat(self, *a, **k):
            raise RuntimeError("x")

    st = {
        "query": "tôi bị trừ lương",
        "traces": {},
        "hits_shallow": [{"so_ky_hieu": "45/2019/QH14", "ten": "Bộ luật Lao động"}],
    }
    ket = as_mod._ngo_cut(st, LlmNo(), "m", as_mod.ResultType.abstain)
    assert ket["coverage_note"].startswith(as_mod.KHONG_TIM_DUOC)
    assert "khớp từ ngữ" not in ket["coverage_note"] and "45/2019" not in ket["coverage_note"]
