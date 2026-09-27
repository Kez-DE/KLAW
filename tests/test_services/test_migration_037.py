"""Migration 037 — `ban_thao.viec_id` + `ban_thao.phep_sua` (quyết định
2026-09-26, `docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`).

Chứng minh migration áp dụng SẠCH và IDEMPOTENT (lifespan chạy lại cả danh sách
ở mỗi lần khởi động), đúng hai cột nullable của hợp đồng Storage, và khoá ngoại
`ON DELETE SET NULL`: xoá việc đọc không xoá bản thảo, chỉ cắt nó khỏi khuôn gốc.
"""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, hoi_thoai
from src.services import tai_lieu as tl
from src.services.db import get_engine, run_migrations

pytestmark = pytest.mark.integration


def test_037_ap_dung_sach_va_idempotent_dung_cot_va_khoa_ngoai():
    run_migrations()
    run_migrations()
    with get_engine().connect() as c:
        cot = {
            r["column_name"]: (r["data_type"], r["is_nullable"])
            for r in c.execute(
                text(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns"
                    " WHERE table_name = 'ban_thao' AND column_name IN ('viec_id', 'phep_sua')"
                )
            ).mappings()
        }
        fk = (
            c.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                    " WHERE conrelid = 'ban_thao'::regclass AND contype = 'f'"
                    " AND conname = 'ban_thao_viec_id_fkey'"
                )
            )
            .scalars()
            .all()
        )
    assert cot == {"viec_id": ("uuid", "YES"), "phep_sua": ("jsonb", "YES")}
    assert len(fk) == 1, "chạy lại migration không được nhân khoá ngoại"
    assert "REFERENCES viec_doc_tai_lieu(id) ON DELETE SET NULL" in fk[0]


def test_037_XOA_viec_doc_dat_viec_id_NULL_giu_ban_thao():
    run_migrations()
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    try:
        ht = hoi_thoai.tao_phien(sub, "khuôn gốc")
        viec = tl.tao_viec(get_engine(), user_sub=sub, hoi_thoai_id=ht, ten_tep="a.docx", du_lieu=b"x", loai=None)
        with get_engine().begin() as c:
            bt = c.execute(
                text(
                    "INSERT INTO ban_thao (user_sub, hoi_thoai_id, loai, document, viec_id, phep_sua)"
                    " VALUES (CAST(:u AS uuid), CAST(:h AS uuid), 'tong_quat', 'x', CAST(:v AS uuid),"
                    " CAST('[]' AS jsonb)) RETURNING id"
                ),
                {"u": sub, "h": ht, "v": viec},
            ).scalar_one()
            c.execute(text("DELETE FROM viec_doc_tai_lieu WHERE id = CAST(:v AS uuid)"), {"v": viec})
            con = c.execute(text("SELECT viec_id, phep_sua FROM ban_thao WHERE id = :b"), {"b": bt}).one()
        assert (con[0], con[1]) == (None, [])
    finally:
        with get_engine().begin() as c:
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})
