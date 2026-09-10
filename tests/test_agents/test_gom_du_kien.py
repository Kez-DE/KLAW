import json

from src.agents.graph_soan_thao import cac_loai
from src.agents.nodes import gom_du_kien as g
from src.services.llm import Usage


class LlmGia:
    def __init__(self, tra):
        self.tra, self.da_goi = tra, []

    def chat(self, model, messages, json_schema=None):
        self.da_goi.append((messages, json_schema))
        return json.dumps(self.tra, ensure_ascii=False), Usage(1, 1, 0.0)


def test_schema_dung_cho_moi_loai():
    for loai in sorted(cac_loai()):
        s = g.schema_du_kien(loai)
        assert s["additionalProperties"] is False and "du" in s["required"] and "ghi_chu" in s["required"]
        for t in g.truong_cua(loai):
            assert t["key"] in s["properties"]
            if t.get("lua_chon"):
                assert set(s["properties"][t["key"]]["enum"]) >= set(t["lua_chon"]) | {""}


def test_gom_lan_dau_thieu_thi_hoi_va_du_bi_python_phu_quyet():
    loai = "hdld"
    truong = g.truong_cua(loai)
    bat_buoc = [t["key"] for t in truong if t["bat_buoc"]]
    assert bat_buoc, "hdld phải có trường bắt buộc để test có ý nghĩa"
    tra = {t["key"]: "" for t in truong} | {
        bat_buoc[0]: (truong[0].get("lua_chon") or ["x"])[0],
        "du": True,
        "ghi_chu": "",
    }
    llm = LlmGia(tra)
    st = g.gom_du_kien(
        {
            "query": "soạn hợp đồng lao động",
            "ho_so": {},
            "user_sub": "u",
            "soan_thao_goi_y": {"loai": loai, "ten": "hợp đồng lao động"},
            "traces": {},
        },
        llm,
        "m",
    )
    sd = st["soan_thao_dang_mo"]
    assert sd["loai"] == loai and sd["du"] is False  # model nói đủ nhưng còn trường bắt buộc trống
    assert [t["key"] for t in sd["con_thieu"]] == bat_buoc[1:][: g.TOI_DA_HOI] or len(sd["con_thieu"]) <= g.TOI_DA_HOI
    assert llm.da_goi[0][1] == g.schema_du_kien(loai)


def test_cu_soan_thi_du_du_thieu():
    loai = "hdld"
    truong = g.truong_cua(loai)
    llm = LlmGia({t["key"]: "" for t in truong} | {"du": False, "ghi_chu": ""})
    st = g.gom_du_kien(
        {
            "query": "thiếu thì cứ soạn đi",
            "ho_so": {},
            "user_sub": "u",
            "soan_thao_dang_mo": {"loai": loai, "facts": {}, "ban_thao_id": None, "so_lan_sua": 0},
            "traces": {},
        },
        llm,
        "m",
    )
    assert st["soan_thao_dang_mo"]["du"] is True and st["soan_thao_dang_mo"]["cu_soan"] is True


def test_gom_giu_facts_cu_va_de_bang_gia_tri_moi():
    loai = "hdld"
    truong = g.truong_cua(loai)
    k0 = truong[0]["key"]
    gia_tri_moi = (truong[0].get("lua_chon") or ["moi"])[0]
    llm = LlmGia({t["key"]: "" for t in truong} | {k0: gia_tri_moi, "du": False, "ghi_chu": ""})
    st = g.gom_du_kien(
        {
            "query": "đổi lại",
            "ho_so": {},
            "user_sub": "u",
            "soan_thao_dang_mo": {
                "loai": loai,
                "facts": {k0: "cu", "khac": "giu"},
                "ban_thao_id": None,
                "so_lan_sua": 0,
            },
            "traces": {},
        },
        llm,
        "m",
    )
    assert st["soan_thao_dang_mo"]["facts"][k0] == gia_tri_moi and st["soan_thao_dang_mo"]["facts"]["khac"] == "giu"


def test_phan_hoi_khong_phai_object_thi_giu_facts_cu_khong_raise():
    """JSON hợp lệ (`json.loads` không nổi) nhưng SAI HÌNH DẠNG — mảng, chuỗi, số,
    null đều là JSON hợp lệ và đều vi phạm schema object đã xin — phải rơi vào
    CÙNG đường suy biến với lỗi hạ tầng (giữ facts cũ, hỏi lại phần thiếu), không
    được để `.get()` trên một non-dict làm lượt này crash."""
    loai = "hdld"
    truong = g.truong_cua(loai)
    k0 = truong[0]["key"]
    llm = LlmGia(["không phải object"])  # JSON hợp lệ, không phải dict
    st = g.gom_du_kien(
        {
            "query": "tiếp tục",
            "ho_so": {},
            "user_sub": "u",
            "soan_thao_dang_mo": {"loai": loai, "facts": {k0: "cu"}, "ban_thao_id": None, "so_lan_sua": 0},
            "traces": {},
        },
        llm,
        "m",
    )
    sd = st["soan_thao_dang_mo"]
    assert sd["facts"][k0] == "cu"  # dữ kiện đã gom trước đó không mất
    assert st["traces"]["gom_du_kien_nguon"] == "loi"


# ── Phần thuần (không model, không DB): field lookup, schema builder, missing-field
# calculation — bổ sung ngoài 4 test brief để phủ trực tiếp hai ca controller yêu cầu:
# "mọi trường đã có giá trị" và "loại không có rule-derived field nào".


def test_con_thieu_rong_khi_moi_truong_da_co_gia_tri():
    loai = "hdld"
    truong = g.truong_cua(loai)
    facts_du = {t["key"]: (t.get("lua_chon") or ["x"])[0] for t in truong}
    assert g.con_thieu(loai, facts_du) == []


def test_con_thieu_day_du_khi_facts_rong():
    loai = "hdld"
    truong = g.truong_cua(loai)
    assert [t["key"] for t in g.con_thieu(loai, {})] == [t["key"] for t in truong]


def test_loai_khong_rule_thi_truong_rong_va_khong_bao_gio_thieu():
    loai = next(loai_ for loai_ in sorted(cac_loai()) if not g.truong_cua(loai_))
    assert g.truong_cua(loai) == []
    assert g.con_thieu(loai, {}) == []
    s = g.schema_du_kien(loai)
    assert set(s["properties"]) == {"du", "ghi_chu"} and s["required"] == ["du", "ghi_chu"]


def test_gom_du_kien_voi_loai_khong_rule_thi_du_ngay_khong_hoi_gi():
    loai = next(loai_ for loai_ in sorted(cac_loai()) if not g.truong_cua(loai_))
    llm = LlmGia({"du": True, "ghi_chu": ""})
    st = g.gom_du_kien(
        {
            "query": "soạn giúp tôi",
            "ho_so": {},
            "user_sub": "u",
            "soan_thao_goi_y": {"loai": loai, "ten": loai},
            "traces": {},
        },
        llm,
        "m",
    )
    sd = st["soan_thao_dang_mo"]
    assert sd["du"] is True and sd["con_thieu"] == []
