"""Decision 2026-09-30 (`docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md`)
items 1, 2, 5, 6, 8 — fake LLMs only, no DB.

The four questions the owner typed on 2026-09-30 (traces 88117154, 8eb13b06,
6203bc9d, 2cfaa33a): a land dispute forced into the introduction, "bạn làm được
những gì, bạn là ai" answered with two overlapping fixed blocks, and "bạn giúp tôi
được chứ" answered with a generic block under "Tôi hiểu câu hỏi của bạn là…".
"""

import json
from pathlib import Path

import pytest

from src.agents.nodes import gioi_thieu as gt
from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.giai_nghia import doi_nghia, giai_nghia
from src.agents.nodes.route import Intent, route
from src.services import khuon_mau
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.kho import CAU_GIOI_HAN
from src.services.llm import Usage, generate_model, judge_model, router_model

DAT_DAI = "tôi đang gặp sự cố tranh chấp nhà đất , cần nắm rõ những bộ luật gì để ko bị mất quyền lợi"
LAM_GI_LA_AI = "bạn làm được những gì, bạn là ai"
LA_AI = "Bạn là ai và bạn làm được những gì"
GIUP = "bạn giúp tôi được chứ"


def _vb(so, ten, loai="Luật", depth="deep", linh_vuc=None):
    return {
        "so_ky_hieu": so,
        "ten": ten,
        "loai_van_ban": loai,
        "depth": depth,
        "hieu_luc": Effectivity(V.con_hieu_luc, "cao", "x"),
        "linh_vuc": linh_vuc,
    }


KHO = [
    _vb(
        "45/2019/QH14", "Bộ Luật lao động số 45/2019/QH14", loai="Bộ luật", linh_vuc="Lao động - Thương binh và Xã hội"
    ),
    _vb("145/2020/NĐ-CP", "Nghị định 145/2020/NĐ-CP", loai="Nghị định", linh_vuc="Lao động - Thương binh và Xã hội"),
    _vb("31/2024/QH15", "Luật Đất đai số 31/2024/QH15", linh_vuc="Đất đai"),
    _vb("27/2023/QH15", "Luật Nhà ở số 27/2023/QH15", depth="shallow", linh_vuc="Xây dựng"),
]


class LlmRoute:
    def __init__(self, intent: str):
        self.intent = intent

    def chat(self, model, messages, json_schema=None):
        return json.dumps({"intent": self.intent}), Usage(1, 1, 0.0)


def _route(cau: str, y_dinh: str, tmp_path: Path) -> dict:
    mau = tmp_path / "route.md"
    mau.write_text("{cau_hoi}", encoding="utf-8")
    return route({"query": cau}, LlmRoute(y_dinh), "m", prompt_path=mau)


class LlmViet:
    """The meta writer: records each prompt, returns a fixed text."""

    def __init__(self, tra_loi: str):
        self.tra_loi, self.prompts = tra_loi, []

    def chat(self, model, messages, json_schema=None):
        assert "tra_loi" in json_schema["properties"]
        self.prompts.append(messages[-1]["content"])
        return json.dumps({"tra_loi": self.tra_loi}), Usage(40, 20, 0.0001)


class LlmHong:
    def chat(self, *a, **k):
        raise RuntimeError("OpenRouter 429")


def _meta(cau: str, llm, intent: str = "gioi_thieu", kho=KHO, **them) -> dict:
    bang = gt.bang_du_kien(cau, kho)
    van_ban = gt.van_ban_cua_bang(bang, kho) if kho is not None else {}
    return assemble(
        {"query": cau, "intent": intent, "bang_du_kien": bang, "van_ban_bang": van_ban, **them}, {}, llm, "m"
    )


# ══ Item 2 — a situation question is a legal question ═══════════════════════

DAT_DAI_KHONG_DAU = "toi dang gap su co tranh chap nha dat can nam ro nhung bo luat gi"


