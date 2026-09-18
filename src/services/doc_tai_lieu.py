"""Đọc tài liệu người dùng thành các đơn vị văn bản có vị trí (spec 2026-09-15
§FR-001..FR-005). Thuần Python, 0 token — nhưng KHÔNG "không I/O ngoài bộ
nhớ" tuyệt đối (sửa fix round 2, task review — Minor #2: câu cũ ở đây không
còn đúng). `.pdf`/`.docx`/ảnh đọc thẳng từ bytes, đúng như câu cũ mô tả. OCR
(`_ocr_anh`/`_ocr_pdf`, `tesseract`/`pdftoppm`) và `.doc`
(`_chuyen_doc_sang_docx`, LibreOffice) thì KHÔNG: cả hai gọi công cụ ngoài chỉ
đọc được tệp trên đĩa, nên phải ghi tạm ra `tempfile` trước — luôn xoá khi
hàm trả về hoặc ném lỗi, trừ phi tiến trình bị giết/hết bộ nhớ giữa chừng
(xem docstring `_chuyen_doc_sang_docx`).

Hai quyết định định hình toàn bộ file:

**Đơn vị không bao giờ bị gộp.** Mỗi đoạn, mỗi ô bảng đứng riêng. Đây là điều
kiện để FR-010 có nghĩa: một đoạn trích phải nằm gọn trong một đơn vị. Nối các
đơn vị lại tạo ra những vết ghép không tồn tại trong tài liệu gốc, và một đoạn
trích vắt qua hai ô bảng sẽ khớp dù nó không nguyên văn ở bất kỳ đâu — đúng chế
độ hỏng mà `verify_tier1._tim_quote` đã chặn cho trích dẫn điều luật bằng cách
so với TỪNG DÒNG `provisions` thay vì nối cả cây.

**Bốn nguyên nhân hỏng là bốn mã riêng.** "Không hỗ trợ", "tệp hỏng", "cần mật
khẩu" và "không có lớp chữ" đòi bốn câu trả lời khác nhau cho người dùng: đổi
định dạng, gửi lại tệp, bỏ mật khẩu, hoặc gửi bản gốc thay vì bản chụp. Gộp
chúng thành một nhãn "không đọc được" là vứt đi thứ duy nhất giúp họ tự sửa.
"""

import logging
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, replace
from enum import StrEnum
from io import BytesIO
from math import ceil

logger = logging.getLogger(__name__)

# ponytail: DOCX không có khái niệm trang cố định — số trang phụ thuộc máy in,
# lề và font lúc mở. Quy đổi theo ký tự là xấp xỉ có chủ đích, chỉ dùng để chọn
# đường xử lý tại chỗ hay chạy nền (FR-029/030), không bao giờ hiện cho người
# dùng như số trang thật. Đổi một chỗ này nếu đo lại thấy lệch.
KY_TU_MOI_TRANG = 3000

_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_DUOI_ANH = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".heic")
_DUOI_HO_TRO = (".pdf", ".docx", ".doc", *_DUOI_ANH)

# .doc là OLE2/CFB (Compound File Binary), không phải zip+XML — không đọc trực
# tiếp được bằng `zipfile`. Chuyển sang .docx bằng LibreOffice headless rồi TÁI
# DÙNG `_doc_docx` KHÔNG ĐỔI GÌ: đo trên BM.M05 thật (`.sdd/phase-13-brief.md`),
# vòng .doc -> .docx giữ nguyên số đoạn, số bảng và tỉ lệ cột — viết một bộ đọc
# .doc riêng (kiểu antiword) sẽ vứt bỏ đúng những gì Phase 8/9/11 dựng lên.
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# LibreOffice là một tiến trình con nhận dữ liệu KHÔNG ĐÁNG TIN (CVE history có
# thật). 60 giây: soffice khởi động nguội mất vài giây, một .doc hợp lệ dưới
# trần TRAN_BYTE (20 MB, `tai_lieu.kiem_kich_thuoc`) chuyển xong trong vài giây
# nữa — một tệp CỐ Ý làm treo bộ phân tích OLE2 phải lộ ra trong một phút, không
# phải đợi hết `_HAN_TREO_GIAY` (300s) vốn đo cho OCR cả trang ảnh, việc nặng
# hơn nhiều lần.
_HAN_CHUYEN_DOI_GIAY = 60

# Fix round 1 (task review) — `soffice` là một wrapper thực thi `soffice.bin`,
# và bản thân LibreOffice có thể tự sinh thêm tiến trình của riêng nó (không
# phải lúc nào cũng exec-thay-thế PID mà `Popen` đang giữ). Diệt riêng PID
# trực tiếp — hành vi mặc định của `subprocess.run(timeout=...)` — có thể để
# lại một tiến trình `soffice.bin` mồ côi vẫn giữ tệp và thư mục hồ sơ tạm; vài
# lượt tải hỏng liên tiếp tích thành một rò rỉ tiến trình trên một endpoint
# công khai. 5 giây: đủ để SIGKILL có tác dụng và tiến trình được dọn (reap)
# trong mọi trường hợp bình thường; không cần dài hơn vì SIGKILL không đợi
# được sự hợp tác của tiến trình bị giết.
_HAN_XAC_NHAN_DA_GIET_GIAY = 5

# Fix round 2 (task review, Important) — mỗi lần chuyển đổi chiếm MỘT luồng
# của pool threadpool dùng chung (anyio mặc định 40 luồng, xem `bao_ve` cổng
# lá chắn — CHÍNH luồng đó cũng phục vụ mọi lệnh gọi DB khác của ứng dụng)
# trong tối đa `_HAN_CHUYEN_DOI_GIAY` (60s), và tự bản thân soffice giữ một
# lượng RAM đáng kể mỗi lần chạy — đo THẬT trên máy này: một tiến trình
# soffice.bin chuyển MỘT .doc nhỏ chiếm ~171 MB RSS (`ps -o rss`). Không có gì
# ở tầng trên chặn số lượt CHẠY ĐỒNG THỜI: giới hạn theo IP (10/60s,
# `bao_ve.rate_limit_ip_so_luot`) chặn được TẦN SUẤT của một IP, không chặn
# được TỔNG số phiên đang xử lý từ nhiều IP cùng lúc, và hạn mức tài liệu/ngày
# không có trần đồng thời nào cả.
#
# 3 suất: 3 × ~171 MB ≈ 513 MB RAM đỉnh cho riêng phần chuyển đổi — một mức
# đủ nhỏ để không đánh cược cả container, và chỉ chiếm tối đa 3/40 luồng
# threadpool ngay cả khi cả ba suất đều bận, để phần còn lại của ứng dụng
# (mọi truy vấn DB, mọi lệnh gọi mô hình khác) luôn còn ít nhất 37 luồng tự
# do. Con số RAM/container thật (Railway) chưa đo được — trần đang tạm dừng —
# nên đổi số này khi có số đo thật từ môi trường triển khai.
_SO_CHUYEN_DOI_DONG_THOI = 3

# Một request KHÔNG giành được suất phải biết NGAY, không chờ vô hạn — "hàng
# đợi im lặng" là một lỗi của chính nó (task review). 10s: đủ để một đợt tải
# dồn dập ngắn (vài .doc tới cùng lúc) tự giải phóng chỗ nếu một suất đang
# chuyển đổi sắp xong (đo thật: một .doc nhỏ dưới trần kích thước chuyển đổi
# trong vài giây), mà vẫn đủ ngắn để KHÔNG biến một lượt tải quá tải thành
# một request treo gần bằng `_HAN_CHUYEN_DOI_GIAY`.
_HAN_CHO_SUAT_GIAY = 10

# Semaphore ĐẾM — bị chiếm/nhả quanh CHÍNH việc chạy soffice (không quanh
# toàn bộ `_chuyen_doc_sang_docx`, để một .doc không phải OLE2 hay một máy
# chủ thiếu LibreOffice bị từ chối NGAY, không phải xếp hàng chờ một tài
# nguyên nó sẽ không bao giờ cần).
_suat_chuyen_doi = threading.Semaphore(_SO_CHUYEN_DOI_DONG_THOI)

# Dưới ngưỡng này thì chữ OCR đọc ra là nhiễu chứ không phải nội dung. Đo trên
# một trang sạch: tesseract `vie` cho 92–96%. Để 0.60 vì trang chụp nghiêng, mờ
# hay thiếu sáng tụt xuống khoảng 70–80% mà vẫn đọc đúng.
# ponytail: một ngưỡng cho cả trang; tách theo vùng nếu đo thấy cần.
NGUONG_TIN_OCR = 0.60

# DPI rasterize PDF-ảnh. 200 đủ cho chữ 10–12pt; cao hơn chỉ tốn thời gian.
_DPI_OCR = 200

# Chặn tiến trình TREO, không phải chặn chạy lâu. FR-032 cấm huỷ vì chạy lâu;
# một `tesseract` treo thì không phải đang chạy lâu, nó đang không chạy nữa.
_HAN_TREO_GIAY = 300

# Phanh zip bom. `tai_lieu.kiem_kich_thuoc` đo tệp ĐÃ NÉN, nên 64 MB số 0 nén
# lại còn vài chục KB đi lọt qua nó và nở ra trong RAM lúc đọc. Hai con số dưới
# đây đo cái zip KHAI BÁO, trước khi giải nén một byte nào. Một DOCX thật có
# vài chục mục và vài MB giải nén, nên trần này chỉ chạm tệp dựng ra để phá.
TRAN_SO_MUC_ZIP = 512
TRAN_GIAI_NEN_BYTE = 64 * 1024 * 1024


class NguonChu(StrEnum):
    """Chữ này đến từ đâu — và vì thế đáng tin tới đâu.

    `lop_chu` là chữ THẬT của tài liệu, đọc thẳng từ tệp. `ocr` là PHỎNG ĐOÁN
    của máy nhìn vào ảnh. Hai hạng bằng chứng khác nhau, không bao giờ gộp:
    nếu OCR đọc "20.000.000" thành "2O.OOO.OOO" thì đoạn trích vẫn khớp với đầu
    ra OCR, phép tra chuỗi vẫn chạy đúng, nhưng nó không còn chứng minh được
    điều người dùng tưởng. Bằng chứng yếu đi trong khi giao diện trông y hệt —
    đúng chế độ hỏng nguy hiểm nhất của một sản phẩm pháp lý.
    """

    lop_chu = "lop_chu"
    ocr = "ocr"


