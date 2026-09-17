"""Migration 032 — `ban_thao.hoi_thoai_id` chuyển sang `ON DELETE CASCADE`
(spec 2026-09-17 Phase 6, D10), khớp cách `viec_doc_tai_lieu` đã khai từ 026.

Chưa từng có một xoá THẬT hàng `hoi_thoai` nào trong `src/` (mọi xoá đều mềm,
xem `hoi_thoai.xoa_mem`), nên ràng buộc này không đổi hành vi hôm nay — file
này chứng minh nó áp dụng SẠCH trên một DB đã có 024–031, và rằng nếu một xoá
thật từng xảy ra thì CASCADE đúng như khai báo, không phải `SET NULL` cũ.
"""

import pytest
from sqlalchemy import text

from src.services.db import get_engine, run_migrations

pytestmark = pytest.mark.integration


def test_032_ap_dung_sach_tren_db_da_co_024_den_031_va_idempotent():
    run_migrations()
    run_migrations()
    with get_engine().connect() as c:
        chk = c.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                " WHERE conname = 'ban_thao_hoi_thoai_id_fkey'"
            )
        ).scalar_one()
    assert "ON DELETE CASCADE" in chk
    assert "ON DELETE SET NULL" not in chk


def test_032_XOA_THAT_hoi_thoai_XOA_THEO_ban_thao():
    """Cùng phép thử `test_XOA_HOI_THOAI_XOA_THEO_du_kien` của migration 026,
    áp cho `ban_thao`: một xoá THẬT (không phải `xoa_mem`) phải kéo theo xoá
    THẬT bản thảo của nó, không để lại một hàng `hoi_thoai_id` mồ côi."""
    run_migrations()
    with get_engine().begin() as c:
        sub = c.execute(text("INSERT INTO users (sub) VALUES (gen_random_uuid()) RETURNING sub")).scalar_one()
        ht = c.execute(
            text("INSERT INTO hoi_thoai (user_sub, tieu_de) VALUES (:u, 'thử') RETURNING id"), {"u": sub}
        ).scalar_one()
        bt = c.execute(
            text(
                "INSERT INTO ban_thao (user_sub, hoi_thoai_id, loai, document)"
                " VALUES (:u, :h, 'don_xin_nghi_viec', 'x') RETURNING id"
            ),
            {"u": sub, "h": ht},
        ).scalar_one()
        c.execute(text("DELETE FROM hoi_thoai WHERE id = :h"), {"h": ht})
        con = c.execute(text("SELECT count(*) FROM ban_thao WHERE id = :b"), {"b": bt}).scalar_one()
        assert con == 0
        c.execute(text("ROLLBACK"))
