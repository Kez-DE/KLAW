"""Mang phép điền sang tệp dựng lại — `ban_thao.mang_phep_sang` và thứ tự ưu tiên của
`dat_khuon_mau` (thiết kế `khuon-mau-thiet-ke.md` §3). Không DB, không LibreOffice:
bản dựng thật (`khuon_mau.dung_docx`) đọc bằng bộ đọc thật (`doc_tai_lieu.doc`).
"""

import pytest

from src.services import ban_thao
from src.services import khuon_mau as km
from src.services.doc_tai_lieu import doc
from src.services.tai_lieu import _hang_don_vi

BEN = [{"khoa": "ben_a", "vai": "Bên cho thuê", "loai": "ca_nhan"}, {"khoa": "ben_b", "vai": "Bên thuê"}]
D1 = {"key": None, "ten": "Tài sản thuê", "doan": ["Bên A cho thuê căn hộ tại ……"]}
D2 = {"key": None, "ten": "Giá thuê", "doan": ["Giá thuê …… đồng/tháng."]}
D2_MOI = {"key": None, "ten": "Giá thuê", "doan": ["Giá thuê …… đồng/tháng, trả trước ngày ……"]}
D3 = {"key": None, "ten": "Phạt vi phạm", "doan": ["Bên vi phạm chịu phạt theo thỏa thuận."]}


def _dung(dieu: list[dict]) -> tuple[list[dict], list[dict]]:
    spec = km.spec_tu(
        {**km.khung_tong_quat("hop_dong", BEN), "loai": None},
        tieu_de="Hợp đồng thuê",
        trich_yeu=None,
        can_cu=[],
        dieu=dieu,
    )
    docx, ban_do = km.dung_docx(spec)
    dv = [_hang_don_vi(d) for d in doc("k.docx", docx).don_vi]
    return dv, ban_thao.o_truong(dv, ban_do)


def _phep(o: list[dict], ben: str, truong: str, v: str) -> list[dict]:
    return ban_thao.phep_tu_gia_tri(o, {(ben, truong): v})


def _cho_dieu(dv: list[dict], chu: str) -> dict:
    d = next(d for d in dv if d["noi_dung"].startswith(chu))
    return {"loai": "dien", "don_vi": d["chi_so"], "cho_trong": 0, "gia_tri": "8.000.000"}


def test_gia_tri_cac_ben_mang_sang_khi_them_dieu_va_khoi_ky_doi_cho():
    dv1, o1 = _dung([D1, D2])
    dv2, o2 = _dung([D1, D3, D2])
    phep = _phep(o1, "ben_a", "ho_ten", "Nguyễn Văn An") + _phep(o1, "ben_b", "dien_thoai", "0912345678")
    giu, bo = ban_thao.mang_phep_sang(dv1, dv2, phep)
    assert bo == []
    moi = {(p["don_vi"], p["cho_trong"]): p["gia_tri"] for p in giu}
    mong = {
        (p["don_vi"], p["cho_trong"]): p["gia_tri"]
        for p in _phep(o2, "ben_a", "ho_ten", "Nguyễn Văn An") + _phep(o2, "ben_b", "dien_thoai", "0912345678")
    }
    assert moi == mong, "tên ở khối các bên VÀ ở khối ký (đã dời chỗ) đều mang sang"


def test_gia_tri_trong_doan_da_viet_lai_bi_bo_va_bao_ra():
    dv1, _ = _dung([D1, D2])
    dv2, _ = _dung([D1, D2_MOI])
    giu, bo = ban_thao.mang_phep_sang(dv1, dv2, [_cho_dieu(dv1, "Giá thuê ……")])
    assert giu == [] and len(bo) == 1


def test_gia_tri_trong_doan_khong_doi_van_mang_sang():
    dv1, _ = _dung([D1, D2])
    dv2, _ = _dung([D3, D1, D2])
    giu, bo = ban_thao.mang_phep_sang(dv1, dv2, [_cho_dieu(dv1, "Giá thuê ……")])
    assert bo == [] and giu[0]["don_vi"] == next(d["chi_so"] for d in dv2 if d["noi_dung"].startswith("Giá thuê"))


