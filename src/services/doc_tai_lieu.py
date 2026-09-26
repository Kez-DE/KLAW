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
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field, replace
from enum import StrEnum
from io import BytesIO
from math import ceil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

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

# Dấu hiệu của một chỗ ĐỂ ĐIỀN: dấu chấm lửng `…`, hoặc một dãy từ ba dấu chấm
# / gạch ngang / gạch dưới trở lên. Một dấu chấm lẻ thì không — `20.000.000`
# phân nhóm nghìn bằng đúng ký tự đó. DÙNG CHUNG hai nơi: `hieu_tai_lieu.
# vung_trong` (một giá trị có phải chỗ trống không) và bộ đọc chỗ trống ở đây
# (`_day_cham`) — hai câu trả lời cho "chỗ này để điền" không được lệch nhau.
RE_CHO_DIEN = re.compile(r"…|[._–—-]{3,}")

# Công cụ poppler nhẹ (`pdftotext -tsv`, `pdftoppm -gray`) chỉ để lấy HỘP chữ và
# ảnh xám — không phải để đọc chữ. 60 giây cùng lý lẽ `_HAN_CHUYEN_DOI_GIAY`:
# một tệp cố ý làm treo bộ phân tích phải lộ ra trong một phút.
_HAN_CONG_CU_GIAY = 60


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
class MocTab:
    """MỘT mốc tab (`w:pPr/w:tabs/w:tab`) — chỗ con trỏ nhảy tới, và đường vẽ
    lấp khoảng nhảy qua.

    `leader="dot"` là thứ vẽ ra dòng "…………" mà một biểu mẫu tiếng Việt chừa
    cho người điền tay — đo trên tám biểu mẫu thật của chủ dự án: 68/134 mốc
    khai `dot`, tất cả đều là dòng điền cuối câu ("Company name: ……"). Không
    có nó thì chỗ để điền biến mất hẳn khỏi bản dựng lại.

    `pos` là twip tính từ MÉP TRÁI của cột chữ, không phải từ mép giấy — cùng
    hệ quy chiếu `w:ind` dùng, nên hai trường cộng/trừ được với nhau.
    """

    val: str = "left"
    pos: int = 0
    leader: str = ""


@dataclass(frozen=True)
class GianCach:
    """Giãn cách, thụt lề và mốc tab của MỘT `w:p` — quyết định 2026-09-18,
    mục "thụt lề, tab, giãn dòng".

    Cùng khuôn `DinhDangChu`: những trường đã GIẢI (đã trộn thừa kế từ
    `w:pStyle` → `w:basedOn`) để render dùng, cộng `khai` giữ NGUYÊN VĂN những
    gì `w:pPr` của chính đoạn nói. Hai câu hỏi khác nhau — "phải vẽ thế nào"
    và "tệp tự khai gì ở đây" — nên hai chỗ trả lời, không gộp.

    `doan` là `w:p` thứ mấy trong ô bảng (luôn `0` với một đoạn thân bài, ở đó
    đơn vị LÀ đoạn), đúng nghĩa `DinhDangChu.doan`.

    `tab` là offset ký tự trong `noi_dung` nơi một `<w:tab/>` đứng. KHÔNG phải
    một ký tự: `<w:tab/>` không nằm trong `w:t` nên `_chu` chưa bao giờ đưa nó
    vào `noi_dung`, và bản vá này KHÔNG được thêm nó vào — `noi_dung` là chuỗi
    mà `neo_du_kien.xac_minh`, `normalize` và `lam_sach_van_ban` đang tra. Một
    VỊ TRÍ nằm cạnh chuỗi giữ được cả hai: chuỗi không đổi một byte, mà phía
    vẽ vẫn biết đường dẫn bắt đầu từ đâu.
    """

    doan: int = 0
    truoc: int = 0
    """`w:spacing/@w:before` — khoảng trống TRÊN đoạn, twip. `0` khi không khai."""
    sau: int = 0
    """`w:spacing/@w:after` — khoảng trống DƯỚI đoạn, twip."""
    dong: int = 0
    """`w:spacing/@w:line`. Ý nghĩa phụ thuộc `luat_dong`, xem ngay dưới."""
    luat_dong: str = ""
    """`w:spacing/@w:lineRule`: `auto` (mặc định OOXML) thì `dong` là BỘI SỐ của
    240 — 360 nghĩa là 1,5 dòng; `exact`/`atLeast` thì `dong` là twip TUYỆT
    ĐỐI. Giữ cả hai trường vì một con số không nói được nó đang đo cái gì."""
    trai: int = 0
    phai: int = 0
    """`w:ind/@w:left|@w:start` và `@w:right|@w:end` — twip, ÂM được (một biểu
    mẫu thật khai `-567` để tràn ra ngoài lề)."""
    dau_dong: int = 0
    treo: int = 0
    """`w:ind/@w:firstLine` (dòng ĐẦU thụt thêm) và `@w:hanging` (dòng đầu thụt
    NGƯỢC ra). Hai thuộc tính loại trừ nhau trong OOXML; giữ riêng vì render
    cộng chúng theo hai dấu khác nhau."""
    moc: tuple[MocTab, ...] = ()
    """Mốc tab VẼ ĐƯỢC, theo thứ tự `pos` tăng dần."""
    tab: tuple[int, ...] = ()
    khai: tuple[tuple[str, str], ...] = ()
    """NGUYÊN VĂN những gì `w:pPr` TRỰC TIẾP của đoạn khai, khoá theo đúng tên
    OOXML: `("spacing/before", "120")`, `("ind/hanging", "426")`, `("tabs",
    "2")` — số `w:tab` tệp khai, kể cả mốc `clear`. Thứ tự cố định (spacing,
    rồi ind, rồi tabs; trong mỗi nhóm theo tên thuộc tính) để hai lần đọc cùng
    một tệp cho cùng một dãy."""


@dataclass(frozen=True)
class AnhTaiLieu:
    """MỘT ảnh đã tách khỏi tệp — quyết định 2026-09-18, mục "media đã tách".

    Đây là phần MÔ TẢ, đi cùng biểu diễn văn bản và lưu trong `don_vi`. Bytes
    đi đường KHÁC (`TaiLieuDaDoc.anh_byte` → bảng `anh_tai_lieu`, migration
    035): một khối bytea trong cột JSONB của biểu diễn sẽ đi theo mọi truy vấn
    đọc biểu diễn, và nội dung ảnh của bên thứ ba không được đi qua dây mỗi
    lần có người neo một trích dẫn.

    `phan` là tên part trong zip (`word/media/image1.png`) — vừa là khoá lưu
    bytes, vừa là thứ `eval.run_trung_thuc` đối chiếu. Giữ tên NGUỒN chứ không
    đánh số lại: hai tham chiếu tới cùng một logo phải nhận ra là cùng một ảnh,
    và tên part là thứ duy nhất nói được điều đó.

    `rong`/`cao` là EMU (English Metric Unit, 914400 EMU = 1 inch) — đơn vị
    của chính `wp:extent`. Giữ nguyên EMU thay vì quy ra pt hay mm ở đây, đúng
    lý lẽ `DinhDangChu.co` giữ nửa điểm: `.docx` tải về ghi lại chính đơn vị
    này, còn màn hình và PDF mới là nơi quy đổi. `0` nghĩa là nguồn KHÔNG khai
    cỡ — ba nơi vẽ khi đó dùng cỡ thật của chính ảnh.

    `vung` (`than`/`dau_trang`/`chan_trang`) và `thu_tu` (thứ mấy TRONG vùng
    ấy, theo thứ tự tài liệu) là vị trí. Không mang toạ độ tuyệt đối: giữ
    `wp:anchor/@posOffset` cần cả hệ quy chiếu neo của OOXML, và quyết định
    2026-09-18 đã nói thẳng vị trí tuyệt đối nằm ngoài phạm vi khi không lưu
    OOXML.
    """

    phan: str
    kieu: str
    rong: int = 0
    cao: int = 0
    vung: str = "than"
    thu_tu: int = 0


@dataclass(frozen=True)
class DiaChi:
    """Chỗ một đơn vị DOCX đứng trong khuôn gốc — kế hoạch
    `khuon-goc-dien-tai-cho.md`, hợp đồng "Đơn vị văn bản additions".

    `phan` là tên part THẬT trong zip (`word/document.xml`, `word/header2.xml`).
    `chi_muc` là chỉ số con PHẦN TỬ ở từng cấp, đi từ `w:body` (hoặc gốc
    `w:hdr`/`w:ftr`) xuống vật chứa của đơn vị: `(i,)` cho một đoạn thân bài,
    `(bảng, hàng, ô)` cho một ô. Mọi cấp đếm TẤT CẢ con phần tử (`w:tblPr`,
    `w:tblGrid`, `w:trPr` cũng được đếm); chú thích XML và PI thì không — bộ
    đọc (ElementTree) không giữ chúng, nên bộ áp (lxml) phải lọc đúng như vậy.

    Đo trên part THÔ đúng như nằm trong tệp, TRƯỚC khi `_bo_fallback` gỡ gì:
    bộ áp đi lại trên chính bytes đã lưu, nơi `mc:Fallback` vẫn còn. Ghim lúc
    đọc; bộ áp không bao giờ duyệt lại bằng mã mới hơn.
    """

    phan: str
    chi_muc: tuple[int, ...]


