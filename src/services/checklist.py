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

# Hai giá trị, cố ý KHÔNG có giá trị thứ ba cho mẫu "lai". `quyet_dinh_bo_nhiem`
# có chín mục thể thức CỘNG một rule nội dung: `pham_vi_soat` mô tả các MỤC, còn
# phần nội dung của nó nằm ở `rules` và lộ ra API qua `facts`. Bên gọi ghép hai
# thứ đó: `the_thuc` + `facts` rỗng = CHỈ soát thể thức; `the_thuc` + có `facts`
# = thể thức cộng quy tắc. Thêm một enum "the_thuc_va_quy_tac" sẽ là dữ liệu
# suy được từ hai trường đã có, và nó sẽ lệch vào ngày ai đó thêm rule mà quên
# đổi enum.
PHAM_VI_SOAT = frozenset({"noi_dung", "the_thuc"})

# Hai phần mà MỌI hợp đồng bằng văn bản phải có nhưng KHÔNG checklist nào liệt
# kê — vì các checklist dựng trên điều luật quy định NỘI DUNG bắt buộc (Đ398.2,
# Đ430, Đ21…), không quy định giải phẫu của một văn bản hợp đồng.
#
# Không phải khung trang trí, cả hai có căn cứ thật:
#   Đ385   — "Hợp đồng là sự thoả thuận GIỮA CÁC BÊN…". Không nêu các bên thì
#            không xác định được ai thoả thuận với ai.
#   Đ400.4 — "Thời điểm giao kết hợp đồng BẰNG VĂN BẢN là thời điểm BÊN SAU
#            CÙNG KÝ vào văn bản…". Với hợp đồng bằng văn bản, chữ ký là thứ
#            LÀM NÊN việc giao kết — chưa ký thì chưa có hợp đồng.
#
# Ở đây chứ không trong 12 file YAML: hai điều này giống hệt nhau ở mọi hợp
# đồng, nên chép 12 lần là 12 chỗ để lệch. Và ở đây chứ không trong frontend:
# một can_cu nằm trong frontend sẽ không bao giờ đi qua cổng
# `test_moi_can_cu_trong_cau_truc_phan_giai_duoc`.
#
# CỐ Ý KHÔNG phải là `muc`: chúng không nằm trong mẫu số của
# `check_completeness`, nên tỷ lệ trên giao diện khớp đúng con số `/soat` trả về.
KHUNG_HOP_DONG: tuple[dict[str, str], ...] = (
    {"key": "cac_ben",
     "ten": "Thông tin các bên giao kết hợp đồng",
     "can_cu": "91/2015/QH13 > Điều 385"},
    {"key": "chu_ky",
     "ten": "Chữ ký, đóng dấu của các bên",
     "can_cu": "91/2015/QH13 > Điều 400 > Khoản 4"},
)


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
    # Đơn vị đánh số mục của văn bản sinh ra: "Điều" cho hợp đồng và nội quy,
    # "Mục" cho đơn từ và biên bản — một lá đơn khởi kiện chia thành "Điều 1."
    # đọc sai thể loại ngay từ dòng đầu. `extract_clauses` cắt văn bản theo
    # CHÍNH đơn vị này, nên soạn ra rồi đem soát lại vẫn tách đúng số mục.
    muc: list[dict]
    don_vi_muc: str = "Điều"
    # Mức độ của finding khi một mục bắt buộc VẮNG MẶT. "chan" khi luật liệt kê
    # nội dung bằng chữ "PHẢI CÓ"/"bao gồm những nội dung chủ yếu" (Đ21.1 HĐLĐ,
    # Đ118.2 nội quy, Đ189.4 đơn khởi kiện). "canh_bao" khi luật nói "CÓ THỂ
    # gồm" (BLDS Đ398.2 — nội dung của hợp đồng nói chung): ở đó một mục thiếu
    # là hợp đồng SƠ SÀI, không phải hợp đồng TRÁI LUẬT, và gọi nó là trái luật
    # đúng bằng loại khẳng định sai mà hệ thống này tồn tại để không mắc phải.
    muc_do_thieu: str = "chan"
    # `the_thuc` khi các MỤC của checklist là thành phần trình bày (quốc hiệu,
    # số ký hiệu, nơi nhận — NĐ 30/2020 Đ8.2), `noi_dung` khi chúng là nội dung
    # nghiệp vụ luật đòi (BLLĐ Đ21.1, Đ118.2, BLTTDS Đ189.4, Luật Khiếu nại
    # Đ8.2). Mặc định `noi_dung` vì đó là đa số và vì đoán nhầm theo hướng đó
    # AN TOÀN HƠN: gắn nhãn "chỉ soát thể thức" cho một mẫu soát nội dung làm
    # người dùng coi nhẹ một phát hiện thật.
    #
    # Trường này TỒN TẠI ĐỂ LỘ RA API. Trước nó, giới hạn "1.0 nghĩa là đủ chín
    # thành phần, không phải viết đúng việc" chỉ nằm trong COMMENT đầu file
    # checklist_cong_van.yaml — người đọc YAML thấy, `GET /mau/{loai}` không
    # thấy, nên frontend không có cách nào gắn nhãn đúng ngoài việc viết cứng
    # một danh sách tên loại và để nó lệch vào ngày thêm mẫu.
    pham_vi_soat: str = "noi_dung"
    # `True` khi checklist dựng trên CHẾ ĐỊNH HỢP ĐỒNG (BLDS Đ385: "sự thoả
    # thuận GIỮA CÁC BÊN"). Chỉ khi đó văn bản mới có giải phẫu hai bên + chỗ ký
    # — xem `KHUNG_HOP_DONG` dưới đây.
    #
    # Mặc định `False`, và hướng mặc định đó CÓ CHỦ Ý: một mẫu mới quên khai cờ
    # sẽ KHÔNG mọc ra khối "BÊN A / BÊN B" — thiếu một khối là lỗi trình bày,
    # thêm nhầm một khối vào đơn khiếu nại hay quyết định kỷ luật là sai thể
    # loại văn bản.
    #
    # Phải là một trường TRONG YAML chứ không phải danh sách tên loại trong
    # Python, cùng lý do với `pham_vi_soat`: danh sách viết cứng lệch đúng vào
    # ngày thêm mẫu. Và KHÔNG suy được từ `can_cu_goc` — cùng một văn bản gốc
    # chứa cả hai loại (91/2015/QH13 có Đ430 hợp đồng mua bán VÀ Đ138 giấy uỷ
    # quyền; 45/2019/QH14 có Đ21 HĐLĐ VÀ Đ118 nội quy) — cũng không suy được từ
    # `muc` (giay_uy_quyen có `ben_uy_quyen` nhưng là hành vi MỘT bên).
    la_hop_dong: bool = False
    rules: list[str] = field(default_factory=list)
    can_cu_chi_tiet: str | None = None
    # Điều luật trao THẨM QUYỀN ban hành văn bản (LDN Đ153.3: HĐQT thông qua nghị quyết)
    # khi các mục chỉ dẫn tới nguồn thể thức (NĐ 30/2020, không in thành căn cứ): văn
    # bản của chúng vào khối "Căn cứ" của khuôn mẫu (quyết định 2026-09-29 mục 7), không
    # là mục nào của checklist.
    can_cu_ban_hanh: list[str] = field(default_factory=list)
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
    pham_vi = d.get("pham_vi_soat") or "noi_dung"
    if pham_vi not in PHAM_VI_SOAT:
        # Không im lặng rơi về mặc định: một giá trị gõ sai ("the_thức",
        # "hinh_thuc") sẽ thành `noi_dung` và mẫu chỉ soát bìa thư được gắn
        # nhãn soát nội dung — đúng lời hứa sai mà trường này sinh ra để chặn.
        raise ValueError(
            f"{path}: pham_vi_soat={pham_vi!r} không hợp lệ, phải là một trong {sorted(PHAM_VI_SOAT)}")
    return Checklist(
        loai=d["loai"],
        ten=d["ten"],
        tieu_de=d["tieu_de"],
        can_cu_goc=d["can_cu_goc"],
        muc=d["muc"],
        don_vi_muc=d.get("don_vi_muc") or "Điều",
        muc_do_thieu=d.get("muc_do_thieu") or "chan",
        pham_vi_soat=pham_vi,
        la_hop_dong=bool(d.get("la_hop_dong")),
        rules=list(d.get("rules") or []),
        can_cu_chi_tiet=d.get("can_cu_chi_tiet"),
        can_cu_ban_hanh=list(d.get("can_cu_ban_hanh") or []),
        nganh_duoc_giam=d.get("nganh_duoc_giam") or {},
        khong_bat_buoc=d.get("khong_bat_buoc") or {},
        quy_tac_dinh_dang=d.get("quy_tac_dinh_dang") or {},
    )


def _key_trung_lap(keys: list[str]) -> list[str]:
    return sorted(k for k, n in Counter(keys).items() if n > 1)


def cac_can_cu(cl: Checklist) -> set[str]:
    """Mọi can_cu mà checklist này trích dẫn: từng mục + mọi khối ngoại lệ CÓ
    khai báo + can_cu gốc/chi tiết/ban hành cấp checklist. Dùng bởi
    `kiem_tra_can_cu_ton_tai` — một khối ngoại lệ vắng mặt không đóng góp can_cu
    nào, chứ không phải một can_cu rỗng lọt qua phép kiểm.
    """
    ngoai_le = (cl.nganh_duoc_giam, cl.khong_bat_buoc, cl.quy_tac_dinh_dang)
    return {
        cl.can_cu_goc,
        *([cl.can_cu_chi_tiet] if cl.can_cu_chi_tiet else []),
        *cl.can_cu_ban_hanh,
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
