"""Parse cấu trúc Phần/Chương/Mục/Tiểu mục/Điều/Khoản/Điểm từ HTML của API MOJ.

Đọc class `prov-*`, KHÔNG regex tiếng Việt để nhận cấp. HTML phẳng: mọi <p> là
anh em ruột trong div.WordSection1, cấp bậc chỉ nằm ở tên class → duyệt tuần tự
+ stack.

Hai nguyên tắc gốc của module này (thay cho một họ special case):

1. **KHÔNG WHITELIST.** Mọi text node ngoài <table> đều thuộc về một provision.
   Thẻ có class `prov-<cấp>` mở node mới; MỌI text khác (prov-content, <p> không
   class, <div>/<em>/<strong> trơ) nối vào `noi_dung` của node đang mở. Bản cũ
   `continue` với thẻ không có `prov-*` và mất 113.121 ký tự / 21 văn bản — chủ
   yếu là Phụ lục và DANH MỤC của cụm Lao động (TT 09/2020: 64,4% tài liệu).

2. **GỘP TRƯỚC, ĐỌC LẠI SỐ HIỆU SAU.** MOJ tách tiêu đề một node thành nhiều thẻ
   cùng cấp theo ít nhất bốn cách khác nhau ("Chương I" + "NHỮNG QUY ĐỊNH CHUNG";
   "Điều 33." + "Bảo vệ quyền nhân thân"; "Tiểu mục 1" + "QUYỀN CHIẾM HỮU";
   "Chương " + "VIII QUYẾT ĐỊNH HÌNH PHẠT"). Vì số hiệu được đọc SAU khi ghép
   chuỗi, cả bốn đi qua cùng một nhánh — không cần biết thẻ nào bị tách kiểu nào.

`noi_dung` là TOÀN VĂN điều luật (nhãn + thân), `tieu_de` là nhãn ngắn. Đây là
trường verifier tầng 1 đối chiếu câu trích vào, nên nó không được rỗng ở cấp
trích dẫn được — bất biến `CITABLE` dưới đây raise nếu vi phạm.

Năm cạm bẫy HTML (spec 4.5), mỗi cái có test riêng:
  1. HTML phẳng          → stack theo Cap.bac
  2. prov-content KHÔNG có id → gắn vào node đỉnh stack, KHÔNG tạo node mới
  3. <br> dính chữ       → thay bằng ' ' TRƯỚC khi strip tag
  4. bảng bị bẹp         → parse <table> bằng đường riêng, loại khỏi luồng prov-*
  5. tiêu đề tách nhiều thẻ → nguyên tắc 2 ở trên

parse_provisions() là cổng NỘI DUNG (đo độ phủ token). parse_anomalies() là cổng
CẤU TRÚC bổ trợ — xem docstring của nó.
"""

import re
import unicodedata
import warnings

from bs4 import BeautifulSoup, CData, NavigableString, Tag

from src.models.domain import Cap, ProvisionRow

CLASS_TO_CAP = {
    "prov-part": Cap.phan,
    "prov-chapter": Cap.chuong,
    "prov-section": Cap.muc,
    # Đã đếm class thật trên cả 21 văn bản: prov-subsection có 43 lần. Thiếu nó
    # trong bảng này làm 22 Tiểu mục BLDS mất trắng (22/29 token thiếu ở Cổng A).
    "prov-subsection": Cap.tieu_muc,
    "prov-article": Cap.dieu,
    "prov-clause": Cap.khoan,
    "prov-item": Cap.diem,
}

# `hang_bang` là cấp DUY NHẤT có nhãn rỗng: nhãn của nó không phải một từ cố
# định mà là chữ của chính bảng ("Vùng I", "Bậc thuế 1"), nên nó nằm trọn trong
# `so_hieu_cap`. Xem `_nhan_hang`.
NHAN = {Cap.phan: "Phần", Cap.chuong: "Chương", Cap.muc: "Mục",
        Cap.tieu_muc: "Tiểu mục", Cap.dieu: "Điều", Cap.khoan: "Khoản",
        Cap.diem: "Điểm", Cap.hang_bang: "", Cap.phu_luc: "Phụ lục",
        Cap.mo_dau: "Mở đầu"}

# Cấp TRÍCH DẪN ĐƯỢC — nơi verifier tầng 1 đối chiếu câu trích vào văn bản.
# `noi_dung` rỗng ở đây nghĩa là phép kiểm "câu trích khớp nguyên văn" không có
# gì để đối chiếu: hoặc luôn thất bại (hệ thống ABSTAIN mọi câu hỏi), hoặc được
# viết cho "rỗng thì bỏ qua" và khi đó nó không kiểm gì cả. Nên nó là RAISE.
CITABLE = {Cap.dieu, Cap.khoan, Cap.diem, Cap.hang_bang}

# Phần/Chương/Mục/Tiểu mục là tiêu đề mục lục, không phải neo trích dẫn: Điều
# được đánh số duy nhất trong toàn văn bản nên duong_dan bỏ qua các tổ tiên này
# khi build path (vd. "45/2019/QH14 > Điều 25", không phải "... > Chương III >
# Điều 25"). Nhưng parent_local_id vẫn giữ nguyên cây thật (spec 4.4).
CONTAINER_CAPS = {Cap.phan, Cap.chuong, Cap.muc, Cap.tieu_muc}

# Cấp có NHÃN CHỮ xuất hiện trong text ("Phần"/"Chương"/"Mục"/"Tiểu mục"/"Điều").
# Khoản/Điểm không nằm ở đây vì nhãn của chúng KHÔNG phải chữ — với chúng SỐ HỌC
# LÀ NHÃN, nên `_la_tiep_noi_tieu_de` đọc dấu hiệu "không mở đầu bằng nhãn" từ
# chính việc không parse được số. Cùng một luật, hai cách đọc nhãn.
LABEL_LEVELS = {Cap.phan, Cap.chuong, Cap.muc, Cap.tieu_muc, Cap.dieu}

# Cấp phải có số hiệu vì nhãn của chúng LUÔN kèm số trong văn bản nguồn. Rỗng =
# node rác sẽ nhận nhầm con và làm duong_dan mất neo (Chương VIII của BLHS).
# `phan` không nằm ở đây: nó theo tiêu chí ĐẠT của brief (dieu/chuong/muc/tieu_muc).
# `phan` thêm 2026-09-01: `provisions_so_hieu_cap_check` (migration 005) đòi số
# hiệu ở MỌI cấp cấu trúc, nên cổng parser hẹp hơn cổng DB đúng một cấp — và
# chênh lệch đó chỉ lộ ra khi ingest ném CheckViolation và rollback cả lần nạp
# 23 văn bản. Cổng phải chặn ở chỗ biết được văn bản nào gây lỗi.
SO_HIEU_BAT_BUOC = {Cap.dieu, Cap.chuong, Cap.muc, Cap.tieu_muc, Cap.phan}

# Điều/Khoản dùng chung quy ước hậu tố chữ cho điều/khoản bổ sung (vd. "Điều 33a"
# của luật sửa đổi) — thiếu hậu tố này thì "Điều 33" và "Điều 33a" ra cùng
# duong_dan, tức false-positive verification: một claim trích Điều 33a sẽ được
# "kiểm chứng thành công" trên văn bản Điều 33. IGNORECASE để bắt "ĐIỀU 5" viết
# hoa toàn bộ (thiếu cờ này trước đây làm so_hieu="" → node rác nhận nhầm con).
RE_SO = {
    Cap.dieu: re.compile(r"^Điều\s+(\d+[a-zA-ZđĐ]*)", re.IGNORECASE),
    # Khoản: số rồi HOẶC dấu ./) HOẶC khoảng trắng.
    # Đã đo: BLTTDS (96115) có Khoản viết "1 Trường hợp..." không dấu phân cách.
    # An toàn vì regex này chỉ áp cho thẻ ĐÃ có class prov-clause — số dẫn đầu
    # trong một prov-clause gần như luôn là số hiệu Khoản.
    Cap.khoan: re.compile(r"^(\d+[a-zA-ZđĐ]*)(?:\s*[.)]|\s)", re.IGNORECASE),
    Cap.diem: re.compile(r"^([a-zăâđêôơư])\s*\)", re.IGNORECASE),
    Cap.chuong: re.compile(r"^Chương\s+([IVXLCDM\d]+)", re.IGNORECASE),
    # "Tiểu mục 1" KHÔNG khớp ^Mục nên hai regex không chồng nhau.
    Cap.tieu_muc: re.compile(r"^Tiểu\s+mục\s+([IVXLCDM\d]+)", re.IGNORECASE),
    Cap.muc: re.compile(r"^Mục\s+([IVXLCDM\d]+)", re.IGNORECASE),
    # "Phần thứ nhất" (BLDS 95942) ưu tiên trước "Phần I" — nhánh `thứ\s+\S+`
    # đứng trước nên khớp hết "thứ nhất", không cắt ở khoảng trắng đầu.
    Cap.phan: re.compile(r"^Phần\s+(thứ\s+\S+|\S+)", re.IGNORECASE),
}

