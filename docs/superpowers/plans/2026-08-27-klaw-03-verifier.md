# KLAW Plan 3/5 — Verifier & Graph tra cứu (tuần 5–6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây **đóng góp chính của khóa luận** — verifier 2 tầng — và graph tra cứu đầy đủ, cho ra 4 loại kết quả và ba dòng đầu của bảng ablation.

**Architecture:** Tầng 1 là **Python thuần, 0 token, 4 phép kiểm tra tra bảng**; tầng 2 là LLM judge khác họ model với generator. Cơ chế hiệu lực 3 mức có guard chống lỗi phân loại của đồ thị nguồn. Mọi node là một file để test được độc lập.

**Tech Stack:** Python 3.11 · LangGraph · OpenRouter `/chat/completions` · Postgres · pytest

**Spec:** `docs/superpowers/specs/2026-08-27-klaw-design.md` (mục 5, 6, 7b)
**Plan trước:** `2026-08-27-klaw-02-retrieval-eval.md` — cần `hybrid` Recall@5 đã đo

## Global Constraints

- **Tầng 1 KHÔNG được gọi LLM.** Nếu nó cần một API call thì thiết kế đã sai
- `OPENROUTER_JUDGE_MODEL_NAME` **phải khác họ** `OPENROUTER_GENERATE_MODEL_NAME` (self-preference bias, spec 7b.2)
- `LLM_TEMPERATURE=0.0` cho mọi vai
- Citation neo `provisions.id`; `duong_dan` là citation string canonical
- **Không định danh văn bản bằng `title`** (`doc_id 96117` → `"Hàng hải"`); dùng `so_ky_hieu`
- `ABSTAIN` là **hành vi đúng, được tính điểm**, không phải lỗi
- Prompt là artifact **có version trong git**: `prompts/*.md`, không nhúng trong code
- Mọi node ghi vào `traces` — dữ liệu chương đánh giá

## Giả định cần xác nhận

