import json
from datetime import date

import pytest

from src.agents.nodes.assemble import (
    ANSWER_SCHEMA,
    CHUA_GIAI_NGHIA_DUOC,
    GIAI_THICH_SCHEMA,
    KHONG_TIM_DUOC,
    ResultType,
    assemble,
)
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.hoi_lai import HOI_LAI_SCHEMA
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity, VanBanNeu
from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage

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
        if json_schema is GIAI_THICH_SCHEMA:
            # Phase 14 R6 — vai THỨ BA: giải thích chung, không trích dẫn.
            return json.dumps({"giai_thich": self.giai_thich}), Usage(2, 3, 0.0)
        return json.dumps({"answer": "Ít nhất 85% mức lương."}), Usage(1, 1, 0.0)

    giai_thich = "Thử việc là giai đoạn hai bên làm thử trước khi ký hợp đồng chính thức."

    @property
    def so_lan_hanh_van(self) -> int:
        return sum(1 for s in self.schema_da_goi if s is ANSWER_SCHEMA)

    @property
    def so_lan_hoi_lai(self) -> int:
        return sum(1 for s in self.schema_da_goi if s is HOI_LAI_SCHEMA)

    @property
    def so_lan_giai_thich(self) -> int:
        return sum(1 for s in self.schema_da_goi if s is GIAI_THICH_SCHEMA)


def _pass(pid=11):
    return Tier1Result(Claim("Ít nhất 85%.", pid, "85%"), True, R.ok, EFF)


def test_ngoai_pham_vi_tra_out_of_scope_va_KHONG_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không gọi LLM khi ngoài phạm vi")

    st = assemble({"intent": "ngoai_pham_vi"}, DB, Never(), "m")
    assert st["result_type"] is ResultType.out_of_scope and st["answer"] is None


def test_ngoai_pham_vi_noi_dung_pham_vi_moi():
    """ADR 2026-09-30 mục 6: phạm vi là pháp luật Việt Nam, sâu nhất ở lao động —
    câu từ chối không còn nói "6 Bộ luật" hay "chỉ soạn thảo lao động", và không
    nhắc "kho" (mục 4)."""
    st = assemble({"intent": "ngoai_pham_vi"}, DB, FakeLlm(), "m")
    note = st["coverage_note"]
    assert "pháp luật Việt Nam" in note and "lao động" in note
    assert "6 Bộ luật" not in note and "chỉ soạn thảo" not in note and "kho" not in note


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


def test_canh_bao_neu_dich_danh_van_ban_sua_KHONG_ly_do_ca_that_BLLD_45_2019():
    # Yêu cầu #1: cảnh báo nêu ĐÍCH DANH văn bản sửa, không một câu mẫu chung
    # chung. Quyết định 2026-09-28 mục 10 thay ruling 2026-08-31 ("`ly_do`
    # NGUYÊN VĂN"): người đọc thấy câu thường dựng từ `Effectivity.van_ban`,
    # không bao giờ dòng chẩn đoán ("CSDL quốc gia…", ngày ISO). Effectivity
    # dưới đây là hình dạng THẬT `danh_gia` trả cho 45/2019/QH14 bị 19/2023/QH15
    # sửa đổi, bổ sung (Mức 2c).
    ly_do_that = (
        "bị 19/2023/QH15 sửa đổi, bổ sung từ 2024-07-01; CSDL quốc gia không công bố "
        "dữ liệu cấp điều khoản nên không xác định được điều này còn hiệu lực hay không"
    )
    blld = Effectivity(V.mot_phan_khong_xac_dinh, "thap", ly_do_that, van_ban=(VanBanNeu("1", "19/2023/QH15"),))
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, blld)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["warnings"] == [
        "45/2019/QH14 còn hiệu lực một phần. Đã được sửa đổi, bổ sung bởi 19/2023/QH15."
    ], st["warnings"]
    assert not any(x in w for w in st["warnings"] for x in ("CSDL", "2024-07-01", "xác định")), st["warnings"]


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
    # Phase 14 (R6): `answer` có thể là lời GIẢI THÍCH CHUNG (vai riêng, không
    # trích dẫn) — cái ruling này cấm là dựng câu trả lời TỪ CLAIM chưa qua
    # tầng 2: không citation nào, và vai hành văn không được gọi.
    assert st["citations"] == [] and llm.so_lan_hanh_van == 0
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
    assert [{k: n[k] for k in ("doc_id", "so_ky_hieu", "bo_luat")} for n in st["nguon"]] == [
        {"doc_id": "84265", "so_ky_hieu": "84/2015/QH13", "bo_luat": "Luật An toàn, vệ sinh lao động"}
    ], "gộp theo doc_id — hai Điều cùng một văn bản là MỘT nguồn, không phải hai"


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
                      "từ 2026-07-01 (nguồn: congbao.chinhphu.vn — 18/VBHN-VPQH)",
                      van_ban=(VanBanNeu(None, "113/2025/QH15"),))
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, eff)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["warnings"], "điều khoản đã bị sửa đổi phải sinh cảnh báo"
    (w,) = st["warnings"]
    # Nêu đích danh văn bản sửa (Mức 4 sinh ra để cung cấp đúng điều đó) bằng lời
    # cho người đọc — quyết định 2026-09-28 mục 10: không ngày ISO, không nguồn thô.
    assert "113/2025/QH15" in w and "trước khi sửa đổi" in w, w
    assert "2026-07-01" not in w and "VBHN" not in w, w


# ══ Bản trước sửa đổi và bản hiện hành (chủ dự án chốt 2026-09-30) ══════════
# "Chỉ nêu bản hiện hành, đủ danh sách" — trace c8a98c3d: 64/2025/QH15 Điều 4 bị
# 87/2025/QH15 Điều 1 khoản 1 thay trọn, và câu trả lời liệt kê cả "cấp huyện" đã bỏ.

DB_HIEN_HANH = {
    11: {
        "id": 11,
        "document_id": "175440",
        "duong_dan": "64/2025/QH15 > Điều 4 > Khoản 13",
        "so_ky_hieu": "64/2025/QH15",
        "ten": "Luật Ban hành văn bản quy phạm pháp luật",
        "noi_dung": "13. Nghị quyết của Hội đồng nhân dân huyện (sau đây gọi chung là cấp huyện).",
    },
    12: {
        "id": 12,
        "document_id": "178717",
        "duong_dan": "87/2025/QH15 > Điều 1 > Khoản 1",
        "so_ky_hieu": "87/2025/QH15",
        "ten": "Luật sửa đổi Luật Ban hành văn bản quy phạm pháp luật",
        "noi_dung": "1. Sửa đổi, bổ sung Điều 4 như sau: “Điều 4. … 14. Nghị quyết của Hội đồng "
        "nhân dân xã (sau đây gọi chung là cấp xã).”.",
    },
}
EFF_SUA = Effectivity(
    V.bi_sua_doi,
    "cao",
    "Điều 4 bị sửa bởi khoản 1 Điều 1 của 87/2025/QH15",
    van_ban=(VanBanNeu(None, "87/2025/QH15"),),
    sua_boi=("87/2025/QH15 > Điều 1 > Khoản 1",),
)
T1_CU = Tier1Result(Claim("Nghị quyết của HĐND cấp huyện.", 11, "cấp huyện"), True, R.ok, EFF_SUA)
T1_MOI = Tier1Result(Claim("Nghị quyết của HĐND cấp xã.", 12, "cấp xã"), True, R.ok, EFF)


