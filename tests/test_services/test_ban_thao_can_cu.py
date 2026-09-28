"""Khối "Căn cứ" của bản thảo checklist (quyết định 2026-09-28, mục 5).

Bản thảo checklist/HTML mở đầu bằng khối "Căn cứ" theo khuôn lời mở đầu của
chính văn bản luật, chỉ dẫn văn bản CÒN hiệu lực, không kèm câu khẳng định hiệu
lực. Bản thảo tổng quát (không checklist) và bản thảo trên khuôn gốc KHÔNG có
khối này — luật chủ dự án: soạn lại là đúng 100% tệp tải lên.

Phần đầu THUẦN (không DB); phần `integration` chạy trên kho thật, 0 lượt LLM.
"""

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from src.agents import graph_soan_thao as gst
from src.agents.nodes.draft_generate import DraftClause
from src.services import ban_thao, bao_ve, hoi_thoai
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V

KHOI = [
    "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;",
    "Căn cứ Nghị định số 293/2025/NĐ-CP ngày 10 tháng 11 năm 2025 của Chính phủ quy định mức lương tối thiểu.",
]
MUC = [{"ten": "Công việc và địa điểm làm việc", "noi_dung": "Nhân viên kinh doanh tại Hà Nội."}]


def test_render_checklist_dat_khoi_can_cu_ngay_sau_tieu_de_truoc_muc_dau():
    md = ban_thao._render_markdown("hdld", MUC, can_cu=KHOI)
    assert md.startswith(f"# HỢP ĐỒNG LAO ĐỘNG\n\n{KHOI[0]}\n\n{KHOI[1]}\n\n## Điều 1. ")
    # Đường soạn-rồi-soát: khối nằm TRƯỚC dòng "Điều 1." nên không thành một mục.
    assert gst._split_dieu(md) == [f"## Điều 1. {MUC[0]['ten']}\n\n{MUC[0]['noi_dung']}"]
    assert ban_thao._render_markdown("hdld", MUC) == "# HỢP ĐỒNG LAO ĐỘNG\n\n## Điều 1. " + (
        f"{MUC[0]['ten']}\n\n{MUC[0]['noi_dung']}\n"
    ), "không có căn cứ thì văn bản y như trước"


def test_ban_thao_tong_quat_va_khuon_goc_KHONG_co_khoi_can_cu():
    md = ban_thao._render_markdown(ban_thao.LOAI_TONG_QUAT, MUC, "BIÊN BẢN", can_cu=KHOI)
    assert "Căn cứ" not in md and ban_thao.can_cu_tu_document(md) == []
    khuon = ban_thao.tom_tat_khuon("Giấy", {"cho_trong": [{"don_vi": 0, "so": 0, "nhan": "Căn cứ", "gia_tri": "x"}]})
    assert ban_thao.can_cu_tu_document(khuon) == []


def test_can_cu_tu_document_doc_lai_dung_khoi_da_dung():
    assert ban_thao.can_cu_tu_document(ban_thao._render_markdown("hdld", MUC, can_cu=KHOI)) == KHOI
    assert ban_thao.can_cu_tu_document(ban_thao._render_markdown("hdld", MUC)) == []
    assert ban_thao.can_cu_tu_document(None) == [] and ban_thao.can_cu_tu_document("") == []


def _st(**them):
    bao_cao = SimpleNamespace(dat=True, completeness=1.0, so_dieu_khoan=1, self_audit=True, findings=[])
    return {
        "loai": "hdld",
        "clauses": [DraftClause("cong_viec", MUC[0]["ten"], MUC[0]["noi_dung"], 1)],
        "db_provisions": {},
        "audit_report": bao_cao,
        **them,
    }


def test_tu_state_soan_thao_dua_khoi_vao_document_va_ket():
    ket = ban_thao.tu_state_soan_thao(_st(can_cu_van_ban=KHOI))
    assert ket["can_cu_van_ban"] == KHOI and KHOI[0] in ket["document"]
    assert [c["key"] for c in ket["clauses"]] == ["cong_viec"], "khối căn cứ KHÔNG phải một mục của clauses"
    ket = ban_thao.tu_state_soan_thao(_st())
    assert ket["can_cu_van_ban"] == [] and "Căn cứ" not in ket["document"]


# ─────────────────────────────────────────────────────── kho thật, 0 LLM


def _so_ky_hieu_duoc_hien() -> set[str]:
    """Số hiệu của văn bản được hiện hôm nay (quyết định 2026-09-28 mục 8): khối
    "Căn cứ" chỉ dẫn chúng, nên kỳ vọng của test đi theo tập này, không theo kho."""
    from src.services.db import get_engine
    from src.services.hien_thi import hien_thi_luc

    with get_engine().connect() as c:
        return set(
            c.execute(
                text("SELECT so_ky_hieu FROM documents WHERE id = ANY(CAST(:h AS text[]))"),
                {"h": list(hien_thi_luc(get_engine(), date(2026, 9, 28)))},
            ).scalars()
        )