| Giả định | Xác nhận ở | Nếu sai |
|---|---|---|
| `gemini-2.5-flash-lite` trả JSON đúng schema ≥95% | Task 4 Step 6 | lên `gemini-2.5-flash` hoặc `gpt-5-mini` |
| `/doc/{id}/related` trả cạnh ĐI VÀO (Phase 0 #4) | Task 1 Step 1 | dùng `relationships.parquet` |
| `ABSTAIN_THRESHOLD=0.5` hợp lý | Task 10 Step 5 | tinh chỉnh trên **tập dev tách riêng**, không trên tập báo cáo |

---

## Task 1: Nạp cạnh ĐI VÀO cho cơ chế hiệu lực

**Files:**
- Create: `scripts/load_incoming_edges.py`
- Create: `tests/test_scripts/test_incoming_edges.py`

**Interfaces:**
- Produces: `load_from_parquet(path, engine) -> int`; sau khi chạy, `"references"` có cạnh với `to_document_id` là văn bản trong corpus

- [ ] **Step 1: Quyết định nguồn theo Phase 0 #4**

```bash
grep -A2 'related.*cạnh ĐI VÀO' docs/phase0-findings.md
```
Nếu endpoint `related` trả cạnh đi vào → dùng `MojClient.fetch_related` cho 18 doc_id, bỏ qua Step 3.
Nếu không → dùng `relationships.parquet` (Step 3). **Ghi lựa chọn vào commit message.**

- [ ] **Step 2: Viết test thất bại**

```python
# tests/test_scripts/test_incoming_edges.py
import pytest
from sqlalchemy import text

from src.services.db import get_engine


@pytest.mark.integration
def test_nd_90_2019_co_canh_DI_VAO_tu_van_ban_thay_the():
    """NĐ 90/2019 (139094) bị thay nhưng MOJ đánh 'còn hiệu lực'.
    Chỉ cạnh đi vào phát hiện được — đây là ca then chốt của Mức 2."""
    with get_engine().connect() as c:
        n = c.execute(text(
            'SELECT count(*) FROM "references"'
            " WHERE to_document_id = '139094' AND loai IN (1, 12)"  # 1 Bãi bỏ, 12 Thay thế
        )).scalar_one()
    assert n > 0, "không có cạnh đi vào cho NĐ 90/2019 — Mức 2 sẽ không bắt được lỗi MOJ"


@pytest.mark.integration
def test_khong_tu_tro_vao_chinh_no():
    with get_engine().connect() as c:
        n = c.execute(text(
            'SELECT count(*) FROM "references" WHERE from_document_id = to_document_id'
            " AND loai IN (1, 12)"
        )).scalar_one()
    assert n == 0, "văn bản tự thay thế chính nó — dữ liệu cạnh sai"
```

- [ ] **Step 3: Viết `scripts/load_incoming_edges.py`**

```python
"""Nạp cạnh quan hệ ĐI VÀO các văn bản trong corpus.

API /doc/{id} chỉ trả cạnh ĐI RA. Cơ chế hiệu lực Mức 2 cần cạnh ĐI VÀO
("ai đã thay thế văn bản này?") → phải quét đồ thị, không tra từng văn bản.
relationships.parquet: 1.033.255 cạnh, 9,4 MB, quét vài giây.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from scripts.fetch_moj import DOC_IDS

# Mã quan hệ MOJ có ý nghĩa cho hiệu lực
LOAI_HIEU_LUC = {1: "Bãi bỏ", 5: "Đình chỉ thi hành", 11: "Tạm ngưng hiệu lực", 12: "Thay thế"}

# Tên loại quan hệ trong parquet → mã MOJ
TEN_TO_MA = {"Bãi bỏ": 1, "Đình chỉ thi hành": 5, "Tạm ngưng hiệu lực": 11,
             "Thay thế": 12, "Sửa đổi, bổ sung": 10, "Dẫn chiếu": 4, "Căn cứ": 3}


def load_from_parquet(path: Path, engine: Engine) -> int:
    df = pd.read_parquet(path)
    cols = {c.lower(): c for c in df.columns}
    c_from = cols.get("doc_id") or cols.get("from_doc_id")
    c_to = cols.get("other_doc_id") or cols.get("to_doc_id")
    c_rel = cols.get("relationship") or cols.get("loai")
    if not all((c_from, c_to, c_rel)):
        raise ValueError(f"không nhận ra cột trong parquet: {list(df.columns)}")

    trong_corpus = set(DOC_IDS)
    df[c_from] = df[c_from].astype(str)
    df[c_to] = df[c_to].astype(str)
    # cạnh ĐI VÀO: đích nằm trong corpus
    m = df[df[c_to].isin(trong_corpus)]

    ghi = 0
    with engine.begin() as conn:
        conn.execute(text(
            'DELETE FROM "references" WHERE from_provision_id IS NULL'
            " AND from_document_id NOT IN :ids"
        ).bindparams(ids=tuple(trong_corpus)))
        for row in m.itertuples(index=False):
            ten = str(getattr(row, c_rel))
            ma = TEN_TO_MA.get(ten)
            if ma is None:
                continue
            conn.execute(text(
                'INSERT INTO "references" (from_document_id, to_document_id, loai, raw_text)'
                " VALUES (:f, :t, :l, :r)"
            ), {"f": str(getattr(row, c_from)), "t": str(getattr(row, c_to)),
                "l": ma, "r": ten})
            ghi += 1
    return ghi


if __name__ == "__main__":
    from src.config import get_settings

    s = get_settings()
    n = load_from_parquet(Path(s.data_raw_dir) / "relationships.parquet", get_engine := __import__(
        "src.services.db", fromlist=["get_engine"]).get_engine())
    print("cạnh đi vào đã nạp:", n)
```

- [ ] **Step 4: Chạy và kiểm ca then chốt**

```bash
python -m scripts.load_incoming_edges
pytest tests/test_scripts/test_incoming_edges.py -v
```
Expected: PASS. **Nếu test đầu FAIL → Mức 2 không có dữ liệu, không đi tiếp Task 2.**

- [ ] **Step 5: Commit**

```bash
git add scripts/load_incoming_edges.py tests/test_scripts/test_incoming_edges.py
git commit -m "feat(effectivity): load incoming relationship edges from the graph

The document API returns only outgoing edges, but deciding whether a document is
still in force asks the opposite question - what replaced this? - so the graph has
to be scanned rather than queried per document. The test that matters names NĐ
90/2019 specifically: MOJ still marks it effective although it was superseded, and
an incoming edge is the only signal that catches it."
```

---

## Task 2: Cơ chế hiệu lực 3 mức + guard

**Files:**
- Create: `src/services/effectivity.py`
- Create: `tests/test_services/test_effectivity.py`

**Interfaces:**
- Produces: `EffectivityVerdict` (StrEnum), `Effectivity(verdict, tin_cay, ly_do)`, `danh_gia(doc: dict, canh_di_vao: list[dict], as_of: date) -> Effectivity`, `cung_chu_de(ten_a: str, ten_b: str) -> bool`

- [ ] **Step 1: Viết test thất bại — hàm thuần, không cần DB**

```python
# tests/test_services/test_effectivity.py
from datetime import date

from src.services.effectivity import EffectivityVerdict as V
from src.services.effectivity import cung_chu_de, danh_gia

HOM_NAY = date(2026, 8, 27)


def _doc(**kw) -> dict:
    base = {"id": "x", "so_ky_hieu": "1/2020/NĐ-CP", "ten": "Nghị định thử",
            "ngay_hieu_luc": date(2020, 1, 1), "ngay_het_hieu_luc": None, "tinh_trang": "CHL"}
    return base | kw


def test_muc_1_effTo_da_qua_thi_het_hieu_luc_tin_cay_cao():
    r = danh_gia(_doc(ngay_het_hieu_luc=date(2025, 1, 1)), [], HOM_NAY)
    assert r.verdict is V.het_hieu_luc and r.tin_cay == "cao"


def test_muc_1_effTo_tuong_lai_thi_chua_het():
    r = danh_gia(_doc(ngay_het_hieu_luc=date(2030, 1, 1)), [], HOM_NAY)
    assert r.verdict is not V.het_hieu_luc


def test_muc_2_bat_duoc_loi_MOJ_ND_90_2019():
    """MOJ đánh 'CHL' nhưng có cạnh Thay thế từ văn bản CÙNG chủ đề đã hiệu lực."""
    doc = _doc(id="139094", ten="Nghị định về mức lương tối thiểu vùng", tinh_trang="CHL")
    canh = [{"loai": 12, "from_ten": "Nghị định quy định mức lương tối thiểu",
             "from_ngay_hieu_luc": date(2024, 7, 1), "from_so_ky_hieu": "74/2024/NĐ-CP"}]
    r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is V.bi_thay_the and r.tin_cay == "cao"
    assert "74/2024" in r.ly_do


def test_muc_2_GUARD_canh_thay_the_KHAC_CHU_DE_thi_khong_ket_luan():
    """Luật Việc làm 'thay thế' Luật BHXH — gần chắc là lỗi dữ liệu MOJ.
    Guard phải hạ xuống cần đối chiếu tay, KHÔNG kết luận hết hiệu lực."""
    doc = _doc(id="175027", ten="Luật Bảo hiểm xã hội", tinh_trang="HHL")
    canh = [{"loai": 12, "from_ten": "Luật Việc làm",
             "from_ngay_hieu_luc": date(2026, 1, 1), "from_so_ky_hieu": "74/2025/QH15"}]
    r = danh_gia(doc, canh, HOM_NAY)
    assert r.verdict is V.can_doi_chieu_tay
    assert r.tin_cay == "thap"


def test_muc_2_van_ban_thay_CHUA_hieu_luc_thi_chua_ket_luan():
    doc = _doc(ten="Nghị định về lương tối thiểu")
    canh = [{"loai": 12, "from_ten": "Nghị định về lương tối thiểu",
             "from_ngay_hieu_luc": date(2030, 1, 1), "from_so_ky_hieu": "9/2030/NĐ-CP"}]
    assert danh_gia(doc, canh, HOM_NAY).verdict is not V.bi_thay_the


def test_muc_3_HHL1P_tra_khong_xac_dinh_tin_cay_thap():
    r = danh_gia(_doc(tinh_trang="HHL1P"), [], HOM_NAY)
    assert r.verdict is V.mot_phan_khong_xac_dinh and r.tin_cay == "thap"
    assert "cấp điều khoản" in r.ly_do


def test_chua_hieu_luc_khi_ngay_hieu_luc_o_tuong_lai():
    r = danh_gia(_doc(ngay_hieu_luc=date(2030, 1, 1)), [], HOM_NAY)
    assert r.verdict is V.chua_hieu_luc and r.tin_cay == "cao"


def test_mac_dinh_con_hieu_luc_nhung_tin_cay_chi_TRUNG_BINH():
    r = danh_gia(_doc(), [], HOM_NAY)
    assert r.verdict is V.con_hieu_luc and r.tin_cay == "trung_binh", (
        "chưa đối chiếu cấp điều khoản thì không được tự tin"
    )


def test_cung_chu_de_so_theo_danh_tu_chinh():
    assert cung_chu_de("Nghị định về mức lương tối thiểu vùng",
                       "Nghị định quy định mức lương tối thiểu") is True
    assert cung_chu_de("Luật Việc làm", "Luật Bảo hiểm xã hội") is False


def test_muc_1_thang_muc_2_khi_ca_hai_dung():
    doc = _doc(ngay_het_hieu_luc=date(2025, 1, 1), ten="Nghị định lương tối thiểu")
    canh = [{"loai": 12, "from_ten": "Nghị định lương tối thiểu",
             "from_ngay_hieu_luc": date(2024, 1, 1), "from_so_ky_hieu": "a"}]
    assert danh_gia(doc, canh, HOM_NAY).verdict is V.het_hieu_luc
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_services/test_effectivity.py -v`
Expected: FAIL — `ModuleNotFoundError: src.services.effectivity`

- [ ] **Step 3: Viết `src/services/effectivity.py`**

```python
"""Suy luận hiệu lực 3 mức (spec 5.2).

effStatus của MOJ KHÔNG đủ tin: NĐ 90/2019, 157/2018, 141/2017, 122/2015 đều đã
bị thay nhưng vẫn mang trạng thái "Còn hiệu lực".

Nhưng Mức 2 KẾ THỪA lỗi phân loại của đồ thị: Luật Việc làm 74/2025 có cạnh
"Thay thế" trỏ vào Luật BHXH 41/2024 — gần chắc chắn sai. Nên Mức 2 có guard:
cạnh giữa hai văn bản khác chủ đề → hạ xuống cần đối chiếu tay, KHÔNG kết luận.
"""

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

LOAI_CHAM_DUT = {1, 5, 11, 12}  # Bãi bỏ · Đình chỉ · Tạm ngưng · Thay thế

TU_BO = {"nghị", "định", "luật", "bộ", "thông", "tư", "quy", "của", "về", "và",
         "số", "việt", "nam", "quyết", "nghị quyết", "chi", "tiết", "hướng", "dẫn",
         "một", "các", "điều"}


class EffectivityVerdict(StrEnum):
    con_hieu_luc = "con_hieu_luc"
    chua_hieu_luc = "chua_hieu_luc"
    het_hieu_luc = "het_hieu_luc"
    bi_thay_the = "bi_thay_the"
    mot_phan_khong_xac_dinh = "mot_phan_khong_xac_dinh"
    can_doi_chieu_tay = "can_doi_chieu_tay"


@dataclass(frozen=True)
class Effectivity:
    verdict: EffectivityVerdict
    tin_cay: str          # cao | trung_binh | thap
    ly_do: str


def _tu_chinh(ten: str) -> set[str]:
    tu = re.findall(r"\w+", (ten or "").lower())
    return {t for t in tu if t not in TU_BO and len(t) > 2}


def cung_chu_de(ten_a: str, ten_b: str) -> bool:
    """Guard Mức 2: hai văn bản có chia sẻ danh từ chính không?

    "Nghị định về mức lương tối thiểu vùng" vs "Nghị định quy định mức lương tối
    thiểu" → có (lương, tối, thiểu). "Luật Việc làm" vs "Luật Bảo hiểm xã hội"
    → không.
    """
    a, b = _tu_chinh(ten_a), _tu_chinh(ten_b)
    return bool(a & b)


def danh_gia(doc: dict, canh_di_vao: list[dict], as_of: date) -> Effectivity:
    # ── Mức 1: effTo đã qua ──
    het = doc.get("ngay_het_hieu_luc")
    if het and het <= as_of:
        return Effectivity(EffectivityVerdict.het_hieu_luc, "cao", f"effTo={het}")

    # ── Mức 2: có cạnh chấm dứt từ văn bản đã hiệu lực ──
    for c in canh_di_vao:
        if c.get("loai") not in LOAI_CHAM_DUT:
            continue
        hl = c.get("from_ngay_hieu_luc")
        if not hl or hl > as_of:
            continue
        if cung_chu_de(doc.get("ten", ""), c.get("from_ten", "")):
            return Effectivity(
                EffectivityVerdict.bi_thay_the, "cao",
                f"bị {c.get('from_so_ky_hieu')} thay thế từ {hl}")
        return Effectivity(
            EffectivityVerdict.can_doi_chieu_tay, "thap",
            f"có cạnh thay thế từ {c.get('from_so_ky_hieu')} nhưng KHÁC chủ đề "
            f"({c.get('from_ten')!r} vs {doc.get('ten')!r}) — nghi lỗi dữ liệu MOJ, "
            "phải đối chiếu tay")

    # ── Chưa hiệu lực ──
    bd = doc.get("ngay_hieu_luc")
    if bd and bd > as_of:
        return Effectivity(EffectivityVerdict.chua_hieu_luc, "cao", f"effFrom={bd}")

    # ── Mức 3: hết hiệu lực một phần, KHÔNG biết phần nào ──
    if doc.get("tinh_trang") == "HHL1P":
        return Effectivity(
            EffectivityVerdict.mot_phan_khong_xac_dinh, "thap",
            "văn bản hết hiệu lực một phần; CSDL quốc gia không công bố dữ liệu "
            "cấp điều khoản nên không xác định được điều này còn hiệu lực hay không")
    if doc.get("tinh_trang") == "HHL":
        return Effectivity(EffectivityVerdict.het_hieu_luc, "cao", "effStatus=HHL")

    return Effectivity(EffectivityVerdict.con_hieu_luc, "trung_binh",
                       "theo effStatus; chưa đối chiếu cấp điều khoản")
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_services/test_effectivity.py -v`
Expected: PASS (10 test)

- [ ] **Step 5: Kiểm trên dữ liệu thật — hai ca bẫy**

```python
# thêm vào tests/test_services/test_effectivity.py
import pytest
from sqlalchemy import text

from src.services.db import get_engine


def _load(doc_id: str):
    from datetime import date
    with get_engine().connect() as c:
        d = dict(c.execute(text(
            "SELECT id, so_ky_hieu, ten, ngay_hieu_luc, ngay_het_hieu_luc, tinh_trang"
            " FROM documents WHERE id = :i"), {"i": doc_id}).mappings().one())
        canh = [dict(r) for r in c.execute(text(
            'SELECT r.loai, d2.ten AS from_ten, d2.so_ky_hieu AS from_so_ky_hieu,'
            " d2.ngay_hieu_luc AS from_ngay_hieu_luc"
            ' FROM "references" r JOIN documents d2 ON d2.id = r.from_document_id'
            " WHERE r.to_document_id = :i"), {"i": doc_id}).mappings().all()]
    return d, canh, date(2026, 8, 27)


@pytest.mark.integration
def test_that_ND_74_2024_muc_1_bat_duoc():
    d, canh, ngay = _load("168670")
    assert danh_gia(d, canh, ngay).verdict is V.het_hieu_luc


@pytest.mark.integration
def test_that_ND_90_2019_KHONG_duoc_bao_la_con_hieu_luc():
    """Ca then chốt: MOJ đánh 'còn hiệu lực' nhưng đã bị thay."""
    d, canh, ngay = _load("139094")
    r = danh_gia(d, canh, ngay)
    assert r.verdict is not V.con_hieu_luc, (
        f"hệ thống tin theo effStatus sai của MOJ: {r}"
    )
```

- [ ] **Step 6: Commit**

```bash
git add src/services/effectivity.py tests/test_services/test_effectivity.py
git commit -m "feat(effectivity): three-tier inference with a guard against the graph's own errors

Tier 2 exists because MOJ still marks four superseded minimum-wage decrees as
effective, and an incoming Thay thế edge catches what effStatus misses. But tier 2
inherits the graph's misclassifications: Luật Việc làm 74/2025 carries a
document-level Thay thế edge pointing at Luật Bảo hiểm xã hội 41/2024, which a
labour-market statute cannot plausibly replace wholesale. The guard compares the
two titles' head nouns and downgrades a cross-subject edge to
can_doi_chieu_tay rather than declaring a statute dead on bad data.

Default confidence is only trung_binh, never cao: clause-level repeal data is
unpublished, so 'appears effective' is the strongest honest claim."
```

---

## Task 3: LLM service — ba vai, một key

**Files:**
- Modify: `src/services/llm.py`
- Create: `tests/test_services/test_llm.py`

**Interfaces:**
- Produces: `LlmClient(api_key, base_url, temperature)`, `.chat(model: str, messages: list[dict], json_schema: dict | None = None) -> tuple[str, Usage]`, `Usage(token_in, token_out, cost_usd)`; helper `router_model()`, `generate_model()`, `judge_model()`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_services/test_llm.py
import httpx
import pytest

from src.services.llm import LlmClient


def _c(handler) -> LlmClient:
    c = LlmClient(api_key="k", base_url="https://x/api/v1", temperature=0.0)
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_temperature_0_duoc_gui_di():
    got = {}

    def h(req):
        import json
        got.update(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}})

    _c(h).chat("m", [{"role": "user", "content": "x"}])
    assert got["temperature"] == 0.0


