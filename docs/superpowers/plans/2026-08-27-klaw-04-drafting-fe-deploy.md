# KLAW Plan 4/5 — Soạn thảo & tự soát · FE · Deploy (tuần 7–8)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Module soạn thảo 3 loại văn bản có **vòng tự soát**, ba màn hình FE với citation click-to-verify, và một URL live cho hội đồng.

**Architecture:** Rule engine đọc YAML (rules là **data**, không phải code) nên xác minh căn cứ pháp lý là task nhập dữ liệu chứ không phải sửa code. Generator sinh văn bản rồi **chính rule engine đó soát lại output của mình** — đối xứng thật với verify tầng 1. FE là React build static mount trong FastAPI: một service, một domain, không CORS.

**Tech Stack:** Python 3.11 · LangGraph · React + Vite · Postgres · Railway

**Spec:** `docs/superpowers/specs/2026-08-27-klaw-design.md` (mục 7, 9, 10)
**Plan trước:** `2026-08-27-klaw-03-verifier.md`

## Global Constraints

- Rules và checklist là **YAML trong `config/`**, không hardcode trong Python
- `can_cu` của mỗi rule phải là `duong_dan` **tồn tại trong DB** — có test khẳng định
- **KHÔNG `python-docx`**, không LaTeX. Xuất Markdown/HTML
- `self_audit=True` phân biệt "soát output của mình" với "soát văn bản người dùng" — cần cho metric
- FE: `abstain` phải hiển thị như **hành vi đúng**, không như lỗi
- `GET /van-ban/{id}` **phải lazy** — BLDS 689 điều
- Không định danh văn bản bằng `title`; hiện `so_ky_hieu` + `bo_luat`

---

## Task 1: Ghi `traces` vào DB

**Files:**
- Create: `src/services/traces.py`
- Modify: `src/api/routes.py`
- Create: `tests/test_services/test_traces.py`

**Interfaces:**
- Produces: `ghi_trace(row: dict) -> None`; mỗi request ghi một dòng vào `traces`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_services/test_traces.py
import uuid

import pytest
from sqlalchemy import text

from src.services.db import get_engine
from src.services.traces import ghi_trace


@pytest.mark.integration
def test_ghi_trace_luu_du_cot_can_cho_bang_ablation():
    tid = str(uuid.uuid4())
    ghi_trace({"id": tid, "endpoint": "/api/v1/tra-cuu", "query": "x",
               "config_name": "full", "result_type": "answer",
               "claims_raw": 3, "claims_after_tier1": 2, "claims_after_tier2": 2,
               "latency_ms": 1200, "token_in": 100, "token_out": 20, "cost_usd": 0.0001})
    with get_engine().connect() as c:
        r = c.execute(text("SELECT * FROM traces WHERE id = :i"), {"i": tid}).mappings().one()
    assert r["claims_raw"] == 3 and r["claims_after_tier1"] == 2
    assert r["config_name"] == "full" and r["cost_usd"] is not None


@pytest.mark.integration
def test_ghi_trace_loi_KHONG_lam_sap_request():
    """Trace là dữ liệu nghiên cứu, không phải đường dẫn quan trọng — lỗi ghi
    trace không được làm người dùng mất câu trả lời."""
    ghi_trace({"id": None, "endpoint": None})   # thiếu PK → lỗi SQL, phải nuốt và log
```

- [ ] **Step 2: Chạy test, xác nhận FAIL** — `ModuleNotFoundError`

- [ ] **Step 3: Viết `src/services/traces.py`**

```python
"""Ghi traces — dữ liệu cho chương đánh giá.

Ghi trace lỗi KHÔNG được làm sập request: đây là dữ liệu nghiên cứu, không phải
đường dẫn quan trọng. Nhưng phải LOG lỗi, không nuốt im lặng.
"""

import logging

from sqlalchemy import text

from src.services.db import get_engine

log = logging.getLogger(__name__)

COLS = ("id", "endpoint", "query", "config_name", "result_type", "retrieved_ids",
        "claims_raw", "claims_after_tier1", "claims_after_tier2",
        "latency_ms", "token_in", "token_out", "cost_usd")


def ghi_trace(row: dict) -> None:
    data = {k: row.get(k) for k in COLS}
    cols = ", ".join(COLS)
    binds = ", ".join(f":{k}" for k in COLS)
    try:
        with get_engine().begin() as conn:
            conn.execute(text(f"INSERT INTO traces ({cols}) VALUES ({binds})"), data)
    except Exception:
        log.exception("ghi trace thất bại (không ảnh hưởng response)")
```

Trong `routes.py`, bọc mỗi endpoint: đo `latency_ms` bằng `time.perf_counter()`, gọi `ghi_trace` sau khi có kết quả.

- [ ] **Step 4: Chạy lại test** — PASS (2 test)

- [ ] **Step 5: Commit**

```bash
git add src/services/traces.py src/api/routes.py tests/test_services/test_traces.py
git commit -m "feat(traces): log every request for the evaluation chapter

