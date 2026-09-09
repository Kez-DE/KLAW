import json

import pytest

from src.agents.nodes.assemble import (
    ANSWER_SCHEMA,
    CHUA_GIAI_NGHIA_DUOC,
    ResultType,
    assemble,
)
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.hoi_lai import HOI_LAI_SCHEMA
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V

DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26", "so_ky_hieu": "45/2019/QH14",
           "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}
EFF = Effectivity(V.con_hieu_luc, "trung_binh", "x")


class FakeLlm:
    """GHI LẠI schema của từng lượt gọi, không chỉ trả nội dung.

    Từ 2026-09-02 `assemble` gọi LLM ở HAI vai khác nhau: hành văn
    (`ANSWER_SCHEMA`) và sinh câu hỏi lại cho một ngõ cụt (`HOI_LAI_SCHEMA`).
    Cách canh cũ — một fake `raise AssertionError` khi bị gọi — nay là một LƯỚI
    CHẾT: `hoi_lai` bắt `Exception` để một ngõ cụt không bao giờ thành HTTP 500,
    nên nó nuốt luôn AssertionError của fake và test PASS mà không canh gì. Đếm
    theo schema thì không nuốt được.
    """

    def __init__(self) -> None:
        self.schema_da_goi: list[dict | None] = []

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        self.schema_da_goi.append(json_schema)
        if json_schema is HOI_LAI_SCHEMA:
            return json.dumps({"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}]}), Usage(1, 1, 0.0)
        return json.dumps({"answer": "Ít nhất 85% mức lương."}), Usage(1, 1, 0.0)

    @property
    def so_lan_hanh_van(self) -> int:
        return sum(1 for s in self.schema_da_goi if s is ANSWER_SCHEMA)

    @property
    def so_lan_hoi_lai(self) -> int:
        return sum(1 for s in self.schema_da_goi if s is HOI_LAI_SCHEMA)


def _pass(pid=11):
    return Tier1Result(Claim("Ít nhất 85%.", pid, "85%"), True, R.ok, EFF)


def test_ngoai_pham_vi_tra_out_of_scope_va_KHONG_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không gọi LLM khi ngoài phạm vi")

    st = assemble({"intent": "ngoai_pham_vi"}, DB, Never(), "m")
    assert st["result_type"] is ResultType.out_of_scope and st["answer"] is None


def test_deep_rong_shallow_co_thi_partial_coverage_va_KHONG_goi_LLM_hanh_van():
    """`partial_coverage` không còn là nhánh 0 token — nó tiêu MỘT lượt sinh câu
    hỏi lại (Pha 2, cố ý). Cái KHÔNG đổi: nó tuyệt đối không được gọi LLM HÀNH
    VĂN, vì hành văn ở đây nghĩa là dựng lời giải thích pháp luật từ nội dung
    chưa qua tầng nào kiểm chứng."""
    llm = FakeLlm()
    st = assemble({"intent": "tra_cuu", "query": "an toàn lao động quy định thế nào",
                   "expanded": [], "hits_shallow": [
                       {"id": 5, "duong_dan": "84/2015/QH13 > Điều 3",
                        "so_ky_hieu": "84/2015/QH13",
                        "ten": "Luật An toàn, vệ sinh lao động"}]}, DB, llm, "m")
    assert st["result_type"] is ResultType.partial_coverage
    assert st["answer"] is None
    assert "84/2015/QH13" in st["coverage_note"]
    assert llm.so_lan_hanh_van == 0, "không được dựng lời giải thích khi chưa kiểm chứng gì"
    assert llm.so_lan_hoi_lai == 1, "ngõ cụt phải hỏi lại, không được dừng ở một danh sách"


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
    llm = FakeLlm()
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, llm, "m")
    assert st["result_type"] is ResultType.answer
    c = st["citations"][0]
    assert c["so_ky_hieu"] == "45/2019/QH14" and c["duong_dan"].startswith("45/2019/QH14")
    # Nhánh CÓ câu trả lời không được hỏi lại (review 2026-09-02: chiều ngược của
    # `so_lan_hanh_van == 0` trên nhánh ngõ cụt chưa có lưới nào). Một lượt
    # `hoi_lai` "phòng hờ" ở đây chỉ tốn token mà không đổi kết quả, nên không
    # assertion nào khác bắt được.
    assert llm.so_lan_hoi_lai == 0, "nhánh answer không được gọi hỏi lại"
    assert llm.so_lan_hanh_van == 1, "nhánh answer phải hành văn đúng MỘT lần"


def test_y_dinh_phu_soan_thao_dinh_kem_goi_y_khong_hijack_answer():
    """Router v3 (Task 13): câu hỏi vừa hỏi luật vừa nhờ soạn — `answer` vẫn là
    câu trả lời tra cứu THẬT, chỉ đính kèm `soan_thao_goi_y` để FE gợi ý soạn
    tiếp. KHÔNG được ghi đè `answer` bằng lời hướng dẫn của nhánh soạn thảo
    riêng (`huong_dan_soan_thao`)."""
    llm = FakeLlm()
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5,
                   "y_dinh_phu": "soan_thao",
                   "soan_thao_goi_y": {"loai": "don_xin_nghi_viec", "ly_do": "bạn sắp nghỉ", "thay_the": []}},
                  DB, llm, "m")
    assert st["result_type"] is ResultType.answer
    assert st["answer"] == "Ít nhất 85% mức lương.", "answer không được bị ghi đè bởi gợi ý soạn thảo"
    gy = st["soan_thao_goi_y"]
    assert gy["loai"] == "don_xin_nghi_viec" and gy["ho_tro"] is True


def test_y_dinh_phu_khong_co_thi_khong_dinh_kem_goi_y():
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.answer
    assert st.get("soan_thao_goi_y") is None


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
    assert c["khop_tai_id"] == 12, "khop_tai_id phải ghi tường minh dòng thật đã khớp"
    assert c["khop_tai_id"] != c["provision_id"], (
        "coordinator review 2026-08-31: hai id phải TÁCH BẠCH khi lệch nhau, không giấu vào duong_dan"
    )
    assert c["duong_dan"] == "45/2019/QH14 > Điều 127 > Khoản 2", (
        "duong_dan hiển thị phải trỏ dòng khop_tai_id, không phải Điều cha rỗng ruột"
    )