def _tra_sua(t1: list, db: dict = DB_HIEN_HANH) -> tuple[dict, str]:
    """`(kết quả, lời nhắc hành văn)` — lời nhắc là thứ duy nhất nói claim nào vào prose."""
    class GhiPrompt(FakeLlm):
        prompt = ""

        def chat(self, model, messages, json_schema=None):
            if json_schema is ANSWER_SCHEMA:
                self.prompt = messages[-1]["content"]
            return super().chat(model, messages, json_schema)

    llm = GhiPrompt()
    st = assemble(
        {
            "intent": "tra_cuu",
            "query": "hiện tại pháp luật việt nam chia thành những gì",
            "expanded": list(db.values()),
            "tier1": t1,
            "tier2": [Tier2Verdict(i, True, "ok") for i in range(len(t1))],
            "abstain_threshold": 0.5,
        },
        db,
        llm,
        "m",
    )
    return st, llm.prompt


def test_bi_sua_doi_khong_co_ban_hien_hanh_thi_van_vao_prose_kem_canh_bao():
    """Điều khoản đi sửa KHÔNG có trong căn cứ: điều khoản bị sửa vẫn CÓ THẬT, nguyên văn
    vẫn đúng nguồn gốc, nên nó vào prose kèm cảnh báo — nói nó còn hơn im lặng. Chỉ văn
    bản CHẾT HẲN (`bi_thay_the`/`het_hieu_luc`) mới bị loại vô điều kiện."""
    st, prompt = _tra_sua([T1_CU])
    assert st["result_type"] is ResultType.answer
    (c,) = st["citations"]
    assert c["k"] == 1 and "cấp huyện" in prompt
    assert st["warnings"] and c["canh_bao"]
    assert st["traces"]["assemble_ban_cu_khoi_prose"] == []


def test_bi_sua_doi_co_ban_hien_hanh_trong_can_cu_thi_chi_ban_hien_hanh_vao_prose():
    """Điều khoản đi sửa CÓ trong căn cứ dùng cho prose: bản trước sửa đổi không được viết
    thành câu — nó ở lại nguồn (`k=None`) với nhãn "đã sửa đổi", như nguồn lạc đề."""
    st, prompt = _tra_sua([T1_CU, T1_MOI])
    assert st["result_type"] is ResultType.answer
    cu, moi = st["citations"]
    assert "cấp huyện" not in prompt and "cấp xã" in prompt
    assert moi["k"] == 1
    assert cu["k"] is None and cu["hieu_luc"] == "bi_sua_doi" and cu["canh_bao"], "bản cũ vẫn ở nguồn, kèm nhãn"
    assert st["traces"]["assemble_ban_cu_khoi_prose"] == ["64/2025/QH15 > Điều 4 > Khoản 13"]


def test_khoan_khac_cua_luat_sua_khong_thay_duoc_ban_truoc_sua_doi():
    """Khoản 13 bắt đầu bằng đúng chuỗi "Khoản 1" nhưng là một điều khoản đi sửa khác."""
    db = {**DB_HIEN_HANH, 12: {**DB_HIEN_HANH[12], "duong_dan": "87/2025/QH15 > Điều 1 > Khoản 13"}}
    st, prompt = _tra_sua([T1_CU, T1_MOI], db)
    assert "cấp huyện" in prompt and st["citations"][0]["k"] == 1


def test_hoi_ve_kho_xin_bang_dung_chuoi_da_tinh_san_va_KHONG_goi_LLM():
    """Lượt xin BẢNG về kho: hai bảng do `graph_tra_cuu.n_assemble` tính bằng SQL
    (nơi có `engine`), câu dẫn tất định — 0 token, không con số nào do model sinh.
    Mọi lượt `hoi_ve_kho` khác do model viết từ bảng dữ kiện (quyết định
    2026-09-30 mục 1, `test_tra_loi_meta.py`)."""

    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("lượt xin bảng phải là nhánh 0 token")

    bang = [{"tieu_de": "Phân theo loại văn bản", "cot": ["Loại"], "hang": [["Luật"]]}]
    st = assemble(
        {"intent": "hoi_ve_kho", "tra_loi_kho": "Tôi dựng hai bảng…", "tra_loi_kho_bang": bang}, DB, Never(), "m"
    )
    assert st["result_type"] is ResultType.hoi_ve_kho
    assert st["answer"] == "Tôi dựng hai bảng…" and st["bang"] == bang
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