class LoaiHong(StrEnum):
    """Mỗi nguyên nhân có ĐÚNG MỘT mã của riêng nó (FR-003)."""

    dinh_dang_khong_ho_tro = "dinh_dang_khong_ho_tro"
    tep_hong = "tep_hong"
    can_mat_khau = "can_mat_khau"
    khong_co_lop_chu = "khong_co_lop_chu"


class KhongDocDuoc(Exception):  # noqa: N818
    """Tài liệu không đọc được, kèm nguyên nhân phân biệt được."""

    def __init__(self, ly_do: LoaiHong, chi_tiet: str = "") -> None:
        super().__init__(f"{ly_do}: {chi_tiet}" if chi_tiet else str(ly_do))
        self.ly_do = ly_do
        self.chi_tiet = chi_tiet


class ChuyenDoiKhongSanSang(Exception):  # noqa: N818
    """Nhánh chuyển đổi .doc không làm được việc NGAY BÂY GIỜ — vì HỆ THỐNG,
    không phải vì tài liệu của người dùng (fix round 2, task review — Important
    và Minor #4).

    Cố tình KHÔNG phải một `LoaiHong`/`KhongDocDuoc` thứ năm: FR-003 xếp bốn
    nguyên nhân đó theo tính chất của CHÍNH tài liệu (định dạng, hỏng, mật
    khẩu, không lớp chữ) — mỗi nguyên nhân người dùng có thể tự sửa bằng cách
    đổi tệp họ gửi. Hai nguyên nhân ở đây thì người dùng không sửa được gì cả:

    - `"khong_co_cong_cu"` — máy chủ chưa cài LibreOffice. Lỗi CẤU HÌNH, cần
      người vận hành sửa, không tự hết.
    - `"qua_tai"` — không giành được một suất chuyển đổi trong thời gian chờ
      hợp lý (`_HAN_CHO_SUAT_GIAY`). TẠM THỜI, tự hết khi tải giảm.

    Cả hai đều: không đáng tính vào hạn mức tài liệu/ngày của người dùng
    (cùng nguyên tắc `vuot_tran_chi_phi` đã áp dụng — "hệ thống từ chối,
    không phải người dùng tiêu lượt"), và không đáng nhận cùng câu trả lời
    422 "tệp của bạn có vấn đề" mà `KhongDocDuoc` dùng cho bốn nguyên nhân
    trên — tầng API ánh xạ lớp này sang 503, không phải 422.
    """

    def __init__(self, ly_do: str, chi_tiet: str = "") -> None:
        super().__init__(f"{ly_do}: {chi_tiet}" if chi_tiet else ly_do)
        self.ly_do = ly_do
        self.chi_tiet = chi_tiet


@dataclass(frozen=True)
class DinhDangChu:
    """Định dạng chữ của MỘT `w:r`, kèm khoảng nó chiếm trong `noi_dung`.

    `[dau, cuoi)` là offset ký tự trên CHÍNH chuỗi `DonViVanBan.noi_dung` —
    biểu diễn duy nhất giữ được `noi_dung` y nguyên (xem docstring trường
    `DonViVanBan.dinh_dang`). Một run không có chữ (`<w:r><w:rPr><w:b/>
    </w:rPr></w:r>`, Word sinh ra thường xuyên) có `dau == cuoi`: nó vẫn là
    một điều tệp KHAI, chỉ không phủ ký tự nào.

    `doan`/`so` là toạ độ của run trong nguồn — `doan` là `w:p` thứ mấy trong
    ô bảng (luôn `0` với một đoạn thân bài, ở đó đơn vị LÀ đoạn), `so` là
    `w:r` thứ mấy trong chính `w:p` đó. Giữ chúng vì đây là thứ duy nhất truy
    ngược được một run về đúng chỗ nó đứng trong tệp, và `eval.run_trung_thuc`
    chấm theo đúng toạ độ ấy.

    `khai` là những gì `w:rPr` TRỰC TIẾP của run nói, NGUYÊN VĂN, theo thứ tự
    `_TEN_RPR` — `("b", "")` nghĩa là `<w:b/>` (bật, OOXML mặc định),
    `("b", "0")` nghĩa là `<w:b w:val="0"/>` (TẮT). Năm trường đã giải bên
    trên không thay được nó: chúng đã gộp cả thừa kế từ `w:rStyle` và
    `w:pPr/w:rPr`, nên không còn phân biệt được "tệp tự khai ở đây" với "thừa
    kế từ chỗ khác", mà đó đúng là điều một thước đo độ trung thực phải hỏi.
    """

    dau: int
    cuoi: int
    doan: int = 0
    so: int = 0
    dam: bool = False
    nghieng: bool = False
    gach: bool = False
    co: int = 0
    """Cỡ chữ theo NỬA điểm (`w:sz`, đơn vị của chính OOXML), `0` khi không
    khai. Giữ nguyên nửa điểm thay vì quy ra pt ở đây: `.docx` dùng lại đúng
    đơn vị này, và chia 2 quá sớm biến 27 (13,5pt — cỡ có thật trong thể thức
    hành chính Việt Nam) thành một số lẻ phải làm tròn hai lần."""
    phong: str = ""
    """Tên phông NGUỒN khai (`w:rFonts/@w:ascii`), `""` khi không khai. Giữ
    ĐÚNG tên nguồn, không quy đổi ở đây: `.docx` tải về ghi lại chính tên này
    (Word có phông đó, hoặc tự thay), còn màn hình mới là nơi phải ánh xạ về
    một họ chữ thật sự có trong kho — hai câu trả lời khác nhau cho cùng một
    sự thật, nên sự thật được giữ nguyên ở đây."""
    khai: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DonViVanBan:
    """Một mẩu văn bản liền mạch trong tài liệu, kèm chỗ nó nằm.

    `offset_dau` tính theo ký tự TRONG TRANG, không tính toàn tài liệu: người
    dùng định vị bằng cặp (trang, vị trí trong trang), và trang là thứ họ thấy.
    """

    chi_so: int
    trang: int
    offset_dau: int
    noi_dung: str
    nguon_chu: NguonChu = NguonChu.lop_chu
    """Mặc định là chữ thật: không khai báo thì KHÔNG bị hạ cấp im lặng."""
    do_tin: float | None = None
    """0–1, chỉ có với `ocr`. `None` với chữ đọc thẳng — ở đó không có gì để đoán."""
    vung: str = "than"
    """`than` | `dau_trang` | `chan_trang`.

    Đầu trang và chân trang là NGUỒN KHÁC với thân bài: số hiệu biểu mẫu, tên
    đơn vị ban hành, số trang. Trộn chúng vào thân là nói sai chỗ một câu được
    viết, và một neo tài liệu chỉ vào "trang 1" của một chân trang lặp lại ở
    mọi trang thì không chỉ vào đâu cả.
    """
    bang: tuple[int, int, int] | None = None
    """(chỉ số bảng, hàng, cột) — ĐẾM TỪ 0, `None` khi đơn vị không ở trong bảng.

    Với phiếu chấm, biểu mẫu, bảng lương thì bảng LÀ nội dung: "2,0" một mình
    không nói gì, "2,0 ở hàng Chuyên cần" mới nói. Giao diện cộng 1 khi hiển
    thị cho người đọc; ở đây giữ chỉ số để cùng gốc với `chi_so`.
    """
    can_le: str = "trai"
    """`trai` | `giua` | `phai` (Phase 9 U5) — căn lề THẬT của đoạn/ô này, đọc
    từ `w:pPr/w:jc` hoặc, khi vắng (nghĩa là "thừa kế"), từ kiểu đoạn văn của
    nó (`w:pStyle`, theo hết chuỗi `w:basedOn`). Mặc định `trai`: DOCX không
    khai báo `jc` là căn trái, không phải "chưa biết" — cùng lý lẽ `vung`
    không được suy diễn thêm gì ngoài những gì tệp nói.
    """
    bang_nhip: int = 1
    """Số cột LƯỚI ô này CHIẾM (Phase 11 R6) — đọc `w:tcPr/w:gridSpan/@w:val`,
    mặc định 1 (không gộp ngang). `bang[2]` (cột) đã là cột lưới THẬT, cộng
    dồn nhịp các ô đứng trước trong CÙNG hàng — không còn là số thứ tự ô đến
    thứ mấy. Cần trường riêng vì một ô gộp 2 cột vẫn CHỈ là một đơn vị (một
    `w:tc`), và số cột nó chiếm là sự thật thứ hai, khác với vị trí nó bắt đầu.
    """
    bang_ti_le: tuple[int, ...] = ()
    """% mỗi cột lưới trên tổng bề rộng BẢNG mà ô này thuộc về (Phase 11 R1),
    đọc từ `w:tblGrid/w:gridCol` — GIỐNG NHAU trên mọi ô của cùng một bảng,
    cùng cách `bang`/`vung` tự mô tả theo từng đơn vị thay vì một bảng tra
    riêng. Rỗng khi bảng không khai `w:tblGrid`: không suy đoán tỉ lệ, để
    phía render tự quyết định (chia đều) — cùng nguyên tắc không suy diễn
    thêm gì ngoài những gì tệp nói.
    """
    bang_vien: bool = True
    """Bảng chứa ô này có VẼ viền không — đọc `w:tblBorders`/`w:tcBorders`
    (và kiểu bảng `w:tblStyle`), xem `_vien_bang`.

    Biểu mẫu tiếng Việt dùng một bảng KHÔNG viền để xếp cột: cặp ô ký tên
    cuối trang, hay khối "quốc hiệu bên phải, tên đơn vị bên trái" ở đầu
    trang. Trước trường này, render vẽ viền cho MỌI bảng, nên một khối ký
    hai cột ra màn hình thành một cái lưới có kẻ ô — đúng loại "suy diễn
    thêm ngoài những gì tệp nói" mà `bang_ti_le` ở trên từ chối làm với tỉ lệ
    cột.

    Mặc định `True` chứ không `False`: chỗ DUY NHẤT đọc được sự thật này là
    `_duyet_than` (nó luôn đặt giá trị thật cho mọi ô bảng), nên mặc định chỉ
    còn tác dụng cho dòng LƯU TRƯỚC trường này tồn tại — ở đó "vẽ viền như
    cũ" là câu trả lời không đổi hành vi, còn `False` sẽ xoá viền của mọi
    tài liệu đã đọc xong trước bản vá.
    """
    bang_cao: int = 0
    """Chiều cao KHAI BÁO của HÀNG chứa ô này, đơn vị twip (1/20 pt) — đọc
    `w:trPr/w:trHeight/@w:val`, `0` khi hàng không khai.

    Đây là thứ cho một hàng ký chỗ trống để ký tay: hàng ký của BM.ĐT.18.05
    khai 1499 twip (~2,6 cm) trong khi chữ của nó chỉ chiếm hai dòng. Bỏ số
    này thì bảng vẫn hết viền nhưng vẫn không có chỗ ký.

    KHÔNG phân biệt `hRule="exact"` với `"atLeast"`: cả hai đọc thành chiều
    cao TỐI THIỂU khi vẽ. `exact` nghĩa là Word CẮT phần chữ tràn ra, và cắt
    mất chữ của người dùng là hỏng tệ hơn nhiều so với một hàng cao hơn khai
    báo vài milimét.
    """
    dinh_dang: tuple[DinhDangChu, ...] = ()
    """Định dạng chữ ở mức run (`w:rPr`) của đơn vị này — quyết định
    2026-09-18, mục "định dạng chữ ở mức run".

    Là một DÃY KHOẢNG trên chính `noi_dung`, không phải một chuỗi đánh dấu
    thay cho nó: `noi_dung` vẫn là đúng chuỗi thuần trước bản vá này, ký tự
    nào cũng ở đúng chỗ cũ, nên `neo_du_kien.xac_minh`, `normalize`,
    `lam_sach_van_ban` và `bo_nho._vuong_luoi_chan` không hề biết trường này
    tồn tại. Nhét thẻ định dạng vào `noi_dung` sẽ phá tất cả cùng lúc — phép
    neo trích dẫn là bằng chứng của cả sản phẩm, không phải một chi tiết
    trình bày đánh đổi được.

    Rỗng khi nguồn không khai gì (và với mọi dòng lưu TRƯỚC trường này).
    Khoảng KHÔNG phủ kín `noi_dung`: chỗ không có khoảng nào là chỗ tệp
    không nói gì, và render giữ nguyên chữ thường ở đó.
    """


