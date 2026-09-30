"""Khuôn mẫu — `.docx` KLAW tự dựng cho một loại văn bản (quyết định 2026-09-29
`the-thuc-moi-ban-thao.md` mục 5–8; thiết kế `docs/plans/active/khuon-mau-thiet-ke.md`
§1, §2, §7).

Hai phần, cùng một file vì chúng chỉ có nghĩa cùng nhau:

**Registry** (`config/khuon_mau/<loai>.yaml`, `_truong.yaml`): khung của từng loại —
bố cục, thể thức, các bên, thân, khối ký — kèm nguồn (mẫu chính thức với URL và
SHA-256, hay dựng theo Phụ lục I NĐ 30/2020). Nạp một lần (`lru_cache`), hỏng thì nổ
lúc nạp như `load_checklist`.

**Bộ dựng** `dung_docx(spec) -> (bytes, ban_do)`: hàm THUẦN (không DB, không mô
hình, không LibreOffice) ghi thẳng OOXML bằng `lxml` — cùng đường `dien_khuon` ghi,
không python-docx (thiết kế §2). Mã dựng KHUNG (quốc hiệu, tiêu ngữ, số, ngày, căn
cứ, các bên, khối ký, nơi nhận); mô hình chỉ viết điều khoản (`spec["dieu"]`). Chỗ
chưa biết là "……" hoặc một `w:tab` tới mốc dẫn chấm — đúng hai hình dạng bộ đọc
(`doc_tai_lieu._cho_trong_doan`) nhận ra, nên bản dựng đi CÙNG đường khuôn gốc: dựng
trang, bấm chỗ trống để điền, phép `dien`, phiên bản, tải về. Không có dấu giữ chỗ
nào trong tệp — không gì để gỡ.

`ban_do`: `(part, chi_muc)` → danh sách, thẳng hàng với `so` của chỗ trống trong đơn
vị đó (thứ tự đọc), mỗi phần tử `(ben, truong)` cho một chỗ trống của trường, `None`
cho chỗ trống không thuộc trường nào (ngày, số, chỗ trống trong điều khoản). Đúng
`dia_chi` bộ đọc ghim, nên `ban_thao` biến giá trị các bên thành phép `dien`.
"""

import re
import zipfile
from collections import Counter
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml
from lxml import etree

THU_MUC = Path("config/khuon_mau")
BO_CUC = ("hanh_chinh", "don", "hop_dong")
NGUON_LOAI = ("mau_chinh_thuc", "tuong_tu", "tu_dung")
NGAY = ("dau", "cot_phai", "cuoi", "khong")
# `lien`: "Điều n." đậm mở đầu đoạn đầu của điều, không dòng tên riêng — quyết định,
# nghị quyết theo Phụ lục III NĐ 30/2020 (Mẫu 1.1, 1.2: "Điều 1……").
# `doan`: điều khoản in thành đoạn văn liền, không tên, không số (thân một lá đơn).
KIEU_DIEU = ("dieu", "so", "muc", "lien", "doan")
# Chữ đặt vào dòng mẫu, không phải chỗ trống: trích yếu (khi có), tên văn bản viết
# thường ("Quy chế …", cho quyết định ban hành), tên loại viết thường.
_TU_KHOA = ("trich_yeu", "ten_van_ban", "loai_thuong")
# Trường của cả VĂN BẢN, không của bên nào (tên Tòa án ở dòng Kính gửi, cơ quan nhận).
BEN_VAN_BAN = "van_ban"
# Hai loại của một bên `loai: tuy` (`chon_ben`).
LOAI_BEN = ("ca_nhan", "to_chuc")

QUOC_HIEU = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"
TIEU_NGU = "Độc lập - Tự do - Hạnh phúc"
# Chỗ trống DUY NHẤT bộ dựng viết giữa dòng (thiết kế §1): hai U+2026, đủ cho
# `RE_CHO_DIEN`; mọi dãy chấm khác đã bị chuẩn hoá trước khi tới đây (§6).
CHO = "……"
# U+2060 WORD JOINER giữa "……" và dấu "." ngay sau nó: bộ đọc gộp mọi dãy `.`/`…` liền
# nhau thành MỘT chỗ trống ("……." — đúng với biểu mẫu tải lên, xem `_day_cham`), nên
# không có ký tự này thì dấu chấm hết câu mất khi điền ("Theo đề nghị của Trưởng phòng",
# "Lưu: VT, HCNS" thiếu "." Phụ lục I đòi). Vô hình, cấm ngắt dòng trước dấu chấm.
NOI = "\u2060"

# Ngân sách chữ điều khoản của một bản thảo (§6), ĐO trên bản dựng thật (2026-09-29,
# LibreOffice 26.2, `test_khuon_mau_trang.py`): 25 Điều với đoạn 400 ký tự ra 8 trang
# ở cả ba bố cục cho 16.000 lẫn 18.000 ký tự, và 10 trang ở 20.000 (đơn, hợp đồng).
# Giữ 16.000: chữ thật chia đoạn ngắn hơn tốn thêm khoảng cách đoạn, và trần 10 trang
# của khuôn gốc còn dư hai trang.
NGAN_SACH_KY_TU = 16_000
TOI_DA_DIEU = 25
TOI_DA_DOAN = 8
TOI_DA_KY_TU_DOAN = 1_200

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_W = f"{{{_W_NS}}}"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_NSMAP = {"w": _W_NS, "r": _R_NS}

# A4 dọc (twip). Lề mặc định Phụ lục I, cận dưới mỗi khoảng: trên/dưới 20, trái 30,
# phải 15 mm; một loại mang lề của chính mẫu nó (`the_thuc.le_mm`).
_A4 = (11906, 16838)
_LE_MM = (20, 20, 30, 15)
_MM = 1440 / 25.4

# Cỡ chữ (nửa điểm), một bộ cho cả văn bản — cận trên mỗi khoảng Phụ lục I (§1).
_CO = {"quoc_hieu": 26, "co_quan": 26, "so": 26, "vv": 26, "noi_nhan_nhan": 24, "noi_nhan": 22}
_CO_THAN = 28
# Giãn dòng 1,15; sau đoạn 6 pt; lùi đầu dòng 1,27 cm (Phụ lục I, "Nội dung").
_DONG = 276
_SAU = 120
_THUT = 720
# Chiều dài dòng tiêu ngữ ở cỡ 14 đậm Times New Roman (Liberation Serif cùng số đo),
# đo trên bản dựng thật bằng `pdftotext -bbox` (2026-09-29): 171,2 pt.
# ponytail: một hằng số cho một chuỗi cố định; đổi cỡ tiêu ngữ thì đo lại.
_DAI_TIEU_NGU = 3425
# Bề rộng trung bình một ký tự đậm cỡ 14 (twip) — chỉ để ước độ dài dòng kẻ dưới
# trích yếu (1/3–1/2 dòng chữ); sai vài mm không đổi nghĩa gì.
_RONG_KY_TU = 134

_RE_O = re.compile(r"\{(\w*)\}")
_LA_MA = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII")
_BEN_CHU = "ABCDEFGH"


class KhuonMauHongError(ValueError):
    """Registry hỏng — nổ lúc nạp, không giữa lượt người dùng."""


# ═══ Registry ══════════════════════════════════════════════════════════════


@lru_cache
def truong() -> dict[str, str]:
    """Danh mục trường: khoá → nhãn ("ho_ten" → "Họ và tên")."""
    return yaml.safe_load((THU_MUC / "_truong.yaml").read_text(encoding="utf-8"))


@lru_cache
def cac_loai() -> frozenset[str]:
    """Mọi loại có khuôn mẫu — suy từ tệp trên đĩa, như `graph_soan_thao.cac_loai`."""
    return frozenset(p.stem for p in THU_MUC.glob("*.yaml") if not p.stem.startswith("_"))


def _cac_o(mau: Any) -> list[str]:
    return _RE_O.findall(mau) if isinstance(mau, str) else []


def _chuoi_cua_dong(d: Any) -> str:
    return d.get("d", "") if isinstance(d, dict) else d


def _chuoi_cua_o(x: Any) -> str:
    """Chữ của một ô bảng dữ liệu: chuỗi, hay `{chu, gop, dam}`."""
    return str(x.get("chu") or "") if isinstance(x, dict) else str(x)


@lru_cache
def nap(loai: str) -> dict:
    """Mục registry của `loai`, đã kiểm. `KhuonMauHongError` khi tệp hỏng: bố cục lạ, khoá
    trường lạ, bên lạ, mục thân lạ, hay một mẫu chính thức thiếu tệp/SHA-256."""
    if loai not in cac_loai():
        raise KhuonMauHongError(f"không có khuôn mẫu {loai!r}")
    duong = THU_MUC / f"{loai}.yaml"
    d = yaml.safe_load(duong.read_text(encoding="utf-8"))
    loi = _kiem_muc(d, loai)
    if loi:
        raise KhuonMauHongError(f"{duong}: {loi}")
    return d


