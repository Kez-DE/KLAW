"""Parse cấu trúc Điều/Khoản/Điểm từ HTML của API MOJ.

Đọc class `prov-*`, KHÔNG regex tiếng Việt. HTML phẳng: mọi <p> là anh em ruột
trong div.WordSection1, cấp bậc chỉ nằm ở tên class → duyệt tuần tự + stack.

Bốn cạm bẫy (spec 4.5), mỗi cái có test riêng:
  1. HTML phẳng          → stack theo Cap.bac
  2. prov-content KHÔNG có id → gắn vào node đỉnh stack, KHÔNG tạo node mới
  3. <br> dính chữ       → thay bằng ' ' TRƯỚC khi strip tag
  4. bảng bị bẹp         → parse <table> bằng đường riêng, loại khỏi luồng prov-*
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
CONTAINER_CAPS = (Cap.phan, Cap.chuong, Cap.muc)

RE_SO = {
    Cap.dieu: re.compile(r"^Điều\s+(\d+)"),
    Cap.khoan: re.compile(r"^(\d+)\s*[.)]"),
    Cap.diem: re.compile(r"^([a-zăâđêôơư])\s*\)", re.IGNORECASE),
    Cap.chuong: re.compile(r"^Chương\s+([IVXLCDM\d]+)", re.IGNORECASE),
    Cap.muc: re.compile(r"^Mục\s+([IVXLCDM\d]+)", re.IGNORECASE),
    Cap.phan: re.compile(r"^Phần\s+(\S+)"),  # `re` KHÔNG hỗ trợ \p{L} — dùng \S+
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
    """Công ước dẫn chiếu: đi ngược cây thật qua `parent_local_id`, nhưng bỏ qua
    mọi ancestor Phần/Chương/Mục — chỉ Điều/Khoản/Điểm góp mặt trong duong_dan."""
    segments = [f"{NHAN[cap]} {so}".rstrip()]
    node = parent
    while node is not None:
        if node.cap not in CONTAINER_CAPS:
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
        # node đã có, không tạo node mồ côi mới.
        if so == "" and stack and stack[-1].cap is cap:
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