@dataclass(frozen=True)
class TaiLieuDaDoc:
    don_vi: list[DonViVanBan]
    so_trang: int
    so_ky_tu: int

    @property
    def co_ocr(self) -> bool:
        """Tài liệu này có phần nào đọc bằng OCR không — người dùng phải biết."""
        return any(d.nguon_chu is NguonChu.ocr for d in self.don_vi)


def co_ocr() -> bool:
    """Máy này chạy được OCR không. Thiếu tesseract thì nhánh ảnh phải nói thật
    là không đọc được, chứ không im lặng trả về tài liệu rỗng."""
    return shutil.which("tesseract") is not None


def doc(ten_tep: str, du_lieu: bytes) -> TaiLieuDaDoc:
    """Đọc `du_lieu` thành các đơn vị văn bản, hoặc ném `KhongDocDuoc`.

    Vào bằng bytes, ra bằng dataclass; người gọi chịu trách nhiệm buông tham
    chiếu ngay khi hàm này trả về hoặc ném lỗi — tinh thần FR-022. Nhánh
    `.pdf`/`.docx`/ảnh giữ đúng lời hứa cũ, KHÔNG ghi gì ra đĩa. Nhánh `.doc`
    thì KHÔNG (sửa fix round 2, task review — Minor #2: câu cũ ở đây khẳng
    định sai cho nhánh này): `_chuyen_doc_sang_docx` cần một tệp thật trên
    đĩa để LibreOffice đọc — không có cách chuyển đổi thuần bộ nhớ — và luôn
    xoá tệp tạm đó khi trả về hoặc ném lỗi, TRỪ PHI tiến trình bị SIGKILL/hết
    bộ nhớ đúng lúc đang chuyển đổi (residual, không phải một lỗ hổng mới —
    brief đã cho phép tệp tạm này tồn tại).
    """
    ten = (ten_tep or "").lower()
    if ten.endswith(".pdf"):
        thoi = _doc_pdf(du_lieu)
        if not thoi:
            # PDF bọc ảnh — bản scan trông đúng như vậy. Trước đây bị từ chối
            # thẳng; giờ thử OCR, nhưng kết quả mang nhãn `ocr` chứ không được
            # đánh đồng với PDF có lớp chữ.
            thoi = _ocr_pdf(du_lieu)
    elif ten.endswith(".docx"):
        thoi = _doc_docx(du_lieu)
    elif ten.endswith(".doc"):
        # Chuyển trước, đọc sau — bằng ĐÚNG một hàm `_doc_docx`, không nhánh
        # riêng nào biết tệp .docx này từng là .doc.
        thoi = _doc_docx(_chuyen_doc_sang_docx(du_lieu))
    elif ten.endswith(_DUOI_ANH):
        thoi = _ocr_anh(du_lieu)
    else:
        raise KhongDocDuoc(
            LoaiHong.dinh_dang_khong_ho_tro,
            f"chỉ hỗ trợ {', '.join(_DUOI_HO_TRO)}",
        )

    if not thoi:
        raise KhongDocDuoc(LoaiHong.khong_co_lop_chu, "không rút được ký tự nào")
    return _dat_vi_tri(thoi)


# ------------------------------------------------------------------------ DOCX


_P = f"{{{_NS['w']}}}p"
_TBL = f"{{{_NS['w']}}}tbl"
_TR = f"{{{_NS['w']}}}tr"
_TC = f"{{{_NS['w']}}}tc"
_BODY = f"{{{_NS['w']}}}body"
_PPR = f"{{{_NS['w']}}}pPr"
_JC = f"{{{_NS['w']}}}jc"
_PSTYLE = f"{{{_NS['w']}}}pStyle"
_BASEDON = f"{{{_NS['w']}}}basedOn"
_TCPR = f"{{{_NS['w']}}}tcPr"
_GRIDSPAN = f"{{{_NS['w']}}}gridSpan"
_TBLGRID = f"{{{_NS['w']}}}tblGrid"
_GRIDCOL = f"{{{_NS['w']}}}gridCol"
_STYLE = f"{{{_NS['w']}}}style"
_TBLPR = f"{{{_NS['w']}}}tblPr"
_TBLSTYLE = f"{{{_NS['w']}}}tblStyle"
_TBLBORDERS = f"{{{_NS['w']}}}tblBorders"
_TCBORDERS = f"{{{_NS['w']}}}tcBorders"
_TRPR = f"{{{_NS['w']}}}trPr"
_TRHEIGHT = f"{{{_NS['w']}}}trHeight"
_R = f"{{{_NS['w']}}}r"
_RPR = f"{{{_NS['w']}}}rPr"
_RSTYLE = f"{{{_NS['w']}}}rStyle"
_T = f"{{{_NS['w']}}}t"
_VAL = f"{{{_NS['w']}}}val"
_ASCII = f"{{{_NS['w']}}}ascii"

# Năm thuộc tính `w:rPr` đọc được (quyết định 2026-09-18). Thứ tự này là thứ
# tự `DinhDangChu.khai` ghi ra, để hai lần đọc cùng một tệp cho cùng một dãy.
_TEN_RPR = ("b", "i", "u", "sz", "rFonts")

# `w:val` của một thuộc tính BẬT/TẮT (`ST_OnOff`) nghĩa là TẮT. Thiếu tập này
# thì `<w:b w:val="0"/>` — cách Word ghi "BỎ đậm" cho một run nằm trong một
# kiểu vốn in đậm — đọc thành ĐẬM, và cả biểu mẫu ra màn hình đen sì (chế độ
# hỏng đã gặp thật một lần: "mọi đoạn đều đậm").
_TAT = {"0", "false", "off"}

# `w:u` KHÔNG phải thuộc tính bật/tắt: nó mang KIỂU gạch (`single`, `dotted`,
# `wave`…) và `none` nghĩa là không gạch. Chuỗi rỗng = `<w:u/>` không có
# `w:val`: OOXML để mặc định kiểu gạch là `none`, nên không suy diễn thành có
# gạch — cùng luật "chỉ đọc những gì tệp nói" của `bang_ti_le`.
_KHONG_GACH = _TAT | {"none", ""}

# `w:val` của một cạnh viền nghĩa là KHÔNG vẽ. Mọi giá trị khác (`single`,
# `double`, `dotted`…) đều là một nét thật. Không xét `w:sz="0"`: OOXML vẫn coi
# đó là một cạnh có kiểu, và đoán rằng nó "coi như không có" là suy diễn thêm
# ngoài những gì tệp nói.
_VIEN_KHONG_VE = {"none", "nil"}

# OOXML `w:jc` → `DonViVanBan.can_le` (Phase 9 U5). Chỉ "center"/"right"/"end"
# đổi khỏi trái: "left"/"start"/"both" (căn đều) và mọi giá trị lạ đọc như
# người xem thường thấy — căn đều trông giống căn trái, không giống căn giữa.
_JC_RA_CAN_LE = {"center": "giua", "right": "phai", "end": "phai"}


def _can_le_gia_tri(v: str | None) -> str:
    return _JC_RA_CAN_LE.get(v or "", "trai")


def _kieu_can_le(goc_styles: ET.Element | None) -> dict[str, str]:
    """id kiểu đoạn văn → giá trị `w:jc` THẬT của kiểu đó, đã theo hết chuỗi
    `w:basedOn` — `styles.xml` có thể vắng mặt (DOCX không bắt buộc phần này),
    và một kiểu có thể không tự khai `jc` mà thừa kế từ kiểu nó dựa vào."""
    if goc_styles is None:
        return {}
    truc_tiep: dict[str, str] = {}
    cha: dict[str, str] = {}
    for st in goc_styles.findall(_STYLE):
        sid = st.get(f"{{{_NS['w']}}}styleId")
        if not sid:
            continue
        b = st.find(_BASEDON)
        if b is not None and (v := b.get(f"{{{_NS['w']}}}val")):
            cha[sid] = v
        jc = st.find(f"{_PPR}/{_JC}")
        if jc is not None and (v := jc.get(f"{{{_NS['w']}}}val")):
            truc_tiep[sid] = v

    def _giai(sid: str | None, di_qua: frozenset[str]) -> str | None:
        if sid is None or sid in di_qua:
            return None
        if sid in truc_tiep:
            return truc_tiep[sid]
        return _giai(cha.get(sid), di_qua | {sid})

    return {sid: v for sid in {*truc_tiep, *cha} if (v := _giai(sid, frozenset()))}


