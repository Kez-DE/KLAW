"""`scripts/don_kho._gop` — gộp một bản ghi trùng của gateway vào dòng giữ (quyết
định 2026-09-28 mục 17): số hiệu so bằng `build_seed.khoa_so_hieu` (chữ Kirin đồng
hình, khoảng trắng), cạnh của dòng thừa về dòng giữ, dẫn chiếu nội bộ và bằng chứng
đối chiếu của dòng giữ không mất, dòng xoá được chép ra CSV trước.

Bảng TẠM (`pg_temp`) trên MỘT kết nối, id ghi tay (không `nextval` nào của DB dùng
chung); `canh_doi_chieu` tạm có FK CASCADE như migration 039 để phép chặn mất bằng
chứng thật sự bị thử.
"""

import csv

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from scripts.don_kho import _gop
from src.services.db import get_engine

pytestmark = pytest.mark.integration

GIU, BO = "k12-giu", "k12-bo"


@pytest.fixture
def c():
    e = create_engine(get_engine().url, poolclass=StaticPool)
    with e.connect() as conn, conn.begin() as tx:
        for bang in (
            "documents",
            "provisions",
            "chunks",
            '"references"',
            "sua_doi_dieu_khoan",
            "verified_provisions",
            "verified_documents",
            "anh_van_ban",
        ):
            conn.execute(
                text(
                    f"CREATE TEMP TABLE {bang} (LIKE public.{bang} INCLUDING DEFAULTS INCLUDING CONSTRAINTS"
                    " INCLUDING INDEXES)"
                )
            )
        conn.execute(
            text(
                'CREATE TEMP TABLE canh_doi_chieu (reference_id bigint PRIMARY KEY REFERENCES "references"(id)'
                " ON DELETE CASCADE)"
            )
        )
        for i, so, depth in (
            (GIU, "07/2025/NĐ-CP", "deep"),
            (BO, "07/2025/NĐ-СР", "shallow"),
            ("k12-x", "01/2020/NĐ-CP", "deep"),
            ("k12-y", "02/2020/NĐ-CP", "deep"),
        ):
            conn.execute(
                text(
                    "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, depth, checksum)"
                    " VALUES (:i, :so, 'Nghị định', :so, 'CHL', :depth, 'k12')"
                ),
                {"i": i, "so": so, "depth": depth},
            )
        for pid, doc, cap in ((1, GIU, "mo_dau"), (2, GIU, "dieu"), (3, GIU, "khoan"), (4, BO, "mo_dau")):
            conn.execute(
                text(
                    "INSERT INTO provisions (id, document_id, cap, so_hieu_cap, tieu_de, noi_dung, duong_dan, thu_tu)"
                    " VALUES (:p, :d, :cap, '1', 't', 'n', :dd, :p)"
                ),
                {"p": 9_300_000 + pid, "d": doc, "cap": cap, "dd": f"{doc} > {pid}"},
            )
        conn.execute(
            text(
                "INSERT INTO chunks (id, provision_id, noi_dung_embed, embedding_model, embedding_dim)"
                " VALUES (9300004, 9300004, 'tên văn bản', 'm', 1024)"
            )
        )
        for rid, tu, toi, loai, p_tu, p_toi in (
            (1, GIU, "k12-x", 20, None, None),  # dòng giữ đã có, mang bằng chứng
            (2, GIU, GIU, 4, 9_300_002, 9_300_003),  # dẫn chiếu nội bộ cấp điều khoản
            (3, BO, "k12-x", 20, None, None),  # trùng hệt (1) sau khi trỏ lại → bỏ
            (4, BO, "k12-y", 20, None, None),  # mới với dòng giữ → trỏ lại
            (5, "k12-y", BO, 23, None, None),  # đi vào → trỏ lại
            (6, BO, GIU, 20, None, None),  # giữa hai bản sao → tự trỏ → bỏ
        ):
            conn.execute(
                text(
                    'INSERT INTO "references" (id, from_document_id, to_document_id, loai, from_provision_id,'
                    " to_provision_id) VALUES (:i, :f, :t, :l, :pf, :pt)"
                ),
                {"i": rid, "f": tu, "t": toi, "l": loai, "pf": p_tu, "pt": p_toi},
            )
        conn.execute(text("INSERT INTO canh_doi_chieu VALUES (1)"))
        yield conn
        tx.rollback()
    e.dispose()


def _canh(c) -> set[tuple]:
    return set(c.execute(text('SELECT id, from_document_id, to_document_id, loai FROM "references"')).all())


def test_gop_ban_kirin_giu_canh_noi_bo_va_bang_chung_chep_csv(c, tmp_path):
    kq = _gop(c, BO, GIU, tmp_path)
    assert (kq["canh_tro_lai"], kq["canh_trung_bo"], kq["provision_mo_dau_xoa"]) == (4, 2, 1)
    assert _canh(c) == {(1, GIU, "k12-x", 20), (2, GIU, GIU, 4), (4, GIU, "k12-y", 20), (5, "k12-y", GIU, 23)}
    assert c.execute(text("SELECT count(*) FROM canh_doi_chieu")).scalar_one() == 1
    assert c.execute(text("SELECT id FROM documents WHERE id = :b"), {"b": BO}).first() is None
    with open(kq["sao_luu"]["documents"], encoding="utf-8") as fh:
        assert [r["so_ky_hieu"] for r in csv.DictReader(fh)] == ["07/2025/NĐ-СР"]
    with open(kq["sao_luu"]["references"], encoding="utf-8") as fh:
        assert sorted(int(r["id"]) for r in csv.DictReader(fh)) == [3, 4, 5, 6], "trạng thái TRƯỚC khi trỏ lại"
    assert kq["sao_luu"]["chunks"] and kq["sao_luu"]["provisions"]
    assert _gop(c, BO, GIU, tmp_path) == {"bo": BO, "da_gop_tu_truoc": True}, "chạy lại là no-op"


def test_so_hieu_khac_that_thi_khong_gop(c):
    c.execute(text("UPDATE documents SET so_ky_hieu = '08/2025/NĐ-CP' WHERE id = :b"), {"b": BO})
    with pytest.raises(ValueError, match="không cùng số hiệu"):
        _gop(c, BO, GIU)


def test_anh_ban_goc_cua_dong_thua_chan_gop(c):
    c.execute(text("INSERT INTO anh_van_ban (doc_id, png, so_byte) VALUES (:b, '\\x89', 1)"), {"b": BO})
    with pytest.raises(ValueError, match="ảnh bản gốc"):
        _gop(c, BO, GIU)


def test_mat_bang_chung_doi_chieu_thi_dung(c):
    """Cạnh vừa trỏ lại mà trùng một cạnh của dòng giữ thì bị bỏ; nếu CHÍNH nó mang
    bằng chứng đối chiếu, bỏ nó là mất bằng chứng — dừng, không gộp."""
    c.execute(text("INSERT INTO canh_doi_chieu VALUES (3)"))
    with pytest.raises(ValueError, match="canh_doi_chieu"):
        _gop(c, BO, GIU)
