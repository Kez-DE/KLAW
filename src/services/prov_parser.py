"""Parse cấu trúc Điều/Khoản/Điểm từ HTML của API MOJ.

Đọc class `prov-*`, KHÔNG regex tiếng Việt. HTML phẳng: mọi <p> là anh em ruột
trong div.WordSection1, cấp bậc chỉ nằm ở tên class → duyệt tuần tự + stack.

Năm cạm bẫy (spec 4.5), mỗi cái có test riêng:
  1. HTML phẳng          → stack theo Cap.bac
  2. prov-content KHÔNG có id → gắn vào node đỉnh stack, KHÔNG tạo node mới
  3. <br> dính chữ       → thay bằng ' ' TRƯỚC khi strip tag
  4. bảng bị bẹp         → parse <table> bằng đường riêng, loại khỏi luồng prov-*
  5. tiêu đề container tách 2 thẻ CÙNG id → gộp thay vì tạo node mồ côi
     (BLLĐ: Chương I có 'Chương I' và 'NHỮNG QUY ĐỊNH CHUNG' ở 2 thẻ id edbf3bf0;
      18 thẻ prov-chapter thô → 17 chương thật)

parse_provisions() là cổng NỘI DUNG (đo độ phủ token). parse_anomalies() là cổng
CẤU TRÚC bổ trợ — bắt ba đường mất dữ liệu mà cổng nội dung không thấy vì token
vẫn còn đủ (xem docstring của nó).
"""

import re

from bs4 import BeautifulSoup, Tag

from src.models.domain import Cap, ProvisionRow

CLASS_TO_CAP = {
    "prov-part": Cap.phan,
    "prov-chapter": Cap.chuong,
    "prov-section": Cap.muc,
    "prov-article": Cap.dieu,
    "prov-clause": Cap.khoan,
    "prov-item": Cap.diem,
}

NHAN = {Cap.phan: "Phần", Cap.chuong: "Chương", Cap.muc: "Mục",
        Cap.dieu: "Điều", Cap.khoan: "Khoản", Cap.diem: "Điểm"}

# Phần/Chương/Mục là tiêu đề mục lục, không phải neo trích dẫn: Điều được đánh số
# duy nhất trong toàn văn bản nên duong_dan bỏ qua các tổ tiên này khi build path
# (vd. "45/2019/QH14 > Điều 25", không phải "... > Chương III > Điều 25"). Nhưng
# parent_local_id vẫn giữ nguyên cây thật (spec 4.4: provisions là cây
# Phần>Chương>Mục>Điều>Khoản>Điểm) — nếu không thì Chương/Mục thành lá rời,
# không nối được vào cây.
CONTAINER_CAPS = {Cap.phan, Cap.chuong, Cap.muc}

# Điều/Khoản dùng chung quy ước hậu tố chữ cho điều/khoản bổ sung (vd. "Điều 33a"
# của luật sửa đổi) — thiếu hậu tố này thì "Điều 33" và "Điều 33a" ra cùng
# duong_dan, tức false-positive verification: một claim trích Điều 33a sẽ được
# "kiểm chứng thành công" trên văn bản Điều 33. IGNORECASE để bắt "ĐIỀU 5" viết
# hoa toàn bộ (thiếu cờ này trước đây làm so_hieu="" → node rác nhận nhầm con).
RE_SO = {
    Cap.dieu: re.compile(r"^Điều\s+(\d+[a-zA-ZđĐ]*)", re.IGNORECASE),
    Cap.khoan: re.compile(r"^(\d+[a-zA-ZđĐ]*)\s*[.)]", re.IGNORECASE),
    Cap.diem: re.compile(r"^([a-zăâđêôơư])\s*\)", re.IGNORECASE),
    Cap.chuong: re.compile(r"^Chương\s+([IVXLCDM\d]+)", re.IGNORECASE),
    Cap.muc: re.compile(r"^Mục\s+([IVXLCDM\d]+)", re.IGNORECASE),
    # "Phần thứ nhất" (BLDS 95942) ưu tiên trước "Phần I" — nhánh `thứ\s+\S+`
    # đứng trước nên khớp hết "thứ nhất", không cắt ở khoảng trắng đầu.
    Cap.phan: re.compile(r"^Phần\s+(thứ\s+\S+|\S+)", re.IGNORECASE),
}