def _can_le_doan(p: ET.Element | None, theo_kieu: dict[str, str]) -> str:
    """Căn lề THẬT của một `w:p` — trực tiếp (`w:pPr/w:jc`) nếu có; vắng mặt
    thì theo kiểu đoạn văn của nó (`w:pStyle`, đã giải qua `_kieu_can_le`),
    KHÔNG mặc định trái ngay: `jc` vắng mặt trên `w:p` nghĩa là "thừa kế kiểu",
    và một tài liệu căn giữa bằng KIỂU (không phải định dạng trực tiếp) đọc
    thẳng `jc` trên từng đoạn sẽ luôn ra trái, sai với chính tài liệu đó."""
    if p is None:
        return "trai"
    jc = p.find(f"{_PPR}/{_JC}")
    if jc is not None:
        return _can_le_gia_tri(jc.get(f"{{{_NS['w']}}}val"))
    kieu = p.find(f"{_PPR}/{_PSTYLE}")
    sid = kieu.get(f"{{{_NS['w']}}}val") if kieu is not None else None
    return _can_le_gia_tri(theo_kieu.get(sid) if sid else None)


def _nhip_o(tc: ET.Element) -> int:
    """Số cột lưới một Ô CHIẾM (Phase 11 R6) — `w:tcPr/w:gridSpan/@w:val`, mặc
    định 1. Đọc trực tiếp thay vì suy từ số ô trong hàng: một hàng ngắn hơn
    hàng tiêu đề có thể là do MỘT ô gộp (nhịp > 1) hoặc do các ô cuối THẬT SỰ
    không tồn tại (đã đọc hết, không còn `w:tc` nào) — hai ca khác nhau, và chỉ
    tệp mới nói được ca nào đang xảy ra, không phải phép đếm chênh lệch."""
    gs = tc.find(f"{_TCPR}/{_GRIDSPAN}")
    if gs is None:
        return 1
    try:
        n = int(gs.get(f"{{{_NS['w']}}}val") or "1")
    except ValueError:
        return 1
    return n if n > 0 else 1


def _ti_le_luoi(tbl: ET.Element) -> tuple[int, ...]:
    """% mỗi cột lưới trên tổng bề rộng BẢNG — `w:tblGrid/w:gridCol` (Phase 11
    R1). Rỗng khi bảng không khai lưới; phía render tự quyết định chia đều,
    không suy đoán tỉ lệ ở đây.

    Làm tròn TỪNG cột ĐỘC LẬP theo tổng của chính bảng đó — `sum(gridCol)`
    không nhất thiết bằng bề rộng thân trang (đo trên form thật: 10371/9062/
    8950 twips cho một thân 9072 twips, đây là ca THƯỜNG chứ không phải ca
    hiếm), nên phép quy đổi luôn tính theo TỔNG của chính bảng. Không dồn phần
    dư làm tròn vào cột nào: tổng các % có thể lệch 100 một chút (vd 101, đo
    được trên BM.ĐT.18.05 — 7/15/30/34/15), và một cột lệch 1% không đáng để
    đổi số đo trực tiếp của MỘT cột thành số đã bị nắn cho tổng tròn.
    """
    grid = tbl.find(_TBLGRID)
    if grid is None:
        return ()
    rong = [v for g in grid.findall(_GRIDCOL) if (w := g.get(f"{{{_NS['w']}}}w")) and (v := int(w)) > 0]
    tong = sum(rong)
    if not rong or tong <= 0:
        return ()
    return tuple(round(w * 100 / tong) for w in rong)


def _co_net(vien: ET.Element) -> bool:
    """Một nhóm viền (`w:tblBorders`/`w:tcBorders`) có vẽ cạnh nào không —
    đúng một cạnh khai giá trị ngoài `none`/`nil` là đủ."""
    return any(c.get(f"{{{_NS['w']}}}val") not in _VIEN_KHONG_VE for c in vien)


def _kieu_vien_bang(goc_styles: ET.Element | None) -> dict[str, bool]:
    """id kiểu BẢNG → kiểu đó có vẽ viền không, đã theo hết chuỗi `w:basedOn`.

    Cần vì `TableGrid` (kiểu bảng có viền sẵn của Word) là cách phổ biến nhất
    để một biểu mẫu tiếng Việt có viền: bảng đó KHÔNG khai `w:tblBorders` nào
    trong `document.xml`, chỉ khai `w:tblStyle`. Bỏ qua styles.xml là đọc mọi
    bảng TableGrid thành không viền — đúng thứ "bỏ mất một nét tệp có vẽ" mà
    bản vá này tồn tại để tránh.

    KHÔNG dùng chung vòng duyệt với `_kieu_can_le`: hai bên đọc hai thuộc
    tính khác kiểu (chuỗi `w:jc` với một bool gộp từ nhiều cạnh) và gộp thừa
    kế khác nhau, nên gộp lại thành một hàm tổng quát chỉ để tiết kiệm sáu
    dòng đi chuỗi `basedOn` sẽ làm đường căn lề đang chạy đúng khó đọc hơn.

    Trần đã biết: kiểu con khai `w:tblBorders` thì CHẶN hẳn kiểu cha, không
    trộn theo từng cạnh như Word làm. Trộn theo cạnh chỉ đổi kết quả khi một
    kiểu con tắt đúng vài cạnh của cha — ở đó câu trả lời "bảng này có viền"
    vẫn đúng, chỉ là hình dạng viền không được tả đủ, mà một cờ bool thì
    không tả được hình dạng nào cả.
    """
    if goc_styles is None:
        return {}
    truc_tiep: dict[str, bool] = {}
    cha: dict[str, str] = {}
    for st in goc_styles.findall(_STYLE):
        sid = st.get(f"{{{_NS['w']}}}styleId")
        if not sid or st.get(f"{{{_NS['w']}}}type") != "table":
            continue
        b = st.find(_BASEDON)
        if b is not None and (v := b.get(f"{{{_NS['w']}}}val")):
            cha[sid] = v
        vien = st.find(f"{_TBLPR}/{_TBLBORDERS}")
        if vien is not None:
            truc_tiep[sid] = _co_net(vien)

    def _giai(sid: str | None, di_qua: frozenset[str]) -> bool:
        if sid is None or sid in di_qua:
            return False
        if sid in truc_tiep:
            return truc_tiep[sid]
        return _giai(cha.get(sid), di_qua | {sid})

    return {sid: _giai(sid, frozenset()) for sid in {*truc_tiep, *cha}}


def _vien_bang(tbl: ET.Element, vien_kieu: dict[str, bool]) -> bool:
    """Bảng này có vẽ viền nào không (xem `DonViVanBan.bang_vien`).

    Ba nguồn, gộp bằng HOẶC vì câu hỏi là "tệp có vẽ nét nào không": viền
    cấp bảng (`w:tblPr/w:tblBorders`), kiểu bảng (`w:tblStyle`, đã giải qua
    `_kieu_vien_bang`), và viền cấp Ô (`w:tcPr/w:tcBorders`) — một bảng khai
    `nil` ở cấp bảng nhưng kẻ khung cho vài ô VẪN là một bảng có nét.

    Một cờ bool cho cả bảng là biểu diễn nhỏ nhất mà vẫn trung thực với chỗ
    dùng nó: cả ba nơi vẽ bảng (`XemTruocA4`, `.docx`, PDF) đều kẻ MỘT kiểu
    viền cho mọi ô, nên biết thêm "ô này mất cạnh phải" cũng không có chỗ
    nào diễn đạt được. Cờ này chỉ phân biệt đúng hai ca render làm được:
    "tệp không vẽ gì" với "tệp có vẽ".
    """
    pr = tbl.find(_TBLPR)
    if pr is not None:
        vien = pr.find(_TBLBORDERS)
        if vien is not None and _co_net(vien):
            return True
        kieu = pr.find(_TBLSTYLE)
        sid = kieu.get(f"{{{_NS['w']}}}val") if kieu is not None else None
        if sid and vien_kieu.get(sid):
            return True
    # Chỉ ô của CHÍNH bảng này (`findall`, không `iter`): một bảng lồng bên
    # trong một ô là bảng khác, và viền của nó không nói gì về bảng bao ngoài.
    return any(
        (v := tc.find(f"{_TCPR}/{_TCBORDERS}")) is not None and _co_net(v)
        for tr in tbl.findall(_TR)
        for tc in tr.findall(_TC)
    )


def _cao_hang(tr: ET.Element) -> int:
    """Chiều cao khai báo của một hàng, twip — `w:trPr/w:trHeight/@w:val`, `0`
    khi hàng không khai hoặc khai giá trị đọc không ra số (xem
    `DonViVanBan.bang_cao`)."""
    h = tr.find(f"{_TRPR}/{_TRHEIGHT}")
    if h is None:
        return 0
    try:
        n = int(h.get(f"{{{_NS['w']}}}val") or "0")
    except ValueError:
        return 0
    return n if n > 0 else 0


def _rpr_tho(rpr: ET.Element | None) -> dict[str, str]:
    """`w:rPr` → `{tên thuộc tính: giá trị NGUYÊN VĂN tệp khai}`.

    Khoá VẮNG MẶT nghĩa là tệp không khai thuộc tính đó ở cấp này — khác hẳn
    khai một giá trị tắt (`w:val="0"`), và chính chỗ phân biệt ấy làm cho phép
    xếp chồng bốn lớp ở `_dinh_dang_doan` đúng: một run không khai `w:b` phải
    THỪA KẾ đậm từ kiểu, còn một run khai `w:b w:val="0"` phải HUỶ nó.

    Giá trị `""` nghĩa là "có thẻ, không có `w:val`" (`<w:b/>` — bật, theo mặc
    định OOXML; `<w:u/>` — không gạch, theo mặc định của chính `w:u`).
    """
    if rpr is None:
        return {}
    ra: dict[str, str] = {}
    for ten in _TEN_RPR:
        e = rpr.find(f"{{{_NS['w']}}}{ten}")
        if e is None:
            continue
        # `w:rFonts` không có `w:val`; tên phông nằm ở `w:ascii`.
        ra[ten] = e.get(_VAL) or (e.get(_ASCII) or "" if ten == "rFonts" else "")
    return ra


