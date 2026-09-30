"""Nạp cạnh quan hệ hiệu lực ĐI VÀO các văn bản trong corpus.

API `/doc/{id}` (và endpoint `related`) chỉ trả cạnh ĐI RA — đã ĐO ở Plan 1
rằng `related` không lọc theo quan hệ thật (gọi `/doc/96122/related` trả về
văn bản "mới nhất toàn hệ thống", không liên quan BLHS). Cơ chế hiệu lực Mức 2
(Task 2) cần cạnh ĐI VÀO ("ai đã thay thế văn bản này?") → phải quét đồ thị
`data/raw/relationships.parquet` (1.033.255 cạnh, crawl vài giây), không tra
từng văn bản qua API.

CẢNH BÁO NGUỒN: `relationships.parquet` và `metadata.parquet` không tải từ API
MOJ — chúng đến từ dataset HuggingFace `th1nhng0/vietnamese-legal-documents`,
một crawl bên thứ ba VINTAGE KHÔNG RÕ (xác định ở Plan 1). Cạnh hiệu lực nạp từ
đây KHÔNG được tin thẳng là đúng-hiện-tại — Task 2 áp guard hợp lý trước khi
dùng để quyết định hiệu lực.

Chỉ 4 quan hệ mang TÍN HIỆU HIỆU LỰC được nạp (`QUAN_HE_HIEU_LUC`); 1.053/1.233
cạnh đi vào corpus là "Căn cứ" (căn cứ pháp lý, không phải hiệu lực) và các
quan hệ dẫn chiếu/hướng dẫn khác — CỐ Ý không nạp.

FK `references_from_document_fk` bắt `from_document_id` có trong `documents`,
mà cạnh đi vào xuất phát từ văn bản NGOÀI corpus theo định nghĩa. Trước khi nạp
cạnh, hàm chèn các văn bản ngoài corpus đó dưới dạng CHỈ-METADATA
(`depth='metadata'`, `tinh_trang='chua_xac_dinh'`, `checksum='metadata-only'`)
— đủ để thoả FK và để trích dẫn được văn bản sửa đổi bằng so_ky_hieu, không
đụng tới văn bản THẬT nào của corpus (`ON CONFLICT DO NOTHING`).
"""

import csv
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import Connection, Engine, text

from scripts.fetch_moj import DOC_IDS
from src.models.domain import sql_khoa_so_ky_hieu
from src.services.db import run_migrations

# Quan hệ mang TÍN HIỆU HIỆU LỰC (không phải "Căn cứ", "Dẫn chiếu", "Quy định chi
# tiết, hướng dẫn thi hành", "Hướng dẫn áp dụng"...) → mã loai TỰ SUY RA, dải
# 20..23 do migration 007 sở hữu — không đụng 1..15 của MOJ.
QUAN_HE_HIEU_LUC: dict[str, int] = {
    "Sửa đổi, bổ sung": 20,
    "Thay thế": 21,
    "Văn bản quy định hết hiệu lực": 22,
    "Văn bản quy định hết hiệu lực 1 phần": 23,
}

_COT_METADATA = ("id", "so_ky_hieu", "title", "loai_van_ban",
                  "ngay_ban_hanh", "ngay_co_hieu_luc", "ngay_het_hieu_luc")

