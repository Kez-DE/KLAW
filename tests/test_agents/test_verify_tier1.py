"""Test cho verify tầng 1 — phép kiểm trung tâm của khoá luận.

Fixture dùng SỐ LIỆU THẬT lấy từ DB (`klaw-p1-db-1`), không phải số bịa:

  141418  45/2019/QH14 > Điều 127            noi_dung CHỈ LÀ TIÊU ĐỀ
  141419/141420/141421  ... > Khoản 1/2/3    thân điều luật nằm ở đây
  146340  84/2015/QH13 > Điều 23 > Khoản 3 > Điểm b   "Không phát tiền thay cho..."

Cặp 141420 / 146340 là bằng chứng thật cho mức chuẩn hoá: "Phạt tiền" (Điều 127
CẤM phạt tiền người lao động) và "phát tiền" (Điều 23 nói về TRẢ tiền thay
trang cấp) chỉ khác nhau MỘT DẤU, và bỏ dấu thì trùng khít. Corpus có 705 dòng
"phạt tiền" và 1 dòng "phát tiền" — cả hai đều có thật.
"""

import ast
import inspect
import socket
import unicodedata
from datetime import date
from pathlib import Path

import pytest

from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import citation_precision, normalize, verify_tier1
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from tests.conftest import pid

# ── Fixture: Điều 26 (có thân trong chính noi_dung — 26,4% số Điều) ───────────
D26 = {"id": 11, "parent_id": None, "document_id": "139264",
       "duong_dan": "45/2019/QH14 > Điều 26",
       "noi_dung": "Tiền lương của người lao động trong thời gian thử việc do hai bên "
                   "thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó."}
D25 = {"id": 10, "parent_id": None, "document_id": "139264",
       "duong_dan": "45/2019/QH14 > Điều 25",
       "noi_dung": "Không quá 06 ngày làm việc."}

# ── Fixture: Điều 127 — noi_dung CHỈ LÀ TIÊU ĐỀ (73,6% số Điều trong corpus) ──
D127 = {"id": 141418, "parent_id": 141357, "document_id": "139264",
        "duong_dan": "45/2019/QH14 > Điều 127",
        "noi_dung": "Điều 127. Các hành vi bị nghiêm cấm khi xử lý kỷ luật lao động"}
K127_1 = {"id": 141419, "parent_id": 141418, "document_id": "139264",
          "duong_dan": "45/2019/QH14 > Điều 127 > Khoản 1",
          "noi_dung": "1. Xâm phạm sức khỏe, danh dự, tính mạng, uy tín, nhân phẩm của người lao động."}
K127_2 = {"id": 141420, "parent_id": 141418, "document_id": "139264",
          "duong_dan": "45/2019/QH14 > Điều 127 > Khoản 2",
          "noi_dung": "2. Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động."}
# Dòng thật chứa quote NGẮN NHẤT trong 65 quote đo được ("không quá 40 giờ
# trong 01 tháng;" — 32 ký tự sau normalize). Dùng để khoá sàn `QUOTE_TOI_THIEU`
# không cắt phải quote thật.
D107 = {"id": 141301, "parent_id": None, "document_id": "139264",
        "duong_dan": "45/2019/QH14 > Điều 107 > Khoản 2",
        "noi_dung": "2. Người sử dụng lao động được sử dụng người lao động làm thêm giờ khi đáp ứng đầy đủ các yêu cầu sau đây:"}
E107 = {"id": 141303, "parent_id": 141301, "document_id": "139264",
        "duong_dan": "45/2019/QH14 > Điều 107 > Khoản 2 > Điểm b",
        "noi_dung": "b) Bảo đảm số giờ làm thêm của người lao động không quá 50% số giờ làm việc bình thường "
                    "trong 01 ngày; trường hợp áp dụng quy định thời giờ làm việc bình thường theo tuần thì "
                    "tổng số giờ làm việc bình thường và số giờ làm thêm không quá 12 giờ trong 01 ngày; "
                    "không quá 40 giờ trong 01 tháng;"}

# Điều hàng xóm — dùng để chứng minh cây con KHÔNG rò sang anh em
D128 = {"id": 141422, "parent_id": 141357, "document_id": "139264",
        "duong_dan": "45/2019/QH14 > Điều 128",
        "noi_dung": "Điều 128. Tạm đình chỉ công việc"}

