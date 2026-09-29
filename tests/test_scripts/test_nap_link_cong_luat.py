"""Ba phép kiểm của loader link cổng luật (spec 2026-09-06 §4.2) — thuần,
không cần DB: allowlist host, https, ngày kiểm, khoá lạ."""

from datetime import date

import pytest

from scripts.nap_link_cong_luat import HOST_CHO_PHEP, kiem_hang, kiem_url

HOM_NAY = date(2026, 9, 6)
VBPL = "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=139264"


def test_allowlist_dung_ba_host():
    assert HOST_CHO_PHEP == {"vbpl": "vbpl.vn", "chinhphu": "vanban.chinhphu.vn", "tvpl": "thuvienphapluat.vn"}


def test_kiem_url_null_di_qua_https_dung_host_di_qua():
    assert kiem_url("vbpl", None) is None
    assert kiem_url("vbpl", VBPL) == VBPL


@pytest.mark.parametrize(
    "cot, url",
    [
        ("vbpl", "http://vbpl.vn/x"),  # không https
        ("vbpl", "https://vanban.chinhphu.vn/x"),  # host của cột khác
        ("chinhphu", "https://evil.example/vanban.chinhphu.vn"),
        ("tvpl", "https://thuvienphapluat.vn.evil/x"),
        ("vbpl", 123),  # không phải chuỗi
    ],
)
def test_kiem_url_tu_choi(cot, url):
    with pytest.raises(ValueError):
        kiem_url(cot, url)


def test_kiem_hang_tra_ba_cot_va_null_cho_cot_thieu():
    ra = kiem_hang("139264", {"vbpl": VBPL, "kiem_luc": HOM_NAY, "kiem_boi": "chu-du-an"}, HOM_NAY)
    assert ra == {"vbpl": VBPL, "chinhphu": None, "tvpl": None}


@pytest.mark.parametrize(
    "hang, loi",
    [
        ({"vbpl": VBPL, "kiem_boi": "x"}, "kiem_luc"),  # thiếu ngày
        ({"vbpl": VBPL, "kiem_luc": "2026-09-06", "kiem_boi": "x"}, "kiem_luc"),  # ngày là chuỗi
        ({"vbpl": VBPL, "kiem_luc": date(2027, 1, 1), "kiem_boi": "x"}, "tương lai"),
        ({"vbpl": VBPL, "kiem_luc": HOM_NAY}, "kiem_boi"),  # thiếu người kiểm
        ({"vbpl": VBPL, "kiem_luc": HOM_NAY, "kiem_boi": "x", "moj": "y"}, "khoá lạ"),
    ],
)
def test_kiem_hang_tu_choi(hang, loi):
    with pytest.raises(ValueError, match=loi):
        kiem_hang("139264", hang, HOM_NAY)


# ── Seed máy kiểm `data/seed/link_vbpl_da_kiem.yaml` (quyết định 2026-09-28 mục 2) ──
from datetime import UTC, datetime  # noqa: E402

from scripts.nap_link_cong_luat import kiem_hang_da_kiem  # noqa: E402

BAY_GIO = datetime(2026, 9, 28, 12, tzinfo=UTC)
DAT = {
    "so_ky_hieu": "45/2019/QH14",
    "url": "https://vbpl.vn/van-ban/chi-tiet/139264",
    "canonical": "https://vbpl.vn/van-ban/chi-tiet/bo-luat-lao-dong-so-45-2019-qh14--139264",
    "kiem_boi": "may-doi-chieu-tieu-de",
    "kiem_luc": datetime(2026, 9, 28, 5, tzinfo=UTC),
}


def test_da_kiem_dat_tra_url():
    assert kiem_hang_da_kiem("139264", DAT, "45/2019/QH14", BAY_GIO) == DAT["url"]


def test_da_kiem_co_ly_do_la_truot_tra_None_de_xoa_link_cu():
    """Một link từng đạt nay trượt thì phải BIẾN MẤT khỏi DB, không được giữ lại."""
    assert kiem_hang_da_kiem("139264", {**DAT, "canonical": None, "ly_do": "HTTP 404"}, "45/2019/QH14", BAY_GIO) is None


def test_da_kiem_van_ban_khong_co_id_gateway_dung_id_anh_xa():
    hang = {
        **DAT,
        "so_ky_hieu": "02/2011/QH13",
        "url": "https://vbpl.vn/van-ban/chi-tiet/27325",
        "canonical": "https://vbpl.vn/van-ban/chi-tiet/luat-khieu-nai-so-02-2011-qh13--27325",
    }
    assert kiem_hang_da_kiem("cp-162374", hang, "02/2011/QH13", BAY_GIO) == hang["url"]


@pytest.mark.parametrize(
    "sua, loi",
    [
        ({"url": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=139264"}, "url"),  # mẫu cũ → trang chủ
        ({"url": "https://vbpl.vn/van-ban/chi-tiet/139265"}, "url"),  # id của văn bản khác
        ({"url": "http://vbpl.vn/van-ban/chi-tiet/139264"}, "https"),
        ({"url": "https://vbpl.vn.evil/van-ban/chi-tiet/139264"}, "host"),
        ({"canonical": "https://vbpl.vn"}, "canonical"),
        ({"canonical": "https://vbpl.vn/van-ban/chi-tiet/luat-khac--139265"}, "canonical"),
        ({"so_ky_hieu": "45/2019/QH15"}, "so_ky_hieu"),
        ({"kiem_boi": "chu-du-an"}, "kiem_boi"),
        ({"kiem_luc": datetime(2026, 9, 29, tzinfo=UTC)}, "tương lai"),
        ({"kiem_luc": date(2026, 9, 28)}, "kiem_luc"),
        ({"moj": "x"}, "khoá lạ"),
    ],
)
def test_da_kiem_tu_choi(sua, loi):
    with pytest.raises(ValueError, match=loi):
        kiem_hang_da_kiem("139264", {**DAT, **sua}, "45/2019/QH14", BAY_GIO)