def test_json_schema_bien_thanh_response_format():
    got = {}

    def h(req):
        import json
        got.update(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}], "usage": {}})

    _c(h).chat("m", [{"role": "user", "content": "x"}], json_schema={"type": "object"})
    assert got["response_format"]["type"] == "json_schema"


def test_usage_va_cost_duoc_boc_ra():
    def h(req):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.00012}})

    _, u = _c(h).chat("m", [{"role": "user", "content": "x"}])
    assert u.token_in == 100 and u.token_out == 20 and u.cost_usd == 0.00012


def test_content_rong_nem_khong_tra_chuoi_rong():
    def h(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}], "usage": {}})

    with pytest.raises(ValueError, match="rỗng"):
        _c(h).chat("m", [{"role": "user", "content": "x"}])


def test_generate_va_judge_la_hai_model_khac_nhau():
    from src.services.llm import generate_model, judge_model

    assert generate_model() != judge_model()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_services/test_llm.py -v`
Expected: FAIL — template `llm.py` chỉ có `get_llm()`

- [ ] **Step 3: Viết lại `src/services/llm.py`**

```python
"""LLM qua OpenRouter — ba vai, một key.

route/rewrite : OPENROUTER_MODEL_NAME
generate      : OPENROUTER_GENERATE_MODEL_NAME  (bắt buộc structured output)
judge         : OPENROUTER_JUDGE_MODEL_NAME     (PHẢI khác họ với generate)
"""

from dataclasses import dataclass

import httpx

from src.config import get_settings


@dataclass(frozen=True)
class Usage:
    token_in: int
    token_out: int
    cost_usd: float


class LlmClient:
    def __init__(self, api_key: str, base_url: str, temperature: float) -> None:
        self.temperature = temperature
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=180,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})

    def chat(self, model: str, messages: list[dict],
             json_schema: dict | None = None) -> tuple[str, Usage]:
        body: dict = {"model": model, "messages": messages, "temperature": self.temperature}
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "klaw", "strict": True, "schema": json_schema}}
        r = self._http.post("/chat/completions", json=body)
        r.raise_for_status()
        data = r.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if not content.strip():
            raise ValueError(f"model {model} trả content rỗng")
        u = data.get("usage") or {}
        return content, Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
                              float(u.get("cost", 0.0)))


def from_settings() -> LlmClient:
    s = get_settings()
    return LlmClient(s.openrouter_api_key, s.openrouter_base_url, s.llm_temperature)


def router_model() -> str:
    return get_settings().openrouter_model_name


def generate_model() -> str:
    return get_settings().openrouter_generate_model_name


def judge_model() -> str:
    return get_settings().openrouter_judge_model_name
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_services/test_llm.py -v`
Expected: PASS (5 test)

- [ ] **Step 5: Commit**

```bash
git add src/services/llm.py tests/test_services/test_llm.py
git commit -m "feat(llm): three model roles behind one OpenRouter key

Empty content raises instead of returning an empty string, because a silent empty
response would parse to zero claims and read as 'the model found no basis' - which
is a legitimate result the system reports, so the two must never be confusable.
Usage carries the cost OpenRouter reports, which feeds traces.cost_usd and the
\$/query column of the ablation table."
```

---

## Task 4: `generate_claims` + prompt có version

**Files:**
- Create: `prompts/generate_claims.v1.md`
- Create: `src/agents/nodes/generate_claims.py`
- Create: `tests/test_agents/test_generate_claims.py`

**Interfaces:**
- Consumes: `LlmClient` (Task 3)
- Produces: `Claim(text: str, provision_id: int, quote: str)`; `CLAIMS_SCHEMA` (JSON Schema); `generate_claims(state: dict, llm, model) -> dict` cập nhật `state["draft_claims"]` và `state["insufficient_evidence"]`

- [ ] **Step 1: Viết prompt `prompts/generate_claims.v1.md`**

```markdown
Bạn là trợ lý tra cứu pháp luật Việt Nam. Bạn chỉ được dùng CÁC ĐIỀU LUẬT ĐƯỢC CUNG CẤP dưới đây.

QUY TẮC TUYỆT ĐỐI:
1. CHỈ dùng nội dung trong phần "ĐIỀU LUẬT". Không dùng kiến thức bên ngoài.
2. Mỗi khẳng định phải kèm `provision_id` của điều luật hỗ trợ nó, lấy đúng từ danh sách.
3. `quote` phải là đoạn NGUYÊN VĂN copy từ điều luật đó. Không diễn giải, không rút gọn, không sửa dấu câu.
4. Nếu các điều luật cung cấp KHÔNG trả lời được câu hỏi, đặt `insufficient_evidence: true` và `claims: []`. Đây là câu trả lời ĐÚNG, không phải thất bại.
5. Không nêu số điều nào không có trong danh sách.

CÂU HỎI:
{cau_hoi}

ĐIỀU LUẬT:
{context}
```

- [ ] **Step 2: Viết test thất bại**

```python
# tests/test_agents/test_generate_claims.py
import json

from src.agents.nodes.generate_claims import CLAIMS_SCHEMA, build_context, generate_claims


class FakeLlm:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.last: dict | None = None

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        self.last = {"model": model, "messages": messages, "schema": json_schema}
        return json.dumps(self.payload), Usage(10, 5, 0.0001)


PROVS = [
    {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26", "tieu_de": "Điều 26. Tiền lương thử việc",
     "noi_dung": "Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận "
                 "nhưng ít nhất phải bằng 85% mức lương của công việc đó.",
     "so_ky_hieu": "45/2019/QH14"},
]


def test_context_co_provision_id_va_duong_dan_khong_co_title():
    ctx = build_context(PROVS)
    assert "[provision_id=11]" in ctx
    assert "45/2019/QH14 > Điều 26" in ctx


def test_claims_duoc_parse_thanh_object():
    llm = FakeLlm({"insufficient_evidence": False, "claims": [
        {"text": "Lương thử việc ít nhất 85%.", "provision_id": 11, "quote": "ít nhất phải bằng 85%"}]})
    st = generate_claims({"query": "thử việc lương bao nhiêu", "expanded": PROVS}, llm, "m")
    assert len(st["draft_claims"]) == 1
    assert st["draft_claims"][0].provision_id == 11


def test_insufficient_evidence_duoc_ton_trong():
    llm = FakeLlm({"insufficient_evidence": True, "claims": []})
    st = generate_claims({"query": "thuế TNCN", "expanded": PROVS}, llm, "m")
    assert st["insufficient_evidence"] is True and st["draft_claims"] == []


def test_json_schema_duoc_truyen_va_bat_buoc_ba_field():
    llm = FakeLlm({"insufficient_evidence": True, "claims": []})
    generate_claims({"query": "x", "expanded": PROVS}, llm, "m")
    props = llm.last["schema"]["properties"]["claims"]["items"]
    assert set(props["required"]) == {"text", "provision_id", "quote"}