DB = {p["id"]: p for p in (D26, D25, D127, K127_1, K127_2, D128, D107, E107)}
CON_HL = Effectivity(V.con_hieu_luc, "trung_binh", "x")


def _eff(_pid):
    return CON_HL


# ══ Phép kiểm 1 — điều luật có tồn tại? ═════════════════════════════════════
def test_claim_hop_le_di_qua():
    c = Claim("Ít nhất 85%.", 11, "ít nhất phải bằng 85%")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is True and r.reason is R.ok


def test_kiem_1_provision_id_KHONG_TON_TAI_thi_DROP():
    c = Claim("Theo Điều 999.", 999, "bất kỳ")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is False and r.reason is R.provision_khong_ton_tai


# ══ Phép kiểm 2 — có trong tập đã truy hồi? ═════════════════════════════════
def test_kiem_2_provision_KHONG_TRONG_CONTEXT_thi_DROP():
    """LLM lôi điều luật từ tham số của nó, không từ context đã retrieve."""
    c = Claim("Không quá 06 ngày.", 10, "Không quá 06 ngày làm việc")
    r = verify_tier1([c], [D26], DB, _eff)[0]   # context chỉ có D26
    assert r.ok is False and r.reason is R.khong_trong_context


def test_kiem_2_KHAC_kiem_1_hai_ly_do_KHONG_duoc_gop():
    """Tỉ lệ loại theo từng lý do là số liệu chương đánh giá: 'bịa ra một id
    không tồn tại' và 'dẫn một điều luật CÓ THẬT nhưng chưa từng được cho xem'
    là hai chế độ hỏng khác nhau của mô hình."""
    rs = verify_tier1([Claim("a", 999, "x"), Claim("b", 10, "Không quá 06 ngày làm việc")],
                      [D26], DB, _eff)
    assert [r.reason for r in rs] == [R.provision_khong_ton_tai, R.khong_trong_context]


def test_kiem_2_con_trong_cay_nhung_KHONG_duoc_cho_xem_van_bi_DROP():
    """Khoản 2 nằm trong cây con của Điều 127 nhưng KHÔNG có trong context —
    mô hình không thể lấy id đó từ đâu ngoài tham số của chính nó."""
    c = Claim("x", 141420, "Phạt tiền, cắt lương")
    r = verify_tier1([c], [D127], DB, _eff)[0]
    assert r.ok is False and r.reason is R.khong_trong_context


# ══ Phép kiểm 3 — câu trích khớp nguyên văn (ĐỐI CHIẾU VÀO CÂY CON) ═════════
def test_kiem_3_quote_KHONG_KHOP_NGUYEN_VAN_thi_DROP():
    """LLM 'trích dẫn' nhưng viết lại nội dung."""
    c = Claim("Ít nhất 85%.", 11, "tối thiểu 85 phần trăm mức lương")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is False and r.reason is R.quote_khong_khop


def test_kiem_3_khop_sau_normalize_khoang_trang():
    c = Claim("x", 11, "ít   nhất  phải bằng   85%")
    assert verify_tier1([c], [D26], DB, _eff)[0].ok is True


def test_kiem_3_DIEU_127_quote_lay_tu_KHOAN_CON_van_DI_QUA():
    """⭐ Ca khoá của cả module.

    73,6% số Điều trong corpus có `noi_dung` CHỈ LÀ TIÊU ĐỀ; thân điều luật nằm
    ở các dòng con cấp Khoản/Điểm. Đối chiếu quote vào MỘT DÒNG `provisions` sẽ
    loại nhầm mọi claim hợp lệ trên 73,6% số Điều — một false-negative quy mô
    lớn ở đúng phép kiểm trung tâm, và trong bảng kết quả nó sẽ trông y hệt
    "mô hình bịa trích dẫn".
    """
    c = Claim("Cấm phạt tiền thay xử lý kỷ luật.", 141418, "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động")
    r = verify_tier1([c], [D127], DB, _eff)[0]
    assert r.ok is True and r.reason is R.ok


def test_kiem_3_DIEU_127_khop_tai_dung_KHOAN_2_chu_khong_phai_dong_DIEU():
    """`ok is True` một mình có thể đúng vì lý do sai. `khop_tai` khoá chặt:
    quote phải được tìm thấy ở ĐÚNG dòng Khoản 2, không phải dòng Điều 127."""
    c = Claim("x", 141418, "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động")
    assert verify_tier1([c], [D127], DB, _eff)[0].khop_tai == 141420


