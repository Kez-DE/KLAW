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

from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from scripts.fetch_moj import DOC_IDS
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


def _canh_hieu_luc_di_vao(rel: pd.DataFrame, corpus: set[str]) -> pd.DataFrame:
    """Trích cạnh ĐI VÀO `corpus` mang tín hiệu hiệu lực, map tên quan hệ sang loai.

    Cột của `relationships.parquet`: `doc_id` (bên THỰC HIỆN hành vi sửa đổi/thay
    thế/...), `other_doc_id` (bên BỊ tác động), `relationship` (tên quan hệ tiếng
    Việt). Cạnh ĐI VÀO corpus là cạnh có `other_doc_id` nằm trong corpus — hướng
    ngược với "đi ra" mà API trả.
    """
    df = rel[["doc_id", "other_doc_id", "relationship"]].copy()
    df["doc_id"] = df["doc_id"].astype(str)
    df["other_doc_id"] = df["other_doc_id"].astype(str)
    df = df[df["other_doc_id"].isin(corpus) & df["relationship"].isin(QUAN_HE_HIEU_LUC)]
    df["loai"] = df["relationship"].map(QUAN_HE_HIEU_LUC)
    return df.rename(columns={"doc_id": "from_document_id", "other_doc_id": "to_document_id",
                               "relationship": "raw_text"})


def _ngay(s: object) -> date | None:
    """metadata.parquet ghi ngày dạng chuỗi 'DD/MM/YYYY'; NaN khi văn bản còn
    hiệu lực (chưa có ngày hết hiệu lực) — không phải lỗi, trả None."""
    if not isinstance(s, str) or not s:
        return None
    return datetime.strptime(s, "%d/%m/%Y").date()


def load_from_parquet(path: Path, engine: Engine) -> int:
    """Nạp cạnh hiệu lực đi vào corpus từ `path` (relationships.parquet) vào
    `"references"`. `metadata.parquet` được suy ra CÙNG THƯ MỤC với `path`.

    Idempotent: chèn văn bản ngoài corpus qua `ON CONFLICT DO NOTHING`, và xoá
    sạch cạnh loai 20..23 cũ trước khi chèn lại — chạy hai lần cho cùng số dòng.

    Trả số cạnh đã ghi. RAISE trước khi chạm DB nếu có cạnh trỏ tới văn bản
    ngoài corpus mà `metadata.parquet` không có — không tự bịa dữ liệu, không
    âm thầm bỏ qua (yêu cầu #3).
    """
    corpus = set(DOC_IDS)
    rel = pd.read_parquet(path)
    canh = _canh_hieu_luc_di_vao(rel, corpus)

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

        conn.execute(text('DELETE FROM "references" WHERE loai IN (20, 21, 22, 23)'))
        ghi = 0
        for r in canh.itertuples(index=False):
            conn.execute(text(
                'INSERT INTO "references" (from_document_id, to_document_id, loai, raw_text)'
                " VALUES (:f, :t, :l, :r)"
            ), {"f": r.from_document_id, "t": r.to_document_id, "l": r.loai, "r": r.raw_text})
            ghi += 1
    return ghi


if __name__ == "__main__":
    from src.config import get_settings
    from src.services.db import get_engine

    s = get_settings()
    n = load_from_parquet(Path(s.data_raw_dir) / "relationships.parquet", get_engine())
    print(f"cạnh hiệu lực đi vào đã nạp: {n}")
