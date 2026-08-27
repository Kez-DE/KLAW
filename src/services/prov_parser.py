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

from bs4 import BeautifulSoup, NavigableString, Tag

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

NHAN = {Cap.phan: "Phần", Cap.chuong: "Chương", Cap.muc: "Mục",
        Cap.tieu_muc: "Tiểu mục", Cap.dieu: "Điều", Cap.khoan: "Khoản",
        Cap.diem: "Điểm"}

# Cấp TRÍCH DẪN ĐƯỢC — nơi verifier tầng 1 đối chiếu câu trích vào văn bản.
# `noi_dung` rỗng ở đây nghĩa là phép kiểm "câu trích khớp nguyên văn" không có
# gì để đối chiếu: hoặc luôn thất bại (hệ thống ABSTAIN mọi câu hỏi), hoặc được
# viết cho "rỗng thì bỏ qua" và khi đó nó không kiểm gì cả. Nên nó là RAISE.
CITABLE = {Cap.dieu, Cap.khoan, Cap.diem}

# Phần/Chương/Mục/Tiểu mục là tiêu đề mục lục, không phải neo trích dẫn: Điều
# được đánh số duy nhất trong toàn văn bản nên duong_dan bỏ qua các tổ tiên này
# khi build path (vd. "45/2019/QH14 > Điều 25", không phải "... > Chương III >
# Điều 25"). Nhưng parent_local_id vẫn giữ nguyên cây thật (spec 4.4).
CONTAINER_CAPS = {Cap.phan, Cap.chuong, Cap.muc, Cap.tieu_muc}

# Cấp có NHÃN xuất hiện trong text ("Phần"/"Chương"/"Mục"/"Tiểu mục"/"Điều").
# Khoản/Điểm chỉ có số ("1.", "a)") nên không dùng được dấu hiệu nhãn — và vì
# thế chúng KHÔNG BAO GIỜ bị gộp, đúng bất biến cần giữ.
LABEL_LEVELS = {Cap.phan, Cap.chuong, Cap.muc, Cap.tieu_muc, Cap.dieu}

# Cấp phải có số hiệu vì nhãn của chúng LUÔN kèm số trong văn bản nguồn. Rỗng =
# node rác sẽ nhận nhầm con và làm duong_dan mất neo (Chương VIII của BLHS).
# `phan` không nằm ở đây: nó theo tiêu chí ĐẠT của brief (dieu/chuong/muc/tieu_muc).
SO_HIEU_BAT_BUOC = {Cap.dieu, Cap.chuong, Cap.muc, Cap.tieu_muc}

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