# Cạnh parquet ĐÃ ĐỐI CHIẾU NGUYÊN VĂN là sai: `(doc_id, other_doc_id,
# relationship)`. Ghi TƯỜNG MINH từng cạnh, cùng lý do `013_bang_trong_noi_dung`
# không nới điều kiện: thêm dòng là hành vi có ý thức, đòi mở nguồn ra đọc.
CANH_SAI: frozenset[tuple[str, str, str]] = frozenset({
    # 19/2023/QH15 (Bảo vệ quyền lợi người tiêu dùng) "sửa" BLLĐ 45/2019/QH14:
    # Điều 78 chỉ sửa BLTTDS 92/2015 "đã được sửa đổi, bổ sung một số điều theo
    # Bộ luật số 45/2019/QH14, ..." — crawl nguồn bắt nhầm số hiệu trong câu.
    # 18/VBHN-VPQH (hợp nhất BLLĐ) không có 19/2023. Đo 2026-09-28.
    ("161263", "139264", "Sửa đổi, bổ sung"),
    # Không văn bản nào dưới đây sửa Luật Thi hành án hình sự 127/2025/QH15 (đọc
    # toàn văn gateway 2026-09-28): 143/2025/QH15 Điều 50 khoản 2 sửa Luật Thuế
    # TNDN 67/2025 "đã được sửa đổi, bổ sung ... theo Luật số ... 127/2025/QH15"
    # — cùng lỗi bắt nhầm số hiệu; 231/2026/NĐ-CP chỉ "Căn cứ" và thi hành 127/2025.
    ("187601", "187035", "Sửa đổi, bổ sung"),
    ("386e5ad0-7d09-11f1-9c00-f9e84f25c1dc", "187035", "Sửa đổi, bổ sung"),
    # K8 2026-09-29 (nghiên cứu K8b, `docs/plans/active/kho-luat-trich-dan-day-du.md`):
    # 158/2025/NĐ-CP KHÔNG thay 135/2020/NĐ-CP (còn hiệu lực). Điều 44 khoản 2 điểm c
    # chỉ chấm dứt "Khoản 2 Điều 3; các khoản 1, 3 Điều 7 và khoản 2 Điều 8" và Phụ lục
    # III (Công báo 851+852) — cạnh đúng là loai 23, ở `CANH_DOI_CHIEU_NGUYEN_VAN`.
    ("178757", "152734", "Thay thế"),
    # Luật 71/2025/QH15 Điều 49 khoản 5 điểm a chỉ thay một cụm từ tại khoản 22 Điều
    # 79 và khoản 1 Điều 202 Luật Đất đai 31/2024/QH15 (Công báo 965+966): sửa đổi,
    # không thay thế — cạnh loai 20 ở `CANH_DOI_CHIEU_NGUYEN_VAN`.
    ("179989", "177815", "Thay thế"),
    # Nghị định 71/2024/NĐ-CP không thay thế được Luật Đất đai 31/2024/QH15 (thứ bậc
    # văn bản, Luật Ban hành VBQPPL); toàn văn 71/2024 chưa đối chiếu nên không thêm
    # cạnh thay nó.
    ("168381", "177815", "Thay thế"),
    # Đọc ra "Thông tư 01/2014/TT-BLĐTBXH quy định Nghị định 55/2013/NĐ-CP hết hiệu
    # lực" — sai thứ bậc và sai văn bản: 29/2019/NĐ-CP Điều 28 khoản 2 mới chấm dứt
    # 55/2013 (29.signed.pdf trang 14); cạnh đó (loai 21) đã có.
    ("30475", "37502", "Văn bản quy định hết hiệu lực"),
    # F1 2026-09-29 — cạnh parquet vào nhóm "nền tảng". Văn bản HĐND, UBND tỉnh không
    # sửa hay thay được luật của Quốc hội (thứ bậc, 64/2025/QH15 Điều 4 do 87/2025/QH15
    # sửa). Trang vbpl.vn của 178717 và 175440 (2026-09-29) cũng ghi các quan hệ này:
    # lỗi có từ CSDL quốc gia, không riêng parquet.
    ("184262", "178717", "Sửa đổi, bổ sung"),  # 74/2025/QĐ-UBND
    ("183018", "178717", "Sửa đổi, bổ sung"),  # 27/2025/NQ-HĐND
    ("183300", "178717", "Thay thế"),  # 146/2025/QĐ-UBND
    ("552ed4e0-6087-11f1-b7fc-b958fe2dd742", "175440", "Sửa đổi, bổ sung"),  # 28/2026/NQ-HĐND
    # 136/2025/QH15 nêu 203/2025/QH15 chỉ ở lời căn cứ ("Căn cứ Hiến pháp … đã được sửa
    # đổi, bổ sung một số điều theo Nghị quyết số 203/2025/QH15"), toàn văn gateway 187809.
    ("187809", "178314", "Sửa đổi, bổ sung"),
    # N1 2026-09-30: 151/2025/NĐ-CP (phân định thẩm quyền 2 cấp, đất đai) KHÔNG thay
    # 101/2024/NĐ-CP hay 102/2024/NĐ-CP. Điều 21 khoản 4 điểm b, c (toàn văn gateway
    # 178259) chỉ cho một số khoản, điều, mẫu của hai nghị định hết hiệu lực — cạnh
    # đúng là loai 23, ở `CANH_DOI_CHIEU_NGUYEN_VAN`.
    ("178259", "169188", "Thay thế"),
    ("178259", "169363", "Thay thế"),
})

