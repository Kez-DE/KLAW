"""Test cho `scripts/load_incoming_edges.py` — nạp cạnh hiệu lực ĐI VÀO corpus.

Nguồn dữ liệu: `data/raw/relationships.parquet` + `metadata.parquet`, crawl bên
thứ ba (HuggingFace `th1nhng0/vietnamese-legal-documents`), vintage KHÔNG rõ —
xem cảnh báo đầu `scripts/load_incoming_edges.py`. Chỉ 4 quan hệ mang tín hiệu
hiệu lực được nạp (Ruling 4 của Kenz, đã đo lại ở đây): "Căn cứ" (1.053/1.233
cạnh đi vào 21 văn bản corpus) là căn cứ pháp lý, KHÔNG phải tín hiệu hiệu lực,
và không được đếm chung.
"""

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from scripts.load_incoming_edges import QUAN_HE_HIEU_LUC, _canh_hieu_luc_di_vao, load_from_parquet
from src.services.db import get_engine, run_migrations

RAW = Path("data/raw")


# ══ Đơn vị — DataFrame dựng tay, không cần Postgres lẫn file parquet thật ══


def test_canh_hieu_luc_di_vao_LOAI_can_cu_va_CHI_giu_dich_trong_corpus():
    """'Căn cứ' là 1.053/1.233 cạnh đi vào THẬT — phải bị loại. Cạnh đi vào một
    văn bản NGOÀI corpus cũng phải bị loại dù cùng tên quan hệ hiệu lực."""
    rel = pd.DataFrame([
        {"doc_id": "A", "other_doc_id": "139264", "relationship": "Thay thế"},  # giữ
        {"doc_id": "B", "other_doc_id": "139264", "relationship": "Căn cứ"},  # loại: Căn cứ
        {"doc_id": "C", "other_doc_id": "999999", "relationship": "Thay thế"},  # loại: ngoài corpus
        {"doc_id": "D", "other_doc_id": "96122", "relationship": "Dẫn chiếu"},  # loại: không hiệu lực
    ])
    out = _canh_hieu_luc_di_vao(rel, {"139264", "96122"})
    assert list(out["from_document_id"]) == ["A"]
    assert out.iloc[0]["to_document_id"] == "139264"
    assert out.iloc[0]["loai"] == QUAN_HE_HIEU_LUC["Thay thế"]


def test_canh_hieu_luc_di_vao_MAP_dung_ca_4_ma():
    rel = pd.DataFrame([
        {"doc_id": str(i), "other_doc_id": "139264", "relationship": ten}
        for i, ten in enumerate(QUAN_HE_HIEU_LUC)
    ])
    out = _canh_hieu_luc_di_vao(rel, {"139264"})
    assert dict(zip(out["raw_text"], out["loai"], strict=True)) == QUAN_HE_HIEU_LUC


def test_load_from_parquet_RAISE_khi_thieu_metadata_khong_am_tham_bo_qua(tmp_path):
    """Một cạnh trỏ tới văn bản ngoài corpus mà `metadata.parquet` không có: phải
    RAISE (đếm + báo rõ id) TRƯỚC KHI chạm DB, không được continue/skip lặng lẽ
    (yêu cầu #3 — không swallow lỗi). Hiện thật là 0/36 thiếu, nhưng code phải
    xử lý đúng nếu con số đó khác 0 trong tương lai."""
    rel = pd.DataFrame([
        {"doc_id": "__khong_co_metadata__", "other_doc_id": "139264", "relationship": "Thay thế"},
    ])
    rel.to_parquet(tmp_path / "relationships.parquet")
    pd.DataFrame({"id": pd.Series(dtype=str), "so_ky_hieu": pd.Series(dtype=str),
                  "title": pd.Series(dtype=str), "loai_van_ban": pd.Series(dtype=str),
                  "ngay_ban_hanh": pd.Series(dtype=str), "ngay_co_hieu_luc": pd.Series(dtype=str),
                  "ngay_het_hieu_luc": pd.Series(dtype=str)}).to_parquet(tmp_path / "metadata.parquet")

    with pytest.raises(ValueError, match="__khong_co_metadata__"):
        load_from_parquet(tmp_path / "relationships.parquet", engine=None)


