import uuid

import pytest
from sqlalchemy import text

from src.services import ban_thao, bao_ve, hoi_thoai
from src.services.db import get_engine

pytestmark = pytest.mark.integration
KET = {
    "document": "# ĐƠN\nMục 1",
    "clauses": [{"stt": 1, "key": "nguoi_lam_don", "noi_dung": "Tôi là A"}],
    "audit_report": {"findings": [], "completeness": 1.0},
}


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def test_tao_sua_lui_va_tran_sua(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    bt = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A", "ngay_nghi": "01/10/2026"}, KET)
    assert bt["phien_ban"] == 1 and bt["document"].startswith("# ĐƠN")
    bt2 = ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "ngay_nghi": "15/10/2026"}, {**KET, "document": "# ĐƠN v2"})
    assert bt2["phien_ban"] == 2 and bt2["phien_ban_truoc"][-1]["phien_ban"] == 1
    assert ban_thao.doi_so_voi(bt, bt2) == ["ngay_nghi"]
    bt3 = ban_thao.lui(nguoi, bt["id"])
    # Bản bị rời đi (v2) không được mất — `lui` đẩy nó vào lịch sử, đối xứng với `sua`.
    assert bt3["phien_ban"] == 1 and bt3["document"].startswith("# ĐƠN\n")
    assert len(bt3["phien_ban_truoc"]) == 1 and bt3["phien_ban_truoc"][0]["phien_ban"] == 2
    assert ban_thao.sua("00000000-0000-0000-0000-000000000000", bt["id"], {}, KET) is None
    for i in range(ban_thao.TRAN_SUA):
        ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "ngay_nghi": f"{i + 1}/10/2026"}, KET)
    assert len(ban_thao.chi_tiet(nguoi, bt["id"])["phien_ban_truoc"]) == ban_thao.TRAN_SUA
    items, tong = ban_thao.danh_sach(nguoi, 10, 0)
    assert tong == 1 and items[0]["id"] == bt["id"] and items[0]["loai"] == "don_xin_nghi_viec"
    assert ban_thao.xoa_mem(nguoi, bt["id"]) is True and ban_thao.chi_tiet(nguoi, bt["id"]) is None


def test_lui_giu_ban_bi_roi_va_khoi_phuc_dung_ca_clauses_audit(nguoi):
    """Tiến hai lần rồi lùi một lần: bản khôi phục phải nhất quán NỘI BỘ (document,
    facts, clauses, audit đều của ĐÚNG v2 — trước bản vá, `lui` giữ nguyên
    clauses/audit của bản đang bị rời đi thay vì khôi phục của v2), và bản bị rời đi
    (v3) phải còn lấy lại được — `lui` lần nữa phải trả về đúng NGUYÊN v3."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    ket_v2 = {
        **KET,
        "document": "# ĐƠN v2",
        "clauses": [{"stt": 1, "key": "k2", "noi_dung": "N2"}],
        "audit_report": {"findings": [], "completeness": 0.5},
    }
    ket_v3 = {
        **KET,
        "document": "# ĐƠN v3",
        "clauses": [{"stt": 1, "key": "k3", "noi_dung": "N3"}],
        "audit_report": {"findings": [], "completeness": 0.9},
    }
    v1 = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    v2 = ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "2"}, ket_v2)
    v3 = ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "3"}, ket_v3)

    ve_v2 = ban_thao.lui(nguoi, v1["id"])
    assert ve_v2["phien_ban"] == 2
    assert (ve_v2["document"], ve_v2["facts"], ve_v2["clauses"], ve_v2["audit"]) == (
        v2["document"],
        v2["facts"],
        v2["clauses"],
        v2["audit"],
    )
    v3_trong_lich_su = next(b for b in ve_v2["phien_ban_truoc"] if b["phien_ban"] == 3)
    assert (v3_trong_lich_su["document"], v3_trong_lich_su["clauses"], v3_trong_lich_su["audit"]) == (
        v3["document"],
        v3["clauses"],
        v3["audit"],
    )

    ve_v3 = ban_thao.lui(nguoi, v1["id"])
    assert ve_v3["phien_ban"] == 3
    assert (ve_v3["document"], ve_v3["clauses"], ve_v3["audit"]) == (v3["document"], v3["clauses"], v3["audit"])


def test_soan_thao_cua_phien(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    khac = "00000000-0000-0000-0000-000000000000"
    assert hoi_thoai.soan_thao_cua_phien(nguoi, pid) is None
    assert hoi_thoai.ghi_soan_thao(khac, pid, {"a": 1}) is False, "sai chủ phải fail closed, không âm thầm ghi"
    assert hoi_thoai.soan_thao_cua_phien(khac, pid) is None, "sai chủ không được đọc được state của người khác"
    assert (
        hoi_thoai.ghi_soan_thao(
            nguoi, pid, {"loai": "don_xin_nghi_viec", "facts": {"ho_ten": "A"}, "ban_thao_id": None, "so_lan_sua": 0}
        )
        is True
    )
    assert hoi_thoai.soan_thao_cua_phien(nguoi, pid)["facts"] == {"ho_ten": "A"}
    assert hoi_thoai.ghi_soan_thao(nguoi, pid, {}) is True
    assert hoi_thoai.soan_thao_cua_phien(nguoi, pid) == {}, "trạng thái rỗng-nhưng-hợp-lệ khác None"
    hoi_thoai.ghi_soan_thao(nguoi, pid, None)
    assert hoi_thoai.soan_thao_cua_phien(nguoi, pid) is None