def _text(tag: Tag) -> str:
    """Bẫy #3: thay <br> bằng khoảng trắng TRƯỚC khi lấy text."""
    for br in tag.find_all("br"):
        br.replace_with(" ")
    return re.sub(r"\s+", " ", tag.get_text()).strip()


def _cap_of(tag: Tag) -> Cap | None:
    for cls in tag.get("class") or []:
        if cls in CLASS_TO_CAP:
            return CLASS_TO_CAP[cls]
    return None


def _is_content(tag: Tag) -> bool:
    return "prov-content" in (tag.get("class") or [])


def _so_hieu(cap: Cap, text: str) -> str:
    m = RE_SO.get(cap)
    if m is None:
        return ""
    hit = m.match(text)
    return hit.group(1) if hit else ""


def _duong_dan(cap: Cap, so: str, parent: ProvisionRow | None, so_ky_hieu: str,
               rows: list[ProvisionRow]) -> str:
    """Đường dẫn canonical, đi ngược cây thật qua `parent_local_id`.

    Cấp trích dẫn được (dieu/khoan/diem): BỎ container, theo công ước dẫn chiếu
    pháp lý Việt Nam — "khoản 2 Điều 25", không ai viết "Chương III Điều 25".

    Cấp container (phan/chuong/muc) đang xét: GIỮ đủ chuỗi container, vì tự thân
    nó (vd. "Mục 1") không duy nhất — BLLĐ có 6 "Mục 1" ở 6 Chương khác nhau. Nhờ
    vậy duong_dan duy nhất trên TOÀN BỘ provision, không chỉ ở cấp dieu.
    """
    bo_container = cap not in CONTAINER_CAPS
    segments = [f"{NHAN[cap]} {so}".rstrip()]
    node = parent
    while node is not None:
        if not (bo_container and node.cap in CONTAINER_CAPS):
            segments.append(f"{NHAN[node.cap]} {node.so_hieu_cap}".rstrip())
        node = rows[node.parent_local_id] if node.parent_local_id is not None else None
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