# ─── thứ tự ưu tiên ở bản thảo checklist (`dat_khuon_mau`) ───────────────────


@pytest.fixture
def checklist_hdld(monkeypatch):
    """`dat_khuon_mau` không DB, không LibreOffice: yêu cầu checklist rỗng, lưu tệp thành
    đọc lại bằng bộ đọc thật, mục registry có một ánh xạ fact → trường."""
    entry = {**km.nap("hdld"), "truong_tu_facts": {"ten_nld": ["nld", "ho_ten"]}}
    monkeypatch.setattr(km, "nap", lambda loai: entry)
    monkeypatch.setattr(ban_thao.graph_soan_thao, "requirements", lambda loai: ([], None, {}))
    monkeypatch.setattr(ban_thao, "hien_thi_luc", lambda engine, as_of: frozenset())
    monkeypatch.setattr(ban_thao, "get_engine", lambda: _Engine())
    tep: dict = {}

    def _luu(sub, pid, loai, tieu_de, docx):
        vid = f"viec-{len(tep) + 1}"
        dl = doc("k.docx", docx)
        tep[vid] = [_hang_don_vi(d) for d in dl.don_vi]
        return {"viec_id": vid, "don_vi": tep[vid], "don_vi_goc": dl.don_vi, "so_trang": 1, "ten_tep": "k.docx"}

    monkeypatch.setattr(ban_thao, "luu_khuon_mau", _luu)
    monkeypatch.setattr(ban_thao, "_khuon_goc", lambda c, sub, vid, **k: {"don_vi": tep.get(vid)} if vid else None)
    return tep


class _Engine:
    def connect(self):
        class _C:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _C()


def _ket(clauses=None):
    return {
        "document": "",
        "clauses": clauses
        or [{"key": "cong_viec", "ten": "Công việc", "noi_dung": "Lập trình.", "can_cu_provision_id": 0}],
        "audit_report": {"dat": True, "completeness": 1.0, "so_dieu_khoan": 1, "self_audit": True, "findings": []},
        "can_cu_co_id": [],
    }


def _gia_tri_ten(ket: dict, tep: dict) -> set[str]:
    o = {
        (x["don_vi"], x["so"])
        for x in ket["audit_report"]["khung"]["o"]
        if x["truong"] == "ho_ten" and x["ben"] == "nld"
    }
    return {p["gia_tri"].strip() for p in ket["phep_sua"] if (p["don_vi"], p["cho_trong"]) in o}


def test_fact_vua_doi_thang_gia_tri_mang_sang(checklist_hdld):
    k1 = ban_thao.dat_khuon_mau("s", "h", "hdld", {"ten_nld": "An"}, _ket())
    assert _gia_tri_ten(k1, checklist_hdld) == {"An"}
    cu = {"viec_id": k1["viec_id"], "phep_sua": k1["phep_sua"], "facts": {"ten_nld": "An"}}
    k2 = ban_thao.dat_khuon_mau("s", "h", "hdld", {"ten_nld": "Bình"}, _ket(), cu)
    assert k2["viec_id"] != k1["viec_id"] and _gia_tri_ten(k2, checklist_hdld) == {"Bình"}


def test_fact_khong_doi_thua_gia_tri_dien_tren_trang(checklist_hdld):
    k1 = ban_thao.dat_khuon_mau("s", "h", "hdld", {"ten_nld": "An"}, _ket())
    # Người dùng sửa trên trang: "An" thành "An Nguyễn" (phiên bản mới hơn fact).
    tren_trang = [{**p, "gia_tri": " An Nguyễn"} if p["gia_tri"].strip() == "An" else p for p in k1["phep_sua"]]
    cu = {"viec_id": k1["viec_id"], "phep_sua": tren_trang, "facts": {"ten_nld": "An"}}
    k2 = ban_thao.dat_khuon_mau("s", "h", "hdld", {"ten_nld": "An"}, _ket(), cu)
    assert _gia_tri_ten(k2, checklist_hdld) == {"An Nguyễn"}


def test_khong_hoi_thoai_giu_ban_html(checklist_hdld):
    ket = _ket()
    assert ban_thao.dat_khuon_mau("s", None, "hdld", {}, ket) is ket
