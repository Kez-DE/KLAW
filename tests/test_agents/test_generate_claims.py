import json

from src.agents.nodes.generate_claims import (
    CLAIMS_SCHEMA,
    PROMPT_PATH,
    build_context,
    generate_claims,
)
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import verify_tier1
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V


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
        # `document_id` là khoá GỘP thật (build_context, 2026-09-02): `so_ky_hieu`
        # không duy nhất — `65/2006/QH11` có hai dòng trong `documents`.
        "document_id": "139264",
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


def test_json_schema_duoc_truyen_va_bat_buoc_bon_field():
    llm = FakeLlm({"insufficient_evidence": True, "claims": []})
    generate_claims({"query": "x", "expanded": PROVS}, llm, "m")
    assert llm.last["schema"] == CLAIMS_SCHEMA
    props = llm.last["schema"]["properties"]["claims"]["items"]
    # Task 15: `hang` (hàng của bảng so sánh) thêm vào required — schema strict
    # (llm.py) đòi mọi thuộc tính có mặt trong `required`, null được phép qua `anyOf`.
    assert set(props["required"]) == {"text", "provision_id", "quote", "hang"}


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


# ══ Pha 3a (spec 2026-09-02 §7) — bối cảnh dày hơn ═══════════════════════════
# Chỗ nghẽn đo được 2026-09-02: "Hiện tại có bao nhiêu bộ luật?" → 30 điều khoản
# tầng sâu trong tay, generate_claims sinh 0 luận điểm. `build_context` cũ đưa
# đúng 5 trường (id/so_ky_hieu/duong_dan/tieu_de/noi_dung) dàn PHẲNG ngăn bằng
# `---`, nên 30 dòng của vài văn bản khác nhau trông như 30 nguồn NGANG HÀNG:
# model không có cách nào ưu tiên bản còn áp dụng, cũng không phân biệt Bộ luật
# với Thông tư để áp thứ bậc hiệu lực.
_D26 = {
    "id": 11, "document_id": "139264", "so_ky_hieu": "45/2019/QH14", "loai_van_ban": "Luật",
    "duong_dan": "45/2019/QH14 > Điều 26", "tieu_de": "Điều 26. Tiền lương thử việc",
    "noi_dung": "Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận.",
    "effectivity": Effectivity(V.con_hieu_luc, "cao", "trong thời gian hiệu lực"),
}
_D102 = {
    "id": 12, "document_id": "139264", "so_ky_hieu": "45/2019/QH14", "loai_van_ban": "Luật",
    "duong_dan": "45/2019/QH14 > Điều 102", "tieu_de": "Điều 102. Khấu trừ tiền lương",
    "noi_dung": "Người sử dụng lao động chỉ được khấu trừ tiền lương của người lao động"
                " để bồi thường thiệt hại do làm hỏng dụng cụ, thiết bị.",
    "effectivity": Effectivity(V.bi_sua_doi, "trung_binh", "bị sửa bởi 113/2025/QH15"),
}
# Văn bản THỨ HAI, đã bị thay thế — đúng hình dạng ca lương tối thiểu ở Plan 1,
# nơi bốn nghị định đã bị thay thế được trình bày ngang hàng với bản hiện hành.
_ND38 = {
    "id": 21, "document_id": "152999", "so_ky_hieu": "38/2022/ND-CP", "loai_van_ban": "Nghị định",
    "duong_dan": "38/2022/ND-CP > Điều 3", "tieu_de": "Điều 3. Mức lương tối thiểu",
    "noi_dung": "Quy định mức lương tối thiểu tháng theo bốn vùng.",
    "effectivity": Effectivity(V.bi_thay_the, "cao", "bị thay bởi 74/2024/ND-CP"),
}
PROVS_HAI_VAN_BAN = [_D26, _D102, _ND38]


def test_context_co_loai_van_ban_de_model_ap_duoc_thu_bac_hieu_luc():
    """Không có `loai_van_ban`, model không biết đâu là Bộ luật đâu là Thông tư
    nên không áp được thứ bậc hiệu lực giữa hai nguồn nói khác nhau."""
    ctx = build_context(PROVS_HAI_VAN_BAN)
    assert "loai_van_ban=Luật" in ctx
    assert "loai_van_ban=Nghị định" in ctx