# Bản ghi trùng (dòng thừa → dòng giữ): gateway và parquet mang HAI id cho cùng một
# văn bản; `scripts/don_kho.py` gộp chúng trong DB, và ở đây mọi cạnh parquet của
# dòng thừa được trỏ sang dòng giữ để nạp lại không chèn dòng thừa trở lại.
# Bằng chứng (response gateway 2026-09-28), cả bốn id đều Publish, cùng số, cùng ngày:
# - 33/2005/NĐ-CP: 18451 có publicDate 2013-03-02, tệp '33.2005.ND.CP.doc', tiêu
#   đề "Pháp lệnh Thú y"; 40022 không publicDate, tệp 'ND 33 Huong dan PLTY 15.3.05.doc'.
# - 60/2020/QH14: 142846 là văn bản Quốc hội thông qua; 153788 là bản sao y
#   ("SAO Y BẢN CHÍNH … Số: 05/SY-VPCTN") của Văn phòng Chủ tịch nước.
# K12 2026-09-29 (quyết định 2026-09-28 mục 17, chủ dự án chốt hai bản giữ đầu):
# - 07/2025/NĐ-CP: giữ 174485; 187195 ghi docNum '07/2025/NĐ-СР' (С Р Kirin), cùng
#   ngày ban hành, tiêu đề, người ký (review K6 vòng 1).
# - 18/2011/TT-BNNPTNT: giữ 67884; 26419 ghi docNum 'TT- BNNPTNT' (khoảng trắng).
# - 55/2025/NQ-HĐND: giữ 184706. Cả hai trang vbpl.vn (184706, 185035) qua phép kiểm
#   link (`lam_moi_hieu_luc.kiem_trang_vbpl`, 2026-09-29 10:34 UTC) và hiện cùng toàn
#   văn; phá hoà bằng bản ghi gateway: 184706 mang người ký (Lê Văn Hiệu) và
#   effTo 2030-12-31 đúng Điều 6 khoản 1 ("đến ngày 31 tháng 12 năm 2030"), 185035
#   ghi người ký "Đang cập nhật" và effTo null.
# - 115/1998/TT-BTC: giữ 7576. Review K12 tìm ra cặp này bằng `khoa_so_hieu` trên tập
#   được hiện. Toàn văn gateway của CẢ HAI ghi "ngày 19 tháng 8 năm 1998", cùng thân
#   bài, cùng người ký Phạm Văn Trọng; 7576 có issueDate 1998-08-19 khớp chính văn bản,
#   110222 ghi 1998-08-18. Cả hai trang vbpl.vn qua phép kiểm link (2026-09-29).
BAN_TRUNG: dict[str, str] = {
    "40022": "18451",
    "153788": "142846",
    "187195": "174485",
    "26419": "67884",
    "185035": "184706",
    "110222": "7576",
}

# Cùng quan hệ sai ấy trong mảng `references` MOJ của 19/2023/QH15 (loai 10,
# `raw_text` '45/2019/QH14'): `(from, to, loai)`. `build_seed` bỏ nó khỏi seed,
# `ingest` xoá nó khỏi DB đã nạp từ seed cũ.
CANH_SAI_MOJ: frozenset[tuple[str, str, int]] = frozenset({
    ("161263", "139264", 10),
    # K8 2026-09-29 — mã MOJ 1/12 đi vào đọc là "thay thế" (`effectivity.TAC_DONG`)
    # ngay khi loader cạnh MOJ được bật; nguyên văn nói khác:
    # 71/2025/QH15 chỉ thay cụm từ trong 31/2024/QH15 (Điều 49 khoản 5 điểm a).
    ("179989", "177815", 12),
    # 293/2025/NĐ-CP Điều 5 khoản 3 chỉ bãi bỏ khoản 7 Điều 15 và Phụ lục I của
    # 128/2025/NĐ-CP; cạnh đúng loai 23 (128/2025 → 293/2025) đã có.
    ("183939", "178260", 1),
    # 113/2025/QH15 Điều 30 khoản 3: Pháp lệnh 06/2003 "đã được sửa đổi, bổ sung theo
    # Pháp lệnh số 07/2025/UBTVQH15 hết hiệu lực" — hai dòng loai 1 trùng nhau, thay
    # bằng MỘT cạnh loai 21 ở `CANH_DOI_CHIEU_NGUYEN_VAN` để Mức 2a đọc được.
    ("6fa2fd20-597e-11f1-add2-7717d93a2118", "179969", 1),
    # Hai dòng loai 12 trùng của 293/2025 → 74/2024; cạnh loai 21 cùng cặp đã có
    # (293/2025 Điều 5 khoản 2).
    ("183939", "168670", 12),
    # 90/2019/NĐ-CP không thể căn cứ một luật năm 2025 ("74/2025/QH15", đích không có
    # trong kho); cạnh căn cứ đúng 74/2014/QH13 đã có.
    ("139094", "179273", 3),
})

