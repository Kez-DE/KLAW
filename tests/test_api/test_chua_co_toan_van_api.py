"""Văn bản được hiện mà KLAW chưa có toàn văn (quyết định 2026-09-28 mục 16): mọi
con số nói "có toàn văn" chỉ đếm văn bản có điều khoản thật, và trang văn bản mang
`co_toan_van` để nói thẳng khi chưa có.

Kho RIÊNG của test như `test_hien_thi_api.py`: bảng TẠM (`pg_temp`) cùng tên trên
MỘT kết nối (`StaticPool`), nên không dòng nào của DB dùng chung bị đọc hay ghi.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from src.services.db import get_engine
from src.services.effectivity import xoa_cache_danh_gia_toan_bo

pytestmark = pytest.mark.integration

VBPL = "https://vbpl.vn/van-ban/chi-tiet/"

# id, số hiệu, tình trạng, depth, provisions (cap, số hiệu cấp, nội dung)
VAN_BAN = [
    ("k16-sau", "61/2020/NĐ-CP", "CHL", "deep", [("dieu", "1", "Nghị định này quy định về tiền lương.")]),
    # Có toàn văn nhưng không chia Điều (chỉ thị đánh số khoản): vẫn là có toàn văn.
    ("k16-khoan", "62/2020/CT-TTg", "CHL", "deep", [("khoan", "1", "1. Các bộ tổ chức thực hiện.")]),
    # Chỉ có hàng `mo_dau` mang tên (migration 016): được hiện, CHƯA có toàn văn.
    ("k16-ten", "63/2020/NĐ-CP", "CHL", "shallow", [("mo_dau", "", "Nghị định về bảo hiểm thất nghiệp")]),
    # Hết hiệu lực: ẩn, không vào con số nào.
    ("k16-an", "64/2019/NĐ-CP", "HHL", "deep", [("dieu", "1", "Nghị định này quy định về tiền lương cũ.")]),
]


@pytest.fixture
def kho(monkeypatch):
    from src.api import routes, routes_tim_kiem, routes_van_ban
    from src.services.embedding import from_settings

    e = create_engine(get_engine().url, poolclass=StaticPool)
    with e.begin() as c:
        for bang in ("documents", "provisions", "chunks", '"references"', "sua_doi_dieu_khoan", "anh_van_ban"):
            c.execute(text(f"CREATE TEMP TABLE {bang} (LIKE public.{bang} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"))
        c.execute(text("CREATE TEMP TABLE canh_doi_chieu (reference_id bigint PRIMARY KEY)"))
        pid = 9_200_000
        for n, (i, so, tt, depth, provs) in enumerate(VAN_BAN, 1):
            c.execute(
                text(
                    "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, co_quan_ban_hanh,"
                    " ngay_ban_hanh, ngay_hieu_luc, depth, checksum, link_vbpl)"
                    " VALUES (:i, :so, 'Nghị định', :ten, :tt, 'Chính phủ', :bh, :hl, :depth, 'k16', :vbpl)"
                ),
                {
                    "i": i,
                    "so": so,
                    "ten": provs[0][2] if depth == "shallow" else f"Nghị định {so}",
                    "tt": tt,
                    "bh": date(2020, 5, 1),
                    "hl": date(2020, 7, 1),
                    "depth": depth,
                    "vbpl": f"{VBPL}91000{n}",
                },
            )
            for cap, so_cap, nd in provs:
                pid += 1
                dd = f"{so} > Mở đầu" if cap == "mo_dau" else f"{so} > {'Điều' if cap == 'dieu' else 'Khoản'} {so_cap}"
                c.execute(
                    text(
                        "INSERT INTO provisions (id, document_id, cap, so_hieu_cap, tieu_de, noi_dung, duong_dan, thu_tu)"
                        " VALUES (:p, :d, :cap, :s, :t, :n, :dd, 1)"
                    ),
                    {"p": pid, "d": i, "cap": cap, "s": so_cap, "t": nd[:40], "n": nd, "dd": dd},
                )
                c.execute(
                    text(
                        "INSERT INTO chunks (id, provision_id, noi_dung_embed, embedding_model, embedding_dim, tsv)"
                        " VALUES (:p, :p, :n, :m, 1024, klaw_tsv(:n))"
                    ),
                    {"p": pid, "n": f"{dd}\n{nd}", "m": from_settings().model},
                )
    xoa_cache_danh_gia_toan_bo()
    for m in (routes, routes_tim_kiem, routes_van_ban):
        monkeypatch.setattr(m, "get_engine", lambda: e)
    yield e
    xoa_cache_danh_gia_toan_bo()
    e.dispose()


async def test_bo_loc_dem_rieng_van_ban_co_toan_van_va_khop_pham_vi(client, kho):
    bl = (await client.get("/api/v1/bo-loc")).json()
    assert (bl["tong_van_ban"], bl["so_co_toan_van"]) == (3, 2), (
        "văn bản ẩn không vào; văn bản chỉ có tên không phải toàn văn"
    )
    pv = (await client.get("/api/v1/pham-vi")).json()
    assert pv["sau"]["so_van_ban"] == bl["so_co_toan_van"], "hai trang không được nói hai con số"
    assert pv["sau"]["so_van_ban"] + pv["nong"]["so_van_ban"] == bl["tong_van_ban"]
    assert [v["doc_id"] for v in pv["nong"]["van_ban"]] == ["k16-ten"]


@pytest.mark.parametrize(("doc_id", "mong"), [("k16-sau", True), ("k16-khoan", True), ("k16-ten", False)])
async def test_trang_van_ban_noi_co_toan_van_hay_khong(client, kho, doc_id, mong):
    d = (await client.get(f"/api/v1/van-ban/{doc_id}")).json()
    assert d["co_toan_van"] is mong
    if doc_id != "k16-sau":
        assert d["muc_luc"] == [], "không có Điều: mục lục rỗng, dù có hay không có toàn văn"


async def test_van_ban_chi_co_ten_tim_duoc_theo_ten_khong_theo_noi_dung(client, kho):
    """Câu dưới ô tìm kiếm nói văn bản chưa có toàn văn "chỉ tìm được theo tên":
    hàng `mo_dau` mang tên có chunk, nên tên khớp; nội dung thì không có gì để khớp."""
    tk = (await client.get("/api/v1/tim-kiem", params={"q": "bảo hiểm thất nghiệp"})).json()
    assert [(r["doc_id"], r["cap"]) for r in tk["ket_qua"]] == [("k16-ten", "mo_dau")]
