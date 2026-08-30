"""Test cho verify tầng 2 — LLM judge khác họ, batch.

DB fixture tối thiểu (`provision_id=11` là node LÁ, `khop_tai` trùng
`provision_id`) dùng cho các test hợp đồng batch/fail-closed lấy từ brief.
`DB_127` là số liệu THẬT copy từ `test_verify_tier1.py` (Điều 127 của
45/2019/QH14 chỉ có tiêu đề, thân nằm ở Khoản 2 — hình dạng của 73,6% số Điều
trong corpus) — dùng riêng cho test khoá việc lấy văn bản theo `khop_tai`
chứ không phải `claim.provision_id`.
"""

import json

import pytest

from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import verify_tier2, verify_tier2_and_trace
from src.services.llm import Usage, _provider, generate_model, judge_model

DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26",
           "noi_dung": "Ít nhất phải bằng 85% mức lương của công việc đó."}}

DB_127 = {
    141418: {"id": 141418, "duong_dan": "45/2019/QH14 > Điều 127",
             "noi_dung": "Điều 127. Các hành vi bị nghiêm cấm khi xử lý kỷ luật lao động"},
    141420: {"id": 141420, "duong_dan": "45/2019/QH14 > Điều 127 > Khoản 2",
             "noi_dung": "2. Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động."},
}


class FakeLlm:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.last_messages = None

    def chat(self, model, messages, json_schema=None):
        self.calls += 1
        self.last_messages = messages
        return json.dumps(self.payload), Usage(1, 1, 0.0)


def _ok(i, provision_id=11, khop_tai=11, quote="85%"):
    return Tier1Result(Claim(f"c{i}", provision_id, quote), True, R.ok, None, khop_tai=khop_tai)


# ══ Hợp đồng batch (brief) ══════════════════════════════════════════════════
def test_batch_nhieu_claim_trong_MOT_call():
    llm = FakeLlm({"verdicts": [{"claim_index": i, "supported": True, "reason": "x"} for i in range(3)]})
    verify_tier2([_ok(0), _ok(1), _ok(2)], DB, llm, "m")
    assert llm.calls == 1, "phải batch, không gọi từng claim"


def test_chi_kiem_claim_DA_QUA_tang_1():
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "reason": "x"}]})
    fail = Tier1Result(Claim("bad", 999, "x"), False, R.provision_khong_ton_tai, None)
    out = verify_tier2([_ok(0), fail], DB, llm, "m")
    assert len(out) == 1 and out[0].claim_index == 0


def test_khong_co_claim_nao_qua_tang_1_thi_KHONG_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không được gọi LLM khi không có gì để kiểm")

    fail = Tier1Result(Claim("bad", 999, "x"), False, R.provision_khong_ton_tai, None)
    assert verify_tier2([fail], DB, Never({}), "m") == []


def test_verdict_thieu_thi_mac_dinh_KHONG_supported():
    llm = FakeLlm({"verdicts": []})  # judge không trả verdict cho claim 0
    out = verify_tier2([_ok(0)], DB, llm, "m")
    assert out[0].supported is False, "thiếu verdict phải mặc định false, không true"


def test_json_hong_thi_toan_bo_KHONG_supported_khong_sap():
    class Bad(FakeLlm):
        def chat(self, *a, **k):
            return "not json", Usage(1, 1, 0.0)

    out = verify_tier2([_ok(0), _ok(1)], DB, Bad({}), "m")
    assert all(v.supported is False for v in out)


# ══ Khoá thứ tự — hoán vị KHÔNG được gán nhầm phán quyết (yêu cầu #1) ═══════
def test_hoan_vi_thu_tu_van_gan_dung_claim_index():
    """Judge trả verdict KHÔNG theo thứ tự claim_index (2, 0, 1). Một cài đặt
    ghép bằng zip(enumerate(qua), verdicts) thay vì tra theo claim_index sẽ
    gán phán quyết của claim A cho claim B ở đúng ca này, mà không phép kiểm
    hạ nguồn nào bắt được — test này bắt trực tiếp lỗi đó."""
    llm = FakeLlm({"verdicts": [
        {"claim_index": 2, "supported": False, "reason": "claim 2 sai"},
        {"claim_index": 0, "supported": True, "reason": "claim 0 dung"},
        {"claim_index": 1, "supported": False, "reason": "claim 1 sai"},
    ]})
    out = verify_tier2([_ok(0), _ok(1), _ok(2)], DB, llm, "m")
    assert [v.claim_index for v in out] == [0, 1, 2]
    assert [v.supported for v in out] == [True, False, False]
    assert out[0].reason == "claim 0 dung"
    assert out[2].reason == "claim 2 sai"


def test_verdict_di_dang_bi_bo_qua_khong_lam_hong_ca_batch():
    """'batch lỗi giữa chừng' (yêu cầu #3): MỘT verdict trong mảng thiếu
    claim_index hợp lệ không được kéo cả batch về supported=False — chỉ
    claim đó mặc định False, claim khác vẫn dùng verdict thật của nó."""
    llm = FakeLlm({"verdicts": [
        {"claim_index": 0, "supported": True, "reason": "ok"},
        {"claim_index": "not-an-int", "supported": True, "reason": "hong"},
    ]})
    out = verify_tier2([_ok(0), _ok(1)], DB, llm, "m")
    assert out[0].supported is True
    assert out[1].supported is False  # claim 1 không có verdict hợp lệ nào khớp


