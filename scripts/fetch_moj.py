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
    # ── Đợt A — 10 văn bản CÒN HIỆU LỰC, lấp 7 lĩnh vực trống của bộ lọc ──
    # Chọn đợt A trước vì đây là phần TRẢ LỜI ĐƯỢC kèm trích dẫn và KHẲNG ĐỊNH
    # ĐƯỢC là hiện hành; văn bản HHL một phần (đợt B) chỉ làm dày nhánh
    # `mot_phan_khong_xac_dinh`. Xem `.superpowers/sdd/khao-sat-mo-rong-corpus.md`.
    "179252": ("deep", "91/2025/QH15"),    # Luật Bảo vệ dữ liệu cá nhân
    "187276": ("deep", "356/2025/NĐ-CP"),  # hướng dẫn BVDLCN
    "132957": ("deep", "24/2018/QH14"),    # Luật An ninh mạng
    "161263": ("deep", "19/2023/QH15"),    # Bảo vệ quyền lợi người tiêu dùng
    "133401": ("deep", "23/2018/QH14"),    # Luật Cạnh tranh
    "187043": ("deep", "108/2025/QH15"),   # Luật Quản lý thuế
    "187601": ("deep", "143/2025/QH15"),   # Luật Đầu tư
    "179095": ("deep", "76/2025/QH15"),    # sửa đổi Luật Doanh nghiệp
    "178737": ("deep", "88/2025/QH15"),    # sửa đổi Luật Xử lý VPHC
    # ── Đợt B — 13 văn bản HẾT HIỆU LỰC MỘT PHẦN ──
    # Nạp có chủ đích: chúng làm dày nhánh `mot_phan_khong_xac_dinh`, và đó là
    # phần trung thực nhất hệ thống nói được ở cấp điều khoản khi CSDL quốc gia
    # không công bố dữ liệu sửa đổi cấp điều khoản (0/272 reference, đã đo).
    "142881": ("deep", "59/2020/QH14"),    # Luật Doanh nghiệp (142847 đã chết)
    "128706": ("deep", "04/2017/QH14"),    # Hỗ trợ doanh nghiệp nhỏ và vừa
    "26117":  ("deep", "36/2005/QH11"),    # Luật Thương mại
    "177815": ("deep", "31/2024/QH15"),    # Luật Đất đai
    "170509": ("deep", "43/2024/QH15"),    # sửa đổi Luật Đất đai
    "187045": ("deep", "109/2025/QH15"),   # Thuế thu nhập cá nhân
    "179941": ("deep", "67/2025/QH15"),    # Thuế thu nhập doanh nghiệp
    "166581": ("deep", "22/2023/QH15"),    # Luật Đấu thầu
    "142882": ("deep", "64/2020/QH14"),    # Luật PPP (142841 đã chết)
    "165913": ("deep", "20/2023/QH15"),    # Giao dịch điện tử
    "179989": ("deep", "71/2025/QH15"),    # Công nghiệp công nghệ số
    "27621":  ("deep", "15/2012/QH13"),    # Xử lý vi phạm hành chính
    "96035":  ("deep", "93/2015/QH13"),    # Tố tụng hành chính

    # ── Đợt C 2026-09-01 — mở khoá mẫu soạn thảo ──
    # Thể thức văn bản hành chính (công văn, quyết định, biên bản…) nằm trọn ở
    # đây; không có nó thì sáu mẫu cuối không có căn cứ nào để soát. Qua cổng
    # cấu trúc sạch: 0 lỗi, 0 cảnh báo, 262 điều khoản.
    "141142": ("deep", "30/2020/NĐ-CP"),   # Công tác văn thư
    # ── Đợt C — 2 văn bản HẾT HIỆU LỰC TOÀN BỘ, nạp LÀM BẪY ──
    # Cùng vai trò với 4 nghị định lương tối thiểu ở trên: có ích VÌ đã chết.
    # `13/2023/NĐ-CP` đặc biệt đáng nạp — FE dẫn nó như luật hiện hành, song song
    # với chính cặp `91/2025/QH15` + `356/2025/NĐ-CP` đã thay thế nó.
    "161106": ("deep", "13/2023/NĐ-CP"),   # BVDLCN cũ — chết từ 01/01/2026
    "15066":  ("deep", "67/2006/QH11"),    # Luật Công nghệ thông tin
}

# ── KHÔNG NẠP, kèm lý do đo được (đừng thêm lại mà không đọc phần này) ──
# Mỗi dòng ở đây là một văn bản đã fetch được toàn văn nhưng KHÔNG qua được một
# bất biến của parser vì KHIẾM KHUYẾT CỦA NGUỒN. Ghi ra thay vì im lặng bỏ: lần
# sau ai đó mở rộng corpus sẽ gặp lại đúng những văn bản này.
KHONG_NAP: dict[str, tuple[str, str]] = {
    # MOJ ghi HAI điểm liên tiếp cùng nhãn "i)" trong Điều 31 Khoản 2 (bảng chữ
    # cái pháp lý VN đi a…h, i, k — điểm thứ hai lẽ ra là "k)"). Hai neo trích
    # dẫn trùng nhau ⇒ một claim sai được "kiểm chứng thành công" trên điểm kia,
    # đúng thứ `_kiem_bat_bien` tồn tại để chặn. Không tự đặt nhãn thay nguồn:
    # đó là bịa ký hiệu, và cách sửa (bỏ văn bản / thêm hậu tố vị trí / đối chiếu
    # Công báo rồi ghi bản sửa) là một CHÍNH SÁCH TRÍCH DẪN cần người quyết.
    "27325": ("02/2011/QH13", "Điều 31 Khoản 2 có hai Điểm cùng nhãn 'i)'"),
}

if __name__ == "__main__":
    s = get_settings()
    client = MojClient(base=s.moj_api_base, sleep=s.moj_rate_limit_sleep)
    client.fetch_many(list(DOC_IDS), Path(s.data_raw_dir) / "moj")
