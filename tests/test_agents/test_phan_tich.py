"""Phần "Phân tích cho tình huống của bạn" và "Nên đối chiếu thêm" (quyết định
2026-09-30 mục 3–4, plan `tra-loi-tu-nhien.md` N3).

Fake LLM, 0 lượt gọi thật. Câu tranh chấp nhà đất là câu chủ dự án đo trên app thật
(trace 88117154): câu kể tình huống của chính người hỏi nhận quy định có trích dẫn,
phần phân tích áp chúng vào tình huống, và văn bản cần mà chưa trích được nguyên văn.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from src.agents.nodes import assemble as m_assemble
from src.agents.nodes.assemble import (
    ANSWER_SCHEMA,
    PHAN_TICH_SCHEMA,
    PHAN_TICH_TIEU_DE,
    ResultType,
    assemble,
    loc_phan_tich,
)
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.hoi_lai import HOI_LAI_SCHEMA
from src.agents.nodes.suy_dien import ke_tinh_huong
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage

CAU_NHA_DAT = "tôi đang gặp sự cố tranh chấp nhà đất , cần nắm rõ những bộ luật gì để ko bị mất quyền lợi"
EFF = Effectivity(V.con_hieu_luc, "cao", "x")

_DAT = {
    "document_id": "177815",
    "so_ky_hieu": "31/2024/QH15",
    "ten": "Luật Đất đai số 31/2024/QH15",
    "loai_van_ban": "Luật",
    "link_vbpl": "https://vbpl.vn/van-ban/chi-tiet/177815",
}
DB = {
    235: {
        "id": 235,
        "cap": "dieu",
        "duong_dan": "31/2024/QH15 > Điều 235",
        **_DAT,
        "noi_dung": "Nhà nước khuyến khích các bên tranh chấp đất đai tự hòa giải…",
    },
    236: {
        "id": 236,
        "cap": "dieu",
        "duong_dan": "31/2024/QH15 > Điều 236",
        **_DAT,
        "noi_dung": "Tranh chấp đất đai đã được hòa giải tại Ủy ban nhân dân cấp xã mà không thành…",
    },
    237: {
        "id": 237,
        "cap": "dieu",
        "duong_dan": "31/2024/QH15 > Điều 237",
        **_DAT,
        "noi_dung": "Khiếu nại, khiếu kiện về quản lý đất đai…",
    },
}
CLAIM_HOA_GIAI = Claim(
    "Trước khi khởi kiện, tranh chấp đất đai phải được hòa giải tại Ủy ban nhân dân cấp xã.",
    235,
    "Tranh chấp đất đai mà các bên tranh chấp không hòa giải được thì gửi đơn đến Ủy ban nhân dân cấp xã"
    " nơi có đất tranh chấp để hòa giải",
)
CLAIM_THAM_QUYEN = Claim(
    "Hòa giải không thành thì Tòa án giải quyết tranh chấp khi đương sự có giấy chứng nhận.",
    236,
    "Tranh chấp đất đai mà đương sự có Giấy chứng nhận hoặc không có Giấy chứng nhận … thì do Tòa án giải quyết",
)
# Khẳng định tầng 2 bác — phần phân tích KHÔNG được thấy nó.
CLAIM_BI_BAC = Claim("Mọi khiếu nại đất đai được giải quyết trong 45 ngày.", 237, "Khiếu nại, khiếu kiện")

# Văn bản được hiện nhưng mới có tên (migration 016: một hàng `mo_dau`).
NHA_O = {
    "id": 900,
    "document_id": "169032",
    "cap": "mo_dau",
    "duong_dan": "27/2023/QH15 > Mở đầu",
    "so_ky_hieu": "27/2023/QH15",
    "ten": "Luật Nhà ở số 27/2023/QH15",
    "loai_van_ban": "Luật",
    "link_vbpl": "https://vbpl.vn/van-ban/chi-tiet/169032",
    "link_chinhphu": None,
}

DOAN_SACH = [
    "Chuyện của bạn là tranh chấp đất đai, nên bước đầu tiên là gửi đơn đề nghị Ủy ban nhân dân cấp xã"
    " nơi có đất tổ chức hòa giải, theo Điều 235 Luật Đất đai.",
    "Nếu hòa giải không thành, theo Điều 236 Luật Đất đai bạn đưa tranh chấp ra Tòa án khi có giấy"
    " chứng nhận. Bạn nên giữ lại giấy chứng nhận, hợp đồng và biên bản hòa giải.",
]


class FakeLlm:
    """Ghi schema VÀ prompt của từng lượt gọi — phần phân tích được canh cả trên thứ
    nó ĐƯỢC THẤY, không chỉ trên thứ nó viết ra."""

    def __init__(self, doan: list[str] | None = None, loi: bool = False) -> None:
        self.doan = DOAN_SACH if doan is None else doan
        self.loi = loi
        self.goi: list[tuple[dict | None, str]] = []

    def chat(self, model, messages, json_schema=None):
        self.goi.append((json_schema, messages[-1]["content"]))
        if json_schema is PHAN_TICH_SCHEMA:
            if self.loi:
                raise RuntimeError("provider 429")
            return json.dumps({"doan": self.doan}), Usage(10, 20, 0.001)
        if json_schema is HOI_LAI_SCHEMA:
            return json.dumps({"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}]}), Usage(1, 1, 0.0)
        return json.dumps(
            {
                "answer": "Chào bạn, tranh chấp của bạn phải qua hòa giải ở cấp xã trước"
                " [Điều 235](cite:1), rồi mới tới Tòa án [Điều 236](cite:2)."
            }
        ), Usage(1, 1, 0.0)

    def prompt_phan_tich(self) -> list[str]:
        return [p for s, p in self.goi if s is PHAN_TICH_SCHEMA]


def _st(query: str = CAU_NHA_DAT, **kw) -> dict:
    return {
        "intent": "tra_cuu",
        "query": query,
        "abstain_threshold": 0.5,
        "expanded": [DB[235], DB[236], DB[237]],
        "hits_shallow": [NHA_O],
        "tier1": [Tier1Result(c, True, R.ok, EFF) for c in (CLAIM_HOA_GIAI, CLAIM_THAM_QUYEN, CLAIM_BI_BAC)],
        "tier2": [Tier2Verdict(0, True, "ok"), Tier2Verdict(1, True, "ok"), Tier2Verdict(2, False, "không")],
        **kw,
    }


# ══ Câu kể tình huống ════════════════════════════════════════════════════════


def test_cau_tranh_chap_nha_dat_co_quy_dinh_trich_dan_phan_tich_va_doi_chieu_them():
    llm = FakeLlm()
    st = assemble(_st(), DB, llm, "m")

    assert st["result_type"] is ResultType.answer
    assert [c["duong_dan"] for c in st["citations"] if c["k"]] == ["31/2024/QH15 > Điều 235", "31/2024/QH15 > Điều 236"]
    assert st["phan_tich"] == {"tieu_de": PHAN_TICH_TIEU_DE, "doan": DOAN_SACH}
    assert PHAN_TICH_TIEU_DE == "Phân tích cho tình huống của bạn"
    assert st["doi_chieu_them"] == [
        {
            "so_ky_hieu": "27/2023/QH15",
            "ten_van_ban": "Luật Nhà ở số 27/2023/QH15",
            "lien_ket": "https://vbpl.vn/van-ban/chi-tiet/169032",
        }
    ]

    # Phần phân tích thấy ĐÚNG hai căn cứ đã qua hai tầng và câu hỏi — không thấy
    # khẳng định tầng 2 đã bác.
    (prompt,) = llm.prompt_phan_tich()
    assert CLAIM_HOA_GIAI.text in prompt and CLAIM_THAM_QUYEN.text in prompt
    assert CLAIM_HOA_GIAI.quote in prompt and "31/2024/QH15 > Điều 236" in prompt
    assert CLAIM_BI_BAC.text not in prompt and "Điều 237" not in prompt
    assert "tranh chấp nhà đất" in prompt

    # Tiền của lượt phân tích vào CÙNG `usage` của assemble — trần chi phí ngày đọc nó.
    assert st["traces"]["assemble_token_in"] == 11 and st["traces"]["assemble_token_out"] == 21
    assert st["traces"]["assemble_phan_tich"] == {"nguon": "llm", "bi_bo": []}


def test_cau_hoi_dinh_nghia_khong_co_phan_tich_va_khong_goi_them_luot_nao():
    llm = FakeLlm()
    st = assemble(_st("Hòa giải tranh chấp đất đai tại Ủy ban nhân dân cấp xã là gì?"), DB, llm, "m")
    assert st["result_type"] is ResultType.answer
    assert st.get("phan_tich") is None
    assert llm.prompt_phan_tich() == []
    assert [s for s, _ in llm.goi] == [ANSWER_SCHEMA]
    assert st["traces"]["assemble_phan_tich"] == {"nguon": "bo_qua", "bi_bo": []}


@pytest.mark.parametrize(
    "cau",
    [
        CAU_NHA_DAT,
        "Tôi bị công ty nợ lương 3 tháng thì phải làm sao",
        "Công ty tôi muốn sa thải nhân viên đi muộn nhiều lần",
        "em mới đi làm được 2 tháng, nghỉ việc có phải báo trước không",
        "Tôi muốn ly hôn thì cần làm thủ tục gì",
    ],
)
def test_ke_tinh_huong_nhan_ra_cau_ke_chuyen_cua_chinh_nguoi_hoi(cau):
    assert ke_tinh_huong(cau)


@pytest.mark.parametrize(
    "cau",
    [
        "Hòa giải tranh chấp đất đai là gì?",
        "Cho tôi hỏi thời gian thử việc tối đa là bao lâu?",
        "Tôi muốn biết thủ tục ly hôn gồm những bước nào",
        "Thẩm quyền giải quyết tranh chấp đất đai thuộc cơ quan nào",
    ],
)
def test_ke_tinh_huong_bo_qua_cau_hoi_chung_va_loi_mo_lich_su(cau):
    assert not ke_tinh_huong(cau)


# ══ Phép lọc: phần phân tích không nêu quy định nào ngoài căn cứ ══════════════


def test_phan_tich_neu_dieu_ngoai_can_cu_bi_cat_khoi_cau_tra_loi():
    llm = FakeLlm(doan=[DOAN_SACH[0], "Theo Điều 999 Luật Đất đai, bạn được đền bù gấp đôi giá đất."])
    st = assemble(_st(), DB, llm, "m")
    assert st["result_type"] is ResultType.answer, "phép lọc cắt câu, không hạ cả câu trả lời"
    assert st["phan_tich"]["doan"] == [DOAN_SACH[0]]
    assert st["traces"]["assemble_phan_tich"]["bi_bo"] == ["dieu:999"]


def test_phan_tich_bi_loc_sach_thi_khong_co_phan_tich():
    llm = FakeLlm(doan=["Pháp luật bắt buộc bạn hòa giải trước khi khởi kiện."])
    st = assemble(_st(), DB, llm, "m")
    assert st["result_type"] is ResultType.answer
    assert st.get("phan_tich") is None
    assert st["traces"]["assemble_phan_tich"] == {"nguon": "rong", "bi_bo": ["khong_dan_dieu"]}


def test_phan_tich_loi_provider_khong_lam_hong_cau_tra_loi_da_kiem():
    st = assemble(_st(), DB, FakeLlm(loi=True), "m")
    assert st["result_type"] is ResultType.answer and st["citations"]
    assert st.get("phan_tich") is None
    assert st["traces"]["assemble_phan_tich"]["nguon"] == "loi"


CAN_CU = [
    {
        "duong_dan": "31/2024/QH15 > Điều 235",
        "so_ky_hieu": "31/2024/QH15",
        "quote": "gửi đơn đến Ủy ban nhân dân cấp xã nơi có đất tranh chấp để hòa giải",
    },
    {
        "duong_dan": "31/2024/QH15 > Điều 236 > Khoản 1",
        "so_ky_hieu": "31/2024/QH15",
        "quote": "thời hạn hòa giải không quá 30 ngày",
    },
]
CHU_CAN_CU = " ".join(c["quote"] for c in CAN_CU)


@pytest.mark.parametrize(
    ("cau", "ly_do"),
    [
        ("Theo Điều 999 Luật Đất đai, bạn được bồi thường.", "dieu:999"),
        ("Nghị định 102/2024/NĐ-CP hướng dẫn thủ tục này theo Điều 235.", "so_hieu:102/2024"),
        ("Theo Điều 236 Luật Đất đai, bạn có 45 ngày để khởi kiện.", "moc:45 ngày"),
        ("Pháp luật bắt buộc bạn hòa giải trước.", "khong_dan_dieu"),
        ("Ủy ban nhân dân cấp xã có trách nhiệm tổ chức hòa giải.", "khong_dan_dieu"),
        ("Theo Điều 236, bạn chắc chắn thắng kiện.", "phan_quyet:chắc chắn thắng"),
        ("Xem [Điều 235](cite:1) để rõ hơn.", "the_url"),
        ("Đọc thêm tại https://vbpl.vn theo Điều 235.", "the_url"),
    ],
)
def test_loc_phan_tich_bo_dung_cau_vuot_can_cu(cau, ly_do):
    giu, bo = loc_phan_tich([f"Bạn nên giữ lại biên bản hòa giải. {cau}"], CAN_CU, CHU_CAN_CU)
    assert giu == ["Bạn nên giữ lại biên bản hòa giải."]
    assert bo == [ly_do]


def test_loc_phan_tich_giu_cau_dan_dung_dieu_va_moc_co_trong_can_cu():
    doan = [
        "Theo khoản 1 Điều 236 Luật Đất đai, việc hòa giải không quá 30 ngày.",
        "Bạn nên chụp lại giấy tờ nhà đất và giữ bản gốc.",
    ]
    assert loc_phan_tich(doan, CAN_CU, CHU_CAN_CU) == (doan, [])


# ══ "Nên đối chiếu thêm" — chỉ văn bản ĐƯỢC HIỆN ═════════════════════════════


def test_doi_chieu_them_gop_theo_van_ban_va_toi_da_ba():
    nong = [NHA_O, {**NHA_O, "id": 901}]
    for i, so in enumerate(("100/2024/NĐ-CP", "151/2025/NĐ-CP", "88/2024/NĐ-CP")):
        nong.append(
            {
                **NHA_O,
                "id": 910 + i,
                "document_id": f"d{i}",
                "so_ky_hieu": so,
                "ten": f"Nghị định số {so}",
                "link_vbpl": None,
            }
        )
    st = assemble(_st(hits_shallow=nong), DB, FakeLlm(), "m")
    assert [d["so_ky_hieu"] for d in st["doi_chieu_them"]] == ["27/2023/QH15", "100/2024/NĐ-CP", "151/2025/NĐ-CP"]
    assert st["doi_chieu_them"][1]["lien_ket"] is None, "không có link đã kiểm thì không bịa link"


def test_khong_van_ban_nong_thi_doi_chieu_them_rong():
    st = assemble(_st(hits_shallow=[]), DB, FakeLlm(), "m")
    assert st["doi_chieu_them"] == []


# ══ Không chữ "kho" trong câu trả lời pháp lý ══════════════════════════════════

_RE_KHO = re.compile(r"\bkho\b", re.IGNORECASE)


def _chuoi(x: object) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for v in x.values() for s in _chuoi(v)]
    if isinstance(x, (list, tuple, frozenset, set)):
        return [s for v in x for s in _chuoi(v)]
    return []


def chuoi_trong_ma(ma: str) -> list[str]:
    """Mọi chuỗi ký tự trong mã — kể cả phần chữ của f-string trong thân hàm — bỏ
    docstring. Cùng cách `test_gioi_thieu.test_Q1_…` quét giọng xưng hô."""
    cay = ast.parse(ma)
    doc = {
        id(n.body[0].value)
        for n in ast.walk(cay)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    return [
        n.value for n in ast.walk(cay) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc
    ]


# Lời của câu trả lời pháp lý, ngõ cụt và bản thảo. `gioi_thieu.py` đứng ngoài: câu
# hỏi về KLAW được gọi tên kho (CONTEXT.md "kho"), và nó mang khoá khía cạnh "kho".
MA_TRA_LOI_PHAP_LY = ("agents/nodes/assemble.py", "agents/nodes/hoi_lai.py", "services/hien_thi.py", "services/kho.py")


@pytest.mark.parametrize("duong", MA_TRA_LOI_PHAP_LY)
def test_loi_cho_nguoi_doc_khong_goi_ten_kho(duong):
    ma = (Path(m_assemble.__file__).resolve().parents[2] / duong).read_text(encoding="utf-8")
    assert [s for s in chuoi_trong_ma(ma) if _RE_KHO.search(s)] == []


def test_phep_quet_kho_bat_duoc_cau_ban_thao_cu():
    """Đối chứng âm: câu bản thảo trước quyết định 2026-09-30 phải bị phép quét bắt."""
    cu = """def f(x):\n    return f"Kho chưa có toàn văn {x}, nên các điều khoản chỉ dựa trên căn cứ"\n"""
    assert [s for s in chuoi_trong_ma(cu) if _RE_KHO.search(s)] == ["Kho chưa có toàn văn "]


def test_cau_tra_loi_phap_ly_va_ngo_cut_khong_goi_ten_kho():
    ra = [
        assemble(_st(), DB, FakeLlm(), "m"),
        assemble(
            _st(tier1=[Tier1Result(Claim("x", 999, "y"), False, R.provision_khong_ton_tai, None)], tier2=[]),
            DB,
            FakeLlm(),
            "m",
        ),
        assemble(_st(expanded=[]), DB, FakeLlm(), "m"),
    ]
    assert [r["result_type"] for r in ra] == [ResultType.answer, ResultType.abstain, ResultType.partial_coverage]
    for r in ra:
        for truong in ("answer", "coverage_note", "phan_tich", "doi_chieu_them", "warnings"):
            assert not [s for s in _chuoi(r.get(truong)) if _RE_KHO.search(s)], (r["result_type"], truong)


# ══ Biên HTTP ════════════════════════════════════════════════════════════════


def test_phan_tich_va_doi_chieu_them_song_qua_payload_cache_va_TraCuuResponse():
    from src.api.routes import _payload_cache, tra_cuu_response

    st = assemble(_st(), DB, FakeLlm(), "m")
    resp = tra_cuu_response(_payload_cache(st, "answer"), "t", "full")
    assert resp.phan_tich.tieu_de == PHAN_TICH_TIEU_DE and resp.phan_tich.doan == DOAN_SACH
    assert [d.so_ky_hieu for d in resp.doi_chieu_them] == ["27/2023/QH15"]
    # Dòng cache ghi trước bản này không có hai khoá.
    cu = {k: v for k, v in _payload_cache(st, "answer").items() if k not in ("phan_tich", "doi_chieu_them")}
    resp_cu = tra_cuu_response(cu, "t", "full")
    assert resp_cu.phan_tich is None and resp_cu.doi_chieu_them == []
