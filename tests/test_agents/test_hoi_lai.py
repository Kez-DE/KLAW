"""Câu hỏi lại — chỉ được hỏi về DỮ KIỆN TÌNH HUỐNG của người hỏi.

Vì sao bộ lọc bằng quy tắc là BẮT BUỘC chứ không phải một lớp trang trí:
"hợp đồng của bạn dưới 12 tháng không?" đã KHẲNG ĐỊNH mốc 12 tháng có ý nghĩa
pháp lý. Không trích dẫn nào chống đỡ khẳng định đó, và cả hai tầng kiểm chứng
KHÔNG bắt được — chúng kiểm claim, còn đây không có claim nào để kiểm. Nên chỗ
duy nhất chặn được là một bộ lọc trên chính chuỗi trước khi nó tới màn hình.
"""

import inspect
import json

import pytest

from src.agents.nodes.hoi_lai import (
    CAU_DAN,
    CHIEU,
    MAC_DINH,
    TOI_DA,
    bi_loai,
    dung_cau_hoi_lai,
    hoi_lai,
)
from src.services.llm import Usage


class FakeLlm:
    """Trả đúng một chiều hợp lệ. `cau_gui` giữ lại prompt để test tra."""

    cau_gui = ""

    def __init__(self, payload: object = None) -> None:
        self.payload = payload if payload is not None else {
            "chieu": [{"ma": "loai_hop_dong", "cau": "Hợp đồng của bạn ghi thời hạn thế nào?"}]
        }

    def chat(self, model, messages, json_schema=None):
        FakeLlm.cau_gui = messages[-1]["content"]
        return json.dumps(self.payload), Usage(7, 3, 0.001)


# ══ Bộ lọc bằng quy tắc ══════════════════════════════════════════════════════


def test_moi_cau_hang_so_deu_qua_duoc_bo_loc_cua_chinh_no():
    """Bẫy kinh điển: câu mặc định — thứ được dùng KHI câu sinh bị loại — lại
    tự vướng bộ lọc, nên đường suy biến trả về rỗng và người hỏi vẫn nhận ngõ
    cụt. Khoá cả sáu chiều, không phải chiều đang dùng."""
    vuong = {ma: cau for ma, cau in CHIEU.items() if bi_loai(cau)}
    assert vuong == {}, f"câu hằng số tự vướng bộ lọc: {vuong}"


@pytest.mark.parametrize("cau", [
    "Bạn đã ký hợp đồng theo Điều 20 chưa?",
    "Công ty bạn áp dụng Nghị định 145/2020/NĐ-CP không?",
    "Hợp đồng của bạn dưới 12 tháng không?",
    "Bạn đã nghỉ quá 5 ngày trong tháng chưa?",
    "Công ty giữ lại bao nhiêu, 10% hay hơn?",
    "Bạn được trả 500000 đồng hay nhiều hơn?",
    "Bạn làm ở đó trên 3 năm chưa?",
])
def test_bo_loc_chan_moi_cau_phat_bieu_quy_tac_phap_luat(cau):
    assert bi_loai(cau), f"phải bị loại: {cau!r}"


@pytest.mark.parametrize("cau", [
    "Bạn đang ở phía người lao động hay phía công ty?",
    "Chuyện này xảy ra vào khoảng thời gian nào?",
    "Bạn đang giữ những giấy tờ nào về việc này?",
    "Công ty bạn đóng ở tỉnh hay thành phố nào?",
])
def test_bo_loc_khong_chan_cau_hoi_thuan_du_kien(cau):
    assert not bi_loai(cau), f"không được loại một câu chỉ hỏi dữ kiện: {cau!r}"


def test_bo_loc_bat_ca_Dj_U00D0_cua_corpus():
    """Corpus có `Ð` U+00D0 lẫn `Đ` U+0110 — một bộ lọc chỉ biết một chữ sẽ để
    lọt đúng dạng còn lại."""
    assert bi_loai("Bạn đã đọc Ðiều 25 chưa?")


# ══ Dựng chuỗi — thuần, 0 token ══════════════════════════════════════════════


def test_dung_cau_hoi_lai_la_ham_thuan_khong_nhan_llm():
    """Cùng lý do `kho.dung_cau_tra_loi` tách khỏi `nap_kho`: phần quyết định
    người hỏi đọc được gì phải kiểm được mà không cần mạng."""
    assert set(inspect.signature(dung_cau_hoi_lai).parameters) == {"chon"}


