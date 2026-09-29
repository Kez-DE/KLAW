"""Tải toàn văn 21 văn bản từ API MOJ vào data/raw/moj/*.json."""

import json
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

    # ── Task 1 (T1) — mở kho sang 8 lĩnh vực, `.superpowers/sdd/tro-ly-8-linh-vuc/` ──
    # 13 id đã VERIFY TAY qua metadata.parquet + API live (task-1-brief.md); 6
    # trong số đó (177815, 142881, 26117, 187045, 96035, 27621) đã có mặt ở
    # trên — 5 dòng dưới đây là THÊM MỚI (11/13; `169032` và `175027` bị chặn
    # ở cổng cấu trúc, xem `KHONG_NAP` bên dưới). `TIEU_DE_DOI_CHIEU` đối
    # chiếu tiêu đề response cho ĐỦ 11, kể cả 6 đã có: số hiệu trùng nhau giữa
    # các loại văn bản (`50/2005/QH11` trả một Nghị quyết, không phải Luật Sở
    # hữu trí tuệ) nên id đúng vẫn cần đối chiếu, không chỉ id mới thêm.
    "169027": ("deep", "29/2023/QH15"),    # Luật Kinh doanh bất động sản
    "36870":  ("deep", "52/2014/QH13"),    # Luật Hôn nhân và gia đình
    "142867": ("deep", "61/2020/QH14"),    # Luật Đầu tư
    "16748":  ("deep", "50/2005/QH11"),    # Luật Sở hữu trí tuệ
    "136036": ("deep", "38/2019/QH14"),    # Luật Quản lý thuế

    # ── K1 2026-09-28 — văn bản mà văn bản trong kho THAY THẾ/BÃI BỎ nhưng kho
    # thiếu (`docs/plans/active/kho-luat-trich-dan-day-du.md`). Đích của cạnh
    # MOJ loai 1/12 đi ra từ văn bản deep, lọc theo `linh_vuc_chuan` các văn bản
    # deep đang dùng. `so_ky_hieu` sinh từ `docNum` của gateway (không gõ tay),
    # và khớp 33/33 với `metadata.parquet` lẫn `raw_text` của cạnh trỏ tới nó.
    # Cột chú thích = `effStatus` MOJ ngày fetch — nhiều dòng CHL là SAI (vd
    # 44/2013 đã bị 145/2020 thay), đúng cái bẫy của 90/2019 ở trên.
    "154245": ("deep", "38/2022/NĐ-CP"),        # HHL — mắt xích 90/2019 → 38/2022 → 74/2024
    "33381":  ("deep", "03/2014/NĐ-CP"),        # HHL1P
    "48298":  ("deep", "05/2015/NĐ-CP"),        # HHL1P
    "43821":  ("deep", "10/2013/TT-BLĐTBXH"),   # CHL
    "43819":  ("deep", "11/2013/TT-BLĐTBXH"),   # CHL
    "131010": ("deep", "121/2018/NĐ-CP"),       # CHL
    "131643": ("deep", "148/2018/NĐ-CP"),       # CHL
    "132028": ("deep", "149/2018/NĐ-CP"),       # CHL
    "34095":  ("deep", "27/2014/NĐ-CP"),        # CHL
    "141147": ("deep", "28/2020/NĐ-CP"),        # CHL — nguồn viết "2:" ở Điều 56, gộp vào Khoản 1
    "43992":  ("deep", "40/2014/TT-NHNN"),      # CHL
    "30472":  ("deep", "41/2013/NĐ-CP"),        # CHL
    "32526":  ("deep", "44/2013/NĐ-CP"),        # CHL
    "30460":  ("deep", "45/2013/NĐ-CP"),        # HHL1P
    "30467":  ("deep", "46/2013/NĐ-CP"),        # HHL1P
    "30466":  ("deep", "49/2013/NĐ-CP"),        # HHL1P
    "94345":  ("deep", "54/2015/TT-BLĐTBXH"),   # CHL
    "30475":  ("deep", "55/2013/NĐ-CP"),        # HHL
    "36843":  ("deep", "73/2014/NĐ-CP"),        # CHL
    "84922":  ("deep", "85/2015/NĐ-CP"),        # CHL
    "37502":  ("deep", "01/2014/TT-BLĐTBXH"),   # CHL
    "179969": ("deep", "07/2025/UBTVQH15"),     # HHL
    "12807":  ("deep", "14/2008/QH12"),         # HHL1P
    "14832":  ("deep", "78/2006/QH11"),         # HHL1P
    # ── K8 2026-09-29 — mở rộng kho theo quyết định 2026-09-28 mục 14. Id gateway
    # (= id vbpl.vn) đọc từ trang chi tiết vbpl.vn, `docNum` đối chiếu lúc fetch.
    "787d3780-866f-11f1-8511-612429c9d15e": ("deep", "283/2026/NĐ-CP"),  # xử phạt lao động, thay 12/2022
    "178757": ("deep", "158/2025/NĐ-CP"),  # BHXH bắt buộc; đang shallow → nâng tại chỗ
    "178294": ("deep", "129/2025/NĐ-CP"),  # phân định thẩm quyền 2 cấp, Bộ Nội vụ
    # ── K6 2026-09-29 — BẮT ĐẦU khối sinh máy (k6)
    # Toàn văn cho MỌI văn bản được hiện (quyết định 2026-09-28 mục 9). Tập đích:
    # văn bản shallow/metadata trong `hien_thi.tap_hien_thi` tại 2026-09-28 (DB dùng
    # chung, 480 hiện) ∪ tập sau khôi phục K8 (484 hiện) = 438 văn bản; ở đây là
    # những văn bản qua cổng `_soat_va_bam` mà mọi điều khoản ngoài bảng là chuỗi
    # con nguyên văn của gateway. Phần còn lại ở `KHONG_NAP` (khối K6). Response
    # lấy từ lượt làm mới toàn kho 2026-09-28 (cache `lam_moi_hieu_luc`, cùng dạng
    # data/raw/moj/*.json); `so_ky_hieu` = `docNum`. Dòng đang có được NÂNG TẠI
    # CHỖ (`ingest._ghi_van_ban`), không DELETE.
    "133113": ("deep", "01/2018/UBNVQH14"),
    "172438": ("deep", "01/2018/UBTVQH14"),
    "142035": ("deep", "01/2020/TT-BNNPTNT"),
    "152678": ("deep", "01/2022/TT-BNNPTNT"),
    "166384": ("deep", "01/2024/TT-BNNPTNT"),
    "175635": ("deep", "01/2025/TT-BNNPTNT"),
    "122443": ("deep", "02/2017/TT-BNNPTNT"),
    "153151": ("deep", "02/2021/QH15"),
    "251c4420-5265-11f1-848d-2bb321e41052": ("deep", "02/2026/QH16"),
    "12900": ("deep", "03/2007/QH12"),
    "104377": ("deep", "03/2016/TT-BNNPTNT"),
    "27308": ("deep", "04/2011/QH13"),
    "141413": ("deep", "04/2020/TT-BNNPTNT"),
    "148221": ("deep", "04/2021/TT-BNNPTNT"),
    "159806": ("deep", "04/2023/NĐ-CP"),
    "178681": ("deep", "05/2025/TT-BNNMT"),
    "122170": ("deep", "06/2017/TT-BNNPTNT"),
    "130771": ("deep", "06/2018/TT-BNNPTN"),
    "155158": ("deep", "06/2022/TT-BNNPTNT"),
    "14681": ("deep", "07/2007/NQ-CP"),
    "67346": ("deep", "07/2015/TT-BLĐTBXH"),
    "106202": ("deep", "07/2016/TT-BNNPTNT"),
    "123514": ("deep", "07/2017/QH14"),
    "153251": ("deep", "07/2022/NĐ-CP"),
    "152655": ("deep", "07/2022/QĐ-UBND"),
    "174485": ("deep", "07/2025/NĐ-CP"),
    "187195": ("deep", "07/2025/NĐ-СР"),
    "5b03a780-5b30-11f1-be19-439d7a536e10": ("deep", "07/2026/TTLT-VKSNDTC-TANDTC"),
    "27706": ("deep", "08/2012/QH13"),
    "106212": ("deep", "08/2016/TT-BNNPTNT"),
    "142665": ("deep", "08/2020/TT-BNNPTNT"),
    "163515": ("deep", "08/2022/QH15"),
    "167031": ("deep", "08/2023/TT-BLĐTBXH"),
    "26112": ("deep", "09/2011/TT-BTC"),
    "153300": ("deep", "09/2021/TT-BNNPTNT"),
    "160606": ("deep", "09/2022/QH15"),
    "168449": ("deep", "09/2024/TT-BNNPTNT"),
    "6dbee1e0-6e19-11f1-91ec-bfa56133551d": ("deep", "09/2026/QH16"),
    "9924": ("deep", "09/CP"),
    "119077": ("deep", "10/2017/NĐ-CP"),
    "165573": ("deep", "10/2024/NĐ-CP"),
    "178653": ("deep", "10/2025/TT-BNNMT"),
    "187552": ("deep", "10/2026/TT-BGDĐT"),
    "112489": ("deep", "100/2016/NĐ-CP"),
    "140152": ("deep", "100/2019/NĐ-CP"),
    "187036": ("deep", "100/2025/QH15"),
    "187037": ("deep", "101/2025/QH15"),
    "185946": ("deep", "102/2025/QH15"),
    "8263": ("deep", "103/1997/NĐ-CP"),
    "83314": ("deep", "104/2008/QĐ-BTC"),
    "178104": ("deep", "104/2025/NĐ-CP"),
    "92155": ("deep", "105/2015/NĐ-CP"),
    "177733": ("deep", "105/2025/NĐ-CP"),
    "c759d970-6541-11f1-8445-f5d165b435cc": ("deep", "106/2026/QĐ-UBND"),
    "101897": ("deep", "107/2016/QH13"),
    "187040": ("deep", "107/2025/QH15"),
    "28073": ("deep", "11/2013/NĐ-CP"),
    "122827": ("deep", "11/2017/QH14"),
    "146676": ("deep", "11/2021/NĐ-CP"),
    "159014": ("deep", "11/2022/TT-BNNPTNT"),
    "176975": ("deep", "11/2025/NĐ-CP"),
    "23620": ("deep", "116/2009/QĐ-TTg"),
    "155947": ("deep", "116/2021/NĐ-CP"),
    "13851": ("deep", "117/2007/NĐ-CP"),
    "151943": ("deep", "118/2021/NĐ-CP"),
    "46289": ("deep", "119/2014/TT-BTC"),
    "186573": ("deep", "119/2025/QH15"),
    "44043": ("deep", "12/2014/TT-BNNPTTN"),
    "134060": ("deep", "12/2019/NĐ-CP"),
    "145000": ("deep", "12/2020/TT-BNNPTNT"),
    "170834": ("deep", "12/2024/TT-BNNPTNT"),
    "6eea5ec0-5b2f-11f1-b060-1f2b6a7ba34e": ("deep", "12/2025/TTLT-VKSNDTC-TANDTC-BCA-BQP"),
    "178265": ("deep", "120/2025/NĐ-CP"),
    "187033": ("deep", "120/2025/QH15"),
    "178222": ("deep", "121/2025/NĐ-CP"),
    "32496": ("deep", "123/2013/NĐ-CP"),
    "92897": ("deep", "123/2015/NĐ-CP"),
    "27263": ("deep", "124/2011/NĐ-CP"),
    "22940": ("deep", "125/2001/QĐ-TTg"),
    "c0473f60-65a5-11f1-a544-6ff39238f2e0": ("deep", "125/2026/QĐ-UBND"),
    "47412": ("deep", "126/2014/NĐ-CP"),
    "185899": ("deep", "126/2025/QH15"),
    "186570": ("deep", "128/2025/QH15"),
    "cf007110-59a3-11f1-8c15-2dbf1042f751": ("deep", "128/2026/NĐ-CP"),
    "114551": ("deep", "13/2016/TT-BNNPTNT"),
    "167755": ("deep", "13/2022/QH15"),
    "156126": ("deep", "13/2022/TT-BNNPTNT"),
    "179380": ("deep", "13/2025/TT-BGDĐT"),
    "187492": ("deep", "131/2025/QH15"),
    "f3610e80-791e-11f1-b9f5-f71e4de9d6f8": ("deep", "133/2025/QH15"),
    "119757": ("deep", "134/2016/NĐ-CP"),
    "185659": ("deep", "135/2025/QH15"),
    "187047": ("deep", "139/2025/QH15"),
    "148195": ("deep", "14/2021/NĐ-CP"),
    "152536": ("deep", "14/2021/QĐ-TTg"),
    "17168": ("deep", "141/2005/NĐ-CP"),
    "0b18ef50-7f2f-11f1-ac91-b52787e0a2e9": ("deep", "141/2026/NĐ-CP"),
    "128550": ("deep", "142/2017/NĐ-CP"),
    "187584": ("deep", "142/2025/QH15"),
    "114476": ("deep", "143/2016/NĐ-CP"),
    "118090": ("deep", "143/2016/TT-BTC"),
    "127300": ("deep", "144/2017/NĐ-CP"),
    "185664": ("deep", "144/2025/QH15"),
    "2f53d590-68a2-11f1-abca-2fa19d617f21": ("deep", "144/2026/NĐ-CP"),
    "183299": ("deep", "145/2025/QĐ-UBND"),
    "126410": ("deep", "146/2017/NĐ-CP"),
    "186271": ("deep", "147/2025/QH15"),
    "12811": ("deep", "15/2008/QH12"),
    "124612": ("deep", "15/2017/TT-BNNPTNT"),
    "134195": ("deep", "15/2019/NĐ-CP"),
    "153601": ("deep", "15/2022/QĐ-UBND"),
    "168125": ("deep", "15/2023/QH15"),
    "cf687d00-64ac-11f1-b68a-cdb6a707fd95": ("deep", "15/2026/NQ-HĐND"),
    "132170": ("deep", "150/2018/NĐ-CP"),
    "37430": ("deep", "151/2014/TT-BTC"),
    "174967": ("deep", "157/2024/NĐ-CP"),
    "187020": ("deep", "158/2025/TT-BTC"),
    "179149": ("deep", "159/2025/NĐ-CP"),
    "185195": ("deep", "159/2025/QĐ-CTUBND"),
    "104462": ("deep", "16/2014/TT-BNNPTNT"),
    "167565": ("deep", "16/2023/QH15"),
    "174139": ("deep", "161/2024/NĐ-CP"),
    "132374": ("deep", "162/2018/NĐ-CP"),
    "179140": ("deep", "164/2025/NĐ-CP"),
    "6155": ("deep", "17/1999/QH10"),
    "151590": ("deep", "17/2021/TT-BNNPTNT"),
    "186426": ("deep", "17/2026/NĐ-CP"),
    "174197": ("deep", "172/2024/NĐ-CP"),
    "184035": ("deep", "176/2025/NĐ-CP"),
    "19141": ("deep", "178/2004/NĐ-CP"),
    "26419": ("deep", "18/2011/TT- BNNPTNT"),
    "67884": ("deep", "18/2011/TT-BNNPTNT"),
    "42790": ("deep", "18/2012/TT-BNNPTNT"),
    "67747": ("deep", "18/2015/QĐ-TTg"),
    "132920": ("deep", "18/2018/TT-BLĐTBXH"),
    "133964": ("deep", "18/2018/TT-BNNPTNT"),
    "151157": ("deep", "18/2021/NĐ-CP"),
    "173177": ("deep", "18/2024/TT-BNNPTNT"),
    "178668": ("deep", "18/2025/TT-BNNMT"),
    "187582": ("deep", "18/2026/NĐ-CP"),
    "110923": ("deep", "184/2015/TT-BTC"),
    "179825": ("deep", "184/2025/NĐ-CP"),
    "26420": ("deep", "19/2011/TT- BNNPTNT"),
    "142716": ("deep", "19/2020/TT-BTC"),
    "17717": ("deep", "190/2005/QĐ-TTg"),
    "179389": ("deep", "190/2025/NĐ-CP"),
    "27755": ("deep", "196/2011/TT-BTC"),
    "37750": ("deep", "196/2013/NĐ-CP"),
    "28019": ("deep", "20/2012/QH13"),
    "114572": ("deep", "20/2016/TT-BNNPTNT"),
    "133920": ("deep", "20/2018/TT-BNNPTNT"),
    "147348": ("deep", "20/2020/TT-BLĐTBXH"),
    "152303": ("deep", "20/2021/TT-BNNPTNT"),
    "154794": ("deep", "20/2022/NĐ-CP"),
    "6fb7dd80-59a6-11f1-a013-532655e6581a": ("deep", "20/2026/TT-BTC"),
    "09a8e5d0-688c-11f1-af8e-adfd6ae9c135": ("deep", "200/2026/NĐ-CP"),
    "12354": ("deep", "21/2008/QH12"),
    "28026": ("deep", "21/2012/QH13"),
    "67763": ("deep", "21/2015/TT-BNNPTNT"),
    "131014": ("deep", "21/2017/QH14"),
    "147004": ("deep", "21/2021/NĐ-CP"),
    "173180": ("deep", "21/2024/TT-BNNPTNT"),
    "6728": ("deep", "210/1999/QĐ-TTg"),
    "180281": ("deep", "218/2025/NĐ-CP"),
    "180273": ("deep", "219/2025/NĐ-CP"),
    "25201": ("deep", "22/2010/QĐ-TTg"),
    "139201": ("deep", "22/2019/TT-BNNPTNT"),
    "186413": ("deep", "22/2025/TT-BNNMT"),
    "7da35fe0-7f31-11f1-8df0-5f93228b4774": ("deep", "220/2026/NĐ-CP"),
    "122584": ("deep", "23/2017/QĐ-TTG"),
    "141055": ("deep", "23/2020/NĐ-CP"),
    "186456": ("deep", "23/2026/NĐ-CP"),
    "386e5ad0-7d09-11f1-9c00-f9e84f25c1dc": ("deep", "231/2026/NĐ-CP"),
    "12384": ("deep", "236/QĐ-TTg"),
    "30386": ("deep", "24/2013/NĐ-CP"),
    "140209": ("deep", "24/2019/TT-BNNPTNT"),
    "153604": ("deep", "24/2022/NĐ-CP"),
    "158969": ("deep", "24/2022/TT-BNNPTNT"),
    "15038": ("deep", "246/2006/QĐ-TTg"),
    "87786": ("deep", "249/QĐ-BNN-BVTV"),
    "12326": ("deep", "25/2008/QH12"),
    "24253": ("deep", "25/2008/QĐ-BGDĐT"),
    "128846": ("deep", "25/2018/TT-BTC"),
    "187818": ("deep", "253/2025/NĐ-CP"),
    "61650": ("deep", "254/2014/QĐ-UBND"),
    "33768": ("deep", "26/2012/TT-BLĐTBXH"),
    "133922": ("deep", "26/2018/TT-BNNPTNT"),
    "539a1450-7a13-11f1-bfab-2d6d51f414a0": ("deep", "26/2026/NQ-CP"),
    "182774": ("deep", "261/2025/NĐ-CP"),
    "f8fc0770-8033-11f1-9ecb-65d57157638f": ("deep", "273/2026/NĐ-CP"),
    "31206": ("deep", "2746/2006/QĐ-BTC"),
    "11761": ("deep", "28/2009/QH12"),
    "130821": ("deep", "28/2018/QH14"),
    "185254": ("deep", "282/2025/NĐ-CP"),
    "44858": ("deep", "29/2014/TT-BNNPTTN"),
    "100456": ("deep", "30/2015/QĐ-UBND"),
    "128844": ("deep", "30/2018/TT-BTC"),
    "168904": ("deep", "30/2023/QH15"),
    "179713": ("deep", "30/2025/TT-BNNMT"),
    "178371": ("deep", "30/2025/TT-BTC"),
    "118657": ("deep", "302/2016/TT-BTC"),
    "11913": ("deep", "31/2009/TTLT-BNNPTNT-BNV"),
    "73839": ("deep", "31/2015/QĐ-TTg"),
    "164914": ("deep", "31/2023/NĐ-CP"),
    "30615": ("deep", "32/2013/QH13"),
    "aaff53a0-767f-11f1-a26c-15d47590a02f": ("deep", "32/2026/NĐ-CP"),
    "186493": ("deep", "320/2025/NĐ-CP"),
    "135710": ("deep", "33/2019/TT-BTC"),
    "152258": ("deep", "33/2021/QĐ-UBND"),
    "122449": ("deep", "34/2017/TT-BTC"),
    "137459": ("deep", "34/2018/QH14"),
    "134291": ("deep", "34/2018/TT-BNNPTNT"),
    "166653": ("deep", "34/2024/NĐ-CP"),
    "170570": ("deep", "34/2024/QH15"),
    "177613": ("deep", "34/2025/QĐ-UBND"),
    "187092": ("deep", "34/2026/NĐ-CP"),
    "92225": ("deep", "35/2015/TT-BNNPTNT"),
    "135360": ("deep", "35/2019/NĐ-CP"),
    "158798": ("deep", "35/2022/NĐ-CP"),
    "172475": ("deep", "35/2024/QH15"),
    "11716": ("deep", "36/2009/QH12"),
    "134035": ("deep", "36/2018/TT-BNNPTNT"),
    "186980": ("deep", "360/2025/NĐ-CP"),
    "26557": ("deep", "37/2011/TTLT-BNNPTNT-BNV"),
    "122446": ("deep", "37/2017/TT-BTC"),
    "26444": ("deep", "38/2011/NĐ-CP"),
    "172437": ("deep", "38/2024/QH15"),
    "25162": ("deep", "39/2010/NĐ-CP"),
    "45756": ("deep", "39/2014/TT-BTC"),
    "136039": ("deep", "40/2019/QH14"),
    "23856": ("deep", "42/2009/QH12"),
    "41587": ("deep", "42/2010/TT-BLĐTBXH"),
    "136041": ("deep", "42/2019/QH14"),
    "25478": ("deep", "43/2010/TT–BNNPTNT"),
    "186739": ("deep", "43/2026/NĐ-CP"),
    "117760": ("deep", "44/2016/NĐ-CP"),
    "175084": ("deep", "44/2024/QH15"),
    "9137": ("deep", "45-CP"),
    "32425": ("deep", "45/2013/TT-BTC"),
    "151161": ("deep", "45/2021/NĐ-CP"),
    "36793": ("deep", "46/2014/QH13"),
    "154637": ("deep", "46/2022/NĐ-CP"),
    "172799": ("deep", "46/2024/QH15"),
    "26637": ("deep", "47/2011/NĐ-CP"),
    "27840": ("deep", "48/2012/TT-BNNPTNT"),
    "187432": ("deep", "48/2026/NĐ-CP"),
    "25701": ("deep", "49/2010/QH12"),
    "173624": ("deep", "49/2024/QH15"),
    "25702": ("deep", "51/2010/QH12"),
    "144399": ("deep", "51/2017/QH14"),
    "172923": ("deep", "51/2024/QH15"),
    "25699": ("deep", "52/2010/QH12"),
    "36141": ("deep", "52/2014/NĐ-CP"),
    "27642": ("deep", "53/2012/NĐ-CP"),
    "34055": ("deep", "53/2013/QĐ-TTg"),
    "46848": ("deep", "53/2013/TT- BNNPTNT"),
    "173982": ("deep", "53/2024/QH15"),
    "36878": ("deep", "54/2014/QH13"),
    "186852": ("deep", "54/2026/NĐ-CP"),
    "163098": ("deep", "56/2023/NĐ-CP"),
    "17065": ("deep", "57/2005/QH11"),
    "26354": ("deep", "57/2010/QH12"),
    "123126": ("deep", "57/2017/NĐ-CP"),
    "6ad0bc90-62ea-11f1-8d8f-7326969477ba": ("deep", "57/2026/NĐ-CP"),
    "142815": ("deep", "58/2020/NĐ-CP"),
    "22442": ("deep", "59/2002/NĐ-CP"),
    "36572": ("deep", "59/2014/NĐ-CP"),
    "187063": ("deep", "59/2026/NĐ-CP"),
    "142846": ("deep", "60/2020/QH14"),
    "174877": ("deep", "60/2024/QH15"),
    "26357": ("deep", "61/2010/QH12"),
    "46747": ("deep", "61/2014/QH13"),
    "108574": ("deep", "615 TC/TCT/QÐ"),
    "24312": ("deep", "62/2008/TT-BNN"),
    "15076": ("deep", "65/2006/QH11"),
    "25402": ("deep", "65/2010/NĐ-CP"),
    "143616": ("deep", "65/2020/TT-BTC"),
    "187585": ("deep", "65/2026/NĐ-CP"),
    "180017": ("deep", "66/2025/QH15"),
    "146541": ("deep", "67/2020/QH14"),
    "146648": ("deep", "68/2020/QH14"),
    "176454": ("deep", "68/2025/NĐ-CP"),
    "109880": ("deep", "682/QĐ-BTC"),
    "19451": ("deep", "70/2003/QĐ-BNN"),
    "157020": ("deep", "70/2022/NĐ-CP"),
    "162330": ("deep", "70/2023/NĐ-CP"),
    "179100": ("deep", "71/2025/TT-BTC"),
    "146609": ("deep", "72/2020/QH14"),
    "88392": ("deep", "734/QĐ-BNN-BVTV"),
    "184262": ("deep", "74/2025/QĐ-UBND"),
    "d9335530-51b0-11f1-b90b-43de5e4394dd": ("deep", "74/2026/QĐ-UBND"),
    "179167": ("deep", "75/2025/QH15"),
    "173641": ("deep", "76/2024/NĐ-CP"),
    "11738": ("deep", "77/2008/NĐ-CP"),
    "37769": ("deep", "77/2014/TT-BTC"),
    "125397": ("deep", "77/2017/TT-BTC"),
    "186436": ("deep", "77/2025/TT-BNNMT"),
    "179893": ("deep", "78/2025/QH15"),
    "14831": ("deep", "79/2006/QH11"),
    "23603": ("deep", "79/2009/NĐ-CP"),
    "36921": ("deep", "80/2014/NĐ-CP"),
    "159007": ("deep", "80/2022/NĐ-CP"),
    "187505": ("deep", "80/2026/NĐ-CP"),
    "27792": ("deep", "81/2012/NĐ-CP"),
    "135988": ("deep", "81/2018/TT-BTC"),
    "179416": ("deep", "81/2025/QH15"),
    "186332": ("deep", "81/2025/TT-BNNMT"),
    "146141": ("deep", "82/2020/TT-BTC"),
    "112967": ("deep", "83/2016/TT-BTC"),
    "179420": ("deep", "85/2025/QH15"),
    "186303": ("deep", "88/2025/TT-BNNMT"),
    "179427": ("deep", "89/2025/QH15"),
    "96020": ("deep", "90/2015/QH13"),
    "125398": ("deep", "93/2017/TT-BTC"),
    "92437": ("deep", "94/2015/NĐ-CP"),
    "860f7bf0-5fbf-11f1-baad-7baf349e4825": ("deep", "95/2026/NĐ-CP"),
    "169708": ("deep", "96/2024/NĐ-CP"),
    "96119": ("deep", "97/2015/QH13"),
    "151384": ("deep", "97/2021/NĐ-CP"),
    "169619": ("deep", "97/2022/NĐ-CP"),
    "177779": ("deep", "97/2025/NĐ-CP"),
    "140187": ("deep", "98/2019/NĐ-CP"),
    "112157": ("deep", "99/2016/NĐ-CP"),
    "159372": ("deep", "99/2022/NĐ-CP"),
    # ── K6 — HẾT khối sinh máy
}

