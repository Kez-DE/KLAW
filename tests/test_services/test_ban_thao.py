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
    assert bt3["phien_ban"] == 1 and bt3["document"].startswith("# ĐƠN\n") and bt3["phien_ban_truoc"] == []
    assert ban_thao.sua("00000000-0000-0000-0000-000000000000", bt["id"], {}, KET) is None
    for i in range(ban_thao.TRAN_SUA):
        ban_thao.sua(nguoi, bt["id"], {"ho_ten": "A", "ngay_nghi": f"{i + 1}/10/2026"}, KET)
    assert len(ban_thao.chi_tiet(nguoi, bt["id"])["phien_ban_truoc"]) == ban_thao.TRAN_SUA
    items, tong = ban_thao.danh_sach(nguoi, 10, 0)
    assert tong == 1 and items[0]["id"] == bt["id"] and items[0]["loai"] == "don_xin_nghi_viec"
    assert ban_thao.xoa_mem(nguoi, bt["id"]) is True and ban_thao.chi_tiet(nguoi, bt["id"]) is None


def test_lui_lien_tiep_di_den_ban_cu_nhat_va_tu_choi_khi_het(nguoi):
    """`lui` là một BƯỚC ĐI LÙI, không phải bật qua bật lại: tạo, sửa hai lần, lùi
    hai lần phải đi dần về ĐÚNG bản gốc (v1) với lịch sử rỗng — không dừng lại ở
    v2 rồi bật ngược lại v3. Và khi đã ở bản cũ nhất, lùi thêm phải TỪ CHỐI (trả
    về y nguyên), không làm gì bất ngờ."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    v1 = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})
    ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "3"}, {**KET, "document": "# ĐƠN v3"})

    ve_v2 = ban_thao.lui(nguoi, v1["id"])
    assert ve_v2["phien_ban"] == 2 and ve_v2["document"] == "# ĐƠN v2"

    ve_v1 = ban_thao.lui(nguoi, v1["id"])
    assert ve_v1["phien_ban"] == 1
    assert (ve_v1["document"], ve_v1["facts"], ve_v1["clauses"], ve_v1["audit"]) == (
        v1["document"],
        v1["facts"],
        v1["clauses"],
        v1["audit"],
    )
    assert ve_v1["phien_ban_truoc"] == []

    tu_choi = ban_thao.lui(nguoi, v1["id"])
    assert tu_choi == ban_thao.chi_tiet(nguoi, v1["id"])


def test_sua_sau_khi_lui_khong_dung_so_phien_ban(nguoi):
    """Lùi rồi sửa tiếp: số phiên bản mới phải LỚN HƠN mọi số đang có trong bản
    ghi, và không có hai mục nào trùng số — nhánh bị bỏ (v3 cũ) không còn tồn tại
    ở đâu để va số với v3 mới do lần sửa này tạo ra."""
    pid = hoi_thoai.tao_phien(nguoi, "đơn nghỉ việc")
    v1 = ban_thao.tao(nguoi, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "2"}, {**KET, "document": "# ĐƠN v2"})
    ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "3"}, {**KET, "document": "# ĐƠN v3 cũ"})
    ban_thao.lui(nguoi, v1["id"])  # về v2, bỏ hẳn "v3 cũ"

    moi = ban_thao.sua(nguoi, v1["id"], {"ho_ten": "A", "buoc": "3 mới"}, {**KET, "document": "# ĐƠN v3 mới"})

    so_lich_su = [b["phien_ban"] for b in moi["phien_ban_truoc"]]
    assert all(moi["phien_ban"] > so for so in so_lich_su)
    assert len(set(so_lich_su)) == len(so_lich_su), "không mục lịch sử nào trùng số phiên bản"
    assert moi["phien_ban"] not in so_lich_su


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
