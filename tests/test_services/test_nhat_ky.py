"""`nhat_ky` (spec 2B §5.2): ghi thêm, lọc, CSV — và bất biến KHÔNG sửa/xoá trong src/."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from src.services import nhat_ky
from src.services.db import get_engine

BOI = "test-nhat-ky@klaw.local"


@pytest.fixture
def don():
    yield
    with get_engine().begin() as c:
        # Test là nơi DUY NHẤT được xoá — src/ thì không (test grep bên dưới).
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI})


@pytest.mark.integration
def test_ghi_tra_id_va_doc_lai_duoc(don):
    i = nhat_ky.ghi("thu_nghiem", doi_tuong=None, chi_tiet={"a": 1}, boi=BOI, ip="10.0.0.1")
    tong, rows = nhat_ky.danh_sach(tu=None, den=None, hanh_dong="thu_nghiem", doi_tuong=None, limit=10, offset=0)
    assert tong >= 1 and rows[0]["id"] == i and rows[0]["chi_tiet"] == {"a": 1} and rows[0]["ip"] == "10.0.0.1"


@pytest.mark.integration
def test_loc_theo_khoang_thoi_gian_va_doi_tuong(don):
    sub = str(uuid.uuid4())
    nhat_ky.ghi("thu_nghiem", doi_tuong=sub, chi_tiet={}, boi=BOI)
    tu = datetime.now(UTC) - timedelta(minutes=1)
    tong, rows = nhat_ky.danh_sach(tu=tu, den=None, hanh_dong=None, doi_tuong=sub, limit=10, offset=0)
    assert tong == 1 and rows[0]["doi_tuong"] == sub
    tong0, _ = nhat_ky.danh_sach(tu=None, den=tu, hanh_dong=None, doi_tuong=sub, limit=10, offset=0)
    assert tong0 == 0


@pytest.mark.integration
def test_ghi_trong_transaction_ngoai(don):
    with get_engine().begin() as c:
        nhat_ky.ghi("thu_nghiem", doi_tuong=None, chi_tiet={}, boi=BOI, c=c)
        assert c.execute(text("SELECT count(*) FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI}).scalar_one() == 1


def test_csv_dung_so_dong_va_tieu_de():
    rows = [
        {
            "id": 1,
            "tao_luc": datetime(2026, 9, 8, tzinfo=UTC),
            "hanh_dong": "x",
            "doi_tuong": None,
            "boi": "a",
            "tac_nhan_loai": "admin",
            "ip": None,
            "chi_tiet": {"k": "v, có dấu phẩy"},
        },
    ]
    dong = nhat_ky.csv(rows).strip().splitlines()
    assert dong[0] == "id,tao_luc,hanh_dong,doi_tuong,boi,tac_nhan_loai,ip,chi_tiet"
    assert len(dong) == 2 and '"' in dong[1], "JSON có dấu phẩy phải được bao ngoặc kép"


def test_src_khong_co_UPDATE_hay_DELETE_tren_nhat_ky_quan_tri():
    """Bất biến §5.1: bảng chỉ ghi thêm. Kiểm bằng grep, không bằng mắt."""
    mau = re.compile(r"(UPDATE\s+nhat_ky_quan_tri|DELETE\s+FROM\s+nhat_ky_quan_tri)", re.IGNORECASE)
    # Chứng minh mẫu regex CÒN bắt được vi phạm — một lỗi gõ ở mẫu không còn
    # được phép lọt qua âm thầm.
    assert mau.search("DELETE FROM nhat_ky_quan_tri WHERE id = 1"), (
        "mẫu regex bất biến §5.1 không khớp câu vi phạm tổng hợp"
    )
    vi_pham = [str(p) for p in Path("src").rglob("*.py") if mau.search(p.read_text(encoding="utf-8"))]
    assert vi_pham == [], (
        "bất biến §5.1 nhat_ky_quan_tri chỉ ghi thêm"
        " (docs/superpowers/specs/2026-09-08-cms-quan-ly-tai-khoan-design.md) bị vi phạm ở: " + str(vi_pham)
    )