@pytest.mark.parametrize("cau", [DAT_DAI, DAT_DAI_KHONG_DAU])
@pytest.mark.parametrize("y_dinh", ["tra_cuu", "gioi_thieu", "hoi_ve_kho"])
def test_cau_tranh_chap_nha_dat_di_tra_cuu(cau, y_dinh, tmp_path):
    """Trace 88117154: the "những bộ luật gì" branch had no bạn/KLAW/kho anchor,
    so the land dispute got the list of six Bộ luật. Whatever the router says,
    the asker's own situation makes it a legal question — typed without
    diacritics too (review 2026-09-30)."""
    assert not gt.chac_chan_meta(cau)
    assert gt.ke_tinh_huong(cau)
    st = _route(cau, y_dinh, tmp_path)
    assert st["intent"] is Intent.tra_cuu
    assert st["traces"]["route_ep_meta"] is False
    assert st["traces"]["route_ep_luat"] is (y_dinh != "tra_cuu")


@pytest.mark.parametrize(
    "cau",
    [
        "tôi mới dùng lần đầu, bạn làm được những gì?",
        "tôi đang hỏi bạn là ai mà",
        "câu hỏi của tôi là: bạn làm được gì",
        "tôi đang cần bạn giúp, bạn là ai vậy",
        "tôi vừa đăng ký tài khoản, KLAW hỗ trợ gì",
    ],
)
def test_ngoi_thu_nhat_khong_co_su_viec_van_la_cau_hoi_meta(cau, tmp_path):
    """Review 2026-09-30: first-person time words alone ("tôi đang/mới/vừa",
    "của tôi") vetoed a correct meta verdict and sent these to retrieval — the
    2026-09-16 failure class. Only a legal event or legal content vetoes."""
    assert not gt.ke_tinh_huong(cau)
    st = _route(cau, "gioi_thieu", tmp_path)
    assert st["intent"] is Intent.gioi_thieu and st["traces"]["route_ep_luat"] is False
    st = _route(cau, "tra_cuu", tmp_path)
    assert st["intent"] is Intent.gioi_thieu and st["traces"]["route_ep_meta"] is True


@pytest.mark.parametrize(
    "cau",
    [
        "tôi đang tranh chấp đất với hàng xóm, bạn có những bộ luật nào",
        "những bộ luật nào áp dụng khi bị sa thải",
        "cần nắm những lĩnh vực pháp luật gì khi mở công ty",
        "có bao nhiêu văn bản hướng dẫn luật đất đai",
        "những bộ luật gì quy định về thừa kế",
        "hợp đồng của tôi có những lĩnh vực pháp luật nào liên quan",
    ],
)
def test_nhanh_meta_can_neo_klaw_va_khong_ke_tinh_huong(cau):
    assert not gt.chac_chan_meta(cau)


@pytest.mark.parametrize(
    "cau",
    [
        LAM_GI_LA_AI,
        "bạn là ai",
        "bạn có những bộ luật nào",
        "kho có những lĩnh vực gì",
        "KLAW có bao nhiêu văn bản",
        "trợ lý có những lĩnh vực pháp luật nào",
    ],
)
def test_cau_goi_thang_klaw_hay_kho_van_bi_ep_meta(cau, tmp_path):
    assert gt.chac_chan_meta(cau)
    st = _route(cau, "tra_cuu", tmp_path)
    assert st["intent"] is Intent.gioi_thieu and st["traces"]["route_ep_meta"] is True


def test_giup_toi_duoc_chu_giu_phan_quyet_cua_router(tmp_path):
    """No situation, no legal content: the router's gioi_thieu stands."""
    assert not gt.ke_tinh_huong(GIUP)
    st = _route(GIUP, "gioi_thieu", tmp_path)
    assert st["intent"] is Intent.gioi_thieu and st["traces"]["route_ep_luat"] is False