# ══ Đưa ĐÚNG khop_tai cho judge — không phải tiêu đề rỗng của provision_id ═══
def test_dua_dung_khop_tai_khong_phai_tieu_de_rong_cua_dieu():
    """Task 5 đo: 73,6% số Điều có `noi_dung` CHỈ LÀ TIÊU ĐỀ, thân nằm ở Khoản
    con — đúng nơi `khop_tai` trỏ tới. Tra theo `claim.provision_id` trong các
    ca đó đưa cho judge một tiêu đề RỖNG NỘI DUNG, judge không còn gì để chấm."""
    r = Tier1Result(Claim("x", 141418, "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động"),
                     True, R.ok, None, khop_tai=141420)
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "reason": "x"}]})
    verify_tier2([r], DB_127, llm, "m")
    sent = str(llm.last_messages)
    assert "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động" in sent, \
        "phải đưa đúng nội dung Khoản 2 (khop_tai), không phải tiêu đề Điều 127"


def test_khong_gop_ca_cay_con_thanh_mot_khoi():
    """Chỉ dòng `khop_tai` của TỪNG claim được đưa cho judge — một Khoản anh
    em không liên quan (Khoản 3) không được lọt vào cùng khối văn bản, đúng
    tinh thần "so từng dòng, không nối cây" của tầng 1."""
    db = dict(DB_127)
    db[141421] = {"id": 141421, "duong_dan": "45/2019/QH14 > Điều 127 > Khoản 3",
                  "noi_dung": "3. Một khoản khác không liên quan."}
    r = Tier1Result(Claim("x", 141418, "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động"),
                     True, R.ok, None, khop_tai=141420)
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "reason": "x"}]})
    verify_tier2([r], db, llm, "m")
    sent = str(llm.last_messages)
    assert "Một khoản khác không liên quan" not in sent


# ══ Lỗi hạ tầng KHÔNG được nuốt (yêu cầu #3) ════════════════════════════════
def test_loi_tu_llm_chat_KHONG_bi_nuot():
    """`LlmClient.chat()` raise khi response thiếu 'usage' (Task 3) — đây là
    lỗi HẠ TẦNG, khác với "judge trả JSON hỏng". Không được bắt và biến thành
    supported=False im lặng: một claim mất phán quyết vì lỗi mạng bị nuốt sẽ
    làm sai tỉ lệ tầng 2 mà không ai biết vì sao."""
    class Explode(FakeLlm):
        def chat(self, *a, **k):
            raise ValueError("model m: response thiếu 'usage' — không thể lấy cost thật, không bịa số")

    with pytest.raises(ValueError, match="usage"):
        verify_tier2([_ok(0)], DB, Explode({}), "m")


# ══ Usage thật + tên model vào traces (yêu cầu #2, Global Constraint) ══════
def test_traces_dung_usage_that_va_ca_hai_ten_model():
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "reason": "x"}]})
    verdicts, traces = verify_tier2_and_trace([_ok(0)], DB, llm, "mistralai/judge-fake")
    assert verdicts[0].supported is True
    assert traces["tier2_token_in"] == 1
    assert traces["tier2_token_out"] == 1
    assert traces["tier2_cost_usd"] == 0.0
    assert traces["tier2_judge_model"] == "mistralai/judge-fake"
    assert traces["tier2_generate_model"] == generate_model()


def test_traces_khac_ho_that_giua_generate_va_judge_mac_dinh():
    """Chứng minh bằng SỐ đo được qua chính `traces`, không tuyên bố suông:
    model mặc định của hai vai khác PROVIDER (spec 7b.2)."""
    llm = FakeLlm({"verdicts": []})
    _, traces = verify_tier2_and_trace([], DB, llm, judge_model())
    assert _provider(traces["tier2_generate_model"]) != _provider(traces["tier2_judge_model"])


def test_traces_khong_goi_llm_thi_khong_co_cost_nhung_van_ghi_ten_model():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không có claim nào để kiểm")

    fail = Tier1Result(Claim("bad", 999, "x"), False, R.provision_khong_ton_tai, None)
    verdicts, traces = verify_tier2_and_trace([fail], DB, Never({}), "m")
    assert verdicts == []
    assert traces["tier2_token_in"] == 0 and traces["tier2_cost_usd"] == 0.0
    assert traces["tier2_judge_model"] == "m"


def test_traces_gop_voi_traces_co_san_khong_ghi_de():
    """Global Constraint: nhiều node cùng ghi vào traces — node này không được
    xoá đóng góp của node trước, và không được đụng vào khoá TRẦN
    (`token_in`/`cost_usd`) mà `generate_claims` đã dùng cho vai khác."""
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "reason": "x"}]})
    _, traces = verify_tier2_and_trace([_ok(0)], DB, llm, "m", prior_traces={"claims_raw": 5, "token_in": 999})
    assert traces["claims_raw"] == 5
    assert traces["token_in"] == 999  # của generate_claims — tier2 KHÔNG được ghi đè
    assert traces["tier2_token_in"] == 1  # đóng góp riêng của tier2, khoá riêng


# ══ Integration — một lần gọi judge THẬT, xem báo cáo Task 6 ═══════════════
@pytest.mark.integration
def test_that_judge_cham_dung_mot_claim_that_ho_tro():
    """Claim thật, quote thật (Điều 26 — xem test_verify_tier1.py), khớp
    tier 1 thật, đưa cho judge THẬT (khác họ generate — spec 7b.2)."""
    from src.services.llm import from_settings

    r = Tier1Result(Claim("Lương thử việc ít nhất 85%.", 11, "ít nhất phải bằng 85%"),
                     True, R.ok, None, khop_tai=11)
    llm = from_settings()
    verdicts, traces = verify_tier2_and_trace([r], DB, llm, judge_model())
    assert len(verdicts) == 1
    assert verdicts[0].supported is True, verdicts[0].reason
    assert traces["tier2_token_in"] > 0 and traces["tier2_cost_usd"] >= 0.0
    assert _provider(traces["tier2_generate_model"]) != _provider(traces["tier2_judge_model"])