# Bảng chữ cái Điểm của văn bản quy phạm Việt Nam. KHÔNG phải a–z: bỏ f/j/w/z,
# và `đ` đứng NGAY SAU `d` (không phải sau `e` như thứ tự ASCII). Đã xác nhận
# trên cả 49 văn bản: 23 nhãn phân biệt, không nhãn nào ngoài bảng này. Quét
# đứt quãng theo thứ tự ASCII cho 419 nhóm "có gap" — toàn bộ là dương tính giả
# vì `đ` U+0111 xếp sau `z`.
BANG_CHU_DIEM = ("a", "b", "c", "d", "đ", "e", "g", "h", "i", "k", "l", "m",
                 "n", "o", "p", "q", "r", "s", "t", "u", "v", "x", "y")

# Nhãn Khoản ở dạng CHẶT: số rồi BẮT BUỘC có `.` hoặc `)`. Hẹp hơn `RE_SO[khoan]`
# (vốn nhận cả `23 ` chỉ có khoảng trắng) và cố ý vậy — nó chỉ dùng để KẾT LUẬN
# "thẻ này bị gắn sai class", nên một mảnh tiếp nối mở đầu bằng số ("10 ngày kể
# từ…") không được phép bị đọc thành Khoản 10.
_RE_KHOAN_CHAT = re.compile(r"^\d+[a-zA-ZđĐ]*\s*[.)]")

# Chuẩn hoá CHỈ ĐỂ SO KHỚP, không đổi text lưu.
#   U+200B/U+FEFF: zero-width, vô hình nhưng làm hai chuỗi "khác nhau".
#   Ð U+00D0 (LATIN CAPITAL LETTER ETH) ≠ Đ U+0110 — đã có đúng 2 lần trong
#   96172. Nếu rơi vào đầu thẻ prov-article thì regex ^Điều không khớp, node ra
#   số rỗng và một Điều thật bị gộp mất.
_MAP_KHOA = str.maketrans({"​": "", "﻿": "",
                           "Ð": "Đ", "ð": "đ"})

# Cùng phép chuẩn hoá, nhưng GIỮ NGUYÊN ĐỘ DÀI: zero-width thành khoảng trắng
# thay vì bị xoá. `_tach_lien` cắt chuỗi GỐC theo offset tìm được trên chuỗi đã
# chuẩn hoá, nên một ký tự biến mất giữa chừng sẽ làm hai chuỗi lệch chỉ số và
# vết cắt trượt sang giữa từ.
_MAP_KHOA_GIU_DAI = str.maketrans({"​": " ", "﻿": " ",
                                   "Ð": "Đ", "ð": "đ"})


def _chuan_hoa(s: str) -> str:
    """Gộp khoảng trắng + NFC. Đây là dạng ĐƯỢC LƯU.

    NFC ở tầng lưu, không chỉ tầng so: corpus không thuần NFC (96117 tại offset
    33.642 ghi 'ư' U+01B0 + U+0323 thay vì 'ự' U+1EF1), còn BM25/tsvector và
    embedding coi 'ự' NFD ≠ NFC. IME tiếng Việt sinh NFC ⇒ truy vấn người dùng
    sẽ ÂM THẦM không khớp Bộ luật Hàng hải nếu chỉ chuẩn hoá lúc so sánh.

    NFC là mức ĐỦ VÀ KHÔNG QUÁ TAY: không casefold, không unaccent, không NFKC.
    Đã đo: casefold nâng độ phủ BLDS +0,63pp bằng cách CHE ~20 token thiếu thật.
    """
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", s)).strip()


def _dem(s: str) -> int:
    """Đếm ký tự khác khoảng trắng, sau NFC. Đơn vị của phép bảo toàn."""
    return len(re.sub(r"\s+", "", unicodedata.normalize("NFC", s)))


def _khoa(s: str) -> str:
    """Khoá so khớp (duong_dan, dò nhãn). Chỉ để so, KHÔNG lưu."""
    return _chuan_hoa(s).translate(_MAP_KHOA)


def _text(tag: Tag) -> str:
    """Bẫy #3: thay <br> bằng khoảng trắng TRƯỚC khi lấy text."""
    for br in tag.find_all("br"):
        br.replace_with(" ")
    return _chuan_hoa(tag.get_text())


def _sua_cap_theo_nhan(cap: Cap, tag: Tag) -> Cap:
    """Class của MOJ sai cấp thì tin CHỮ, không tin class.

    `124/2025/QH15` gắn `prov-part` cho "Chương I NHỮNG QUY ĐỊNH CHUNG" — đúng
    MỘT node, 9 Chương còn lại đều `prov-chapter`. Tin class thì node đó ra
    `cap=phan, so_hieu_cap=''`, vi phạm `provisions_so_hieu_cap_check`
    (migration 005) và làm ROLLBACK cả lần ingest — lỗi nổ ở tầng DB, cách xa
    văn bản gây ra nó.

    Chỉ áp cho cấp CHỨA (Phần/Chương/Mục/Tiểu mục): nhãn của chúng luôn là chữ
    có trong text nên đọc lại được. KHÔNG áp cho Điều/Khoản/Điểm —
    `_la_tiep_noi_tieu_de` đọc "regex trượt" làm dấu hiệu TIẾP NỐI tiêu đề, đổi
    cấp ở đó sẽ phá phép gộp. Và chỉ đổi khi regex của chính cấp đó trượt VÀ
    đúng MỘT cấp chứa khác khớp: mảnh tiêu đề tràn dòng ("TRONG GIÁO DỤC NGHỀ
    NGHIỆP") không khớp cấp nào nên không bị đụng.
    """
    if cap not in CONTAINER_CAPS:
        return cap
    text = _khoa(_text(tag))
    if RE_SO[cap].match(text):
        return cap
    khop = [c for c in CONTAINER_CAPS if c is not cap and RE_SO[c].match(text)]
    return khop[0] if len(khop) == 1 else cap


def _sua_cap_khoan_diem(cap: Cap, text: str) -> Cap:
    """`prov-clause`/`prov-item` gắn sai cấp thì tin NHÃN, không tin class.

    Đối xứng với `_sua_cap_theo_nhan`, nhưng cho hai cấp trích dẫn được — và với
    một điều kiện chặt hơn hẳn: chỉ đổi khi regex của cấp KIA khớp, tức thẻ có
    nhãn thật, chỉ sai tầng. Vì thế nó KHÔNG đụng vào nhánh
    `_la_tiep_noi_tieu_de`, vốn đọc "không parse được số hiệu NÀO" làm dấu hiệu
    tiếp nối: một mảnh tiếp nối không có nhãn nên không cấp nào khớp.

    Hai ca đo được trên 49 văn bản, cả hai đều làm MẤT một neo trích dẫn vì thẻ
    sai cấp không đọc được số hiệu rồi bị gộp vào anh em liền trước:
      - `88/2025/QH15`: "10. Bổ sung khoản 3 vào sau khoản 2 Điều 59 như sau:"
        mang class `prov-item` → cả Khoản 10 chui vào Điều 1 > Khoản 9 > Điểm c.
      - `13/2023/NĐ-CP`: "a) Biện pháp quản lý do tổ chức…" mang class
        `prov-clause` → Điểm a của Điều 26 Khoản 2 biến mất, dãy còn b…đ.
    """
    t = _khoa(text)
    if cap is Cap.diem and not RE_SO[Cap.diem].match(t) and _RE_KHOAN_CHAT.match(t):
        return Cap.khoan
    if cap is Cap.khoan and not RE_SO[Cap.khoan].match(t) and RE_SO[Cap.diem].match(t):
        return Cap.diem
    return cap


def _nhan_ke_tiep(cap: Cap, so: str) -> str | None:
    """Nhãn LIỀN SAU `so` trong dãy của cấp đó. None nếu `so` không đọc được."""
    if cap is Cap.diem:
        i = BANG_CHU_DIEM.index(so.lower()) if so.lower() in BANG_CHU_DIEM else -1
        return BANG_CHU_DIEM[i + 1] if 0 <= i < len(BANG_CHU_DIEM) - 1 else None
    if cap is Cap.khoan and so.isdigit():
        return str(int(so) + 1)
    return None