def test_context_co_verdict_hieu_luc_cua_TUNG_dieu_khoan():
    """Verdict lấy lại từ `state["expanded"]` (expand() đã tính qua cạnh đi vào
    thật) — mỗi điều khoản một verdict, KHÔNG một verdict chung cho cả văn bản:
    45/2019/QH14 ở đây có Điều còn hiệu lực và Điều đã bị sửa."""
    ctx = build_context(PROVS_HAI_VAN_BAN)
    assert "hieu_luc=con_hieu_luc" in ctx
    assert "hieu_luc=bi_sua_doi" in ctx
    assert "hieu_luc=bi_thay_the" in ctx


def test_dieu_khoan_cung_MOT_van_ban_duoc_gop_duoi_MOT_dau_muc():
    """Gộp theo văn bản, không dàn phẳng: hai Điều của 45/2019/QH14 nằm dưới một
    đầu mục duy nhất, và chỉ còn MỘT dấu ngăn `---` — giữa hai VĂN BẢN, không
    giữa hai điều khoản của cùng một văn bản."""
    ctx = build_context(PROVS_HAI_VAN_BAN)
    assert ctx.count("so_ky_hieu=45/2019/QH14") == 1, "45/2019/QH14 vẫn bị lặp đầu mục — chưa gộp"
    assert ctx.count("VĂN BẢN so_ky_hieu=") == 2  # đếm ĐẦU MỤC, không đếm dấu phân cách, "vẫn dàn phẳng: mỗi điều khoản một khối ngăn bằng ---"
    # thứ tự ưu tiên truy hồi phải được giữ: văn bản xuất hiện trước đứng trước.
    assert ctx.index("45/2019/QH14 > Điều 26") < ctx.index("38/2022/ND-CP > Điều 3")


def test_gop_van_ban_van_giu_provision_id_va_so_ky_hieu_tuong_minh():
    """Global Constraint: model phải dẫn được `provision_id` chính xác, và văn
    bản phải định danh bằng `so_ky_hieu` (KHÔNG bằng `ten`). Việc gộp nhóm không
    được làm mờ hai thứ đó."""
    ctx = build_context(PROVS_HAI_VAN_BAN)
    for p in PROVS_HAI_VAN_BAN:
        assert f"[provision_id={p['id']}]" in ctx
    assert "so_ky_hieu=45/2019/QH14" in ctx and "so_ky_hieu=38/2022/ND-CP" in ctx


def test_effectivity_None_roi_ve_chua_xac_dinh_KHONG_PHAI_con_hieu_luc():
    """`expand()` gán effectivity cho MỌI dòng, nên None chỉ đến từ một tối ưu
    tương lai làm lệch tập — và đúng lúc đó, mặc định phải là `chua_xac_dinh`.
    Mặc định `con_hieu_luc` là chế độ hỏng nguy hiểm nhất của cả đề tài (xem
    graph_tra_cuu.n_tier1 + src/services/effectivity.py): một điều khoản CHƯA
    TỪNG được đánh giá sẽ được model trình bày như nguồn còn áp dụng."""
    ctx = build_context([{**_D26, "effectivity": None}])
    assert "hieu_luc=chua_xac_dinh" in ctx
    assert "con_hieu_luc" not in ctx


def test_thieu_han_khoa_effectivity_khong_no_AttributeError():
    """Bản ghi không có khoá `effectivity` (vd. test cũ, hoặc caller ngoài
    expand()) không được làm sập node — rơi về `chua_xac_dinh` như ca None."""
    p = {k: v for k, v in _D26.items() if k != "effectivity"}
    assert "hieu_luc=chua_xac_dinh" in build_context([p])


