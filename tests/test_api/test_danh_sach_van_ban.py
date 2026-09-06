"""`GET /api/v1/van-ban` — danh sách văn bản theo bộ lọc, KHÔNG cần từ khoá.

Tồn tại vì trang Tra cứu tick "Nghị định" (696) mà ô từ khoá rỗng thì trước
đây trống: `/tim-kiem` bắt buộc `q`. Cùng ba bất biến với `/tim-kiem`: giá trị
lọc lạ → 422 nêu giá trị thật; `hieu_luc` là phán quyết KLAW, không bao giờ
`documents.tinh_trang`; chỉ văn bản có toàn văn (`depth <> 'metadata'`), cùng
tập mà `/bo-loc` đếm.
"""

import pytest

BAC = {"con_hieu_luc": 0, "het_hieu_luc": 2, "bi_thay_the": 2}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_mac_dinh_20_dong_moi_nhat(client):
    r = await client.get("/api/v1/van-ban")
    assert r.status_code == 200
    d = r.json()
    assert d["sap_xep"] == "moi_nhat" and d["limit"] == 20 and d["offset"] == 0
    assert d["tong"] > 0
    assert len(d["ket_qua"]) == min(20, d["tong"])
    ngay = [k["ngay_ban_hanh"] for k in d["ket_qua"] if k["ngay_ban_hanh"] is not None]
    assert ngay == sorted(ngay, reverse=True), "moi_nhat phải giảm dần theo ngày ban hành"
    k = d["ket_qua"][0]
    for truong in ("doc_id", "so_ky_hieu", "bo_luat", "loai_van_ban", "co_quan_ban_hanh",
                   "ngay_ban_hanh", "hieu_luc"):
        assert truong in k, f"thiếu {truong} — FE không dựng được dòng"
    assert "tinh_trang" not in k and "tinh_trang" not in d


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_tong_khop_bo_loc(client):
    bo_loc = (await client.get("/api/v1/bo-loc")).json()
    loai = bo_loc["loai_van_ban"][0]
    r = await client.get("/api/v1/van-ban", params={"loai": loai["gia_tri"]})
    assert r.status_code == 200
    d = r.json()
    # Cùng tập `depth <> 'metadata'` với `/bo-loc`, nên con số phải TRÙNG — đây
    # là con số người dùng thấy cạnh ô tick, và họ đếm được dòng.
    assert d["tong"] == loai["so_van_ban"]
    assert all(k["loai_van_ban"] == loai["gia_tri"] for k in d["ket_qua"])
    khong_loc = (await client.get("/api/v1/van-ban")).json()
    assert khong_loc["tong"] == bo_loc["tong_van_ban"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_loc_theo_nam_va_phan_trang(client):
    r = await client.get("/api/v1/van-ban", params={"tu_nam": 2019, "den_nam": 2019, "limit": 5})
    assert r.status_code == 200
    d = r.json()
    assert all((k["ngay_ban_hanh"] or "2019")[:4] == "2019" for k in d["ket_qua"])
    trang2 = (await client.get(
        "/api/v1/van-ban", params={"tu_nam": 2019, "den_nam": 2019, "limit": 5, "offset": 5}
    )).json()
    ids1 = {k["doc_id"] for k in d["ket_qua"]}
    ids2 = {k["doc_id"] for k in trang2["ket_qua"]}
    assert ids1.isdisjoint(ids2), "hai trang không được lặp văn bản"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_con_hieu_luc_truoc_xep_theo_bac(client):
    r = await client.get("/api/v1/van-ban", params={"sap_xep": "con_hieu_luc_truoc", "limit": 50})
    assert r.status_code == 200
    bac = [BAC.get(k["hieu_luc"]["verdict"], 1) for k in r.json()["ket_qua"]]
    assert bac == sorted(bac), "còn hiệu lực → chưa rõ → đã chết, không trộn"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_tu_choi_tham_so_sai(client):
    assert (await client.get("/api/v1/van-ban", params={"tu_nam": 2020, "den_nam": 2019})).status_code == 422
    assert (await client.get("/api/v1/van-ban", params={"limit": 51})).status_code == 422
    assert (await client.get("/api/v1/van-ban", params={"sap_xep": "lien_quan"})).status_code == 422
    r = await client.get("/api/v1/van-ban", params={"loai": "Loại bịa"})
    assert r.status_code == 422
    assert "Giá trị thật" in r.json()["detail"]