def _re_nuot(cap: Cap, nhan_sau: str) -> re.Pattern[str]:
    """Regex tìm nhãn `nhan_sau` NẰM GIỮA THÂN một điều khoản.

    Ba ràng buộc, mỗi cái loại một họ dương tính giả đã đo trên corpus:

    1. Đứng ngay sau `;` hoặc `.` + khoảng trắng. Loại mọi dẫn chiếu nội văn
       ("quy định tại khoản 3 Điều 6", "ngày 01 tháng 3 năm 2020", "60 tuổi 3
       tháng", ô bảng "| 3 |") — đó là 40+ ca trên corpus và là đúng cái lỗi
       NGƯỢC mà nới regex quá tay sẽ gây ra.
    2. KHÔNG nhận dấu mở ngoặc kép trước nhãn. Luật sửa đổi trích nguyên văn
       điều khoản mới trong “ ” ("Sửa đổi khoản 1 như sau: “c) Trường hợp…");
       nhãn trong đó thuộc luật KHÁC, không phải anh em ruột.
    3. Ký tự đầu của phần thân phải VIẾT HOA. Soạn thảo văn bản quy phạm luôn
       viết hoa sau nhãn Khoản/Điểm; một con số giữa câu thì không.

    Với Khoản, dấu `.`/`)` sau số là TÙY CHỌN: `93/2015/QH13 > Điều 55` viết
    "23 Đề nghị…" không có dấu chấm. Ràng buộc 1 và 3 gánh phần an toàn.
    """
    duoi = r"\s*\)" if cap is Cap.diem else r"\s*[.)]?"
    return re.compile(r"[;.]\s+(" + re.escape(nhan_sau) + r")" + duoi
                      + r"\s+(?=[A-ZĐÀ-Ỹ])")


def _tach_lien(cap: Cap, text: str) -> list[str]:
    """Một thẻ `prov-*` gói NHIỀU điều khoản → từng đoạn một.

    Đã đếm trên cả 49 văn bản: 6 thẻ (5 `prov-item`, 1 `prov-clause`) chứa cả
    điều khoản kế tiếp — có thẻ chứa tới ba — nên phép tách này khôi phục 11
    provision. Parser đọc cấp bậc từ class nên không tách được:
    cả điều khoản sau rơi vào `noi_dung` của điều khoản trước và KHÔNG tồn tại —
    không `id`, không `duong_dan`. Đó là chế độ hỏng nặng nhất của bảng tra: mô
    hình trích đúng nguyên văn Điểm d rồi dẫn Điểm c, và verifier tầng 1 BÁO ĐẠT
    vì câu trích nằm trong cây con của neo. Một trích dẫn sai nguồn được đóng
    dấu đã-kiểm-chứng.

    Tách lặp: `100/2015/QH13 > Điều 175 > Khoản 2` có `c) …; d) …; đ) …` trong
    một thẻ. Dấu `;`/`.` phân cách ở lại với đoạn TRƯỚC (nó là dấu câu của đoạn
    đó); chỉ khoảng trắng bị bỏ, nên phép BẢO TOÀN KÝ TỰ của `parse_anomalies`
    vẫn khít tuyệt đối.
    """
    if cap not in (Cap.khoan, Cap.diem):
        return [text]
    doan: list[str] = []
    con_lai = text
    while (nhan_sau := _nhan_ke_tiep(cap, _so_hieu(cap, con_lai))) is not None:
        m = _re_nuot(cap, nhan_sau).search(con_lai.translate(_MAP_KHOA_GIU_DAI))
        if m is None or m.start() == 0:
            break
        doan.append(con_lai[:m.start() + 1])
        con_lai = con_lai[m.start(1):]
    doan.append(con_lai)
    return doan


def _trong_trich_dan(s: str) -> bool:
    """Cuối chuỗi `s` có đang nằm TRONG một đoạn trích dẫn chưa đóng?

    Đây là phép phân biệt DUY NHẤT tách "điều khoản bị nuốt" khỏi "luật sửa đổi
    chép nguyên văn điều khoản mới của luật khác". Cả hai đều là một nhãn
    Khoản/Điểm nằm trong thân của một điều khoản; khác nhau ở chỗ nhãn thứ hai
    thuộc VĂN BẢN KHÁC nên nó KHÔNG phải anh em ruột và tách nó ra là dựng một
    neo trích dẫn không có thật.

    Bốn ca đo được, tất cả đều mở bằng “ và đóng bằng ”:
    `31/2024/QH15 > Điều 248 > Khoản 6/7/8 > Điểm b` (chép khoản 2 và khoản 5
    Luật Lâm nghiệp) và `88/2025/QH15 > Điều 1 > Khoản 25 > Điểm c` (chép khoản
    4 Điều 125 Luật XLVPHC). Nếu chỉ lọc bằng "anh em cùng nhãn đã tồn tại" —
    phép lọc của vòng thẩm định — bốn ca này lọt, vì luật sửa đổi thường chỉ
    trích MỘT điểm nên anh em thật không tồn tại.

    Ngoặc kép thẳng `"` không phân biệt mở/đóng nên đếm theo tính chẵn lẻ.
    """
    sau = 0
    thang = False
    for ch in s:
        if ch == "\u201c":
            sau += 1
        elif ch == "\u201d":
            sau = max(0, sau - 1)
        elif ch == '"':
            thang = not thang
    return sau > 0 or thang


def _la_dieu_khoan_bi_nuot(cap: Cap, da_co: str, text: str,
                           co_con_khoan: bool = False) -> Cap | None:
    """Khối `prov-content` này thật ra là điều khoản KẾ TIẾP, không phải thân?

    Trả về CẤP của điều khoản bị nuốt, hoặc None nếu đây đúng là thân.

    MOJ gắn `prov-content` (= "thân của node đang mở") cho một số thẻ vốn là
    Khoản/Điểm thật. Parser tin class nên nối chúng vào `noi_dung` của anh em
    liền trước và điều khoản đó BIẾN MẤT khỏi bảng tra — không `id`, không
    `duong_dan`, nhưng nguyên văn vẫn nằm trong cây con của một neo khác. Đó là
    dạng hỏng tệ nhất: verifier tầng 1 báo ĐẠT cho một trích dẫn sai nguồn.

    Ba ràng buộc, không nới cái nào:
      1. Node đang mở phải là Khoản/Điểm — chỉ hai cấp này có dãy nhãn đọc được.
      2. `text` phải MỞ ĐẦU bằng đúng nhãn LIỀN SAU nhãn của node đang mở. Không
         phải "một nhãn bất kỳ": một khối thân bắt đầu bằng "10 ngày kể từ…" chỉ
         bị đọc là Khoản 10 khi node đang mở là Khoản 9.
      3. Chỗ nối KHÔNG được nằm trong một đoạn trích dẫn đang mở (xem
         `_trong_trich_dan`).

    Node đang mở là ĐIỀU là ca riêng của ràng buộc 2: Điều chưa có Khoản nào thì
    nhãn liền sau nó là "Khoản 1". Hai ca đo được — `84/2015/QH13 > Điều 33` và
    `91/2015/QH13 > Điều 490` — gắn `prov-content` cho Khoản 1 ngay dưới dòng
    tiêu đề, nên Khoản 1 mất neo VÀ mọi Điểm của nó bị treo thẳng vào Điều. Đòi
    "chưa có Khoản nào" chứ không phải "nhãn kế tiếp": một Điều đã có Khoản 1..n
    thì khối thân mở đầu bằng số là văn xuôi, không phải Khoản n+1 lạc chỗ.
    """
    if cap is Cap.dieu:
        if co_con_khoan:
            return None
        cap_moi, nhan_sau = Cap.khoan, "1"
    elif cap in (Cap.khoan, Cap.diem):
        cap_moi = cap
        nhan_sau = _nhan_ke_tiep(cap, _so_hieu(cap, da_co))
        if nhan_sau is None:
            return None
    else:
        return None
    t = _khoa(text)
    if _so_hieu(cap_moi, t) != nhan_sau:
        return None
    # Khoản: đòi dấu `.`/`)` sau số. Biến thể chỉ có khoảng trắng ("23 Đề nghị")
    # là thật, nhưng ở ĐẦU một thẻ prov-content nó không phân biệt được với một
    # đoạn thân mở đầu bằng số, nên ở vị trí này quy tắc chặt hơn ở `_tach_lien`
    # (nơi còn có dấu `;`/`.` phía trước làm chứng).
    if cap_moi is Cap.khoan and not _RE_KHOAN_CHAT.match(t):
        return None
    return None if _trong_trich_dan(da_co) else cap_moi


def _cap_of(tag: Tag) -> Cap | None:
    for cls in tag.get("class") or []:
        if cls in CLASS_TO_CAP:
            cap = CLASS_TO_CAP[cls]
            if cap in (Cap.khoan, Cap.diem):
                return _sua_cap_khoan_diem(cap, _text(tag))
            return _sua_cap_theo_nhan(cap, tag)
    return None