def test_json_hong_khong_lam_sap_ma_thanh_insufficient():
    class Bad(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            from src.services.llm import Usage
            return "không phải json", Usage(1, 1, 0.0)

    st = generate_claims({"query": "x", "expanded": PROVS}, Bad({}), "m")
    assert st["insufficient_evidence"] is True
    assert st["schema_error"] is True, "phải ghi nhận lỗi schema để đo tỉ lệ, không im lặng"


def test_expanded_rong_thi_khong_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không được gọi LLM khi không có điều luật nào")

    st = generate_claims({"query": "x", "expanded": []}, Never({}), "m")
    assert st["insufficient_evidence"] is True
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_agents/test_generate_claims.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Viết `src/agents/nodes/generate_claims.py`**

```python
"""Node generate_claims — LLM sinh khẳng định KÈM provision_id và quote nguyên văn.

Prompt nằm ở prompts/generate_claims.v*.md (artifact có version trong git).
JSON hỏng KHÔNG làm sập: ghi schema_error=True để đo tỉ lệ, coi như thiếu căn cứ.
"""

import json
from dataclasses import dataclass
from pathlib import Path

PROMPT_PATH = Path("prompts/generate_claims.v1.md")

CLAIMS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["insufficient_evidence", "claims"],
    "properties": {
        "insufficient_evidence": {"type": "boolean"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "provision_id", "quote"],
                "properties": {
                    "text": {"type": "string"},
                    "provision_id": {"type": "integer"},
                    "quote": {"type": "string"},
                },
            },
        },
    },
}


@dataclass(frozen=True)
class Claim:
    text: str
    provision_id: int
    quote: str


def build_context(provisions: list[dict]) -> str:
    parts: list[str] = []
    for p in provisions:
        parts.append(
            f"[provision_id={p['id']}] {p['duong_dan']}\n"
            f"{p.get('tieu_de') or ''}\n{p.get('noi_dung') or ''}".strip())
    return "\n\n---\n\n".join(parts)


def generate_claims(state: dict, llm, model: str) -> dict:
    expanded = state.get("expanded") or []
    if not expanded:
        return {**state, "draft_claims": [], "insufficient_evidence": True, "schema_error": False}

    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        cau_hoi=state["query"], context=build_context(expanded))
    raw, usage = llm.chat(model, [{"role": "user", "content": prompt}],
                          json_schema=CLAIMS_SCHEMA)
    try:
        data = json.loads(raw)
        claims = [Claim(**c) for c in data.get("claims", [])]
        insufficient = bool(data.get("insufficient_evidence"))
        schema_error = False
    except (json.JSONDecodeError, TypeError, ValueError):
        claims, insufficient, schema_error = [], True, True

    return {**state, "draft_claims": claims, "insufficient_evidence": insufficient,
            "schema_error": schema_error, "usage_generate": usage}
```

- [ ] **Step 5: Chạy lại test**

Run: `pytest tests/test_agents/test_generate_claims.py -v`
Expected: PASS (6 test)

- [ ] **Step 6: Đo tỉ lệ JSON đúng schema trên 20 câu thật (xác nhận giả định)**

```bash
python3 -c "
from src.agents.nodes.generate_claims import generate_claims
from src.services.llm import from_settings, generate_model
from src.services.db import get_engine
from sqlalchemy import text
import yaml
items = yaml.safe_load(open('eval/datasets/golden_qa.yaml',encoding='utf-8'))['items'][:20]
llm = from_settings()
with get_engine().connect() as c:
    ok = err = 0
    for it in items:
        provs=[dict(r) for r in c.execute(text(
          'SELECT p.id, p.duong_dan, p.tieu_de, p.noi_dung FROM provisions p'
          ' WHERE p.id = ANY(:ids)'), {'ids': it['provision_ids']}).mappings().all()]
        st = generate_claims({'query': it['cau_hoi'], 'expanded': provs}, llm, generate_model())
        err += st['schema_error']; ok += not st['schema_error']
print(f'schema OK {ok}/{ok+err} = {ok/(ok+err):.0%}')
"
```
**Tiêu chí: ≥95%.** Nếu thấp hơn → đổi `OPENROUTER_GENERATE_MODEL_NAME` sang `google/gemini-2.5-flash`, đo lại, ghi cả hai số vào `docs/prompt-iterations.md`.

- [ ] **Step 7: Commit**

```bash
git add prompts/generate_claims.v1.md src/agents/nodes/generate_claims.py tests/test_agents/test_generate_claims.py docs/prompt-iterations.md
git commit -m "feat(generate): claims with provision_id and verbatim quote, prompt versioned in git

Broken JSON records schema_error and degrades to insufficient_evidence rather than
raising, because the schema-validity rate is a number the thesis reports and a
crash would hide it. Two tests guard the boundary that matters: an empty context
must not reach the API at all, and insufficient_evidence must survive as a
first-class answer - abstaining is correct behaviour, not a failure to recover
from. The prompt lives in prompts/ so its revisions are diffable, which is what
makes 'citation precision 0.6 to 0.9 across four prompt versions' a reportable
result."
```

---

## Task 5: ⭐ Verify tầng 1 — bốn phép kiểm, 0 token

**Files:**
- Create: `src/agents/nodes/verify_tier1.py`
- Create: `tests/test_agents/test_verify_tier1.py`

**Interfaces:**
- Consumes: `Claim` (Task 4), `Effectivity` (Task 2)
- Produces: `Tier1Reason` (StrEnum), `Tier1Result(claim, ok, reason, effectivity)`, `verify_tier1(claims, expanded, db_provisions, effectivity_of) -> list[Tier1Result]`, `normalize(s: str) -> str`

**Đây là đóng góp chính. Luận điểm: tính hợp lệ của trích dẫn là bài toán TRA BẢNG, không phải bài toán suy luận.**

- [ ] **Step 1: Viết test thất bại — hàm thuần, 0 API call**

```python
# tests/test_agents/test_verify_tier1.py
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import normalize, verify_tier1
from src.services.effectivity import Effectivity, EffectivityVerdict as V

D26 = {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26",
       "noi_dung": "Tiền lương của người lao động trong thời gian thử việc do hai bên "
                   "thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó."}
D25 = {"id": 10, "duong_dan": "45/2019/QH14 > Điều 25", "noi_dung": "Không quá 06 ngày làm việc."}
DB = {11: D26, 10: D25}
CON_HL = Effectivity(V.con_hieu_luc, "trung_binh", "x")


def _eff(_pid):
    return CON_HL


def test_claim_hop_le_di_qua():
    c = Claim("Ít nhất 85%.", 11, "ít nhất phải bằng 85%")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is True and r.reason is R.ok


def test_kiem_1_provision_id_KHONG_TON_TAI_thi_DROP():
    c = Claim("Theo Điều 999.", 999, "bất kỳ")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is False and r.reason is R.provision_khong_ton_tai


def test_kiem_2_provision_KHONG_TRONG_CONTEXT_thi_DROP():
    """LLM lôi điều luật từ tham số của nó, không từ context đã retrieve."""
    c = Claim("Không quá 06 ngày.", 10, "Không quá 06 ngày làm việc")
    r = verify_tier1([c], [D26], DB, _eff)[0]   # context chỉ có D26
    assert r.ok is False and r.reason is R.khong_trong_context


def test_kiem_3_quote_KHONG_KHOP_NGUYEN_VAN_thi_DROP():
    """LLM 'trích dẫn' nhưng viết lại nội dung."""
    c = Claim("Ít nhất 85%.", 11, "tối thiểu 85 phần trăm mức lương")
    r = verify_tier1([c], [D26], DB, _eff)[0]
    assert r.ok is False and r.reason is R.quote_khong_khop


def test_kiem_3_khop_sau_normalize_dau_va_khoang_trang():
    c = Claim("x", 11, "ít   nhất  phải bằng   85%")
    assert verify_tier1([c], [D26], DB, _eff)[0].ok is True


def test_kiem_4_het_hieu_luc_thi_WARN_KHONG_drop():
    het = Effectivity(V.bi_thay_the, "cao", "bị 74/2024 thay thế")
    c = Claim("x", 11, "ít nhất phải bằng 85%")
    r = verify_tier1([c], [D26], DB, lambda _p: het)[0]
    assert r.ok is True, "hiệu lực là CẢNH BÁO, không phải lý do drop"
    assert r.effectivity.verdict is V.bi_thay_the


def test_quote_rong_bi_drop():
    c = Claim("x", 11, "")
    assert verify_tier1([c], [D26], DB, _eff)[0].reason is R.quote_khong_khop


def test_KHONG_goi_LLM_bang_chung_bang_khong_co_tham_so_llm():
    import inspect

    from src.agents.nodes import verify_tier1 as mod
    sig = inspect.signature(mod.verify_tier1)
    assert "llm" not in sig.parameters, "tầng 1 phải là 0 token — không nhận llm"
    src = inspect.getsource(mod)
    assert "httpx" not in src and "chat(" not in src, "tầng 1 gọi mạng — sai thiết kế"


def test_normalize_bo_dau_va_gop_khoang_trang():
    assert normalize("Ít   NHẤT  85%") == normalize("it nhat 85%")


def test_nhieu_claim_moi_claim_doc_lap():
    cs = [Claim("a", 11, "ít nhất phải bằng 85%"), Claim("b", 999, "x")]
    rs = verify_tier1(cs, [D26], DB, _eff)
    assert [r.ok for r in rs] == [True, False]
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_agents/test_verify_tier1.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Viết `src/agents/nodes/verify_tier1.py`**

```python
"""⭐ Verify tầng 1 — ĐÓNG GÓP CHÍNH của khóa luận.

Luận điểm: tính hợp lệ của trích dẫn là bài toán TRA BẢNG, không phải bài toán
suy luận. Phần lớn hệ thống hiện nay nhờ LLM tự kiểm tra chính nó — sai về
nguyên tắc. Tầng này bắt phần lớn ảo giác citation với CHI PHÍ 0 TOKEN và
độ chính xác 100% theo định nghĩa.

TUYỆT ĐỐI KHÔNG import httpx, không gọi LLM. Có test khẳng định điều đó.

Bốn phép kiểm:
  1. provision_id tồn tại trong DB?              → không thì DROP
  2. provision_id có trong tập đã retrieve?      → không thì DROP
  3. quote là substring nguyên văn (sau normalize)? → không thì DROP
  4. điều luật còn hiệu lực tại as_of_date?      → không thì WARN (vẫn trả lời)
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from src.agents.nodes.generate_claims import Claim
from src.services.effectivity import Effectivity


class Tier1Reason(StrEnum):
    ok = "ok"
    provision_khong_ton_tai = "provision_khong_ton_tai"
    khong_trong_context = "khong_trong_context"
    quote_khong_khop = "quote_khong_khop"


@dataclass(frozen=True)
class Tier1Result:
    claim: Claim
    ok: bool
    reason: Tier1Reason
    effectivity: Effectivity | None


def normalize(s: str) -> str:
    """Bỏ dấu, hạ chữ, gộp khoảng trắng — để so khớp quote chịu được khác biệt
    gõ dấu và xuống dòng, nhưng KHÔNG chịu được diễn giải lại nội dung."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[\s ]+", " ", s).strip().lower()
    return s


def verify_tier1(
    claims: list[Claim],
    expanded: list[dict],
    db_provisions: dict[int, dict],
    effectivity_of: Callable[[int], Effectivity],
) -> list[Tier1Result]:
    trong_context = {p["id"] for p in expanded}
    out: list[Tier1Result] = []

    for c in claims:
        # Kiểm 1 — tồn tại
        prov = db_provisions.get(c.provision_id)
        if prov is None:
            out.append(Tier1Result(c, False, Tier1Reason.provision_khong_ton_tai, None))
            continue

        # Kiểm 2 — có trong tập đã retrieve
        if c.provision_id not in trong_context:
            out.append(Tier1Result(c, False, Tier1Reason.khong_trong_context, None))
            continue

        # Kiểm 3 — quote nguyên văn
        if not c.quote.strip() or normalize(c.quote) not in normalize(prov.get("noi_dung", "")):
            out.append(Tier1Result(c, False, Tier1Reason.quote_khong_khop, None))
            continue

        # Kiểm 4 — hiệu lực: WARN, không DROP
        out.append(Tier1Result(c, True, Tier1Reason.ok, effectivity_of(c.provision_id)))

    return out