def test_kiem_3_khop_tai_chinh_no_khi_DIEU_co_than():
    c = Claim("x", 11, "ít nhất phải bằng 85%")
    assert verify_tier1([c], [D26], DB, _eff)[0].khop_tai == 11


def test_kiem_3_cay_con_KHONG_RO_sang_DIEU_ANH_EM():
    """Cây con là hậu duệ của CHÍNH điều được dẫn, không phải cả văn bản.
    Dẫn Điều 127 nhưng trích Điều 128 phải bị loại."""
    c = Claim("x", 141418, "Tạm đình chỉ công việc")
    r = verify_tier1([c], [D127, D128], DB, _eff)[0]
    assert r.ok is False and r.reason is R.quote_khong_khop


def test_kiem_3_quote_VAT_QUA_RANH_GIOI_cha_con_bi_DROP():
    """Ghép tiêu đề Điều với thân Khoản 1 thành một chuỗi liên tục là văn bản
    KHÔNG tồn tại ở bất kỳ dòng nào. Đối chiếu theo TỪNG DÒNG (không nối cả
    cây thành một chuỗi) nên vết ghép không tạo ra khớp giả."""
    c = Claim("x", 141418, "xử lý kỷ luật lao động 1. Xâm phạm sức khỏe")
    r = verify_tier1([c], [D127], DB, _eff)[0]
    assert r.ok is False and r.reason is R.quote_khong_khop


def test_quote_rong_co_MA_RIENG_khong_gop_vao_quote_khong_khop():
    """"Không trích gì cả" là mô hình KHÔNG TUÂN THỦ ĐỊNH DẠNG; "trích rồi bịa"
    là mô hình BỊA NỘI DUNG. Hai chế độ hỏng khác nhau, hai cách sửa khác nhau,
    nên phải là hai cột khác nhau trong chương đánh giá."""
    c = Claim("x", 11, "")
    assert verify_tier1([c], [D26], DB, _eff)[0].reason is R.quote_rong


def test_quote_toan_khoang_trang_cung_la_quote_rong():
    c = Claim("x", 11, "   \n  ")
    assert verify_tier1([c], [D26], DB, _eff)[0].reason is R.quote_rong


# ══ Sàn độ dài — đóng đường vòng tầm thường của phép kiểm 3 ═════════════════
def test_quote_MOT_KY_TU_bi_DROP_voi_ma_rieng():
    """⭐ Không có sàn thì `quote="a"` là substring của gần như mọi điều luật,
    tức mô hình luôn được đóng dấu "đã kiểm chứng" chỉ bằng một ký tự. Đó là lỗ
    hổng NGUYÊN TẮC ở đúng phép kiểm trung tâm của khoá luận."""
    c = Claim("Điều 26 nói về thử việc.", 11, "a")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is False and r.reason is R.quote_qua_ngan


def test_quote_mot_tu_chung_chung_bi_DROP():
    c = Claim("x", 11, "thỏa thuận")   # 10 ký tự — có thật trong D26 nhưng vô nghĩa làm căn cứ
    assert "thỏa thuận" in D26["noi_dung"]
    assert verify_tier1([c], [D26], DB, _eff)[0].reason is R.quote_qua_ngan


def test_quote_THAT_NGAN_NHAT_do_duoc_van_DI_QUA():
    """Sàn đặt để chặn ca suy biến, KHÔNG để lọc quote thật. 32 ký tự là quote
    ngắn nhất trong 65 quote thật `generate_claims` sinh ra; sàn 12 phải chừa
    nó lại với dự phòng 2,7 lần."""
    q = "không quá 40 giờ trong 01 tháng;"
    assert len(normalize(q)) == 32
    r = verify_tier1([Claim("x", 141301, q)], [D107], DB, _eff)[0]
    assert r.ok is True and r.khop_tai == 141303