def _kieu_dinh_dang_chu(goc_styles: ET.Element | None) -> dict[str, dict[str, str]]:
    """id kiểu → `w:rPr` của kiểu đó đã TRỘN hết chuỗi `w:basedOn` (con đè cha).

    Trộn theo TỪNG thuộc tính, không lấy nguyên khối của kiểu đầu tiên có khai
    như `_kieu_vien_bang` làm: một kiểu con chỉ khai `w:b` vẫn phải thừa kế cỡ
    chữ và tên phông của kiểu cha, và lấy nguyên khối sẽ xoá mất hai thuộc
    tính kia. Ở viền thì không có gì để trộn (một bool gộp sẵn), nên hai hàm
    không gộp chung được dù cùng đi một chuỗi `basedOn`.

    Nhận CẢ kiểu đoạn văn lẫn kiểu chữ, không lọc theo `w:type`: `w:pStyle`
    tra vào đây cho định dạng chữ mặc định của đoạn, `w:rStyle` tra vào đây
    cho định dạng của riêng run — hai lối tra khác nhau trên cùng một bảng.

    KHÔNG đọc `w:docDefaults`: quyết định 2026-09-18 đặt phạm vi ở chuỗi
    `w:rStyle`/`w:basedOn` và `w:pPr/w:rPr`. Hệ quả nhận rõ — một tài liệu chỉ
    khai cỡ chữ ở `docDefaults` sẽ đọc ra "không khai cỡ", và render giữ cỡ
    mặc định của chính nó.
    """
    if goc_styles is None:
        return {}
    truc_tiep: dict[str, dict[str, str]] = {}
    cha: dict[str, str] = {}
    for st in goc_styles.findall(_STYLE):
        sid = st.get(f"{{{_NS['w']}}}styleId")
        if not sid:
            continue
        b = st.find(_BASEDON)
        if b is not None and (v := b.get(_VAL)):
            cha[sid] = v
        truc_tiep[sid] = _rpr_tho(st.find(_RPR))

    def _giai(sid: str | None, di_qua: frozenset[str]) -> dict[str, str]:
        if sid is None or sid in di_qua or sid not in truc_tiep:
            return {}
        return {**_giai(cha.get(sid), di_qua | {sid}), **truc_tiep[sid]}

    return {sid: v for sid in truc_tiep if (v := _giai(sid, frozenset()))}


def _bat(v: str | None) -> bool:
    """Một thuộc tính bật/tắt OOXML: có khai và KHÔNG mang giá trị tắt."""
    return v is not None and v not in _TAT


def _nua_diem(v: str | None) -> int:
    """`w:sz/@w:val` → nửa điểm, `0` khi không khai hoặc khai thứ không đọc ra
    số (giữ nguyên luật `_cao_hang`: giá trị lạ đọc thành "không khai")."""
    try:
        n = int(v or "0")
    except ValueError:
        return 0
    return n if n > 0 else 0


def _vi_tri_chu(p: ET.Element) -> tuple[dict[int, tuple[int, int]], str]:
    """Mỗi `w:t` dưới `p` → khoảng nó chiếm trong chuỗi nối CHƯA cắt khoảng
    trắng, kèm chính chuỗi đó — cùng phép nối `_chu` dùng, để offset trả về
    đúng trên `_chu(p)` sau khi trừ phần `strip()` cắt đi."""
    vi: dict[int, tuple[int, int]] = {}
    phan: list[str] = []
    n = 0
    for t in p.iter(_T):
        s = t.text or ""
        vi[id(t)] = (n, n + len(s))
        n += len(s)
        phan.append(s)
    return vi, "".join(phan)


def _dinh_dang_doan(p: ET.Element, kieu_chu: dict[str, dict[str, str]], doan: int = 0) -> tuple[DinhDangChu, ...]:
    """Định dạng từng `w:r` của một `w:p`, offset tính trên đúng `_chu(p)`.

    BỐN lớp xếp chồng, lớp sau đè lớp trước — đúng thứ tự Word áp dụng:
    kiểu đoạn văn (`w:pPr/w:pStyle`), định dạng chữ của chính đoạn
    (`w:pPr/w:rPr`), kiểu chữ của run (`w:rPr/w:rStyle`), rồi `w:rPr` trực
    tiếp. Đọc thẳng `w:rPr` và bỏ ba lớp kia là đọc một biểu mẫu lấy chữ đậm
    TỪ KIỂU thành chữ thường — nó không khai `w:b` ở đâu trong `document.xml`
    cả, đúng cách `_can_le_doan` đã phải giải `w:pStyle` cho `w:jc`.

    `so` đếm theo `w:r` con TRỰC TIẾP của `w:p`. Chữ trong một `w:hyperlink`
    hay `w:smartTag` vẫn vào `noi_dung` (`_chu` duyệt `iter`), nhưng run của
    nó không được đánh số ở đây — nó không phải một `w:r` của đoạn này, và
    đánh số nó vào giữa dãy sẽ làm mọi run sau trỏ sai chỗ.

    Bỏ những run KHÔNG nói gì (không khai gì, không thừa kế gì): chúng là phần
    lớn số run của một tài liệu, và giữ lại chỉ làm biểu diễn phình ra mà
    không thêm một sự thật nào.
    """
    vi, tho = _vi_tri_chu(p)
    lech = len(tho) - len(tho.lstrip())
    het = len(tho.strip())

    def _ke(x: int) -> int:
        return min(max(x - lech, 0), het)

    nen: dict[str, str] = {}
    if (ppr := p.find(_PPR)) is not None:
        kieu = ppr.find(_PSTYLE)
        sid = kieu.get(_VAL) if kieu is not None else None
        nen = {**kieu_chu.get(sid or "", {}), **_rpr_tho(ppr.find(_RPR))}

    ra: list[DinhDangChu] = []
    cuoi_truoc = 0
    so = 0
    for con in p:
        # Tính khoảng cho MỌI con (kể cả `w:hyperlink`) trước khi bỏ qua nó:
        # con trỏ chữ phải đi qua chúng, nếu không mọi run sau sẽ lệch.
        if ts := list(con.iter(_T)):
            dau, cuoi = vi[id(ts[0])][0], vi[id(ts[-1])][1]
            cuoi_truoc = max(cuoi_truoc, cuoi)
        else:
            dau = cuoi = cuoi_truoc
        if con.tag != _R:
            continue
        rpr = con.find(_RPR)
        rs = rpr.find(_RSTYLE) if rpr is not None else None
        khai = _rpr_tho(rpr)
        gop = {**nen, **kieu_chu.get((rs.get(_VAL) or "") if rs is not None else "", {}), **khai}
        dam, nghieng = _bat(gop.get("b")), _bat(gop.get("i"))
        gach = (u := gop.get("u")) is not None and u not in _KHONG_GACH
        co, phong = _nua_diem(gop.get("sz")), gop.get("rFonts") or ""
        if khai or dam or nghieng or gach or co or phong:
            ra.append(
                DinhDangChu(
                    dau=_ke(dau),
                    cuoi=_ke(cuoi),
                    doan=doan,
                    so=so,
                    dam=dam,
                    nghieng=nghieng,
                    gach=gach,
                    co=co,
                    phong=phong,
                    khai=tuple((ten, khai[ten]) for ten in _TEN_RPR if ten in khai),
                )
            )
        so += 1
    return tuple(ra)


def _chu_va_dinh_dang_o(tc: ET.Element, kieu_chu: dict[str, dict[str, str]]) -> tuple[str, tuple[DinhDangChu, ...]]:
    """Chữ của một ô bảng và định dạng run của nó, offset dịch về chuỗi ô.

    Chữ ô là các `w:p` trong ô nối bằng MỘT dấu cách (`_duyet_than`), nên mỗi
    đoạn góp một đoạn offset riêng. Đoạn RỖNG chữ không góp chữ và không góp
    dấu cách, nhưng run của nó vẫn được giữ: một `w:p` rỗng khai `w:rPr` là
    một điều tệp nói, và `doan` vẫn đếm nó để toạ độ khớp với nguồn.
    """
    phan: list[str] = []
    ra: list[DinhDangChu] = []
    n = 0
    for j, p in enumerate(tc.iter(_P)):
        x = _chu(p)
        goc = n + (1 if phan and x else 0)
        ra.extend(replace(r, dau=r.dau + goc, cuoi=r.cuoi + goc) for r in _dinh_dang_doan(p, kieu_chu, j))
        if x:
            if phan:
                n += 1
            phan.append(x)
            n += len(x)
    return " ".join(phan), tuple(ra)


def _kiem_zip(z: zipfile.ZipFile) -> None:
    """Phanh zip bom, chạy TRƯỚC khi đọc bất kỳ mục nào — xem `TRAN_SO_MUC_ZIP`."""
    muc = z.infolist()
    if len(muc) > TRAN_SO_MUC_ZIP:
        raise KhongDocDuoc(LoaiHong.tep_hong, f"tệp docx có quá {TRAN_SO_MUC_ZIP} mục")
    if sum(m.file_size for m in muc) > TRAN_GIAI_NEN_BYTE:
        raise KhongDocDuoc(LoaiHong.tep_hong, "tệp docx giải nén ra quá lớn")


_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


def _bo_fallback(goc: ET.Element) -> ET.Element:
    """Bỏ `mc:Fallback`. `mc:AlternateContent` mang CÙNG một nội dung hai lần —
    `Choice` cho Word mới, `Fallback` cho Word cũ — nên đọc cả hai là đọc
    "Phụ lục 4" thành "Phụ lục 4Phụ lục 4" (đo trên tệp thật 2026-09-16), và
    mọi phép so độ dài phía sau đều lệch theo."""
    for cha in list(goc.iter()):
        for con in [c for c in cha if c.tag == _MC_FALLBACK]:
            cha.remove(con)
    return goc


def _tong_chu(nut: ET.Element) -> int:
    """Tổng ký tự `w:t` dưới `nut`, mỗi `w:t` đếm đúng một lần."""
    return sum(len((t.text or "").strip()) for t in nut.iter(f"{{{_NS['w']}}}t"))


def _goc_xml(xml: bytes, ten: str) -> ET.Element:
    try:
        return ET.fromstring(xml)
    except ET.ParseError as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, f"{ten} hỏng") from e


def _chu(nut: ET.Element) -> str:
    return "".join(t.text or "" for t in nut.iter(f"{{{_NS['w']}}}t")).strip()


def _duyet_phang(
    goc: ET.Element,
    vung: str,
    theo_kieu: dict[str, str] | None = None,
    kieu_chu: dict[str, dict[str, str]] | None = None,
) -> list[tuple]:
    """Mọi `w:p` theo thứ tự tài liệu, KHÔNG toạ độ bảng.

    Vừa là đường lùi của thân bài, vừa là đường duy nhất cho đầu/chân trang —
    ở đó một `w:p` là một dòng và không có gì để định vị thêm.
    """
    tk = theo_kieu or {}
    kc = kieu_chu or {}
    return [
        (None, c, None, vung, None, _can_le_doan(p, tk), _dinh_dang_doan(p, kc))
        for p in goc.iter(_P)
        if (c := _chu(p))
    ]