# Cạnh hiệu lực ĐỌC TỪ NGUYÊN VĂN mà parquet không có (0 cạnh hiệu lực nào chạm
# 154245, đo 2026-09-28): `(from, to, loai, relationship)`, chiều như parquet —
# `from` là văn bản ĐI THAY.
CANH_DOI_CHIEU_NGUYEN_VAN: tuple[tuple[str, str, int, str], ...] = (
    # 38/2022/NĐ-CP Điều 5 khoản 2: "Nghị định số 90/2019/NĐ-CP ... hết hiệu lực
    # kể từ ngày Nghị định này có hiệu lực thi hành" (01/7/2022).
    ("154245", "139094", 21, "Thay thế"),
    # 74/2024/NĐ-CP Điều 5 khoản 2, cùng câu cho 38/2022/NĐ-CP; `applicationNote`
    # của gateway cho 154245: "Bị thay thế bởi Nghị định số 74/2024/NĐ-CP".
    ("168670", "154245", 21, "Thay thế"),
    # 145/2020/NĐ-CP Điều 114 khoản 2 điểm đ: "các Nghị định sau đây hết hiệu
    # lực thi hành: ... Nghị định số 121/2018/NĐ-CP" — cùng khoản mà parquet ghi
    # loai 21 cho 44/2013, 45/2013, 49/2013..., riêng 121/2018 thì thiếu. Không
    # có cạnh này, 121/2018 ra `con_hieu_luc` theo effStatus CHL đã cũ của MOJ.
    ("152668", "131010", 21, "Thay thế"),
    # 38/2019/QH14 Điều 151 khoản 3: "Luật Quản lý thuế số 78/2006/QH11 ... hết
    # hiệu lực kể từ ngày Luật này có hiệu lực thi hành". Parquet không có cạnh
    # hiệu lực nào cho 14832 (chỉ hai cạnh MOJ loai 12, Mức 2a không đọc).
    ("136036", "14832", 21, "Thay thế"),
    # K8 2026-09-29. 283/2026/NĐ-CP Điều 66 khoản 4: "Nghị định số 12/2022/NĐ-CP ...
    # hết hiệu lực thi hành kể từ ngày Nghị định này có hiệu lực" (10/9/2026, khoản 1).
    ("787d3780-866f-11f1-8511-612429c9d15e", "153913", 21, "Thay thế"),
    # 158/2025/NĐ-CP Điều 44 khoản 2 điểm c: chấm dứt MỘT PHẦN 135/2020/NĐ-CP (thay
    # cạnh sai loai 21 trong `CANH_SAI`). Chiều như parquet: `from` bị khai tử.
    ("152734", "178757", 23, "Văn bản quy định hết hiệu lực 1 phần"),
    # Luật 71/2025/QH15 Điều 49 khoản 5 điểm a sửa cụm từ trong 31/2024/QH15.
    ("179989", "177815", 20, "Sửa đổi, bổ sung"),
    # 153/2016/NĐ-CP Điều 6 khoản 1: "Nghị định số 122/2015/NĐ-CP ... hết hiệu lực kể
    # từ ngày Nghị định này có hiệu lực thi hành" (01/01/2017). Parquet thiếu cạnh.
    ("117553", "92898", 21, "Thay thế"),
    # 113/2025/QH15 Điều 30 khoản 3 (thay hai dòng MOJ loai 1 trong `CANH_SAI_MOJ`).
    ("6fa2fd20-597e-11f1-add2-7717d93a2118", "179969", 21, "Thay thế"),
    # Luật 148/2025/QH15 Điều 47 khoản 2 (Công báo số 43, `scripts.fetch_congbao`): Luật
    # Công nghệ thông tin 67/2006/QH11 "hết hiệu kể từ ngày Luật này có hiệu lực thi hành"
    # (01/7/2026, khoản 1), trừ chuyển tiếp Điều 48 khoản 1, 2.
    ("cb-468708", "15066", 21, "Thay thế"),
    # F1 2026-09-29 (bằng chứng ở `data/seed/canh_doi_chieu.yaml`): Luật 87/2025/QH15
    # Điều 1 sửa 64/2025/QH15, khoản 1 thay Điều 4; Nghị quyết 203/2025/QH15 Điều 1 sửa
    # Hiến pháp Điều 9, 10, khoản 1 Điều 84, Điều 110, 111. Parquet có cả hai, nhưng
    # `--chi-danh-sach` không nạp parquet.
    ("178717", "175440", 20, "Sửa đổi, bổ sung"),
    ("178314", "32801", 20, "Sửa đổi, bổ sung"),
    # N1 2026-09-30: 151/2025/NĐ-CP Điều 21 khoản 4 điểm b, c chấm dứt MỘT PHẦN
    # 101/2024/NĐ-CP và 102/2024/NĐ-CP (thay hai cạnh sai loai 21 trong `CANH_SAI`).
    # Chiều như parquet: `from` bị khai tử.
    ("169188", "178259", 23, "Văn bản quy định hết hiệu lực 1 phần"),
    ("169363", "178259", 23, "Văn bản quy định hết hiệu lực 1 phần"),
)