def test_san_do_dai_dat_DUOI_moi_quote_that_da_do():
    """Khoá quan hệ giữa hằng số và phép đo: sàn phải nằm dưới min quan sát
    được (32), không phải sát nó. Đổi `QUOTE_TOI_THIEU` lên quá 32 là bắt đầu
    cắt vào quote thật."""
    from src.agents.nodes.verify_tier1 import QUOTE_TOI_THIEU

    assert QUOTE_TOI_THIEU < 32, "sàn đã chạm vùng quote thật"
    assert QUOTE_TOI_THIEU >= 8, "sàn quá thấp thì không chặn được ca suy biến"


# ══ Quote GẦN ĐÚNG NHƯNG SAI phải bị loại ═══════════════════════════════════
# Chế độ hỏng nguy hiểm nhất của cả khoá luận không phải "loại nhầm claim đúng"
# mà là "đóng dấu ĐÃ KIỂM CHỨNG cho một quote SAI". Ba ca dưới đây là ba cách
# một quote có thể gần đúng.
def test_quote_DOI_MOT_CON_SO_bi_DROP():
    c = Claim("Ít nhất 80%.", 11, "ít nhất phải bằng 80%")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is False and r.reason is R.quote_khong_khop


def test_quote_THEM_MOT_MENH_DE_bi_DROP():
    c = Claim("x", 11, "ít nhất phải bằng 85% mức lương tối thiểu vùng của công việc đó")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is False and r.reason is R.quote_khong_khop


def test_quote_DOI_MOT_DAU_phat_thanh_phat_bi_DROP():
    """⭐ Vì sao `normalize` KHÔNG bỏ dấu.

    Điều 127 CẤM "Phạt tiền" người lao động. "phát tiền" là hành vi ngược lại
    (trả tiền) và có thật trong corpus ở 84/2015/QH13 Điều 23. Bỏ dấu thì hai
    chuỗi trùng khít, và tầng 1 sẽ đóng dấu "đã kiểm chứng" cho một câu đảo
    ngược nghĩa của điều luật — đúng chế độ hỏng khoá luận tồn tại để chống.
    """
    c = Claim("Được phát tiền thay xử lý kỷ luật.", 141418, "Phát tiền, cắt lương thay việc xử lý kỷ luật lao động")
    r = verify_tier1([c], [D127], DB, _eff)[0]
    assert r.ok is False and r.reason is R.quote_khong_khop


# ══ Phép kiểm 4 — hiệu lực: WARN, KHÔNG drop ════════════════════════════════
def test_kiem_4_het_hieu_luc_thi_WARN_KHONG_drop():
    het = Effectivity(V.bi_thay_the, "cao", "bị 74/2024 thay thế")
    c = Claim("x", 11, "ít nhất phải bằng 85%")
    r = verify_tier1([c], [D26], DB, lambda _p: het)[0]
    assert r.ok is True, "hiệu lực là CẢNH BÁO, không phải lý do drop"
    assert r.effectivity.verdict is V.bi_thay_the


def test_kiem_4_ly_do_giu_NGUYEN_VAN_khong_viet_lai():
    """`ly_do` của Task 2 nêu đích danh văn bản thay thế. Viết lại nó là xoá
    mất tên văn bản mà người đọc cần để tự đối chiếu."""
    ly_do = "đồ thị xác nhận: bị 74/2024/NĐ-CP thay thế từ 2024-07-01"
    c = Claim("x", 11, "ít nhất phải bằng 85%")
    r = verify_tier1([c], [D26], DB, lambda _p: Effectivity(V.bi_thay_the, "cao", ly_do))[0]
    assert r.effectivity.ly_do == ly_do


def test_kiem_4_KHONG_duoc_goi_cho_claim_da_bi_loai():
    """Claim đã rớt ba phép kiểm đầu thì không tra hiệu lực — vừa thừa, vừa
    làm `effectivity` của một kết quả DROP trông như đã được kiểm."""
    goi: list[int] = []

    def dem(pid):
        goi.append(pid)
        return CON_HL

    verify_tier1([Claim("a", 999, "x"), Claim("b", 11, "ít nhất phải bằng 85%")], [D26], DB, dem)
    assert goi == [11]


# ══ normalize — mức chuẩn hoá ═══════════════════════════════════════════════
def test_normalize_gop_khoang_trang_va_bo_khoang_trang_hai_dau():
    assert normalize("  Ít   nhất\nphải bằng  85%  ") == "Ít nhất phải bằng 85%"


