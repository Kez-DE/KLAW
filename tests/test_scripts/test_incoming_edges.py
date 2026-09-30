"""Test cho `scripts/load_incoming_edges.py` — nạp cạnh hiệu lực ĐI VÀO corpus.

Nguồn dữ liệu: `data/raw/relationships.parquet` + `metadata.parquet`, crawl bên
thứ ba (HuggingFace `th1nhng0/vietnamese-legal-documents`), vintage KHÔNG rõ —
xem cảnh báo đầu `scripts/load_incoming_edges.py`. Chỉ 4 quan hệ mang tín hiệu
hiệu lực được nạp (Ruling 4 của Kenz, đã đo lại ở đây): "Căn cứ" (1.053/1.233
cạnh đi vào 21 văn bản corpus) là căn cứ pháp lý, KHÔNG phải tín hiệu hiệu lực,
và không được đếm chung.
"""

import os
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from scripts.load_incoming_edges import (
    CANH_DOI_CHIEU_NGUYEN_VAN,
    CANH_SAI,
    CANH_SAI_MOJ,
    QUAN_HE_HIEU_LUC,
    _bo_sung,
    _canh_hieu_luc_di_vao,
    _canh_tu_vbhn,
    danh_sach_ap,
    load_from_parquet,
)
from src.services.db import get_engine, run_migrations
from src.services.effectivity import EffectivityVerdict, danh_gia
from src.services.hien_thi import VERDICT_HIEN

RAW = Path("data/raw")

# Test gọi `load_from_parquet` XOÁ RỒI CHÈN LẠI mọi cạnh loai 20..23 (kéo theo
# `canh_doi_chieu`) và chèn văn bản ngoài kho của DB đang cấu hình — tức DB dev DÙNG
# CHUNG. 2026-09-29 một lượt chạy từ nhánh chưa có K8 đã hoàn ngược toàn bộ cạnh đã
# sửa của K8 và thêm 60 văn bản ngoài kho. Chỉ chạy khi người chạy chủ động xác nhận
# DB là của riêng mình.
_GHI_DB = pytest.mark.skipif(
    os.environ.get("KLAW_TEST_GHI_DB") != "1",
    reason="ghi đè cạnh hiệu lực của DB dùng chung — chỉ chạy trên DB riêng, với KLAW_TEST_GHI_DB=1",
)


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


def test_ban_trung_tro_ve_dong_giu_va_canh_trung_gop_lai():
    """40022/153788 là bản trùng của 18451/142846 (`BAN_TRUNG`, K2 2026-09-28): nạp
    lại parquet không được chèn lại dòng thừa — cạnh của nó thuộc về dòng giữ, và
    cạnh trùng hệt sau khi trỏ thì chỉ còn một."""
    rel = pd.DataFrame([
        {"doc_id": "40022", "other_doc_id": "139264", "relationship": "Thay thế"},
        {"doc_id": "18451", "other_doc_id": "139264", "relationship": "Thay thế"},
        {"doc_id": "A", "other_doc_id": "153788", "relationship": "Thay thế"},
    ])
    out = _canh_hieu_luc_di_vao(rel, {"139264", "142846"})
    assert sorted(zip(out["from_document_id"], out["to_document_id"], strict=True)) == [
        ("18451", "139264"), ("A", "142846")]


def test_hai_canh_sua_doi_127_2025_bat_nham_bi_loai():
    """143/2025/QH15 Điều 50 khoản 2 sửa Luật Thuế TNDN 67/2025 "đã được sửa đổi, bổ
    sung ... theo Luật số ... 127/2025/QH15"; 231/2026/NĐ-CP chỉ "Căn cứ" 127/2025.
    Không văn bản nào sửa Luật Thi hành án hình sự 127/2025 (đọc toàn văn gateway
    2026-09-28) — cùng lỗi crawl với 19/2023 → BLLĐ."""
    rel = pd.DataFrame([
        {"doc_id": "187601", "other_doc_id": "187035", "relationship": "Sửa đổi, bổ sung"},
        {"doc_id": "386e5ad0-7d09-11f1-9c00-f9e84f25c1dc", "other_doc_id": "187035",
         "relationship": "Sửa đổi, bổ sung"},
    ])
    assert _canh_hieu_luc_di_vao(rel, {"187035"}).empty


