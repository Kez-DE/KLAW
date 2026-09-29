"""Metadata mở rộng của `GET /api/v1/van-ban/{doc_id}` + `nguoi_ky` (Pha 2).

Trang đọc văn bản của FE hiển thị 10 trường; dạng không-tham-số của endpoint
này trả đúng 4 (`doc_id`, `so_ky_hieu`, `bo_luat`, `muc_luc`). Sáu trường còn
lại đều đã nằm trong `documents` — trừ người ký, và người ký cũng đã nằm sẵn
trong response MOJ mà `scripts/build_seed` tải về rồi bỏ qua (`documentIssues[]`
→ `personName`/`jobTitleName`). Lấy lại nó là 0 request phát sinh.

Trường KHÔNG được thêm, cố ý: `tinh_trang`. Nó có sẵn trong cùng dòng
`documents`, thêm nó vào đây là một dòng code — và là dòng code khiến trang đọc
văn bản dán nhãn "Còn hiệu lực" lên bốn nghị định lương tối thiểu đã bị thay.
Hiệu lực đi qua `GET /van-ban/{doc_id}/hieu-luc`, chỗ duy nhất `effectivity.py`
chạy.
"""

import pytest
from sqlalchemy import text

from src.services.db import get_engine

BLLD = "139264"      # 45/2019/QH14 — tầng sâu, có người ký

