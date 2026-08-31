"""Tải toàn văn 21 văn bản từ API MOJ vào data/raw/moj/*.json."""

from pathlib import Path

from src.config import get_settings
from src.services.moj_client import MojClient

# doc_id → (depth, so_ky_hieu).  Xác minh 2026-08-27 qua metadata.parquet + API live.
DOC_IDS: dict[str, tuple[str, str]] = {
    # ── 6 Bộ luật — trục tra cứu (tầng sâu-A) ──
    "95942": ("deep", "91/2015/QH13"),    # Bộ luật Dân sự
    "96122": ("deep", "100/2015/QH13"),   # Bộ luật Hình sự
    "96115": ("deep", "92/2015/QH13"),    # Bộ luật Tố tụng dân sự
    "96172": ("deep", "101/2015/QH13"),   # Bộ luật Tố tụng hình sự
    "139264": ("deep", "45/2019/QH14"),   # Bộ luật Lao động
    "96117": ("deep", "95/2015/QH13"),    # Bộ luật Hàng hải (title CSDL = "Hàng hải")
    # ── Cụm Lao động — trục soạn thảo (tầng sâu-B) ──
    "152668": ("deep", "145/2020/NĐ-CP"),
    "146696": ("deep", "10/2020/TT-BLĐTBXH"),
    "183939": ("deep", "293/2025/NĐ-CP"),
    "185561": ("deep", "337/2025/NĐ-CP"),
    "153913": ("deep", "12/2022/NĐ-CP"),
    "152670": ("deep", "09/2020/TT-BLĐTBXH"),
    "153297": ("deep", "18/2021/TT-BLĐTBXH"),
    "152734": ("deep", "135/2020/NĐ-CP"),
    "134611": ("deep", "29/2019/NĐ-CP"),
    "70811": ("deep", "84/2015/QH13"),
    # ── Tập bẫy hiệu lực: PHẢI ingest dù đã hết hiệu lực (spec 4.3 tầng 3) ──
    "168670": ("deep", "74/2024/NĐ-CP"),  # hết hiệu lực toàn bộ → test Mức 1
    "139094": ("deep", "90/2019/NĐ-CP"),  # MOJ đánh sai "còn hiệu lực" → test Mức 2
    "132862": ("deep", "157/2018/NĐ-CP"), # lương tối thiểu cũ — MOJ đánh sai "Còn hiệu lực"
    "126319": ("deep", "141/2017/NĐ-CP"), # lương tối thiểu cũ — MOJ đánh sai "Còn hiệu lực"
    "92898":  ("deep", "122/2015/NĐ-CP"), # lương tối thiểu cũ — MOJ đánh sai "Còn hiệu lực"
    # ── Hai luật ĐANG SỬA Bộ luật Lao động (bản đồ `sua_doi_dieu_khoan`) ──
    # Không có chúng, hệ thống nói đúng "Điều 139 Khoản 1 đã bị sửa từ 01/7/2026"
    # nhưng không nói được nội dung mới là gì. `113/2025/QH15` mang doc_id kiểu
    # UUID chứ không phải số: MOJ cấp UUID cho văn bản nhập sau (đo 2026-09-01,
    # `/doc/<uuid>` trả JSON cùng shape). Đừng "sửa" nó thành số.
    "6fa2fd20-597e-11f1-add2-7717d93a2118": ("deep", "113/2025/QH15"),  # Luật Dân số
    "187742": ("deep", "124/2025/QH15"),  # Luật Giáo dục nghề nghiệp
}

if __name__ == "__main__":
    s = get_settings()
    client = MojClient(base=s.moj_api_base, sleep=s.moj_rate_limit_sleep)
    client.fetch_many(list(DOC_IDS), Path(s.data_raw_dir) / "moj")
