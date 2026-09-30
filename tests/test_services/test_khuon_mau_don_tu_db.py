"""Căn cứ của khuôn mẫu nhóm đơn từ trên KHO THẬT — CHỈ ĐỌC (`integration`, chạy bằng
đường dẫn tệp). Cùng đường `graph_tra_cuu._nap_khuon_mau` đi mỗi lượt soạn: điều khoản
của checklist (`requirements`) lọc qua quy tắc hiện (`hien_thi_luc`: tình trạng, hiệu
lực tại hôm nay, link chính thống). Mỗi mục checklist có căn cứ phải còn nguyên sau bộ
lọc ấy — không thì trang bản thảo có mục mà ngăn "Căn cứ" không mở được gì.

Bản không DB (điều khoản có thật trong `data/seed`, tình trạng còn hiệu lực) ở
`test_khuon_mau_don_tu.py`.
"""

import pytest

from src.agents import graph_soan_thao as gst
from src.config import as_of_hieu_luc
from src.services import khuon_mau as km
from src.services.db import get_engine
from src.services.hien_thi import hien_thi_luc

pytestmark = pytest.mark.integration

CO_CHECKLIST = ["don_khoi_kien", "don_khieu_nai", "don_xin_nghi_viec"]


@pytest.mark.parametrize("loai", CO_CHECKLIST)
def test_can_cu_moi_muc_la_dieu_khoan_cua_van_ban_duoc_hien(loai):
    engine = get_engine()
    _, cl, db = gst.requirements(loai)
    hien = gst.chi_van_ban_hien(db, hien_thi_luc(engine, as_of_hieu_luc(None)))
    duoc_hien = {r["duong_dan"] for r in hien.values()}
    can_cu = {m["can_cu"] for m in cl.muc if m.get("can_cu")}
    assert can_cu and can_cu <= duoc_hien, sorted(can_cu - duoc_hien)


@pytest.mark.parametrize("loai", CO_CHECKLIST)
def test_loai_co_checklist_nhung_khung_khong_in_can_cu(loai):
    """Ba mẫu đơn này không có khối căn cứ (Mẫu 23-DS, NĐ 124 Mẫu 01): dòng căn cứ của
    lượt không in ra — căn cứ chỉ mở từ ngăn "Căn cứ" của từng mục."""
    assert not km.nap(loai)["the_thuc"].get("can_cu")