# Văn bản hợp nhất (Công báo) nêu đích danh luật đi sửa từng điều khoản
# (`sua_doi_dieu_khoan`, `scripts/nap_sua_doi_vbhn.py`) ⇒ cạnh "Sửa đổi, bổ
# sung" cấp VĂN BẢN. Nối `sua_boi_so_ky_hieu` sang id bằng số hiệu.
_SQL_VBHN = text(
    "SELECT DISTINCT s.sua_boi_so_ky_hieu AS sk, d.id AS f, p.document_id AS t"
    " FROM sua_doi_dieu_khoan s"
    " JOIN provisions p ON p.id = s.provision_id"
    f" JOIN documents d ON {sql_khoa_so_ky_hieu('d.so_ky_hieu')} = {sql_khoa_so_ky_hieu('s.sua_boi_so_ky_hieu')}"
    " WHERE s.do_tin_cay <> 'can_doi_chieu_tay'"
)


def _canh_tu_vbhn(conn) -> list[tuple[str, str, int, str]]:
    """Cạnh loai 20 suy từ VBHN. Số hiệu KHÔNG duy nhất trong `documents` (Luật
    và Nghị quyết dùng chung số) — trùng thì RAISE, không đoán văn bản nào."""
    theo_sk: dict[tuple[str, str], set[str]] = {}
    for sk, f, t in conn.execute(_SQL_VBHN):
        theo_sk.setdefault((sk, t), set()).add(f)
    mo_ho = {k: v for k, v in theo_sk.items() if len(v) > 1}
    if mo_ho:
        raise ValueError(f"số hiệu đi sửa khớp nhiều văn bản, không chọn được: {mo_ho}")
    return [(f, t, QUAN_HE_HIEU_LUC["Sửa đổi, bổ sung"], "Sửa đổi, bổ sung")
            for (_, t), (f,) in sorted(theo_sk.items()) if f != t]


def _bo_sung(canh: pd.DataFrame, them) -> pd.DataFrame:
    """Nối `them` vào `canh`, bỏ cạnh `(from, to, loai)` đã có — một quan hệ
    hai nguồn cùng nói thì vẫn là MỘT cạnh (`/lien-quan` liệt kê từng dòng)."""
    co = set(zip(canh["from_document_id"], canh["to_document_id"], canh["loai"], strict=True))
    moi = []
    for f, t, loai, ten in them:
        if (f, t, loai) not in co:
            co.add((f, t, loai))
            moi.append({"from_document_id": f, "to_document_id": t, "loai": loai, "raw_text": ten})
    return pd.concat([canh, pd.DataFrame(moi)], ignore_index=True) if moi else canh