def test_normalize_dua_ve_NFC_de_quote_NFD_cua_LLM_van_khop():
    """Corpus đã được `prov_parser._chuan_hoa` đưa về NFC lúc nạp (đo được: 0
    dòng non-NFC trong `provisions`). Nhưng quote đến từ LLM, không từ corpus —
    nó có thể ở NFD. Chuẩn hoá phải áp ĐỐI XỨNG cho cả hai phía."""
    nfd = unicodedata.normalize("NFD", "ít nhất phải bằng 85%")
    assert nfd != "ít nhất phải bằng 85%"
    assert normalize(nfd) == normalize("ít nhất phải bằng 85%")


def test_normalize_Ð_U00D0_bang_Đ_U0110():
    """Hai codepoint hiện lên y hệt nhau; corpus có thật 2 lần Ð U+00D0 ở
    101/2015/QH13 (Điều 414 và 420, "Ðoàn thanh niên")."""
    assert "Ð" != "Đ"
    assert normalize("Ðoàn thanh niên") == normalize("Đoàn thanh niên")


def test_normalize_KHONG_BO_DAU():
    """Trong tiếng Việt dấu là chữ, không phải trang trí: phạt ≠ phát."""
    assert normalize("Phạt tiền") != normalize("Phát tiền")


def test_normalize_KHONG_CASEFOLD():
    """Prompt v1 quy định `quote` là "đoạn NGUYÊN VĂN copy", và `prov_parser`
    đã ghim mức chuẩn hoá của repo là "không casefold, không unaccent" (đo
    được ở Plan 2: casefold nâng độ phủ +0,63pp bằng cách CHE ~20 token thiếu
    thật). Nới hơn corpus đã được nạp là leniency không có căn cứ."""
    assert normalize("ÍT NHẤT") != normalize("ít nhất")


# ══ 0 TOKEN — ba bằng chứng độc lập ═════════════════════════════════════════
def test_KHONG_goi_LLM_bang_chung_1_khong_co_tham_so_llm():
    from src.agents.nodes import verify_tier1 as mod

    assert "llm" not in inspect.signature(mod.verify_tier1).parameters


