"""Test cho GET /api/v1/van-ban/{doc_id} (Task 7, Step 2) — ba dạng lazy.

Đụng Postgres thật (seed 21 văn bản / 19.135 provisions) nên mọi test chạm DB
ở đây mang `@pytest.mark.integration`, theo đúng quy ước đã có trong repo (xem
test_tra_cuu.py, test_infra/test_migrations.py) — CI bỏ qua bằng
`-m "not integration"`. Test 422 (cả hai tham số) không chạm DB nên không
mang marker, giống `test_query_rong_bi_422` trong test_tra_cuu.py.

Dùng doc_id 95942 — Bộ luật Dân sự (91/2015/QH13), 689 Điều — vì đây chính là
văn bản LỚN NHẤT trong corpus, đúng ca "lazy quan trọng" mà endpoint này phải
xử lý (không được kéo cả cây).

Mốc dùng trong test là `duong_dan`, KHÔNG phải `provisions.id`:
  - Điều 300 nằm giữa văn bản. 2 Điều liền trước theo `thu_tu` là 299, 298;
    2 Điều liền sau là 301, 302.
  - Điều 1 là Điều ĐẦU của BLDS — không có Điều nào trước.
  - Điều 689 là Điều CUỐI — không có Điều nào sau.
  - Điều 4 có đúng 4 Khoản con (Khoản 1..4), không có Điểm.
  - Chương I (dưới Phần thứ nhất) có đúng 7 Điều.
  - doc_id 96117 (Bộ luật Hàng hải, 95/2015/QH13) dùng để kiểm around trỏ
    sang provision của MỘT VĂN BẢN KHÁC.

Vì sao không ghi id: `provisions.id` là BIGSERIAL và `scripts.ingest` xoá-rồi-
chèn mỗi document có checksum đổi, nên MỌI id dịch sau một lần sửa parser hay
một lần mở rộng corpus. Bản trước ghim 129006/129007/127872/127873/127883/130383
và cả 7 test này đỏ với `404` — đỏ vì một lý do KHÔNG liên quan tới điều chúng
muốn khoá, đúng loại nhiễu làm người ta bỏ qua CI. `conftest.pid()` tra theo
`duong_dan`, khoá canonical mà `ux_provisions_neo_trich_dan` (migration 004)
bảo đảm duy nhất — và cũng là chuỗi người đọc thấy trong trích dẫn.
"""

import pytest

from tests.conftest import pid

DOC_ID_BLDS = "95942"
BLDS = "91/2015/QH13"


# ══ ?around= — dạng FE dùng nhiều nhất ═══════════════════════════════════════


@pytest.mark.integration
@pytest.mark.asyncio
async def test_around_dieu_giua_van_ban_tra_dung_5_dieu_mot_tam(client):
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"around": pid(f"{BLDS} > Điều 300")})
    assert r.status_code == 200
    data = r.json()
    assert data["doc_id"] == DOC_ID_BLDS
    assert data["so_ky_hieu"] == "91/2015/QH13"
    assert data["bo_luat"] == "Bộ luật Dân sự số 91/2015/QH13"

    dieu_rows = [p for p in data["provisions"] if p["cap"] == "dieu"]
    assert [p["so_hieu_cap"] for p in dieu_rows] == ["298", "299", "300", "301", "302"]

    la_tam_dieu = {p["so_hieu_cap"] for p in dieu_rows if p["la_tam"]}
    assert la_tam_dieu == {"300"}, "đúng MỘT Điều tâm điểm — Điều 300"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_around_lazy_gioi_han_so_dong_tra_ve(client):
    """Ràng buộc lazy cốt lõi: BLDS có 689 Điều, `?around=` KHÔNG được kéo cả
    cây. Đo thật trên Điều 300: đúng 13 dòng (5 Điều + Khoản con) — chặn ở
    60 theo đúng ví dụ trong yêu cầu, dư biên độ lớn nên không giòn (flaky)
    nếu seed đổi nhẹ."""
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"around": pid(f"{BLDS} > Điều 300")})
    assert r.status_code == 200
    assert len(r.json()["provisions"]) < 60


@pytest.mark.integration
@pytest.mark.asyncio
async def test_around_dieu_dau_van_ban_cat_bien_dung_khong_loi(client):
    """Điều 1 không có Điều nào trước — cắt biên đúng, không lỗi 500, không
    bịa hàng xóm không tồn tại."""
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"around": pid(f"{BLDS} > Điều 1")})
    assert r.status_code == 200
    dieu_rows = [p for p in r.json()["provisions"] if p["cap"] == "dieu"]
    assert [p["so_hieu_cap"] for p in dieu_rows] == ["1", "2", "3"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_around_dieu_cuoi_van_ban_cat_bien_dung_khong_loi(client):
    """Điều 689 (Điều cuối BLDS) không có Điều nào sau — cắt biên đúng."""
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"around": pid(f"{BLDS} > Điều 689")})
    assert r.status_code == 200
    dieu_rows = [p for p in r.json()["provisions"] if p["cap"] == "dieu"]
    assert [p["so_hieu_cap"] for p in dieu_rows] == ["687", "688", "689"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_around_nhan_id_khoan_van_tim_dung_dieu_cha(client):
    """Ca THƯỜNG (73,6% số Điều chỉ có tiêu đề — xem verify_tier1._cay_con):
    FE gửi `khop_tai_id`, thường là id của một Khoản chứ không phải Điều.
    Neo Khoản 1 của Điều 300 phải cho kết quả giống hệt neo Điều 300."""
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"around": pid(f"{BLDS} > Điều 300 > Khoản 1")})
    assert r.status_code == 200
    data = r.json()
    dieu_rows = [p for p in data["provisions"] if p["cap"] == "dieu"]
    assert [p["so_hieu_cap"] for p in dieu_rows] == ["298", "299", "300", "301", "302"]
    la_tam_dieu = {p["so_hieu_cap"] for p in dieu_rows if p["la_tam"]}
    assert la_tam_dieu == {"300"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_around_provision_khac_van_ban_tra_404_khong_im_lang(client):
    """provision thuộc văn bản KHÁC — phải 404, không được âm thầm trả rỗng
    hay trộn dữ liệu của văn bản đang hỏi với provision của văn bản khác."""
    ok = await client.get("/api/v1/van-ban/96117")  # sanity: 96117 tồn tại thật
    assert ok.status_code == 200
    r = await client.get("/api/v1/van-ban/96117", params={"around": pid(f"{BLDS} > Điều 300")})  # thuộc 95942
    assert r.status_code == 404


# ══ không tham số — mục lục, KHÔNG kéo nội dung Điều ═════════════════════════


@pytest.mark.integration
@pytest.mark.asyncio
async def test_khong_tham_so_tra_muc_luc_khong_co_dieu(client):
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}")
    assert r.status_code == 200
    data = r.json()
    assert data["so_ky_hieu"] == "91/2015/QH13"
    assert len(data["muc_luc"]) > 0
    caps = {item["cap"] for item in data["muc_luc"]}
    assert "dieu" not in caps
    assert caps <= {"phan", "chuong", "muc", "tieu_muc"}


