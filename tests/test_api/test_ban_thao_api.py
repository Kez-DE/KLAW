"""Endpoint `/ban-thao` — danh sách, chi tiết, lùi, xoá, dựng lại (spec 2026-09-09 §8.3, Task 25)."""

import json
import uuid

import pytest
from sqlalchemy import text

from src.services import ban_thao, bao_ve, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration

KET = {
    "document": "# ĐƠN\nMục 1",
    "clauses": [{"stt": 1, "key": "nguoi_lam_don", "noi_dung": "Tôi là A"}],
    "audit_report": {"findings": [], "completeness": 1.0},
}

# `hdld` (không phải `don_xin_nghi_viec`) vì nó có rule cần fact BẮT BUỘC —
# `test_dung_thieu_du_kien_bat_buoc_422` cần một trường bỏ trống được.
FACTS_HDLD = {
    "thoi_gian_thu_viec_ngay": "30",
    "nhom_chuc_danh": "cao_dang_tro_len",
    "luong_thu_viec": "5000000",
    "luong_chinh_thuc": "6000000",
    "luong_thang": "6000000",
    "vung": "I",
    "co_dieu_khoan_phat_tien": "false",
    "co_dieu_khoan_giu_giay_to": "false",
    "co_dieu_khoan_dat_coc": "false",
}


class _KetAuditGia:
    """Đủ thuộc tính để `ban_thao.tu_state_soan_thao` đọc (thuộc tính, không phải
    khoá dict) — cùng double dùng ở `test_soan_thao_hoi_thoai_api.py`."""

    dat = True
    completeness = 1.0
    so_dieu_khoan = 0
    self_audit = True
    findings: list = []


class _GraphSoanThaoGia:
    """Thay `graph_soan_thao_cached()` mà `ban_thao.dung_lai` gọi — không chạy
    `draft_generate`/`draft_audit` thật (không tốn LLM trả phí)."""

    async def ainvoke(self, st):
        return {**st, "clauses": [], "audit_report": _KetAuditGia(), "db_provisions": {}, "traces": {}}


@pytest.fixture
def graph_soan_thao_gia(monkeypatch):
    monkeypatch.setattr(ban_thao, "graph_soan_thao_cached", lambda: _GraphSoanThaoGia())


def _cham_tran(ban_thao_id: str) -> None:
    """Đưa bản thảo tới ĐÚNG trần sửa mà không chạy `TRAN_SUA` lượt dựng thật:
    `so_lan_sua` là cột trần (migration 025), `phien_ban_truoc` chỉ là ngăn xếp
    hoàn tác — đặt cả hai để trạng thái giống hệt một bản thảo đã sửa đủ."""
    snap = {"phien_ban": 1, "document": "x", "facts": {}, "clauses": [], "audit": {}}
    with get_engine().begin() as c:
        c.execute(
            text(
                "UPDATE ban_thao SET phien_ban_truoc = CAST(:v AS jsonb), so_lan_sua = :n"
                " WHERE id = CAST(:id AS uuid)"
            ),
            {"v": json.dumps([snap] * ban_thao.TRAN_SUA), "n": ban_thao.TRAN_SUA, "id": ban_thao_id},
        )


@pytest.fixture
def hai_nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    yield a, b
    with get_engine().begin() as c:
        for s in (a, b):
            c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": s})


