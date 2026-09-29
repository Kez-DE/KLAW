"""Bản thảo CHECKLIST cũng là một tệp .docx — thiết kế `khuon-mau-thiet-ke.md` §3
("Checklist drafts also become docx"). Không DB, không LibreOffice, không mô hình:
graph soạn thảo giả, bộ dựng và bộ đọc thật, chỗ lưu giả.
"""

import pytest

from src.agents.nodes.draft_generate import DraftClause
from src.services import ban_thao
from src.services import khuon_mau as km
from src.services.doc_tai_lieu import doc
from src.services.tai_lieu import _hang_don_vi


class _Audit:
    dat, completeness, so_dieu_khoan, self_audit, findings = True, 1.0, 1, True, []


class _Graph:
    async def ainvoke(self, st):
        return {
            "loai": st["loai"],
            "clauses": [DraftClause("cong_viec", "Điều 1. Công việc", "Lập trình viên tại [địa điểm].", 1)],
            "audit_report": _Audit(),
            "db_provisions": {},
            "can_cu_van_ban": ["Căn cứ X."],
            "can_cu_co_id": [
                {"dong": "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019.", "doc_id": "139264"}
            ],
            "traces": {"draft_generate_cost_usd": 0.002},
        }


@pytest.fixture
def moi_truong(monkeypatch):
    tep: dict = {}
    ghi: dict = {}

    def _luu(sub, pid, loai, tieu_de, docx):
        vid = f"viec-{len(tep) + 1}"
        dl = doc("k.docx", docx)
        tep[vid] = [_hang_don_vi(d) for d in dl.don_vi]
        return {"viec_id": vid, "don_vi": tep[vid], "don_vi_goc": dl.don_vi, "so_trang": 1, "ten_tep": "k.docx"}

    class _C:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Engine:
        def connect(self):
            return _C()

    row = {"db": {1: {"id": 1, "document_id": "139264", "duong_dan": "45/2019/QH14 > Điều 21 > Khoản 1 > Điểm c"}}}
    monkeypatch.setattr(ban_thao, "luu_khuon_mau", _luu)
    monkeypatch.setattr(ban_thao, "_khuon_goc", lambda c, sub, vid, **k: {"don_vi": tep.get(vid)} if vid else None)
    monkeypatch.setattr(ban_thao.graph_soan_thao, "requirements", lambda loai: ([], None, row["db"]))
    monkeypatch.setattr(ban_thao, "hien_thi_luc", lambda engine, as_of: frozenset({"139264"}))
    monkeypatch.setattr(ban_thao, "get_engine", lambda: _Engine())
    monkeypatch.setattr(ban_thao, "graph_soan_thao_cached", lambda: _Graph())
    monkeypatch.setattr(ban_thao, "_ghi_traces", lambda *a, **k: None)

    def _sua(sub, id, facts, ket, *, tang=1, doi=None):
        ghi["ket"], ghi["doi"] = ket, doi
        return {
            "id": id,
            "phien_ban": 2,
            "viec_id": ket.get("viec_id"),
            "phep_sua": ket.get("phep_sua"),
            "document": ket["document"],
            "clauses": ket["clauses"],
            "audit": ket["audit_report"],
            "facts": facts,
        }

    monkeypatch.setattr(ban_thao, "sua", _sua)
    return tep, ghi


async def test_sua_facts_dung_tep_moi_khong_bao_gio_ve_html(moi_truong, monkeypatch):
    tep, ghi = moi_truong
    cu = {
        "id": "b1",
        "loai": "hdld",
        "hoi_thoai_id": "h1",
        "so_lan_sua": 0,
        "facts": {"luong_thang": "1"},
        "viec_id": None,
        "phep_sua": None,
    }
    monkeypatch.setattr(ban_thao, "chi_tiet", lambda sub, id: cu)
    bt = await ban_thao.dung_lai("s", "b1", {"luong_thang": "2"})
    ket = ghi["ket"]
    assert ket["viec_id"] == "viec-1" and bt["viec_id"] == "viec-1"
    assert ket["clauses"][0]["ten"] == "Công việc", "số đầu tên điều của mô hình bị bỏ"
    assert ket["clauses"][0]["doan"] == [f"Lập trình viên tại {km.CHO}."]
    assert ket["clauses"][0]["can_cu"] == {
        "duong_dan": "45/2019/QH14 > Điều 21 > Khoản 1 > Điểm c",
        "doc_id": "139264",
        "khop_tai_id": 1,
    }
    assert ket["audit_report"]["khung"]["can_cu"][0]["doc_id"] == "139264"
    assert "Căn cứ Bộ luật Lao động số 45/2019/QH14" in ket["document"]
    assert ghi["doi"] == ["luong_thang"] and bt["doi_so_voi_truoc"] == ["luong_thang"]
    # Lần sửa thứ hai: lại một tệp MỚI (tệp cũ ở lại cho Lùi).
    cu.update(viec_id="viec-1", phep_sua=ket["phep_sua"], facts={"luong_thang": "2"})
    await ban_thao.dung_lai("s", "b1", {"luong_thang": "3"})
    assert ghi["ket"]["viec_id"] == "viec-2" and set(tep) == {"viec-1", "viec-2"}