# ══ Tích hợp — cần Postgres đang chạy + parquet thật trong data/raw/ ══


@pytest.mark.integration
def test_nap_dung_moi_canh_hieu_luc_di_vao_corpus_va_BLLD_co_3_canh():
    """Số cạnh là hàm của (parquet × corpus), KHÔNG phải hằng số.

    Bản đầu ghim `n == 46` và `{20: 23, 21: 5, 22: 13, 23: 5}` — đo trên corpus
    21 văn bản ngày 2026-08-30. Mở corpus lên 32 văn bản làm nó thành 55, và
    "sửa" bằng cách bump con số thì test không còn kiểm gì: nó chỉ chép lại kết
    quả của lần chạy gần nhất. Kỳ vọng vì thế tính LẠI từ chính hàm THUẦN
    `_canh_hieu_luc_di_vao` trên parquet thật + corpus thật, và phép kiểm là
    "loader ghi vào DB đúng bằng cái hàm thuần nói" — bất biến đó đúng ở mọi cỡ
    corpus.

    `BLLĐ có 3 cạnh` thì GIỮ nguyên số: nó neo vào một văn bản cố định và một
    file parquet cố định, không phụ thuộc corpus lớn bao nhiêu.
    """
    run_migrations()
    with get_engine().connect() as c:
        corpus = {r[0] for r in c.execute(text("SELECT id FROM documents WHERE depth <> 'metadata'"))}
    rel = pd.read_parquet(RAW / "relationships.parquet")
    mong_doi = _canh_hieu_luc_di_vao(rel, corpus)

    n = load_from_parquet(RAW / "relationships.parquet", get_engine())
    assert n == len(mong_doi), f"loader ghi {n} cạnh, hàm thuần nói {len(mong_doi)}"
    with get_engine().connect() as c:
        theo_loai = dict(c.execute(text(
            'SELECT loai, count(*) FROM "references" WHERE loai IN (20,21,22,23) GROUP BY loai'
        )).all())
        blld = c.execute(text(
            "SELECT count(*) FROM \"references\" WHERE to_document_id = '139264'"
            " AND loai IN (20,21,22,23)")).scalar_one()
    assert theo_loai == dict(mong_doi["loai"].value_counts()), theo_loai
    assert blld == 3, f"BLLĐ (139264) phải có 3 cạnh hiệu lực đi vào, được {blld}"


@pytest.mark.integration
def test_nd_90_2019_KHONG_co_canh_hieu_luc_di_vao_trong_du_lieu_hien_tai():
    """Brief gốc giả định NĐ 90/2019 (139094) có cạnh đi vào loại Thay thế/Bãi bỏ
    để bắt ca MOJ đánh sai 'còn hiệu lực' (ca then chốt của Mức 2) — ĐÃ ĐO LẠI,
    giả định đó SAI với dữ liệu hiện có: cả 14 cạnh đi vào 139094 trong
    `relationships.parquet` đều là 'Căn cứ' (bị loại theo Ruling 4), không cạnh
    nào thuộc 4 loại hiệu lực. Test này GHIM sự thật đo được thay vì giả định
    chưa kiểm của brief: T1 KHÔNG có tín hiệu đồ thị cho riêng ca 139094 từ
    nguồn này — Task 2 cần biết điều này TRƯỚC khi thiết kế guard Mức 2, không
    phải sau khi guard im lặng bỏ sót nó."""
    run_migrations()
    load_from_parquet(RAW / "relationships.parquet", get_engine())
    with get_engine().connect() as c:
        n = c.execute(text(
            "SELECT count(*) FROM \"references\" WHERE to_document_id = '139094'"
            " AND loai IN (20,21,22,23)")).scalar_one()
    assert n == 0, (
        "139094 giờ CÓ cạnh hiệu lực đi vào — dữ liệu nguồn đã đổi; cập nhật lại "
        "assumption của Task 2 và xoá dòng ghi chú này")


