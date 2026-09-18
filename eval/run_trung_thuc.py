"""Đo độ TRUNG THỰC của bộ đọc tài liệu so với chính tệp gốc — cái thước cho
lời hứa "render chuẩn 99%" của một biểu mẫu tải lên.

    python -m eval.run_trung_thuc [--bo PATH ...] [--out PATH]

KHÔNG gọi mô hình, KHÔNG ra mạng. Chân lý ở đây là XML nằm trong chính tệp
`.docx` (`zipfile` + `xml.etree`), còn số đo là phần XML đó sống sót qua
`src.services.doc_tai_lieu.doc`. Một câu hỏi thuần đọc tệp không cần LLM, và
một cái thước tốn tiền mỗi lần chạy thì không ai chạy.

Mười mục chấm RIÊNG chứ không gộp thành một số: "99%" gộp lại che đúng thứ cần
thấy — bảng còn nguyên mà đường viền mất sạch vẫn ra 99%. Mục nào bộ đọc CHƯA
CÀI thì ăn 0 và hiện chữ "CHƯA CÀI", không bỏ qua và không miễn trừ: bỏ qua
đúng những mục chưa làm là cách một cái thước tự cho mình điểm cao.

Một mục bị TÁCH ĐÔI khi biểu diễn của bộ đọc chỉ trả lời được một PHẦN câu hỏi:
`vien_bang_co_net` hỏi "bảng này có vẽ nét nào không" — đúng thứ một cờ bool
mỗi bảng chở được; `vien_bang_tung_canh` hỏi hình dạng viền theo từng cạnh,
từng ô — thứ không có chỗ nào cất, nên ăn 0 và mang chữ "CHƯA CÀI". Cặp
`chieu_cao_hang` (số twip mỗi hàng) / `chieu_cao_hang_hrule` (`exact` hay
`atLeast`) tách cùng một lẽ. Gộp lại thì không gian khoá hai bên không bao giờ
gặp nhau và một khả năng CHẠY ĐÚNG bị chấm 0 — sai đúng bằng cách chấm 100%
cho một khả năng không chạy.

Chỉ đếm những gì TỆP KHAI. `w:jc` vắng mặt không phải "căn trái", nó là "không
khai"; tính nó thành một dữ kiện đúng là thổi điểm bằng những thứ tệp không hề
nói. Mục có 0 dữ kiện khai báo hiện "—" và KHÔNG vào trung bình — nhưng lý do
"nguồn không khai" được in ra, để không ai đọc nhầm nó thành "đã đo, đã đạt".

Phần giải `w:jc` theo `w:pStyle`/`w:basedOn` ở đây viết LẠI thay vì gọi
`doc_tai_lieu._can_le_doan`: một cái thước gọi chính vật nó đo thì luôn đo ra
100%.
"""

import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import fields
from io import BytesIO
from pathlib import Path
from typing import TypeVar

from src.services.doc_tai_lieu import DonViVanBan, KhongDocDuoc, TaiLieuDaDoc, doc

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BO_MAC_DINH = (
    _REPO_ROOT / "eval" / "datasets" / "tai_lieu_tong_quat",
    _REPO_ROOT / "eval" / "datasets" / "tai_lieu_mau",
)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _q(ten: str) -> str:
    return f"{{{_W}}}{ten}"


# Mục chấm → những trường của `DonViVanBan` CHỞ được mục đó. Tuple rỗng nghĩa
# là mô hình đọc không có chỗ nào cất mục này: "chưa cài" là thuộc tính của BỘ
# ĐỌC, không phải của tập mẫu — nên một mục chưa cài vẫn ăn 0 kể cả khi không
# tệp mẫu nào khai nó. Cài xong một mục thì thêm tên trường vào đây, và chính
# việc phải sửa bảng này làm cho lần cài đó không thể đi qua im lặng.
_TRUONG_DOC_RA: dict[str, tuple[str, ...]] = {
    "cau_truc": ("bang", "bang_nhip", "bang_ti_le"),
    "vien_bang_co_net": ("bang_vien",),
    "vien_bang_tung_canh": (),
    "chieu_cao_hang": ("bang_cao",),
    "chieu_cao_hang_hrule": (),
    "can_le": ("can_le",),
    "dinh_dang_run": ("dinh_dang",),
    "gian_cach_thut_le": (),
    "le_trang": (),
    "media": (),
}