def test_khop_tai_none_thi_khop_tai_id_bang_provision_id():
    # coordinator review 2026-08-31: khi khop_tai vắng (không có Khoản con nào
    # tách biệt khỏi Điều đã dẫn), hai id phải BẰNG NHAU — không phải một id
    # "biến mất", để người tiêu thụ citation luôn thấy khop_tai_id, không cần
    # tự suy ra khi nào nó trùng provision_id.
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    c = st["citations"][0]
    assert c["khop_tai_id"] == c["provision_id"] == 11


def test_canh_bao_mang_nguyen_van_ly_do_ca_that_BLLD_45_2019():
    # Yêu cầu #1 + ruling 2026-08-31: `ly_do` phải NGUYÊN VĂN, không phải câu
    # mẫu chung chung ("đã bị thay thế."). Effectivity dưới đây KHÔNG bịa — là
    # kết quả THẬT của `danh_gia_theo_id(get_engine(), "139264", date(2026, 8,
    # 31))` chạy trên DB thật: chính 45/2019/QH14 (Bộ luật Lao động, văn bản
    # trung tâm của khoá luận) bị 19/2023/QH15 sửa đổi, bổ sung từ 2024-07-01,
    # đồ thị không có cạnh xác nhận cấp điều khoản nên rơi vào
    # `mot_phan_khong_xac_dinh`. `test_hieu_luc_khong_chac_sinh_warning` (test
    # hợp đồng của brief) chỉ kiểm `warnings` không rỗng, không kiểm NỘI DUNG —
    # tự thêm test này để một tái phát (quay lại câu mẫu chung chung) không lọt
    # qua CI.
    ly_do_that = (
        "bị 19/2023/QH15 sửa đổi, bổ sung từ 2024-07-01; CSDL quốc gia không công bố "
        "dữ liệu cấp điều khoản nên không xác định được điều này còn hiệu lực hay không"
    )
    blld = Effectivity(V.mot_phan_khong_xac_dinh, "thap", ly_do_that)
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, blld)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert any(ly_do_that in w for w in st["warnings"]), (
        f"ly_do nguyên văn phải xuất hiện trong warnings, thấy: {st['warnings']!r}"
    )


def test_chua_xac_dinh_cung_sinh_canh_bao_khong_duoc_im_lang():
    # Ruling 2026-08-31: brief không liệt kê chua_xac_dinh, nhưng im lặng ở
    # verdict "hoàn toàn không biết" bị người dùng đọc thành "ổn" — ngược với
    # lời hứa "bảo đảm nguồn gốc/nguyên văn, KHÔNG bảo đảm là bản hiện hành".
    khong_biet = Effectivity(V.chua_xac_dinh, "thap", "thiếu ngày hiệu lực — không so được chiều thời gian")
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, khong_biet)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["warnings"], "chua_xac_dinh phải sinh cảnh báo, không được im lặng"


# ══ Phép kiểm thứ năm (coordinator, task-10 round 3) — số Điều trong `answer` ═
# phải nằm trong tập trích dẫn đã xác minh. Ca thật: trap-nonexist-09 (Điều 550
# BLTTDS không tồn tại) — assemble lấy đúng nội dung Điều 363-365 nhưng viết
# prose gán cho "Điều 550". Gián đoạn 1/6 lần đo lại, không hệ thống.

import inspect  # noqa: E402

from src.agents.nodes.assemble import _dieu_khong_duoc_chong_do  # noqa: E402


def test_dieu_khong_chong_do_bat_so_dieu_khong_co_trong_citation():
    citations = [{"duong_dan": "92/2015/QH13 > Điều 363"}, {"duong_dan": "92/2015/QH13 > Điều 364"}]
    assert _dieu_khong_duoc_chong_do(
        "Điều 550 Bộ luật Tố tụng dân sự quy định thủ tục nhận đơn yêu cầu.", citations,
    ) == ["550"]


def test_dieu_khong_chong_do_giu_nguyen_khi_so_dieu_co_trong_citation():
    citations = [{"duong_dan": "45/2019/QH14 > Điều 35 > Khoản 1"}]
    assert _dieu_khong_duoc_chong_do("Điều 35 quy định người lao động có quyền nghỉ.", citations) == []


def test_dieu_khong_chong_do_answer_khong_nhac_dieu_nao_thi_rong():
    citations = [{"duong_dan": "45/2019/QH14 > Điều 35"}]
    assert _dieu_khong_duoc_chong_do("Người lao động có quyền nghỉ hằng năm.", citations) == []


def test_dieu_khong_chong_do_0_token_khong_can_llm_hay_engine():
    """Hàm thuần tra bảng: chữ ký chỉ nhận answer/citations — không llm, không
    engine, không cách nào chạm mạng. Cùng tinh thần test chữ ký của
    verify_tier1 (module đó dùng cả quét AST + chặn socket vì nó là phép kiểm
    TRUNG TÂM của khoá luận; phép kiểm thứ năm này nhỏ và thuần set/regex nên
    kiểm chữ ký là đủ)."""
    assert set(inspect.signature(_dieu_khong_duoc_chong_do).parameters) == {"answer", "citations"}


