"""Test cho phần logic thuần của src/services/traces.py (tách từ routes.py,
task-1 klaw-04-drafting-fe-deploy).

Chỉ `_tong_hop_traces` ở đây — hàm thuần, không đụng DB. `_ghi_traces` (nửa
ghi DB thật) tiếp tục được phủ bởi tests/test_api/test_tra_cuu.py qua
monkeypatch (`test_ghi_traces_khong_chan_event_loop`,
`test_loi_ghi_traces_KHONG_lam_hong_response_da_tinh_dung`) vì nó cần state
`st` đầy đủ của graph, không phải logic thuần.
"""

from src.services.traces import _tong_hop_traces


def test_tong_hop_traces_cong_dung_5_diem_goi_LLM():
    traces = {
        "route_token_in": 10, "route_token_out": 1, "route_cost_usd": 0.001,
        "rewrite_query_token_in": 20, "rewrite_query_token_out": 2, "rewrite_query_cost_usd": 0.002,
        "token_in": 30, "token_out": 3, "cost_usd": 0.003,  # generate_claims — khoá TRẦN
        "tier2_token_in": 40, "tier2_token_out": 4, "tier2_cost_usd": 0.004,
        "assemble_token_in": 50, "assemble_token_out": 5, "assemble_cost_usd": 0.005,
    }
    tong = _tong_hop_traces(traces)
    assert tong["token_in"] == 10 + 20 + 30 + 40 + 50
    assert tong["token_out"] == 1 + 2 + 3 + 4 + 5
    assert abs(tong["cost_usd"] - (0.001 + 0.002 + 0.003 + 0.004 + 0.005)) < 1e-9


def test_tong_hop_traces_khoa_thieu_tinh_la_0_khong_sap():
    assert _tong_hop_traces({}) == {
        "token_in": 0, "token_out": 0, "cost_usd": 0.0,
        "generate_model": None, "judge_model": None,
        "expand_before": None, "expand_after": None,
    }


def test_tong_hop_traces_model_va_expand_lay_dung_khoa():
    traces = {
        "tier2_generate_model": "google/gemini-2.5-flash-lite",
        "tier2_judge_model": "mistralai/mistral-small-3.2-24b-instruct",
        "expand_before": 10, "expand_after": 101,
    }
    tong = _tong_hop_traces(traces)
    assert tong["generate_model"] == "google/gemini-2.5-flash-lite"
    assert tong["judge_model"] == "mistralai/mistral-small-3.2-24b-instruct"
    assert tong["expand_before"] == 10
    assert tong["expand_after"] == 101


def test_tong_hop_traces_tier2_khong_chay_thi_model_la_None():
    """tier2 tắt hoặc không có claim nào qua tầng 1 → không có khoá tier2_* →
    cột DB phải là NULL, không phải tên model 'lẽ ra' dùng."""
    traces = {"route_token_in": 5}
    tong = _tong_hop_traces(traces)
    assert tong["generate_model"] is None
    assert tong["judge_model"] is None
