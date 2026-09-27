"""Áp phép sửa lên khuôn gốc DOCX — kế hoạch `docs/plans/active/khuon-goc-dien-tai-cho.md`,
hợp đồng "Edit operations"; quyết định 2026-09-26 (`luu-khuon-goc-va-dien-tai-cho`).

`ap_dung_docx(docx, don_vi, phep_sua) -> (docx_moi, bao_cao)` là hàm THUẦN: không
DB, không mạng, không log. `don_vi` là đúng mảng dict `tai_lieu` đọc lại từ
`viec_doc_tai_lieu.don_vi`; mỗi phiên bản bản thảo gọi hàm trên khuôn gốc NGUYÊN
với TRỌN danh sách phép của phiên bản đó — tầng này không có "phép chênh".

Ba luật định hình file:

**Đi thẳng tới địa chỉ đã ghim.** `dia_chi`/`cho_trong` do bộ đọc ghim trên part
THÔ (P2b). Ở đây giải lại trên chính bytes đó bằng lxml, đếm con PHẦN TỬ (lxml giữ
comment/PI làm con, ElementTree của bộ đọc thì không) — không duyệt lại, không tra
theo chữ.

**Kiểm trước khi sửa, bỏ chứ không đoán.** Mọi phép được giải và kiểm trên cây
NGUYÊN trước khi phép đầu tiên chạm cây: chỗ trống phải còn đúng là dãy chấm (hay
đúng `w:tab` mốc dẫn chấm) ở `[dau:cuoi]`, vật chứa không mang thứ mà phép sẽ phá
(hộp chữ, hình, trường, chú thích). Phép hỏng vào `bo_qua` với một mã của
`LyDoBoQua`; phép còn lại vẫn áp.

**Chỉ ghi lại part bị chạm.** Part bị sửa giữ nguyên khai báo XML và mọi khai báo
namespace (kể cả tiền tố chỉ `mc:Ignorable` nhắc tới — Word đòi, LibreOffice thì
không); các mục zip khác chép nguyên nội dung, đúng thứ tự, tên và kiểu nén.
Không phép nào áp được thì trả lại CHÍNH bytes vào.
"""

import re
import zipfile
import zlib
from bisect import bisect_left, bisect_right
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from typing import Any

from lxml import etree

from src.services.doc_tai_lieu import _NS, KhongDocDuoc, LoaiHong, _kiem_zip, _la_cham, _moc_tab, o_rong
from src.services.tai_lieu import _cho_trong_tu_hang, _dia_chi_tu_hang, _doan_chu_tu_hang, _so_tu_nhien

