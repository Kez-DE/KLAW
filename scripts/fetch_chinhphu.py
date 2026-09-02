"""Tải toàn văn từ `vanban.chinhphu.vn` vào data/raw/chinhphu/*.html.

Nguồn THỨ HAI, chỉ dùng cho văn bản mà bản MOJ hỏng. Mỗi mục ở đây phải kèm lý
do đo được vì sao không lấy từ MOJ — nếu MOJ có bản sạch thì dùng MOJ, đường đó
đã phục vụ 48 văn bản và có metadata phong phú hơn (`references`,
`documentIssues`, `effStatus`) mà trang Chính phủ không cấp.

`robots.txt`: `User-agent: * / Allow: /` (kiểm 2026-09-02). Không auth, không
CAPTCHA, User-Agent trung thực. Nhịp 1,5 s tự đặt cho một máy chủ nhà nước
không có API — cùng mức lịch sự đã dùng ở `congbao_client.py`.
"""

import time
from pathlib import Path

import httpx

from src.config import get_settings

NHIP_TOI_THIEU = 1.5

# docid trên vanban.chinhphu.vn → metadata. `docid` là khoá của HỌ, không phải
# doc_id MOJ; `id` của document trong DB dùng tiền tố `cp-` để không bao giờ va
# vào dải id thuần số của MOJ.
#
# Metadata viết tay chứ không bới từ HTML: trang chi tiết bày chúng trong một
# bảng không có class ổn định, và với MỘT văn bản thì một bảng literal đã tra
# tay đáng tin hơn một scraper sẽ hỏng lặng lẽ. Mỗi trường dưới đây đọc từ
# chính thể thức văn bản (số hiệu, ngày ban hành, cơ quan ban hành ở đầu bản).
VAN_BAN: dict[str, dict] = {
    # Luật Khiếu nại — bản MOJ (doc_id 27325) BỊ TƯỜNG PHÍ: 86 chỗ trong toàn
    # văn bị thay bằng `<a class="clsBookmark clsopentLogin">`, câu cụt giữa
    # chừng, nên nằm trong `KHONG_NAP` của scripts/fetch_moj.py. Bản này đầy đủ
    # và còn đúng hơn ở Điều 31 Khoản 2 (MOJ có hai Điểm cùng nhãn `i)`; bản
    # này ghi `i)` rồi `k)`, đúng bảng chữ cái pháp lý VN).
    "162374": {
        "so_ky_hieu": "02/2011/QH13",
        "ten": "Luật Khiếu nại",
        "loai_van_ban": "Luật",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": "2011-11-11",
        "ngay_hieu_luc": "2012-07-01",
        "ngay_het_hieu_luc": None,
        "tinh_trang": "CHL",
        "depth": "deep",
    },
}


def url_chi_tiet(docid: str) -> str:
    return f"https://vanban.chinhphu.vn/default.aspx?pageid=27160&docid={docid}"


def fetch_many(docids: list[str], dest: Path) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    http = httpx.Client(timeout=120, follow_redirects=True,
                        headers={"User-Agent": "klaw-thesis/1.0"})
    out: dict[str, Path] = {}
    for did in docids:
        p = dest / f"{did}.html"
        if p.exists():
            out[did] = p
            continue
        time.sleep(NHIP_TOI_THIEU)
        r = http.get(url_chi_tiet(did))
        r.raise_for_status()
        p.write_text(r.text, encoding="utf-8")
        print(f"[ok] {did} → {p.name}")
        out[did] = p
    return out


if __name__ == "__main__":
    s = get_settings()
    fetch_many(list(VAN_BAN), Path(s.data_raw_dir) / "chinhphu")
