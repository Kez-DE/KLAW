"""Node TỰ SOÁT — chạy chính rule engine soát output của generator.

XÁC ĐỊNH, 0 token, cùng tính chất với verify tầng 1. Không nhận tham số llm;
có test khẳng định điều đó.

self_audit=True  → đang soát văn bản do hệ thống sinh  → tính self-audit catch rate
self_audit=False → đang soát văn bản người dùng dán vào

Bốn phép kiểm, TẤT CẢ tra bảng — không phép nào gọi LLM:
  1. completeness — đủ mục bắt buộc (đi qua checklist.py, Task 2/3)
  2. định dạng    — TT10 Đ3.5.c: phúc lợi khác phải ghi mục riêng (xem dưới)
  3. legality     — 5 rule của rules.yaml (đi qua rules.py, Task 2)
  4. citation     — can_cu_provision_id có tồn tại trong db_provisions

Phép kiểm 2 đóng một khoảng trống Task 3 để lại (task-3-report.md mục 9):
`checklist.quy_tac_dinh_dang` trước đó chỉ là can_cu tham chiếu, chưa có kiểm
chủ động, vì `check_completeness(clauses: list[dict])` chỉ thấy `key`, không
đủ tín hiệu để biết "phúc lợi khác" bị gộp hay tách. draft_audit có nguyên
`noi_dung` của từng DraftClause — đủ để tra bằng từ khoá
(`quy_tac_dinh_dang.tu_khoa` trong config/checklist_hdld.yaml) mà không cần
LLM phán đoán ngữ nghĩa: một clause thuộc MỘT TRONG 10 MỤC BẮT BUỘC mà
`noi_dung` chứa từ khoá phúc lợi coi như đã bị gộp; một clause mang `key`
riêng (vd. "phuc_loi_khac") coi như đã tách mục, không bị kiểm bởi phép này.
RULING coordinator 2026-08-31: giữ 0 token, không nhường sang LLM.
"""

from dataclasses import dataclass, field

from src.agents.nodes.verify_tier1 import normalize
from src.services.checklist import Checklist, check_completeness
from src.services.rules import Rule, run_rules


@dataclass(frozen=True)
class AuditFinding:
    loai: str            # thieu_noi_dung | trai_luat | citation_khong_hop_le
    muc_do: str          # chan | canh_bao
    mo_ta: str
    dieu_khoan_lien_quan: str | None = None
    can_cu: dict | None = None
    rule_id: str | None = None
    # Cờ đi KÈM finding, không để tầng trên suy lại từ chuỗi `chi_tiet`.
    # `rules.Violation` đã phân biệt "chưa biết" (`None`) với "vi phạm thật"
    # (`False`); bỏ cờ ở đây buộc frontend khớp hình dạng một câu tiếng Việt —
    # sửa câu thông báo là làm hỏng phân loại, và không test nào đỏ.
    khong_kiem_duoc: bool = False


@dataclass(frozen=True)
class AuditReport:
    dat: bool
    completeness: float
    so_dieu_khoan: int
    self_audit: bool
    findings: list[AuditFinding] = field(default_factory=list)


def draft_audit(state: dict, rules: list[Rule], checklist: Checklist,
                 db_provisions: dict[int, dict]) -> dict:
    clauses = state.get("clauses") or []
    findings: list[AuditFinding] = []

    # 1 — completeness (Task 3)
    comp = check_completeness(checklist, [{"key": c.key} for c in clauses],
                               nganh=state.get("nganh", "thuong_mai"))
    ten_theo_key = {m["key"]: m["ten"] for m in checklist.muc}
    for k in comp.thieu:
        findings.append(AuditFinding(
            "thieu_noi_dung", "chan",
            f"Thiếu nội dung bắt buộc: {ten_theo_key.get(k, k)}",
            can_cu={"duong_dan": checklist.can_cu_goc}))

    # 2 — TT10 Đ3.5.c: phúc lợi khác phải ghi mục riêng, không gộp vào mục khác.
    # ponytail: khớp từ khoá là xấp xỉ theo chuỗi, không phải hiểu ngữ nghĩa —
    # "nhà ở" khớp cả câu không thật sự nói về phúc lợi. canh_bao (không chan)
    # đúng vì lý do đó. Nâng cấp phép nhận diện khi có ca đo được cần nó.
    tu_khoa = checklist.quy_tac_dinh_dang.get("tu_khoa") or []
    for c in clauses:
        if c.key not in ten_theo_key:
            continue  # mục riêng hoặc ngoài 10 mục bắt buộc — không phải đối tượng kiểm
        noi_dung_chuan_hoa = normalize(c.noi_dung).lower()
        khop = [tk for tk in tu_khoa if normalize(tk).lower() in noi_dung_chuan_hoa]
        if khop:
            findings.append(AuditFinding(
                "trai_luat", "canh_bao",
                f"Phúc lợi khác ({', '.join(khop)}) có vẻ bị gộp vào mục "
                f"{ten_theo_key[c.key]!r}, TT10 Đ3.5.c yêu cầu ghi thành mục riêng",
                dieu_khoan_lien_quan=c.noi_dung[:120],
                can_cu={"duong_dan": checklist.quy_tac_dinh_dang["can_cu"]}))

    # 3 — legality (Task 2). run_rules đã tự phân biệt None/False (xem
    # rules.py: check() trả bool | None); draft_audit chỉ forward v.muc_do
    # nguyên vẹn, không tự viết lại `if not check(...)`.
    for v in run_rules(rules, state.get("facts") or {}):
        findings.append(AuditFinding(
            "trai_luat", v.muc_do, f"{v.mo_ta} — {v.chi_tiet}",
            can_cu={"duong_dan": v.can_cu}, rule_id=v.rule_id,
            khong_kiem_duoc=v.khong_kiem_duoc))

    # 4 — citation: cùng nguyên tắc verify tầng 1 — tra bảng, không suy luận.
    for c in clauses:
        if c.can_cu_provision_id not in db_provisions:
            findings.append(AuditFinding(
                "citation_khong_hop_le", "chan",
                f"Điều khoản {c.ten!r} dẫn provision_id={c.can_cu_provision_id} không tồn tại",
                dieu_khoan_lien_quan=c.noi_dung[:120]))

    dat = not any(f.muc_do == "chan" for f in findings)
    return {**state, "audit_report": AuditReport(
        dat=dat, completeness=comp.ty_le, so_dieu_khoan=len(clauses),
        self_audit=bool(state.get("self_audit")), findings=findings)}