def _duyet_than(
    goc: ET.Element,
    theo_kieu: dict[str, str] | None = None,
    vien_kieu: dict[str, bool] | None = None,
    kieu_chu: dict[str, dict[str, str]] | None = None,
) -> list[tuple]:
    """Con trực tiếp của `w:body` theo thứ tự: `w:p` là một đơn vị, `w:tbl` cho
    một đơn vị mỗi ô kèm toạ độ (bảng, hàng, cột).

    Chữ của một ô là các `w:p` TRONG ô nối bằng một dấu cách — kể cả `w:p` của
    bảng lồng bên trong. Bảng lồng không được đánh số riêng: nó là chi tiết
    trình bày của ô bao ngoài, và tách ra thì "hàng 2 cột 1" của người đọc trỏ
    vào một bảng họ không nhìn thấy.

    Viền (`w:tblBorders`/`w:tcBorders`/`w:tblStyle`) và chiều cao hàng
    (`w:trHeight`) đi CÙNG vòng lặp này, không thêm lượt duyệt thứ hai — cùng
    lý lẽ `ti_le`/`nhip` đã theo: một ô tự mô tả đủ mọi sự thật cấu trúc của
    nó, không cần một bảng tra riêng đứng ngoài.

    Cột (Phase 11 R6) là cột LƯỚI THẬT — cộng dồn nhịp (`w:gridSpan`) của các
    ô đứng TRƯỚC nó trong cùng hàng, không phải số thứ tự ô thứ mấy. Con trỏ
    cột đi qua CẢ ô rỗng chữ (để nhịp của nó vẫn được cộng dồn cho ô sau) — chỉ
    đơn vị (dòng `ra.append`) mới bỏ qua ô rỗng, đúng hành vi trước Phase 11.
    """
    than = goc.find(_BODY)
    if than is None:
        return []
    tk = theo_kieu or {}
    vk = vien_kieu or {}
    kc = kieu_chu or {}
    ra: list[tuple] = []
    so_bang = 0
    for con in than:
        if con.tag == _P:
            if chu := _chu(con):
                ra.append((None, chu, None, "than", None, _can_le_doan(con, tk), _dinh_dang_doan(con, kc)))
        elif con.tag == _TBL:
            ti_le = _ti_le_luoi(con)
            vien = _vien_bang(con, vk)
            for h, tr in enumerate(con.findall(_TR)):
                cao = _cao_hang(tr)
                cot = 0
                for tc in tr.findall(_TC):
                    nhip = _nhip_o(tc)
                    c = cot
                    cot += nhip
                    # Phase 11 fix round 2 — GIỮ ô rỗng chữ, không bỏ qua như
                    # một đoạn văn rỗng. Một phiếu TRẮNG (biểu mẫu để trống
                    # cho người điền tay) có những HÀNG toàn ô rỗng — bỏ qua
                    # chúng thì `don_vi` không còn dấu vết những hàng đó tồn
                    # tại, và `hieu_tai_lieu._bang_theo_nhan` dựng lại bảng chỉ
                    # thấy đúng hàng tiêu đề (đo được thật: 5 hàng nguồn, 1
                    # hàng dựng lại). Ô rỗng CŨNG là ý nghĩa của biểu mẫu —
                    # cùng nguyên tắc dấu chấm điền của một dòng trường tự do,
                    # chỉ khác hình dạng (một Ô thay vì một cụm ký tự).
                    chu, dinh_dang = _chu_va_dinh_dang_o(tc, kc)
                    # Căn lề của Ô lấy từ ĐOẠN VĂN ĐẦU của chính ô đó — một
                    # ô có thể có nhiều `w:p` lồng, nhưng căn lề hiển thị
                    # là của dòng đầu tiên người đọc thấy.
                    can_le = _can_le_doan(tc.find(_P), tk)
                    ra.append(
                        (None, chu, None, "than", (so_bang, h, c), can_le, dinh_dang, nhip, ti_le, vien, cao)
                    )
            so_bang += 1
    return ra


def _doc_docx(du_lieu: bytes) -> list[tuple]:
    """Thân bài theo cấu trúc, rồi đầu trang, rồi chân trang.

    Duyệt theo cấu trúc BỎ SÓT thứ duyệt phẳng thấy: `w:sdt` (content control),
    hộp chữ, và mọi phần tử cấp thân chưa được kể tên ở đây. Nên nó không thay
    thế duyệt phẳng một cách mù quáng — ít chữ hơn thì lùi về. Mất toạ độ bảng
    là khoản lỗ sống chung được; mất nguyên một điều khoản thì không.
    """
    try:
        with zipfile.ZipFile(BytesIO(du_lieu)) as z:
            _kiem_zip(z)
            goc = _bo_fallback(_goc_xml(z.read("word/document.xml"), "word/document.xml"))
            # Căn lề theo KIỂU (Phase 9 U5) — `styles.xml` không bắt buộc có
            # trong một DOCX hợp lệ, và hỏng ở đó không được làm hỏng cả tài
            # liệu: mất căn lề theo kiểu là khoản lỗ sống chung được (`jc` trực
            # tiếp trên từng đoạn vẫn đọc đúng), mất nguyên một điều khoản thì
            # không.
            theo_kieu: dict[str, str] = {}
            vien_kieu: dict[str, bool] = {}
            kieu_chu: dict[str, dict[str, str]] = {}
            if "word/styles.xml" in z.namelist():
                try:
                    goc_kieu = _goc_xml(z.read("word/styles.xml"), "word/styles.xml")
                except KhongDocDuoc:
                    pass
                else:
                    theo_kieu = _kieu_can_le(goc_kieu)
                    # Viền theo KIỂU bảng (`TableGrid`) — mất nó thì một bảng
                    # có viền đọc thành không viền, xem `_kieu_vien_bang`.
                    vien_kieu = _kieu_vien_bang(goc_kieu)
                    # Định dạng chữ theo KIỂU — mất nó thì một biểu mẫu in đậm
                    # bằng kiểu đọc ra chữ thường, xem `_kieu_dinh_dang_chu`.
                    kieu_chu = _kieu_dinh_dang_chu(goc_kieu)
            than = _duyet_than(goc, theo_kieu, vien_kieu, kieu_chu)
            # Thước đo để lùi về là TỔNG chữ `w:t` của thân, KHÔNG phải duyệt
            # phẳng: duyệt phẳng đếm hai lần chữ trong hộp chữ (một `w:p` lồng
            # trong `w:p`), và với thước đó cấu trúc luôn "thua". Đo 2026-09-16
            # trên một kế hoạch thực tập: ba bảng mất toạ độ vì hai chữ "Phụ lục 4".
            nut_than = goc.find(_BODY)
            tong = _tong_chu(nut_than) if nut_than is not None else 0
            if sum(len(t[1]) for t in than) < 0.9 * tong:
                than = _duyet_phang(goc, "than", theo_kieu, kieu_chu)

            ra = list(than)
            for tien_to, vung in (("word/header", "dau_trang"), ("word/footer", "chan_trang")):
                for ten in sorted(n for n in z.namelist() if n.startswith(tien_to) and n.endswith(".xml")):
                    ra.extend(_duyet_phang(_goc_xml(z.read(ten), ten), vung, theo_kieu, kieu_chu))
            return ra
    except KeyError as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, "thiếu word/document.xml") from e
    except zipfile.BadZipFile as e:
        # DOCX có mật khẩu là tệp OLE chứ không phải zip, nên rơi vào đây. Không
        # phân biệt được hai ca này nếu không đọc header OLE; báo `tep_hong` là
        # nói đúng những gì biết chắc.
        raise KhongDocDuoc(LoaiHong.tep_hong, "không mở được tệp docx") from e


# ------------------------------------------------------------------------- DOC


def _duong_soffice() -> str | None:
    """Đường dẫn `soffice`. `KLAW_SOFFICE_PATH` (Settings) THẮNG dò theo PATH —
    máy dev, CI và container triển khai không chắc cài LibreOffice ở cùng một
    chỗ, cùng cách mọi công cụ ngoài khác của dự án đọc qua Settings thay vì
    một hằng số cứng. `None` khi cả hai đều không ra gì — người gọi phải báo
    lỗi rõ ràng, không được thử gọi một chuỗi rỗng làm lệnh."""
    from src.config import get_settings

    return get_settings().soffice_path or shutil.which("soffice")


def _la_ole2(du_lieu: bytes) -> bool:
    """8 byte đầu của container OLE2/CFB — .doc, .xls, .ppt (bản cũ) đều dùng
    chung. Không đọc sâu hơn (thư mục CFB) để biết đây có đúng là Word hay
    không: một .xls/.ppt đổi đuôi thành .doc qua được cửa này, nhưng KHÔNG qua
    được bộ chuyển đổi phía dưới — soffice mở nó bằng Calc/Impress rồi không
    xuất được sang khuôn Writer (.docx), và việc đó tự rơi vào nhánh `tep_hong`
    (đo thật, không chỉ suy luận — xem
    `test_DOC_gia_dang_XLS_that_bai_o_buoc_chuyen_doi_khong_phai_o_cong_OLE2`).

    Có một cách rẻ hơn để phân biệt NGAY tại đây: CLSID của "Root Entry"
    trong thư mục CFB là một GUID cố định theo ứng dụng (`00020906-...` cho
    Word 97-2003, `00020810-...`/`00020820-...` cho Excel, `64818D10-...`
    cho PowerPoint — [MS-CFB]). Đã CÂN NHẮC nhưng CHƯA làm (fix round 1, task
    review): việc này chỉ tiết kiệm một lần soffice khởi động nguội cho một
    ca hiếm (đổi đuôi tệp cố ý hoặc nhầm lẫn), chế độ hỏng đã ĐÚNG
    (`tep_hong`, không rò dữ liệu, không hổng bảo mật) mà không cần nó, và
    `_giet_sach_nhom` giờ chặn được đúng rủi ro tích luỹ mà việc này từng
    được nối vào (một loạt tệp như vậy không còn để lại tiến trình mồ côi).
    Đáng làm nếu sau này đo được đây là một đường vào bị lạm dụng thật, không
    phải trước đó."""
    return du_lieu[:8] == _OLE2_MAGIC


