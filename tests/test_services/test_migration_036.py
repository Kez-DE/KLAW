"""Migration 036 — bảng `khuon_goc` (quyết định 2026-09-26,
`docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`).

Chứng minh migration áp dụng SẠCH và IDEMPOTENT (lifespan chạy lại cả danh sách
ở mỗi lần khởi động), đúng các cột của hợp đồng Storage, khoá ngoại cascade, và
ràng buộc DB tự chặn một khuôn gốc sai hình dạng — không tin kỷ luật người gọi.
"""

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.services import bao_ve, hoi_thoai
from src.services import tai_lieu as tl
from src.services.db import get_engine, run_migrations

pytestmark = pytest.mark.integration


def test_036_ap_dung_sach_va_idempotent_dung_cot_hop_dong():
    run_migrations()
    run_migrations()
    with get_engine().connect() as c:
        cot = {
            r["column_name"]: (r["data_type"], r["is_nullable"])
            for r in c.execute(
                text(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns"
                    " WHERE table_name = 'khuon_goc'"
                )
            ).mappings()
        }
        xoa = c.execute(
            text(
                "SELECT rc.delete_rule FROM information_schema.referential_constraints rc"
                " JOIN information_schema.table_constraints tc ON tc.constraint_name = rc.constraint_name"
                " WHERE tc.table_name = 'khuon_goc'"
            )
        ).scalar_one()
    assert cot == {
        "viec_id": ("uuid", "NO"),
        "dinh_dang": ("text", "NO"),
        "noi_dung": ("bytea", "NO"),
        "so_byte": ("integer", "NO"),
        "so_trang": ("integer", "NO"),
        "kho": ("jsonb", "NO"),
        "tao_luc": ("timestamp with time zone", "NO"),
    }
    assert xoa == "CASCADE"


@pytest.fixture
def viec():
    run_migrations("036")
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    phien = hoi_thoai.tao_phien(sub, "khuôn gốc")
    id_ = tl.tao_viec(get_engine(), user_sub=sub, hoi_thoai_id=phien, ten_tep="a.pdf", du_lieu=b"x", loai=None)
    yield id_
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _chen(viec_id: str, *, dinh_dang="pdf", noi_dung=b"%PDF", so_byte=None, so_trang=1, kho=None):
    with get_engine().begin() as c:
        c.execute(
            text(
                "INSERT INTO khuon_goc (viec_id, dinh_dang, noi_dung, so_byte, so_trang, kho)"
                " VALUES (:v, :d, :n, :s, :t, CAST(:k AS jsonb))"
            ),
            {
                "v": viec_id, "d": dinh_dang, "n": noi_dung,
                "s": len(noi_dung) if so_byte is None else so_byte,
                "t": so_trang, "k": json.dumps(kho if kho is not None else [[595, 842]] * so_trang),
            },
        )


def test_dong_hop_le_vao_duoc(viec):
    _chen(viec)


@pytest.mark.parametrize(
    "sai",
    [
        {"dinh_dang": "doc"},
        {"so_byte": 999},
        {"so_trang": 0, "kho": []},
        {"so_trang": 11},
        {"so_trang": 2, "kho": [[595, 842]]},
    ],
    ids=["dinh_dang_la", "so_byte_khai_lech", "0_trang", "11_trang", "kho_lech_so_trang"],
)
def test_DB_tu_chan_khuon_goc_sai_hinh_dang(viec, sai):
    with pytest.raises(IntegrityError):
        _chen(viec, **sai)
