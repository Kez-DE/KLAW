"""`rewrite_query` v1/v2 (spec 2026-09-06 §5.5). Test thuần: FakeLlm, template tmp."""

import json

from src.agents.nodes.rewrite_query import QUERIES_SCHEMA, QUERIES_V2_SCHEMA, rewrite_query
from src.services.llm import Usage

GOC = "sếp em đuổi em không báo trước"


class Llm:
    def __init__(self, tra_ve: dict | Exception):
        self.tra_ve, self.schema_da_goi = tra_ve, []

    def chat(self, model, messages, json_schema=None):
        self.schema_da_goi.append(json_schema)
        if isinstance(self.tra_ve, Exception):
            raise self.tra_ve
        return json.dumps(self.tra_ve, ensure_ascii=False), Usage(1, 1, 0.0)


V2 = {
    "quan_he": "chấm dứt hợp đồng lao động đơn phương",
    "vai": "người lao động",
    "linh_vuc": "lao_dong",
    "ba_lop": ["nguyen_tac", "che_tai"],
    "du_kien_van_ban": ["Bộ luật Lao động"],
    "queries": ["người sử dụng lao động đơn phương chấm dứt hợp đồng", "thời hạn báo trước"],
}


def test_v2_dung_schema_v2_va_ghi_linh_vuc(tmp_path):
    mau = tmp_path / "v2.md"
    mau.write_text("quan_he vai linh_vuc {cau_hoi}", encoding="utf-8")
    llm = Llm(V2)
    st = rewrite_query({"query": GOC}, llm, "m", prompt_path=mau)
    assert llm.schema_da_goi == [QUERIES_V2_SCHEMA]
    assert st["queries"][0] == GOC and len(st["queries"]) == 3
    assert st["linh_vuc_du_doan"] == "lao_dong"
    assert st["traces"]["rewrite_query_nhan_dien"] == {
        "quan_he": V2["quan_he"],
        "vai": V2["vai"],
        "ba_lop": V2["ba_lop"],
        "du_kien_van_ban": V2["du_kien_van_ban"],
    }
    assert st["traces"]["rewrite_query_degraded"] is False


def test_v1_giu_schema_cu_va_linh_vuc_None(tmp_path):
    mau = tmp_path / "v1.md"
    mau.write_text("chỉ có {cau_hoi}", encoding="utf-8")
    llm = Llm({"queries": ["a", "b"]})
    st = rewrite_query({"query": GOC}, llm, "m", prompt_path=mau)
    assert llm.schema_da_goi == [QUERIES_SCHEMA]
    assert st["queries"] == [GOC, "a", "b"]
    assert st["linh_vuc_du_doan"] is None
    assert "rewrite_query_nhan_dien" not in st["traces"]


def test_loi_llm_fallback_query_goc_va_dem_degraded(tmp_path):
    mau = tmp_path / "v2.md"
    mau.write_text("quan_he {cau_hoi}", encoding="utf-8")
    st = rewrite_query({"query": GOC}, Llm(RuntimeError("429")), "m", prompt_path=mau)
    assert st["queries"] == [GOC]
    assert st["linh_vuc_du_doan"] is None
    assert st["traces"]["rewrite_query_degraded"] is True


def test_linh_vuc_rong_hoac_khac_chuoi_thanh_None(tmp_path):
    mau = tmp_path / "v2.md"
    mau.write_text("quan_he {cau_hoi}", encoding="utf-8")
    st = rewrite_query({"query": GOC}, Llm({**V2, "linh_vuc": "  "}), "m", prompt_path=mau)
    assert st["linh_vuc_du_doan"] is None


# ══ v3 — khung yêu cầu (cai_thien GĐ2) ═══════════════════════════════════════

from src.agents.nodes.rewrite_query import QUERIES_V3_SCHEMA, khung_yeu_cau_tu  # noqa: E402

V3 = {
    **V2,
    "muc_tieu": "biết công ty có được cho nghỉ không báo trước không",
    "cau_hoi_phap_ly": "người sử dụng lao động đơn phương chấm dứt hợp đồng cần báo trước bao lâu",
    "du_kien_quyet_dinh_con_thieu": [
        {"ma": "ly_do_cham_dut", "cau": "Công ty nêu lý do gì khi cho bạn nghỉ", "lam_doi_ket_luan": True},
        {"ma": "loai_hop_dong", "cau": "Hợp đồng của bạn ghi thời hạn thế nào?", "lam_doi_ket_luan": True},
        {"ma": "tham_nien", "cau": "Bạn làm ở đó được bao lâu?", "lam_doi_ket_luan": False},
    ],
}


def _mau_v3(tmp_path):
    mau = tmp_path / "v3.md"
    mau.write_text("quan_he vai linh_vuc muc_tieu {cau_hoi} {tinh_huong}", encoding="utf-8")
    return mau


