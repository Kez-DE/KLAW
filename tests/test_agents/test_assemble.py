import json

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V

DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26", "so_ky_hieu": "45/2019/QH14",
           "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}
EFF = Effectivity(V.con_hieu_luc, "trung_binh", "x")


class FakeLlm:
    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        return json.dumps({"answer": "Ít nhất 85% mức lương."}), Usage(1, 1, 0.0)


def _pass(pid=11):
    return Tier1Result(Claim("Ít nhất 85%.", pid, "85%"), True, R.ok, EFF)


def test_ngoai_pham_vi_tra_out_of_scope_va_KHONG_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không gọi LLM khi ngoài phạm vi")

    st = assemble({"intent": "ngoai_pham_vi"}, DB, Never(), "m")
    assert st["result_type"] is ResultType.out_of_scope and st["answer"] is None


def test_deep_rong_shallow_co_thi_partial_coverage_va_KHONG_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("PARTIAL_COVERAGE phải là nhánh 0 token")

    st = assemble({"intent": "tra_cuu", "expanded": [], "hits_shallow": [
        {"id": 5, "duong_dan": "84/2015/QH13 > Điều 3", "so_ky_hieu": "84/2015/QH13",
         "ten": "Luật An toàn, vệ sinh lao động"}]}, DB, Never(), "m")
    assert st["result_type"] is ResultType.partial_coverage
    assert st["answer"] is None
    assert "84/2015/QH13" in st["coverage_note"]


def test_khong_claim_nao_qua_tang_1_thi_abstain():
    fail = Tier1Result(Claim("x", 999, "y"), False, R.provision_khong_ton_tai, None)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [fail],
                   "tier2": [], "abstain_threshold": 0.5}, DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain


def test_ty_le_verified_duoi_nguong_thi_abstain():
    ok = _pass()
    fails = [Tier1Result(Claim("x", 999, "y"), False, R.provision_khong_ton_tai, None)] * 3
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [ok, *fails],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain, "1/4 = 0.25 < 0.5"


def test_insufficient_evidence_tu_LLM_duoc_ton_trong():
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "insufficient_evidence": True,
                   "tier1": [], "tier2": [], "abstain_threshold": 0.5}, DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain


def test_tang_2_bac_thi_claim_bi_loai_khoi_citation():
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, False, "không hỗ trợ")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain


def test_answer_mang_citation_co_bo_luat_va_so_ky_hieu_khong_mang_title():
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.answer
    c = st["citations"][0]
    assert c["so_ky_hieu"] == "45/2019/QH14" and c["duong_dan"].startswith("45/2019/QH14")


def test_hieu_luc_khong_chac_sinh_warning():
    mp = Effectivity(V.mot_phan_khong_xac_dinh, "thap", "HHL1P")
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, mp)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["warnings"], "điều luật hết hiệu lực một phần phải sinh cảnh báo"


# ── Bổ sung ngoài 8 test hợp đồng của brief ──────────────────────────────────
# `khop_tai` mặc định None trên Tier1Result (dataclass thật ở verify_tier1.py) và
# không test nào ở trên từng đặt nó khác None — nên riêng nhánh "quote khớp ở
# Khoản con, không phải Điều cha" (yêu cầu #3 của task) chưa có test nào phủ.
# Không có test này thì một regression làm assemble luôn tra theo
# claim.provision_id (bỏ qua khop_tai hoàn toàn) sẽ không bị bắt.
DB_CON = {
    11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 127", "so_ky_hieu": "45/2019/QH14",
         "ten": "Bộ Luật lao động", "noi_dung": "Điều 127. Các hành vi bị nghiêm cấm..."},
    12: {"id": 12, "duong_dan": "45/2019/QH14 > Điều 127 > Khoản 2", "so_ky_hieu": "45/2019/QH14",
         "ten": "Bộ Luật lao động", "noi_dung": "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động."},
}


def test_khop_tai_khac_provision_id_thi_duong_dan_theo_dong_that_chua_quote():
    t1 = Tier1Result(Claim("Cấm phạt tiền.", 11, "Phạt tiền"), True, R.ok, EFF, khop_tai=12)
    st = assemble({"intent": "tra_cuu", "expanded": [DB_CON[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB_CON, FakeLlm(), "m")
    assert st["result_type"] is ResultType.answer
    c = st["citations"][0]
    assert c["provision_id"] == 11, "vẫn neo provisions.id mà claim đã dẫn"
    assert c["duong_dan"] == "45/2019/QH14 > Điều 127 > Khoản 2", (
        "duong_dan hiển thị phải trỏ dòng THẬT chứa quote (khop_tai), không phải Điều cha rỗng ruột"
    )


def test_canh_bao_mang_nguyen_van_ly_do_khong_phai_cau_chung_chung():
    # Yêu cầu #1 của task: cảnh báo hiệu lực phải CHỊU TẢI — `ly_do` nêu đích
    # danh văn bản thay thế, một câu mẫu chung chung ("đã bị thay thế.") xoá
    # mất đúng thông tin đó. `test_hieu_luc_khong_chac_sinh_warning` (test hợp
    # đồng của brief) chỉ kiểm `warnings` không rỗng, không kiểm NỘI DUNG — nên
    # tự thêm test này để một bản tái phát (quay lại câu mẫu chung chung) không
    # lọt qua CI.
    ly_do_that = "đồ thị xác nhận: bị 38/2022/NĐ-CP thay thế từ 2022-07-01"
    bi_thay_the = Effectivity(V.bi_thay_the, "cao", ly_do_that)
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, bi_thay_the)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert any(ly_do_that in w for w in st["warnings"]), (
        f"ly_do nguyên văn phải xuất hiện trong warnings, thấy: {st['warnings']!r}"
    )