def test_khia_canh_bo_luat_chi_khi_hoi_klaw_co_gi():
    assert "bo_luat" not in gt.khia_canh("cần nắm rõ những bộ luật gì")
    assert "bo_luat" not in gt.khia_canh("Bộ luật Hàng hải có hiệu lực không")
    assert gt.khia_canh("bạn có những bộ luật nào") == ["bo_luat"]
    assert gt.khia_canh("hiện có bao nhiêu bộ luật") == ["bo_luat"]


# ══ Item 1, 6 — the fact sheet ═══════════════════════════════════════════════


def test_bang_du_kien_dung_tu_du_lieu_he_thong():
    bang = gt.bang_du_kien("bạn là ai", KHO)
    toan = "\n".join(bang.values())
    assert "pháp luật Việt Nam" in bang["vai_tro"] and "sâu nhất ở pháp luật lao động" in bang["vai_tro"]
    # Real counts: 4 shown documents, 3 with full text.
    assert "4 văn bản" in bang["pham_vi"] and "3 văn bản" in bang["pham_vi"]
    assert "Lao động - Thương binh và Xã hội (2 văn bản)" in bang["linh_vuc"]
    # Model names from config, with their roles.
    for ten in (router_model(), generate_model(), judge_model()):
        assert ten in bang["model"]
    # Every registered khuôn mẫu type is named.
    for loai in khuon_mau.cac_loai():
        assert khuon_mau.nap(loai)["ten"] in bang["soan_thao"]
    assert ".docx" in bang["viec"] and "PDF" in bang["viec"] and "rà soát" in bang["viec"].lower()
    assert "không phải luật sư" in bang["ban_chat"]
    # No labour-only copy, no "kho", no "mình".
    assert "chỉ lao động" not in toan and "lao động Việt Nam và soạn" not in toan
    assert not gt._RE_CHU_KHO.search(toan)
    assert " mình " not in f" {toan.lower()} "


def test_bang_khong_co_so_lieu_khi_chua_nap_duoc_van_ban():
    bang = gt.bang_du_kien("bạn có những bộ luật nào", None)
    assert "pham_vi" not in bang and "bo_luat" not in bang
    assert gt.THIEU_KHO in gt.cau_gioi_thieu("bạn có những bộ luật nào")


# ══ Item 1 — one model-written block, checked against the sheet ══════════════


def test_cau_hoi_ve_klaw_la_mot_luot_model_viet_tu_bang():
    viet = (
        "Tôi là KLAW, trợ lý AI tra cứu pháp luật Việt Nam, sâu nhất ở pháp luật lao động.\n\nBạn đang gặp chuyện gì?"
    )
    llm = LlmViet(viet)
    st = _meta(LAM_GI_LA_AI, llm)
    assert st["result_type"] is ResultType.gioi_thieu
    assert st["answer"] == viet
    assert len(llm.prompts) == 1
    p = llm.prompts[0]
    assert LAM_GI_LA_AI in p, "the model answers the question as typed"
    assert gt.bang_du_kien(LAM_GI_LA_AI, KHO)["soan_thao"] in p
    assert st["traces"]["assemble_token_in"] == 40 and st["traces"]["gioi_thieu_nguon"] == "llm"


def test_prompt_mang_cau_go_va_cau_da_giai_nghia():
    llm = LlmViet("Được chứ. Bạn đang gặp chuyện gì?")
    _meta(
        "KLAW, bạn giúp tôi được chứ",
        llm,
        cau_hoi_goc=GIUP,
        cau_hoi_day_du="KLAW, bạn giúp tôi được chứ",
        lich_su=[{"cau_hoi": "chào", "tra_loi": "chào"}],
    )
    assert f"CÂU NGƯỜI DÙNG VỪA GÕ: {GIUP}" in llm.prompts[0]
    assert "KLAW, bạn giúp tôi được chứ" in llm.prompts[0]