claims_raw, claims_after_tier1 and claims_after_tier2 are the three numbers the
ablation table's citation-precision column is computed from, so they are stored per
request rather than recomputed later. A trace write failure logs and continues -
research data must never cost a user their answer - but it logs loudly rather than
swallowing, because silently missing traces would look like a working system with
an empty results chapter."
```

---

## Task 2: Rule engine đọc YAML

**Files:**
- Create: `config/rules.yaml`
- Create: `src/services/rules.py`
- Create: `tests/test_services/test_rules.py`

**Interfaces:**
- Produces: `Rule` (dataclass), `load_rules(path) -> list[Rule]`, `check(rule, facts: dict) -> bool | None` (None = không áp dụng được vì thiếu fact), `run_rules(rules, facts) -> list[Violation]`

**Căn cứ đã xác minh (spec 7.3) — nguyên văn từ API MOJ:**
Đ25 K1–K4 thử việc 180/60/30/06 ngày · Đ26 lương thử việc ≥85% · NĐ 293/2025 Đ3.1 lương tối thiểu vùng I–IV · Đ127.2 cấm phạt tiền · Đ17.1–2 cấm giữ giấy tờ/đặt cọc

- [ ] **Step 1: Viết `config/rules.yaml`**

```yaml
rules:
  - id: thu_viec_toi_da
    can_cu: "45/2019/QH14 > Điều 25"
    muc_do: chan
    mo_ta: "Thời gian thử việc vượt mức tối đa theo chức danh"
    can_facts: [thoi_gian_thu_viec_ngay, nhom_chuc_danh]
    gioi_han:
      quan_ly_doanh_nghiep: 180
      cao_dang_tro_len: 60
      trung_cap_cnkt_nghiep_vu: 30
      cong_viec_khac: 6
    kiem: thoi_gian_thu_viec_ngay <= gioi_han[nhom_chuc_danh]

  - id: luong_thu_viec_toi_thieu
    can_cu: "45/2019/QH14 > Điều 26"
    muc_do: chan
    mo_ta: "Tiền lương thử việc thấp hơn 85% mức lương của công việc"
    can_facts: [luong_thu_viec, luong_chinh_thuc]
    ty_le_toi_thieu: 0.85
    kiem: luong_thu_viec >= 0.85 * luong_chinh_thuc

  - id: luong_toi_thieu_vung
    can_cu: "293/2025/NĐ-CP > Điều 3 > Khoản 1"
    muc_do: chan
    mo_ta: "Mức lương tháng thấp hơn lương tối thiểu vùng"
    can_facts: [luong_thang, vung]
    bang_thang: {I: 5310000, II: 4730000, III: 4140000, IV: 3700000}
    bang_gio:   {I: 25500,   II: 22700,   III: 20000,   IV: 17800}
    kiem: luong_thang >= bang_thang[vung]
    ghi_chu: >
      Danh mục địa bàn vùng I–IV nằm ở Phụ lục NĐ 293/2025, KHÔNG có trong
      documentContent và endpoint tải file trả 401 → `vung` PHẢI là input người dùng,
      không suy ra từ địa chỉ.

  - id: cam_phat_tien_nld
    can_cu: "45/2019/QH14 > Điều 127 > Khoản 2"
    muc_do: chan
    mo_ta: "Có điều khoản phạt tiền hoặc cắt lương thay xử lý kỷ luật"
    can_facts: [co_dieu_khoan_phat_tien]
    kiem: not co_dieu_khoan_phat_tien

  - id: cam_giu_giay_to_dat_coc
    can_cu: "45/2019/QH14 > Điều 17"
    muc_do: chan
    mo_ta: "Có điều khoản giữ bản chính giấy tờ hoặc buộc đặt cọc"
    can_facts: [co_dieu_khoan_giu_giay_to, co_dieu_khoan_dat_coc]
    kiem: not (co_dieu_khoan_giu_giay_to or co_dieu_khoan_dat_coc)
```

- [ ] **Step 2: Viết test thất bại**

```python
# tests/test_services/test_rules.py
from pathlib import Path

import pytest
from sqlalchemy import text

from src.services.db import get_engine
from src.services.rules import load_rules, run_rules

RULES = load_rules(Path("config/rules.yaml"))


def test_du_5_rule_va_id_duy_nhat():
    ids = [r.id for r in RULES]
    assert len(ids) == 5 and len(set(ids)) == 5


def test_thu_viec_90_ngay_cho_cong_viec_khac_la_VI_PHAM():
    v = run_rules(RULES, {"thoi_gian_thu_viec_ngay": 90, "nhom_chuc_danh": "cong_viec_khac"})
    assert any(x.rule_id == "thu_viec_toi_da" for x in v)


def test_thu_viec_180_ngay_cho_quan_ly_doanh_nghiep_la_HOP_PHAP():
    v = run_rules(RULES, {"thoi_gian_thu_viec_ngay": 180,
                          "nhom_chuc_danh": "quan_ly_doanh_nghiep"})
    assert not any(x.rule_id == "thu_viec_toi_da" for x in v)


def test_thu_viec_181_ngay_cho_quan_ly_la_VI_PHAM_bien_dung():
    v = run_rules(RULES, {"thoi_gian_thu_viec_ngay": 181,
                          "nhom_chuc_danh": "quan_ly_doanh_nghiep"})
    assert any(x.rule_id == "thu_viec_toi_da" for x in v)


def test_luong_thu_viec_84_phan_tram_la_VI_PHAM():
    v = run_rules(RULES, {"luong_thu_viec": 8_400_000, "luong_chinh_thuc": 10_000_000})
    assert any(x.rule_id == "luong_thu_viec_toi_thieu" for x in v)


def test_luong_thu_viec_dung_85_phan_tram_la_HOP_PHAP():
    v = run_rules(RULES, {"luong_thu_viec": 8_500_000, "luong_chinh_thuc": 10_000_000})
    assert not any(x.rule_id == "luong_thu_viec_toi_thieu" for x in v)


def test_luong_duoi_toi_thieu_vung_I_la_VI_PHAM():
    v = run_rules(RULES, {"luong_thang": 5_000_000, "vung": "I"})
    assert any(x.rule_id == "luong_toi_thieu_vung" for x in v)


def test_thieu_fact_thi_KHONG_bao_vi_pham_ma_bao_khong_kiem_duoc():
    v = run_rules(RULES, {"luong_thang": 5_000_000})   # thiếu `vung`
    lq = [x for x in v if x.rule_id == "luong_toi_thieu_vung"]
    assert lq and lq[0].khong_kiem_duoc is True, (
        "thiếu fact phải báo 'không kiểm được', KHÔNG được im lặng cho qua"
    )


def test_dieu_khoan_phat_tien_la_VI_PHAM():
    assert any(x.rule_id == "cam_phat_tien_nld"
               for x in run_rules(RULES, {"co_dieu_khoan_phat_tien": True}))


@pytest.mark.integration
def test_MOI_can_cu_TON_TAI_trong_DB():
    """Rule trích dẫn điều luật không tồn tại thì audit report vô giá trị."""
    with get_engine().connect() as c:
        co = {r[0] for r in c.execute(text("SELECT duong_dan FROM provisions")).all()}
    thieu = [r.can_cu for r in RULES if r.can_cu not in co]
    assert not thieu, f"căn cứ không có trong DB: {thieu}"
