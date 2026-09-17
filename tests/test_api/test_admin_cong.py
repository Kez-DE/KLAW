"""Cổng `/admin` (spec 2B §5.3): 503 khi chưa cấu hình, 401 + nhật ký khi sai khoá,
400 khi thiếu danh tính, không liên quan `KLAW_API_KEY`."""

import pytest

from src.services import bao_ve, nang_goi, nhat_ky, tai_khoan_qt

DUNG = {"X-Admin-Key": "khoa-thu", "X-Admin-Boi": "qa@klaw.local"}
BAY_SO = ["tong_tai_khoan", "dang_ca_nhan", "cho_duyet", "het_han_7_ngay", "moi_7_ngay", "dang_khoa", "hoi_dap_hom_nay"]
MOT_SUB = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


@pytest.fixture
def ghi_gia(monkeypatch):
    dong: list[dict] = []
    monkeypatch.setattr(nhat_ky, "ghi", lambda hanh_dong, **kw: dong.append({"hanh_dong": hanh_dong, **kw}) or 1)
    monkeypatch.setattr(tai_khoan_qt, "tong_quan", lambda: dict.fromkeys(BAY_SO, 0))
    return dong


async def test_chua_cau_hinh_thi_503_ke_ca_khoa_dung(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="")
    r = await client.get("/api/v1/admin/tong-quan", headers=DUNG)
    assert r.status_code == 503 and r.json()["detail"] == bao_ve.LOI_ADMIN_CHUA_CAU_HINH


async def test_sai_khoa_401_va_ghi_xac_thuc_that_bai(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="khoa-thu")
    r = await client.get("/api/v1/admin/tong-quan", headers={**DUNG, "X-Admin-Key": "sai"})
    assert r.status_code == 401 and "khoa-thu" not in r.text
    assert ghi_gia[-1]["hanh_dong"] == "xac_thuc_that_bai" and ghi_gia[-1]["boi"] == "(không rõ)"
    assert (await client.get("/api/v1/admin/tong-quan", headers={"X-Admin-Boi": "qa@klaw.local"})).status_code == 401


async def test_thieu_boi_400_du_khoa_dung(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="khoa-thu")
    assert (await client.get("/api/v1/admin/tong-quan", headers={"X-Admin-Key": "khoa-thu"})).status_code == 400


async def test_khoa_dung_va_boi_dung_thi_200(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="khoa-thu")
    assert (await client.get("/api/v1/admin/tong-quan", headers=DUNG)).status_code == 200


async def test_KLAW_API_KEY_khong_lien_quan_toi_admin(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="khoa-thu", api_key="khoa-cong-khai")
    assert (await client.get("/api/v1/admin/tong-quan", headers=DUNG)).status_code == 200


async def test_loi_lap_trinh_KHONG_bi_LookupError_nuot_thanh_404(client, cai_dat, ghi_gia, monkeypatch):
    """`KeyError`/`IndexError` không phải lỗi NGHIỆP VỤ (`_LOI_NGHIEP_VU`) — `_thuc_hien`
    (bọc quanh các thao tác ghi như `mo_khoa`) KHÔNG được nuốt nó thành một 404 giả kèm
    một dòng nhật ký `..._that_bai` giả. `main.BatLoiMayChu` (Task 2, handler `Exception`
    toàn cục) bắt nó ở tầng ASGI và trả 500 — không còn thoát ra ngoài như trước khi có
    handler đó — nhưng `_thuc_hien` vẫn phải KHÔNG tự map nó thành 404/ghi nhật ký giả."""
    cai_dat(admin_api_key="khoa-thu")

    def no(sub: str, ly_do: str, boi: str, ip: str | None = None) -> dict:
        raise KeyError("x")

    monkeypatch.setattr(tai_khoan_qt, "mo_khoa", no)
    r = await client.post(f"/api/v1/admin/tai-khoan/{MOT_SUB}/mo-khoa", json={"ly_do": "x"}, headers=DUNG)
    assert r.status_code == 500
    assert not any(d["hanh_dong"] == "mo_khoa_tai_khoan_that_bai" for d in ghi_gia)


async def test_loi_nghiep_vu_KhongTonTai_van_map_dung_404_va_ghi_nhat_ky(client, cai_dat, ghi_gia, monkeypatch):
    """Đối xứng với ca trên: một lỗi NGHIỆP VỤ THẬT (`nang_goi.KhongTonTai`, cũng là một
    `LookupError`) vẫn phải được `_thuc_hien` bắt, map đúng 404, và ghi đúng MỘT dòng
    `mo_khoa_tai_khoan_that_bai` — chứng minh việc bỏ `LookupError` trần khỏi
    `_LOI_NGHIEP_VU` không làm hỏng đường xử lý lỗi hợp lệ."""
    cai_dat(admin_api_key="khoa-thu")

    def no(sub: str, ly_do: str, boi: str, ip: str | None = None) -> dict:
        raise nang_goi.KhongTonTai("x")

    monkeypatch.setattr(tai_khoan_qt, "mo_khoa", no)
    r = await client.post(f"/api/v1/admin/tai-khoan/{MOT_SUB}/mo-khoa", json={"ly_do": "x"}, headers=DUNG)
    assert r.status_code == 404
    ghi = [d for d in ghi_gia if d["hanh_dong"] == "mo_khoa_tai_khoan_that_bai"]
    assert len(ghi) == 1 and ghi[0]["chi_tiet"] == {"loi": "KhongTonTai"}
