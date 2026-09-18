"""Router v4 — ý định `tai_lieu` CHỈ tồn tại khi hội thoại thật sự có tài liệu
(quyết định chủ sở hữu 2026-09-16 Q4).

Ba điều bị khoá ở đây:

1. Enum `intent` của `schema_v4` mở thêm `tai_lieu` theo ĐIỀU KIỆN. Mở vô điều
   kiện là mời model rẽ một lượt hỏi luật bình thường sang nhánh đọc tài liệu
   khi chẳng có tài liệu nào để đọc.
2. Template chọn theo NỘI DUNG (`{tai_lieu_trong_phien}`), không theo tên file —
   cùng quy ước `route()` đã lập cho v2/v3.
3. Một `intent="tai_lieu"` trả về khi phiên KHÔNG có tài liệu bị hạ xuống
   `tra_cuu` bằng phép kiểm 0 token, không đi tiếp vào một node không có gì đọc.
"""

import json
from pathlib import Path

import pytest

from src.agents.graph_tra_cuu import _re_sau_route, _vao_graph
from src.agents.nodes import route as r
from src.services.llm import Usage

V4 = Path("prompts/route.v4.md")

PHIEN = [
    {"id": "11111111-1111-1111-1111-111111111111", "ten_tep": "phieu.docx", "so_trang": 1,
     "so_don_vi": 34, "loai": None, "mo_ta": "Phiếu đánh giá thực tập", "co_ocr": False},
]


class LlmGia:
    def __init__(self, tra):
        self.tra, self.da_goi = tra, []

    def chat(self, model, messages, json_schema=None):
        self.da_goi.append((messages, json_schema))
        return json.dumps(self.tra, ensure_ascii=False), Usage(1, 1, 0.0)


def _tra(intent="tra_cuu"):
    return {"intent": intent, "loai_van_ban": "khong_ro", "thay_the": [], "ly_do": "",
            "dang_tra_loi": "van_xuoi", "y_dinh_phu": "khong"}


# ─────────────────────────────────────────────────────────────────── lược đồ


def test_schema_v4_KHONG_co_tai_lieu_khi_phien_khong_co_tai_lieu():
    enum = r.schema_v4(False)["properties"]["intent"]["enum"]
    assert "tai_lieu" not in enum
    assert set(enum) == set(r.INTENT_SCHEMA["properties"]["intent"]["enum"])


def test_schema_v4_co_tai_lieu_khi_phien_co_tai_lieu():
    assert "tai_lieu" in r.schema_v4(True)["properties"]["intent"]["enum"]


def test_schema_v4_giu_nguyen_phan_v3():
    s = r.schema_v4(True)
    assert {"dang_tra_loi", "y_dinh_phu", "loai_van_ban", "thay_the", "ly_do"} <= set(s["required"])


def test_schema_v4_KHONG_lam_ban_enum_dung_chung():
    """`schema_v2`/`schema_v3` dùng CHUNG một list `_INTENT_ENUM`; thêm bằng
    `.append` sẽ rò `tai_lieu` sang mọi bản template cũ."""
    r.schema_v4(True)
    assert "tai_lieu" not in r.schema_v3()["properties"]["intent"]["enum"]
    assert "tai_lieu" not in r.INTENT_SCHEMA["properties"]["intent"]["enum"]


# ───────────────────────────────────────────────── khối {tai_lieu_trong_phien}


def test_tai_lieu_trong_phien_rong():
    assert r._tai_lieu_trong_phien(None) == "(không)"
    assert r._tai_lieu_trong_phien([]) == "(không)"


def test_tai_lieu_trong_phien_mot_dong_moi_tai_lieu():
    dong = r._tai_lieu_trong_phien(PHIEN)
    assert dong == "- phieu.docx — Phiếu đánh giá thực tập (34 đơn vị)"


def test_tai_lieu_trong_phien_chua_co_mo_ta():
    dong = r._tai_lieu_trong_phien([{**PHIEN[0], "mo_ta": None}])
    assert "chưa mô tả" in dong


