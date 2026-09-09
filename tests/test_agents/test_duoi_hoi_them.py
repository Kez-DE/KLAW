"""Task 14: đuôi hỏi thêm ở cuối một câu trả lời ĐÃ CÓ luận điểm, và abstain
không còn liệt kê văn bản trước khi hỏi lại — xem brief 2026-09-09 §14."""

from src.agents.nodes import assemble as as_mod
from src.agents.nodes import hoi_lai


def test_duoi_hoi_them_toi_da_hai_chieu_con_trong_theo_thu_tu_mac_dinh():
    duoi = hoi_lai.duoi_hoi_them({})
    assert duoi.startswith(hoi_lai.CAU_DAN_DUOI)
    assert duoi.count("\n- ") == 2 and "phía nào" in duoi and "thời hạn thế nào" in duoi
    duoi2 = hoi_lai.duoi_hoi_them({"chu_the": {"gia_tri": "người lao động", "nguon": "suy_dien"}})
    assert "phía nào" not in duoi2 and "thời hạn thế nào" in duoi2 and "khoảng thời gian nào" in duoi2
    du = {k: {"gia_tri": "x", "nguon": "nguoi_noi"} for k in hoi_lai.MAC_DINH}
    assert hoi_lai.duoi_hoi_them(du) == ""


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
