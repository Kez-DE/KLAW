"""`GET /api/v1/pham-vi` — phạm vi corpus, lấy từ DB chứ không viết cứng.

Trang `/pham-vi` của FE bị CẤM gõ "21 văn bản / 19.135 điều khoản" vào JSX: một
con số viết cứng sai ngay lần seed sau, và dự án này tồn tại để chống đúng loại
khẳng định không kiểm chứng được đó.

Endpoint phơi bày HAI TẦNG vì corpus thật có hai tầng, và giấu tầng nông đi là
mô tả sai sản phẩm: 21 văn bản có toàn văn (`depth='deep'`) trả lời được thành
`answer`; các văn bản chỉ có metadata chính là thứ sinh ra `partial_coverage`.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pham_vi_lay_so_lieu_that_tu_db(client):
    r = await client.get("/api/v1/pham-vi")
    assert r.status_code == 200
    d = r.json()

    sau = d["sau"]
    assert sau["so_van_ban"] == len(sau["van_ban"]), "so_van_ban phải khớp danh sách, không phải hằng số rời"
    assert sau["so_dieu_khoan"] == sum(v["so_dieu_khoan"] for v in sau["van_ban"]), (
        "tổng điều khoản phải cộng từ chính danh sách trả về — nếu lệch thì một trong hai đang bịa"
    )
    assert sau["so_van_ban"] > 0 and sau["so_dieu_khoan"] > 0

    assert all(v["so_dieu_khoan"] > 0 for v in sau["van_ban"]), (
        "tầng sâu theo định nghĩa là có toàn văn; văn bản 0 điều khoản thuộc tầng nông"
    )
    assert all(v["so_dieu_khoan"] == 0 for v in d["nong"]["van_ban"]), (
        "tầng nông chỉ có metadata — có điều khoản nghĩa là phân tầng sai"
    )

    ids_sau = {v["doc_id"] for v in sau["van_ban"]}
    ids_nong = {v["doc_id"] for v in d["nong"]["van_ban"]}
    assert not (ids_sau & ids_nong), "một văn bản không thể vừa sâu vừa nông"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pham_vi_dinh_danh_bang_so_ky_hieu_va_neu_ro_tinh_trang_la_CUA_MOJ(client):
    d = (await client.get("/api/v1/pham-vi")).json()
    v = d["sau"]["van_ban"][0]
    assert v["so_ky_hieu"], "định danh là so_ky_hieu (Global Constraint), không bao giờ là tên"
    # Tên trường phải nói rõ đây là tuyên bố CỦA CSDL QUỐC GIA, không phải phán
    # quyết của KLAW: MOJ đánh sai hiệu lực 4 nghị định lương tối thiểu, và
    # trang /mien-tru dựa vào chính sự khác biệt này.
    assert "tinh_trang_moj" in v
    assert "tinh_trang" not in v, "tên trần gây hiểu nhầm là KLAW xác nhận"
