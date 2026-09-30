from datetime import date

import pytest
from sqlalchemy import text

from src.agents.nodes.expand import _duong_dan_di_sua, expand
from src.services.db import get_engine
from src.services.effectivity import EffectivityVerdict as V
from tests.conftest import pid


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


# ── Task-9 ruling (2026-08-31): `d.ten` thêm vào `_SQL_PROV` để tầng assemble
# hiển thị "Bộ luật Lao động" cạnh trích dẫn — CHỈ hiển thị, không định danh
# (`so_ky_hieu` vẫn là khoá duy nhất, xem test trên). Không có `ten` thì
# `assemble.Citation.bo_luat` luôn rỗng trên dữ liệu thật.
@pytest.mark.integration
def test_moi_provision_mang_ten_KHONG_RONG_de_hien_thi():
    with get_engine().connect() as c:
        pid = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
    deep, _ = expand([pid], get_engine(), date(2026, 8, 27), hops=1)
    p = deep[0]
    assert p.get("ten"), "d.ten vắng hoặc rỗng — assemble sẽ hiển thị bo_luat rỗng"


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
# Điều 127 chỉ được xuất hiện MỘT LẦN (dedup theo cha chung). CẢ HAI CHIỀU
# (task-7 review, 2026-08-31): cho Khoản → có Điều cha (đã có từ đầu); và
# NGƯỢC LẠI, cho Điều 127 một mình → phải có CẢ Khoản 1 và Khoản 2 (mới thêm).
@pytest.mark.integration
def test_ca_DIEU_127_KHOAN_1_va_KHOAN_2_deu_keo_ve_DIEU_127_KHONG_TRUNG_LAP():
    d127 = pid("45/2019/QH14 > Điều 127")
    k1 = pid("45/2019/QH14 > Điều 127 > Khoản 1")
    k2 = pid("45/2019/QH14 > Điều 127 > Khoản 2")

    deep1, _ = expand([k1], get_engine(), date(2026, 8, 27), hops=1)
    assert d127 in {p["id"] for p in deep1}, "Khoản 1 không kéo được Điều 127"

    deep2, _ = expand([k2], get_engine(), date(2026, 8, 27), hops=1)
    assert d127 in {p["id"] for p in deep2}, "Khoản 2 không kéo được Điều 127"

    both, _ = expand([k1, k2], get_engine(), date(2026, 8, 27), hops=1)
    ids_both = [p["id"] for p in both]
    assert {d127, k1, k2} <= set(ids_both)
    assert ids_both.count(d127) == 1, "Điều 127 bị trùng lặp khi hai Khoản con cùng có mặt"

    # chiều ngược: chỉ đưa Điều 127 (không đưa Khoản nào) — phải TỰ kéo về cả
    # Khoản 1 và Khoản 2, không chỉ giữ nguyên dòng tiêu đề trơ trọi.
    deep3, _ = expand([d127], get_engine(), date(2026, 8, 27), hops=1)
    ids3 = {p["id"] for p in deep3}
    assert {d127, k1, k2} <= ids3, "Điều 127 không kéo được Khoản 1 và Khoản 2 con"


# ── Ca đo được trên đường chạy thật (task-7 review, 2026-08-31): retrieval
# (Plan 2) neo 3.093 chunk ở cấp `dieu`, chỉ 190 ở `khoan` — 5 id thật dưới đây
# là r.hybrid_provisions() thật của một truy vấn thật, cả 5 đều cấp `dieu`,
# 4/5 chỉ-tiêu-đề (<120 ký tự). TRƯỚC bản sửa này expand(5 id) -> 5, không
# thêm gì (chỉ có chiều con→cha, mà không id nào là con). Giờ PHẢI có ít nhất
# một Khoản/Điểm con mang nội dung thật.
@pytest.mark.integration
def test_5_DIEU_that_tu_san_xuat_PHAI_co_it_nhat_mot_con_mang_noi_dung_that():
    ids = [pid(d) for d in ("100/2015/QH13 > Điều 155", "100/2015/QH13 > Điều 391",
                            "101/2015/QH13 > Điều 73", "101/2015/QH13 > Điều 186",
                            "92/2015/QH13 > Điều 492")]
    deep, _ = expand(ids, get_engine(), date(2026, 8, 27), hops=1)
    con_that = [p for p in deep if p["id"] not in ids and len(p.get("noi_dung") or "") > 120]
    assert con_that, "expand không kéo được Khoản/Điểm con mang nội dung thật cho ca dieu-only thật"


# ══ CRITICAL 2 (silent-failure review round 2) — logic thuần, KHÔNG integration ═
# 0% code của expand.py từng chạy trong CI (`-m "not integration"` loại sạch cả
# 10 test cũ). Bốn test dưới đây khoá đúng bốn hành vi tối thiểu, thuần Python,
# không cần Postgres.

