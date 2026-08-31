"""draft_audit — hàm xác định, KHÔNG nhận tham số llm (cùng tính chất verify tầng 1).

RULES/CL nạp từ config THẬT (không phải fixture giả) để mọi assertion đối
chiếu đúng ngưỡng luật định thật, cùng khuôn test_rules.py/test_checklist.py.
"""

from pathlib import Path

from src.agents.nodes.draft_audit import draft_audit
from src.agents.nodes.draft_generate import DraftClause
from src.services.checklist import load_checklist
from src.services.rules import load_rules

RULES = load_rules(Path("config/rules.yaml"))
CL = load_checklist(Path("config/checklist_hdld.yaml"))
DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26", "so_ky_hieu": "45/2019/QH14",
           "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}

# Bộ facts hợp pháp trên cả 5 rule của rules.yaml — dùng chung cho mọi test
# "hợp đồng đạt".
#
# thoi_gian_thu_viec_ngay=3, KHÔNG PHẢI 30 như task-4-brief.md viết: brief gốc
# đặt nhom_chuc_danh="cong_viec_khac" (giới hạn thật trong rules.yaml
# gioi_han.cong_viec_khac là 6 ngày) CÙNG với 30 ngày — tự vi phạm chính rule
# thu_viec_toi_da (30 > 6), mâu thuẫn với tên test "hợp pháp thì đạt". Xác
# nhận bằng cách tự tra config/rules.yaml, không chép nguyên số của brief —
# cùng bài học Task 2/Task 3 để lại: brief có thể sai, YAML thật mới là
# authority. 3 ngày giữ nguyên nhom_chuc_danh gốc, chỉ sửa con số.
FACTS_HOP_PHAP = {
    "thoi_gian_thu_viec_ngay": 3, "nhom_chuc_danh": "cong_viec_khac",
    "luong_thu_viec": 9_000_000, "luong_chinh_thuc": 10_000_000,
    "luong_thang": 10_000_000, "vung": "I",
    "co_dieu_khoan_phat_tien": False,
    "co_dieu_khoan_giu_giay_to": False,
    "co_dieu_khoan_dat_coc": False,
}


def _clauses(keys):
    return [DraftClause(k, k, f"nội dung {k}", 11) for k in keys]


DU_10 = ["nsdld", "nld", "cong_viec", "thoi_han", "luong", "nang_luong",
         "thoi_gio", "bao_ho", "bao_hiem", "dao_tao"]


def test_hop_dong_du_muc_va_hop_phap_thi_dat():
    st = draft_audit({"clauses": _clauses(DU_10), "nganh": "thuong_mai",
                      "facts": FACTS_HOP_PHAP, "self_audit": True}, RULES, CL, DB)
    r = st["audit_report"]
    assert r.dat is True and r.completeness == 1.0


def test_thu_viec_90_ngay_sinh_finding_trai_luat_CO_CAN_CU():
    st = draft_audit({"clauses": _clauses(DU_10), "nganh": "thuong_mai",
                      "facts": {"thoi_gian_thu_viec_ngay": 90,
                                "nhom_chuc_danh": "cong_viec_khac"},
                      "self_audit": True}, RULES, CL, DB)
    r = st["audit_report"]
    f = next(x for x in r.findings if x.rule_id == "thu_viec_toi_da")
    assert f.loai == "trai_luat" and f.muc_do == "chan"
    assert f.can_cu is not None and f.can_cu["duong_dan"], "finding trái luật PHẢI có căn cứ"
    assert r.dat is False


def test_thieu_muc_sinh_finding_thieu_noi_dung():
    st = draft_audit({"clauses": _clauses(DU_10[:8]), "nganh": "thuong_mai", "facts": {},
                      "self_audit": True}, RULES, CL, DB)
    r = st["audit_report"]
    assert any(x.loai == "thieu_noi_dung" for x in r.findings)
    assert r.completeness == 0.8


def test_can_cu_provision_id_khong_ton_tai_sinh_finding_citation():
    bad = [DraftClause("luong", "Lương", "x", 999999)]
    st = draft_audit({"clauses": bad, "nganh": "thuong_mai", "facts": {},
                      "self_audit": True}, RULES, CL, DB)
    assert any(x.loai == "citation_khong_hop_le" for x in st["audit_report"].findings)


def test_self_audit_flag_duoc_giu_de_tinh_catch_rate():
    st = draft_audit({"clauses": _clauses(DU_10), "nganh": "thuong_mai", "facts": {},
                      "self_audit": False}, RULES, CL, DB)
    assert st["audit_report"].self_audit is False


def test_audit_KHONG_nhan_tham_so_llm():
    import inspect

    from src.agents.nodes import draft_audit as mod
    assert "llm" not in inspect.signature(mod.draft_audit).parameters, (
        "audit phải xác định — cùng tính chất với verify tầng 1"
    )


# ══ TT10 Đ3.5.c — phúc lợi khác phải ghi mục riêng ══════════════════════════
# RULING coordinator 2026-08-31 (đáp concern Task 3 mục 9): giữ là phép tra
# bảng bằng từ khoá (config/checklist_hdld.yaml quy_tac_dinh_dang.tu_khoa),
# không nhường cho LLM phán đoán ngữ nghĩa.


def test_phuc_loi_khac_gop_vao_mot_muc_bat_buoc_sinh_canh_bao_khong_chan():
    clauses = _clauses(DU_10)
    clauses[4] = DraftClause("luong", "Lương", "Mức lương 10 triệu, có thưởng cuối năm", 11)
    st = draft_audit({"clauses": clauses, "nganh": "thuong_mai",
                      "facts": FACTS_HOP_PHAP, "self_audit": True}, RULES, CL, DB)
    r = st["audit_report"]
    f = next(x for x in r.findings if "Phúc lợi khác" in x.mo_ta)
    assert f.muc_do == "canh_bao", "định dạng là cảnh báo, không phải vi phạm chặn phát hành"
    assert f.can_cu is not None and f.can_cu["duong_dan"]
    assert r.dat is True, "canh_bao không được kéo dat xuống False"


def test_phuc_loi_khac_co_muc_rieng_thi_khong_sinh_finding():
    clauses = _clauses(DU_10) + [
        DraftClause("phuc_loi_khac", "Phúc lợi khác", "Thưởng cuối năm theo kết quả kinh doanh", 11)
    ]
    st = draft_audit({"clauses": clauses, "nganh": "thuong_mai",
                      "facts": FACTS_HOP_PHAP, "self_audit": True}, RULES, CL, DB)
    assert not any("Phúc lợi khác" in x.mo_ta for x in st["audit_report"].findings)
