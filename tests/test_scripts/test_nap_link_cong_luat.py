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
