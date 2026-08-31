"""Test CHẤT LƯỢNG tập golden_qa, không chỉ schema (spec 11.1, Task 8).

`test_moi_item_da_qua_review_cua_NGUOI` cố ý đỏ/deselect. Trường `duyet_boi`
(`chua-ai` | `agent` | `nguoi`) mang sự thật về AI đã duyệt; chỉ chủ dự án mới có
quyền đặt `true` sau khi tự đọc từng câu. Đánh dấu `pending_review` để không
chặn CI trước khi việc review tay đó xảy ra; xem pyproject.toml.

`test_moi_provision_id_ton_tai_trong_DB_va_duong_dan_khop` cần Postgres thật
— một id bịa sẽ làm Recall@k sai mà không ai biết, nên đánh dấu `integration`
và tra thẳng bảng `provisions`, không tin dữ liệu tự khai trong YAML.
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


def test_moi_item_co_id_duy_nhat_va_provision_ids_khong_rong():
    items = _load()
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)), "id trùng"
    assert all(i["provision_ids"] for i in items), "có item không có ground truth"


def test_provision_ids_va_duong_dan_song_song_cung_do_dai():
    xau = [i["id"] for i in _load() if len(i["provision_ids"]) != len(i["duong_dan"])]
    assert not xau, f"provision_ids và duong_dan lệch độ dài: {xau}"


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
    da = [i["id"] for i in _load() if len(i["provision_ids"]) > 1]
    assert len(da) >= 5, f"chỉ {len(da)} câu có >1 provision_ids, cần ≥5"


def test_it_nhat_8_van_ban_khac_nhau_duoc_phu():
    van_ban = {dd.split(" > ")[0] for i in _load() for dd in i["duong_dan"]}
    assert len(van_ban) >= 8, f"chỉ phủ {len(van_ban)} văn bản: {van_ban}"


@pytest.mark.integration
def test_moi_provision_id_ton_tai_trong_DB_va_duong_dan_khop():
    """Chống bịa: provision_ids phải là provisions.id THẬT, và duong_dan trong
    YAML phải khớp nguyên văn duong_dan lưu trong DB cho đúng id đó."""
    items = _load()
    tat_ca_id = {pid for i in items for pid in i["provision_ids"]}
    with get_engine().connect() as c:
        rows = c.execute(
            text("SELECT id, duong_dan FROM provisions WHERE id = ANY(:ids)"),
            {"ids": list(tat_ca_id)},
        ).all()
    duong_dan_that = dict(rows)

    thieu = tat_ca_id - duong_dan_that.keys()
    assert not thieu, f"provision_ids không tồn tại trong DB: {thieu}"

    lech = [
        (i["id"], pid, dd, duong_dan_that[pid])
        for i in items
        for pid, dd in zip(i["provision_ids"], i["duong_dan"], strict=True)
        if duong_dan_that[pid] != dd
    ]
    assert not lech, f"duong_dan trong YAML lệch với DB (item, id, yaml, db): {lech}"
