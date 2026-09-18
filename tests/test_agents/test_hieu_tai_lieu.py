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
        self.so_lan_goi = 0

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        self.json_schema, self.prompt = json_schema, messages[-1]["content"]
        self.so_lan_goi += 1
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


def test_loc_don_vi_bo_o_bang_rong_chu_khong_gui_mo_hinh():
    """Phase 11 fix round 2 — `doc_tai_lieu` giờ giữ cả ô bảng rỗng chữ (để
    dựng lại đủ hàng trắng của một biểu mẫu, xem `doc_tai_lieu._duyet_than`),
    nhưng một ô rỗng không có gì để mô hình đọc hay trích — `loc_don_vi` (phần
    ĐI VÀO PROMPT) phải bỏ nó, không gửi một dòng không chữ tốn token. Bảng
    dựng lại vẫn đủ hàng vì `_khop_bang` đọc `t["don_vi"]` (TOÀN BỘ), không
    phải `t["gui"]`."""
    co_o_rong = [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="STT", bang=(0, 0, 0)),
        DonViVanBan(chi_so=1, trang=1, offset_dau=5, noi_dung="", bang=(0, 1, 0)),
    ]
    assert h.loc_don_vi(co_o_rong, "x") == [co_o_rong[0]]


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
    """`doi_chieu_luat` là đường của S5; tới đó thì node vẫn GHI LẠI mục đích
    thật (`muc_dich_tai_lieu`) nhưng trả lời như một câu hỏi thường."""
    llm = _LLM(_ra(muc_dich="doi_chieu_luat"))
    ra = h.hieu_tai_lieu(ST, TL, llm, "m")
    assert ra["muc_dich_tai_lieu"] == "doi_chieu_luat"
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


# ───────────────────────────────────────────────────────────── neo hàng bảng
# Đo trên tệp mẫu 2026-09-16: mô hình đọc bảng theo HÀNG (các ô nối bằng xuống
# dòng) nên 13/13 quan sát bị loại khi chỉ so với từng ô. Neo hàng bảng vẫn là
# tra chuỗi thuần, chỉ nới đúng một điều: một hàng duy nhất cũng là một vị trí.


def _o(chi_so, noi_dung, b, h_, c):
    return DonViVanBan(chi_so=chi_so, trang=1, offset_dau=chi_so * 10, noi_dung=noi_dung, bang=(b, h_, c))


DV_BANG = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Phiếu đánh giá quá trình thực tập công nghiệp"),
    _o(1, "TT", 0, 0, 0), _o(2, "Tiêu chí đánh giá", 0, 0, 1), _o(3, "Điểm tối đa", 0, 0, 2),
    _o(4, "1", 0, 1, 0), _o(5, "Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập", 0, 1, 1), _o(6, "2,0", 0, 1, 2),
    _o(7, "2", 0, 2, 0), _o(8, "Tinh thần trách nhiệm, thái độ đối với công việc", 0, 2, 1), _o(9, "2,0", 0, 2, 2),
    _o(10, "Tổng", 0, 3, 1), _o(11, "10", 0, 3, 2),
]
TL_BANG = [{"id": A_ID, "ten_tep": "phieu.docx", "don_vi": DV_BANG}]


