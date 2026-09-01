"""Checklist nội dung bắt buộc của một loại văn bản — DỮ LIỆU, không phải mã.

Mỗi loại văn bản là MỘT file `config/checklist_<loai>.yaml`; thêm một mẫu soạn
thảo mới là thêm một file, không đụng module này. Cùng khuôn với
config/rules.yaml + src/services/rules.py (Task 2).

Ba khối ngoại lệ (`nganh_duoc_giam`, `khong_bat_buoc`, `quy_tac_dinh_dang`) là
TUỲ CHỌN — chúng encode ba ngoại lệ RIÊNG của hợp đồng lao động, và một checklist
khác (nội quy lao động, đơn khởi kiện, hợp đồng vay…) không có lý do gì phải khai
báo chúng rỗng để nạp được. Vắng mặt = ngoại lệ đó không áp dụng cho loại này.

Ba ngoại lệ của HĐLĐ, nếu bỏ qua sẽ báo sai (can_cu của từng ngoại lệ nằm trong
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

`rules:` liệt kê ID các rule của config/rules.yaml áp dụng cho loại văn bản này.
Rule là một THƯ VIỆN DÙNG CHUNG, checklist chọn cái nào áp dụng: chạy
`thu_viec_toi_da` (thời gian thử việc theo BLLĐ Đ25) lên một hợp đồng vay tài
sản là vô nghĩa, và một checklist mới không được thừa hưởng rule của HĐLĐ chỉ
vì chúng nằm chung một file.
"""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text

from src.services.db import get_engine


@dataclass(frozen=True)
class Checklist:
    loai: str
    # `ten` đi thẳng vào prompt draft_generate ("Soạn {loai_van_ban}…") nên PHẢI
    # là cụm tiếng Việt tự nhiên; `tieu_de` là dòng tiêu đề Markdown của văn bản
    # sinh ra. Cả hai từng là hai dict viết cứng trong Python (TEN_LOAI_VAN_BAN,
    # _TIEU_DE_VAN_BAN) — nghĩa là thêm một mẫu phải sửa hai file mã nguồn ngoài
    # YAML, đúng thứ khuôn "checklist là DỮ LIỆU" tồn tại để tránh.
    ten: str
    tieu_de: str
    can_cu_goc: str
    muc: list[dict]
    rules: list[str] = field(default_factory=list)
    can_cu_chi_tiet: str | None = None
    nganh_duoc_giam: dict[str, Any] = field(default_factory=dict)
    khong_bat_buoc: dict[str, Any] = field(default_factory=dict)
    quy_tac_dinh_dang: dict[str, Any] = field(default_factory=dict)


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
    thieu = [k for k in ("loai", "ten", "tieu_de", "can_cu_goc", "muc") if not d.get(k)]
    if thieu:
        raise ValueError(f"{path}: thiếu khoá bắt buộc {thieu}")
    trung = _key_trung_lap([m["key"] for m in d["muc"]])
    if trung:
        raise ValueError(f"{path}: key mục trùng lặp {trung} — completeness sẽ đếm sai")
    return Checklist(
        loai=d["loai"],
        ten=d["ten"],
        tieu_de=d["tieu_de"],
        can_cu_goc=d["can_cu_goc"],
        muc=d["muc"],
        rules=list(d.get("rules") or []),
        can_cu_chi_tiet=d.get("can_cu_chi_tiet"),
        nganh_duoc_giam=d.get("nganh_duoc_giam") or {},
        khong_bat_buoc=d.get("khong_bat_buoc") or {},
        quy_tac_dinh_dang=d.get("quy_tac_dinh_dang") or {},
    )


def _key_trung_lap(keys: list[str]) -> list[str]:
    return sorted(k for k, n in Counter(keys).items() if n > 1)


def cac_can_cu(cl: Checklist) -> set[str]:
    """Mọi can_cu mà checklist này trích dẫn: từng mục + mọi khối ngoại lệ CÓ
    khai báo + can_cu gốc/chi tiết cấp checklist. Dùng bởi
    `kiem_tra_can_cu_ton_tai` — một khối ngoại lệ vắng mặt không đóng góp can_cu
    nào, chứ không phải một can_cu rỗng lọt qua phép kiểm.
    """
    ngoai_le = (cl.nganh_duoc_giam, cl.khong_bat_buoc, cl.quy_tac_dinh_dang)
    return {
        cl.can_cu_goc,
        *([cl.can_cu_chi_tiet] if cl.can_cu_chi_tiet else []),
        *(k["can_cu"] for k in ngoai_le if k.get("can_cu")),
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
    khong_bat_buoc_keys = set(cl.khong_bat_buoc.get("keys") or [])
    bat_buoc = [m["key"] for m in cl.muc if m["key"] not in khong_bat_buoc_keys]

    duoc_giam: list[str] = []
    if nganh in (cl.nganh_duoc_giam.get("danh_sach") or []):
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
