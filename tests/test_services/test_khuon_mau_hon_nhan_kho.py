"""Căn cứ của ba khuôn mẫu hôn nhân gia đình trên KHO THẬT — chỉ đọc, không ghi dòng nào.

`@integration`: cần Postgres có dữ liệu luật. Chạy bằng đường dẫn tệp tường minh. Khoá
lời hứa "căn cứ mở được": mọi điều khoản mục registry dẫn có trong `provisions`, và qua
đúng `graph_tra_cuu._nap_khuon_mau` của lượt chat thật, mỗi điều bắt buộc mang căn cứ
của một văn bản ĐƯỢC HIỆN, mỗi dòng căn cứ khung đủ số và ngày.
"""

import re

import pytest

from src.agents import graph_tra_cuu as g
from src.agents.graph_soan_thao import provisions_theo_duong_dan
from src.config import as_of_hieu_luc
from src.services import khuon_mau as km
from src.services.db import get_engine
from src.services.hien_thi import hien_thi_luc

pytestmark = pytest.mark.integration

LOAI = ["don_thuan_tinh_ly_hon", "thoa_thuan_chia_tai_san_chung", "thoa_thuan_nuoi_con"]


@pytest.mark.parametrize("loai", LOAI)
def test_can_cu_mo_duoc_tren_kho_that(loai):
    engine = get_engine()
    d = km.nap(loai)
    duong = {*(d.get("can_cu") or []), *(m["can_cu"] for m in d["muc"] if m.get("can_cu"))}
    co = {r["duong_dan"] for r in provisions_theo_duong_dan(frozenset(duong)).values()}
    assert co == duong, f"đường dẫn không có trong kho: {sorted(duong - co)}"
    hien = hien_thi_luc(engine, as_of_hieu_luc(None))
    ng = g._nap_khuon_mau(engine, {"soan_thao_goi_y": {"loai": loai}})["khuon_mau_ngu_canh"]
    theo = {m["key"]: m for m in ng["muc"]}
    for m in d["muc"]:
        cc = theo[m["key"]].get("can_cu")
        assert cc and cc["duong_dan"] == m["can_cu"] and cc["doc_id"] in hien, m["key"]
        assert theo[m["key"]]["trich"], "mô hình thấy nguyên văn điều luật của mục"
    if d["the_thuc"].get("can_cu"):
        assert ng["can_cu"] and all(x["doc_id"] in hien for x in ng["can_cu"])
        assert all(re.search(r"số \S+/\S+ ngày \d+ tháng \d+ năm \d{4}[;.]$", x["dong"]) for x in ng["can_cu"])
    else:
        assert ng["can_cu"] == [], "Mẫu 01-VDS không có khối căn cứ"