def test_abstain_khong_con_liet_ke_van_ban_da_khop_khi_chua_dung_noi_luan_diem():
    """Task 14: `_da_biet` (nửa đầu MẶC ĐỊNH cũ — liệt kê tên văn bản khớp TỪ
    NGỮ trước khi hỏi lại) đã bị gỡ, đúng hai điều chủ đề tài phàn nàn: trích
    dẫn sai thứ, và không đoán ra khách cần gì. Nửa đầu mặc định nay là
    `KHONG_TIM_DUOC` — không còn nêu tên văn bản nào, kể cả văn bản đã khớp ở
    tầng truy hồi (`expanded`)."""
    st = assemble({"intent": "tra_cuu", "query": "liệt kê bảng cho tôi",
                   "expanded": [DB[11]], "tier1": [], "tier2": [],
                   "abstain_threshold": 0.5}, DB, FakeLlm(), "m")
    ghi_chu = st["coverage_note"]
    assert st["result_type"] is ResultType.abstain
    assert ghi_chu.startswith(KHONG_TIM_DUOC)
    assert "45/2019/QH14" not in ghi_chu, "Task 14: abstain không còn liệt kê văn bản đã khớp"


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
    cũng None (nó không chạy `giai_nghia`). Phân biệt bằng `lich_su`.

    Task 14 đổi câu chữ của `KHONG_TIM_DUOC` — so với chính HẰNG SỐ, không chép
    lại lời: sửa câu chữ ở `assemble` không làm test đỏ oan."""
    st = assemble({"intent": "tra_cuu", "query": "thử việc bao lâu",
                   "expanded": [], "hits_shallow": [], "insufficient_evidence": True,
                   "abstain_threshold": 0.5}, DB, FakeLlm(), "m")
    assert KHONG_TIM_DUOC in st["coverage_note"], (
        "lượt đầu không tìm được gì thì câu ĐÚNG vẫn là 'chưa tìm được', không phải câu của nhánh chưa giải nghĩa được"
    )
    assert CHUA_GIAI_NGHIA_DUOC not in st["coverage_note"]


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
    # Q2 ("documents không mang ngày") đã được quyết định 2026-09-28 thay thế:
    # ngày là dữ kiện của văn bản; NULL đi nguyên, không bịa. Link mẫu cũ
    # `vbpq-toanvan.aspx` (về trang chủ) không thành `lien_ket`.
    d0 = st["documents"][0]
    assert d0["ngay_ban_hanh"] is None and d0["lien_ket"] is None
    assert d0["cach_trich"] == "Bộ luật Lao động số 45/2019/QH14"
    json.dumps(st["documents"])  # vào cache câu trả lời được


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


def test_goi_y_dung_ten_tu_checklist_va_loc_thay_the():
    """`soan_thao_goi_y` (0 token) — tên đọc từ checklist thật, `thay_the` chỉ
    giữ mẫu thật và khác `loai`. Phase 14: hàm này chỉ còn dựng lời MỜI biểu
    mẫu đính kèm bản thảo/câu trả lời, không còn một lời đáp riêng."""
    from src.agents.nodes.assemble import _goi_y_soan_thao

    gy = _goi_y_soan_thao({
        "loai": "don_xin_nghi_viec",
        "ly_do": "bạn là người lao động muốn nghỉ",
        "thay_the": ["thoa_thuan_cham_dut_hdld", "loai_khong_co", "don_xin_nghi_viec"],
    })
    assert gy["loai"] == "don_xin_nghi_viec" and gy["ten"] == "đơn xin nghỉ việc" and gy["ho_tro"] is True
    assert gy["ly_do"] == "bạn là người lao động muốn nghỉ"
    assert [t["loai"] for t in gy["thay_the"]] == ["thoa_thuan_cham_dut_hdld"]


def test_goi_y_loai_la_thanh_khong_ho_tro_va_giu_thay_the_that():
    """Phase 14: `_goi_y_soan_thao` chỉ còn dựng `soan_thao_goi_y` (0 token) —
    lời đáp "Kho mẫu của tôi chưa có loại văn bản này" đã bị gỡ (R1). Loại lạ
    → `ho_tro=False`, `thay_the` chỉ giữ mẫu thật."""
    from src.agents.nodes.assemble import _goi_y_soan_thao

    gy = _goi_y_soan_thao({"loai": "loai_khong_co", "ly_do": "", "thay_the": ["don_xin_nghi_viec", "x"]})
    assert gy["loai"] is None and gy["ho_tro"] is False
    assert [t["loai"] for t in gy["thay_the"]] == ["don_xin_nghi_viec"]
    assert _goi_y_soan_thao(None) is None


def test_goi_y_ly_do_co_url_hay_the_bi_loc_rong():
    from src.agents.nodes.assemble import _goi_y_soan_thao

    gy = _goi_y_soan_thao({"loai": "don_xin_nghi_viec", "ly_do": "xem [Điều 1](cite:1) tại https://x.vn", "thay_the": []})
    assert gy["ly_do"] == "" and gy["ho_tro"] is True


def test_soan_thao_khong_co_checklist_mo_khong_con_huong_dan_sang_bieu_mau():
    """R1: không còn `huong_dan_soan_thao` cho một lượt `soan_thao` không có
    checklist mở — lượt đó đã đi `hieu_tai_lieu` và `assemble` chỉ đọc kết quả;
    gọi trực tiếp không có gì để đọc thì hỏi lại (`soan_thao_hoi`), không chỉ
    sang "Chọn loại văn bản"."""
    st = assemble({"intent": "soan_thao", "query": "x", "user_sub": "u"}, {}, FakeLlm(), "m")
    assert st["result_type"] is ResultType.soan_thao_hoi
    assert "Chọn loại văn bản" not in st["answer"] and "kho" not in st["answer"].lower()
    assert st["traces"]["assemble_token_in"] == 0


def test_ten_loai_roi_ve_chinh_ma_loai_khi_khong_tra_duoc_checklist():
    """Cùng lý do `route._dang_soan`: một `loai` không tra được checklist (YAML bị
    gỡ hay đổi tên) phải suy biến thành chính mã loại, không phải một ngoại lệ
    giữa lúc hành văn câu trả lời cuối."""
    from src.agents.nodes.assemble import _ten_loai

    assert _ten_loai("khong_co_that") == "khong_co_that"


# ══ GĐ3/GĐ4 (cai_thien.md §6) — lạc đề, vai trò, mức chắc, đuôi từ khung ════
# Ba thứ dưới đây đều GÁC bằng dữ liệu: `relevant`/`overstated` chỉ khác mặc định
# khi tầng 2 chạy prompt v2; vai trò chỉ có khi generate chạy prompt v3; khung yêu
# cầu chỉ có khi rewrite chạy prompt v3. Không cái nào là mặc định hôm nay.

from pathlib import Path  # noqa: E402

from src.agents.nodes.assemble import LAC_DE, TOI_DA_CLAIM_PROSE  # noqa: E402

V3_PROMPT = Path("prompts/assemble.v3.md")
V6_PROMPT = Path("prompts/assemble.v6.md")


class GhiPrompt(FakeLlm):
    """`FakeLlm` + giữ lại lời nhắc HÀNH VĂN: định dạng khối căn cứ là hợp đồng
    giữa `assemble` và prompt, và cách duy nhất để khoá nó là đọc chuỗi đã gửi."""

    def __init__(self) -> None:
        super().__init__()
        self.prompt = ""

    def chat(self, model, messages, json_schema=None):
        if json_schema is ANSWER_SCHEMA:
            self.prompt = messages[-1]["content"]
        return super().chat(model, messages, json_schema)


def _claim(text="Ít nhất 85%.", vai_tro=None, pid=11):
    return Tier1Result(Claim(text, pid, "85%", None, vai_tro, True), True, R.ok, EFF)


def _st(*tier1, tier2=None, query="lương thử việc bao nhiêu", **kw):
    return {"intent": "tra_cuu", "query": query, "expanded": [DB[11]], "tier1": list(tier1),
            "tier2": tier2 if tier2 is not None else [Tier2Verdict(i, True, "ok") for i in range(len(tier1))],
            "abstain_threshold": 0.5, **kw}


def test_claim_lac_de_bi_loai_khoi_van_xuoi_nhung_o_lai_citations():
    """Tầng 2 (v2) nói điều luật CHỐNG ĐỠ khẳng định, nhưng khẳng định không trả
    lời điều được hỏi. Đây là bộ lọc VĂN XUÔI, không phải phép kiểm thứ ba: vết
    kiểm toán phải giữ nguyên trích dẫn, chỉ không cấp số `k` cho nó."""
    llm = GhiPrompt()
    st = assemble(_st(_claim("Đúng mục tiêu."), _claim("Cùng chủ đề thôi."),
                      tier2=[Tier2Verdict(0, True, "ok"),
                             Tier2Verdict(1, True, "ok", relevant=False)]),
                  DB, llm, "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.answer
    assert len(st["citations"]) == 2
    assert [c["k"] for c in st["citations"]] == [1, None]
    assert st["traces"]["assemble_lac_de"] == [1]
    assert "Đúng mục tiêu." in llm.prompt and "Cùng chủ đề thôi." not in llm.prompt


def test_claim_overstated_cung_bi_loai_khoi_van_xuoi():
    llm = GhiPrompt()
    st = assemble(_st(_claim("Đúng mục tiêu."), _claim("Nói rộng hơn luật."),
                      tier2=[Tier2Verdict(0, True, "ok"),
                             Tier2Verdict(1, True, "ok", overstated=True)]),
                  DB, llm, "m", prompt_path=V3_PROMPT)
    assert st["traces"]["assemble_lac_de"] == [1]
    assert "Nói rộng hơn luật." not in llm.prompt


def test_moi_claim_deu_lac_de_thi_abstain_va_KHONG_goi_LLM_hanh_van():
    """Lý do phải nói ĐÚNG: nguồn ở đây còn hiệu lực, cái thiếu là nó không trả
    lời câu được hỏi — câu "đều đã bị thay thế" của nhánh hiệu lực là nói sai."""
    llm = GhiPrompt()
    st = assemble(_st(_claim("Cùng chủ đề thôi."),
                      tier2=[Tier2Verdict(0, True, "ok", relevant=False)]),
                  DB, llm, "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.abstain
    assert LAC_DE in st["coverage_note"]
    assert "đã bị thay thế" not in st["coverage_note"]
    assert llm.so_lan_hanh_van == 0, "không dựng văn xuôi khi không còn căn cứ đúng mục tiêu"
    assert st["traces"]["assemble_lac_de"] == [0]


def test_tier2_v1_khong_loc_gi_duong_mac_dinh_giu_nguyen():
    """MẶC ĐỊNH hôm nay: verdict dựng bằng ba tham số vị trí (`relevant=True`,
    `overstated=False`) — bộ lọc mới phải nằm im hoàn toàn."""
    llm = GhiPrompt()
    st = assemble(_st(_claim("a"), _claim("b")), DB, llm, "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.answer
    assert [c["k"] for c in st["citations"]] == [1, 2]
    assert st["traces"]["assemble_lac_de"] == []


def test_citation_mang_vai_tro_va_None_khi_prompt_sinh_v2():
    st = assemble(_st(_claim("a", "ket_luan"), _claim("b")), DB, GhiPrompt(), "m", prompt_path=V3_PROMPT)
    assert [c["vai_tro"] for c in st["citations"]] == ["ket_luan", None]


def test_xep_can_cu_theo_vai_tro_va_khu_trung_text():
    """Kết luận trước, rồi điều kiện/ngoại lệ; hai claim cùng một câu (chỉ khác
    dấu câu và hoa thường) là MỘT ý lặp — quy tắc 6 của §6 GĐ3."""
    llm = GhiPrompt()
    st = assemble(_st(_claim("Ngoại lệ đảo kết luận.", "ngoai_le"),
                      _claim("Điều kiện phải thoả.", "dieu_kien"),
                      _claim("điều kiện phải thoả", "dieu_kien"),
                      _claim("Kết luận thẳng.", "ket_luan")),
                  DB, llm, "m", prompt_path=V3_PROMPT)
    gui = llm.prompt
    assert gui.index("Kết luận thẳng.") < gui.index("Điều kiện phải thoả.") < gui.index("Ngoại lệ đảo kết luận.")
    assert gui.count("iều kiện phải thoả") == 1, "bản trùng sau chuẩn hoá phải bị bỏ"
    # Bản bị khử trùng vẫn ở lại vết kiểm toán, không được cấp số.
    assert len(st["citations"]) == 4
    assert sorted(c["k"] for c in st["citations"] if c["k"]) == [1, 2, 3]


def test_che_tai_bi_bo_khi_nguoi_hoi_khong_hoi_hau_qua():
    llm = GhiPrompt()
    assemble(_st(_claim("Kết luận thẳng.", "ket_luan"), _claim("Điều kiện.", "dieu_kien"),
                 _claim("Phạt tiền 3 triệu.", "che_tai"), query="công ty có được trừ lương không"),
             DB, llm, "m", prompt_path=V3_PROMPT)
    assert "Phạt tiền 3 triệu." not in llm.prompt


def test_che_tai_duoc_giu_khi_cau_hoi_hoi_hau_qua():
    llm = GhiPrompt()
    assemble(_st(_claim("Kết luận thẳng.", "ket_luan"), _claim("Điều kiện.", "dieu_kien"),
                 _claim("Phạt tiền 3 triệu.", "che_tai"),
                 query="công ty vi phạm thì bị xử lý thế nào"),
             DB, llm, "m", prompt_path=V3_PROMPT)
    assert "Phạt tiền 3 triệu." in llm.prompt


def test_che_tai_duoc_giu_khi_bo_di_thi_con_duoi_hai_can_cu():
    """Thà kém gọn còn hơn dựng một câu trả lời trên một căn cứ duy nhất."""
    llm = GhiPrompt()
    assemble(_st(_claim("Kết luận thẳng.", "ket_luan"), _claim("Phạt tiền 3 triệu.", "che_tai"),
                 query="công ty có được trừ lương không"),
             DB, llm, "m", prompt_path=V3_PROMPT)
    assert "Phạt tiền 3 triệu." in llm.prompt


def test_tran_sau_can_cu_vao_loi_nhac():
    llm = GhiPrompt()
    st = assemble(_st(*[_claim(f"Ý số {i}.", "dieu_kien") for i in range(9)]),
                  DB, llm, "m", prompt_path=V3_PROMPT)
    assert llm.prompt.count("Ý số ") == TOI_DA_CLAIM_PROSE
    assert len(st["citations"]) == 9, "citations giữ đủ vết kiểm toán"


def test_khoi_can_cu_giu_NGUYEN_dinh_dang_cu_khi_khong_co_vai_tro():
    """Bất biến của baseline: prompt sinh v2 (mọi `vai_tro` là None) phải cho ra
    ĐÚNG chuỗi cũ, kể cả khi hành văn chạy v6."""
    llm = GhiPrompt()
    assemble(_st(_claim("Ít nhất 85%.")), DB, llm, "m", prompt_path=V6_PROMPT)
    assert "[1] 45/2019/QH14 > Điều 26 — Bộ Luật lao động\n    Ít nhất 85%." in llm.prompt
    # "(kết luận)" có sẵn trong CHÍNH văn bản v6 (phần dặn cách chọn căn cứ), nên
    # phải soi đúng dòng căn cứ, không soi cả lời nhắc.
    assert "[1] (" not in llm.prompt


def test_khoi_can_cu_v6_in_vai_tro_doc_duoc():
    llm = GhiPrompt()
    assemble(_st(_claim("Ít nhất 85%.", "ket_luan")), DB, llm, "m", prompt_path=V6_PROMPT)
    assert "[1] (kết luận) 45/2019/QH14 > Điều 26 — Bộ Luật lao động\n    Ít nhất 85%." in llm.prompt


def test_prompt_v3_khong_in_vai_tro_du_claim_co_vai_tro():
    """v3 không có `{muc_chac}` nên nó không biết nhãn vai trò nghĩa là gì —
    thêm nhãn vào một prompt đang được đo là đổi thứ đang đo."""
    llm = GhiPrompt()
    assemble(_st(_claim("Ít nhất 85%.", "ket_luan")), DB, llm, "m", prompt_path=V3_PROMPT)
    assert "(kết luận)" not in llm.prompt
    assert "[1] 45/2019/QH14 > Điều 26 — Bộ Luật lao động\n    Ít nhất 85%." in llm.prompt


# ── GĐ4: đuôi hỏi thêm lấy từ khung yêu cầu ─────────────────────────────────


def _khung(*du_kien):
    return {"muc_tieu": "biết có bị chấm dứt đúng luật không", "cau_hoi_phap_ly": "c",
            "du_kien_quyet_dinh_con_thieu": list(du_kien)}


def test_duoi_lay_tu_khung_va_KHONG_hoi_them_chieu_ho_so():
    from src.agents.nodes.hoi_lai import CHIEU

    st = assemble(_st(_claim("a"), khung_yeu_cau=_khung(
        {"ma": "ly_do_cham_dut", "cau": "Công ty nêu lý do gì khi chấm dứt?", "lam_doi_ket_luan": True}),
        traces={"suy_dien_chu_the": "người lao động"}),
        DB, GhiPrompt(), "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.answer
    assert "Công ty nêu lý do gì khi chấm dứt?" in st["coverage_note"]
    assert CHIEU["chu_the"] not in st["coverage_note"], "nhiều nhất MỘT đuôi"
    assert st["coverage_note"].count("\n- ") == 1


def test_du_kien_da_co_trong_ho_so_thi_khong_hoi_lai():
    st = assemble(_st(_claim("a"), khung_yeu_cau=_khung(
        {"ma": "ly_do_cham_dut", "cau": "Công ty nêu lý do gì khi chấm dứt?", "lam_doi_ket_luan": True}),
        ho_so={"ly_do_cham_dut": {"gia_tri": "thu hẹp sản xuất", "nguon": "nguoi_noi"}}),
        DB, GhiPrompt(), "m", prompt_path=V3_PROMPT)
    assert st["coverage_note"] is None


def test_hoi_dung_du_kien_con_thieu_khi_loai_hop_dong_da_biet():
    st = assemble(_st(_claim("a"), khung_yeu_cau=_khung(
        {"ma": "loai_hop_dong", "cau": "Hợp đồng của bạn thuộc loại nào?", "lam_doi_ket_luan": True},
        {"ma": "ly_do_cham_dut", "cau": "Công ty nêu lý do gì khi chấm dứt?", "lam_doi_ket_luan": True}),
        ho_so={"loai_hop_dong": {"gia_tri": "không xác định thời hạn", "nguon": "nguoi_noi"}}),
        DB, GhiPrompt(), "m", prompt_path=V3_PROMPT)
    assert "lý do gì" in st["coverage_note"] and "loại nào" not in st["coverage_note"]


def test_cau_du_du_kien_khong_co_cau_hoi_cuoi():
    """`cai_thien.md` §6 GĐ4, ca test bắt buộc: không khung, không giả định mới
    ⇒ câu trả lời kết thúc, không đính một câu hỏi chung nào."""
    st = assemble(_st(_claim("a"), khung_yeu_cau=_khung()), DB, GhiPrompt(), "m", prompt_path=V3_PROMPT)
    assert st["coverage_note"] is None


def test_ngo_cut_dung_cau_hoi_tu_khung_va_KHONG_goi_LLM_hoi_lai():
    """0 token cho nửa sau của ngõ cụt khi khung đã hỏi được — và câu hỏi bám
    vào vụ việc chứ không phải sáu chiều chung."""
    llm = GhiPrompt()
    st = assemble(_st(tier2=[], khung_yeu_cau=_khung(
        {"ma": "ly_do_cham_dut", "cau": "Công ty nêu lý do gì khi chấm dứt?", "lam_doi_ket_luan": True},
        {"ma": "hanh_vi", "cau": "Công ty nói bạn đã làm gì?", "lam_doi_ket_luan": True},
        {"ma": "giay_to", "cau": "Bạn giữ giấy tờ nào?", "lam_doi_ket_luan": False})),
        DB, llm, "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.abstain
    assert llm.so_lan_hoi_lai == 0 and llm.so_lan_hanh_van == 0
    assert st["traces"]["assemble_hoi_lai"] == "khung"
    assert st["coverage_note"].count("\n- ") == 2, "trần hai câu"
    assert "giấy tờ" not in st["coverage_note"]


def test_ngo_cut_khong_co_khung_van_goi_hoi_lai_nhu_cu():
    llm = GhiPrompt()
    st = assemble(_st(tier2=[]), DB, llm, "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.abstain
    assert llm.so_lan_hoi_lai == 1 and st["traces"]["assemble_hoi_lai"] == "llm"


def test_CitationOut_nhan_vai_tro_va_van_optional():
    """Trường THÊM ở biên HTTP: payload cache cũ (không có khoá) vẫn hợp lệ."""
    from src.models.schemas import CitationOut

    tho = {"provision_id": 11, "khop_tai_id": 11, "doc_id": "1", "duong_dan": "d",
           "bo_luat": "b", "so_ky_hieu": "s", "quote": "q"}
    assert CitationOut(**tho).vai_tro is None
    assert CitationOut(**tho, vai_tro="ket_luan").vai_tro == "ket_luan"


# ═══ Phase 14 R6 — không có căn cứ kiểm chứng được thì GIẢI THÍCH, không từ chối ═══
#
# Owner: "ko bị giới hạn chỉ tham chiếu mỗi data base, agent có thể trả lời được
# thực tế dựa vào database". Ranh giới không nhượng bộ: lời giải thích chung
# KHÔNG mang số Điều/Khoản/Điểm hay số hiệu văn bản nào — một trích dẫn chỉ có
# thể là một neo đã kiểm. `result_type` vẫn là `abstain` (vẫn KHÔNG có căn cứ
# dùng được — đó là sự thật về lượt này), điều mới là `answer` khác None và
# giao diện dán nhãn "giải thích chung" cho nó.


def _st_khong_can_cu():
    fail = Tier1Result(Claim("x", 999, "y"), False, R.provision_khong_ton_tai, None)
    return {"intent": "tra_cuu", "query": "thử việc là gì", "expanded": [DB[11]], "tier1": [fail],
            "tier2": [], "abstain_threshold": 0.5}


def test_khong_can_cu_kiem_chung_thi_tra_giai_thich_chung_trong_answer():
    llm = FakeLlm()
    st = assemble(_st_khong_can_cu(), DB, llm, "m")
    assert st["result_type"] is ResultType.abstain, "vẫn là abstain: không có căn cứ nào dùng được"
    assert st["answer"] == FakeLlm.giai_thich
    assert st["citations"] == [], "giải thích chung không mang trích dẫn nào"
    assert st["coverage_note"].startswith(KHONG_TIM_DUOC), "nửa đầu vẫn nói thẳng chưa tìm được điều khoản"
    assert llm.so_lan_giai_thich == 1 and llm.so_lan_hanh_van == 0, "vai giải thích, KHÔNG phải vai hành văn có trích dẫn"
    assert st["traces"]["assemble_giai_thich"] == "llm"
    # Chi phí của lượt giải thích cộng vào `assemble_*` — không có khoá mới nào
    # vô hình với trần chi phí ngày (`traces._COST_KEYS`).
    assert st["traces"]["assemble_token_in"] == 1 + 2 and st["traces"]["assemble_token_out"] == 1 + 3


@pytest.mark.parametrize("bia", [
    "Theo Điều 25 Bộ luật Lao động, thử việc tối đa 60 ngày.",
    "Khoản 1 quy định thời gian thử việc.",
    "Nghị định 145/2020/NĐ-CP hướng dẫn việc này.",
    "Xem [Điều 25](cite:1).",
    "Chi tiết tại https://thuvienphapluat.vn.",
    # Năm hình dạng bản lưới CHÉP TAY (`_RE_DIEU|_RE_KHOAN_DIEM|_RE_SO_KY_HIEU|
    # _RE_THE|_RE_URL`) để lọt, còn `bi_loai`/`moi_so_hieu_trong` — hai bộ nhận
    # diện repo đã có, đang được áp cho CÂU HỎI LẠI của chính lượt abstain này
    # — chặn. Đây là lý do lưới nay dùng lại chúng thay vì giữ bản thứ hai.
    "Bộ luật Lao động 2019 quy định thời gian thử việc tối đa 60 ngày.",  # mốc, không số Điều
    "Bạn thường phải báo trước 45 ngày trước khi nghỉ.",                  # mốc trong văn xuôi dè dặt
    "Ðiều 47 quy định về trợ cấp thôi việc.",                             # Ð U+00D0
    "Điều47 quy định về trợ cấp.",                                        # thiếu khoảng trắng
    "Thời hạn báo trước là ba mươi ngày làm việc.",                       # mốc viết bằng chữ
    "Nghị định 145/2020 hướng dẫn việc này.",                             # số hiệu viết thiếu đuôi
])
def test_giai_thich_chung_mang_so_dieu_hay_so_hieu_thi_bi_loai_khong_toi_nguoi_doc(bia):
    """Lưới 0 token: mô hình lỡ dẫn một số Điều/Khoản/số hiệu/mốc pháp lý/thẻ/
    URL trong lời giải thích → cả lời giải thích bị bỏ (rơi về abstain trơ như
    trước), vì ở đây KHÔNG có trích dẫn nào đã kiểm để đối chiếu — mọi số Điều
    đều là bịa. Giá đã chấp nhận: văn xuôi dè dặt hợp lệ có mốc cũng rơi."""
    llm = FakeLlm()
    llm.giai_thich = bia
    st = assemble(_st_khong_can_cu(), DB, llm, "m")
    assert st["result_type"] is ResultType.abstain and st["answer"] is None
    assert st["traces"]["assemble_giai_thich"] == "bi_loc"


def test_loi_giai_thich_qua_luoi_KHONG_bach_hoa_dinh_danh_nao_cho_luot_sau():
    """Từ Phase 14 `answer` của một lượt abstain ĐƯỢC LƯU — `hoi_thoai.
    _luot_thanh_lich_su` đọc đúng khoá `answer` — rồi chảy vào
    `giai_nghia.ngu_canh(lich_su)`. Ở đó `dinh_danh_bia` tính "bịa" bằng phép
    TRỪ: định danh trong câu đã giải nghĩa TRỪ định danh có ở `cau_goc` + lịch
    sử. Nên bất cứ định danh nào lọt lưới `giai_thich_chung` sẽ được BẠCH HOÁ
    từ lượt N+1 trở đi, và tầng kiểm tiền đề của câu HỎI mất tác dụng với nó.

    Khoá cửa đó bằng chính lưới đã có, KHÔNG bằng một cơ chế thứ hai: lời nào
    qua được lưới thì `dinh_danh_bia` không tìm thấy định danh nào trong nó —
    tức lưới phủ đủ ba họ `dinh_danh_bia` kiểm (số Điều, số hiệu, mốc pháp lý).
    Nới lưới ở `giai_thich_chung` mà quên chỗ này sẽ đỏ ngay tại đây."""
    from src.agents.nodes.assemble import giai_thich_chung
    from src.agents.nodes.giai_nghia import dinh_danh_bia

    ung_vien = [
        FakeLlm.giai_thich,
        "Thử việc là giai đoạn hai bên làm thử trước khi ký hợp đồng chính thức.",
        "Bộ luật Lao động 2019 quy định thời gian thử việc tối đa 60 ngày.",
        "Bạn thường phải báo trước 45 ngày trước khi nghỉ.",
        "Ðiều 47 quy định về trợ cấp thôi việc.",
        "Điều47 quy định về trợ cấp.",
        "Thời hạn báo trước là ba mươi ngày làm việc.",
        "Nghị định 145/2020 hướng dẫn việc này.",
        "Mức trợ cấp thường là nửa tháng lương cho mỗi năm làm việc.",
    ]
    for van in ung_vien:
        llm = FakeLlm()
        llm.giai_thich = van
        loi, _, nguon = giai_thich_chung("thử việc là gì", llm, "m")
        if nguon == "bi_loc":
            assert loi is None
            continue
        assert dinh_danh_bia(loi, "", []) == [], f"lời qua lưới vẫn bạch hoá định danh: {van!r}"


def test_giai_thich_chung_loi_mo_hinh_roi_ve_abstain_tro():
    class Hong(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            if json_schema is GIAI_THICH_SCHEMA:
                raise RuntimeError("openrouter 502")
            return super().chat(model, messages, json_schema)

    st = assemble(_st_khong_can_cu(), DB, Hong(), "m")
    assert st["result_type"] is ResultType.abstain and st["answer"] is None
    assert st["traces"]["assemble_giai_thich"] == "loi"


def test_moi_anh_em_cua_abstain_truy_hoi_rong_deu_giai_thich():
    """Bốn chỗ "truy hồi không cho gì kiểm chứng được": không bằng chứng
    (`insufficient_evidence`, không tầng nông), không claim qua tầng 1, tỉ lệ
    dưới ngưỡng, và mọi nguồn dùng được đều bị lọc (lạc đề)."""
    ok = _pass()
    fails = [Tier1Result(Claim("x", 999, "y"), False, R.provision_khong_ton_tai, None)] * 3
    cac_state = [
        {"intent": "tra_cuu", "query": "q", "expanded": [DB[11]], "insufficient_evidence": True,
         "tier1": [], "tier2": [], "abstain_threshold": 0.5},
        _st_khong_can_cu(),
        {"intent": "tra_cuu", "query": "q", "expanded": [DB[11]], "tier1": [ok, *fails],
         "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
        {"intent": "tra_cuu", "query": "q", "expanded": [DB[11]], "tier1": [ok],
         "tier2": [Tier2Verdict(0, True, "ok", relevant=False)], "abstain_threshold": 0.5},
    ]
    for st_vao in cac_state:
        llm = FakeLlm()
        st = assemble(st_vao, DB, llm, "m")
        assert st["result_type"] is ResultType.abstain and st["answer"] == FakeLlm.giai_thich, st_vao


def test_tien_de_sai_va_ha_cap_vi_so_dieu_bia_KHONG_giai_thich():
    """Hai ngõ cụt KHÔNG phải "truy hồi rỗng" giữ nguyên: tiền đề sai (câu hỏi
    nêu một Điều không tồn tại — giải thích là tiếp tay cho tiền đề), và lượt
    bị HẠ vì answer dẫn số Điều không có trong trích dẫn đã kiểm (R4/proof 9:
    lưới cuối vẫn hạ, và không một lượt gọi nào thêm để "cứu" câu đó)."""
    llm = FakeLlm()
    st = assemble({"intent": "tra_cuu", "query": "Điều 999 nói gì", "tien_de_sai": "Bộ luật Lao động không có Điều 999"},
                  DB, llm, "m")
    assert st["result_type"] is ResultType.abstain and st["answer"] is None and llm.so_lan_giai_thich == 0

    class GanSaiDieu(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            if json_schema is ANSWER_SCHEMA:
                self.schema_da_goi.append(json_schema)
                return json.dumps({"answer": "Theo Điều 550, ít nhất 85% mức lương."}), Usage(1, 1, 0.0)
            return super().chat(model, messages, json_schema)

    llm = GanSaiDieu()
    st = assemble({"intent": "tra_cuu", "query": "lương thử việc", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5}, DB, llm, "m")
    assert st["result_type"] is ResultType.abstain and st["answer"] is None
    assert st["traces"]["assemble_dieu_bi_loai"] == ["550"] and llm.so_lan_giai_thich == 0


# ═══ Quyết định 2026-09-28 — trích dẫn đầy đủ, liên kết nguồn chính thống ═══

DB_DU = {
    11: {
        **DB[11],
        "document_id": "139264",
        "duong_dan": "45/2019/QH14 > Điều 26 > Khoản 1",
        "loai_van_ban": "Bộ luật",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": date(2019, 11, 20),
        "ngay_hieu_luc": date(2021, 1, 1),
        "link_vbpl": "https://vbpl.vn/van-ban/chi-tiet/139264",
        "link_chinhphu": "https://vanban.chinhphu.vn/?pageid=27160&docid=198540",
        "link_tvpl": None,
    }
}


def test_citation_mang_du_truong_trich_dan_va_cach_trich_theo_mau_luat():
    st = assemble(
        {
            "intent": "tra_cuu",
            "expanded": [DB_DU[11]],
            "tier1": [_pass()],
            "tier2": [Tier2Verdict(0, True, "ok")],
            "abstain_threshold": 0.5,
        },
        DB_DU,
        FakeLlm(),
        "m",
    )
    assert st["result_type"] is ResultType.answer
    c = st["citations"][0]
    assert c["ten_van_ban"] == "Bộ Luật lao động" and c["loai_van_ban"] == "Bộ luật"
    assert c["co_quan_ban_hanh"] == "Quốc hội"
    assert (c["ngay_ban_hanh"], c["ngay_hieu_luc"]) == ("2019-11-20", "2021-01-01")
    assert c["lien_ket"] == "https://vbpl.vn/van-ban/chi-tiet/139264", "vbpl.vn trước vanban.chinhphu.vn"
    assert c["cach_trich"] == "khoản 1 Điều 26 Bộ luật Lao động số 45/2019/QH14 ngày 20/11/2019 của Quốc hội"
    assert c["canh_bao"] is None, "còn hiệu lực thì không có cảnh báo"
    # Trường CŨ giữ nguyên cho FE đang chạy.
    assert (c["bo_luat"], c["so_ky_hieu"]) == ("Bộ Luật lao động", "45/2019/QH14")
    d = st["documents"][0]
    assert d["cach_trich"] == "Bộ luật Lao động số 45/2019/QH14 ngày 20/11/2019 của Quốc hội"
    assert d["links"]["tvpl"] is None and d["lien_ket"] == c["lien_ket"]
    json.dumps(st["citations"])  # ngày là chuỗi ISO — cache câu trả lời tuần tự hoá được


def test_canh_bao_gan_vao_DUNG_trich_dan_cua_no_va_trung_warnings():
    mp = Effectivity(V.mot_phan_khong_xac_dinh, "thap", "bị 71/2025/QH15 sửa đổi, bổ sung từ 2026-01-01",
                     van_ban=(VanBanNeu("9", "71/2025/QH15"),))
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, mp)
    st = assemble(
        {
            "intent": "tra_cuu",
            "expanded": [DB_DU[11]],
            "tier1": [t1],
            "tier2": [Tier2Verdict(0, True, "ok")],
            "abstain_threshold": 0.5,
        },
        DB_DU,
        FakeLlm(),
        "m",
    )
    (w,) = st["warnings"]
    c = st["citations"][0]
    assert c["canh_bao"] == w and "71/2025/QH15" in w, "FE hiện cảnh báo ngay cạnh trích dẫn, không phải dò chuỗi"


def test_nguon_partial_coverage_mang_truong_trich_dan_NULL_thi_an():
    shallow = [
        {
            "id": 5,
            "document_id": "84265",
            "duong_dan": "84/2015/QH13 > Mở đầu",
            "so_ky_hieu": "84/2015/QH13",
            "ten": "Luật An toàn, vệ sinh lao động số 84/2015/QH13",
            "loai_van_ban": "Luật",
            "co_quan_ban_hanh": None,
            "ngay_ban_hanh": date(2015, 6, 25),
            "ngay_hieu_luc": None,
            "link_vbpl": None,
            "link_chinhphu": None,
        }
    ]
    st = assemble({"intent": "tra_cuu", "expanded": [], "hits_shallow": shallow}, DB, FakeLlm(), "m")
    (n,) = st["nguon"]
    assert n["cach_trich"] == "Luật An toàn, vệ sinh lao động số 84/2015/QH13 ngày 25/06/2015"
    assert n["co_quan_ban_hanh"] is None and n["lien_ket"] is None and n["ngay_hieu_luc"] is None


def test_CitationOut_NguonOut_DocumentOut_nhan_truong_moi_va_payload_cu_van_hop_le():
    from src.models.schemas import CitationOut, DocumentOut, NguonOut

    tho = {
        "provision_id": 11,
        "khop_tai_id": 11,
        "doc_id": "1",
        "duong_dan": "d",
        "bo_luat": "b",
        "so_ky_hieu": "s",
        "quote": "q",
    }
    assert CitationOut(**tho).cach_trich is None and CitationOut(**tho).canh_bao is None
    c = CitationOut(**tho, ngay_ban_hanh="2019-11-20", lien_ket="https://vbpl.vn/van-ban/chi-tiet/1")
    assert c.model_dump(mode="json")["ngay_ban_hanh"] == "2019-11-20"
    assert NguonOut(doc_id="1", so_ky_hieu="s", bo_luat="b").lien_ket is None
    assert DocumentOut(doc_id="1", ten="t", so_ky_hieu="s", loai_van_ban="Luật").ngay_hieu_luc is None


# ══ Lệnh sửa đổi mang nguyên văn mới của một Điều khác (trace c8a98c3d) ═══════
# "hiện tại pháp luật việt nam chia thành những gì", 2026-09-30: 35/35/35 claim
# qua hai tầng, rồi `_the_khong_hop_le` hạ cả lượt xuống abstain với
# `cite:15≠['1']` … `cite:23≠['1']` (uvicorn log; `traces` không lưu chữ claim).
# Căn cứ Điều 1 trong tập truy hồi là 87/2025/QH15 > Điều 1 > Khoản 1 — "Sửa đổi,
# bổ sung Điều 4 như sau: “Điều 4 …”" — tức CHÍNH Điều 4 hiện hành của
# 64/2025/QH15, và mô hình gọi nó "Điều 4". Replay trên CSDL dev (expand thật ra
# đúng 205 dòng như trace) tái lập đúng chín thẻ `≠['1']` đó.
# Dòng dưới đây chép từ CSDL dev (SELECT, id thật), nguyên văn khoản 1 rút gọn.
K1_87 = (
    "1. Sửa đổi, bổ sung Điều 4 như sau: “Điều 4. Hệ thống văn bản quy phạm pháp luật "
    "1. Hiến pháp. 2. Bộ luật, luật (sau đây gọi chung là luật), nghị quyết của Quốc hội. "
    "15. Quyết định của Ủy ban nhân dân cấp xã.”."
)
_VB_87 = {
    "document_id": "178717",
    "so_ky_hieu": "87/2025/QH15",
    "loai_van_ban": "Luật",
    "ten": "Luật Sửa đổi, bổ sung một số điều của luật ban hành văn bản quy phạm pháp luật số 87/2025/QH15",
}
DB_SUA = {
    337734: {
        **_VB_87,
        "id": 337734,
        "parent_id": None,
        "duong_dan": "87/2025/QH15 > Điều 1",
        "noi_dung": "Điều 1. Sửa đổi, bổ sung một số điều của Luật Ban hành văn bản quy phạm pháp luật",
    },
    337735: {
        **_VB_87,
        "id": 337735,
        "parent_id": 337734,
        "duong_dan": "87/2025/QH15 > Điều 1 > Khoản 1",
        "noi_dung": K1_87,
    },
    337743: {
        **_VB_87,
        "id": 337743,
        "parent_id": 337734,
        "duong_dan": "87/2025/QH15 > Điều 1 > Khoản 9",
        "noi_dung": "9. Sửa đổi, bổ sung một số điểm, khoản của Điều 31 như sau:",
    },
    337744: {
        **_VB_87,
        "id": 337744,
        "parent_id": 337743,
        "duong_dan": "87/2025/QH15 > Điều 1 > Khoản 9 > Điểm a",
        "noi_dung": "a) Sửa đổi, bổ sung khoản 1 như sau: “1. Bộ Tư pháp chủ trì, phối hợp với Bộ Tài chính.”",
    },
    # Đối chứng: một điều luật THƯỜNG dẫn chiếu Điều khác (ca mh-004, "Điều 108").
    162173: {
        "id": 162173,
        "parent_id": None,
        "document_id": "139264",
        "so_ky_hieu": "45/2019/QH14",
        "loai_van_ban": "Bộ luật",
        "ten": "Bộ Luật lao động số 45/2019/QH14",
        "duong_dan": "45/2019/QH14 > Điều 108",
        "noi_dung": "Điều 108. Làm thêm giờ trong trường hợp đặc biệt Người sử dụng lao động có quyền "
        "yêu cầu người lao động làm thêm giờ vào bất kỳ ngày nào mà không bị giới hạn về số "
        "giờ làm thêm theo quy định tại Điều 107 của Bộ luật này",
    },
}


def test_dieu_duoc_sua_doc_lenh_sua_doi_va_dong_cha_khong_doc_dan_chieu_thuong():
    from src.agents.nodes.assemble import dieu_duoc_sua

    assert dieu_duoc_sua(337735, DB_SUA) == ["4"]
    assert dieu_duoc_sua(337744, DB_SUA) == ["31"], "điểm a sửa khoản 1 CỦA Điều 31 — số nằm ở khoản cha"
    assert dieu_duoc_sua(337734, DB_SUA) == [], "tiêu đề Điều 1 không phải lệnh sửa"
    assert dieu_duoc_sua(162173, DB_SUA) == [], "dẫn chiếu thường ('theo Điều 107') KHÔNG được bạch hoá"
    cho_nguyen_van = {1: {"id": 1, "noi_dung": "3. Sửa đổi, bổ sung Điều 21 như sau: “Điều 21. … theo Điều 5 …”"}}
    assert dieu_duoc_sua(1, cho_nguyen_van) == ["21"], "số Điều trong NGUYÊN VĂN MỚI không tính"


def _st_he_thong(*claims):
    return {
        "intent": "tra_cuu",
        "query": "hiện tại pháp luật việt nam chia thành những gì",
        "expanded": [DB_SUA[337735]],
        "tier1": list(claims),
        "tier2": [Tier2Verdict(i, True, "ok") for i in range(len(claims))],
        "abstain_threshold": 0.5,
    }


_HIEN_PHAP = Tier1Result(
    Claim("Hiến pháp đứng đầu hệ thống.", 337734, "1. Hiến pháp."), True, R.ok, EFF, khop_tai=337735
)
_LUAT = Tier1Result(
    Claim(
        "Sau đó là luật, nghị quyết của Quốc hội.",
        337735,
        "2. Bộ luật, luật (sau đây gọi chung là luật), nghị quyết của Quốc hội.",
    ),
    True,
    R.ok,
    EFF,
)


def test_the_goi_dieu_ma_lenh_sua_doi_mang_nguyen_van_thi_giu_cau_tra_loi():
    """Replay trace c8a98c3d: thẻ `[Khoản N Điều 4](cite:K)` trên căn cứ
    87/2025/QH15 > Điều 1 > Khoản 1 là ĐÚNG — không được hạ cả lượt."""
    answer = (
        "Chào bạn, hệ thống văn bản quy phạm pháp luật hiện hành theo "
        "[Luật số 87/2025/QH15](doc:178717) đứng đầu là Hiến pháp [Khoản 1 Điều 4](cite:1), "
        "rồi tới luật và nghị quyết của Quốc hội [Khoản 2 Điều 4](cite:2)."
    )
    st = assemble(_st_he_thong(_HIEN_PHAP, _LUAT), DB_SUA, LlmTraLoi(answer), "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.answer, st["coverage_note"]
    assert st["traces"]["assemble_the_loi"] == [] and st["traces"]["assemble_dieu_bi_loai"] == []
    assert [(c["duong_dan"], c["k"]) for c in st["citations"]] == [
        ("87/2025/QH15 > Điều 1 > Khoản 1", 1),
        ("87/2025/QH15 > Điều 1 > Khoản 1", 2),
    ]
    assert st["answer"] == answer


@pytest.mark.parametrize(
    "answer, the_loi, dieu_loai",
    [
        # Điều khác Điều mà lệnh sửa mang — vẫn là số lạ.
        ("Đứng đầu là Hiến pháp [Khoản 1 Điều 5](cite:1).", ["cite:1≠['1', '4']"], []),
        ("Theo Điều 5, đứng đầu là Hiến pháp.", [], ["5"]),
    ],
)
def test_lenh_sua_doi_chi_bach_hoa_dung_dieu_no_sua(answer, the_loi, dieu_loai):
    st = assemble(_st_he_thong(_HIEN_PHAP), DB_SUA, LlmTraLoi(answer), "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.abstain
    assert st["traces"]["assemble_the_loi"] == the_loi
    assert st["traces"]["assemble_dieu_bi_loai"] == dieu_loai


@pytest.mark.parametrize(
    "answer", ["Trừ trường hợp đặc biệt [Điều 107](cite:1).", "Trừ trường hợp đặc biệt theo Điều 107."]
)
def test_dan_chieu_thuong_van_bi_ha_nhu_cu(answer):
    """Ca mh-004 (K11): điều luật thường nhắc Điều khác KHÔNG làm số đó thành căn cứ."""
    t1 = Tier1Result(Claim("Làm thêm giờ đặc biệt.", 162173, "không bị giới hạn về số giờ làm thêm"), True, R.ok, EFF)
    st = assemble(
        {**_st_he_thong(t1), "query": "làm thêm giờ đặc biệt", "expanded": [DB_SUA[162173]]},
        DB_SUA,
        LlmTraLoi(answer),
        "m",
        prompt_path=V3_PROMPT,
    )
    assert st["result_type"] is ResultType.abstain


def test_dieu_khong_chong_do_tinh_ca_dieu_duoc_sua_cua_can_cu():
    cits = [{"duong_dan": "87/2025/QH15 > Điều 1 > Khoản 1", "dieu_duoc_sua": ["4"]}]
    assert _dieu_khong_duoc_chong_do("Điều 4 liệt kê 15 loại văn bản.", cits) == []
    assert _dieu_khong_duoc_chong_do("Điều 5 liệt kê 15 loại văn bản.", cits) == ["5"]


# ── Ngõ cụt của câu hỏi không về một vụ việc lao động (trace c8a98c3d) ───────
# "pháp luật việt nam chia thành những gì" nhận "Chuyện này xảy ra khi nào bạn?"
# và "Bạn có giấy tờ gì về việc này?": sáu chiều của `hoi_lai` là dữ kiện một vụ
# việc lao động, và câu hỏi này không có vụ việc nào để hỏi.
@pytest.mark.parametrize(
    "kw",
    [
        {"query": "hiện tại pháp luật việt nam chia thành những gì"},
        # bộ nhớ nền kéo lĩnh vực về lao_dong: câu hỏi vẫn không có vụ việc nào
        {"query": "hiện tại pháp luật việt nam chia thành những gì", "linh_vuc_du_doan": "lao_dong"},
        {"query": "chia tài sản chung khi ly hôn thế nào", "linh_vuc_du_doan": "hon_nhan_gia_dinh"},
    ],
)
def test_ngo_cut_cau_hoi_khong_ve_lao_dong_KHONG_hoi_tinh_huong(kw):
    from src.agents.nodes.hoi_lai import CAU_DAN

    llm = FakeLlm()
    st = assemble(_st(tier2=[], **kw), DB, llm, "m", prompt_path=V3_PROMPT)
    assert st["result_type"] is ResultType.abstain
    assert llm.so_lan_hoi_lai == 0 and st["traces"]["assemble_hoi_lai"] == "bo_qua"
    assert st["coverage_note"] == KHONG_TIM_DUOC and CAU_DAN not in st["coverage_note"]


@pytest.mark.parametrize(
    "query",
    [
        "lương thử việc bao nhiêu",
        # "luật VN" / "luật nước ta" chỉ mở đầu một vụ việc, không hỏi hệ thống
        # pháp luật được xây thế nào (review 2026-09-30: nhánh trơ của
        # `hoi_he_thong_phap_luat` từng làm mất câu hỏi lại của các câu này)
        "Theo luật VN thì tôi bị nợ lương 3 tháng phải làm sao",
        "Theo pháp luật Việt Nam, công ty sa thải tôi khi đang mang thai có đúng không",
        "pháp luật nước ta quy định thời gian thử việc tối đa bao lâu",
    ],
)
def test_ngo_cut_cau_hoi_lao_dong_van_hoi_tinh_huong(query):
    llm = FakeLlm()
    st = assemble(_st(tier2=[], query=query, linh_vuc_du_doan="lao_dong"), DB, llm, "m", prompt_path=V3_PROMPT)
    assert llm.so_lan_hoi_lai == 1 and st["traces"]["assemble_hoi_lai"] == "llm"
