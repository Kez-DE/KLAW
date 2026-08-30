import json
import logging

import pytest

from src.agents.nodes.rewrite_query import rewrite_query
from src.agents.nodes.route import Intent, route


class FakeLlm:
    def __init__(self, payload):
        self.payload = payload

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        return json.dumps(self.payload), Usage(1, 1, 0.0)


def test_route_tra_ve_intent_hop_le():
    st = route({"query": "thử việc bao lâu"}, FakeLlm({"intent": "tra_cuu"}), "m")
    assert st["intent"] is Intent.tra_cuu


def test_route_intent_la_khong_ro_thi_mac_dinh_tra_cuu():
    """Route sai sang ngoai_pham_vi làm hệ thống từ chối oan — mặc định an toàn
    là cứ tra cứu rồi để verifier/abstain quyết."""
    st = route({"query": "x"}, FakeLlm({"intent": "khong_biet"}), "m")
    assert st["intent"] is Intent.tra_cuu


def test_route_json_hong_thi_mac_dinh_tra_cuu():
    class Bad(FakeLlm):
        def chat(self, *a, **k):
            from src.services.llm import Usage
            return "not json", Usage(1, 1, 0.0)

    assert route({"query": "x"}, Bad({}), "m")["intent"] is Intent.tra_cuu


def test_route_loi_ha_tang_PHAI_no_ra_khong_duoc_nuot():
    """Ruling: lỗi hạ tầng (LlmClient raise vì content rỗng hoặc usage thiếu —
    xem llm.py ValueError ở _usage_from/chat) phải NỔ RA NGOÀI route, khác
    'model trả intent không nhận ra' (JSON hỏng/enum lạ) — cái đó mới được
    phép fallback tra_cuu. Gộp hai chế độ hỏng làm số liệu độ chính xác route
    không tách được 'model không chắc' với 'hạ tầng chết' (silent-failure
    review, sau task-10)."""
    class Bad(FakeLlm):
        def chat(self, *a, **k):
            raise ValueError("model trả content rỗng")

    with pytest.raises(ValueError):
        route({"query": "x"}, Bad({}), "m")


def test_rewrite_luon_giu_query_GOC_o_vi_tri_0():
    st = rewrite_query({"query": "công ty cho nghỉ không báo trước"},
                       FakeLlm({"queries": ["nghĩa vụ thông báo khi đơn phương chấm dứt HĐLĐ"]}), "m")
    assert st["queries"][0] == "công ty cho nghỉ không báo trước", (
        "mất query gốc thì rewrite tệ sẽ làm mất luôn kết quả đúng"
    )
    assert len(st["queries"]) == 2


def test_rewrite_loi_thi_van_con_query_goc():
    class Bad(FakeLlm):
        def chat(self, *a, **k):
            raise RuntimeError("api down")

    st = rewrite_query({"query": "abc"}, Bad({}), "m")
    assert st["queries"] == ["abc"]


# ══ Ngoài brief — ba yêu cầu bắt buộc thêm (xem task-8-report.md) ══════════


def test_route_ngoai_pham_vi_la_hanh_vi_dung_duoc_tinh_diem():
    """ngoai_pham_vi KHÔNG phải lỗi cần chặn — câu hỏi rõ ràng ngoài phạm vi (6
    Bộ luật + cụm Lao động) phải được route giữ nguyên, không bị ép về
    tra_cuu như nhánh 'không nhận ra giá trị' ở trên."""
    st = route({"query": "thuế thu nhập cá nhân tính thế nào"},
               FakeLlm({"intent": "ngoai_pham_vi"}), "m")
    assert st["intent"] is Intent.ngoai_pham_vi


def test_route_ghi_traces_dung_khoa_rieng_khong_dam_token_in_tran():
    """route dùng khoá `route_*`, không phải token_in/token_out/cost_usd trần
    mà generate_claims đã chiếm — cùng lý do verify_tier2 dùng `tier2_*`."""
    st = route({"query": "x", "traces": {"claims_raw": 5}}, FakeLlm({"intent": "tra_cuu"}), "m")
    assert st["traces"]["claims_raw"] == 5  # traces của node trước không bị mất
    assert st["traces"]["route_model"] == "m"
    assert st["traces"]["route_token_in"] == 1
    assert st["traces"]["route_token_out"] == 1
    assert st["traces"]["route_cost_usd"] == 0.0


def test_rewrite_ghi_traces_dung_khoa_rieng_va_ve_0_khi_loi():
    st = rewrite_query({"query": "abc", "traces": {"route_token_in": 9}},
                       FakeLlm({"queries": ["def"]}), "m")
    assert st["traces"]["route_token_in"] == 9  # traces của route không bị mất
    assert st["traces"]["rewrite_query_token_in"] == 1
    assert st["traces"]["rewrite_query_variants"] == 1
    assert st["traces"]["rewrite_query_degraded"] is False  # đường thành công: không suy giảm

    class Bad(FakeLlm):
        def chat(self, *a, **k):
            raise RuntimeError("api down")

    st_loi = rewrite_query({"query": "abc"}, Bad({}), "m")
    assert st_loi["traces"]["rewrite_query_token_in"] == 0  # lỗi hạ tầng: 0 thật, không bịa số
    assert st_loi["traces"]["rewrite_query_variants"] == 0
    assert st_loi["traces"]["rewrite_query_degraded"] is True  # Task 9 cần cờ này để loại/tính riêng