_CO_THUC = {f.name for f in fields(DonViVanBan)}
if _thieu := sorted({t for ts in _TRUONG_DOC_RA.values() for t in ts} - _CO_THUC):
    raise RuntimeError(f"_TRUONG_DOC_RA nhắc trường không có trong DonViVanBan: {_thieu}")

_JC_RA_CAN_LE = {"center": "giua", "right": "phai", "end": "phai"}
_CANH_VIEN = ("top", "left", "bottom", "right", "insideH", "insideV")
_VIEN_KHONG_VE = {"none", "nil"}

_T = TypeVar("_T")


def _val(e: ET.Element | None) -> str | None:
    return e.get(_q("val")) if e is not None else None


def _chu(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.iter(_q("t"))).strip()


def _giai_chuoi(truc: dict[str, _T], cha: dict[str, str]) -> dict[str, _T]:
    """id kiểu → giá trị THẬT sau khi đi hết chuỗi `w:basedOn`.

    Kiểu nào cả chuỗi cha không ai khai thì KHÔNG có mặt trong kết quả: "không
    khai" phải phân biệt được với "khai rồi", đúng luật của cả tệp này.
    """
    ra: dict[str, _T] = {}
    for sid in {*truc, *cha}:
        cur, da_qua = sid, set()
        while cur and cur not in da_qua and cur not in truc:
            da_qua.add(cur)
            cur = cha.get(cur)
        if cur in truc:
            ra[sid] = truc[cur]
    return ra


def _jc_theo_kieu(z: zipfile.ZipFile) -> dict[str, str]:
    """id kiểu đoạn văn → `w:jc` thật của kiểu đó, đã đi hết chuỗi `w:basedOn`.

    `styles.xml` không bắt buộc có; thiếu nó thì chỉ còn `jc` trực tiếp.
    """
    if "word/styles.xml" not in z.namelist():
        return {}
    goc = ET.fromstring(z.read("word/styles.xml"))
    truc: dict[str, str] = {}
    cha: dict[str, str] = {}
    for st in goc.findall(_q("style")):
        if not (sid := st.get(_q("styleId"))):
            continue
        if v := _val(st.find(_q("basedOn"))):
            cha[sid] = v
        if v := _val(st.find(f'{_q("pPr")}/{_q("jc")}')):
            truc[sid] = v
    return _giai_chuoi(truc, cha)


def _co_net(vien: ET.Element) -> bool:
    """Một nhóm viền (`w:tblBorders`/`w:tcBorders`) có vẽ cạnh nào không — một
    cạnh khai giá trị ngoài `none`/`nil` là đủ."""
    return any(c.get(_q("val")) not in _VIEN_KHONG_VE for c in vien)


def _vien_theo_kieu(z: zipfile.ZipFile) -> dict[str, bool]:
    """id kiểu BẢNG → kiểu đó có vẽ viền không, đã đi hết chuỗi `w:basedOn`.

    Cần vì `TableGrid` (kiểu bảng có viền sẵn của Word) là cách phổ biến nhất
    để một biểu mẫu tiếng Việt có viền: bảng ấy chỉ khai `w:tblStyle`, không
    khai `w:tblBorders` nào trong `document.xml`. Bỏ qua `styles.xml` thì chính
    CHÂN LÝ đọc bảng đó thành "không viền", và bộ đọc bị trừ điểm cho một câu
    nó trả lời đúng — cái thước sai theo hướng ngược lại vẫn là thước sai.
    """
    if "word/styles.xml" not in z.namelist():
        return {}
    goc = ET.fromstring(z.read("word/styles.xml"))
    truc: dict[str, bool] = {}
    cha: dict[str, str] = {}
    for st in goc.findall(_q("style")):
        if not (sid := st.get(_q("styleId"))) or st.get(_q("type")) != "table":
            continue
        if v := _val(st.find(_q("basedOn"))):
            cha[sid] = v
        if (e := st.find(f'{_q("tblPr")}/{_q("tblBorders")}')) is not None:
            truc[sid] = _co_net(e)
    return _giai_chuoi(truc, cha)