def test_HAI_van_ban_cung_so_ky_hieu_KHONG_bi_gop_thanh_mot():
    """`so_ky_hieu` KHÔNG duy nhất — đo được trên DB thật 2026-09-02:
    `65/2006/QH11` có HAI dòng trong `documents`, một "Luật sư số 65/2006/QH11"
    (`loai_van_ban='Luật'`) và một "Nghị quyết số 65/2006/QH11"
    (`loai_van_ban='Nghị quyết'`).

    Gộp theo khoá đó thì hai văn bản khác nhau thành MỘT đầu mục, và
    `loai_van_ban` của đầu mục lấy của phần tử đầu nhóm — nên quy tắc 4 của prompt
    (ưu tiên văn bản cấp cao hơn) tính sai giữa hai văn bản nó tưởng là một.

    Ca này đang BẤT HOẠT trên corpus hiện tại vì phía "Luật sư" có 0 provision nên
    không vào được `expand()`. Đó là may rủi dữ liệu, không phải mã chặn — test
    này là mã chặn.
    """
    luat = {"id": 91, "document_id": "15076", "so_ky_hieu": "65/2006/QH11",
            "loai_van_ban": "Luật", "duong_dan": "65/2006/QH11 > Điều 1",
            "tieu_de": "Điều 1", "noi_dung": "Phạm vi điều chỉnh của Luật Luật sư.",
            "effectivity": Effectivity(V.con_hieu_luc, "cao", "x")}
    nghi_quyet = {"id": 92, "document_id": "15074", "so_ky_hieu": "65/2006/QH11",
                  "loai_van_ban": "Nghị quyết", "duong_dan": "65/2006/QH11 > Điều 1",
                  "tieu_de": "Điều 1", "noi_dung": "Về việc thi hành Luật Luật sư.",
                  "effectivity": Effectivity(V.con_hieu_luc, "cao", "x")}

    ctx = build_context([luat, nghi_quyet])
    assert ctx.count("VĂN BẢN so_ky_hieu=") == 2, f"hai văn bản bị gộp thành một:\n{ctx}"
    # Cả hai loại phải hiện ra — nếu gộp, một loại bị xoá khỏi tầm nhìn của model.
    assert "loai_van_ban=Luật" in ctx
    assert "loai_van_ban=Nghị quyết" in ctx


def test_prompt_giu_phep_kiem_TRA_LOI_DUOC_khong_ha_xuong_CO_LIEN_QUAN():
    """Siết lối thoát (quy tắc 5) không được vô tình nới bar cho "đủ căn cứ".

    Bản đầu của quy tắc 6 viết "chỉ khi cả ba loại đều không có gì LIÊN QUAN tới
    câu hỏi" — "liên quan" là ngưỡng chủ đề, lỏng hơn hẳn "trả lời được" của bản
    gốc. Hệ quả (review 2026-09-02): model dễ tạo ra một lần "thử trả lời" hơn và
    khó tạo `insufficient_evidence` hơn; nếu phần lớn lần thử đó bị tầng 1 loại vì
    quote không khớp, người hỏi nhận một câu trả lời gần trống thay vì một lời
    "chưa đủ căn cứ" sạch.

    Bất biến "thiếu căn cứ là câu trả lời ĐÚNG" là đóng góp trung tâm của đề tài.
    Quy tắc 5 chỉ được buộc model TÌM cho hết trước khi bỏ cuộc, không được hạ
    thấp mức thế nào là đủ.
    """
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "KHÔNG TRẢ LỜI ĐƯỢC câu hỏi" in prompt
    assert "câu trả lời ĐÚNG, không phải thất bại" in prompt, "mất lời khẳng định abstain là đúng"
    # Ngưỡng chủ đề bị loại tường minh, để lần sau ai viết lại prompt thấy ngay.
    assert 'KHÔNG phải "có liên quan tới chủ đề"' in prompt