def _so_hieu(cap: Cap, text: str) -> str:
    m = RE_SO.get(cap)
    if m is None:
        return ""
    hit = m.match(_khoa(text))
    return hit.group(1) if hit else ""


def _la_tiep_noi_tieu_de(text: str, cap: Cap, so: str) -> bool:
    """Thẻ này là phần TIẾP NỐI tiêu đề của node trước, không phải node mới?

    Dấu hiệu: không parse được số hiệu VÀ text không mở đầu bằng nhãn của cấp.
    Một node THẬT luôn mở đầu bằng nhãn ("Điều 33a", "ĐIỀU 5", "Chương ") dù số
    hiệu lạ hoặc thiếu.

    Đã đo: BLLĐ Chương I tách 2 thẻ CÙNG id; BLDS/BLHS/BLTTDS/BLTTHS có 75 thẻ
    prov-article tách tiêu đề với id KHÁC nhau; BLDS có 22 thẻ prov-subsection
    tách "Tiểu mục N" khỏi tên; BLHS có "Chương " trơ. Một quy tắc phủ cả bốn.
    """
    if so:
        return False
    if cap in LABEL_LEVELS:
        return not _khoa(text).lower().startswith(NHAN[cap].lower())
    # Khoản/Điểm: SỐ HỌC LÀ NHÃN, nên "không parse được số" CHÍNH LÀ dấu hiệu
    # "không mở đầu bằng nhãn" ở trên — cùng một luật, không phải ca riêng thứ
    # sáu. Không gộp thì Khoản cha bị CẮT CỤT (đoạn hai của nó đi sang một node
    # khác) và một trích dẫn ĐÚNG vào khoản đó thất bại ở tầng 1: hệ thống
    # ABSTAIN một câu trả lời đúng. An toàn vì `RE_SO[khoan]` nhận cả số chỉ có
    # khoảng trắng phân cách ("1 Trường hợp…"), nên Khoản có số thật gần như
    # không thể lọt xuống nhánh này — và số mảnh đã gộp được WARN lúc build.
    return cap in (Cap.khoan, Cap.diem)


def _don_vi(node: Tag):
    """Duyệt cây theo thứ tự văn bản, yield MỌI text node — không whitelist.

    Yield `(cap, text, tag)`, ba dạng phân biệt được bằng chính hai trường đó:
      - `cap` có giá trị            → thẻ mở node mới (class prov-<cấp>)
      - `cap` None, `tag` có giá trị → thẻ `prov-content`: thân của node đang mở,
                                       MOJ đánh dấu tường minh nên KHÔNG mồ côi
      - `cap` None, `tag` None       → text MỒ CÔI: không có tổ tiên `prov-*` nào

    Phân biệt dạng 2 và dạng 3 là điều kiện để tách chữ mồ côi theo vị trí:
    `prov-content` đứng sau thẻ `prov-<cấp>` cuối cùng vẫn là thân của Điều đó
    (vd. Điều 26 BLLĐ), không phải nội dung đuôi.

    KHÔNG đi sâu vào thẻ đã có class prov-* : lấy nguyên text của nó một lần.
    Đã kiểm trên cả 21 văn bản: không có prov-* nào lồng trong prov-* (0 ca).
    """
    for child in node.children:
        if isinstance(child, NavigableString):
            # `type(...) in` chứ KHÔNG `isinstance`: Doctype/Comment/Stylesheet/
            # Script đều là lớp CON của NavigableString, và `soup.get_text()` —
            # vế NGUỒN của phép BẢO TOÀN KÝ TỰ ở `parse_anomalies` — bỏ đúng bốn
            # lớp đó. `isinstance` nhặt chúng, nên hai vế lệch nhau.
            # Ca thật: MOJ trả `88/2025/QH15` (178737) dưới dạng TRANG HTML đầy
            # đủ (`<!DOCTYPE html><head><style>…`) chứ không phải mảnh
            # `<div class="WordSection1">` như 22 văn bản trước. CSS trong
            # `<style>` (79 ký tự) cộng chuỗi "html" của Doctype (4) đi thẳng vào
            # `noi_dung` của bản ghi `mo_dau` và làm cổng bảo toàn báo lệch -83.
            # CSS không phải văn bản quy phạm; để nó trong `noi_dung` là mở một
            # neo cho câu trích lấy từ markup.
            if type(child) not in (NavigableString, CData):
                continue
            t = _chuan_hoa(str(child))
            if t:
                yield None, t, None
        elif isinstance(child, Tag):
            cap = _cap_of(child)
            if cap is not None:
                # 337/2025/NĐ-CP có một `<p class="prov-clause"></p>` trống trơn.
                # Thẻ không có chữ không phải một provision: nó chỉ tạo node có
                # noi_dung rỗng và duong_dan mất số hiệu. Không chữ = không mất gì.
                t = _text(child)
                if t:
                    # Một thẻ có thể gói NHIỀU điều khoản (xem `_tach_lien`).
                    # `tag` chỉ đi kèm đoạn ĐẦU: các đoạn sau không có node
                    # tương ứng trong nguồn nên `source_node_id` của chúng phải
                    # là None — bịa lại id của thẻ cha sẽ làm hai provision
                    # khác nhau cùng trỏ về một node HTML.
                    for k, doan in enumerate(_tach_lien(cap, t)):
                        yield cap, doan, (child if k == 0 else None)
            elif child.name == "table":
                # Bẫy #4: KHÔNG đi sâu vào bảng — ô của nó không phải prov-content
                # rời. Yield chính thẻ để `parse_provisions` biết VỊ TRÍ của bảng
                # trong văn bản, thứ quyết định bảng thuộc về provision nào.
                yield None, "", child
            elif "prov-content" in (child.get("class") or []):
                # CÙNG guard `if t:` như nhánh trên, vì cùng một lý do đo bằng
                # vị trí: mốc `cuoi` của parse_provisions tính theo thẻ MANG
                # class prov-*, nên một `<p class="prov-content"></p>` rỗng ở
                # cuối trang đẩy mốc VƯỢT QUA Phụ lục, `duoi` thành rỗng, và
                # toàn bộ chữ đuôi sập lại vào provision đang mở — đúng bug
                # 42.636 ký tự đã chữa ở 1ddf020. Thẻ không có chữ không mang
                # thông tin vị trí; MOJ đã ship thẻ prov-* trống trơn thật.
                t = _text(child)
                if t:
                    yield None, t, child
            else:
                yield from _don_vi(child)


def _duong_dan(i: int, caps: list[Cap], so_hieu: list[str],
               parents: list[int | None], so_ky_hieu: str) -> str:
    """Đường dẫn canonical, đi ngược cây thật qua `parents`.

    Cấp trích dẫn được (dieu/khoan/diem): BỎ container, theo công ước dẫn chiếu
    pháp lý Việt Nam — "khoản 2 Điều 25", không ai viết "Chương III Điều 25".

    Cấp container đang xét: GIỮ đủ chuỗi container, vì tự thân nó (vd. "Mục 1")
    không duy nhất — BLLĐ có 6 "Mục 1" ở 6 Chương khác nhau, BLDS có nhiều
    "Tiểu mục 1". Nhờ vậy duong_dan duy nhất trên TOÀN BỘ provision.
    """
    bo_container = caps[i] not in CONTAINER_CAPS
    segments: list[str] = []
    j: int | None = i
    while j is not None:
        if j == i or not (bo_container and caps[j] in CONTAINER_CAPS):
            # `.strip()` chứ không `.rstrip()`: `hang_bang` có nhãn RỖNG nên
            # `f"{''} {'Vùng I'}"` để lại khoảng trắng ở ĐẦU, và một đường dẫn
            # `"… >  Vùng I"` hai khoảng trắng là một neo khác với neo đúng.
            segments.append(f"{NHAN[caps[j]]} {so_hieu[j]}".strip())
        j = parents[j]
    segments.reverse()
    return " > ".join([so_ky_hieu, *segments])


def _la_bang(tag: Tag | None) -> bool:
    return tag is not None and tag.name == "table"


def _bang_md(tbl: Tag) -> str:
    """Một <table> → một markdown table. Rỗng nếu bảng không có ô nào.

    Đã kiểm trên cả 21 văn bản: 133 <table>, 0 lồng nhau — nên `find_all("tr")`
    không thể nhặt phải hàng của một bảng con.
    """
    lines: list[str] = []
    for tr in tbl.find_all("tr"):
        cells = [_text(td) for td in tr.find_all(["td", "th"])]
        if cells:
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _o(dong: str) -> list[str]:
    """Một dòng markdown `| a | b | c |` → `["a", "b", "c"]`."""
    return [c.strip() for c in dong.strip().strip("|").split("|")]


