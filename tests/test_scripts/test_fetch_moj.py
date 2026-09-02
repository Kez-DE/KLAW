"""`_doi_chieu_tieu_de` — cổng chặn nạp sai văn bản khi số hiệu trùng giữa các
loại văn bản (T1, `.superpowers/sdd/tro-ly-8-linh-vuc/task-1-brief.md`: tra
`50/2005/QH11` theo số hiệu trả một Nghị quyết, không phải Luật Sở hữu trí
tuệ). Test thuần, không chạm network/DB.
"""

import pytest

from scripts.fetch_moj import TIEU_DE_DOI_CHIEU, _doi_chieu_tieu_de


def test_no_khi_tieu_de_khong_chua_manh_mong_doi():
    with pytest.raises(ValueError, match="16748"):
        _doi_chieu_tieu_de("16748", "Nghị quyết về một việc không liên quan")


def test_cho_qua_khi_tieu_de_chua_manh_mong_doi():
    _doi_chieu_tieu_de("16748", "Luật Sở hữu trí tuệ số 50/2005/QH11")  # không raise


def test_bo_qua_doc_id_ngoai_bang():
    _doi_chieu_tieu_de("999999", "bất kỳ tiêu đề nào")  # không có trong bảng → không kiểm


def test_no_khi_tieu_de_None():
    with pytest.raises(ValueError, match="27621"):
        _doi_chieu_tieu_de("27621", None)


def test_bang_du_11_id_va_khong_manh_nao_rong():
    """11/13: `169032` (Luật Nhà ở, giới hạn parser) và `175027` (Luật Bảo
    hiểm xã hội, lỗi chính tả nguồn "Điêu 38") bị `parse_anomalies` chặn ở
    tầng `build_seed` — không phải id sai — nên loại khỏi
    `DOC_IDS`/`TIEU_DE_DOI_CHIEU`. Xem `KHONG_NAP` ở `scripts/fetch_moj.py`."""
    assert len(TIEU_DE_DOI_CHIEU) == 11
    assert all(doc_id.isdigit() for doc_id in TIEU_DE_DOI_CHIEU)
    assert all(manh.strip() for manh in TIEU_DE_DOI_CHIEU.values())