_W = f"{{{_NS['w']}}}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_KHOANG = "{http://www.w3.org/XML/1998/namespace}space"
_P, _TC, _R, _T, _TAB, _PPR, _RPR, _TCPR, _SECTPR, _BODY = (
    f"{_W}{x}" for x in ("p", "tc", "r", "t", "tab", "pPr", "rPr", "tcPr", "sectPr", "body")
)
_NGAT = (_TAB, f"{_W}br", f"{_W}cr")
_GOC = (f"{_W}document", f"{_W}hdr", f"{_W}ftr")
_HOP_CHU = (f"{_MC}AlternateContent", f"{_W}txbxContent")
# Thứ `thay`/`xoa` sẽ phá mà mô hình không thấy trong `noi_dung`: hình, đối tượng,
# nửa của một trường phức (`fldChar` có thể vắt qua nhiều đoạn), mốc chú thích và
# tham chiếu chú thích cuối trang — gỡ chúng là để lại tệp Word phải "sửa".
_MAT_KHI_THAY = (
    *_HOP_CHU,
    *(
        f"{_W}{x}"
        for x in (
            "drawing",
            "pict",
            "object",
            "fldChar",
            "commentRangeStart",
            "commentRangeEnd",
            "commentReference",
            "footnoteReference",
            "endnoteReference",
        )
    ),
)
_GIU_KHI_THAY = {_PPR, *(f"{_W}{x}" for x in ("bookmarkStart", "bookmarkEnd", "permStart", "permEnd"))}
# `thay` MỘT đoạn (`doan`) chỉ thay CHỮ của đoạn: hình không chữ (đường kẻ dưới tên
# cơ quan của BM.M05 là một `mc:AlternateContent` → `w:drawing`) ở nguyên chỗ.
# Hộp chữ, trường, chú thích thì vẫn từ chối như `thay` cả đơn vị.
_HINH = (f"{_MC}AlternateContent", *(f"{_W}{x}" for x in ("drawing", "pict", "object")))
_MAT_KHI_THAY_DOAN = tuple(x for x in _MAT_KHI_THAY if x not in _HINH)
# Gỡ khỏi bản CHÉP `w:pPr`/`w:rPr`: ngắt phân đoạn không được nhân lên, và dấu
# sửa đổi mang `w:id` phải duy nhất trong tệp.
_BO_KHI_CHEP = tuple(f"{_W}{x}" for x in ("sectPr", "pPrChange", "rPrChange", "ins", "del", "moveFrom", "moveTo"))
_LOAI = ("dien", "thay", "chen_sau", "xoa")
# Ký tự XML 1.0 không chở được, cộng các ký tự điều khiển; `\n` chỉ hợp lệ ở
# `thay`/`chen_sau`, nơi nó tách đoạn.
_KY_TU_CAM = re.compile("[\x00-\x09\x0b-\x1f\x7f\ud800-\udfff￾￿]")
_KHAI_XML = re.compile(rb"\A(?:\xef\xbb\xbf)?<\?xml[^>]*\?>\s*")
_MA_KHAC_UTF8 = re.compile(rb"encoding\s*=\s*[\"'](?!utf-8[\"'])", re.I)
_THE_MO = re.compile(rb"<[^?!][^>]*>")
_ZIP_HONG = (zipfile.BadZipFile, zlib.error, NotImplementedError, EOFError)


class LyDoBoQua(StrEnum):
    """Tập ĐÓNG mã lý do một phép bị bỏ (`bao_cao["bo_qua"][i]["ly_do"]`) — dùng
    CHUNG cho bộ áp DOCX (ở đây) và PDF (`dien_khuon_pdf`); hai mã cuối chỉ PDF
    phát ra."""

    khong_hop_le = "khong_hop_le"
    """Phép sai hình dạng: không phải dict, chỉ số không phải số tự nhiên, giá
    trị rỗng hay mang ký tự điều khiển (`\\n` trong `dien`)."""
    loai_khong_ho_tro = "loai_khong_ho_tro"
    """`loai` lạ; với PDF cả `chen_sau`/`xoa` — PDF chỉ nhận `dien`, `thay`."""
    khong_co_don_vi = "khong_co_don_vi"
    khong_co_dia_chi = "khong_co_dia_chi"
    """DOCX: đơn vị không có `dia_chi`, hoặc địa chỉ không giải ra đúng
    `w:p`/`w:tc`. PDF: đơn vị không có `hop` (`thay`), hoặc hộp/trang không
    thuộc tệp này."""
    khong_co_cho_trong = "khong_co_cho_trong"
    cho_trong_da_doi = "cho_trong_da_doi"
    """`[dau:cuoi]` trên chuỗi thô không còn là một dãy chấm (hoặc vắt qua một
    `w:tab`/`w:br`), hay không còn `w:tab` mốc dẫn chấm ở đó; ô của chỗ `o` không
    còn rỗng (`doc_tai_lieu.o_rong`)."""
    khong_an_toan = "khong_an_toan"
    """Vật chứa nằm trong/chứa hộp chữ; hoặc `thay`/`xoa` sẽ phá thứ nằm ngoài
    `noi_dung` (`_MAT_KHI_THAY`), hay `xoa` một đoạn mang ngắt phân đoạn."""
    xung_dot = "xung_dot"
    """`thay`/`xoa` thứ hai trên cùng đơn vị (hay cùng đoạn, với `thay` theo
    `doan`; cả đơn vị và theo đoạn trên cùng đơn vị cũng vậy), `dien` trên đơn vị
    đã bị `thay`/`xoa` hay vào đoạn đã bị `thay`, hoặc `dien` lần hai vào cùng
    một chỗ trống. PDF: vùng vẽ chồng lên vùng của một phép ĐỨNG TRƯỚC đã nhận
    trên cùng trang — phép trước giữ chỗ."""
    khong_vua = "khong_vua"
    """PDF: chữ không vừa bề rộng hộp kể cả khi thu nhỏ tới 70 %."""
    khong_co_phong = "khong_co_phong"
    """PDF: không có phông tiếng Việt, hoặc phông không vẽ được một ký tự của giá trị."""


def ap_dung_docx(docx: bytes, don_vi: list[dict], phep_sua: list[dict]) -> tuple[bytes, dict]:
    """Áp `phep_sua` lên khuôn gốc `docx`, trả `(bytes mới, báo cáo)`.

    Báo cáo: `{"da_ap": [chỉ số phép đã áp], "bo_qua": [{"phep": i, "ly_do": mã}]}`.
    Zip hỏng (hay vượt trần zip bomb của bộ đọc) → `KhongDocDuoc(tep_hong)`."""
    if not phep_sua:
        return docx, {"da_ap": [], "bo_qua": []}
    try:
        with zipfile.ZipFile(BytesIO(docx)) as z:
            _kiem_zip(z)
            return _Khuon(z, don_vi).ap(phep_sua, docx)
    except _ZIP_HONG as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, "khuôn gốc không mở được như docx") from e


# Đích của mốc dò: `.invalid` không bao giờ phân giải (RFC 6761), và liên kết
# không bị LibreOffice tải (đo 2026-09-27, quyết định 2026-09-26 mục Tradeoffs).
O_URI = "https://klaw.invalid/o/"
# Nền mốc của chỗ `o` trên bản dò: đỏ `O_MAU_DO`, xanh lá + xanh lam là số đơn vị
# (`mau_o`). ponytail: một ô CỦA tài liệu tô đúng #01xxxx trùng mốc của đơn vị xxxx
# (chưa thấy ở biểu mẫu nào) — thêm kênh kiểm khi đo thấy.
O_MAU_DO = 1
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_HL = f"{_W}hyperlink"


