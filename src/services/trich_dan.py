"""Trích dẫn đầy đủ — quyết định 2026-09-28
(`docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`).

MỘT chỗ dựng mọi trường trích dẫn đi ra giao diện (citation của câu trả lời,
nguồn của `partial_coverage`, `documents[]`, metadata trang văn bản) và khối
"Căn cứ" của bản thảo — để câu "khoản 1 Điều 3 Nghị định số 90/2019/NĐ-CP ngày
15/11/2019 của Chính phủ" chỉ có một cách viết.

Hàm THUẦN, không DB: người gọi đưa dòng `documents` đã đọc. NULL là KHÔNG BIẾT,
nên phần nào NULL thì câu bỏ phần đó — không bao giờ in một chỗ trống hay một
link giữ chỗ.

Ngày ở đây là DỮ KIỆN của văn bản, không phải phán quyết: nhãn hiệu lực cạnh
trích dẫn (`effectivity.py`) vẫn là nơi duy nhất KLAW nói về hiệu lực.
"""

import html
import re
from collections.abc import Callable, Iterable
from datetime import date
from urllib.parse import urlparse

from src.services.effectivity import EffectivityVerdict as V
from src.services.kho import hien_van_ban

# Loại văn bản gọi bằng TÊN ("Bộ luật Lao động số 45/2019/QH14"); mọi loại khác
# gọi bằng số hiệu ("Nghị định số 90/2019/NĐ-CP"), cùng cách văn bản luật tự dẫn.
_LOAI_CO_TEN = ("Hiến pháp", "Bộ luật", "Luật", "Pháp lệnh")

# Cấp đứng TRÊN hoặc NGANG Điều giữ chữ hoa ("Điều 21", "Chương II", "Mục 3");
# khoản, điểm và hàng bảng viết thường ("điểm a khoản 1 Điều 21", "vùng III").
_CAP_VIET_HOA = ("Điều ", "Chương ", "Mục ", "Tiểu mục ", "Phần ", "Phụ lục")

# Thứ bậc hiệu lực pháp lý cho thứ tự dòng "Căn cứ"; loại khác đứng sau cùng.
_THU_BAC = {"Hiến pháp": 0, "Bộ luật": 1, "Luật": 1, "Nghị định": 2, "Thông tư": 3}

# Văn bản chỉ quy định THỂ THỨC (cách trình bày), không bao giờ là căn cứ ban hành
# của khối "Căn cứ": NĐ 30/2020 về công tác văn thư. Checklist dẫn nó cho quốc
# hiệu, số ký hiệu, nơi nhận (checklist_cong_van.yaml mục 1: "không quy định
# nghiệp vụ"), Đ2.1 của nó không với tới doanh nghiệp tư nhân, và in nó thành căn
# cứ là bịa căn cứ ban hành (checklist_quyet_dinh_bo_nhiem.yaml mục 6).
_CHI_THE_THUC = frozenset({"30/2020/NĐ-CP"})

# "Còn hiệu lực" cho khối "Căn cứ": văn bản vẫn sống, kể cả khi một phần đã bị
# sửa hay hết hiệu lực (Bộ luật Lao động 45/2019 là `mot_phan_khong_xac_dinh`).
# Không gồm `chua_xac_dinh`/`can_doi_chieu_tay`: chưa kiểm được thì không dẫn.
CON_HIEU_LUC = frozenset({V.con_hieu_luc, V.bi_sua_doi, V.mot_phan_khong_xac_dinh})

# Link đọc được của từng cột (migration 019): đúng host, đúng https, và với
# vbpl.vn đúng mẫu `/van-ban/chi-tiet/{id}` — mẫu cũ `vbpq-toanvan.aspx`
# chuyển hướng về trang chủ, tức một link hỏng trông như link thật.
_HOST_LINK = (("vbpl.vn", "/van-ban/chi-tiet/"), ("vanban.chinhphu.vn", "/"))


def _ngay(d: date | str | None) -> date | None:
    if d is None or isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def _viet_hoa_dau(s: str) -> str:
    return s[:1].upper() + s[1:]


def _viet_thuong_dau(s: str) -> str:
    return s[:1].lower() + s[1:]