def _canh_hieu_luc_di_vao(rel: pd.DataFrame, corpus: set[str]) -> pd.DataFrame:
    """Trích cạnh ĐI VÀO `corpus` mang tín hiệu hiệu lực, map tên quan hệ sang loai.

    Cột của `relationships.parquet`: `doc_id` (bên THỰC HIỆN hành vi sửa đổi/thay
    thế/...), `other_doc_id` (bên BỊ tác động), `relationship` (tên quan hệ tiếng
    Việt). Cạnh ĐI VÀO corpus là cạnh có `other_doc_id` nằm trong corpus — hướng
    ngược với "đi ra" mà API trả.

    Loại cạnh TỰ TRỎ (`doc_id == other_doc_id`, "văn bản X thay thế/sửa đổi
    chính X") — rác của nguồn crawl bên thứ ba (xem cảnh báo đầu file), không
    phải một quan hệ pháp lý có thật. Đo được 2026-09-02 sau khi mở corpus
    (`other_doc_id` giờ phủ cả 87 văn bản tầng `shallow`, không chỉ 53 văn
    bản `deep` của `DOC_IDS`): đúng 3 cạnh loại này lộ ra, cả ba đều trỏ vào
    một văn bản `shallow` (`2322`, `146541`, `132170`) — trước đó bị lọc mất
    tình cờ vì `other_doc_id` của chúng chưa từng nằm trong corpus hẹp.
    """
    df = rel[["doc_id", "other_doc_id", "relationship"]].copy()
    df["doc_id"] = df["doc_id"].astype(str).replace(BAN_TRUNG)
    df["other_doc_id"] = df["other_doc_id"].astype(str).replace(BAN_TRUNG)
    df = df[df["other_doc_id"].isin(corpus) & df["relationship"].isin(QUAN_HE_HIEU_LUC)
            & (df["doc_id"] != df["other_doc_id"])].drop_duplicates()
    sai = pd.Series([k in CANH_SAI for k in zip(df["doc_id"], df["other_doc_id"],
                                                  df["relationship"], strict=True)],
                    index=df.index, dtype=bool)
    df = df[~sai]
    df["loai"] = df["relationship"].map(QUAN_HE_HIEU_LUC)
    return df.rename(columns={"doc_id": "from_document_id", "other_doc_id": "to_document_id",
                               "relationship": "raw_text"})


def _ngay(s: object) -> date | None:
    """metadata.parquet ghi ngày dạng chuỗi 'DD/MM/YYYY'; NaN khi văn bản còn
    hiệu lực (chưa có ngày hết hiệu lực) — không phải lỗi, trả None."""
    if not isinstance(s, str) or not s:
        return None
    return datetime.strptime(s, "%d/%m/%Y").date()