def _kiem_muc(d: dict, loai: str) -> str | None:
    if d.get("loai") != loai:
        return f"`loai: {d.get('loai')}` phải bằng tên tệp"
    for k in ("ten", "tieu_de", "bo_cuc", "nguon", "the_thuc", "than"):
        if not d.get(k):
            return f"thiếu `{k}`"
    if d["bo_cuc"] not in BO_CUC:
        return f"bo_cuc lạ {d['bo_cuc']!r}"
    ng = d["nguon"]
    if ng.get("loai") not in NGUON_LOAI:
        return f"nguon.loai lạ {ng.get('loai')!r}"
    if ng["loai"] == "mau_chinh_thuc" and not (ng.get("tep_d2") and ng.get("sha256") and ng.get("url")):
        return "mẫu chính thức phải có nguon.url, nguon.tep_d2 và nguon.sha256"
    danh_muc = truong()
    ben = {b["khoa"]: b for b in d.get("ben") or []}
    if len(ben) != len(d.get("ben") or []):
        return "khoá bên trùng"
    tuy = [b for b in ben.values() if b.get("loai") == "tuy"]
    for b in tuy:
        if b.get("mac_dinh") not in LOAI_BEN or not all(isinstance(b.get(x), dict) for x in LOAI_BEN):
            return f"bên {b['khoa']}: `loai: tuy` cần `mac_dinh` và hai khối `ca_nhan`, `to_chuc`"
    # Mỗi cách chọn là một mục registry thường: kiểm cả hai.
    for x in LOAI_BEN if tuy else ():
        if loi := _kiem_muc(chon_ben(d, [{"khoa": b["khoa"], "loai": x} for b in tuy]), loai):
            return f"khi bên tuỳ loại là {x}: {loi}"
    mau: list[str] = []
    for b in ben.values():
        mau += [_chuoi_cua_dong(x) for x in b.get("dong") or []]
        if lech := [t for t in b.get("truong") or [] if t not in danh_muc]:
            return f"bên {b['khoa']}: trường lạ {lech}"
    # Quyết định ban hành đi trước văn bản kèm theo (Mẫu 1.3 NĐ 30/2020): cùng các bên,
    # thể thức, thân và khối ký riêng — kiểm như chính mục.
    phan = [d, *([d["ban_hanh"]] if d.get("ban_hanh") else [])]
    for x in phan:
        loi = _kiem_phan(x, ben, mau)
        if loi:
            return loi
    if lech := sorted({o for s in mau for o in _cac_o(s) if o and o not in danh_muc and o not in _TU_KHOA}):
        return f"trường lạ trong dòng mẫu {lech}"
    # Loại KHÔNG checklist mang điều luật của nó ngay trong mục: `muc` (khoá, tên, điều
    # khoản căn cứ, bắt buộc hay không) và `can_cu` (điều khoản thêm cho khối căn cứ).
    luat = d.get("muc") or []
    if any(not isinstance(m, dict) or not m.get("key") or not m.get("ten") for m in luat):
        return "muc: mỗi mục cần `key` và `ten`"
    if len({m["key"] for m in luat}) != len(luat):
        return "khoá muc trùng"
    if any(not isinstance(x, str) for x in [*(d.get("can_cu") or []), *(m.get("can_cu", "") for m in luat)]):
        return "can_cu phải là đường dẫn điều khoản"
    for k, (b, t) in (d.get("truong_tu_facts") or {}).items():
        if b not in ben or t not in danh_muc:
            return f"truong_tu_facts.{k} trỏ tới [{b}, {t}] không có"
    return None


def _kiem_phan(d: dict, ben: dict, mau: list[str]) -> str | None:
    """Kiểm thể thức, thân và khối ký của MỘT văn bản trong mục; gom mọi dòng mẫu vào
    `mau` để kiểm trường một lần."""
    tt = d.get("the_thuc") or {}
    if not d.get("than") or not d.get("tieu_de"):
        return "thiếu `than` hay `tieu_de`"
    if tt.get("ngay", "khong") not in NGAY:
        return f"the_thuc.ngay lạ {tt.get('ngay')!r}"
    for m in d["than"]:
        if not isinstance(m, dict) or len({"ben", "muc", "dieu", "dong", "bang"} & m.keys()) != 1:
            return f"mục thân lạ {m!r}"
        if "ben" in m and m["ben"] not in ben:
            return f"thân gọi bên lạ {m['ben']!r}"
        if "dieu" in m and m["dieu"] not in KIEU_DIEU:
            return f"kiểu điều lạ {m['dieu']!r}"
        if "bang" in m and not (
            m["bang"].get("cot") and all(len(h) <= len(m["bang"]["cot"]) for h in m["bang"]["dong"])
        ):
            return f"bảng thiếu cột hay hàng thừa ô {m!r}"
        mau.append(m.get("dong") or m.get("nhan") or "")
        mau += [_chuoi_cua_o(x) for h in (m.get("bang") or {}).get("dong") or [] for x in h]
    kg = tt.get("kinh_gui") or {}
    mau += [kg.get("dong") or "", tt.get("so") or "", tt.get("ket_thuc") or "", *(tt.get("noi_nhan") or [])]
    mau += [str(tt.get(k) or "") for k in ("tham_quyen", "trich_yeu", "kem_theo", "lenh")]
    mau += [tt["vv"] if isinstance(tt.get("vv"), str) else ""]
    mau += [x["dong"] if isinstance(x, dict) else x for x in tt.get("can_cu_them") or []]
    mau += [_chuoi_cua_dong(x) for x in tt.get("ten_loai") or []]
    ky = d.get("ky") or {}
    if lech := [k for k in [*(ky.get("thu_tu") or []), *(o["khoa"] for o in ky.get("o") or [])] if k not in ben]:
        return f"khối ký gọi bên lạ {lech}"
    return None


def chon_ben(entry: dict, ben: list[dict] | None = None) -> dict:
    """Bên `loai: tuy` của một mục registry — cá nhân HAY tổ chức (ví dụ BLDS Đ505.2
    với hợp đồng hợp tác: "cá nhân … pháp nhân"; BLLĐ Đ3.2: người sử dụng lao động có
    thể là cá nhân) → khối của đúng loại. `ben` (`[{khoa, loai}]`: lời mô hình, hay khung đã lưu) nói loại nào thì lấy
    khối ấy, không nói thì `mac_dinh`. Khối chọn (`dong`/`truong`/`nhan`) và phần cùng
    loại của ô ký (`ky.o[].ca_nhan|to_chuc`) gộp vào mục; bên cố định giữ nguyên, nên
    gọi lại trên mục đã chọn không đổi gì."""
    noi = {b.get("khoa"): b.get("loai") for b in ben or [] if isinstance(b, dict)}
    loai = {
        b["khoa"]: noi[b["khoa"]] if noi.get(b["khoa"]) in LOAI_BEN else b["mac_dinh"]
        for b in entry.get("ben") or []
        if b.get("loai") == "tuy"
    }
    if not loai:
        return entry

    def _gop(x: dict) -> dict:
        if x["khoa"] not in loai:
            return x
        return {**{k: v for k, v in x.items() if k not in LOAI_BEN}, **(x.get(loai[x["khoa"]]) or {})}

    ky = entry.get("ky") or {}
    return {
        **entry,
        "ben": [{**_gop(b), "loai": loai[b["khoa"]]} if b["khoa"] in loai else b for b in entry["ben"]],
        "ky": {**ky, "o": [_gop(o) for o in ky.get("o") or []]},
    }


def can_cu_hien(can_cu: list[dict], dieu: list[dict]) -> list[dict]:
    """Dòng căn cứ IN trên khung. Dòng `tuy_chon` — văn bản mà chỉ mục tuỳ chọn của
    checklist dẫn tới (`graph_soan_thao.can_cu_khung`) — chỉ in khi một Điều đang có
    dẫn chính văn bản ấy; dấu câu tính lại theo dòng cuối còn lại."""
    co = {
        str(d["can_cu"].get("doc_id")) for d in dieu or [] if isinstance(d, dict) and isinstance(d.get("can_cu"), dict)
    }
    ra = [
        x
        for x in can_cu or []
        if isinstance(x, dict) and x.get("dong") and (not x.get("tuy_chon") or str(x.get("doc_id")) in co)
    ]
    return [{**x, "dong": x["dong"].rstrip(";.") + (";" if k < len(ra) - 1 else ".")} for k, x in enumerate(ra)]


def khung_tong_quat(bo_cuc: str, ben: list[dict]) -> dict:
    """Khung của một bản thảo TỔNG QUÁT (không mục registry): cùng hình dạng mục
    registry, dựng từ bố cục mô hình chọn và các bên nó kể (`{khoa, vai, loai}`).
    Tên loại và trích yếu đi riêng trong `spec`."""
    ca_nhan = ["ho_ten", "ngay_sinh", "so_dinh_danh", "noi_cu_tru", "dien_thoai"]
    to_chuc = ["ten_to_chuc", "ma_so_doanh_nghiep", "dia_chi_tru_so", "nguoi_dai_dien", "chuc_vu", "dien_thoai"]
    ds = [b for b in ben if isinstance(b, dict) and b.get("khoa")][: len(_BEN_CHU)]
    vai = [str(b.get("vai") or "").strip() or f"Bên {_BEN_CHU[i]}" for i, b in enumerate(ds)]
    cac_ben = [
        {
            "khoa": b["khoa"],
            "vai": vai[i],
            "loai": "to_chuc" if b.get("loai") == "to_chuc" else "ca_nhan",
            "truong": to_chuc if b.get("loai") == "to_chuc" else ca_nhan,
            **(
                {"tieu_de": f"{_LA_MA[i]}. {vai[i].upper()} (sau đây gọi là Bên {_BEN_CHU[i]}):"}
                if bo_cuc == "hop_dong"
                else {}
            ),
        }
        for i, b in enumerate(ds)
    ]
    ho_ten = {b["khoa"]: ("nguoi_dai_dien" if b["loai"] == "to_chuc" else "ho_ten") for b in cac_ben}
    if bo_cuc == "hop_dong":
        cac = "Các bên" if len(cac_ben) > 2 else "Hai bên"
        return {
            "bo_cuc": "hop_dong",
            "the_thuc": {
                "ngay": "khong",
                "so": "Số: {}/{}",
                "can_cu": True,
                "ket_thuc": "{loai_thuong} này được lập thành {} bản, mỗi bên giữ {} bản, có giá trị như nhau.",
            },
            "ben": cac_ben,
            "than": [
                {"dong": "Hôm nay, ngày {} tháng {} năm {}, tại {}, chúng tôi gồm:"},
                *({"ben": b["khoa"]} for b in cac_ben),
                {"dong": f"{cac} thống nhất lập {{loai_thuong}} với các điều khoản sau:", "nghieng": True},
                {"dieu": "dieu"},
            ],
            "ky": {
                "thu_tu": [b["khoa"] for b in cac_ben],
                "o": [
                    {
                        "khoa": b["khoa"],
                        "vai": ("ĐẠI DIỆN " if b["loai"] == "to_chuc" else "") + f"BÊN {_BEN_CHU[i]}",
                        "ghi_chu": "(Ký, ghi rõ họ tên" + (", chức vụ và đóng dấu)" if b["loai"] == "to_chuc" else ")"),
                        "ho_ten_tu": ho_ten[b["khoa"]],
                    }
                    for i, b in enumerate(cac_ben)
                ],
            },
        }
    if bo_cuc == "don":
        dau = cac_ben[:1]
        return {
            "bo_cuc": "don",
            "the_thuc": {"ngay": "dau", "kinh_gui": {"dong": "Kính gửi: {co_quan_nhan}", "can": "giua"}},
            "ben": cac_ben,
            "than": [*({"ben": b["khoa"]} for b in cac_ben), {"dieu": "muc"}],
            "ky": {
                "thu_tu": [b["khoa"] for b in dau],
                "o": [
                    {"khoa": b["khoa"], "vai": "NGƯỜI LÀM ĐƠN", "ghi_chu": "(Ký, ghi rõ họ tên)", "ho_ten_tu": "ho_ten"}
                    for b in dau
                ],
            },
        }
    # hanh_chinh: cơ quan ban hành ở đầu trang, người ký ở khối ký — hai "bên" không in
    # thành khối thông tin.
    return {
        "bo_cuc": "hanh_chinh",
        "the_thuc": {
            "co_quan": True,
            "so": "Số: {}/{}",
            "ngay": "cot_phai",
            "can_cu": True,
            "noi_nhan": ["{};", "Lưu: {}."],
        },
        "ben": [
            {"khoa": "co_quan", "vai": "Cơ quan, tổ chức ban hành", "loai": "to_chuc", "truong": ["ten_to_chuc"]},
            {"khoa": "nguoi_ky", "vai": "Người ký", "loai": "ca_nhan", "truong": ["chuc_vu", "ho_ten"]},
        ],
        "than": [{"dieu": "so"}],
        "ky": {"thu_tu": ["nguoi_ky"], "o": [{"khoa": "nguoi_ky", "vai": None, "ho_ten_tu": "ho_ten"}]},
    }


