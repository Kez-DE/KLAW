"""Mặt TRẢ LỜI không được nói bằng giọng một hệ thống tự thuật về giới hạn của
mình.

ĐO ĐƯỢC 2026-09-02, câu "Hiện tại có bao nhiêu bộ luật?": `deep=30`,
`claims=0`, `result_type=abstain`, `answer=None`, `coverage_note=None`,
`nguon=[]` — người hỏi nhận một MÀN HÌNH TRẮNG. Khi truy hồi chạm tầng nông thì
thay vào đó là một danh sách văn bản kèm câu "Hệ thống KHÔNG diễn giải trong
trường hợp này — văn bản gốc được nêu đích danh dưới đây để bạn tự đối chiếu."
Cả hai đều đẩy việc suy luận về phía người hỏi.

## Vì sao MỘT danh sách cụm bị cấm, dùng cho CẢ HAI phía

Lời cũ bò về được theo hai đường (Python dựng chuỗi, TSX viết chuỗi tĩnh) và
một danh sách chép làm hai bản sẽ lệch pha đúng vào ngày ai đó thêm cụm thứ
tám. `CUM_BI_CAM` ở đây là bản duy nhất; test Python đọc thẳng file `.tsx` chứ
KHÔNG nhân bản danh sách sang một script `kiem-*.ts` thứ hai.

## Vì sao KHÔNG quét `BaoLoi.tsx` và `lib/api.ts`

Chúng nói về LỖI HẠ TẦNG — mạng đứt, timeout, 500, 429. Ở đó "Lỗi ở phía máy
chủ KLAW, không phải ở câu hỏi của bạn" là câu ĐÚNG PHẢI NÓI: người dùng cần
biết lỗi không do mình và nên thử lại. Xoá giọng "máy chủ" khỏi đó là làm tệ
hơn, nên chúng nằm NGOÀI phép quét này một cách có chủ ý.
"""

import re
from pathlib import Path

import pytest

from src.agents.nodes import assemble as m_assemble
from src.agents.nodes import gioi_thieu as m_gioi_thieu
from src.agents.nodes import hoi_lai as m_hoi_lai
from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.gioi_thieu import cau_gioi_thieu
from src.agents.nodes.hoi_lai import CAU_DAN
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage

# BẢN DUY NHẤT. Thêm cụm thì thêm ở đây, cả hai phía tự được canh.
CUM_BI_CAM = (
    "hệ thống",
    "không diễn giải",
    "chưa đủ căn cứ",
    "truy hồi",
    "database",
    "để bạn tự đối chiếu",
    "máy chủ trả về",
)

TSX = Path(__file__).resolve().parents[2] / "frontend/src/components/klaw/TheKetQua.tsx"
# Đổi tên `frontend-moi/` → `frontend/` (2026-09-02) làm hai test ở đây đỏ với
# một lỗi đọc file khó hiểu. Assert này biến lần sau thành một câu nói rõ.
assert TSX.exists(), f"không thấy {TSX} — thư mục frontend đã đổi tên?"