def load_from_parquet(path: Path, engine: Engine, them_van_ban_ngoai: bool = True) -> int:
    """Nạp cạnh hiệu lực đi vào corpus từ `path` (relationships.parquet) vào
    `"references"`. `metadata.parquet` được suy ra CÙNG THƯ MỤC với `path`.

    Idempotent: chèn văn bản ngoài corpus qua `ON CONFLICT DO NOTHING`, và xoá
    sạch cạnh loai 20..23 cũ trước khi chèn lại — chạy hai lần cho cùng số dòng.

    Trả số cạnh đã ghi. RAISE trước khi chạm DB nếu có cạnh trỏ tới văn bản
    ngoài corpus mà `metadata.parquet` không có — không tự bịa dữ liệu, không
    âm thầm bỏ qua (yêu cầu #3).

    `corpus`: khi có `engine`, đọc TRỰC TIẾP từ `documents` (`depth <>
    'metadata'`) — sửa 2026-09-02. Trước đó dùng `set(DOC_IDS)` (danh sách 53
    văn bản `deep` mà `fetch_moj.py` tải toàn văn), đúng lúc corpus THẬT chỉ
    có đúng ngần ấy văn bản; mở kho ra 8 lĩnh vực thêm 87 văn bản tầng
    `shallow` vào `documents` mà KHÔNG thêm vào `DOC_IDS` (chúng không tải
    toàn văn), nên "corpus" của loader tụt lại phía sau "corpus" thật — cạnh
    đi vào các văn bản `shallow` bị loại oan, và văn bản `shallow` đóng vai
    `from_document_id` bị coi nhầm là ngoài corpus. `DOC_IDS` giữ lại làm
    phương án lùi khi `engine=None` (test đơn vị dựng tay, không có DB).

    ĐỌC corpus TRƯỚC khi gọi `run_migrations()` ở dưới — KHÔNG đảo thứ tự.
    `run_migrations()` (qua `016_tang_nong.sql`) nâng cấp `depth='metadata'`
    thành `'shallow'` cho văn bản chỉ-metadata đủ điều kiện, mà CHÍNH HÀM
    NÀY vừa chèn những văn bản chỉ-metadata đó ở lần gọi TRƯỚC. Gọi
    `run_migrations()` rồi mới đọc corpus tạo một vòng phản hồi: mỗi lần gọi
    lại nâng cấp lô văn bản chỉ-metadata của lần gọi trước thành `shallow`
    (⇒ vào corpus), corpus phình ra, kéo thêm cạnh mới, tạo thêm văn bản
    chỉ-metadata mới cho lần gọi kế — không bao giờ dừng, và
    `test_idempotent_chay_hai_lan_cung_so_dong` bắt được ngay (683→776 dòng
    chỉ-metadata chỉ sau một lần gọi lại). Đọc corpus TRƯỚC giữ nó là một ẢNH
    CHỤP của `documents` tại thời điểm gọi, độc lập với tác dụng phụ của
    chính lần gọi này.

    `them_van_ban_ngoai=False`: KHÔNG chèn văn bản chỉ-metadata mới; cạnh từ văn
    bản chưa có trong `documents` bị bỏ và ĐẾM ra. Dùng khi kho vừa nhận văn
    bản deep mới mà quyết định mở kho có ranh giới
    (`docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md` mục 4)
    chưa cho nạp vòng văn bản kế tiếp.

    Sau cạnh parquet (trừ `CANH_SAI`) là `CANH_DOI_CHIEU_NGUYEN_VAN` và cạnh suy
    từ VBHN (`_canh_tu_vbhn`); hai đầu của chúng phải có trong `documents`,
    thiếu thì RAISE. Cuối cùng `canh_doi_chieu` được đặt lại từ seed
    (`scripts.nap_canh_doi_chieu`), vì id cạnh vừa đổi hết.
    """
    if engine is not None:
        with engine.connect() as c:
            corpus = {r[0] for r in c.execute(
                text("SELECT id FROM documents WHERE depth <> 'metadata'")
            )}
            da_co = {r[0] for r in c.execute(text("SELECT id FROM documents"))}
    else:
        corpus = set(DOC_IDS)
        da_co = corpus
    rel = pd.read_parquet(path)
    canh = _canh_hieu_luc_di_vao(rel, corpus)
    if not them_van_ban_ngoai:
        ngoai = ~canh["from_document_id"].isin(da_co)
        print(f"bỏ {int(ngoai.sum())} cạnh từ {canh[ngoai]['from_document_id'].nunique()} "
              "văn bản chưa có trong documents (them_van_ban_ngoai=False)")
        canh = canh[~ngoai]

    ngoai_corpus = set(canh["from_document_id"]) - corpus
    meta = pd.read_parquet(path.parent / "metadata.parquet", columns=list(_COT_METADATA))
    meta["id"] = meta["id"].astype(str)
    meta = meta[meta["id"].isin(ngoai_corpus)].set_index("id")

    thieu = ngoai_corpus - set(meta.index)
    if thieu:
        raise ValueError(
            f"{len(thieu)} văn bản ngoài corpus không có metadata trong metadata.parquet — "
            f"KHÔNG nạp được cạnh trỏ tới chúng (không tự bịa dữ liệu): {sorted(thieu)}"
        )

    run_migrations()
    with engine.begin() as conn:
        for doc_id, row in meta.iterrows():
            conn.execute(text(
                "INSERT INTO documents"
                " (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, depth, checksum,"
                "  ngay_ban_hanh, ngay_hieu_luc, ngay_het_hieu_luc)"
                " VALUES (:id, :so_ky_hieu, :loai_van_ban, :ten, 'chua_xac_dinh', 'metadata',"
                "         'metadata-only', :ngay_ban_hanh, :ngay_hieu_luc, :ngay_het_hieu_luc)"
                " ON CONFLICT (id) DO NOTHING"
            ), {"id": doc_id, "so_ky_hieu": row["so_ky_hieu"], "loai_van_ban": row["loai_van_ban"],
                "ten": row["title"], "ngay_ban_hanh": _ngay(row["ngay_ban_hanh"]),
                "ngay_hieu_luc": _ngay(row["ngay_co_hieu_luc"]),
                "ngay_het_hieu_luc": _ngay(row["ngay_het_hieu_luc"])})

        them = [*CANH_DOI_CHIEU_NGUYEN_VAN, *_canh_tu_vbhn(conn)]
        co = {r[0] for r in conn.execute(text("SELECT id FROM documents"))}
        vang = sorted({x for f, t, _, _ in them for x in (f, t)} - co)
        if vang:
            raise ValueError(f"cạnh bổ sung trỏ tới văn bản chưa có trong documents: {vang}")
        canh = _bo_sung(canh, them)

        conn.execute(text('DELETE FROM "references" WHERE loai IN (20, 21, 22, 23)'))
        ghi = 0
        for r in canh.itertuples(index=False):
            conn.execute(text(
                'INSERT INTO "references" (from_document_id, to_document_id, loai, raw_text)'
                " VALUES (:f, :t, :l, :r)"
            ), {"f": r.from_document_id, "t": r.to_document_id, "l": r.loai, "r": r.raw_text})
            ghi += 1
        # DELETE ở trên CASCADE bằng chứng đối chiếu (migration 039): đặt lại từ seed,
        # cùng giao dịch — một cạnh seed nói đã đối chiếu mà nay không còn là LỖI, rollback.
        from scripts.nap_canh_doi_chieu import doc_seed, nap_vao

        nap_vao(conn, doc_seed())
    return ghi