def test_canh_hieu_luc_di_vao_LOAI_canh_da_doi_chieu_la_sai():
    """19/2023/QH15 "Sửa đổi, bổ sung" BLLĐ là lỗi của crawl nguồn (toàn văn chỉ
    sửa BLTTDS) — nạp lại parquet không được đưa nó trở lại. Cạnh thật của
    71/2025/QH15 vào BLLĐ phải còn."""
    rel = pd.DataFrame([
        {"doc_id": "161263", "other_doc_id": "139264", "relationship": "Sửa đổi, bổ sung"},
        {"doc_id": "179989", "other_doc_id": "139264", "relationship": "Sửa đổi, bổ sung"},
    ])
    out = _canh_hieu_luc_di_vao(rel, {"139264"})
    assert list(out["from_document_id"]) == ["179989"]


def test_bo_sung_them_canh_moi_va_khong_nhan_doi_canh_da_co():
    canh = pd.DataFrame([{"from_document_id": "179989", "to_document_id": "139264",
                          "loai": 20, "raw_text": "Sửa đổi, bổ sung"}])
    them = [("179989", "139264", 20, "Sửa đổi, bổ sung"),   # parquet đã có → bỏ
            ("187742", "139264", 20, "Sửa đổi, bổ sung"),
            ("187742", "139264", 20, "Sửa đổi, bổ sung")]   # trùng trong chính `them` → một
    out = _bo_sung(canh, them)
    assert sorted(zip(out["from_document_id"], out["loai"])) == [("179989", 20), ("187742", 20)]


def test_canh_doi_chieu_nguyen_van_dung_chieu_va_chi_dai_tu_suy():
    """Chuỗi lương tối thiểu 90/2019 → 38/2022 → 74/2024 đọc từ Điều 5 khoản 2 của
    38/2022 và 74/2024. `from` là văn bản ĐI THAY (hiệu lực sau), loai 21."""
    assert ("154245", "139094", 21, "Thay thế") in CANH_DOI_CHIEU_NGUYEN_VAN
    assert ("168670", "154245", 21, "Thay thế") in CANH_DOI_CHIEU_NGUYEN_VAN
    assert all(loai in QUAN_HE_HIEU_LUC.values() and QUAN_HE_HIEU_LUC[ten] == loai
               for _, _, loai, ten in CANH_DOI_CHIEU_NGUYEN_VAN)


def test_canh_K8_doi_chieu_nguyen_van_nap_lai_khong_dua_canh_sai_tro_lai():
    """K8 (nghiên cứu K8b): bốn cạnh parquet đọc sai nguyên văn không quay lại khi
    nạp lại; cạnh đúng thay chúng mang đúng chiều/loai; mã MOJ sai bị bỏ khỏi seed."""
    sai = [
        ("178757", "152734", "Thay thế"),
        ("179989", "177815", "Thay thế"),
        ("168381", "177815", "Thay thế"),
        ("30475", "37502", "Văn bản quy định hết hiệu lực"),
    ]
    rel = pd.DataFrame([{"doc_id": f, "other_doc_id": t, "relationship": r} for f, t, r in sai])
    assert _canh_hieu_luc_di_vao(rel, {"152734", "177815", "37502"}).empty
    assert {
        ("787d3780-866f-11f1-8511-612429c9d15e", "153913", 21, "Thay thế"),  # 283/2026 Điều 66 k4
        ("152734", "178757", 23, "Văn bản quy định hết hiệu lực 1 phần"),  # 158/2025 Điều 44 k2 c
        ("179989", "177815", 20, "Sửa đổi, bổ sung"),  # 71/2025 Điều 49 k5 a
        ("117553", "92898", 21, "Thay thế"),  # 153/2016 Điều 6 k1
        ("cb-468708", "15066", 21, "Thay thế"),  # 148/2025 Điều 47 k2 (Công báo)
    } <= set(CANH_DOI_CHIEU_NGUYEN_VAN)
    assert {("179989", "177815", 12), ("183939", "178260", 1), ("139094", "179273", 3)} <= CANH_SAI_MOJ