def _giet_sach_nhom(proc: subprocess.Popen) -> None:
    """SIGKILL cho CẢ NHÓM tiến trình của `proc`, rồi XÁC NHẬN nhóm đã hết —
    không giả định gửi được tín hiệu nghĩa là tiến trình đã thoát (fix round 1,
    task review — Critical).

    `proc` được `Popen` với `start_new_session=True` ở nơi gọi, nên `proc.pid`
    cũng là ID của cả PHIÊN/NHÓM mới đó. Vì sao cần: `soffice` là một wrapper
    thực thi `soffice.bin`, và bản thân LibreOffice có thể tự sinh thêm tiến
    trình của riêng nó — `proc.pid` không chắc là PID của tiến trình đang THẬT
    SỰ làm việc. Diệt riêng PID trực tiếp (hành vi mặc định của
    `subprocess.run(timeout=...)`, cách cũ của hàm này) có thể để lại một
    `soffice.bin` mồ côi vẫn giữ tệp và thư mục hồ sơ tạm — trên một endpoint
    tải lên công khai, vài lượt tải hỏng liên tiếp tích thành một rò rỉ tiến
    trình. `os.killpg` bắt được TẤT CẢ hậu duệ trong cùng nhóm, kể cả những
    tiến trình `Popen` của chúng ta không trực tiếp biết tới.
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # nhóm đã tự thoát trước khi kịp gửi tín hiệu

    try:
        proc.communicate(timeout=_HAN_XAC_NHAN_DA_GIET_GIAY)
    except subprocess.TimeoutExpired:
        logger.warning(
            "doc_tai_lieu: soffice %d không thoát sau SIGKILL trong %ss",
            proc.pid,
            _HAN_XAC_NHAN_DA_GIET_GIAY,
        )

    # Xác nhận: dò xem NHÓM (không chỉ proc vừa reap ở trên) còn ai sống
    # không. `killpg(pgid, 0)` không gửi tín hiệu thật, chỉ báo lỗi nếu không
    # còn tiến trình nào mang pgid đó — đây là bước "confirm", không phải
    # "assume", mà review round 1 đòi.
    han = time.monotonic() + _HAN_XAC_NHAN_DA_GIET_GIAY
    while time.monotonic() < han:
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            return  # xác nhận: không còn hậu duệ nào trong nhóm
        time.sleep(0.1)
    logger.warning(
        "doc_tai_lieu: sau SIGKILL vẫn không xác nhận được nhóm tiến trình %d đã hết",
        proc.pid,
    )


def _chuyen_doc_sang_docx(du_lieu: bytes) -> bytes:
    """.doc (OLE2) -> bytes .docx, bằng LibreOffice headless.

    Những điều làm tiến trình con này an toàn hơn với dữ liệu người dùng —
    và một điều KHÔNG được an toàn, nói thẳng thay vì để im lặng như đã đủ:

    - Hồ sơ (`-env:UserInstallation`) RIÊNG cho MỖI lần gọi, trong chính thư
      mục tạm sắp bị xoá — hồ sơ mặc định DÙNG CHUNG là nguồn lỗi đã biết "lần
      chuyển đổi thứ hai lặng lẽ không làm gì" khi hai tiến trình soffice đụng
      khoá cùng một hồ sơ.
    - TRẦN THỜI GIAN cứng (`_HAN_CHUYEN_DOI_GIAY`), và khi hết hạn, tín hiệu
      diệt gửi cho CẢ NHÓM tiến trình (`_giet_sach_nhom`, fix round 1) — không
      chỉ PID trực tiếp `Popen` giữ, vì `soffice` có thể tự sinh thêm tiến
      trình của riêng nó mà PID đó không nắm được.
    - MÔI TRƯỜNG tối giản — tiến trình con KHÔNG thừa hưởng biến môi trường của
      ứng dụng (API key, secrets khác). Không có cách tắt macro bằng cờ dòng
      lệnh, nhưng một hồ sơ MỚI TOANH giữ mức an toàn macro mặc định "Trung
      bình" (hỏi trước khi chạy) — ở chế độ headless không có hộp thoại nào để
      lỡ tay bấm "Đồng ý", nên macro không tự chạy được.
    - **"Không có mạng" KHÔNG được thi hành ở hàm này** (fix round 1, task
      review — Important; báo cáo trước đó khẳng định nhầm điều này). Môi
      trường tối giản bỏ được proxy/secrets khỏi tầm với của tiến trình con,
      nhưng KHÔNG chặn một kết nối ra ngoài — trường field-code/OLE link kiểu
      Word cũ có thể trỏ tới một URL và LibreOffice có thể thử với tới nó bất
      kể biến môi trường nào được cấp. Chặn THẬT cần một ranh giới hệ điều
      hành (network namespace, quy tắc tường lửa, hay chính sách mạng ở tầng
      container) — nằm ngoài những gì một tiến trình con Python tự làm được,
      và ngoài phạm vi bản vá này. Rủi ro còn lại (residual), không phải đã
      được chặn. **Cùng lý do đó, việc CHE biến môi trường (ở trên) cũng chỉ
      là một lớp phòng thủ PHỤ, không phải một ranh giới** (fix round 2, task
      review): tiến trình con chạy dưới CÙNG người dùng hệ điều hành với ứng
      dụng, nên nó vẫn đọc được `/proc/<pid>/environ` của chính nó — và của
      TIẾN TRÌNH CHA (ứng dụng) nếu quyền tệp cho phép — bất kể `env=` truyền
      cho `Popen` là gì. Ranh giới thật cho cả hai rủi ro (mạng, môi trường)
      là cùng MỘT thứ: cách ly ở tầng hệ điều hành/container, chưa có ở đây.
    - **SỐ LƯỢT CHẠY ĐỒNG THỜI bị chặn bằng `_suat_chuyen_doi`** (fix round
      2, task review — Important). Mỗi lượt chuyển đổi chiếm một luồng
      threadpool DÙNG CHUNG với mọi lệnh gọi DB khác của ứng dụng, và tự bản
      thân soffice giữ một lượng RAM đáng kể — không có gì ở tầng trên (giới
      hạn theo IP, hạn mức tài liệu/ngày) chặn được TỔNG số lượt xử lý cùng
      lúc. Một request không giành được suất trong `_HAN_CHO_SUAT_GIAY` nhận
      `ChuyenDoiKhongSanSang("qua_tai", …)` ngay — không xếp hàng im lặng.

    Tệp .doc và .docx tạm đều nằm trong MỘT thư mục do
    `tempfile.TemporaryDirectory` dựng và tự xoá khi hàm kết thúc — trên MỌI
    lối thoát Python bình thường, kể cả khi kết thúc bằng lỗi (kể cả đường
    hết hạn — `_giet_sach_nhom` chạy XONG rồi mới `raise`, nên khối `with`
    phía dưới vẫn thoát bình thường và tự dọn). Đây KHÔNG phải "không bao giờ
    chạm đĩa" tuyệt đối (fix round 2, task review — Minor #2, sửa cùng lúc
    với `doc()` và `tai_lieu.py`): nếu tiến trình bị SIGKILL hoặc hết bộ nhớ
    ĐÚNG lúc đang chuyển đổi, `tempfile.TemporaryDirectory.__exit__` không
    kịp chạy, và tệp tạm (bytes gốc + bản .docx đã chuyển) có thể sót lại
    trong `/tmp` của container cho tới khi container đó bị dọn/khởi động lại.
    Brief đã cho phép tệp tạm này tồn tại (không phải một vi phạm FR-022 mới);
    điều cần nói thẳng là "luôn xoá" chỉ đúng cho lối thoát BÌNH THƯỜNG.
    """
    if not _la_ole2(du_lieu):
        raise KhongDocDuoc(LoaiHong.tep_hong, "tệp .doc không đúng định dạng OLE2")

    soffice = _duong_soffice()
    if not soffice:
        # LỖI CẤU HÌNH, không phải lỗi của người dùng — phải ồn ào với người
        # vận hành (fix round 2, Minor #4). Trước đây dùng
        # `KhongDocDuoc(khong_co_lop_chu, ...)`, DÙNG CHUNG thông điệp với ca
        # "ảnh chụp mờ" — người tải một .doc bình thường thấy "chụp lại rõ",
        # câu trả lời sai hoàn toàn. Tách hẳn khỏi bốn nguyên nhân FR-003
        # (xem docstring `ChuyenDoiKhongSanSang`) giải quyết luôn việc đó:
        # không phải sửa lại câu chữ dùng chung, mà không còn dùng chung nữa.
        logger.error(
            "doc_tai_lieu: máy chủ chưa cài LibreOffice (KLAW_SOFFICE_PATH rỗng và "
            "không thấy 'soffice' trên PATH) — MỌI tải lên .doc sẽ hỏng cho tới khi "
            "khắc phục. Đây là lỗi cấu hình, không phải lỗi của người dùng."
        )
        raise ChuyenDoiKhongSanSang("khong_co_cong_cu", "chưa cài LibreOffice")

    if not _suat_chuyen_doi.acquire(timeout=_HAN_CHO_SUAT_GIAY):
        # Quá tải TẠM THỜI — tự hết khi tải giảm, khác hẳn ca thiếu công cụ ở
        # trên. Log ở mức INFO: đây là hành vi ĐÚNG của một cái phanh dưới
        # tải cao, không phải một lỗi cần báo động.
        logger.info(
            "doc_tai_lieu: không giành được suất chuyển đổi .doc trong %ss (đang có %d suất)",
            _HAN_CHO_SUAT_GIAY,
            _SO_CHUYEN_DOI_DONG_THOI,
        )
        raise ChuyenDoiKhongSanSang(
            "qua_tai", f"không giành được suất chuyển đổi trong {_HAN_CHO_SUAT_GIAY}s"
        )

    try:
        return _chay_soffice(du_lieu, soffice)
    finally:
        _suat_chuyen_doi.release()


def _chay_soffice(du_lieu: bytes, soffice: str) -> bytes:
    """Phần THẬT SỰ tốn tài nguyên của `_chuyen_doc_sang_docx` — tách riêng để
    suất chuyển đổi (`_suat_chuyen_doi`) chỉ bị giữ quanh ĐÚNG đoạn này, không
    quanh các cổng chặn sớm (OLE2, thiếu soffice) phía trên."""
    from pathlib import Path as _P  # noqa: N814 — cùng cách `_ocr_pdf` làm

    with tempfile.TemporaryDirectory() as tmp:
        thu_muc = _P(tmp)
        vao = thu_muc / "vao.doc"
        vao.write_bytes(du_lieu)
        moi_truong = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp}
        proc = subprocess.Popen(
            [
                soffice,
                "--headless",
                "--invisible",
                "--nocrashreport",
                "--nodefault",
                "--nofirststartwizard",
                "--nolockcheck",
                "--nologo",
                "--norestore",
                f"-env:UserInstallation=file://{thu_muc / 'ho_so'}",
                "--convert-to",
                "docx:MS Word 2007 XML",
                "--outdir",
                tmp,
                str(vao),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=moi_truong,
            # Phiên (session) MỚI làm `proc.pid` cũng là ID của cả nhóm tiến
            # trình — điều kiện để `_giet_sach_nhom` diệt được TẤT CẢ hậu duệ
            # bằng `os.killpg`, không chỉ tiến trình `Popen` biết trực tiếp.
            start_new_session=True,
        )
        try:
            proc.communicate(timeout=_HAN_CHUYEN_DOI_GIAY)
        except subprocess.TimeoutExpired as e:
            _giet_sach_nhom(proc)
            raise KhongDocDuoc(LoaiHong.tep_hong, "chuyển đổi tệp .doc quá lâu") from e

        ra = thu_muc / "vao.docx"
        if proc.returncode != 0 or not ra.exists():
            # KHÔNG log nội dung `stderr` của soffice (fix round 2, task
            # review — Minor #3): chuỗi đó bắt nguồn từ TÀI LIỆU người dùng
            # (tên tệp, đôi khi trích cả một đoạn nội dung soffice không phân
            # tích được), và FR-027 + quyết định 2026-09-16 cấm nội dung tài
            # liệu vào log. Chỉ ghi lại SỰ KIỆN (hỏng) và mã thoát — đủ để vận
            # hành biết CÓ hỏng, không đủ để lộ tài liệu của ai đó.
            logger.warning(
                "doc_tai_lieu: soffice không chuyển được .doc (mã thoát %s)",
                proc.returncode,
            )
            raise KhongDocDuoc(LoaiHong.tep_hong, "không chuyển đổi được tệp .doc")

        return ra.read_bytes()


# ------------------------------------------------------------------------- PDF


def _doc_pdf(du_lieu: bytes) -> list[tuple[int | None, str]]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(du_lieu))
    except Exception as e:
        # pypdf ném `PyPdfError` cho tệp sai cấu trúc nhưng cũng ném
        # ValueError/OSError cho tệp rác; bắt rộng ở đây là đúng vì mọi nhánh
        # đều dẫn tới cùng một câu trả lời cho người dùng: gửi lại tệp.
        raise KhongDocDuoc(LoaiHong.tep_hong, "không mở được tệp pdf") from e

    if reader.is_encrypted:
        raise KhongDocDuoc(LoaiHong.can_mat_khau, "pdf được bảo vệ bằng mật khẩu")

    ra: list[tuple[int | None, str]] = []
    for so, trang in enumerate(reader.pages, start=1):
        try:
            chu = trang.extract_text() or ""
        except Exception:
            # Một trang hỏng không được làm hỏng cả tài liệu; nếu MỌI trang đều
            # câm thì `doc()` sẽ báo `khong_co_lop_chu` ở tầng trên.
            logger.warning("doc_tai_lieu: không rút được chữ ở trang %d", so)
            chu = ""
        for dong in chu.splitlines():
            if dong.strip():
                ra.append((so, dong.strip()))
    return ra


# ---------------------------------------------------------------- gán vị trí


def _dat_vi_tri(thoi: list[tuple]) -> TaiLieuDaDoc:
    """Gán `trang`, `offset_dau` và nguồn chữ cho từng đơn vị.

    Nhận cả sáu hình dạng: `(trang, noi_dung)` từ nhánh đọc chữ thật,
    `(trang, noi_dung, do_tin)` từ nhánh OCR,
    `(trang, noi_dung, do_tin, vung, bang)` từ DOCX trước Phase 9,
    `(trang, noi_dung, do_tin, vung, bang, can_le)` từ DOCX có căn lề (Phase 9
    U5), `(…, can_le, dinh_dang)` từ một đoạn DOCX có định dạng chữ
    (2026-09-18), và `(…, dinh_dang, bang_nhip, bang_ti_le, bang_vien,
    bang_cao)` từ một Ô BẢNG. Có `do_tin` nghĩa là máy đang đoán, nên đơn vị
    đó mang nhãn `ocr`.

    `dinh_dang` chèn vào giữa (sau `can_le`) chứ không nối vào cuối: đoạn văn
    thân bài khi đó chỉ cần 7 phần tử thay vì 11 phần tử toàn giá trị mặc
    định. Cả hai nơi dựng tuple (`_duyet_than`, `_duyet_phang`) đổi cùng lúc
    với hàm này, nên không có hình dạng cũ nào còn chạy qua đây.

    PDF đã biết trang thật. DOCX chưa, nên trang được suy ra từ số ký tự đã đi
    qua — xem ghi chú ở `KY_TU_MOI_TRANG`.
    """
    don_vi: list[DonViVanBan] = []
    da_di = 0          # ký tự đã đi qua trong toàn tài liệu (nhánh DOCX)
    trang_hien = None
    offset = 0
    theo_ky_tu = bool(thoi) and thoi[0][0] is None

    for i, muc in enumerate(thoi):
        trang, noi_dung = muc[0], muc[1]
        do_tin = muc[2] if len(muc) > 2 else None
        vung = muc[3] if len(muc) > 3 else "than"
        bang = muc[4] if len(muc) > 4 else None
        can_le = muc[5] if len(muc) > 5 else "trai"
        dinh_dang = muc[6] if len(muc) > 6 else ()
        bang_nhip = muc[7] if len(muc) > 7 else 1
        bang_ti_le = muc[8] if len(muc) > 8 else ()
        bang_vien = muc[9] if len(muc) > 9 else True
        bang_cao = muc[10] if len(muc) > 10 else 0
        if trang is None:
            trang = 1 + da_di // KY_TU_MOI_TRANG
        if trang != trang_hien:
            trang_hien, offset = trang, 0
        don_vi.append(
            DonViVanBan(
                chi_so=i,
                trang=trang,
                offset_dau=offset,
                noi_dung=noi_dung,
                nguon_chu=NguonChu.ocr if do_tin is not None else NguonChu.lop_chu,
                do_tin=do_tin,
                vung=vung,
                bang=bang,
                can_le=can_le,
                bang_nhip=bang_nhip,
                bang_ti_le=bang_ti_le,
                bang_vien=bang_vien,
                bang_cao=bang_cao,
                dinh_dang=dinh_dang,
            )
        )
        offset += len(noi_dung) + 1   # +1 cho dấu xuống dòng giữa hai đơn vị
        da_di += len(noi_dung) + 1

    so_ky_tu = sum(len(d.noi_dung) for d in don_vi)
    so_trang = max((d.trang for d in don_vi), default=1)
    if theo_ky_tu:   # DOCX: trang là xấp xỉ theo ký tự
        so_trang = max(1, ceil(so_ky_tu / KY_TU_MOI_TRANG))
    return TaiLieuDaDoc(don_vi=don_vi, so_trang=so_trang, so_ky_tu=so_ky_tu)


# ═══ OCR ════════════════════════════════════════════════════════════════════
# Gọi `tesseract` qua subprocess thay vì thêm `pytesseract`: một tiến trình con
# và một lần đọc TSV là đủ, còn thư viện bọc thì thêm một dependency để làm
# đúng việc đó. Bản thân `tesseract` với gói `vie` vẫn là điều kiện bắt buộc.


def _tesseract(duong_anh: str) -> list[tuple[str, float]]:
    """(dòng, độ tin) cho một ảnh. TSV vì nó cho độ tin TỪNG TỪ.

    Độ tin của một dòng là trung bình độ tin các từ trong dòng đó — thấp nghĩa
    là máy đang đoán, và một dòng máy đang đoán không nên thành bằng chứng.
    """
    ra = subprocess.run(
        ["tesseract", duong_anh, "-", "-l", "vie", "tsv"],
        capture_output=True,
        timeout=_HAN_TREO_GIAY,
    )
    if ra.returncode != 0:
        raise KhongDocDuoc(LoaiHong.tep_hong, "tesseract không đọc được ảnh")

    dong: dict[tuple, list[tuple[str, float]]] = {}
    for hang in ra.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
        c = hang.split("\t")
        if len(c) < 12 or not c[11].strip():
            continue
        try:
            tin = float(c[10])
        except ValueError:
            continue
        if tin < 0:
            continue
        dong.setdefault(tuple(c[2:5]), []).append((c[11], tin / 100.0))

    ket: list[tuple[str, float]] = []
    for tu in dong.values():
        chu = " ".join(t for t, _ in tu).strip()
        tin = sum(d for _, d in tu) / len(tu)
        if chu and tin >= NGUONG_TIN_OCR:
            ket.append((chu, tin))
    return ket


def _ocr_anh(du_lieu: bytes) -> list[tuple[int | None, str, float]]:
    if not co_ocr():
        raise KhongDocDuoc(
            LoaiHong.khong_co_lop_chu,
            "máy chủ chưa cài công cụ nhận dạng chữ, chưa đọc được ảnh",
        )
    with tempfile.NamedTemporaryFile(suffix=".img", delete=True) as f:
        f.write(du_lieu)
        f.flush()
        return [(1, chu, tin) for chu, tin in _tesseract(f.name)]


def _ocr_pdf(du_lieu: bytes) -> list[tuple[int | None, str, float]]:
    """Rasterize từng trang rồi OCR. Cần `pdftoppm` của poppler."""
    if not co_ocr() or not shutil.which("pdftoppm"):
        raise KhongDocDuoc(
            LoaiHong.khong_co_lop_chu,
            "tệp không có lớp chữ và máy chủ chưa đọc được bản scan",
        )
    ra: list[tuple[int | None, str, float]] = []
    with tempfile.TemporaryDirectory() as thu_muc:
        goc = f"{thu_muc}/t"
        kq = subprocess.run(
            ["pdftoppm", "-r", str(_DPI_OCR), "-png", du_lieu and "-", goc],
            input=du_lieu,
            capture_output=True,
            timeout=_HAN_TREO_GIAY,
        )
        if kq.returncode != 0:
            raise KhongDocDuoc(LoaiHong.tep_hong, "không dựng được ảnh từ pdf")
        from pathlib import Path as _P  # noqa: N814

        for so, anh in enumerate(sorted(_P(thu_muc).glob("t-*.png")), start=1):
            ra.extend((so, chu, tin) for chu, tin in _tesseract(str(anh)))
    return ra