```

- [ ] **Step 3: Chạy test, xác nhận FAIL** — `ModuleNotFoundError`

- [ ] **Step 4: Viết `src/services/rules.py`**

```python
"""Rule engine — rules là DATA (config/rules.yaml), không phải code.

Ba lợi ích: xác minh căn cứ pháp lý thành task nhập dữ liệu có checklist; mỗi
rule unit-test độc lập; khóa luận báo cáo được "N rule, M đã đối chiếu nguồn".

Thiếu fact → BÁO "không kiểm được", KHÔNG im lặng cho qua. Một rule âm thầm
không chạy trông y hệt một rule đã chạy và thấy hợp pháp.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Rule:
    id: str
    can_cu: str
    muc_do: str
    mo_ta: str
    can_facts: list[str]
    cfg: dict[str, Any]


@dataclass(frozen=True)
class Violation:
    rule_id: str
    can_cu: str
    muc_do: str
    mo_ta: str
    chi_tiet: str
    khong_kiem_duoc: bool = False


def load_rules(path: Path) -> list[Rule]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Rule(id=r["id"], can_cu=r["can_cu"], muc_do=r.get("muc_do", "chan"),
                 mo_ta=r["mo_ta"], can_facts=r.get("can_facts", []), cfg=r)
            for r in data["rules"]]


def _kiem(rule: Rule, f: dict) -> tuple[bool, str]:
    """Trả (hop_phap, chi_tiet). Mỗi rule một nhánh tường minh — KHÔNG eval()."""
    c = rule.cfg
    if rule.id == "thu_viec_toi_da":
        gh = c["gioi_han"].get(f["nhom_chuc_danh"])
        if gh is None:
            return True, f"nhóm chức danh lạ: {f['nhom_chuc_danh']}"
        ok = f["thoi_gian_thu_viec_ngay"] <= gh
        return ok, f"thử việc {f['thoi_gian_thu_viec_ngay']} ngày, tối đa {gh} ngày"
    if rule.id == "luong_thu_viec_toi_thieu":
        nguong = c["ty_le_toi_thieu"] * f["luong_chinh_thuc"]
        return f["luong_thu_viec"] >= nguong, \
            f"lương thử việc {f['luong_thu_viec']:,}đ, tối thiểu {nguong:,.0f}đ (85%)"
    if rule.id == "luong_toi_thieu_vung":
        nguong = c["bang_thang"].get(f["vung"])
        if nguong is None:
            return True, f"vùng lạ: {f['vung']}"
        return f["luong_thang"] >= nguong, \
            f"lương {f['luong_thang']:,}đ, tối thiểu vùng {f['vung']} là {nguong:,}đ"
    if rule.id == "cam_phat_tien_nld":
        return not f["co_dieu_khoan_phat_tien"], "có điều khoản phạt tiền người lao động"
    if rule.id == "cam_giu_giay_to_dat_coc":
        xau = f.get("co_dieu_khoan_giu_giay_to") or f.get("co_dieu_khoan_dat_coc")
        return not xau, "có điều khoản giữ giấy tờ gốc hoặc buộc đặt cọc"
    raise KeyError(f"rule {rule.id} chưa có nhánh kiểm — thêm vào _kiem()")


def run_rules(rules: list[Rule], facts: dict) -> list[Violation]:
    out: list[Violation] = []
    for r in rules:
        thieu = [k for k in r.can_facts if k not in facts]
        if thieu:
            out.append(Violation(r.id, r.can_cu, "canh_bao", r.mo_ta,
                                 f"không kiểm được: thiếu {', '.join(thieu)}",
                                 khong_kiem_duoc=True))
            continue
        ok, chi_tiet = _kiem(r, facts)
        if not ok:
            out.append(Violation(r.id, r.can_cu, r.muc_do, r.mo_ta, chi_tiet))
    return out
```

- [ ] **Step 5: Chạy lại test** — PASS (10 test)

- [ ] **Step 6: Commit**

```bash
git add config/rules.yaml src/services/rules.py tests/test_services/test_rules.py
git commit -m "feat(rules): YAML-driven legality rules with citations checked against the database

Rules are data, so verifying a legal citation is data entry with a checklist
rather than a code change, and the thesis can report 'five rules, five verified
against source'. An integration test asserts every can_cu resolves to a real
duong_dan in provisions: a rule citing a nonexistent article would make the whole
audit report worthless while looking fine.

A missing fact produces an explicit 'could not check' warning rather than passing.
A rule that silently did not run looks exactly like a rule that ran and found
nothing wrong, which is the more dangerous of the two.

_kiem uses an explicit branch per rule and never eval() - config files are not a
place to execute expressions. Boundary tests pin 180 legal and 181 illegal, and
85% exactly legal."
```

---

## Task 3: Checklist nội dung bắt buộc + 3 ngoại lệ

**Files:**
- Create: `config/checklist_hdld.yaml`
- Create: `src/services/checklist.py`
- Create: `tests/test_services/test_checklist.py`

**Interfaces:**
- Produces: `load_checklist(path) -> Checklist`, `check_completeness(cl, clauses: list[dict], nganh: str) -> Completeness(ty_le, thieu, duoc_phep_giam)`

**10 mục Đ21.1.a–k × TT 10/2020 Đ3.1–10 (spec 7.2), ba ngoại lệ:**
Đ21.3 nông/lâm/ngư/diêm nghiệp được giảm → báo `ĐƯỢC_PHÉP_GIẢM`, denominator đổi theo ngành · Đ21.2 bí mật KD là **quyền**, không bắt buộc · TT10 Đ3.5.c phúc lợi khác phải **ghi mục riêng**

- [ ] **Step 1: Viết `config/checklist_hdld.yaml`**

```yaml
can_cu_goc: "45/2019/QH14 > Điều 21 > Khoản 1"
can_cu_chi_tiet: "10/2020/TT-BLĐTBXH > Điều 3"
muc:
  - {stt: 1,  key: nsdld,        ten: "Tên, địa chỉ NSDLĐ và họ tên, chức danh người giao kết", diem: a}
  - {stt: 2,  key: nld,          ten: "Họ tên, ngày sinh, giới tính, nơi cư trú, số CCCD của NLĐ", diem: b}
  - {stt: 3,  key: cong_viec,    ten: "Công việc và địa điểm làm việc", diem: c}
  - {stt: 4,  key: thoi_han,     ten: "Thời hạn của hợp đồng lao động", diem: d}
  - {stt: 5,  key: luong,        ten: "Mức lương, hình thức trả, thời hạn trả, phụ cấp", diem: đ}
  - {stt: 6,  key: nang_luong,   ten: "Chế độ nâng bậc, nâng lương", diem: e}
  - {stt: 7,  key: thoi_gio,     ten: "Thời giờ làm việc, thời giờ nghỉ ngơi", diem: g}
  - {stt: 8,  key: bao_ho,       ten: "Trang bị bảo hộ lao động", diem: h}
  - {stt: 9,  key: bao_hiem,     ten: "BHXH, BHYT, BHTN", diem: i}
  - {stt: 10, key: dao_tao,      ten: "Đào tạo, bồi dưỡng, nâng cao trình độ kỹ năng nghề", diem: k}

nganh_duoc_giam:
  can_cu: "45/2019/QH14 > Điều 21 > Khoản 3"
  danh_sach: [nong_nghiep, lam_nghiep, ngu_nghiep, diem_nghiep]
  duoc_giam_muc: [bao_ho, nang_luong, dao_tao]
  bat_buoc_them:
    key: thien_tai
    ten: "Phương thức xử lý khi chịu ảnh hưởng thiên tai, hỏa hoạn, thời tiết"

khong_bat_buoc:
  can_cu: "45/2019/QH14 > Điều 21 > Khoản 2"
  ghi_chu: "Điều khoản bí mật KD/công nghệ là QUYỀN thỏa thuận, KHÔNG bắt buộc — đừng báo thiếu"
  keys: [bi_mat_kinh_doanh]

quy_tac_dinh_dang:
  can_cu: "10/2020/TT-BLĐTBXH > Điều 3"
  ghi_chu: "Phúc lợi khác (thưởng, ăn giữa ca, xăng xe, điện thoại, nhà ở, giữ trẻ) phải GHI THÀNH MỤC RIÊNG"
```

- [ ] **Step 2: Viết test thất bại**

```python
# tests/test_services/test_checklist.py
from pathlib import Path

from src.services.checklist import check_completeness, load_checklist

CL = load_checklist(Path("config/checklist_hdld.yaml"))
DU_10 = [{"key": k} for k in ("nsdld", "nld", "cong_viec", "thoi_han", "luong",
                              "nang_luong", "thoi_gio", "bao_ho", "bao_hiem", "dao_tao")]


def test_du_10_muc_thi_completeness_1_0():
    r = check_completeness(CL, DU_10, nganh="thuong_mai")
    assert r.ty_le == 1.0 and r.thieu == []


def test_thieu_2_muc_thi_completeness_0_8():
    r = check_completeness(CL, DU_10[:8], nganh="thuong_mai")
    assert r.ty_le == 0.8
    assert set(r.thieu) == {"bao_hiem", "dao_tao"}


def test_NGOAI_LE_D21_3_nganh_nong_nghiep_thieu_bao_ho_la_DUOC_PHEP_GIAM():
    thieu_bao_ho = [c for c in DU_10 if c["key"] != "bao_ho"]
    thieu_bao_ho.append({"key": "thien_tai"})
    r = check_completeness(CL, thieu_bao_ho, nganh="nong_nghiep")
    assert "bao_ho" in r.duoc_phep_giam
    assert "bao_ho" not in r.thieu, "ngành được giảm thì không tính là thiếu"
    assert r.ty_le == 1.0


def test_NGOAI_LE_D21_3_nganh_nong_nghiep_THIEU_dieu_khoan_thien_tai_la_VI_PHAM():
    r = check_completeness(CL, DU_10, nganh="nong_nghiep")
    assert "thien_tai" in r.thieu, "ngành nông nghiệp phải có điều khoản thiên tai"


def test_denominator_doi_theo_nganh_khong_co_dinh_10():
    r = check_completeness(CL, DU_10, nganh="nong_nghiep")
    assert r.tong_muc != 10, "denominator phải đổi theo ngành (spec 7.2 Đ21.3)"


def test_NGOAI_LE_D21_2_bi_mat_kinh_doanh_KHONG_bao_thieu():
    r = check_completeness(CL, DU_10, nganh="thuong_mai")
    assert "bi_mat_kinh_doanh" not in r.thieu, "bí mật KD là quyền, không bắt buộc"
```

- [ ] **Step 3: Chạy test, xác nhận FAIL** — `ModuleNotFoundError`

- [ ] **Step 4: Viết `src/services/checklist.py`**

```python
"""Checklist nội dung bắt buộc của HĐLĐ (BLLĐ Đ21.1 × TT 10/2020 Đ3).

