"""Biên HTTP của lượt hỏi VỀ TÀI LIỆU — phần THUẦN, không DB, không LLM.

Ba chỗ nối dây phải khớp nhau, và mỗi chỗ đã từng hỏng câm một lần trong dự án:

* `_state_vao` phải mang `tai_lieu_ids`/`tai_lieu_phien` vào state, nếu không
  `_vao_graph`/`route` không bao giờ thấy tài liệu;
* cache phải TẮT cho lượt có tài liệu, nếu không hai hội thoại cùng câu hỏi
  nhận câu trả lời của nhau;
* `BUOC_TRA_CUU` phải có `hieu_tai_lieu` đúng chỗ, nếu không một bước THẬT biến
  mất khỏi thanh tiến trình SSE.
"""

from src.api.routes import BUOC_TRA_CUU, _bo_qua_cache, _state_vao, chi_tiet_buoc
from src.models.schemas import TraCuuRequest

ID = "11111111-1111-1111-1111-111111111111"
PHIEN = [{"id": ID, "ten_tep": "phieu.docx", "so_trang": 1, "so_don_vi": 34,
          "loai": None, "mo_ta": None, "co_ocr": False}]


# ─────────────────────────────────────────────────────────────── _state_vao


def test_state_vao_mang_tai_lieu_ids_dang_chuoi():
    req = TraCuuRequest(query="tóm tắt tài liệu này", tai_lieu_ids=[ID])
    st = _state_vao(req, None, "t", tai_lieu_phien=PHIEN)
    assert st["tai_lieu_ids"] == [ID] and all(isinstance(x, str) for x in st["tai_lieu_ids"])
    assert st["tai_lieu_phien"] == PHIEN


def test_state_vao_mac_dinh_rong():
    st = _state_vao(TraCuuRequest(query="x"), None, "t")
    assert st["tai_lieu_ids"] == [] and st["tai_lieu_phien"] == []


def test_request_chan_qua_hai_tai_lieu():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TraCuuRequest(query="x", tai_lieu_ids=[ID, ID, ID])


# ──────────────────────────────────────────────────────────── bỏ qua cache


def test_bo_qua_cache_khi_co_tai_lieu_dinh_kem():
    req = TraCuuRequest(query="x", tai_lieu_ids=[ID])
    assert _bo_qua_cache(req, None, None, []) is True


def test_bo_qua_cache_khi_hoi_thoai_da_co_tai_lieu():
    assert _bo_qua_cache(TraCuuRequest(query="x"), None, None, PHIEN) is True


def test_khong_bo_qua_cache_cho_luot_thuong():
    assert _bo_qua_cache(TraCuuRequest(query="x"), None, None, []) is False


def test_cac_dieu_kien_cu_van_tat_cache():
    from src.models.schemas import LuotTruoc

    req = TraCuuRequest(query="x", lich_su=[LuotTruoc(cau_hoi="a")])
    assert _bo_qua_cache(req, None, None, []) is True
    assert _bo_qua_cache(TraCuuRequest(query="x"), {"tom_tat": "t", "ho_so": {}}, None, []) is True
    assert _bo_qua_cache(TraCuuRequest(query="x"), None, {"loai": "hdld"}, []) is True


# ────────────────────────────────────────────────────────── bước tiến trình


def test_buoc_hieu_tai_lieu_ngay_sau_route():
    ten = [t for t, _ in BUOC_TRA_CUU]
    assert ten[ten.index("route") + 1] == "hieu_tai_lieu"


def test_chi_tiet_buoc_hieu_tai_lieu_dem_quan_sat():
    st = {"tai_lieu_ket": {"quan_sat": [{}, {}]}}
    assert chi_tiet_buoc("hieu_tai_lieu", st) == {"so_quan_sat": 2}
    assert chi_tiet_buoc("hieu_tai_lieu", {}) == {"so_quan_sat": 0}