def test_cau_nang_luc_bia_bi_bo_cau_duoc_bang_do_duoc_giu():
    llm = LlmViet(
        "Tôi tra cứu pháp luật kèm trích dẫn tới đúng điều, khoản.\n"
        "Tôi có thể gửi email nhắc lịch hầu tòa cho bạn.\n"
        "Tôi cũng có thể đại diện cho bạn ra tòa.\n"
        "Tôi không đại diện cho bạn tại tòa."
    )
    ans = _meta("bạn làm được gì", llm)["answer"]
    assert "Tôi tra cứu pháp luật kèm trích dẫn" in ans
    assert "email" not in ans and "có thể đại diện" not in ans
    assert "Tôi không đại diện cho bạn tại tòa." in ans


def test_so_lieu_va_loai_van_ban_bia_bi_bo():
    llm = LlmViet(
        "Tôi đọc được 5000 văn bản. Tôi đọc được 4 văn bản pháp luật Việt Nam. "
        "Tôi soạn được đơn xin visa du lịch. Tôi soạn được đơn khởi kiện."
    )
    ans = _meta("bạn có bao nhiêu văn bản và soạn được gì", llm)["answer"]
    assert "5000" not in ans and "visa" not in ans
    assert "Tôi đọc được 4 văn bản pháp luật Việt Nam." in ans and "Tôi soạn được đơn khởi kiện." in ans


def test_khong_con_cau_nao_thi_ve_cau_du_phong_tu_bang():
    st = _meta("bạn là ai", LlmViet("Tôi có thể gửi email cho luật sư của bạn."))
    bang = gt.bang_du_kien("bạn là ai", KHO)
    assert st["answer"].startswith(bang["vai_tro"])
    assert st["traces"]["gioi_thieu_nguon"] == "du_phong"


def test_model_loi_thi_ve_cau_du_phong_khong_no():
    st = _meta("bạn là ai", LlmHong())
    assert st["result_type"] is ResultType.gioi_thieu and st["answer"]
    assert st["traces"]["gioi_thieu_nguon"] == "loi"


def test_khong_cau_nao_lap_lai():
    cau = "Tôi là KLAW, trợ lý AI tra cứu pháp luật Việt Nam."
    ans = _meta(LAM_GI_LA_AI, LlmViet(f"{cau}\n\n{cau}\n\n- {cau}"))["answer"]
    assert ans.count(cau) == 1


def test_chu_kho_chi_khi_hoi_ve_van_ban():
    ans = _meta("bạn là ai", LlmViet("Kho của tôi có 4 văn bản. Tôi là KLAW."))["answer"]
    assert "Kho" not in ans and "Tôi là KLAW." in ans
    ans = _meta("kho có bao nhiêu văn bản", LlmViet("Kho hiện có 4 văn bản."), intent="hoi_ve_kho")["answer"]
    assert "Kho hiện có 4 văn bản." in ans


def test_cau_gioi_han_chi_di_voi_cau_hoi_so_lieu_van_ban():
    ans = _meta("bạn là ai", LlmViet("Tôi là KLAW."))["answer"]
    assert CAU_GIOI_HAN not in ans
    ans = _meta(
        "có bao nhiêu văn bản", LlmViet("Tôi đọc được 4 văn bản.\n\nBạn muốn xem lĩnh vực nào?"), intent="hoi_ve_kho"
    )["answer"]
    assert ans.count(CAU_GIOI_HAN) == 1
    assert ans.endswith("Bạn muốn xem lĩnh vực nào?"), "the invitation stays last"


@pytest.mark.parametrize("llm", [LlmViet("Tôi có Luật Nhà ở số 27/2023/QH15."), LlmHong()])
def test_tra_so_hieu_khong_mang_cau_gioi_han(llm):
    """Item 5 with the kho rule (`kho.dung_cau_tra_loi`): a number lookup already
    says whether the document is held — it is not a document-count answer, on the
    model path or the fallback."""
    ans = _meta("có luật nhà ở 27/2023/QH15 không", llm, intent="hoi_ve_kho")["answer"]
    assert "27/2023/QH15" in ans
    assert CAU_GIOI_HAN not in ans


