"""Node `hieu_tai_lieu` — đọc tài liệu đính kèm thành quan sát CÓ NEO.

File này khoá năm điều:

1. Mọi `quan_sat` ra khỏi node đều neo được về MỘT đơn vị của ĐÚNG tài liệu mô
   hình chỉ tên. Cái không neo được bị loại và chỉ còn tồn tại trong `traces`
   dưới dạng một con số — cùng khuôn `rut_du_kien_bo_*`.
2. Nhãn tài liệu (`A`, `B`) là cách duy nhất mô hình chỉ được tài liệu nào; một
   đoạn trích của tài liệu B gán nhãn A KHÔNG được neo nhầm sang A.
3. Trần hình dạng (12 quan sát, 5 suy luận) cưỡng chế bằng mã, 0 token.
4. Tài liệu dài đi qua phép lọc THUẦN trước khi vào prompt.
5. Trần chi phí và lỗi hạ tầng KHÔNG sinh nội dung bịa — node nói thật là chưa
   đọc được, y hệt `rut_du_kien`.
"""

import json

import pytest

from src.agents.nodes import hieu_tai_lieu as h
from src.services.doc_tai_lieu import DonViVanBan
from src.services.tai_lieu import VuotTran

A_ID = "aaaaaaaa-0000-0000-0000-000000000001"
B_ID = "bbbbbbbb-0000-0000-0000-000000000002"

DV_A = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Phiếu đánh giá quá trình thực tập công nghiệp"),
    DonViVanBan(chi_so=1, trang=1, offset_dau=50, noi_dung="Tổng điểm tối đa là 10 cho bốn tiêu chí"),
]
DV_B = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Hợp đồng lao động số 12/2026 ký ngày 01/10/2026"),
]

TL = [
    {"id": A_ID, "ten_tep": "phieu.docx", "don_vi": DV_A},
    {"id": B_ID, "ten_tep": "hopdong.docx", "don_vi": DV_B},
]
MOT = [TL[0]]
ST = {"query": "phiếu này chấm theo tiêu chí nào"}


class _Usage:
    token_in, token_out, cost_usd = 10, 20, 0.001


class _LLM:
    def __init__(self, ra, no=False):
        self.ra, self.no, self.json_schema, self.prompt = ra, no, None, None

    def chat(self, model, messages, json_schema=None):
        self.json_schema, self.prompt = json_schema, messages[-1]["content"]
        if self.no:
            raise RuntimeError("openrouter 502")
        return json.dumps(self.ra, ensure_ascii=False), _Usage()


def _ra(**ghi_de) -> dict:
    ra = {"muc_dich": "hoi", "mo_ta": "Phiếu đánh giá thực tập", "tra_loi_ngan": "Phiếu chấm bốn tiêu chí.",
          "quan_sat": [], "suy_luan": [], "can_du_kien": []}
    ra.update(ghi_de)
    return ra


def _qs(noi_dung, trich, nhan="A"):
    return {"noi_dung": noi_dung, "trich": trich, "tai_lieu": nhan}


# ───────────────────────────────────────────────────────────── lọc đơn vị


def test_loc_don_vi_giu_ca_tai_lieu_khi_duoi_nguong_trang():
    assert h.loc_don_vi(DV_A, "tiêu chí") == DV_A


def test_loc_don_vi_tren_nguong_giu_dau_cong_trung_tu_khoa():
    dai = [
        DonViVanBan(chi_so=i, trang=i + 1, offset_dau=0, noi_dung=f"đoạn số {i} nói chuyện khác")
        for i in range(60)
    ]
    dai[55] = DonViVanBan(chi_so=55, trang=56, offset_dau=0, noi_dung="tổng điểm tối đa là 10")
    giu = h.loc_don_vi(dai, "tổng điểm tối đa")
    chi_so = [d.chi_so for d in giu]
    assert chi_so == sorted(chi_so), "giữ nguyên thứ tự đọc"
    assert len(giu) <= h.GIU_DAU + h.GIU_THEO_CAU_HOI
    assert list(range(h.GIU_DAU)) == chi_so[: h.GIU_DAU], "12 đơn vị đầu luôn ở lại"
    assert 55 in chi_so, "đơn vị trùng từ khoá với câu hỏi phải lọt"


