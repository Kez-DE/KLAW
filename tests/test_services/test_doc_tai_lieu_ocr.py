"""OCR cho ảnh và PDF không có lớp chữ (spec 2026-09-15, mở rộng 2026-09-15b).

Quyết định định hình toàn bộ nhánh này, và nó là quyết định về LỜI HỨA chứ
không phải về kỹ thuật:

**Chữ do OCR đọc ra KHÔNG phải chữ của tài liệu.** Nó là phỏng đoán của máy.
Nếu OCR đọc "20.000.000" thành "2O.OOO.OOO" thì đoạn trích vẫn khớp với đầu ra
OCR — phép tra chuỗi vẫn chạy đúng — nhưng nó không còn chứng minh được điều
người dùng tưởng nó chứng minh. Bằng chứng yếu đi trong khi giao diện trông y
hệt. Đó đúng là chế độ hỏng nguy hiểm nhất của một sản phẩm pháp lý.

Nên nguồn chữ được GIỮ RIÊNG suốt cả đường, y hệt cách dự án giữ riêng
`verify_tier1` với `verify_tier2`, và `answer` với `partial_coverage`. Không gộp
hai hạng bằng chứng thành một.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from src.services.doc_tai_lieu import (
    NGUONG_TIN_OCR,
    DonViVanBan,
    KhongDocDuoc,
    LoaiHong,
    NguonChu,
    co_ocr,
    doc,
)

PDF_CHU = Path("tests/fixtures/tieng-viet-co-dau.pdf")
ANH = Path("tests/fixtures/tieng-viet-scan.png")

pytestmark = pytest.mark.skipif(not co_ocr(), reason="cần tesseract + gói ngôn ngữ vie")


@pytest.fixture(scope="module", autouse=True)
def _dung_anh():
    """Dựng ảnh thử từ PDF đã có, để kho mã không phải giữ hai tệp nhị phân."""
    if ANH.exists():
        return
    subprocess.run(
        ["pdftoppm", "-r", "200", "-png", "-f", "1", "-l", "1", str(PDF_CHU), str(ANH.with_suffix(""))],
        check=True,
        capture_output=True,
    )
    Path(str(ANH.with_suffix("")) + "-1.png").rename(ANH)


# ────────────────────────────────────────────────────────────── ảnh


def test_ANH_doc_duoc_va_GIU_DAU_tieng_Viet():
    t = doc("scan.png", ANH.read_bytes())
    chu = " ".join(d.noi_dung for d in t.don_vi)
    assert "Mức lương" in chu, chu
    assert "20.000.000" in chu


def test_ANH_danh_dau_nguon_chu_la_OCR():
    """Đây là dòng quan trọng nhất file này."""
    t = doc("scan.png", ANH.read_bytes())
    assert all(d.nguon_chu is NguonChu.ocr for d in t.don_vi)
    assert all(d.do_tin is not None for d in t.don_vi)


def test_PDF_CO_lop_chu_KHONG_bi_gan_nhan_OCR():
    t = doc("hd.pdf", PDF_CHU.read_bytes())
    assert all(d.nguon_chu is NguonChu.lop_chu for d in t.don_vi)
    assert all(d.do_tin is None for d in t.don_vi)


def test_do_tin_nam_trong_0_1():
    t = doc("scan.png", ANH.read_bytes())
    assert all(0.0 <= d.do_tin <= 1.0 for d in t.don_vi)


def test_NGUONG_TIN_OCR_la_hang_so_neu_ten_duoc():
    assert 0.0 < NGUONG_TIN_OCR < 1.0


def test_anh_trang_khong_co_chu_la_khong_co_lop_chu():
    """Một ảnh trắng không sinh ra dữ kiện, và nói rõ lý do."""
    import struct
    import zlib

    def _png_trang(w=200, h=100) -> bytes:
        raw = b"".join(b"\x00" + b"\xff" * (w * 3) for _ in range(h))
        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw))
                + chunk(b"IEND", b""))

    with pytest.raises(KhongDocDuoc) as e:
        doc("trang.png", _png_trang())
    assert e.value.ly_do is LoaiHong.khong_co_lop_chu


# ─────────────────────────────────────────────────── PDF không lớp chữ


def test_PDF_khong_lop_chu_TU_CHUYEN_sang_OCR(tmp_path):
    """Bản scan là PDF bọc ảnh. Trước đây bị từ chối; giờ đọc được, nhưng
    KHÔNG được đánh đồng với PDF có lớp chữ."""
    if not shutil.which("cupsfilter"):
        pytest.skip("cần cupsfilter để dựng PDF-ảnh")
    ra = tmp_path / "scan.pdf"
    kq = subprocess.run(["cupsfilter", str(ANH)], capture_output=True)
    if kq.returncode != 0 or not kq.stdout.startswith(b"%PDF"):
        pytest.skip("cupsfilter không dựng được PDF từ ảnh")
    ra.write_bytes(kq.stdout)

    t = doc("scan.pdf", ra.read_bytes())
    assert any("Mức lương" in d.noi_dung for d in t.don_vi), [d.noi_dung for d in t.don_vi]
    assert all(d.nguon_chu is NguonChu.ocr for d in t.don_vi)
    assert t.co_ocr is True


# ──────────────────────────────────────────────────────── định dạng


@pytest.mark.parametrize("ten", ["a.png", "a.jpg", "a.jpeg", "a.tif", "a.tiff", "a.webp"])
def test_cac_duoi_anh_deu_duoc_nhan(ten):
    """Không nhận thì rơi vào `dinh_dang_khong_ho_tro`, và đó là câu trả lời SAI
    cho người vừa chụp giấy tờ bằng điện thoại."""
    try:
        doc(ten, ANH.read_bytes())
    except KhongDocDuoc as e:
        assert e.ly_do is not LoaiHong.dinh_dang_khong_ho_tro, ten


def test_dinh_dang_thuc_su_khong_ho_tro_van_bi_tu_choi():
    with pytest.raises(KhongDocDuoc) as e:
        doc("bang-tinh.xlsx", b"PK\x03\x04")
    assert e.value.ly_do is LoaiHong.dinh_dang_khong_ho_tro


def test_co_ocr_bao_dung_trang_thai_may():
    assert co_ocr() is bool(shutil.which("tesseract"))


def test_DonViVanBan_mac_dinh_la_lop_chu():
    """Mặc định an toàn: không khai báo thì là chữ thật, không phải phỏng đoán —
    ngược lại sẽ hạ cấp im lặng mọi nguồn đã có."""
    d = DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="x")
    assert d.nguon_chu is NguonChu.lop_chu and d.do_tin is None