@pytest.mark.integration
def test_ban_thao_HDLD_dan_BLLD_45_2019_va_nghi_dinh_luong_toi_thieu():
    from src.services.db import get_engine

    db = gst.load_requirements(get_engine(), "hdld")[2]
    khoi = gst.can_cu_van_ban(get_engine(), db, date(2026, 9, 28))
    assert khoi[0] == "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;", khoi
    assert any(d.startswith("Căn cứ Nghị định số 293/2025/NĐ-CP ngày ") and "của Chính phủ" in d for d in khoi), khoi
    assert khoi[-1].endswith(".") and all(d.endswith(";") for d in khoi[:-1])
    assert not any("hiệu lực" in d for d in khoi), "khối căn cứ không phán về hiệu lực"
    hien = _so_ky_hieu_duoc_hien()
    assert len(khoi) <= len({r["document_id"] for r in db.values() if r["so_ky_hieu"] in hien}), (
        "mỗi văn bản được hiện nhiều nhất một dòng"
    )


@pytest.mark.integration
def test_van_ban_het_hieu_luc_bi_bo_khoi_can_cu(monkeypatch):
    from src.services.db import get_engine

    db = gst.load_requirements(get_engine(), "hdld")[2]
    nd = next(r["document_id"] for r in db.values() if r["so_ky_hieu"] == "293/2025/NĐ-CP")
    that = gst.danh_gia_theo_id
    monkeypatch.setattr(
        gst,
        "danh_gia_theo_id",
        lambda e, i, a: Effectivity(V.het_hieu_luc, "cao", "ngày hết hiệu lực đã qua") if i == nd else that(e, i, a),
    )
    khoi = gst.can_cu_van_ban(get_engine(), db, date(2026, 9, 28))
    assert khoi and not any("293/2025" in d for d in khoi), khoi
    assert khoi[-1].endswith(".")


@pytest.mark.integration
@pytest.mark.parametrize(
    ("loai", "mong"),
    [
        ("cong_van", []),
        ("quyet_dinh_hdqt", []),
        ("quy_che_noi_bo", []),
        ("quyet_dinh_bo_nhiem", ["Căn cứ Luật Doanh nghiệp số 59/2020/QH14 ngày 17 tháng 6 năm 2020."]),
        ("giay_uy_quyen", ["Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm 2015."]),
    ],
)
def test_nguon_the_thuc_ND_30_2020_khong_thanh_can_cu(loai, mong):
    """Năm checklist này dẫn NĐ 30/2020 cho thể thức (Đ8.2, Đ7). Checklist tự ghi
    nó không quy định nội dung và Đ2.1 không với tới doanh nghiệp tư nhân — in nó
    thành căn cứ ban hành là bịa căn cứ (checklist_quyet_dinh_bo_nhiem.yaml mục 6)."""
    from src.services.db import get_engine

    db = gst.load_requirements(get_engine(), loai)[2]
    assert any(r["so_ky_hieu"] == "30/2020/NĐ-CP" for r in db.values()), "tiền đề: checklist có dẫn NĐ 30/2020"
    hien = _so_ky_hieu_duoc_hien()
    mong = [m for m in mong if any(sk in m for sk in hien)]
    assert gst.can_cu_van_ban(get_engine(), db, date(2026, 9, 28)) == mong


@pytest.fixture
def nguoi():
    from src.services.db import get_engine

    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


@pytest.mark.integration
def test_sua_tay_ban_thao_checklist_GIU_khoi_can_cu_cua_phien_ban(nguoi):
    ket = ban_thao.tu_state_soan_thao(_st(can_cu_van_ban=KHOI))
    bt = ban_thao.tao(nguoi, hoi_thoai.tao_phien(nguoi, "hđlđ"), "hdld", {}, ket)
    moi = ban_thao.sua_tay(nguoi, bt["id"], "cong_viec", 0, "Kế toán tại Đà Nẵng.", bt["phien_ban"])
    assert isinstance(moi, dict), moi
    assert "Kế toán tại Đà Nẵng." in moi["document"]
    assert ban_thao.can_cu_tu_document(moi["document"]) == KHOI


def test_ban_thao_out_tra_khoi_can_cu_cho_giao_dien_xuat_tep():
    """Giao diện dựng tệp tải về từ `clauses` + khung checklist, không từ
    `document` — nên khối phải đi ra thành một trường riêng, đọc từ `document`."""
    from src.api import routes_ban_thao as rbt

    ket = ban_thao.tu_state_soan_thao(_st(can_cu_van_ban=KHOI))
    bt = {
        "id": str(uuid.uuid4()),
        "loai": "hdld",
        "phien_ban": 1,
        "document": ket["document"],
        "clauses": ket["clauses"],
        "audit": ket["audit_report"],
        "facts": {},
    }
    assert rbt._out(bt).can_cu_van_ban == KHOI
    assert rbt._out({**bt, "document": "# HỢP ĐỒNG LAO ĐỘNG\n"}).can_cu_van_ban == [], "bản lưu trước khối: rỗng"


# ───────────────────── căn cứ gốc thuộc văn bản ẩn (quyết định 2026-09-28 mục 8)