def _nhan_hang(tieu_de_cot1: str, o1: str) -> str:
    """Nhãn của một hàng bảng, ghép TỪ CHÍNH BẢNG — không đặt hộ ký hiệu nào.

    Ô cột 1 một mình không phải lúc nào cũng đọc được như một neo: bảng lương
    ghi `Vùng I` (tự mô tả), bảng thuế ghi `1` (một chữ số trơ, không phân biệt
    được với Khoản 1 hay Điểm 1 trong cùng đường dẫn). Nên nhãn = TIÊU ĐỀ CỘT 1
    + ô, và bỏ tiêu đề khi ô đã mở đầu bằng chính nó:

      | Vùng     | … |  +  | Vùng I | … |  →  "Vùng I"      (không "Vùng Vùng I")
      | Bậc thuế | … |  +  | 1      | … |  →  "Bậc thuế 1"

    Cả hai vế đều là chữ nguồn tự in ra. "Bậc thuế 1" cũng đúng cách người Việt
    dẫn biểu thuế luỹ tiến trên thực tế.
    """
    if not tieu_de_cot1 or _khoa(o1).lower().startswith(_khoa(tieu_de_cot1).lower()):
        return o1
    return f"{tieu_de_cot1} {o1}"


def _tach_bang(md: str) -> tuple[str, list[tuple[str, str]]] | None:
    """Bảng markdown → `(hàng tiêu đề, [(nhãn, hàng dữ liệu)…])`, hoặc None.

    None = bảng KHÔNG tách được, để nguyên trong `noi_dung` của Khoản cha. Bốn
    điều kiện, mỗi cái loại một hình dạng đã đo trên corpus — và đây là chỗ
    "thà 2 bảng đúng còn hơn 6 bảng có 4 bảng méo" được thi hành:

    1. **≥ 3 hàng** (tiêu đề + ít nhất 2 hàng dữ liệu). Bảng một hàng dữ liệu
       không phải một liệt kê: không có anh em nào để phép so tập con đối chiếu,
       nên tách nó chỉ thêm một tầng cây mà không chặn được sai nào.
       (`31/2024/QH15 > Điều 243 > Khoản 4`: đúng 1 hàng, sửa Phụ lục luật khác.)
    2. **Mọi hàng cùng số ô.** `135/2020/NĐ-CP > Điều 4/5 > Khoản 2` có hàng đầu
       2 ô (`| Lao động nam | Lao động nữ |`) rồi 16 hàng 4 ô — tiêu đề hai
       tầng, ô gộp đã mất khi sang markdown.
    3. **Ô cột 1 của mọi hàng dữ liệu khác rỗng.** Cùng hai bảng đó: 7 hàng cuối
       có cột 1 rỗng vì ô gộp bị bẹp — tách ra sẽ ra 7 neo `so_hieu_cap` rỗng,
       thứ `provisions_so_hieu_cap_check` chặn, và một neo `"… > Khoản 2 > "`
       không tra được.
    4. **Nhãn không trùng nhau.** Neo trích dẫn trùng = một claim sai được
       "kiểm chứng thành công" trên hàng kia.

    Hàng TIÊU ĐỀ không thành neo: nó là nhãn cột, không phải văn bản quy phạm.
    Nó ở lại `noi_dung` của Khoản cha — nếu bỏ hẳn thì tên cột biến mất và không
    ai (kể cả FE) dựng lại được cái bảng.
    """
    dong = [d for d in md.split("\n") if d.strip().startswith("|")]
    if len(dong) < 3:
        return None
    o = [_o(d) for d in dong]
    if len({len(x) for x in o}) != 1:
        return None
    tieu_de_cot1 = o[0][0]
    nhan = [_nhan_hang(tieu_de_cot1, x[0]) for x in o[1:]]
    if not all(nhan) or len(set(nhan)) != len(nhan):
        return None
    return dong[0], list(zip(nhan, dong[1:], strict=True))


def parse_tables(html: str) -> list[str]:
    """Bẫy #4: parse <table> riêng, mỗi bảng thành một markdown table.

    HÀM THUẦN, và cũng là nguồn markdown DUY NHẤT của `parse_provisions` (qua
    `_bang_md`). Trước Plan 2 nó không có caller nào ngoài test của chính nó:
    `parse_provisions` gọi `decompose()` nên mọi bảng ra khỏi cây và biến mất
    khỏi corpus — xem docstring `parse_provisions`.
    """
    soup = BeautifulSoup(html, "html.parser")
    return [md for tbl in soup.find_all("table") if (md := _bang_md(tbl))]


def _noi_dung(nhan: str, than: list[str], bang: list[tuple[int, str]]) -> str:
    """Văn xuôi và bảng theo ĐÚNG thứ tự nguồn, phân tách bằng dòng trống.

    `bang` là `(vị trí, markdown)`: bảng đứng trước `than[vị trí]`. Văn xuôi sau
    một bảng ở lại sau bảng đó — dồn nó lên trước sinh ra câu không có trong
    nguồn ("Phương pháp tính thuế: Trong đó: …", 41 điều khoản đo 2026-09-29).
    Bảng đứng sau mọi văn xuôi (ca thường) cho đúng chuỗi của bản cũ.

    `_chuan_hoa` chạy trên TỪNG đoạn văn xuôi, không trên chuỗi đã ghép: nó gộp
    MỌI khoảng trắng (kể cả xuống dòng) nên sẽ bẹp bảng thành một dòng
    `| a | b | | c | d |`. Từng Ô đã đi qua `_text()` nên phần bảng vẫn ở dạng
    ĐƯỢC LƯU (NFC, gộp khoảng trắng trong ô).

    Nhãn luôn mở đầu đoạn văn xuôi đầu tiên: bất biến "neo trích dẫn mở đầu bằng
    nhãn của chính nó" (ruling C1) đọc ký tự đầu của `noi_dung`.
    """
    khoi, dau, van = [], 0, [nhan]
    for vi_tri, md in bang:
        khoi += [_chuan_hoa(" ".join([*van, *than[dau:vi_tri]])), md]
        dau, van = vi_tri, []
    khoi.append(_chuan_hoa(" ".join([*van, *than[dau:]])))
    return "\n\n".join(x for x in khoi if x)


def _thu_tu_nhan(cap: Cap, so: str) -> int | None:
    """Vị trí của nhãn `so` trong dãy của cấp đó (0-based). None nếu không đọc được."""
    if cap is Cap.diem:
        return BANG_CHU_DIEM.index(so.lower()) if so.lower() in BANG_CHU_DIEM else None
    return int(so) - 1 if cap is Cap.khoan and so.isdigit() else None


def _do_nuot_anh_em(rows: list[ProvisionRow]) -> list[str]:
    """Điều khoản KẾ TIẾP còn nằm trong `noi_dung` của anh em liền trước?

    Đây là cổng cho đúng chế độ hỏng mà `_tach_lien`,
    `_la_dieu_khoan_bi_nuot` và `_sua_cap_khoan_diem` vừa chữa: điều khoản bị
    nuốt KHÔNG tồn tại (không `id`, không `duong_dan`) nhưng nguyên văn của nó
    vẫn nằm trong cây con của một neo khác, nên verifier tầng 1 báo ĐẠT cho một
    trích dẫn SAI NGUỒN. Cổng nội dung (bảo toàn ký tự) mù với nó — không ký tự
    nào mất, chúng chỉ bị gán sai neo.

    LỖI chứ không phải cảnh báo, và chạy TRƯỚC khi ghi seed: cả ba cơ chế trên
    đọc hình dạng của nguồn, nên lần MOJ đổi hình dạng lần nữa thì đây là chỗ
    duy nhất biết được — im lặng ở đây là ship lại đúng lỗi cũ.

    Hai phép lọc dương tính giả, cả hai đều cần (đo trên 49 văn bản):
      - nhãn kế tiếp ĐÃ tồn tại như anh em ruột → thân chỉ đang dẫn chiếu;
      - chỗ nối nằm trong một trích dẫn chưa đóng → luật sửa đổi chép nguyên văn
        điều khoản của luật khác (4 ca; xem `_trong_trich_dan`).
    """
    anh_em: dict[tuple[int | None, Cap], set[str]] = {}
    for r in rows:
        anh_em.setdefault((r.parent_local_id, r.cap), set()).add(r.so_hieu_cap.lower())

    loi: list[str] = []
    for r in rows:
        if r.cap not in (Cap.khoan, Cap.diem):
            continue
        nhan_sau = _nhan_ke_tiep(r.cap, r.so_hieu_cap)
        if nhan_sau is None or nhan_sau in anh_em[(r.parent_local_id, r.cap)]:
            continue
        m = _re_nuot(r.cap, nhan_sau).search(r.noi_dung.translate(_MAP_KHOA_GIU_DAI))
        if m is None or m.start() == 0 or _trong_trich_dan(r.noi_dung[:m.start()]):
            continue
        loi.append(
            f"NUỐT ANH EM: {r.duong_dan!r} chứa nguyên văn {NHAN[r.cap]} "
            f"{nhan_sau} trong thân — điều khoản đó không có neo trích dẫn riêng "
            f"nên một câu trích của nó sẽ 'kiểm chứng thành công' trên neo này: "
            f"…{r.noi_dung[max(0, m.start() - 30):m.start() + 40]!r}")
    return loi