def test_loc_don_vi_rong():
    assert h.loc_don_vi([], "x") == []


# ─────────────────────────────────────────────────────────────── lược đồ


def test_schema_enum_nhan_dung_so_tai_lieu():
    s = h.schema_hieu(["A", "B"])
    assert s["properties"]["quan_sat"]["items"]["properties"]["tai_lieu"]["enum"] == ["A", "B"]
    assert s["properties"]["muc_dich"]["enum"] == list(h.MUC_DICH)


def test_llm_nhan_dung_json_schema():
    llm = _LLM(_ra())
    h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert llm.json_schema == h.schema_hieu(["A"])


# ────────────────────────────────────────────────────────────── neo quan sát


def test_giu_quan_sat_co_trich_KHOP():
    llm = _LLM(_ra(quan_sat=[_qs("Thang điểm tối đa là 10.", "Tổng điểm tối đa là 10")]))
    ket = h.hieu_tai_lieu(ST, MOT, llm, "m")["tai_lieu_ket"]
    assert len(ket["quan_sat"]) == 1
    neo = ket["quan_sat"][0]["neo"]
    assert neo["tai_lieu_id"] == A_ID and neo["chi_so_don_vi"] == 1 and neo["trang"] == 1
    assert neo["vung"] == "than" and neo["bang"] is None and neo["nguon_chu"] == "lop_chu"


def test_bo_quan_sat_khong_neo_duoc_va_dem_theo_ly_do():
    llm = _LLM(
        _ra(
            quan_sat=[
                _qs("bịa", "Tổng điểm tối đa là 99 cho bốn tiêu chí"),
                _qs("ngắn", "10"),
                _qs("rỗng", ""),
            ]
        )
    )
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []
    t = ra["traces"]
    assert t["hieu_tai_lieu_bo_trich_khong_khop"] == 1
    assert t["hieu_tai_lieu_bo_trich_qua_ngan"] == 1
    assert t["hieu_tai_lieu_bo_trich_rong"] == 1
    assert t["hieu_tai_lieu_so_quan_sat_bo"] == 3 and t["hieu_tai_lieu_so_quan_sat_giu"] == 0


