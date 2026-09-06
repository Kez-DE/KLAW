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