from src.agents.nodes.expand import _chia_deep_shallow, _mo_rong_cha, _mo_rong_con_hai_muc  # noqa: E402


def test_thuan_con_den_cha_khoan_diem_keo_ve_dieu():
    """Bước 1: Khoản 5 (con) → kéo về Điều 10 (cha) — chiều con→cha."""
    assert _mo_rong_cha({5}, [10]) == {5, 10}


def test_thuan_cha_den_con_dieu_keo_ve_khoan_diem_hai_muc():
    """Bước 2: Điều 10 (cha) → con 11,12 rồi cháu 13 — chiều cha→con, CHẶN Ở
    HAI MỨC (không đệ quy thêm dù đồ thị còn sâu hơn)."""
    assert _mo_rong_con_hai_muc({10}, [11, 12], [13]) == {10, 11, 12, 13}


def test_thuan_khu_trung_id_da_co_khong_nhan_ban():
    """Id đã có mặt (vd. đã là cha của chính nó qua path khác) không bị thêm
    trùng — set union tự khử trùng."""
    assert _mo_rong_cha({5, 10}, [10, 10, None]) == {5, 10}
    assert _mo_rong_con_hai_muc({10, 11}, [11, 12], [12]) == {10, 11, 12}


def test_thuan_hieu_luc_DANH_DAU_khong_LOC_ke_ca_het_hieu_luc():
    """Provision hết hiệu lực VẪN xuất hiện trong deep — hiệu lực chỉ đính
    kèm, không bao giờ là lý do loại (module docstring: 'ĐÁNH DẤU, không LỌC')."""
    rows = [{"id": 1, "depth": "deep"}]
    eff = {1: V.het_hieu_luc}
    deep, shallow = _chia_deep_shallow(rows, lambda pid: eff[pid], {1: 0})
    assert len(deep) == 1 and deep[0]["effectivity"] == V.het_hieu_luc
    assert shallow == []


def test_thuan_deep_shallow_khong_tron_va_metadata_bi_loai_ca_hai():
    rows = [{"id": 1, "depth": "deep"}, {"id": 2, "depth": "shallow"}, {"id": 3, "depth": "metadata"}]
    deep, shallow = _chia_deep_shallow(rows, lambda pid: None, {1: 0, 2: 1, 3: 2})
    assert [r["id"] for r in deep] == [1]
    assert [r["id"] for r in shallow] == [2]
    assert all(r["id"] != 3 for r in deep + shallow), "'metadata' phải bị loại khỏi CẢ HAI, không rơi vào deep"


def test_thuan_sap_theo_do_uu_tien_ban_dau():
    rows = [{"id": 20, "depth": "deep"}, {"id": 10, "depth": "deep"}]
    deep, _ = _chia_deep_shallow(rows, lambda pid: None, {10: 0, 20: 1})
    assert [r["id"] for r in deep] == [10, 20]


# ══ Bước 0 — điều khoản BỊ SỬA kéo theo điều khoản ĐI SỬA ════════════════════
# `effectivity` nói được "Điều 139 Khoản 1 bị sửa bởi 113/2025/QH15 từ
# 2026-07-01" từ trước; cái nó KHÔNG nói được là nội dung mới. Nội dung mới nằm
# trong điều khoản đi sửa, và trước bước 0 nó chỉ vào context khi truy hồi tình
# cờ bắt được. Đo 2026-09-01 trên 3 ca thật: 2 bắt được, 1 TRƯỢT.


def test_thuan_doc_so_dieu_tu_cau_tieng_viet_cua_ban_do_sua_doi():
    assert _duong_dan_di_sua([("113/2025/QH15", "khoản 1 Điều 29")]) == [
        "113/2025/QH15 > Điều 29"]
    assert _duong_dan_di_sua([("124/2025/QH15", "điểm a khoản 1 Điều 43")]) == [
        "124/2025/QH15 > Điều 43"]


def test_thuan_dieu_co_hau_to_chu_giu_nguyen_hau_to():
    """"Điều 33a" là điều do luật sửa CHÈN. Cắt hậu tố sẽ neo sang Điều 33 —
    một điều luật khác hẳn, và không ai thấy vì cả hai đều tồn tại."""
    assert _duong_dan_di_sua([("x/2026/QH15", "khoản 2 Điều 33a")]) == [
        "x/2026/QH15 > Điều 33a"]


def test_thuan_khong_doc_duoc_so_dieu_thi_KHONG_neo_bua():
    """`can_doi_chieu_tay` để `sua_boi_duong_dan` NULL và bị lọc ở SQL. Chuỗi
    lệch khuôn lọt tới đây thì thà không mở rộng còn hơn đoán một Điều."""
    assert _duong_dan_di_sua([("x/2026/QH15", "bãi bỏ toàn bộ")]) == []
    assert _duong_dan_di_sua([("x/2026/QH15", "")]) == []