def citation_precision(results: list[Tier1Result]) -> float:
    """Metric riêng của đề tài: tính deterministic, không cần LLM judge."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.ok) / len(results)
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_agents/test_verify_tier1.py -v`
Expected: PASS (10 test)

- [ ] **Step 5: Commit**

```bash
git add src/agents/nodes/verify_tier1.py tests/test_agents/test_verify_tier1.py
git commit -m "feat(verify): tier-1 citation verification — four table lookups, zero tokens

This is the thesis's central claim in code: citation validity is a lookup, not an
inference. Most systems ask the model to check itself, which is wrong in
principle; this layer catches fabricated and misattributed citations at zero token
cost and, by construction, without error.

Check two is the one that is easy to omit and hardest to notice missing: a
provision may exist in the database yet never have been retrieved, which means the
model produced it from its own parameters rather than from context. Effectivity is
deliberately a warning and not a drop - a dead citation is still a real citation,
and conflating the two would hide which failure occurred.

A test asserts verify_tier1 takes no llm parameter and that the module never
imports httpx. If this layer ever needs a network call, the design is broken."
```

---

## Task 6: Verify tầng 2 — LLM judge khác họ, batch

**Files:**
- Create: `prompts/verify_tier2.v1.md`
- Create: `src/agents/nodes/verify_tier2.py`
- Create: `tests/test_agents/test_verify_tier2.py`

**Interfaces:**
- Consumes: `Tier1Result` (Task 5), `LlmClient` (Task 3)
- Produces: `Tier2Verdict(claim_index: int, supported: bool, reason: str)`; `verify_tier2(tier1: list[Tier1Result], db_provisions, llm, model) -> list[Tier2Verdict]`

- [ ] **Step 1: Viết prompt `prompts/verify_tier2.v1.md`**

```markdown
Bạn là người kiểm chứng độc lập. Với mỗi cặp (khẳng định, điều luật), xác định điều luật đó có THỰC SỰ hỗ trợ khẳng định hay không.

Quy tắc:
- `supported: true` chỉ khi nội dung điều luật trực tiếp hỗ trợ khẳng định.
- Nếu điều luật chỉ liên quan chủ đề nhưng không hỗ trợ nội dung cụ thể → `supported: false`.
- Nếu khẳng định nói rộng hơn điều luật cho phép → `supported: false`.
- Mặc định là `false` khi không chắc.

Trả về JSON: {{"verdicts": [{{"claim_index": 0, "supported": true, "reason": "..."}}]}}

CÁC CẶP CẦN KIỂM:
{pairs}
```

- [ ] **Step 2: Viết test thất bại**

```python
# tests/test_agents/test_verify_tier2.py
import json

from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import verify_tier2

DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26", "noi_dung": "…85%…"}}


class FakeLlm:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        self.calls += 1
        return json.dumps(self.payload), Usage(1, 1, 0.0)


def _ok(i):
    return Tier1Result(Claim(f"c{i}", 11, "85%"), True, R.ok, None)


def test_batch_nhieu_claim_trong_MOT_call():
    llm = FakeLlm({"verdicts": [{"claim_index": i, "supported": True, "reason": "x"}
                                for i in range(3)]})
    verify_tier2([_ok(0), _ok(1), _ok(2)], DB, llm, "m")
    assert llm.calls == 1, "phải batch, không gọi từng claim"


def test_chi_kiem_claim_DA_QUA_tang_1():
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "reason": "x"}]})
    fail = Tier1Result(Claim("bad", 999, "x"), False, R.provision_khong_ton_tai, None)
    out = verify_tier2([_ok(0), fail], DB, llm, "m")
    assert len(out) == 1 and out[0].claim_index == 0


def test_khong_co_claim_nao_qua_tang_1_thi_KHONG_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không được gọi LLM khi không có gì để kiểm")

    fail = Tier1Result(Claim("bad", 999, "x"), False, R.provision_khong_ton_tai, None)
    assert verify_tier2([fail], DB, Never({}), "m") == []


def test_verdict_thieu_thi_mac_dinh_KHONG_supported():
    llm = FakeLlm({"verdicts": []})   # judge không trả verdict cho claim 0
    out = verify_tier2([_ok(0)], DB, llm, "m")
    assert out[0].supported is False, "thiếu verdict phải mặc định false, không true"


def test_json_hong_thi_toan_bo_KHONG_supported_khong_sap():
    class Bad(FakeLlm):
        def chat(self, *a, **k):
            from src.services.llm import Usage
            return "not json", Usage(1, 1, 0.0)

    out = verify_tier2([_ok(0), _ok(1)], DB, Bad({}), "m")
    assert all(v.supported is False for v in out)
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_agents/test_verify_tier2.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Viết `src/agents/nodes/verify_tier2.py`**

```python
"""Verify tầng 2 — LLM judge, chỉ cho claim ĐÃ QUA tầng 1.

Model PHẢI khác họ với generate_claims: LLM-as-judge có self-preference bias,
model đánh giá cao output của chính nó (spec 7b.2). Batch mọi claim trong một
call để tiết kiệm.

Mặc định an toàn: thiếu verdict hoặc JSON hỏng → supported=False. Judge im lặng
không được hiểu là judge đồng ý.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.agents.nodes.verify_tier1 import Tier1Result

PROMPT_PATH = Path("prompts/verify_tier2.v1.md")

VERDICTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdicts"],
    "properties": {"verdicts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["claim_index", "supported", "reason"],
        "properties": {"claim_index": {"type": "integer"},
                       "supported": {"type": "boolean"},
                       "reason": {"type": "string"}}}}},
}


@dataclass(frozen=True)
class Tier2Verdict:
    claim_index: int
    supported: bool
    reason: str


def verify_tier2(tier1: list[Tier1Result], db_provisions: dict[int, dict],
                 llm, model: str) -> list[Tier2Verdict]:
    qua = [(i, r) for i, r in enumerate(tier1) if r.ok]
    if not qua:
        return []

    pairs: list[str] = []
    for pos, (_, r) in enumerate(qua):
        prov = db_provisions.get(r.claim.provision_id, {})
        pairs.append(
            f"claim_index={pos}\n"
            f"KHẲNG ĐỊNH: {r.claim.text}\n"
            f"ĐIỀU LUẬT ({prov.get('duong_dan','?')}): {prov.get('noi_dung','')}")

    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(pairs="\n\n---\n\n".join(pairs))
    try:
        raw, _ = llm.chat(model, [{"role": "user", "content": prompt}],
                          json_schema=VERDICTS_SCHEMA)
        got = {v["claim_index"]: v for v in json.loads(raw).get("verdicts", [])}
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        got = {}

    out: list[Tier2Verdict] = []
    for pos, _ in enumerate(qua):
        v = got.get(pos)
        out.append(Tier2Verdict(
            claim_index=pos,
            supported=bool(v.get("supported")) if v else False,
            reason=(v or {}).get("reason", "judge không trả verdict → mặc định không hỗ trợ")))
    return out
```

- [ ] **Step 5: Chạy lại test**

Run: `pytest tests/test_agents/test_verify_tier2.py -v`
Expected: PASS (5 test)

- [ ] **Step 6: Commit**

```bash
git add prompts/verify_tier2.v1.md src/agents/nodes/verify_tier2.py tests/test_agents/test_verify_tier2.py
git commit -m "feat(verify): tier-2 judge on a different model family, batched, fail-closed

The judge model must differ in family from the generator: LLM-as-judge carries
self-preference bias, so sharing a model would systematically inflate
faithfulness. Tier 2 only sees claims that already passed tier 1, so the expensive
layer never pays for citations the free layer already rejected.

Every failure path defaults to supported=False. A silent judge is not an agreeing
judge, and a broken response must not become a passing grade - the asymmetry is
deliberate, because an inflated faithfulness number is worse than a low one."
```

---

## Task 7: `expand` — Khoản→Điều, reference 1 hop, lọc hiệu lực

**Files:**
- Create: `src/agents/nodes/expand.py`
- Create: `tests/test_agents/test_expand.py`

**Interfaces:**
- Consumes: `Retriever.provision_ids` (plan 2), `danh_gia` (Task 2)
- Produces: `expand(provision_ids: list[int], engine, as_of, hops: int) -> tuple[list[dict], list[dict]]` → `(expanded_deep, hits_shallow)`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_agents/test_expand.py
import pytest
from datetime import date
from sqlalchemy import text

from src.agents.nodes.expand import expand
from src.services.db import get_engine


@pytest.mark.integration
def test_khop_KHOAN_thi_tra_ve_ca_DIEU_cha():
    with get_engine().connect() as c:
        khoan = c.execute(text(
            "SELECT id, parent_id FROM provisions WHERE cap='khoan' AND parent_id IS NOT NULL LIMIT 1"
        )).mappings().one()
    deep, _ = expand([khoan["id"]], get_engine(), date(2026, 8, 27), hops=1)
    ids = {p["id"] for p in deep}
    assert khoan["parent_id"] in ids, "parent-document retrieval không hoạt động"


@pytest.mark.integration
def test_expand_1_hop_theo_reference_khong_lap_sau():
    with get_engine().connect() as c:
        row = c.execute(text(
            'SELECT from_provision_id, to_provision_id FROM "references"'
            " WHERE from_provision_id IS NOT NULL LIMIT 1")).mappings().first()
    if row is None:
        pytest.skip("chưa có cạnh cấp điều khoản")
    deep, _ = expand([row["from_provision_id"]], get_engine(), date(2026, 8, 27), hops=1)
    assert row["to_provision_id"] in {p["id"] for p in deep}


@pytest.mark.integration
def test_hops_0_thi_khong_expand_reference():
    with get_engine().connect() as c:
        row = c.execute(text(
            'SELECT from_provision_id, to_provision_id FROM "references"'
            " WHERE from_provision_id IS NOT NULL LIMIT 1")).mappings().first()
    if row is None:
        pytest.skip("chưa có cạnh")
    deep, _ = expand([row["from_provision_id"]], get_engine(), date(2026, 8, 27), hops=0)
    assert row["to_provision_id"] not in {p["id"] for p in deep}


@pytest.mark.integration
def test_tach_deep_va_shallow_theo_documents_depth():
    with get_engine().begin() as c:
        c.execute(text("UPDATE documents SET depth='shallow' WHERE id='70811'"))
        pid = c.execute(text(
            "SELECT id FROM provisions WHERE document_id='70811' LIMIT 1")).scalar_one()
    deep, shallow = expand([pid], get_engine(), date(2026, 8, 27), hops=1)
    assert pid in {p["id"] for p in shallow}
    assert pid not in {p["id"] for p in deep}
    with get_engine().begin() as c:
        c.execute(text("UPDATE documents SET depth='deep' WHERE id='70811'"))


@pytest.mark.integration
def test_moi_provision_mang_effectivity_va_so_ky_hieu_khong_mang_title():
    with get_engine().connect() as c:
        pid = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
    deep, _ = expand([pid], get_engine(), date(2026, 8, 27), hops=1)
    p = deep[0]
    assert "effectivity" in p and "so_ky_hieu" in p
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_agents/test_expand.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Viết `src/agents/nodes/expand.py`**

```python
"""Node expand — mở rộng tập provision đã retrieve.

Ba việc:
  1. Khoản → Điều (parent-document retrieval): khớp Khoản thì đưa cả Điều cho LLM
  2. Reference 1 hop: thêm các provision được dẫn chiếu trực tiếp. KHÔNG lặp sâu
  3. Tách deep vs shallow: shallow chỉ để xác định ranh giới phủ (PARTIAL_COVERAGE)
"""

from datetime import date

from sqlalchemy import Engine, text

from src.services.effectivity import danh_gia

SQL_PROV = (
    "SELECT p.id, p.document_id, p.parent_id, p.cap, p.so_hieu_cap, p.tieu_de,"
    " p.noi_dung, p.duong_dan, d.so_ky_hieu, d.ten, d.depth, d.tinh_trang,"
    " d.ngay_hieu_luc, d.ngay_het_hieu_luc"
    " FROM provisions p JOIN documents d ON d.id = p.document_id"
    " WHERE p.id = ANY(:ids)"
)


def _canh_di_vao(conn, doc_ids: set[str]) -> dict[str, list[dict]]:
    if not doc_ids:
        return {}
    rows = conn.execute(text(
        'SELECT r.to_document_id, r.loai, d2.ten AS from_ten,'
        " d2.so_ky_hieu AS from_so_ky_hieu, d2.ngay_hieu_luc AS from_ngay_hieu_luc"
        ' FROM "references" r JOIN documents d2 ON d2.id = r.from_document_id'
        " WHERE r.to_document_id = ANY(:ids)"
    ), {"ids": list(doc_ids)}).mappings().all()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["to_document_id"], []).append(dict(r))
    return out