def parse_anomalies(html: str) -> list[str]:
    """Phát hiện đường MẤT DỮ LIỆU ÂM THẦM mà parse_provisions không báo.

    parse_provisions() là cổng NỘI DUNG — đo độ phủ bằng token. Hàm này là cổng
    CẤU TRÚC bổ trợ, bắt ba thứ cổng nội dung không thấy (vì token vẫn còn đủ,
    chỉ cấu trúc/số hiệu/id bị mất — cổng nội dung không đo được điều đó):
      1. Text ngoài mọi thẻ prov-* — parse_provisions chỉ duyệt <p> có class prov-*
      2. prov-content xuất hiện khi chưa có node nào (lời mở đầu "Căn cứ Hiến pháp…")
         → bị bỏ vì `if stack:` không có nhánh else. Mất ~20 token, DƯỚI ngưỡng 98%
         của cổng nội dung nên nó không bắt được.
      3. <p class="prov-*"> nằm TRONG <table> — bị decompose() xóa trước khi duyệt,
         mất cả cấp/số hiệu/id. parse_tables giữ text nên cổng nội dung vẫn PASS.

    Trả về list mô tả người đọc được. Rỗng = không phát hiện gì.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []

    # 3 — provision thật nằm trong bảng
    for tbl in soup.find_all("table"):
        for p in tbl.find_all("p"):
            if _cap_of(p) is not None:
                out.append(
                    f"provision trong <table> sẽ bị mất cấu trúc: "
                    f"class={p.get('class')} id={p.get('id')} text={_text(p)[:60]!r}")
    for tbl in soup.find_all("table"):
        tbl.decompose()

    # 2 — prov-content trước mọi node
    thay_node = False
    for p in soup.find_all("p"):
        if _cap_of(p) is not None:
            thay_node = True
            continue
        if _is_content(p) and not thay_node and _text(p):
            out.append(f"prov-content trước mọi node, sẽ bị bỏ: {_text(p)[:70]!r}")

    # 1 — text ngoài mọi thẻ prov-*
    for p in soup.find_all("p"):
        if _cap_of(p) is None and not _is_content(p):
            t = _text(p)
            if len(t) > 40:  # bỏ qua dòng trắng/ngắt trang
                out.append(f"<p> không có class prov-*, text sẽ biến mất: {t[:70]!r}")

    return out


def parse_provisions(html: str, so_ky_hieu: str) -> list[ProvisionRow]:
    soup = BeautifulSoup(html, "html.parser")

    # Bẫy #4: bỏ hẳn <table> khỏi luồng prov-* để ô không lọt vào dạng prov-content rời
    for tbl in soup.find_all("table"):
        tbl.decompose()

    rows: list[ProvisionRow] = []
    stack: list[ProvisionRow] = []
    thu_tu = 0

    for tag in soup.find_all("p"):
        text = _text(tag)
        if not text:
            continue

        if _is_content(tag):
            # Bẫy #2: KHÔNG tạo node mới, KHÔNG đòi id — gắn vào đỉnh stack.
            # Immutable: thay object bằng bản copy đã update, không sửa tại chỗ.
            if stack:
                cur = stack[-1]
                noi_dung = (cur.noi_dung + " " + text).strip() if cur.noi_dung else text
                updated = cur.model_copy(update={"noi_dung": noi_dung})
                stack[-1] = updated
                rows[cur.local_id] = updated
            continue

        cap = _cap_of(tag)
        if cap is None:
            continue

        so = _so_hieu(cap, text)

        # Phát hiện qua verify dữ liệu thật: có tiêu đề bị tách làm 2 thẻ cùng cấp
        # thay vì nối bằng <br> trong 1 thẻ (vd. Chương I của BLLĐ: "Chương I" và
        # "NHỮNG QUY ĐỊNH CHUNG" là 2 <p class="prov-chapter"> riêng, cùng id).
        # Thẻ sau không khớp số hiệu và cùng cấp với đỉnh stack → nối tiêu đề vào
        # node đã có, không tạo node mồ côi mới. CHỈ áp cho container: một Khoản
        # thật ở văn bản khác không khớp regex số hiệu thì phải vẫn ra node riêng
        # (bảo vệ bằng cách không gộp), không được âm thầm nuốt vào Khoản trước.
        if so == "" and cap in CONTAINER_CAPS and stack and stack[-1].cap is cap:
            cur = stack[-1]
            updated = cur.model_copy(update={"tieu_de": (cur.tieu_de + " " + text).strip()})
            stack[-1] = updated
            rows[cur.local_id] = updated
            continue

        # Bẫy #1: pop stack tới khi đỉnh có bậc nhỏ hơn
        while stack and stack[-1].cap.bac >= cap.bac:
            stack.pop()

        parent = stack[-1] if stack else None  # cha thật (spec 4.4: cây, không bỏ container)
        duong_dan = _duong_dan(cap, so, parent, so_ky_hieu, rows)

        row = ProvisionRow(
            local_id=len(rows),
            parent_local_id=parent.local_id if parent else None,
            cap=cap,
            so_hieu_cap=so,
            tieu_de=text,
            noi_dung="",
            duong_dan=duong_dan,
            source_node_id=tag.get("id"),
            thu_tu=thu_tu,
        )
        thu_tu += 1
        rows.append(row)
        stack.append(row)

    return rows