@pytest.mark.integration
def test_khong_tu_tro_vao_chinh_no():
    run_migrations()
    load_from_parquet(RAW / "relationships.parquet", get_engine())
    with get_engine().connect() as c:
        n = c.execute(text(
            'SELECT count(*) FROM "references" WHERE from_document_id = to_document_id'
            " AND loai IN (20,21,22,23)")).scalar_one()
    assert n == 0, "văn bản tự thay thế/sửa đổi chính nó — dữ liệu cạnh sai"


@pytest.mark.integration
def test_van_ban_ngoai_corpus_duoc_chen_metadata_va_van_ban_that_khong_bi_dung():
    """FK `references_from_document_fk` bắt `from_document_id` phải có trong
    `documents`, mà cạnh đi vào xuất phát từ văn bản NGOÀI corpus — chèn trước
    36 dòng chỉ-metadata (Ruling 2) là cách gỡ. Văn bản THẬT của corpus (đã
    ingest đầy đủ provisions) không được đụng tới, kể cả khi nó cũng xuất hiện
    làm `from_document_id` của một cạnh (BLLĐ sửa BLDS, vẫn trong corpus)."""
    run_migrations()
    load_from_parquet(RAW / "relationships.parquet", get_engine())
    with get_engine().connect() as c:
        n_metadata = c.execute(text(
            "SELECT count(*) FROM documents WHERE checksum = 'metadata-only'")).scalar_one()
        sai_dau = c.execute(text(
            "SELECT count(*) FROM documents WHERE checksum = 'metadata-only'"
            " AND (depth != 'metadata' OR tinh_trang != 'chua_xac_dinh')")).scalar_one()
        that = c.execute(text(
            "SELECT depth, checksum FROM documents WHERE id = '139264'")).one()
    # Số dòng chỉ-metadata = số `from_document_id` KHÔNG thuộc corpus, tính lại
    # từ chính cạnh vừa nạp. Ghim 36 là ghim cỡ corpus ngày 2026-08-30: mở corpus
    # ra 32 văn bản làm nó thành 44, và bump con số thì test chỉ còn chép lại kết
    # quả lần chạy gần nhất.
    with get_engine().connect() as c:
        ngoai = c.execute(text(
            'SELECT count(DISTINCT r.from_document_id) FROM "references" r'
            " WHERE r.loai IN (20,21,22,23)"
            "   AND NOT EXISTS (SELECT 1 FROM documents d"
            "                   WHERE d.id = r.from_document_id AND d.depth <> 'metadata')"
        )).scalar_one()
    assert n_metadata == ngoai, \
        f"{ngoai} văn bản ngoài corpus đi sửa corpus, nhưng có {n_metadata} dòng chỉ-metadata"
    assert n_metadata > 0, "0 dòng chỉ-metadata — loader không chèn gì, phép kiểm rỗng"
    assert sai_dau == 0, "dòng chỉ-metadata phải có depth='metadata' và tinh_trang='chua_xac_dinh'"
    assert that.depth == "deep" and that.checksum != "metadata-only", (
        "BLLĐ (139264) là văn bản THẬT của corpus — không được ghi đè bằng dòng chỉ-metadata")


@pytest.mark.integration
def test_idempotent_chay_hai_lan_cung_so_dong():
    run_migrations()

    def dem() -> dict[str, int]:
        with get_engine().connect() as c:
            return {
                "documents_metadata": c.execute(text(
                    "SELECT count(*) FROM documents WHERE checksum = 'metadata-only'")).scalar_one(),
                "references_hieu_luc": c.execute(text(
                    'SELECT count(*) FROM "references" WHERE loai IN (20,21,22,23)')).scalar_one(),
            }

    load_from_parquet(RAW / "relationships.parquet", get_engine())
    truoc = dem()
    load_from_parquet(RAW / "relationships.parquet", get_engine())
    sau = dem()
    assert truoc == sau, f"load_from_parquet không idempotent: {truoc} != {sau}"
    assert all(n > 0 for n in truoc.values()), f"bảng rỗng sau lần nạp đầu: {truoc}"