def expand(provision_ids: list[int], engine: Engine, as_of: date,
           hops: int) -> tuple[list[dict], list[dict]]:
    if not provision_ids:
        return [], []

    ids = list(dict.fromkeys(provision_ids))
    with engine.connect() as conn:
        # 1 — Khoản/Điểm → Điều cha
        parents = conn.execute(text(
            "SELECT DISTINCT parent_id FROM provisions"
            " WHERE id = ANY(:ids) AND parent_id IS NOT NULL AND cap IN ('khoan','diem')"
        ), {"ids": ids}).scalars().all()
        ids += [p for p in parents if p is not None]

        # 2 — reference 1 hop
        if hops > 0:
            targets = conn.execute(text(
                'SELECT DISTINCT to_provision_id FROM "references"'
                " WHERE from_provision_id = ANY(:ids) AND to_provision_id IS NOT NULL"
            ), {"ids": ids}).scalars().all()
            ids += list(targets)

        ids = list(dict.fromkeys(ids))
        rows = [dict(r) for r in conn.execute(text(SQL_PROV), {"ids": ids}).mappings().all()]
        canh = _canh_di_vao(conn, {r["document_id"] for r in rows})

    deep: list[dict] = []
    shallow: list[dict] = []
    for r in rows:
        r["effectivity"] = danh_gia(r, canh.get(r["document_id"], []), as_of)
        (shallow if r.get("depth") == "shallow" else deep).append(r)

    # giữ thứ tự retrieval gốc trước, rồi mới đến phần expand thêm
    uu_tien = {pid: i for i, pid in enumerate(provision_ids)}
    deep.sort(key=lambda p: uu_tien.get(p["id"], 10**6))
    shallow.sort(key=lambda p: uu_tien.get(p["id"], 10**6))
    return deep, shallow
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_agents/test_expand.py -v`
Expected: PASS (5 test)

- [ ] **Step 5: Commit**

```bash
git add src/agents/nodes/expand.py tests/test_agents/test_expand.py
git commit -m "feat(expand): parent articles, one reference hop, and the deep/shallow split

Matching a clause returns its whole article, so the model reads at article level
while retrieval still scores at clause level. Reference expansion is capped at one
hop by parameter, and a test asserts hops=0 really disables it - that switch is an
ablation row, not a constant. The deep/shallow split is what makes
PARTIAL_COVERAGE possible: when only shallow provisions match, there is nothing to
answer from and the system says so instead of guessing."
```

---

## Task 8: `route` và `rewrite_query`

**Files:**
- Create: `prompts/route.v1.md`, `prompts/rewrite_query.v1.md`
- Create: `src/agents/nodes/route.py`, `src/agents/nodes/rewrite_query.py`
- Create: `tests/test_agents/test_route.py`

**Interfaces:**
- Produces: `Intent` (StrEnum: `tra_cuu`, `soan_thao`, `ngoai_pham_vi`); `route(state, llm, model) -> dict`; `rewrite_query(state, llm, model) -> dict` (thêm `state["queries"]: list[str]`, phần tử 0 là query gốc)

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_agents/test_route.py
import json

from src.agents.nodes.route import Intent, route
from src.agents.nodes.rewrite_query import rewrite_query


class FakeLlm:
    def __init__(self, payload):
        self.payload = payload

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        return json.dumps(self.payload), Usage(1, 1, 0.0)


def test_route_tra_ve_intent_hop_le():
    st = route({"query": "thử việc bao lâu"}, FakeLlm({"intent": "tra_cuu"}), "m")
    assert st["intent"] is Intent.tra_cuu


def test_route_intent_la_khong_ro_thi_mac_dinh_tra_cuu():
    """Route sai sang ngoai_pham_vi làm hệ thống từ chối oan — mặc định an toàn
    là cứ tra cứu rồi để verifier/abstain quyết."""
    st = route({"query": "x"}, FakeLlm({"intent": "khong_biet"}), "m")
    assert st["intent"] is Intent.tra_cuu


def test_route_json_hong_thi_mac_dinh_tra_cuu():
    class Bad(FakeLlm):
        def chat(self, *a, **k):
            from src.services.llm import Usage
            return "not json", Usage(1, 1, 0.0)

    assert route({"query": "x"}, Bad({}), "m")["intent"] is Intent.tra_cuu


def test_rewrite_luon_giu_query_GOC_o_vi_tri_0():
    st = rewrite_query({"query": "công ty cho nghỉ không báo trước"},
                       FakeLlm({"queries": ["nghĩa vụ thông báo khi đơn phương chấm dứt HĐLĐ"]}), "m")
    assert st["queries"][0] == "công ty cho nghỉ không báo trước", (
        "mất query gốc thì rewrite tệ sẽ làm mất luôn kết quả đúng"
    )
    assert len(st["queries"]) == 2


def test_rewrite_loi_thi_van_con_query_goc():
    class Bad(FakeLlm):
        def chat(self, *a, **k):
            raise RuntimeError("api down")

    st = rewrite_query({"query": "abc"}, Bad({}), "m")
    assert st["queries"] == ["abc"]
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_agents/test_route.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Viết hai prompt**

`prompts/route.v1.md`:
```markdown
Phân loại ý định của câu hỏi sau. Phạm vi hệ thống: 6 Bộ luật của Việt Nam (Dân sự, Hình sự, Tố tụng dân sự, Tố tụng hình sự, Lao động, Hàng hải) và các văn bản hướng dẫn về lao động.

- `tra_cuu`: hỏi về nội dung pháp luật
- `soan_thao`: yêu cầu soạn hoặc soát một văn bản (hợp đồng lao động, nội quy lao động, quyết định kỷ luật)
- `ngoai_pham_vi`: rõ ràng không thuộc phạm vi (thuế, đất đai, hành chính, y tế…) hoặc không phải câu hỏi pháp luật

Nếu không chắc, chọn `tra_cuu`.

Trả về JSON: {{"intent": "tra_cuu"}}

CÂU HỎI: {cau_hoi}
```

`prompts/rewrite_query.v1.md`:
```markdown
Câu hỏi sau viết bằng ngôn ngữ đời thường. Hãy viết lại thành 1–2 truy vấn dùng thuật ngữ pháp lý Việt Nam, để tìm trong văn bản luật.

Chỉ trả truy vấn, không giải thích. Không thêm số điều.

Trả về JSON: {{"queries": ["...", "..."]}}

CÂU HỎI: {cau_hoi}
```

- [ ] **Step 4: Viết hai node**

```python
# src/agents/nodes/route.py
"""Node route — phân loại ý định. Mặc định an toàn là tra_cuu."""

import json
from enum import StrEnum
from pathlib import Path

PROMPT_PATH = Path("prompts/route.v1.md")

INTENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["intent"],
                 "properties": {"intent": {"type": "string",
                                           "enum": ["tra_cuu", "soan_thao", "ngoai_pham_vi"]}}}


class Intent(StrEnum):
    tra_cuu = "tra_cuu"
    soan_thao = "soan_thao"
    ngoai_pham_vi = "ngoai_pham_vi"


def route(state: dict, llm, model: str) -> dict:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(cau_hoi=state["query"])
    try:
        raw, _ = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=INTENT_SCHEMA)
        intent = Intent(json.loads(raw)["intent"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, RuntimeError):
        # Route sai sang ngoai_pham_vi làm hệ thống từ chối oan.
        # Mặc định tra_cuu, để verifier và abstain quyết định.
        intent = Intent.tra_cuu
    return {**state, "intent": intent}
```

```python
# src/agents/nodes/rewrite_query.py
"""Node rewrite_query — dân sinh → ngôn ngữ pháp lý (pain point #3).

LUÔN giữ query gốc ở vị trí 0: rewrite tệ không được làm mất kết quả đúng.
Ablate được bằng cách bỏ node này khỏi graph.
"""

import json
from pathlib import Path

PROMPT_PATH = Path("prompts/rewrite_query.v1.md")

QUERIES_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["queries"],
                  "properties": {"queries": {"type": "array", "items": {"type": "string"},
                                             "maxItems": 3}}}


def rewrite_query(state: dict, llm, model: str) -> dict:
    goc = state["query"]
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(cau_hoi=goc)
    try:
        raw, _ = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=QUERIES_SCHEMA)
        them = [q for q in json.loads(raw).get("queries", []) if q and q.strip() != goc.strip()]
    except Exception:
        them = []
    return {**state, "queries": [goc, *them[:2]]}
```

- [ ] **Step 5: Chạy lại test**

Run: `pytest tests/test_agents/test_route.py -v`
Expected: PASS (5 test)

- [ ] **Step 6: Commit**

```bash
git add prompts/route.v1.md prompts/rewrite_query.v1.md src/agents/nodes/route.py src/agents/nodes/rewrite_query.py tests/test_agents/test_route.py
git commit -m "feat(nodes): route defaults to lookup, rewrite always keeps the original query

Both nodes fail toward doing more work rather than less. A route error defaults to
tra_cuu because misrouting to ngoai_pham_vi refuses a question the system could
have answered, and refusing wrongly is the failure mode that most undermines a
system whose contribution is knowing when to abstain. Rewrite keeps the user's
original wording at index 0, so a bad rewrite can only add noise, never remove the
phrasing that would have worked."
```

---

## Task 9: `assemble` — bốn loại kết quả

**Files:**
- Create: `prompts/assemble.v1.md`
- Create: `src/agents/nodes/assemble.py`
- Create: `tests/test_agents/test_assemble.py`

**Interfaces:**
- Produces: `ResultType` (StrEnum: `answer`, `partial_coverage`, `abstain`, `out_of_scope`); `Citation`; `assemble(state, db_provisions, llm, model) -> dict`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_agents/test_assemble.py
import json

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity, EffectivityVerdict as V

DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26", "so_ky_hieu": "45/2019/QH14",
           "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}
EFF = Effectivity(V.con_hieu_luc, "trung_binh", "x")


class FakeLlm:
    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        return json.dumps({"answer": "Ít nhất 85% mức lương."}), Usage(1, 1, 0.0)


def _pass(pid=11):
    return Tier1Result(Claim("Ít nhất 85%.", pid, "85%"), True, R.ok, EFF)


def test_ngoai_pham_vi_tra_out_of_scope_va_KHONG_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("không gọi LLM khi ngoài phạm vi")

    st = assemble({"intent": "ngoai_pham_vi"}, DB, Never(), "m")
    assert st["result_type"] is ResultType.out_of_scope and st["answer"] is None


def test_deep_rong_shallow_co_thi_partial_coverage_va_KHONG_goi_LLM():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("PARTIAL_COVERAGE phải là nhánh 0 token")

    st = assemble({"intent": "tra_cuu", "expanded": [], "hits_shallow": [
        {"id": 5, "duong_dan": "84/2015/QH13 > Điều 3", "so_ky_hieu": "84/2015/QH13",
         "ten": "Luật An toàn, vệ sinh lao động"}]}, DB, Never(), "m")
    assert st["result_type"] is ResultType.partial_coverage
    assert st["answer"] is None
    assert "84/2015/QH13" in st["coverage_note"]


def test_khong_claim_nao_qua_tang_1_thi_abstain():
    fail = Tier1Result(Claim("x", 999, "y"), False, R.provision_khong_ton_tai, None)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [fail],
                   "tier2": [], "abstain_threshold": 0.5}, DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain


def test_ty_le_verified_duoi_nguong_thi_abstain():
    ok = _pass()
    fails = [Tier1Result(Claim("x", 999, "y"), False, R.provision_khong_ton_tai, None)] * 3
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [ok, *fails],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain, "1/4 = 0.25 < 0.5"


def test_insufficient_evidence_tu_LLM_duoc_ton_trong():
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "insufficient_evidence": True,
                   "tier1": [], "tier2": [], "abstain_threshold": 0.5}, DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain


def test_tang_2_bac_thi_claim_bi_loai_khoi_citation():
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, False, "không hỗ trợ")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain


def test_answer_mang_citation_co_bo_luat_va_so_ky_hieu_khong_mang_title():
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.answer
    c = st["citations"][0]
    assert c["so_ky_hieu"] == "45/2019/QH14" and c["duong_dan"].startswith("45/2019/QH14")


def test_hieu_luc_khong_chac_sinh_warning():
    mp = Effectivity(V.mot_phan_khong_xac_dinh, "thap", "HHL1P")
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, mp)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["warnings"], "điều luật hết hiệu lực một phần phải sinh cảnh báo"
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_agents/test_assemble.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Viết `prompts/assemble.v1.md`**

```markdown
Viết câu trả lời ngắn gọn cho câu hỏi, CHỈ dựa vào các khẳng định đã được kiểm chứng dưới đây. Không thêm thông tin nào khác. Không nêu số điều — hệ thống sẽ tự gắn dẫn nguồn.