def _giu(cau_hoi: str, cau: str, kho=KHO) -> bool:
    """Does the sheet check keep this one model sentence?"""
    bang = gt.bang_du_kien(cau_hoi, kho)
    van_ban = gt.van_ban_cua_bang(bang, kho) if kho is not None else {}
    return bool(gt.loc_theo_bang(cau, bang, cho_phep_kho=True, van_ban=van_ban))


@pytest.mark.parametrize(
    "cau",
    [
        # Counts must match the noun they count (sheet: 4 shown, 3 full text, 1 Bộ luật).
        "Tôi hiện có 2 Bộ luật: Lao động và Dân sự.",
        "Tôi hiện có ba Bộ luật.",
        "Tôi đọc được 4 văn bản có toàn văn.",
        "Tôi đọc được 3 văn bản pháp luật, 4 văn bản có toàn văn.",
        # Identity and limits the sheet contradicts.
        "Tôi là luật sư AI của bạn.",
        "Câu trả lời của tôi có giá trị pháp lý như ý kiến luật sư.",
        "Dữ liệu của tôi luôn là bản hợp nhất mới nhất.",
        "Tôi cam kết bạn sẽ không mất quyền lợi.",
        # Vendors and models the config does not name.
        "Tôi chạy trên GPT-4 của OpenAI.",
        "Tôi dùng model Claude của Anthropic.",
        "Tôi dùng Gemini 2.5 Pro để hành văn.",
        # Capabilities the sheet does not list; KLAW as the actor of advice.
        "Tôi sẽ nhắc bạn khi sắp hết thời hiệu khởi kiện.",
        "Tôi lưu trữ hồ sơ vĩnh viễn.",
        "Bạn nên để tôi đại diện cho bạn ra tòa.",
        # A list item after a positive clause borrows no negation.
        "Tôi tra cứu luật, đại diện cho bạn tại tòa.",
    ],
)
def test_cau_bang_khong_do_bi_bo(cau):
    """Review 2026-09-30, probes against the real sheet: every one was kept."""
    assert not _giu("bạn là ai, có bao nhiêu văn bản", cau)


@pytest.mark.parametrize(
    "cau",
    [
        "Tôi đọc được 4 văn bản pháp luật Việt Nam, trong đó 3 văn bản có toàn văn.",
        "Tôi hiện có 1 Bộ luật: Lao động.",
        "Tôi không phải luật sư, và câu trả lời của tôi không thay thế tư vấn của luật sư.",
        "Tôi đọc bản gốc, không phải bản hợp nhất.",
        f"Tôi hành văn bằng {generate_model()}.",
        "Tôi nhớ các lượt trước trong cùng cuộc trò chuyện.",
        "Việc quan trọng thì bạn nên hỏi thêm luật sư.",
        "Tôi không phải luật sư, thẩm phán hay cơ quan nhà nước.",
    ],
)
def test_cau_bang_do_duoc_van_giu(cau):
    assert _giu("bạn là ai, có bao nhiêu văn bản", cau)


KHO_TEN_TRUNG_VIEC = [
    *KHO,
    _vb("65/2006/QH11", "Luật Luật sư số 65/2006/QH11", linh_vuc="Tư pháp"),
    _vb("100/2024/NĐ-CP", "Nghị định 100/2024/NĐ-CP về cấp Giấy chứng nhận và bảo đảm", loai="Nghị định"),
    _vb("01/2020/VBHN", "Văn bản hợp nhất 01/2020", loai="Văn bản hợp nhất", depth="shallow"),
]