def _do_dut_quang(rows: list[ProvisionRow]) -> list[str]:
    """Dãy nhãn anh em có lỗ hổng — điều khoản mất HẲN nhãn.

    Bổ trợ cho `_do_nuot_anh_em`, vốn chỉ thấy được ca mà nhãn kế tiếp CÒN nguyên
    trong thân. Khi nhãn mất luôn (nguồn không ship nó), dấu vết duy nhất là lỗ
    trong dãy `a b c d đ e g h …` hoặc `1 2 3 …`.

    CẢNH BÁO chứ không phải lỗi: đã đo `100/2015/QH13 > Điều 278 > Khoản 2` —
    HTML nguồn nhảy thẳng từ `d)` sang `e)`, không thẻ nào chứa Điểm đ. Parser
    không dựng lại được thứ nguồn không có, và raise ở đây sẽ chặn vĩnh viễn cả
    Bộ luật Hình sự vì một khiếm khuyết của MOJ.
    """
    nhom: dict[tuple[int | None, Cap], list[str]] = {}
    for r in rows:
        if r.cap in (Cap.khoan, Cap.diem):
            nhom.setdefault((r.parent_local_id, r.cap), []).append(r.so_hieu_cap)

    duong_dan = {r.local_id: r.duong_dan for r in rows}
    canh_bao: list[str] = []
    for (cha, cap), nhan_list in nhom.items():
        thu_tu = sorted(t for t in (_thu_tu_nhan(cap, n) for n in nhan_list) if t is not None)
        if len(thu_tu) < 2:
            continue
        thieu = [t for t in range(0, thu_tu[-1] + 1) if t not in set(thu_tu)]
        if not thieu:
            continue
        ten = [BANG_CHU_DIEM[t] if cap is Cap.diem else str(t + 1) for t in thieu]
        canh_bao.append(
            f"ĐỨT DÃY {NHAN[cap]} trong {duong_dan.get(cha, '<gốc>')!r}: thiếu "
            f"{ten} (có {sorted(nhan_list)})")
    return canh_bao


def _do_bang_ket(rows: list[ProvisionRow]) -> list[str]:
    """Neo trích dẫn giữ nguyên một BẢNG NHIỀU HÀNG mà không có con nào.

    Kho phân rã mọi liệt kê thành dòng con — 17.160 Khoản, 13.725 Điểm. Đúng 13
    neo trích dẫn thoát khỏi quy tắc đó, và cả 13 vì cùng một lý do: liệt kê của
    chúng được nguồn dàn trang bằng `<table>` nên nó nằm gọn trong `noi_dung`
    của MỘT dòng thay vì thành các dòng anh em.

    Hậu quả đã đo (`trace_id` cbd9f317): mô hình trích hai trong bốn hàng của
    bảng lương tối thiểu vùng rồi kết luận "pháp luật quy định HAI mức lương tối
    thiểu tháng". Mọi trích dẫn đều đúng nguyên văn nên cả bảy phép kiểm đi qua
    sạch — phép so tập con không có gì để so, vì hai citation trỏ cùng một
    `khop_tai_id` chứ không phải hai hàng anh em.

    Từ 2026-09-02, bảng ĐỦ SẠCH được `_tach_bang` tách thành các dòng
    `hang_bang` con, nên chúng không còn rơi vào đây. Cảnh báo này giờ chỉ còn
    kể tên những bảng `_tach_bang` TỪ CHỐI tách — và đó là mục đích của nó: giữ
    chúng ở trạng thái ĐỂ NGUYÊN CÓ CHỦ ĐÍCH thay vì bị bỏ sót im lặng. Bốn điều
    kiện từ chối nằm ở docstring `_tach_bang`; ép tách một bảng méo sẽ đẻ ra neo
    `so_hieu_cap` rỗng hoặc trùng, tệ hơn hẳn việc để nguyên.
    """
    co_con = {r.parent_local_id for r in rows}
    canh_bao: list[str] = []
    for r in rows:
        if r.cap not in CITABLE or r.local_id in co_con:
            continue
        hang = [d for d in r.noi_dung.split("\n") if d.lstrip().startswith("|")]
        if len(hang) > 1:
            canh_bao.append(
                f"BẢNG KẸT trong neo {r.duong_dan!r}: {len(hang)} hàng nằm trong "
                f"noi_dung của MỘT provision, không có dòng con nào — một câu trả "
                f"lời trích được vài hàng vẫn qua sạch mọi phép kiểm. "
                f"`_tach_bang` từ chối tách: {_vi_sao_khong_tach(hang)}.")
    return canh_bao


def _vi_sao_khong_tach(hang: list[str]) -> str:
    """Câu ngắn nói vì sao `_tach_bang` trả None — để cảnh báo tự giải thích."""
    if len(hang) < 3:
        return "chỉ 1 hàng dữ liệu, không phải một liệt kê"
    o = [_o(d) for d in hang]
    if len({len(x) for x in o}) != 1:
        return f"số ô không đều ({sorted({len(x) for x in o})}), tiêu đề nhiều tầng"
    nhan = [_nhan_hang(o[0][0], x[0]) for x in o[1:]]
    if not all(nhan):
        return f"{sum(1 for n in nhan if not n)} hàng có ô cột 1 RỖNG (ô gộp bị bẹp)"
    if len(set(nhan)) != len(nhan):
        return "nhãn hàng TRÙNG nhau"
    return "không rõ"


def parse_anomalies(html: str, so_ky_hieu: str = "?") -> tuple[list[str], list[str]]:
    """Cổng CẤU TRÚC: đường mất dữ liệu mà cổng nội dung (token) không thấy.

    Sau khi bỏ whitelist, hai trong ba đường cũ thành KHÔNG THỂ XẢY RA thay vì
    "phát hiện được":
      - text ngoài mọi thẻ prov-* → nay nối vào node đang mở
      - prov-content trước mọi node ("Căn cứ Hiến pháp…") → nay nối vào node đầu
    Hàm này vì thế không đi tìm chúng nữa; nó ASSERT LẠI bằng phép BẢO TOÀN
    token — mất bất kỳ token nào của HTML đã strip tag là lỗi, không ngưỡng.

    Đường thứ ba vẫn thật: `<p class="prov-*">` nằm TRONG `<table>`. Bảng thuộc
    Plan 2, parse_provisions decompose() nó, nên mọi thứ trong bảng ra khỏi cây.
    Chỉ cấp TRÍCH DẪN ĐƯỢC ở đó là lỗi CHẶN (mất một neo trích dẫn); container
    trong bảng là artefact dàn trang Công báo (BLHS có 9 ca: "Phần thứ hai"/
    "Mục 3" lặp ở đầu trang tiếp) — WARN, không chặn build.

    Trả về `(loi, canh_bao)`. `loi` rỗng = build đi tiếp.
    """
    soup = BeautifulSoup(html, "html.parser")
    loi: list[str] = []
    canh_bao: list[str] = []

    for tbl in soup.find_all("table"):
        for p in tbl.find_all("p"):
            cap = _cap_of(p)
            if cap is None:
                continue
            mo_ta = (f"cấp {cap.value} trong <table> sẽ ra khỏi cây provision: "
                     f"class={p.get('class')} id={p.get('id')} text={_text(p)[:60]!r}")
            (loi if cap in CITABLE else canh_bao).append(mo_ta)

    # BẢO TOÀN KÝ TỰ. Đếm ký tự khác khoảng trắng, nên phép so không phụ thuộc
    # quy ước chèn dấu cách giữa các thẻ inline (<sup>/<b>/<a>) — thứ làm phép so
    # theo token báo lệch giả ở dấu câu và công thức "L[T(N)]".
    # So với `noi_dung` THÔI (không cộng `tieu_de`): mỗi đơn vị text đi vào đúng
    # MỘT `noi_dung`, nên đẳng thức phải khít tuyệt đối, không ngưỡng. Lệch ⇒ có
    # đơn vị bị bỏ (whitelist quay lại, `if stack:` không có else, thẻ bị skip).
    # `soup` ở đây KHÔNG còn decompose bảng: từ Plan 2 chữ trong <table> đi vào
    # `noi_dung`, nên nó phải nằm ở CẢ HAI vế — bỏ nó ở vế nguồn thì phép so
    # báo thừa, và cách sửa dễ dãi là nới đẳng thức thành ngưỡng.
    # Chỉ `|` bị loại khỏi hai vế: đó là ký tự DUY NHẤT `_bang_md` thêm vào mà
    # nguồn không có (khoảng trắng thì `_dem` đã bỏ). Đã đếm trên cả 21 văn bản:
    # `soup.get_text()` có ĐÚNG 0 ký tự `|`, nên phép loại này không che được
    # mất mát nào có thật.
    rows = parse_provisions(html, so_ky_hieu)
    goc = _dem(soup.get_text().replace("|", ""))
    trong_rows = sum(_dem(r.noi_dung.replace("|", "")) for r in rows)
    if goc != trong_rows:
        loi.append(f"KHÔNG BẢO TOÀN: HTML có {goc} ký tự, provisions.noi_dung giữ "
                   f"{trong_rows} — lệch {goc - trong_rows}")

    loi.extend(_do_nuot_anh_em(rows))
    canh_bao.extend(_do_dut_quang(rows))
    canh_bao.extend(_do_bang_ket(rows))

    return loi, canh_bao


