"""Test CHẤT LƯỢNG tập golden_qa, không chỉ schema (spec 11.1, Task 8).

`test_moi_item_da_qua_review_cua_NGUOI` cố ý đỏ/deselect. Trường `duyet_boi`
(`chua-ai` | `agent` | `nguoi`) mang sự thật về AI đã duyệt; chỉ chủ dự án mới có
quyền đặt `true` sau khi tự đọc từng câu. Đánh dấu `pending_review` để không
chặn CI trước khi việc review tay đó xảy ra; xem pyproject.toml.

`test_moi_duong_dan_phan_giai_duoc_ve_dung_MOT_provision` cần Postgres thật —
một neo bịa sẽ làm Recall@k sai mà không ai biết, nên đánh dấu `integration` và
tra thẳng bảng `provisions`, không tin dữ liệu tự khai trong YAML.

Ground truth của tập này là `duong_dan`, KHÔNG phải `provisions.id`. Bản trước
mang cả hai và id là bản sao dẫn xuất: `provisions.id` là BIGSERIAL nên nó dịch
sau mỗi lần sửa parser hoặc mở rộng corpus, và khi nó dịch thì `eval/run.py`
tính Recall trên một tập gold không tồn tại rồi trả 0,0 — bảng số liệu tụt mà
không dòng lỗi nào chỉ ra vì sao. Id nay được `eval.run.phan_giai_gold` phân
giải từ `duong_dan` ngay trước khi chạy, và neo không phân giải được là lỗi.
"""

import re
from pathlib import Path

import pytest
import yaml
from sqlalchemy import text

from src.services.db import get_engine

P = Path("eval/datasets/golden_qa.yaml")
THUAT_NGU = ["quy định tại", "theo quy định của pháp luật", "nghĩa vụ thông báo",
             "đơn phương chấm dứt", "người sử dụng lao động"]


def _load() -> list[dict]:
    return yaml.safe_load(P.read_text(encoding="utf-8"))["items"]


def test_moi_item_co_id_duy_nhat_va_duong_dan_khong_rong():
    items = _load()
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)), "id trùng"
    assert all(i["duong_dan"] for i in items), "có item không có ground truth"


def test_YAML_KHONG_mang_provisions_id():
    """`provisions.id` là BIGSERIAL — ghi nó vào dataset là ghim một con số sẽ
    chết ở lần nạp lại kế tiếp, và chết IM LẶNG (Recall=0, không lỗi)."""
    co = [i["id"] for i in _load() if "provision_ids" in i]
    assert not co, f"item còn mang provision_ids ghi cứng: {co[:5]}"


def test_cau_hoi_KHONG_chua_so_dieu():
    """Câu hỏi chứa "Điều 25" thì retrieval quá dễ, không test được pain point #3."""
    xau = [i["id"] for i in _load() if re.search(r"Điều\s+\d+", i["cau_hoi"])]
    assert not xau, f"các item nêu thẳng số điều: {xau}"


def test_it_nhat_80_phan_tram_cau_hoi_khong_dung_thuat_ngu_phap_ly():
    items = _load()
    sach = [i for i in items if not any(t in i["cau_hoi"].lower() for t in THUAT_NGU)]
    ty_le = len(sach) / len(items)
    assert ty_le >= 0.8, f"chỉ {ty_le:.0%} câu hỏi dùng giọng dân sinh, cần ≥80%"


@pytest.mark.pending_review
def test_moi_item_da_qua_review_cua_NGUOI():
    """`da_review: true` KHÔNG còn nghĩa là người duyệt.

    Một agent đã duyệt 66/77 câu (2026-09-01) và đặt `da_review: true`. Nếu test
    này chỉ kiểm `da_review` thì nó xanh cho 66 câu **không người nào đọc** —
    một test mang tên "review của người" mà không kiểm điều đó là một lời nói
    dối, và khóa luận sẽ trích dẫn con số nó tạo ra.

    `duyet_boi` mang sự thật: `chua-ai` | `agent` | `nguoi`. Test này chỉ xanh
    khi CON NGƯỜI đã xác nhận — hiện đỏ trên cả 77, đúng như thực tế.
    """
    chua = [i["id"] for i in _load() if i.get("duyet_boi") != "nguoi"]
    assert not chua, f"chưa có người duyệt ({len(chua)}/77): {chua[:8]}…"


@pytest.mark.pending_review
def test_moi_item_da_qua_review_cua_AI_DO():
    """Cổng yếu hơn: đã có ai đó (agent hoặc người) duyệt. Đỏ trên 11 câu
    SAI/THIẾU mà agent cố ý không tự quyết — chúng cần phán quyết pháp lý."""
    chua = [i["id"] for i in _load() if i.get("duyet_boi") == "chua-ai"]
    assert not chua, f"chưa ai duyệt: {chua}"


def test_dot_1_co_it_nhat_50_cau_va_toan_bo_thuoc_lao_dong():
    items = _load()
    assert len(items) >= 50
    assert all(i["bo_luat"] == "Lao động" for i in items), "đợt 1 chỉ Lao động"


def test_it_nhat_5_cau_can_nhieu_hon_1_provision_id():
    """Câu hỏi thật (vd mức lương tối thiểu) thường cần vài điều luật cùng lúc."""
    da = [i["id"] for i in _load() if len(i["duong_dan"]) > 1]
    assert len(da) >= 5, f"chỉ {len(da)} câu có >1 neo, cần ≥5"


def test_it_nhat_8_van_ban_khac_nhau_duoc_phu():
    van_ban = {dd.split(" > ")[0] for i in _load() for dd in i["duong_dan"]}
    assert len(van_ban) >= 8, f"chỉ phủ {len(van_ban)} văn bản: {van_ban}"


@pytest.mark.integration
def test_moi_duong_dan_phan_giai_duoc_ve_dung_MOT_provision():
    """Chống bịa: mỗi neo trong YAML phải là một `provisions.duong_dan` THẬT, và
    phải phân giải về đúng MỘT dòng — cùng phép phân giải `eval/run.py` chạy."""
    from eval.run import phan_giai_gold

    items = _load()
    can = sorted({dd for i in items for dd in i["duong_dan"]})
    with get_engine().connect() as c:
        dem = dict(c.execute(
            text("SELECT duong_dan, count(*) FROM provisions"
                 " WHERE duong_dan = ANY(:dd) GROUP BY duong_dan"), {"dd": can}).all())
    thieu = [dd for dd in can if dd not in dem]
    assert not thieu, f"{len(thieu)}/{len(can)} neo không có trong DB: {thieu[:5]}"
    trung = {dd: n for dd, n in dem.items() if n > 1}
    assert not trung, f"neo phân giải ra nhiều dòng — Recall sẽ tính sai: {trung}"

    # Và phép phân giải THẬT chạy được, không chỉ truy vấn tương đương ở trên.
    da_giai = phan_giai_gold(get_engine(), items)
    assert all(len(i["provision_ids"]) == len(i["duong_dan"]) for i in da_giai)