def test_v3_dung_schema_v3_va_ghi_khung_yeu_cau(tmp_path):
    llm = Llm(V3)
    st = rewrite_query({"query": GOC}, llm, "m", prompt_path=_mau_v3(tmp_path))
    assert llm.schema_da_goi == [QUERIES_V3_SCHEMA]
    assert st["queries"][0] == GOC and st["linh_vuc_du_doan"] == "lao_dong"
    k = st["khung_yeu_cau"]
    assert k["muc_tieu"] == V3["muc_tieu"]
    assert k["cau_hoi_phap_ly"] == V3["cau_hoi_phap_ly"]
    assert [m["ma"] for m in k["du_kien_quyet_dinh_con_thieu"]] == ["ly_do_cham_dut", "loai_hop_dong", "tham_nien"]
    # Thiếu dấu hỏi thì thêm; câu đã có thì giữ nguyên.
    assert k["du_kien_quyet_dinh_con_thieu"][0]["cau"].endswith("?")
    assert k["du_kien_quyet_dinh_con_thieu"][1]["cau"] == "Hợp đồng của bạn ghi thời hạn thế nào?"
    assert k["du_kien_quyet_dinh_con_thieu"][2]["lam_doi_ket_luan"] is False


def test_v3_khong_hoi_lai_khoa_ho_so_da_co():
    """Dữ kiện người nói thắng: khoá đã có giá trị trong hồ sơ bị bỏ khỏi danh sách hỏi."""
    ho_so = {"loai_hop_dong": {"gia_tri": "không xác định thời hạn", "nguon": "nguoi_noi"}}
    k = khung_yeu_cau_tu(V3, ho_so)
    assert [m["ma"] for m in k["du_kien_quyet_dinh_con_thieu"]] == ["ly_do_cham_dut", "tham_nien"]


def test_v3_cau_hoi_phat_bieu_moc_phap_ly_bi_loai():
    """`hoi_lai.bi_loai`: "dưới 12 tháng" đã phát biểu thay luật — câu đó không được tới người hỏi."""
    d = {**V3, "du_kien_quyet_dinh_con_thieu": [
        {"ma": "loai_hop_dong", "cau": "Hợp đồng của bạn dưới 12 tháng không?", "lam_doi_ket_luan": True},
        {"ma": "thoi_diem", "cau": "Chuyện này xảy ra khi nào?", "lam_doi_ket_luan": True},
    ]}
    k = khung_yeu_cau_tu(d, {})
    assert [m["ma"] for m in k["du_kien_quyet_dinh_con_thieu"]] == ["thoi_diem"]


def test_v3_muc_tieu_mang_so_dieu_hoac_dinh_danh_bi_bo():
    d = {**V3, "muc_tieu": "biết quyền theo Điều 35 Bộ luật Lao động", "cau_hoi_phap_ly": "liên hệ a@b.vn"}
    k = khung_yeu_cau_tu(d, {})
    assert k["muc_tieu"] == "" and k["cau_hoi_phap_ly"] == ""
    assert k["du_kien_quyet_dinh_con_thieu"]  # phần còn dùng được vẫn giữ


def test_v3_ma_la_hoac_toi_da_ba():
    d = {**V3, "du_kien_quyet_dinh_con_thieu": [
        {"ma": "Điều 35", "cau": "Bạn có hợp đồng không?", "lam_doi_ket_luan": True},
        {"ma": "a", "cau": "Bạn có hợp đồng không?", "lam_doi_ket_luan": True},
        {"ma": "x1", "cau": "Câu một?", "lam_doi_ket_luan": True},
        {"ma": "x2", "cau": "Câu hai?", "lam_doi_ket_luan": True},
        {"ma": "x3", "cau": "Câu ba?", "lam_doi_ket_luan": True},
        {"ma": "x4", "cau": "Câu bốn?", "lam_doi_ket_luan": True},
    ]}
    k = khung_yeu_cau_tu(d, {})
    assert [m["ma"] for m in k["du_kien_quyet_dinh_con_thieu"]] == ["x1", "x2", "x3"]


def test_v3_khong_con_gi_dung_duoc_thi_None():
    assert khung_yeu_cau_tu({"muc_tieu": "", "cau_hoi_phap_ly": "", "du_kien_quyet_dinh_con_thieu": []}, {}) is None
    assert khung_yeu_cau_tu({"muc_tieu": "theo Điều 35"}, {}) is None


def test_v3_json_hong_thi_fallback_khong_khung(tmp_path):
    llm = Llm(RuntimeError("429"))
    st = rewrite_query({"query": GOC}, llm, "m", prompt_path=_mau_v3(tmp_path))
    assert st["queries"] == [GOC] and st["khung_yeu_cau"] is None
    assert st["traces"]["rewrite_query_degraded"] is True


def test_v2_khong_co_khung_yeu_cau(tmp_path):
    mau = tmp_path / "v2.md"
    mau.write_text("quan_he vai linh_vuc {cau_hoi}", encoding="utf-8")
    st = rewrite_query({"query": GOC}, Llm(V2), "m", prompt_path=mau)
    assert st["khung_yeu_cau"] is None