def test_rewrite_loi_ha_tang_thi_bat_VA_dem_khong_im_lang(caplog):
    """Ruling coordinator: fallback êm là đúng cho đường chạy thật (OpenRouter
    đang trả 429 thật), nhưng KHÔNG được vô hình — nếu không, phép đo Recall@5
    của Task 9 hỏng theo hướng khó phát hiện nhất (kết quả vẫn hợp lệ, chỉ tệ
    hơn). Ba điều phải cùng đúng: còn nguyên query gốc, cờ degraded bật, và
    có ĐÚNG MỘT bản ghi cảnh báo (không im lặng, không đếm trùng)."""

    class Bad(FakeLlm):
        def chat(self, *a, **k):
            raise RuntimeError("api down")

    with caplog.at_level(logging.WARNING, logger="src.agents.nodes.rewrite_query"):
        st = rewrite_query({"query": "abc"}, Bad({}), "m")

    assert st["queries"] == ["abc"]
    assert st["traces"]["rewrite_query_degraded"] is True
    canh_bao = [r for r in caplog.records if "rewrite_query" in r.getMessage()]
    assert len(canh_bao) == 1, "lỗi hạ tầng phải được đếm đúng một lần, không được nuốt im lặng"


# ══ Integration — mẫu thật, số liệu đầy đủ trong task-8-report.md ═════════
# Đo, KHÔNG chặn CI trên từng câu: model thật không tất định 100%, một câu
# route sai là dữ liệu (yêu cầu #1: ngoai_pham_vi đúng cũng được tính điểm),
# không phải lỗi phải fix. `assert` cuối chỉ chặn khi độ chính xác tụt bất
# thường (< 0.6 trên mẫu 15 câu này).

_MAU_THAT_ROUTE = [
    # tra_cuu — 4 pain point Plan 2 đo được (xem eval/results/report.md)
    ("nghỉ thai sản được bao lâu", Intent.tra_cuu),
    ("nghỉ việc báo trước bao nhiêu ngày", Intent.tra_cuu),
    ("một ngày làm việc mấy tiếng", Intent.tra_cuu),
    ("công ty nợ lương thì làm sao", Intent.tra_cuu),
    # tra_cuu — câu hỏi dân sinh thật từ eval/datasets/golden_qa.yaml (đã ingest)
    ("Nếu sếp em cứ chửi bới, xúc phạm em trước mặt mọi người thì có được không ạ?", Intent.tra_cuu),
    ("Công ty có được trừ thẳng tiền lương của em vì đi muộn vài lần không ạ?", Intent.tra_cuu),
    ("Công ty tôi muốn giảm lương của tôi, họ có được làm ngay không hay phải báo trước bao lâu?", Intent.tra_cuu),
    ("Nếu tôi làm việc không tốt và công ty có quy định đánh giá, họ có thể sa thải tôi mà không "
     "cần báo trước không?", Intent.tra_cuu),
    # soan_thao
    ("soạn giúp tôi một bản hợp đồng lao động thời vụ 6 tháng", Intent.soan_thao),
    ("viết nội quy lao động cho công ty 20 nhân viên", Intent.soan_thao),
    ("giúp tôi soạn quyết định kỷ luật sa thải nhân viên vi phạm", Intent.soan_thao),
    # ngoai_pham_vi — rõ ràng ngoài 6 Bộ luật + cụm Lao động (yêu cầu #1)
    ("thuế thu nhập cá nhân tính như thế nào", Intent.ngoai_pham_vi),
    ("tranh chấp ranh giới đất đai giải quyết ở đâu", Intent.ngoai_pham_vi),
    ("thủ tục ly hôn đơn phương cần giấy tờ gì", Intent.ngoai_pham_vi),
    ("khám bảo hiểm y tế trái tuyến có được thanh toán không", Intent.ngoai_pham_vi),
]


@pytest.mark.integration
def test_do_chinh_xac_route_tren_mau_that():
    from src.services.llm import from_settings, router_model

    llm = from_settings()
    model = router_model()
    dung = 0
    for cau_hoi, ky_vong in _MAU_THAT_ROUTE:
        st = route({"query": cau_hoi}, llm, model)
        khop = st["intent"] is ky_vong
        dung += int(khop)
        print(f"{'OK ' if khop else 'SAI'} kỳ_vọng={ky_vong.value:14} dự_đoán={st['intent'].value:14} — {cau_hoi}")
    do_chinh_xac = dung / len(_MAU_THAT_ROUTE)
    print(f"\nđộ chính xác: {dung}/{len(_MAU_THAT_ROUTE)} = {do_chinh_xac:.2%}")
    assert do_chinh_xac >= 0.6, f"độ chính xác route quá thấp: {do_chinh_xac:.2%}"


_MAU_THAT_REWRITE = [
    "công ty nợ lương thì làm sao",
    "nghỉ việc báo trước bao nhiêu ngày",
    "một ngày làm việc mấy tiếng",
    "nghỉ thai sản được bao lâu",
]


@pytest.mark.integration
def test_rewrite_tren_mau_that_giu_goc_va_khong_bia_thuat_ngu():
    """Gọi rewrite_query THẬT — in biến thể để soát bằng mắt xem có bịa thuật
    ngữ không có trong corpus không (yêu cầu #2, xem task-8-report.md)."""
    from src.services.llm import from_settings, router_model

    llm = from_settings()
    model = router_model()
    for cau_hoi in _MAU_THAT_REWRITE:
        st = rewrite_query({"query": cau_hoi}, llm, model)
        print(f"\nGỐC: {cau_hoi}")
        for q in st["queries"]:
            print(f"  - {q}")
        assert st["queries"][0] == cau_hoi
        assert 1 <= len(st["queries"]) <= 3
