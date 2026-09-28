"""`GET /api/v1/bo-loc` và `GET /api/v1/tim-kiem` (Pha 2, nhóm B).

Hai endpoint này tồn tại vì cùng MỘT lý do với `/pham-vi`: giao diện không được
viết cứng thứ nó không đo được. `kiem-ke-fe-lovable.md` §9 đo được FE giả định
**11 loại văn bản / 8 cơ quan**; DB lúc đó có 6/3, và sau lần mở rộng corpus
gần nhất có **8 loại / 3 cơ quan + 79 văn bản KHÔNG có cơ quan**. Cả hai con số
FE đoán đều sai, và sai theo hướng nguy hiểm nhất: một chip lọc trỏ vào giá trị
không tồn tại trả về danh sách RỖNG mà không nói lý do, nên người dùng kết luận
"KLAW không có văn bản nào về việc này" trong khi thật ra họ vừa bấm một cái
nhãn bịa.

Nên hai bất biến được khoá ở đây:
  1. `/bo-loc` trả giá trị ĐẾM ĐƯỢC TỪ DB, không phải hằng số trong Python.
  2. `/tim-kiem` TỪ CHỐI (422) một giá trị lọc không có trong DB, nêu tên các
     giá trị thật — thay vì trả rỗng im lặng.

Và bất biến thứ ba, kế thừa từ `effectivity.py`: mỗi kết quả mang phán quyết
hiệu lực của KLAW, KHÔNG BAO GIỜ `documents.tinh_trang` thô (CSDL quốc gia đánh
4 nghị định lương tối thiểu đã bị thay là "còn hiệu lực").
"""

import pytest

