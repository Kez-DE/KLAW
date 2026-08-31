"""Checklist nội dung bắt buộc của HĐLĐ (BLLĐ Đ21.1 × TT 10/2020 Đ3).

Checklist nạp từ config/checklist_hdld.yaml — DỮ LIỆU, không phải mã nguồn, cùng
khuôn với config/rules.yaml + src/services/rules.py (Task 2): sửa checklist
là sửa YAML, không đụng module này.

Ba ngoại lệ, nếu bỏ qua sẽ báo sai (can_cu của từng ngoại lệ nằm trong
config/checklist_hdld.yaml):
  Đ21.3  nông/lâm/ngư/diêm nghiệp ĐƯỢC GIẢM một số mục, và phải THÊM điều
         khoản thiên tai → denominator (tong_muc) đổi theo ngành, KHÔNG cố
         định 10.
  Đ21.2  bí mật KD/công nghệ là QUYỀN, không bắt buộc → đừng báo thiếu. Được
         encode CHỦ ĐỘNG bằng cách loại `khong_bat_buoc.keys` khỏi danh sách
         bắt buộc trước khi so sánh — không phụ thuộc vào việc `muc` tình cờ
         không chứa key đó.
  TT10   phúc lợi khác phải ghi mục riêng (Đ3.5.c) → quy tắc ĐỊNH DẠNG văn
         bản, không phải nội dung có/thiếu. `check_completeness` chỉ nhận
         `clauses: list[dict]` dạng khoá hiện diện/vắng mặt — không đủ thông
         tin cấu trúc (mục nào gộp mục nào) để kiểm tự động ở dạng đó.
         `quy_tac_dinh_dang` được nạp cùng can_cu đã xác thực trong DB, giữ
         làm dữ liệu tham chiếu cho một rule tương lai — cùng vai trò với
         `bang_gio` (chưa rule nào dùng) trong config/rules.yaml.

Giá trị `nganh` lạ (không có trong nganh_duoc_giam.danh_sach) KHÔNG ném lỗi:
phép kiểm dùng `in` trên một danh sách, không tra từ điển theo khoá, nên
không có nguy cơ KeyError như `bang_thang[vung]` của Task 2 — một ngành lạ
đơn giản là một ngành không được giảm mục nào.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text

from src.services.db import get_engine


@dataclass(frozen=True)
class Checklist:
    can_cu_goc: str
    can_cu_chi_tiet: str
    muc: list[dict]
    nganh_duoc_giam: dict[str, Any]
    khong_bat_buoc: dict[str, Any]
    quy_tac_dinh_dang: dict[str, Any]


@dataclass(frozen=True)
class Completeness:
    ty_le: float
    tong_muc: int
    co: list[str] = field(default_factory=list)
    thieu: list[str] = field(default_factory=list)
    duoc_phep_giam: list[str] = field(default_factory=list)


def load_checklist(path: Path) -> Checklist:
    """Đọc checklist từ YAML. Không kiểm can_cu với DB — xem
    `kiem_tra_can_cu_ton_tai` bên dưới, tách riêng vì lý do tương tự
    `load_rules`/`kiem_tra_can_cu_ton_tai` ở rules.py: import module này
    không được ép buộc phải có kết nối Postgres.
    """
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Checklist(
        can_cu_goc=d["can_cu_goc"],
        can_cu_chi_tiet=d["can_cu_chi_tiet"],
        muc=d["muc"],
        nganh_duoc_giam=d["nganh_duoc_giam"],
        khong_bat_buoc=d["khong_bat_buoc"],
        quy_tac_dinh_dang=d["quy_tac_dinh_dang"],
    )


def cac_can_cu(cl: Checklist) -> set[str]:
    """Mọi can_cu mà checklist này trích dẫn: 10 mục + 3 ngoại lệ + can_cu chi
    tiết cấp checklist. Dùng bởi `kiem_tra_can_cu_ton_tai`.
    """
    return {
        cl.can_cu_goc,
        cl.can_cu_chi_tiet,
        cl.nganh_duoc_giam["can_cu"],
        cl.khong_bat_buoc["can_cu"],
        cl.quy_tac_dinh_dang["can_cu"],
        *(m["can_cu"] for m in cl.muc),
    }


def kiem_tra_can_cu_ton_tai(cl: Checklist, duong_dan_hop_le: set[str] | None = None) -> None:
    """Raise loudly nếu bất kỳ can_cu nào của checklist không phải một
    `provisions.duong_dan` có thật. Vai trò giống hàm cùng tên ở rules.py,
    viết riêng vì Checklist không có shape `list[Rule]`.

    Pass `duong_dan_hop_le` để kiểm không cần DB thật (unit test nhanh).
    """
    if duong_dan_hop_le is None:
        with get_engine().connect() as conn:
            duong_dan_hop_le = {row[0] for row in conn.execute(text("SELECT duong_dan FROM provisions")).all()}
    thieu = sorted(cac_can_cu(cl) - duong_dan_hop_le)
    if thieu:
        raise ValueError(f"can_cu không tồn tại trong provisions.duong_dan: {thieu}")


def check_completeness(cl: Checklist, clauses: list[dict], nganh: str) -> Completeness:
    """So khớp các `clauses` (mỗi clause có `key`) đã trích xuất từ văn bản
    với danh sách mục bắt buộc, áp dụng ngoại lệ Đ21.2 và Đ21.3.
    """
    co = {c["key"] for c in clauses if c.get("key")}
    khong_bat_buoc_keys = set(cl.khong_bat_buoc["keys"])
    bat_buoc = [m["key"] for m in cl.muc if m["key"] not in khong_bat_buoc_keys]

    duoc_giam: list[str] = []
    if nganh in cl.nganh_duoc_giam["danh_sach"]:
        duoc_giam = list(cl.nganh_duoc_giam["duoc_giam_muc"])
        bat_buoc = [k for k in bat_buoc if k not in duoc_giam]
        bat_buoc.append(cl.nganh_duoc_giam["bat_buoc_them"]["key"])

    thieu = [k for k in bat_buoc if k not in co]
    ty_le = (len(bat_buoc) - len(thieu)) / len(bat_buoc) if bat_buoc else 1.0
    return Completeness(
        round(ty_le, 4),
        len(bat_buoc),
        co=sorted(co & set(bat_buoc)),
        thieu=thieu,
        duoc_phep_giam=[k for k in duoc_giam if k not in co],
    )