def test_canh_F1_nhom_nen_tang_chi_giu_canh_sua_doi_that():
    """F1: parquet gán văn bản HĐND/UBND tỉnh "sửa/thay" luật 87/2025 và 64/2025, và
    136/2025/QH15 (chỉ căn cứ) "sửa" Nghị quyết 203/2025. Nạp lại chỉ giữ hai cạnh
    đọc từ nguyên văn: 87/2025 Điều 1 → 64/2025, 203/2025 Điều 1 → Hiến pháp."""
    sai = [
        ("184262", "178717", "Sửa đổi, bổ sung"),
        ("183018", "178717", "Sửa đổi, bổ sung"),
        ("183300", "178717", "Thay thế"),
        ("552ed4e0-6087-11f1-b7fc-b958fe2dd742", "175440", "Sửa đổi, bổ sung"),
        ("187809", "178314", "Sửa đổi, bổ sung"),
    ]
    dung = [("178717", "175440", "Sửa đổi, bổ sung"), ("178314", "32801", "Sửa đổi, bổ sung")]
    rel = pd.DataFrame([{"doc_id": f, "other_doc_id": t, "relationship": r} for f, t, r in sai + dung])
    out = _canh_hieu_luc_di_vao(rel, {"178717", "175440", "178314", "32801"})
    assert sorted(zip(out["from_document_id"], out["to_document_id"])) == [("178314", "32801"), ("178717", "175440")]
    assert {("178717", "175440", 20, "Sửa đổi, bổ sung"), ("178314", "32801", 20, "Sửa đổi, bổ sung")} <= set(
        CANH_DOI_CHIEU_NGUYEN_VAN
    )


def test_101_102_2024_hien_va_151_2025_chi_bai_bo_mot_so_dieu():
    """N1 + quyết định 2026-09-30 mục 9: 151/2025/NĐ-CP Điều 21 khoản 4 điểm b, c cho một số
    điều khoản của 101/2024/NĐ-CP và 102/2024/NĐ-CP hết hiệu lực từ 01/7/2025 — không thay
    hai nghị định. Nạp lại không đưa cạnh parquet "thay thế" trở lại; cạnh đúng là loai 23
    (`from` bị khai tử), đã đối chiếu nguyên văn, nên hai nghị định được HIỆN với nhãn "còn
    hiệu lực một phần"; các điều bị bãi bỏ nằm ở `data/seed/bai_bo_dieu_khoan.yaml` và bị ẩn
    khỏi truy hồi, trích dẫn (`tests/test_scripts/test_nap_bai_bo_dieu_khoan.py`)."""
    sai = [("178259", "169188", "Thay thế"), ("178259", "169363", "Thay thế")]
    rel = pd.DataFrame([{"doc_id": f, "other_doc_id": t, "relationship": r} for f, t, r in sai])
    assert _canh_hieu_luc_di_vao(rel, {"169188", "169363", "178259"}).empty
    assert {
        ("169188", "178259", 23, "Văn bản quy định hết hiệu lực 1 phần"),
        ("169363", "178259", 23, "Văn bản quy định hết hiệu lực 1 phần"),
    } <= set(CANH_DOI_CHIEU_NGUYEN_VAN)
    ten = {
        "169188": "Nghị định số 101/2024/NĐ-CP Quy định về điều tra cơ bản đất đai; đăng ký, cấp Giấy chứng "
        "nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất và Hệ thống thông tin đất đai",
        "169363": "Nghị định số 102/2024/NĐ-CP Quy định chi tiết thi hành một số điều của Luật Đất đai",
    }
    canh = {
        "loai": 23,
        "chieu": "di_ra",
        "from_document_id": "178259",
        "from_so_ky_hieu": "151/2025/NĐ-CP",
        "from_loai_van_ban": "Nghị định",
        "from_ten": "Nghị định số 151/2025/NĐ-CP Quy định về phân định thẩm quyền của chính quyền địa phương 02 "
        "cấp, phân quyền, phân cấp trong lĩnh vực đất đai",
        "from_ngay_hieu_luc": date(2025, 7, 1),
        "da_doi_chieu": True,
    }
    for i, t in ten.items():
        doc = {"id": i, "loai_van_ban": "Nghị định", "ten": t, "ngay_hieu_luc": date(2024, 8, 1), "tinh_trang": "HHL1P"}
        e = danh_gia(doc, [canh], date(2026, 9, 30))
        assert e.verdict == EffectivityVerdict.mot_phan_khong_xac_dinh and e.verdict in VERDICT_HIEN, i