Ba ngoại lệ, nếu bỏ qua sẽ báo sai:
  Đ21.3  nông/lâm/ngư/diêm nghiệp ĐƯỢC GIẢM một số mục, và phải THÊM điều khoản
         thiên tai → denominator đổi theo ngành, KHÔNG cố định 10
  Đ21.2  bí mật KD/công nghệ là QUYỀN, không bắt buộc → đừng báo thiếu
  TT10 Đ3.5.c  phúc lợi khác phải ghi mục riêng → quy tắc định dạng
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Checklist:
    can_cu_goc: str
    muc: list[dict]
    nganh_duoc_giam: dict[str, Any]
    khong_bat_buoc: dict[str, Any]
    quy_tac_dinh_dang: dict[str, Any]


@dataclass(frozen=True)
class Completeness:
    ty_le: float
    tong_muc: int
    co: list[str] = field(default_factory=list)
    thieu: list[str] = field(default_factory=list)
    duoc_phep_giam: list[str] = field(default_factory=list)


def load_checklist(path: Path) -> Checklist:
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Checklist(d["can_cu_goc"], d["muc"], d["nganh_duoc_giam"],
                     d["khong_bat_buoc"], d["quy_tac_dinh_dang"])


def check_completeness(cl: Checklist, clauses: list[dict], nganh: str) -> Completeness:
    co = {c["key"] for c in clauses if c.get("key")}
    bat_buoc = [m["key"] for m in cl.muc]

    duoc_giam: list[str] = []
    if nganh in cl.nganh_duoc_giam["danh_sach"]:
        duoc_giam = list(cl.nganh_duoc_giam["duoc_giam_muc"])
        bat_buoc = [k for k in bat_buoc if k not in duoc_giam]
        bat_buoc.append(cl.nganh_duoc_giam["bat_buoc_them"]["key"])

    thieu = [k for k in bat_buoc if k not in co]
    ty_le = (len(bat_buoc) - len(thieu)) / len(bat_buoc) if bat_buoc else 1.0
    return Completeness(round(ty_le, 4), len(bat_buoc),
                        co=sorted(co & set(bat_buoc)), thieu=thieu,
                        duoc_phep_giam=[k for k in duoc_giam if k not in co])
```

- [ ] **Step 5: Chạy lại test** — PASS (6 test)

- [ ] **Step 6: Commit**

```bash
git add config/checklist_hdld.yaml src/services/checklist.py tests/test_services/test_checklist.py
git commit -m "feat(checklist): ten mandatory clauses with the three statutory exceptions encoded