def parse_provisions(html: str, so_ky_hieu: str) -> list[ProvisionRow]:
    soup = BeautifulSoup(html, "html.parser")

    # ── Pha 1: gom khối theo thứ tự văn bản ────────────────────────────────
    # `nhan[i]` = text của (các) thẻ nhãn đã GỘP; `than[i]` = mọi text nối theo.
    # Số hiệu đọc SAU pha này, từ chuỗi đã ghép — đó là cả mục D.
    caps: list[Cap] = []
    nhan: list[str] = []
    than: list[list[str]] = []
    # (vị trí trong `than`, markdown) của <table> nằm TRONG node này
    bang: list[list[tuple[int, str]]] = []
    src: list[str | None] = []
    parents: list[int | None] = []
    stack: list[int] = []
    mo_dau: list[str] = []  # text xuất hiện TRƯỚC node đầu tiên
    bang_mo_dau: list[str] = []

    # TÁCH CHỮ MỒ CÔI THEO VỊ TRÍ. Đã đo phân bố so với thẻ prov-* CUỐI CÙNG:
    # 152668 có 42.636 ký tự ở đuôi / 647 xen giữa; 152670 25.316/560; 134611
    # 21.296/653 — 97–98% ở đuôi. Ranh giới là thật, không trùng hợp.
    #   trước thẻ prov-* đầu = lời mở đầu (tiêu ngữ, tên văn bản, "Căn cứ …") →
    #     MỘT bản ghi `mo_dau` cho mỗi văn bản, cũng KHÔNG trích dẫn được
    #   xen giữa hai thẻ prov-* = tiếp nối thật của provision đang mở (đó là thứ
    #     giữ được 232 ký tự của BLDS Điều 493) → gắn như cũ
    #   sau thẻ prov-* cuối = nội dung đuôi (Phụ lục, khối chữ ký) → MỘT bản ghi
    #     `phu_luc` cho mỗi văn bản, cấp KHÔNG trích dẫn được, nên nó không thể
    #     làm neo cho câu trích nào
    # Nhận diện bằng VỊ TRÍ, không bằng regex tiếng Việt — nên đây là quy tắc về
    # cấu trúc tài liệu, không phải special case thứ sáu của parser.
    # Mốc là thẻ MANG CLASS `prov-*` cuối cùng — gồm cả `prov-content`, vì một
    # `prov-content` sau thẻ `prov-article` cuối vẫn là thân của Điều đó
    # (Điều 26 của BLLĐ) chứ không phải nội dung đuôi.
    units = list(_don_vi(soup))
    # Mốc `cuoi` CỐ Ý bỏ qua <table>: nó phải giữ nguyên giá trị của bản trước
    # khi bảng vào cây. NĐ 145/2020 có 40 bảng (Mẫu số của Phụ lục) nằm SAU thẻ
    # prov-* cuối cùng; tính chúng vào mốc sẽ đẩy `cuoi` xuống tận cuối trang,
    # `duoi` thành rỗng, và toàn bộ Phụ lục sập lại vào `Điều 115` — đúng bug
    # 42.636 ký tự mà ruling chữ-đuôi đã chữa, chỉ là quay lại qua cửa khác.
    cuoi = max((i for i, (cap, _, tag) in enumerate(units)
                if cap is not None or (tag is not None and not _la_bang(tag))), default=-1)
    duoi = [t for _, t, tag in units[cuoi + 1:] if not _la_bang(tag)]
    bang_duoi = [md for _, _, tag in units[cuoi + 1:]
                 if _la_bang(tag) and (md := _bang_md(tag))]

    gop_khoan_diem = 0
    # Điều đã có ít nhất một Khoản con. Chỉ Điều CHƯA có Khoản nào mới nhận được
    # một `prov-content` mở đầu bằng "1." như Khoản 1 bị gắn nhầm class.
    co_con_khoan: set[int] = set()
    # Nhãn ÉP cho `hang_bang`: pha 2 đọc số hiệu bằng regex trên `nhan[i]`, mà
    # nhãn hàng bảng cần TIÊU ĐỀ CỘT (một ô khác) nên không regex ra được từ
    # riêng dòng đó. Ghi sẵn ở pha 1, nơi còn nhìn thấy cả bảng.
    so_hieu_ep: dict[int, str] = {}
    for cap, text, tag in units[:cuoi + 1]:
        if _la_bang(tag):
            # Bảng thuộc về node ĐANG MỞ tại vị trí của nó — cùng luật vị trí
            # mà chữ mồ côi đang dùng, không phải một quy tắc thứ hai. Với 5 ca
            # đo được ("… như sau:" rồi trỏ vào bảng) node đó chính là Khoản
            # giới thiệu bảng, KHÔNG phải Điều cha: 73,6% số Điều có
            # `noi_dung == tieu_de` nên ghép lên Điều là ghép sai cấp.
            md = _bang_md(tag)
            if not md:
                continue
            dinh = stack[-1] if stack else None
            tach = (_tach_bang(md) if dinh is not None and caps[dinh] in CITABLE
                    else None)
            if tach is None:
                if dinh is None:
                    bang_mo_dau.append(md)
                else:
                    bang[dinh].append((len(than[dinh]), md))
                continue
            # Mỗi HÀNG DỮ LIỆU thành một neo trích dẫn riêng. Không tách thì cả
            # bảng là MỘT `noi_dung`: mô hình trích hai trong bốn hàng lương tối
            # thiểu rồi kết luận "pháp luật quy định hai mức", và bảy phép kiểm
            # đều xanh vì hai citation trỏ cùng một `khop_tai_id` — không có hai
            # anh em nào để phép so tập con đối chiếu (trace cbd9f317).
            dau, hangs = tach
            bang[dinh].append((len(than[dinh]), dau))
            for nhan_hang, dong in hangs:
                caps.append(Cap.hang_bang)
                nhan.append(dong)     # noi_dung = ĐÚNG hàng markdown, vì đó là
                than.append([])       # thứ mô hình trích và verify_tier1 đối
                bang.append([])       # chiếu vào.
                # Không có node HTML riêng: hàng là một `<tr>` bên trong thẻ
                # `<table>`, không phải một thẻ `prov-*` mang id.
                src.append(None)
                parents.append(dinh)
                so_hieu_ep[len(caps) - 1] = nhan_hang
            # CỐ Ý không push vào `stack`: hàng bảng không nhận con, và một
            # `prov-content` đứng sau bảng vẫn là thân của Khoản giới thiệu nó.
            continue
        if cap is None:
            # Nguyên tắc 1: không bao giờ bỏ. Chưa có node nào mở → dồn vào
            # `mo_dau`, thành bản ghi riêng cấp TÀI LIỆU ở dưới. Không raise: cả
            # 21 văn bản đều mở bằng lời mở đầu ("THÔNG TƯ …", "Căn cứ …") nên
            # raise sẽ chặn toàn bộ corpus. `mo_dau` KHÔNG phải cấp bịa: nó là
            # một khối có thật trong văn bản nguồn, chỉ không trích dẫn được —
            # đúng như `phu_luc` ở đầu bên kia.
            dinh = stack[-1] if stack else None
            bi_nuot = None if dinh is None else _la_dieu_khoan_bi_nuot(
                caps[dinh], " ".join([nhan[dinh], *than[dinh]]), text,
                dinh in co_con_khoan)
            if bi_nuot is None:
                (than[dinh] if dinh is not None else mo_dau).append(text)
                continue
            # Thẻ này là điều khoản kế tiếp bị gắn nhầm class → rơi xuống nhánh
            # tạo node mới. `tag` vẫn là thẻ prov-content nên `src` giữ đúng id
            # nguồn của nó.
            cap = bi_nuot

        so = _so_hieu(cap, text)
        if stack and caps[stack[-1]] is cap and _la_tiep_noi_tieu_de(text, cap, so):
            nhan[stack[-1]] = f"{nhan[stack[-1]]} {text}".strip()
            if cap in (Cap.khoan, Cap.diem):
                gop_khoan_diem += 1
            continue

        # Bẫy #1: pop stack tới khi đỉnh có bậc nhỏ hơn
        while stack and caps[stack[-1]].bac >= cap.bac:
            stack.pop()

        caps.append(cap)
        nhan.append(text)
        than.append([])
        bang.append([])
        src.append(tag.get("id") if tag is not None else None)
        parents.append(stack[-1] if stack else None)
        if cap is Cap.khoan and stack:
            co_con_khoan.add(stack[-1])
        stack.append(len(caps) - 1)

    if gop_khoan_diem:
        # WARN, KHÔNG raise: 0 là con số hiện tại của corpus (4 mảnh trước khi
        # sửa, tất cả đã gộp), không phải một bất biến. Raise sẽ chặn build ngay
        # lần MOJ tách thêm một đoạn — mà gộp là hành vi ĐÚNG cho ca đó.
        warnings.warn(
            f"{so_ky_hieu}: đã gộp {gop_khoan_diem} mảnh Khoản/Điểm không có số "
            "hiệu vào sibling cùng cấp liền trước", stacklevel=2)

    if not caps:
        con_lai = sum(len(t) for t in duoi + mo_dau + bang_duoi + bang_mo_dau)
        raise ValueError(
            f"{so_ky_hieu}: có {con_lai} ký tự nhưng KHÔNG có thẻ prov-<cấp> "
            "nào — không thể dựng cây provision")

    if mo_dau or bang_mo_dau:
        # ĐỐI XỨNG với `phu_luc` dưới đây. Chữ trước thẻ prov-* đầu tiên (tiêu
        # ngữ "CHÍNH PHỦ / CỘNG HÒA…", số hiệu, tên văn bản, chuỗi "Căn cứ …")
        # không thuộc điều luật nào. Trước đây nó ghép vào `noi_dung` của row 0;
        # với 8/21 văn bản mở đầu TRỰC TIẾP bằng "Điều 1", row 0 là cấp TRÍCH
        # DẪN ĐƯỢC và một câu trích lấy từ TÊN VĂN BẢN được "kiểm chứng thành
        # công" trên neo Điều 1 — véc-tơ tấn công số 1.
        # Một bản ghi mỗi văn bản nên `duong_dan` tự duy nhất: KHÔNG đánh số thứ
        # tự, đó là bịa ký hiệu không có trong nguồn. Đặt ở CUỐI danh sách (chứ
        # không phải index 0) để `parent_local_id` của mọi node quy phạm giữ
        # nguyên; `mo_dau` không bao giờ vào stack nên thứ tự này vô hại.
        caps.append(Cap.mo_dau)
        nhan.append("")
        than.append(mo_dau)
        # Bảng TIÊU NGỮ ("CHÍNH PHỦ / CỘNG HÒA…") là dàn trang Công báo, không
        # phải quy phạm. Nó đứng trước thẻ prov-* đầu nên rơi vào đây — cấp
        # KHÔNG trích dẫn được, nên một câu trích lấy từ tiêu ngữ không thể
        # "kiểm chứng thành công" trên một neo Điều.
        # Hai bản ghi cấp tài liệu giữ bảng SAU văn xuôi như bản cũ: không trích
        # dẫn được, không đối chiếu (`don_kho._BO_QUA`).
        bang.append([(len(mo_dau), md) for md in bang_mo_dau])
        src.append(None)
        parents.append(None)  # cấp tài liệu, không treo vào cây quy phạm

    if duoi or bang_duoi:
        caps.append(Cap.phu_luc)
        nhan.append("")   # nhãn nằm ở `tieu_de`; noi_dung chỉ chứa chữ NGUỒN,
        than.append(duoi)  # nếu không phép bảo toàn ký tự sẽ lệch
        # 40 bảng Mẫu số của NĐ 145/2020 và các khối chữ ký nằm sau thẻ prov-*
        # cuối cùng đi vào đây, KHÔNG vào Điều cuối của văn bản.
        bang.append([(len(duoi), md) for md in bang_duoi])
        src.append(None)
        parents.append(None)  # cấp tài liệu, không treo vào cây quy phạm

    # ── Pha 2: đọc số hiệu từ chuỗi ĐÃ GỘP, rồi dựng row ───────────────────
    so_hieu = [so_hieu_ep.get(i) or _so_hieu(caps[i], nhan[i])
               for i in range(len(caps))]

    thieu_so = [(caps[i].value, nhan[i][:60]) for i in range(len(caps))
                if caps[i] in SO_HIEU_BAT_BUOC and not so_hieu[i]]
    if thieu_so:
        raise ValueError(
            f"{so_ky_hieu}: so_hieu_cap rỗng ở {len(thieu_so)} node cấp bắt buộc — "
            f"node rác sẽ nhận nhầm con và duong_dan mất neo: {thieu_so[:5]}")

    rows: list[ProvisionRow] = []
    for i, cap in enumerate(caps):
        # Mục A: noi_dung = TOÀN VĂN (nhãn + thân). Với Khoản/Điểm, MOJ nhét
        # toàn bộ text quy phạm vào chính thẻ nhãn nên `nhan[i]` LÀ điều luật.
        # Với Điều/container, `nhan[i]` là dòng tiêu đề và vẫn thuộc toàn văn.
        rows.append(ProvisionRow(
            local_id=i,
            parent_local_id=parents[i],
            cap=cap,
            so_hieu_cap=so_hieu[i],
            # `tieu_de` là NHÃN NGẮN. Khoản/Điểm không có tiêu đề riêng trong
            # nguồn (thẻ nhãn chứa toàn văn), nên nhãn ngắn là chính số hiệu.
            tieu_de=nhan[i] if cap not in (Cap.khoan, Cap.diem, Cap.hang_bang,
                                           Cap.phu_luc, Cap.mo_dau)
            else f"{NHAN[cap]} {so_hieu[i]}".strip(),
            noi_dung=_noi_dung(nhan[i], than[i], bang[i]),
            duong_dan=_duong_dan(i, caps, so_hieu, parents, so_ky_hieu),
            source_node_id=src[i],
            # `local_id` của `mo_dau` ở CUỐI (để `parent_local_id` của mọi node
            # quy phạm giữ nguyên) nhưng chữ mở đầu nằm ở ĐẦU văn bản, nên
            # `thu_tu` phải là -1: nếu không, lời mở đầu xếp SAU cả Phụ lục
            # (126319 từng có mo_dau=35, phu_luc=36, dieu 0–32). Không cần đánh
            # số lại gì cả — không có CHECK nào bắt `thu_tu >= 0`, và `ingest`
            # chỉ dùng `thu_tu` để bảo đảm cha đứng trước con (mo_dau không cha).
            thu_tu=-1 if cap is Cap.mo_dau else i,
        ))

    _kiem_bat_bien(rows, so_ky_hieu)
    return rows


