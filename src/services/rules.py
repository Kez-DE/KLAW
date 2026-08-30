"""Rule engine — rules are DATA (config/rules.yaml), not code.

Adding or changing a legality rule must be a YAML edit, never a Python
change: the real user of this system is HR staff, not engineers. `kiem` is a
small formula (comparisons, and/or/not, +-*/, table lookup via `bang[khoa]`)
parsed with `ast` and evaluated against a whitelist of node types — never
`eval()`. A config file is data, not a place to execute code, and the
whitelist is what keeps that true even if this YAML is ever edited by someone
we trust less than the engineering team.

This buys three things: verifying a legal citation becomes a data-entry task
with a checklist instead of a code change; each rule is independently
unit-testable through its own facts; and the thesis can report "N rules, M
verified against source" as a real number.

A missing fact must be reported as "could not check", never as a silent
pass. `check()` therefore returns `bool | None` — `None` means the rule could
not be evaluated because a required fact was absent, `False` means an actual
violation. Collapsing the two would make a document that is merely missing
information look identical to one that was checked and found compliant,
which is the failure mode this module exists to avoid (see the
`false_positive` accounting in the thesis's Task 6 eval).
"""

import ast
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text

from src.services.db import get_engine

# Fields every rule must declare. Anything else in the raw YAML mapping is
# rule-specific parameter data (gioi_han, ty_le_toi_thieu, bang_thang, ...)
# available to that rule's own `kiem` expression.
_TRUONG_BAT_BUOC = ("id", "can_cu", "muc_do", "mo_ta", "can_facts", "kiem")
_TRUONG_KHONG_PHAI_THAM_SO = {*_TRUONG_BAT_BUOC, "ghi_chu"}


@dataclass(frozen=True)
class Rule:
    id: str
    can_cu: str
    muc_do: str
    mo_ta: str
    can_facts: list[str]
    kiem: str
    cfg: dict[str, Any]


@dataclass(frozen=True)
class Violation:
    rule_id: str
    can_cu: str
    muc_do: str
    mo_ta: str
    chi_tiet: str
    khong_kiem_duoc: bool = False


# ══ Safe expression evaluator for `kiem:` — whitelist, never eval() ═══════

_NUT_DUOC_PHEP = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Subscript,
)

_SO_SANH = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_NHI_PHAN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _kiem_tra_cu_phap(node: ast.AST) -> None:
    """Walk every node of a `kiem:` expression and reject anything outside
    the whitelist above — no Call, Attribute, Lambda, comprehension, Import,
    or assignment can reach evaluation. Runs once at `load_rules` time so a
    malformed or unsafe formula fails loud immediately, not on first use.
    """
    for n in ast.walk(node):
        if not isinstance(n, _NUT_DUOC_PHEP):
            raise ValueError(f"cú pháp không được phép trong 'kiem': {type(n).__name__}")
        if isinstance(n, ast.Compare) and len(n.ops) != 1:
            raise ValueError("'kiem' chỉ hỗ trợ so sánh một toán tử, không nối chuỗi kiểu a < b < c")


def _tinh_bieu_thuc(node: ast.AST, ns: dict[str, Any]) -> Any:
    """Evaluate a `kiem:` expression tree already accepted by
    `_kiem_tra_cu_phap` against a namespace of facts + rule parameters.
    """
    if isinstance(node, ast.Expression):
        return _tinh_bieu_thuc(node.body, ns)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return ns[node.id]
    if isinstance(node, ast.BoolOp):
        vals = (_tinh_bieu_thuc(v, ns) for v in node.values)
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.UnaryOp):
        return not _tinh_bieu_thuc(node.operand, ns)
    if isinstance(node, ast.BinOp):
        return _NHI_PHAN[type(node.op)](_tinh_bieu_thuc(node.left, ns), _tinh_bieu_thuc(node.right, ns))
    if isinstance(node, ast.Compare):
        return _SO_SANH[type(node.ops[0])](_tinh_bieu_thuc(node.left, ns), _tinh_bieu_thuc(node.comparators[0], ns))
    if isinstance(node, ast.Subscript):
        bang = _tinh_bieu_thuc(node.value, ns)
        return bang[_tinh_bieu_thuc(node.slice, ns)]
    raise ValueError(f"nút AST chưa hỗ trợ: {type(node).__name__}")  # pragma: no cover - chặn bởi whitelist ở trên


# ══ Loading & validating config/rules.yaml ════════════════════════════════


