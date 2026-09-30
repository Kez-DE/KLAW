"""Nhãn tập bẫy theo phạm vi "pháp luật Việt Nam" (quyết định 2026-09-30 mục 10).

Câu nào luật điều chỉnh được hiện kèm toàn văn thì chấm "trả lời, dẫn đúng"; nhãn
cũ giữ nguyên ở `trap.truoc-pham-vi.yaml` để so với các lượt đo trước.
"""

import pytest
import yaml
from sqlalchemy import text

from eval.run_trap import TRAP_PATH, dung
from src.services.db import get_engine

CU = TRAP_PATH.with_name("trap.truoc-pham-vi.yaml")


def _items(p=TRAP_PATH) -> list[dict]:
    return yaml.safe_load(p.read_text(encoding="utf-8"))["items"]


def test_nhan_cu_duoc_giu_va_chi_nhan_doi():
    cu = {i["id"]: i for i in _items(CU)}
    moi = {i["id"]: i for i in _items()}
    assert cu.keys() == moi.keys(), "id là khoá nối các lượt đo — không được thêm/bớt/đổi"
    assert all(cu[k]["cau_hoi"] == moi[k]["cau_hoi"] for k in cu), "đổi nhãn không được đổi câu hỏi"
    doi = {k for k in cu if cu[k] != moi[k]}
    assert doi and all(cu[k]["nhom"] == "ngoai_pham_vi" for k in doi), "chỉ nhóm ngoài phạm vi được đổi nhãn"


def test_cau_trong_pham_vi_cham_bang_neo_dieu_luat():
    trong = [i for i in _items() if i["nhom"] == "trong_pham_vi"]
    assert trong
    for i in trong:
        assert i["ky_vong"] == "tra_loi_dan_dung" and i["duong_dan"], i["id"]
        st = {"result_type": "answer", "citations": [{"duong_dan": i["duong_dan"][0]}]}
        assert dung(i, st), i["id"]
        assert not dung(i, {**st, "result_type": "out_of_scope"}), i["id"]
    assert all(i["ky_vong"] == "out_of_scope" for i in _items() if i["nhom"] == "ngoai_pham_vi")


@pytest.mark.integration
def test_moi_neo_trap_phan_giai_ve_dung_MOT_provision():
    """Chống bịa, cùng phép kiểm của bộ vàng: neo phải là `provisions.duong_dan` thật."""
    can = sorted({dd for i in _items() for dd in i.get("duong_dan") or []})
    with get_engine().connect() as c:
        dem = dict(
            c.execute(
                text("SELECT duong_dan, count(*) FROM provisions WHERE duong_dan = ANY(:dd) GROUP BY duong_dan"),
                {"dd": can},
            ).all()
        )
    assert not [dd for dd in can if dd not in dem], f"neo không có trong DB: {[dd for dd in can if dd not in dem]}"
    assert not {dd: n for dd, n in dem.items() if n > 1}, "neo phân giải ra nhiều dòng"
