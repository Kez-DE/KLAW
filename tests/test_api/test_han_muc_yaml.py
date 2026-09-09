"""`config/han_muc.yaml` v3 + gói hiệu lực (spec 2026-09-07 §4.1, §5)."""

from datetime import UTC, datetime, timedelta

import pytest
from starlette.requests import Request

from src.services import bao_ve

YAML_OK = (
    "goi_mac_dinh: free\nmui_gio: Asia/Ho_Chi_Minh\n"
    "goi:\n  free: {hoi_dap_ngay: 100, soan_thao_ngay: 3, soan_thao_thang: 20, luot_moi_phien: 30}\n"
    "  pro: {hoi_dap_ngay: 500, soan_thao_ngay: 20, soan_thao_thang: 100000, luot_moi_phien: 100000}\n"
    "la_chan: {free_hoi_dap_thang: 3000, ip_ngay: 1500}\n"
    "khach: {hoi_dap_24h: 10, ip_24h: 30}\nchu_ky_pro_ngay: 30\n"
)


@pytest.fixture
def yaml_tam(tmp_path, monkeypatch):
    def _dat(noi_dung: str):
        f = tmp_path / "han_muc.yaml"
        f.write_text(noi_dung, encoding="utf-8")
        monkeypatch.setattr(bao_ve, "HAN_MUC_PATH", f)
        bao_ve._doc_han_muc.cache_clear()

    yield _dat
    bao_ve._doc_han_muc.cache_clear()


def test_yaml_that_doc_duoc_va_dung_so():
    assert bao_ve.han_muc("free", "hoi_dap_ngay") == 100
    assert bao_ve.han_muc("free", "luot_moi_phien") == 30
    assert bao_ve.han_muc("pro", "hoi_dap_ngay") == 500
    assert bao_ve.han_muc("pro", "luot_moi_phien") >= 100_000
    assert bao_ve.la_chan("free_hoi_dap_thang") == 3000
    assert bao_ve.la_chan("ip_ngay") == 1500
    assert bao_ve.KHOA_LA_CHAN == ("free_hoi_dap_thang", "ip_ngay")


def test_yaml_khong_con_khoa_pro_hoi_dap_ngay():
    assert "pro_hoi_dap_ngay" not in bao_ve._doc_han_muc()["la_chan"]


@pytest.mark.parametrize(
    "hong, khop",
    [
        (YAML_OK.replace("chu_ky_pro_ngay: 30\n", ""), "chu_ky_pro_ngay"),
        (YAML_OK.replace("mui_gio: Asia/Ho_Chi_Minh\n", "mui_gio: Sao/Hoa\n"), "mui_gio"),
        (YAML_OK.replace(", luot_moi_phien: 30}", "}"), "luot_moi_phien"),
        (YAML_OK.replace("la_chan: {free_hoi_dap_thang: 3000, ", "la_chan: {"), "free_hoi_dap_thang"),
        (YAML_OK + "phien_luu: {free: 10}\n", "phien_luu"),
    ],
)
def test_yaml_hong_thi_fail_loud(yaml_tam, hong, khop):
    yaml_tam(hong)
    with pytest.raises(ValueError, match=khop):
        bao_ve._doc_han_muc()


def test_moc_ngay_thang_theo_gio_viet_nam():
    # 23:30 UTC ngày 7 = 06:30 ngày 8 giờ VN → mốc ngày là 00:00 ngày 8 (+07:00)
    luc = datetime(2026, 9, 7, 23, 30, tzinfo=UTC)
    assert bao_ve.moc_ngay(luc).isoformat() == "2026-09-08T00:00:00+07:00"
    assert bao_ve.moc_ngay_sau(luc).isoformat() == "2026-09-09T00:00:00+07:00"
    assert bao_ve.moc_thang(luc).isoformat() == "2026-09-01T00:00:00+07:00"
    assert bao_ve.moc_thang_sau(luc).isoformat() == "2026-10-01T00:00:00+07:00"


def test_plan_hieu_luc_tu_het_han():
    assert bao_ve.plan_hieu_luc_tu("pro", None) == "pro"
    assert bao_ve.plan_hieu_luc_tu("pro", datetime.now(UTC) + timedelta(days=1)) == "pro"
    assert bao_ve.plan_hieu_luc_tu("pro", datetime.now(UTC) - timedelta(seconds=1)) == "free"
    assert bao_ve.plan_hieu_luc_tu("free", None) == "free"


def _request(gia_tri: str | None) -> Request:
    """Request tối thiểu chỉ mang header `X-Khach-Id` (hoặc không mang gì)."""
    headers = [(bao_ve.KHACH_HEADER.encode(), gia_tri.encode())] if gia_tri is not None else []
    return Request({"type": "http", "headers": headers})


def test_khach_id_tu_request_uuid_hop_le_tra_ve_chinh_no():
    ma = "550e8400-e29b-41d4-a716-446655440000"
    assert bao_ve.khach_id_tu_request(_request(ma)) == ma


def test_khach_id_tu_request_khong_phai_uuid_tra_ve_none():
    assert bao_ve.khach_id_tu_request(_request("not-a-uuid")) is None


def test_khach_id_tu_request_thieu_header_tra_ve_none():
    assert bao_ve.khach_id_tu_request(_request(None)) is None


def test_khach_id_tu_request_uuid_hoa_thi_chuan_hoa_ve_chu_thuong():
    assert (
        bao_ve.khach_id_tu_request(_request("550E8400-E29B-41D4-A716-446655440000"))
        == "550e8400-e29b-41d4-a716-446655440000"
    )