def khoa_khung(entry: dict) -> set[str]:
    """Khoá mục checklist mà CHÍNH khung đã có — khối các bên, dòng ngày, Kính gửi,
    thể thức: `them_dieu_bat_buoc` không đòi điều khoản cho chúng."""
    return {b["khoa"] for b in entry.get("ben") or []} | set(entry.get("muc_khung") or [])


def muc_than(entry: dict) -> set[str]:
    """Khoá các mục cố định của thân (đơn: yêu cầu, tài liệu kèm theo…)."""
    return {m["muc"] for m in entry.get("than") or [] if "muc" in m}


def them_dieu_bat_buoc(
    dieu: list[dict], loai: str | None, *, tao: bool = True, mau: dict[str, str] | None = None
) -> tuple[list[dict], dict]:
    """Điều khoản luật đòi mà danh sách còn thiếu (§6 bước 7) — `check_completeness`
    trên khoá của `dieu` cộng khoá khung đã có, cùng `khong_bat_buoc` với
    `draft_audit`. Lúc TẠO, mỗi mục thiếu được chèn đúng vị trí checklist là một Điều
    tên mục. Điều của HỢP ĐỒNG không bao giờ trống (app thật 2026-09-30: Điều 5 "Giao tài
    sản thuê" in một "……" trơn): đoạn là `mau[khoá]` — nội dung chuẩn lấy nguyên văn từ
    căn cứ của mục (`graph_tra_cuu._nap_khuon_mau`) — hay, không có, một câu trung tính để
    các bên điền; không bịa giá trị, không dẫn số điều luật. Đơn và văn bản hành chính
    giữ MỘT đoạn "……": đó là chỗ điền của chính mẫu (danh mục tài liệu "1. 2. 3.", nội
    dung quyết định), không có "các bên" nào thỏa thuận. Lúc SỬA không chèn gì — mục
    thiếu là một phát hiện. `loai` không checklist: `muc` của chính mục registry (mục
    `bat_buoc: false` không đòi); không có thì không đòi gì. Trả `(dieu, {thieu,
    completeness})`."""
    from src.agents.graph_soan_thao import cac_loai as cac_checklist
    from src.agents.graph_soan_thao import load_checklist_cached
    from src.services.checklist import check_completeness

    entry = nap(loai) if loai and loai in cac_loai() else {}
    co = [{"key": k} for k in khoa_khung(entry)] + [{"key": d.get("key")} for d in dieu]
    if loai and loai in cac_checklist():
        cl = load_checklist_cached(loai)
        comp = check_completeness(cl, co, "thuong_mai")
        muc, thieu, ty_le = cl.muc, comp.thieu, comp.ty_le
    elif entry.get("muc"):
        muc = entry["muc"]
        bat_buoc = [m["key"] for m in muc if m.get("bat_buoc", True)]
        thieu = [k for k in bat_buoc if k not in {c["key"] for c in co}]
        ty_le = round((len(bat_buoc) - len(thieu)) / len(bat_buoc), 4) if bat_buoc else 1.0
    else:
        return list(dieu), {"thieu": [], "completeness": None}
    if not tao or not thieu:
        return list(dieu), {"thieu": thieu, "completeness": ty_le}
    thu_tu = [m["key"] for m in muc]
    ten = {m["key"]: m["ten"] for m in muc}
    ra = list(dieu)
    for k in thieu:
        t = ten.get(k, k)
        doan = (
            ((mau or {}).get(k) or f"Các bên thỏa thuận về {t[:1].lower()}{t[1:]} như sau: {CHO}")
            if entry.get("bo_cuc") == "hop_dong"
            else CHO
        )
        moi = {"key": k, "ten": t, "doan": [doan], "can_cu": None, "chen": True}
        # Chèn trước điều đầu tiên có vị trí checklist SAU mục này; không có thì cuối.
        vt = thu_tu.index(k) if k in thu_tu else len(thu_tu)
        i = next(
            (i for i, d in enumerate(ra) if d.get("key") in thu_tu and thu_tu.index(d["key"]) > vt),
            len(ra),
        )
        ra.insert(i, moi)
    return ra, {"thieu": thieu, "completeness": ty_le}


# ═══ Chuẩn hoá chữ điều khoản (§6 bước 1, 3, 4) — thuần, dùng chung hai đường ═══

_RE_SO_DAU = re.compile(r"^\s*(?:(?:điều|ĐIỀU|Điều)\s*\d+\s*[.:–-]?\s*|\d+\s*[.)]\s*)")
_RE_CHO_MO_HINH = re.compile(r"\[[^\]\n]{0,80}\]|<[^>\n]{0,80}>|\{[^}\n]{0,80}\}")
_RE_DIEU_KHIEN = re.compile(r"[\x00-\x08\x0b-\x1f\x7f⟦⟧¶]")
_RE_CHO_Y = re.compile(r"…{2,}|\.{4,}|_{3,}|(?:…\s*\.{1,3}|\.{1,3}\s*…)+")
_RE_BA_CHAM_LE = re.compile(r"…|(?<!\.)\.\.\.(?!\.)")
_RE_GACH = re.compile(r"[-–—]{3,}")


def bo_so_dau(ten: str) -> str:
    """Tên một Điều không mang số của mô hình: "Điều 3. Giá thuê" → "Giá thuê" — mã
    đánh số, không mô hình (§2)."""
    return _RE_SO_DAU.sub("", str(ten or ""), count=1).strip()


def chuan_chu(s: str) -> tuple[str, int]:
    """Chữ mô hình viết cho một đoạn → chữ bộ dựng ghi được, và số chỗ giữ chỗ của
    mô hình đã đổi thành "……" (`[Tên Bên A]`, `<…>`, `{…}`, `[…]`).

    Sau hàm này, "……" là dãy chấm DUY NHẤT: hai "…" trở lên, bốn "." trở lên, ba "_"
    trở lên là một chỗ trống cố ý → "……"; một "…" hay đúng "..." lẻ bị bỏ (cuối đoạn
    thành "."); ba gạch trở lên bị bỏ. Không thì một "điện, nước…" thành một chỗ
    trống lạc trên trang (§1)."""
    s = _RE_DIEU_KHIEN.sub("", str(s or ""))
    s, n = _RE_CHO_MO_HINH.subn(CHO, s)
    s = _RE_CHO_Y.sub("\x00", s)
    s = _RE_BA_CHAM_LE.sub("\x01", s)
    s = re.sub(r"\s*\x01\s*$", ".", s)
    s = re.sub(r"\s*\x01\s*", " ", s)
    s = _RE_GACH.sub("", s).replace("\x00", CHO)
    return re.sub(r"\s+([,.;:!?)])", r"\1", " ".join(s.split())), n


# ═══ Bộ dựng ══════════════════════════════════════════════════════════════


def _e(ten: str, **thuoc: Any) -> Any:
    el = etree.Element(_W + ten, nsmap=None)
    for k, v in thuoc.items():
        el.set(_W + k, str(v))
    return el


def _con(cha: Any, ten: str, **thuoc: Any) -> Any:
    el = _e(ten, **thuoc)
    cha.append(el)
    return el


def _rpr(cha: Any, *, b: bool = False, i: bool = False, sz: int | None = None, caps: bool = False) -> None:
    """`caps`: chữ hiện IN HOA dù người dùng gõ thường — chỗ trống của tên cơ quan,
    thẩm quyền, chức vụ người ký (Phụ lục I: "chữ in hoa"). Thứ tự con theo CT_RPr."""
    rpr = _e("rPr")
    if b:
        _con(rpr, "b")
        _con(rpr, "bCs")
    if i:
        _con(rpr, "i")
        _con(rpr, "iCs")
    if caps:
        _con(rpr, "caps")
    if sz:
        _con(rpr, "sz", val=sz)
        _con(rpr, "szCs", val=sz)
    if len(rpr):
        cha.append(rpr)


def _run(chu: str, *, b: bool = False, i: bool = False, sz: int | None = None, caps: bool = False) -> Any:
    r = _e("r")
    _rpr(r, b=b, i=i, sz=sz, caps=caps)
    t = _con(r, "t")
    t.text = chu
    if chu != chu.strip():
        t.set(_XML_SPACE, "preserve")
    return r


def _run_tab(*, b: bool = False, sz: int | None = None, caps: bool = False) -> Any:
    r = _e("r")
    _rpr(r, b=b, sz=sz, caps=caps)
    _con(r, "tab")
    return r


# Dòng địa danh – ngày của đơn, hợp đồng (một dòng mỗi văn bản): địa danh là trường của
# văn bản (nhãn "Địa danh" cho ô điền); ngày, tháng, năm là chỗ trống của dòng — không
# phải "ngày ban hành" của văn bản hành chính (`_dau_hanh_chinh`).
_DIA_DANH_NGAY = "{dia_danh}, ngày {} tháng {} năm {}"