class _LlmDem:
    """Mô hình giả đếm lượt gọi: lượt `draft_generate` là một lượt trả phí thật."""

    def __init__(self):
        self.goi = 0

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage

        self.goi += 1
        return '{"clauses": []}', Usage(0, 0, 0.0)


def _graph(monkeypatch, loai: str, db: dict, hien: frozenset[str]):
    llm = _LlmDem()
    cl = gst.load_checklist_cached(loai)
    monkeypatch.setattr(gst, "llm_from_settings", lambda: llm)
    monkeypatch.setattr(gst, "requirements", lambda _loai: ([], cl, db))
    monkeypatch.setattr(gst, "hien_thi_luc", lambda engine, as_of: hien)
    monkeypatch.setattr(gst, "get_engine", lambda: None)
    monkeypatch.setattr(gst, "can_cu_van_ban", lambda engine, db, as_of: [])
    return gst.build_graph_soan_thao(), llm, cl


def test_can_cu_goc_thuoc_van_ban_an_thi_dung_truoc_luot_LLM(monkeypatch):
    """7/29 mẫu mất trọn nguồn và `thoa_thuan_bao_mat` mất căn cứ gốc (TT 10/2020
    chưa có link chính thống, đo 2026-09-28). Soạn tiếp là trả tiền một lượt LLM
    để ra một bản thảo không có căn cứ mà người đọc mở được."""
    cl = gst.load_checklist_cached("cong_van")
    db = {1: {"id": 1, "document_id": "an", "duong_dan": cl.can_cu_goc, "so_ky_hieu": "30/2020/NĐ-CP"}}
    graph, llm, _ = _graph(monkeypatch, "cong_van", db, frozenset())
    with pytest.raises(gst.KhongSoanDuocError) as loi:
        graph.invoke({"loai": "cong_van", "loai_van_ban": "cong_van", "facts": {}})
    assert llm.goi == 0
    cau = str(loi.value)
    assert cl.ten in cau and "30/2020" not in cau and "chưa xác định" not in cau.lower(), cau


def test_can_cu_goc_duoc_hien_thi_van_soan_du_mat_nguon_phu(monkeypatch):
    cl = gst.load_checklist_cached("hop_dong_mua_ban")
    db = {
        1: {"id": 1, "document_id": "song", "duong_dan": cl.can_cu_goc, "so_ky_hieu": "91/2015/QH13"},
        2: {"id": 2, "document_id": "an", "duong_dan": "36/2005/QH11 > Điều 301", "so_ky_hieu": "36/2005/QH11"},
    }
    graph, llm, _ = _graph(monkeypatch, "hop_dong_mua_ban", db, frozenset({"song"}))
    st = graph.invoke({"loai": "hop_dong_mua_ban", "loai_van_ban": "hop_dong_mua_ban", "facts": {}})
    assert llm.goi == 1 and set(st["db_provisions"]) == {1}


def test_finding_KHONG_dan_can_cu_cua_van_ban_an():
    """`db_provisions` đã lọc theo tập được hiện: căn cứ vắng khỏi chỉ mục là căn
    cứ của văn bản ẩn — không nêu nó, cả ở `/soan-thao` lẫn `/soat`."""
    from src.agents.nodes.draft_audit import AuditFinding
    from src.api import routes

    idx = {"91/2015/QH13 > Điều 430": {"id": 7, "document_id": "song"}}
    an = AuditFinding("trai_luat", "chan", "Mức phạt vượt trần", can_cu={"duong_dan": "36/2005/QH11 > Điều 301"})
    song = AuditFinding("thieu_noi_dung", "chan", "Thiếu", can_cu={"duong_dan": "91/2015/QH13 > Điều 430"})
    for f_out in (routes._finding_out, ban_thao._finding_out):
        assert (f_out(an, idx)["can_cu"], f_out(an, idx)["doc_id"]) == (None, None)
        assert (f_out(song, idx)["can_cu"], f_out(song, idx)["khop_tai_id"]) == ("91/2015/QH13 > Điều 430", 7)


async def test_soan_thao_mau_khong_soan_duoc_tra_422_noi_ro_khong_ghi_chi_phi(monkeypatch):
    """Cửa `/soan-thao`: lời từ chối thường, 4xx (giao diện hiện `detail` chuỗi), không 500."""
    from fastapi import HTTPException

    from src.api import routes

    class _G:
        async def ainvoke(self, st):
            raise gst.KhongSoanDuocError("Hiện chưa soạn được Công văn.")

    ghi: list = []

    async def _ghi(*a, **k):
        ghi.append(a)

    monkeypatch.setattr(routes, "_g_soan_thao", lambda: _G())
    monkeypatch.setattr(routes, "_ghi_traces_nhe", _ghi)
    req = routes.SoanThaoRequest(loai_van_ban="cong_van", facts={})
    with pytest.raises(HTTPException) as loi:
        await routes.soan_thao(req, None)
    assert (loi.value.status_code, loi.value.detail) == (422, "Hiện chưa soạn được Công văn.")
    assert ghi == [], "không lượt LLM nào chạy thì không có gì để ghi chi phí"