async def test_ban_thao_ngoai_hoi_thoai_giu_html(moi_truong, monkeypatch):
    _, ghi = moi_truong
    monkeypatch.setattr(
        ban_thao,
        "chi_tiet",
        lambda sub, id: {
            "id": "b1",
            "loai": "hdld",
            "hoi_thoai_id": None,
            "so_lan_sua": 0,
            "facts": {},
            "viec_id": None,
        },
    )
    await ban_thao.dung_lai("s", "b1", {})
    assert "viec_id" not in ghi["ket"] and ghi["doi"] is None


def test_xem_ban_thao_tim_ca_ban_checklist_tren_khuon():
    """`_SQL_MOI_NHAT_KHUON` không lọc `loai` nữa: "cho tôi xem bản thảo" thấy cả bản
    thảo checklist nằm trên một khuôn mẫu."""
    sql = str(ban_thao._SQL_MOI_NHAT_KHUON)
    assert "loai = :loai" not in sql and "viec_id IS NOT NULL" in sql


# ─── tệp không dựng được SAU lượt sinh trả phí: chi phí vẫn ghi, lượt vẫn đếm ─────


def _ban(*a):
    raise ban_thao.KhuonMauChuaDungError(ban_thao.LOI_KHUON_MAU_BAN)


async def test_sua_tep_khong_dung_duoc_van_ghi_chi_phi_va_tinh_lan_sua(moi_truong, monkeypatch):
    """`draft_generate` đã chạy (trả phí) thì dòng traces mang chi phí của nó — trần chi phí
    ngày đọc `traces` — với `result_type` "loi" (không trừ lượt), và lần thử TÍNH vào
    `TRAN_SUA`: không thì drawer lặp lại mãi, mỗi lần một lượt trả phí không ai đếm."""
    _, ghi = moi_truong
    cu = {"id": "b1", "loai": "hdld", "hoi_thoai_id": "h1", "so_lan_sua": 0, "facts": {}, "viec_id": None}
    monkeypatch.setattr(ban_thao, "chi_tiet", lambda sub, id: cu)
    monkeypatch.setattr(ban_thao, "luu_khuon_mau", _ban)
    traces, dem = [], []
    monkeypatch.setattr(ban_thao, "_ghi_traces", lambda *a, **k: traces.append((a, k)))
    monkeypatch.setattr(ban_thao, "tinh_lan_sua_hong", lambda sub, id: dem.append((sub, id)))
    with pytest.raises(ban_thao.KhuonMauChuaDungError):
        await ban_thao.dung_lai("s", "b1", {"luong_thang": "2"})
    assert "ket" not in ghi, "không lưu phiên bản nào"
    ((a, k),) = traces
    assert a[4] == {"result_type": "loi", "traces": {"draft_generate_cost_usd": 0.002}} and k["user_sub"] == "s"
    assert dem == [("s", "b1")]


async def test_tao_tep_khong_dung_duoc_van_ghi_chi_phi_khong_luu(monkeypatch):
    from src.agents import graph_tra_cuu as g

    monkeypatch.setattr(g, "llm_from_settings", lambda: None)
    monkeypatch.setattr(g, "embedder_from_settings", lambda: None)
    monkeypatch.setattr(g, "Retriever", lambda *a: None)
    monkeypatch.setattr(g, "get_engine", lambda: None)
    monkeypatch.setattr(g.bao_ve, "plan_hieu_luc", lambda sub: "free")
    monkeypatch.setattr(g.bao_ve, "kiem_han_muc", lambda *a: None)
    monkeypatch.setattr(g, "graph_soan_thao_cached", lambda: _Graph())
    monkeypatch.setattr(g.ban_thao, "dat_khuon_mau", _ban)
    tao, traces = [], []
    monkeypatch.setattr(g.ban_thao, "tao", lambda *a: tao.append(a))
    monkeypatch.setattr(g, "_ghi_traces", lambda *a, **k: traces.append((a, k)))
    node = g.build_graph_tra_cuu().builder.nodes["dung_ban_thao"].runnable.afunc
    ra = await node({"soan_thao_dang_mo": {"loai": "hdld", "facts": {}}, "user_sub": "s", "hoi_thoai_id": "h"})
    assert ra["soan_thao_dang_mo"]["het_han_muc"] == ban_thao.LOI_KHUON_MAU_BAN and tao == []
    ((a, k),) = traces
    assert a[1] == g.bao_ve.EP_SOAN_THAO and a[4]["result_type"] == "loi"
    assert a[4]["traces"] == {"draft_generate_cost_usd": 0.002} and k["user_sub"] == "s"