def test_KHONG_goi_LLM_bang_chung_2_module_khong_import_gi_ra_mang():
    """Quét AST chứ không quét chuỗi: docstring của module CỐ Ý nhắc tên
    `httpx` để cảnh báo người sửa sau, nên phép kiểm bằng substring sẽ đỏ vì
    chính lời cảnh báo đó."""
    from src.agents.nodes import verify_tier1 as mod

    cam = {"httpx", "requests", "urllib", "openai", "aiohttp", "socket", "src.services.llm"}
    goc: set[str] = set()
    for node in ast.walk(ast.parse(Path(inspect.getfile(mod)).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            goc.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            goc.add(node.module)
    assert not {g for g in goc if any(g == c or g.startswith(c + ".") for c in cam)}


def test_KHONG_goi_LLM_bang_chung_3_chan_socket_van_chay_dung(monkeypatch):
    """Bằng chứng mạnh nhất: chặn socket ở runtime rồi chạy đủ bốn phép kiểm."""
    def no_net(*a, **k):
        raise AssertionError("tầng 1 mở socket — sai thiết kế, tầng này phải là 0 token")

    monkeypatch.setattr(socket, "socket", no_net)
    monkeypatch.setattr(socket, "create_connection", no_net)
    rs = verify_tier1(
        [Claim("a", 141418, "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động"),
         Claim("b", 999, "x"), Claim("c", 10, "Không quá 06 ngày làm việc"),
         Claim("d", 11, "diễn giải lại nội dung điều luật"), Claim("e", 11, "a"), Claim("f", 11, "")],
        [D127, D26], DB, _eff)
    assert [r.reason for r in rs] == [
        R.ok, R.provision_khong_ton_tai, R.khong_trong_context, R.quote_khong_khop,
        R.quote_qua_ngan, R.quote_rong]


# ══ Hợp đồng chung ══════════════════════════════════════════════════════════
def test_nhieu_claim_moi_claim_doc_lap():
    cs = [Claim("a", 11, "ít nhất phải bằng 85%"), Claim("b", 999, "x")]
    rs = verify_tier1(cs, [D26], DB, _eff)
    assert [r.ok for r in rs] == [True, False]


def test_claim_bi_loai_khong_mang_effectivity():
    r = verify_tier1([Claim("a", 999, "x")], [D26], DB, _eff)[0]
    assert r.effectivity is None


def test_khong_co_claim_thi_khong_co_ket_qua():
    assert verify_tier1([], [D26], DB, _eff) == []


def test_citation_precision():
    rs = verify_tier1([Claim("a", 11, "ít nhất phải bằng 85%"), Claim("b", 999, "x")], [D26], DB, _eff)
    assert citation_precision(rs) == 0.5
    assert citation_precision([]) == 0.0


def test_cay_con_chiu_duoc_parent_id_vong_lap():
    """Dữ liệu vòng (a là cha của b, b là cha của a) phải cho kết quả, không
    treo. Rẻ hơn nhiều so với đi tìm nguyên nhân một test CI đứng im."""
    a = {"id": 1, "parent_id": 2, "document_id": "d", "noi_dung": "dòng alpha của văn bản vòng"}
    b = {"id": 2, "parent_id": 1, "document_id": "d", "noi_dung": "dòng beta của văn bản vòng"}
    r = verify_tier1([Claim("x", 1, "dòng beta của văn bản vòng")], [a], {1: a, 2: b}, _eff)[0]
    assert r.ok is True


# ══ Tầng DB — cây con lấy từ Postgres ═══════════════════════════════════════
@pytest.mark.integration
def test_nap_provisions_lay_ca_HAU_DUE_cua_dieu_duoc_dan():
    from src.agents.nodes.verify_tier1 import nap_provisions
    from src.services.db import get_engine

    d127 = pid("45/2019/QH14 > Điều 127")
    khoan = {pid(f"45/2019/QH14 > Điều 127 > Khoản {n}") for n in (1, 2, 3)}
    db = nap_provisions(get_engine(), [d127])
    assert d127 in db, "phải có chính điều được dẫn"
    assert khoan <= set(db), "phải có cả ba Khoản con"
    assert db[d127]["document_id"] == "139264"


@pytest.mark.integration
def test_DIEU_127_that_trong_DB_di_qua_duoc_phep_kiem_3():
    """Chạy lại ca khoá trên dữ liệu thật, không phải fixture chép tay."""
    from src.agents.nodes.verify_tier1 import nap_provisions
    from src.services.db import get_engine

    d127, k2 = pid("45/2019/QH14 > Điều 127"), pid("45/2019/QH14 > Điều 127 > Khoản 2")
    db = nap_provisions(get_engine(), [d127])
    c = Claim("Cấm phạt tiền.", d127, "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động.")
    r = verify_tier1([c], [db[d127]], db, _eff)[0]
    assert r.ok is True and r.khop_tai == k2


@pytest.mark.integration
def test_hieu_luc_doc_qua_danh_gia_theo_id_chu_khong_qua_tinh_trang():
    """Task 2 tồn tại vì `documents.tinh_trang` SAI 4/6 trên chuỗi nghị định
    lương tối thiểu. Adapter phải đi qua `danh_gia_theo_id`."""
    from src.agents.nodes.verify_tier1 import effectivity_qua_provision, nap_provisions
    from src.services.db import get_engine

    d127 = pid("45/2019/QH14 > Điều 127")
    db = nap_provisions(get_engine(), [d127])
    eff = effectivity_qua_provision(get_engine(), db, date(2026, 8, 30))
    assert isinstance(eff(d127), Effectivity)


# ══ Phép kiểm thứ sáu — tiền đề sai ở đầu vào (coordinator, sau phép kiểm thứ 5) ══


def test_tien_de_khong_can_llm_hay_client_mang():
    """Chữ ký chỉ nhận query/engine — engine là SQLAlchemy, không phải LLM
    client hay HTTP client, khớp đúng bất biến '0 token' của cả module."""
    from src.agents.nodes.verify_tier1 import tien_de_cau_hoi_sai
    assert set(inspect.signature(tien_de_cau_hoi_sai).parameters) == {"query", "engine"}


@pytest.mark.integration
def test_tien_de_dieu_khong_ton_tai_tra_ve_ly_do_neu_dich_danh():
    from src.agents.nodes.verify_tier1 import tien_de_cau_hoi_sai
    from src.services.db import get_engine

    ly_do = tien_de_cau_hoi_sai("Điều 999 Bộ luật Lao động quy định gì về nghỉ phép", get_engine())
    assert ly_do == "Bộ luật Lao động không có Điều 999"


@pytest.mark.integration
def test_tien_de_phan_biet_DUNG_van_ban_khong_chi_so_dieu():
    """Điều 550 CÓ THẬT ở Bộ luật Dân sự (689 điều) nhưng KHÔNG có ở Bộ luật
    Tố tụng dân sự (517 điều) — lẫn hai văn bản là chặn oan hoặc bỏ lọt sai
    chiều, đúng chế độ hỏng phép kiểm này tồn tại để tránh."""
    from src.agents.nodes.verify_tier1 import tien_de_cau_hoi_sai
    from src.services.db import get_engine

    eng = get_engine()
    assert tien_de_cau_hoi_sai("Điều 550 Bộ luật Tố tụng dân sự quy định thủ tục gì", eng) == (
        "Bộ luật Tố tụng dân sự không có Điều 550"
    )
    assert tien_de_cau_hoi_sai("Điều 550 Bộ luật Dân sự quy định thủ tục gì", eng) is None


@pytest.mark.integration
def test_tien_de_dieu_co_that_thi_KHONG_chan():
    from src.agents.nodes.verify_tier1 import tien_de_cau_hoi_sai
    from src.services.db import get_engine

    assert tien_de_cau_hoi_sai("Điều 35 Bộ luật Lao động quy định quyền gì", get_engine()) is None


@pytest.mark.integration
def test_tien_de_khong_nhac_so_dieu_nao_thi_KHONG_chan():
    from src.agents.nodes.verify_tier1 import tien_de_cau_hoi_sai
    from src.services.db import get_engine

    assert tien_de_cau_hoi_sai("công ty nợ lương thì làm sao", get_engine()) is None


# ══ C1/H2 — silent-failure review round 2: khớp văn bản theo VỊ TRÍ, hai chiều ══


@pytest.mark.integration
def test_tien_de_chon_van_ban_GAN_dieu_N_nhat_khong_theo_thu_tu_bang():
    """Bug đo được (coordinator): 'Điều 600 Bộ luật Dân sự về hợp đồng lao
    động' khớp NHẦM 'Bộ luật Lao động' — chỉ vì 'lao động' đứng TRƯỚC 'dân sự'
    trong bảng `_VAN_BAN_BO_LUAT`, dù 'Bộ luật Dân sự' đứng NGAY SAU 'Điều 600'
    trong câu thật. Điều 600 CÓ THẬT ở Bộ luật Dân sự (689 điều) — câu hợp lệ,
    không được chặn."""
    from src.agents.nodes.verify_tier1 import tien_de_cau_hoi_sai
    from src.services.db import get_engine

    eng = get_engine()
    assert tien_de_cau_hoi_sai("Điều 600 Bộ luật Dân sự về hợp đồng lao động", eng) is None
    # Chiều ngược: BLLĐ đứng NGAY SAU Điều 250, "tố tụng dân sự" đứng xa hơn ở
    # cuối câu — BLLĐ chỉ có 220 điều nên câu này PHẢI bị chặn.
    assert tien_de_cau_hoi_sai("Điều 250 Bộ luật Lao động trong tố tụng dân sự", eng) == (
        "Bộ luật Lao động không có Điều 250"
    )


@pytest.mark.integration
def test_tien_de_quet_ca_hai_chieu_quanh_dieu_N():
    """Bug đo được (coordinator): phép kiểm chỉ quét VỀ SAU từ 'Điều N', bỏ lọt
    hoàn toàn cách viết văn bản đứng TRƯỚC — và cả 15/15 câu `dieu_khong_ton_tai`
    trong trap.yaml đều dùng trật tự 'Điều N [văn bản]' nên 15/15 không chứng
    minh được phép kiểm hoạt động cho cách viết ngược lại."""
    from src.agents.nodes.verify_tier1 import tien_de_cau_hoi_sai
    from src.services.db import get_engine

    eng = get_engine()
    assert tien_de_cau_hoi_sai("Bộ luật Lao động Điều 999 nói gì", eng) == "Bộ luật Lao động không có Điều 999"
    assert tien_de_cau_hoi_sai("Trong BLLĐ, Điều 999 quy định thế nào", eng) == (
        "Bộ luật Lao động không có Điều 999"
    )
    assert tien_de_cau_hoi_sai("Theo BLLĐ thì Điều 999 quy định thế nào", eng) == (
        "Bộ luật Lao động không có Điều 999"
    )


# ══ Câu trích lấy TỪ BẢNG phải qua được tầng 1 ══════════════════════════════
#
# Đây là lý do bảng được ghép vào `noi_dung` chứ không vào một cột/bảng riêng.
# Nếu con số lương nằm ở nơi khác, một câu trích chứa nó KHÔNG BAO GIỜ verify
# được, và cơ chế chống ảo giác mất tác dụng đúng chỗ nó cần nhất: câu hỏi
# "lương tối thiểu vùng I bao nhiêu" là câu người lao động hỏi nhiều nhất, và
# con số sai ở đó là thiệt hại tiền thật.
#
# Fixture đi QUA parser thật (không gõ tay dạng đã ghép) để test không thể xanh
# giả nếu định dạng markdown của `prov_parser` đổi. Khoản 2 sau bảng là CÓ CHỦ Ý
# và giống văn bản thật (293/2025 có Khoản 2–5 sau bảng lương): bảng đứng sau thẻ
# prov-* CUỐI CÙNG là chữ đuôi, và parser cố ý đưa nó vào `phu_luc` chứ không vào
# một neo trích dẫn — xem `test_bang_TIEU_NGU_va_bang_CHU_KY_khong_vao_neo_trich_dan`.

_HTML_BANG_LUONG = """
<div class="WordSection1">
<p id="d1" class="MsoNormal prov-article"><b>Điều 3. Mức lương tối thiểu</b></p>
<p id="k1" class="MsoNormal prov-clause">1. Quy định mức lương tối thiểu tháng đối với người lao động theo vùng như sau:</p>
<table><tr><td>Vùng</td><td>Mức lương tối thiểu tháng (Đơn vị: đồng/tháng)</td></tr>
<tr><td>Vùng I</td><td>5.310.000</td></tr>
<tr><td>Vùng II</td><td>4.730.000</td></tr></table>
<p id="k2" class="MsoNormal prov-clause">2. Danh mục địa bàn vùng quy định tại Phụ lục kèm theo.</p>
</div>
"""


def _prov_bang_luong() -> dict:
    from src.services.prov_parser import parse_provisions

    rows = parse_provisions(_HTML_BANG_LUONG, "293/2025/NĐ-CP")
    k1 = next(r for r in rows if r.duong_dan == "293/2025/NĐ-CP > Điều 3 > Khoản 1")
    return {"id": 900, "parent_id": None, "document_id": "183939",
            "duong_dan": k1.duong_dan, "noi_dung": k1.noi_dung}


def test_quote_lay_TU_BANG_qua_duoc_tang_1():
    p = _prov_bang_luong()
    db = {p["id"]: p}
    c = Claim("Mức lương tối thiểu tháng vùng I là 5.310.000 đồng.", 900,
              "| Vùng I | 5.310.000 |")
    r = verify_tier1([c], [p], db, _eff)[0]
    assert r.ok is True, r.reason
    assert r.reason is R.ok
    assert r.khop_tai == 900


def test_quote_bia_CON_SO_SAI_trong_bang_van_bi_loai():
    """Phép kiểm chỉ có giá trị nếu nó còn LOẠI được. 5.310.000 là mức thật của
    293/2025; 5.500.000 là con số mô hình có thể viết ra từ trí nhớ huấn luyện."""
    p = _prov_bang_luong()
    c = Claim("Vùng I là 5.500.000 đồng.", 900, "| Vùng I | 5.500.000 |")
    r = verify_tier1([c], [p], {p["id"]: p}, _eff)[0]
    assert r.ok is False and r.reason is R.quote_khong_khop


def test_quote_vat_qua_van_xuoi_SANG_bang_van_khop():
    """`normalize` gộp mọi khoảng trắng, nên dấu phân tách giữa văn xuôi và bảng
    không tạo ra vết ghép mà quote thật phải né."""
    p = _prov_bang_luong()
    c = Claim("Bảng lương theo vùng.", 900, "theo vùng như sau: | Vùng | Mức lương tối thiểu tháng")
    r = verify_tier1([c], [p], {p["id"]: p}, _eff)[0]
    assert r.ok is True, r.reason
