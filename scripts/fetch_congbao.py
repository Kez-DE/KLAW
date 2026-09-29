"""Tải toàn văn `.docx` từ Công báo (`congbao.chinhphu.vn`) vào data/raw/congbao/*.docx.

Nguồn toàn văn DỰ PHÒNG (quyết định 2026-09-28 mục 13): chỉ cho văn bản mà gateway
Bộ Tư pháp chưa có — tìm không thấy id trên vbpl.vn lẫn gateway (K8, 2026-09-29).
Bản đăng Công báo là bản chính thức theo Luật Ban hành văn bản QPPL. `build_seed` nạp
nó qua đúng cổng `_soat_va_bam` của hai nguồn kia (`chinhphu_parser.docx_sang_html_prov`).

Metadata viết tay, đọc từ chính thể thức văn bản (cùng lệ `fetch_chinhphu.VAN_BAN`).
`tinh_trang` là `chua_xac_dinh`: CSDL quốc gia chưa có bản ghi nên KLAW chưa xác định
được tình trạng từ Bộ Tư pháp — văn bản ẩn theo quyết định mục 8 cho tới khi có.
`id` trong DB mang tiền tố `cb-` để không va vào dải id của gateway.

Chưa nạp: 66.18/2026/NQ-CP (Công báo 469585). Bảy Điều thân văn bản thì đọc được, nhưng
nội dung thực chất nằm ở 217 bảng phụ lục (thủ tục từng bộ, mẫu biểu có "Điều 1." riêng):
parser gộp cả khối sau "TM. CHÍNH PHỦ" thành MỘT `phu_luc` không trích dẫn được. Chờ bản
gateway (HTML có cấu trúc) thay vì nạp một văn bản mà phần cần trích lại không trích được.
"""

from pathlib import Path

from src.config import get_settings
from src.services.congbao_client import CongBaoClient

VAN_BAN: dict[str, dict] = {
    # Điều 47 khoản 2: Luật Công nghệ thông tin 67/2006/QH11 "hết hiệu kể từ ngày Luật này có
    # hiệu lực thi hành" (01/7/2026, khoản 1) — chữ "hiệu" thiếu "lực" là nguyên văn Công báo.
    "468708": {
        "url": "https://congbao.chinhphu.vn/van-ban/luat-so-148-2025-qh15-468708.htm",
        "so_ky_hieu": "148/2025/QH15",
        "ten": "Luật Chuyển đổi số",
        "loai_van_ban": "Luật",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": "2025-12-11",
        "ngay_hieu_luc": "2026-07-01",
        "ngay_het_hieu_luc": None,
        "tinh_trang": "chua_xac_dinh",
        "depth": "deep",
    },
}


def fetch_many(ids: list[str], dest: Path) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    client = CongBaoClient()
    out: dict[str, Path] = {}
    for cbid in ids:
        p = dest / f"{cbid}.docx"
        if not p.exists():
            p.write_bytes(client.tai_vbhn(VAN_BAN[cbid]["url"]))
            print(f"[ok] {cbid} → {p.name}")
        out[cbid] = p
    return out


if __name__ == "__main__":
    fetch_many(list(VAN_BAN), Path(get_settings().data_raw_dir) / "congbao")
