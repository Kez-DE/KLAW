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


@pytest.mark.integration
def test_ban_thao_HDLD_dan_BLLD_45_2019_va_nghi_dinh_luong_toi_thieu():
    from src.services.db import get_engine

    db = gst.load_requirements(get_engine(), "hdld")[2]
    khoi = gst.can_cu_van_ban(get_engine(), db, date(2026, 9, 28))
    assert khoi[0] == "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;", khoi
    assert any(d.startswith("Căn cứ Nghị định số 293/2025/NĐ-CP ngày ") and "của Chính phủ" in d for d in khoi), khoi
    assert khoi[-1].endswith(".") and all(d.endswith(";") for d in khoi[:-1])
    assert not any("hiệu lực" in d for d in khoi), "khối căn cứ không phán về hiệu lực"
    assert len(khoi) == len({r["document_id"] for r in db.values()}), "mỗi văn bản một dòng"


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