def _kiem_bat_bien(rows: list[ProvisionRow], so_ky_hieu: str) -> None:
    """Bất biến RAISE ở cấp trích dẫn được — làm lỗi cũ không thể ship lại."""
    rong = [r.duong_dan for r in rows if r.cap in CITABLE and not r.noi_dung.strip()]
    if rong:
        raise ValueError(
            f"{so_ky_hieu}: noi_dung RỖNG ở {len(rong)} provision cấp trích dẫn "
            f"được — verifier tầng 1 không có gì để đối chiếu: {rong[:5]}")

    # Neo trích dẫn phải duy nhất. KHÔNG bịa số thứ tự vào duong_dan để né trùng:
    # neo phải là thứ có trong văn bản nguồn, nên trùng ở cấp trích dẫn được là
    # lỗi thật (false-positive verification) và phải raise.
    seen: dict[str, str] = {}
    trung_container: list[str] = []
    for r in rows:
        k = _khoa(r.duong_dan)
        if k in seen:
            if r.cap in CITABLE:
                raise ValueError(
                    f"{so_ky_hieu}: duong_dan TRÙNG ở cấp trích dẫn được — một "
                    f"claim sai sẽ được 'kiểm chứng thành công': {seen[k]!r} vs "
                    f"{r.duong_dan!r}")
            trung_container.append(r.duong_dan)
        seen[k] = r.duong_dan
    if trung_container:
        # NĐ 145/2020 (152668) thật sự đánh số hai Chương cùng là "Chương XI" —
        # đã chấp nhận có chủ đích, nên container chỉ WARN.
        warnings.warn(
            f"{so_ky_hieu}: duong_dan trùng ở cấp container (chấp nhận được nếu "
            f"nguồn thật đánh số trùng): {trung_container}", stacklevel=3)