Trả về JSON: {{"answer": "..."}}

CÂU HỎI: {cau_hoi}

KHẲNG ĐỊNH ĐÃ KIỂM CHỨNG:
{claims}
```

- [ ] **Step 4: Viết `src/agents/nodes/assemble.py`**

```python
"""Node assemble — quyết định một trong BỐN loại kết quả (spec 6.2).

answer            : có claim qua cả hai tầng
partial_coverage  : chỉ trúng tầng nông → nêu luật, KHÔNG diễn giải. 0 TOKEN
abstain           : không đủ căn cứ. HÀNH VI ĐÚNG, không phải lỗi
out_of_scope      : route xác định ngoài phạm vi. 0 TOKEN
"""

import json
from enum import StrEnum
from pathlib import Path

from src.services.effectivity import EffectivityVerdict as V

PROMPT_PATH = Path("prompts/assemble.v1.md")

ANSWER_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answer"],
                 "properties": {"answer": {"type": "string"}}}

CANH_BAO = {
    V.mot_phan_khong_xac_dinh:
        "Văn bản này hết hiệu lực một phần. Cơ sở dữ liệu quốc gia không công bố "
        "dữ liệu bãi bỏ cấp điều khoản, nên không xác định được điều luật này còn "
        "hiệu lực hay không.",
    V.bi_thay_the: "Văn bản này đã bị thay thế.",
    V.het_hieu_luc: "Văn bản này đã hết hiệu lực.",
    V.chua_hieu_luc: "Văn bản này chưa có hiệu lực.",
    V.can_doi_chieu_tay:
        "Trạng thái hiệu lực của văn bản này không xác định được tự động, cần đối chiếu tay.",
}


class ResultType(StrEnum):
    answer = "answer"
    partial_coverage = "partial_coverage"
    abstain = "abstain"
    out_of_scope = "out_of_scope"


def _base(state: dict, rt: ResultType, **kw) -> dict:
    return {**state, "result_type": rt, "answer": None, "citations": [],
            "warnings": [], "coverage_note": None, **kw}


def assemble(state: dict, db_provisions: dict[int, dict], llm, model: str) -> dict:
    if state.get("intent") == "ngoai_pham_vi":
        return _base(state, ResultType.out_of_scope,
                     coverage_note="Câu hỏi ngoài phạm vi hệ thống: 6 Bộ luật của Việt Nam; "
                                   "soạn thảo chỉ trong lĩnh vực lao động.")

    deep = state.get("expanded") or []
    shallow = state.get("hits_shallow") or []

    # PARTIAL_COVERAGE — nhánh xác định, KHÔNG gọi LLM
    if not deep and shallow:
        luat = sorted({f"{p['so_ky_hieu']} ({p.get('ten') or ''})".strip() for p in shallow})
        dieu = ", ".join(p["duong_dan"] for p in shallow[:3])
        return _base(state, ResultType.partial_coverage, coverage_note=(
            f"Câu hỏi thuộc {'; '.join(luat)} — liên quan {dieu}. "
            "KLAW phủ sâu 6 Bộ luật và các văn bản hướng dẫn về lao động; "
            "chưa phủ nghị định/thông tư hướng dẫn lĩnh vực này nên không diễn giải chi tiết."))

    if state.get("insufficient_evidence"):
        return _base(state, ResultType.abstain)

    tier1 = state.get("tier1") or []
    tier2 = {v.claim_index: v for v in (state.get("tier2") or [])}
    qua_t1 = [r for r in tier1 if r.ok]

    if not tier1 or not qua_t1:
        return _base(state, ResultType.abstain)

    # tier2 index theo vị trí trong danh sách đã qua tầng 1
    verified = [r for pos, r in enumerate(qua_t1)
                if (tier2.get(pos).supported if tier2.get(pos) else not tier2)]
    ty_le = len(verified) / len(tier1)
    if not verified or ty_le < float(state.get("abstain_threshold", 0.5)):
        return _base(state, ResultType.abstain)

    citations: list[dict] = []
    warnings: list[str] = []
    for r in verified:
        p = db_provisions.get(r.claim.provision_id, {})
        eff = r.effectivity
        citations.append({
            "provision_id": r.claim.provision_id,
            "duong_dan": p.get("duong_dan", ""),
            "bo_luat": p.get("ten", ""),
            "so_ky_hieu": p.get("so_ky_hieu", ""),
            "quote": r.claim.quote,
            "hieu_luc": eff.verdict.value if eff else None,
            "tin_cay": eff.tin_cay if eff else None,
        })
        if eff and eff.verdict in CANH_BAO:
            msg = f"{p.get('so_ky_hieu','')}: {CANH_BAO[eff.verdict]}"
            if msg not in warnings:
                warnings.append(msg)

    claims_txt = "\n".join(f"- {r.claim.text}" for r in verified)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        cau_hoi=state["query"], claims=claims_txt)
    try:
        raw, _ = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=ANSWER_SCHEMA)
        answer = json.loads(raw)["answer"]
    except Exception:
        answer = " ".join(r.claim.text for r in verified)

    return _base(state, ResultType.answer, answer=answer,
                 citations=citations, warnings=warnings)
```

- [ ] **Step 5: Chạy lại test**

Run: `pytest tests/test_agents/test_assemble.py -v`
Expected: PASS (8 test)

- [ ] **Step 6: Commit**

```bash
git add prompts/assemble.v1.md src/agents/nodes/assemble.py tests/test_agents/test_assemble.py
git commit -m "feat(assemble): four result types, two of them costing zero tokens

out_of_scope and partial_coverage never reach the LLM, which is not an
optimisation: a branch that cannot generate text cannot hallucinate, so
partial_coverage names the governing statute and states the coverage boundary by
construction. Tests assert both branches raise if an LLM is called at all.

Abstain triggers three ways - the model reporting insufficient evidence, nothing
surviving tier 1, or the verified ratio falling below threshold - and it is
returned as a result, not an error. Effectivity produces warnings alongside a real
answer rather than suppressing it, and the partially-expired wording says plainly
that the national database does not publish clause-level repeal data."
```

---

## Task 10: Graph + endpoint + tập bẫy

**Files:**
- Create: `src/agents/graph_tra_cuu.py`, `src/agents/state.py` *(modify)*
- Modify: `src/api/routes.py`, `src/models/schemas.py`
- Create: `eval/datasets/trap.yaml`
- Create: `tests/test_api/test_tra_cuu.py`

**Interfaces:**
- Produces: `build_graph_tra_cuu()`; `POST /api/v1/tra-cuu` → `TraCuuResponse` (spec 8.0a); `eval/datasets/trap.yaml` 40 câu

- [ ] **Step 1: Viết `eval/datasets/trap.yaml` — 40 câu, ba nhóm**

```yaml
items:
  # ── Nhóm 1: điều luật KHÔNG tồn tại (15 câu) ──
  - id: trap-nonexist-01
    cau_hoi: "Điều 999 Bộ luật Lao động quy định gì về nghỉ phép"
    nhom: dieu_khong_ton_tai
    ky_vong: abstain
  # … 14 câu nữa, số điều vượt quá số điều thật của từng bộ luật

  # ── Nhóm 2: ngoài phạm vi (15 câu) ──
  - id: trap-oos-01
    cau_hoi: "thu nhập bao nhiêu thì phải đóng thuế thu nhập cá nhân"
    nhom: ngoai_pham_vi
    ky_vong: out_of_scope
  # … thuế, đất đai, hành chính, y tế, giáo dục — KHÔNG Bộ luật nào phủ

  # ── Nhóm 3: văn bản ĐÃ BỊ THAY THẾ (10 câu) ──
  - id: trap-superseded-01
    cau_hoi: "mức lương tối thiểu vùng một hiện nay là bao nhiêu"
    nhom: van_ban_bi_thay
    doc_id_bay: "139094"     # NĐ 90/2019 — MOJ đánh sai "còn hiệu lực"
    ky_vong: warning_bi_thay_the
  - id: trap-superseded-02
    cau_hoi: "lương tối thiểu vùng bốn theo quy định năm hai nghìn hai mươi bốn"
    nhom: van_ban_bi_thay
    doc_id_bay: "168670"     # NĐ 74/2024 — hết hiệu lực toàn bộ
    ky_vong: warning_het_hieu_luc
```

**Viết đủ 40 câu.** Nhóm 3 là nhóm quan trọng nhất: nó test cơ chế Mức 2 bắt được lỗi của chính CSDL quốc gia.

- [ ] **Step 2: Viết test thất bại**

```python
# tests/test_api/test_tra_cuu.py
import pytest


@pytest.mark.asyncio
async def test_tra_cuu_tra_ve_result_type_khong_phai_bool_abstained(client):
    r = await client.post("/api/v1/tra-cuu", json={"query": "thử việc bao lâu"})
    assert r.status_code == 200
    d = r.json()
    assert "result_type" in d and "abstained" not in d
    assert d["result_type"] in {"answer", "partial_coverage", "abstain", "out_of_scope"}


