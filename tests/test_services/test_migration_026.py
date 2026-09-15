"""Migration 026 — tài liệu người dùng và dữ kiện rút ra (spec 2026-09-15).

Hai bất biến của FR-007 và FR-015 được đẩy xuống Postgres chứ không chỉ nằm ở
Python. File này chứng minh CẢ HAI CHIỀU theo `docs/patterns/encoding-invariants.md`
§4: một ca hợp lệ đi qua, và một ca vi phạm BỊ CHẶN kèm đúng tên ràng buộc.

Một repo xanh mà chưa từng có ca vi phạm chạy qua không chứng minh được rằng
guard còn phát hiện được tái phạm.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.services.db import get_engine, run_migrations

pytestmark = pytest.mark.integration


def _cot(bang: str) -> set[str]:
    with get_engine().connect() as c:
        return {
            r[0]
            for r in c.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = :b"),
                {"b": bang},
            ).all()
        }


def test_026_chay_hai_lan_va_du_cot():
    run_migrations()
    run_migrations()
    assert {"id", "user_sub", "hoi_thoai_id", "ten_tep", "dau_van_ban", "so_byte",
            "so_trang", "loai", "trang_thai", "ly_do_hong", "chi_phi_usd",
            "so_lan_thu", "tao_luc", "cap_nhat_luc"} <= _cot("viec_doc_tai_lieu")
    assert {"id", "viec_id", "hoi_thoai_id", "khoa", "nhan", "gia_tri", "nguon",
            "trich", "trich_goc", "chi_so_don_vi", "trang", "offset_dau",
            "tao_luc", "xoa_luc"} <= _cot("du_kien_tai_lieu")


def _viec(c) -> tuple[str, str, str]:
    """Một user + hội thoại + việc đọc dùng một lần, trả (user_sub, hoi_thoai_id, viec_id)."""
    sub = c.execute(text("INSERT INTO users (sub) VALUES (gen_random_uuid()) RETURNING sub")).scalar_one()
    ht = c.execute(
        text("INSERT INTO hoi_thoai (user_sub, tieu_de) VALUES (:u, 'thử') RETURNING id"), {"u": sub}
    ).scalar_one()
    viec = c.execute(
        text(
            "INSERT INTO viec_doc_tai_lieu (user_sub, hoi_thoai_id, ten_tep, dau_van_ban, so_byte) "
            "VALUES (:u, :h, 'hd.docx', 'sha256:x len=1 clauses=0', 100) RETURNING id"
        ),
        {"u": sub, "h": ht},
    ).scalar_one()
    return str(sub), str(ht), str(viec)


def test_du_kien_tu_tai_lieu_CO_neo_thi_ghi_duoc():
    """Chiều thuận: một dữ kiện đúng luật đi qua."""
    with get_engine().begin() as c:
        _, ht, viec = _viec(c)
        c.execute(
            text(
                "INSERT INTO du_kien_tai_lieu (viec_id, hoi_thoai_id, khoa, gia_tri, nguon, trich, chi_so_don_vi, trang) "
                "VALUES (:v, :h, 'luong_thang', '20000000', 'tai_lieu', 'Mức lương: 20.000.000 đồng/tháng', 0, 1)"
            ),
            {"v": viec, "h": ht},
        )
        c.execute(text("ROLLBACK"))


@pytest.mark.parametrize(
    "trich, chi_so, trang",
    [(None, 0, 1), ("   ", 0, 1), ("Mức lương: 20.000.000 đồng/tháng", None, 1),
     ("Mức lương: 20.000.000 đồng/tháng", 0, None)],
)
def test_du_kien_tu_tai_lieu_THIEU_neo_BI_CHAN(trich, chi_so, trang):
    """Chiều nghịch: FR-007 không thể bị lách bằng một INSERT thẳng vào DB."""
    with pytest.raises(IntegrityError) as e:
        with get_engine().begin() as c:
            _, ht, viec = _viec(c)
            c.execute(
                text(
                    "INSERT INTO du_kien_tai_lieu (viec_id, hoi_thoai_id, khoa, gia_tri, nguon, trich, chi_so_don_vi, trang) "
                    "VALUES (:v, :h, 'luong_thang', '20000000', 'tai_lieu', :t, :c, :p)"
                ),
                {"v": viec, "h": ht, "t": trich, "c": chi_so, "p": trang},
            )
    assert "ck_du_kien_tai_lieu_co_neo" in str(e.value)


def test_du_kien_da_sua_THIEU_trich_goc_BI_CHAN():
    """FR-015: sửa mà không giữ trích gốc là mất đường đối chiếu."""
    with pytest.raises(IntegrityError) as e:
        with get_engine().begin() as c:
            _, ht, viec = _viec(c)
            c.execute(
                text(
                    "INSERT INTO du_kien_tai_lieu (viec_id, hoi_thoai_id, khoa, gia_tri, nguon) "
                    "VALUES (:v, :h, 'luong_thang', '25000000', 'nguoi_dung_sua')"
                ),
                {"v": viec, "h": ht},
            )
    assert "ck_du_kien_sua_giu_trich_goc" in str(e.value)


def test_viec_HONG_khong_co_ly_do_BI_CHAN():
    with pytest.raises(IntegrityError) as e:
        with get_engine().begin() as c:
            sub = c.execute(text("INSERT INTO users (sub) VALUES (gen_random_uuid()) RETURNING sub")).scalar_one()
            ht = c.execute(text("INSERT INTO hoi_thoai (user_sub, tieu_de) VALUES (:u, 'thử') RETURNING id"), {"u": sub}).scalar_one()
            c.execute(
                text(
                    "INSERT INTO viec_doc_tai_lieu (user_sub, hoi_thoai_id, ten_tep, dau_van_ban, so_byte, trang_thai) "
                    "VALUES (:u, :h, 'hd.docx', 'x', 1, 'hong')"
                ),
                {"u": sub, "h": ht},
            )
    assert "ck_viec_doc_hong_co_ly_do" in str(e.value)


def test_XOA_HOI_THOAI_XOA_THEO_du_kien():
    """FR-027 ở tầng dữ liệu, không phụ thuộc kỷ luật của người gọi."""
    with get_engine().begin() as c:
        _, ht, viec = _viec(c)
        c.execute(
            text(
                "INSERT INTO du_kien_tai_lieu (viec_id, hoi_thoai_id, khoa, gia_tri, nguon, trich, chi_so_don_vi, trang) "
                "VALUES (:v, :h, 'k', 'g', 'tai_lieu', 'Mức lương: 20.000.000 đồng/tháng', 0, 1)"
            ),
            {"v": viec, "h": ht},
        )
        c.execute(text("DELETE FROM hoi_thoai WHERE id = :h"), {"h": ht})
        con = c.execute(
            text("SELECT count(*) FROM du_kien_tai_lieu WHERE hoi_thoai_id = :h"), {"h": ht}
        ).scalar_one()
        assert con == 0
        c.execute(text("ROLLBACK"))
