"""`GET /api/v1/van-ban/{doc_id}/hieu-luc` (Pha 2, nhóm B).

Endpoint quan trọng nhất về ĐÚNG/SAI trong cả Pha 2: nó là chỗ duy nhất giao
diện được phép lấy nhãn hiệu lực, và vì vậy là chỗ duy nhất phải bảo đảm nhãn
đó KHÔNG PHẢI `documents.tinh_trang`.

Vì sao đó không phải kỷ luật thừa. CSDL quốc gia đánh bốn nghị định lương tối
thiểu — 122/2015, 141/2017, 157/2018, 90/2019 — là `CHL` ("còn hiệu lực") dù cả
bốn đã bị thay. `kiem-ke-fe-lovable.md` đo được FE Lovable render trường đó
thẳng ra màn hình ở **11 vị trí**, và bộ lọc mặc định của nó (`tinhTrang:
["Còn hiệu lực"]`) GIẤU ĐI đúng những văn bản KLAW phát hiện sai. Nếu endpoint
này để lọt `tinh_trang`, FE sẽ dùng nó, và đóng góp trung tâm của khoá luận bị
lật ngược bằng một trường JSON.

Hai tầng, vì bằng chứng có ở hai cấp:
  * cấp VĂN BẢN — `effectivity.danh_gia` (Mức 1/2/3);
  * cấp ĐIỀU KHOẢN — `effectivity.ap_sua_doi` trên bảng `sua_doi_dieu_khoan`
    (Mức 4, nguồn Công báo/VBHN). Bảng này có 4 dòng `do_tin_cay='cao'` và
    chúng PHẢI xuất hiện: đó là toàn bộ lý do Mức 4 tồn tại.
"""

import json

import pytest

BLLD = "139264"      # 45/2019/QH14 — có cả 4 dòng sua_doi_dieu_khoan
BLDS = "95942"       # 91/2015/QH13 — không có dòng nào (ca rỗng cấp điều khoản)

VERDICT_HOP_LE = {
    "con_hieu_luc", "chua_hieu_luc", "het_hieu_luc", "bi_thay_the", "bi_sua_doi",
    "mot_phan_khong_xac_dinh", "can_doi_chieu_tay", "chua_xac_dinh",
}


# ── Bất biến khoá: không bao giờ rò tinh_trang thô ───────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_KHONG_BAO_GIO_tra_tinh_trang_tho_cua_MOJ(client):
    """Khoá bằng cách quét TOÀN BỘ response, không chỉ vài khoá đã biết.

    Kiểm theo tên khoá thôi thì một lần thêm trường `meta.tinh_trang` về sau đi
    lọt. Bốn mã của CSDL quốc gia (`CHL`/`HHL`/`HHL1P`/`chua_xac_dinh`) là chuỗi
    hiếm, quét cả response tìm chúng là phép kiểm rẻ và không có ngoại lệ hợp lệ
    — trừ `chua_xac_dinh`, TRÙNG TÊN với một verdict thật của KLAW nên không
    kiểm được bằng chuỗi (đã kiểm bằng `VERDICT_HOP_LE` ở test dưới).
    """
    for doc in (BLLD, BLDS):
        d = (await client.get(f"/api/v1/van-ban/{doc}/hieu-luc")).json()
        tho = json.dumps(d, ensure_ascii=False)
        assert "tinh_trang" not in tho, f"{doc}: rò tên trường tinh_trang"
        for ma in ('"CHL"', '"HHL"', '"HHL1P"'):
            assert ma not in tho, f"{doc}: rò mã tình trạng thô {ma} của MOJ"


