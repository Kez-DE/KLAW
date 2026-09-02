"""`GET /api/v1/van-ban/{doc_id}/tim?q=` — ô lọc mục lục (Pha 2, nhóm B).

Khác `/tim-kiem` toàn corpus ở ba điểm, và cả ba đều theo sau từ việc nó là một
Ô LỌC chứ không phải một máy tìm kiếm:

  * **Khớp CHUỖI CON, không phải lexeme.** Người dùng gõ dần từng chữ vào ô lọc
    và mong danh sách hẹp lại ngay từ "thai s". `to_tsquery` chỉ khớp trọn
    lexeme nên chuỗi dở dang không khớp gì — ô lọc trông như hỏng.
  * **Xếp theo THỨ TỰ VĂN BẢN (`thu_tu`), không theo điểm.** Đây là mục lục;
    xáo nó theo độ liên quan là làm mất chỗ người đọc đang đứng.
  * **Quét `provisions`, không quét `chunks`.** `chunks` chỉ phủ 6.067/36.710
    điều khoản (cấp Điều và một phần Khoản, 0 Điểm, 0 Chương/Mục), nên lọc qua
    nó thì gõ tên một Chương ra rỗng. Đo được: quét thẳng `provisions` của văn
    bản LỚN NHẤT (2.515 dòng) mất 9,2ms — rẻ hơn nhiều so với việc dựng một
    cột `tsv` thứ hai cho một ô lọc.
"""

import pytest

BLLD = "139264"      # 45/2019/QH14


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_trong_van_ban_ca_thuong(client):
    r = await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": "thai sản"})
    assert r.status_code == 200
    d = r.json()

    assert d["tong"] > 0
    assert d["ket_qua"]
    assert any("Điều 139" in k["duong_dan"] for k in d["ket_qua"]), (
        "Điều 139 là điều về nghỉ thai sản — không tìm thấy nó nghĩa là ô lọc hỏng"
    )
    k = d["ket_qua"][0]
    for truong in ("provision_id", "cap", "so_hieu_cap", "duong_dan", "tieu_de", "trich"):
        assert truong in k


@pytest.mark.integration
@pytest.mark.asyncio
async def test_go_khong_dau_van_tim_ra(client):
    """Người Việt gõ nhanh thường bỏ dấu. `unaccent` hai vế, cùng quy ước với
    `chunks.tsv` (migration 006)."""
    co_dau = (await client.get(
        f"/api/v1/van-ban/{BLLD}/tim", params={"q": "thai sản"})).json()
    khong_dau = (await client.get(
        f"/api/v1/van-ban/{BLLD}/tim", params={"q": "thai san"})).json()
    assert khong_dau["tong"] == co_dau["tong"] > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_go_chuoi_do_dang_van_hep_dan_duoc(client):
    """Ô lọc phải phản hồi từ ký tự thứ ba, không đợi trọn từ."""
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": "thai s"})).json()
    assert d["tong"] > 0, "khớp chuỗi con, không phải khớp trọn lexeme"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_duoc_ca_cap_CHUONG_khong_chi_dieu(client):
    """`chunks` phủ 0/407 Chương. Ô lọc mục lục mà không lọc được mục lục thì
    nó lọc nhầm thứ."""
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": "Chương"})).json()
    assert "chuong" in {k["cap"] for k in d["ket_qua"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ket_qua_theo_THU_TU_VAN_BAN_khong_theo_diem(client):
    d = (await client.get(
        f"/api/v1/van-ban/{BLLD}/tim", params={"q": "lao động", "limit": 60})).json()
    thu_tu = [k["thu_tu"] for k in d["ket_qua"]]
    assert thu_tu == sorted(thu_tu), "mục lục bị xáo là người đọc mất chỗ đang đứng"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_khong_lot_dieu_khoan_cua_van_ban_khac(client):
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": "lao động"})).json()
    assert all(k["duong_dan"].startswith("45/2019/QH14 >") for k in d["ket_qua"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ky_tu_dac_biet_cua_LIKE_khong_bien_thanh_ky_tu_dai_dien(client):
    """`%` và `_` trong truy vấn phải là chữ CỦA NGƯỜI DÙNG, không phải toán tử.

    Không escape thì gõ `%` khớp MỌI điều khoản — ô lọc "không lọc gì" mà không
    một thông báo nào; và `_` khớp một ký tự bất kỳ, cho kết quả sai lặng lẽ.
    """
    tat_ca = (await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": "a"})).json()
    phan_tram = (await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": "%"})).json()
    assert phan_tram["tong"] < tat_ca["tong"], "% bị hiểu là ký tự đại diện"


# ── Ca rỗng / tham số sai / không tồn tại ────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_khong_khop_tra_rong_khong_loi(client):
    r = await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": "zzqqxxkhongcogi"})
    assert r.status_code == 200
    d = r.json()
    assert d["ket_qua"] == [] and d["tong"] == 0


@pytest.mark.asyncio
async def test_thieu_q_tra_422(client):
    assert (await client.get(f"/api/v1/van-ban/{BLLD}/tim")).status_code == 422


@pytest.mark.asyncio
async def test_q_rong_tra_422(client):
    r = await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_limit_qua_lon_tra_422(client):
    r = await client.get(f"/api/v1/van-ban/{BLLD}/tim", params={"q": "a", "limit": 9999})
    assert r.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_doc_id_khong_ton_tai_tra_404(client):
    r = await client.get("/api/v1/van-ban/khong-ton-tai/tim", params={"q": "a"})
    assert r.status_code == 404
