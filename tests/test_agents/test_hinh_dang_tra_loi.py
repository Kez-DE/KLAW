"""Hình dạng câu trả lời — trần 4 gạch, trần 900 ký tự, 0 token.

ĐO ĐƯỢC trong chính repo này: các câu trả lời dài 1.600–3.400 ký tự với 10–21
trích dẫn. Một câu trả lời đúng luật mà phải cuộn ba màn hình thì người hỏi vẫn
không biết mình được phép làm gì.

Vì sao CẮT GẠCH chứ không cắt ký tự: cắt theo ký tự sẽ chặt đứt một thẻ
`[...](cite:n)` đang mở và biến một câu trả lời HỢP LỆ thành một câu có thẻ hỏng
— tệ hơn hẳn một câu dài. Nên trần ký tự chỉ GHI NHẬN vào `traces`, còn thứ thật
sự bị cắt là gạch cấp một thứ năm trở đi.

Vì sao 0 token: gọi lại mô hình để viết ngắn hơn là thêm một lượt gọi trong
đường thành công thường — `cai_thien.md` §11 cấm đúng điều đó.
"""

import json
from pathlib import Path

from src.agents.nodes.assemble import (
    ANSWER_SCHEMA,
    CON_Y_BI_CAT,
    MO_DAU_LUOT_DAU,
    TRAN_GACH,
    TRAN_KY_TU,
    ResultType,
    assemble,
    cat_gach_thua,
)
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage

DB = {11: {"id": 11, "document_id": "139264", "cap": "dieu",
           "duong_dan": "45/2019/QH14 > Điều 26", "so_ky_hieu": "45/2019/QH14",
           "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}


class LlmTra:
    """Trả đúng chuỗi đặt trước và GIỮ LẠI prompt đã nhận, để test đọc được lời
    mở mà `assemble` đã chọn — thứ không lộ ra ở kết quả."""

    def __init__(self, answer: str):
        self.answer = answer
        self.prompt = ""

    def chat(self, model, messages, json_schema=None):
        # Chỉ lượt HÀNH VĂN: câu kể tình huống còn một lượt phân tích sau nó.
        if json_schema is ANSWER_SCHEMA:
            self.prompt = "\n".join(m["content"] for m in messages)
        return json.dumps({"answer": self.answer}), Usage(1, 1, 0.0)


def _trang_thai(**them) -> dict:
    eff = Effectivity(V.con_hieu_luc, "trung_binh", "x")
    return {
        "intent": "tra_cuu",
        "query": "công ty trừ lương tôi có đúng không",
        "abstain_threshold": 0.5,
        "expanded": [DB[11]],
        "tier1": [Tier1Result(Claim("Ít nhất 85%.", 11, "85%"), True, R.ok, eff)],
        "tier2": [Tier2Verdict(0, True, "ok")],
        **them,
    }


# ══ Hàm thuần ═══════════════════════════════════════════════════════════════

def test_cat_gach_thua_giu_dung_tran_va_bao_so_da_bo():
    van = "Mở đầu.\n" + "\n".join(f"- gạch {i}" for i in range(1, 7))
    moi, bo = cat_gach_thua(van)
    assert bo == 2
    assert moi.count("\n- ") == TRAN_GACH
    assert "gạch 4" in moi and "gạch 5" not in moi


def test_cat_gach_thua_khong_dung_den_van_ban_du_tran():
    van = "Mở đầu.\n- một\n- hai\n- ba"
    assert cat_gach_thua(van) == (van, 0)


def test_cat_gach_thua_bo_ca_dong_long_cua_gach_bi_bo():
    van = "\n".join(["- một", "- hai", "- ba", "- bốn", "- năm", "  dòng lồng của năm"])
    moi, bo = cat_gach_thua(van)
    assert bo == 1
    assert "dòng lồng" not in moi
    assert moi.endswith("- bốn")


def test_cat_gach_thua_giu_dong_khong_phai_gach_nam_sau_cac_gach():
    van = "\n".join([f"- gạch {i}" for i in range(1, 7)] + ["Câu kết còn lại."])
    moi, _ = cat_gach_thua(van)
    assert moi.endswith("Câu kết còn lại.")


def test_cat_gach_thua_khong_cat_giua_cau():
    """Mọi dòng còn lại phải là NGUYÊN dòng gốc — không có dòng nào bị xén."""
    goc = ["- " + "x" * 400 for _ in range(6)]
    moi, _ = cat_gach_thua("\n".join(goc))
    assert all(dong in goc for dong in moi.split("\n"))


def test_cat_gach_thua_khong_nham_dau_gach_giua_cau_thanh_mot_gach():
    van = "Người lao động - theo Điều 26 - được biết lý do.\n- một\n- hai"
    assert cat_gach_thua(van) == (van, 0)


# ══ Qua `assemble` ══════════════════════════════════════════════════════════

def test_assemble_cat_gach_thu_nam_va_ghi_lai_so_da_cat():
    llm = LlmTra("Kết luận.\n" + "\n".join(f"- điều kiện {i}" for i in range(1, 7)))
    st = assemble(_trang_thai(), DB, llm, "m", prompt_path=Path("prompts/assemble.v3.md"))
    assert st["result_type"] == ResultType.answer
    assert st["answer"].count("\n- ") == TRAN_GACH
    assert st["traces"]["assemble_hinh_dang"]["gach_bo"] == 2
    # Chủ dự án 2026-09-30: phép cắt không bao giờ im lặng với người đọc.
    assert st["answer"].endswith(CON_Y_BI_CAT.format(so=2))


# ══ Liệt kê lấy từ MỘT Điều (chủ dự án 2026-09-30: "đủ danh sách") ══════════
# Replay trace c8a98c3d: danh sách 15 loại văn bản của Điều 4 (87/2025/QH15 Điều 1 khoản
# 1) bị trần 4 gạch cắt còn 4, không một chữ nào nói phần còn lại.

DB_DIEU = {
    i: {
        "id": i,
        "document_id": "175440",
        "cap": "khoan",
        "duong_dan": dd,
        "so_ky_hieu": "64/2025/QH15",
        "ten": "Luật Ban hành văn bản quy phạm pháp luật",
        "noi_dung": "…",
    }
    for i, dd in (
        (21, "64/2025/QH15 > Điều 4 > Khoản 1"),
        (22, "64/2025/QH15 > Điều 4 > Khoản 2"),
        (23, "64/2025/QH15 > Điều 5"),
    )
}


def _liet_ke(pids: list[int]) -> tuple[dict, str]:
    """`(kết quả, câu mô hình viết)`: một gạch mỗi claim, thẻ `cite` trỏ đúng claim đó."""
    eff = Effectivity(V.con_hieu_luc, "trung_binh", "x")
    viet = "Gồm:\n" + "\n".join(f"- loại {k} [Điều {5 if p == 23 else 4}](cite:{k})" for k, p in enumerate(pids, 1))
    st = assemble(
        {
            **_trang_thai(),
            "expanded": list(DB_DIEU.values()),
            "tier1": [Tier1Result(Claim(f"Loại {k}.", p, "…"), True, R.ok, eff) for k, p in enumerate(pids, 1)],
            "tier2": [Tier2Verdict(i, True, "ok") for i in range(len(pids))],
        },
        DB_DIEU,
        LlmTra(viet),
        "m",
        prompt_path=Path("prompts/assemble.v3.md"),
    )
    return st, viet


def test_liet_ke_moi_gach_dan_cung_mot_dieu_thi_khong_cat():
    """Khoản 1, khoản 2 của cùng Điều 4 là MỘT phép liệt kê — cũng như 15 mục trong một khoản."""
    st, viet = _liet_ke([21, 22, 21, 22, 21, 22])
    assert st["result_type"] == ResultType.answer
    assert st["answer"] == viet, "đủ 6 gạch, không thêm câu nào"
    hd = st["traces"]["assemble_hinh_dang"]
    assert hd["gach_bo"] == 0 and hd["mien_tran"] is True


def test_liet_ke_tu_hai_dieu_van_cat_va_noi_ra():
    st, _ = _liet_ke([21, 22, 23, 21, 22, 23])
    assert st["answer"].count("\n- ") == TRAN_GACH
    assert st["answer"].endswith(CON_Y_BI_CAT.format(so=2))
    assert st["traces"]["assemble_hinh_dang"]["mien_tran"] is False


def test_assemble_ghi_nhan_cau_vuot_tran_ky_tu_ma_khong_xen_chu():
    dai = "Kết luận. " + "chữ " * 300
    llm = LlmTra(dai)
    st = assemble(_trang_thai(), DB, llm, "m", prompt_path=Path("prompts/assemble.v3.md"))
    assert len(dai) > TRAN_KY_TU
    assert st["answer"] == dai, "vượt trần thì GHI NHẬN, không cắt"
    assert st["traces"]["assemble_hinh_dang"]["vuot_tran"] is True
    assert st["traces"]["assemble_hinh_dang"]["do_dai"] == len(dai)


def test_assemble_cau_dat_tran_khong_bi_danh_dau_vuot():
    llm = LlmTra("Kết luận ngắn.\n- một điều kiện")
    st = assemble(_trang_thai(), DB, llm, "m", prompt_path=Path("prompts/assemble.v3.md"))
    hd = st["traces"]["assemble_hinh_dang"]
    assert hd["vuot_tran"] is False and hd["gach_bo"] == 0


# ══ Lời mở ở phiên đã có ngữ cảnh ═══════════════════════════════════════════

def test_phien_co_tom_tat_nhung_lich_su_rong_thi_khong_chao_lai():
    """`graph_tra_cuu` đã coi `lich_su or tom_tat` là "phiên đã có ngữ cảnh"
    (điều kiện vào `giai_nghia`). Lời mở của `assemble` phải dùng cùng một định
    nghĩa, nếu không một phiên vừa bị rút gọn lịch sử sẽ bị chào lại như người lạ.
    """
    llm = LlmTra("Kết luận.")
    assemble(_trang_thai(tom_tat="người hỏi là người lao động", lich_su=[]), DB, llm, "m",
             prompt_path=Path("prompts/assemble.v3.md"))
    assert MO_DAU_LUOT_DAU not in llm.prompt


def test_phien_moi_hoan_toan_van_chao_dung_mot_lan():
    llm = LlmTra("Kết luận.")
    assemble(_trang_thai(), DB, llm, "m", prompt_path=Path("prompts/assemble.v3.md"))
    assert MO_DAU_LUOT_DAU in llm.prompt