The naive version reports 'x/10' and is wrong three ways. Article 21.3 lets
agriculture, forestry, fishery and salt-production contracts omit some items while
requiring a natural-disaster clause the others do not need, so the denominator
moves with the industry - a test asserts it is not 10 for those sectors. Article
21.2 makes trade-secret terms a right rather than a requirement, so their absence
must never be reported as missing. Every exception carries its own can_cu, so an
audit finding can cite why an omission is permitted."
```

---

## Task 4: Node sinh + node tự soát

**Files:**
- Create: `prompts/draft_generate.v1.md`
- Create: `src/agents/nodes/draft_generate.py`, `src/agents/nodes/draft_audit.py`
- Create: `tests/test_agents/test_draft_audit.py`

**Interfaces:**
- Produces: `DraftClause(key, ten, noi_dung, can_cu_provision_id)`; `draft_generate(state, llm, model) -> dict`; `draft_audit(state, rules, checklist, db_provisions) -> dict` → `state["audit_report"]`
- `AuditFinding` / `AuditReport` theo spec 8.0b, có `self_audit: bool`

- [ ] **Step 1: Viết test thất bại — audit là hàm xác định, test không cần LLM**

```python
# tests/test_agents/test_draft_audit.py
from pathlib import Path

from src.agents.nodes.draft_audit import draft_audit
from src.agents.nodes.draft_generate import DraftClause
from src.services.checklist import load_checklist
from src.services.rules import load_rules

RULES = load_rules(Path("config/rules.yaml"))
CL = load_checklist(Path("config/checklist_hdld.yaml"))
DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26", "so_ky_hieu": "45/2019/QH14",
           "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}


def _clauses(keys):
    return [DraftClause(k, k, f"nội dung {k}", 11) for k in keys]


DU_10 = ["nsdld", "nld", "cong_viec", "thoi_han", "luong", "nang_luong",
         "thoi_gio", "bao_ho", "bao_hiem", "dao_tao"]


def test_hop_dong_du_muc_va_hop_phap_thi_dat():
    st = draft_audit({"clauses": _clauses(DU_10), "nganh": "thuong_mai",
                      "facts": {"thoi_gian_thu_viec_ngay": 30, "nhom_chuc_danh": "cong_viec_khac",
                                "luong_thu_viec": 9_000_000, "luong_chinh_thuc": 10_000_000,
                                "luong_thang": 10_000_000, "vung": "I",
                                "co_dieu_khoan_phat_tien": False,
                                "co_dieu_khoan_giu_giay_to": False,
                                "co_dieu_khoan_dat_coc": False},
                      "self_audit": True}, RULES, CL, DB)
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
```

- [ ] **Step 2: Chạy test, xác nhận FAIL** — `ModuleNotFoundError`

- [ ] **Step 3: Viết `prompts/draft_generate.v1.md`**

```markdown
Soạn {loai_van_ban} theo pháp luật lao động Việt Nam, dựa trên các thông tin và điều luật dưới đây.

Với MỖI điều khoản bạn viết:
- `key`: mã mục nội dung bắt buộc mà nó đáp ứng (lấy từ danh sách DANH MỤC MỤC)
- `can_cu_provision_id`: provision_id của điều luật là căn cứ, lấy đúng từ ĐIỀU LUẬT
- `noi_dung`: nội dung điều khoản, viết bằng văn phong hợp đồng

Không thêm điều khoản trái pháp luật. Không tự đặt mức thấp hơn mức tối thiểu luật định.

Trả về JSON: {{"clauses": [{{"key": "...", "ten": "...", "noi_dung": "...", "can_cu_provision_id": 0}}]}}

THÔNG TIN: {facts}
DANH MỤC MỤC: {muc}
ĐIỀU LUẬT: {context}
```

- [ ] **Step 4: Viết hai node**

```python
# src/agents/nodes/draft_generate.py
"""Node sinh văn bản — LLM viết điều khoản kèm key và can_cu_provision_id."""

import json
from dataclasses import dataclass
from pathlib import Path

PROMPT_PATH = Path("prompts/draft_generate.v1.md")

CLAUSES_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["clauses"],
    "properties": {"clauses": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["key", "ten", "noi_dung", "can_cu_provision_id"],
        "properties": {"key": {"type": "string"}, "ten": {"type": "string"},
                       "noi_dung": {"type": "string"},
                       "can_cu_provision_id": {"type": "integer"}}}}},
}


@dataclass(frozen=True)
class DraftClause:
    key: str
    ten: str
    noi_dung: str
    can_cu_provision_id: int


def draft_generate(state: dict, llm, model: str) -> dict:
    from src.agents.nodes.generate_claims import build_context

    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        loai_van_ban=state["loai_van_ban"], facts=json.dumps(state["facts"], ensure_ascii=False),
        muc=json.dumps([m["key"] for m in state["muc"]], ensure_ascii=False),
        context=build_context(state.get("expanded") or []))
    try:
        raw, usage = llm.chat(model, [{"role": "user", "content": prompt}],
                             json_schema=CLAUSES_SCHEMA)
        clauses = [DraftClause(**c) for c in json.loads(raw)["clauses"]]
        err = False
    except Exception:
        clauses, usage, err = [], None, True
    return {**state, "clauses": clauses, "schema_error": err, "usage_generate": usage,
            "self_audit": True}
```

```python
# src/agents/nodes/draft_audit.py
"""Node TỰ SOÁT — chạy chính rule engine soát output của generator.

XÁC ĐỊNH, 0 token, cùng tính chất với verify tầng 1. Không nhận tham số llm;
có test khẳng định điều đó.

self_audit=True  → đang soát văn bản do hệ thống sinh  → tính self-audit catch rate
self_audit=False → đang soát văn bản người dùng dán vào
"""

from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class AuditReport:
    dat: bool
    completeness: float
    so_dieu_khoan: int
    self_audit: bool
    findings: list[AuditFinding] = field(default_factory=list)


def _cit(db: dict[int, dict], pid: int) -> dict | None:
    p = db.get(pid)
    if p is None:
        return None
    return {"provision_id": pid, "duong_dan": p.get("duong_dan", ""),
            "bo_luat": p.get("ten", ""), "so_ky_hieu": p.get("so_ky_hieu", "")}