def test_danh_sach_ap_chi_xoa_canh_sai_va_them_canh_thieu():
    """Đường áp RIÊNG hai danh sách đã đối chiếu (không nạp lại parquet): xoá đúng cạnh
    khớp `CANH_SAI` (quy tên quan hệ về loai), thêm cạnh bổ sung còn thiếu (một lần dù
    trùng), không đụng cạnh parquet khác; chạy lại trên kết quả thì không còn gì làm."""
    canh_db = [
        (1, "178757", "152734", 21),  # CANH_SAI K8: 158/2025 "thay" 135/2020
        (2, "178757", "152734", 20),  # cùng cặp, khác loai: không phải cạnh sai
        (3, "11824", "13767", 21),  # cạnh parquet thường
        (4, "154245", "139094", 21),  # cạnh bổ sung đã có
    ]
    them = [
        ("154245", "139094", 21, "Thay thế"),
        ("152734", "178757", 23, "Văn bản quy định hết hiệu lực 1 phần"),
        ("152734", "178757", 23, "Văn bản quy định hết hiệu lực 1 phần"),
    ]
    xoa, moi = danh_sach_ap(canh_db, them)
    assert xoa == [1]
    assert moi == [("152734", "178757", 23, "Văn bản quy định hết hiệu lực 1 phần")]
    sau = [c for c in canh_db if c[0] not in xoa] + [(9, f, t, loai) for f, t, loai, _ in moi]
    assert danh_sach_ap(sau, them) == ([], [])


def test_canh_sai_va_canh_doi_chieu_khong_chung_khoa():
    """Một khoá vừa ở `CANH_SAI` vừa ở `CANH_DOI_CHIEU_NGUYEN_VAN` thì `danh_sach_ap`
    xoá rồi thêm lại nó mỗi lượt — hai danh sách phải rời nhau."""
    sai = {(f, t, QUAN_HE_HIEU_LUC[r]) for f, t, r in CANH_SAI}
    assert not sai & {c[:3] for c in CANH_DOI_CHIEU_NGUYEN_VAN}


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
@_GHI_DB
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

    with get_engine().connect() as c:
        mong_doi = _bo_sung(mong_doi, [*CANH_DOI_CHIEU_NGUYEN_VAN, *_canh_tu_vbhn(c)])

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
    # 3 của parquet − 19/2023 (cạnh sai) + 124/2025 và 113/2025 (18/VBHN-VPQH).
    assert blld == 4, f"BLLĐ (139264) phải có 4 cạnh hiệu lực đi vào, được {blld}"


@pytest.mark.integration
def test_canh_tu_vbhn_BLLD_du_ba_luat_sua_doi():
    """Chỉ ĐỌC: 18/VBHN-VPQH nêu ba luật sửa BLLĐ — 124/2025, 113/2025, 71/2025 —
    qua bảng `sua_doi_dieu_khoan`; không có 19/2023."""
    with get_engine().connect() as c:
        tu = {f for f, t, loai, _ in _canh_tu_vbhn(c) if t == "139264" and loai == 20}
    assert tu == {"187742", "6fa2fd20-597e-11f1-add2-7717d93a2118", "179989"}, tu


@pytest.mark.integration
@_GHI_DB
def test_nd_90_2019_chi_co_canh_thay_the_doc_tu_nguyen_van_38_2022():
    """`relationships.parquet` KHÔNG có cạnh hiệu lực nào đi vào NĐ 90/2019
    (139094): cả 14 cạnh là 'Căn cứ' (đo ở T1). Từ K1 (2026-09-28) cạnh duy nhất
    là 38/2022/NĐ-CP → 90/2019 loai 21, đọc từ Điều 5 khoản 2 của 38/2022
    (`CANH_DOI_CHIEU_NGUYEN_VAN`) — nếu parquet tự có thêm cạnh thì dữ liệu nguồn
    đã đổi, đo lại trước khi sửa con số."""
    run_migrations()
    load_from_parquet(RAW / "relationships.parquet", get_engine())
    with get_engine().connect() as c:
        canh = c.execute(text(
            "SELECT from_document_id, loai FROM \"references\" WHERE to_document_id = '139094'"
            " AND loai IN (20,21,22,23)")).all()
    assert [tuple(r) for r in canh] == [("154245", 21)], canh


@pytest.mark.integration
@_GHI_DB
def test_khong_tu_tro_vao_chinh_no():
    run_migrations()
    load_from_parquet(RAW / "relationships.parquet", get_engine())
    with get_engine().connect() as c:
        n = c.execute(text(
            'SELECT count(*) FROM "references" WHERE from_document_id = to_document_id'
            " AND loai IN (20,21,22,23)")).scalar_one()
    assert n == 0, "văn bản tự thay thế/sửa đổi chính nó — dữ liệu cạnh sai"