# ── /bo-loc ──────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bo_loc_dem_tu_db_khong_phai_hang_so(client):
    r = await client.get("/api/v1/bo-loc")
    assert r.status_code == 200
    d = r.json()

    assert d["loai_van_ban"], "corpus có văn bản thì phải có ít nhất một loại"
    assert all(v["so_van_ban"] > 0 for v in d["loai_van_ban"]), (
        "một giá trị lọc 0 văn bản là một chip bấm vào ra rỗng — không được trả về"
    )
    assert all(v["so_van_ban"] > 0 for v in d["co_quan_ban_hanh"])

    tong = sum(v["so_van_ban"] for v in d["loai_van_ban"])
    assert tong == d["tong_van_ban"], (
        "tổng theo loại phải bằng tổng corpus — lệch nghĩa là một nhánh đang bịa"
    )
    # `co_quan_khong_ro` giữ lại dù nay bằng 0: nếu sau này một văn bản CÓ
    # điều khoản mà thiếu cơ quan ban hành, con số đó phải được nói ra chứ
    # không được giấu bằng cách bỏ qua. Tầng metadata thì đã có `/pham-vi`
    # công bố riêng (`nong`), không phải việc của bộ lọc.
    assert d["co_quan_khong_ro"] == d["tong_van_ban"] - sum(
        v["so_van_ban"] for v in d["co_quan_ban_hanh"]
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bo_loc_chi_mo_ta_van_ban_tim_kiem_toi_duoc(client):
    """Từ vựng của bộ lọc phải mô tả ĐÚNG tập hợp mà bộ lọc tìm trong đó.

    `/tim-kiem` khớp trên `provisions`, nên 79 bản ghi tầng metadata (0 điều
    khoản) là thứ nó KHÔNG BAO GIỜ trả về. Trước bản này `/bo-loc` đếm cả
    chúng, nên nó hứa "Luật: 75" trong khi tìm kiếm chỉ với tới 25, "Bộ luật:
    12" trong khi thật là 6 — và chào bốn nhóm (Quyết định, Pháp lệnh, Nghị
    quyết, Thông tư liên tịch) luôn luôn ra rỗng khi bấm.

    Test cũ ngay bên trên ĐÃ nêu đúng luật ("một giá trị lọc 0 văn bản là một
    chip bấm vào ra rỗng") nhưng đo nhầm đại lượng: `so_van_ban > 0` tính cả
    bản ghi metadata, nên đúng bốn cái chip rỗng ấy lọt qua.

    Không neo vào con số 47 — corpus còn lớn lên. Neo vào bất biến: mỗi giá
    trị lọc phải đếm đúng số văn bản CÓ điều khoản mang giá trị đó.
    """
    from sqlalchemy import text as _text

    from src.config import as_of_hieu_luc
    from src.services.db import get_engine
    from src.services.hien_thi import hien_thi_luc

    d = (await client.get("/api/v1/bo-loc")).json()

    # Chỉ văn bản được hiện (quyết định 2026-09-28 mục 8) — tìm kiếm cũng chỉ với tới chúng.
    with get_engine().connect() as c:
        that = dict(c.execute(_text(
            "SELECT loai_van_ban, count(*)::int FROM documents d"
            " WHERE EXISTS (SELECT 1 FROM provisions p WHERE p.document_id = d.id)"
            "   AND d.id = ANY(CAST(:hien AS text[]))"
            " GROUP BY 1"
        ), {"hien": list(hien_thi_luc(get_engine(), as_of_hieu_luc(None)))}).all())

    tra_ve = {v["gia_tri"]: v["so_van_ban"] for v in d["loai_van_ban"]}
    assert tra_ve == that, (
        "mỗi chip phải đếm đúng số văn bản tìm kiếm với tới được"
    )
    assert d["tong_van_ban"] == sum(that.values())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bo_loc_khong_bia_gia_tri_FE_gia_dinh(client):
    """FE Lovable hardcode 11 loại / 8 cơ quan / 10 lĩnh vực. `linh_vuc` KHÔNG
    có cột nào trong DB, nên endpoint này không được có khoá đó — thà FE vỡ
    lúc tích hợp còn hơn dựng một bộ lọc không lọc gì."""
    d = (await client.get("/api/v1/bo-loc")).json()
    assert "linh_vuc" not in d, "không có cột lĩnh vực trong DB — không được hứa"
    assert "tinh_trang" not in d, (
        "lọc theo tinh_trang thô của MOJ là đúng lỗi Mức 2 mà dự án tồn tại để chữa"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bo_loc_neu_khoang_nam_that(client):
    d = (await client.get("/api/v1/bo-loc")).json()
    assert d["nam_min"] <= d["nam_max"]
    assert 1900 < d["nam_min"] < 2100


# ── /tim-kiem: ca thường ─────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_tra_danh_sach_dieu_khoan_kem_tong(client):
    r = await client.get("/api/v1/tim-kiem", params={"q": "thai sản"})
    assert r.status_code == 200
    d = r.json()

    assert d["tong_dieu_khoan"] > 0
    assert d["tong_van_ban"] > 0
    assert d["tong_van_ban"] <= d["tong_dieu_khoan"], (
        "không thể có nhiều văn bản hơn số điều khoản khớp"
    )
    assert len(d["ket_qua"]) == min(d["limit"], d["tong_dieu_khoan"])

    k = d["ket_qua"][0]
    # Khoá chính xác bộ khoá FE cần để mở văn bản (click-to-verify).
    for truong in ("provision_id", "doc_id", "so_ky_hieu", "duong_dan", "score", "hieu_luc"):
        assert truong in k, f"thiếu {truong} — FE không dựng được liên kết"
    assert k["score"] > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_moi_ket_qua_mang_phan_quyet_KLAW_khong_phai_tinh_trang_MOJ(client):
    """Bất biến trung tâm của cả đề tài, ở một endpoint mới.

    `documents.tinh_trang` không bao giờ được rò ra response — CSDL quốc gia
    đánh 122/2015, 141/2017, 157/2018, 90/2019 là "CHL" (còn hiệu lực) dù cả
    bốn đã bị thay. FE Lovable render thẳng trường đó ở 11 vị trí.
    """
    d = (await client.get("/api/v1/tim-kiem", params={"q": "lương tối thiểu"})).json()
    assert d["ket_qua"], "truy vấn này phải khớp — corpus có chuỗi nghị định lương tối thiểu"

    hop_le = {
        "con_hieu_luc", "chua_hieu_luc", "het_hieu_luc", "bi_thay_the", "bi_sua_doi",
        "mot_phan_khong_xac_dinh", "can_doi_chieu_tay", "chua_xac_dinh",
    }
    for k in d["ket_qua"]:
        assert "tinh_trang" not in k
        assert k["hieu_luc"]["verdict"] in hop_le
        assert k["hieu_luc"]["tin_cay"] in {"cao", "trung_binh", "thap"}
        assert k["hieu_luc"]["ly_do"], "một phán quyết không nêu lý do là một khẳng định trần"

    # Mã thô của CSDL quốc gia không được rò ra dưới bất kỳ trường nào.
    tho = {"CHL", "HHL", "HHL1P"}
    assert tho.isdisjoint(str(d).split()), (
        "mã tình trạng thô của MOJ xuất hiện trong response"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_loc_theo_loai_chi_tra_dung_loai_do(client):
    bo_loc = (await client.get("/api/v1/bo-loc")).json()
    loai = bo_loc["loai_van_ban"][0]["gia_tri"]
    d = (await client.get(
        "/api/v1/tim-kiem", params={"q": "lao động", "loai": loai}
    )).json()
    assert d["ket_qua"]
    assert {k["loai_van_ban"] for k in d["ket_qua"]} == {loai}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_loc_theo_nam_ban_hanh(client):
    d = (await client.get(
        "/api/v1/tim-kiem", params={"q": "lao động", "tu_nam": 2019, "den_nam": 2019}
    )).json()
    assert d["ket_qua"], "corpus có Bộ luật Lao động 2019"
    assert all(k["ngay_ban_hanh"].startswith("2019") for k in d["ket_qua"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_phan_trang_khong_lap_khong_sot(client):
    p = {"q": "hợp đồng lao động", "limit": 5}
    trang1 = (await client.get("/api/v1/tim-kiem", params={**p, "offset": 0})).json()
    trang2 = (await client.get("/api/v1/tim-kiem", params={**p, "offset": 5})).json()
    assert trang1["tong_dieu_khoan"] == trang2["tong_dieu_khoan"], (
        "tổng phải là tổng của TOÀN tập khớp, không phải của trang"
    )
    id1 = [k["provision_id"] for k in trang1["ket_qua"]]
    id2 = [k["provision_id"] for k in trang2["ket_qua"]]
    assert not set(id1) & set(id2), "hai trang chồng nhau = thứ tự không tất định"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_sap_xep_moi_nhat_giam_dan_theo_ngay(client):
    d = (await client.get(
        "/api/v1/tim-kiem", params={"q": "lao động", "sap_xep": "moi_nhat", "limit": 20}
    )).json()
    ngay = [k["ngay_ban_hanh"] for k in d["ket_qua"]]
    assert ngay == sorted(ngay, reverse=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_sap_xep_con_hieu_luc_truoc_dat_van_ban_song_len_dau(client):
    d = (await client.get("/api/v1/tim-kiem", params={
        "q": "lao động", "sap_xep": "con_hieu_luc_truoc", "limit": 50,
    })).json()
    # Ba bậc: còn hiệu lực → chưa kết luận được → đã chết. Bậc phải không giảm.
    chet = {"bi_thay_the", "het_hieu_luc", "chua_hieu_luc"}
    day = [0 if k["hieu_luc"]["verdict"] == "con_hieu_luc"
           else 2 if k["hieu_luc"]["verdict"] in chet else 1
           for k in d["ket_qua"]]
    assert day == sorted(day), f"thứ tự hiệu lực bị vỡ: {day}"


# ── /tim-kiem: ca rỗng ───────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_khong_khop_tra_rong_khong_loi(client):
    r = await client.get("/api/v1/tim-kiem", params={"q": "zzzqqqxxx khongcotutnaykhop"})
    assert r.status_code == 200
    d = r.json()
    assert d["ket_qua"] == []
    assert d["tong_dieu_khoan"] == 0
    assert d["tong_van_ban"] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_offset_qua_cuoi_tra_rong_nhung_giu_tong(client):
    d = (await client.get(
        "/api/v1/tim-kiem", params={"q": "lao động", "offset": 100000}
    )).json()
    assert d["ket_qua"] == []
    assert d["tong_dieu_khoan"] > 0, "tổng là của tập khớp, không phải của trang"


# ── /tim-kiem: tham số sai → 422 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tim_kiem_thieu_q_tra_422(client):
    assert (await client.get("/api/v1/tim-kiem")).status_code == 422


@pytest.mark.asyncio
async def test_tim_kiem_q_rong_tra_422(client):
    assert (await client.get("/api/v1/tim-kiem", params={"q": ""})).status_code == 422


@pytest.mark.asyncio
async def test_tim_kiem_sap_xep_la_tra_422(client):
    r = await client.get("/api/v1/tim-kiem", params={"q": "a", "sap_xep": "ngau_nhien"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_tim_kiem_limit_qua_lon_tra_422(client):
    r = await client.get("/api/v1/tim-kiem", params={"q": "a", "limit": 5000})
    assert r.status_code == 422, "limit không chặn trên là một đường kéo cả corpus"


@pytest.mark.asyncio
async def test_tim_kiem_nam_dao_nguoc_tra_422(client):
    r = await client.get("/api/v1/tim-kiem", params={"q": "a", "tu_nam": 2020, "den_nam": 2010})
    assert r.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_loai_khong_co_trong_db_tra_422_neu_ten_gia_tri_that(client):
    """Ca 'không tồn tại' của endpoint này.

    KHÔNG trả rỗng: rỗng không phân biệt được "không có văn bản nào khớp" với
    "bạn vừa bấm một chip bịa". FE Lovable hardcode 11 loại; 3 trong số đó
    không tồn tại. 422 kèm danh sách thật là thứ duy nhất làm lỗi đó lộ ra.
    """
    r = await client.get(
        "/api/v1/tim-kiem", params={"q": "lao động", "loai": "Sắc lệnh"}
    )
    assert r.status_code == 422
    chi_tiet = r.json()["detail"]
    assert "Sắc lệnh" in chi_tiet
    assert "Nghị định" in chi_tiet, "phải nêu giá trị THẬT để FE sửa được chip"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tim_kiem_co_quan_khong_co_trong_db_tra_422(client):
    r = await client.get(
        "/api/v1/tim-kiem", params={"q": "lao động", "co_quan": "Bộ Tư pháp"}
    )
    assert r.status_code == 422