# Chuẩn hoá CHỈ ĐỂ SO KHỚP, không đổi text lưu.
#   U+200B/U+FEFF: zero-width, vô hình nhưng làm hai chuỗi "khác nhau".
#   Ð U+00D0 (LATIN CAPITAL LETTER ETH) ≠ Đ U+0110 — đã có đúng 2 lần trong
#   96172. Nếu rơi vào đầu thẻ prov-article thì regex ^Điều không khớp, node ra
#   số rỗng và một Điều thật bị gộp mất.
_MAP_KHOA = str.maketrans({"​": "", "﻿": "",
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


def _cap_of(tag: Tag) -> Cap | None:
    for cls in tag.get("class") or []:
        if cls in CLASS_TO_CAP:
            return CLASS_TO_CAP[cls]
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
    if so or cap not in LABEL_LEVELS:
        return False
    return not _khoa(text).lower().startswith(NHAN[cap].lower())


def _don_vi(node: Tag):
    """Duyệt cây theo thứ tự văn bản, yield MỌI text node — không whitelist.

    Yield `(cap, text, tag)`:
      - `cap is not None` → thẻ mở node mới (class prov-<cấp>), `tag` để lấy id
      - `cap is None`     → text thuộc node đang mở (prov-content, <p> không
                            class, hoặc text trần trong <div>/<em>/<strong>)

    KHÔNG đi sâu vào thẻ đã có class prov-* : lấy nguyên text của nó một lần.
    Đã kiểm trên cả 21 văn bản: không có prov-* nào lồng trong prov-* (0 ca).
    """
    for child in node.children:
        if isinstance(child, NavigableString):
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
                    yield cap, t, child
            elif "prov-content" in (child.get("class") or []):
                yield None, _text(child), None
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
            segments.append(f"{NHAN[caps[j]]} {so_hieu[j]}".rstrip())
        j = parents[j]
    segments.reverse()
    return " > ".join([so_ky_hieu, *segments])


def parse_tables(html: str) -> list[str]:
    """Bẫy #4: parse <table> riêng, mỗi bảng thành một markdown table."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for tbl in soup.find_all("table"):
        lines: list[str] = []
        for tr in tbl.find_all("tr"):
            cells = [_text(td) for td in tr.find_all(["td", "th"])]
            if cells:
                lines.append("| " + " | ".join(cells) + " |")
        if lines:
            out.append("\n".join(lines))
    return out


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

    for tbl in soup.find_all("table"):
        tbl.decompose()

    # BẢO TOÀN KÝ TỰ. Đếm ký tự khác khoảng trắng, nên phép so không phụ thuộc
    # quy ước chèn dấu cách giữa các thẻ inline (<sup>/<b>/<a>) — thứ làm phép so
    # theo token báo lệch giả ở dấu câu và công thức "L[T(N)]".
    # So với `noi_dung` THÔI (không cộng `tieu_de`): mỗi đơn vị text đi vào đúng
    # MỘT `noi_dung`, nên đẳng thức phải khít tuyệt đối, không ngưỡng. Lệch ⇒ có
    # đơn vị bị bỏ (whitelist quay lại, `if stack:` không có else, thẻ bị skip).
    rows = parse_provisions(html, so_ky_hieu)
    goc = _dem(soup.get_text())
    trong_rows = sum(_dem(r.noi_dung) for r in rows)
    if goc != trong_rows:
        loi.append(f"KHÔNG BẢO TOÀN: HTML có {goc} ký tự, provisions.noi_dung giữ "
                   f"{trong_rows} — lệch {goc - trong_rows}")

    return loi, canh_bao


def parse_provisions(html: str, so_ky_hieu: str) -> list[ProvisionRow]:
    soup = BeautifulSoup(html, "html.parser")

    # Bẫy #4: bỏ hẳn <table> khỏi luồng prov-* để ô không lọt vào dạng prov-content rời
    for tbl in soup.find_all("table"):
        tbl.decompose()

    # ── Pha 1: gom khối theo thứ tự văn bản ────────────────────────────────
    # `nhan[i]` = text của (các) thẻ nhãn đã GỘP; `than[i]` = mọi text nối theo.
    # Số hiệu đọc SAU pha này, từ chuỗi đã ghép — đó là cả mục D.
    caps: list[Cap] = []
    nhan: list[str] = []
    than: list[list[str]] = []
    src: list[str | None] = []
    parents: list[int | None] = []
    stack: list[int] = []
    mo_dau: list[str] = []  # text xuất hiện TRƯỚC node đầu tiên

    for cap, text, tag in _don_vi(soup):
        if cap is None:
            # Nguyên tắc 1: không bao giờ bỏ. Chưa có node nào mở → giữ lại và
            # gắn vào node ĐẦU TIÊN. Không raise: cả 21 văn bản đều mở bằng lời
            # mở đầu ("THÔNG TƯ …", "Căn cứ …"), raise sẽ chặn toàn bộ corpus;
            # không tạo cấp giả vì cấp phải là thứ có trong văn bản nguồn.
            (than[stack[-1]] if stack else mo_dau).append(text)
            continue

        so = _so_hieu(cap, text)
        if stack and caps[stack[-1]] is cap and _la_tiep_noi_tieu_de(text, cap, so):
            nhan[stack[-1]] = f"{nhan[stack[-1]]} {text}".strip()
            continue

        # Bẫy #1: pop stack tới khi đỉnh có bậc nhỏ hơn
        while stack and caps[stack[-1]].bac >= cap.bac:
            stack.pop()

        caps.append(cap)
        nhan.append(text)
        than.append([])
        src.append(tag.get("id") if tag is not None else None)
        parents.append(stack[-1] if stack else None)
        stack.append(len(caps) - 1)

    if mo_dau and not caps:
        raise ValueError(
            f"{so_ky_hieu}: có {sum(len(t) for t in mo_dau)} ký tự nhưng KHÔNG có "
            "thẻ prov-* nào — không thể gắn nội dung vào provision nào")

    # ── Pha 2: đọc số hiệu từ chuỗi ĐÃ GỘP, rồi dựng row ───────────────────
    so_hieu = [_so_hieu(caps[i], nhan[i]) for i in range(len(caps))]

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
            tieu_de=nhan[i] if cap not in (Cap.khoan, Cap.diem)
            else f"{NHAN[cap]} {so_hieu[i]}".rstrip(),
            noi_dung=_chuan_hoa(" ".join(
                [*(mo_dau if i == 0 else []), nhan[i], *than[i]])),
            duong_dan=_duong_dan(i, caps, so_hieu, parents, so_ky_hieu),
            source_node_id=src[i],
            thu_tu=i,
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
