"""`eval/kiem_tran_chi.py` với HTTP giả: đóng khi vượt trần, không mạng."""

import httpx
import pytest

from eval import kiem_tran_chi


def test_kiem_tran_chi_thoat_3_khi_vuot_tran(monkeypatch, capsys):
    monkeypatch.setattr(
        kiem_tran_chi.httpx,
        "get",
        lambda url, **k: httpx.Response(
            200,
            json={"data": {"usage": 26.5, "limit": None, "limit_remaining": None}},
            request=httpx.Request("GET", url),
        ),
    )
    assert kiem_tran_chi.main([]) == 0
    assert kiem_tran_chi.main(["27.6"]) == 0
    assert kiem_tran_chi.main(["26.4"]) == 3
    assert "usage_usd 26.5" in capsys.readouterr().out


def test_kiem_tran_chi_dong_khi_khong_doc_duoc_muc_da_dung(monkeypatch):
    """Khoá sai hay mạng lỗi: thoát khác 0, lệnh tốn phí nối bằng `&&` không chạy."""
    monkeypatch.setattr(
        kiem_tran_chi.httpx, "get", lambda url, **k: httpx.Response(401, request=httpx.Request("GET", url))
    )
    with pytest.raises(httpx.HTTPStatusError):
        kiem_tran_chi.main(["27.6"])
