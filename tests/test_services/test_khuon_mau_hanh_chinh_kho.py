"""Căn cứ của khuôn mẫu nhóm hành chính trên KHO THẬT — chỉ ĐỌC (không ghi DB).

`@integration`: cần Postgres đã nạp corpus; chạy bằng đường dẫn tệp tường minh. Khoá hai
điều của thiết kế `khuon-mau-thiet-ke.md` §2, §5 cho từng loại có checklist:

1. Mỗi dòng căn cứ khung in ra là một văn bản ĐƯỢC HIỆN, còn hiệu lực, đủ số và ngày
   (`can_cu_van_ban_co_id`) — và đúng những dòng ấy lên trang.
2. Căn cứ của mỗi điều khoản (mục checklist ngoài khung) mở được: `duong_dan` của nó là
   một điều khoản của văn bản được hiện.
"""

import re

import pytest

from src.agents import graph_soan_thao as gst
from src.config import as_of_hieu_luc
from src.services import khuon_mau as km
from src.services.db import get_engine
from src.services.hien_thi import hien_thi_luc
from tests.test_services.test_khuon_mau_hanh_chinh import _doan_than

pytestmark = pytest.mark.integration

LOAI = sorted(lo for lo in km.cac_loai() if lo in gst.cac_loai() and km.nap(lo)["bo_cuc"] == "hanh_chinh") + [
    "giay_uy_quyen",
    "van_ban_giai_trinh",
]
_RE_DU = re.compile(r"số \d+/\d{4}/[\wĐ-]+ ngày \d{1,2} tháng \d{1,2} năm \d{4}")


def _kho(loai: str):
    e = get_engine()
    as_of = as_of_hieu_luc(None)
    hien = hien_thi_luc(e, as_of)
    _, cl, db = gst.requirements(loai)
    db_hien = gst.chi_van_ban_hien(db, hien)
    return cl, db_hien, gst.can_cu_van_ban_co_id(e, db_hien, as_of), hien


@pytest.mark.parametrize("loai", LOAI)
def test_dong_can_cu_khung_la_van_ban_duoc_hien_du_so_ngay_va_len_trang(loai):
    _, _, dong, hien = _kho(loai)
    for x in dong:
        assert x["doc_id"] in hien, x
        assert _RE_DU.search(x["dong"]), x["dong"]
        assert not re.search(r"Nghị định số 30/2020", x["dong"]), "NĐ 30 chỉ là nguồn thể thức"
    entry = km.nap(loai)
    docx, _ = km.dung_docx(km.spec_tu(entry, tieu_de=None, trich_yeu=None, can_cu=dong, dieu=[]))
    chu = [c for _, c, _ in _doan_than(docx)]
    in_ra = [c for c in chu if _RE_DU.search(c)]
    if (entry.get("ban_hanh") or entry)["the_thuc"].get("can_cu"):
        assert [re.sub(r"[;.]$", "", c) for c in in_ra] == [re.sub(r"[;.]$", "", x["dong"]) for x in dong]
    else:
        assert in_ra == [], "mẫu không có khối căn cứ (công văn, biên bản, đơn) thì không in dòng nào"


@pytest.mark.parametrize("loai", LOAI)
def test_can_cu_cua_moi_dieu_khoan_mo_duoc(loai):
    cl, db_hien, _, _ = _kho(loai)
    co = {r["duong_dan"] for r in db_hien.values()}
    khung = km.khoa_khung(km.nap(loai))
    thieu = [m["key"] for m in cl.muc if m["key"] not in khung and m["can_cu"] not in co]
    assert thieu == [], f"mục có căn cứ không mở được: {thieu}"


@pytest.mark.parametrize(
    "loai", [lo for lo in LOAI if (km.nap(lo).get("ban_hanh") or km.nap(lo))["the_thuc"].get("lenh")]
)
def test_moi_quyet_dinh_nghi_quyet_co_it_nhat_mot_dong_can_cu_luat(loai):
    """Quyết định 2026-09-29 mục 7: căn cứ lấy từ kho, đủ số, ngày, cơ quan. Quyết định hay
    nghị quyết ("QUYẾT ĐỊNH:"/"QUYẾT NGHỊ:") ra đời không dòng luật nào là thiếu căn cứ."""
    _, _, dong, _ = _kho(loai)
    assert dong, loai
