"""Node `rut_du_kien` — rút dữ kiện từ tài liệu người dùng (spec 2026-09-15 §FR-006/007).

File này khoá bốn điều:

1. Lược đồ structured output DÙNG LẠI `truong_cua(loai)` của `gom_du_kien`,
   không định nghĩa bộ trường thứ hai. Hai bộ trường song song sẽ lệch nhau, và
   lệch ở đây nghĩa là dữ kiện rút ra không điền được vào biểu mẫu.
2. Mỗi trường BẮT BUỘC kèm `trich`. Không có chỗ nào cho một dữ kiện không
   trích dẫn.
3. Dữ kiện có `trich` không tra ngược được BỊ LOẠI trước khi ra khỏi node —
   người dùng không bao giờ nhìn thấy nó (FR-007).
4. Lỗi hạ tầng của LLM không sinh ra dữ kiện bịa: node trả rỗng và ghi nguồn
   `loi`, chứ không đoán.
"""

import json

from src.agents.nodes.gom_du_kien import truong_cua
from src.agents.nodes.rut_du_kien import _dong_tai_lieu, rut_du_kien, schema_rut
from src.services.doc_tai_lieu import DonViVanBan, TaiLieuDaDoc
from src.services.neo_du_kien import LyDoNeo

LOAI = "hdld"
DV = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Lương chính thức: 20.000.000 đồng/tháng"),
    DonViVanBan(chi_so=1, trang=1, offset_dau=40, noi_dung="Thời gian thử việc: 60 ngày"),
]
TL = TaiLieuDaDoc(don_vi=DV, so_trang=1, so_ky_tu=70)


class _Usage:
    token_in, token_out, cost_usd = 10, 20, 0.001


class _LLM:
    def __init__(self, ra, no=False):
        self.ra, self.no, self.json_schema = ra, no, None

    def chat(self, model, messages, json_schema=None):
        self.json_schema = json_schema
        if self.no:
            raise RuntimeError("openrouter 502")
        return json.dumps(self.ra), _Usage()


# --------------------------------------------------------- prompt tài liệu


def test_dong_tai_lieu_bo_don_vi_rong_chu():
    """Phase 11 fix round 3 (reviewer I4) — `doc_tai_lieu` (Phase 11 fix round
    2) giờ giữ cả ô bảng RỖNG CHỮ, để `hieu_tai_lieu._bang_theo_nhan` dựng lại
    đủ hàng/cột thật. Node này (sibling của `loc_don_vi`, cũng đọc `don_vi`)
    không được lọc theo cùng luật thì mỗi ô trống của một biểu mẫu chưa điền
    ra một dòng `[N] (trang X) ` không chữ trong PROMPT — tốn tiền mỗi lượt
    rút dữ kiện mà không có gì để mô hình đọc hay trích."""
    dv = [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Lương chính thức: 20.000.000 đồng/tháng"),
        DonViVanBan(chi_so=1, trang=1, offset_dau=40, noi_dung="", bang=(0, 0, 1)),
    ]
    tl = TaiLieuDaDoc(don_vi=dv, so_trang=1, so_ky_tu=40)
    dong = _dong_tai_lieu(tl)
    assert dong == "[0] (trang 1) Lương chính thức: 20.000.000 đồng/tháng", (
        "ô rỗng chữ không được ra dòng contentless trong prompt"
    )


def _day_du(**ghi_de) -> dict:
    ra = {t["key"]: {"gia_tri": "", "trich": ""} for t in truong_cua(LOAI)}
    ra.update(ghi_de)
    return ra


# ------------------------------------------------------------------- lược đồ


def test_schema_dung_lai_truong_cua():
    s = schema_rut(LOAI)
    assert set(s["properties"]) == {t["key"] for t in truong_cua(LOAI)}


def test_schema_moi_truong_BAT_BUOC_co_trich():
    for key, p in schema_rut(LOAI)["properties"].items():
        assert p["required"] == ["gia_tri", "trich"], key