def danh_sach_ap(canh_db: list[tuple], them: list[tuple]) -> tuple[list[int], list[tuple]]:
    """Phần ĐÃ ĐỐI CHIẾU của `load_from_parquet`, tính trên cạnh `(id, from, to, loai)`
    đang có trong DB: id cạnh khớp `CANH_SAI` phải xoá, và cạnh `them` (dạng
    `CANH_DOI_CHIEU_NGUYEN_VAN`) còn thiếu phải chèn — mỗi khoá một lần."""
    sai = {(f, t, QUAN_HE_HIEU_LUC[r]) for f, t, r in CANH_SAI}
    xoa = [i for i, f, t, loai in canh_db if (f, t, loai) in sai]
    co = {(f, t, loai) for i, f, t, loai in canh_db if i not in xoa}
    moi = []
    for c in them:
        if c[:3] not in co:
            co.add(c[:3])
            moi.append(c)
    return xoa, moi


def ap_danh_sach(conn: Connection, sao_luu: Path | None) -> dict:
    """Áp RIÊNG `CANH_SAI` + `CANH_DOI_CHIEU_NGUYEN_VAN` + cạnh VBHN lên DB rồi đặt lại
    `canh_doi_chieu` từ seed, trên `conn` (giao dịch của người gọi). KHÔNG nạp lại
    parquet: lượt nạp đầy đủ kéo thêm cạnh parquet chưa ai soát vào văn bản mới vào kho
    và (mặc định) chèn văn bản ngoài kho. Idempotent. Dòng sắp xoá được ghi ra
    `sao_luu/canh-xoa-<UTC>.csv` (không bao giờ ghi đè) TRƯỚC khi xoá."""
    dong = [
        dict(r)
        for r in conn.execute(
            text(
                'SELECT id, from_document_id, to_document_id, loai, raw_text FROM "references"'
                " WHERE loai BETWEEN 20 AND 23 AND from_provision_id IS NULL ORDER BY id"
            )
        ).mappings()
    ]
    xoa, moi = danh_sach_ap(
        [(d["id"], d["from_document_id"], d["to_document_id"], d["loai"]) for d in dong],
        [*CANH_DOI_CHIEU_NGUYEN_VAN, *_canh_tu_vbhn(conn)],
    )
    tep = None
    if xoa and sao_luu is not None:
        sao_luu.mkdir(parents=True, exist_ok=True)
        tep = sao_luu / f"canh-xoa-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.csv"
        with tep.open("x", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, list(dong[0]))
            w.writeheader()
            w.writerows(d for d in dong if d["id"] in xoa)
    conn.execute(text('DELETE FROM "references" WHERE id = ANY(:ids)'), {"ids": xoa})
    them = [
        conn.execute(
            text(
                'INSERT INTO "references" (from_document_id, to_document_id, loai, raw_text)'
                " VALUES (:f, :t, :l, :r) RETURNING id"
            ),
            {"f": f, "t": t, "l": loai, "r": ten},
        ).scalar_one()
        for f, t, loai, ten in moi
    ]
    from scripts.nap_canh_doi_chieu import doc_seed, nap_vao

    return {
        "xoa": xoa,
        "sao_luu": str(tep) if tep else None,
        "them": list(zip(them, moi, strict=True)),
        "canh_doi_chieu": nap_vao(conn, doc_seed()),
    }


if __name__ == "__main__":
    import sys

    from src.config import get_settings
    from src.services.db import get_engine

    if "--chi-danh-sach" in sys.argv:  # dry-run trừ khi có --ghi
        ghi = "--ghi" in sys.argv
        thu_muc = Path(sys.argv[sys.argv.index("--sao-luu") + 1]) if "--sao-luu" in sys.argv else Path("data/sao-luu")
        with get_engine().connect() as c, c.begin() as tx:
            print(ap_danh_sach(c, thu_muc if ghi else None))
            if not ghi:
                tx.rollback()
                print("DRY-RUN — ROLLBACK")
        sys.exit(0)

    s = get_settings()
    n = load_from_parquet(Path(s.data_raw_dir) / "relationships.parquet", get_engine(),
                          them_van_ban_ngoai="--khong-them-van-ban-ngoai" not in sys.argv)
    print(f"cạnh hiệu lực đi vào đã nạp: {n}")