# ── Ca then chốt: Điều 139 Khoản 1 ───────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dieu_139_khoan_1_ra_bi_sua_doi_va_neu_DICH_DANH_113_2025(client):
    """Ca sinh ra cả Mức 4.

    DB giữ nguyên văn BẢN GỐC ("06 tháng"); Luật Dân số 113/2025/QH15 sửa khoản
    này từ 01/7/2026, tức đã có hiệu lực tại hôm nay. Trước Mức 4, hệ thống trả
    nguyên văn cũ kèm nhãn `mot_phan_khong_xac_dinh` — trung thực nhưng là dạng
    yếu nhất của sự thật. Nhãn phải nêu ĐÍCH DANH văn bản sửa và NGÀY, nếu không
    người đọc không có cách nào tự đối chiếu.
    """
    d = (await client.get(
        f"/api/v1/van-ban/{BLLD}/hieu-luc", params={"as_of_date": "2026-09-01"}
    )).json()

    khoan = [k for k in d["dieu_khoan"]
             if k["duong_dan"] == "45/2019/QH14 > Điều 139 > Khoản 1"]
    assert khoan, "Khoản 1 Điều 139 phải có mặt — đây là ca trung tâm của Mức 4"
    k = khoan[0]

    assert k["hieu_luc"]["verdict"] == "bi_sua_doi"
    assert k["hieu_luc"]["tin_cay"] == "cao"
    assert "113/2025/QH15" in k["hieu_luc"]["ly_do"], "phải nêu ĐÍCH DANH văn bản sửa"
    assert "2026-07-01" in k["hieu_luc"]["ly_do"], "phải nêu NGÀY sửa đổi có hiệu lực"

    assert k["sua_boi"], "phải trả bản ghi có cấu trúc, không chỉ một câu văn xuôi"
    b = k["sua_boi"][0]
    assert b["so_ky_hieu"] == "113/2025/QH15"
    assert b["tu_ngay"] == "2026-07-01"
    assert b["nguon"], "Công báo yêu cầu ghi rõ nguồn khi phát hành lại thông tin"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dieu_cha_cung_bi_danh_dau_khong_chi_rieng_khoan(client):
    """Câu trả lời thường dẫn cả "Điều 139" trong khi bản ghi neo ở "Khoản 1".

    Chỉ đánh dấu đúng khoản neo thì một trích dẫn cấp Điều đi qua không một
    cảnh báo nào — đúng lỗ hổng im lặng mà `_SQL_SUA_DOI` (LIKE hậu duệ) tồn
    tại để bịt. Ngược lại, tổ tiên KHÔNG được lan xuống anh em: Khoản 2 của
    Điều 139 không có bản ghi nào thì không được đeo nhãn.
    """
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/hieu-luc")).json()
    dd = {k["duong_dan"] for k in d["dieu_khoan"]}
    assert "45/2019/QH14 > Điều 139" in dd, "Điều cha phải được đánh dấu"
    assert "45/2019/QH14 > Điều 139 > Khoản 2" not in dd, (
        "khoản anh em không bị sửa — dán nhãn lên nó là báo động giả"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_du_ca_bon_diem_sua_cua_bang_sua_doi_dieu_khoan(client):
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/hieu-luc")).json()
    neo = {b["vi_tri"] for k in d["dieu_khoan"] for b in k["sua_boi"]}
    assert neo == {
        "Điều 59 > Khoản 2 > Điểm a",
        "Điều 61 > Khoản 3",
        "Điều 139 > Khoản 1",
        "Điều 154 > Khoản 8a",
    }, "mất một điểm sửa nghĩa là một điều khoản đã đổi vẫn hiện ra như chưa"


# ── Cấp văn bản ──────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cap_van_ban_la_phan_quyet_KLAW_co_ly_do(client):
    d = (await client.get(f"/api/v1/van-ban/{BLLD}/hieu-luc")).json()
    v = d["van_ban"]
    assert v["verdict"] in VERDICT_HOP_LE
    assert v["tin_cay"] in {"cao", "trung_binh", "thap"}
    assert v["ly_do"], "một phán quyết không nêu lý do là một khẳng định trần"
    assert d["so_ky_hieu"] == "45/2019/QH14"
    assert d["as_of"], "phán quyết hiệu lực không có mốc thời gian là vô nghĩa"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_as_of_truoc_ngay_sua_doi_thi_khoan_van_CON_HIEU_LUC(client):
    """Chiều ngược của cùng một sự thật: 01/01/2026 là TRƯỚC 01/7/2026.

    Nói "đã bị sửa" lúc đó là sai theo chiều ngược lại — văn bản gốc đang ĐÚNG,
    và người dùng cần biết nó SẮP đổi chứ không phải nó đã hỏng.
    """
    d = (await client.get(
        f"/api/v1/van-ban/{BLLD}/hieu-luc", params={"as_of_date": "2026-01-15"}
    )).json()
    k = next(k for k in d["dieu_khoan"]
             if k["duong_dan"] == "45/2019/QH14 > Điều 139 > Khoản 1")
    assert k["hieu_luc"]["verdict"] == "con_hieu_luc"
    assert "sẽ bị" in k["hieu_luc"]["ly_do"]


# ── Ca rỗng ──────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_khong_co_ban_do_sua_doi_tra_danh_sach_rong_KHONG_404(client):
    """Rỗng ở cấp điều khoản là một KẾT QUẢ, không phải một lỗi.

    19.131/19.135 điều khoản không có bản ghi nào; nếu endpoint 404 hay 500 ở
    đây thì nó chỉ dùng được cho đúng một văn bản.
    """
    r = await client.get(f"/api/v1/van-ban/{BLDS}/hieu-luc")
    assert r.status_code == 200
    d = r.json()
    assert d["dieu_khoan"] == []
    assert d["van_ban"]["verdict"] in VERDICT_HOP_LE, (
        "không có bản đồ cấp điều khoản KHÔNG có nghĩa là không có phán quyết cấp văn bản"
    )


# ── Tham số sai / không tồn tại ──────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_doc_id_khong_ton_tai_tra_404(client):
    r = await client.get("/api/v1/van-ban/khong-ton-tai/hieu-luc")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_as_of_date_sai_dinh_dang_tra_422(client):
    r = await client.get(
        f"/api/v1/van-ban/{BLLD}/hieu-luc", params={"as_of_date": "31-12-2026"}
    )
    assert r.status_code == 422