@pytest.mark.asyncio
async def test_danh_sach_chi_tiet_lui_xoa_va_chu_so_huu(client, khoa_ky, hai_nguoi):
    a, b = hai_nguoi
    ha, hb = _bearer(khoa_ky, a), _bearer(khoa_ky, b)
    pid = hoi_thoai.tao_phien(a, "đơn nghỉ việc")
    bt = ban_thao.tao(a, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(a, bt["id"], {"ho_ten": "A", "ngay_nghi": "15/10/2026"}, {**KET, "document": "# ĐƠN v2"})

    d = (await client.get("/api/v1/ban-thao", headers=ha)).json()
    assert d["tong"] == 1
    item = d["items"][0]
    assert item["id"] == bt["id"] and item["loai"] == "don_xin_nghi_viec" and item["hoi_thoai_id"] == pid
    assert item["phien_ban"] == 2 and "ten" in item and "cap_nhat_luc" in item

    r = await client.get(f"/api/v1/ban-thao/{bt['id']}", headers=ha)
    assert r.status_code == 200
    ct = r.json()
    assert ct["id"] == bt["id"] and ct["phien_ban"] == 2 and ct["document"] == "# ĐƠN v2"

    # Người khác không thấy gì — cùng câu trả lời với một id không tồn tại.
    assert (await client.get(f"/api/v1/ban-thao/{bt['id']}", headers=hb)).status_code == 404
    assert (await client.post(f"/api/v1/ban-thao/{bt['id']}/lui", headers=hb)).status_code == 404
    assert (await client.delete(f"/api/v1/ban-thao/{bt['id']}", headers=hb)).status_code == 404
    khong_ton_tai = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/api/v1/ban-thao/{khong_ton_tai}", headers=ha)).status_code == 404

    r = await client.post(f"/api/v1/ban-thao/{bt['id']}/lui", headers=ha)
    assert r.status_code == 200
    assert r.json()["phien_ban"] == 1

    assert (await client.delete(f"/api/v1/ban-thao/{bt['id']}", headers=ha)).status_code == 204
    assert (await client.get(f"/api/v1/ban-thao/{bt['id']}", headers=ha)).status_code == 404


@pytest.mark.asyncio
async def test_dung_sua_tang_phien_ban_va_bao_doi_so_voi_truoc(client, khoa_ky, hai_nguoi, graph_soan_thao_gia):
    """`POST /ban-thao/{id}/dung` (Task 25): facts đổi → phiên bản tăng,
    `doi_so_voi_truoc` đúng đúng trường vừa đổi; chủ khác không dựng lại được."""
    a, b = hai_nguoi
    ha, hb = _bearer(khoa_ky, a), _bearer(khoa_ky, b)
    pid = hoi_thoai.tao_phien(a, "hợp đồng lao động")
    bt = ban_thao.tao(a, pid, "hdld", FACTS_HDLD, KET)

    r = await client.post(
        f"/api/v1/ban-thao/{bt['id']}/dung",
        json={"facts": {**FACTS_HDLD, "vung": "II"}},
        headers=ha,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == bt["id"] and d["phien_ban"] == 2
    assert d["doi_so_voi_truoc"] == ["vung"]
    assert d["facts"]["vung"] == "II"

    # Chủ khác không dựng lại được — 404 y hệt một id không tồn tại.
    r_b = await client.post(f"/api/v1/ban-thao/{bt['id']}/dung", json={"facts": FACTS_HDLD}, headers=hb)
    assert r_b.status_code == 404


@pytest.mark.asyncio
async def test_dung_thieu_du_kien_bat_buoc_422(client, khoa_ky, hai_nguoi, graph_soan_thao_gia):
    """Endpoint của drawer không được là đường vòng qua ràng buộc trường bắt
    buộc mà lượt sửa bằng lời cũng phải qua (`gom_du_kien.con_thieu`)."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "hợp đồng lao động")
    bt = ban_thao.tao(a, pid, "hdld", FACTS_HDLD, KET)

    facts_thieu = {k: v for k, v in FACTS_HDLD.items() if k != "luong_thang"}
    r = await client.post(f"/api/v1/ban-thao/{bt['id']}/dung", json={"facts": facts_thieu}, headers=ha)
    assert r.status_code == 422
    assert "Lương tháng" in r.json()["detail"]


@pytest.mark.asyncio
async def test_dung_lua_chon_ngoai_danh_sach_422(client, khoa_ky, hai_nguoi, graph_soan_thao_gia):
    """`vung` chỉ nhận `I`/`II`/`III`/`IV` (`gom_du_kien.lua_chon_sai`) — lượt hỏi
    bằng lời không bao giờ sinh ra giá trị ngoài `enum` đó, nên endpoint HTTP
    (nhận facts thô, không qua ràng buộc `enum`) phải tự chặn."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "hợp đồng lao động")
    bt = ban_thao.tao(a, pid, "hdld", FACTS_HDLD, KET)

    facts_sai = {**FACTS_HDLD, "vung": "V"}
    r = await client.post(f"/api/v1/ban-thao/{bt['id']}/dung", json={"facts": facts_sai}, headers=ha)
    assert r.status_code == 422
    assert "Vùng lương tối thiểu" in r.json()["detail"]


@pytest.mark.asyncio
async def test_dung_het_tran_sua_429(client, khoa_ky, hai_nguoi, graph_soan_thao_gia):
    """Đã chạm trần `TRAN_SUA` lần sửa → 429 với thông điệp tiếng Việt
    `LOI_HET_LAN_SUA`, không phải một 500 hay một lần sửa âm thầm."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "hợp đồng lao động")
    bt = ban_thao.tao(a, pid, "hdld", FACTS_HDLD, KET)

    _cham_tran(bt["id"])

    r = await client.post(f"/api/v1/ban-thao/{bt['id']}/dung", json={"facts": FACTS_HDLD}, headers=ha)
    assert r.status_code == 429
    assert r.json()["detail"] == ban_thao.LOI_HET_LAN_SUA


@pytest.mark.asyncio
async def test_lui_khong_mo_lai_tran_sua(client, khoa_ky, hai_nguoi, graph_soan_thao_gia):
    """Đã chạm trần rồi `lui` (miễn phí, 0 token) thì `dung` (một lượt LLM trả phí)
    VẪN bị từ chối — nếu không, xen kẽ hai lệnh này là một vòng lặp tiêu tiền không
    có hạn mức nào chặn (`so_lan_sua` đơn điệu, migration 025)."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "hợp đồng lao động")
    bt = ban_thao.tao(a, pid, "hdld", FACTS_HDLD, KET)
    _cham_tran(bt["id"])

    assert (await client.post(f"/api/v1/ban-thao/{bt['id']}/lui", headers=ha)).status_code == 200

    r = await client.post(f"/api/v1/ban-thao/{bt['id']}/dung", json={"facts": FACTS_HDLD}, headers=ha)
    assert r.status_code == 429
    assert r.json()["detail"] == ban_thao.LOI_HET_LAN_SUA


@pytest.mark.asyncio
async def test_id_sai_dinh_dang_uuid_la_404(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    h = _bearer(khoa_ky, a)
    assert (await client.get("/api/v1/ban-thao/khong-phai-uuid", headers=h)).status_code == 404
    assert (await client.post("/api/v1/ban-thao/khong-phai-uuid/lui", headers=h)).status_code == 404
    assert (await client.delete("/api/v1/ban-thao/khong-phai-uuid", headers=h)).status_code == 404
    r = await client.post("/api/v1/ban-thao/khong-phai-uuid/dung", json={"facts": {}}, headers=h)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_khong_dang_nhap_401(client):
    assert (await client.get("/api/v1/ban-thao")).status_code == 401