@pytest.mark.asyncio
async def test_query_rong_bi_422(client):
    r = await client.post("/api/v1/tra-cuu", json={"query": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_response_luon_co_trace_id_va_config_name(client):
    d = (await client.post("/api/v1/tra-cuu", json={"query": "x"})).json()
    assert d["trace_id"] and d["config_name"]


@pytest.mark.asyncio
async def test_citation_khong_bao_gio_thieu_duong_dan(client):
    d = (await client.post("/api/v1/tra-cuu", json={"query": "thử việc lương bao nhiêu"})).json()
    assert all(c["duong_dan"] and c["so_ky_hieu"] for c in d["citations"])
```

- [ ] **Step 3: Viết graph + state + endpoint**

```python
# src/agents/state.py  (thay nội dung cũ)
from __future__ import annotations

from typing import TypedDict


class KLawState(TypedDict, total=False):
    # vào
    query: str
    as_of_date: object            # date | None
    config_name: str
    abstain_threshold: float
    # trung gian
    intent: object
    queries: list[str]
    retrieved: list[int]
    expanded: list[dict]
    hits_shallow: list[dict]
    draft_claims: list
    insufficient_evidence: bool
    schema_error: bool
    tier1: list
    tier2: list
    # ra
    result_type: object
    answer: str | None
    citations: list[dict]
    warnings: list[str]
    coverage_note: str | None
    trace_id: str
```

```python
# src/agents/graph_tra_cuu.py
"""Graph tra cứu (spec mục 6).

route → rewrite_query → retrieve_hybrid → expand → generate_claims
      → verify_tier1 → verify_tier2 → assemble
"""

from datetime import date

from langgraph.graph import END, StateGraph
from sqlalchemy import text

from src.agents.nodes.assemble import assemble
from src.agents.nodes.expand import expand
from src.agents.nodes.generate_claims import generate_claims
from src.agents.nodes.route import Intent, route
from src.agents.nodes.rewrite_query import rewrite_query
from src.agents.nodes.verify_tier1 import verify_tier1
from src.agents.nodes.verify_tier2 import verify_tier2
from src.agents.state import KLawState
from src.config import get_settings
from src.services.db import get_engine
from src.services.effectivity import danh_gia
from src.services.embedding import from_settings as embedder_from_settings
from src.services.llm import from_settings as llm_from_settings
from src.services.llm import generate_model, judge_model, router_model
from src.services.retrieval import Retriever


def _db_provisions(ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    with get_engine().connect() as c:
        return {r["id"]: dict(r) for r in c.execute(text(
            "SELECT p.id, p.duong_dan, p.noi_dung, p.tieu_de, d.so_ky_hieu, d.ten,"
            " d.tinh_trang, d.ngay_hieu_luc, d.ngay_het_hieu_luc"
            " FROM provisions p JOIN documents d ON d.id = p.document_id"
            " WHERE p.id = ANY(:ids)"), {"ids": ids}).mappings().all()}


def build_graph_tra_cuu():
    s = get_settings()
    llm = llm_from_settings()
    retriever = Retriever(get_engine(), embedder_from_settings(), s)

    def n_route(st: KLawState) -> KLawState:
        return route(st, llm, router_model())

    def n_rewrite(st: KLawState) -> KLawState:
        return rewrite_query(st, llm, router_model())

    def n_retrieve(st: KLawState) -> KLawState:
        ids: list[int] = []
        for q in st.get("queries") or [st["query"]]:
            ids += retriever.provision_ids(retriever.hybrid(q))
        return {**st, "retrieved": list(dict.fromkeys(ids))}

    def n_expand(st: KLawState) -> KLawState:
        as_of = st.get("as_of_date") or s.as_of_date or date.today()
        deep, shallow = expand(st.get("retrieved") or [], get_engine(), as_of,
                               s.expand_reference_hops)
        return {**st, "expanded": deep, "hits_shallow": shallow}

    def n_generate(st: KLawState) -> KLawState:
        if not st.get("expanded"):
            return {**st, "draft_claims": [], "insufficient_evidence": True}
        return generate_claims(st, llm, generate_model())

    def n_tier1(st: KLawState) -> KLawState:
        claims = st.get("draft_claims") or []
        dbp = _db_provisions([c.provision_id for c in claims])
        canh: dict = {}
        return {**st, "tier1": verify_tier1(
            claims, st.get("expanded") or [], dbp,
            lambda pid: danh_gia(dbp.get(pid, {}), canh.get(pid, []),
                                 st.get("as_of_date") or date.today()))}

    def n_tier2(st: KLawState) -> KLawState:
        if not s.verify_tier2_enabled:
            return {**st, "tier2": []}
        t1 = st.get("tier1") or []
        dbp = _db_provisions([r.claim.provision_id for r in t1 if r.ok])
        return {**st, "tier2": verify_tier2(t1, dbp, llm, judge_model())}

    def n_assemble(st: KLawState) -> KLawState:
        ids = [r.claim.provision_id for r in (st.get("tier1") or [])]
        return assemble({**st, "abstain_threshold": s.abstain_threshold},
                        _db_provisions(ids), llm, generate_model())

    g = StateGraph(KLawState)
    for name, fn in (("route", n_route), ("rewrite", n_rewrite), ("retrieve", n_retrieve),
                     ("expand", n_expand), ("generate", n_generate), ("tier1", n_tier1),
                     ("tier2", n_tier2), ("assemble", n_assemble)):
        g.add_node(name, fn)

    g.set_entry_point("route")
    g.add_conditional_edges("route", lambda st: (
        "assemble" if st.get("intent") is Intent.ngoai_pham_vi else "rewrite"))
    for a, b in (("rewrite", "retrieve"), ("retrieve", "expand"), ("expand", "generate"),
                 ("generate", "tier1"), ("tier1", "tier2"), ("tier2", "assemble")):
        g.add_edge(a, b)
    g.add_edge("assemble", END)
    return g.compile()
```

Thêm vào `src/models/schemas.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field


class TraCuuRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    as_of_date: str | None = None
    config_name: str | None = None


class CitationOut(BaseModel):
    provision_id: int
    duong_dan: str
    bo_luat: str
    so_ky_hieu: str
    quote: str
    hieu_luc: str | None = None
    tin_cay: str | None = None


class TraCuuResponse(BaseModel):
    result_type: Literal["answer", "partial_coverage", "abstain", "out_of_scope"]
    answer: str | None
    citations: list[CitationOut]
    warnings: list[str]
    coverage_note: str | None
    trace_id: str
    config_name: str
```

Thay `/chat` trong `src/api/routes.py` bằng:

```python
import uuid

from src.agents.graph_tra_cuu import build_graph_tra_cuu
from src.config import get_settings
from src.models.schemas import TraCuuRequest, TraCuuResponse

_graph = None


def _g():
    global _graph
    if _graph is None:
        _graph = build_graph_tra_cuu()
    return _graph


@router.post("/tra-cuu", response_model=TraCuuResponse)
async def tra_cuu(req: TraCuuRequest) -> TraCuuResponse:
    s = get_settings()
    trace_id = str(uuid.uuid4())
    st = await _g().ainvoke({"query": req.query, "as_of_date": req.as_of_date,
                             "trace_id": trace_id})
    return TraCuuResponse(
        result_type=st["result_type"].value if hasattr(st["result_type"], "value")
        else st["result_type"],
        answer=st.get("answer"), citations=st.get("citations") or [],
        warnings=st.get("warnings") or [], coverage_note=st.get("coverage_note"),
        trace_id=trace_id, config_name=req.config_name or s.eval_config_name)
```

Xóa `tests/test_api/test_routes.py::test_chat_empty_message` (endpoint `/chat` không còn).

- [ ] **Step 4: Chạy test**

```bash
pytest tests/test_api/ -v
```
Expected: PASS

- [ ] **Step 5: Chạy tập bẫy, có ba dòng đầu bảng ablation**

```bash
python3 -c "
import asyncio, yaml, json
from src.agents.graph_tra_cuu import build_graph_tra_cuu
g = build_graph_tra_cuu()
items = yaml.safe_load(open('eval/datasets/trap.yaml',encoding='utf-8'))['items']
async def go():
    dem = {}
    for it in items:
        st = await g.ainvoke({'query': it['cau_hoi']})
        rt = st['result_type'].value
        dung = (rt in ('abstain','out_of_scope')) if it['ky_vong'].startswith(('abstain','out_of')) \
               else bool(st.get('warnings'))
        dem[it['nhom']] = dem.get(it['nhom'], [0,0])
        dem[it['nhom']][0] += dung; dem[it['nhom']][1] += 1
    for k,(a,b) in dem.items(): print(f'{k}: {a}/{b} = {a/b:.0%}')
asyncio.run(go())
"
```
**Đây là con số thuyết phục nhất của khóa luận.** Ghi vào `eval/results/report.md`.

- [ ] **Step 6: So ba cấu hình verify**

```bash
# không verify / tầng 1 / tầng 1+2 — bằng biến môi trường
VERIFY_TIER2_ENABLED=false python3 -c "..."   # dùng script Step 5
VERIFY_TIER2_ENABLED=true  python3 -c "..."
```
Ghi cả ba dòng vào `eval/results/report.md`.

- [ ] **Step 7: Commit**

```bash
git add src/agents/graph_tra_cuu.py src/agents/state.py src/api/routes.py src/models/schemas.py eval/datasets/trap.yaml tests/test_api/ eval/results/report.md
git commit -m "feat(graph): wire the lookup graph and expose result_type over HTTP

The response carries a result_type enum rather than a boolean abstained, because
four outcomes cannot be encoded in one flag and partial_coverage in particular
would have been forced into either 'answered' or 'refused' - both wrong.

Adds the 40-question trap set. Its third group is the most valuable: questions
whose answer lives in NĐ 90/2019, which MOJ still marks effective despite its
having been superseded. A baseline answers those confidently with a
technically-valid citation, which is precisely the failure this thesis exists to
address, and the tier-2 mechanism is the only thing that catches it."
```

---

## KHÔNG thuộc plan này

| Hoãn | Thuộc plan |
|---|---|
| Reranker + ablation của nó | Plan 5 |
| Ghi `traces` vào DB (hiện chỉ có `trace_id` trong response) | Plan 4 Task 1 |
| 60 câu golden cho 5 Bộ luật khác, tập `boundary` | Plan 5 |
| Tinh chỉnh `ABSTAIN_THRESHOLD` trên tập dev | Plan 5 — phải tách tập dev, không tinh chỉnh trên tập báo cáo |

## Sau plan này

**Điều kiện sang plan 4:** `pytest tests/ -v -m "not integration"` xanh · `POST /api/v1/tra-cuu` trả đúng 4 `result_type` · `trap.yaml` đủ 40 câu, có tỉ lệ từ chối đúng cho cả 3 nhóm · tỉ lệ JSON đúng schema của `generate_claims` ≥95% · ba dòng đầu bảng ablation trong `eval/results/report.md`.
