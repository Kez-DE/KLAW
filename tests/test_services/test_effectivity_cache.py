"""Memo 60 s của `danh_gia_toan_bo`: cùng (engine, as_of) trong TTL → tính một lần;
hết TTL hoặc khác as_of/engine → tính lại; `xoa_cache_danh_gia_toan_bo` quên hết."""

from datetime import date
from types import SimpleNamespace

from src.services import effectivity as eff


def _engine(url: str):
    return SimpleNamespace(url=url)


def test_memo_trong_ttl_tinh_dung_mot_lan(monkeypatch):
    eff.xoa_cache_danh_gia_toan_bo()
    goi = []
    monkeypatch.setattr(eff, "_danh_gia_toan_bo_tinh", lambda e, d: goi.append(d) or {"x": "kq"})
    t = [1000.0]
    monkeypatch.setattr(eff.time, "monotonic", lambda: t[0])
    e = _engine("postgresql://a")
    assert eff.danh_gia_toan_bo(e, date(2026, 9, 6)) == {"x": "kq"}
    t[0] += 30
    assert eff.danh_gia_toan_bo(e, date(2026, 9, 6)) == {"x": "kq"}
    assert goi == [date(2026, 9, 6)]


def test_het_ttl_khac_as_of_khac_engine_deu_tinh_lai(monkeypatch):
    eff.xoa_cache_danh_gia_toan_bo()
    goi = []
    monkeypatch.setattr(eff, "_danh_gia_toan_bo_tinh", lambda e, d: goi.append((e.url, d)) or {})
    t = [0.0]
    monkeypatch.setattr(eff.time, "monotonic", lambda: t[0])
    eff.danh_gia_toan_bo(_engine("postgresql://a"), date(2026, 9, 6))
    eff.danh_gia_toan_bo(_engine("postgresql://a"), date(2026, 9, 7))  # khác as_of
    eff.danh_gia_toan_bo(_engine("postgresql://b"), date(2026, 9, 6))  # khác engine
    t[0] = 61.0
    eff.danh_gia_toan_bo(_engine("postgresql://a"), date(2026, 9, 6))  # hết TTL
    assert len(goi) == 4
    eff.xoa_cache_danh_gia_toan_bo()
    eff.danh_gia_toan_bo(_engine("postgresql://a"), date(2026, 9, 6))
    assert len(goi) == 5
