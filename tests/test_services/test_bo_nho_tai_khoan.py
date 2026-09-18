"""Phase 12 (R1) — `bo_nho_tai_khoan`: migration 034 và dịch vụ ghi/liệt kê/xoá.

Mọi giá trị trong file là giả rõ ràng (không tên thật, không mã sinh viên thật).
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.services import bao_ve, hoi_thoai
from src.services import bo_nho_tai_khoan as bn
from src.services.db import get_engine, run_migrations


def _dem(sub: str) -> int:
    with get_engine().connect() as c:
        return c.execute(
            text("SELECT count(*) FROM bo_nho_tai_khoan WHERE user_sub = CAST(:s AS uuid)"), {"s": sub}
        ).scalar_one()


@pytest.fixture
def hai_nguoi():
    # Bảng chỉ được tạo lúc app khởi động (`MIGRATIONS_KHOI_DONG`); test tự áp
    # migration để không lệ thuộc thứ tự file hay một lần restart uvicorn.
    run_migrations("034")
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    yield a, b
    with get_engine().begin() as c:
        for s in (a, b):
            # `users` cascade sang `bo_nho_tai_khoan` và `hoi_thoai` (034, 020).
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": s})


@pytest.mark.integration
def test_034_chay_hai_lan_tren_db_da_co_024_den_033_va_du_cot():
    run_migrations()
    run_migrations()
    with get_engine().connect() as c:
        cot = {
            r[0]
            for r in c.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'bo_nho_tai_khoan'")
            ).all()
        }
        # Không FK nào tới `hoi_thoai`: ký ức KHÔNG được chết theo hội thoại (D10).
        fk_hoi_thoai = c.execute(
            text(
                "SELECT count(*) FROM information_schema.table_constraints tc"
                " JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name"
                " WHERE tc.table_name = 'bo_nho_tai_khoan' AND tc.constraint_type = 'FOREIGN KEY'"
                " AND ccu.table_name = 'hoi_thoai'"
            )
        ).scalar_one()
    assert cot == {"id", "user_sub", "loai", "khoa", "gia_tri", "nguon_hoi_thoai_id", "tao_luc", "cap_nhat_luc"}
    assert fk_hoi_thoai == 0


@pytest.mark.integration
def test_db_tu_choi_loai_ngoai_hai_gia_tri(hai_nguoi):
    a, _ = hai_nguoi
    # `ghi` đã chặn `loai` lạ bằng `ValueError`, nhưng lưới đó nằm trong Python:
    # một script, một migration sau hay một lượt sửa tay đi thẳng SQL sẽ đi vòng
    # qua nó. CHECK của 034 là hàng rào CUỐI, nên phải có test ghi thẳng bằng SQL
    # mới chứng minh được nó thật sự đang gác.
    with pytest.raises(IntegrityError):
        with get_engine().begin() as c:
            c.execute(
                text(
                    "INSERT INTO bo_nho_tai_khoan (user_sub, loai, khoa, gia_tri)"
                    " VALUES (CAST(:s AS uuid), 'transcript', 'ho_ten', 'x')"
                ),
                {"s": a},
            )
    assert _dem(a) == 0


@pytest.mark.integration
def test_upsert_giu_mot_dong_gia_tri_moi_nhat_va_bao_dung_trang_thai(hai_nguoi):
    a, _ = hai_nguoi
    assert bn.ghi(a, "ca_nhan", "ho_ten", "Nguyễn Văn Thử") == "moi"
    assert bn.ghi(a, "ca_nhan", "ho_ten", "Nguyễn  Văn Thử ") == "giu"  # khoảng trắng chuẩn hoá — không phải đổi
    assert bn.ghi(a, "ca_nhan", "ho_ten", "Trần Thị Mẫu") == "doi"
    ds = bn.liet_ke(a)
    assert len(ds) == 1 and _dem(a) == 1
    assert ds[0]["gia_tri"] == "Trần Thị Mẫu" and ds[0]["nhan"] == "Họ và tên" and ds[0]["loai"] == "ca_nhan"


@pytest.mark.integration
def test_liet_ke_khong_phan_biet_hoi_thoai_nguon_va_song_sot_khi_xoa_hoi_thoai(hai_nguoi):
    a, _ = hai_nguoi
    ht1, ht2 = hoi_thoai.tao_phien(a, "c1"), hoi_thoai.tao_phien(a, "c2")
    bn.ghi(a, "ca_nhan", "ma_sv", "00000000", ht1)
    bn.ghi(a, "thoi_quen", "xung_ho", "em/thầy", ht2)
    khoa = {(m["khoa"], m["nguon_hoi_thoai_id"]) for m in bn.liet_ke(a)}
    assert khoa == {("ma_sv", ht1), ("xung_ho", ht2)}
    # Xoá THẬT hội thoại nguồn: ký ức phải còn nguyên (không FK cascade — D10 không áp lên bảng này).
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM hoi_thoai WHERE id = CAST(:h AS uuid)"), {"h": ht1})
    assert _dem(a) == 2


@pytest.mark.integration
def test_tai_khoan_a_khong_doc_khong_xoa_duoc_cua_b(hai_nguoi):
    a, b = hai_nguoi
    bn.ghi(b, "ca_nhan", "noi_thuc_tap", "Công ty Mẫu Thử")
    id_b = bn.liet_ke(b)[0]["id"]
    assert bn.liet_ke(a) == []
    assert bn.xoa_mot(a, id_b) is False
    assert bn.xoa_het(a) == 0
    assert _dem(b) == 1


@pytest.mark.integration
def test_xoa_la_xoa_that(hai_nguoi):
    a, _ = hai_nguoi
    bn.ghi(a, "ca_nhan", "lop", "K00-Thử")
    bn.ghi(a, "thoi_quen", "van_phong", "trang trọng")
    id_lop = next(m["id"] for m in bn.liet_ke(a) if m["khoa"] == "lop")
    assert bn.xoa_mot(a, id_lop) is True
    with get_engine().connect() as c:
        assert c.execute(text("SELECT count(*) FROM bo_nho_tai_khoan WHERE id = CAST(:i AS uuid)"), {"i": id_lop}).scalar_one() == 0
    assert bn.xoa_het(a) == 1 and _dem(a) == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    "loai, khoa, gia_tri",
    [("khac", "ho_ten", "x"), ("ca_nhan", "Họ tên", "x"), ("ca_nhan", "ho_ten", "   "), ("ca_nhan", "ho_ten", "a" * 201)],
)
def test_ghi_tu_choi_dau_vao_sai(hai_nguoi, loai, khoa, gia_tri):
    a, _ = hai_nguoi
    with pytest.raises(ValueError):
        bn.ghi(a, loai, khoa, gia_tri)
    assert _dem(a) == 0