class _Dung:
    """Trạng thái của MỘT lần dựng: thân bài, bản đồ chỗ trống, hình học trang."""

    def __init__(self, spec: dict) -> None:
        self.spec = spec
        tt = spec.get("the_thuc") or {}
        tren, duoi, trai, phai = tt.get("le_mm") or _LE_MM
        self.le = tuple(round(x * _MM) for x in (tren, duoi, trai, phai))
        self.rong = _A4[0] - self.le[2] - self.le[3]
        self.co = int(tt.get("co_chu", 14)) * 2
        # Khối các bên thụt bằng lùi đầu dòng của đoạn (NĐ 96/2024 Phụ lục II: "I. BÊN …"
        # và các dòng "- …" thẳng lề chữ thân bài), thân bài giữ lùi dòng đầu.
        self.thut_ben = round(float(tt.get("thut_ben_mm", 0)) * _MM)
        # Dòng trường các bên và nhãn mục trình bày NHƯ ĐOẠN THÂN (NĐ 124 Mẫu 01, NĐ 30
        # Mẫu 1.8/1.9): lùi đầu dòng 1,27 cm, cách đoạn 6 pt (Phụ lục I, "Nội dung").
        # Khác `thut_nhan` (chỉ lùi đầu dòng): cả khoảng cách đoạn như thân bài.
        self.nhu_than = bool(tt.get("dong_nhu_than"))
        self.body = _e("body")
        self.o: dict[Any, list] = {}
        # Đoạn → Điều/mục nó thuộc ("khoá hay tên#lần"): `ban_thao.mang_phep_sang` so theo
        # đó, nên chèn/bỏ một điều (đánh số lại mọi tiêu đề) không đẩy giá trị sang điều khác.
        self.thuoc: dict[Any, str] = {}
        self.ben = {b["khoa"]: b for b in spec.get("ben") or []}
        self.ten_van_ban = _ten_van_ban(spec)
        # Dòng trường của các bên và nhãn mục lùi đầu dòng như lời văn (Mẫu 1.9, Mẫu 01
        # NĐ 124/2020); mặc định sát lề như Mẫu 23-DS.
        self.thut_nhan = _THUT if tt.get("thut_nhan") else 0

    # ─── đoạn và dòng mẫu ───────────────────────────────────────────────

    def doan(
        self,
        cha: Any,
        *,
        can: str = "both",
        thut_dau: int = 0,
        trai: int = 0,
        phai: int = 0,
        truoc: int = 0,
        sau: int = 0,
        dong: int | None = None,
        moc: tuple[int, ...] = (),
        vien_duoi: bool = False,
        giu_sau: bool = False,
        sz: int | None = None,
    ) -> Any:
        """Một `w:p` mới cuối `cha`. Thứ tự con của `w:pPr` theo lược đồ CT_PPr — Word
        báo tệp hỏng khi sai thứ tự."""
        p = _con(cha, "p")
        ppr = _con(p, "pPr")
        if giu_sau:
            _con(ppr, "keepNext")
        if vien_duoi:
            _con(_con(ppr, "pBdr"), "bottom", val="single", sz=6, space=1, color="000000")
        if moc:
            tabs = _con(ppr, "tabs")
            for pos in moc:
                _con(tabs, "tab", val="right", leader="dot", pos=pos)
        _con(ppr, "spacing", before=truoc, after=sau, line=dong or 240, lineRule="auto")
        if trai or phai or thut_dau:
            _con(ppr, "ind", left=trai, right=phai, firstLine=thut_dau)
        _con(ppr, "jc", val=can)
        _rpr(ppr, sz=sz or self.co)
        return p

    def dong_mau(
        self,
        p: Any,
        mau: str,
        vat: Any,
        ben: str | None,
        *,
        tab: bool = False,
        b: bool = False,
        i: bool = False,
        sz: int | None = None,
        trai: int = 0,
        caps: bool = False,
    ) -> None:
        """Điền `p` bằng dòng mẫu `mau`: chữ tĩnh nguyên văn, mỗi `{truong}` (hay `{}`)
        là MỘT chỗ trống ghi vào `self.o[vat]` theo thứ tự đọc. `tab`: chỗ trống là
        `w:tab` tới mốc phải dẫn chấm (dòng trường của các bên — chữ sau chỗ trống
        dạt về mốc); không thì "……" giữa dòng. `{trich_yeu}` là trích yếu của văn bản,
        in thành chữ khi có (bỏ phần lặp chữ tĩnh đứng trước: "V/v V/v …" không lên
        trang); `{ten_van_ban}` là tên văn bản viết thường."""
        sz = sz or self.co
        ty = self.spec.get("trich_yeu")
        phan = _RE_O.split(mau.replace("{ten_van_ban}", self.ten_van_ban))
        o = [k for k in range(1, len(phan), 2) if phan[k] != "trich_yeu" or not ty]
        moc = []
        sau_cho = False
        for k, chu in enumerate(phan):
            if k % 2 == 0:
                if chu:
                    p.append(_run(_sau_cho(chu) if sau_cho else chu, b=b, i=i, sz=sz, caps=caps))
                continue
            sau_cho = False
            if chu == "trich_yeu" and ty:
                p.append(_run(_bo_tien_to(ty, phan[k - 1]), b=b, i=i, sz=sz, caps=caps))
                continue
            # Trích yếu chưa có là chỗ trống CỦA VĂN BẢN: mọi bản sao của nó (tên loại,
            # "Ban hành …", Điều 1 của quyết định ban hành) cùng một trường.
            khoa = None if not chu else (ben or BEN_VAN_BAN, chu)
            self.o.setdefault(vat, []).append(khoa)
            if tab:
                p.append(_run_tab(b=b, sz=sz, caps=caps))
                moc.append(trai + (self.rong - trai) * (o.index(k) + 1) // len(o))
            else:
                p.append(_run(CHO, b=b, i=i, sz=sz, caps=caps))
                sau_cho = True
        if moc:
            ppr = p.find(_W + "pPr")
            tabs = _e("tabs")
            for pos in moc:
                _con(tabs, "tab", val="right", leader="dot", pos=pos)
            vi_tri = ppr.find(_W + "spacing")
            vi_tri.addprevious(tabs)

    def ke(self, cha: Any, rong_o: int, dai: int, *, truoc: int = 0) -> None:
        """Đường kẻ nét liền dài `dai` ở giữa ô rộng `rong_o`: một đoạn RỖNG có viền
        dưới, thụt đều hai bên — đoạn rỗng không phải đơn vị văn bản."""
        le = max((rong_o - dai) // 2, 0)
        self.doan(cha, can="center", trai=le, phai=le, truoc=truoc, vien_duoi=True, sz=8, dong=240)

    # ─── bảng không viền ────────────────────────────────────────────────

    def bang(self, rong: list[int]) -> Any:
        """Bảng KHÔNG viền (xếp cột: đầu trang, khối ký) — không bao giờ là bảng dữ
        liệu, nên bộ đọc không mời ô `o` nào trong nó (`bang_vien` False)."""
        tbl = _con(self.body, "tbl")
        pr = _con(tbl, "tblPr")
        _con(pr, "tblW", w=sum(rong), type="dxa")
        vien = _con(pr, "tblBorders")
        for c in ("top", "left", "bottom", "right", "insideH", "insideV"):
            _con(vien, c, val="none", sz=0, space=0, color="auto")
        _con(pr, "tblLayout", type="fixed")
        mar = _con(pr, "tblCellMar")
        _con(mar, "left", w=57, type="dxa")
        _con(mar, "right", w=57, type="dxa")
        luoi = _con(tbl, "tblGrid")
        for w in rong:
            _con(luoi, "gridCol", w=w)
        return tbl

    def hang(self, tbl: Any, rong: list[int], *, khong_tach: bool = False) -> list[Any]:
        tr = _con(tbl, "tr")
        if khong_tach:
            _con(_con(tr, "trPr"), "cantSplit")
        o = []
        for w in rong:
            tc = _con(tr, "tc")
            _con(_con(tc, "tcPr"), "tcW", w=w, type="dxa")
            o.append(tc)
        return o

    # ─── các khối ───────────────────────────────────────────────────────

    def ngay_mau(self, cha: Any, vat: Any, can: str) -> None:
        p = self.doan(cha, can=can, truoc=0, sau=0)
        self.dong_mau(p, "{}, ngày {} tháng {} năm {}", vat, None, i=True)

    def dau_trang(self) -> None:
        tt = self.spec.get("the_thuc") or {}
        if tt.get("dong_mau"):
            p = self.doan(self.body, can="center", sz=24)
            p.append(_run(tt["dong_mau"], i=True, sz=24))
        if self.spec.get("bo_cuc") == "hanh_chinh" or tt.get("co_quan"):
            self._dau_hanh_chinh(tt)
            return
        p = self.doan(self.body, can="center", sz=_CO["quoc_hieu"])
        p.append(_run(QUOC_HIEU, b=True, sz=_CO["quoc_hieu"]))
        p = self.doan(self.body, can="center")
        p.append(_run(TIEU_NGU, b=True))
        self.ke(self.body, self.rong, _DAI_TIEU_NGU)
        if tt.get("ngay") == "dau":
            # Mẫu 23-DS: sát dưới tiêu ngữ; NĐ 124 Mẫu 01: cách một dòng (`ngay_truoc_pt`).
            p = self.doan(self.body, can="center", truoc=round(float(tt.get("ngay_truoc_pt", 3)) * 20))
            self.dong_mau(p, _DIA_DANH_NGAY, p, None, i=True)
        self._ten_loai(truoc=240)
        if tt.get("so"):
            p = self.doan(self.body, can="center", sz=_CO["so"])
            self.dong_mau(p, tt["so"], p, None, sz=_CO["so"])

    def _dau_hanh_chinh(self, tt: dict) -> None:
        trai = round(self.rong * 0.38)
        rong = [trai, self.rong - trai]
        tbl = self.bang(rong)
        o_trai, o_phai = self.hang(tbl, rong)
        p = self.doan(o_trai, can="center", sz=_CO["co_quan"])
        self.dong_mau(p, "{ten_to_chuc}", o_trai, "co_quan", b=True, sz=_CO["co_quan"], caps=True)
        self.ke(o_trai, rong[0], rong[0] // 3)
        p = self.doan(o_phai, can="center", sz=_CO["quoc_hieu"])
        p.append(_run(QUOC_HIEU, b=True, sz=_CO["quoc_hieu"]))
        p = self.doan(o_phai, can="center")
        p.append(_run(TIEU_NGU, b=True))
        self.ke(o_phai, rong[1], _DAI_TIEU_NGU)
        # Hàng Số | địa danh-ngày. Văn bản kèm theo quyết định không có cả hai (Mẫu 1.3
        # NĐ 30/2020, "Mẫu văn bản … kèm theo"): không dựng hàng rỗng.
        if tt.get("so") or tt.get("vv") or tt.get("ngay") == "cot_phai":
            o_trai, o_phai = self.hang(tbl, rong)
            p = self.doan(o_trai, can="center", truoc=120, sz=_CO["so"])
            if tt.get("so"):
                self.dong_mau(p, tt["so"], o_trai, None, sz=_CO["so"])
            if tt.get("vv"):
                p = self.doan(o_trai, can="center", sz=_CO["vv"])
                vv = tt["vv"] if isinstance(tt["vv"], str) else "V/v {trich_yeu}"
                self.dong_mau(p, vv, o_trai, None, sz=_CO["vv"])
            if tt.get("ngay") == "cot_phai":
                # Địa danh và ngày ban hành là trường của văn bản: "(Kèm theo Quyết định số …
                # ngày … tháng … năm …)" của văn bản kèm theo lặp lại ngày, tháng, năm. Một
                # ngày đủ ("25/9/2026") tách ra ba chỗ ở phép kiểm (`hieu_tai_lieu._tach_ngay`).
                p = self.doan(o_phai, can="center", truoc=120)
                mau = "{dia_danh}, ngày {ngay_ban_hanh} tháng {thang_ban_hanh} năm {nam_ban_hanh}"
                self.dong_mau(p, mau, o_phai, None, i=True)
            else:
                self.doan(o_phai, can="center")
        if not tt.get("vv"):
            self._ten_loai(truoc=360, ke=True)
        if tt.get("tham_quyen"):
            # Thẩm quyền ban hành (Mẫu 1.1–1.3): in hoa đậm giữa trang, trước căn cứ.
            p = self.doan(self.body, can="center", truoc=240, sau=60, giu_sau=True)
            self.dong_mau(p, tt["tham_quyen"], p, None, b=True, caps=True)

    def _ten_loai(self, *, truoc: int, ke: bool = False) -> None:
        """Tên loại, trích yếu (dòng mẫu `the_thuc.trich_yeu`, hay trích yếu của lượt),
        dòng "(Kèm theo …)" của văn bản kèm theo; `ke`: đường kẻ ngắn dưới cùng, dài 2/5
        dòng trích yếu (hay tên loại khi không có trích yếu) — Phụ lục I: 1/3–1/2.
        Tên loại in theo DÒNG của mẫu khi mẫu ngắt dòng (`the_thuc.ten_loai`; Mẫu 01-VDS:
        "ĐƠN YÊU CẦU" / "GIẢI QUYẾT VIỆC DÂN SỰ" / "(V/v: …)" nghiêng); `tieu_de` vẫn là
        tên của văn bản (tên tệp, tóm tắt)."""
        tt = self.spec.get("the_thuc") or {}
        if tt.get("ten_loai"):
            for k, d in enumerate(tt["ten_loai"]):
                mau, nghieng = (d.get("d", ""), bool(d.get("nghieng"))) if isinstance(d, dict) else (d, False)
                p = self.doan(self.body, can="center", truoc=0 if k else truoc, giu_sau=True)
                self.dong_mau(p, mau, p, None, b=True, i=nghieng)
        else:
            p = self.doan(self.body, can="center", truoc=truoc, giu_sau=True)
            p.append(_run(self.spec["tieu_de"], b=True))
        ke_dai = min(len(self.spec["tieu_de"]) * _RONG_KY_TU, self.rong) * 2 // 5
        mau_ty = tt.get("trich_yeu")
        # `trich_yeu: true`: mẫu có dòng trích yếu (NĐ 30 Mẫu 1.9: tên cuộc họp) — trích
        # yếu của lượt, chưa có thì chỗ trống của văn bản. `false`: mẫu không có dòng ấy.
        mau_ty = "{trich_yeu}" if mau_ty is True else (mau_ty or None)
        if mau_ty or self.spec.get("trich_yeu"):
            p = self.doan(self.body, can="center", giu_sau=True)
            self.dong_mau(p, mau_ty or "{trich_yeu}", p, None, b=True)
            chu = _chu_doan(p)
            ke_dai = self.rong // 5 if chu.strip() == CHO else min(len(chu) * _RONG_KY_TU, self.rong) * 2 // 5
        if tt.get("kem_theo"):
            p = self.doan(self.body, can="center", giu_sau=True)
            self.dong_mau(p, tt["kem_theo"], p, None, i=True)
        if ke:
            self.ke(self.body, self.rong, ke_dai, truoc=60 if tt.get("kem_theo") else 0)

    def kinh_gui(self) -> None:
        kg = (self.spec.get("the_thuc") or {}).get("kinh_gui")
        if not kg:
            return
        thut = kg.get("can") == "thut"
        trai = round(float(kg.get("thut_mm", 30)) * _MM) if thut else 0
        p = self.doan(self.body, can="left" if thut else "center", trai=trai, truoc=180, sau=120)
        self.dong_mau(p, kg["dong"], p, None, tab=thut, trai=trai)

    def can_cu(self) -> None:
        """Dòng căn cứ của kho (đủ số, ngày), rồi dòng căn cứ của khung (`can_cu_them`:
        "Căn cứ Điều lệ ……;", "Theo đề nghị của ……" — văn bản của chính tổ chức, không
        phải luật, nên là chỗ trống), rồi dòng lệnh ("QUYẾT ĐỊNH:", "QUYẾT NGHỊ:").
        Dòng khung đi sau thì dòng kho cuối kết bằng ";" (Phụ lục I: dòng cuối mới ".")."""
        tt = self.spec.get("the_thuc") or {}
        if tt.get("can_cu"):
            kho = [cc["dong"] for cc in self.spec.get("can_cu") or []]
            them = list(tt.get("can_cu_them") or [])
            if kho and them:
                kho[-1] = re.sub(r"\.\s*$", ";", kho[-1])
            for k, dong in enumerate([*kho, *them]):
                p = self.doan(self.body, thut_dau=_THUT, truoc=120 if k == 0 else 0, sau=60, dong=_DONG)
                if k < len(kho):
                    p.append(_run(dong, i=True))
                else:
                    # "……" giữa dòng: điền xong không còn dẫn chấm thừa, và dấu "." hết
                    # khối căn cứ ngay sau nó còn nguyên (`NOI`). `{dong, tab}`: chỗ trống
                    # cuối dòng là dẫn chấm tới lề.
                    mau, tab = (dong["dong"], True) if isinstance(dong, dict) else (dong, False)
                    self.dong_mau(p, mau, p, None, tab=tab, i=True)
        if tt.get("lenh"):
            p = self.doan(self.body, can="center", truoc=240, sau=120, giu_sau=True)
            p.append(_run(tt["lenh"], b=True))

    def than(self) -> list[Any]:
        """Thân bài theo `spec["than"]`; trả các đoạn thân bài (để gắn "./." cho
        văn bản hành chính)."""
        tt = self.spec.get("the_thuc") or {}
        thut = round(float(tt.get("thut_dong_mm", 0)) * _MM)
        doan_than: list[Any] = []
        dieu = list(self.spec.get("dieu") or [])
        theo_khoa = {d["key"]: d for d in dieu if d.get("key")}
        muc_co_dinh = muc_than(self.spec)
        con_lai = [d for d in dieu if d.get("key") not in muc_co_dinh]
        if self.nhu_than:
            # Một dòng trống giữa phần đầu (tên loại, Kính gửi) và thân — NĐ 124 Mẫu 01, NĐ 30
            # Mẫu 1.8, 1.9. Đoạn rỗng: không phải đơn vị văn bản.
            self.doan(self.body, dong=_DONG)
        for m in self.spec.get("than") or []:
            if "ben" in m:
                self._ben(m["ben"], thut)
            elif "dong" in m:
                # `tab`: chỗ trống cuối dòng là dẫn chấm tới lề phải (dòng trường của
                # biên bản); `dau`: phần đậm mở đầu ("Điều 1. ").
                giua = m.get("can") == "center"
                deu = bool(m.get("tab") and self.thut_nhan)
                p = self.doan(
                    self.body,
                    can=m.get("can", "left" if m.get("tab") else "both"),
                    thut_dau=0 if thut or giua else _THUT,
                    trai=thut,
                    truoc=0 if self.nhu_than else (60 if deu else 120),
                    sau=_SAU if self.nhu_than else (0 if deu else 60),
                    dong=_DONG,
                )
                if m.get("dau"):
                    p.append(_run(m["dau"], b=True))
                mau = _voi_loai(m["dong"], self.spec["tieu_de"])
                self.dong_mau(
                    p, mau, p, None, tab=bool(m.get("tab")), trai=thut, b=bool(m.get("dam")), i=bool(m.get("nghieng"))
                )
                # Dòng mẫu cuối thân nhận "./." như mọi đoạn thân (`_ket_bang_dau` không gắn
                # lần hai khi dòng đã kết bằng "./.", như Điều 3 của quyết định ban hành).
                doan_than.append(p)
            elif "muc" in m:
                doan_than += self._muc(m, theo_khoa.get(m["muc"]), thut)
            elif "bang" in m:
                self._bang(m["bang"])
                # Nội dung kết bằng bảng thì không có "./." nào (Phụ lục III đặt nó sau chữ).
                doan_than = []
            else:
                doan_than += self._dieu(con_lai, m["dieu"], thut)
        return doan_than

    def _bang(self, b: dict) -> None:
        """Bảng DỮ LIỆU có viền (phiếu đánh giá, tiến độ): hàng tiêu đề đậm lặp lại mỗi
        trang, rồi các hàng của mẫu. Ô `""` là ô trống điền được — bộ đọc gọi nó là chỗ
        `o` "<tên cột> (dòng n)"; ô có chữ giữ nguyên, `{}` trong ô là "……"."""
        rong = [self.rong * pt // 100 for _, pt in b["cot"]]
        rong[-1] += self.rong - sum(rong)
        tbl = _con(self.body, "tbl")
        pr = _con(tbl, "tblPr")
        _con(pr, "tblW", w=sum(rong), type="dxa")
        vien = _con(pr, "tblBorders")
        for c in ("top", "left", "bottom", "right", "insideH", "insideV"):
            _con(vien, c, val="single", sz=4, space=0, color="000000")
        _con(pr, "tblLayout", type="fixed")
        mar = _con(pr, "tblCellMar")
        # Thứ tự CT_TblCellMar: top, left, bottom, right.
        for canh, w in (("top", 20), ("left", 85), ("bottom", 20), ("right", 85)):
            _con(mar, canh, w=w, type="dxa")
        luoi = _con(tbl, "tblGrid")
        for w in rong:
            _con(luoi, "gridCol", w=w)
        sz = self.co - 2
        hang_bang = [[{"chu": ten, "dam": True, "can": "center"} for ten, _ in b["cot"]], *b["dong"]]
        for h, hang in enumerate(hang_bang):
            tr = _con(tbl, "tr")
            tr_pr = _con(tr, "trPr")
            _con(tr_pr, "cantSplit")
            if h == 0:
                _con(tr_pr, "tblHeader")
            cot = 0
            for o in hang:
                o = o if isinstance(o, dict) else {"chu": str(o)}
                gop = int(o.get("gop") or 1)
                tc = _con(tr, "tc")
                tc_pr = _con(tc, "tcPr")
                _con(tc_pr, "tcW", w=sum(rong[cot : cot + gop]), type="dxa")
                if gop > 1:
                    _con(tc_pr, "gridSpan", val=gop)
                _con(tc_pr, "vAlign", val="center")
                cot += gop
                # Hai hàng cuối đi cùng đoạn sau bảng (và qua nó, khối ký): trang cuối không
                # bao giờ chỉ có chữ ký (kế hoạch thực tập ba mục, 2026-09-29).
                p = self.doan(
                    tc,
                    can=o.get("can") or ("center" if cot == gop else "left"),
                    sz=sz,
                    dong=240,
                    giu_sau=h >= len(hang_bang) - 2,
                )
                if o.get("chu"):
                    self.dong_mau(p, o["chu"], tc, None, b=bool(o.get("dam")), sz=sz)
                else:
                    self.o[tc] = [None]
        # 6 pt tách bảng khỏi đoạn sau (và khỏi một bảng kế tiếp, Word gộp hai bảng liền
        # nhau). Đoạn rỗng: không phải đơn vị.
        self.doan(self.body, sz=12, dong=240, giu_sau=True)

    def _ben(self, khoa: str, thut: int) -> None:
        b = self.ben[khoa]
        thut = thut or self.thut_ben
        if b.get("tieu_de"):
            p = self.doan(self.body, can="left", trai=thut, truoc=120, sau=0, dong=_DONG, giu_sau=True)
            p.append(_run(b["tieu_de"], b=True))
        danh_muc = truong()
        nhan = b.get("nhan") or {}
        # Nhãn sát dấu hai chấm ("Họ và tên:……", như mẫu Chính phủ): bộ áp đặt MỘT dấu
        # cách trước giá trị chỗ `tab`, nhãn kết bằng dấu cách thì ra hai.
        dong = list(b.get("dong") or []) or [f"{nhan.get(t) or danh_muc[t]}:{{{t}}}" for t in b.get("truong") or []]
        for k, d in enumerate(dong):
            mau, dam = (d.get("d", ""), bool(d.get("dam"))) if isinstance(d, dict) else (d, False)
            # `cham`: dòng dài nhiều trường ("Số CMND/… ……, ngày cấp ……, nơi cấp: ……") — chỗ
            # trống "……" giữa dòng, dòng tự xuống như mẫu, thay cho các mốc tab.
            cham = isinstance(d, dict) and bool(d.get("cham"))
            p = self.doan(
                self.body,
                can="both" if cham else "left",
                trai=thut,
                thut_dau=_THUT if self.nhu_than else self.thut_nhan,
                truoc=0
                if self.nhu_than
                else (60 if self.thut_nhan else (120 if k == 0 and not b.get("tieu_de") else 0)),
                sau=_SAU if self.nhu_than else 0,
                dong=_DONG,
            )
            self.dong_mau(p, mau, p, khoa, tab=not cham, trai=thut, b=dam)

    def _muc(self, m: dict, d: dict | None, thut: int) -> list[Any]:
        """Một mục cố định của thân: nhãn nguyên văn của mẫu, rồi đoạn của mô hình;
        không có đoạn nào thì dòng nhãn mang MỘT chỗ trống dẫn chấm (hay `danh_sach`
        dòng đánh số). Một đoạn chỉ là "……" (mục luật đòi được chèn trống) cũng là mục
        trống: in đúng hình trống của MẪU (dòng dẫn chấm, "1. … 2. …"), không một dòng "……"."""
        doan = _doan_that(d)
        ra = []
        truoc = len(self.body)
        nhan = m.get("nhan")
        if nhan and "{}" in nhan:
            ra = self._muc_cung_dong(m, doan, thut)
            for p in self.body[truoc:]:
                self.thuoc[p] = m["muc"]
            return ra
        if nhan:
            p = self.doan(
                self.body,
                can="left" if not doan else "both",
                trai=thut,
                thut_dau=_THUT if self.nhu_than else self.thut_nhan,
                truoc=0 if self.nhu_than else 60,
                sau=_SAU // 2 if self.nhu_than else 0,
                dong=_DONG,
                giu_sau=bool(doan),
            )
            # `cho: false`: nhãn đứng một mình, không chỗ trống (NĐ 124 Mẫu 01 "(Tài liệu,
            # chứng cứ kèm theo - nếu có).").
            lien = not (doan or m.get("danh_sach") or m.get("cho") is False)
            # Chỗ trống sát nhãn: giá trị điền (bộ áp thêm một dấu cách trước giá trị `tab`)
            # cách nhãn đúng một dấu cách.
            self.dong_mau(
                p,
                nhan + ("{}" if lien else ""),
                p,
                None,
                tab=True,
                trai=thut,
                b=bool(m.get("dam")),
                i=bool(m.get("nghieng")),
            )
            if lien:
                # Dòng nhãn mang chỗ trống là dòng thân của mục ("./." có thể rơi vào nó).
                ra.append(p)
        if not doan and m.get("danh_sach"):
            # `dau_so`: dấu sau số thứ tự đúng như mẫu ("1." của Mẫu 01-VDS, "1" của 23-DS).
            for i in range(1, int(m["danh_sach"]) + 1):
                p = self.doan(self.body, can="left", trai=thut, sau=0, dong=_DONG)
                self.dong_mau(p, f"{i}{m.get('dau_so', '')} {{}}", p, None, tab=True, trai=thut)
        # Mục không nhãn mà mẫu không in khi trống (`cho: false`: yêu cầu giải quyết của NĐ
        # 124 Mẫu 01 nằm trong "Nội dung khiếu nại") — chỉ có mặt khi có chữ.
        if not doan and not nhan and m.get("cho") is not False:
            p = self.doan(self.body, thut_dau=_THUT, sau=_SAU, dong=_DONG)
            self.dong_mau(p, "{}", p, None)
            ra.append(p)
        for x in doan:
            p = self.doan(self.body, thut_dau=0 if thut else _THUT, trai=thut, sau=_SAU // 2, dong=_DONG)
            self._chu(p, x)
            ra.append(p)
        for p in self.body[truoc:]:
            self.thuoc[p] = m["muc"]
        return ra

    def _muc_cung_dong(self, m: dict, doan: list[str], thut: int) -> list[Any]:
        """Mục mà mẫu điền NGAY SAU nhãn, trên cùng dòng ("Khiếu nại về việc: ……(5);"
        của NĐ 124 Mẫu 01): `nhan` mang `{}` ở chỗ điền. Chưa có đoạn nào thì `{}` là
        chỗ trống dẫn chấm; có thì đoạn đầu nối vào sau nhãn, các đoạn sau xuống dòng,
        và dấu câu của mẫu sau `{}` (";", ".") kết đoạn cuối."""
        dau, _, duoi = m["nhan"].partition("{}")
        b, i = bool(m.get("dam")), bool(m.get("nghieng"))

        def _p() -> Any:
            return self.doan(
                self.body,
                can="both" if doan else "left",
                trai=thut,
                thut_dau=_THUT if self.nhu_than or not thut else 0,
                sau=_SAU // 2 if self.nhu_than else 0,
                dong=_DONG,
            )

        p = _p()
        if not doan:
            self.dong_mau(p, m["nhan"], p, None, tab=True, trai=thut, b=b, i=i)
            return [p]
        ra = []
        for k, x in enumerate(doan):
            if k:
                p = _p()
            elif dau:
                # "Nội dung khiếu nại:{}." — mẫu dính dãy chấm vào dấu hai chấm; chữ thì cách.
                p.append(_run(dau if dau.endswith(" ") else dau + " ", b=b, i=i))
            if k == len(doan) - 1 and duoi:
                x = x.rstrip(" .;:,") + duoi
            self._chu(p, x)
            ra.append(p)
        return ra

    def _dieu(self, dieu: list[dict], kieu: str, thut: int) -> list[Any]:
        ra = []
        mot = len(dieu) == 1 and kieu not in ("dieu", "lien")
        lan: Counter = Counter()
        for n, d in enumerate(dieu, 1):
            ten = str(d.get("ten") or "").strip()
            goc = str(d.get("key") or " ".join(ten.split()))
            thuoc, lan[goc] = f"{goc}#{lan[goc]}", lan[goc] + 1
            truoc = len(self.body)
            if kieu == "lien":
                # "Điều n." đậm mở đầu đoạn đầu; tên điều không in. Điều chỉ có chỗ trống
                # (điều luật đòi, chèn lúc tạo) thì in tên để người đọc biết điền gì.
                doan = [x for x in d.get("doan") or [] if x.strip()] or [CHO]
                if ten and all(x.strip() == CHO for x in doan):
                    doan = [f"{ten}: {CHO}"]
                for k, x in enumerate(doan):
                    p = self.doan(self.body, thut_dau=0 if thut else _THUT, trai=thut, sau=_SAU, dong=_DONG)
                    if k == 0:
                        p.append(_run(f"Điều {n}. ", b=True))
                    self._chu(p, x)
                    ra.append(p)
                for p in self.body[truoc:]:
                    self.thuoc[p] = thuoc
                continue
            if not mot and kieu != "doan" and (ten or kieu != "muc"):
                p = self.doan(
                    self.body, thut_dau=0 if thut else _THUT, trai=thut, truoc=120, sau=60, dong=_DONG, giu_sau=True
                )
                dau = {"dieu": f"Điều {n}. ", "so": f"{n}. ", "muc": ""}[kieu]
                if dau:
                    p.append(_run(dau, b=True))
                if ten:
                    p.append(_run(ten, b=True))
            doan = _doan_that(d)
            if not doan and kieu == "doan" and ten:
                # Thân lá đơn không in tên mục; mục luật đòi còn trống thì dòng của nó
                # mang tên mục làm nhãn ("Loại hợp đồng lao động đang thực hiện: ……").
                p = self.doan(self.body, thut_dau=0 if thut else _THUT, trai=thut, sau=_SAU, dong=_DONG)
                p.append(_run(f"{ten}:"))
                self.dong_mau(p, "{}", p, None, tab=True, trai=thut)
                ra.append(p)
            else:
                for x in doan or [CHO]:
                    p = self.doan(self.body, thut_dau=0 if thut else _THUT, trai=thut, sau=_SAU, dong=_DONG)
                    self._chu(p, x)
                    ra.append(p)
            for p in self.body[truoc:]:
                self.thuoc[p] = thuoc
        return ra

    def _chu(self, p: Any, chu: str) -> None:
        """Chữ của mô hình: nguyên văn, trừ "……" (chỗ trống cố ý, §6) ghi vào bản đồ."""
        for k, manh in enumerate(chu.split(CHO)):
            if k:
                p.append(_run(CHO))
                self.o.setdefault(p, []).append(None)
            if manh:
                p.append(_run(_sau_cho(manh) if k else manh))

    def ket_thuc(self) -> Any:
        mau = (self.spec.get("the_thuc") or {}).get("ket_thuc")
        if not mau:
            return None
        # Đi cùng trang với khối ký: câu kết không bị bỏ lại một mình ở trang trước.
        p = self.doan(self.body, thut_dau=_THUT, truoc=120, sau=_SAU, dong=_DONG, giu_sau=True)
        self.dong_mau(p, _voi_loai(mau, self.spec["tieu_de"]), p, None)
        return p

    def cuoi_ngay(self) -> None:
        if (self.spec.get("the_thuc") or {}).get("ngay") == "cuoi":
            _giu_voi_sau(self.body[-1])
            # Dòng ngày ở cuối đứng ngay trên người ký: cùng trang với khối ký.
            p = self.doan(self.body, can="right", truoc=240, giu_sau=True)
            self.dong_mau(p, _DIA_DANH_NGAY, p, None, i=True)

    def khoi_ky(self) -> None:
        ky = self.spec.get("ky") or {}
        theo = {o["khoa"]: o for o in ky.get("o") or []}
        nguoi = [theo[k] for k in ky.get("thu_tu") or [] if k in theo]
        tt = self.spec.get("the_thuc") or {}
        noi_nhan = tt.get("noi_nhan")
        # Biên bản (NĐ 30 Mẫu 1.9): hai người ký cùng hàng, "Nơi nhận" DƯỚI cả hai khối,
        # không ở cột trái.
        nn_cot = None if tt.get("noi_nhan_duoi") else noi_nhan
        if not nguoi and not noi_nhan:
            return
        # Đoạn cuối thân đi cùng trang với khối ký (đoạn cách `keepNext`, hàng ký
        # `cantSplit`): không bao giờ một trang chỉ có Nơi nhận và chữ ký.
        _giu_voi_sau(self.body[-1])
        # Khoảng trắng tách thân khỏi khối ký: một đoạn rỗng, không phải đơn vị.
        self.doan(self.body, sau=0, giu_sau=True)
        if nguoi:
            cot = len(nguoi) + (1 if nn_cot or len(nguoi) == 1 else 0)
            rong = [self.rong // cot] * cot
            if cot == 2 and (nn_cot or tt.get("noi_nhan_duoi")):
                # Hành chính: người ký thẳng cột quốc hiệu (38 % / 62 %, D2 §4.4).
                rong = [round(self.rong * 0.38)] * 2
            if len(ky.get("rong") or []) == cot:
                # Cột theo mẫu (NĐ 30 Mẫu 1.9: THƯ KÝ hẹp trái, CHỦ TỌA rộng phải cho ghi chú hai dòng).
                rong = [self.rong * pt // 100 for pt in ky["rong"]]
            rong[-1] += self.rong - sum(rong)
            tbl = self.bang(rong)
            o = self.hang(tbl, rong, khong_tach=True)
            if nn_cot or len(nguoi) == 1:
                o_trai, o = o[0], o[1:]
                if nn_cot:
                    self._noi_nhan(o_trai, nn_cot)
                else:
                    self.doan(o_trai)
            # Dòng họ tên các cột thẳng hàng dù chức danh, ghi chú dài ngắn khác nhau: cột ít
            # dòng hơn được đệm đoạn rỗng (không phải đơn vị) cùng cỡ chữ, sau chức danh và
            # sau ghi chú — không đo khoảng cách theo phông (Liberation Serif và Times New
            # Roman cao khác nhau).
            so_dong = [((_so_dong(x.get("vai")) or 1), _so_dong(x.get("ghi_chu"))) for x in nguoi]
            can = (max(a for a, _ in so_dong), max(g for _, g in so_dong))
            for tc, k in zip(o, nguoi, strict=True):
                self._nguoi_ky(tc, k, can)
        if noi_nhan and not nn_cot:
            self._noi_nhan(self.body, noi_nhan)
        if xn := ky.get("duoi"):
            # Khối xác nhận giữa trang dưới chữ ký các bên (Mẫu 02 NĐ 124/2020).
            for k, dong in enumerate(str(xn["vai"]).split("\n")):
                p = self.doan(self.body, can="center", truoc=360 if k == 0 else 0, giu_sau=True)
                p.append(_run(dong, b=True))
            if xn.get("ghi_chu"):
                p = self.doan(self.body, can="center", giu_sau=True)
                p.append(_run(xn["ghi_chu"], i=True))
            p = self.doan(self.body, can="center", truoc=1300)
            self.dong_mau(p, "{}", p, None, b=True)
        # Word luôn giữ một đoạn sau bảng cuối thân bài: dựng sẵn (1 pt, rỗng — không
        # phải đơn vị) để tệp mở ra không phải "sửa".
        self.doan(self.body, sz=2)

    def _noi_nhan(self, cha: Any, ds: list[str]) -> None:
        """ "Nơi nhận:" và các dòng "- …;". Trong ô của khối ký thì cả ô là MỘT đơn vị;
        dưới khối ký (biên bản) thì mỗi dòng là một đơn vị."""
        o_bang = cha is not self.body
        p = self.doan(cha, can="left", truoc=0 if o_bang else 240, sz=_CO["noi_nhan_nhan"])
        p.append(_run("Nơi nhận:", b=True, i=True, sz=_CO["noi_nhan_nhan"]))
        for d in ds:
            p = self.doan(cha, can="left", sz=_CO["noi_nhan"])
            self.dong_mau(p, f"- {d}", cha if o_bang else p, None, sz=_CO["noi_nhan"])

    def _nguoi_ky(self, tc: Any, o: dict, can: tuple[int, int] = (1, 0)) -> None:
        """Một cột ký. `can`: số dòng chức danh, số dòng ghi chú của cột cao nhất — cột
        này đệm đoạn rỗng tới đó để dòng họ tên thẳng hàng."""
        vai = o.get("vai")
        p = self.doan(tc, can="center")
        if vai:
            for k, dong in enumerate(str(vai).split("\n")):
                if k:
                    p = self.doan(tc, can="center")
                p.append(_run(dong.upper() if o.get("in_hoa", True) else dong, b=True))
        else:
            # Quyền hạn, chức vụ người ký (hành chính): chỗ trống của chính người ký.
            self.dong_mau(p, "{chuc_vu}", tc, o["khoa"], b=True, caps=True)
        for _ in range(can[0] - (_so_dong(vai) or 1)):
            self.doan(tc, can="center")
        ghi_chu = str(o.get("ghi_chu") or "").split("\n") if o.get("ghi_chu") else []
        for dong in ghi_chu:
            p = self.doan(tc, can="center")
            p.append(_run(dong, i=True))
        for _ in range(can[1] - len(ghi_chu)):
            self.doan(tc, can="center")
        if o.get("ho_ten_tu"):
            p = self.doan(tc, can="center", truoc=1300)
            self.dong_mau(p, f"{{{o['ho_ten_tu']}}}", tc, o["khoa"], b=True)

    # ─── đóng gói ───────────────────────────────────────────────────────

    def dung(self) -> tuple[bytes, dict]:
        bh = self.spec.get("ban_hanh")
        if bh:
            # Mẫu 1.3 NĐ 30/2020: QUYẾT ĐỊNH ban hành (căn cứ, khối ký, nơi nhận) ở trang
            # đầu, rồi văn bản kèm theo mang điều khoản của lượt. Văn bản kèm theo là một
            # văn bản riêng (tên loại, dòng "(Kèm theo …)" riêng): nó mở một PHÂN ĐOẠN mới
            # sang trang, số trang đếm lại từ 1, trang đầu không hiện số (Phụ lục I, Phần
            # I mục 7; phụ lục "được đánh số riêng", Phần III mục 1.đ).
            chinh = self.spec
            self.spec = {**chinh, **bh, "trich_yeu": chinh.get("trich_yeu"), "dieu": [], "ban_hanh": None}
            self._van_ban()
            p = self.body[-1] if self.body[-1].tag == _W + "p" else self.doan(self.body, sz=2)
            p.find(_W + "pPr").append(self._sect())
            self.spec = {**chinh, "can_cu": []}
        self._van_ban()
        self.body.append(self._sect(danh_lai=bool(bh)))
        return _dong_goi(self.body), self._ban_do()

    def _van_ban(self) -> None:
        self.dau_trang()
        self.kinh_gui()
        self.can_cu()
        doan_than = self.than()
        p_ket = self.ket_thuc()
        if self.spec.get("bo_cuc") == "hanh_chinh":
            # "./." sau đoạn cuối thân — câu kết của biên bản khi có (Mẫu 1.9).
            cuoi = p_ket if p_ket is not None else (doan_than[-1] if doan_than else None)
            if cuoi is not None:
                _ket_bang_dau(cuoi)
        self.cuoi_ngay()
        self.khoi_ky()

    def _sect(self, *, danh_lai: bool = False) -> Any:
        """`w:sectPr` (thứ tự con theo CT_SectPr): A4, lề, số trang ở lề trên trừ trang
        đầu (`titlePg`). `danh_lai`: phân đoạn sang trang mới, số trang đếm lại từ 1."""
        s = _e("sectPr")
        ref = _con(s, "headerReference", type="default")
        ref.set(f"{{{_R_NS}}}id", "rIdKlawH1")
        if danh_lai:
            _con(s, "type", val="nextPage")
        _con(s, "pgSz", w=_A4[0], h=_A4[1])
        tren, duoi, trai, phai = self.le
        _con(s, "pgMar", top=tren, right=phai, bottom=duoi, left=trai, header=567, footer=567, gutter=0)
        if danh_lai:
            _con(s, "pgNumType", start=1)
        _con(s, "titlePg")
        return s

    def _duong(self, vat: Any) -> tuple[str, tuple[int, ...]]:
        """Vật chứa → `(part, chi_muc)` đúng như bộ đọc ghim: chỉ số con PHẦN TỬ ở mỗi
        cấp từ `w:body` (`doc_tai_lieu.DiaChi`)."""
        duong = []
        nut = vat
        while nut is not self.body:
            cha = nut.getparent()
            duong.append(cha.index(nut))
            nut = cha
        return ("word/document.xml", tuple(reversed(duong)))

    def _ban_do(self) -> dict[tuple[str, tuple[int, ...]], list]:
        return {self._duong(vat): khoa for vat, khoa in self.o.items()}

    def thuoc_duong(self) -> dict[tuple[str, tuple[int, ...]], str]:
        return {self._duong(p): t for p, t in self.thuoc.items()}


def _so_dong(x: Any) -> int:
    return len(str(x).split("\n")) if x else 0


def _chu_doan(p: Any) -> str:
    return "".join(t.text or "" for t in p.iter(_W + "t"))


def _ten_van_ban(spec: dict) -> str:
    """Tên văn bản viết thường, hoa chữ đầu, cho câu của quyết định ban hành ("Ban hành
    kèm theo Quyết định này Quy chế quản lý tài sản"): tên loại, cộng trích yếu khi
    mẫu có dòng trích yếu — chưa có trích yếu thì là chỗ trống `{trich_yeu}`."""
    ten = " ".join(str(spec.get("tieu_de") or "văn bản").split()).lower()
    ten = ten[:1].upper() + ten[1:]
    if "{trich_yeu}" not in str((spec.get("the_thuc") or {}).get("trich_yeu") or ""):
        return ten
    ty = " ".join(str(spec.get("trich_yeu") or "").split())
    return f"{ten} {ty[:1].lower() + ty[1:]}" if ty else f"{ten} {{trich_yeu}}"


def _bo_tien_to(ty: str, truoc: str) -> str:
    """Trích yếu mô hình viết lặp lại chữ tĩnh đứng ngay trước chỗ của nó ("V/v …",
    "Về việc …") → bỏ phần lặp."""
    t = truoc.strip()
    return re.sub(rf"^\s*{re.escape(t)}\s*:?\s*", "", ty, flags=re.IGNORECASE) if t else ty


def _doan_that(d: dict | None) -> list[str]:
    """Đoạn có chữ của một điều khoản. Điều khoản chèn vì luật đòi (`them_dieu_bat_buoc`:
    một đoạn "……") là RỖNG: mục cố định in chỗ trống của chính mẫu, không "……" trơ trọi."""
    doan = [x for x in (d or {}).get("doan") or [] if x.strip()]
    return [] if all(x.strip() == CHO for x in doan) else doan


def _voi_loai(mau: str, tieu_de: str) -> str:
    """`{loai_thuong}` của dòng mẫu → tên loại viết thường ("HỢP ĐỒNG THUÊ NHÀ" →
    "hợp đồng thuê nhà"), hoa chữ đầu khi nó mở đầu câu."""
    ra = mau.replace("{loai_thuong}", " ".join(str(tieu_de or "văn bản").split()).lower())
    return ra[:1].upper() + ra[1:]


def _sau_cho(chu: str) -> str:
    """Chữ tĩnh đứng NGAY sau một "……": dấu "." mở đầu nó cách chỗ trống bằng `NOI`."""
    return NOI + chu if chu.startswith(".") else chu


def _giu_voi_sau(p: Any) -> None:
    """Đoạn `p` (khi là `w:p`) đi cùng trang với đoạn sau và không tách dòng —
    `keepNext`, `keepLines` ở đầu `w:pPr` (bộ dựng không dùng `pStyle`)."""
    if p.tag != _W + "p":
        return
    ppr = p.find(_W + "pPr")
    k = ppr.find(_W + "keepNext")
    if k is None:
        k = _e("keepNext")
        ppr.insert(0, k)
    if ppr.find(_W + "keepLines") is None:
        k.addnext(_e("keepLines"))


def _ket_bang_dau(p: Any) -> None:
    """ "./." sau đoạn cuối thân văn bản hành chính (mẫu Phụ lục III). Dòng mẫu đã kết
    bằng "./." (Điều 3 của quyết định ban hành) giữ nguyên."""
    if _chu_doan(p).rstrip().endswith("./."):
        return
    runs = p.findall(_W + "r")
    t = runs[-1].find(_W + "t") if runs else None
    if t is None:
        p.append(_run("./."))
        return
    s = (t.text or "").rstrip()
    if _chu_doan(p).rstrip().rstrip(".").rstrip(NOI).endswith(CHO):
        # Đoạn kết bằng chỗ trống (có thể kèm dấu chấm của câu, "giữ chức vụ ……."): `NOI`
        # tách "./." khỏi chỗ trống — dính vào thì dấu chấm thành một phần của dãy chấm,
        # và điền xong trang còn "Giám đốc/.".
        s = s.rstrip(".").rstrip(NOI) + NOI + "./."
    else:
        s = s[:-1] + "./." if s.endswith(".") else s + "./."
    t.text = s
    t.set(_XML_SPACE, "preserve")


# ─── các part cố định ─────────────────────────────────────────────────────

_KHAI = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
_CT = (
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/settings.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
    '<Override PartName="/word/header1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
    "</Types>"
)
_RELS = (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    'officeDocument" Target="word/document.xml"/></Relationships>'
)
_DOC_RELS = (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rIdKlawS" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    'styles" Target="styles.xml"/>'
    '<Relationship Id="rIdKlawT" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    'settings" Target="settings.xml"/>'
    '<Relationship Id="rIdKlawH1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    'header" Target="header1.xml"/></Relationships>'
)
_FONT = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" w:cs="Times New Roman"/>'
_STYLES = (
    f'<w:styles xmlns:w="{_W_NS}"><w:docDefaults><w:rPrDefault><w:rPr>{_FONT}'
    f'<w:sz w:val="{_CO_THAN}"/><w:szCs w:val="{_CO_THAN}"/><w:lang w:val="vi-VN" w:eastAsia="en-US" w:bidi="ar-SA"/>'
    '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    "</w:pPrDefault></w:docDefaults>"
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
    '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/>'
    '<w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
    '<w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/>'
    "</w:tblCellMar></w:tblPr></w:style></w:styles>"
)
_SETTINGS = (
    f'<w:settings xmlns:w="{_W_NS}"><w:defaultTabStop w:val="720"/><w:characterSpacingControl w:val="doNotCompress"/>'
    '<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" '
    'w:val="15"/></w:compat></w:settings>'
)
# Số trang giữa lề trên, cỡ 14, không ở trang 1 (`w:titlePg`, không đầu trang riêng
# cho trang đầu). Trường không mang kết quả dựng sẵn: Word và LibreOffice tự tính.
_HEADER = (
    f'<w:hdr xmlns:w="{_W_NS}"><w:p><w:pPr><w:jc w:val="center"/><w:rPr><w:sz w:val="28"/></w:rPr></w:pPr>'
    '<w:fldSimple w:instr=" PAGE "><w:r><w:rPr><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:r></w:fldSimple>'
    "</w:p></w:hdr>"
)
# Giờ cố định cho mọi mục zip: cùng `spec` ra cùng bytes (thiết kế §2).
_GIO = (1980, 1, 1, 0, 0, 0)


def _dong_goi(body: Any) -> bytes:
    doc = etree.Element(_W + "document", nsmap=_NSMAP)
    doc.append(body)
    phan = [
        ("[Content_Types].xml", _KHAI + _CT.encode()),
        ("_rels/.rels", _KHAI + _RELS.encode()),
        ("word/document.xml", _KHAI + etree.tostring(doc, encoding="UTF-8")),
        ("word/_rels/document.xml.rels", _KHAI + _DOC_RELS.encode()),
        ("word/styles.xml", _KHAI + _STYLES.encode()),
        ("word/settings.xml", _KHAI + _SETTINGS.encode()),
        ("word/header1.xml", _KHAI + _HEADER.encode()),
    ]
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for ten, du_lieu in phan:
            z.writestr(zipfile.ZipInfo(ten, _GIO), du_lieu, compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def dung_docx(spec: dict) -> tuple[bytes, dict[tuple[str, tuple[int, ...]], list[tuple[str, str] | None]]]:
    """`spec` (mục registry hay `khung_tong_quat`, cộng `tieu_de`, `trich_yeu`,
    `can_cu: [{dong, doc_id}]`, `dieu: [{key, ten, doan, can_cu}]`) → `(docx, ban_do)`.
    Thuần: cùng `spec` ra cùng bytes."""
    return dung_docx_thuoc(spec)[:2]


def dung_docx_thuoc(spec: dict) -> tuple[bytes, dict, dict[tuple[str, tuple[int, ...]], str]]:
    """`dung_docx` cộng đoạn nào thuộc Điều/mục nào: `{(part, chi_muc): "khoá#lần"}`
    (khoá checklist hay tên điều; đoạn khung không có mặt)."""
    d = _Dung(spec)
    docx, ban_do = d.dung()
    return docx, ban_do, d.thuoc_duong()


def dieu_khung(entry: dict, *, tieu_de: str | None, trich_yeu: str | None) -> list[str]:
    """Chữ các Điều của quyết định BAN HÀNH (`ban_hanh.than`, Mẫu 1.3) như trang in,
    chỗ trống là "……" — khung của mẫu, không phải điều khoản. `[]` khi mục không có
    quyết định ban hành."""
    bh = entry.get("ban_hanh") or {}
    ten = _ten_van_ban(spec_tu(entry, tieu_de=tieu_de, trich_yeu=trich_yeu, can_cu=[], dieu=[]))
    return [
        (m.get("dau") or "") + _RE_O.sub(CHO, m["dong"].replace("{ten_van_ban}", ten))
        for m in bh.get("than") or []
        if "dong" in m
    ]


def spec_tu(
    entry: dict,
    *,
    tieu_de: str | None,
    trich_yeu: str | None,
    can_cu: list[dict],
    dieu: list[dict],
    ben: list[dict] | None = None,
) -> dict:
    """Ghép khung (mục registry hay `khung_tong_quat`) với phần đổi theo lượt: loại của
    bên tuỳ loại (`chon_ben`), căn cứ đúng các Điều đang có (`can_cu_hien`)."""
    return {
        **chon_ben(entry, ben),
        "tieu_de": " ".join(str(tieu_de or entry.get("tieu_de") or "VĂN BẢN").split()).upper(),
        "trich_yeu": (" ".join(str(trich_yeu).split()) or None) if trich_yeu else None,
        "can_cu": can_cu_hien(list(can_cu or []), list(dieu or [])),
        "dieu": list(dieu or []),
    }