# ──────────────────────────────────────────────────────── chọn template + gọi


def test_route_nhan_ra_v4_theo_NOI_DUNG_va_dung_schema_co_dieu_kien():
    llm = LlmGia(_tra())
    r.route({"query": "tài liệu này nói gì", "tai_lieu_phien": PHIEN}, llm, "m", prompt_path=V4)
    assert llm.da_goi[0][1] == r.schema_v4(True)


def test_route_v4_khong_co_tai_lieu_thi_schema_khong_mo_intent_moi():
    llm = LlmGia(_tra())
    r.route({"query": "thử việc bao lâu"}, llm, "m", prompt_path=V4)
    assert llm.da_goi[0][1] == r.schema_v4(False)


def test_route_v4_chon_tai_lieu_khi_phien_co_tai_lieu():
    llm = LlmGia(_tra("tai_lieu"))
    st = r.route({"query": "tóm tắt phiếu này", "tai_lieu_phien": PHIEN}, llm, "m", prompt_path=V4)
    assert st["intent"] is r.Intent.tai_lieu


def test_route_v4_cau_hoi_luat_thuan_van_la_tra_cuu_du_co_tai_lieu():
    llm = LlmGia(_tra("tra_cuu"))
    st = r.route({"query": "thử việc tối đa bao nhiêu ngày", "tai_lieu_phien": PHIEN},
                 llm, "m", prompt_path=V4)
    assert st["intent"] is r.Intent.tra_cuu


def test_tai_lieu_khi_phien_RONG_bi_ha_xuong_tra_cuu():
    """Phép kiểm 0 token: không có tài liệu nào thì `hieu_tai_lieu` không có gì
    để đọc — rẽ vào đó là một ngõ cụt câm."""
    llm = LlmGia(_tra("tai_lieu"))
    st = r.route({"query": "tóm tắt phiếu này"}, llm, "m", prompt_path=V4)
    assert st["intent"] is r.Intent.tra_cuu


def test_prompt_v4_ta_du_moi_intent_ke_ca_tai_lieu():
    mau = V4.read_text(encoding="utf-8")
    thieu = [i.value for i in r.Intent if f"`{i.value}`" not in mau]
    assert not thieu, f"{thieu} không được mô tả trong {V4}"
    assert "{tai_lieu_trong_phien}" in mau
    # QT-3: tên tệp và mô tả là chữ của người dùng đi vào prompt.
    assert "dữ liệu" in mau


# ───────────────────────────────────────────────────────────────── rẽ nhánh


def test_re_sau_route_dua_tai_lieu_sang_hieu_tai_lieu():
    assert _re_sau_route({"intent": r.Intent.tai_lieu}) == "hieu_tai_lieu"


@pytest.mark.parametrize(
    "intent,mong",
    # `soan_thao` không `user_sub` là khách → `assemble` (Phase 14, lời mời đăng
    # nhập 0 token); các đường có danh tính xem `test_re_tat_som`.
    [(r.Intent.tra_cuu, "tien_de"), (r.Intent.soan_thao, "assemble"),
     (r.Intent.gioi_thieu, "assemble")],
)
def test_re_sau_route_khong_doi_cac_nhanh_cu(intent, mong):
    assert _re_sau_route({"intent": intent}) == mong


def test_vao_graph_co_tai_lieu_dinh_kem_di_thang_hieu_tai_lieu():
    """Lượt đính kèm tài liệu rẽ TẤT ĐỊNH, 0 token: không qua `route`."""
    assert _vao_graph({"tai_lieu_ids": ["x"], "lich_su": [{"cau_hoi": "a"}]}) == "hieu_tai_lieu"
    assert _vao_graph({"tai_lieu_ids": ["x"]}) == "hieu_tai_lieu"


def test_vao_graph_khong_doi_khi_khong_dinh_kem():
    assert _vao_graph({"tai_lieu_ids": []}) == "suy_dien"
    assert _vao_graph({"lich_su": [{"cau_hoi": "a"}]}) == "giai_nghia"