def _phan_sau_so(loai: str, so_tho: str, ten: str) -> str:
    """Phần của `ten` còn lại sau khi bỏ tên loại và số hiệu: tên riêng của một
    luật ("lao động"), hay trích yếu của một nghị định ("Quy định mức lương…")."""
    t = html.unescape(ten)
    if so_tho:
        # Không phân biệt hoa thường: tên trong kho có dạng "LUẬT DÂN SỐ SỐ 113/2025/QH15".
        t = re.sub(rf"\s*(?:số\s+)?{re.escape(so_tho)}", " ", t, count=1, flags=re.IGNORECASE)
    t = " ".join(t.split())
    if loai and t.lower().startswith(loai.lower()):
        t = t[len(loai) :]
    return t.strip(" .;")


def _ten_goi(loai: str, so_tho: str, ten: str) -> str:
    """ "Bộ luật Lao động số 45/2019/QH14" / "Nghị định số 90/2019/NĐ-CP"."""
    so, ten = hien_van_ban(so_tho, ten)
    if loai == "Hiến pháp":  # không có số hiệu; văn bản luật gọi bằng tên ("Hiến pháp năm 2013")
        return html.unescape(ten)
    if so and loai and loai not in _LOAI_CO_TEN:
        return f"{loai} số {so}"
    rieng = _phan_sau_so(loai, so_tho, ten)
    if rieng.isupper():
        rieng = rieng.capitalize()
    goi = " ".join(x for x in (loai, _viet_hoa_dau(rieng)) if x)
    return f"{goi} số {so}" if so else goi


def _vi_tri(duong_dan: str | None) -> str:
    """`"45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a"` → `"điểm a khoản 1 Điều 21"`.
    Đoạn đầu của `duong_dan` luôn là số hiệu văn bản, không phải một vị trí."""
    phan = [p.strip() for p in (duong_dan or "").split(" > ")[1:]]
    return " ".join(
        p if p.startswith(_CAP_VIET_HOA) else _viet_thuong_dau(p) for p in reversed(phan) if p and p != "Mở đầu"
    )


def cach_trich(
    duong_dan: str | None,
    loai: str | None,
    so_ky_hieu: str | None,
    ngay_ban_hanh: date | str | None,
    co_quan: str | None,
    ten: str | None,
) -> str | None:
    """Câu trích theo cách chính văn bản luật viết: "khoản 1 Điều 3 Nghị định số
    90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ". `ten` cần cho loại gọi bằng tên
    (luật, bộ luật). `None` khi không có gì để trích."""
    goi = _ten_goi(loai or "", so_ky_hieu or "", ten or "")
    ngay = _ngay(ngay_ban_hanh)
    cau = " ".join(
        x
        for x in (
            _vi_tri(duong_dan),
            goi,
            f"ngày {ngay:%d/%m/%Y}" if ngay else "",
            f"của {co_quan}" if co_quan else "",
        )
        if x
    )
    return cau if goi else None


def lien_ket(link_vbpl: str | None, link_chinhphu: str | None) -> str | None:
    """MỘT link chính thống: vbpl.vn trước, vanban.chinhphu.vn sau. KHÔNG bao
    giờ `nguon_url` (endpoint API, không phải trang đọc) hay thuvienphapluat."""
    for url, (host, dau_duong) in zip((link_vbpl, link_chinhphu), _HOST_LINK, strict=True):
        u = urlparse(url or "")
        if u.scheme == "https" and u.hostname == host and u.path.startswith(dau_duong):
            return url
    return None


def link_ban_ky(url: str | None) -> str | None:
    """Link bản PDF đã ký (quyết định 2026-09-28 mục 9), hoặc `None`: https, đúng
    máy chủ tệp của Cổng TTĐT Chính phủ, không tài khoản hay cổng mạng lạ, đuôi
    `.pdf`. Nút mở nó ra dưới tên cổng nhà nước, nên kiểm lại dù cột đã có CHECK."""
    u = urlparse(url or "")
    # `netloc` đúng bằng tên máy: không `user@`, không `:cổng` (kể cả cổng dị dạng).
    ok = u.scheme == "https" and u.netloc == "datafiles.chinhphu.vn"
    return url if ok and u.path.lower().endswith(".pdf") else None