def test_schema_giu_enum_cua_truong_co_lua_chon():
    t = next(t for t in truong_cua(LOAI) if t.get("lua_chon"))
    p = schema_rut(LOAI)["properties"][t["key"]]["properties"]["gia_tri"]
    assert p["enum"] == ["", *t["lua_chon"]]


# --------------------------------------------------------------------- rút


def test_giu_du_kien_co_trich_KHOP():
    llm = _LLM(_day_du(luong_chinh_thuc={"gia_tri": "20000000", "trich": "Lương chính thức: 20.000.000 đồng/tháng"}))
    ra = rut_du_kien(LOAI, TL, llm, "m")
    assert [f["key"] for f in ra["du_kien"]] == ["luong_chinh_thuc"]
    assert ra["du_kien"][0]["neo"].ly_do is LyDoNeo.ok
    assert ra["du_kien"][0]["neo"].trang == 1


def test_LOAI_du_kien_co_trich_KHONG_KHOP():
    llm = _LLM(_day_du(luong_chinh_thuc={"gia_tri": "99000000", "trich": "Lương chính thức: 99.000.000 đồng/tháng"}))
    ra = rut_du_kien(LOAI, TL, llm, "m")
    assert ra["du_kien"] == []
    assert [f["key"] for f in ra["bo"]] == ["luong_chinh_thuc"]
    assert ra["bo"][0]["neo"].ly_do is LyDoNeo.trich_khong_khop


def test_MOI_du_kien_tra_ra_deu_co_neo_ok():
    llm = _LLM(
        _day_du(
            luong_chinh_thuc={"gia_tri": "20000000", "trich": "Lương chính thức: 20.000.000 đồng/tháng"},
            thoi_gian_thu_viec_ngay={"gia_tri": "60", "trich": "Thời gian thử việc: 99 ngày"},
        )
    )
    ra = rut_du_kien(LOAI, TL, llm, "m")
    assert all(f["neo"].ly_do is LyDoNeo.ok for f in ra["du_kien"])
    assert len(ra["du_kien"]) == 1 and len(ra["bo"]) == 1


def test_truong_TRONG_khong_thanh_du_kien():
    ra = rut_du_kien(LOAI, TL, _LLM(_day_du()), "m")
    assert ra["du_kien"] == [] and ra["bo"] == []


def test_loi_LLM_khong_sinh_du_kien_bia():
    ra = rut_du_kien(LOAI, TL, _LLM(None, no=True), "m")
    assert ra["du_kien"] == [] and ra["bo"] == []
    assert ra["traces"]["rut_du_kien_nguon"] == "loi"


def test_phan_hoi_khong_phai_object_xu_nhu_loi():
    ra = rut_du_kien(LOAI, TL, _LLM(["khong", "phai", "object"]), "m")
    assert ra["du_kien"] == [] and ra["traces"]["rut_du_kien_nguon"] == "loi"


def test_llm_nhan_dung_json_schema():
    llm = _LLM(_day_du())
    rut_du_kien(LOAI, TL, llm, "m")
    assert llm.json_schema == schema_rut(LOAI)


def test_traces_tach_theo_TUNG_ly_do_bo():
    llm = _LLM(
        _day_du(
            luong_chinh_thuc={"gia_tri": "1", "trich": "khong co trong tai lieu nay dau"},
            luong_thu_viec={"gia_tri": "2", "trich": "ngan"},
            luong_thang={"gia_tri": "3", "trich": ""},
        )
    )
    t = rut_du_kien(LOAI, TL, llm, "m")["traces"]
    assert t["rut_du_kien_bo_trich_khong_khop"] == 1
    assert t["rut_du_kien_bo_trich_qua_ngan"] == 1
    assert t["rut_du_kien_bo_trich_rong"] == 1


def test_traces_ghi_chi_phi():
    t = rut_du_kien(LOAI, TL, _LLM(_day_du()), "m")["traces"]
    assert t["rut_du_kien_token_in"] == 10 and t["rut_du_kien_cost_usd"] == 0.001