def danh_dau_docx(docx: bytes, don_vi: list[dict], o: list[tuple[int, int]]) -> bytes:
    """Bản DÒ của khuôn gốc: ký tự của mỗi chỗ trống `(don_vi, so)` trong `o` —
    dãy chấm, hay `w:tab` của chỗ trống `tab` — tách vào run riêng (cùng `w:rPr`)
    và bọc trong một `w:hyperlink` trỏ tới `O_URI{don_vi}/{so}`. LibreOffice xuất
    mỗi liên kết thành một `/Link` có `/Rect` (`dung_trang.vi_tri_o`).

    Chuỗi thô, `dia_chi` và `[dau:cuoi]` không đổi, nên bộ áp đi lại đúng chỗ
    trống trên bản dò, và giá trị nó điền rơi vào run đầu của chỗ trống — trong
    liên kết. Chỗ trống bộ áp không tới (`_chuan_bi` bỏ), hay đã nằm trong một
    liên kết của tài liệu, không có mốc. Không mốc nào thì trả chính `docx`.

    Liên kết đổi cách LibreOffice ngắt dòng ở ranh giới của nó (đo trên BM.M05:
    "Khoa .……" xuống dòng khác), nên bản dò chỉ để ĐO, không để hiện.

    Chỗ `o` (ô rỗng, G5) không có ký tự nào để bọc, và mọi run chèn vào đoạn rỗng
    — NBSP, ZWSP, WJ, chữ ẩn, có hay không liên kết — làm hàng thấp đi (đo trên
    BM.M05, LibreOffice 26.2.4: dòng dưới bảng lên 1,4 pt sau bốn hàng). Nên ô được
    tô NỀN `mau_o(don_vi)` (`w:shd`): không đổi từ nào (0 hộp từ lệch trên BM.M05),
    và LibreOffice vẽ nền thành một hình chữ nhật đúng màu ấy (`dung_trang`)."""
    if not o:
        return docx
    try:
        with zipfile.ZipFile(BytesIO(docx)) as z:
            _kiem_zip(z)
            return _Khuon(z, don_vi).danh_dau(o, docx)
    except _ZIP_HONG as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, "khuôn gốc không mở được như docx") from e


@dataclass
class _Doan:
    """Một `w:p` thô như bộ đọc thấy (`_vi_tri_chu`/`_vi_tri_tab`), đo MỘT lần
    trên cây nguyên: offset đầu/cuối NGUYÊN của từng `w:t` — đủ để sửa từ phải
    sang trái mà không đo lại."""

    tho: str
    t: list[tuple[int, int, Any]]
    dau_t: list[int]
    tab: list[tuple[int, Any]]
    """`w:tab` rơi vào mốc dẫn chấm, theo thứ tự — đúng luật "tab thứ n → mốc n"."""
    tab_o: list[int]
    ngat: list[int]
    hop_chu: bool


@dataclass
class _Phep:
    i: int
    loai: str
    chi_so: int
    vat: Any
    phan: str
    gia_tri: str = ""
    dong: tuple[str, ...] = ()
    doan: _Doan | None = None
    dau: int = 0
    cuoi: int = 0
    tab: Any = None
    cho: tuple[int, int] = (0, 0)
    so_doan: int | None = None
    """Đoạn (thứ tự `vat.iter(w:p)`) một `dien` rơi vào, hay một `thay` theo đoạn thay."""
    p: Any = None
    """`w:p` của một `thay` theo đoạn; `None` với `thay` cả đơn vị."""
    o: Any = None
    """`w:p` đầu của ô rỗng mà một `dien` vào chỗ `o` chèn run vào."""
    rpr: Any = None
    """`w:rPr` của run đó: dấu đoạn của `o`, chụp trên cây nguyên (`_sach`)."""


