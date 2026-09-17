"""Endpoint `/ban-thao` — danh sách, chi tiết, lùi, xoá, dựng lại (spec 2026-09-09 §8.3, Task 25)."""

import json
import uuid

import pytest
from fastapi import HTTPException
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

# S6 — bản thảo TỔNG QUÁT (`loai = "tong_quat"`, plan `ban-thao-tong-quat.md`
# Task 1): không checklist nào để tra `ten`. Dựng `document` qua CHÍNH
# `ban_thao._render_markdown`, đúng cách `dung_ban_thao_tong_quat.py:154` dựng
# một dòng thật — không gõ tay một khuôn Markdown khác có thể trôi lệch.
CLAUSES_TONG_QUAT = [
    {"key": "muc_1", "ten": "Điều 1", "noi_dung": "Nội dung 1"},
    {"key": "muc_2", "ten": "Điều 2", "noi_dung": "Nội dung 2"},
    {"key": "muc_3", "ten": "Điều 3", "noi_dung": "Nội dung 3"},
]
KET_TONG_QUAT = {
    "document": ban_thao._render_markdown(ban_thao.LOAI_TONG_QUAT, CLAUSES_TONG_QUAT, "Văn bản thử"),
    "clauses": CLAUSES_TONG_QUAT,
    "audit_report": {
        "dat": None,
        "completeness": None,
        "so_dieu_khoan": len(CLAUSES_TONG_QUAT),
        "self_audit": False,
        "findings": [],
        "muc_kiem": "tong_quat",
    },
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
async def test_ban_thao_tong_quat_chi_tiet_200(client, khoa_ky, hai_nguoi):
    """Task 1: `GET /ban-thao/{id}` trên một bản thảo `tong_quat` phải trả 200,
    không phải 500 — trước bản vá, `_out()` gọi thẳng
    `load_checklist_cached("tong_quat")`, và hàm đó nổ `ValueError: loai không
    có checklist` vì không có `config/checklist_tong_quat.yaml` nào (S6 không
    theo checklist nào, đúng định nghĩa)."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "văn bản tổng quát")
    bt = ban_thao.tao(a, pid, ban_thao.LOAI_TONG_QUAT, {}, KET_TONG_QUAT)

    r = await client.get(f"/api/v1/ban-thao/{bt['id']}", headers=ha)
    assert r.status_code == 200
    ct = r.json()
    assert ct["ten"] == "Bản thảo tổng quát"
    assert ct["loai"] == "tong_quat"
    assert ct["clauses"] == CLAUSES_TONG_QUAT


@pytest.mark.asyncio
async def test_ban_thao_tong_quat_trong_danh_sach_200(client, khoa_ky, hai_nguoi):
    """Task 1: `GET /ban-thao` phải liệt kê được một bản thảo `tong_quat` —
    trước bản vá, `danh_sach()` gọi `load_checklist_cached(i["loai"]).ten` cho
    MỖI dòng, nên một bản thảo tổng quát của tài khoản làm nổ 500 cho CẢ danh
    sách, kể cả khi các bản thảo checklist khác của cùng người vẫn hợp lệ."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "văn bản tổng quát")
    bt = ban_thao.tao(a, pid, ban_thao.LOAI_TONG_QUAT, {}, KET_TONG_QUAT)

    r = await client.get("/api/v1/ban-thao", headers=ha)
    assert r.status_code == 200
    d = r.json()
    assert d["tong"] == 1
    assert d["items"][0]["id"] == bt["id"]
    assert d["items"][0]["ten"] == "Bản thảo tổng quát"


@pytest.mark.asyncio
async def test_ban_thao_tong_quat_lui_200(client, khoa_ky, hai_nguoi):
    """Task 1: `POST /ban-thao/{id}/lui` ở `phien_ban > 1` phải trả 200.
    `ban_thao.lui` (tầng service) không hề gọi `load_checklist_cached` — phục
    hồi một bản thảo tổng quát về phiên bản trước đã được hỗ trợ sẵn ở tầng
    service; chỉ tầng route (`_out()`) là chỗ nổ. Nếu chủ trương là KHÔNG cho
    lùi bản thảo tổng quát thì đây là chỗ phải đổi assertion sang mã cố ý,
    không phải giữ nguyên một 500 không định trước."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "văn bản tổng quát")
    bt = ban_thao.tao(a, pid, ban_thao.LOAI_TONG_QUAT, {}, KET_TONG_QUAT)
    clauses_v2 = [{**c, "noi_dung": c["noi_dung"] + " (sửa)"} for c in CLAUSES_TONG_QUAT]
    ban_thao.sua(a, bt["id"], {}, {**KET_TONG_QUAT, "clauses": clauses_v2})

    r = await client.post(f"/api/v1/ban-thao/{bt['id']}/lui", headers=ha)
    assert r.status_code == 200
    assert r.json()["phien_ban"] == 1


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


@pytest.mark.asyncio
async def test_dung_tu_choi_khi_cham_tran_chi_phi_ngay(client, khoa_ky, hai_nguoi, graph_soan_thao_gia, monkeypatch):
    """`dung` chạy `draft_generate` trên model trả phí nhưng KHÔNG đếm vào hạn mức
    soạn thảo (spec §8.4), nên trần chi phí NGÀY là cổng cuối trước ví tiền — cùng
    cổng mà `cong_bao_ve` gọi cho `/tra-cuu` và `/soan-thao`, cùng hình dạng lỗi."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "hợp đồng lao động")
    bt = ban_thao.tao(a, pid, "hdld", FACTS_HDLD, KET)

    def _het_tien():
        raise HTTPException(status_code=429, detail="Đã đạt trần chi phí ngày (2.0 USD; đã dùng 2.10000 USD).")

    monkeypatch.setattr(bao_ve, "kiem_tran_chi_phi", _het_tien)
    r = await client.post(f"/api/v1/ban-thao/{bt['id']}/dung", json={"facts": FACTS_HDLD}, headers=ha)
    assert r.status_code == 429
    assert "trần chi phí ngày" in r.json()["detail"]


@pytest.mark.asyncio
async def test_dung_tu_choi_facts_qua_bien_422(client, khoa_ky, hai_nguoi, graph_soan_thao_gia):
    """Biên `facts` (số khoá, kiểu, độ dài chuỗi) phải chặn TẠI HTTP, trước lượt
    LLM trả phí, và `detail` phải là CHUỖI tiếng Việt như hai lỗi 422 anh em —
    xem `routes_ban_thao.loi_facts_ngoai_bien`."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "hợp đồng lao động")
    bt = ban_thao.tao(a, pid, "hdld", FACTS_HDLD, KET)

    for facts, cum in (
        ({**FACTS_HDLD, "ghi_chu": "x" * 501}, "ghi_chu"),
        ({**FACTS_HDLD, "ghi_chu": {"long": "dong"}}, "ghi_chu"),
        ({**FACTS_HDLD, **{f"k{i}": "x" for i in range(40)}}, "tối đa"),
    ):
        r = await client.post(f"/api/v1/ban-thao/{bt['id']}/dung", json={"facts": facts}, headers=ha)
        assert r.status_code == 422
        assert isinstance(r.json()["detail"], str) and cum in r.json()["detail"]


@pytest.mark.asyncio
async def test_dung_tu_choi_facts_trung_ten_tham_so_rule_422(client, khoa_ky, hai_nguoi, graph_soan_thao_gia):
    """Cùng 422 mà `/soan-thao` trả cho khoá trùng tên tham số của rule
    (`routes._validate_facts`) — cửa này không được là đường vòng qua nó."""
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "hợp đồng lao động")
    bt = ban_thao.tao(a, pid, "hdld", FACTS_HDLD, KET)

    r = await client.post(
        f"/api/v1/ban-thao/{bt['id']}/dung",
        json={"facts": {**FACTS_HDLD, "bang_thang": 0}},
        headers=ha,
    )
    assert r.status_code == 422
    assert "bang_thang" in r.text