@pytest.mark.parametrize(
    "cau_hoi",
    [
        "bạn là ai",
        "kho có bao nhiêu văn bản",
        "có luật luật sư 65/2006 không",
        "có nghị định 100/2024 không",
        "có nghị định 102/2024 và 01/2020 không",
        "model của bạn là gì",
        "bạn soạn được gì",
    ],
)
def test_moi_cau_cua_bang_qua_duoc_phep_loc(cau_hoi):
    """The check never drops the sheet's own sentences — titles that carry claim
    words ("Luật Luật sư", "Giấy chứng nhận", "Văn bản hợp nhất") and the negated
    list "không phải luật sư, thẩm phán hay…" included (self-check on the real
    sheet, 2026-09-30: 16 sentences lost before the verbatim window)."""
    bang = gt.bang_du_kien(cau_hoi, KHO_TEN_TRUNG_VIEC)
    van_ban = gt.van_ban_cua_bang(bang, KHO_TEN_TRUNG_VIEC)
    for dong in "\n".join(bang.values()).splitlines():
        for cau in gt._RE_CAU.split(dong.strip().removeprefix("- ").strip()):
            if cau:
                # `**` is stripped by design (the UI does not render markdown).
                assert gt.loc_theo_bang(cau, bang, cho_phep_kho=True, van_ban=van_ban) == cau.replace("**", ""), cau


KHO_DAT = [
    *KHO,
    {
        **_vb("101/2024/NĐ-CP", "Nghị định 101/2024/NĐ-CP", loai="Nghị định", depth="shallow", linh_vuc="Đất đai"),
        "hien": False,
        "cau_an": "Nghị định số 101/2024/NĐ-CP hiện chưa có trong phạm vi tra cứu.",
    },
]


@pytest.mark.parametrize(
    ("cau_hoi", "cau", "giu"),
    [
        # Absent: a yes answer is flipped.
        ("bạn có nghị định 102/2024 không", "Có, tôi có Nghị định 102/2024/NĐ-CP với đầy đủ toàn văn.", False),
        ("bạn có nghị định 102/2024 không", "Tôi không có văn bản nào mang số hiệu 102/2024.", True),
        # Shallow: full text is not claimed, in the same sentence or the next.
        ("có luật nhà ở 27/2023/QH15 không", "Tôi có toàn văn Luật Nhà ở số 27/2023/QH15.", False),
        (
            "có luật nhà ở 27/2023/QH15 không",
            "Tôi có Luật Nhà ở số 27/2023/QH15. Văn bản này có toàn văn, tra được tới từng điều.",
            False,
        ),
        ("có luật nhà ở 27/2023/QH15 không", "Tôi có Luật Nhà ở số 27/2023/QH15 nhưng chưa có toàn văn.", True),
        # Deep: absence and shallowness are not claimed.
        ("có luật đất đai 31/2024 không", "Tôi có toàn văn Luật Đất đai số 31/2024/QH15.", True),
        ("có luật đất đai 31/2024 không", "Tôi không có Luật Đất đai số 31/2024/QH15.", False),
        # Hidden: not shown, so not "có".
        ("có nghị định 101/2024 không", "Tôi có Nghị định 101/2024/NĐ-CP.", False),
        ("có nghị định 101/2024 không", "Nghị định 101/2024/NĐ-CP hiện chưa có trong phạm vi tra cứu.", True),
        # A document number the sheet never names.
        ("có luật đất đai 31/2024 không", "Tôi cũng có Nghị định 102/2024/NĐ-CP.", False),
    ],
)
def test_so_hieu_khop_dong_kho(cau_hoi, cau, giu):
    """Review 2026-09-30: a paraphrased document lookup passed with its yes/no or
    its depth flipped. Every document number the model names is checked against
    the kho row: present and shown, and at the depth claimed."""
    ans = gt.loc_theo_bang(
        cau,
        gt.bang_du_kien(cau_hoi, KHO_DAT),
        cho_phep_kho=True,
        van_ban=gt.van_ban_cua_bang(gt.bang_du_kien(cau_hoi, KHO_DAT), KHO_DAT),
    )
    assert (ans == cau) is giu, ans