class _Khuon:
    """Bộ nhớ đệm của MỘT lần áp: part đã mở, vật chứa, đoạn đã đo, mẫu định dạng."""

    def __init__(self, z: zipfile.ZipFile, don_vi: list[dict]) -> None:
        self.z = z
        self.hang = {d["chi_so"]: d for d in don_vi if isinstance(d, dict) and _so_tu_nhien(d.get("chi_so"))}
        self.cay: dict[str, Any] = {}
        self.vi: dict[int, tuple[str, Any] | LyDoBoQua] = {}
        self.doan: dict[Any, _Doan] = {}
        self.ds: dict[Any, list] = {}
        self.cho: dict[int, tuple[dict, dict]] = {}
        self.mau: dict[Any, tuple[Any, Any]] = {}

    # ─── giải ───────────────────────────────────────────────────────────

    def _goc(self, phan: str) -> Any:
        if phan not in self.cay:
            try:
                goc = etree.fromstring(self.z.read(phan), etree.XMLParser(resolve_entities=False, no_network=True))
            except (KeyError, etree.XMLSyntaxError):
                goc = None
            self.cay[phan] = goc if goc is not None and goc.tag in _GOC else None
        return self.cay[phan]

    def _vat(self, hang: dict) -> tuple[str, Any] | LyDoBoQua:
        dc = _dia_chi_tu_hang(hang.get("dia_chi"))
        goc = self._goc(dc.phan) if dc else None
        nut = goc.find(_BODY) if goc is not None and goc.tag == _GOC[0] else goc
        for i in dc.chi_muc if nut is not None else ():
            con = [c for c in nut if isinstance(c.tag, str)]
            if i >= len(con):
                return LyDoBoQua.khong_co_dia_chi
            nut = con[i]
        if nut is None or nut.tag != (_TC if hang.get("bang") else _P):
            return LyDoBoQua.khong_co_dia_chi
        if any(a.tag in _HOP_CHU for a in nut.iterancestors()):
            return LyDoBoQua.khong_an_toan
        return dc.phan, nut

    def _do_doan(self, p: Any) -> _Doan:
        if p not in self.doan:
            t, tab, ngat, n = [], [], [], 0
            for con in p:
                if con.tag == _PPR or not isinstance(con.tag, str):
                    continue
                for e in con.iter(_T, *_NGAT):
                    if e.tag == _T:
                        s = e.text or ""
                        t.append((n, n + len(s), e))
                        n += len(s)
                    else:
                        ngat.append(n)
                        if e.tag == _TAB:
                            tab.append((n, e))
            moc = _moc_tab(p.find(f"{_PPR}/{_W}tabs"))[0]
            cham = [x for k, x in enumerate(tab) if k < len(moc) and moc[k].leader == "dot"]
            hop = any(a.tag in _HOP_CHU for a in p.iterancestors()) or next(p.iter(*_HOP_CHU), None) is not None
            self.doan[p] = _Doan(
                tho="".join(e.text or "" for *_, e in t),
                t=t,
                dau_t=[a for a, _, _ in t],
                tab=cham,
                tab_o=[o for o, _ in cham],
                ngat=ngat,
                hop_chu=hop,
            )
        return self.doan[p]

    def _cho_trong(self, chi_so: int) -> tuple[dict, dict]:
        """`so` → chỗ trống DOCX của đơn vị, và `so` → hạng của một chỗ `tab`
        giữa các chỗ `tab` CÙNG đoạn, CÙNG offset (hai `w:tab` liền nhau)."""
        if chi_so not in self.cho:
            cho = {c.so: c for c in _cho_trong_tu_hang(self.hang[chi_so].get("cho_trong")) if c.hop is None}
            dem: dict[tuple[int, int], int] = {}
            hang_tab = {}
            for so in sorted(k for k, c in cho.items() if c.kieu == "tab"):
                k = (cho[so].doan, cho[so].dau)
                hang_tab[so] = dem.get(k, 0)
                dem[k] = hang_tab[so] + 1
            self.cho[chi_so] = (cho, hang_tab)
        return self.cho[chi_so]

    def _chuan_bi(self, i: int, phep: Any) -> _Phep | LyDoBoQua:
        if (ly_do := _kiem_hinh(phep)) is not None:
            return ly_do
        loai, chi_so = phep["loai"], phep["don_vi"]
        if chi_so not in self.hang:
            return LyDoBoQua.khong_co_don_vi
        if chi_so not in self.vi:
            self.vi[chi_so] = self._vat(self.hang[chi_so])
        vat = self.vi[chi_so]
        if isinstance(vat, LyDoBoQua):
            return vat
        phan, vat = vat
        if loai == "thay" and phep.get("doan") is not None:
            return self._chuan_bi_doan(i, chi_so, vat, phan, phep)
        if loai != "dien":
            if next(vat.iter(*(_HOP_CHU if loai == "chen_sau" else _MAT_KHI_THAY)), None) is not None:
                return LyDoBoQua.khong_an_toan
            if loai == "xoa" and vat.find(f"{_PPR}/{_SECTPR}") is not None:
                return LyDoBoQua.khong_an_toan
            if vat not in self.mau:  # chụp TRƯỚC mọi phép: mẫu luôn lấy từ cây nguyên
                self.mau[vat] = _mau(vat)
            # `xoa` không đọc `noi_dung`: `_kiem_hinh` không kiểm nó ở đó.
            dong = () if loai == "xoa" else tuple(phep["noi_dung"].split("\n"))
            return _Phep(i, loai, chi_so, vat, phan, dong=dong)

        cho, hang_tab = self._cho_trong(chi_so)
        c = cho.get(phep["cho_trong"])
        if c is None:
            return LyDoBoQua.khong_co_cho_trong
        if c.kieu == "o":
            # Ô rỗng (G5): kiểm lại trên cây nguyên — ô vẫn rỗng, vẫn an toàn — rồi
            # giá trị là MỘT run mới cuối đoạn đầu, định dạng của dấu đoạn đó (thứ
            # Word dùng khi gõ vào đoạn rỗng); không dấu đoạn thì theo kiểu đoạn/bảng.
            if vat.tag != _TC or not o_rong(vat):
                return LyDoBoQua.cho_trong_da_doi
            p = next(vat.iter(_P))
            rpr = _sach(p.find(f"{_PPR}/{_RPR}"))
            return _Phep(i, loai, chi_so, vat, phan, phep["gia_tri"], cho=(chi_so, c.so), so_doan=0, o=p, rpr=rpr)
        if vat not in self.ds:
            self.ds[vat] = list(vat.iter(_P))
        ds = self.ds[vat]
        if c.doan >= len(ds):
            return LyDoBoQua.cho_trong_da_doi
        d = self._do_doan(ds[c.doan])
        if d.hop_chu:
            return LyDoBoQua.khong_an_toan
        ra = _Phep(
            i,
            loai,
            chi_so,
            vat,
            phan,
            gia_tri=phep["gia_tri"],
            doan=d,
            dau=c.dau,
            cuoi=c.cuoi,
            cho=(chi_so, c.so),
            so_doan=c.doan,
        )
        if c.kieu == "cham":
            k = bisect_right(d.ngat, c.dau)
            vat_qua_ngat = k < len(d.ngat) and d.ngat[k] < c.cuoi
            if c.cuoi > len(d.tho) or not _la_cham(d.tho[c.dau : c.cuoi]) or vat_qua_ngat:
                return LyDoBoQua.cho_trong_da_doi
            return ra
        k = bisect_left(d.tab_o, c.dau) + hang_tab[c.so]
        if k >= len(d.tab_o) or d.tab_o[k] != c.dau or d.tab[k][1].getparent().tag != _R:
            return LyDoBoQua.cho_trong_da_doi
        ra.tab = d.tab[k][1]
        return ra

    def _chuan_bi_doan(self, i: int, chi_so: int, vat: Any, phan: str, phep: dict) -> _Phep | LyDoBoQua:
        """`thay` MỘT đoạn: đoạn thứ `doan` của `vat.iter(w:p)` THÔ (cùng thứ tự
        `ChoTrong.doan`). Từ chối đoạn trong/chứa hộp chữ, trường hay chú thích,
        và chữ nằm trong một hình — thứ sẽ mất mà mô hình không thấy.

        Số đoạn đã lưu (`doan_chu`; không có = một đoạn) phải bằng số `w:p` của
        vật chứa: dòng lưu TRƯỚC `doan_chu` có ô nhiều đoạn mà phép kiểm coi là
        một đoạn, và `w:p` thô số 0 của ô ấy có thể là một đoạn rỗng."""
        if vat not in self.ds:
            self.ds[vat] = list(vat.iter(_P))
        so, luu = phep["doan"], len(_doan_chu_tu_hang(self.hang[chi_so].get("doan_chu"))) or 1
        if so >= len(self.ds[vat]) or luu != len(self.ds[vat]):
            return LyDoBoQua.khong_co_dia_chi
        p = self.ds[vat][so]
        if (
            any(a.tag in _HOP_CHU for a in p.iterancestors())
            or next(p.iter(*_MAT_KHI_THAY_DOAN), None) is not None
            or any(next(t.iterancestors(*_HINH), None) is not None for t in p.iter(_T))
        ):
            return LyDoBoQua.khong_an_toan
        if p not in self.mau:  # chụp TRƯỚC mọi phép, như `thay` cả đơn vị
            self.mau[p] = _mau(p)
        return _Phep(i, "thay", chi_so, vat, phan, dong=(phep["noi_dung"],), so_doan=so, p=p)

    # ─── áp ─────────────────────────────────────────────────────────────

    def ap(self, phep_sua: list, docx: bytes) -> tuple[bytes, dict]:
        bo_qua: dict[int, LyDoBoQua] = {}
        hop_le: list[_Phep] = []
        for i, phep in enumerate(phep_sua):
            x = self._chuan_bi(i, phep)
            if isinstance(x, LyDoBoQua):
                bo_qua[i] = x
            else:
                hop_le.append(x)

        # Xung đột: `thay`/`xoa` ĐẦU TIÊN của một vật chứa (hay của một đoạn, với
        # `thay` theo `doan`) thắng; `dien` lên vật chứa/đoạn ấy, hay lần hai vào
        # cùng một chỗ trống, bị bỏ. Cả vật chứa và theo đoạn cũng xung đột nhau.
        doi: dict[Any, _Phep] = {}
        doi_doan: set[tuple[Any, int | None]] = set()
        co_doan: set[Any] = set()
        for x in hop_le:
            if x.loai not in ("thay", "xoa"):
                continue
            if x.vat in doi or (x.p is None and x.vat in co_doan) or (x.vat, x.so_doan) in doi_doan:
                bo_qua[x.i] = LyDoBoQua.xung_dot
            elif x.p is None:
                doi[x.vat] = x
            else:
                doi_doan.add((x.vat, x.so_doan))
                co_doan.add(x.vat)
        da_dien: set[tuple[int, int]] = set()
        for x in hop_le:
            if x.loai == "dien" and (x.vat in doi or (x.vat, x.so_doan) in doi_doan or x.cho in da_dien):
                bo_qua[x.i] = LyDoBoQua.xung_dot
            elif x.loai == "dien":
                da_dien.add(x.cho)
        chay = [x for x in hop_le if x.i not in bo_qua]
        if not chay:
            return docx, _bao_cao([], bo_qua)

        dien = [x for x in chay if x.loai == "dien"]
        # Phải → trái: một `w:t` mang hai chỗ trống vẫn đúng offset NGUYÊN của chỗ
        # bên trái. `tab` chèn theo phần tử, sau cùng, không chạm chữ của `w:t` nào.
        for x in sorted((x for x in dien if x.tab is None and x.o is None), key=lambda x: -x.dau):
            _dien_cham(x.doan, x.dau, x.cuoi, x.gia_tri)
        for x in dien:
            if x.tab is not None:
                x.tab.addprevious(_t_moi(x.gia_tri))
            elif x.o is not None:
                x.o.append(_run_moi(x.gia_tri, x.rpr))
        for x in chay:
            if x.p is not None:
                _thay_doan(x.p, x.dong[0], self.mau[x.p][1])

        theo_vat: dict[Any, list[_Phep]] = {}
        for x in chay:
            if x.loai != "dien" and x.p is None:
                theo_vat.setdefault(x.vat, []).append(x)
        for vat, ds in theo_vat.items():
            _cau_truc(vat, ds, *self.mau[vat])

        sua = {x.phan for x in chay}
        return _dong_goi(self.z, {phan: _xml(self.cay[phan], self.z.read(phan)) for phan in sua}), _bao_cao(
            [x.i for x in chay], bo_qua
        )

    def danh_dau(self, o: list[tuple[int, int]], docx: bytes) -> bytes:
        """Xem `danh_dau_docx`. Giải MỌI chỗ trống trên cây nguyên như `ap`, rồi
        tách phải → trái: phần trái của một `w:t` bị tách giữ nguyên phần tử và
        offset, nên chỗ trống bên trái cùng `w:t` vẫn đúng."""
        chon = []
        for i, (d, so) in enumerate(o):
            x = self._chuan_bi(i, {"loai": "dien", "don_vi": d, "cho_trong": so, "gia_tri": "x"})
            if not isinstance(x, LyDoBoQua):
                chon.append(x)
        moc: dict[str, list[tuple[str, str]]] = {}
        to: set[str] = set()
        for x in sorted(chon, key=lambda x: -x.dau):
            if x.o is not None:
                if x.cho[1] == 0 and x.cho[0] <= 0xFFFF:
                    _to_nen(x.vat, mau_o(x.cho[0]))
                    to.add(x.phan)
                continue
            if x.tab is not None:
                ky_tu = [x.tab]
            else:
                ky_tu = []
                for a, b, t in x.doan.t:
                    if b <= x.dau or a >= x.cuoi:
                        continue
                    if b > x.cuoi:
                        _tach_t(t, x.cuoi - a)
                    ky_tu.append(_tach_t(t, x.dau - a) if a < x.dau else t)
            rid = f"rIdKlawO{x.cho[0]}_{x.cho[1]}"
            run = [r for e in ky_tu if (r := _run_rieng(e)) is not None]
            for r in run:
                hl = r.makeelement(_HL, {f"{{{_R_NS}}}id": rid})
                r.addprevious(hl)
                hl.append(r)
            if run:
                moc.setdefault(x.phan, []).append((rid, f"{O_URI}{x.cho[0]}/{x.cho[1]}"))
        if not moc and not to:
            return docx
        sua = {phan: _xml(self.cay[phan], self.z.read(phan)) for phan in {*moc, *to}}
        them = {}
        for phan, lien_ket in moc.items():
            thu_muc, ten = phan.rsplit("/", 1)
            ten_rels = f"{thu_muc}/_rels/{ten}.rels"
            nguon = self.z.read(ten_rels) if ten_rels in self.z.namelist() else None
            try:
                goc = (
                    etree.fromstring(nguon, etree.XMLParser(resolve_entities=False, no_network=True)) if nguon else None
                )
            except etree.XMLSyntaxError:
                del sua[phan]  # rels hỏng: part đó không mốc — ô của nó "chưa định vị"
                continue
            if goc is None:
                goc = etree.Element(f"{{{_PKG_NS}}}Relationships", nsmap={None: _PKG_NS})
            for rid, dich in lien_ket:
                etree.SubElement(
                    goc,
                    f"{{{_PKG_NS}}}Relationship",
                    {"Id": rid, "Type": f"{_R_NS}/hyperlink", "Target": dich, "TargetMode": "External"},
                )
            if nguon:
                sua[ten_rels] = _xml(goc, nguon)
            else:
                them[ten_rels] = etree.tostring(goc, xml_declaration=True, encoding="UTF-8", standalone=True)
        return _dong_goi(self.z, sua, them)


