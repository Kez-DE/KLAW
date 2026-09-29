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