def test_tra_cuu_so_hieu_qua_do_thi_lat_co_khong_ve_cau_du_phong(monkeypatch):
    """End to end: the node hands the kho facts to the check; a flipped lookup
    falls back to the deterministic kho row."""
    llm = LlmDoThi("hoi_ve_kho", tra_loi="Có, tôi có Nghị định 102/2024/NĐ-CP với đầy đủ toàn văn.")
    st = _do_thi(monkeypatch, llm).invoke({"query": "bạn có nghị định 102/2024 không"})
    assert st["result_type"] is ResultType.hoi_ve_kho
    assert st["answer"].startswith("Tôi không có văn bản nào mang số hiệu 102/2024.")
    assert st["traces"]["gioi_thieu_nguon"] == "du_phong"


def test_khong_url_khong_markdown():
    ans = _meta(
        "model của bạn là gì", LlmViet(f"Tôi dùng **{generate_model()}** để hành văn. Xem https://openrouter.ai nhé.")
    )["answer"]
    assert "**" not in ans and "http" not in ans and generate_model() in ans


# ══ The four real questions through the real graph ═══════════════════════════


class LlmDoThi:
    """Router, giai_nghia and meta writer in one double; any other call fails."""

    def __init__(self, intent: str, day_du: str | None = None, tra_loi: str = "Tôi là KLAW."):
        self.intent, self.day_du, self.tra_loi, self.meta = intent, day_du, tra_loi, []

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        props = (json_schema or {}).get("properties", {})
        if "intent" in props:
            return json.dumps(
                {
                    "intent": self.intent,
                    "loai_van_ban": "khong_ro",
                    "thay_the": [],
                    "ly_do": "",
                    "dang_tra_loi": "van_xuoi",
                    "y_dinh_phu": "khong",
                }
            ), Usage(1, 1, 0.0)
        if "cau_hoi_day_du" in props:
            return json.dumps({"cau_hoi_day_du": self.day_du, "ly_do": ""}), Usage(1, 1, 0.0)
        if "tra_loi" in props:
            self.meta.append(messages[-1]["content"])
            return json.dumps({"tra_loi": self.tra_loi}), Usage(40, 20, 0.0)
        raise AssertionError(f"unexpected model call: {sorted(props)}")


def _do_thi(monkeypatch, llm):
    from src.agents import graph_tra_cuu as g

    monkeypatch.setattr(g, "get_engine", lambda: None)
    monkeypatch.setattr(g, "llm_from_settings", lambda: llm)
    monkeypatch.setattr(g, "embedder_from_settings", lambda: None)
    monkeypatch.setattr(g, "Retriever", lambda *a, **k: None)
    monkeypatch.setattr(g, "nap_kho", lambda engine, as_of: KHO)
    return g.build_graph_tra_cuu()


@pytest.mark.parametrize("cau", [LAM_GI_LA_AI, LA_AI])
def test_lam_duoc_gi_la_ai_mot_khoi_model_viet(monkeypatch, cau):
    llm = LlmDoThi("tra_cuu", tra_loi="Tôi là KLAW, trợ lý AI tra cứu pháp luật Việt Nam.")
    st = _do_thi(monkeypatch, llm).invoke({"query": cau})
    assert st["result_type"] is ResultType.gioi_thieu
    assert st["answer"] == "Tôi là KLAW, trợ lý AI tra cứu pháp luật Việt Nam."
    assert len(llm.meta) == 1 and st["traces"]["route_ep_meta"] is True
    assert set(st["traces"]["gioi_thieu_khia_canh"]) == {"nang_luc", "danh_tinh"}
    assert st["hien_cau_hoi_day_du"] is False


def test_giup_toi_duoc_chu_luot_noi_tiep_khong_hien_cau_da_hieu(monkeypatch):
    llm = LlmDoThi(
        "gioi_thieu", day_du="KLAW, bạn giúp tôi được chứ", tra_loi="Được chứ. Bạn kể tôi nghe chuyện bạn đang gặp nhé?"
    )
    st = _do_thi(monkeypatch, llm).invoke({"query": GIUP, "lich_su": [{"cau_hoi": "chào", "tra_loi": "Chào bạn."}]})
    assert st["result_type"] is ResultType.gioi_thieu
    assert st["answer"] == "Được chứ. Bạn kể tôi nghe chuyện bạn đang gặp nhé?"
    assert f"CÂU NGƯỜI DÙNG VỪA GÕ: {GIUP}" in llm.meta[0]
    assert st["hien_cau_hoi_day_du"] is False