def _bao_cao(da_ap: list[int], bo_qua: dict[int, LyDoBoQua]) -> dict:
    return {"da_ap": sorted(da_ap), "bo_qua": [{"phep": i, "ly_do": str(v)} for i, v in sorted(bo_qua.items())]}


def _chu_hop_le(s: Any, mot_dong: bool = False) -> bool:
    return isinstance(s, str) and bool(s.strip()) and not _KY_TU_CAM.search(s) and not (mot_dong and "\n" in s)


def _kiem_hinh(phep: Any) -> LyDoBoQua | None:
    if not isinstance(phep, dict):
        return LyDoBoQua.khong_hop_le
    loai = phep.get("loai")
    if loai not in _LOAI:
        return LyDoBoQua.loai_khong_ho_tro
    if not _so_tu_nhien(phep.get("don_vi")):
        return LyDoBoQua.khong_hop_le
    if loai == "dien":
        ok = _so_tu_nhien(phep.get("cho_trong")) and _chu_hop_le(phep.get("gia_tri"), mot_dong=True)
    elif loai == "thay" and phep.get("doan") is not None:
        # Một đoạn là MỘT dòng: nhiều dòng thì chỉ số các đoạn sau trong ô lệch đi.
        ok = _so_tu_nhien(phep["doan"]) and _chu_hop_le(phep.get("noi_dung"), mot_dong=True)
    else:
        ok = loai == "xoa" or _chu_hop_le(phep.get("noi_dung"))
    return None if ok else LyDoBoQua.khong_hop_le