# ══ ?so_dieu= — một Điều + Khoản/Điểm con ════════════════════════════════════


@pytest.mark.integration
@pytest.mark.asyncio
async def test_so_dieu_tra_dung_mot_dieu_va_khoan_con(client):
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"so_dieu": "4"})
    assert r.status_code == 200
    data = r.json()
    dieu_rows = [p for p in data["provisions"] if p["cap"] == "dieu"]
    assert [p["so_hieu_cap"] for p in dieu_rows] == ["4"]
    khoan_so_hieu = sorted(p["so_hieu_cap"] for p in data["provisions"] if p["cap"] == "khoan")
    assert khoan_so_hieu == ["1", "2", "3", "4"]
    assert all(p["la_tam"] for p in data["provisions"]), "chỉ một Điều — mọi dòng đều là tâm"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_so_dieu_khong_ton_tai_tra_404(client):
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"so_dieu": "99999"})
    assert r.status_code == 404


# ══ lỗi biên chung ═══════════════════════════════════════════════════════════


@pytest.mark.integration
@pytest.mark.asyncio
async def test_doc_id_la_tra_404(client):
    r = await client.get("/api/v1/van-ban/00000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_so_dieu_va_around_cung_luc_tra_422(client):
    """Không chạm DB — chặn ở biên validate trước khi tới bất kỳ truy vấn
    nào, nên không cần `@pytest.mark.integration`."""
    r = await client.get(
        f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"so_dieu": "1", "around": 1}
    )
    assert r.status_code == 422


# ══ ?trong_chuong= — mục lục Chương bấm được ═════════════════════════════════
# Trước bản này mục lục là danh sách CHẾT: `?around=<id Chương>` trả 404 ("không
# thuộc Điều nào") và không endpoint nào liệt kê Điều của một Chương. Agent dựng
# màn hình đã TỪ CHỐI suy `id Chương + 1` — cách đó đúng hôm nay và sai lặng lẽ
# ở lần seed sau.
#
# Mốc đo TRỰC TIẾP trên DB trước khi viết test: Chương I của BLDS có đúng 7 Điều.
# Chương lớn nhất corpus có 156 Điều nhưng 1231 dòng hậu duệ — nên endpoint trả
# TIÊU ĐỀ ĐIỀU, không kéo Khoản/Điểm.
# Neo Chương mang cả Phần cha: container KHÔNG bị lược khỏi `duong_dan` (chỉ cấp
# trích dẫn được mới lược — xem `prov_parser._duong_dan`).
CHUONG_I_BLDS = f"{BLDS} > Phần thứ nhất > Chương I"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trong_chuong_chi_tra_DIEU_khong_keo_ca_cay(client):
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"trong_chuong": pid(CHUONG_I_BLDS)})
    assert r.status_code == 200
    ps = r.json()["provisions"]
    assert len(ps) == 7, "Chương I của BLDS có đúng 7 Điều (đo trên DB)"
    assert all(p["cap"] == "dieu" for p in ps), (
        "chương lớn nhất corpus có 1231 dòng hậu duệ — kéo cả cây là phá đúng nguyên "
        "tắc lazy mà endpoint này sinh ra để giữ"
    )
    assert all(p["la_tam"] is False for p in ps), "duyệt mục lục chưa chọn Điều nào làm tâm"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trong_chuong_tu_choi_id_khong_phai_chuong(client):
    dieu_1 = pid(f"{BLDS} > Điều 1")
    r = await client.get(f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"trong_chuong": dieu_1})
    assert r.status_code == 422, f"{dieu_1} là Điều 1, không phải Chương — nói thẳng thay vì trả rỗng"


@pytest.mark.asyncio
async def test_trong_chuong_khong_dung_chung_voi_tham_so_khac(client):
    """Chặn ở biên validate, TRƯỚC mọi truy vấn — nên không `@integration` và
    KHÔNG gọi `pid()`: một id bất kỳ là đủ, và gọi DB ở đây sẽ bắt CI (chạy
    `-m "not integration"`, không có Postgres) phải dựng Postgres."""
    r = await client.get(
        f"/api/v1/van-ban/{DOC_ID_BLDS}", params={"trong_chuong": 1, "so_dieu": "1"}
    )
    assert r.status_code == 422