META = (
    "loai_van_ban", "co_quan_ban_hanh", "ngay_ban_hanh",
    "ngay_hieu_luc", "ngay_het_hieu_luc", "nguoi_ky", "chuc_danh_nguoi_ky",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dang_muc_luc_mang_du_metadata(client):
    d = (await client.get(f"/api/v1/van-ban/{BLLD}")).json()
    for t in META:
        assert t in d, f"thiếu {t} — FE phải gọi thêm một endpoint nữa để có nó"
    assert d["loai_van_ban"] == "Bộ luật"
    assert d["co_quan_ban_hanh"] == "Quốc hội"
    assert d["ngay_ban_hanh"] == "2019-11-20"
    assert d["ngay_hieu_luc"], "0/126 văn bản thiếu ngày hiệu lực trong DB"
    assert d["muc_luc"], "metadata mở rộng KHÔNG được thay thế mục lục"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dang_so_dieu_mang_cung_bo_metadata(client):
    """Ba dạng lazy phải trả CÙNG một bộ metadata.

    FE đi thẳng vào `?so_dieu=` khi mở một liên kết chia sẻ; nếu chỉ dạng mục
    lục có metadata thì trang đó hiện tiêu đề trống cho tới khi người dùng bấm
    ngược lên mục lục.
    """
    d = (await client.get(f"/api/v1/van-ban/{BLLD}", params={"so_dieu": "139"})).json()
    for t in META:
        assert t in d
    assert d["so_ky_hieu"] == "45/2019/QH14"
    assert d["provisions"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_KHONG_them_tinh_trang_du_no_nam_cung_dong(client):
    for params in ({}, {"so_dieu": "139"}):
        d = (await client.get(f"/api/v1/van-ban/{BLLD}", params=params)).json()
        assert "tinh_trang" not in d, (
            "hiệu lực đi qua /van-ban/{id}/hieu-luc; trường thô ở đây dán nhãn "
            "'Còn hiệu lực' lên văn bản đã bị thay"
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nguoi_ky_lay_duoc_tu_documentIssues_da_tai(client):
    d = (await client.get(f"/api/v1/van-ban/{BLLD}")).json()
    assert d["nguoi_ky"], "47/47 văn bản tầng sâu có personName trong response MOJ"
    assert d["chuc_danh_nguoi_ky"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_tang_metadata_tra_nguoi_ky_NULL_khong_bia(client):
    """Ca rỗng. 79 văn bản nạp từ `relationships.parquet` không có trường người
    ký nào, và NULL ở đó nghĩa là KHÔNG BIẾT — không phải "không có người ký".
    """
    from sqlalchemy import text

    from src.services.db import get_engine

    with get_engine().connect() as c:
        doc = c.execute(text(
            "SELECT id FROM documents WHERE depth = 'metadata' ORDER BY id LIMIT 1"
        )).scalar_one()

    d = (await client.get(f"/api/v1/van-ban/{doc}")).json()
    assert d["nguoi_ky"] is None
    assert d["chuc_danh_nguoi_ky"] is None
    assert d["muc_luc"] == [], "tầng metadata không có toàn văn nên không có mục lục"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_doc_id_khong_ton_tai_van_404(client):
    assert (await client.get("/api/v1/van-ban/khong-ton-tai")).status_code == 404


@pytest.mark.asyncio
async def test_hai_tham_so_cung_luc_van_422(client):
    r = await client.get(f"/api/v1/van-ban/{BLLD}", params={"so_dieu": "1", "around": 1})
    assert r.status_code == 422


# ── Bộ trích, độc lập với HTTP ───────────────────────────────────────────────


def test_trich_nguoi_ky_lay_muc_orderIndex_nho_nhat():
    from scripts.nap_nguoi_ky import nguoi_ky_tu_response

    d = {"documentIssues": [
        {"personName": "B", "jobTitleName": "Phó", "orderIndex": 2},
        {"personName": "A", "jobTitleName": "Chủ tịch", "orderIndex": 1},
    ]}
    assert nguoi_ky_tu_response(d) == ("A", "Chủ tịch")


def test_trich_nguoi_ky_khong_co_muc_nao_tra_None_khong_no():
    from scripts.nap_nguoi_ky import nguoi_ky_tu_response

    assert nguoi_ky_tu_response({}) == (None, None)
    assert nguoi_ky_tu_response({"documentIssues": []}) == (None, None)


def test_trich_nguoi_ky_chuoi_rong_thanh_None_khong_thanh_chuoi_rong():
    """CHECK của migration 015 chặn chuỗi rỗng: "" và NULL đọc giống nhau trên
    màn hình nhưng khác nhau ở `IS NULL`, và hai cách biểu đạt "không biết" là
    có một cách sẽ bị quên."""
    from scripts.nap_nguoi_ky import nguoi_ky_tu_response

    d = {"documentIssues": [{"personName": "  ", "jobTitleName": None, "orderIndex": 1}]}
    assert nguoi_ky_tu_response(d) == (None, None)


def test_chu_giu_cho_Chua_xac_dinh_cua_gateway_thanh_None():
    """12/2025/TTLT-VKSNDTC-TANDTC-BCA-BQP (6eea5ec0…): gateway ghi "Chưa xác định"
    vào `agencyName`, `personName`, `jobTitleName` thay cho "không có". Chép nguyên
    vào DB thì bộ lọc và trang văn bản hiện chữ đó — trái quyết định 2026-09-28 mục 8."""
    from scripts.nap_nguoi_ky import co_quan_tu_response, nguoi_ky_tu_response

    d = {
        "agencyName": "Chưa xác định",
        "documentIssues": [
            {"agencyName": "Chưa xác định", "personName": "Chưa xác định",
             "jobTitleName": "chưa xác định ", "orderIndex": 1},
        ],
    }
    assert co_quan_tu_response(d) is None
    assert nguoi_ky_tu_response(d) == (None, None)


def test_trich_nguoi_ky_KHONG_chuan_hoa_hoa_thuong():
    """13/2023/NĐ-CP công bố "TRẦN LƯU QUANG" viết hoa toàn bộ. Đó là thứ CSDL
    quốc gia công bố; `.title()` sẽ phá những tên mà quy tắc viết hoa tiếng Việt
    không áp được. Trình bày là việc của giao diện."""
    from scripts.nap_nguoi_ky import nguoi_ky_tu_response

    d = {"documentIssues": [
        {"personName": "TRẦN LƯU QUANG", "jobTitleName": "Phó Thủ tướng Chính phủ",
         "orderIndex": 1},
        {"personName": "Trần Lưu Quang", "jobTitleName": "Phó Thủ tướng", "orderIndex": 1},
    ]}
    assert nguoi_ky_tu_response(d) == ("TRẦN LƯU QUANG", "Phó Thủ tướng Chính phủ")


def test_van_ban_lien_tich_giu_du_co_quan_va_nguoi_ky():
    """31/2009/TTLT-BNNPTNT-BNV (11913): `agencyName` chỉ nêu Bộ Nông nghiệp, nhưng
    `documentIssues[]` nêu cả Bộ Nội vụ và người ký của nó. Lấy mục đầu thì trích dẫn
    mất một cơ quan ban hành (quyết định 2026-09-28 mục 3)."""
    from scripts.nap_nguoi_ky import co_quan_tu_response, nguoi_ky_tu_response

    d = {
        "agencyName": "Bộ Nông nghiệp và Phát triển nông thôn",
        "documentIssues": [
            {"agencyName": "Bộ Nội vụ", "personName": "Trần Văn Tuấn", "jobTitleName": "Bộ trưởng", "orderIndex": 2},
            {
                "agencyName": "Bộ Nông nghiệp và Phát triển nông thôn",
                "personName": "Cao Đức Phát",
                "jobTitleName": "Bộ trưởng",
                "orderIndex": 1,
            },
        ],
    }
    assert co_quan_tu_response(d) == "Bộ Nông nghiệp và Phát triển nông thôn, Bộ Nội vụ"
    assert nguoi_ky_tu_response(d) == ("Cao Đức Phát, Trần Văn Tuấn", "Bộ trưởng")


def test_mot_co_quan_giu_agencyName_va_nguoi_ky_dau():
    from scripts.nap_nguoi_ky import co_quan_tu_response

    d = {
        "agencyName": "Chính phủ",
        "documentIssues": [
            {"agencyName": "Chính phủ", "personName": "A", "orderIndex": 1},
            {"agencyName": "Chính phủ", "personName": "B", "orderIndex": 2},
        ],
    }
    assert co_quan_tu_response(d) == "Chính phủ"
    assert co_quan_tu_response({"agencyName": "Quốc hội"}) == "Quốc hội"


@pytest.mark.integration
def test_migration_015_idempotent_va_chan_chuoi_rong():
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from src.services.db import get_engine, run_migrations

    run_migrations("015")
    run_migrations("015")   # hai lần, trên bảng đã có dữ liệu

    with get_engine().begin() as c:
        cols = {r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'documents'"
        )).all()}
    assert {"nguoi_ky", "chuc_danh_nguoi_ky"} <= cols

    with pytest.raises(IntegrityError), get_engine().begin() as c:
        c.execute(text("UPDATE documents SET nguoi_ky = '' WHERE id = :i"), {"i": BLLD})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ba_dang_mang_cach_trich_va_lien_ket_chinh_thong(client):
    """Quyết định 2026-09-28: khung đối chiếu (`?around=`) và trang văn bản cùng
    mang câu trích theo mẫu luật và MỘT link chính thống — không bao giờ
    `nguon_url` (endpoint API) hay link giữ chỗ."""
    with get_engine().connect() as c:
        pid = c.execute(
            text("SELECT id FROM provisions WHERE document_id = :d AND cap = 'dieu' LIMIT 1"), {"d": BLLD}
        ).scalar_one()
    for params in ({}, {"so_dieu": "139"}, {"around": pid}):
        d = (await client.get(f"/api/v1/van-ban/{BLLD}", params=params)).json()
        assert d["cach_trich"] == "Bộ luật Lao động số 45/2019/QH14 ngày 20/11/2019 của Quốc hội", params
        assert d["ten_van_ban"] == d["bo_luat"]
        assert d["lien_ket"] is None or d["lien_ket"].startswith(
            ("https://vbpl.vn/van-ban/chi-tiet/", "https://vanban.chinhphu.vn/")
        ), d["lien_ket"]
        assert "gateway" not in (d["lien_ket"] or "")