# ─── sửa cây ────────────────────────────────────────────────────────────────


def _khoang(t: Any) -> None:
    s = t.text or ""
    if s[:1].isspace() or s[-1:].isspace():
        t.set(_KHOANG, "preserve")


def _t_moi(chu: str) -> Any:
    t = etree.Element(_T)
    t.text = chu
    _khoang(t)
    return t


def _dien_cham(d: _Doan, dau: int, cuoi: int, gia_tri: str) -> None:
    """Thay đúng ký tự `[dau, cuoi)` của chuỗi thô, có thể vắt qua nhiều
    `w:t`/`w:r`: giá trị vào `w:t` ĐẦU (định dạng của run đó), `w:t` rỗng ra
    bị gỡ, run chỉ còn `w:rPr` bị gỡ theo — run còn mang thứ khác thì giữ."""
    j = max(bisect_right(d.dau_t, dau) - 1, 0)
    chon = []
    while j < len(d.t) and d.t[j][0] < cuoi:
        if d.t[j][1] > dau:
            chon.append(d.t[j])
        j += 1
    (a0, b0, t0), *sau = chon
    s = t0.text or ""
    t0.text = s[: dau - a0] + gia_tri + (s[cuoi - a0 :] if cuoi < b0 else "")
    _khoang(t0)
    for a, b, t in sau:
        t.text = (t.text or "")[cuoi - a :] if cuoi < b else ""
        if t.text:
            _khoang(t)
            continue
        r = t.getparent()
        r.remove(t)
        if r.tag == _R and all(c.tag == _RPR for c in r if isinstance(c.tag, str)):
            r.getparent().remove(r)