def test_assemble_ha_xuong_abstain_khi_answer_gan_sai_so_dieu():
    """Ca thật trap-nonexist-09: citation đúng là Điều 363, nhưng LLM hành văn
    gán nội dung cho 'Điều 550' (số bịa từ câu hỏi) — phải hạ xuống abstain,
    với mã lý do riêng (LY_DO_DIEU_KHONG_CHONG_DO) để đếm được tần suất."""
    class FakeLlmGanSaiSoDieu(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            from src.services.llm import Usage
            return json.dumps({"answer": "Điều 550 quy định thủ tục nhận và xử lý đơn yêu cầu."}), Usage(1, 1, 0.0)

    db = {363: {"id": 363, "duong_dan": "92/2015/QH13 > Điều 363", "so_ky_hieu": "92/2015/QH13", "ten": "x"}}
    t1 = Tier1Result(Claim("Thủ tục nhận đơn.", 363, "nội dung"), True, R.ok, EFF)
    st = assemble({"intent": "tra_cuu", "expanded": [db[363]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  db, FakeLlmGanSaiSoDieu(), "m")
    assert st["result_type"] is ResultType.abstain
    assert st["answer"] is None and st["citations"] == []
    assert st["traces"]["assemble_dieu_bi_loai"] == ["550"]


def test_assemble_khong_ha_xuong_khi_khong_co_so_dieu_lech():
    """Đường bình thường (FakeLlm trả lời không nhắc số Điều nào) phải KHÔNG bị
    ảnh hưởng — traces vẫn ghi assemble_dieu_bi_loai=[] để đếm được mẫu số
    (bao nhiêu request đã qua phép kiểm này mà không bị hạ)."""
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.answer
    assert st["traces"]["assemble_dieu_bi_loai"] == []


# ══ Phép kiểm thứ bảy (coordinator, sau khi tự kiểm phép kiểm 6) — không dựng ═
# câu trả lời từ các nguồn đã bị thay thế khi câu hỏi KHÔNG neo văn bản cụ thể.
# Ca thật đo được: "mức lương tối thiểu vùng I HIỆN NAY" gộp 4.420.000/
# 4.180.000/3.980.000/3.500.000 (bốn NĂM khác nhau, đều bi_thay_the) thành
# "các phương án song song" — từng citation đúng, hành văn sai.


def test_khong_neo_va_TOAN_BO_da_bi_thay_thi_abstain_KHONG_hanh_van():
    """LLM hành văn KHÔNG được gọi khi đã biết trước không còn nguồn nào hợp lệ
    để dựng câu trả lời. (Lượt sinh câu hỏi lại là một vai KHÁC và vẫn chạy —
    xem `FakeLlm`.)"""
    llm = FakeLlm()
    db = {1: {"id": 1, "duong_dan": "90/2019/NĐ-CP > Điều 3", "so_ky_hieu": "90/2019/NĐ-CP", "ten": "x"}}
    eff_thay = Effectivity(V.bi_thay_the, "trung_binh", "suy luận cùng chủ đề: 74/2024/NĐ-CP cùng chủ đề và đã có "
                            "hiệu lực từ 2024-07-01")
    t1 = Tier1Result(Claim("4.420.000 đồng/tháng vùng I.", 1, "4.420.000"), True, R.ok, eff_thay)
    st = assemble({"intent": "tra_cuu", "query": "mức lương tối thiểu vùng I hiện nay là bao nhiêu",
                   "expanded": [db[1]], "tier1": [t1], "tier2": [Tier2Verdict(0, True, "ok")],
                   "abstain_threshold": 0.5}, db, llm, "m")
    assert st["result_type"] is ResultType.abstain
    assert "74/2024/NĐ-CP" in st["coverage_note"], "phải nêu ĐÍCH DANH văn bản đi thay"
    assert st["traces"]["assemble_nguon_bi_loc_khoi_prose"] == ["90/2019/NĐ-CP"]
    assert llm.so_lan_hanh_van == 0


def test_neo_van_ban_thi_KHONG_loc_giu_nguyen_hanh_vi():
    db = {1: {"id": 1, "duong_dan": "90/2019/NĐ-CP > Điều 3 > Khoản 1 > Điểm a",
              "so_ky_hieu": "90/2019/NĐ-CP", "ten": "x"}}
    eff_thay = Effectivity(V.bi_thay_the, "trung_binh", "suy luận cùng chủ đề: 74/2024/NĐ-CP cùng chủ đề")
    t1 = Tier1Result(Claim("Mức 4.420.000 đồng/tháng, áp dụng vùng I.", 1, "4.420.000"), True, R.ok, eff_thay)

    class FakeLlmSo(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            from src.services.llm import Usage
            return json.dumps({"answer": "Theo Nghị định 90/2019, mức 4.420.000 đồng/tháng."}), Usage(1, 1, 0.0)

    st = assemble({"intent": "tra_cuu", "query": "theo Nghị định 90/2019 lương tối thiểu vùng I bao nhiêu",
                   "expanded": [db[1]], "tier1": [t1], "tier2": [Tier2Verdict(0, True, "ok")],
                   "abstain_threshold": 0.5}, db, FakeLlmSo(), "m")
    assert st["result_type"] is ResultType.answer
    assert "4.420.000" in st["answer"]
    assert st["warnings"], "cảnh báo hiệu lực vẫn phải còn dù đã neo văn bản"
    assert st["traces"]["assemble_nguon_bi_loc_khoi_prose"] == []


def test_mix_con_hieu_luc_va_bi_thay_the_prose_chi_dung_con_hieu_luc():
    db = {1: {"id": 1, "duong_dan": "293/2025/NĐ-CP > Điều 3", "so_ky_hieu": "293/2025/NĐ-CP", "ten": "x"},
          2: {"id": 2, "duong_dan": "90/2019/NĐ-CP > Điều 3", "so_ky_hieu": "90/2019/NĐ-CP", "ten": "y"}}
    eff_con = Effectivity(V.con_hieu_luc, "thap", "không có tín hiệu chấm dứt nào")
    eff_thay = Effectivity(V.bi_thay_the, "trung_binh", "suy luận cùng chủ đề: 293/2025/NĐ-CP cùng chủ đề")
    t1a = Tier1Result(Claim("NOI DUNG CON HIEU LUC.", 1, "q1"), True, R.ok, eff_con)
    t1b = Tier1Result(Claim("NOI DUNG DA BI THAY THE.", 2, "q2"), True, R.ok, eff_thay)

    class Ghi(FakeLlm):
        cau_hoi_gui = ""

        def chat(self, model, messages, json_schema=None):
            Ghi.cau_hoi_gui = messages[-1]["content"]
            from src.services.llm import Usage
            return json.dumps({"answer": "NOI DUNG CON HIEU LUC."}), Usage(1, 1, 0.0)

    st = assemble({"intent": "tra_cuu", "query": "mức lương tối thiểu hiện nay",
                   "expanded": [db[1], db[2]], "tier1": [t1a, t1b],
                   "tier2": [Tier2Verdict(0, True, "ok"), Tier2Verdict(1, True, "ok")],
                   "abstain_threshold": 0.5}, db, Ghi(), "m")
    assert "NOI DUNG CON HIEU LUC" in Ghi.cau_hoi_gui
    assert "NOI DUNG DA BI THAY THE" not in Ghi.cau_hoi_gui, "prose không được nạp claim đã lọc"
    assert st["result_type"] is ResultType.answer
    assert st["traces"]["assemble_nguon_bi_loc_khoi_prose"] == ["90/2019/NĐ-CP"]


def test_neo_vao_van_ban_va_ly_do_ke_nhiem_0_token():
    from src.agents.nodes.assemble import _neo_vao_van_ban, _van_ban_ke_nhiem
    assert set(inspect.signature(_neo_vao_van_ban).parameters) == {"query", "so_ky_hieu"}
    assert set(inspect.signature(_van_ban_ke_nhiem).parameters) == {"ly_do"}


def test_N1_phep_kiem_5_chi_so_voi_citation_DUNG_CHO_PROSE_khong_phai_toan_bo():
    """Bug đo được (silent-failure review round 2): phép kiểm thứ năm từng so
    `answer` với TOÀN BỘ `citations` — kể cả claim đã bị phép kiểm thứ bảy
    loại khỏi văn xuôi (bi_thay_the, không neo). Answer nhắc số Điều của
    nguồn ĐÃ BỊ LOẠI đó vẫn "qua" phép kiểm 5 vì nó tình cờ có mặt ở đâu đó
    trong `citations` đầy đủ — dù prompt hành văn chưa từng thấy claim đó.

    Điều 5 (con_hieu_luc, DÙNG cho prose) và Điều 3 (bi_thay_the, không neo,
    BỊ LOẠI khỏi prose) khác số cố ý — để "Điều 3 có mặt trong citations đầy
    đủ" và "Điều 3 có mặt trong citations_dung_cho_prose" tách bạch được."""
    db = {1: {"id": 1, "duong_dan": "293/2025/NĐ-CP > Điều 5", "so_ky_hieu": "293/2025/NĐ-CP", "ten": "x"},
          2: {"id": 2, "duong_dan": "90/2019/NĐ-CP > Điều 3", "so_ky_hieu": "90/2019/NĐ-CP", "ten": "y"}}
    eff_con = Effectivity(V.con_hieu_luc, "thap", "không có tín hiệu chấm dứt nào")
    eff_thay = Effectivity(V.bi_thay_the, "trung_binh", "suy luận cùng chủ đề: 293/2025/NĐ-CP cùng chủ đề")
    t1a = Tier1Result(Claim("Điều 5 quy định mức lương mới.", 1, "q1"), True, R.ok, eff_con)
    t1b = Tier1Result(Claim("Điều 3 quy định mức lương cũ.", 2, "q2"), True, R.ok, eff_thay)

    class NhacDieuDaBiLoc(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            from src.services.llm import Usage
            # answer nhắc "Điều 3" — số Điều của claim ĐÃ BỊ LOẠI khỏi prose
            # (90/2019, bi_thay_the, không neo). Trước fix N1: phép kiểm 5 so
            # với `citations` ĐẦY ĐỦ (có cả Điều 3 của claim bị loại) → cho
            # qua NHẦM. Sau fix: so với `citations_dung_cho_prose` (chỉ Điều
            # 5) → không thấy Điều 3 → hạ xuống abstain, đúng ý phép kiểm 5.
            return json.dumps({"answer": "Điều 3 quy định mức lương cũ."}), Usage(1, 1, 0.0)

    st = assemble({"intent": "tra_cuu", "query": "mức lương tối thiểu hiện nay",
                   "expanded": [db[1], db[2]], "tier1": [t1a, t1b],
                   "tier2": [Tier2Verdict(0, True, "ok"), Tier2Verdict(1, True, "ok")],
                   "abstain_threshold": 0.5}, db, NhacDieuDaBiLoc(), "m")
    assert st["result_type"] is ResultType.abstain
    assert st["traces"]["assemble_dieu_bi_loai"] == ["3"]


def test_CRITICAL_tier2_RONG_HOAN_TOAN_khong_duoc_coi_la_da_verified():
    """Test quan trọng nhất của lượt này (coordinator): khoá đúng RULING
    2026-08-31 mà Task 9 đã gỡ khỏi assemble.py — "tier2 rỗng toàn bộ" KHÔNG
    được coi là "mọi claim qua tầng 1 đã verified". Một mutation tái lập đúng
    bug đó (`if not tier2: verified = qua_t1`) từng chạy qua CI xanh tuyệt đối
    vì không test nào canh nhánh này — một comment ruling không phải một phép
    kiểm. Tier 1 CÓ 2 claim pass, tier2 RỖNG HOÀN TOÀN (không phải thiếu vài
    verdict — không có lấy MỘT cái)."""
    llm = FakeLlm()
    t1a = Tier1Result(Claim("a", 11, "85%"), True, R.ok, EFF)
    t1b = Tier1Result(Claim("b", 11, "85%"), True, R.ok, EFF)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1a, t1b],
                   "tier2": [], "abstain_threshold": 0.5}, DB, llm, "m")
    assert st["result_type"] is not ResultType.answer
    assert st["result_type"] is ResultType.abstain
    assert st["citations"] == [] and st["answer"] is None
    assert llm.so_lan_hanh_van == 0, "verified rỗng thì không được gọi LLM hành văn"


def test_citation_mang_doc_id_de_FE_mo_duoc_dieu_luat():
    # Click-to-verify gọi `GET /api/v1/van-ban/{doc_id}?around=<khop_tai_id>`.
    # Trước bản này citation KHÔNG mang `doc_id`: FE chỉ có `so_ky_hieu` và
    # không dựng nổi URL, nên panel đối chiếu — đóng góp trung tâm của đề tài —
    # không mở được. `documents.id` là TEXT (xem VanBanProvisionsResponse), nên
    # citation phải mang str, không phải int.
    db = {11: {**DB[11], "document_id": "139264"}}
    st = assemble({"intent": "tra_cuu", "expanded": [db[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  db, FakeLlm(), "m")
    assert st["citations"][0]["doc_id"] == "139264"


def test_partial_coverage_mang_nguon_co_doc_id_de_mo_duoc_van_ban():
    # `partial_coverage` luôn có `citations: []` (đúng thiết kế: chưa kiểm chứng
    # được thì không được dựng trích dẫn). Nhưng nếu response CHỈ có
    # `coverage_note` dạng văn xuôi thì giao diện không mở nổi văn bản đang nói
    # tới — người dùng nhận một ngõ cụt. FE không được phép parse chuỗi để bịa
    # link. Nên nhánh này phải mang `nguon`: doc_id + so_ky_hieu, đủ để mở mục
    # lục văn bản, KHÔNG kèm quote (chưa có gì được kiểm chứng để trích).
    shallow = [
        {"id": 5, "document_id": "84265", "duong_dan": "84/2015/QH13 > Điều 3",
         "so_ky_hieu": "84/2015/QH13", "ten": "Luật An toàn, vệ sinh lao động"},
        {"id": 6, "document_id": "84265", "duong_dan": "84/2015/QH13 > Điều 4",
         "so_ky_hieu": "84/2015/QH13", "ten": "Luật An toàn, vệ sinh lao động"},
    ]
    st = assemble({"intent": "tra_cuu", "expanded": [], "hits_shallow": shallow}, DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.partial_coverage
    assert st["citations"] == [], "partial_coverage không được dựng trích dẫn chưa kiểm chứng"
    assert st["nguon"] == [{"doc_id": "84265", "so_ky_hieu": "84/2015/QH13",
                            "bo_luat": "Luật An toàn, vệ sinh lao động"}], (
        "gộp theo doc_id — hai Điều cùng một văn bản là MỘT nguồn, không phải hai"
    )


def test_cac_nhanh_khac_co_nguon_rong():
    st = assemble({"intent": "ngoai_pham_vi"}, DB, FakeLlm(), "m")
    assert st["nguon"] == []


def test_bi_sua_doi_sinh_warning_neu_dich_danh_van_ban_sua():
    """Bẫy whitelist: `CANH_BAO_NHAN` liệt kê verdict được cảnh báo, nên một
    verdict MỚI mặc định IM LẶNG. `bi_sua_doi` (Mức 4, bản đồ sửa đổi cấp điều
    khoản từ VBHN Công báo) chính xác hơn `mot_phan_khong_xac_dinh` mà nó thay
    — nêu đích danh văn bản sửa và ngày — nên để nó rơi khỏi whitelist là biến
    một cải tiến thành HỒI QUY: điều khoản trước đây có cảnh báo mơ hồ nay
    không còn cảnh báo nào.
    """
    eff = Effectivity(V.bi_sua_doi, "trung_binh",
                      "Điều 139 > Khoản 1 bị sửa bởi khoản 1 Điều 29 của 113/2025/QH15 "
                      "từ 2026-07-01 (nguồn: congbao.chinhphu.vn — 18/VBHN-VPQH)")
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, eff)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["warnings"], "điều khoản đã bị sửa đổi phải sinh cảnh báo"
    (w,) = st["warnings"]
    assert "113/2025/QH15" in w and "2026-07-01" in w, (
        "cảnh báo phải mang `ly_do` NGUYÊN VĂN — nhãn ngắn một mình xoá mất "
        "đúng thông tin mà Mức 4 sinh ra để cung cấp")


def test_bi_sua_doi_KHONG_bi_loc_khoi_prose():
    """Điều khoản bị sửa vẫn là điều khoản CÓ THẬT và trích dẫn nguyên văn của
    nó vẫn đúng nguồn gốc — chỉ kèm cảnh báo. Chỉ văn bản CHẾT HẲN
    (`bi_thay_the`/`het_hieu_luc`) mới bị loại khỏi prose."""
    eff = Effectivity(V.bi_sua_doi, "trung_binh", "... 113/2025/QH15 từ 2026-07-01")
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, eff)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.answer
    assert st["citations"], "trích dẫn vẫn phải được phát ra"


def test_hoi_ve_kho_dung_chuoi_da_tinh_san_va_KHONG_goi_LLM():
    """Số liệu về kho là một phép tra bảng, không phải một lượt suy luận: chuỗi
    do `graph_tra_cuu.n_assemble` tính bằng SQL (nơi có `engine`) rồi đưa vào
    state. `assemble` chỉ dán nó vào `answer` — 0 token, và không con số nào do
    model sinh ra."""
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("câu hỏi về kho phải là nhánh 0 token")

    st = assemble({"intent": "hoi_ve_kho", "tra_loi_kho": "Trong kho của mình…"},
                  DB, Never(), "m")
    assert st["result_type"] is ResultType.hoi_ve_kho
    assert st["answer"] == "Trong kho của mình…"
    assert st["traces"]["assemble_token_in"] == 0


# ══ Thôi khẳng định điều chưa chứng minh (spec mục 5) ═══════════════════════
# ĐO ĐƯỢC 2026-09-02: "liệt kê bảng cho tôi" khớp NHIỄU hai văn bản shallow
# (Luật Phòng chống ma túy, Luật Thương mại) và người hỏi nhận về "Mình tìm được
# **văn bản chi phối** câu hỏi của bạn". Luật Phòng chống ma túy không chi phối
# "liệt kê bảng cho tôi" — đó là một lời nói SAI, không phải một lời nói mềm.
#
# Cái được nói ở đây là điều đúng được: mấy văn bản này KHỚP TỪ NGỮ trong câu
# hỏi, và mình chưa có toàn văn để đọc. KHÔNG dựng bộ phân loại "câu hỏi có nội
# dung pháp lý hay không" — đó lại là một danh sách từ khoá pháp lý cần thẩm
# quyền domain, đúng thứ đã bị từ chối cho bộ lọc `hoi_lai`.

_NHIEU = {"id": 5, "document_id": "8532", "cap": "mo_dau",
          "duong_dan": "120/2025/QH15 > Mở đầu", "so_ky_hieu": "120/2025/QH15",
          "ten": "LUẬT PHÒNG, CHỐNG MA TÚY"}


def test_partial_coverage_KHONG_khang_dinh_van_ban_chi_phoi_cau_hoi():
    st = assemble({"intent": "tra_cuu", "query": "liệt kê bảng cho tôi",
                   "expanded": [], "hits_shallow": [_NHIEU]}, DB, FakeLlm(), "m")
    ghi_chu = st["coverage_note"]
    assert st["result_type"] is ResultType.partial_coverage
    assert "khớp từ ngữ" in ghi_chu, f"chưa nói ra mức độ thật của phép khớp:\n{ghi_chu}"
    for sai in ("chi phối", "nằm trong"):
        assert sai not in ghi_chu, f"vẫn khẳng định {sai!r} cho một khớp nhiễu:\n{ghi_chu}"
    assert "120/2025/QH15" in ghi_chu, "vẫn phải nêu đích danh văn bản đã khớp"


def test_abstain_co_nguon_cung_KHONG_khang_dinh_van_ban_chi_phoi():
    """`_da_biet` — nửa đầu MẶC ĐỊNH của mọi ngõ cụt — viết cùng một câu ấy, nên
    sửa một mình `_phu_mot_phan` chỉ vá đúng đường mà bảng `traces` tình cờ ghi
    lại. Cùng lời nói sai, cùng phải sửa."""
    st = assemble({"intent": "tra_cuu", "query": "liệt kê bảng cho tôi",
                   "expanded": [DB[11]], "tier1": [], "tier2": [],
                   "abstain_threshold": 0.5}, DB, FakeLlm(), "m")
    ghi_chu = st["coverage_note"]
    assert st["result_type"] is ResultType.abstain
    for sai in ("chi phối", "nằm trong"):
        assert sai not in ghi_chu, f"vẫn khẳng định {sai!r} khi chưa dựng nổi luận điểm:\n{ghi_chu}"
    assert "45/2019/QH14" in ghi_chu, "vẫn phải nêu cái đã biết"


# ══ `so_ky_hieu` dị dạng KHÔNG ra tới mặt người đọc (spec mục 6) ════════════

_DI_DANG = {"id": 6, "document_id": "8532", "cap": "mo_dau",
            "duong_dan": "Không số > Mở đầu", "so_ky_hieu": "Không số",
            "ten": "Luật Thương mại số Không số"}


def test_coverage_note_khong_trinh_bay_Khong_so_nhu_mot_dinh_danh():
    st = assemble({"intent": "tra_cuu", "query": "liệt kê bảng cho tôi",
                   "expanded": [], "hits_shallow": [_DI_DANG]}, DB, FakeLlm(), "m")
    ghi_chu = st["coverage_note"]
    assert "Không số" not in ghi_chu, f"'Không số' hiện ra như một số hiệu:\n{ghi_chu}"
    assert "Luật Thương mại" in ghi_chu, f"cắt số hiệu dị dạng mà mất luôn văn bản:\n{ghi_chu}"


def test_nguon_khong_mang_so_hieu_di_dang():
    """`nguon` là thứ giao diện in ra cạnh nút mở văn bản gốc — `doc_id` mới là
    khoá dựng URL, `so_ky_hieu`/`bo_luat` chỉ để đọc."""
    st = assemble({"intent": "tra_cuu", "query": "liệt kê bảng cho tôi",
                   "expanded": [], "hits_shallow": [_DI_DANG]}, DB, FakeLlm(), "m")
    (n,) = st["nguon"]
    assert n["doc_id"] == "8532", "khoá dữ liệu không được đụng tới"
    assert n["so_ky_hieu"] == "", "không có số hiệu thật thì để trống, không bịa một cái"
    assert n["bo_luat"] == "Luật Thương mại"


def test_khong_giai_nghia_duoc_thi_noi_DUNG_dieu_do_khong_noi_kho_thieu_van_ban():
    """Giải nghĩa thất bại rẽ thẳng sang đây, nên `expanded`/`hits_shallow` đều
    rỗng và nửa đầu mặc định rơi vào `KHONG_TIM_DUOC` — một câu SAI ở nhánh này:
    không phải kho thiếu văn bản, mà là mình chưa hiểu câu hỏi nối tiếp trỏ vào
    đâu. Cùng lỗi lớp với "văn bản chi phối" ở trên: khẳng định một điều chưa
    kiểm, chỉ khác chiều.

    Vẫn là `abstain`, KHÔNG loại kết quả mới: pha này đổi LỜI của ngõ cụt, không
    đổi KHI NÀO ngõ cụt.
    """
    st = assemble({"intent": "tra_cuu", "query": "còn nó thì sao",
                   "lich_su": [{"cau_hoi": "chào", "tra_loi": "", "duong_dan": []}],
                   "cau_hoi_day_du": None, "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    ghi_chu = st["coverage_note"]
    assert st["result_type"] is ResultType.abstain
    assert "không có văn bản nào khớp" not in ghi_chu, f"nói sai vì sao dừng:\n{ghi_chu}"
    # So với chính HẰNG SỐ, không chép lại lời: sửa câu chữ ở `assemble` không
    # làm test đỏ oan — chỉ gỡ nó khỏi nhánh này mới làm.
    assert CHUA_GIAI_NGHIA_DUOC in ghi_chu, f"chưa nói ra điều thật:\n{ghi_chu}"
    assert st["traces"].get("assemble_hoi_lai") == "llm", "ngõ cụt này vẫn phải có nửa sau"


def test_luot_dau_KHONG_roi_vao_nhanh_chua_giai_nghia_duoc():
    """`cau_hoi_day_du is None` một mình KHÔNG phải tín hiệu thất bại — lượt đầu
    cũng None (nó không chạy `giai_nghia`). Phân biệt bằng `lich_su`."""
    st = assemble({"intent": "tra_cuu", "query": "thử việc bao lâu",
                   "expanded": [], "hits_shallow": [], "insufficient_evidence": True,
                   "abstain_threshold": 0.5}, DB, FakeLlm(), "m")
    assert "không có văn bản nào khớp" in st["coverage_note"], (
        "lượt đầu không tìm được gì thì câu ĐÚNG vẫn là kho không có văn bản khớp"
    )


def test_assemble_doc_prompt_tu_prompt_path_khi_duoc_truyen(tmp_path):
    """Task 4 (spec §5.2): graph truyền đường dẫn từ Settings; không truyền thì
    giữ hằng cũ — hơn 40 chỗ gọi trong test không đổi."""
    mau = tmp_path / "p.md"
    mau.write_text("MAU-RIENG {cau_hoi}\n{claims}", encoding="utf-8")

    class GhiPrompt(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            self.prompt_cuoi = messages[-1]["content"]
            return super().chat(model, messages, json_schema)

    llm = GhiPrompt()
    st = assemble(
        {
            "intent": "tra_cuu",
            "expanded": [DB[11]],
            "tier1": [_pass()],
            "tier2": [Tier2Verdict(0, True, "ok")],
            "abstain_threshold": 0.5,
        },
        DB,
        llm,
        "m",
        prompt_path=mau,
    )
    assert st["result_type"] is ResultType.answer
    assert llm.prompt_cuoi.startswith("MAU-RIENG")


DB_V2 = {
    11: {
        "id": 11,
        "document_id": "139264",
        "duong_dan": "45/2019/QH14 > Điều 26",
        "so_ky_hieu": "45/2019/QH14",
        "ten": "Bộ Luật lao động",
        "loai_van_ban": "Bộ luật",
        "link_vbpl": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=139264",
        "link_chinhphu": None,
        "link_tvpl": None,
        "noi_dung": "…85%…",
    },
    21: {
        "id": 21,
        "document_id": "152668",
        "duong_dan": "145/2020/NĐ-CP > Điều 74",
        "so_ky_hieu": "145/2020/NĐ-CP",
        "ten": "Nghị định 145",
        "loai_van_ban": "Nghị định",
        "link_vbpl": None,
        "link_chinhphu": None,
        "link_tvpl": None,
        "noi_dung": "…",
    },
}
MAU_V2 = "{mo_dau}\n===\n{van_ban}\n===\n{claims}\n===\n{cau_hoi}"


class GhiPromptV2(FakeLlm):
    def chat(self, model, messages, json_schema=None):
        self.prompt_cuoi = messages[-1]["content"]
        return super().chat(model, messages, json_schema)


def _st_hai_can_cu():
    return {
        "intent": "tra_cuu",
        "expanded": [DB_V2[11], DB_V2[21]],
        "tier1": [_pass(11), _pass(21)],
        "tier2": [Tier2Verdict(0, True, "ok"), Tier2Verdict(1, True, "ok")],
        "abstain_threshold": 0.5,
    }


def test_v2_danh_so_k_va_dung_documents_khu_trung(tmp_path):
    mau = tmp_path / "v2.md"
    mau.write_text(MAU_V2, encoding="utf-8")
    st = assemble(_st_hai_can_cu(), DB_V2, GhiPromptV2(), "m", prompt_path=mau)
    assert st["result_type"] is ResultType.answer
    assert [c["k"] for c in st["citations"]] == [1, 2]
    assert [d["doc_id"] for d in st["documents"]] == ["139264", "152668"]
    assert st["documents"][0]["links"] == {
        "vbpl": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=139264",
        "chinhphu": None,
        "tvpl": None,
    }
    assert st["documents"][0]["loai_van_ban"] == "Bộ luật"
    assert "ngay" not in json.dumps(st["documents"]), "Q2: documents không mang ngày"


def test_v2_prompt_mang_mo_dau_theo_lich_su_va_khoi_van_ban(tmp_path):
    from src.agents.nodes.assemble import MO_DAU_LUOT_DAU, MO_DAU_NOI_TIEP

    mau = tmp_path / "v2.md"
    mau.write_text(MAU_V2, encoding="utf-8")

    llm = GhiPromptV2()
    assemble(_st_hai_can_cu(), DB_V2, llm, "m", prompt_path=mau)
    assert MO_DAU_LUOT_DAU in llm.prompt_cuoi
    assert "[doc:139264] Bộ Luật lao động — 45/2019/QH14 — Bộ luật" in llm.prompt_cuoi
    assert "[1] 45/2019/QH14 > Điều 26 — Bộ Luật lao động" in llm.prompt_cuoi

    llm2 = GhiPromptV2()
    # `cau_hoi_day_du` phải đi kèm `lich_su`: thiếu nó, dòng 549 (kiểm tiền đề
    # ĐẦU VÀO — "câu hỏi nối tiếp không giải nghĩa được") rẽ thẳng sang nhánh
    # abstain/hoi_lai TRƯỚC khi tới khối dựng `{mo_dau}`, nên `llm2.prompt_cuoi`
    # sẽ là prompt của `hoi_lai`, không phải `mau`. Ở đây câu nối tiếp coi như
    # ĐÃ giải nghĩa xong để bài test đi tới đúng nhánh nó muốn canh.
    assemble(
        {**_st_hai_can_cu(), "lich_su": [{"cau_hoi": "a", "tra_loi": "b", "duong_dan": []}], "cau_hoi_day_du": "a"},
        DB_V2,
        llm2,
        "m",
        prompt_path=mau,
    )
    assert MO_DAU_NOI_TIEP in llm2.prompt_cuoi


def test_v1_giu_dinh_dang_claims_cu_nhung_van_co_k_va_documents():
    """Template v1 không có `{van_ban}` → claims dạng gạch đầu dòng như cũ, để
    A/B v1-v2 đo đúng prompt cũ. `k`/`documents` vẫn được dựng (FE dùng được
    khối liên kết dù prompt nào)."""
    llm = GhiPromptV2()
    st = assemble(_st_hai_can_cu(), DB_V2, llm, "m")
    assert "(căn cứ: 45/2019/QH14 > Điều 26" in llm.prompt_cuoi
    assert "[1] " not in llm.prompt_cuoi
    assert [c["k"] for c in st["citations"]] == [1, 2]
    assert len(st["documents"]) == 2


class LlmTraLoi(FakeLlm):
    """Hành văn trả đúng chuỗi `answer` cho sẵn — để bẫy từng loại thẻ sai."""

    def __init__(self, answer: str) -> None:
        super().__init__()
        self.answer = answer

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        self.schema_da_goi.append(json_schema)
        if json_schema is HOI_LAI_SCHEMA:
            return json.dumps({"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}]}), Usage(1, 1, 0.0)
        return json.dumps({"answer": self.answer}), Usage(1, 1, 0.0)


def test_the_hop_le_tra_answer_va_trace_rong():
    st = assemble(_st_hai_can_cu(), DB_V2,
                  LlmTraLoi("Theo [Bộ luật Lao động 2019](doc:139264), bạn được 85% [Điều 26](cite:1)."),
                  "m")
    assert st["result_type"] is ResultType.answer
    assert st["traces"]["assemble_the_loi"] == []


@pytest.mark.parametrize("answer, loi", [
    ("Xem [Nghị định 126](doc:999999).", ["doc:999999"]),                 # doc lạ
    ("Bạn được 85% [Điều 26](cite:7).", ["cite:7"]),                       # K ngoài tập
    ("Bạn được 85% [Điều 26](cite:x).", ["cite:x"]),                       # K không phải số
    ("Bạn được 85% [Điều 26](cite:²).", ["cite:²"]),                       # ký tự số Unicode không phải Nd — isdigit() nhận, int() nổ
    ("Bạn được 85% [Điều 99](cite:1).", ["cite:1≠['26']"]),               # Điều lệch căn cứ
    ("Xem thêm tại vbpl.vn nhé.", ["url"]),                                # URL trần
    ("Xem https://thuvienphapluat.vn/x [Điều 26](cite:1).", ["url"]),      # URL đầy đủ
])
def test_the_hoac_url_sai_ha_xuong_abstain_va_ghi_trace(answer, loi):
    st = assemble(_st_hai_can_cu(), DB_V2, LlmTraLoi(answer), "m")
    assert st["result_type"] is ResultType.abstain, answer
    assert st["traces"]["assemble_the_loi"] == loi


def test_ngoac_vuong_khong_phai_the_thi_khong_bi_bat():
    st = assemble(_st_hai_can_cu(), DB_V2, LlmTraLoi("Nguyên văn [sic] nói 85% [Điều 26](cite:1)."), "m")
    assert st["result_type"] is ResultType.answer


def test_so_ky_hieu_va_so_tien_khong_bi_coi_la_url():
    from src.agents.nodes.assemble import _RE_URL
    for s in ("45/2019/QH14", "10/2020/TT-BLĐTBXH", "4.420.000 đồng/tháng", "Điều 5. Phạm vi"):
        assert not _RE_URL.search(s), s


def test_soan_thao_co_goi_y_dung_ten_tu_checklist_va_loc_thay_the():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("nhánh soan_thao không gọi LLM")

    st = assemble(
        {
            "intent": "soan_thao",
            "query": "soạn cho tôi hợp đồng nghỉ việc",
            "soan_thao_goi_y": {
                "loai": "don_xin_nghi_viec",
                "ly_do": "bạn là người lao động muốn nghỉ",
                "thay_the": ["thoa_thuan_cham_dut_hdld", "loai_khong_co", "don_xin_nghi_viec"],
            },
        },
        {},
        Never(),
        "m",
    )
    assert st["result_type"] is ResultType.huong_dan_soan_thao
    gy = st["soan_thao_goi_y"]
    assert gy["loai"] == "don_xin_nghi_viec" and gy["ten"] == "đơn xin nghỉ việc" and gy["ho_tro"] is True
    assert [t["loai"] for t in gy["thay_the"]] == ["thoa_thuan_cham_dut_hdld"]
    assert st["answer"].startswith("Tôi hiểu bạn cần đơn xin nghỉ việc: bạn là người lao động muốn nghỉ")
    assert "khung bên cạnh" in st["answer"]
    assert st["traces"]["assemble_token_in"] == 0


def test_soan_thao_loai_la_thanh_khong_ho_tro_va_neu_gan_nhat():
    st = assemble(
        {
            "intent": "soan_thao",
            "query": "x",
            "soan_thao_goi_y": {"loai": "loai_khong_co", "ly_do": "", "thay_the": ["don_xin_nghi_viec"]},
        },
        {},
        FakeLlm(),
        "m",
    )
    gy = st["soan_thao_goi_y"]
    assert gy["loai"] is None and gy["ho_tro"] is False
    assert st["answer"].startswith("Kho mẫu của tôi chưa có loại văn bản này.")
    assert "đơn xin nghỉ việc" in st["answer"]


def test_soan_thao_loai_la_va_khong_co_thay_the_thi_moi_mo_ta_ro_hon():
    from src.agents.nodes.assemble import GAN_NHAT_KHONG

    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("nhánh soan_thao không gọi LLM")

    st = assemble(
        {
            "intent": "soan_thao",
            "query": "x",
            "soan_thao_goi_y": {"loai": "loai_khong_co", "ly_do": "y", "thay_the": []},
        },
        {},
        Never(),
        "m",
    )
    assert st["result_type"] is ResultType.huong_dan_soan_thao
    gy = st["soan_thao_goi_y"]
    assert gy["loai"] is None and gy["ho_tro"] is False and gy["thay_the"] == []
    assert GAN_NHAT_KHONG in st["answer"]


def test_soan_thao_ly_do_co_url_hay_the_bi_loc_ve_mac_dinh():
    from src.agents.nodes.assemble import LY_DO_MAC_DINH

    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("nhánh soan_thao không gọi LLM")

    st = assemble(
        {
            "intent": "soan_thao",
            "query": "x",
            "soan_thao_goi_y": {
                "loai": "don_xin_nghi_viec",
                "ly_do": "xem [Điều 1](cite:1) tại https://x.vn",
                "thay_the": [],
            },
        },
        {},
        Never(),
        "m",
    )
    assert LY_DO_MAC_DINH in st["answer"]
    assert "https://" not in st["answer"] and "cite:" not in st["answer"]


def test_soan_thao_khong_goi_y_giu_huong_dan_cu():
    from src.agents.nodes.assemble import HUONG_DAN_SOAN_THAO

    st = assemble({"intent": "soan_thao", "query": "x"}, {}, FakeLlm(), "m")
    assert st["answer"] == HUONG_DAN_SOAN_THAO and st["soan_thao_goi_y"] is None
    assert "Chọn loại văn bản" in HUONG_DAN_SOAN_THAO