def _net_bang(tbl: ET.Element, vien_kieu: dict[str, bool]) -> bool | None:
    """Bảng này có vẽ nét nào không, `None` khi tệp KHÔNG khai gì về viền.

    Gộp ba nguồn bằng HOẶC — `w:tblPr/w:tblBorders`, `w:tblStyle` đã giải qua
    `w:basedOn`, và `w:tcPr/w:tcBorders` của ô — vì đó đúng là câu hỏi mà biểu
    diễn của bộ đọc trả lời được: một cờ bool mỗi bảng, "tệp có vẽ nét nào
    không". Hình dạng viền theo cạnh đi về mục `vien_bang_tung_canh` bên cạnh.

    `None` giữ nguyên luật "chỉ đếm những gì tệp khai": một bảng không nhắc tới
    viền ở đâu cả thì không phải một dữ kiện, dù OOXML mặc định là không viền —
    cùng lý lẽ đã dùng cho `w:jc` vắng mặt.
    """
    nguon: list[bool] = []
    if (e := tbl.find(f'{_q("tblPr")}/{_q("tblBorders")}')) is not None:
        nguon.append(_co_net(e))
    if (sid := _val(tbl.find(f'{_q("tblPr")}/{_q("tblStyle")}'))) in vien_kieu:
        nguon.append(vien_kieu[sid])
    # Chỉ ô của CHÍNH bảng này (`findall`, không `iter`): một bảng lồng trong
    # một ô là bảng khác, viền của nó không nói gì về bảng bao ngoài.
    nguon.extend(
        _co_net(e)
        for tr in tbl.findall(_q("tr"))
        for tc in tr.findall(_q("tc"))
        if (e := tc.find(f'{_q("tcPr")}/{_q("tcBorders")}')) is not None
    )
    return any(nguon) if nguon else None


def _jc_khai(p: ET.Element | None, kieu: dict[str, str]) -> str | None:
    """Căn lề tệp KHAI cho một `w:p`, hoặc `None` khi tệp không khai gì."""
    if p is None:
        return None
    if (v := _val(p.find(f'{_q("pPr")}/{_q("jc")}'))) is not None:
        return _JC_RA_CAN_LE.get(v, "trai")
    sid = _val(p.find(f'{_q("pPr")}/{_q("pStyle")}'))
    v = kieu.get(sid) if sid else None
    return _JC_RA_CAN_LE.get(v, "trai") if v is not None else None


def _vien(cha: ET.Element | None, khoa: str, ra: dict[str, str]) -> None:
    if cha is None:
        return
    for canh in _CANH_VIEN:
        if (e := cha.find(_q(canh))) is not None:
            ra[f"{khoa}/{canh}"] = f'{_val(e) or ""}/{e.get(_q("sz")) or ""}'


def _run_va_gian_cach(p: ET.Element, tien_to: str, ra: dict[str, dict[str, str]]) -> None:
    for j, r in enumerate(p.findall(_q("r"))):
        if (rpr := r.find(_q("rPr"))) is None:
            continue
        for ten in ("b", "i", "u", "sz", "rFonts"):
            if (e := rpr.find(_q(ten))) is None:
                continue
            # `w:b` không có `w:val` nghĩa là BẬT — mặc định của OOXML, khác
            # `w:sz` vốn luôn mang số.
            ra["dinh_dang_run"][f"{tien_to}/run{j}/{ten}"] = _val(e) or e.get(_q("ascii")) or "1"
    ppr = p.find(_q("pPr"))
    if ppr is None:
        return
    for ten in ("spacing", "ind"):
        if (e := ppr.find(_q(ten))) is not None:
            for k, v in sorted(e.attrib.items()):
                ra["gian_cach_thut_le"][f'{tien_to}/{ten}/{k.split("}")[-1]}'] = v
    if (e := ppr.find(_q("tabs"))) is not None:
        ra["gian_cach_thut_le"][f"{tien_to}/tabs"] = str(len(e.findall(_q("tab"))))


def _ti_le_luoi(tbl: ET.Element) -> str:
    """% mỗi cột lưới trên tổng bề rộng bảng, từ `w:tblGrid/w:gridCol`.

    Quy về % chứ không so twips trần trụi: `sum(gridCol)` không bằng bề rộng
    thân trang, nên tỉ lệ mới là thứ render dùng được. Phép quy đổi tự làm ở
    đây, không mượn của bộ đọc.
    """
    if (grid := tbl.find(_q("tblGrid"))) is None:
        return ""
    rong = [n for g in grid.findall(_q("gridCol")) if (w := g.get(_q("w"))) and (n := int(w)) > 0]
    if not (tong := sum(rong)):
        return ""
    return ",".join(str(round(w * 100 / tong)) for w in rong)


