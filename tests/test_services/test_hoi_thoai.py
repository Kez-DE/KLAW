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


def test_danh_sach_khong_an_va_dem_luot(nguoi):
    ids = [hoi_thoai.tao_phien(nguoi, f"câu {i}") for i in range(3)]
    for pid in ids:
        hoi_thoai.ghi_luot(pid, "q", PAYLOAD, None)
    hoi_thoai.ghi_luot(ids[2], "q2", PAYLOAD, None)
    items, tong = hoi_thoai.danh_sach(nguoi, limit=20, offset=0)
    assert tong == 3 and [i["id"] for i in items] == list(reversed(ids))
    assert hoi_thoai.dem_luot(ids[2]) == 2 and hoi_thoai.dem_luot(ids[0]) == 1


def test_nhap_phien_tao_phien_va_ghi_dung_thu_tu(nguoi):
    pid = hoi_thoai.nhap_phien(
        nguoi,
        [
            {"cau_hoi": "Câu một?", "tra_loi": PAYLOAD, "trace_id": "t1"},
            {"cau_hoi": "Câu hai?", "tra_loi": PAYLOAD, "trace_id": None},
        ],
    )
    ct = hoi_thoai.chi_tiet(nguoi, pid)
    assert ct["tieu_de"] == "Câu một?"
    assert [(lu["thu_tu"], lu["cau_hoi"], lu["trace_id"]) for lu in ct["luot"]] == [
        (1, "Câu một?", "t1"),
        (2, "Câu hai?", None),
    ]


def test_doi_ten_va_xoa_mem(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    assert hoi_thoai.doi_ten(nguoi, pid, "Tên mới")["tieu_de"] == "Tên mới"
    assert hoi_thoai.xoa_mem(nguoi, pid) is True
    assert hoi_thoai.lay_phien(nguoi, pid) is None
    assert hoi_thoai.danh_sach(nguoi, 20, 0)[1] == 0


def test_bo_nho_phien_mac_dinh_rong_va_ghi_doc_duoc(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "câu đầu")
    bn = hoi_thoai.bo_nho_cua_phien(pid)
    assert bn == {"tom_tat": None, "tom_tat_den_thu_tu": 0, "ho_so": {}, "khong_ghi_nho": False, "user_sub": nguoi}
    hoi_thoai.ghi_bo_nho(pid, "tóm tắt", 3, {"chu_the": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}})
    bn = hoi_thoai.bo_nho_cua_phien(pid)
    assert bn["tom_tat"] == "tóm tắt" and bn["tom_tat_den_thu_tu"] == 3
    assert bn["ho_so"]["chu_the"]["gia_tri"] == "người lao động"


def test_luot_khoang_cat_tra_loi_va_theo_thu_tu(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "c1")
    for i in range(1, 5):
        hoi_thoai.ghi_luot(pid, f"c{i}", {"answer": "x" * 3000, "citations": []}, None)
    ra = hoi_thoai.luot_khoang(pid, 2, 3)
    assert [r["thu_tu"] for r in ra] == [2, 3]
    assert ra[0]["cau_hoi"] == "c2" and len(ra[0]["tra_loi"]) == hoi_thoai.TRA_LOI_TOI_DA


def test_lich_su_gan_nhat_tra_6_luot(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "c1")
    for i in range(1, 9):
        hoi_thoai.ghi_luot(pid, f"c{i}", {"answer": "a", "citations": []}, None)
    ls = hoi_thoai.lich_su_gan_nhat(pid)
    assert [l["cau_hoi"] for l in ls] == ["c3", "c4", "c5", "c6", "c7", "c8"]  # noqa: E741


def test_khong_ghi_nho_va_ho_so_khoa_theo_chu(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "c1")
    assert hoi_thoai.dat_khong_ghi_nho(nguoi, pid, True) is True
    assert hoi_thoai.bo_nho_cua_phien(pid)["khong_ghi_nho"] is True
    assert hoi_thoai.dat_khong_ghi_nho("00000000-0000-0000-0000-000000000000", pid, False) is False
    ho_so = hoi_thoai.dat_ho_so_khoa(nguoi, pid, "loai_hop_dong", "xác định thời hạn")
    assert ho_so["loai_hop_dong"] == {"gia_tri": "xác định thời hạn", "nguon": "nguoi_noi"}
    assert hoi_thoai.dat_ho_so_khoa(nguoi, pid, "loai_hop_dong", None) == {}
    assert any(p["id"] == pid and p["khong_ghi_nho"] is True for p in hoi_thoai.danh_sach(nguoi, 10, 0)[0])