# Mảnh tiêu đề đối chiếu TRƯỚC KHI GHI file raw — 11/13 id của T1 (169032,
# 175027 bị loại, xem KHONG_NAP), đã verify tay. Lệch → `_doi_chieu_tieu_de`
# ném `ValueError` nêu rõ id, tiêu đề nhận được, mảnh mong đợi. Không cảnh báo
# êm: nạp sai văn bản dưới đúng cái tên là lớp sai không phục hồi được (xem ví
# dụ `16748`/`50/2005/QH11` ở trên).
TIEU_DE_DOI_CHIEU: dict[str, str] = {
    "177815": "Đất đai",
    "169027": "Kinh doanh bất động sản",
    "36870": "Hôn nhân và gia đình",
    "142881": "doanh nghiệp",
    "142867": "đầu tư",
    "26117": "Thương mại",
    "16748": "Sở hữu trí tuệ",
    "136036": "Quản lý thuế",
    "187045": "Thuế thu nhập cá nhân",
    "96035": "Tố tụng hành chính",
    "27621": "Xử lý vi phạm hành chính",
}


def _doi_chieu_tieu_de(doc_id: str, tieu_de: str | None) -> None:
    """`tieu_de` (response MOJ) phải CHỨA mảnh mong đợi trong `TIEU_DE_DOI_CHIEU`.

    `doc_id` không có trong bảng → không kiểm, không phải lỗi. Lệch → ném NGAY,
    trước khi bất kỳ byte nào ghi ra `data/raw/moj/`.
    """
    manh = TIEU_DE_DOI_CHIEU.get(doc_id)
    if manh is not None and manh not in (tieu_de or ""):
        raise ValueError(
            f"doc {doc_id}: tiêu đề nhận được {tieu_de!r} không chứa mảnh mong đợi {manh!r}")

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
    # T1 (8 lĩnh vực) — KHÁC ba dòng trên: đây là GIỚI HẠN CỦA PARSER, không
    # phải khiếm khuyết nguồn. HTML hợp lệ: "Chương III" đứng riêng một
    # `<p class="prov-chapter">`, rồi tiêu đề Chương xuống dòng thành HAI thẻ
    # `<p class="prov-chapter">` KHÁC — "CHIẾN LƯỢC PHÁT TRIỂN NHÀ Ở QUỐC GIA,"
    # rồi "CHƯƠNG TRÌNH, KẾ HOẠCH PHÁT TRIỂN NHÀ Ở CẤP TỈNH" — cả ba cùng một
    # `id` HTML. `_la_tiep_noi_tieu_de` nhận diện mảnh tiêu đề tiếp nối bằng
    # `not text.lower().startswith("chương")`; dòng tiêu đề thứ hai TỰ NÓ mở
    # đầu bằng "CHƯƠNG TRÌNH" (nghĩa "program", không phải nhãn "Chương") nên
    # bị đọc nhầm thành một Chương MỚI không số hiệu — cổng `parse_anomalies`
    # đúng khi chặn. Sửa là việc của người sở hữu `src/services/prov_parser.py`
    # (ngoài phạm vi T1: chỉ được đụng migration/model/scripts đã liệt kê),
    # không vá tại đây. Loại khỏi DOC_IDS — domain "Nhà ở" tạm 0 văn bản.
    "169032": ("27/2023/QH15", "tiêu đề Chương III xuống dòng thành node "
               "'CHƯƠNG TRÌNH, KẾ HOẠCH...' không số hiệu — parser đọc nhầm nhãn"),
    # T1 (8 lĩnh vực) — CÙNG loại với `27325`: khiếm khuyết NGUỒN thật, không
    # phải parser. HTML MOJ viết "<strong>Điêu 38. Chậm đóng…</strong>" — thiếu
    # dấu, đúng ra là "Điều 38" (Đ-i-ề-u, không phải Đ-i-ê-u). Nhãn "Điêu" (viết
    # sai chính tả) không khớp regex nhãn "Điều" của cấp `dieu`, nên node rơi
    # xuống thành trẻ mồ côi không số hiệu — `parse_anomalies` đúng khi chặn.
    # KHÔNG tự sửa chính tả nguồn tại đây: đó là bịa chữ thay Công báo, đúng
    # điều đoạn trên đã từ chối làm cho `27325` — cần người đối chiếu Công báo
    # rồi quyết cách ghi. Loại khỏi DOC_IDS — domain "Bảo hiểm xã hội" tạm 0
    # văn bản.
    "175027": ("41/2024/QH15", "Điều 38 viết sai chính tả 'Điêu 38' trong HTML "
               "nguồn MOJ — nhãn không khớp regex cấp dieu"),
    # K1 2026-09-28 — đích thay thế/bãi bỏ trong lĩnh vực của kho, chặn ở cổng
    # `_soat_va_bam`. Bảy dòng đầu là GIỚI HẠN CỦA NGUỒN + PARSER: HTML MOJ của
    # văn bản cũ là văn xuôi phẳng, không có thẻ `prov-*` nào, nên không dựng
    # được cây. `chinhphu_parser.sang_html_prov` suy cấp từ nhãn cho đúng ca này
    # nhưng chưa ai soát nó trên HTML MOJ — không nối vào đây khi chưa soát.
    "95650":  ("134/2015/NĐ-CP", "HTML MOJ không có thẻ prov-* nào"),
    "103067": ("33/2016/NĐ-CP", "HTML MOJ không có thẻ prov-* nào"),
    "46744":  ("58/2014/QH13", "HTML MOJ không có thẻ prov-* nào"),
    "46742":  ("65/2014/QH13", "HTML MOJ không có thẻ prov-* nào"),
    "46749":  ("66/2014/QH13", "HTML MOJ không có thẻ prov-* nào"),
    "126171": ("06/2017/QH14", "HTML MOJ không có thẻ prov-* nào"),
    "40742":  ("71/2014/QH13", "HTML MOJ không có thẻ prov-* nào"),
    # Cùng loại `27325`: khiếm khuyết nguồn thật.
    "20981":  ("06/2003/PL-UBTVQH11", "hai node cùng neo 'Điều 22' ở cấp trích dẫn được"),
    "101890": ("106/2016/QH13", "documentContent.content 83 byte, 0 ký tự chữ"),
    # Không fetch được: gateway trả 400 `invalid.document.entity.not.found` cả
    # 10 lần (hai đợt, backoff tới 24 s) dù 71/2025/QH15 còn trỏ tới id này.
    "168687": ("136/2024/QH15", "gateway 400 invalid.document.entity.not.found"),
    # K6 2026-09-29 — BẮT ĐẦU khối sinh máy (k6)
    # Văn bản ĐANG ĐƯỢC HIỆN mà toàn văn gateway (cache 2026-09-28) không nạp sâu
    # được: cổng `_soat_va_bam` chặn (lý do = thông báo của cổng, rút gọn), hoặc
    # qua cổng nhưng parser dời chữ giữa các neo, hoặc trùng số hiệu. Chúng vẫn
    # shallow — KHÔNG có toàn văn (mục 9 chưa đạt cho chúng).
    "18398": (
        "01/2005/NQ-CP",
        "16 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd chuong 'I. TIẾP TỤC CẢI THIỆN MÔI TRƯỜNG KINH DOANH VÀ ĐẨY'",
    ),
    "25722": (
        "01/NQ-CP",
        "8 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd phan 'A. TẬP TRUNG THÁO GỠ KHÓ KHĂN, VƯỚNG MẮC, THÚC ĐẨY'",
    ),
    "863c7480-7e6d-11f1-87e2-45fe3e3918d3": (
        "02/2026/TT-BNNMT",
        "hai node cùng neo '02/2026/TT-BNNMT > Điều 16 > Điểm a' ở cấp trích dẫn được",
    ),
    "186296": ("03/2026/NĐ-CP", "hai node cùng neo '03/2026/NĐ-CP > Điều 8 > Khoản 2 > Điểm d' ở cấp trích dẫn được"),
    "163761": ("03/VBHN-VPQH", "HTML MOJ không có thẻ prov-* nào"),
    "5ae3af70-54b9-11f1-b102-07539b2807f6": (
        "04/2026/QH16",
        "hai node cùng neo '04/2026/QH16 > Điều 1 > Khoản 2' ở cấp trích dẫn được",
    ),
    "24848": (
        "05/2010/NĐ-CP",
        "khối chữ ký cuối HTML gắn thẻ prov-* nên không tách được bản ghi phu_luc — chữ đuôi nằm trong neo trích dẫn",
    ),
    "9f320090-54c9-11f1-aa08-59e3f5ee2be8": (
        "05/2026/QH16",
        "hai node cùng neo '05/2026/QH16 > Điều 1 > Khoản 3' ở cấp trích dẫn được",
    ),
    "24819": ("06/2010/TT-BTC", "hai node cùng neo '06/2010/TT-BTC > Điều 1 > Năm 2009' ở cấp trích dẫn được"),
    "157722": ("07/2022/QH15", "HTML MOJ không có thẻ prov-* nào"),
    "126723": ("08/2017/QH14", "HTML MOJ không có thẻ prov-* nào"),
    "168754": (
        "08/2022/NĐ-CP",
        "'08/2022/NĐ-CP > Điều 8 > Khoản 3' nuốt nguyên văn Khoản 4 — Khoản 4 không có neo riêng",
    ),
    "176976": ("10/2025/NĐ-CP", "parser không bảo toàn chữ: HTML 123422 ký tự, provisions 123582"),
    "169712": (
        "100/2024/NĐ-CP",
        "dòng công thức gắn thẻ prov-item ('n: là số năm…') tách chữ 'Trong đó: Gt…' khỏi Điều 31 Khoản 1/2 Điểm b — neo không là chuỗi con nguyên văn",
    ),
    "21876": (
        "102/2002/TT-BTC",
        "1 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd muc '1) Cơ sở thương mại, xuất khẩu mua hàng hoá là nôn'",
    ),
    "113073": ("102/2016/NĐ-CP", "hai node cùng neo '102/2016/NĐ-CP > Điều 5 > Khoản 2 > Điểm đ' ở cấp trích dẫn được"),
    "172729": (
        "103/2024/NĐ-CP",
        "33 điểm kết thúc bằng ':' mà không có con (công thức/bảng trong HTML nguồn không vào neo) — neo hứa danh sách mà không giao",
    ),
    "00aed7c0-5d63-11f1-8f07-fd66ec1fa693": (
        "103/2026/NĐ-CP",
        "hai node cùng neo '103/2026/NĐ-CP > Điều 22 > Khoản 1' ở cấp trích dẫn được",
    ),
    "0da53250-5d6b-11f1-807d-c70e99d85013": (
        "104/2026/NĐ-CP",
        "hai node cùng neo '104/2026/NĐ-CP > Điều 1 > Khoản 1 > Điểm d' ở cấp trích dẫn được",
    ),
    "187758": ("105/2025/QH15", "documentContent.content rỗng"),
    "0ae72df0-4247-11f1-9aef-8b444472143a": (
        "109/2026/NĐ-CP",
        "hai node cùng neo '109/2026/NĐ-CP > Điều 74 > Khoản 2 > Điểm a' ở cấp trích dẫn được",
    ),
    "109937": (
        "110/2002/QÐ-BTC",
        "Điều 1 có một Khoản không số hiệu (nhãn '2-') nuốt chữ các khoản sau — neo không là chuỗi con nguyên văn",
    ),
    "186600": (
        "111/2025/QH15",
        "1 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd dieu '15. Tham gia quản lý, thanh lý tài sản của tổ chức'",
    ),
    "178105": ("112/2025/NĐ-CP", "hai node cùng neo '112/2025/NĐ-CP > Điều 1 > Khoản 3' ở cấp trích dẫn được"),
    "23253": ("114/2001/QĐ-TTg", "hai node cùng neo '114/2001/QĐ-TTg > Điều 1 > Khoản 2' ở cấp trích dẫn được"),
    "ebde45c0-5e60-11f1-8fbf-fba9197f5741": (
        "114/2025/QH15",
        "hai node cùng neo '114/2025/QH15 > Điều 32 > Khoản 1' ở cấp trích dẫn được",
    ),
    "110222": ("115/1998/TT-BTC", "HTML MOJ không có thẻ prov-* nào"),
    "7576": ("115/1998/TT-BTC", "HTML MOJ không có thẻ prov-* nào"),
    "170131": ("117/2024/NĐ-CP", "hai node cùng neo '117/2024/NĐ-CP > Điều 1 > Khoản 5' ở cấp trích dẫn được"),
    "20092": ("12/2004/CT-TTg", "HTML MOJ không có thẻ prov-* nào"),
    "122826": ("12/2017/QH14", "HTML MOJ không có thẻ prov-* nào"),
    "161042": ("12/2022/QH15", "hai node cùng neo '12/2022/QH15 > Điều 53 > Khoản 1 > Điểm a' ở cấp trích dẫn được"),
    "178655": ("12/2025/TT-BNNMT", "parser không bảo toàn chữ: HTML 108462 ký tự, provisions 109166"),
    "151904": (
        "120/2021/NĐ-CP",
        "hai node cùng neo '120/2021/NĐ-CP > Điều 50 > Khoản 1 > Điểm d' ở cấp trích dẫn được",
    ),
    "153339": (
        "123/2021/NĐ-CP",
        "nhãn điểm 'р)' viết bằng chữ Kirin trong HTML nguồn: Điều 2 Khoản 17 Điểm o nhận chữ của điểm p, sai thứ tự nguyên văn",
    ),
    "187035": (
        "127/2025/QH15",
        "1 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd muc 'THI HÀNH ÁN TREO'",
    ),
    "15784": ("128/2004/TT-BTC", "HTML MOJ không có thẻ prov-* nào"),
    "20093": ("13/2004/CT-TTg", "HTML MOJ không có thẻ prov-* nào"),
    "185641": (
        "130/2025/QH15",
        "Điều 15 Khoản 1 mở đầu bằng ký tự ẩn U+200B trong HTML nguồn — neo không mở bằng nhãn của nó",
    ),
    "0ed5a0f0-5434-11f1-9423-23103f50c7ff": (
        "131/2026/NĐ-CP",
        "khối trách nhiệm thi hành/chữ ký cuối HTML gắn thẻ prov-* nên không tách được bản ghi phu_luc — chữ đuôi nằm trong neo trích dẫn",
    ),
    "187809": ("136/2025/QH15", "hai node cùng neo '136/2025/QH15 > Điều 2 > Khoản 5' ở cấp trích dẫn được"),
    "131573": (
        "137/2018/NĐ-CP",
        "thẻ prov-* phủ tới hết HTML nên không tách được bản ghi phu_luc — chữ đuôi nằm trong neo trích dẫn",
    ),
    "186425": ("14/2026/NĐ-CP", "hai node cùng neo '14/2026/NĐ-CP > Điều 130 > Khoản 2' ở cấp trích dẫn được"),
    "106333": (
        "14/CT-UBND",
        "1 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd muc '1. Giám đốc các Sở; Thủ trưởng các ban, ngành; Chủ'",
    ),
    "187763": ("141/2025/QH15", "documentContent.content rỗng"),
    "154327": (
        "148/2021/NĐ-CP",
        "hai node cùng neo '148/2021/NĐ-CP > Điều 14 > Khoản 1 > Điểm d' ở cấp trích dẫn được",
    ),
    "118966": ("150/2016/TT-BTC", "hai node cùng neo '150/2016/TT-BTC > Điều 4' ở cấp trích dẫn được"),
    "178259": (
        "151/2025/NĐ-CP",
        "hai node cùng neo '151/2025/NĐ-CP > Điều 19 > Khoản 1 > Điểm d' ở cấp trích dẫn được",
    ),
    "27617": ("16/2012/QH13", "hai node cùng neo '16/2012/QH13 > Điều 12 > Khoản 1 > Điểm a' ở cấp trích dẫn được"),
    "132279": ("16/2018/TT-BNNPTNT", "hai node cùng neo '16/2018/TT-BNNPTNT > Điều 1 > Khoản 19' ở cấp trích dẫn được"),
    "173895": ("165/2024/NĐ-CP", "Chương III không có điều nào — cây provision vỡ"),
    "173920": (
        "168/2024/NĐ-CP",
        "hai node cùng neo '168/2024/NĐ-CP > Điều 16 > Khoản 2 > Điểm đ' ở cấp trích dẫn được",
    ),
    "179096": (
        "168/2025/NĐ-CP",
        "hai node cùng neo '168/2025/NĐ-CP > Điều 92 > Khoản 4 > Điểm d' ở cấp trích dẫn được",
    ),
    "19633": ("17/2004/CT-TTg", "HTML MOJ không có thẻ prov-* nào"),
    "179215": (
        "178/2025/NĐ-CP",
        "1 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd dieu 'Điểm 15. Trình thẩm định, thẩm định quy hoạch đô t'",
    ),
    "126307": ("18/2017/QH14", "hai node cùng neo '18/2017/QH14 > Điều 32 > Khoản 1' ở cấp trích dẫn được"),
    "187372": ("180/2025/NĐ-CP", "dòng công thức 'n: …' gắn thẻ prov-item thành Điều 29 Khoản 5 Điểm không số hiệu"),
    "5a100a90-6f7a-11f1-b30f-9993cb99e536": (
        "182/2025/NĐ-CP",
        "hai node cùng neo '182/2025/NĐ-CP > Điều 1 > Khoản 1' ở cấp trích dẫn được",
    ),
    "14431": (
        "20/2004/TTLT/BLĐTBXH-BKH",
        "25 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd phan 'I. PHẠM VI ÁP DỤNG'",
    ),
    "148955": ("20/2021/NĐ-CP", "hai node cùng neo '20/2021/NĐ-CP > Điều 11 > Khoản 3 > Điểm b' ở cấp trích dẫn được"),
    "14129": (
        "22/2007/TTLT/BNN-BNV",
        "16 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd phan 'I. NHIỆM VỤ, QUYỀN HẠN VÀ CƠ CẤU TỔ CHỨC CỦA CHI C'",
    ),
    "133904": (
        "22/2018/TT-BNNPTNT",
        "hai node cùng neo '22/2018/TT-BNNPTNT > Điều 16 > Khoản 2 > Điểm c' ở cấp trích dẫn được",
    ),
    "166741": ("22/2023/NĐ-CP (1)", "HTML MOJ không có thẻ prov-* nào"),
    "181906": ("226/2025/NĐ-CP", "1 neo kết thúc bằng ':' mà không có con — neo hứa danh sách mà không giao"),
    "69532": ("23/2015/TT-BLĐTBXH", "1 neo kết thúc bằng ':' mà không có con — neo hứa danh sách mà không giao"),
    "f4b0c320-79e6-11f1-8c8a-3587e086d762": (
        "238/2026/NĐ-CP",
        "hai node cùng neo '238/2026/NĐ-CP > Điều 8 > Khoản 3 > Điểm a' ở cấp trích dẫn được",
    ),
    "133543": (
        "25/2018/TT-BNNPTNT",
        "1 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd chuong 'TỔ CHỨC THỰC HIỆN'",
    ),
    "153552": ("25/2022/NĐ-CP", "hai node cùng neo '25/2022/NĐ-CP > Điều 2 > Khoản 1 > Điểm d' ở cấp trích dẫn được"),
    "56844f80-7e93-11f1-92c2-fd52353fce98": ("253/2026/NĐ-CP", "cấp khoan nằm trong <table>, sẽ ra khỏi cây provision"),
    "67438": ("26/2015/TT-BTC", "hai node cùng neo '26/2015/TT-BTC > Điều 2 > Khoản 1' ở cấp trích dẫn được"),
    "114576": ("26/2016/TT-BNNPTNT", "hai node cùng neo '26/2016/TT-BNNPTNT > Điều 9 > Khoản 2' ở cấp trích dẫn được"),
    "18152": (
        "28/2005/TT-BNN",
        "2 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd muc 'I. SỬA ĐỔI, BỒ SUNG NỘI DUNG CỦA GẠCH ĐẦU DÒNG THỨ'",
    ),
    "167282": ("28/2023/QH15", "hai node cùng neo '28/2023/QH15 > Điều 31 > Khoản 1' ở cấp trích dẫn được"),
    "3999d900-48f4-11f1-9108-d1dfc9bf4e51": ("28/2026/QĐ-UBND", "HTML MOJ không có thẻ prov-* nào"),
    "185124": ("280/2025/NĐ-CP", "parser không bảo toàn chữ: HTML 60133 ký tự, provisions 60765"),
    "32522": (
        "29/2013/QH13",
        "Điều 56 có Khoản không số hiệu: nhãn '1.' đứng sau dấu gạch mềm U+00AD trong HTML nguồn",
    ),
    "187822": ("291/2025/NĐ-CP", "cấp diem nằm trong <table>, sẽ ra khỏi cây provision"),
    "135971": ("34/2018/TT-BLĐTBXH", "hai node cùng neo '34/2018/TT-BLĐTBXH > Điều 2 > Khoản 6' ở cấp trích dẫn được"),
    "106010": ("35/2016/NĐ-CP", "parser không bảo toàn chữ: HTML 30231 ký tự, provisions 30255"),
    "14959": ("36/2006/CT-TTg", "HTML MOJ không có thẻ prov-* nào"),
    "154221": ("37/2022/NĐ-CP", "1 neo kết thúc bằng ':' mà không có con — neo hứa danh sách mà không giao"),
    "134036": ("38/2018/TT-BNNPTNT", "hai node cùng neo '38/2018/TT-BNNPTNT > Điều 23 > Khoản 1' ở cấp trích dẫn được"),
    "136038": (
        "39/2019/QH14",
        "2 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd chuong 'NHỮNG QUY ĐỊNH CHUNG'",
    ),
    "27782": ("42/2012/TT-BNNPTNT", "HTML MOJ không có thẻ prov-* nào"),
    "133151": ("43/2018/TT-BNNPTNT", "hai node cùng neo '43/2018/TT-BNNPTNT > Điều 3 > Khoản 2' ở cấp trích dẫn được"),
    "136043": ("44/2019/QH14", "hai node cùng neo '44/2019/QH14 > Điều 3 > Khoản 1' ở cấp trích dẫn được"),
    "161034": ("45/2023/NĐ-CP", "hai node cùng neo '45/2023/NĐ-CP > Điều 22 > Khoản 1' ở cấp trích dẫn được"),
    "86961": ("49-CT/TW", "4 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd muc '1-Nhiệm vụ:'"),
    "187157": ("49/2026/NĐ-CP", "parser không bảo toàn chữ: HTML 60657 ký tự, provisions 60869"),
    "99391630-5b07-11f1-a02d-c7bf6cb95c18": (
        "50/2026/NĐ-CP",
        "hai node cùng neo '50/2026/NĐ-CP > Khoản 1' ở cấp trích dẫn được",
    ),
    "181854": (
        "52/2025/QĐ-UBND",
        "hai node cùng neo '52/2025/QĐ-UBND > Điều 1 > Khoản 2 > Điểm d' ở cấp trích dẫn được",
    ),
    "167313": ("53/2024/NĐ-CP", "hai node cùng neo '53/2024/NĐ-CP > Điều 28 > Khoản 3 > Điểm b' ở cấp trích dẫn được"),
    "184706": (
        "55/2025/NQ-HĐND",
        "bản ghi gateway trùng 185035 (cùng số hiệu 55/2025/NQ-HĐND, ngày, tiêu đề; HTML khác nhau vài chỗ): hai bản sâu làm trùng neo trích dẫn — cần chọn bản giữ (`BAN_TRUNG`) trước",
    ),
    "185035": (
        "55/2025/NQ-HĐND",
        "bản ghi gateway trùng 184706 (cùng số hiệu 55/2025/NQ-HĐND, ngày, tiêu đề; HTML khác nhau vài chỗ): hai bản sâu làm trùng neo trích dẫn — cần chọn bản giữ (`BAN_TRUNG`) trước",
    ),
    "97361": ("57/2015/TT-BLĐTBXH", "hai node cùng neo '57/2015/TT-BLĐTBXH > Điều 13 > Khoản 2' ở cấp trích dẫn được"),
    "175425": ("59/2024/QH15", "hai node cùng neo '59/2024/QH15 > Điều 52 > Khoản 1' ở cấp trích dẫn được"),
    "144268": ("62/2020/QH14", "hai node cùng neo '62/2020/QH14 > Điều 1 > Khoản 8 > Điểm a' ở cấp trích dẫn được"),
    "15074": (
        "65/2006/QH11",
        "2 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd muc '1. Luật Luật sư được Quốc hội nước Cộng hòa xã hội'",
    ),
    "15822": (
        "67/2006/NĐ-CP",
        "1 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd chuong 'NHỮNG QUY ĐỊNH CHUNG'",
    ),
    "26750": ("67/2011/QH12", "hai node cùng neo '67/2011/QH12 > Điều 11 > Khoản 2 > Điểm c' ở cấp trích dẫn được"),
    "137800": ("67/2019/NĐ-CP", "tiêu đề 'ĐIỀU KHOẢN THI HÀNH' gắn thẻ prov-clause thành Khoản không số hiệu"),
    "163442": ("67/2023/NĐ-CP", "hai node cùng neo '67/2023/NĐ-CP > Điều 10 > Khoản 2 > Điểm d' ở cấp trích dẫn được"),
    "187224": ("67/2026/NĐ-CP", "hai node cùng neo '67/2026/NĐ-CP > Điều 14 > Khoản 1' ở cấp trích dẫn được"),
    "24581": ("69/2008/NĐ-CP", "HTML MOJ không có thẻ prov-* nào"),
    "187346": ("69/2025/TT-BTC", "1 neo kết thúc bằng ':' mà không có con — neo hứa danh sách mà không giao"),
    "e4adc8f0-511a-11f1-ac02-8f6e04d42095": (
        "71/2026/QĐ-UBND",
        "thẻ prov-* phủ tới hết HTML nên không tách được bản ghi phu_luc — chữ đuôi nằm trong neo trích dẫn",
    ),
    "123806": ("75/2017/TT-BTC", "HTML MOJ không có thẻ prov-* nào"),
    "15253": ("78/2006/TT-BTC", "HTML MOJ không có thẻ prov-* nào"),
    "186338": (
        "80/2025/TT-BNNMT",
        "1 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd chuong 'CHƯƠNG TRÌNH CHỨNG NHẬN THỦY SẢN XUẤT KHẨU'",
    ),
    "172699": ("85/2024/NĐ-CP", "hai node cùng neo '85/2024/NĐ-CP > Điều 27 > Khoản 1' ở cấp trích dẫn được"),
    "17ca6150-5dbc-11f1-b7b9-79cb7f2eaaeb": (
        "86/2026/QĐ-UBND",
        "khối trách nhiệm thi hành cuối HTML gắn thẻ prov-clause nên không tách được bản ghi phu_luc — chữ đuôi nằm trong neo trích dẫn",
    ),
    "22162": (
        "98/2002/TT-BTC",
        "23 node cấp bắt buộc không số hiệu (nhãn nguồn không khớp parser), vd phan 'A- NHỮNG QUY ĐỊNH CHUNG'",
    ),
    "179428": ("99/2025/QH15", "hai node cùng neo '99/2025/QH15 > Điều 1 > Khoản 5' ở cấp trích dẫn được"),
    # K6 — HẾT khối sinh máy
}


def fetch_va_doi_chieu(client: MojClient, doc_ids: list[str], dest: Path) -> dict[str, Path]:
    """Như `MojClient.fetch_many`, cộng đối chiếu tiêu đề TRƯỚC KHI GHI file —
    cho đúng những id có mặt trong `TIEU_DE_DOI_CHIEU`. Giữ nguyên cơ chế cache
    (bỏ qua id đã có file) và nhịp nghỉ (`client.fetch_doc`) của `fetch_many`.
    """
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for did in doc_ids:
        p = dest / f"{did}.json"
        if p.exists():
            out[did] = p
            continue
        data = client.fetch_doc(did)
        _doi_chieu_tieu_de(did, data.get("title"))
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"[ok] {did} → {p.name}")
        out[did] = p
    return out


if __name__ == "__main__":
    s = get_settings()
    client = MojClient(base=s.moj_api_base, sleep=s.moj_rate_limit_sleep)
    fetch_va_doi_chieu(client, list(DOC_IDS), Path(s.data_raw_dir) / "moj")