def draft_audit(state: dict, rules: list[Rule], checklist: Checklist,
                db_provisions: dict[int, dict]) -> dict:
    clauses = state.get("clauses") or []
    findings: list[AuditFinding] = []

    # 1 — completeness
    comp = check_completeness(checklist, [{"key": c.key} for c in clauses],
                              nganh=state.get("nganh", "thuong_mai"))
    ten_theo_key = {m["key"]: m["ten"] for m in checklist.muc}
    for k in comp.thieu:
        findings.append(AuditFinding(
            "thieu_noi_dung", "chan",
            f"Thiếu nội dung bắt buộc: {ten_theo_key.get(k, k)}",
            can_cu={"duong_dan": checklist.can_cu_goc}))

    # 2 — legality
    for v in run_rules(rules, state.get("facts") or {}):
        findings.append(AuditFinding(
            "trai_luat", v.muc_do, f"{v.mo_ta} — {v.chi_tiet}",
            can_cu={"duong_dan": v.can_cu}, rule_id=v.rule_id))

    # 3 — citation (dùng lại nguyên tắc verify tầng 1: tra bảng)
    for c in clauses:
        if _cit(db_provisions, c.can_cu_provision_id) is None:
            findings.append(AuditFinding(
                "citation_khong_hop_le", "chan",
                f"Điều khoản {c.ten!r} dẫn provision_id={c.can_cu_provision_id} không tồn tại",
                dieu_khoan_lien_quan=c.noi_dung[:120]))

    dat = not any(f.muc_do == "chan" for f in findings)
    return {**state, "audit_report": AuditReport(
        dat=dat, completeness=comp.ty_le, so_dieu_khoan=len(clauses),
        self_audit=bool(state.get("self_audit")), findings=findings)}
```

- [ ] **Step 5: Chạy lại test** — PASS (6 test)

- [ ] **Step 6: Commit**

```bash
git add prompts/draft_generate.v1.md src/agents/nodes/draft_generate.py src/agents/nodes/draft_audit.py tests/test_agents/test_draft_audit.py
git commit -m "feat(draft): generate clauses, then audit them with the same deterministic engine

The audit takes no llm parameter and a test enforces it, because this is the same
argument as tier-1 verification: checking a contract against statute is a lookup,
not an inference. Running it over the system's own output yields the number that
mirrors citation rejection - how many illegal clauses the generator produced and
how many the auditor caught.

Every trai_luat and thieu_noi_dung finding carries a can_cu, so the report says
which article was breached rather than asserting a breach. self_audit
distinguishes checking our own draft from checking a contract a user pasted, which
is what separates the two metrics."
```

---

## Task 5: Graph soạn thảo + endpoint `/soan-thao` và `/soat`

**Files:**
- Create: `src/agents/graph_soan_thao.py`
- Modify: `src/api/routes.py`, `src/models/schemas.py`
- Create: `tests/test_api/test_soan_thao.py`

**Interfaces:**
- Produces: `build_graph_soan_thao()`; `POST /api/v1/soan-thao`, `POST /api/v1/soat`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_api/test_soan_thao.py
import pytest

FACTS = {"nhom_chuc_danh": "cong_viec_khac", "thoi_gian_thu_viec_ngay": 30,
         "luong_thang": 10_000_000, "vung": "I",
         "luong_thu_viec": 9_000_000, "luong_chinh_thuc": 10_000_000,
         "co_dieu_khoan_phat_tien": False, "co_dieu_khoan_giu_giay_to": False,
         "co_dieu_khoan_dat_coc": False}


@pytest.mark.asyncio
async def test_soan_thao_tra_audit_report_co_self_audit_True(client):
    r = await client.post("/api/v1/soan-thao",
                          json={"loai_van_ban": "hdld", "facts": FACTS, "nganh": "thuong_mai"})
    assert r.status_code == 200
    d = r.json()
    assert d["audit_report"]["self_audit"] is True


@pytest.mark.asyncio
async def test_soat_van_ban_nguoi_dung_thi_self_audit_False(client):
    r = await client.post("/api/v1/soat",
                          json={"loai_van_ban": "hdld", "text": "Điều 1. Công việc...",
                                "facts": FACTS, "nganh": "thuong_mai"})
    assert r.status_code == 200
    assert r.json()["audit_report"]["self_audit"] is False


@pytest.mark.asyncio
async def test_thieu_vung_thi_audit_bao_khong_kiem_duoc_chu_khong_im_lang(client):
    f = {k: v for k, v in FACTS.items() if k != "vung"}
    d = (await client.post("/api/v1/soan-thao",
                           json={"loai_van_ban": "hdld", "facts": f,
                                 "nganh": "thuong_mai"})).json()
    assert any("không kiểm được" in x["mo_ta"] for x in d["audit_report"]["findings"])


@pytest.mark.asyncio
async def test_loai_van_ban_la_thi_422(client):
    r = await client.post("/api/v1/soan-thao",
                          json={"loai_van_ban": "khong-co-that", "facts": FACTS})
    assert r.status_code == 422
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

- [ ] **Step 3: Viết graph + schemas + endpoint**

`src/agents/graph_soan_thao.py`: `collect → retrieve_requirements → draft_generate → draft_audit`, trong đó `retrieve_requirements` lấy các provision theo `duong_dan` của checklist + rules (truy vấn trực tiếp, không cần retrieval ngữ nghĩa vì căn cứ đã biết trước).

Thêm vào `src/models/schemas.py`:

```python
from typing import Literal

LoaiVanBan = Literal["hdld", "noi_quy", "quyet_dinh_ky_luat"]


class SoanThaoRequest(BaseModel):
    loai_van_ban: LoaiVanBan
    facts: dict
    nganh: str = "thuong_mai"
    config_name: str | None = None


class SoatRequest(BaseModel):
    loai_van_ban: LoaiVanBan
    text: str = Field(..., min_length=20)
    facts: dict = Field(default_factory=dict)
    nganh: str = "thuong_mai"


class AuditFindingOut(BaseModel):
    loai: str
    muc_do: str
    mo_ta: str
    dieu_khoan_lien_quan: str | None = None
    can_cu: dict | None = None
    rule_id: str | None = None


class AuditReportOut(BaseModel):
    dat: bool
    completeness: float
    so_dieu_khoan: int
    self_audit: bool
    findings: list[AuditFindingOut]


class SoanThaoResponse(BaseModel):
    document: str                    # Markdown
    clauses: list[dict]
    audit_report: AuditReportOut
    trace_id: str


class SoatResponse(BaseModel):
    audit_report: AuditReportOut
    trace_id: str
```

`/soat` trích `clauses` từ `text` bằng cách tách theo dòng `Điều N.` rồi map `key` bằng từ khóa — **không gọi LLM cho việc tách**; nếu không map được `key` thì để `None` và checklist báo thiếu, đúng hành vi mong muốn.

- [ ] **Step 4: Chạy test** — PASS (4 test)

- [ ] **Step 5: Commit**

```bash
git add src/agents/graph_soan_thao.py src/api/routes.py src/models/schemas.py tests/test_api/test_soan_thao.py
git commit -m "feat(api): drafting and audit endpoints sharing one AuditReport shape