_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


def _khoi_than(nut: ET.Element):
    """`w:p` và `w:tbl` cấp khối, THEO TRẬT TỰ TÀI LIỆU, chui qua mọi vỏ bọc.

    KHÔNG duyệt con trực tiếp của `w:body` như bộ đọc: một bảng nằm trong
    `w:sdt` (content control) vẫn là một bảng thật của tài liệu, và nếu chân lý
    cũng mù đúng chỗ bộ đọc mù thì hai bên khớp nhau 100% trên một tệp mà người
    dùng thấy mất sạch bảng. Không chui vào `w:p` (hộp chữ nằm trong một `w:p`
    là chi tiết của đoạn đó, không phải một khối riêng) và không chui vào
    `w:tbl` (ô của nó được đếm riêng). Bỏ `mc:Fallback` vì nó chép lại nội dung
    của `mc:Choice`.
    """
    for con in nut:
        if con.tag in (_q("p"), _q("tbl")):
            yield con
        elif con.tag != _MC_FALLBACK:
            yield from _khoi_than(con)


def dac_ta_nguon(du_lieu: bytes) -> dict[str, dict[str, str]]:
    """Những gì tệp .docx THẬT SỰ khai, theo mười mục — chân lý để đối chiếu."""
    ra: dict[str, dict[str, str]] = {m: {} for m in _TRUONG_DOC_RA}
    with zipfile.ZipFile(BytesIO(du_lieu)) as z:
        goc = ET.fromstring(z.read("word/document.xml"))
        kieu = _jc_theo_kieu(z)
        vien_kieu = _vien_theo_kieu(z)
        for ten in z.namelist():
            if ten.startswith("word/media/"):
                ra["media"][ten] = "co"
    if (n := sum(1 for _ in goc.iter(_q("drawing"))) + sum(1 for _ in goc.iter(_q("pict")))):
        ra["media"]["so_hinh_trong_than"] = str(n)
    if (than := goc.find(_q("body"))) is None:
        return ra
    if (pg := than.find(f'{_q("sectPr")}/{_q("pgMar")}')) is not None:
        for k, v in sorted(pg.attrib.items()):
            ra["le_trang"][f'pgMar/{k.split("}")[-1]}'] = v

    khoi = so_bang = 0
    for con in _khoi_than(than):
        if con.tag == _q("p"):
            # Đoạn rỗng chữ không thành một đơn vị bên bộ đọc, nên cũng không
            # được thành một dữ kiện bên này: hai bên phải đếm cùng một thứ.
            if not _chu(con):
                continue
            k = f"khoi{khoi}"
            ra["cau_truc"][k] = "doan"
            if (jc := _jc_khai(con, kieu)) is not None:
                ra["can_le"][k] = jc
            _run_va_gian_cach(con, k, ra)
            khoi += 1
        elif con.tag == _q("tbl"):
            b = so_bang
            ra["cau_truc"][f"khoi{khoi}"] = "bang"
            if ti_le := _ti_le_luoi(con):
                ra["cau_truc"][f"bang{b}/luoi"] = ti_le
            if (net := _net_bang(con, vien_kieu)) is not None:
                ra["vien_bang_co_net"][f"bang{b}"] = "co" if net else "khong"
            _vien(con.find(f'{_q("tblPr")}/{_q("tblBorders")}'), f"bang{b}/tblBorders", ra["vien_bang_tung_canh"])
            for h, tr in enumerate(con.findall(_q("tr"))):
                if (th := tr.find(f'{_q("trPr")}/{_q("trHeight")}')) is not None:
                    # Số twip và `hRule` tách làm HAI dữ kiện: bộ đọc chở được
                    # số, không chở được luật cắt chữ — gộp thì cả hai cùng sai.
                    if (cao := _val(th)) is not None:
                        ra["chieu_cao_hang"][f"bang{b}/hang{h}"] = cao
                    if hrule := th.get(_q("hRule")):
                        ra["chieu_cao_hang_hrule"][f"bang{b}/hang{h}"] = hrule
                cot = 0
                for tc in tr.findall(_q("tc")):
                    nhip = int(_val(tc.find(f'{_q("tcPr")}/{_q("gridSpan")}')) or 1)
                    nhip = nhip if nhip > 0 else 1
                    o = f"bang{b}/o{h},{cot}"
                    cot += nhip
                    # Ô RỖNG chữ vẫn là một ô: một phiếu trắng gần như toàn ô
                    # rỗng, bỏ chúng đi là bỏ chính hình dạng của biểu mẫu.
                    ra["cau_truc"][o] = str(nhip)
                    if (jc := _jc_khai(tc.find(_q("p")), kieu)) is not None:
                        ra["can_le"][o] = jc
                    _vien(tc.find(f'{_q("tcPr")}/{_q("tcBorders")}'), f"{o}/tcBorders", ra["vien_bang_tung_canh"])
                    for j, p in enumerate(tc.iter(_q("p"))):
                        _run_va_gian_cach(p, f"{o}/p{j}", ra)
            so_bang += 1
            khoi += 1
    return ra