def test_cau_bi_loai_thi_thay_bang_hang_so_va_KHONG_hien_cau_da_sinh():
    cau_xau = "Hợp đồng của bạn dưới 12 tháng không?"
    ra = dung_cau_hoi_lai([{"ma": "loai_hop_dong", "cau": cau_xau}])
    assert cau_xau not in ra, "câu đã sinh bị loại KHÔNG được hiển thị"
    assert CHIEU["loai_hop_dong"] in ra, "phải rơi về câu hằng số của đúng chiều đó"


def test_cau_sach_thi_duoc_giu_nguyen():
    cau = "Bạn ký hợp đồng dạng nào với công ty?"
    assert cau in dung_cau_hoi_lai([{"ma": "loai_hop_dong", "cau": cau}])


def test_toi_da_ba_chieu():
    """Nhiều hơn ba là một bảng biểu, không phải một câu hỏi."""
    chon = [{"ma": ma, "cau": ""} for ma in CHIEU]
    ra = dung_cau_hoi_lai(chon)
    assert len(chon) > TOI_DA, "fixture phải đưa nhiều hơn trần để trần có nghĩa"
    assert ra.count("\n- ") == TOI_DA


def test_ma_la_bi_bo_khong_dung_lam_khoa():
    """`enum` trong json_schema đã chặn, nhưng mặc định an toàn khi model trả
    giá trị lạ phải là BỎ, không phải in nguyên `ma` ra cho người hỏi đọc."""
    ra = dung_cau_hoi_lai([{"ma": "muc_luong_toi_thieu", "cau": "x"},
                           {"ma": "chu_the", "cau": ""}])
    assert "muc_luong_toi_thieu" not in ra
    assert CHIEU["chu_the"] in ra


def test_ma_trung_chi_hoi_mot_lan():
    ra = dung_cau_hoi_lai([{"ma": "chu_the", "cau": ""}, {"ma": "chu_the", "cau": ""}])
    assert ra.count("\n- ") == 1


def test_chon_rong_thi_roi_ve_hang_so_chu_khong_tra_chuoi_rong():
    """Chuỗi rỗng ở đây = màn hình trắng, đúng chế độ hỏng cả pha này tồn tại
    để bỏ."""
    ra = dung_cau_hoi_lai([])
    assert CAU_DAN in ra
    assert all(CHIEU[ma] in ra for ma in MAC_DINH)


# ══ Đường có LLM ═════════════════════════════════════════════════════════════


def test_hoi_lai_dung_cau_model_sinh_va_dem_token():
    kq = hoi_lai("công ty trừ lương tôi", FakeLlm(), "m")
    assert "Hợp đồng của bạn ghi thời hạn thế nào?" in kq.cau
    assert kq.nguon == "llm"
    assert kq.usage is not None and kq.usage.token_in == 7


def test_prompt_nap_tu_vung_chieu_TU_HANG_SO_va_mang_cau_hoi_that():
    """Từ vựng chiều hỏi là hằng số trong mã, không do model chọn — nên prompt
    phải ĐƯỢC BƠM từ `CHIEU`. Viết tay danh sách vào file prompt sẽ lệch pha
    đúng vào ngày ai đó thêm một chiều."""
    hoi_lai("công ty trừ lương tôi", FakeLlm(), "m")
    for ma in CHIEU:
        assert ma in FakeLlm.cau_gui, f"prompt thiếu chiều {ma}"
    assert "công ty trừ lương tôi" in FakeLlm.cau_gui, "câu hỏi lại phải bám câu hỏi thật"


def test_llm_no_thi_roi_ve_hang_so_KHONG_nem_ngoai_le():
    """Một ngõ cụt không được biến thành HTTP 500: đây là khâu cuối, không còn
    quyết định hạ nguồn nào phụ thuộc nó."""
    class No:
        def chat(self, *a, **k):
            raise RuntimeError("429")

    kq = hoi_lai("x", No(), "m")
    assert kq.nguon == "loi" and kq.usage is None
    assert all(CHIEU[ma] in kq.cau for ma in MAC_DINH)


def test_llm_tra_json_sai_hinh_dang_thi_roi_ve_hang_so():
    kq = hoi_lai("x", FakeLlm({"answer": "một câu trả lời, không phải chiều hỏi"}), "m")
    assert kq.nguon == "loi"
    assert CAU_DAN in kq.cau