def _thay_doan(p: Any, chu: str, rpr: Any) -> None:
    """`thay` MỘT đoạn: gỡ mọi con mang chữ của `p` — giữ `w:pPr` của CHÍNH đoạn
    này, dấu trang/vùng quyền (`_GIU_KHI_THAY`), và con mang hình (`_HINH`, chỉ bỏ
    chữ/tab/ngắt của nó) — rồi đặt MỘT run `chu` với `w:rPr` của run mang chữ đầu
    tiên của đoạn, đúng chỗ con mang chữ đầu tiên đứng."""
    cho = None
    for c in list(p):
        if not isinstance(c.tag, str) or c.tag in _GIU_KHI_THAY:
            continue
        if next(c.iter(*_HINH), None) is not None:
            for e in list(c.iter(_T, *_NGAT)):
                e.getparent().remove(e)
            continue
        if cho is None:
            cho = p.index(c)
        p.remove(c)
    r = _run_moi(chu, rpr)
    if cho is None:
        p.append(r)
    else:
        p.insert(cho, r)


def _tach_t(t: Any, k: int) -> Any:
    """Tách `w:t` tại ký tự `k`: `t` giữ phần trái, phần phải là một `w:t` mới
    ngay sau nó, cùng run — trả phần phải."""
    s = t.text or ""
    t.text = s[:k]
    _khoang(t)
    moi = _t_moi(s[k:])
    t.addnext(moi)
    return moi


def _run_rieng(e: Any) -> Any:
    """Run chỉ chứa `e` (một `w:t`/`w:tab`), cùng `w:rPr`: phần tử đứng trước và
    sau nó trong run cũ sang run anh em mới. `None` khi `e` không trong `w:r`
    hay đã trong một `w:hyperlink` — liên kết lồng nhau không hợp lệ. Run cùng
    `w:rPr` không đổi dàn trang (đo pixel trên tám biểu mẫu, 2026-09-27)."""
    r = e.getparent()
    if r is None or r.tag != _R or next(r.iterancestors(_HL), None) is not None:
        return None
    rpr = r.find(_RPR)

    def _anh_em() -> Any:
        moi = r.makeelement(_R, {})
        if rpr is not None:
            moi.append(deepcopy(rpr))
        return moi

    sau = list(e.itersiblings())
    if sau:
        r2 = _anh_em()
        r2.extend(sau)
        r.addnext(r2)
    if any(isinstance(c.tag, str) and c.tag != _RPR for c in e.itersiblings(preceding=True)):
        r1 = _anh_em()
        r.addnext(r1)
        r1.append(e)
        return r1
    return r


def mau_o(don_vi: int) -> str:
    """Màu nền mốc (hex `RRGGBB`) của chỗ `o` của đơn vị `don_vi` ≤ 0xFFFF."""
    return f"{O_MAU_DO:02X}{don_vi:04X}"


# Con của `w:tcPr` đứng SAU `w:shd` trong lược đồ CT_TcPr (ECMA-376 §17.4.70).
_SAU_SHD = {
    f"{_W}{x}"
    for x in ("noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark", "headers")
    + ("cellIns", "cellDel", "cellMerge", "tcPrChange")
}


def _to_nen(tc: Any, mau: str) -> None:
    """Nền đặc `mau` cho ô `tc` (thay nền cũ của nó) — chỉ trên bản DÒ."""
    tcpr = tc.find(_TCPR)
    if tcpr is None:
        tcpr = tc.makeelement(_TCPR, {})
        tc.insert(0, tcpr)
    for cu in tcpr.findall(f"{_W}shd"):
        tcpr.remove(cu)
    shd = tcpr.makeelement(f"{_W}shd", {f"{_W}val": "clear", f"{_W}color": "auto", f"{_W}fill": mau})
    sau = next((c for c in tcpr if c.tag in _SAU_SHD), None)
    if sau is None:
        tcpr.append(shd)
    else:
        sau.addprevious(shd)


def _sach(e: Any) -> Any:
    if e is None:
        return None
    ban = deepcopy(e)
    for x in list(ban.iter(*_BO_KHI_CHEP)):
        x.getparent().remove(x)
    return ban


def _mau(vat: Any) -> tuple[Any, Any]:
    """`(w:pPr, w:rPr)` MẪU của một vật chứa: `w:rPr` của run ĐẦU MANG CHỮ ở BẤT
    KỲ đoạn nào (lùi về run đầu) và `w:pPr` của đoạn chứa run ấy — một run chỉ
    chứa `w:tab` hay dấu trường không nói chữ trông thế nào, và ô "Ghi chú" của
    BM.M05 mở bằng một đoạn rỗng. Không có run: định dạng dấu đoạn của đoạn đầu,
    thứ Word dùng khi gõ vào đoạn rỗng."""
    p0 = vat if vat.tag == _P else next(vat.iter(_P), None)
    if p0 is None:
        return None, None
    run = list(vat.iter(_R))
    r0 = next((r for r in run if any(t.text for t in r.iter(_T))), run[0] if run else None)
    if r0 is None:
        return _sach(p0.find(_PPR)), _sach(p0.find(f"{_PPR}/{_RPR}"))
    return _sach(next(r0.iterancestors(_P), p0).find(_PPR)), _sach(r0.find(_RPR))


