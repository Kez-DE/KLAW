"""`GET /api/v1/van-ban/{doc_id}/lien-quan` (Pha 2, nhóm B).

Bảng `"references"` có 3.597 dòng và 10 mã `loai`, nhưng ba nguồn khác nhau
trộn trong đó, và trộn chúng lại khi hiển thị là nói dối ba lần khác nhau:

  * **MOJ khai** (1/3/4/9/10/12, 517 dòng cấp văn bản) — đọc từ mảng
    `references` trong chính JSON của văn bản. Biết CHẮC bên nào khai, nhưng
    CHIỀU NGỮ NGHĨA chưa đo: "Thay thế" trong danh sách của X có thể là "X thay
    thế Y" hoặc "Y thay thế X" (xem `effectivity.TAC_DONG`: "chiều của 242 dòng
    đó CHƯA đo").
  * **Đồ thị hiệu lực** (20-23, 109 dòng) — suy từ `relationships.parquet`,
    chiều ĐÃ đo nhất quán 46/46.
  * **Dẫn chiếu nội bộ** (loai 4 cấp điều khoản, 2.971 dòng) — do `xref.py`
    sinh. ĐO ĐƯỢC: **2.971/2.971 nằm TRONG cùng một văn bản**, nên chúng không
    liên quan gì tới "văn bản liên quan" và đổ chúng vào danh sách đó là chôn 8
    quan hệ thật dưới 120 dòng nhiễu.

Ràng buộc thứ hai: 273/626 cạnh cấp văn bản trỏ tới văn bản KHÔNG có trong
corpus. Chúng phải hiện ra kèm cờ `trong_corpus=false` — bỏ đi là giấu mất một
nửa bản đồ quan hệ; dựng link cho chúng là hứa một trang 404.

Endpoint này là BẢN ĐỒ ĐIỀU HƯỚNG, không phải phán quyết. Hiệu lực đi qua
`/van-ban/{id}/hieu-luc`.
"""

import pytest

BLLD = "139264"      # 45/2019/QH14


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nhom_theo_quan_he_va_theo_chieu(client):
    r = await client.get(f"/api/v1/van-ban/{BLLD}/lien-quan")
    assert r.status_code == 200
    d = r.json()

    assert d["so_ky_hieu"] == "45/2019/QH14"
    assert d["nhom"], "BLLĐ có 8 nhóm quan hệ cấp văn bản trong DB"

    khoa = {(n["loai"], n["chieu"]) for n in d["nhom"]}
    assert len(khoa) == len(d["nhom"]), "một (loai, chieu) chỉ được xuất hiện một nhóm"
    assert all(n["chieu"] in {"di_ra", "di_vao"} for n in d["nhom"])
    assert all(n["so_luong"] == len(n["van_ban"]) for n in d["nhom"]), (
        "so_luong phải đếm từ chính danh sách trả về"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_moi_nhom_co_nhan_doc_duoc_khong_de_lo_ma_tran(client):
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/lien-quan")).json()
    for n in d["nhom"]:
        assert n["nhan"], f"loai {n['loai']} không có nhãn — FE sẽ hiện số trần"
        assert n["nhan"] != str(n["loai"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_noi_ro_chieu_ngu_nghia_nao_DA_DO_nao_chua(client):
    """Không được để FE suy hiệu lực từ tên quan hệ chưa đo chiều.

    Mã 20-23 do dự án tự suy, chiều đã đo 46/46 — `effectivity.danh_gia` dựa
    vào đúng chúng. Mã MOJ 1/3/4/9/10/12 thì chưa: một nhãn "Thay thế" hiển thị
    mà không nói rõ ai thay ai là một khẳng định pháp lý có 50% khả năng ngược.
    """
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/lien-quan")).json()
    theo_loai = {n["loai"]: n["chieu_da_do"] for n in d["nhom"]}
    assert theo_loai.get(20) is True, "cạnh đồ thị hiệu lực: chiều đã đo"
    assert theo_loai.get(3) is False, "mã MOJ: chiều ngữ nghĩa CHƯA đo"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chi_liet_ke_van_ban_duoc_hien_moi_dong_mo_duoc(client):
    """273/626 cạnh cấp văn bản trỏ ra ngoài corpus. Quyết định 2026-09-28 mục 8
    thay bản cũ ("văn bản ngoài corpus vẫn hiện, không hứa link"): chỉ văn bản
    được HIỆN mới được liệt kê — văn bản ngoài kho không có tình trạng hay link
    đã kiểm nên không qua được quy tắc — và mọi dòng mở được trang của nó."""
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/lien-quan")).json()
    tat_ca = [v for n in d["nhom"] for v in n["van_ban"]]
    for v in tat_ca:
        assert v["trong_corpus"] and v["doc_id"] and v["so_ky_hieu"], v
        assert (await client.get(f"/api/v1/van-ban/{v['doc_id']}")).status_code == 200, v


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dan_chieu_noi_bo_chi_dem_KHONG_tron_vao_van_ban_lien_quan(client):
    """2.971/2.971 dẫn chiếu cấp điều khoản nằm TRONG cùng văn bản.

    Đổ chúng vào `nhom` là chôn 8 quan hệ thật dưới 120 dòng nhiễu, và mỗi dòng
    trong đó trỏ về chính văn bản đang mở.
    """
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/lien-quan")).json()
    assert d["dan_chieu_noi_bo"]["so_luong"] > 0
    assert d["dan_chieu_noi_bo"]["ghi_chu"]
    # Không nhóm nào được chứa chính văn bản này.
    tu_tro = [v for n in d["nhom"] for v in n["van_ban"] if v["doc_id"] == BLLD]
    assert not tu_tro, "một văn bản không phải văn bản liên quan của chính nó"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_tang_metadata_tra_0_dan_chieu_noi_bo_KHONG_loi(client):
    """Ca rỗng thật của corpus này.

    Không văn bản nào có 0 cạnh (mọi dòng `documents` tầng metadata sinh ra
    CHÍNH VÌ có một cạnh trỏ tới nó), nhưng 79 văn bản tầng metadata không có
    toàn văn nên không có một dẫn chiếu nội bộ nào. Endpoint phải trả 0 chứ
    không nổ, và không được bịa ra một nhóm rỗng.
    """
    from sqlalchemy import text

    from src.services.db import get_engine

    with get_engine().connect() as c:
        doc = c.execute(text(
            "SELECT id FROM documents WHERE depth = 'metadata' ORDER BY id LIMIT 1"
        )).scalar_one()

    r = await client.get(f"/api/v1/van-ban/{doc}/lien-quan")
    if r.status_code == 404:
        # Văn bản tầng metadata không có toàn văn, thường thiếu cả link đã kiểm:
        # bị ẩn theo quyết định 2026-09-28 mục 8 — 404 có mã, không phải lỗi.
        assert r.json()["detail"]["ma"] == "khong_hien_thi"
        return
    assert r.status_code == 200
    d = r.json()
    assert d["dan_chieu_noi_bo"]["so_luong"] == 0
    assert all(n["so_luong"] > 0 for n in d["nhom"]), "nhóm rỗng là một chip bấm ra rỗng"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_doc_id_khong_ton_tai_tra_404(client):
    r = await client.get("/api/v1/van-ban/khong-ton-tai/lien-quan")
    assert r.status_code == 404
    assert "khong-ton-tai" in r.json()["detail"]


@pytest.mark.asyncio
async def test_limit_qua_lon_tra_422(client):
    r = await client.get(f"/api/v1/van-ban/{BLLD}/lien-quan", params={"limit_moi_nhom": 9999})
    assert r.status_code == 422
