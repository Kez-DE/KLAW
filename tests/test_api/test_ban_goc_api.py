"""Bản gốc có chữ ký (quyết định 2026-09-28 mục 9): metadata trang văn bản mang
`link_pdf_ban_ky` (chỉ khi qua cửa kiểm) và `co_anh_xem_truoc`; ảnh trang 1 ra ở
`GET /van-ban/{doc_id}/anh-xem-truoc`. Văn bản bị ẩn: 404 `khong_hien_thi` như
mọi route trang một văn bản (K7).

Kho RIÊNG của test như `test_hien_thi_api.py`: bảng TẠM (`pg_temp`) cùng tên trên
MỘT kết nối (`StaticPool`), nên không dòng nào của DB dùng chung bị đọc hay ghi.
Cột `link_pdf_ban_ky` và bảng `anh_van_ban` dựng theo hợp đồng migration 040
(`ADD COLUMN IF NOT EXISTS`: khi public đã có cột, `LIKE` chép luôn CHECK của nó).
"""

import base64
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from src.services.db import get_engine
from src.services.effectivity import xoa_cache_danh_gia_toan_bo

pytestmark = pytest.mark.integration

VBPL = "https://vbpl.vn/van-ban/chi-tiet/"
PDF = "https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/12/145.signed.pdf"
# Qua được CHECK của cột (đúng tiền tố) nhưng không phải PDF: cửa kiểm phải chặn.
KHONG_PDF = "https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/12/145.doc"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")

# id, số hiệu, tình trạng, link PDF, có ảnh
VAN_BAN = [
    ("k10-du", "145/2020/NĐ-CP", "CHL", PDF, True),
    ("k10-khong-anh", "146/2020/NĐ-CP", "CHL", PDF, False),
    ("k10-khong-pdf", "147/2020/NĐ-CP", "CHL", None, True),
    ("k10-link-sai", "148/2020/NĐ-CP", "CHL", KHONG_PDF, True),
    ("k10-an", "149/2019/NĐ-CP", "HHL", PDF, True),
]


@pytest.fixture
def kho(monkeypatch):
    from src.api import routes, routes_van_ban

    e = create_engine(get_engine().url, poolclass=StaticPool)
    with e.begin() as c:
        for bang in ("documents", "provisions", "chunks", '"references"', "sua_doi_dieu_khoan"):
            c.execute(text(f"CREATE TEMP TABLE {bang} (LIKE public.{bang} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"))
        c.execute(
            text(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_pdf_ban_ky text"
                " CHECK (link_pdf_ban_ky IS NULL OR link_pdf_ban_ky LIKE 'https://datafiles.chinhphu.vn/%')"
            )
        )
        c.execute(
            text(
                "CREATE TEMP TABLE anh_van_ban (doc_id text PRIMARY KEY, png bytea NOT NULL,"
                " so_byte integer NOT NULL CHECK (so_byte > 0 AND so_byte <= 307200), rong integer, cao integer,"
                " tao_luc timestamptz NOT NULL DEFAULT now())"
            )
        )
        for n, (i, so, tt, pdf, anh) in enumerate(VAN_BAN, 1):
            c.execute(
                text(
                    "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, co_quan_ban_hanh,"
                    " ngay_ban_hanh, ngay_hieu_luc, depth, checksum, link_vbpl, link_pdf_ban_ky)"
                    " VALUES (:i, :so, 'Nghị định', :ten, :tt, 'Chính phủ', :bh, :hl, 'deep', 'k10', :vbpl, :pdf)"
                ),
                {
                    "i": i,
                    "so": so,
                    "ten": f"Nghị định {so} quy định chi tiết về việc làm",
                    "tt": tt,
                    "bh": date(2020, 12, 14),
                    "hl": date(2021, 2, 1),
                    "vbpl": f"{VBPL}90000{n}",
                    "pdf": pdf,
                },
            )
            c.execute(
                text(
                    "INSERT INTO provisions (id, document_id, cap, so_hieu_cap, tieu_de, noi_dung, duong_dan, thu_tu)"
                    " VALUES (:p, :d, 'dieu', '1', 'Điều 1. Phạm vi điều chỉnh', 'Nghị định này quy định.', :dd, 1)"
                ),
                {"p": 9_100_000 + n, "d": i, "dd": f"{so} > Điều 1"},
            )
            if anh:
                c.execute(
                    text("INSERT INTO anh_van_ban (doc_id, png, so_byte, rong, cao) VALUES (:i, :png, :n, 1, 1)"),
                    {"i": i, "png": PNG, "n": len(PNG)},
                )
    xoa_cache_danh_gia_toan_bo()
    for m in (routes, routes_van_ban):
        monkeypatch.setattr(m, "get_engine", lambda: e)
    yield e
    xoa_cache_danh_gia_toan_bo()
    e.dispose()


@pytest.mark.parametrize("tham_so", [{}, {"so_dieu": "1"}, {"around": 9_100_001}])
async def test_ca_ba_dang_metadata_mang_link_pdf_va_co_anh(client, kho, tham_so):
    d = (await client.get("/api/v1/van-ban/k10-du", params=tham_so)).json()
    assert (d["link_pdf_ban_ky"], d["co_anh_xem_truoc"]) == (PDF, True)


@pytest.mark.parametrize(
    ("doc_id", "mong"),
    [
        ("k10-khong-anh", (PDF, False)),
        ("k10-khong-pdf", (None, False)),
        ("k10-link-sai", (None, False)),
    ],
)
async def test_link_khong_qua_cua_kiem_thi_khong_co_link_va_khong_co_anh(client, kho, doc_id, mong):
    """Ảnh xem trước là trang 1 CỦA bản PDF: không có link PDF hợp lệ thì không có
    gì để bấm mở, nên `co_anh_xem_truoc` cũng tắt."""
    d = (await client.get(f"/api/v1/van-ban/{doc_id}")).json()
    assert (d["link_pdf_ban_ky"], d["co_anh_xem_truoc"]) == mong


async def test_anh_xem_truoc_tra_png_cache_mot_ngay_khong_can_dang_nhap(client, kho):
    r = await client.get("/api/v1/van-ban/k10-du/anh-xem-truoc")
    assert r.status_code == 200 and r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "public, max-age=86400"


@pytest.mark.parametrize("doc_id", ["k10-khong-anh", "khong-ton-tai"])
async def test_anh_xem_truoc_vang_thi_404(client, kho, doc_id):
    assert (await client.get(f"/api/v1/van-ban/{doc_id}/anh-xem-truoc")).status_code == 404


@pytest.mark.parametrize("duong", ["/api/v1/van-ban/k10-an", "/api/v1/van-ban/k10-an/anh-xem-truoc"])
async def test_van_ban_bi_an_tra_404_khong_hien_thi(client, kho, duong):
    r = await client.get(duong)
    assert r.status_code == 404 and r.json()["detail"]["ma"] == "khong_hien_thi"