def _run_moi(chu: str, rpr: Any) -> Any:
    r = etree.Element(_R)
    if rpr is not None:
        r.append(deepcopy(rpr))
    r.append(_t_moi(chu))
    return r


def _doan_moi(chu: str, ppr: Any, rpr: Any) -> Any:
    p = etree.Element(_P)
    if ppr is not None:
        p.append(deepcopy(ppr))
    if chu:
        p.append(_run_moi(chu, rpr))
    return p


def _ket_bang_doan(cha: Any, ppr: Any) -> None:
    """Ô bảng, đầu/chân trang (và thân bài) phải kết bằng một `w:p` — Word báo
    tệp hỏng khi một ô không còn đoạn nào."""
    khoi = [c for c in cha if isinstance(c.tag, str) and c.tag not in (_TCPR, _SECTPR)]
    if khoi and khoi[-1].tag == _P:
        return
    q = _doan_moi("", ppr, None)
    sect = cha.find(_SECTPR) if cha.tag == _BODY else None
    if sect is not None:
        sect.addprevious(q)
    else:
        cha.append(q)


def _cau_truc(vat: Any, ds: list[_Phep], ppr: Any, rpr: Any) -> None:
    """`thay` → `xoa` một ô → `chen_sau` theo thứ tự phép → `xoa` một đoạn. `xoa`
    đoạn đi SAU `chen_sau` để đoạn chèn đứng đúng chỗ đoạn cũ."""
    o = vat.tag == _TC
    thay = next((x for x in ds if x.loai == "thay"), None)
    xoa = any(x.loai == "xoa" for x in ds)
    duoi = vat
    if thay is not None and o:
        for c in [c for c in vat if c.tag != _TCPR]:
            vat.remove(c)
        for s in thay.dong:
            vat.append(_doan_moi(s, ppr, rpr))
    elif thay is not None:
        for c in [c for c in vat if c.tag not in _GIU_KHI_THAY]:
            vat.remove(c)
        vat.append(_run_moi(thay.dong[0], rpr))
        for s in thay.dong[1:]:
            q = _doan_moi(s, ppr, rpr)
            duoi.addnext(q)
            duoi = q
        # Ngắt phân đoạn thuộc đoạn CUỐI của phân đoạn: đi theo dòng cuối.
        if duoi is not vat and (sect := vat.find(f"{_PPR}/{_SECTPR}")) is not None:
            duoi.find(_PPR).append(sect)
    if xoa and o:
        for c in [c for c in vat if c.tag != _TCPR]:
            vat.remove(c)
        _ket_bang_doan(vat, ppr)
    for x in ds:
        if x.loai != "chen_sau":
            continue
        for s in x.dong:
            q = _doan_moi(s, ppr, rpr)
            if o:
                vat.append(q)
            else:
                duoi.addnext(q)
                duoi = q
    if xoa and not o:
        cha = vat.getparent()
        cha.remove(vat)
        _ket_bang_doan(cha, ppr)


# ─── ghi lại ────────────────────────────────────────────────────────────────


def _xml(goc: Any, nguon: bytes) -> bytes:
    """Part đã sửa: khai báo XML và thẻ mở gốc NGUYÊN VĂN của nguồn (UTF-8).

    lxml viết mọi khai báo namespace TRƯỚC thuộc tính, còn Word có thể xen kẽ
    (BM.ĐT.18.11: `mc:Ignorable` đứng giữa các `xmlns:`). Bộ áp không bao giờ
    thêm khai báo nào lên gốc, nên thẻ lxml viết ra là CÙNG các byte, khác thứ
    tự — khi đúng vậy thì dán lại thẻ nguồn, như kế hoạch hứa ("keeps the root
    start tag verbatim"); khác thì giữ bản lxml, vẫn là XML đúng."""
    m = _KHAI_XML.match(nguon)
    if m and not _MA_KHAC_UTF8.search(m[0]):
        dau = m[0]
    else:
        dau = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
            if goc.getroottree().docinfo.standalone
            else b""
        )
    ra = etree.tostring(goc.getroottree(), encoding="UTF-8", xml_declaration=False)
    a, b = _THE_MO.search(nguon), _THE_MO.search(ra)
    if a and b and sorted(a[0]) == sorted(b[0]):
        ra = ra[: b.start()] + a[0] + ra[b.end() :]
    return dau + ra


def _dong_goi(z: zipfile.ZipFile, sua: dict[str, bytes], them: dict[str, bytes] | None = None) -> bytes:
    """Zip mới: đúng thứ tự, tên, kiểu nén, giờ và thuộc tính của từng mục; mục
    không sửa mang NGUYÊN nội dung (luồng nén thì dựng lại — `zipfile` không có
    phép chép thô). `them`: mục mới nối vào cuối (rels mới của bản dò)."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as ra:
        for m in z.infolist():
            moi = zipfile.ZipInfo(m.filename, m.date_time)
            moi.compress_type, moi.external_attr, moi.create_system = m.compress_type, m.external_attr, m.create_system
            ra.writestr(moi, sua[m.filename] if m.filename in sua else z.read(m))
        for ten, du_lieu in (them or {}).items():
            ra.writestr(ten, du_lieu)
        ra.comment = z.comment
    return buf.getvalue()
