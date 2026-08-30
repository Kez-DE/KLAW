import json

from src.agents.nodes.generate_claims import CLAIMS_SCHEMA, build_context, generate_claims


class FakeLlm:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.last: dict | None = None

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage

        self.last = {"model": model, "messages": messages, "schema": json_schema}
        return json.dumps(self.payload), Usage(10, 5, 0.0001)


PROVS = [
    {
        "id": 11,
        "duong_dan": "45/2019/QH14 > Điều 26",
        "tieu_de": "Điều 26. Tiền lương thử việc",
        "noi_dung": "Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận "
        "nhưng ít nhất phải bằng 85% mức lương của công việc đó.",
        "so_ky_hieu": "45/2019/QH14",
    },
]


def test_context_co_provision_id_va_duong_dan_khong_co_title():
    ctx = build_context(PROVS)
    assert "[provision_id=11]" in ctx
    assert "45/2019/QH14 > Điều 26" in ctx


def test_context_co_so_ky_hieu_rieng_biet_dung_lam_dinh_danh():
    """Global Constraint: không định danh văn bản bằng ten/title — dùng so_ky_hieu.
    Context phải đưa so_ky_hieu tường minh cho model, không chỉ ẩn trong duong_dan."""
    ctx = build_context(PROVS)
    assert "so_ky_hieu=45/2019/QH14" in ctx


def test_claims_duoc_parse_thanh_object():
    llm = FakeLlm(
        {
            "insufficient_evidence": False,
            "claims": [{"text": "Lương thử việc ít nhất 85%.", "provision_id": 11, "quote": "ít nhất phải bằng 85%"}],
        }
    )
    st = generate_claims({"query": "thử việc lương bao nhiêu", "expanded": PROVS}, llm, "m")
    assert len(st["draft_claims"]) == 1
    assert st["draft_claims"][0].provision_id == 11


def test_insufficient_evidence_duoc_ton_trong():
    llm = FakeLlm({"insufficient_evidence": True, "claims": []})
    st = generate_claims({"query": "thuế TNCN", "expanded": PROVS}, llm, "m")
    assert st["insufficient_evidence"] is True and st["draft_claims"] == []


def test_json_schema_duoc_truyen_va_bat_buoc_ba_field():
    llm = FakeLlm({"insufficient_evidence": True, "claims": []})
    generate_claims({"query": "x", "expanded": PROVS}, llm, "m")
    assert llm.last["schema"] == CLAIMS_SCHEMA
    props = llm.last["schema"]["properties"]["claims"]["items"]
    assert set(props["required"]) == {"text", "provision_id", "quote"}


def test_json_hong_khong_lam_sap_ma_thanh_insufficient():
    class Bad(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            from src.services.llm import Usage

            return "không phải json", Usage(1, 1, 0.0)

    st = generate_claims({"query": "x", "expanded": PROVS}, Bad({}), "m")
    assert st["insufficient_evidence"] is True
    assert st["schema_error"] is True, "phải ghi nhận lỗi schema để đo tỉ lệ, không im lặng"


def test_expanded_rong_thi_khong_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không được gọi LLM khi không có điều luật nào")

    st = generate_claims({"query": "x", "expanded": []}, Never({}), "m")
    assert st["insufficient_evidence"] is True


def test_traces_dung_usage_that_khi_thanh_cong():
    """Global Constraint: mọi node ghi vào traces, dùng Usage thật (Task 3), không ước lượng."""
    llm = FakeLlm(
        {
            "insufficient_evidence": False,
            "claims": [{"text": "Lương thử việc ít nhất 85%.", "provision_id": 11, "quote": "ít nhất phải bằng 85%"}],
        }
    )
    st = generate_claims({"query": "thử việc lương bao nhiêu", "expanded": PROVS}, llm, "m")
    assert st["traces"] == {"claims_raw": 1, "token_in": 10, "token_out": 5, "cost_usd": 0.0001}


def test_traces_khong_goi_llm_thi_khong_co_cost():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không được gọi LLM khi không có điều luật nào")

    st = generate_claims({"query": "x", "expanded": []}, Never({}), "m")
    assert st["traces"] == {"claims_raw": 0, "token_in": 0, "token_out": 0, "cost_usd": 0.0}


def test_traces_van_ghi_usage_that_khi_json_hong():
    """Usage thật (token/cost bị tính phí) không được biến mất chỉ vì parse JSON thất bại."""

    class Bad(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            from src.services.llm import Usage

            return "không phải json", Usage(7, 3, 0.00005)

    st = generate_claims({"query": "x", "expanded": PROVS}, Bad({}), "m")
    assert st["traces"] == {"claims_raw": 0, "token_in": 7, "token_out": 3, "cost_usd": 0.00005}


def test_traces_gop_voi_traces_co_san_tu_node_truoc_khong_ghi_de():
    """Nhiều node cùng ghi vào traces (Global Constraint) — node này không được xoá
    mất đóng góp của node trước, chỉ cập nhật phần của chính mình."""
    llm = FakeLlm({"insufficient_evidence": True, "claims": []})
    st = generate_claims(
        {"query": "x", "expanded": PROVS, "traces": {"retrieved_ids": [11], "claims_raw": 999}}, llm, "m"
    )
    assert st["traces"]["retrieved_ids"] == [11]
    assert st["traces"]["claims_raw"] == 0