def test_llm_tra_danh_sach_rong_thi_van_co_cau_hoi():
    kq = hoi_lai("x", FakeLlm({"chieu": []}), "m")
    assert CAU_DAN in kq.cau and kq.nguon == "llm"


# ══ Vòng review (silent-failure-hunter, 2026-09-02) — CRITICAL ═════════════


@pytest.mark.parametrize("cau", [
    # ĐO ĐƯỢC bằng cách chạy chính `bi_loai()`: cả ba pattern cũ đều BẮT BUỘC có
    # chữ số Ả Rập, nên bộ lọc chặn "dưới 12 tháng" mà để lọt "dưới một năm" —
    # cùng một mốc pháp lý, khác cách viết. Bảy ca parametrize cũ đều dùng chữ
    # số nên không cái nào đỏ; lỗ hổng im lặng hoàn toàn.
    "Hợp đồng của bạn có thời hạn dưới một năm không?",
    "Bạn đã làm đủ mười hai tháng chưa?",
    "Bạn có được báo trước ba mươi ngày không?",
    "Lương của bạn có dưới năm triệu đồng một tháng không?",
    "Công ty có trừ quá mười phần trăm lương của bạn không?",
    "Bạn đã thử việc quá sáu mươi ngày chưa?",
    "Bạn có làm thêm quá tám giờ một ngày không?",
    "Bạn làm ở đó một năm rưỡi rồi phải không?",
    "Bạn có nghỉ quá nửa tháng không?",
])
def test_bo_loc_chan_ca_MOC_VIET_BANG_CHU(cau):
    """Số viết bằng chữ là cùng một phát biểu pháp luật, chỉ khác chính tả.

    "Hợp đồng của bạn có thời hạn dưới một năm không?" khẳng định mốc một năm có
    ý nghĩa pháp lý, y như "dưới 12 tháng" — mà không trích dẫn nào chống đỡ, và
    verifier KHÔNG bắt được vì đây không phải một claim, không có `provision_id`
    nào để kiểm.
    """
    assert bi_loai(cau), f"lọt qua bộ lọc: {cau!r}"


@pytest.mark.parametrize("cau", [
    # Không được loại oan: đây là câu hỏi DỮ KIỆN, không phát biểu mốc nào.
    *CHIEU.values(),
    # Đo được trên model thật 2026-09-02 — ba câu này TỐT HƠN câu hằng số vì bám
    # vào chính việc được hỏi. Loại oan chúng là làm đầu ra tệ đi, nên bộ lọc
    # mở rộng phải để chúng qua.
    "Bạn có thể nói chi tiết hơn về thời điểm công ty tự ý trừ lương của bạn không?",
    "Hợp đồng của bạn có ghi rõ điều khoản về việc trừ lương không?",
    "Bạn có giữ bất kỳ giấy tờ nào liên quan đến việc trừ lương của công ty không?",
    "Bạn có giấy tờ ghi rõ lý do sa thải không?",
    # "một số", "một vài", "nhiều lần" — có từ số nhưng KHÔNG kèm đơn vị mang
    # mốc pháp lý, nên không phải một phát biểu về luật.
    "Bạn đã bị nhắc nhở một số lần trước đó chưa?",
    "Công ty có gửi bạn một vài thông báo nào không?",
])
def test_bo_loc_KHONG_loai_oan_cau_hoi_du_kien(cau):
    assert not bi_loai(cau), f"loại oan một câu hỏi dữ kiện: {cau!r}"


@pytest.mark.parametrize("cau", [
    # `lăm`/`mốt` là DẠNG GHÉP bắt buộc của tiếng Việt: 5 trong số ghép luôn là
    # "lăm", 1 là "mốt". Thiếu chúng khỏi `_SO_BANG_CHU` thì "bốn mươi lăm ngày"
    # lọt trong khi "bốn mươi năm ngày" — cách không ai viết — bị bắt. Lỗ này
    # nằm trong chính bản mở rộng bộ lọc của sáng 2026-09-02.
    "Bạn có được báo trước bốn mươi lăm ngày không?",
    "Bạn đã làm mười lăm tháng chưa?",
    "Hợp đồng của bạn có thời hạn hai mươi mốt tháng không?",
])
def test_bo_loc_chan_dang_so_GHEP_lam_va_mot(cau):
    assert bi_loai(cau), f"lọt qua bộ lọc: {cau!r}"
