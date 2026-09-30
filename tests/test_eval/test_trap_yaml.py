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
        cam = i.get("cam_dan", [])
        assert not any(dd == c or dd.startswith(c + " >") for dd in i["duong_dan"] for c in cam), i["id"]
    # Năm câu luật Việt Nam mà kho chưa có toàn văn: chủ dự án chưa chọn nhãn, không chấm.
    assert {i["id"] for i in _items() if i["nhom"] == "ngoai_pham_vi" and i["ky_vong"] == "cho_duyet"} == {
        f"trap-oos-{n:02d}" for n in (2, 9, 10, 14, 15)
    }


# Bản lưu đã lỗi thời → bản đi sửa đang là câu trả lời hiện hành (đọc DB 2026-09-30).
# Neo chỉ nhận bản còn đúng; `sua_doi_dieu_khoan` không có dòng nào cho các điều này,
# nên không có gì tự đưa bản hiện hành lên thay.
_BAN_CU_THANH_BAN_SUA = {
    "trap-oos-01": ("109/2025/QH15 > Điều 7 > Khoản 1", "09/2026/QH16 > Điều 1"),  # 500 triệu → mức Chính phủ quy định
    "trap-oos-07": ("92/2015/QH13 > Điều 35", "85/2025/QH15 > Điều 1 > Khoản 2"),  # TAND cấp huyện → khu vực
    "trap-oos-08": ("123/2015/NĐ-CP > Điều 2 > Khoản 1", "18/2026/NĐ-CP > Điều 13 > Khoản 1"),  # CMND
    "trap-oos-11": ("123/2015/NĐ-CP > Điều 9 > Khoản 2", "07/2025/NĐ-CP > Điều 2 > Khoản 5"),  # giấy kết hôn
    "trap-oos-12": ("25/2008/QH12 > Điều 22", "51/2024/QH15 > Điều 1 > Khoản 17"),  # qua 46/2014 rồi 51/2024
    "trap-oos-13": ("25/2008/QH12 > Điều 12", "51/2024/QH15 > Điều 1 > Khoản 10"),
}
_BAN_TRUNG_GIAN = ["46/2014/QH13 > Điều 1 > Khoản 6", "46/2014/QH13 > Điều 1 > Khoản 15"]  # 51/2024 viết lại


def test_neo_la_ban_hien_hanh_khong_phai_ban_da_bi_thay():
    theo_id = {i["id"]: i for i in _items()}
    for id_, (cu, moi) in _BAN_CU_THANH_BAN_SUA.items():
        neo = theo_id[id_]["duong_dan"]
        assert moi in neo, id_
        assert not any(n == cu or n.startswith(cu + " >") or cu.startswith(n + " >") for n in neo), (id_, cu)
    tat_ca = {n for i in _items() for n in i.get("duong_dan") or []}
    assert not tat_ca & set(_BAN_TRUNG_GIAN)
    assert "31/2024/QH15 > Điều 236" not in tat_ca, "khoản 3 điểm a, khoản 4 đã chuyển về cấp xã (151/2025 Điều 5)"


def test_cau_dat_dai_cam_dan_dieu_bai_bo_theo_151_2025_va_toa_an_cap_huyen():
    theo_id = {i["id"]: i for i in _items()}
    for id_ in ("trap-oos-03", "trap-oos-04"):  # lượt tl dẫn 101/2024 Điều 28, 30 và 102/2024 Điều 106, 107
        cam = theo_id[id_]["cam_dan"]
        assert {"101/2024/NĐ-CP > Điều 28", "101/2024/NĐ-CP > Điều 30"} <= set(cam), id_
        assert {"102/2024/NĐ-CP > Điều 106", "102/2024/NĐ-CP > Điều 107"} <= set(cam), id_
    assert "126/2014/NĐ-CP > Điều 25" in theo_id["trap-oos-08"]["cam_dan"], "123/2015 Điều 45 khoản 2 điểm đ"
    for id_ in ("trap-oos-04", "trap-oos-06", "trap-oos-07"):
        assert "cấp huyện" in theo_id[id_]["cam_nhac"], id_


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
    cam = sorted({c for i in _items() for c in i.get("cam_dan") or []})
    with get_engine().connect() as c:
        thieu = [
            p
            for p in cam
            if not c.execute(
                text("SELECT 1 FROM provisions WHERE duong_dan = :p OR duong_dan LIKE :p || ' >%' LIMIT 1"), {"p": p}
            ).first()
        ]
    assert not thieu, f"tiền tố cam_dan không khớp điều khoản nào (gõ sai?): {thieu}"