# ══ Regression — Task 1 (2026-09-02): "vùng ba" abstain SAI dù nguồn có thật ═
# Số liệu THẬT lấy từ DB (khớp task-1-brief.md): 293/2025/NĐ-CP > Điều 3 >
# Khoản 1 > Vùng III, provision_id=258773, hieu_luc=con_hieu_luc. TRƯỚC bản sửa
# này, build_context() in `tieu_de` tổng hợp ("Vùng III") thành một dòng RIÊNG
# đứng trước `noi_dung`, dù prov_parser.py tài liệu hoá rõ (dòng 21):
# "`noi_dung` là TOÀN VĂN điều luật (nhãn + thân)" — với hang_bang/khoan/diem,
# `tieu_de` = nhãn TỔNG HỢP (`f"{NHAN[cap]} {so_hieu_cap}"`, prov_parser.py
# dòng 995-999), KHÔNG phải một dòng tồn tại tách biệt trong nguồn.
#
# Đo được (task-1-report.md, 5 lần chạy graph thật): 3/5 lần model chép NGUYÊN
# CẢ HAI dòng vào `quote`, và tầng 1 loại đúng — quote đó KHÔNG PHẢI substring
# của `noi_dung` — nhưng vì lý do SAI: build_context tự thêm một dòng không có
# trong nguồn, không phải vì model bịa nội dung. Khi tất cả 9 claim của một
# lượt đều dính lỗi này, `qua_t1` rỗng và graph abstain dù nguồn có thật.
#
# Test dưới đây KHÔNG hard-code quote: nó dùng ĐÚNG `generate_claims()` (đi
# qua build_context + JSON schema thật), chỉ giả LLM bằng một "model trung
# thực" — chép NGUYÊN VĂN khối build_context in ra cho provision đó, không
# bịa không rút gọn. Đây là hành vi TỆ NHẤT còn hợp lệ theo quy tắc 3 của
# prompt ("quote phải NGUYÊN VĂN copy"), nên nếu build_context còn lẫn một
# dòng không-verbatim vào khối, test này bắt được — và nếu ai sau này thêm lại
# một dòng metadata tương tự, test sẽ đỏ lại đúng cách nó đã đỏ ở Task 1.
_VUNG_III = {
    "id": 258773,
    "document_id": "183939",
    "so_ky_hieu": "293/2025/NĐ-CP",
    "loai_van_ban": "Nghị định",
    "duong_dan": "293/2025/NĐ-CP > Điều 3 > Khoản 1 > Vùng III",
    "tieu_de": "Vùng III",
    "noi_dung": "| Vùng III | 4.140.000 | 20.000 |",
    "effectivity": Effectivity(V.con_hieu_luc, "thap", "NĐ 293/2025/NĐ-CP còn hiệu lực"),
}


def _quote_mo_hinh_trung_thuc_chep(prompt: str, provision_id: int) -> str:
    """Mô phỏng một model TRUNG THỰC: chép nguyên khối văn bản `build_context`
    in ra cho `provision_id` — không bịa, không rút gọn. Nếu `build_context`
    còn lẫn một dòng KHÔNG-verbatim (nhãn tổng hợp) vào khối đó, hàm này chép
    luôn dòng đó, đúng cơ chế thật đã đo ở Task 1."""
    marker = f"[provision_id={provision_id}] "
    dong_meta_ket_thuc = prompt.index("\n", prompt.index(marker))
    return prompt[dong_meta_ket_thuc + 1 :].rstrip()


def test_model_trung_thuc_chep_dung_khoi_VUNG_III_van_qua_duoc_tang_1():
    """RED trước bản sửa (quote_khong_khop vì build_context lẫn "Vùng III\\n"
    vào một dòng riêng), GREEN sau bản sửa. Dùng generate_claims() + verify_tier1()
    THẬT — chỉ LLM bị giả — nên đây là phép kiểm HÀNH VI (claim sống sót qua
    tầng 1 để thành citation), không phải kiểm build_context trả về gì."""

    class ModHinhChepDung:
        def chat(self, model, messages, json_schema=None):
            from src.services.llm import Usage

            quote = _quote_mo_hinh_trung_thuc_chep(messages[-1]["content"], 258773)
            payload = {
                "insufficient_evidence": False,
                "claims": [
                    {
                        "text": "Mức lương tối thiểu vùng III hiện nay là 4.140.000 đồng/tháng.",
                        "provision_id": 258773,
                        "quote": quote,
                    }
                ],
            }
            return json.dumps(payload), Usage(10, 5, 0.0001)

    st = generate_claims(
        {"query": "lương tối thiểu vùng ba hiện nay quy định thế nào", "expanded": [_VUNG_III]},
        ModHinhChepDung(),
        "m",
    )
    assert len(st["draft_claims"]) == 1

    db_provisions = {_VUNG_III["id"]: {**_VUNG_III, "parent_id": 258770}}
    r = verify_tier1(
        st["draft_claims"], [_VUNG_III], db_provisions,
        lambda pid: Effectivity(V.con_hieu_luc, "thap", "x"),
    )[0]
    assert r.ok is True and r.reason is R.ok, (
        f"claim đúng nội dung (293/2025/NĐ-CP, Vùng III) bị loại vì lý do "
        f"KHÔNG PHẢI ảo giác: {r.reason} — quote={st['draft_claims'][0].quote!r}"
    )
    assert r.khop_tai == 258773