def dac_ta_bo_doc(tai_lieu: TaiLieuDaDoc) -> dict[str, dict[str, str]]:
    """Cùng không gian khoá, nhưng dựng lại TỪ đầu ra của bộ đọc.

    Mục nào `_TRUONG_DOC_RA` để rỗng thì ở đây cũng rỗng — không có trường nào
    chở nó, nên không có gì để dựng.
    """
    ra: dict[str, dict[str, str]] = {m: {} for m in _TRUONG_DOC_RA}
    khoi = 0
    bang_truoc: int | None = None

    def _run(tien_to: str, d) -> None:
        """`DinhDangChu.khai` → đúng khoá `_run_va_gian_cach` bên chân lý dựng.

        `v or "1"` là phép nghịch của `_val(e) or e.get(ascii) or "1"`: bộ đọc
        cất chuỗi RỖNG cho một thẻ không có `w:val` (`<w:b/>`), còn chân lý
        đọc chính thẻ ấy ra `"1"`.
        """
        for r in d.dinh_dang:
            goc = tien_to if d.bang is None else f"{tien_to}/p{r.doan}"
            for ten, v in r.khai:
                ra["dinh_dang_run"][f"{goc}/run{r.so}/{ten}"] = v or "1"

    for d in tai_lieu.don_vi:
        if d.vung != "than":
            continue
        if d.bang is None:
            ra["cau_truc"][f"khoi{khoi}"] = "doan"
            ra["can_le"][f"khoi{khoi}"] = d.can_le
            _run(f"khoi{khoi}", d)
            khoi += 1
            bang_truoc = None
            continue
        b, h, c = d.bang
        if b != bang_truoc:
            ra["cau_truc"][f"khoi{khoi}"] = "bang"
            khoi += 1
            bang_truoc = b
            if d.bang_ti_le:
                ra["cau_truc"][f"bang{b}/luoi"] = ",".join(str(x) for x in d.bang_ti_le)
        # `bang_vien` là MỘT cờ cho cả bảng và `bang_cao` MỘT số cho cả hàng:
        # mọi ô của cùng bảng/hàng ghi lại đúng một giá trị, nên ghi đè vô hại.
        ra["vien_bang_co_net"][f"bang{b}"] = "co" if d.bang_vien else "khong"
        ra["chieu_cao_hang"][f"bang{b}/hang{h}"] = str(d.bang_cao)
        ra["cau_truc"][f"bang{b}/o{h},{c}"] = str(d.bang_nhip)
        ra["can_le"][f"bang{b}/o{h},{c}"] = d.can_le
        _run(f"bang{b}/o{h},{c}", d)
    return ra


def diem_muc(khai: int, khop: int, chua_cai: bool) -> float | None:
    """`None` = nguồn không khai gì để đo (KHÔNG vào trung bình). 0.0 khi bộ
    đọc chưa cài mục đó, kể cả lúc nguồn cũng không khai."""
    if chua_cai:
        return 0.0
    return khop / khai if khai else None