@pytest.mark.integration
def test_dieu_bi_sua_keo_theo_NOI_DUNG_MOI_o_luat_di_sua():
    """Ca trung tâm: hỏi Điều 139 BLLĐ thì Điều 29 của 113/2025/QH15 — nơi chứa
    câu "nghỉ thai sản … 07 tháng" — phải nằm trong context, và phải kéo được
    cả Khoản con của nó (bước 0 chạy TRƯỚC bước cha→con)."""
    goc = pid("45/2019/QH14 > Điều 139")
    deep, _ = expand([goc], get_engine(), date(2026, 9, 1), hops=0)
    dd = {p["duong_dan"] for p in deep}
    assert "113/2025/QH15 > Điều 29" in dd
    assert "113/2025/QH15 > Điều 29 > Khoản 1" in dd, "bước 0 phải chạy trước cha→con"


@pytest.mark.integration
def test_dieu_khong_co_ban_ghi_sua_doi_KHONG_keo_theo_gi_them():
    """Đối chứng: bản đồ không lan sang điều khoản không có bản ghi. `Điều 140`
    là em ruột của `Điều 139` trong cùng Chương."""
    deep, _ = expand([pid("45/2019/QH14 > Điều 140")], get_engine(), date(2026, 9, 1), hops=0)
    assert not [p for p in deep if p["duong_dan"].startswith("113/2025/QH15")]


@pytest.mark.integration
def test_khoan_cua_dieu_bi_sua_ca_dieu_keo_theo_NOI_DUNG_MOI():
    """Trace c8a98c3d: 64/2025/QH15 Điều 4 bị 87/2025/QH15 sửa CẢ Điều. Chỉ trúng
    một khoản cũ của nó ("cấp huyện") vẫn phải đưa danh sách mới vào context."""
    deep, _ = expand([pid("64/2025/QH15 > Điều 4 > Khoản 13")], get_engine(), date(2026, 9, 30), hops=0)
    assert "87/2025/QH15 > Điều 1 > Khoản 1" in {p["duong_dan"] for p in deep}


# ══ Pha 3a (spec 2026-09-02 §7) ══════════════════════════════════════════════
@pytest.mark.integration
def test_moi_provision_mang_loai_van_ban_de_generate_claims_ap_thu_bac():
    """`_SQL_PROV` phải select `d.loai_van_ban`: `build_context` cần nó để model
    phân biệt Bộ luật với Thông tư mà áp thứ bậc hiệu lực. Đây là NGUỒN duy nhất
    — không có cột này trong bản ghi thì bối cảnh không thể có, bất kể prompt
    viết gì. Như `d.ten`, nó CHỈ để model đọc, `so_ky_hieu` vẫn là khoá định
    danh duy nhất."""
    with get_engine().connect() as c:
        p_id = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
    deep, _ = expand([p_id], get_engine(), date(2026, 8, 27), hops=1)
    assert deep[0].get("loai_van_ban"), "d.loai_van_ban vắng hoặc rỗng — build_context không có gì để đưa"


# ══ Quyết định 2026-09-28 — trích dẫn đầy đủ ════════════════════════════════
@pytest.mark.integration
def test_dong_deep_va_shallow_mang_cot_trich_dan_day_du():
    """Nguồn của `partial_coverage` (dòng shallow) và của `documents[]` cần cơ
    quan, ngày, link — đọc ở ĐÂY, không phải một lượt truy vấn thứ hai. Cột có
    thể NULL (tầng shallow đang được điền) nhưng KHOÁ phải có."""
    with get_engine().connect() as c:
        pid = c.execute(text("SELECT id FROM provisions WHERE document_id = '139264' LIMIT 1")).scalar_one()
    deep, _ = expand([pid], get_engine(), date(2026, 8, 27), hops=0)
    p = next(r for r in deep if r["document_id"] == "139264")
    for k in ("co_quan_ban_hanh", "ngay_ban_hanh", "ngay_hieu_luc", "link_vbpl", "link_chinhphu"):
        assert k in p, k
    assert p["ngay_ban_hanh"] == date(2019, 11, 20)


@pytest.mark.integration
def test_db_provisions_mang_cot_trich_dan_day_du():
    from src.agents.graph_tra_cuu import _db_provisions

    with get_engine().connect() as c:
        pid = c.execute(text("SELECT id FROM provisions WHERE document_id = '139264' LIMIT 1")).scalar_one()
    p = _db_provisions([pid], get_engine())[pid]
    assert (p["co_quan_ban_hanh"], p["ngay_ban_hanh"]) == ("Quốc hội", date(2019, 11, 20))
    assert "ngay_hieu_luc" in p and "link_vbpl" in p