/soat reuses the whole engine on text a user pastes, which is the more realistic
use and costs almost nothing beyond a clause splitter. Retrieving the requirement
articles is a direct duong_dan lookup rather than semantic search, because the
statutory basis for a labour contract is known in advance - searching for it would
add a failure mode for no benefit. self_audit distinguishes the two entry points,
which is what makes the catch-rate metric meaningful."
```

---

## Task 6: `draft_facts` — 20 hợp lệ + 30 cài lỗi

**Files:**
- Create: `eval/datasets/draft_facts.yaml`
- Create: `eval/run_draft.py`
- Create: `tests/test_eval/test_draft_facts.py`

**Interfaces:**
- Produces: `eval.run_draft.evaluate() -> dict` với `legality_detection`, `false_positive`, `completeness_avg`, `self_audit_catch_rate`, `generator_violation_rate`

- [ ] **Step 1: Viết `eval/datasets/draft_facts.yaml`**

```yaml
# 20 bộ fact HỢP LỆ + 30 bộ CÀI LỖI (mỗi rule 2–3 case, gồm ca biên)
hop_le:
  - id: ok-01
    nganh: thuong_mai
    facts: {nhom_chuc_danh: cong_viec_khac, thoi_gian_thu_viec_ngay: 6,
            luong_thang: 5310000, vung: I, luong_thu_viec: 4513500,
            luong_chinh_thuc: 5310000, co_dieu_khoan_phat_tien: false,
            co_dieu_khoan_giu_giay_to: false, co_dieu_khoan_dat_coc: false}
  # ca biên hợp lệ: đúng 85%, đúng lương tối thiểu, đúng 180 ngày cho quản lý
  # … 19 bộ nữa

cai_loi:
  - id: bad-thuviec-01
    nganh: thuong_mai
    rule_ky_vong: thu_viec_toi_da
    facts: {nhom_chuc_danh: cong_viec_khac, thoi_gian_thu_viec_ngay: 60, ...}
  - id: bad-thuviec-02
    rule_ky_vong: thu_viec_toi_da
    facts: {nhom_chuc_danh: quan_ly_doanh_nghiep, thoi_gian_thu_viec_ngay: 181, ...}
  - id: bad-luongtv-01
    rule_ky_vong: luong_thu_viec_toi_thieu
    facts: {luong_thu_viec: 8400000, luong_chinh_thuc: 10000000, ...}
  # … đủ 30 bộ, mỗi rule 2–3 case
```

- [ ] **Step 2: Viết test kiểm chất lượng tập dữ liệu**

```python
# tests/test_eval/test_draft_facts.py
from pathlib import Path

import yaml

from src.services.rules import load_rules

D = yaml.safe_load(Path("eval/datasets/draft_facts.yaml").read_text(encoding="utf-8"))
RULE_IDS = {r.id for r in load_rules(Path("config/rules.yaml"))}


def test_du_20_hop_le_va_30_cai_loi():
    assert len(D["hop_le"]) >= 20 and len(D["cai_loi"]) >= 30


def test_MOI_rule_co_it_nhat_2_ca_cai_loi():
    dem: dict[str, int] = {}
    for c in D["cai_loi"]:
        dem[c["rule_ky_vong"]] = dem.get(c["rule_ky_vong"], 0) + 1
    thieu = {r: dem.get(r, 0) for r in RULE_IDS if dem.get(r, 0) < 2}
    assert not thieu, f"rule chưa đủ 2 ca cài lỗi: {thieu}"


def test_rule_ky_vong_deu_ton_tai():
    la = {c["rule_ky_vong"] for c in D["cai_loi"]} - RULE_IDS
    assert not la, f"rule_ky_vong không có thật: {la}"


def test_bo_hop_le_KHONG_vi_pham_rule_nao():
    from src.services.rules import run_rules
    rules = load_rules(Path("config/rules.yaml"))
    for c in D["hop_le"]:
        v = [x for x in run_rules(rules, c["facts"]) if not x.khong_kiem_duoc]
        assert not v, f"{c['id']} đáng lẽ hợp lệ nhưng vi phạm {[x.rule_id for x in v]}"
```

- [ ] **Step 3: Chạy test, xác nhận FAIL** — file chưa đủ

- [ ] **Step 4: Viết đủ 50 bộ fact, rồi viết `eval/run_draft.py`**

Harness chạy `/soan-thao` trên `hop_le` + `cai_loi`, tính:
- `legality_detection` = ca cài lỗi bị bắt / tổng ca cài lỗi
- `false_positive` = bộ hợp lệ bị báo vi phạm / tổng bộ hợp lệ
- `self_audit_catch_rate` = điều khoản trái luật auditor bắt / điều khoản trái luật generator thực tạo (đối chiếu tay 30 văn bản)
- `generator_violation_rate` = điều khoản trái luật / văn bản

- [ ] **Step 5: Chạy và ghi kết quả**

```bash
pytest tests/test_eval/test_draft_facts.py -v
python -m eval.run_draft
```
Ghi 5 số vào `eval/results/report.md`.

- [ ] **Step 6: Commit**

```bash
git add eval/datasets/draft_facts.yaml eval/run_draft.py tests/test_eval/test_draft_facts.py eval/results/report.md
git commit -m "feat(eval): drafting metrics on injected defects with hard ground truth

Ground truth is certain because the defects are ours, which is why auditing beats
generating as the measured task - 'is this contract good?' needs an expert, 'did
the auditor catch the flaw we planted?' needs only bookkeeping. A test asserts
every rule has at least two injected cases and that the 20 supposedly-legal fact
sets really pass all rules; a legal set that quietly violates something would
inflate the false-positive rate and no one would notice."
```

---

## Task 7: Frontend — ba màn hình

**Files:**
- Create: `frontend/` (Vite React), `frontend/src/App.tsx`, `frontend/src/pages/{TraCuu,SoanThao,Soat}.tsx`, `frontend/src/components/{ResultCard,CitationPanel}.tsx`
- Modify: `src/main.py` (mount StaticFiles), `Dockerfile`

**Interfaces:**
- Consumes: `POST /api/v1/tra-cuu`, `/soan-thao`, `/soat`, `GET /api/v1/van-ban/{id}?around=`
- Produces: build vào `src/static/`, FastAPI mount tại `/`

- [ ] **Step 1: Khởi tạo Vite + mount StaticFiles**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install && npm install -D tailwindcss @tailwindcss/vite && cd ..
```

`frontend/vite.config.ts`: `build.outDir = "../src/static"`, `server.proxy["/api"] = "http://localhost:8000"`.

`src/main.py`, sau `app.include_router(...)`:

```python
from pathlib import Path

from fastapi.staticfiles import StaticFiles

STATIC = Path(__file__).parent / "static"
if STATIC.exists():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
```