def test_trich_ca_hang_bang_neo_ve_o_nhieu_chu_nhat_cua_hang():
    llm = _LLM(_ra(quan_sat=[_qs("Tiêu chí 1 tối đa 2,0 điểm",
                                 "1\nÝ thức chấp hành nội quy, kỷ luật tại đơn vị thực tập\n2,0")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    qs = ra["tai_lieu_ket"]["quan_sat"]
    assert len(qs) == 1
    assert qs[0]["neo"]["chi_so_don_vi"] == 5 and qs[0]["neo"]["bang"] == [0, 1, 1]
    assert ra["traces"]["hieu_tai_lieu_so_quan_sat_bo"] == 0


def test_hang_chi_toan_o_ngan_van_neo_khi_hang_la_duy_nhat():
    llm = _LLM(_ra(quan_sat=[_qs("Tổng điểm 10", "Tổng\n10")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [10]


def test_hang_khong_duy_nhat_bi_loai():
    """"2,0" khớp hai hàng — không định danh được vị trí → loại, không đoán hàng."""
    llm = _LLM(_ra(quan_sat=[_qs("điểm 2,0", "2,0\n2,0")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []
    assert ra["traces"]["hieu_tai_lieu_so_quan_sat_bo"] == 1


def test_manh_khong_thuoc_bang_lam_hong_ca_hang():
    llm = _LLM(_ra(quan_sat=[_qs("x", "1\nÝ thức chấp hành nội quy, kỷ luật tại đơn vị thực tập\nkhông có trong bảng")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []


def test_trich_mot_o_don_van_neo_nhu_cu():
    llm = _LLM(_ra(quan_sat=[_qs("tiêu chí 2", "Tinh thần trách nhiệm, thái độ đối với công việc")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [8]


def test_vi_tri_bang_trong_prompt_dem_tu_1():
    llm = _LLM(_ra())
    h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert "bảng 1 hàng 2 cột 2" in llm.prompt
    assert "bảng 0" not in llm.prompt


# ───────────────────────────────────────────────────── tiền tố đánh số bị chép
# Đo trên fixture 2026-09-16: mô hình chép nguyên dòng prompt `[A-0] (tr. 1) …`
# vào `trich`. Tiền tố là của prompt, không phải của tài liệu — bỏ nó đi rồi
# vẫn tra chuỗi theo NỘI DUNG; số chỉ mục trong tiền tố không được tin.


def test_trich_mang_tien_to_danh_so_van_neo_theo_noi_dung():
    llm = _LLM(_ra(quan_sat=[_qs("tiêu đề", "[A-0] (tr. 1) Phiếu đánh giá quá trình thực tập công nghiệp")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [0]
    assert ra["tai_lieu_ket"]["quan_sat"][0]["trich"] == "Phiếu đánh giá quá trình thực tập công nghiệp"


def test_tien_to_sai_chi_so_khong_lam_neo_nham():
    """Tiền tố nói `[A-5]` nhưng chữ là của đơn vị 0 → neo theo CHỮ, về 0."""
    llm = _LLM(_ra(quan_sat=[_qs("x", "[A-5] (tr. 1, bảng 1 hàng 2 cột 2) Phiếu đánh giá quá trình thực tập công nghiệp")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [0]


def test_hang_bang_co_tien_to_moi_dong_van_neo():
    trich = "[A-4] (tr. 1, bảng 1 hàng 2 cột 1) 1\n[A-5] (tr. 1, bảng 1 hàng 2 cột 2) Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập\n[A-6] (tr. 1, bảng 1 hàng 2 cột 3) 2,0"
    llm = _LLM(_ra(quan_sat=[_qs("tiêu chí 1", trich)]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [5]


def test_trich_theo_cot_MOI_MANH_DUY_NHAT_thi_neo_ve_manh_dau():
    """Hai ô của hai hàng khác nhau: không liền kề, nhưng mảnh nào cũng chỉ tới
    đúng một ô. Khẳng định yếu đi đúng chừng ấy — "những mẩu này có trong tài
    liệu" — và neo trỏ vào mảnh đầu. Bản trước của test này đòi loại cả trích;
    đo trên tệp mẫu 2026-09-16 cho thấy luật đó loại oan chính ca cộng một cột
    điểm, nên hợp đồng đổi cùng `_neo_manh_roi_rac`."""
    trich = "Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập\nTinh thần trách nhiệm, thái độ đối với công việc"
    llm = _LLM(_ra(quan_sat=[_qs("các tiêu chí", trich)]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [5]


# ────────────────────────────────────────────── dãy đơn vị liền kề ngoài bảng


def test_hai_doan_ke_nhau_neo_ve_doan_dau_du_dai():
    dv = [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Hà Nội, ngày ..... tháng .... năm 20..."),
        DonViVanBan(chi_so=1, trang=1, offset_dau=40, noi_dung="Giảng viên hướng dẫn"),
        DonViVanBan(chi_so=2, trang=1, offset_dau=60, noi_dung="(Ký, ghi rõ họ tên)"),
        DonViVanBan(chi_so=3, trang=1, offset_dau=80, noi_dung="Sinh viên thực tập"),
        DonViVanBan(chi_so=4, trang=1, offset_dau=100, noi_dung="(Ký, ghi rõ họ tên)"),
    ]
    tl = [{"id": A_ID, "ten_tep": "kh.docx", "don_vi": dv}]
    llm = _LLM(_ra(quan_sat=[_qs("GVHD ký", "Giảng viên hướng dẫn\n(Ký, ghi rõ họ tên)"),
                             _qs("SV ký", "Sinh viên thực tập\n(Ký, ghi rõ họ tên)")]))
    ra = h.hieu_tai_lieu(ST, tl, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [1, 3]


def test_day_khop_hai_cho_bi_loai():
    dv = [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Điều 1. Phạm vi áp dụng của quy chế"),
        DonViVanBan(chi_so=1, trang=1, offset_dau=40, noi_dung="(Ký, ghi rõ họ tên)"),
        DonViVanBan(chi_so=2, trang=1, offset_dau=60, noi_dung="Điều 1. Phạm vi áp dụng của quy chế"),
        DonViVanBan(chi_so=3, trang=1, offset_dau=100, noi_dung="(Ký, ghi rõ họ tên)"),
    ]
    tl = [{"id": A_ID, "ten_tep": "x.docx", "don_vi": dv}]
    llm = _LLM(_ra(quan_sat=[_qs("x", "Điều 1. Phạm vi áp dụng của quy chế\n(Ký, ghi rõ họ tên)")]))
    ra = h.hieu_tai_lieu(ST, tl, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []


def test_ca_bang_chep_nguyen_theo_thu_tu_neo_ve_o_dau_du_dai():
    trich = "TT\nTiêu chí đánh giá\nĐiểm tối đa\n1\nÝ thức chấp hành nội quy, kỷ luật tại đơn vị thực tập\n2,0"
    llm = _LLM(_ra(quan_sat=[_qs("bảng", trich)]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [2]


# ─────────────────────────────────────────────── ô ngắn: duy nhất, không dài
# `QUOTE_TOI_THIEU` (12 ký tự) là quy tắc của TRÍCH DẪN ĐIỀU LUẬT, nơi một đoạn
# ngắn nằm lọt trong hàng nghìn điều. Một ô bảng thì khác: nó là cả một đơn vị,
# và phép đo đúng cho nó là DUY NHẤT chứ không phải dài. Đo trên tệp mẫu
# 2026-09-16: mọi trường điểm bị loại vì ô chỉ chứa "2,0".


def test_o_ngan_KHOP_TRON_mot_don_vi_duy_nhat_thi_neo_duoc():
    llm = _LLM(_ra(quan_sat=[_qs("tổng 10 điểm", "10")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [11]


def test_o_ngan_KHOP_NHIEU_don_vi_bi_loai():
    """"2,0" có ở hai ô — không định danh được vị trí nào."""
    llm = _LLM(_ra(quan_sat=[_qs("điểm tối đa", "2,0")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []
    assert ra["traces"]["hieu_tai_lieu_bo_trich_qua_ngan"] == 1


def test_manh_ngan_KHONG_khop_tron_van_bi_loai():
    """"Ý thức" là một phần của ô, không phải cả ô: quá ngắn để định danh."""
    llm = _LLM(_ra(quan_sat=[_qs("x", "Ý thức")]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []


# ──────────────────────────────────── trích nhiều mảnh KHÔNG liền kề (cột số)


def test_trich_nhieu_manh_roi_rac_neo_khi_TUNG_manh_deu_neo_duoc():
    """Cộng một cột điểm: mô hình chép các ô bỏ qua cột số thứ tự, nên chúng
    không liền kề. Mỗi mảnh vẫn phải tự neo được — chỉ tính liền kề mới bỏ."""
    trich = "Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập\nTinh thần trách nhiệm, thái độ đối với công việc\n10"
    llm = _LLM(_ra(quan_sat=[_qs("các tiêu chí và tổng", trich)]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert [q["neo"]["chi_so_don_vi"] for q in ra["tai_lieu_ket"]["quan_sat"]] == [5]


def test_mot_manh_khong_neo_duoc_thi_ca_trich_bi_loai():
    trich = "Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập\nCâu này không có trong tài liệu"
    llm = _LLM(_ra(quan_sat=[_qs("x", trich)]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []


def test_manh_roi_rac_mo_ho_thi_ca_trich_bi_loai():
    """Mảnh thứ hai ("2,0") có ở hai ô, và hai mảnh KHÔNG liền kề — không đường
    nào định danh được, nên cả trích bị loại chứ không neo vào ô đầu tiên."""
    trich = "Phiếu đánh giá quá trình thực tập công nghiệp\n2,0"
    llm = _LLM(_ra(quan_sat=[_qs("x", trich)]))
    ra = h.hieu_tai_lieu(ST, TL_BANG, llm, "m")
    assert ra["tai_lieu_ket"]["quan_sat"] == []


def test_khoa_chi_phi_duong_tai_lieu_nam_trong_ba_danh_sach_cong_don():
    """`traces._COST_KEYS` cộng từ một danh sách CỐ ĐỊNH — khoá vắng mặt là một
    lượt LLM vô hình với trần chi phí ngày (xem `traces.py`). `hieu_tai_lieu_*`
    và `rut_du_kien_*` từng vắng cả hai, phát hiện ở vòng sửa Phase 16."""
    from src.services.traces import _COST_KEYS, _TOKEN_IN_KEYS, _TOKEN_OUT_KEYS, _tong_hop_traces

    for node in ("hieu_tai_lieu", "rut_du_kien"):
        assert f"{node}_token_in" in _TOKEN_IN_KEYS
        assert f"{node}_token_out" in _TOKEN_OUT_KEYS
        assert f"{node}_cost_usd" in _COST_KEYS

    tong = _tong_hop_traces({
        "hieu_tai_lieu_token_in": 5, "hieu_tai_lieu_token_out": 7, "hieu_tai_lieu_cost_usd": 0.01,
        "rut_du_kien_token_in": 11, "rut_du_kien_token_out": 13, "rut_du_kien_cost_usd": 0.02,
    })
    assert (tong["token_in"], tong["token_out"]) == (16, 20)
    assert tong["cost_usd"] == pytest.approx(0.03)


# ══════════════ Phase 3 (Half A, R4) — mô hình được cho thấy bản thảo đang có


def test_khong_co_ban_thao_tong_quat_dang_mo_thi_prompt_khong_doi():
    """Không có bản thảo tổng quát nào cho hội thoại này (giá trị mặc định
    của mọi state cũ, trước Phase 3) — prompt KHÔNG có mục "Bản thảo đang
    có": hành vi của mọi lượt khác (`hoi`/`tom_tat`/`tao_van_ban` lần đầu…)
    không đổi."""
    llm = _LLM(_ra())
    h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert "# Bản thảo đang có" not in llm.prompt


def test_co_ban_thao_tong_quat_dang_mo_thi_prompt_mang_theo_van_ban():
    """R4 — hội thoại đã có một bản thảo tổng quát (`ban_thao_tong_quat_dang_mo`,
    Phase 3 Half B) thì `hieu_tai_lieu` cho mô hình thấy CHÍNH văn bản đó,
    không chỉ tài liệu nguồn — nếu không có mục này, một lượt "sửa" không có
    gì để giữ nguyên ngoài việc soạn lại từ đầu."""
    bt = {"document": "# VĂN BẢN\n\n## 1. Nội dung\n\nCâu đã soạn trước đó.\n", "audit": {}}
    llm = _LLM(_ra())
    h.hieu_tai_lieu({**ST, "ban_thao_tong_quat_dang_mo": bt}, MOT, llm, "m")
    assert "# Bản thảo đang có" in llm.prompt
    assert "Câu đã soạn trước đó." in llm.prompt


def test_ban_thao_da_sua_tay_thi_prompt_canh_bao_khong_duoc_viet_de():
    """R4's câu chữ chính xác — `sua_tay=True` (Phase 3 R2/R3, hạ `muc_kiem`)
    phải đổi LỜI CẢNH BÁO đi kèm bản thảo, không chỉ đính kèm văn bản: mô
    hình phải được nói THẲNG là phần đó do người dùng viết, không phải chính
    nó, để không tưởng nó đang sửa lại câu của chính mình."""
    bt_sua_tay = {"document": "# VĂN BẢN\n\nCâu người dùng tự viết.\n", "audit": {"sua_tay": True}}
    llm = _LLM(_ra())
    h.hieu_tai_lieu({**ST, "ban_thao_tong_quat_dang_mo": bt_sua_tay}, MOT, llm, "m")
    assert "NGƯỜI DÙNG" in llm.prompt and "sửa lại" in llm.prompt

    bt_chua_sua = {"document": "# VĂN BẢN\n\nCâu KLAW tự soạn.\n", "audit": {}}
    llm2 = _LLM(_ra())
    h.hieu_tai_lieu({**ST, "ban_thao_tong_quat_dang_mo": bt_chua_sua}, MOT, llm2, "m")
    assert "NGƯỜI DÙNG" not in llm2.prompt


def test_tran_chi_phi_dem_ca_do_dai_ban_thao_dang_co(monkeypatch):
    """Review (I2/finding 3) — `_khoi_ban_thao_dang_co` cộng CẢ bản thảo đang
    có vào CHÍNH prompt tài liệu, nhưng trần chi phí trước bản vá này chỉ đếm
    độ dài tài liệu NGUỒN — một lượt `sua_ban_thao` có thể tốn gấp đôi trần
    0,05 USD/request mà trần đó tồn tại để chặn. Test này khoá đúng THAM SỐ
    (số ký tự) truyền vào `kiem_tran_chi_phi_tai_lieu`, không chỉ hành vi khi
    vượt trần."""
    goi_voi = {}

    def gia(so_ky_tu):
        goi_voi["so_ky_tu"] = so_ky_tu

    monkeypatch.setattr(h, "kiem_tran_chi_phi_tai_lieu", gia)
    do_dai_nguon = sum(len(d.noi_dung) for d in DV_A)
    ban_thao = {"document": "x" * 500, "audit": {}}
    h.hieu_tai_lieu({**ST, "ban_thao_tong_quat_dang_mo": ban_thao}, MOT, _LLM(_ra()), "m")
    assert goi_voi["so_ky_tu"] == do_dai_nguon + 500, (
        "trần chi phí phải đếm CẢ độ dài bản thảo đang có, không chỉ tài liệu nguồn"
    )


def test_vuot_tran_voi_ban_thao_dang_co_bao_dung_thu(monkeypatch):
    """Fix round 2 (N3) — khi bản thảo đang có (I2's fix) góp phần đẩy trần
    chi phí vượt ngưỡng, thông điệp "tách nhỏ tài liệu rồi gửi lại" (`QUA_DAI`)
    không làm được gì — tài liệu không phải thứ vượt trần, và lượt sửa TIẾP
    THEO sẽ vấp lại y hệt vì bản thảo vẫn còn đó. Phải là nhánh riêng
    (`QUA_DAI_VOI_BAN_THAO`, nói người dùng tự rút ngắn bản thảo)."""

    def vuot(_):
        raise VuotTran("chi_phi", 1, 2)

    monkeypatch.setattr(h, "kiem_tran_chi_phi_tai_lieu", vuot)
    ban_thao = {"document": "x" * 500, "audit": {}}
    ra = h.hieu_tai_lieu({**ST, "ban_thao_tong_quat_dang_mo": ban_thao}, MOT, _LLM(_ra()), "m")
    tra_loi = ra["tai_lieu_ket"]["tra_loi_ngan"]
    assert "rút ngắn bản thảo" in tra_loi, "phải nói người dùng tự rút ngắn bản thảo, không phải tài liệu"
    assert tra_loi == h.QUA_DAI_VOI_BAN_THAO

    # Không có bản thảo đang có (đường cũ, trước Half B) — vẫn thông điệp cũ.
    ra2 = h.hieu_tai_lieu(ST, MOT, _LLM(_ra()), "m")
    assert ra2["tai_lieu_ket"]["tra_loi_ngan"] == h.QUA_DAI


# ───────────────────────────────────── Phase 14 — soạn tự do, không tài liệu

from src.agents.nodes.route import Intent  # noqa: E402

ST_SOAN = {"query": "soạn cho tôi đơn xin nghỉ phép ba ngày", "intent": Intent.soan_thao, "user_sub": "u"}


def _van_ban(*noi_dung: str) -> dict:
    return {"tieu_de": "ĐƠN XIN NGHỈ PHÉP",
            "muc": [{"ten": f"Mục {i}", "vung": "than", "khoi": [{"noi_dung": nd, "bang": []}]}
                    for i, nd in enumerate(noi_dung, 1)]}


def test_soan_tu_do_khong_tai_lieu_van_goi_mo_hinh_va_ra_van_ban():
    """R2: router đã nói `soan_thao`, hội thoại không có tài liệu nào — mô hình
    vẫn được gọi (một lượt, khối tài liệu rỗng có lời dặn) và trả về một văn
    bản đi tiếp sang `dung_ban_thao_tong_quat`."""
    llm = _LLM(_ra(muc_dich="tao_van_ban", van_ban=_van_ban("Kính gửi Ban Giám đốc.", "Tôi xin nghỉ phép ba ngày.")))
    ra = h.hieu_tai_lieu(ST_SOAN, [], llm, "m")
    assert llm.so_lan_goi == 1
    assert h.KHONG_TAI_LIEU in llm.prompt
    assert ra["muc_dich_tai_lieu"] == "tao_van_ban"
    assert [m["khoi"][0]["noi_dung"] for m in ra["van_ban_tong_quat"]["muc"]] == [
        "Kính gửi Ban Giám đốc.", "Tôi xin nghỉ phép ba ngày."]
    assert ra["traces"]["hieu_tai_lieu_so_don_vi_gui"] == 0
    assert ra["tai_lieu_ket"]["tai_lieu_da_dung"] == []


def test_soan_tu_do_schema_khong_ep_enum_nhan_rong():
    """`quan_sat.tai_lieu` là enum NHÃN; không tài liệu thì không có nhãn nào —
    một `enum: []` là lược đồ không hợp lệ với provider, nên bỏ hẳn enum."""
    assert "enum" not in h.schema_hieu([])["properties"]["quan_sat"]["items"]["properties"]["tai_lieu"]
    assert h.schema_hieu(["A"])["properties"]["quan_sat"]["items"]["properties"]["tai_lieu"]["enum"] == ["A"]


def test_soan_tu_do_mo_hinh_gan_nham_hoi_van_ep_ve_tao_van_ban():
    """Router (ý kiến độc lập) đã nói soạn; mô hình gán `hoi` cho một lượt không
    có tài liệu để hỏi là vô nghĩa — ép về `tao_van_ban` để lượt đi đúng nhánh
    dựng bản thảo (hoặc nói thật là chưa soạn được mục nào)."""
    ra = h.hieu_tai_lieu(ST_SOAN, [], _LLM(_ra(muc_dich="hoi")), "m")
    assert ra["muc_dich_tai_lieu"] == "tao_van_ban"


def test_soan_tu_do_co_ban_thao_dang_mo_thi_sua_ban_thao():
    st = {**ST_SOAN, "query": "viết lại trang trọng hơn",
          "ban_thao_tong_quat_dang_mo": {"document": "# ĐƠN\n\nTôi xin nghỉ.", "audit": {}}}
    llm = _LLM(_ra(muc_dich="sua_ban_thao", van_ban=_van_ban("Tôi trân trọng xin nghỉ.")))
    ra = h.hieu_tai_lieu(st, [], llm, "m")
    assert ra["muc_dich_tai_lieu"] == "sua_ban_thao"
    assert "# Bản thảo đang có" in llm.prompt
    # Mô hình gán `hoi` khi đang có bản thảo → ép về `sua_ban_thao`, không phải
    # `tao_van_ban` (không mở một bản thảo thứ hai cho một lượt xin sửa).
    ra2 = h.hieu_tai_lieu(st, [], _LLM(_ra(muc_dich="hoi")), "m")
    assert ra2["muc_dich_tai_lieu"] == "sua_ban_thao"


def test_soan_tu_do_van_qua_luoi_lam_sach_khong_mang_so_dieu_hay_so_bia():
    """R4: bản thảo chat KHÔNG mang một số Điều nào tới người đọc. Hai đường
    của lưới có sẵn (`lam_sach_van_ban`, không đổi): số Điều CÓ trong lời
    người hỏi thì mục dẫn nó bị BỎ (`_vuong_luoi_chan`); số Điều/con số KHÔNG
    có trong nguồn thì bị thay `[…]` — một chỗ trống, không phải một trích dẫn
    bịa. Con số có trong lời họ ("3 ngày") thì giữ."""
    st = {**ST_SOAN, "query": "soạn đơn xin nghỉ phép 3 ngày theo Điều 115"}
    llm = _LLM(_ra(muc_dich="tao_van_ban", van_ban=_van_ban(
        "Căn cứ Điều 115 Bộ luật Lao động, tôi xin nghỉ.",
        "Theo Điều 113, tôi xin nghỉ 3 ngày, lương 15.000.000 đồng.")))
    ra = h.hieu_tai_lieu(st, [], llm, "m")
    muc = ra["van_ban_tong_quat"]["muc"]
    assert len(muc) == 1 and ra["traces"]["dung_ban_thao_so_muc_bo"] == 1
    assert muc[0]["khoi"][0]["noi_dung"] == f"Theo Điều {h.CHO_TRONG}, tôi xin nghỉ 3 ngày, lương {h.CHO_TRONG} đồng."
    assert not h.re.search(r"[Đđ]iều\s*\d", muc[0]["khoi"][0]["noi_dung"])


def test_co_tai_lieu_ma_router_noi_soan_thi_nhan_hoi_van_bi_ep_ve_tao_van_ban():
    """Ngõ cụt đo được: hội thoại SỞ HỮU một tài liệu ("dựa vào hợp đồng này
    soạn giúp tôi đơn xin nghỉ việc"). Bản trước gác phép sửa nhãn trên
    `soan_tu_do` (= KHÔNG tài liệu), nên nhãn `hoi` của mô hình đứng nguyên,
    `_re_sau_hieu_tai_lieu` rẽ `assemble`, và `_ban_thao_tong_quat` trả về
    "Lượt này tôi chưa soạn được mục nào." — đúng ngõ cụt R1 đã gỡ. Gác nay là
    ý kiến của router, nên có tài liệu hay không đều sửa như nhau."""
    st = {**ST_SOAN, "query": "dựa vào hợp đồng này soạn giúp tôi đơn xin nghỉ việc"}
    llm = _LLM(_ra(muc_dich="hoi", van_ban=_van_ban("Kính gửi Ban Giám đốc.", "Tôi xin nghỉ việc.")))
    ra = h.hieu_tai_lieu(st, MOT, llm, "m")
    assert ra["muc_dich_tai_lieu"] == "tao_van_ban"
    assert [m["khoi"][0]["noi_dung"] for m in ra["van_ban_tong_quat"]["muc"]] == [
        "Kính gửi Ban Giám đốc.", "Tôi xin nghỉ việc."]
    assert ra["traces"]["hieu_tai_lieu_so_don_vi_gui"] > 0, "tài liệu vẫn được gửi làm nguồn soạn"


def test_co_tai_lieu_ma_router_noi_soan_thi_doi_chieu_luat_KHONG_di_duong_phap_ly():
    """Ca thứ hai, tệ hơn: mô hình gán `doi_chieu_luat` cho một lượt router đã
    gọi là soạn thảo. `assemble` rẽ theo `intent` (`intent == "soan_thao"`) nên
    một câu trả lời pháp lý của lượt này KHÔNG bao giờ được dựng — để nó chạy
    hết rewrite → retrieve → expand → generate → hai tầng kiểm là trả tiền năm
    lượt gọi cho một kết quả bị vứt. Quyết định: sửa nhãn về soạn và KHÔNG vào
    đường pháp lý; không trích dẫn đã kiểm nào bị bỏ, vì không cái nào được
    dựng."""
    from src.agents.graph_tra_cuu import _re_sau_hieu_tai_lieu

    llm = _LLM(_ra(muc_dich="doi_chieu_luat", van_ban=_van_ban("Tôi xin nghỉ việc.")))
    ra = h.hieu_tai_lieu(ST_SOAN, MOT, llm, "m")
    assert ra["muc_dich_tai_lieu"] == "tao_van_ban"
    assert ra["tai_lieu_neo"] == [], "không điều khoản nào đẩy sang đường pháp lý"
    assert _re_sau_hieu_tai_lieu(ra) == "dung_ban_thao_tong_quat"


def test_co_tai_lieu_ma_router_KHONG_noi_soan_thi_nhan_cua_mo_hinh_giu_nguyen():
    """Nửa kia của gác: router mới là ý kiến độc lập. `Intent.tai_lieu` ("đây
    là đơn gì") không được biến một lượt hỏi thành một lượt ghi đè bản thảo —
    chính sự cố `_muc_dich_soan_da_xac_nhan` đã dựng lưới cho."""
    from src.agents.graph_tra_cuu import _re_sau_hieu_tai_lieu

    st = {**ST_SOAN, "intent": Intent.tai_lieu, "query": "đây là đơn gì"}
    ra = h.hieu_tai_lieu(st, MOT, _LLM(_ra(muc_dich="hoi")), "m")
    assert ra["muc_dich_tai_lieu"] == "hoi"
    assert _re_sau_hieu_tai_lieu(ra) == "assemble"


def test_khong_tai_lieu_va_khong_phai_soan_thao_thi_van_khong_goi_mo_hinh():
    """Nhánh cũ giữ nguyên: không tài liệu và router KHÔNG nói soạn thảo thì
    không gọi mô hình với một prompt rỗng."""
    for intent in (None, Intent.tai_lieu, Intent.tra_cuu):
        llm = _LLM(_ra())
        ra = h.hieu_tai_lieu({**ST, "intent": intent}, [], llm, "m")
        assert llm.so_lan_goi == 0 and ra["muc_dich_tai_lieu"] is None


def test_soan_tu_do_loi_ha_tang_noi_chua_soan_duoc_khong_phai_chua_doc_duoc():
    ra = h.hieu_tai_lieu(ST_SOAN, [], _LLM(_ra(), no=True), "m")
    assert ra["muc_dich_tai_lieu"] is None
    assert ra["ban_thao_tong_quat_loi"] == h.CHUA_SOAN_DUOC
    assert "tài liệu" not in h.CHUA_SOAN_DUOC