def test_trich_cua_tai_lieu_khac_KHONG_neo_nham_sang_tai_lieu_duoc_goi_ten():
    llm = _LLM(_ra(quan_sat=[_qs("của B nhưng gán A", "Hợp đồng lao động số 12/2026", "A")]))
    ra = h.hieu_tai_lieu(ST, TL, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []
    assert ra["traces"]["hieu_tai_lieu_bo_trich_khong_khop"] == 1


def test_nhan_dung_tai_lieu_thi_neo_ve_dung_id():
    llm = _LLM(_ra(quan_sat=[_qs("ngày ký", "Hợp đồng lao động số 12/2026", "B")]))
    ket = h.hieu_tai_lieu(ST, TL, llm, "m")["tai_lieu_ket"]
    assert ket["quan_sat"][0]["neo"]["tai_lieu_id"] == B_ID


def test_tai_lieu_da_dung_gan_nhan_theo_thu_tu():
    ket = h.hieu_tai_lieu(ST, TL, _LLM(_ra()), "m")["tai_lieu_ket"]
    assert ket["tai_lieu_da_dung"] == [
        {"id": A_ID, "ten_tep": "phieu.docx", "nhan": "A"},
        {"id": B_ID, "ten_tep": "hopdong.docx", "nhan": "B"},
    ]


def test_prompt_danh_so_don_vi_theo_nhan_tai_lieu():
    llm = _LLM(_ra())
    h.hieu_tai_lieu(ST, TL, llm, "m")
    assert "[A-0]" in llm.prompt and "[B-0]" in llm.prompt
    assert "(tr. 1" in llm.prompt


# ─────────────────────────────────────────────────────────────────── trần


def test_tran_quan_sat_va_suy_luan():
    llm = _LLM(
        _ra(
            quan_sat=[_qs(f"q{i}", "Tổng điểm tối đa là 10") for i in range(20)],
            suy_luan=[f"s{i}" for i in range(12)],
        )
    )
    ket = h.hieu_tai_lieu(ST, MOT, llm, "m")["tai_lieu_ket"]
    assert len(ket["quan_sat"]) == h.TOI_DA_QUAN_SAT
    assert len(ket["suy_luan"]) == h.TOI_DA_SUY_LUAN


# ────────────────────────────────────────────────────────────── mục đích


def test_muc_dich_ngoai_lat_cat_nay_duoc_ghi_lai_nhung_xu_nhu_hoi():
    llm = _LLM(_ra(muc_dich="so_sanh"))
    ra = h.hieu_tai_lieu(ST, TL, llm, "m")
    assert ra["muc_dich_tai_lieu"] == "so_sanh"
    assert ra["tai_lieu_ket"]["muc_dich"] == "hoi"


def test_muc_dich_trong_lat_cat_nay_giu_nguyen():
    ra = h.hieu_tai_lieu(ST, MOT, _LLM(_ra(muc_dich="tom_tat")), "m")
    assert ra["tai_lieu_ket"]["muc_dich"] == "tom_tat" and ra["muc_dich_tai_lieu"] == "tom_tat"


# ───────────────────────────────────────────────────── trần chi phí và lỗi


def test_vuot_tran_chi_phi_KHONG_goi_mo_hinh(monkeypatch):
    llm = _LLM(_ra())

    def no(_):
        raise VuotTran("chi_phi", 1, 2)

    monkeypatch.setattr(h, "kiem_tran_chi_phi_tai_lieu", no)
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert llm.json_schema is None, "không được gọi mô hình khi đã vượt trần"
    assert "quá dài" in ra["tai_lieu_ket"]["tra_loi_ngan"]
    assert ra["tai_lieu_ket"]["quan_sat"] == []
    assert ra["traces"]["hieu_tai_lieu_nguon"] == "vuot_tran"


def test_loi_ha_tang_khong_sinh_noi_dung_bia():
    ra = h.hieu_tai_lieu(ST, MOT, _LLM(None, no=True), "m")
    assert ra["traces"]["hieu_tai_lieu_nguon"] == "loi"
    assert ra["tai_lieu_ket"]["quan_sat"] == [] and ra["tai_lieu_ket"]["suy_luan"] == []
    assert "Chưa đọc được tài liệu" in ra["tai_lieu_ket"]["tra_loi_ngan"]


def test_phan_hoi_khong_phai_object_xu_nhu_loi():
    ra = h.hieu_tai_lieu(ST, MOT, _LLM(["khong", "phai", "object"]), "m")
    assert ra["traces"]["hieu_tai_lieu_nguon"] == "loi"


def test_khong_co_tai_lieu_nao_thi_khong_goi_mo_hinh():
    llm = _LLM(_ra())
    ra = h.hieu_tai_lieu(ST, [], llm, "m")
    assert llm.json_schema is None
    assert ra["tai_lieu_ket"]["quan_sat"] == []


# ─────────────────────────────────────────────────────────────── traces


def test_traces_chi_mang_con_so_KHONG_mang_chu_cua_tai_lieu():
    llm = _LLM(_ra(quan_sat=[_qs("Thang điểm tối đa là 10.", "Tổng điểm tối đa là 10")]))
    t = h.hieu_tai_lieu(ST, MOT, llm, "m")["traces"]
    assert t["hieu_tai_lieu_so_don_vi_gui"] == 2 and t["hieu_tai_lieu_so_quan_sat_giu"] == 1
    assert t["hieu_tai_lieu_token_in"] == 10 and t["hieu_tai_lieu_cost_usd"] == 0.001
    assert t["hieu_tai_lieu_model"] == "m"
    for v in t.values():
        assert "Tổng điểm" not in str(v), "traces không được mang chữ của tài liệu"


def test_traces_cu_duoc_giu_nguyen():
    ra = h.hieu_tai_lieu({**ST, "traces": {"route_model": "x"}}, MOT, _LLM(_ra()), "m")
    assert ra["traces"]["route_model"] == "x"


@pytest.mark.parametrize("khoa", ["tai_lieu_ket", "muc_dich_tai_lieu", "tai_lieu_neo"])
def test_node_tra_ve_du_khoa_state(khoa):
    assert khoa in h.hieu_tai_lieu(ST, MOT, _LLM(_ra()), "m")
