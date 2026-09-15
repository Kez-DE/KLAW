"""Xếp một văn bản vào 15 lĩnh vực pháp luật chuẩn (spec 2026-09-15d).

`documents.linh_vuc` lấy nguyên văn từ nguồn: 56 giá trị tự do và chỉ 88/1634
văn bản có giá trị. `retrieval.loc_theo_linh_vuc` lại BẬT mặc định, nên bộ lọc
lĩnh vực đang lọc trên một cột rỗng 95% — nó fail-open nên không ai thấy, nhưng
nó cũng không lọc gì cả.

Bộ từ khoá là DỮ LIỆU (`config/linh_vuc.yaml`), phép khớp là tra chuỗi tất định,
0 token — cùng nguyên tắc `phan_loai_tai_lieu` và `route.R-INT-001`.

**Chồng lấn giải bằng độ cụ thể.** "Bộ luật Tố tụng dân sự" khớp cả `dan_su` lẫn
`to_tung`. Nếu để bảng chữ cái hay thứ tự nạp quyết định thì mọi luật tố tụng rơi
vào dân sự và bộ lọc thành vô nghĩa. `uu_tien` trong YAML nói rõ nhóm nào cụ thể
hơn, và số nhỏ hơn thắng.

**Dám trả None.** Văn bản không khớp nhóm nào để trống. Dồn vào
`hien_phap_hanh_chinh` cho đủ sẽ biến một nhóm thật thành thùng rác, và bộ lọc
"hành chính" sau đó kéo về đủ thứ không liên quan.
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

DUONG_DAN = Path("config/linh_vuc.yaml")


@dataclass(frozen=True)
class LinhVuc:
    slug: str
    ten: str
    uu_tien: int
    tu_khoa: tuple[str, ...]


@dataclass(frozen=True)
class KetQuaLinhVuc:
    linh_vuc: str
    linh_vuc_ten: str
    tu_khoa: str
    """Từ khoá đã khớp. Một phép xếp loại không nói được vì sao thì không sửa được."""


def _chuan(s: str) -> str:
    """Bỏ dấu để so từ khoá — KHÔNG phải nới phép kiểm trích dẫn.

    Ở đây ta xếp văn bản vào nhóm; ở `verify_tier1.normalize` ta đối chiếu một
    trích dẫn với điều luật, và ở đó dấu là chữ chứ không phải trang trí.
    """
    s = unicodedata.normalize("NFD", (s or "").lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", s)).strip()


@lru_cache(maxsize=4)
def _nap(truc: str) -> dict[str, LinhVuc]:
    d = yaml.safe_load(DUONG_DAN.read_text(encoding="utf-8"))[truc]
    return {
        slug: LinhVuc(
            slug=slug, ten=v["ten"], uu_tien=int(v["uu_tien"]), tu_khoa=tuple(v["tu_khoa"])
        )
        for slug, v in d.items()
    }


NGANH_LUAT = _nap("nganh_luat")
"""12 ngành luật — phân loại học thuật, trích dẫn được, gộp mạnh."""

LINH_VUC = _nap("linh_vuc")
"""27 lĩnh vực — phân loại thực dụng, mịn hơn, lọc retrieval tốt hơn."""


def phan_nganh_luat(
    *, ten: str = "", linh_vuc_nguon: str = "", co_quan: str = ""
) -> KetQuaLinhVuc | None:
    """Ngành luật (trục 12). Xem `phan_linh_vuc` cho cách khớp."""
    return _khop(NGANH_LUAT, ten=ten, linh_vuc_nguon=linh_vuc_nguon, co_quan=co_quan)


def phan_linh_vuc(
    *, ten: str = "", linh_vuc_nguon: str = "", co_quan: str = ""
) -> KetQuaLinhVuc | None:
    """Lĩnh vực (trục 27) của văn bản, hoặc `None` khi không khớp nhóm nào.

    Ba nguồn tín hiệu, gộp lại rồi tra một lần: tên văn bản mang nhiều thông tin
    nhất, `linh_vuc` nguồn lộn xộn nhưng vẫn là tín hiệu, cơ quan ban hành cứu
    được những thông tư chỉ có số hiệu trong tên.

    Khi nhiều nhóm cùng khớp, nhóm CỤ THỂ HƠN thắng (`uu_tien` nhỏ hơn); cùng ưu
    tiên thì từ khoá dài hơn thắng, vì nó mô tả hẹp hơn.
    """
    return _khop(LINH_VUC, ten=ten, linh_vuc_nguon=linh_vuc_nguon, co_quan=co_quan)


def _khop(
    bang: dict[str, LinhVuc], *, ten: str = "", linh_vuc_nguon: str = "", co_quan: str = ""
) -> KetQuaLinhVuc | None:
    chu = " ".join(_chuan(x) for x in (ten, linh_vuc_nguon, co_quan) if x).strip()
    if not chu:
        return None
    # Đệm khoảng trắng hai đầu để so THEO RANH GIỚI TỪ. Không có nó thì `gia`
    # khớp bên trong `giao` ("giao thông", "giáo dục") và cuối "quốc gia" — đo
    # được, ba ca sai trong lần chạy đầu.
    khung = f" {chu} "

    tot: tuple[int, int, LinhVuc, str] | None = None
    for lv in bang.values():
        for tu in lv.tu_khoa:
            t = _chuan(tu)
            if not t or f" {t} " not in khung:
                continue
            khoa = (lv.uu_tien, -len(t))
            if tot is None or khoa < (tot[0], tot[1]):
                tot = (lv.uu_tien, -len(t), lv, t)
    if tot is None:
        return None
    return KetQuaLinhVuc(linh_vuc=tot[2].slug, linh_vuc_ten=tot[2].ten, tu_khoa=tot[3])
