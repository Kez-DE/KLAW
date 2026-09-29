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
