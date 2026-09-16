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
    """ngoai_pham_vi KHÔNG phải lỗi cần chặn — câu hỏi rõ ràng ngoài phạm vi
    (8 lĩnh vực, xem `prompts/route.v1.md`) phải được route giữ nguyên, không
    bị ép về tra_cuu như nhánh 'không nhận ra giá trị' ở trên.

    Sửa 2026-09-02: ví dụ cũ ("thuế thu nhập cá nhân") hết đúng sau khi T1 mở
    phạm vi — Thuế nay TRONG phạm vi (`prompts/route.v1.md`). Đổi sang bảo
    hiểm y tế: kho không có Luật Bảo hiểm y tế nào mang toàn văn (tự kiểm
    `SELECT ... FROM documents WHERE ten ILIKE '%bảo hiểm y tế%'` — cả ba bản
    đều `depth='shallow'`, 1 provision `mo_dau`/bản, không điều khoản thật).
    `FakeLlm` ép sẵn `intent="ngoai_pham_vi"` nên câu hỏi chỉ mang tính minh
    hoạ, không đổi cơ chế test."""
    st = route({"query": "khám bảo hiểm y tế trái tuyến có được thanh toán không"},
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
    # tra_cuu — T1 mở phạm vi 2026-09-02 (xem prompts/route.v1.md): ba câu dưới
    # ĐÃ TỪNG khai ngoai_pham_vi ở đây, nhưng Thuế/Đất đai/Hôn nhân gia đình
    # nay có luật gốc trong kho (Luật Thuế TNCN 187045, Luật Đất đai 177815,
    # Luật HN&GĐ 36870) nên router trả tra_cuu là ĐÚNG, không phải lỗi. Nhãn
    # cũ hạ oan độ chính xác 3/15 = 20 điểm phần trăm — sửa để đo đúng.
    ("thuế thu nhập cá nhân tính như thế nào", Intent.tra_cuu),
    ("tranh chấp ranh giới đất đai giải quyết ở đâu", Intent.tra_cuu),
    ("thủ tục ly hôn đơn phương cần giấy tờ gì", Intent.tra_cuu),
    # ngoai_pham_vi — rõ ràng ngoài cả 8 lĩnh vực (xem prompts/route.v1.md).
    # Luật Bảo hiểm y tế: kho không có bản nào mang toàn văn (tự kiểm — cả ba
    # bản đều depth='shallow', 1 provision mo_dau/bản).
    ("khám bảo hiểm y tế trái tuyến có được thanh toán không", Intent.ngoai_pham_vi),
    # Hai ca dưới do coordinator chỉ định 2026-09-02 (review vừa xong), thay
    # cho việc tôi tự chọn một câu ngoài phạm vi — đây là hai ca RỦI RO NHẤT
    # đang có trong hệ thống, không phải hai ca ngẫu nhiên: `route.v1.md` liệt
    # "Đất đai, Kinh doanh bất động sản" trong phạm vi mà KHÔNG nhắc Nhà ở, và
    # BHXH nằm sát cụm Lao động (đã trong phạm vi) — cả hai đều dễ bị model
    # gộp nhầm vào một lĩnh vực họ hàng đã mở, rồi trả lời (kèm trích dẫn đã
    # xác minh) từ SAI luật. Tự kiểm bằng
    # `SELECT id, so_ky_hieu, ten, depth, (SELECT count(*) FROM provisions p
    # WHERE p.document_id = d.id) AS n FROM documents d WHERE ten ILIKE
    # '%nhà ở%' OR ten ILIKE '%bảo hiểm xã hội%'` trước khi tin dòng này:
    # Luật Nhà ở 27/2023/QH15 (169032) — depth='shallow', n=1 (chỉ mo_dau).
    # Luật Bảo hiểm xã hội 41/2024/QH15 (175027) — depth='metadata', n=0.
    # Cả hai được fetch nhưng KHÔNG tải được toàn văn nên bị loại khỏi kho có
    # chủ đích (xem task-1) — không văn bản nào trả lời được câu dưới.
    ("mua nhà ở xã hội cần điều kiện gì", Intent.ngoai_pham_vi),
    ("đóng bảo hiểm xã hội bao nhiêu năm thì được hưởng lương hưu", Intent.ngoai_pham_vi),
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


def test_moi_Intent_deu_co_mat_trong_PROMPT_va_trong_JSON_SCHEMA():
    """Chỗ hỏng IM LẶNG NHẤT của việc thêm một ý định: `Intent` có thành viên
    mới, `_RE_TAT` có, `assemble` có nhánh, `TraCuuResponse` có `Literal` — mà
    `prompts/route.v1.md` không tả nó và `INTENT_SCHEMA` không cho phép nó.

    Không test nào ở trên đỏ, không log nào bật lên: model chỉ đơn giản không
    bao giờ chọn được giá trị đó (JSON schema chặn), rồi `route` nuốt lỗi bằng
    mặc định `tra_cuu` — đúng nhánh mặc định an toàn — và cả tính năng thành mã
    chết. So HAI TẬP, không liệt kê tay.

    `tai_lieu` là ý định CÓ ĐIỀU KIỆN (quyết định chủ sở hữu 2026-09-16 Q4): nó
    chỉ được chào ra khi hội thoại đang giữ tài liệu, nên nó nằm ở
    `schema_v4(True)` + `route.v4.md` chứ không ở `INTENT_SCHEMA` + `route.v1.md`.
    Bất biến KHÔNG đổi — mọi ý định vẫn phải có một schema chào nó và một
    template tả nó — chỉ là tập schema/template để so có hai phần tử.
    """
    from pathlib import Path

    from src.agents.nodes.route import INTENT_SCHEMA, PROMPT_PATH, schema_v4

    duong_v4 = Path("prompts/route.v4.md")
    co_dieu_kien = {Intent.tai_lieu.value}
    trong_schema = set(INTENT_SCHEMA["properties"]["intent"]["enum"])
    luon_co = {i.value for i in Intent} - co_dieu_kien
    assert trong_schema == luon_co, (
        f"lệch: Intent có {luon_co - trong_schema}, schema có {trong_schema - luon_co}"
    )
    assert co_dieu_kien <= set(schema_v4(True)["properties"]["intent"]["enum"])
    assert not (co_dieu_kien & set(schema_v4(False)["properties"]["intent"]["enum"]))

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    thieu = [v for v in luon_co if f"`{v}`" not in prompt]
    assert not thieu, f"{thieu} không được mô tả trong {PROMPT_PATH}"
    mau_v4 = duong_v4.read_text(encoding="utf-8")
    thieu_v4 = [i.value for i in Intent if f"`{i.value}`" not in mau_v4]
    assert not thieu_v4, f"{thieu_v4} không được mô tả trong {duong_v4}"


def test_route_doc_template_tu_prompt_path_khi_duoc_truyen(tmp_path):
    mau = tmp_path / "r.md"
    mau.write_text("MAU-RIENG {cau_hoi}", encoding="utf-8")

    class Ghi(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            self.prompt_cuoi = messages[-1]["content"]
            return super().chat(model, messages, json_schema)

    llm = Ghi({"intent": "tra_cuu"})
    st = route({"query": "x"}, llm, "m", prompt_path=mau)
    assert st["intent"] is Intent.tra_cuu and llm.prompt_cuoi.startswith("MAU-RIENG")


# ══ Task 3 — router v2: chọn loại văn bản trong cùng lượt gọi ══════════════

V2_MAU = "Phân loại. Khi soan_thao chọn loai_van_ban trong:\n{danh_sach_loai}\nCÂU HỎI: {cau_hoi}"


def _v2(tmp_path):
    p = tmp_path / "route.v2.md"
    p.write_text(V2_MAU, encoding="utf-8")
    return p


def test_v2_schema_enum_dung_tu_checklist_tren_dia():
    from src.agents.graph_soan_thao import cac_loai
    from src.agents.nodes.route import schema_v2

    enum = schema_v2()["properties"]["loai_van_ban"]["enum"]
    assert set(enum) == set(cac_loai()) | {"khong_ro"}
    assert "thoa_thuan_cham_dut_hdld" in enum
    assert schema_v2()["required"] == ["intent", "loai_van_ban", "thay_the", "ly_do"]


def test_v2_danh_sach_loai_co_ten_doc_duoc():
    from src.agents.nodes.route import danh_sach_loai

    ds = danh_sach_loai()
    assert "`don_xin_nghi_viec` — đơn xin nghỉ việc" in ds
    assert ds.count("\n") >= 28


def test_v2_soan_thao_ghi_goi_y_vao_state(tmp_path):
    class Ghi(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            self.schema = json_schema
            self.prompt = messages[-1]["content"]
            return super().chat(model, messages, json_schema)

    llm = Ghi(
        {
            "intent": "soan_thao",
            "loai_van_ban": "don_xin_nghi_viec",
            "thay_the": ["thoa_thuan_cham_dut_hdld"],
            "ly_do": "bạn là người lao động muốn nghỉ",
        }
    )
    st = route({"query": "soạn cho tôi hợp đồng nghỉ việc"}, llm, "m", prompt_path=_v2(tmp_path))
    assert st["intent"] is Intent.soan_thao
    assert st["soan_thao_goi_y"] == {
        "loai": "don_xin_nghi_viec",
        "ly_do": "bạn là người lao động muốn nghỉ",
        "thay_the": ["thoa_thuan_cham_dut_hdld"],
    }
    assert llm.schema["required"][0] == "intent" and "loai_van_ban" in llm.schema["properties"]
    assert "`don_xin_nghi_viec` — " in llm.prompt, "danh sách loại phải được điền vào template"


def test_v2_khong_ro_thanh_None_va_intent_khac_khong_goi_y(tmp_path):
    st = route(
        {"query": "x"},
        FakeLlm({"intent": "soan_thao", "loai_van_ban": "khong_ro", "thay_the": [], "ly_do": ""}),
        "m",
        prompt_path=_v2(tmp_path),
    )
    assert st["soan_thao_goi_y"] == {"loai": None, "ly_do": "", "thay_the": []}
    st2 = route(
        {"query": "x"},
        FakeLlm({"intent": "tra_cuu", "loai_van_ban": "khong_ro", "thay_the": [], "ly_do": ""}),
        "m",
        prompt_path=_v2(tmp_path),
    )
    assert st2["intent"] is Intent.tra_cuu and st2["soan_thao_goi_y"] is None


def test_v1_khong_dat_khoa_goi_y():
    st = route({"query": "soạn hợp đồng"}, FakeLlm({"intent": "soan_thao"}), "m")
    assert "soan_thao_goi_y" not in st


def test_v2_khong_tiem_soul():
    from pathlib import Path

    assert "src.services.prompts" not in Path("src/agents/nodes/route.py").read_text(encoding="utf-8")