def truong_trich_dan(van_ban: dict, duong_dan: str | None = None) -> dict:
    """Các trường trích dẫn của một dòng `documents` (kèm `duong_dan` khi trích
    tới điều khoản). Ngày là chuỗi ISO: dict này đi thẳng vào cache câu trả lời
    (`json.dumps`), và pydantic đọc lại chuỗi đó thành `date`."""
    _, ten = hien_van_ban(van_ban.get("so_ky_hieu") or "", van_ban.get("ten") or "")
    ngay_bh, ngay_hl = _ngay(van_ban.get("ngay_ban_hanh")), _ngay(van_ban.get("ngay_hieu_luc"))
    return {
        "ten_van_ban": html.unescape(ten) or None,
        "loai_van_ban": van_ban.get("loai_van_ban") or None,
        "co_quan_ban_hanh": van_ban.get("co_quan_ban_hanh") or None,
        "ngay_ban_hanh": ngay_bh.isoformat() if ngay_bh else None,
        "ngay_hieu_luc": ngay_hl.isoformat() if ngay_hl else None,
        "lien_ket": lien_ket(van_ban.get("link_vbpl"), van_ban.get("link_chinhphu")),
        "cach_trich": cach_trich(
            duong_dan,
            van_ban.get("loai_van_ban"),
            van_ban.get("so_ky_hieu"),
            ngay_bh,
            van_ban.get("co_quan_ban_hanh"),
            van_ban.get("ten"),
        ),
    }


def _ngay_chu(d: date) -> str:
    """ "ngày 20 tháng 11 năm 2019". Ngày dưới 10 và tháng 1, 2 thêm số 0 — đúng
    cách lời mở đầu trong kho viết ("ngày 17 tháng 02 năm 2017", "ngày 08 tháng
    12"), không phải "tháng 2"."""
    thang = f"{d.month:02d}" if d.month < 3 else str(d.month)
    return f"ngày {d.day:02d} tháng {thang} năm {d.year}"


def dong_can_cu(van_ban: dict) -> str:
    """Một dòng "Căn cứ" chưa có dấu kết: "Căn cứ Bộ luật Lao động số
    45/2019/QH14 ngày 20 tháng 11 năm 2019". Văn bản gọi bằng số hiệu mang thêm
    cơ quan và trích yếu ("… của Chính phủ quy định mức lương tối thiểu…"), như
    lời mở đầu của chính các nghị định trong kho. Không một chữ nào về hiệu lực."""
    loai = van_ban.get("loai_van_ban") or ""
    so_tho, ten = van_ban.get("so_ky_hieu") or "", van_ban.get("ten") or ""
    ngay = _ngay(van_ban.get("ngay_ban_hanh"))
    phan = [f"Căn cứ {_ten_goi(loai, so_tho, ten)}", _ngay_chu(ngay) if ngay else ""]
    if loai not in _LOAI_CO_TEN and hien_van_ban(so_tho, ten)[0]:
        co_quan = van_ban.get("co_quan_ban_hanh")
        phan += [f"của {co_quan}" if co_quan else "", _viet_thuong_dau(_phan_sau_so(loai, so_tho, ten))]
    return " ".join(x for x in phan if x)


def khoi_can_cu(van_ban: Iterable[dict], verdict_cua: Callable[[str], V]) -> list[str]:
    """Khối "Căn cứ" của bản thảo: mỗi văn bản MỘT dòng, chỉ văn bản còn hiệu lực
    (`verdict_cua(id)` — cùng phép tính hiệu lực của câu trả lời), trừ nguồn chỉ
    quy định thể thức (`_CHI_THE_THUC`), xếp theo thứ bậc rồi ngày ban hành; mọi
    dòng kết bằng ";", dòng cuối bằng "."."""
    theo_id = {v["id"]: v for v in van_ban if v.get("so_ky_hieu") not in _CHI_THE_THUC}
    con = [v for i, v in theo_id.items() if verdict_cua(i) in CON_HIEU_LUC]
    con.sort(
        key=lambda v: (
            _THU_BAC.get(v.get("loai_van_ban") or "", 4),
            _ngay(v.get("ngay_ban_hanh")) or date.max,
            v.get("so_ky_hieu") or "",
        )
    )
    dong = [dong_can_cu(v) for v in con]
    return [f"{d};" for d in dong[:-1]] + [f"{d}." for d in dong[-1:]]
