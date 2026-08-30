from datetime import date

import pytest
from sqlalchemy import text

from src.agents.nodes.expand import expand
from src.services.db import get_engine
from src.services.effectivity import EffectivityVerdict as V


@pytest.mark.integration
def test_khop_KHOAN_thi_tra_ve_ca_DIEU_cha():
    with get_engine().connect() as c:
        khoan = c.execute(text(
            "SELECT id, parent_id FROM provisions WHERE cap='khoan' AND parent_id IS NOT NULL LIMIT 1"
        )).mappings().one()
    deep, _ = expand([khoan["id"]], get_engine(), date(2026, 8, 27), hops=1)
    ids = {p["id"] for p in deep}
    assert khoan["parent_id"] in ids, "parent-document retrieval không hoạt động"


@pytest.mark.integration
def test_expand_1_hop_theo_reference_khong_lap_sau():
    with get_engine().connect() as c:
        row = c.execute(text(
            'SELECT from_provision_id, to_provision_id FROM "references"'
            " WHERE from_provision_id IS NOT NULL LIMIT 1")).mappings().first()
    if row is None:
        pytest.skip("chưa có cạnh cấp điều khoản")
    deep, _ = expand([row["from_provision_id"]], get_engine(), date(2026, 8, 27), hops=1)
    assert row["to_provision_id"] in {p["id"] for p in deep}


@pytest.mark.integration
def test_hops_0_thi_khong_expand_reference():
    with get_engine().connect() as c:
        row = c.execute(text(
            'SELECT from_provision_id, to_provision_id FROM "references"'
            " WHERE from_provision_id IS NOT NULL LIMIT 1")).mappings().first()
    if row is None:
        pytest.skip("chưa có cạnh")
    deep, _ = expand([row["from_provision_id"]], get_engine(), date(2026, 8, 27), hops=0)
    assert row["to_provision_id"] not in {p["id"] for p in deep}


@pytest.mark.integration
def test_tach_deep_va_shallow_theo_documents_depth():
    with get_engine().begin() as c:
        c.execute(text("UPDATE documents SET depth='shallow' WHERE id='70811'"))
        pid = c.execute(text(
            "SELECT id FROM provisions WHERE document_id='70811' LIMIT 1")).scalar_one()
    deep, shallow = expand([pid], get_engine(), date(2026, 8, 27), hops=1)
    assert pid in {p["id"] for p in shallow}
    assert pid not in {p["id"] for p in deep}
    with get_engine().begin() as c:
        c.execute(text("UPDATE documents SET depth='deep' WHERE id='70811'"))


@pytest.mark.integration
def test_moi_provision_mang_effectivity_va_so_ky_hieu_khong_mang_title():
    with get_engine().connect() as c:
        pid = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
    deep, _ = expand([pid], get_engine(), date(2026, 8, 27), hops=1)
    p = deep[0]
    assert "effectivity" in p and "so_ky_hieu" in p


# ── Yêu cầu #3 (task-7 review): 'metadata' (36 văn bản, Plan 3 Task 1) không
# có provisions thật trong DB hiện tại (đo được: 0/0), nhưng expand PHẢI tự
# loại nó khỏi CẢ HAI danh sách một cách tường minh — không dựa vào bất biến
# "metadata không có provisions" giữ mãi. Mô phỏng bằng cách gắn tạm một
# provision thật vào một document depth='metadata'.
@pytest.mark.integration
def test_depth_METADATA_khong_roi_vao_deep_lan_shallow():
    with get_engine().begin() as c:
        doc_id = c.execute(text(
            "SELECT id FROM documents WHERE depth='deep' AND id <> '70811' LIMIT 1")).scalar_one()
        c.execute(text("UPDATE documents SET depth='metadata' WHERE id=:i"), {"i": doc_id})
        pid = c.execute(text(
            "SELECT id FROM provisions WHERE document_id=:i LIMIT 1"), {"i": doc_id}).scalar_one()
    deep, shallow = expand([pid], get_engine(), date(2026, 8, 27), hops=1)
    assert pid not in {p["id"] for p in deep}
    assert pid not in {p["id"] for p in shallow}
    with get_engine().begin() as c:
        c.execute(text("UPDATE documents SET depth='deep' WHERE id=:i"), {"i": doc_id})


# ── Yêu cầu #1 (task-7 review): hiệu lực là ĐÁNH DẤU, không LỌC. Nếu expand
# loại điều hết hiệu lực khỏi tập, tầng 1 (phép kiểm 4, WARN-không-DROP) sẽ
# không bao giờ thấy nó để cảnh báo.
@pytest.mark.integration
def test_het_hieu_luc_van_O_LAI_khong_bi_LOAI_khoi_expand():
    with get_engine().begin() as c:
        pid, doc_id = c.execute(text("SELECT id, document_id FROM provisions LIMIT 1")).one()
        cu = c.execute(text(
            "SELECT ngay_het_hieu_luc FROM documents WHERE id=:i"), {"i": doc_id}).scalar_one()
        c.execute(text("UPDATE documents SET ngay_het_hieu_luc=:d WHERE id=:i"),
                  {"d": date(2000, 1, 1), "i": doc_id})
    deep, _ = expand([pid], get_engine(), date(2026, 8, 27), hops=1)
    p = next(p for p in deep if p["id"] == pid)
    assert p["id"] in {x["id"] for x in deep}, "hết hiệu lực bị LOẠI khỏi expand — phải ĐÁNH DẤU, không loại"
    assert p["effectivity"].verdict is V.het_hieu_luc
    with get_engine().begin() as c:
        c.execute(text("UPDATE documents SET ngay_het_hieu_luc=:d WHERE id=:i"), {"d": cu, "i": doc_id})


# ── Ca khoá của cả task (xem docstring module + test-verify_tier1.py::D127):
# 45/2019/QH14 > Điều 127 (141418, noi_dung CHỈ LÀ TIÊU ĐỀ) > Khoản 1 (141419)
# "Xâm phạm sức khỏe, danh dự..." / Khoản 2 (141420) "Phạt tiền, cắt lương...".
# golden_qa lao-001-0/lao-001-1: mỗi câu hỏi truy hồi RIÊNG một Khoản — expand
# phải đưa Điều 127 vào CẢ HAI trường hợp, và khi cả hai Khoản cùng có mặt thì
# Điều 127 chỉ được xuất hiện MỘT LẦN (dedup theo cha chung).
@pytest.mark.integration
def test_ca_DIEU_127_KHOAN_1_va_KHOAN_2_deu_keo_ve_DIEU_127_KHONG_TRUNG_LAP():
    deep1, _ = expand([141419], get_engine(), date(2026, 8, 27), hops=1)
    assert 141418 in {p["id"] for p in deep1}, "Khoản 1 không kéo được Điều 127"

    deep2, _ = expand([141420], get_engine(), date(2026, 8, 27), hops=1)
    assert 141418 in {p["id"] for p in deep2}, "Khoản 2 không kéo được Điều 127"

    both, _ = expand([141419, 141420], get_engine(), date(2026, 8, 27), hops=1)
    ids_both = [p["id"] for p in both]
    assert {141418, 141419, 141420} <= set(ids_both)
    assert ids_both.count(141418) == 1, "Điều 127 bị trùng lặp khi hai Khoản con cùng có mặt"