DB = {11: {"id": 11, "document_id": "139264", "cap": "dieu",
           "duong_dan": "45/2019/QH14 > Điều 26", "so_ky_hieu": "45/2019/QH14",
           "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}


class FakeLlm:
    def chat(self, model, messages, json_schema=None):
        return '{"chieu": [{"ma": "chu_the", "cau": "Bạn đang ở phía nào?"}]}', Usage(1, 1, 0.0)


def _cum_vuong(chu: str) -> list[str]:
    thap = chu.lower()
    return [c for c in CUM_BI_CAM if c in thap]


def _chuoi_trong(x: object) -> list[str]:
    """Chuỗi người dùng đọc được, gồm cả chuỗi nằm trong dict/list/tuple cấp
    module (`CANH_BAO_NHAN`, `CHIEU` — nhãn và câu hỏi thật, không phải hằng số
    trần)."""
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for v in x.values() for s in _chuoi_trong(v)]
    if isinstance(x, (list, tuple)):
        return [s for v in x for s in _chuoi_trong(v)]
    return []


# `m_gioi_thieu` có trong danh sách vì các hằng số lời tự giới thiệu ĐÃ CHUYỂN
# khỏi `assemble` sang đó 2026-09-02 (`GIOI_THIEU` → năm dạng). Thiếu nó, phép
# quét này lặng lẽ mất đúng những chuỗi nó vốn đang canh.
@pytest.mark.parametrize("mo_dun", [m_assemble, m_gioi_thieu, m_hoi_lai],
                         ids=["assemble", "gioi_thieu", "hoi_lai"])
def test_hang_so_cua_mo_dun_khong_mang_giong_he_thong(mo_dun):
    """Quét HẰNG SỐ THẬT qua `vars(module)`, không chép lại chuỗi cần tìm: một
    test liệt kê tay đúng những câu hôm nay có sẽ mù với câu thêm vào mai."""
    xau: dict[str, list[str]] = {}
    for ten, gia_tri in vars(mo_dun).items():
        if ten.startswith("__"):
            continue
        for chu in _chuoi_trong(gia_tri):
            if vuong := _cum_vuong(chu):
                xau[ten] = vuong
    assert xau == {}, f"hằng số mang giọng hệ thống: {xau}"


# ══ Mọi nhánh KHÔNG có câu trả lời — quét chính chuỗi người hỏi nhận ═════════
# Quét ĐẦU RA thay vì chỉ quét hằng số, vì phần lớn `coverage_note` được GHÉP
# lúc chạy: một cụm bị cấm chen vào giữa hai hằng số sạch vẫn tới màn hình.


def _ngo_cut() -> dict[str, dict]:
    eff = Effectivity(V.con_hieu_luc, "trung_binh", "x")
    t1_pass = Tier1Result(Claim("Ít nhất 85%.", 11, "85%"), True, R.ok, eff)
    t1_fail = Tier1Result(Claim("x", 999, "y"), False, R.provision_khong_ton_tai, None)
    eff_thay = Effectivity(V.bi_thay_the, "trung_binh",
                           "bị 74/2024/NĐ-CP thay thế từ 2024-07-01")
    t1_thay = Tier1Result(Claim("4.420.000 đồng.", 11, "85%"), True, R.ok, eff_thay)
    chung = {"intent": "tra_cuu", "query": "công ty trừ lương tôi có đúng không",
             "abstain_threshold": 0.5}
    return {
        "out_of_scope": {"intent": "ngoai_pham_vi", "query": "thuế TNCN tính sao"},
        "tien_de_sai": {**chung, "tien_de_sai": "Bộ luật Lao động không có Điều 999."},
        "partial_coverage": {**chung, "expanded": [], "hits_shallow": [
            {"id": 5, "document_id": "84265", "cap": "mo_dau",
             "duong_dan": "84/2015/QH13 > Mở đầu", "so_ky_hieu": "84/2015/QH13",
             "ten": "Luật An toàn, vệ sinh lao động"}]},
        "abstain_tro": {**chung, "expanded": [DB[11]], "tier1": [t1_fail], "tier2": []},
        "abstain_khong_nguon": {**chung, "expanded": [], "hits_shallow": [],
                                "insufficient_evidence": True},
        "abstain_moi_nguon_bi_thay": {**chung, "expanded": [DB[11]], "tier1": [t1_thay],
                                      "tier2": [Tier2Verdict(0, True, "ok")]},
        # 1/4 = 0,25 < ngưỡng 0,5 — nhánh TỈ LỆ, khác nhánh "không claim nào qua
        # tầng 1" ở trên; cả hai đều từng trả về một abstain trơ.
        "abstain_duoi_nguong": {**chung, "expanded": [DB[11]],
                                "tier1": [t1_pass, t1_fail, t1_fail, t1_fail],
                                "tier2": [Tier2Verdict(0, True, "ok")]},
    }


@pytest.mark.parametrize("ten", list(_ngo_cut()))
def test_moi_nhanh_ngo_cut_khong_mang_giong_he_thong(ten):
    st = assemble(_ngo_cut()[ten], DB, FakeLlm(), "m")
    assert st["result_type"] is not ResultType.answer, "fixture phải là một ngõ cụt"
    for truong in ("answer", "coverage_note"):
        chu = st.get(truong) or ""
        assert not _cum_vuong(chu), f"{ten}.{truong} mang {_cum_vuong(chu)}: {chu!r}"


@pytest.mark.parametrize("ten", [t for t in _ngo_cut() if t != "out_of_scope"])
def test_moi_abstain_va_partial_deu_co_HAI_NUA(ten):
    """Nửa đầu: cái đã biết (tên văn bản chi phối, hoặc nói thẳng là không tìm
    được gì). Nửa sau: đúng dữ kiện còn thiếu. Ngõ cụt cũ — một danh sách văn
    bản rồi hết — bị loại, nên KHÔNG nhánh nào được thiếu nửa sau.

    `out_of_scope` nằm ngoài: câu hỏi ở ngoài kho thì thêm dữ kiện tình huống
    cũng không đưa nó vào trong, và nhánh đó phải giữ 0 token.
    """
    st = assemble(_ngo_cut()[ten], DB, FakeLlm(), "m")
    ghi_chu = st["coverage_note"] or ""
    assert len(ghi_chu) > 80, f"{ten}: ngõ cụt trơ — {ghi_chu!r}"
    assert CAU_DAN in ghi_chu, f"{ten}: thiếu nửa sau (dữ kiện còn thiếu)"
    assert "\n- " in ghi_chu, f"{ten}: nửa sau không nêu chiều hỏi nào"


def test_out_of_scope_KHONG_hoi_lai_va_giu_0_token():
    """Mặt còn lại của trần chi phí: câu hỏi ngoài kho thì thêm dữ kiện tình
    huống cũng không đưa nó vào trong, nên nhánh này KHÔNG được sinh câu hỏi lại.

    Canh bằng SỰ VẮNG MẶT của khoá `assemble_hoi_lai`, không bằng một fake
    `raise`: `hoi_lai` bắt `Exception` để một ngõ cụt không thành HTTP 500, nên
    một fake nổ sẽ bị nuốt và phép canh thành lưới chết.
    """
    st = assemble({"intent": "ngoai_pham_vi", "query": "thuế TNCN tính sao"},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.out_of_scope
    assert "assemble_hoi_lai" not in st["traces"], "out_of_scope không được hỏi lại"
    assert st["traces"]["assemble_token_in"] == 0


# ══ Phía giao diện ═══════════════════════════════════════════════════════════


def _bo_chu_thich(src: str) -> str:
    """Gỡ `/* … */` và các dòng CHỈ CÓ `//`.

    Cố ý không gỡ `//` giữa dòng: một chuỗi `"https://…"` sẽ bị cắt làm đôi và
    phép quét thành mù với phần sau nó. Mọi chú thích `//` trong file này đều
    đứng riêng một dòng.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def test_the_ket_qua_khong_mang_giong_he_thong():
    goc = TSX.read_text(encoding="utf-8")
    ma = _bo_chu_thich(goc)
    # Tự kiểm phép quét: một bộ gỡ chú thích hỏng sẽ xoá sạch file và test
    # PASS mà không kiểm gì — đúng loại lỗi im lặng cả dự án chống.
    assert "KhayTrungTinh" in ma and "partial_coverage" in ma, "bộ gỡ chú thích ăn cả mã"
    assert len(ma) > len(goc) * 0.5

    xau = [(i, dong.strip()) for i, dong in enumerate(ma.splitlines(), 1)
           if _cum_vuong(dong)]
    assert xau == [], f"nhánh kết quả mang giọng hệ thống: {xau}"


def test_nhanh_khong_co_cau_tra_loi_van_hien_duoc_coverage_note_nhieu_doan():
    """`coverage_note` nay có HAI NỬA ngăn bằng dòng trắng và một danh sách
    gạch đầu dòng. Hiện nó trong đúng MỘT `<p>` thì hai nửa dính thành một câu
    dài và danh sách mất hẳn chấm đầu dòng — nên cả hai nhánh phải đi qua
    `KhoiVanXuoi` (`catDoan`), không phải `{ghiChuPhamVi}` trần.
    """
    ma = _bo_chu_thich(TSX.read_text(encoding="utf-8"))
    assert ma.count("<KhoiVanXuoi chu={ghiChuPhamVi}") == 2, (
        "nhánh abstain và partial_coverage phải cùng hiện coverage_note qua catDoan"
    )


# Dạng 3 (model nào / chạy bằng gì) được DỰNG LÚC CHẠY từ config, nên nó không
# phải một hằng số cấp module và phép quét `vars(...)` ở trên mù với nó. Quét
# chính ĐẦU RA của bộ chọn dạng, cùng lý do các nhánh ngõ cụt được quét ở đầu ra.
@pytest.mark.parametrize("cau_hoi", [
    "chào bạn", "bạn làm được những gì", "model của bạn là gì",
    "dữ liệu của bạn lấy từ đâu", "cảm ơn bạn",
])
def test_moi_dang_gioi_thieu_khong_mang_giong_he_thong(cau_hoi):
    chu = cau_gioi_thieu(cau_hoi)
    assert not _cum_vuong(chu), f"{cau_hoi!r} mang {_cum_vuong(chu)}: {chu!r}"
