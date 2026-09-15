"""PDF tiếng Việt CÓ DẤU, đo trên một tệp thật (spec 2026-09-15; rủi ro R3).

Vì sao file này tách khỏi `test_doc_tai_lieu.py`: fixture PDF dựng tay ở đó chỉ
dùng ASCII, vì Type1/WinAnsi không mã được chữ Việt có dấu. Nhánh dấu vì thế
từng CHƯA ĐƯỢC ĐO trên PDF — chỉ được đo trên DOCX. Đó đúng là rủi ro R3 của kế
hoạch: `pypdf` làm vỡ dấu trên PDF font lạ thì mọi phép tra chuỗi phía sau vô
nghĩa, và nó hỏng im lặng.

`tests/fixtures/tieng-viet-co-dau.pdf` là PDF thật, sinh bằng `cupsfilter` của
macOS từ văn bản UTF-8, có font nhúng — cùng hạng với PDF do Word hay trình xuất
PDF thông thường tạo ra.

Giới hạn còn lại: một tệp không phủ hết mọi bộ sinh PDF. Nó chứng minh nhánh
này KHÔNG hỏng mặc định, không chứng minh mọi PDF đều qua.
"""

import pathlib
import unicodedata

from src.services.doc_tai_lieu import doc
from src.services.neo_du_kien import LyDoNeo, xac_minh

TEP = pathlib.Path("tests/fixtures/tieng-viet-co-dau.pdf")
DONG = "Mức lương: 20.000.000 đồng/tháng"
TL = doc("tieng-viet-co-dau.pdf", TEP.read_bytes())


def test_dau_tieng_Viet_di_qua_pypdf_NGUYEN_VEN():
    assert any(d.noi_dung == DONG for d in TL.don_vi), [d.noi_dung for d in TL.don_vi]


def test_chu_rut_ra_o_dang_NFC():
    """Dạng đã chuẩn hoá khớp với dạng corpus được lưu, nên phép tra chuỗi thẳng hàng."""
    s = TL.don_vi[0].noi_dung
    assert s == unicodedata.normalize("NFC", s)


def test_neo_khop_du_doan_trich_o_dang_NFC_hay_NFD():
    """Mô hình sinh được cả hai dạng; `normalize` phải gộp chúng lại."""
    for dang in ("NFC", "NFD"):
        assert xac_minh(unicodedata.normalize(dang, DONG), TL.don_vi).ly_do is LyDoNeo.ok, dang


def test_BO_DAU_van_TRUOT_tren_PDF_that():
    """Lời hứa trung tâm vẫn giữ trên nguồn PDF, không chỉ trên DOCX."""
    assert xac_minh("Muc luong: 20.000.000 dong/thang", TL.don_vi).ly_do is LyDoNeo.trich_khong_khop


def test_moi_dong_la_mot_don_vi_rieng():
    assert len(TL.don_vi) >= 3
    assert any("Thời gian thử việc" in d.noi_dung for d in TL.don_vi)
    assert any("Phạt tiền" in d.noi_dung for d in TL.don_vi)


def test_GHEP_hai_dong_TRUOT_tren_PDF_that():
    ghep = f"{TL.don_vi[0].noi_dung} {TL.don_vi[1].noi_dung}"
    assert xac_minh(ghep, TL.don_vi).ly_do is LyDoNeo.trich_khong_khop