@pytest.mark.integration
@_GHI_DB
def test_van_ban_ngoai_corpus_duoc_chen_metadata_va_van_ban_that_khong_bi_dung():
    """FK `references_from_document_fk` bắt `from_document_id` phải có trong
    `documents`, mà cạnh đi vào xuất phát từ văn bản NGOÀI corpus — chèn trước
    dòng chỉ-metadata (Ruling 2) là cách gỡ. Văn bản THẬT của corpus (đã
    ingest đầy đủ provisions) không được đụng tới, kể cả khi nó cũng xuất hiện
    làm `from_document_id` của một cạnh (BLLĐ sửa BLDS, vẫn trong corpus).

    Sửa 2026-09-02: bản trước ghim `n_metadata == ngoai` (đếm TẤT CẢ dòng
    `checksum='metadata-only'` trong `documents`, so với số văn bản ngoài
    corpus của LẦN NẠP HIỆN TẠI). DB sống, không dọn giữa các lần chạy, và
    `INSERT ... ON CONFLICT DO NOTHING` không bao giờ xoá — mỗi lần corpus mở
    rộng (21 → 32 → 53 văn bản deep → +87 shallow), một số văn bản từng "ngoài
    corpus" nay đã ở TRONG corpus (dưới định nghĩa mới), nhưng dòng chỉ-metadata
    được chèn TỪ LẦN CHẠY CŨ vẫn còn nằm lại — rác lịch sử không liên quan gì
    tới lần nạp hôm nay. Đếm-bằng-đếm vì thế ghim cỡ corpus tại thời điểm chạy,
    đúng lỗi mà comment cũ ở đây đã cảnh báo (ghim 36).
    Bất biến thật không cần đếm KHỚP — nó cần MỖI văn bản ngoài corpus của lần
    nạp hôm nay có một dòng chỉ-metadata đứng chỗ cho nó (bao phủ), không cần
    dòng chỉ-metadata nào khác trong bảng phải biến mất.

    `sai_dau` cũng sửa cùng đợt: bản trước đòi MỌI dòng `checksum='metadata-only'`
    giữ nguyên `depth='metadata'` mãi mãi — đúng lúc `016_tang_nong.sql` (tầng
    `shallow`, cho văn bản chỉ-metadata đủ dài tên một hàng `mo_dau` để tìm
    được bằng tên) CHƯA áp cho bất kỳ dòng nào. Nó là một tính năng CÓ CHỦ Ý,
    không phải suy thoái: `016` chỉ đổi `depth` (`'metadata'` → `'shallow'`),
    KHÔNG bao giờ đổi `tinh_trang`. Bất biến còn đứng được là "chưa từng thành
    `deep`" (đổi thành `deep` nghĩa là bị ghi đè bởi một văn bản thật — đúng
    thứ Ruling 2 cấm) và "tinh_trang không đổi", không phải "depth không đổi".
    """
    run_migrations()
    load_from_parquet(RAW / "relationships.parquet", get_engine())
    with get_engine().connect() as c:
        sai_dau = c.execute(text(
            "SELECT count(*) FROM documents WHERE checksum = 'metadata-only'"
            " AND (depth = 'deep' OR tinh_trang != 'chua_xac_dinh')")).scalar_one()
        that = c.execute(text(
            "SELECT depth, checksum FROM documents WHERE id = '139264'")).one()
        co_metadata = {r[0] for r in c.execute(text(
            "SELECT id FROM documents WHERE checksum = 'metadata-only'")).all()}
        ngoai_ids = {r[0] for r in c.execute(text(
            'SELECT DISTINCT r.from_document_id FROM "references" r'
            " WHERE r.loai IN (20,21,22,23)"
            "   AND NOT EXISTS (SELECT 1 FROM documents d"
            "                   WHERE d.id = r.from_document_id AND d.depth <> 'metadata')"
        )).all()}
    assert ngoai_ids, "0 văn bản ngoài corpus đi sửa corpus — phép kiểm rỗng"
    assert ngoai_ids <= co_metadata, (
        f"{ngoai_ids - co_metadata} văn bản ngoài corpus đi sửa corpus nhưng KHÔNG có "
        "dòng chỉ-metadata đứng chỗ")
    assert sai_dau == 0, (
        "dòng chỉ-metadata không được thành depth='deep' (bị ghi đè) hay đổi "
        "tinh_trang khỏi 'chua_xac_dinh'")
    assert that.depth == "deep" and that.checksum != "metadata-only", (
        "BLLĐ (139264) là văn bản THẬT của corpus — không được ghi đè bằng dòng chỉ-metadata")


@pytest.mark.integration
@_GHI_DB
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
