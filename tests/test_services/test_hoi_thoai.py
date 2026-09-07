"""Dịch vụ phiên hội thoại (spec 2026-09-07 §4, §5.1) — chạy trên DB thật, dọn theo `sub`."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine

pytestmark = pytest.mark.integration

PAYLOAD = {
    "result_type": "answer",
    "answer": "Thử việc tối đa 180 ngày.",
    "warnings": [],
    "coverage_note": None,
    "nguon": [],
    "bang": [],
    "documents": [],
    "soan_thao": None,
    "citations": [
        {
            "provision_id": 1,
            "khop_tai_id": 1,
            "doc_id": "d",
            "duong_dan": "45/2019/QH14 > Điều 25 > Khoản 1",
            "bo_luat": "BLLĐ",
            "so_ky_hieu": "45/2019/QH14",
            "quote": "…",
            "hieu_luc": "con_hieu_luc",
            "tin_cay": None,
            "k": 1,
        }
    ],
}


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, f"{sub[:8]}@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = :s"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = :s"), {"s": sub})


def test_tieu_de_mac_dinh_cat_80_tai_ranh_gioi_tu():
    ngan = "Thử việc tối đa bao lâu?"
    assert hoi_thoai.tieu_de_mac_dinh(ngan) == ngan
    dai = " ".join(["từ"] * 60)
    t = hoi_thoai.tieu_de_mac_dinh(dai)
    assert len(t) <= 81 and t.endswith("…") and not t[:-1].endswith(" ")


def test_tao_ghi_va_lich_su_theo_thu_tu(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "Câu một?")
    assert hoi_thoai.lay_phien(nguoi, pid)["tieu_de"] == "Câu một?"
    assert hoi_thoai.ghi_luot(pid, "Câu một?", PAYLOAD, "t1") == 1
    assert hoi_thoai.ghi_luot(pid, "Câu hai?", PAYLOAD, "t2") == 2
    ls = hoi_thoai.lich_su_gan_nhat(pid, 3)
    assert [l["cau_hoi"] for l in ls] == ["Câu một?", "Câu hai?"]  # noqa: E741
    assert ls[0]["tra_loi"] == "Thử việc tối đa 180 ngày."
    assert ls[0]["duong_dan"] == ["45/2019/QH14 > Điều 25 > Khoản 1"]
    ct = hoi_thoai.chi_tiet(nguoi, pid)
    assert [l["thu_tu"] for l in ct["luot"]] == [1, 2] and ct["luot"][1]["trace_id"] == "t2"  # noqa: E741


def test_phien_cua_nguoi_khac_la_None(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    assert hoi_thoai.lay_phien(str(uuid.uuid4()), pid) is None
    assert hoi_thoai.chi_tiet(str(uuid.uuid4()), pid) is None
    assert hoi_thoai.xoa_mem(str(uuid.uuid4()), pid) is False


def test_free_giu_N_phien_gan_nhat_va_xoa_thi_hien_lai(nguoi, monkeypatch):
    monkeypatch.setattr(hoi_thoai, "phien_luu_toi_da", lambda plan: 3)  # gói thu nhỏ để test nhanh
    ids = [hoi_thoai.tao_phien(nguoi, f"câu {i}") for i in range(5)]
    for pid in ids:  # cập nhật cap_nhat_luc tăng dần theo thứ tự tạo
        hoi_thoai.ghi_luot(pid, "q", PAYLOAD, None)
    items, tong_hien, tong_an = hoi_thoai.danh_sach(nguoi, "free", limit=20, offset=0)
    assert (tong_hien, tong_an) == (3, 2)
    assert [i["id"] for i in items] == list(reversed(ids[2:]))
    assert hoi_thoai.phien_bi_an(nguoi, "free", ids[0]) is True
    assert hoi_thoai.phien_bi_an(nguoi, "free", ids[4]) is False
    assert hoi_thoai.xoa_mem(nguoi, ids[4]) is True
    items, tong_hien, tong_an = hoi_thoai.danh_sach(nguoi, "free", limit=20, offset=0)
    assert (tong_hien, tong_an) == (3, 1) and hoi_thoai.phien_bi_an(nguoi, "free", ids[1]) is False


def test_doi_ten_va_xoa_mem(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    assert hoi_thoai.doi_ten(nguoi, pid, "Tên mới")["tieu_de"] == "Tên mới"
    assert hoi_thoai.xoa_mem(nguoi, pid) is True
    assert hoi_thoai.lay_phien(nguoi, pid) is None
    assert hoi_thoai.danh_sach(nguoi, "free", 20, 0)[1] == 0