`StaticFiles` mount **sau** router để `/api/*` không bị chặn.

- [ ] **Step 2: Endpoint `GET /api/v1/van-ban/{id}` — ba dạng lazy**

```python
@router.get("/van-ban/{doc_id}")
async def van_ban(doc_id: str, around: int | None = None, so_dieu: str | None = None):
    """Lazy — BLDS 689 điều, không trả cả cây.

    không tham số → metadata + danh mục Chương/Mục
    ?so_dieu=25   → một Điều + Khoản/Điểm con
    ?around=<pid> → Điều đó + 2 Điều trước/sau (dạng FE dùng nhiều nhất)
    """
```

- [ ] **Step 3: `ResultCard` — bốn trạng thái, bốn cách hiển thị**

| `result_type` | UI |
|---|---|
| `answer` | câu trả lời + citation click được; badge theo `hieu_luc` từng citation |
| `partial_coverage` | **không** hiện câu trả lời; hiện `coverage_note` + link văn bản gốc |
| `abstain` | *"Không tìm thấy căn cứ pháp lý cho câu hỏi này"* + gợi ý diễn đạt lại. **Màu trung tính, KHÔNG màu lỗi** |
| `out_of_scope` | nêu rõ phạm vi 6 Bộ luật |

Badge `hieu_luc`: `con_hieu_luc` ✓ xanh · `mot_phan_khong_xac_dinh` ⚠ vàng kèm câu *"CSDL quốc gia không công bố dữ liệu cấp điều khoản"* · `bi_thay_the`/`het_hieu_luc` ✗ đỏ · `can_doi_chieu_tay` ⚠ xám.

- [ ] **Step 4: `CitationPanel` — click-to-verify**

Click citation → `GET /api/v1/van-ban/{doc_id}?around={provision_id}` → panel bên phải mở đúng Điều **kèm 2 Điều trước/sau**, highlight đoạn `quote`. Hiện `so_ky_hieu` + `bo_luat`, **không hiện `title`**.

- [ ] **Step 5: Dockerfile multi-stage**

Thêm stage node **trước** stage builder Python:

```dockerfile
FROM node:20-slim AS fe
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # → /fe/../src/static
```

Trong stage runtime: `COPY --from=fe /src/static ./src/static`.

- [ ] **Step 6: Kiểm bằng mắt và commit**

```bash
cd frontend && npm run build && cd ..
uvicorn src.main:app --reload
# mở http://localhost:8000 — thử 4 câu cho 4 result_type
docker compose build backend && docker compose up -d
```

```bash
git add frontend/ src/main.py src/api/routes.py Dockerfile .dockerignore
git commit -m "feat(fe): three screens, four result presentations, lazy citation panel

abstain renders in neutral colour with a plain sentence, never as an error: the
system's contribution is knowing when not to answer, and a UI that paints that red
argues against the thesis in front of the committee. partial_coverage deliberately
shows no answer text at all, only the governing statute and the coverage
boundary.

The citation panel fetches ?around=<provision_id> so clicking opens the cited
article with two neighbours rather than pulling an entire code - the Civil Code has
689 articles. Citations display so_ky_hieu and bo_luat and never title, because
doc_id 96117's title is just 'Hàng hải'."
```

---

## Task 8: Deploy Railway

**Files:**
- Create: `railway.json` *(chỉ nếu Phase 0 #2 nói cần)*
- Create: `docs/deploy.md`

- [ ] **Step 1: Đọc Phase 0 #1 và #2**

```bash
grep -A2 'pgvector\|auto-detect' docs/phase0-findings.md
```
Nếu Railway Postgres **không** bật được pgvector → dùng fallback numpy (spec 8.2): vector ~5 MB, đọc vào RAM lúc khởi động. Ghi quyết định vào `docs/deploy.md`.

- [ ] **Step 2: Tạo service và biến môi trường**

```bash
railway login
railway init
railway add --database postgres
railway variables set OPENROUTER_API_KEY=... OPENROUTER_EMBEDDING_MODEL_NAME=baai/bge-m3 \
  OPENROUTER_EMBEDDING_DIM=1024 LLM_TEMPERATURE=0.0 APP_ENV=production
# DATABASE_URL dùng variable reference của Railway, KHÔNG hardcode
railway up
```

- [ ] **Step 3: Migration + ingest lên Railway (một lần)**

```bash
DATABASE_URL="<railway public url>" python -m scripts.ingest
DATABASE_URL="<railway public url>" python -m scripts.build_chunks
DATABASE_URL="<railway public url>" python -m scripts.load_incoming_edges
```

- [ ] **Step 4: Kiểm URL live**

```bash
railway domain
curl -s "$URL/health"
curl -s -X POST "$URL/api/v1/tra-cuu" -H 'content-type: application/json' \
  -d '{"query":"thử việc lương được bao nhiêu phần trăm"}' | python3 -m json.tool
```
Expected: `result_type: "answer"`, citations có `duong_dan`

- [ ] **Step 5: Security review trước khi công khai**

Chạy `ecc:security-review` và `Senior SecOps Engineer` trên diff toàn dự án. Kiểm tối thiểu: không log `OPENROUTER_API_KEY`; `CORS_ORIGINS` không phải `*`; không có endpoint nào trả stack trace; rate limit ở tầng Railway hoặc middleware.

- [ ] **Step 6: Commit**

```bash
git add docs/deploy.md railway.json
git commit -m "docs(deploy): Railway service with the pgvector decision recorded

Ingest runs from a laptop against the public database URL rather than inside the
container: it is a one-off job, and the spec keeps it out of the serving process on
purpose. Records which pgvector branch was taken, because with a 5 MB vector set
the numpy fallback is a legitimate choice rather than a downgrade, and the thesis
should say which one shipped and why."
```

---

## KHÔNG thuộc plan này

| Hoãn | Thuộc plan |
|---|---|
| Ablation đủ 7 cấu hình · reranker · chiều LLM | Plan 5 |
| 60 câu golden cho 5 Bộ luật khác · tập `boundary` 25 câu | Plan 5 |
| Cổng B — Adversarial Eval Verification | Plan 5 |
| Tinh chỉnh `ABSTAIN_THRESHOLD` trên tập dev | Plan 5 |
| `impeccable` / `Accessibility Auditor` audit FE | Plan 5 (sau khi có nội dung thật để audit) |

## Sau plan này

**Điều kiện sang plan 5:** URL Railway trả `result_type: answer` với citation click được · 5 metric soạn thảo có số trong `eval/results/report.md` · `pytest -m "not integration"` xanh · security review không còn CRITICAL.