# ══ Item 8 — the echo line and the trace fields ═══════════════════════════════


def test_doi_nghia_chi_khi_cau_viet_lai_them_noi_dung():
    assert not doi_nghia(GIUP, "KLAW, bạn giúp tôi được chứ")
    assert not doi_nghia("tien luong toi thieu", "tiền lương tối thiểu")
    assert not doi_nghia("bạn là ai", "Bạn là ai?")
    assert doi_nghia("còn thử việc thì sao", "Thời gian thử việc tối đa theo Bộ luật Lao động là bao lâu")
    assert doi_nghia("liệt kê bảng cho tôi", "Liệt kê thời hạn báo trước khi nghỉ việc dưới dạng bảng")
    # Review 2026-09-30: a dropped qualifier changes the question too.
    assert doi_nghia("nghỉ việc khi đang thử việc có phải báo trước không", "Nghỉ việc có phải báo trước không?")
    assert doi_nghia(
        "người lao động nữ mang thai bị sa thải có được bồi thường không",
        "Người lao động bị sa thải có được bồi thường không",
    )
    # Accented words are not stoplist words: bán ≠ bạn, nhà ≠ nha, tội ≠ tôi.
    assert doi_nghia("thế thì sao", "Thế thì bán nhà có được không?")
    assert doi_nghia("có phạm không", "có phạm tội không")
    # Abbreviations spelled out are not a change.
    assert not doi_nghia("bạn giúp tôi đc ko", "KLAW, bạn giúp tôi được không?")
    assert not doi_nghia("ban giup toi duoc chu", "KLAW, bạn giúp tôi được chứ")


class LlmGiaiNghia:
    def __init__(self, day_du):
        self.day_du = day_du

    def chat(self, model, messages, json_schema=None):
        return json.dumps({"cau_hoi_day_du": self.day_du, "ly_do": ""}), Usage(1, 1, 0.0)


def test_giai_nghia_ghi_co_doi_nghia():
    lich_su = [{"cau_hoi": "tôi sắp nghỉ việc", "tra_loi": "…"}]
    st = giai_nghia({"query": GIUP, "lich_su": lich_su}, LlmGiaiNghia("KLAW, bạn giúp tôi được chứ"), "m")
    assert st["cau_hoi_doi_nghia"] is False
    st = giai_nghia(
        {"query": "còn thử việc thì sao", "lich_su": lich_su}, LlmGiaiNghia("Thời gian thử việc tối đa là bao lâu"), "m"
    )
    assert st["cau_hoi_doi_nghia"] is True


def test_dong_cau_da_hieu_khong_bao_gio_voi_cau_hoi_meta():
    assert assemble({"intent": "ngoai_pham_vi", "cau_hoi_doi_nghia": True}, {}, None, "")["hien_cau_hoi_day_du"]
    assert not assemble({"intent": "ngoai_pham_vi"}, {}, None, "")["hien_cau_hoi_day_du"]
    st = _meta("bạn là ai", LlmViet("Tôi là KLAW."), cau_hoi_doi_nghia=True)
    assert st["hien_cau_hoi_day_du"] is False


def test_co_hien_cau_da_hieu_di_ra_response():
    from src.api.routes import _payload_cache, tra_cuu_response

    st = assemble({"intent": "ngoai_pham_vi", "cau_hoi_doi_nghia": True, "cau_hoi_day_du": "câu"}, {}, None, "")
    res = tra_cuu_response(_payload_cache(st, "out_of_scope"), "t", "c")
    assert res.hien_cau_hoi_day_du is True and res.cau_hoi_day_du == "câu"