@dataclass(frozen=True)
class ChoTrong:
    """MỘT chỗ để điền của một đơn vị, theo thứ tự đọc.

    `so` là chỉ số của chỗ trống TRONG đơn vị, đếm từ 0 — đúng thứ phép sửa
    `{"loai": "dien", "cho_trong": n}` trỏ tới. `kieu`: `cham` (dãy `.`/`…`
    mà `RE_CHO_DIEN` nhận) hoặc `tab` (một `w:tab` rơi vào mốc có đường dẫn
    `dot`). `nhan` là tối đa 60 ký tự CUỐI của chữ đứng trước chỗ trống (sau
    chỗ trống liền trước, nếu có) — phần sát chỗ trống mới là nhãn của nó.

    DOCX dùng `doan`/`dau`/`cuoi`: `doan` là thứ tự `w:p` trong
    `vật_chứa.iter(w:p)` THÔ (0 với đoạn thân bài), `[dau, cuoi)` là offset
    trên chuỗi `w:t` nối THÔ của chính đoạn đó — chưa `strip()`, `w:tab`/
    `w:br` không góp ký tự nào. Một chỗ `tab` có `dau == cuoi`.

    PDF dùng `hop`/`co_chu`: `hop` là `(x0, y0, x1, y1)` bằng điểm PDF, gốc
    TRÊN-trái, trên `trang` của đơn vị; `co_chu` là chiều cao (điểm) của dòng
    chữ chỗ trống ấy nằm — không phải cỡ phông danh nghĩa.
    """

    so: int
    kieu: str
    nhan: str = ""
    doan: int = 0
    dau: int = 0
    cuoi: int = 0
    hop: tuple[float, float, float, float] | None = None
    co_chu: float = 0.0


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
    """`trai` | `giua` | `phai` | `deu` (Phase 9 U5) — căn lề THẬT của đoạn/ô
    này, đọc từ `w:pPr/w:jc` hoặc, khi vắng (nghĩa là "thừa kế"), từ kiểu đoạn
    văn của nó (`w:pStyle`, theo hết chuỗi `w:basedOn`). Mặc định `trai`: DOCX
    không khai báo `jc` là căn trái, không phải "chưa biết" — cùng lý lẽ `vung`
    không được suy diễn thêm gì ngoài những gì tệp nói.

    `deu` (căn đều hai lề, `w:jc="both"`) là giá trị thứ tư từ 2026-09-19 — xem
    `_JC_RA_CAN_LE`. Nó cũng là căn lề mà `hieu_tai_lieu._the_thuc_hanh_chinh`
    gán cho thân bài của một văn bản KLAW TỰ SOẠN (NĐ 30/2020/NĐ-CP, Phụ lục I:
    "nội dung văn bản... được canh đều cả hai lề").
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

    `hRule` đi RIÊNG ở `bang_cao_luat`: con số và luật áp con số ấy là hai sự
    thật, và gộp chúng thì không nói được "tệp khai 1499 twip theo luật nào".
    """
    bang_cao_luat: str = ""
    """`w:trPr/w:trHeight/@w:hRule` NGUYÊN VĂN của HÀNG chứa ô này — `exact`,
    `atLeast`, `auto`, hoặc `""` khi hàng không khai.

    Đọc thành SỰ THẬT ở đây; cách vẽ là quyết định riêng của từng nơi vẽ, và
    cả ba nơi chọn giống nhau (xem `XemTruocA4.caoTrenTrang`,
    `xuat-tep.bangThanhTable`, PDF `caoKhaiMm`):

    - `auto` → BỎ con số. Word bỏ nó ở đây, và ép một chiều cao tối thiểu mà
      tệp bảo đừng ép là vẽ thứ tệp không nói.
    - `exact` → vẽ như chiều cao TỐI THIỂU, KHÔNG cắt. `exact` nghĩa là Word
      cắt phần chữ tràn ra, và cắt mất chữ của người dùng hỏng tệ hơn nhiều so
      với một hàng cao hơn khai báo vài milimét. Đây là chỗ duy nhất trong cả
      bản vá mà hình VẼ cố ý khác nguồn — nên sự thật vẫn được cất nguyên văn
      ở đây, và cái thước chấm sự thật ĐÃ ĐỌC chứ không chấm nét đã vẽ.
    - `atLeast`/`""` → chiều cao tối thiểu, đúng hành vi trước trường này.
    """
    bang_vien_canh: tuple[tuple[str, str, str], ...] = ()
    """Viền cấp BẢNG theo TỪNG CẠNH — `(tên cạnh, w:val, w:sz)` nguyên văn,
    thứ tự `_CANH_VIEN`, đã giải qua `w:tblStyle`/`w:basedOn` (xem
    `_vien_canh_bang`). GIỐNG NHAU trên mọi ô của cùng một bảng, đúng cách
    `bang_ti_le` tự mô tả theo từng đơn vị thay vì một bảng tra đứng ngoài.

    `bang_vien` ở trên trả lời "bảng này có vẽ nét nào không" — vừa đủ cho ba
    nơi vẽ hồi chúng chỉ kẻ được MỘT kiểu viền cho mọi ô. Trường này trả lời
    câu còn lại: nét nào ở cạnh nào, dày bao nhiêu. Giữ CẢ HAI thay vì suy cờ
    bool ra từ đây: `_co_net` duyệt MỌI con của nhóm viền (kể cả `w:start`/
    `w:end` của OOXML strict, và `tl2br`/`tr2bl` của một ô), còn trường này
    chỉ giữ sáu cạnh vẽ được — suy ngược sẽ đọc một bảng chỉ khai `w:start`
    thành bảng không viền, đúng kiểu "bỏ mất một nét tệp có vẽ" mà cờ bool
    tồn tại để tránh.

    Rỗng khi bảng không khai và không thừa kế cạnh nào (và với mọi dòng lưu
    TRƯỚC trường này) — ba nơi vẽ khi đó lùi về đúng nét đều của `bang_vien`.
    """
    o_vien_canh: tuple[tuple[str, str, str], ...] = ()
    """Viền RIÊNG của CHÍNH ô này — `w:tcPr/w:tcBorders`, cùng hình dạng
    `bang_vien_canh`, KHÔNG trộn sẵn viền cấp bảng (xem `_vien_canh_o`).

    Một cạnh có mặt ở đây ĐÈ cạnh cùng tên của bảng; cạnh vắng mặt thì ô thừa
    kế cạnh bảng — và cạnh bảng nào thì phụ thuộc chỗ ô đứng (`top` của hàng
    đầu là `top` của bảng, của hàng giữa là `insideH`). Phép ghép đó nằm ở
    `hieu_tai_lieu._vien_o_bang`, nơi DUY NHẤT biết cả bảng có bao nhiêu hàng
    và cột — một đơn vị đứng một mình không biết nó có phải hàng cuối không.
    """
    le_trang: tuple[tuple[str, int], ...] = ()
    """Lề trang của tài liệu — `w:sectPr/w:pgMar`, `(tên, twip)`, chỉ thuộc
    tính tệp KHAI (xem `_le_trang`).

    GIỐNG NHAU trên MỌI đơn vị của cùng tài liệu, kể cả đầu/chân trang — cùng
    khuôn `bang_ti_le`: một đơn vị tự mô tả đủ, không có bảng tra nào đứng
    ngoài. Đó không chỉ là gu: ranh giới lưu/đọc (`tai_lieu.luu_don_vi`) chỉ
    chở MỘT mảng đơn vị, nên một sự thật cấp tài liệu không nằm trên đơn vị sẽ
    biến mất ngay tại đó — đúng chỗ căn lề từng mất một lần.

    Rỗng khi tệp không khai `w:pgMar` (và với mọi dòng lưu TRƯỚC trường này):
    ba nơi vẽ khi đó giữ đúng lề mặc định của chính chúng, không đoán thêm.
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
    gian_cach: tuple[GianCach, ...] = ()
    """Giãn cách/thụt lề/mốc tab của từng `w:p` trong đơn vị này — quyết định
    2026-09-18, mục "thụt lề, tab, giãn dòng". MỘT phần tử cho mỗi `w:p` CÓ
    khai một điều gì đó; đoạn không khai gì không có phần tử nào, cùng luật
    `dinh_dang` bỏ run không nói gì.

    Đo trên tám biểu mẫu thật của chủ dự án: `w:spacing`/`w:ind`/`w:tabs`
    chiếm 1713 trong 1840 khai báo bộ đọc còn bỏ sót — 93%. Không có chúng
    thì bản dựng lại đúng chữ, đúng kiểu chữ, mà sai toàn bộ nhịp trang: đoạn
    dính nhau, lề thụt biến mất, và dòng "……" để điền tay không còn.

    Rỗng với mọi dòng lưu TRƯỚC trường này."""
    anh: tuple[AnhTaiLieu, ...] = ()
    """Ảnh đã tách khỏi tệp — quyết định 2026-09-18, mục "media đã tách".

    GIỐNG NHAU trên MỌI đơn vị của cùng tài liệu, đúng khuôn `le_trang`: một
    logo letterhead nằm trong một `w:p` KHÔNG CÓ CHỮ, nên không có đơn vị nào
    để treo nó lên theo kiểu `dinh_dang`/`gian_cach` (vốn tra theo chữ nguyên
    văn của từng dòng). Và ranh giới lưu/đọc (`tai_lieu.luu_don_vi`) chỉ chở
    MỘT mảng đơn vị, nên một sự thật cấp tài liệu không nằm trên đơn vị sẽ
    biến mất ngay tại đó — đúng chỗ căn lề đã mất một lần.

    Chỉ MÔ TẢ, không bytes: xem `AnhTaiLieu` và `TaiLieuDaDoc.anh_byte`.

    Rỗng với mọi dòng lưu TRƯỚC trường này, và với mọi tài liệu không phải
    DOCX — PDF và ảnh OCR chưa có đường tách media nào."""
    dia_chi: DiaChi | None = None
    """Vật chứa của đơn vị trong khuôn gốc DOCX (xem `DiaChi`). `None` khi
    nguồn không cho một địa chỉ đáng tin: PDF, ảnh, thân bài đọc bằng đường lùi
    duyệt phẳng, đoạn trong hộp chữ — và mọi dòng lưu TRƯỚC trường này."""
    cho_trong: tuple[ChoTrong, ...] = ()
    """Chỗ để điền của đơn vị, theo thứ tự đọc (xem `ChoTrong`). Đi CẠNH
    `noi_dung`, không chạm nó — cùng luật `dinh_dang`/`gian_cach`."""
    hop: tuple[float, float, float, float] | None = None
    """Hộp của DÒNG (PDF có lớp chữ, PDF scan) — điểm PDF, gốc trên-trái, trên
    `trang`. `None` khi không định vị được chắc chắn."""


@dataclass(frozen=True)
class TaiLieuDaDoc:
    don_vi: list[DonViVanBan]
    so_trang: int
    so_ky_tu: int
    anh_byte: dict[str, tuple[str, bytes]] = field(default_factory=dict)
    """`tên part` → `(kiểu MIME, bytes)` của từng ảnh đã tách.

    Kênh RIÊNG, cố ý không nằm trên `DonViVanBan`: biểu diễn đã đọc đi vào cột
    JSONB `don_vi` và được đọc lại mỗi lần có người neo một trích dẫn, còn
    bytes ảnh chỉ cần đi đúng MỘT lần — từ `doc()` sang `tai_lieu.luu_anh`
    (bảng `anh_tai_lieu`, migration 035) — rồi người gọi buông, đúng tinh thần
    FR-022 với chính tệp gốc.
    """

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
    le: tuple[tuple[str, int], ...] = ()
    anh: tuple[AnhTaiLieu, ...] = ()
    anh_byte: dict[str, tuple[str, bytes]] = {}
    if ten.endswith(".pdf"):
        thoi = _doc_pdf(du_lieu)
        if not thoi:
            # PDF bọc ảnh — bản scan trông đúng như vậy. Trước đây bị từ chối
            # thẳng; giờ thử OCR, nhưng kết quả mang nhãn `ocr` chứ không được
            # đánh đồng với PDF có lớp chữ.
            thoi = _ocr_pdf(du_lieu)
    elif ten.endswith(".docx"):
        thoi, le, anh, anh_byte = _doc_docx(du_lieu)
    elif ten.endswith(".doc"):
        # Chuyển trước, đọc sau — bằng ĐÚNG một hàm `_doc_docx`, không nhánh
        # riêng nào biết tệp .docx này từng là .doc.
        thoi, le, anh, anh_byte = _doc_docx(_chuyen_doc_sang_docx(du_lieu))
    elif ten.endswith(_DUOI_ANH):
        thoi = _ocr_anh(du_lieu)
    else:
        raise KhongDocDuoc(
            LoaiHong.dinh_dang_khong_ho_tro,
            f"chỉ hỗ trợ {', '.join(_DUOI_HO_TRO)}",
        )

    if not thoi:
        raise KhongDocDuoc(LoaiHong.khong_co_lop_chu, "không rút được ký tự nào")
    # `uoc_do_day` chỉ cho DOCX/DOC: PDF và ảnh OCR đã có số trang THẬT, cộng
    # thêm một ước lượng theo ký tự ở đó là bịa một tài liệu dày hơn nó.
    return _dat_vi_tri(thoi, le, anh, anh_byte, uoc_do_day=ten.endswith((".docx", ".doc")))


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
_SPACING = f"{{{_NS['w']}}}spacing"
_IND = f"{{{_NS['w']}}}ind"
_TABS = f"{{{_NS['w']}}}tabs"
_TAB = f"{{{_NS['w']}}}tab"
_POS = f"{{{_NS['w']}}}pos"
_LEADER = f"{{{_NS['w']}}}leader"
_SZ = f"{{{_NS['w']}}}sz"
_HRULE = f"{{{_NS['w']}}}hRule"
_SECTPR = f"{{{_NS['w']}}}sectPr"
_PGMAR = f"{{{_NS['w']}}}pgMar"
_BR = f"{{{_NS['w']}}}br"
_TYPE = f"{{{_NS['w']}}}type"

# Sáu cạnh của một nhóm viền OOXML (`w:tblBorders`/`w:tcBorders`), theo thứ tự
# CỐ ĐỊNH: hai lần đọc cùng một tệp phải cho cùng một dãy, đúng luật
# `DinhDangChu.khai`/`GianCach.khai` đã đặt. Không kể `tl2br`/`tr2bl` (gạch
# chéo trong ô) — không nơi vẽ nào của dự án diễn đạt được một đường chéo, và
# đọc ra một sự thật không ai vẽ được là thêm dữ liệu chứ không thêm độ trung
# thực.
_CANH_VIEN = ("top", "left", "bottom", "right", "insideH", "insideV")

# Bảy thuộc tính `w:sectPr/w:pgMar` — twip, ÂM được (`top`/`bottom` âm là cách
# Word đặt đầu/chân trang tràn vào mép giấy).
_TEN_LE_TRANG = ("top", "right", "bottom", "left", "header", "footer", "gutter")

# Năm thuộc tính `w:rPr` đọc được (quyết định 2026-09-18). Thứ tự này là thứ
# tự `DinhDangChu.khai` ghi ra, để hai lần đọc cùng một tệp cho cùng một dãy.
_TEN_RPR = ("b", "i", "u", "sz", "rFonts")

# `w:tab/@w:val="clear"` XOÁ một mốc kiểu đặt sẵn, nó không phải một mốc để
# nhảy tới. Vẫn ĐẾM trong `khai` (tệp có khai một `w:tab`), nhưng không vào
# `GianCach.moc` — nhảy tới một mốc đã bị xoá là vẽ một đường dẫn không tồn tại.
_TAB_XOA = "clear"

# `w:leader` mặc định của OOXML là `none`: một mốc không khai `w:leader` KHÔNG
# vẽ đường dẫn. Cùng luật `w:u` — thiếu giá trị nghĩa là giá trị mặc định của
# chính thuộc tính đó, không phải "bật".
_KHONG_DAN = {"", "none"}

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

# OOXML `w:jc` → `DonViVanBan.can_le` (Phase 9 U5). "left"/"start" và mọi giá
# trị lạ đọc ra `trai` — đó cũng là giá trị khi tệp KHÔNG khai `w:jc` gì cả.
#
# `both` ra `deu` (2026-09-19), KHÔNG còn gộp vào `trai`. Bản trước gộp vì
# `deu` chưa biểu diễn được ở đâu trong chuỗi; giờ nó đi hết đường (`can_le` →
# `KhoiMuc.canhLe` → `text-justify` → `w:jc="both"`/`align: "justify"`), nên
# gộp tiếp là VỨT một điều tệp NÓI ra. Phân biệt này cũng là thứ giữ cho
# `canhLeThanhHuong` không phải đoán: `trai` vẫn nghĩa là "nguồn không khai",
# `deu` mới nghĩa là "nguồn khai căn đều" — đúng ca hồi quy Phase 11 R2/R8 đã
# đo (mọi đoạn ra `w:jc="both"` vì `trai` bị hiểu là "hãy căn đều").
_JC_RA_CAN_LE = {"center": "giua", "right": "phai", "end": "phai", "both": "deu"}


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


def _canh_vien(vien: ET.Element | None) -> dict[str, tuple[str, str]]:
    """Một nhóm viền → `{tên cạnh: (w:val, w:sz)}` NGUYÊN VĂN, CHỈ cạnh tệp khai.

    Giữ nguyên văn cả hai chuỗi thay vì quy `w:sz` ra số ngay: `w:sz` là đơn
    vị 1/8 điểm của chính OOXML, và ba nơi vẽ cần ba phép quy đổi khác nhau
    (px trên màn hình, `size` của `docx`, mm của PDF) — quy đổi sớm ở đây là
    chọn hộ một trong ba. Cạnh VẮNG MẶT khác hẳn cạnh khai `none`: cái trước
    nghĩa là "thừa kế", cái sau nghĩa là "KHÔNG vẽ", và trộn hai ca ấy đúng là
    cách một kiểu bảng có viền bị xoá sạch viền (hoặc ngược lại).
    """
    if vien is None:
        return {}
    ra: dict[str, tuple[str, str]] = {}
    for canh in _CANH_VIEN:
        e = vien.find(f"{{{_NS['w']}}}{canh}")
        if e is not None:
            ra[canh] = (e.get(_VAL) or "", e.get(_SZ) or "")
    return ra


def _kieu_vien_canh(goc_styles: ET.Element | None) -> dict[str, dict[str, tuple[str, str]]]:
    """id kiểu BẢNG → viền TỪNG CẠNH của kiểu đó, đã theo hết chuỗi `w:basedOn`.

    Trộn theo TỪNG CẠNH (`{**cha, **con}`), không chặn cả cụm như
    `_kieu_vien_bang` phải làm với một cờ bool: một kiểu con khai lại đúng
    `insideH` vẫn thừa kế bốn cạnh ngoài của kiểu cha, đúng cách Word áp dụng.
    Đó chính là cái trần mà docstring `_kieu_vien_bang` tự khai là không tả
    được — một bool không có chỗ cất hình dạng, một dict theo cạnh thì có.
    """
    if goc_styles is None:
        return {}
    truc_tiep: dict[str, dict[str, tuple[str, str]]] = {}
    cha: dict[str, str] = {}
    for st in goc_styles.findall(_STYLE):
        sid = st.get(f"{{{_NS['w']}}}styleId")
        if not sid or st.get(f"{{{_NS['w']}}}type") != "table":
            continue
        b = st.find(_BASEDON)
        if b is not None and (v := b.get(_VAL)):
            cha[sid] = v
        truc_tiep[sid] = _canh_vien(st.find(f"{_TBLPR}/{_TBLBORDERS}"))

    def _giai(sid: str | None, di_qua: frozenset[str]) -> dict[str, tuple[str, str]]:
        if sid is None or sid in di_qua:
            return {}
        return {**_giai(cha.get(sid), di_qua | {sid}), **truc_tiep.get(sid, {})}

    return {sid: _giai(sid, frozenset()) for sid in {*truc_tiep, *cha}}


def _vien_canh_bang(
    tbl: ET.Element, kieu_canh: dict[str, dict[str, tuple[str, str]]]
) -> tuple[tuple[str, str, str], ...]:
    """Viền cấp BẢNG theo từng cạnh — `(tên cạnh, w:val, w:sz)`, thứ tự
    `_CANH_VIEN` (xem `DonViVanBan.bang_vien_canh`).

    `w:tblBorders` TRỰC TIẾP đè kiểu theo TỪNG cạnh, đúng thứ tự Word áp dụng
    (kiểu trước, khai trực tiếp sau) — cùng luật `_gian_cach_doan` đã theo cho
    `w:spacing`/`w:ind`.
    """
    pr = tbl.find(_TBLPR)
    if pr is None:
        return ()
    canh: dict[str, tuple[str, str]] = {}
    kieu = pr.find(_TBLSTYLE)
    if kieu is not None and (sid := kieu.get(_VAL)):
        canh.update(kieu_canh.get(sid, {}))
    canh.update(_canh_vien(pr.find(_TBLBORDERS)))
    return tuple((c, *canh[c]) for c in _CANH_VIEN if c in canh)


def _vien_canh_o(tc: ET.Element) -> tuple[tuple[str, str, str], ...]:
    """Viền RIÊNG của một ô — `w:tcPr/w:tcBorders`, KHÔNG trộn viền cấp bảng.

    Giữ riêng vì đây là hai sự thật khác nhau: cạnh ô khai là cạnh ô ĐÈ, còn
    cạnh bảng là cạnh ô thừa kế khi chính nó không khai. Trộn sẵn ở đây thì
    phía vẽ hết đường biết ô nào thật sự tự khai, và cái thước (đếm ĐÚNG
    `w:tcBorders` trong `document.xml`) sẽ chấm một sự thật bịa thêm.
    """
    return tuple((c, *v) for c, v in _canh_vien(tc.find(f"{_TCPR}/{_TCBORDERS}")).items())


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


def _luat_cao_hang(tr: ET.Element) -> str:
    """`w:trPr/w:trHeight/@w:hRule` NGUYÊN VĂN, `""` khi hàng không khai — xem
    `DonViVanBan.bang_cao_luat`."""
    h = tr.find(f"{_TRPR}/{_TRHEIGHT}")
    return (h.get(_HRULE) or "") if h is not None else ""


def _le_trang(goc: ET.Element) -> tuple[tuple[str, int], ...]:
    """Lề trang — `w:body/w:sectPr/w:pgMar`, twip, chỉ thuộc tính tệp KHAI.

    Chỉ `w:sectPr` CUỐI thân (con trực tiếp của `w:body`, chỗ duy nhất
    `_le_trang` nhìn): một tài liệu nhiều phân đoạn còn giấu `w:sectPr` trong
    `w:pPr` của đoạn kết mỗi phân đoạn, và mỗi phân đoạn ấy có lề riêng. Giữ
    MỘT bộ lề cho cả tài liệu là đúng biểu diễn hiện có — `DonViVanBan` không
    mang số phân đoạn, nên một bộ lề thứ hai không có chỗ nào gắn vào. Trần đã
    biết, không phải một suy diễn ngầm.

    Thuộc tính đọc không ra số bị BỎ RIÊNG nó, không kéo cả bộ lề về rỗng: sáu
    số còn lại vẫn là sáu điều tệp nói đúng, và một lề trái đọc được thì đặt
    được khối vào đúng chỗ dù `w:gutter` có hỏng.
    """
    than = goc.find(_BODY)
    pg = than.find(f"{_SECTPR}/{_PGMAR}") if than is not None else None
    if pg is None:
        return ()
    ra: list[tuple[str, int]] = []
    for ten in _TEN_LE_TRANG:
        v = pg.get(f"{{{_NS['w']}}}{ten}")
        if v is None:
            continue
        try:
            ra.append((ten, int(v)))
        except ValueError:
            continue
    return tuple(ra)


# ─── ẢNH ĐÃ TÁCH ───────────────────────────────────────────────────────────
# Quyết định 2026-09-18 (`docs/decisions/2026-09-18-trung-thuc-bieu-mau-va-media.md`)
# cho phép lưu MEDIA ĐÃ TÁCH khỏi tệp — và CHỈ thế: bytes tệp gốc và OOXML vẫn
# bị cấm nguyên văn. Nên chỗ này rút ra đúng hai thứ: khối bytes của từng ảnh,
# và một mô tả vị trí/kích thước đủ để ba nơi vẽ đặt lại nó. Không giữ một
# mảnh XML nào.


def _rel(ten_phan: str) -> str:
    """`word/header1.xml` → `word/_rels/header1.xml.rels`. Mỗi phần XML có bảng
    quan hệ RIÊNG — logo letterhead nằm trong rels của đầu trang, không phải
    của `document.xml`, và tra nhầm bảng thì `r:embed` không giải ra gì."""
    thu_muc, _, ten = ten_phan.rpartition("/")
    return f"{thu_muc}/_rels/{ten}.rels" if thu_muc else f"_rels/{ten}.rels"


def _quan_he(z: zipfile.ZipFile, ten_phan: str) -> dict[str, str]:
    """`rId` → đường dẫn part ĐÃ chuẩn hoá về gốc zip, cho một phần XML.

    `Target` trong `.rels` là đường dẫn TƯƠNG ĐỐI so với thư mục của phần XML
    (`media/image1.png` từ `word/header1.xml` là `word/media/image1.png`).
    Ghép sai gốc thì mọi ảnh trong đầu trang đọc ra rỗng.

    `.rels` hỏng hay vắng trả về rỗng — mất ảnh là khoản lỗ sống chung được,
    mất nguyên tài liệu thì không (cùng luật `styles.xml` ở `_doc_docx`).
    """
    ten_rel = _rel(ten_phan)
    if ten_rel not in z.namelist():
        return {}
    try:
        goc = ET.fromstring(z.read(ten_rel))
    except ET.ParseError:
        return {}
    thu_muc = ten_phan.rpartition("/")[0]
    ra: dict[str, str] = {}
    for r in goc:
        rid, dich = r.get("Id"), r.get("Target")
        if not rid or not dich or r.get("TargetMode") == "External":
            # Ảnh liên kết NGOÀI (`TargetMode="External"`) không có bytes trong
            # tệp — không có gì để tách, và đi lấy nó là để tài liệu của khách
            # gọi ra mạng. Bỏ, đúng luật fail-closed.
            continue
        ra[rid] = dich[1:] if dich.startswith("/") else f"{thu_muc}/{dich}" if thu_muc else dich
    return ra


_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_V = "{urn:schemas-microsoft-com:vml}"
_WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
_DRAWING = f"{{{_NS['w']}}}drawing"
_PICT = f"{{{_NS['w']}}}pict"

# 1pt = 12700 EMU. VML khai cỡ bằng CSS (`style="width:136.5pt;height:42.3pt"`)
# chứ không bằng `wp:extent`, nên hai đường phải quy về cùng một đơn vị trước
# khi `AnhTaiLieu.rong`/`cao` mang được cả hai.
_EMU_MOI_PT = 12700

# Nhận dạng ảnh theo BYTES ĐẦU, không theo đuôi tệp: đuôi nằm trong tài liệu
# của người lạ và đổi được, còn bytes thì không. Bốn kiểu này là GIAO của ba
# nơi vẽ — trình duyệt vẽ cả bốn, `docx.ImageRun` nhận đúng bốn
# (`"jpg" | "png" | "gif" | "bmp"`), jsPDF nhận qua chính thẻ `<img>` đã vẽ.
#
# SVG bị loại CÓ CHỦ Ý dù trình duyệt vẽ được: nó là XML chạy được script, và
# phát lại nó từ một tệp người lạ tải lên là mở một đường XSS ngay trong trang
# của chủ tài liệu. EMF/WMF loại vì không nơi vẽ nào của dự án dựng được chúng
# — giữ bytes cho một thứ không ai vẽ là lưu dữ liệu cá nhân của bên thứ ba mà
# không đổi lại được gì.
_ANH_NHAN_DANG: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
)

# Trần MỖI ảnh. Một logo letterhead, một con dấu hay một chữ ký quét đều nằm
# sâu dưới mức này (đo trên tám biểu mẫu thật của chủ dự án: ảnh lớn nhất là
# ảnh bìa 5819775×8165347 EMU, dưới 200 KB). 2 MB để một ảnh chụp cả trang ở
# 150 dpi vẫn qua, mà một tệp nhồi ảnh khổng lồ thì không.
TRAN_ANH_BYTE = 2 * 1024 * 1024

# Trần CẢ TÀI LIỆU. Cần riêng với trần mỗi ảnh vì trăm ảnh nhỏ cộng lại vẫn
# đầy một dòng Postgres — và bytea ở đây sống suốt đời cuộc hội thoại. 8 MB
# nằm dưới `TRAN_BYTE` (20 MB, `tai_lieu.kiem_kich_thuoc`) nên một tệp hợp lệ
# không bao giờ chạm trần này trước khi chạm trần kia.
TRAN_ANH_TONG_BYTE = 8 * 1024 * 1024


def _co_vml(hinh: ET.Element) -> tuple[int, int]:
    """Cỡ của một `v:shape` VML từ `style="width:…;height:…"` → EMU.

    VML đo bằng CSS nên đơn vị có thể là `pt`, `in`, `cm`, `mm` hay `px`. Chỉ
    đọc những đơn vị QUY ĐỔI ĐƯỢC chắc chắn; giá trị phần trăm hay không đơn vị
    trả 0 — "không khai cỡ" an toàn hơn một con số đoán sai cả chục lần.
    """
    don_vi = {"pt": 1.0, "in": 72.0, "cm": 72 / 2.54, "mm": 72 / 25.4, "px": 0.75, "pc": 12.0}
    ra = {"width": 0, "height": 0}
    for muc in (hinh.get("style") or "").split(";"):
        ten, _, gia = muc.partition(":")
        ten, gia = ten.strip().lower(), gia.strip().lower()
        if ten not in ra or len(gia) < 3:
            continue
        he = don_vi.get(gia[-2:])
        if he is None:
            continue
        try:
            ra[ten] = round(float(gia[:-2]) * he * _EMU_MOI_PT)
        except ValueError:
            continue
    return (ra["width"], ra["height"])


def _co_drawing(hinh: ET.Element) -> tuple[int, int]:
    """Cỡ khai báo của một `w:drawing` — `wp:extent` của `wp:inline` hay
    `wp:anchor`, EMU sẵn. `(0, 0)` khi không khai hoặc khai không ra số."""
    e = hinh.find(f"{_WP}inline/{_WP}extent")
    if e is None:
        e = hinh.find(f"{_WP}anchor/{_WP}extent")
    if e is None:
        return (0, 0)
    try:
        return (max(0, int(e.get("cx") or 0)), max(0, int(e.get("cy") or 0)))
    except ValueError:
        return (0, 0)


def _tham_chieu_anh(goc: ET.Element, vung: str) -> list[tuple[str, str, int, int]]:
    """`(rId, vung, rộng EMU, cao EMU)` của từng ảnh trong MỘT phần XML, theo
    thứ tự tài liệu.

    Duyệt `w:drawing` (DrawingML, `a:blip/@r:embed`) và `w:pict` (VML,
    `v:imagedata/@r:id`) trong CÙNG một lượt `iter` để thứ tự trả về đúng thứ
    tự chúng đứng trên trang — hai lượt riêng sẽ dồn hết ảnh VML xuống sau,
    và một biểu mẫu cũ trộn hai lối sẽ đặt lại logo sai chỗ.

    Hình KHÔNG mang ảnh (hộp chữ, đường kẻ, khung — `w:drawing` chứa `wps:wsp`,
    `w:pict` chứa `v:line`/`v:rect`) không trả về gì: chúng không có bytes để
    tách, và đếm chúng như ảnh là hứa một thứ không tồn tại. Đo trên tám biểu
    mẫu thật của chủ dự án: 11 trong 13 hình cấp thân là hộp chữ và đường kẻ
    kiểu này, chỉ 2 là ảnh thật.

    Người gọi phải bỏ `mc:Fallback` TRƯỚC (`_bo_fallback`): `mc:AlternateContent`
    chở cùng một hình hai lần — `w:drawing` cho Word mới, `w:pict` VML cho Word
    cũ — nên không bỏ thì mọi logo đếm và tách hai lần.
    """
    ra: list[tuple[str, str, int, int]] = []
    for hinh in goc.iter():
        if hinh.tag == _DRAWING:
            blip = hinh.find(f".//{_A}blip")
            if blip is None or not (rid := blip.get(f"{_R_NS}embed")):
                continue
            rong, cao = _co_drawing(hinh)
            ra.append((rid, vung, rong, cao))
        elif hinh.tag == _PICT:
            for du_lieu in hinh.iter(f"{_V}imagedata"):
                if not (rid := du_lieu.get(f"{_R_NS}id")):
                    continue
                # Cỡ nằm trên `v:shape` BAO NGOÀI, không trên `v:imagedata`.
                rong = cao = 0
                for hd in hinh.iter():
                    if du_lieu in list(hd):
                        rong, cao = _co_vml(hd)
                        break
                ra.append((rid, vung, rong, cao))
    return ra


def _kieu_anh(du_lieu: bytes) -> str:
    """Kiểu MIME theo BYTES ĐẦU, `""` khi không nhận ra — xem `_ANH_NHAN_DANG`."""
    return next((k for dau, k in _ANH_NHAN_DANG if du_lieu.startswith(dau)), "")


def _doc_anh(
    z: zipfile.ZipFile, goc_than: ET.Element
) -> tuple[tuple[AnhTaiLieu, ...], dict[str, tuple[str, bytes]]]:
    """Mọi ảnh của một DOCX: phần mô tả (đi cùng biểu diễn) và bytes (đi riêng).

    `goc_than` là `word/document.xml` ĐÃ qua `_bo_fallback` — dùng lại chính
    cây `_doc_docx` vừa dựng thay vì phân tích lần hai. Đầu/chân trang thì
    phân tích RIÊNG ở đây: đường đọc chữ của chúng (`_duyet_phang`) cố ý KHÔNG
    bỏ `mc:Fallback`, và đổi điều đó sẽ đổi `noi_dung` của những đơn vị ấy —
    thứ mọi neo trích dẫn đang tra. Một lượt phân tích thêm cho vài KB đầu
    trang rẻ hơn nhiều so với một lần neo lệch.

    FAIL CLOSED ở mọi cửa: rel không giải được, part vắng, bytes không nhận ra
    kiểu, quá trần một ảnh hay quá trần cả tài liệu — ảnh đó bị BỎ và phần còn
    lại của tài liệu vẫn dựng đủ. Không ném lỗi: một con dấu hỏng không đáng
    làm cả tờ giấy không đọc được.
    """
    phan_vung = [("word/document.xml", "than", goc_than)]
    for tien_to, vung in (("word/header", "dau_trang"), ("word/footer", "chan_trang")):
        for ten in sorted(n for n in z.namelist() if n.startswith(tien_to) and n.endswith(".xml")):
            try:
                phan_vung.append((ten, vung, _bo_fallback(ET.fromstring(z.read(ten)))))
            except (ET.ParseError, KeyError):
                continue

    anh: list[AnhTaiLieu] = []
    kho: dict[str, tuple[str, bytes]] = {}
    tong = 0
    dem_vung: dict[str, int] = {}
    co_trong_zip = set(z.namelist())
    for ten_phan, vung, goc in phan_vung:
        quan_he = _quan_he(z, ten_phan)
        for rid, _, rong, cao in _tham_chieu_anh(goc, vung):
            phan = quan_he.get(rid, "")
            # CHỈ `word/media/`: một `r:embed` trỏ ra chỗ khác trong zip là
            # đường đọc một part tuỳ ý của tệp người lạ, không phải một ảnh.
            if not phan.startswith("word/media/") or phan not in co_trong_zip:
                continue
            if phan in kho:
                kieu = kho[phan][0]
            else:
                try:
                    du_lieu = z.read(phan)
                except (KeyError, zipfile.BadZipFile, OSError):
                    continue
                if len(du_lieu) > TRAN_ANH_BYTE or tong + len(du_lieu) > TRAN_ANH_TONG_BYTE:
                    # Chỉ ghi SỐ, không ghi bytes và không ghi chữ nào của tài
                    # liệu — FR-027.
                    logger.info("doc_tai_lieu: bỏ 1 ảnh %d byte (vượt trần)", len(du_lieu))
                    continue
                if not (kieu := _kieu_anh(du_lieu)):
                    continue
                kho[phan] = (kieu, du_lieu)
                tong += len(du_lieu)
            anh.append(
                AnhTaiLieu(
                    phan=phan,
                    kieu=kieu,
                    rong=rong,
                    cao=cao,
                    vung=vung,
                    thu_tu=dem_vung.get(vung, 0),
                )
            )
            dem_vung[vung] = dem_vung.get(vung, 0) + 1
    return tuple(anh), kho


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


def _twip(v: str | None) -> int:
    """Một số đo twip tệp khai → `int`. Ném `ValueError` khi đọc không ra số.

    Nhận cả số THỰC (`"48.00000000000001"`): OOXML định nghĩa twip là số
    nguyên, nhưng `Report_instruction.docx` của chủ dự án khai đúng chuỗi ấy
    trên 50 đoạn — vết của một bộ ghi tính `0,0833in × 576` rồi in thẳng ra.
    Làm tròn nó KHÔNG phải đoán bố cục (48,00000000000001 twip chỉ có một
    nghĩa); từ chối nó thì 50 đoạn có thật mất luôn cả giãn dòng của chúng.
    Thứ đọc không ra số nào cả thì vẫn ném — ở đó mới thật sự không biết gì.
    """
    return round(float(v or 0))


def _thuoc_tho(e: ET.Element | None) -> dict[str, str]:
    """Mọi thuộc tính của một phần tử, khoá đã bỏ namespace; `{}` khi vắng mặt.

    Lấy TẤT CẢ chứ không lọc theo một danh sách tên: `khai` phải nói lại đúng
    những gì tệp nói, kể cả thuộc tính bản vá này không vẽ
    (`w:beforeAutospacing`, `w:firstLineChars`) — một thước đo độ trung thực
    hỏi "tệp khai gì", không hỏi "bộ đọc thích gì".
    """
    return {} if e is None else {k.rsplit("}", 1)[-1]: v for k, v in e.attrib.items()}


def _moc_tab(tabs: ET.Element | None) -> tuple[tuple[MocTab, ...], int]:
    """`w:pPr/w:tabs` → (mốc NHẢY ĐƯỢC, số `w:tab` tệp khai), `-1` khi không
    có `w:tabs` nào — khác hẳn `0` (`<w:tabs/>` rỗng, một điều tệp có nói).

    Hai số khác nhau vì `w:val="clear"` XOÁ một mốc kiểu đặt sẵn: nó vẫn là
    một khai báo (thước đo đếm nó) nhưng không phải chỗ để nhảy tới.

    Sắp theo `pos` tăng dần — OOXML không bắt tệp ghi theo thứ tự, còn phép
    "tab thứ n đi tới mốc thứ n" ở tầng vẽ thì cần đúng thứ tự thật. Một
    `w:pos` đọc không ra số làm CẢ nhóm mốc rỗng: một mốc sai chỗ kéo mọi mốc
    sau nó lệch theo, và vẽ nửa bộ mốc tệ hơn không vẽ mốc nào.
    """
    if tabs is None:
        return (), -1
    con = tabs.findall(_TAB)
    try:
        moc = tuple(
            MocTab(val=v, pos=_twip(t.get(_POS)), leader=t.get(_LEADER) or "")
            for t in con
            if (v := t.get(_VAL) or "left") != _TAB_XOA
        )
    except ValueError:
        return (), len(con)
    return tuple(sorted(moc, key=lambda m: m.pos)), len(con)


_KieuGC = tuple[dict[str, str], dict[str, str], tuple[MocTab, ...], int]


def _ppr_tho(ppr: ET.Element | None) -> _KieuGC:
    """`w:pPr` → (thuộc tính `w:spacing`, thuộc tính `w:ind`, mốc tab, số `w:tab`).

    Khoá VẮNG MẶT nghĩa là cấp này không khai thuộc tính đó — đúng chỗ phân
    biệt mà `_rpr_tho` cũng phải giữ để phép xếp chồng thừa kế chạy đúng: một
    đoạn không khai `w:after` phải THỪA KẾ nó từ kiểu, còn một đoạn khai
    `w:after="0"` phải HUỶ nó.
    """
    if ppr is None:
        return {}, {}, (), -1
    moc, so = _moc_tab(ppr.find(_TABS))
    return _thuoc_tho(ppr.find(_SPACING)), _thuoc_tho(ppr.find(_IND)), moc, so


def _kieu_gian_cach(goc_styles: ET.Element | None) -> dict[str, _KieuGC]:
    """id kiểu → giãn cách/thụt lề/mốc tab của kiểu đó, đã TRỘN hết `w:basedOn`.

    Trộn theo TỪNG thuộc tính như `_kieu_dinh_dang_chu`, không lấy nguyên khối
    như `_kieu_vien_bang`: một kiểu con chỉ khai `w:spacing/@w:after` vẫn phải
    thừa kế giãn dòng của kiểu cha, và lấy nguyên khối sẽ xoá mất nó.

    Mốc tab thì thay NGUYÊN BỘ chứ không trộn từng mốc. OOXML trộn theo vị trí
    (`w:val="clear"` của con xoá đúng một mốc của cha); trần này chỉ đổi kết
    quả khi một kiểu con xoá lẻ vài mốc của kiểu cha, và ở đó câu trả lời
    "đoạn này có mốc tab" vẫn đúng — cùng loại trần `_kieu_vien_bang` đã khai.
    """
    if goc_styles is None:
        return {}
    truc: dict[str, _KieuGC] = {}
    cha: dict[str, str] = {}
    for st in goc_styles.findall(_STYLE):
        sid = st.get(f"{{{_NS['w']}}}styleId")
        if not sid:
            continue
        b = st.find(_BASEDON)
        if b is not None and (v := b.get(_VAL)):
            cha[sid] = v
        truc[sid] = _ppr_tho(st.find(_PPR))

    def _giai(sid: str | None, di_qua: frozenset[str]) -> _KieuGC:
        if sid is None or sid in di_qua or sid not in truc:
            return {}, {}, (), -1
        sp_c, ind_c, moc_c, so_c = _giai(cha.get(sid), di_qua | {sid})
        sp, ind, moc, so = truc[sid]
        return (
            {**sp_c, **sp},
            {**ind_c, **ind},
            moc if so >= 0 else moc_c,
            so if so >= 0 else so_c,
        )

    return {sid: _giai(sid, frozenset()) for sid in truc}


def _vi_tri_tab(p: ET.Element) -> list[int]:
    """Offset của mỗi `<w:tab/>` trên chuỗi nối CHƯA cắt khoảng trắng — cùng
    phép nối `_chu`/`_vi_tri_chu` dùng, nên trừ phần `strip()` đi là ra offset
    trên chính `_chu(p)`.

    BỎ QUA `w:pPr`: `w:tab` nằm trong đó là ĐỊNH NGHĨA mốc, không phải ký tự
    tab. Hai thứ trùng tên thẻ, khác hẳn nghĩa.
    """
    vi: list[int] = []
    n = 0
    for con in p:
        if con.tag == _PPR:
            continue
        for e in con.iter():
            if e.tag == _T:
                n += len(e.text or "")
            elif e.tag == _TAB:
                vi.append(n)
    return vi


def _gian_cach_doan(p: ET.Element, kieu_gc: dict[str, _KieuGC], doan: int = 0) -> GianCach | None:
    """Giãn cách/thụt lề/mốc tab THẬT của một `w:p`; `None` khi đoạn không khai
    và không thừa kế gì.

    HAI lớp xếp chồng, lớp sau đè lớp trước, theo TỪNG thuộc tính: kiểu đoạn
    văn (`w:pPr/w:pStyle`, đã giải hết `w:basedOn`) rồi `w:pPr` trực tiếp —
    đúng thứ tự Word áp dụng, và đúng điều `_can_le_doan` đã phải làm cho
    `w:jc`: một biểu mẫu đặt giãn dòng bằng KIỂU không khai `w:spacing` ở đâu
    trong `document.xml` cả.

    Fail closed THEO TỪNG PHẦN TỬ: một giá trị đọc không ra số làm CẢ
    `w:spacing` của đoạn về "không khai" (phía vẽ dùng giãn cách mặc định của
    chính nó), chứ không vẽ một nửa. `w:ind` và `w:tabs` không im theo:
    ba phần tử độc lập, một `w:ind` hỏng không nói gì về giãn dòng, và bắt cả
    ba cùng câm là phạt quá tay. Chỗ phải chặn là vẽ MỘT NỬA của cùng một
    phần tử — đó mới là bố cục đoán.

    `w:ind` đọc `w:left`/`w:right` trước, `w:start`/`w:end` (tên của OOXML
    strict, cùng nghĩa) khi không có: một tệp do bộ ghi mới sinh ra chỉ khai
    cặp sau, và bỏ nó là mất thụt lề của cả tệp đó.
    """
    ppr = p.find(_PPR)
    sp_truc, ind_truc, moc_truc, so_truc = _ppr_tho(ppr)
    nen_sp, nen_ind, nen_moc, nen_so = {}, {}, (), -1
    if ppr is not None:
        kieu = ppr.find(_PSTYLE)
        if kieu is not None and (sid := kieu.get(_VAL)):
            nen_sp, nen_ind, nen_moc, nen_so = kieu_gc.get(sid, ({}, {}, (), -1))
    sp = {**nen_sp, **sp_truc}
    ind = {**nen_ind, **ind_truc}
    moc = moc_truc if so_truc >= 0 else nen_moc

    # `w:beforeAutospacing`/`w:afterAutospacing` BẬT nghĩa là "Word tự tính
    # khoảng này", nên con số `w:before`/`w:after` đi kèm không còn là thứ
    # phải vẽ. `w:val="0"/"false"` TẮT chúng, đúng luật `_TAT` của `w:rPr`.
    tu_truoc = _bat(sp.get("beforeAutospacing"))
    tu_sau = _bat(sp.get("afterAutospacing"))
    try:
        truoc = 0 if tu_truoc else _twip(sp.get("before"))
        sau = 0 if tu_sau else _twip(sp.get("after"))
        dong = _twip(sp.get("line"))
        luat_dong = (sp.get("lineRule") or "auto") if "line" in sp else ""
    except ValueError:
        truoc = sau = dong = 0
        luat_dong = ""
    try:
        trai = _twip(ind.get("left", ind.get("start")))
        phai = _twip(ind.get("right", ind.get("end")))
        dau_dong = _twip(ind.get("firstLine"))
        treo = _twip(ind.get("hanging"))
    except ValueError:
        trai = phai = dau_dong = treo = 0

    # Cùng phép cắt khoảng trắng `_dinh_dang_doan` dùng: offset của một mốc
    # tab phải đo trên ĐÚNG `_chu(p)` mà `noi_dung` mang, không trên chuỗi thô.
    _, tho = _vi_tri_chu(p)
    lech = len(tho) - len(tho.lstrip())
    het = len(tho.strip())
    tab = tuple(min(max(x - lech, 0), het) for x in _vi_tri_tab(p))

    khai: list[tuple[str, str]] = [(f"spacing/{k}", v) for k, v in sorted(sp_truc.items())]
    khai += [(f"ind/{k}", v) for k, v in sorted(ind_truc.items())]
    if so_truc >= 0:
        khai.append(("tabs", str(so_truc)))
    if not (khai or truoc or sau or dong or trai or phai or dau_dong or treo or moc or tab):
        return None
    return GianCach(
        doan=doan,
        truoc=truoc,
        sau=sau,
        dong=dong,
        luat_dong=luat_dong,
        trai=trai,
        phai=phai,
        dau_dong=dau_dong,
        treo=treo,
        moc=moc,
        tab=tab,
        khai=tuple(khai),
    )


def _chu_va_dinh_dang_o(
    tc: ET.Element,
    kieu_chu: dict[str, dict[str, str]],
    kieu_gc: dict[str, _KieuGC] | None = None,
) -> tuple[str, tuple[DinhDangChu, ...], tuple[GianCach, ...]]:
    """Chữ của một ô bảng, định dạng run và giãn cách/thụt lề của nó, offset
    dịch về chuỗi ô.

    Chữ ô là các `w:p` trong ô nối bằng MỘT dấu cách (`_duyet_than`), nên mỗi
    đoạn góp một đoạn offset riêng. Đoạn RỖNG chữ không góp chữ và không góp
    dấu cách, nhưng run và giãn cách của nó vẫn được giữ: một `w:p` rỗng khai
    `w:rPr`/`w:spacing` là một điều tệp nói, và `doan` vẫn đếm nó để toạ độ
    khớp với nguồn.
    """
    kg = kieu_gc or {}
    phan: list[str] = []
    ra: list[DinhDangChu] = []
    gc: list[GianCach] = []
    n = 0
    for j, p in enumerate(tc.iter(_P)):
        x = _chu(p)
        goc = n + (1 if phan and x else 0)
        ra.extend(replace(r, dau=r.dau + goc, cuoi=r.cuoi + goc) for r in _dinh_dang_doan(p, kieu_chu, j))
        if (g := _gian_cach_doan(p, kg, j)) is not None:
            gc.append(replace(g, tab=tuple(t + goc for t in g.tab)))
        if x:
            if phan:
                n += 1
            phan.append(x)
            n += len(x)
    return " ".join(phan), tuple(ra), tuple(gc)


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


def _gc_mot(p: ET.Element, kieu_gc: dict[str, _KieuGC]) -> tuple[GianCach, ...]:
    """Giãn cách của một `w:p` ĐỘC LẬP (thân bài, đầu/chân trang) — luôn 0 hoặc
    1 phần tử, vì ở đó đơn vị LÀ đoạn (`doan` = 0), khác hẳn một ô bảng."""
    g = _gian_cach_doan(p, kieu_gc)
    return (g,) if g is not None else ()


# ─── ĐỊA CHỈ VÀ CHỖ TRỐNG (P2b) ────────────────────────────────────────────
# Bộ áp phép sửa (P3a) đi THẲNG tới `DiaChi` trên bytes khuôn gốc đã lưu và thay
# đúng `[dau:cuoi]` của một chỗ trống. Nên mọi hàm dưới đây chạy trên cây THÔ —
# `_doc_docx` gọi chúng TRƯỚC `_bo_fallback` — và trả về một bảng tra theo
# chính phần tử, để hai bộ duyệt (chạy trên cây đã gỡ Fallback, CÙNG các phần
# tử ấy) chỉ việc tra.

_MC_AC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
_DAY_CHAM = re.compile(r"[.…]+")


def _day_cham(s: str) -> list[tuple[int, int]]:
    """`[dau, cuoi)` của mọi CHỖ ĐIỀN kẻ bằng chấm trong `s`: dãy `.`/`…` liền
    nhau DÀI NHẤT mà `RE_CHO_DIEN` nhận — có `…`, hoặc từ ba `.` liền trở lên.
    `"…."` là một chỗ; `"20.000.000"` và dấu chấm hết câu thì không."""
    return [m.span() for m in _DAY_CHAM.finditer(s) if RE_CHO_DIEN.search(m.group())]


def _la_cham(tu: str) -> bool:
    """Cả `tu` là MỘT chỗ điền kẻ chấm (một từ của poppler/tesseract)."""
    return bool(tu) and _day_cham(tu) == [(0, len(tu))]


def _duoi_nhan(s: str) -> str:
    """Nhãn: gộp khoảng trắng, giữ 60 ký tự CUỐI — sát chỗ trống mới là nhãn."""
    return " ".join(s.split())[-60:].strip()


def _cho_trong_doan(p: ET.Element, doan: int) -> list[ChoTrong]:
    """Chỗ trống của MỘT `w:p` thô, `so` tạm 0 (`_cho_trong_don_vi` đánh lại).

    Chuỗi và vị trí tab lấy đúng từ `_vi_tri_chu`/`_vi_tri_tab` — cùng phép nối
    `noi_dung` dựa vào, chỉ là KHÔNG `strip()`. Tab thứ n nhảy tới mốc thứ n
    (đúng xấp xỉ phía vẽ dùng, xem `_moc_tab`); nó là chỗ trống khi mốc ấy có
    đường dẫn `dot`. Trong nhãn, mỗi `w:tab` là một chỗ ngắt chữ.
    """
    _, tho = _vi_tri_chu(p)
    tab = _vi_tri_tab(p)
    ppr = p.find(_PPR)
    # ponytail: chỉ mốc khai TRỰC TIẾP ở `w:pPr/w:tabs`. Mốc thừa kế từ kiểu
    # (1/46 đoạn có tab của Evaluation Form) không thành chỗ trống — đọc thêm
    # `_kieu_gian_cach` khi một biểu mẫu thật cần.
    moc = _moc_tab(ppr.find(_TABS) if ppr is not None else None)[0]
    vi = [(dau, 1, "cham", cuoi) for dau, cuoi in _day_cham(tho)]
    vi += [(t, 0, "tab", t) for i, t in enumerate(tab) if i < len(moc) and moc[i].leader == "dot"]
    ra: list[ChoTrong] = []
    truoc = 0
    for dau, _, kieu, cuoi in sorted(vi):
        cat = [truoc, *(t for t in tab if truoc < t < dau), dau]
        nhan = _duoi_nhan(" ".join(tho[a:b] for a, b in zip(cat, cat[1:])))
        ra.append(ChoTrong(so=0, kieu=kieu, nhan=nhan, doan=doan, dau=dau, cuoi=cuoi))
        truoc = cuoi
    return ra


def _cho_trong_don_vi(nut: ET.Element) -> tuple[ChoTrong, ...]:
    """Chỗ trống của một vật chứa (`w:p` hoặc `w:tc`) trên cây THÔ, theo thứ tự
    đọc, `so` đánh liền qua các đoạn. `doan` là thứ tự trong `nut.iter(w:p)`
    THÔ — tính cả đoạn trong `mc:Fallback` — đúng như bộ áp đi lại.

    Fail closed với hộp chữ và `mc:AlternateContent`: nội dung ở đó có HAI bản
    (Choice/Fallback), điền một bản là để bản kia sai. Đoạn CHỨA chúng và đoạn
    NẰM TRONG chúng không có chỗ trống nào (đo trên BM.ĐT.18.05: "Phụ lục 4" hai
    lần trên cây thô).
    """
    chan: set[ET.Element] = set()
    for e in nut.iter():
        if e.tag in (_P, _MC_AC) and (trong := [x for x in e.iter() if x is not e and x.tag in (_P, _MC_AC)]):
            chan.add(e)
            chan.update(trong)
    ra = [c for j, p in enumerate(nut.iter(_P)) if p not in chan for c in _cho_trong_doan(p, j)]
    return tuple(replace(c, so=i) for i, c in enumerate(ra))


def _vi_tri(phan: str, chi_muc: tuple[int, ...], nut: ET.Element) -> dict:
    ct = _cho_trong_don_vi(nut)
    return {"dia_chi": DiaChi(phan=phan, chi_muc=chi_muc), **({"cho_trong": ct} if ct else {})}


def _dinh_vi_than(goc: ET.Element, phan: str) -> dict[ET.Element, dict]:
    """Vật chứa → địa chỉ + chỗ trống, cho ĐÚNG những vật chứa `_duyet_than`
    biến thành đơn vị: `w:p` con của `w:body` và `w:tc` của một `w:tbl` con của
    `w:body`. Chỉ số đếm MỌI con phần tử (`enumerate`, không `findall`)."""
    than = goc.find(_BODY)
    if than is None:
        return {}
    ra: dict[ET.Element, dict] = {}
    for i, con in enumerate(than):
        if con.tag == _P:
            ra[con] = _vi_tri(phan, (i,), con)
        elif con.tag == _TBL:
            for h, tr in enumerate(con):
                for c, tc in enumerate(tr) if tr.tag == _TR else ():
                    if tc.tag == _TC:
                        ra[tc] = _vi_tri(phan, (i, h, c), tc)
    return ra


def _dinh_vi_phang(goc: ET.Element, phan: str) -> dict[ET.Element, dict]:
    """Mọi `w:p` của một đầu/chân trang (gốc `w:hdr`/`w:ftr`) → địa chỉ + chỗ
    trống; đường dẫn đi qua bảng, `w:sdt`… tới đúng `w:p` ấy.

    KHÔNG đi vào một `w:p` (hộp chữ) hay `mc:AlternateContent`: đoạn ở đó có
    hai bản, nên nó không có địa chỉ nào (fail closed). Ngăn xếp thay đệ quy —
    một tệp lồng sâu cố ý không được làm tràn ngăn gọi."""
    ra: dict[ET.Element, dict] = {}
    ngan: list[tuple[ET.Element, tuple[int, ...]]] = [(goc, ())]
    while ngan:
        nut, duong = ngan.pop()
        for i, con in enumerate(nut):
            if con.tag == _P:
                ra[con] = _vi_tri(phan, (*duong, i), con)
            elif con.tag != _MC_AC:
                ngan.append((con, (*duong, i)))
    return ra


def _duoi_vi_tri(dinh_vi: dict[ET.Element, dict] | None, nut: ET.Element) -> tuple:
    """Đuôi tuple cho `_dat_vi_tri`: `(dict,)` khi `nut` có địa chỉ, `()` khi
    không — mọi hình dạng tuple cũ đi qua y nguyên."""
    v = (dinh_vi or {}).get(nut)
    return (v,) if v else ()


# ─── DÒNG CHẢY TRANG ───────────────────────────────────────────────────────
# Một `.docx` KHÔNG nói nó dày mấy trang: chỗ ngắt THẬT là kết quả của việc dàn
# trang (phông chữ có trên máy, lề, luật widow/orphan, bảng bị xé) mà chỉ
# Word/LibreOffice lúc MỞ tệp mới tính được. Nhưng tệp CÓ KHAI hai loại ngắt,
# và hai loại ấy đọc thẳng ra được, không cần dàn trang:
#
#   1. `w:br w:type="page"` — người soạn ấn Ctrl+Enter, một ngắt trang CỨNG.
#   2. Ngắt PHÂN ĐOẠN bắt đầu trang mới. `w:type` VẮNG MẶT nghĩa là `nextPage`
#      (mặc định của OOXML), nên ở riêng chỗ này "không khai" LÀ một ngắt —
#      không phải "không biết", và đây là ngoại lệ có căn cứ của luật "chỉ đọc
#      những gì tệp nói" mà cả tệp này theo.
#
# KHÔNG đọc `w:lastRenderedPageBreak`. Nó không phải lời khai của người soạn mà
# là BỘ NHỚ ĐỆM dàn trang của lần cuối một bản Word nào đó mở tệp: công cụ khác
# (LibreOffice — chính đường `.doc` → `.docx` của dự án này — python-docx, trình
# sinh biểu mẫu) không ghi nó; nó ôi ngay khi ai đó sửa phần TRÊN mà chưa dựng
# lại hình; và tin nó thì CÙNG một tài liệu đọc ra hai số trang khác nhau trước
# và sau một vòng mở-lưu bằng Word — đúng kiểu bất định mà phép neo trích dẫn
# tồn tại để chặn. Đo trên BM.M05: đúng MỘT `lastRenderedPageBreak`, và nó nằm
# ngay sau `w:br w:type="page"` — bỏ qua nó không mất một sự thật nào.
#
# Mô hình này CỐ Ý KHÔNG khẳng định: có bao nhiêu trang GIỮA hai ngắt đã khai
# (phải dàn trang mới biết), trang TRẮNG mà `evenPage`/`oddPage` chèn thêm để
# về đúng chẵn/lẻ (phụ thuộc số trang thật của phần đứng trước), và việc Word
# bỏ qua một ngắt cứng nằm trong ô bảng ở một số ca. Số ký tự vẫn ước lượng ĐỘ
# DÀY tài liệu — nhưng chỉ ở `TaiLieuDaDoc.so_trang` (định tuyến FR-029/030,
# xem `KY_TU_MOI_TRANG`), KHÔNG bao giờ ở `DonViVanBan.trang` mà người dùng
# đọc thành "tr. 2".
_SECT_SANG_TRANG = {"", "nextPage", "evenPage", "oddPage"}


def _kieu_phan_doan(goc: ET.Element) -> list[str]:
    """`w:type` của TỪNG phân đoạn, theo thứ tự tài liệu.

    `w:sectPr` nằm trong `w:pPr` KẾT THÚC một phân đoạn, còn `w:type` của nó
    khai phân đoạn ấy BẮT ĐẦU thế nào (cùng cách `python-docx` đọc
    `Section.start_type`). Nên ngắt đứng SAU đoạn kết phân đoạn `j` do `w:type`
    của phân đoạn `j+1` quyết định, không phải của chính `j` — phần tử CUỐI
    danh sách này là `w:sectPr` cấp `w:body`, tức phân đoạn cuối cùng, và nó
    không đẻ ra ngắt nào vì sau nó không còn gì.

    Rỗng với `word/headerN.xml`/`footerN.xml`: ở đó không có `w:body`, và một
    đầu trang không khai ngắt trang nào cả.
    """
    than = goc.find(_BODY)
    if than is None:
        return []

    def _kieu(sect: ET.Element) -> str:
        t = sect.find(_TYPE)
        return (t.get(_VAL) or "") if t is not None else ""

    ra = [
        _kieu(sect)
        for p in than.iter(_P)
        if (sect := p.find(f"{_PPR}/{_SECTPR}")) is not None
    ]
    if (cuoi := than.find(_SECTPR)) is not None:
        ra.append(_kieu(cuoi))
    return ra


def _ngat_trong_doan(nut: ET.Element) -> tuple[int, int]:
    """(số ngắt TRƯỚC ký tự đầu tiên, số ngắt SAU nó) do chính `nut` khai.

    Nhận cả `w:p` lẫn `w:tc`: một ô bảng là MỘT đơn vị dù chứa nhiều `w:p`, nên
    câu hỏi "ngắt đứng trước hay sau chữ của đơn vị này" giống hệt nhau ở hai
    mức. `iter()` đi đúng thứ tự tài liệu, nên nó cũng là thứ tự các run chạy.

    Tách hai vế vì chỗ ĐỨNG của ngắt đổi hẳn nghĩa: ngắt trước chữ đẩy CHÍNH
    đơn vị này sang trang mới, ngắt sau chữ chỉ đẩy đơn vị KẾ TIẾP. Một đoạn
    KHÔNG có chữ nào (đoạn chỉ chứa mỗi ngắt — đúng hình dạng của BM.M05, và
    là cách Word ghi một Ctrl+Enter đứng riêng) không sinh ra đơn vị nào, nên
    mọi ngắt của nó rơi vào vế trước và đẩy đúng đơn vị đứng sau.
    """
    truoc = sau = 0
    da_co_chu = False
    for con in nut.iter():
        if con.tag == _BR and con.get(_TYPE) == "page":
            if da_co_chu:
                sau += 1
            else:
                truoc += 1
        elif con.tag == _T and (con.text or "").strip():
            da_co_chu = True
    return truoc, sau


class _DemTrang:
    """Số trang KHAI hiện tại khi đi dọc thân bài, và phép đẩy nó.

    Một đối tượng nhỏ thay vì ba biến cục bộ lặp ở hai bộ duyệt: `_duyet_than`
    và `_duyet_phang` phải đếm GIỐNG HỆT nhau, nếu không thì cùng một tệp đọc
    ra hai số trang khác nhau tuỳ đường nào thắng phép so `0.9 * tong`.
    """

    def __init__(self, goc: ET.Element) -> None:
        self.trang = 1
        self._sau = 0
        self._kieu = _kieu_phan_doan(goc)
        self._da_qua = 0

    def truoc(self, nut: ET.Element) -> int:
        """Đẩy theo ngắt đứng TRƯỚC chữ, trả về số trang của chính `nut`."""
        truoc, self._sau = _ngat_trong_doan(nut)
        self.trang += truoc
        return self.trang

    def sau(self, p: ET.Element | None = None) -> None:
        """Đẩy theo ngắt đứng SAU chữ, rồi theo ngắt phân đoạn của `p` (nếu có)."""
        self.trang += self._sau
        self._sau = 0
        if p is None or p.find(f"{_PPR}/{_SECTPR}") is None:
            return
        self._da_qua += 1
        if self._da_qua < len(self._kieu) and self._kieu[self._da_qua] in _SECT_SANG_TRANG:
            self.trang += 1


def _duyet_phang(
    goc: ET.Element,
    vung: str,
    theo_kieu: dict[str, str] | None = None,
    kieu_chu: dict[str, dict[str, str]] | None = None,
    kieu_gc: dict[str, _KieuGC] | None = None,
    dinh_vi: dict[ET.Element, dict] | None = None,
) -> list[tuple]:
    """Mọi `w:p` theo thứ tự tài liệu, KHÔNG toạ độ bảng.

    Vừa là đường lùi của thân bài, vừa là đường duy nhất cho đầu/chân trang —
    ở đó một `w:p` là một dòng và không có gì để định vị thêm.

    `dinh_vi` (`_dinh_vi_phang`) chỉ có với đầu/chân trang. Thân bài rơi vào
    đường lùi thì KHÔNG có địa chỉ hay chỗ trống nào: đường lùi tồn tại chính vì
    cấu trúc không đọc được hết, nên không còn chỉ số con nào đáng tin (fail
    closed; thêm khi một biểu mẫu thật cần điền tại chỗ qua `w:sdt` cấp thân).

    Đếm ngắt trang y hệt `_duyet_than` (cùng `_DemTrang`): đây là đường LÙI của
    thân bài, nên một tài liệu rơi vào đây không được mất số trang. Với đầu/chân
    trang thì bộ đếm đứng nguyên ở 1 — không `w:body`, không `w:sectPr`, và một
    chân trang lặp lại ở mọi trang thì trang 1 là chỗ nó xuất hiện lần đầu.
    """
    tk = theo_kieu or {}
    kc = kieu_chu or {}
    kg = kieu_gc or {}
    dem = _DemTrang(goc)
    ra: list[tuple] = []
    for p in goc.iter(_P):
        trang = dem.truoc(p)
        if c := _chu(p):
            ra.append(
                (
                    trang,
                    c,
                    None,
                    vung,
                    None,
                    _can_le_doan(p, tk),
                    _dinh_dang_doan(p, kc),
                    _gc_mot(p, kg),
                    *_duoi_vi_tri(dinh_vi, p),
                )
            )
        dem.sau(p)
    return ra


def _duyet_than(
    goc: ET.Element,
    theo_kieu: dict[str, str] | None = None,
    vien_kieu: dict[str, bool] | None = None,
    kieu_chu: dict[str, dict[str, str]] | None = None,
    kieu_gc: dict[str, _KieuGC] | None = None,
    kieu_canh: dict[str, dict[str, tuple[str, str]]] | None = None,
    dinh_vi: dict[ET.Element, dict] | None = None,
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
    kg = kieu_gc or {}
    kcanh = kieu_canh or {}
    ra: list[tuple] = []
    so_bang = 0
    dem = _DemTrang(goc)
    for con in than:
        if con.tag == _P:
            trang = dem.truoc(con)
            if chu := _chu(con):
                ra.append(
                    (
                        trang,
                        chu,
                        None,
                        "than",
                        None,
                        _can_le_doan(con, tk),
                        _dinh_dang_doan(con, kc),
                        _gc_mot(con, kg),
                        *_duoi_vi_tri(dinh_vi, con),
                    )
                )
            dem.sau(con)
        elif con.tag == _TBL:
            ti_le = _ti_le_luoi(con)
            vien = _vien_bang(con, vk)
            vien_canh = _vien_canh_bang(con, kcanh)
            for h, tr in enumerate(con.findall(_TR)):
                cao = _cao_hang(tr)
                cao_luat = _luat_cao_hang(tr)
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
                    # Ngắt trang đọc ở mức Ô, không ở mức `w:p` bên trong: ô
                    # LÀ đơn vị, nên câu hỏi duy nhất trả lời được là ô này rơi
                    # vào trang nào. Word bỏ qua ngắt cứng trong bảng ở một số
                    # ca — trần đã ghi ở `_SECT_SANG_TRANG` phía trên; ở đây
                    # tệp khai gì thì đọc nấy, không đoán thay Word.
                    trang = dem.truoc(tc)
                    chu, dinh_dang, gian_cach = _chu_va_dinh_dang_o(tc, kc, kg)
                    # Căn lề của Ô lấy từ ĐOẠN VĂN ĐẦU của chính ô đó — một
                    # ô có thể có nhiều `w:p` lồng, nhưng căn lề hiển thị
                    # là của dòng đầu tiên người đọc thấy.
                    can_le = _can_le_doan(tc.find(_P), tk)
                    ra.append(
                        (
                            trang,
                            chu,
                            None,
                            "than",
                            (so_bang, h, c),
                            can_le,
                            dinh_dang,
                            gian_cach,
                            nhip,
                            ti_le,
                            vien,
                            cao,
                            cao_luat,
                            vien_canh,
                            _vien_canh_o(tc),
                            *_duoi_vi_tri(dinh_vi, tc),
                        )
                    )
                    dem.sau()
            so_bang += 1
    return ra


def _doc_docx(
    du_lieu: bytes,
) -> tuple[list[tuple], tuple[tuple[str, int], ...], tuple[AnhTaiLieu, ...], dict[str, tuple[str, bytes]]]:
    """Thân bài theo cấu trúc, rồi đầu trang, rồi chân trang — kèm LỀ TRANG và ẢNH.

    Lề trang trả về RIÊNG chứ không nhét vào từng tuple: nó là sự thật của cả
    tệp, một giá trị duy nhất, và chép nó vào mười hai phần tử của mỗi tuple
    chỉ để `_dat_vi_tri` đọc lại là ba trăm dòng nhiễu cho một con số.
    `_dat_vi_tri` mới là chỗ dán nó lên từng đơn vị (xem `DonViVanBan.le_trang`).

    Duyệt theo cấu trúc BỎ SÓT thứ duyệt phẳng thấy: `w:sdt` (content control),
    hộp chữ, và mọi phần tử cấp thân chưa được kể tên ở đây. Nên nó không thay
    thế duyệt phẳng một cách mù quáng — ít chữ hơn thì lùi về. Mất toạ độ bảng
    là khoản lỗ sống chung được; mất nguyên một điều khoản thì không.
    """
    try:
        with zipfile.ZipFile(BytesIO(du_lieu)) as z:
            _kiem_zip(z)
            goc = _goc_xml(z.read("word/document.xml"), "word/document.xml")
            # Địa chỉ và chỗ trống đo trên cây THÔ, TRƯỚC khi gỡ `mc:Fallback`:
            # bộ áp (P3a) đi lại trên chính bytes đã lưu, nơi Fallback vẫn còn,
            # và một hộp chữ đứng trước làm lệch `doan` nếu đo trên cây đã gỡ.
            dinh_vi = _dinh_vi_than(goc, "word/document.xml")
            goc = _bo_fallback(goc)
            # Căn lề theo KIỂU (Phase 9 U5) — `styles.xml` không bắt buộc có
            # trong một DOCX hợp lệ, và hỏng ở đó không được làm hỏng cả tài
            # liệu: mất căn lề theo kiểu là khoản lỗ sống chung được (`jc` trực
            # tiếp trên từng đoạn vẫn đọc đúng), mất nguyên một điều khoản thì
            # không.
            theo_kieu: dict[str, str] = {}
            vien_kieu: dict[str, bool] = {}
            kieu_chu: dict[str, dict[str, str]] = {}
            kieu_gc: dict[str, _KieuGC] = {}
            kieu_canh: dict[str, dict[str, tuple[str, str]]] = {}
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
                    # Viền TỪNG CẠNH theo kiểu bảng — cùng lý do dòng trên,
                    # ở mức hình dạng: `TableGrid` khai cả sáu cạnh trong
                    # `styles.xml` và KHÔNG khai gì trong `document.xml`.
                    kieu_canh = _kieu_vien_canh(goc_kieu)
                    # Định dạng chữ theo KIỂU — mất nó thì một biểu mẫu in đậm
                    # bằng kiểu đọc ra chữ thường, xem `_kieu_dinh_dang_chu`.
                    kieu_chu = _kieu_dinh_dang_chu(goc_kieu)
                    # Giãn cách/thụt lề theo KIỂU — mất nó thì một biểu mẫu
                    # đặt giãn dòng bằng kiểu đọc ra không giãn dòng gì cả.
                    kieu_gc = _kieu_gian_cach(goc_kieu)
            than = _duyet_than(goc, theo_kieu, vien_kieu, kieu_chu, kieu_gc, kieu_canh, dinh_vi)
            # Thước đo để lùi về là TỔNG chữ `w:t` của thân, KHÔNG phải duyệt
            # phẳng: duyệt phẳng đếm hai lần chữ trong hộp chữ (một `w:p` lồng
            # trong `w:p`), và với thước đó cấu trúc luôn "thua". Đo 2026-09-16
            # trên một kế hoạch thực tập: ba bảng mất toạ độ vì hai chữ "Phụ lục 4".
            nut_than = goc.find(_BODY)
            tong = _tong_chu(nut_than) if nut_than is not None else 0
            if sum(len(t[1]) for t in than) < 0.9 * tong:
                than = _duyet_phang(goc, "than", theo_kieu, kieu_chu, kieu_gc)

            ra = list(than)
            for tien_to, vung in (("word/header", "dau_trang"), ("word/footer", "chan_trang")):
                for ten in sorted(n for n in z.namelist() if n.startswith(tien_to) and n.endswith(".xml")):
                    goc_phan = _goc_xml(z.read(ten), ten)
                    ra.extend(_duyet_phang(goc_phan, vung, theo_kieu, kieu_chu, kieu_gc, _dinh_vi_phang(goc_phan, ten)))
            # Ảnh đi RIÊNG khỏi `ra` cùng lý lẽ lề trang: mô tả ảnh là sự thật
            # cấp TÀI LIỆU (`_dat_vi_tri` dán nó lên từng đơn vị), còn bytes
            # không bao giờ đi vào một đơn vị nào.
            anh, anh_byte = _doc_anh(z, goc)
            return ra, _le_trang(goc), anh, anh_byte
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


def _doc_pdf(du_lieu: bytes) -> list[tuple]:
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
    return _gan_hop_pdf(ra, du_lieu)


def _chay_cong_cu(lenh: list[str], vao: bytes) -> bytes | None:
    """stdout của một công cụ poppler chạy trong hộp cát, hoặc `None` — thiếu
    công cụ, mã thoát khác 0, hay treo quá `_HAN_CONG_CU_GIAY`. `None` nghĩa là
    "không có hộp", KHÔNG phải tài liệu hỏng: chữ đã đọc xong bằng đường khác.

    Cùng khuôn `_chay_soffice`: môi trường tối giản, HOME riêng trong thư mục tạm
    sắp bị xoá, phiên mới để `_giet_sach_nhom` diệt được cả nhóm khi treo. Không
    giữ suất `_suat_chuyen_doi`: một lượt `pdftotext`/`pdftoppm` tốn vài chục
    mili giây, không phải ~171 MB như soffice. Không log stderr — nó bắt nguồn
    từ tài liệu người dùng; chỉ tên công cụ và mã thoát.
    """
    if shutil.which(lenh[0]) is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen(
            lenh,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tmp,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp},
            start_new_session=True,
        )
        try:
            ra, _ = proc.communicate(vao, timeout=_HAN_CONG_CU_GIAY)
        except subprocess.TimeoutExpired:
            _giet_sach_nhom(proc)
            logger.warning("doc_tai_lieu: %s treo quá %ss, đọc tiếp không hộp", lenh[0], _HAN_CONG_CU_GIAY)
            return None
    if proc.returncode != 0:
        logger.warning("doc_tai_lieu: %s thoát mã %s, đọc tiếp không hộp", lenh[0], proc.returncode)
        return None
    return ra


_Hop = tuple[float, float, float, float]


def _tu_pdf(du_lieu: bytes) -> dict[int, list[tuple[tuple[str, ...], str, _Hop]]]:
    """Trang → mọi TỪ của poppler: (khoá dòng poppler, chữ, hộp điểm gốc
    trên-trái). Rỗng khi không có công cụ hay đầu ra không đọc được.

    `-tsv` chứ không `-bbox-layout`: cùng hộp từ, nhưng `-bbox-layout` in
    siêu dữ liệu vào đầu HTML, và poppler 26.04 (máy dev) CHẾT ở đó (exit 134)
    khi `/Keywords` rỗng — đúng thứ reportlab ghi mặc định (đo 2026-09-26;
    poppler 25.03 của image triển khai thì không). TSV không in siêu dữ liệu,
    và có sẵn trong cả hai bản.
    """
    ra = _chay_cong_cu(["pdftotext", "-tsv", "-", "-"], du_lieu)
    tu: dict[int, list[tuple[tuple[str, ...], str, _Hop]]] = {}
    for hang in (ra or b"").decode("utf-8", errors="replace").splitlines()[1:]:
        c = hang.split("\t")
        if len(c) != 12 or c[0] != "5" or not c[11]:
            continue
        try:
            trang = int(c[1])
            x, y, w, h = (float(v) for v in c[6:10])
        except ValueError:
            continue
        tu.setdefault(trang, []).append((tuple(c[1:5]), c[11], (x, y, x + w, y + h)))
    return tu


def _cung_dong(a: _Hop, b: _Hop) -> bool:
    """Hai hộp cùng một dòng THỊ GIÁC: tâm dọc của mỗi hộp nằm trong hộp kia."""
    return a[1] <= (b[1] + b[3]) / 2 <= a[3] and b[1] <= (a[1] + a[3]) / 2 <= b[3]


def _dong_ung_vien(tu: list[tuple[tuple[str, ...], str, _Hop]]) -> list[list[tuple[str, _Hop]]]:
    """Các dòng một đơn vị pypdf có thể khớp: dòng của poppler, CỘNG dòng thị
    giác gom theo độ cao. Cần cả hai: căn đều hai lề làm poppler tách một dòng
    thành nhiều "dòng" (mỗi từ một dòng khi khoảng cách lớn — đo trên BM.M05 dựng
    bằng LibreOffice), còn hai cột cùng độ cao thì chỉ dòng poppler tách đúng.
    Hai ứng viên cùng một bộ từ là MỘT ứng viên."""
    theo_khoa: dict[tuple[str, ...], list[tuple[str, _Hop]]] = {}
    for khoa, chu, hop in tu:
        theo_khoa.setdefault(khoa, []).append((chu, hop))
    nhom: list[list[tuple[str, _Hop]]] = []
    for chu, hop in sorted(((c, h) for _, c, h in tu), key=lambda t: (t[1][1] + t[1][3]) / 2):
        if nhom and _cung_dong(nhom[-1][0][1], hop):
            nhom[-1].append((chu, hop))
        else:
            nhom.append([(chu, hop)])
    ra: dict[tuple[_Hop, ...], list[tuple[str, _Hop]]] = {}
    for dong in [*theo_khoa.values(), *nhom]:
        dong = sorted(dong, key=lambda t: t[1][0])
        ra.setdefault(tuple(sorted(h for _, h in dong)), dong)
    return list(ra.values())


def _chuan_khop(s: str) -> str:
    """Khoá so dòng pypdf với dòng poppler: NFC, bỏ MỌI khoảng trắng — hai bộ
    đọc chia khoảng trắng khác nhau (pypdf giữ hai dấu cách của chữ giãn đều)."""
    return "".join(unicodedata.normalize("NFC", s).split())


def _tron(hop: tuple[float, ...]) -> _Hop:
    x0, y0, x1, y1 = (round(v, 2) for v in hop)
    return (x0, y0, x1, y1)


def _them_dong_pdf(dong: list[tuple[str, _Hop]]) -> dict:
    """Hộp của dòng và chỗ trống của nó: mỗi TỪ toàn chấm là một chỗ, nhãn là
    các từ đứng trước nó trên dòng (sau chỗ trống liền trước)."""
    x0, y0, x1, y1 = zip(*(h for _, h in dong), strict=True)
    hop = _tron((min(x0), min(y0), max(x1), max(y1)))
    cho: list[ChoTrong] = []
    nhan: list[str] = []
    for chu, h in dong:
        if _la_cham(chu):
            nhan_cho = _duoi_nhan(" ".join(nhan))
            cho.append(ChoTrong(so=len(cho), kieu="cham", nhan=nhan_cho, hop=_tron(h), co_chu=round(h[3] - h[1], 2)))
            nhan = []
        else:
            nhan.append(chu)
    return {"hop": hop, **({"cho_trong": tuple(cho)} if cho else {})}


def _gan_hop_pdf(thoi: list[tuple], du_lieu: bytes) -> list[tuple]:
    """Gắn hộp dòng + chỗ trống cho những dòng pypdf khớp DUY NHẤT một dòng
    poppler trên CÙNG trang — hai phía đều duy nhất. `noi_dung` vẫn là đúng dòng
    pypdf như trước; dòng không khớp, hay khớp hai nơi, không có hộp nào (bộ đè
    chữ đặt nhầm dòng tệ hơn không đặt).

    ponytail: một từ trộn nhãn với chấm ("Số…./….") không thành chỗ trống — poppler
    chỉ cho hộp TỪNG TỪ, chia hộp theo ký tự là đoán. Toạ độ là không gian hiển
    thị của poppler (hộp cắt, sau `/Rotate`); P3b phải đổi về không gian người
    dùng của trang.
    """
    tu = _tu_pdf(du_lieu) if thoi else {}
    if not tu:
        return thoi
    ung: dict[tuple[int, str], list[list[tuple[str, _Hop]]]] = {}
    for trang, cac_tu in tu.items():
        for dong in _dong_ung_vien(cac_tu):
            ung.setdefault((trang, _chuan_khop(" ".join(c for c, _ in dong))), []).append(dong)
    dem: dict[tuple[int, str], int] = {}
    for so, dong in thoi:
        dem[(so, _chuan_khop(dong))] = dem.get((so, _chuan_khop(dong)), 0) + 1
    ra: list[tuple] = []
    for so, dong in thoi:
        khoa = (so, _chuan_khop(dong))
        khop = ung.get(khoa, [])
        ra.append((so, dong, _them_dong_pdf(khop[0])) if dem[khoa] == 1 and len(khop) == 1 else (so, dong))
    return ra


# ---------------------------------------------------------------- gán vị trí


def _dat_vi_tri(
    thoi: list[tuple],
    le_trang: tuple[tuple[str, int], ...] = (),
    anh: tuple[AnhTaiLieu, ...] = (),
    anh_byte: dict[str, tuple[str, bytes]] | None = None,
    uoc_do_day: bool = False,
) -> TaiLieuDaDoc:
    """Gán `trang`, `offset_dau`, nguồn chữ, LỀ TRANG và ẢNH cho từng đơn vị.

    Nhận cả sáu hình dạng: `(trang, noi_dung)` từ nhánh đọc chữ thật,
    `(trang, noi_dung, do_tin)` từ nhánh OCR,
    `(trang, noi_dung, do_tin, vung, bang)` từ DOCX trước Phase 9,
    `(trang, noi_dung, do_tin, vung, bang, can_le)` từ DOCX có căn lề (Phase 9
    U5), `(…, can_le, dinh_dang, gian_cach)` từ một đoạn DOCX có định dạng chữ
    và giãn cách (2026-09-18), và `(…, gian_cach, bang_nhip, bang_ti_le,
    bang_vien, bang_cao, bang_cao_luat, bang_vien_canh, o_vien_canh)` từ một Ô
    BẢNG. Có `do_tin` nghĩa là máy đang đoán, nên đơn vị đó mang nhãn `ocr`.

    `le_trang` là sự thật của cả TỆP, không của một tuple nào: nó vào đây một
    lần rồi dán lên MỌI đơn vị (xem `DonViVanBan.le_trang`). Mặc định rỗng để
    ba nhánh không phải DOCX (PDF, OCR ảnh) và mọi lời gọi cũ chạy y nguyên.
    `anh` đi ĐÚNG đường đó, cùng một lý lẽ (xem `DonViVanBan.anh`).

    `anh_byte` thì KHÔNG dán lên đơn vị nào: nó chỉ đi qua đây để về
    `TaiLieuDaDoc`, nơi duy nhất cầm bytes ảnh (xem `TaiLieuDaDoc.anh_byte`).

    Hàm này KHÔNG chạm `noi_dung`, `offset_dau` hay `chi_so` vì có ảnh hay
    không: một ảnh không đẻ ra đơn vị mới và không dịch một ký tự nào, nên mọi
    neo trích dẫn đã lưu vẫn trỏ đúng chỗ cũ (xem
    `test_anh_khong_doi_noi_dung_hay_neo`).

    `dinh_dang`/`gian_cach` chèn vào giữa (sau `can_le`) chứ không nối vào
    cuối: đoạn văn thân bài khi đó chỉ cần 8 phần tử thay vì 12 phần tử toàn
    giá trị mặc định. Cả hai nơi dựng tuple (`_duyet_than`, `_duyet_phang`)
    đổi cùng lúc với hàm này, nên không có hình dạng cũ nào còn chạy qua đây.

    `trang` đến SẴN từ người gọi ở cả bốn nhánh, và nghĩa của nó khác nhau theo
    nguồn — đó là chủ ý: PDF/OCR biết trang THẬT (đã dàn trang rồi), DOCX chỉ
    biết trang KHAI (`w:br w:type="page"` và ngắt phân đoạn, xem `_DemTrang`).
    Cả hai đều là những gì nguồn nói được, không phải một con số suy ra.

    `uoc_do_day` chỉ đổi `so_trang`, không đổi một `DonViVanBan.trang` nào: với
    DOCX, số trang KHAI là một SÀN (tệp nói ít nhất bấy nhiêu trang) chứ không
    phải độ dày, nên `so_trang` — thứ định tuyến FR-029/030 và cổng độ dài của
    `hieu_tai_lieu.loc_don_vi` đọc — lấy thêm ước lượng theo ký tự
    (`KY_TU_MOI_TRANG`) và giữ số LỚN HƠN. Một hợp đồng 40 trang không khai
    ngắt nào vẫn phải lộ ra là dài; một biểu mẫu 2 trang khai đúng một ngắt
    vẫn phải lộ ra là 2 trang.

    `trang is None` (lời gọi cũ, test dựng tay) vẫn chạy: khi đó trang quay về
    đúng phép quy đổi theo ký tự trước bản vá này, không ném lỗi.

    Mọi hình dạng trên có thể mang thêm MỘT đuôi `dict` (P2b) — `dia_chi`,
    `cho_trong`, `hop` — chỉ khi nguồn khai. Đuôi ấy được gỡ TRƯỚC khi đọc
    theo vị trí, nên không một hình dạng cũ nào đổi nghĩa.
    """
    don_vi: list[DonViVanBan] = []
    da_di = 0          # ký tự đã đi qua trong toàn tài liệu (nhánh DOCX)
    trang_hien = None
    offset = 0
    theo_ky_tu = bool(thoi) and thoi[0][0] is None

    for i, muc in enumerate(thoi):
        them: dict = {}
        if isinstance(muc[-1], dict):
            them, muc = muc[-1], muc[:-1]
        trang, noi_dung = muc[0], muc[1]
        do_tin = muc[2] if len(muc) > 2 else None
        vung = muc[3] if len(muc) > 3 else "than"
        bang = muc[4] if len(muc) > 4 else None
        can_le = muc[5] if len(muc) > 5 else "trai"
        dinh_dang = muc[6] if len(muc) > 6 else ()
        gian_cach = muc[7] if len(muc) > 7 else ()
        bang_nhip = muc[8] if len(muc) > 8 else 1
        bang_ti_le = muc[9] if len(muc) > 9 else ()
        bang_vien = muc[10] if len(muc) > 10 else True
        bang_cao = muc[11] if len(muc) > 11 else 0
        bang_cao_luat = muc[12] if len(muc) > 12 else ""
        bang_vien_canh = muc[13] if len(muc) > 13 else ()
        o_vien_canh = muc[14] if len(muc) > 14 else ()
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
                bang_cao_luat=bang_cao_luat,
                bang_vien_canh=bang_vien_canh,
                o_vien_canh=o_vien_canh,
                le_trang=le_trang,
                dinh_dang=dinh_dang,
                gian_cach=gian_cach,
                anh=anh,
                dia_chi=them.get("dia_chi"),
                cho_trong=them.get("cho_trong", ()),
                hop=them.get("hop"),
            )
        )
        offset += len(noi_dung) + 1   # +1 cho dấu xuống dòng giữa hai đơn vị
        da_di += len(noi_dung) + 1

    so_ky_tu = sum(len(d.noi_dung) for d in don_vi)
    so_trang = max((d.trang for d in don_vi), default=1)
    if theo_ky_tu or uoc_do_day:
        so_trang = max(so_trang, 1, ceil(so_ky_tu / KY_TU_MOI_TRANG))
    return TaiLieuDaDoc(
        don_vi=don_vi, so_trang=so_trang, so_ky_tu=so_ky_tu, anh_byte=anh_byte or {}
    )


# ═══ OCR ════════════════════════════════════════════════════════════════════
# Gọi `tesseract` qua subprocess thay vì thêm `pytesseract`: một tiến trình con
# và một lần đọc TSV là đủ, còn thư viện bọc thì thêm một dependency để làm
# đúng việc đó. Bản thân `tesseract` với gói `vie` vẫn là điều kiện bắt buộc.


_HopPx = tuple[int, int, int, int]
_DongOcr = tuple[str, float, _HopPx | None, list[tuple[str, _HopPx | None]]]


def _hop_tsv(c: list[str]) -> _HopPx | None:
    """Cột `left top width height` của một hàng TSV → `(x0, y0, x1, y1)` px."""
    try:
        x, y, w, h = (int(v) for v in c[6:10])
    except ValueError:
        return None
    return (x, y, x + w, y + h)


def _tesseract(duong_anh: str) -> list[_DongOcr]:
    """(dòng, độ tin, hộp dòng px, [(từ, hộp px)]) cho một ảnh. TSV vì nó cho
    độ tin TỪNG TỪ — và, từ P2b, hộp từng từ (cột 6–9, px ở DPI của ảnh).

    Độ tin của một dòng là trung bình độ tin các từ trong dòng đó — thấp nghĩa
    là máy đang đoán, và một dòng máy đang đoán không nên thành bằng chứng.
    Hộp dòng là hộp bao các từ ấy; một hộp đọc không ra số làm cả dòng mất hộp,
    không làm mất chữ — chữ và độ tin đi đúng đường cũ.
    """
    ra = subprocess.run(
        ["tesseract", duong_anh, "-", "-l", "vie", "tsv"],
        capture_output=True,
        timeout=_HAN_TREO_GIAY,
    )
    if ra.returncode != 0:
        raise KhongDocDuoc(LoaiHong.tep_hong, "tesseract không đọc được ảnh")

    dong: dict[tuple, list[tuple[str, float, _HopPx | None]]] = {}
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
        dong.setdefault(tuple(c[2:5]), []).append((c[11], tin / 100.0, _hop_tsv(c)))

    ket: list[_DongOcr] = []
    for tu in dong.values():
        chu = " ".join(t for t, _, _ in tu).strip()
        tin = sum(d for _, d, _ in tu) / len(tu)
        if chu and tin >= NGUONG_TIN_OCR:
            hop = None
            if all(h for _, _, h in tu):
                x0, y0, x1, y1 = zip(*(h for _, _, h in tu), strict=True)
                hop = (min(x0), min(y0), max(x1), max(y1))
            ket.append((chu, tin, hop, [(t, h) for t, _, h in tu]))
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
        # Ảnh tải lên không có khuôn gốc (ngoài phạm vi kế hoạch khuôn gốc), nên
        # không mang hộp: chỉ chữ và độ tin, đúng như trước.
        return [(1, chu, tin) for chu, tin, _, _ in _tesseract(f.name)]


_PGM = re.compile(rb"P5\s+(\d+)\s+(\d+)\s+255\s")


def _cac_trang_pgm(du_lieu: bytes) -> list["np.ndarray"]:
    """Mọi ảnh PGM 8-bit nối liền nhau (stdout của `pdftoppm -gray` khi không có
    tên gốc) → mảng `(cao, rộng)`. Dừng ở ảnh đầu tiên sai hình dạng.

    Đọc tay định dạng PGM thay vì thêm Pillow làm phụ thuộc trực tiếp: đầu đề
    là một dòng chữ, phần còn lại là đúng `rộng × cao` byte."""
    import numpy as np

    ra: list[np.ndarray] = []
    i = 0
    while m := _PGM.match(du_lieu, i):
        w, h = int(m[1]), int(m[2])
        if m.end() + w * h > len(du_lieu):
            break
        ra.append(np.frombuffer(du_lieu, dtype=np.uint8, count=w * h, offset=m.end()).reshape(h, w))
        i = m.end() + w * h
    return ra


def _doan_lien(mat: "np.ndarray") -> list[tuple[int, int]]:
    """`[dau, cuoi)` của mọi đoạn `True` liền nhau trên một mảng bool 1 chiều."""
    import numpy as np

    bien = np.diff(np.concatenate(([0], mat.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(bien == 1).tolist(), np.flatnonzero(bien == -1).tolist(), strict=True))


def _day_cham_anh(den: "np.ndarray", y0: int, y1: int, xa: int, xb: int, dpi: int) -> list[tuple[int, int]]:
    """`[x0, x1)` của mọi dãy chấm trong vùng `[y0, y1) × [xa, xb)` của ảnh mực
    `den` (bool): từ BA đốm nhỏ trở lên, liền nhau không quá một khe chấm, mỗi
    đốm nằm ở phần DƯỚI dải (chấm đứng trên đường chân chữ; dấu thanh và chấm
    chữ "i" thì ở trên). Một dải mỏng hơn một chấm thì mọi đốm đều "dưới".

    Tesseract không đọc ra chữ nào cho một dãy chấm dài, nên chỗ trống của bản
    scan phải tìm bằng điểm ảnh.

    ponytail: ngưỡng đo trên bản dựng 200 dpi của 8 biểu mẫu thật (chữ 11–13 pt:
    chấm ≈ 4 px, bước ≈ 12 px); ảnh chụp nghiêng, nhoè hay nhiễu thật chưa đo —
    đo lại và chỉnh hai hằng số dưới đây khi có bản scan thật.
    """
    import numpy as np

    vung = den[y0:y1, xa:xb]
    if vung.size == 0:
        return []
    cao = vung.shape[0]
    toi_da = round(2.5 * dpi / 72)  # cạnh lớn nhất của một chấm (2,5 pt)
    khe = round(4 * dpi / 72)  # khe lớn nhất giữa hai chấm liền (4 pt)
    co = vung.any(axis=0)
    tren = np.where(co, vung.argmax(axis=0), cao)
    duoi = np.where(co, cao - 1 - vung[::-1].argmax(axis=0), -1)
    thap = co & (duoi - tren < toi_da) & ((tren >= cao * 0.4) | (cao <= toi_da))
    ra: list[tuple[int, int]] = []
    day: list[tuple[int, int]] = []
    for s, e in _doan_lien(co):
        cham = e - s <= toi_da and bool(thap[s:e].all())
        if cham and day and s - day[-1][1] <= khe:
            day.append((s, e))
            continue
        if len(day) >= 3:
            ra.append((xa + day[0][0], xa + day[-1][1]))
        day = [(s, e)] if cham else []
    if len(day) >= 3:
        ra.append((xa + day[0][0], xa + day[-1][1]))
    return ra


def _cho_trong_trang(den: "np.ndarray", dong: list[_DongOcr], dpi: int) -> list[tuple[ChoTrong, ...]]:
    """Chỗ trống của từng dòng OCR trên một trang scan, cùng thứ tự `dong`.

    Hai nơi một dãy chấm đứng:

    1. Cùng dải với dòng OCR — sau nhãn ("Họ tên:"), hay chính những từ "…"
       ngắn tesseract có đọc ra. Tìm từ mép trái dòng tới dòng OCR kế tiếp bên
       phải (hoặc hết trang), nhãn là các từ đứng trước dãy chấm.
    2. Một dải CHỈ có chấm, không dòng OCR nào phủ — dòng chấm dài xuống hàng
       dưới nhãn (LibreOffice và Word đều ngắt như vậy). Gắn vào dòng OCR gần
       nhất PHÍA TRÊN cùng cột, với nhãn là phần chữ cuối dòng ấy — nhưng chỉ
       khi giữa hai dải không có dòng chữ nào tesseract bỏ qua: không biết nhãn
       thật thì không gắn (fail closed).

    `hop` bằng điểm (px × 72 / dpi); `co_chu` là chiều cao dòng chữ chủ.
    """
    import numpy as np

    cao_trang, rong = den.shape
    pt = 72 / dpi
    toi_da = round(2.5 * dpi / 72)
    ket: list[list[ChoTrong]] = [[] for _ in dong]
    duoi_nhan: list[str] = []

    def _them(i: int, x0: int, y0: int, x1: int, y1: int, nhan: str, cao: int) -> None:
        hop = _tron((x0 * pt, y0 * pt, x1 * pt, y1 * pt))
        ket[i].append(ChoTrong(so=len(ket[i]), kieu="cham", nhan=nhan, hop=hop, co_chu=round(cao * pt, 2)))

    for i, (_, _, hop, tu) in enumerate(dong):
        # Tesseract hay dính nhãn với chấm thành MỘT từ ("ten:......"): phần chữ
        # trước dãy chấm đầu tiên mới là nhãn.
        chu_tu = [(t[: _day_cham(t)[0][0]] if _day_cham(t) else t, h) for t, h in tu if h]
        chu_tu = [(t, h) for t, h in chu_tu if t]
        if hop is None:
            duoi_nhan.append("")
            continue
        x0, y0, x1, y1 = hop
        phai = min(
            (h[0] for _, _, h, _ in dong if h and h[0] > x1 and h[1] < y1 and y0 < h[3]),
            default=rong,
        )
        truoc = x0
        for a, b in _day_cham_anh(den, y0, y1, x0, phai, dpi):
            _them(i, a, y0, b, y1, _duoi_nhan(" ".join(t for t, h in chu_tu if truoc <= h[0] < a)), y1 - y0)
            truoc = b
        duoi_nhan.append(_duoi_nhan(" ".join(t for t, h in chu_tu if h[0] >= truoc)))

    phu = np.zeros(cao_trang, dtype=bool)
    for _, _, hop, _ in dong:
        if hop:
            phu[hop[1] : hop[3]] = True
    dai = _doan_lien(den.any(axis=1) & ~phu)
    la_chu = [(s, e) for s, e in dai if e - s > toi_da]
    for s, e in dai:
        if e - s > toi_da:
            continue
        for a, b in _day_cham_anh(den, s, e, 0, rong, dpi):
            tren = [(h[3], i) for i, (_, _, h, _) in enumerate(dong) if h and h[3] <= s and h[0] < b and a < h[2]]
            if not tren:
                continue
            day_chu, i = max(tren)
            if any(day_chu <= cs and ce <= s for cs, ce in la_chu):
                continue
            _, _, h, _ = dong[i]
            _them(i, a, s, b, e, duoi_nhan[i], h[3] - h[1])
    return [tuple(c) for c in ket]


def _ocr_pdf(du_lieu: bytes) -> list[tuple]:
    """Rasterize từng trang rồi OCR. Cần `pdftoppm` của poppler.

    Mỗi dòng OCR mang `hop` (hộp TSV đổi ra điểm) và `cho_trong` (dãy chấm tìm
    trên ảnh XÁM của cùng trang, cùng DPI — `_cho_trong_trang`). Ảnh xám là một
    lượt `pdftoppm -gray` RIÊNG: ảnh PNG tesseract đọc giữ nguyên như trước, nên
    chữ OCR không đổi một byte; thiếu ảnh xám thì chỉ mất chỗ trống.
    """
    if not co_ocr() or not shutil.which("pdftoppm"):
        raise KhongDocDuoc(
            LoaiHong.khong_co_lop_chu,
            "tệp không có lớp chữ và máy chủ chưa đọc được bản scan",
        )
    ra: list[tuple] = []
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

        cac_anh = sorted(_P(thu_muc).glob("t-*.png"))
        xam = _cac_trang_pgm(_chay_cong_cu(["pdftoppm", "-r", str(_DPI_OCR), "-gray", "-"], du_lieu) or b"")
        pt = 72 / _DPI_OCR
        for so, anh in enumerate(cac_anh, start=1):
            dong = _tesseract(str(anh))
            cho: list[tuple[ChoTrong, ...]] = [()] * len(dong)
            if len(xam) == len(cac_anh):
                cho = _cho_trong_trang(xam[so - 1] < 160, dong, _DPI_OCR)
            for (chu, tin, hop, _), ct in zip(dong, cho, strict=True):
                them = {
                    **({"hop": _tron(tuple(v * pt for v in hop))} if hop else {}),
                    **({"cho_trong": ct} if ct else {}),
                }
                ra.append((so, chu, tin, them) if them else (so, chu, tin))
    return ra