def cham(nguon: dict[str, dict[str, str]], doc_ra: dict[str, dict[str, str]]) -> dict[str, dict]:
    ra: dict[str, dict] = {}
    for m, truong in _TRUONG_DOC_RA.items():
        thieu = sorted(k for k, v in nguon[m].items() if doc_ra[m].get(k) != v)
        khai = len(nguon[m])
        ra[m] = {
            "khai": khai,
            "khop": khai - len(thieu),
            "chua_cai": not truong,
            "thieu": thieu[:20],
            "diem": diem_muc(khai, khai - len(thieu), not truong),
        }
    return ra


def _commit_hash() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=_REPO_ROOT
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _tim_tep(bo: list[Path]) -> list[Path]:
    tep: list[Path] = []
    for p in bo:
        tep.extend(sorted(p.glob("*.docx")) if p.is_dir() else [p])
    return tep


def chay(tep: list[Path]) -> dict:
    """Một tệp hỏng KHÔNG được làm mất cả lượt — cùng khuôn `eval.run_trap.chay`."""
    chi_tiet = []
    for t in tep:
        du_lieu = t.read_bytes()
        try:
            tai_lieu = doc(t.name, du_lieu)
        except KhongDocDuoc as e:
            chi_tiet.append({"tep": t.name, "error": f"{e.ly_do}: {e.chi_tiet}"})
            continue
        chi_tiet.append({"tep": t.name, "muc": cham(dac_ta_nguon(du_lieu), dac_ta_bo_doc(tai_lieu))})

    tong_hop: dict[str, dict] = {}
    for m, truong in _TRUONG_DOC_RA.items():
        khai = sum(c["muc"][m]["khai"] for c in chi_tiet if "muc" in c)
        khop = sum(c["muc"][m]["khop"] for c in chi_tiet if "muc" in c)
        tong_hop[m] = {"khai": khai, "khop": khop, "chua_cai": not truong, "diem": diem_muc(khai, khop, not truong)}
    do_duoc = [v["diem"] for v in tong_hop.values() if v["diem"] is not None]
    return {
        "commit_hash": _commit_hash(),
        "so_tep": len(chi_tiet),
        "chi_tiet": chi_tiet,
        "tong_hop": tong_hop,
        "tong": sum(do_duoc) / len(do_duoc) if do_duoc else None,
    }


def _in_bang(ket: dict) -> None:
    print(f"commit_hash={ket['commit_hash']}")
    print(f"tệp đo: {ket['so_tep']}")
    print(f"  {'mục':<22}{'khai':>6}{'khớp':>6}{'điểm':>8}   ghi chú")
    for m, v in ket["tong_hop"].items():
        d = "—" if v["diem"] is None else f"{v['diem']:.0%}"
        ghi = "CHƯA CÀI" if v["chua_cai"] else ("NGUỒN KHÔNG KHAI" if v["diem"] is None else "")
        print(f"  {m:<22}{v['khai']:>6}{v['khop']:>6}{d:>8}   {ghi}")
    chua = sum(1 for v in ket["tong_hop"].values() if v["chua_cai"])
    ngoai = sum(1 for v in ket["tong_hop"].values() if v["diem"] is None)
    tong = "—" if ket["tong"] is None else f"{ket['tong']:.0%}"
    print(f"TỔNG: {tong} ({len(_TRUONG_DOC_RA) - ngoai}/{len(_TRUONG_DOC_RA)} mục vào trung bình; {chua} CHƯA CÀI)")
    for c in ket["chi_tiet"]:
        if "error" in c:
            print(f"  LỖI {c['tep']}: {c['error']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bo", type=Path, nargs="*", default=list(_BO_MAC_DINH), help="thư mục hoặc tệp .docx")
    ap.add_argument("--out", type=Path, default=_REPO_ROOT / "eval" / "results" / "trung_thuc_bieu_mau.json")
    args = ap.parse_args()

    tep = _tim_tep(args.bo)
    if not tep:
        raise SystemExit(
            "không thấy .docx nào — tệp mẫu là ĐẦU RA, không commit; dựng lại bằng\n"
            "  python eval/datasets/tai_lieu_tong_quat/dung_mau.py\n"
            "  python eval/datasets/tai_lieu_mau/dung_mau.py"
        )

    ket = chay(tep)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket, ensure_ascii=False, indent=2), encoding="utf-8")
    _in_bang(ket)


if __name__ == "__main__":
    main()
