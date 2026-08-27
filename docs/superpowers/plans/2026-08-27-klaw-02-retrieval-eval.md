# KLAW Plan 2/5 — Retrieval & Eval harness (tuần 3–4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Từ Postgres đã có `provisions` (plan 1) → chunk, embed qua OpenRouter, hybrid retrieval BM25 ⊕ dense ⊕ RRF, và một eval harness chạy bằng một lệnh cho ra Recall@k / MRR / nDCG trên `golden_qa`.

**Architecture:** Chunk ở mức Điều (cắt theo Khoản nếu vượt `CHUNK_MAX_TOKENS`), mỗi chunk mang context header. Embedding gọi OpenRouter `/embeddings` theo lô. BM25 dùng `tsvector` với `unaccent` + config `simple` (Postgres **không có** config `vietnamese`). RRF trộn hai nhánh. Eval là code, không phải notebook.

**Tech Stack:** Python 3.11 · Postgres 16 + pgvector · OpenRouter `/embeddings` · numpy · pytest

**Spec:** `docs/superpowers/specs/2026-08-27-klaw-design.md`
**Plan trước:** `2026-08-27-klaw-01-data-layer.md` — phải PASS Cổng A trước khi bắt đầu

## Global Constraints

- Python **3.11** · ruff `line-length = 120`, `select = ["E","F","I","N","W","UP"]`
- **MỘT key OpenRouter.** `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- `OPENROUTER_EMBEDDING_MODEL_NAME=baai/bge-m3`, `OPENROUTER_EMBEDDING_DIM=1024`
- Citation neo vào `provisions.id`, **KHÔNG** vào `chunks.id` — `chunks` sẽ bị DROP/CREATE nhiều lần khi ablation
- `chunks.embedding_model` cho phép **nhiều bộ embedding song song** — đó là cơ chế của bảng so sánh
- Postgres **không có** text-search config `vietnamese` → `unaccent` + `simple`
- Tách từ tiếng Việt (`pyvi`/`underthesea`) là **tối ưu hóa sớm** — chỉ thêm nếu đo được Recall@k kém
- `golden_qa` phải viết **giọng dân sinh**, cấm copy thuật ngữ pháp lý — nếu không thì pain point #3 không được test
- Mọi tham số retrieval đọc từ `Settings` (plan 1 Task 2), **không hardcode**

## Giả định cần xác nhận khi chạy

| Giả định | Xác nhận ở | Nếu sai |
|---|---|---|
| Corpus ra ~2.000–4.000 chunk | Task 3 Step 5 | > 10.000 → tăng `RETRIEVE_*_TOPK`; > 50.000 → cân nhắc HNSW index |
| Điều trung bình < 1.500 token | Task 2 Step 5 | nhiều Điều bị cắt → kiểm lại `CHUNK_MAX_TOKENS` |
| OpenRouter `/embeddings` nhận lô ≥ 32 text | Task 3 Step 2 | giảm `BATCH` trong `embedding.py` |

## Files

| File | Trách nhiệm |
|---|---|
| `src/services/xref.py` *(create)* | resolve dẫn chiếu chéo → `references.from/to_provision_id` |
| `src/services/chunker.py` *(create)* | `provisions` → `chunks` (Điều, cắt theo Khoản, context header) |
| `src/services/embedding.py` *(create)* | OpenRouter `/embeddings`, theo lô |
| `src/services/retrieval.py` *(create)* | BM25 · dense · RRF |
| `scripts/build_chunks.py` *(create)* | chunk + embed + ghi DB |
| `eval/run.py` *(create)* | harness một lệnh |
| `eval/metrics.py` *(create)* | Recall@k · MRR@k · nDCG@k |
| `eval/configs/*.yaml` *(create)* | preset cấu hình ablation |
| `eval/datasets/golden_qa.yaml` *(create)* | 50 câu Lao động (đợt 1) |
| `scripts/gen_golden_candidates.py` *(create)* | sinh câu hỏi ứng viên để **người** review |
| `migrations/002_tsv.sql` *(create)* | trigger cập nhật `tsv` |

---

## Task 1: Resolve dẫn chiếu chéo cấp điều khoản

**Files:**
- Create: `src/services/xref.py`
- Create: `tests/test_services/test_xref.py`

**Interfaces:**
- Consumes: `provisions` trong DB (plan 1)
- Produces: `find_xrefs(noi_dung: str) -> list[XrefHit]` với `XrefHit(so_dieu: int, so_khoan: int | None, cung_van_ban: bool, raw: str)`; `resolve_all(engine) -> int` (số cạnh đã ghi)

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_services/test_xref.py
from src.services.xref import find_xrefs


def test_bat_dieu_don_le():
    hits = find_xrefs("Theo quy định tại Điều 35 của Bộ luật này")
    assert len(hits) == 1
    assert hits[0].so_dieu == 35 and hits[0].so_khoan is None and hits[0].cung_van_ban is True


def test_bat_khoan_va_dieu():
    hits = find_xrefs("theo quy định tại khoản 2 Điều 35 của Bộ luật này")
    assert hits[0].so_khoan == 2 and hits[0].so_dieu == 35


def test_dan_chieu_van_ban_khac_thi_cung_van_ban_False():
    hits = find_xrefs("theo Điều 12 của Luật Bảo hiểm xã hội")
    assert hits[0].cung_van_ban is False


def test_bat_nhieu_dan_chieu_trong_mot_doan():
    hits = find_xrefs("quy định tại Điều 35 và khoản 1 Điều 36 của Bộ luật này")
    assert {(h.so_dieu, h.so_khoan) for h in hits} == {(35, None), (36, 1)}


def test_khong_bat_so_thu_tu_thuong():
    # "Điều" phải có số ngay sau; "35 ngày" không phải dẫn chiếu
    assert find_xrefs("trong thời hạn 35 ngày làm việc") == []


def test_khong_bat_chinh_tieu_de_dieu():
    # tiêu đề "Điều 21. Nội dung hợp đồng lao động" không phải dẫn chiếu tới chính nó
    assert find_xrefs("Điều 21. Nội dung hợp đồng lao động") == []
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_services/test_xref.py -v`
Expected: FAIL — `ModuleNotFoundError: src.services.xref`

- [ ] **Step 3: Viết `src/services/xref.py`**

```python
"""Resolve dẫn chiếu chéo trong văn bản pháp luật.

Luật VN đầy "theo quy định tại khoản 2 Điều 35 của Bộ luật này". Chunk độc lập
không resolve được → LLM tự điền vào chỗ trống (pain point #5).
Chỉ expand 1 hop khi retrieve, không lặp sâu.
"""

import re
from dataclasses import dataclass

from sqlalchemy import Engine, text

# "khoản 2 Điều 35 của Bộ luật này"  |  "Điều 12 của Luật BHXH"
# (?!\s*\.)  loại tiêu đề "Điều 21. ..." — sau số là dấu chấm thì không phải dẫn chiếu
RE_XREF = re.compile(
    r"(?:khoản\s+(?P<khoan>\d+)\s+)?"
    r"Điều\s+(?P<dieu>\d+)(?!\s*\.)"
    r"(?P<duoi>\s+(?:của\s+)?(?:Bộ luật|Luật|Nghị định|Thông tư)\s+(?P<nay>này)?)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class XrefHit:
    so_dieu: int
    so_khoan: int | None
    cung_van_ban: bool
    raw: str


def find_xrefs(noi_dung: str) -> list[XrefHit]:
    out: list[XrefHit] = []
    for m in RE_XREF.finditer(noi_dung):
        out.append(XrefHit(
            so_dieu=int(m.group("dieu")),
            so_khoan=int(m.group("khoan")) if m.group("khoan") else None,
            cung_van_ban=bool(m.group("nay")),
            raw=m.group(0).strip(),
        ))
    return out


def resolve_all(engine: Engine) -> int:
    """Quét mọi provision, ghi cạnh cấp điều khoản vào bảng references.

    Chỉ resolve dẫn chiếu CÙNG văn bản — dẫn chiếu sang văn bản khác không nêu
    số hiệu nên không map được chắc chắn, ghi raw_text để tra tay sau.
    """
    ghi = 0
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, document_id, noi_dung FROM provisions WHERE noi_dung <> ''"
        )).mappings().all()

        # index (document_id, so_dieu) → provision_id của Điều
        dieu_idx = {
            (r["document_id"], r["so_hieu_cap"]): r["id"]
            for r in conn.execute(text(
                "SELECT id, document_id, so_hieu_cap FROM provisions WHERE cap = 'dieu'"
            )).mappings().all()
        }

        conn.execute(text('DELETE FROM "references" WHERE from_provision_id IS NOT NULL'))
        for r in rows:
            for hit in find_xrefs(r["noi_dung"]):
                if not hit.cung_van_ban:
                    continue
                target = dieu_idx.get((r["document_id"], str(hit.so_dieu)))
                if target is None or target == r["id"]:
                    continue
                conn.execute(text(
                    'INSERT INTO "references"'
                    " (from_document_id, to_document_id, from_provision_id, to_provision_id, loai, raw_text)"
                    " VALUES (:fd, :td, :fp, :tp, 4, :raw)"   # loai 4 = Dẫn chiếu (mã MOJ)
                ), {"fd": r["document_id"], "td": r["document_id"],
                    "fp": r["id"], "tp": target, "raw": hit.raw})
                ghi += 1
    return ghi
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_services/test_xref.py -v`
Expected: PASS (6 test)

- [ ] **Step 5: Chạy resolve thật, kiểm số hợp lý**

```bash
python3 -c "
from src.services.db import get_engine
from src.services.xref import resolve_all
n = resolve_all(get_engine())
print('cạnh dẫn chiếu cấp điều khoản:', n)
assert n > 0, 'không bắt được dẫn chiếu nào — regex sai hoặc noi_dung rỗng'
"
```
Expected: vài trăm đến vài nghìn cạnh. **Nếu = 0 → dừng, kiểm `provisions.noi_dung` có rỗng hết không (dấu hiệu parser lỗi mà Cổng A bỏ sót).**

- [ ] **Step 6: Commit**

```bash
git add src/services/xref.py tests/test_services/test_xref.py
git commit -m "feat(xref): resolve same-document cross-references at clause level

Vietnamese statutes are full of 'theo quy định tại khoản 2 Điều 35 của Bộ luật
này', and an isolated chunk cannot resolve that, so the model fills the gap
itself. Two negative tests matter more than the positive ones: '35 ngày' must not
match, and an article heading like 'Điều 21. Nội dung...' must not become a
reference to itself - the lookahead rejecting a following period is what
distinguishes them. Cross-document references are left as raw_text because they
rarely name a document number and cannot be mapped with confidence."
```

---

## Task 2: Chunker — Điều là đơn vị, cắt theo Khoản khi quá dài

**Files:**
- Create: `src/services/chunker.py`
- Create: `tests/test_services/test_chunker.py`

**Interfaces:**
- Consumes: `Cap` (plan 1 Task 4)
- Produces: `ChunkRow(provision_id: int, noi_dung_embed: str, token_count: int)`; `build_chunks(provisions: list[dict], max_tokens: int) -> list[ChunkRow]`; `dem_token(s: str) -> int`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_services/test_chunker.py
from src.services.chunker import build_chunks, dem_token

DIEU = {"id": 10, "cap": "dieu", "so_hieu_cap": "25", "parent_id": None,
        "tieu_de": "Điều 25. Thời gian thử việc", "noi_dung": "Thời gian thử việc do hai bên thỏa thuận.",
        "duong_dan": "45/2019/QH14 > Điều 25"}
KHOAN_1 = {"id": 11, "cap": "khoan", "so_hieu_cap": "1", "parent_id": 10,
           "tieu_de": "1. Không quá 180 ngày", "noi_dung": "Không quá 180 ngày đối với người quản lý doanh nghiệp.",
           "duong_dan": "45/2019/QH14 > Điều 25 > Khoản 1"}


def test_dieu_ngan_thanh_MOT_chunk_gom_ca_khoan_con():
    chunks = build_chunks([DIEU, KHOAN_1], max_tokens=1500)
    assert len(chunks) == 1
    assert chunks[0].provision_id == 10
    assert "180 ngày" in chunks[0].noi_dung_embed, "Khoản con phải nằm trong chunk của Điều"


def test_chunk_luon_mang_context_header_duong_dan():
    chunks = build_chunks([DIEU, KHOAN_1], max_tokens=1500)
    assert chunks[0].noi_dung_embed.startswith("45/2019/QH14 > Điều 25")


def test_dieu_qua_dai_bi_cat_theo_khoan_va_moi_chunk_neo_vao_khoan():
    dai = dict(DIEU, noi_dung="x " * 2000)
    k2 = dict(KHOAN_1, id=12, so_hieu_cap="2",
              duong_dan="45/2019/QH14 > Điều 25 > Khoản 2", noi_dung="y " * 900)
    k1 = dict(KHOAN_1, noi_dung="z " * 900)
    chunks = build_chunks([dai, k1, k2], max_tokens=100)
    assert len(chunks) >= 2
    assert {c.provision_id for c in chunks} == {11, 12}, (
        "khi cắt theo Khoản, chunk phải neo vào provision_id của KHOẢN, không của Điều"
    )
    assert all("Điều 25" in c.noi_dung_embed for c in chunks), "vẫn phải giữ ngữ cảnh Điều"


def test_khong_sinh_chunk_rong():
    rong = dict(DIEU, noi_dung="", tieu_de="")
    assert build_chunks([rong], max_tokens=1500) == []


def test_dem_token_xap_xi_theo_tu_khong_theo_ky_tu():
    assert 3 <= dem_token("một hai ba") <= 6
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_services/test_chunker.py -v`
Expected: FAIL — `ModuleNotFoundError: src.services.chunker`

- [ ] **Step 3: Viết `src/services/chunker.py`**

```python
"""provisions → chunks.

Chunk = một Điều (gồm cả Khoản/Điểm con), KHÔNG cắt cứng theo token.
Điều dài hơn max_tokens thì cắt theo Khoản, nhưng mỗi chunk vẫn mang context
header đường dẫn — đó là contextual retrieval nhẹ, giải một phần pain point #4/#5.

Khi cắt theo Khoản, chunk neo vào provision_id của KHOẢN (không của Điều) để
citation trỏ đúng cấp mà người dùng cần kiểm.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkRow:
    provision_id: int
    noi_dung_embed: str
    token_count: int


def dem_token(s: str) -> int:
    """Xấp xỉ: số từ × 1.3. Không dùng tokenizer thật vì embedding qua API.

    ponytail: đủ chính xác để quyết định cắt hay không. Thay bằng tokenizer thật
    nếu đo được sai lệch gây cắt sai.
    """
    return int(len(re.findall(r"\S+", s)) * 1.3)


def _text_of(p: dict) -> str:
    parts = [p.get("tieu_de") or "", p.get("noi_dung") or ""]
    return " ".join(x for x in parts if x).strip()


def build_chunks(provisions: list[dict], max_tokens: int) -> list[ChunkRow]:
    by_id = {p["id"]: p for p in provisions}
    con: dict[int, list[dict]] = {}
    for p in provisions:
        if p.get("parent_id") is not None:
            con.setdefault(p["parent_id"], []).append(p)

    def gom(p: dict) -> str:
        """Text của p + toàn bộ con, theo thứ tự."""
        acc = [_text_of(p)]
        for c in con.get(p["id"], []):
            acc.append(gom(c))
        return " ".join(x for x in acc if x).strip()

    out: list[ChunkRow] = []
    for p in provisions:
        if p["cap"] != "dieu":
            continue
        full = gom(p)
        if not full:
            continue
        header = p["duong_dan"]
        body = f"{header}\n{full}"

        if dem_token(body) <= max_tokens:
            out.append(ChunkRow(p["id"], body, dem_token(body)))
            continue

        # Quá dài → cắt theo Khoản, giữ ngữ cảnh Điều trong header
        khoans = [c for c in con.get(p["id"], []) if c["cap"] == "khoan"]
        if not khoans:
            out.append(ChunkRow(p["id"], body, dem_token(body)))
            continue
        for k in khoans:
            ktext = gom(k)
            if not ktext:
                continue
            kbody = f"{k['duong_dan']}\n{p.get('tieu_de') or ''}\n{ktext}".strip()
            out.append(ChunkRow(k["id"], kbody, dem_token(kbody)))

    return out


def load_provisions(engine) -> list[dict]:
    from sqlalchemy import text

    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(
            "SELECT id, document_id, parent_id, cap, so_hieu_cap, tieu_de, noi_dung, duong_dan"
            " FROM provisions ORDER BY document_id, thu_tu"
        )).mappings().all()]
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_services/test_chunker.py -v`
Expected: PASS (5 test)

- [ ] **Step 5: Kiểm phân bố token thật (xác nhận giả định)**

```bash
python3 -c "
from src.services.chunker import build_chunks, load_provisions
from src.services.db import get_engine
from src.config import get_settings
ps = load_provisions(get_engine())
cs = build_chunks(ps, get_settings().chunk_max_tokens)
tk = sorted(c.token_count for c in cs)
n = len(tk)
print(f'chunk: {n}')
print(f'token  min={tk[0]}  p50={tk[n//2]}  p95={tk[int(n*.95)]}  max={tk[-1]}')
print('chunk bị cắt theo Khoản:', sum(1 for c in cs if '> Khoản ' in c.noi_dung_embed.split(chr(10))[0]))
"
```
Ghi kết quả vào `docs/phase0-findings.md`. Expected (giả định): 2.000–4.000 chunk, p95 < 1.500.

- [ ] **Step 6: Commit**

```bash
git add src/services/chunker.py tests/test_services/test_chunker.py
git commit -m "feat(chunker): article-level chunks with a path header, split by clause when long

An article and its clauses stay in one chunk so retrieval hitting a clause still
gives the model the whole article - the parent-document behaviour the spec asks
for, achieved by construction rather than a second query. When an article exceeds
the token budget the split anchors each chunk to the clause's own provision_id,
not the article's, so a citation points at the level a reader needs to verify.
Every chunk carries its duong_dan header, which is lightweight contextual
retrieval and the cheapest fix for cross-reference blindness."
```

---

## Task 3: Embedding qua OpenRouter

**Files:**
- Create: `src/services/embedding.py`
- Create: `tests/test_services/test_embedding.py`

**Interfaces:**
- Produces: `EmbeddingClient(api_key, base_url, model, dim)`, `.embed(texts: list[str]) -> list[list[float]]`, `.embed_query(text: str) -> list[float]`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_services/test_embedding.py
import httpx
import pytest

from src.services.embedding import EmbeddingClient


def _c(handler, dim=4) -> EmbeddingClient:
    c = EmbeddingClient(api_key="k", base_url="https://x/api/v1", model="baai/bge-m3", dim=dim)
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_embed_giu_dung_thu_tu_theo_index_tra_ve():
    def h(req):
        # OpenRouter có thể trả không đúng thứ tự — phải sort theo index
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [9, 9, 9, 9]},
            {"index": 0, "embedding": [1, 1, 1, 1]},
        ]})

    out = _c(h).embed(["a", "b"])
    assert out[0] == [1, 1, 1, 1] and out[1] == [9, 9, 9, 9]


def test_dim_khong_khop_thi_nem_khong_im_lang():
    def h(req):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})

    with pytest.raises(ValueError, match="chiều vector"):
        _c(h, dim=4).embed(["a"])


def test_chia_lo_khi_nhieu_text():
    lots = []

    def h(req):
        import json
        body = json.loads(req.content)
        lots.append(len(body["input"]))
        return httpx.Response(200, json={"data": [
            {"index": i, "embedding": [0, 0, 0, 0]} for i in range(len(body["input"]))
        ]})

    c = _c(h)
    c.batch = 32
    c.embed(["x"] * 70)
    assert lots == [32, 32, 6]


def test_http_loi_nem_ra():
    def h(req):
        return httpx.Response(429, text="rate limited")

    with pytest.raises(httpx.HTTPStatusError):
        _c(h).embed(["a"])


def test_text_rong_bi_tu_choi_truoc_khi_goi_api():
    def h(req):
        raise AssertionError("không được gọi API với text rỗng")

    with pytest.raises(ValueError, match="rỗng"):
        _c(h).embed(["a", ""])
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_services/test_embedding.py -v`
Expected: FAIL — `ModuleNotFoundError: src.services.embedding`

- [ ] **Step 3: Viết `src/services/embedding.py`**

```python
"""Embedding qua OpenRouter /embeddings.

OpenRouter CÓ embedding — 36 model, chỉ hiện qua ?output_modalities=embeddings,
không hiện trong danh sách /models mặc định. baai/bge-m3: $0.010/1M, dim 1024,
VN-MTEB retrieval 39.84 (cao nhất nhóm ≤1B).
"""

import httpx


class EmbeddingClient:
    def __init__(self, api_key: str, base_url: str, model: str, dim: int) -> None:
        self.model = model
        self.dim = dim
        self.batch = 32
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=120,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if any(not t or not t.strip() for t in texts):
            raise ValueError("có text rỗng — không gọi API, sửa chunker")

        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch):
            lo = texts[i : i + self.batch]
            r = self._http.post("/embeddings", json={"model": self.model, "input": lo})
            r.raise_for_status()
            data = r.json().get("data") or []
            if len(data) != len(lo):
                raise ValueError(f"API trả {len(data)} vector cho {len(lo)} text")
            for item in sorted(data, key=lambda x: x["index"]):
                v = item["embedding"]
                if len(v) != self.dim:
                    raise ValueError(f"chiều vector {len(v)} ≠ cấu hình {self.dim}")
                out.append(v)
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


def from_settings() -> EmbeddingClient:
    from src.config import get_settings

    s = get_settings()
    return EmbeddingClient(
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        model=s.openrouter_embedding_model_name,
        dim=s.openrouter_embedding_dim,
    )
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_services/test_embedding.py -v`
Expected: PASS (5 test)

- [ ] **Step 5: Smoke test thật, kiểm giá đo được**

```bash
python3 -c "
from src.services.embedding import from_settings
c = from_settings()
v = c.embed(['thử việc bao lâu', 'lương tối thiểu vùng I'])
print('dim:', len(v[0]), '| số vector:', len(v))
assert len(v[0]) == c.dim
"
```
Expected: `dim: 1024 | số vector: 2`

- [ ] **Step 6: Commit**

```bash
git add src/services/embedding.py tests/test_services/test_embedding.py
git commit -m "feat(embedding): OpenRouter /embeddings client that sorts by index

Sorting the response by index is not defensive padding: an out-of-order response
would silently pair every chunk with the wrong vector, and retrieval would degrade
in a way no test on retrieval itself could explain. A dimension mismatch and an
empty input both raise rather than pass through, because either one produces a
corrupt index that only surfaces as bad Recall@5 weeks later."
```

---

## Task 4: BM25 qua tsvector với unaccent

**Files:**
- Create: `migrations/002_tsv.sql`
- Create: `tests/test_infra/test_tsv.py`

**Interfaces:**
- Produces: trigger `chunks_tsv_update` tự cập nhật `chunks.tsv`; hàm SQL `klaw_tsv(text) -> tsvector`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_infra/test_tsv.py
import pytest
from sqlalchemy import text

from src.services.db import get_engine, run_migrations


@pytest.mark.integration
def test_postgres_khong_co_config_vietnamese():
    """Xác nhận giả định của spec: phải dùng simple + unaccent."""
    with get_engine().connect() as c:
        cfgs = {r[0] for r in c.execute(text("SELECT cfgname FROM pg_ts_config")).all()}
    assert "vietnamese" not in cfgs, "nếu có config vietnamese thì spec cần cập nhật"
    assert "simple" in cfgs


@pytest.mark.integration
def test_klaw_tsv_bo_dau_de_khop_khong_dau():
    run_migrations()
    with get_engine().connect() as c:
        hit = c.execute(text(
            "SELECT klaw_tsv('thời gian thử việc') @@ plainto_tsquery('simple', unaccent('thu viec'))"
        )).scalar_one()
    assert hit is True, "unaccent chưa hoạt động — 'thu viec' phải khớp 'thử việc'"


@pytest.mark.integration
def test_trigger_tu_cap_nhat_tsv_khi_insert():
    run_migrations()
    with get_engine().begin() as c:
        pid = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
        cid = c.execute(text(
            "INSERT INTO chunks (provision_id, noi_dung_embed, embedding_model, embedding_dim)"
            " VALUES (:p, 'thời gian thử việc tối đa', 'test', 4) RETURNING id"
        ), {"p": pid}).scalar_one()
        tsv = c.execute(text("SELECT tsv FROM chunks WHERE id = :i"), {"i": cid}).scalar_one()
        c.execute(text("DELETE FROM chunks WHERE id = :i"), {"i": cid})
    assert tsv, "trigger không chạy — tsv rỗng sau INSERT"
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_infra/test_tsv.py -v`
Expected: FAIL — `function klaw_tsv(text) does not exist`

- [ ] **Step 3: Viết `migrations/002_tsv.sql`**

```sql
-- PostgreSQL KHÔNG có text-search config 'vietnamese'.
-- Dùng 'simple' + unaccent: bỏ dấu rồi tách theo khoảng trắng.
-- Tách từ tiếng Việt (pyvi/underthesea) là tối ưu hóa sớm — chỉ thêm nếu đo
-- được Recall@k kém, và khi đó nó thành một dòng ablation.

CREATE OR REPLACE FUNCTION klaw_tsv(txt text)
RETURNS tsvector
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT to_tsvector('simple', unaccent(txt));
$$;

CREATE OR REPLACE FUNCTION chunks_tsv_trigger()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.tsv := klaw_tsv(NEW.noi_dung_embed);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS chunks_tsv_update ON chunks;
CREATE TRIGGER chunks_tsv_update
    BEFORE INSERT OR UPDATE OF noi_dung_embed ON chunks
    FOR EACH ROW EXECUTE FUNCTION chunks_tsv_trigger();
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_infra/test_tsv.py -v`
Expected: PASS (3 test)

- [ ] **Step 5: Commit**

```bash
git add migrations/002_tsv.sql tests/test_infra/test_tsv.py
git commit -m "feat(bm25): tsvector via simple + unaccent, with the assumption under test

A test asserts Postgres has no 'vietnamese' text-search configuration, so the
spec's claim is checked rather than trusted, and it will fail loudly if a future
Postgres ships one. Diacritic-insensitive matching is verified by requiring 'thu
viec' to match 'thời gian thử việc', which is how real users type. Vietnamese word
segmentation stays out until measurement shows it is needed - at which point it
becomes an ablation row rather than an assumption."
```

---

## Task 5: Hybrid retrieval — BM25 ⊕ dense ⊕ RRF

**Files:**
- Create: `src/services/retrieval.py`
- Create: `tests/test_services/test_retrieval.py`

**Interfaces:**
- Consumes: `EmbeddingClient` (Task 3), `klaw_tsv` (Task 4), `Settings` (plan 1)
- Produces: `rrf(rankings: list[list[int]], k: int) -> list[tuple[int, float]]`; `Retriever(engine, embedder, settings)` với `.bm25(q, topk) -> list[int]`, `.dense(q, topk) -> list[int]`, `.hybrid(q) -> list[int]` (trả `chunks.id`)

- [ ] **Step 1: Viết test thất bại — RRF là hàm thuần, test không cần DB**

```python
# tests/test_services/test_retrieval.py
from src.services.retrieval import rrf


def test_rrf_item_dung_dau_ca_hai_nhanh_thang():
    out = rrf([[1, 2, 3], [1, 3, 2]], k=60)
    assert out[0][0] == 1


def test_rrf_hop_nhat_item_chi_xuat_hien_o_mot_nhanh():
    out = rrf([[1, 2], [3, 4]], k=60)
    assert {i for i, _ in out} == {1, 2, 3, 4}


def test_rrf_diem_dung_cong_thuc_1_tren_k_cong_rank():
    out = dict(rrf([[7]], k=60))
    assert abs(out[7] - 1 / 61) < 1e-9, "rank bắt đầu từ 1, không từ 0"


def test_rrf_sap_giam_dan_theo_diem():
    out = rrf([[1, 2, 3], [2, 1, 3]], k=60)
    assert [s for _, s in out] == sorted((s for _, s in out), reverse=True)


def test_rrf_nhanh_rong_khong_lam_no():
    assert rrf([[], [1]], k=60)[0][0] == 1


def test_rrf_k_lon_lam_khoang_cach_diem_hep_lai():
    gan = dict(rrf([[1, 2]], k=1000))
    xa = dict(rrf([[1, 2]], k=1))
    assert (gan[1] - gan[2]) < (xa[1] - xa[2])
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_services/test_retrieval.py -v`
Expected: FAIL — `ModuleNotFoundError: src.services.retrieval`

- [ ] **Step 3: Viết `src/services/retrieval.py`**

```python
"""Hybrid retrieval: BM25 (tsvector) ⊕ dense (pgvector) → RRF.

RRF: score(d) = Σ 1/(k + rank(d)), rank bắt đầu từ 1.
k=60 là giá trị thường dùng — CHƯA xác minh nguồn gốc, không trích trong khóa
luận cho tới khi tra được. k lớn làm khoảng cách điểm giữa các rank hẹp lại,
tức tin vào thứ hạng ít hơn.
"""

from collections import defaultdict

from sqlalchemy import Engine, text

from src.config import Settings
from src.services.embedding import EmbeddingClient


def rrf(rankings: list[list[int]], k: int) -> list[tuple[int, float]]:
    score: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            score[item] += 1.0 / (k + rank)
    return sorted(score.items(), key=lambda kv: kv[1], reverse=True)


class Retriever:
    def __init__(self, engine: Engine, embedder: EmbeddingClient, settings: Settings) -> None:
        self.engine = engine
        self.embedder = embedder
        self.s = settings

    def bm25(self, q: str, topk: int | None = None) -> list[int]:
        topk = topk or self.s.retrieve_bm25_topk
        with self.engine.connect() as c:
            rows = c.execute(text(
                "SELECT id FROM chunks"
                " WHERE embedding_model = :m"
                "   AND tsv @@ plainto_tsquery('simple', unaccent(:q))"
                " ORDER BY ts_rank(tsv, plainto_tsquery('simple', unaccent(:q))) DESC"
                " LIMIT :k"
            ), {"q": q, "k": topk, "m": self.embedder.model}).all()
        return [r[0] for r in rows]

    def dense(self, q: str, topk: int | None = None) -> list[int]:
        topk = topk or self.s.retrieve_dense_topk
        vec = self.embedder.embed_query(q)
        with self.engine.connect() as c:
            rows = c.execute(text(
                "SELECT id FROM chunks"
                " WHERE embedding_model = :m AND embedding IS NOT NULL"
                " ORDER BY embedding <=> CAST(:v AS vector)"
                " LIMIT :k"
            ), {"v": str(vec), "k": topk, "m": self.embedder.model}).all()
        return [r[0] for r in rows]

    def hybrid(self, q: str) -> list[int]:
        fused = rrf([self.bm25(q), self.dense(q)], k=self.s.rrf_k)
        return [cid for cid, _ in fused[: self.s.retrieve_final_topk]]

    def provision_ids(self, chunk_ids: list[int]) -> list[int]:
        """chunks.id → provisions.id, giữ thứ tự, bỏ trùng."""
        if not chunk_ids:
            return []
        with self.engine.connect() as c:
            m = dict(c.execute(text(
                "SELECT id, provision_id FROM chunks WHERE id = ANY(:ids)"
            ), {"ids": chunk_ids}).all())
        seen: set[int] = set()
        out: list[int] = []
        for cid in chunk_ids:
            pid = m.get(cid)
            if pid is not None and pid not in seen:
                seen.add(pid)
                out.append(pid)
        return out
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_services/test_retrieval.py -v`
Expected: PASS (6 test)

- [ ] **Step 5: Commit**

```bash
git add src/services/retrieval.py tests/test_services/test_retrieval.py
git commit -m "feat(retrieval): hybrid BM25 and dense fused with RRF

RRF is a pure function tested without a database, including the exact 1/(k+rank)
formula with rank starting at 1 - an off-by-one there shifts every score and would
be invisible against real data. Both branches filter on embedding_model so several
embedding sets coexist in chunks without contaminating each other, which the
week-4 comparison depends on. k=60 is the commonly used value but its provenance
is unverified, and the docstring says so: it must not be cited in the thesis until
the source is found."
```

---

## Task 6: Build chunks + embed toàn corpus

**Files:**
- Create: `scripts/build_chunks.py`
- Create: `tests/test_scripts/test_build_chunks.py`

**Interfaces:**
- Consumes: `build_chunks`/`load_provisions` (Task 2), `EmbeddingClient` (Task 3)
- Produces: `scripts.build_chunks.run(model: str | None = None, dry_run: bool = False) -> dict`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_scripts/test_build_chunks.py
import pytest
from sqlalchemy import text

from scripts.build_chunks import run
from src.services.db import get_engine


@pytest.mark.integration
def test_dry_run_khong_ghi_gi_va_bao_so_chunk():
    with get_engine().connect() as c:
        before = c.execute(text("SELECT count(*) FROM chunks")).scalar_one()
    r = run(dry_run=True)
    with get_engine().connect() as c:
        after = c.execute(text("SELECT count(*) FROM chunks")).scalar_one()
    assert before == after
    assert r["chunks"] > 0


@pytest.mark.integration
def test_chay_lai_cung_model_thi_thay_the_khong_nhan_doi():
    run()
    with get_engine().connect() as c:
        n1 = c.execute(text("SELECT count(*) FROM chunks WHERE embedding_model = :m"),
                       {"m": "baai/bge-m3"}).scalar_one()
    run()
    with get_engine().connect() as c:
        n2 = c.execute(text("SELECT count(*) FROM chunks WHERE embedding_model = :m"),
                       {"m": "baai/bge-m3"}).scalar_one()
    assert n1 == n2, "chạy lại phải DELETE bộ cũ rồi ghi lại, không cộng dồn"


@pytest.mark.integration
def test_moi_chunk_co_provision_id_ton_tai_va_co_embedding():
    run()
    with get_engine().connect() as c:
        orphan = c.execute(text(
            "SELECT count(*) FROM chunks ch"
            " WHERE NOT EXISTS (SELECT 1 FROM provisions p WHERE p.id = ch.provision_id)"
        )).scalar_one()
        thieu = c.execute(text(
            "SELECT count(*) FROM chunks WHERE embedding IS NULL AND embedding_model = :m"
        ), {"m": "baai/bge-m3"}).scalar_one()
    assert orphan == 0
    assert thieu == 0, "có chunk không có vector — embed thất bại mà không báo"
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_scripts/test_build_chunks.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.build_chunks`

- [ ] **Step 3: Viết `scripts/build_chunks.py`**

```python
"""Chunk toàn corpus rồi embed, ghi vào chunks.

Chạy lại với CÙNG model → thay thế bộ cũ. Chạy với model KHÁC → thêm bộ mới
song song (đó là cơ chế của bảng so sánh embedding tuần 4).
"""

import sys

from sqlalchemy import text

from src.config import get_settings
from src.services.chunker import build_chunks, load_provisions
from src.services.db import get_engine, run_migrations
from src.services.embedding import EmbeddingClient


def run(model: str | None = None, dry_run: bool = False) -> dict:
    s = get_settings()
    run_migrations()
    model = model or s.openrouter_embedding_model_name

    provisions = load_provisions(get_engine())
    chunks = build_chunks(provisions, s.chunk_max_tokens)
    if not chunks:
        raise ValueError("0 chunk — provisions rỗng hoặc chunker lỗi")

    info = {"provisions": len(provisions), "chunks": len(chunks), "model": model,
            "tokens": sum(c.token_count for c in chunks)}
    if dry_run:
        return info

    embedder = EmbeddingClient(
        api_key=s.openrouter_api_key, base_url=s.openrouter_base_url,
        model=model, dim=s.openrouter_embedding_dim)

    print(f"embed {len(chunks)} chunk (~{info['tokens']:,} token) bằng {model} …")
    vectors = embedder.embed([c.noi_dung_embed for c in chunks])
    if len(vectors) != len(chunks):
        raise ValueError(f"{len(vectors)} vector cho {len(chunks)} chunk")

    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM chunks WHERE embedding_model = :m"), {"m": model})
        for c, v in zip(chunks, vectors, strict=True):
            conn.execute(text(
                "INSERT INTO chunks (provision_id, noi_dung_embed, embedding,"
                " embedding_model, embedding_dim, token_count)"
                " VALUES (:p, :t, CAST(:v AS vector), :m, :d, :n)"
            ), {"p": c.provision_id, "t": c.noi_dung_embed, "v": str(v),
                "m": model, "d": embedder.dim, "n": c.token_count})
    return info


if __name__ == "__main__":
    mdl = sys.argv[1] if len(sys.argv) > 1 else None
    print(run(model=mdl, dry_run="--dry-run" in sys.argv))
```

- [ ] **Step 4: Dry run trước để biết chi phí, rồi chạy thật**

```bash
python -m scripts.build_chunks --dry-run
# đọc số 'tokens', nhân với $0.010/1M để biết chi phí trước khi gọi API
python -m scripts.build_chunks
pytest tests/test_scripts/test_build_chunks.py -v
```
Expected: chi phí ~$0.02–0.05; test PASS (3 test)

- [ ] **Step 5: Commit**

```bash
git add scripts/build_chunks.py tests/test_scripts/test_build_chunks.py
git commit -m "feat(chunks): build and embed the corpus, replacing per model

--dry-run reports the token count before any API call, so cost is known rather
than discovered. Re-running with the same model deletes that model's set first, so
repeated runs cannot double the index; running a different model adds a parallel
set, which is exactly how the week-4 embedding comparison works. A test asserts no
chunk is left with a NULL embedding, because a partially embedded index degrades
retrieval silently."
```

---

## Task 7: Metrics — Recall@k, MRR@k, nDCG@k

**Files:**
- Create: `eval/metrics.py`
- Create: `tests/test_eval/test_metrics.py`

**Interfaces:**
- Produces: `recall_at_k(retrieved: list[int], relevant: set[int], k: int) -> float`; `mrr_at_k(...) -> float`; `ndcg_at_k(...) -> float`

- [ ] **Step 1: Viết test thất bại — dùng giá trị tính tay**

```python
# tests/test_eval/test_metrics.py
import math

from eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k


def test_recall_dem_ty_le_relevant_tim_thay_trong_top_k():
    assert recall_at_k([1, 2, 3], {1, 4}, k=3) == 0.5
    assert recall_at_k([1, 2, 3], {1, 2}, k=3) == 1.0
    assert recall_at_k([9, 8, 1], {1}, k=2) == 0.0, "vị trí 3 không nằm trong top 2"


def test_recall_relevant_rong_tra_0_khong_chia_cho_0():
    assert recall_at_k([1, 2], set(), k=2) == 0.0


def test_mrr_lay_nghich_dao_hang_dau_tien_dung():
    assert mrr_at_k([5, 3, 1], {1}, k=3) == 1 / 3
    assert mrr_at_k([1, 3, 5], {1}, k=3) == 1.0
    assert mrr_at_k([5, 3], {1}, k=3) == 0.0


def test_ndcg_hoan_hao_bang_1():
    assert abs(ndcg_at_k([1, 2], {1, 2}, k=2) - 1.0) < 1e-9


def test_ndcg_dung_log2_theo_vi_tri():
    # 1 relevant ở vị trí 2: DCG = 1/log2(3); IDCG = 1/log2(2) = 1
    got = ndcg_at_k([9, 1], {1}, k=2)
    assert abs(got - 1 / math.log2(3)) < 1e-9


def test_moi_metric_tra_0_khi_retrieved_rong():
    for f in (recall_at_k, mrr_at_k, ndcg_at_k):
        assert f([], {1}, k=5) == 0.0
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_eval/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: eval.metrics`

- [ ] **Step 3: Viết `eval/metrics.py`**

```python
"""Metric truy hồi. Binary relevance: một provision_id hoặc đúng hoặc không."""

import math


def recall_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    if not relevant or not retrieved:
        return 0.0
    hit = len(set(retrieved[:k]) & relevant)
    return hit / len(relevant)


def mrr_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    for rank, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    if not relevant or not retrieved:
        return 0.0
    dcg = sum(1.0 / math.log2(rank + 1)
              for rank, item in enumerate(retrieved[:k], start=1) if item in relevant)
    idcg = sum(1.0 / math.log2(rank + 1)
               for rank in range(1, min(len(relevant), k) + 1))
    return dcg / idcg if idcg else 0.0
```

Tạo `eval/__init__.py` và `tests/test_eval/__init__.py` (rỗng).

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_eval/test_metrics.py -v`
Expected: PASS (6 test)

- [ ] **Step 5: Commit**

```bash
git add eval/__init__.py eval/metrics.py tests/test_eval/
git commit -m "feat(eval): retrieval metrics with hand-computed expected values

Every assertion uses a value worked out by hand rather than whatever the
implementation returns, so the tests can actually fail. nDCG checks the exact
1/log2(rank+1) discount, and each metric returns 0.0 on empty input instead of
dividing by zero - a NaN leaking into the ablation table would be worse than a
crash because it prints."
```

---

## Task 8: `golden_qa` — công cụ sinh ứng viên + 50 câu đợt 1

**Files:**
- Create: `scripts/gen_golden_candidates.py`
- Create: `eval/datasets/golden_qa.yaml`
- Create: `tests/test_eval/test_golden_qa.py`

**Interfaces:**
- Produces: file YAML mỗi item `{id, cau_hoi, provision_ids: [int], duong_dan: [str], bo_luat, nguon: "llm-gen|nguoi-viet", da_review: bool}`

**Quy trình bắt buộc (spec 11.1) — phải viết vào khóa luận:**
1. LLM sinh câu hỏi **từ một Điều cụ thể** → ground truth biết trước
2. **Người review, loại câu lộ đáp án** → **báo cáo tỉ lệ loại**
3. **Viết lại giọng dân sinh**, cấm copy thuật ngữ pháp lý

- [ ] **Step 1: Viết test thất bại — test kiểm CHẤT LƯỢNG tập dữ liệu**

```python
# tests/test_eval/test_golden_qa.py
import re
from pathlib import Path

import yaml

P = Path("eval/datasets/golden_qa.yaml")
THUAT_NGU = ["quy định tại", "theo quy định của pháp luật", "nghĩa vụ thông báo",
             "đơn phương chấm dứt", "người sử dụng lao động"]


def _load() -> list[dict]:
    return yaml.safe_load(P.read_text(encoding="utf-8"))["items"]


def test_moi_item_co_id_duy_nhat_va_provision_ids_khong_rong():
    items = _load()
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)), "id trùng"
    assert all(i["provision_ids"] for i in items), "có item không có ground truth"


def test_cau_hoi_KHONG_chua_so_dieu():
    """Câu hỏi chứa "Điều 25" thì retrieval quá dễ, không test được pain point #3."""
    xau = [i["id"] for i in _load() if re.search(r"Điều\s+\d+", i["cau_hoi"])]
    assert not xau, f"các item nêu thẳng số điều: {xau}"


def test_it_nhat_80_phan_tram_cau_hoi_khong_dung_thuat_ngu_phap_ly():
    items = _load()
    sach = [i for i in items if not any(t in i["cau_hoi"].lower() for t in THUAT_NGU)]
    ty_le = len(sach) / len(items)
    assert ty_le >= 0.8, f"chỉ {ty_le:.0%} câu hỏi dùng giọng dân sinh, cần ≥80%"


def test_moi_item_da_qua_review_cua_nguoi():
    chua = [i["id"] for i in _load() if not i.get("da_review")]
    assert not chua, f"chưa review: {chua}"


def test_dot_1_co_it_nhat_50_cau_va_toan_bo_thuoc_lao_dong():
    items = _load()
    assert len(items) >= 50
    assert all(i["bo_luat"] == "Lao động" for i in items), "đợt 1 chỉ Lao động"
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_eval/test_golden_qa.py -v`
Expected: FAIL — `FileNotFoundError: eval/datasets/golden_qa.yaml`

- [ ] **Step 3: Viết `scripts/gen_golden_candidates.py`**

```python
"""Sinh câu hỏi ỨNG VIÊN từ các Điều — người phải review trước khi dùng.

KHÔNG ghi trực tiếp vào golden_qa.yaml. Ghi ra *_candidates.yaml với
da_review: false, người đọc từng câu, loại câu lộ đáp án, viết lại giọng dân
sinh, rồi mới chuyển sang golden_qa.yaml. Tỉ lệ loại phải báo cáo (spec 11.1).
"""

import json
import random
import sys
from pathlib import Path

import httpx
import yaml
from sqlalchemy import text

from src.config import get_settings
from src.services.db import get_engine

PROMPT = """Bạn nhận nguyên văn một điều luật Việt Nam. Hãy viết {n} câu hỏi mà
NGƯỜI DÂN THƯỜNG sẽ hỏi, và điều luật này trả lời được.

Bắt buộc:
- Dùng ngôn ngữ đời thường. TUYỆT ĐỐI KHÔNG dùng thuật ngữ pháp lý.
- TUYỆT ĐỐI KHÔNG nêu số điều, số khoản, tên văn bản.
- Mỗi câu là một tình huống cụ thể, không phải câu hỏi định nghĩa.

Trả về JSON: {{"cau_hoi": ["...", "..."]}}

Điều luật:
{noi_dung}
"""


def gen(n_dieu: int = 25, n_moi_dieu: int = 2, seed: int = 7) -> Path:
    s = get_settings()
    random.seed(seed)
    with get_engine().connect() as c:
        rows = c.execute(text(
            "SELECT p.id, p.duong_dan, p.tieu_de, p.noi_dung"
            " FROM provisions p JOIN documents d ON d.id = p.document_id"
            " WHERE p.cap = 'dieu' AND d.id = '139264' AND length(p.noi_dung) > 200"
        )).mappings().all()
    mau = random.sample(list(rows), min(n_dieu, len(rows)))

    http = httpx.Client(
        base_url=s.openrouter_base_url, timeout=120,
        headers={"Authorization": f"Bearer {s.openrouter_api_key}"})
    items: list[dict] = []
    for i, r in enumerate(mau):
        body = {"model": s.openrouter_generate_model_name,
                "temperature": s.llm_temperature,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": PROMPT.format(
                    n=n_moi_dieu, noi_dung=f"{r['tieu_de']}\n{r['noi_dung']}")}]}
        resp = http.post("/chat/completions", json=body)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        for j, q in enumerate(json.loads(raw)["cau_hoi"]):
            items.append({"id": f"lao-{i:03d}-{j}", "cau_hoi": q,
                          "provision_ids": [r["id"]], "duong_dan": [r["duong_dan"]],
                          "bo_luat": "Lao động", "nguon": "llm-gen", "da_review": False})

    out = Path(s.eval_dataset_dir) / "golden_qa_candidates.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump({"items": items}, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    print(f"{len(items)} ứng viên → {out}")
    print("BƯỚC TIẾP THEO LÀ VIỆC CỦA NGƯỜI: review từng câu, loại câu lộ đáp án,")
    print("viết lại giọng dân sinh, đặt da_review: true, chuyển sang golden_qa.yaml.")
    print("Ghi lại tỉ lệ loại — spec 11.1 yêu cầu báo cáo con số này.")
    return out


if __name__ == "__main__":
    gen(n_dieu=int(sys.argv[1]) if len(sys.argv) > 1 else 25)
```

- [ ] **Step 4: Sinh ứng viên, rồi NGƯỜI review**

```bash
python -m scripts.gen_golden_candidates 30
```

**Đây là việc của bạn, không delegate:** mở `eval/datasets/golden_qa_candidates.yaml`, với từng câu:
- Câu nêu số điều / thuật ngữ pháp lý → **xóa** hoặc viết lại
- Câu mà đọc là biết đáp án nằm ở đâu → **xóa**
- Câu hợp lệ → viết lại cho tự nhiên hơn, đặt `da_review: true`, `nguon: nguoi-viet` nếu sửa nhiều

Giữ ≥50 câu. **Đếm số câu bị loại / tổng ứng viên** → ghi vào `docs/golden-qa-process.md`:

```markdown
# Quy trình xây golden_qa

- Ứng viên LLM sinh: N
- Người loại: M  (tỉ lệ loại M/N = x%)
- Người viết lại: P
- Còn lại trong golden_qa.yaml: 50

Lý do loại thường gặp: (liệt kê 3–5 lý do thật)
```

- [ ] **Step 5: Chạy lại test tập dữ liệu**

```bash
mv eval/datasets/golden_qa_candidates.yaml eval/datasets/golden_qa.yaml   # sau khi review
pytest tests/test_eval/test_golden_qa.py -v
```
Expected: PASS (5 test). Nếu `test_cau_hoi_KHONG_chua_so_dieu` fail → còn câu chưa review.

- [ ] **Step 6: Commit**

```bash
git add scripts/gen_golden_candidates.py eval/datasets/golden_qa.yaml docs/golden-qa-process.md tests/test_eval/test_golden_qa.py
git commit -m "feat(eval): golden_qa with dataset-quality tests, not just schema tests

The generator writes to a _candidates file with da_review false and refuses to
touch golden_qa.yaml, because the human review step is what makes the set
defensible and a script that skipped it would look identical. Three tests police
quality rather than structure: no question may name an article number, at least
80% must avoid legal terminology, and every item must be marked reviewed. Without
those, questions phrased in statute language make retrieval trivially easy and the
vocabulary-gap problem never gets tested at all."
```

---

## Task 9: Eval harness một lệnh

**Files:**
- Create: `eval/run.py`
- Create: `eval/configs/hybrid.yaml`, `eval/configs/bm25_only.yaml`, `eval/configs/dense_only.yaml`
- Create: `tests/test_eval/test_run.py`

**Interfaces:**
- Consumes: `Retriever` (Task 5), metrics (Task 7), `golden_qa.yaml` (Task 8)
- Produces: `eval.run.load_config(name: str) -> dict`; `eval.run.evaluate(config_name: str) -> dict`; ghi `eval/results/<config>-<n>.json` và cập nhật `eval/results/report.md`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_eval/test_run.py
import pytest

from eval.run import load_config, overlay_settings


def test_config_bm25_only_tat_nhanh_dense():
    cfg = load_config("bm25_only")
    assert cfg["retrieve_dense_topk"] == 0


def test_overlay_khong_sua_settings_goc():
    from src.config import get_settings

    goc = get_settings().retrieve_bm25_topk
    s2 = overlay_settings({"retrieve_bm25_topk": 999})
    assert s2.retrieve_bm25_topk == 999
    assert get_settings().retrieve_bm25_topk == goc, "overlay làm bẩn settings toàn cục"


def test_config_khong_ton_tai_nem_ro_rang():
    with pytest.raises(FileNotFoundError, match="khong-co-that"):
        load_config("khong-co-that")


@pytest.mark.integration
def test_evaluate_tra_ve_du_metric_va_ghi_file():
    from pathlib import Path

    r = evaluate_or_skip("hybrid")
    assert {"recall@5", "mrr@10", "ndcg@10", "n_queries", "config_name"} <= set(r)
    assert 0.0 <= r["recall@5"] <= 1.0
    assert Path(r["result_file"]).exists()


def evaluate_or_skip(name: str) -> dict:
    from pathlib import Path

    import pytest as _p

    from eval.run import evaluate

    if not Path("eval/datasets/golden_qa.yaml").exists():
        _p.skip("chưa có golden_qa.yaml")
    return evaluate(name)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_eval/test_run.py -v`
Expected: FAIL — `ModuleNotFoundError: eval.run`

- [ ] **Step 3: Viết `eval/configs/*.yaml`**

`hybrid.yaml`:
```yaml
retrieve_bm25_topk: 20
retrieve_dense_topk: 20
rrf_k: 60
retrieve_final_topk: 10
```

`bm25_only.yaml`:
```yaml
retrieve_bm25_topk: 20
retrieve_dense_topk: 0
rrf_k: 60
retrieve_final_topk: 10
```

`dense_only.yaml`:
```yaml
retrieve_bm25_topk: 0
retrieve_dense_topk: 20
rrf_k: 60
retrieve_final_topk: 10
```

- [ ] **Step 4: Viết `eval/run.py`**

```python
"""Eval harness. Một lệnh: python -m eval.run --config hybrid

Mọi tham số đến từ preset YAML, không hardcode — nhờ vậy mỗi dòng ablation là
một file config, tái lập được, và ghi được config_name vào kết quả.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k
from src.config import Settings, get_settings
from src.services.db import get_engine
from src.services.embedding import EmbeddingClient
from src.services.retrieval import Retriever, rrf

CONFIG_DIR = Path("eval/configs")


def load_config(name: str) -> dict:
    p = CONFIG_DIR / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"không có preset {name!r} tại {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def overlay_settings(overrides: dict) -> Settings:
    """Settings mới với override — KHÔNG sửa instance toàn cục đã cache."""
    base = get_settings().model_dump()
    base.update(overrides)
    return Settings(**base)


def _retrieve(r: Retriever, q: str, s: Settings) -> list[int]:
    branches: list[list[int]] = []
    if s.retrieve_bm25_topk > 0:
        branches.append(r.bm25(q, s.retrieve_bm25_topk))
    if s.retrieve_dense_topk > 0:
        branches.append(r.dense(q, s.retrieve_dense_topk))
    if not branches:
        raise ValueError("cả hai nhánh retrieval đều tắt — config sai")
    fused = rrf(branches, k=s.rrf_k)
    chunk_ids = [c for c, _ in fused[: s.retrieve_final_topk]]
    return r.provision_ids(chunk_ids)


def evaluate(config_name: str) -> dict:
    s = overlay_settings(load_config(config_name))
    items = yaml.safe_load(
        (Path(s.eval_dataset_dir) / "golden_qa.yaml").read_text(encoding="utf-8"))["items"]

    embedder = EmbeddingClient(
        api_key=s.openrouter_api_key, base_url=s.openrouter_base_url,
        model=s.openrouter_embedding_model_name, dim=s.openrouter_embedding_dim)
    r = Retriever(get_engine(), embedder, s)

    acc = {"recall@5": 0.0, "recall@10": 0.0, "mrr@10": 0.0, "ndcg@10": 0.0}
    per_item: list[dict] = []
    for it in items:
        got = _retrieve(r, it["cau_hoi"], s)
        gold = set(it["provision_ids"])
        m = {"recall@5": recall_at_k(got, gold, 5),
             "recall@10": recall_at_k(got, gold, 10),
             "mrr@10": mrr_at_k(got, gold, 10),
             "ndcg@10": ndcg_at_k(got, gold, 10)}
        for k in acc:
            acc[k] += m[k]
        per_item.append({"id": it["id"], **m, "retrieved": got[:10]})

    n = len(items)
    out = {k: round(v / n, 4) for k, v in acc.items()}
    out |= {"n_queries": n, "config_name": config_name,
            "embedding_model": s.openrouter_embedding_model_name,
            "ts": datetime.now(UTC).isoformat()}

    res_dir = Path(s.eval_result_dir)
    res_dir.mkdir(parents=True, exist_ok=True)
    f = res_dir / f"{config_name}-{n}.json"
    f.write_text(json.dumps({"summary": out, "per_item": per_item},
                            ensure_ascii=False, indent=2), encoding="utf-8")
    out["result_file"] = str(f)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="hybrid")
    a = ap.parse_args()
    r = evaluate(a.config)
    print(json.dumps({k: v for k, v in r.items() if k != "per_item"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Chạy 3 cấu hình, có bảng đầu tiên**

```bash
pytest tests/test_eval/test_run.py -v
for c in bm25_only dense_only hybrid; do python -m eval.run --config $c; done
```
Expected: 3 file JSON trong `eval/results/`. **Kỳ vọng định tính: `hybrid` ≥ max(bm25, dense) trên Recall@5.** Nếu không, kiểm `rrf_k` và xem một nhánh có trả rỗng không.

- [ ] **Step 6: Commit**

```bash
git add eval/run.py eval/configs/ tests/test_eval/test_run.py eval/results/
git commit -m "feat(eval): one-command harness driven entirely by config presets

Every retrieval parameter comes from a YAML preset, so an ablation row is a file
rather than a code edit - reproducible, and the config name travels into the
result. overlay_settings builds a fresh Settings instead of mutating the cached
global, which a test enforces: leaking an override would silently contaminate
every later row in the table. A config with both branches disabled raises rather
than quietly returning nothing."
```

---

## Task 10: Bảng so sánh embedding (tuần 4)

**Files:**
- Create: `scripts/compare_embeddings.py`
- Create: `docs/embedding-comparison.md`

**Interfaces:**
- Consumes: `scripts.build_chunks.run(model=...)`, `eval.run.evaluate`
- Produces: `docs/embedding-comparison.md` — bảng model × metric × chi phí

**Năm ứng viên, tất cả qua MỘT key OpenRouter:**
`baai/bge-m3` (1024, $0.010) · `openai/text-embedding-3-small` (1536, $0.020) · `qwen/qwen3-embedding-8b` (4096, $0.010) · `google/gemini-embedding-001` (?, $0.150) · `voyageai/voyage-4-lite` (?, $0.020)

- [ ] **Step 1: Viết script**

```python
"""So sánh embedding model trên chính golden_qa của dự án.

VN-MTEB không test model thương mại nào → số liệu này chưa ai công bố.
Mỗi model ghi một bộ chunks riêng (chunks.embedding_model), không ghi đè nhau.
"""

import json
from pathlib import Path

from eval.run import evaluate
from scripts.build_chunks import run as build

MODELS = [
    ("baai/bge-m3", 1024, 0.010),
    ("openai/text-embedding-3-small", 1536, 0.020),
    ("qwen/qwen3-embedding-8b", 4096, 0.010),
    ("google/gemini-embedding-001", 3072, 0.150),
    ("voyageai/voyage-4-lite", 1024, 0.020),
]


def compare() -> list[dict]:
    rows: list[dict] = []
    for model, dim, gia in MODELS:
        print(f"\n=== {model} (dim {dim}) ===")
        try:
            info = build(model=model)
        except Exception as e:  # dim không khớp cột vector(1024) → ghi lại, đi tiếp
            rows.append({"model": model, "dim": dim, "loi": str(e)[:200]})
            print("  LỖI:", str(e)[:200])
            continue
        r = evaluate("hybrid")
        rows.append({"model": model, "dim": dim, "$/1M": gia,
                     "chunks": info["chunks"], "tokens": info["tokens"],
                     "chi_phi_uoc": round(info["tokens"] / 1e6 * gia, 4),
                     "recall@5": r["recall@5"], "recall@10": r["recall@10"],
                     "mrr@10": r["mrr@10"], "ndcg@10": r["ndcg@10"]})
    return rows


if __name__ == "__main__":
    rows = compare()
    Path("docs/embedding-comparison.md").write_text(
        "# So sánh embedding model trên golden_qa Lao động\n\n"
        "VN-MTEB không đánh giá model thương mại nào — số liệu dưới đây chưa ai công bố.\n\n"
        "```json\n" + json.dumps(rows, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8")
    print("\nđã ghi docs/embedding-comparison.md")
```

- [ ] **Step 2: Xử lý ràng buộc chiều vector**

Cột `chunks.embedding` là `vector(1024)`. Model có dim khác **sẽ lỗi**. Trước khi chạy, thêm `migrations/003_embedding_dims.sql`:

```sql
-- pgvector không cho một cột nhiều chiều khác nhau → mỗi chiều một cột.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding_1536 vector(1536);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding_3072 vector(3072);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding_4096 vector(4096);
```

Và sửa `build_chunks.run` + `Retriever.dense` chọn cột theo `embedding_dim`:

```python
def _col(dim: int) -> str:
    return "embedding" if dim == 1024 else f"embedding_{dim}"
```

Dùng `_col()` trong câu INSERT của `build_chunks` và câu `ORDER BY ... <=> ...` của `Retriever.dense`.

- [ ] **Step 3: Chạy so sánh**

```bash
python -m scripts.compare_embeddings
cat docs/embedding-comparison.md
```
Expected: 5 dòng (hoặc ít hơn nếu model nào lỗi — lỗi được ghi lại, không làm dừng)

- [ ] **Step 4: Chốt `OPENROUTER_EMBEDDING_MODEL_NAME` theo số đo**

Đặt lại `.env` theo model thắng, rồi `python -m scripts.build_chunks` một lần cuối để bộ mặc định là model đã chọn.

- [ ] **Step 5: Commit**

```bash
git add scripts/compare_embeddings.py migrations/003_embedding_dims.sql docs/embedding-comparison.md src/services/retrieval.py scripts/build_chunks.py
git commit -m "feat(eval): compare five embedding models on the project's own golden set

VN-MTEB evaluates only open models, so nobody has published Vietnamese legal
numbers for the commercial APIs - this table is a genuine, if small, contribution.
pgvector cannot hold varying dimensions in one column, so each dimension gets its
own; a model that fails records the error and the sweep continues rather than
losing the rows already measured."
```

---

## KHÔNG thuộc plan này

| Hoãn | Thuộc plan |
|---|---|
| `rewrite_query` (dân sinh → ngôn ngữ pháp lý) | Plan 3 — nó là node của graph, và ablation của nó cần verifier để đo citation precision |
| Reranker | Plan 3 |
| Load `relationships.parquet` / cạnh ĐI VÀO cho hiệu lực Mức 2 | Plan 3 |
| `expand` (Khoản→Điều, reference 1-hop, lọc `as_of_date`) | Plan 3 — Task 1 của plan này đã dựng dữ liệu cạnh cho nó |
| 60 câu golden cho 5 Bộ luật khác + `trap` + `boundary` | Plan 3 (trap) và Plan 5 (boundary, cần tầng nông) |

## Sau plan này

**Điều kiện sang plan 3:** 3 file JSON trong `eval/results/` · `hybrid` ≥ max(bm25, dense) trên Recall@5 · `golden_qa.yaml` ≥50 câu đã review, `docs/golden-qa-process.md` có tỉ lệ loại · `docs/embedding-comparison.md` có bảng · `OPENROUTER_EMBEDDING_MODEL_NAME` đã chốt theo số đo.

**Ghi lại số Recall@5 của `hybrid`** — nó là baseline mà toàn bộ bảng ablation ở plan 5 so với.
