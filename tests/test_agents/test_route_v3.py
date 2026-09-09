import json
from pathlib import Path

from src.agents.nodes import route as r
from src.services.llm import Usage


class LlmGia:
    def __init__(self, tra):
        self.tra, self.da_goi = tra, []

    def chat(self, model, messages, json_schema=None):
        self.da_goi.append((messages, json_schema))
        return json.dumps(self.tra, ensure_ascii=False), Usage(1, 1, 0.0)


V3 = Path("prompts/route.v3.md")


def test_schema_v3_them_hai_khoa():
    s = r.schema_v3()
    assert {"dang_tra_loi", "y_dinh_phu"} <= set(s["required"])
    assert s["properties"]["dang_tra_loi"]["enum"] == ["van_xuoi", "bang"]
    assert s["properties"]["y_dinh_phu"]["enum"] == ["soan_thao", "khong"]


def test_route_v3_doc_du_truong_va_goi_y_soan_thao_khi_y_dinh_phu():
    llm = LlmGia(
        {
            "intent": "tra_cuu",
            "loai_van_ban": "don_xin_nghi_viec",
            "thay_the": [],
            "ly_do": "bạn sắp nghỉ",
            "dang_tra_loi": "van_xuoi",
            "y_dinh_phu": "soan_thao",
        }
    )
    st = r.route({"query": "tôi sắp nghỉ việc, cho tôi luật và văn bản nghỉ việc"}, llm, "m", prompt_path=V3)
    assert st["intent"] == r.Intent.tra_cuu and st["y_dinh_phu"] == "soan_thao" and st["dang_tra_loi"] == "van_xuoi"
    assert st["soan_thao_goi_y"]["loai"] == "don_xin_nghi_viec"
    assert llm.da_goi[0][1] == r.schema_v3()


def test_route_v3_xin_bang_theo_quy_tac_0_token_du_model_noi_van_xuoi():
    llm = LlmGia(
        {
            "intent": "tra_cuu",
            "loai_van_ban": "khong_ro",
            "thay_the": [],
            "ly_do": "",
            "dang_tra_loi": "van_xuoi",
            "y_dinh_phu": "khong",
        }
    )
    st = r.route({"query": "so sánh trợ cấp thôi việc và trợ cấp mất việc dạng bảng"}, llm, "m", prompt_path=V3)
    assert st["dang_tra_loi"] == "bang" and st["y_dinh_phu"] is None


def test_route_v2_van_chay_khong_co_hai_khoa_moi():
    llm = LlmGia({"intent": "tra_cuu", "loai_van_ban": "khong_ro", "thay_the": [], "ly_do": ""})
    st = r.route({"query": "x"}, llm, "m", prompt_path=Path("prompts/route.v2.md"))
    assert st.get("dang_tra_loi", "van_xuoi") == "van_xuoi" and st.get("y_dinh_phu") is None