def load_rules(path: Path) -> list[Rule]:
    """Read every rule from `path`. Fails loud — never silently drops a
    broken rule — on invalid YAML, a missing required field, a duplicate id,
    or a `kiem` formula using disallowed syntax.

    Deliberately does NOT touch the database: see `kiem_tra_can_cu_ton_tai`
    for the separate check that every `can_cu` resolves to a real provision.
    That check needs a live connection, and this function's callers —
    including plain unit tests that only exercise `check()`/`run_rules()` —
    should not be forced to provide one.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise ValueError(f"{path}: cần một khoá 'rules' kiểu danh sách ở gốc file")

    rules: list[Rule] = []
    id_da_gap: set[str] = set()
    for i, r in enumerate(data["rules"]):
        if not isinstance(r, dict):
            raise ValueError(f"{path}: rule #{i} không phải mapping YAML hợp lệ")
        thieu = [f for f in _TRUONG_BAT_BUOC if f not in r]
        if thieu:
            nhan = r.get("id", f"#{i}")
            raise ValueError(f"{path}: rule '{nhan}' thiếu trường bắt buộc: {thieu}")
        if r["id"] in id_da_gap:
            raise ValueError(f"{path}: id trùng lặp '{r['id']}'")
        id_da_gap.add(r["id"])
        try:
            _kiem_tra_cu_phap(ast.parse(r["kiem"], mode="eval"))
        except SyntaxError as e:
            raise ValueError(f"{path}: rule '{r['id']}' có 'kiem' sai cú pháp: {e}") from e
        except ValueError as e:
            raise ValueError(f"{path}: rule '{r['id']}': {e}") from e
        rules.append(
            Rule(
                id=r["id"],
                can_cu=r["can_cu"],
                muc_do=r["muc_do"],
                mo_ta=r["mo_ta"],
                can_facts=list(r["can_facts"]),
                kiem=r["kiem"],
                cfg=r,
            )
        )
    return rules


def kiem_tra_can_cu_ton_tai(rules: list[Rule], duong_dan_hop_le: set[str] | None = None) -> None:
    """Raise loudly if any rule's `can_cu` is not a real `provisions.duong_dan`.

    A rule engine that checks legal compliance while citing a nonexistent
    article would make the whole audit worthless while looking fine — this
    is the central constraint of Task 2. Kept separate from `load_rules` so
    the database round-trip only happens where a connection is actually
    available (`@pytest.mark.integration`, or a real deployment's startup
    check), never as a side effect of importing this module.

    Pass `duong_dan_hop_le` explicitly (a set of paths) to check without a
    database at all — this is what makes "a bad can_cu gets caught" itself
    unit-testable without Postgres.
    """
    if duong_dan_hop_le is None:
        with get_engine().connect() as conn:
            duong_dan_hop_le = {row[0] for row in conn.execute(text("SELECT duong_dan FROM provisions")).all()}
    thieu = sorted({r.can_cu for r in rules} - duong_dan_hop_le)
    if thieu:
        raise ValueError(f"can_cu không tồn tại trong provisions.duong_dan: {thieu}")


# ══ Checking facts against rules ═══════════════════════════════════════════


def check(rule: Rule, facts: dict[str, Any]) -> bool | None:
    """True = compliant, False = VIOLATION, None = could not be evaluated
    because `facts` is missing one of `rule.can_facts`.

    `None` comes only from a missing fact, never from evaluating the
    formula. Callers must branch on `is None` / `is False` explicitly —
    `if not check(...)` would wrongly treat "could not check" the same as
    "violation", since both are falsy in Python.
    """
    if any(k not in facts for k in rule.can_facts):
        return None
    tham_so = {k: v for k, v in rule.cfg.items() if k not in _TRUONG_KHONG_PHAI_THAM_SO}
    ns = {**tham_so, **facts}
    ket_qua = _tinh_bieu_thuc(ast.parse(rule.kiem, mode="eval"), ns)
    return bool(ket_qua)


def run_rules(rules: list[Rule], facts: dict[str, Any]) -> list[Violation]:
    """Evaluate every rule against one set of facts."""
    out: list[Violation] = []
    for r in rules:
        ket_qua = check(r, facts)
        if ket_qua is None:
            thieu = [k for k in r.can_facts if k not in facts]
            out.append(
                Violation(
                    r.id,
                    r.can_cu,
                    "canh_bao",
                    r.mo_ta,
                    f"không kiểm được: thiếu {', '.join(thieu)}",
                    khong_kiem_duoc=True,
                )
            )
        elif ket_qua is False:
            chi_tiet = ", ".join(f"{k}={facts[k]!r}" for k in r.can_facts)
            out.append(Violation(r.id, r.can_cu, r.muc_do, r.mo_ta, chi_tiet))
    return out
