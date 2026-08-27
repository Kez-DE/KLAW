# KLAW Plan 1/5 — Phase 0 & Tầng dữ liệu

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng Postgres local có 6 Bộ luật + cụm văn bản Lao động đã parse thành cây `documents`/`provisions`/`references`, và vượt Cổng A (Data Integrity Audit).

**Architecture:** Bốn script rời chạy offline (`download_data` → `fetch_moj` → `parse_prov` → `ingest`), ghi seed JSONL vào git rồi load vào Postgres. Parser đọc class `prov-*` trong HTML của MOJ, không regex tiếng Việt. Ingest idempotent qua `documents.checksum`. API/agent chưa chạm tới ở plan này.

**Tech Stack:** Python 3.11 · FastAPI · Postgres 16 + pgvector + unaccent (docker-compose) · pandas/pyarrow · httpx · pytest

**Spec:** `docs/superpowers/specs/2026-08-27-klaw-design.md`

## Global Constraints

- Python **3.11** (`ruff target-version = "py311"`, `Dockerfile: python:3.11-slim`)
- ruff `line-length = 120`, `select = ["E","F","I","N","W","UP"]`, `ignore = ["E501"]`
- **MỘT key OpenRouter** cho LLM + embedding + rerank. `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- `OPENROUTER_EMBEDDING_MODEL_NAME=baai/bge-m3`, `OPENROUTER_EMBEDDING_DIM=1024`
- `LLM_TEMPERATURE=0.0` — **không** phải 0.7 của template
- `MOJ_API_BASE=https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public`
- `MOJ_RATE_LIMIT_SLEEP=1.5` — quan sát thực: HTTP 400 sau ~35 request liên tiếp
- **KHÔNG định danh văn bản bằng `title`** — `doc_id 96117` có `title = "Hàng hải"`. Dùng `so_ky_hieu` hoặc `doc_id`
- Citation neo vào `provisions.id`, **KHÔNG** vào `chunks.id`
- `data/raw/` **gitignored**; `data/seed/` **vào git**
- Postgres **local** cho toàn bộ dev/eval; Railway chỉ để demo (plan 4)
- **Không** `python-docx`, không LaTeX

## 6 Bộ luật (đã xác minh 2026-08-27, `metadata.parquet`)

| Bộ luật | `doc_id` | `so_ky_hieu` |
|---|---|---|
| Dân sự | 95942 | 91/2015/QH13 |
| Hình sự | 96122 | 100/2015/QH13 |
| Tố tụng dân sự | 96115 | 92/2015/QH13 |
| Tố tụng hình sự | 96172 | 101/2015/QH13 |
| Lao động | 139264 | 45/2019/QH14 |
| Hàng hải Việt Nam | 96117 | 95/2015/QH13 |

## Cụm Lao động (tầng sâu-B)

`152668` NĐ 145/2020 · `146696` TT 10/2020 · `183939` NĐ 293/2025 · `185561` NĐ 337/2025 · `153913` NĐ 12/2022 · `152670` TT 09/2020 · `153297` TT 18/2021 · `152734` NĐ 135/2020 · `134611` NĐ 29/2019 · `70811` Luật ATVSLĐ · `168670` NĐ 74/2024 *(bẫy: hết hiệu lực toàn bộ)* · `139094` NĐ 90/2019 *(bẫy: MOJ đánh sai "còn hiệu lực")*

## Files

| File | Trách nhiệm |
|---|---|
| `docker-compose.yml` *(modify)* | thêm service `db` — `pgvector/pgvector:pg16` |
| `requirements.txt` *(modify)* | bật DB deps, thêm pandas/pyarrow/httpx/beautifulsoup4 |
| `src/config.py` *(modify)* | `Settings` theo mục 8.1 spec |
| `src/models/domain.py` *(create)* | `Cap`, `ProvisionRow`, `DocumentRow`, `ReferenceRow` |
| `src/services/db.py` *(create)* | engine + `run_migrations()` |
| `src/services/moj_client.py` *(create)* | HTTP client MOJ, rate-limit |
| `src/services/prov_parser.py` *(create)* | **parser `prov-*` — 4 cạm bẫy** |
| `migrations/001_init.sql` *(create)* | 6 bảng + index |
| `scripts/download_data.py` *(create)* | 2 file parquet → `data/raw/` |
| `scripts/fetch_moj.py` *(create)* | 18 `doc_id` → `data/raw/moj/*.json` |
| `scripts/build_seed.py` *(create)* | parse → `data/seed/*.jsonl` |
| `scripts/ingest.py` *(create)* | seed → Postgres, idempotent |
| `scripts/gate_a_audit.py` *(create)* | **Cổng A** |
| `.env.example` *(modify)* | contract mục 8.1 |

---

## Task 0: Phase 0 — xác minh trước khi code

**Files:**
- Create: `docs/phase0-findings.md`

**Interfaces:**
- Produces: `docs/phase0-findings.md` — mỗi dòng có URL hoặc chữ "không xác minh được". Plan 2 đọc file này để chọn nhánh.

- [ ] **Step 1: Tạo file với 7 câu hỏi, chưa có câu trả lời**

```markdown
# Phase 0 — Findings (KLAW)

| # | Câu hỏi | Trả lời | Nguồn |
|---|---|---|---|
| 1 | Railway Postgres bật được `pgvector` + `unaccent`? | | |
| 2 | Railway auto-detect Dockerfile, hay cần `railway.json`? | | |
| 3 | Class `prov-*` có phủ đều cả 18 văn bản? | | |
| 4 | `/doc/{id}/related` có trả cạnh ĐI VÀO không? | | |
| 5 | **[NGƯỜI DÙNG]** Đối chiếu tay 10 điều BLLĐ với văn bản hợp nhất | | |
| 6 | `doc_id` của NĐ 157/2018, 141/2017, 122/2015 | | |
| 7 | **[NGƯỜI DÙNG]** Đối chiếu tay hiệu lực 6 luật gốc, ưu tiên Luật BHXH 41/2024 (`175027`) | | |
```

- [ ] **Step 2: Trả lời #4 — endpoint `related` có cạnh đi vào?**

```bash
python3 -c "
import json,urllib.request
u='https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/139094/related?pageNumber=0&pageSize=50'
d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'curl/8'}),timeout=40))
print(json.dumps(d, ensure_ascii=False)[:1500])
"
```

Ghi vào bảng: nếu response chứa văn bản **thay thế** NĐ 90/2019 thì cạnh đi vào **có** → bỏ được `relationships.parquet`. Nếu không → giữ.

- [ ] **Step 3: Trả lời #6 — tra 3 doc_id lương tối thiểu cũ**

```bash
python3 -c "
import pandas as pd
df=pd.read_parquet('data/raw/metadata.parquet')
m=df[df['so_ky_hieu'].astype(str).str.contains('157/2018|141/2017|122/2015',na=False)]
print(m[['id','so_ky_hieu','title','ngay_co_hieu_luc','tinh_trang_hieu_luc']].to_string(index=False))
"
```

- [ ] **Step 4: Ghi #5 và #7 là việc của người dùng, KHÔNG delegate**

Thêm vào cuối file:

```markdown
## Việc KHÔNG delegate được

#5 và #7 cần đọc văn bản hợp nhất và phán đoán pháp lý. Agent không làm thay.
Chặn: task Rule engine (plan 3) và cơ chế hiệu lực Mức 2 guard (plan 2).
```

- [ ] **Step 5: Commit**

```bash
git add docs/phase0-findings.md
git commit -m "docs: Phase 0 findings — verified answers and the two manual items"
```

---

## Task 1: Postgres local với pgvector + unaccent

**Files:**
- Modify: `docker-compose.yml`
- Create: `tests/test_infra/test_db_extensions.py`

**Interfaces:**
- Produces: Postgres tại `localhost:5432`, db `klaw`, user/pass `klaw`/`klaw`, có extension `vector` và `unaccent`.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_infra/test_db_extensions.py
import os

import psycopg
import pytest

DSN = os.getenv("DATABASE_URL", "postgresql://klaw:klaw@localhost:5432/klaw")


@pytest.mark.integration
def test_pgvector_va_unaccent_da_bat():
    with psycopg.connect(DSN) as conn:
        rows = conn.execute("SELECT extname FROM pg_extension").fetchall()
    names = {r[0] for r in rows}
    assert "vector" in names, f"thiếu pgvector; có: {names}"
    assert "unaccent" in names, f"thiếu unaccent; có: {names}"
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_infra/test_db_extensions.py -v`
Expected: FAIL — `psycopg.OperationalError: connection refused` (chưa có DB)

- [ ] **Step 3: Thêm service `db` vào `docker-compose.yml`**

```yaml
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: klaw
      POSTGRES_PASSWORD: klaw
      POSTGRES_DB: klaw
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./migrations/000_extensions.sql:/docker-entrypoint-initdb.d/000_extensions.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U klaw -d klaw"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  pgdata:
```

Và `migrations/000_extensions.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;
```

- [ ] **Step 4: Khởi động và chạy lại test**

```bash
docker compose up -d db
docker compose exec db pg_isready -U klaw -d klaw
pip install psycopg[binary]
pytest tests/test_infra/test_db_extensions.py -v
```
Expected: PASS

- [ ] **Step 5: Đăng ký marker `integration` để CI bỏ qua**

Thêm vào `pyproject.toml` (tạo mới nếu chưa có):

```toml
[tool.pytest.ini_options]
markers = ["integration: cần Postgres đang chạy; CI bỏ qua bằng -m 'not integration'"]
asyncio_mode = "auto"
```

Sửa `.github/workflows/ci.yml`, dòng `run: pytest tests/ -v --tb=short` thành:

```yaml
        run: pytest tests/ -v --tb=short -m "not integration"
```

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml migrations/000_extensions.sql tests/test_infra/ pyproject.toml .github/workflows/ci.yml
git commit -m "feat(infra): local Postgres 16 with pgvector and unaccent

Adds the db service the spec's local-first workflow needs: every ablation runs
against this container, so whether Railway supports pgvector no longer blocks
weeks 1-7. Marks the extension check as integration so CI stays green without a
database."
```

---

## Task 2: `Settings` theo contract spec 8.1

**Files:**
- Modify: `src/config.py`
- Modify: `.env.example`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `get_settings() -> Settings` với các field: `openrouter_api_key`, `openrouter_base_url`, `openrouter_model_name`, `openrouter_generate_model_name`, `openrouter_judge_model_name`, `openrouter_embedding_model_name`, `openrouter_embedding_dim`, `openrouter_rerank_model_name`, `openrouter_rerank_enabled`, `llm_temperature`, `database_url`, `chunk_max_tokens`, `retrieve_bm25_topk`, `retrieve_dense_topk`, `rrf_k`, `retrieve_final_topk`, `expand_reference_hops`, `verify_tier2_enabled`, `abstain_threshold`, `as_of_date`, `eval_config_name`, `eval_dataset_dir`, `eval_result_dir`, `data_raw_dir`, `data_seed_dir`, `moj_api_base`, `moj_rate_limit_sleep`.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_config.py
from src.config import Settings


def test_temperature_mac_dinh_la_0_khong_phai_0_7():
    s = Settings(_env_file=None)
    assert s.llm_temperature == 0.0


def test_embedding_mac_dinh_la_bge_m3_dim_1024():
    s = Settings(_env_file=None)
    assert s.openrouter_embedding_model_name == "baai/bge-m3"
    assert s.openrouter_embedding_dim == 1024


def test_ba_vai_llm_la_ba_model_khac_nhau():
    s = Settings(_env_file=None)
    assert s.openrouter_generate_model_name != s.openrouter_judge_model_name, (
        "judge phải khác họ với generate — self-preference bias, spec 7b.2"
    )


def test_database_url_mac_dinh_la_postgres_khong_phai_sqlite():
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql://")


def test_abstain_threshold_bi_chan_trong_khoang_0_1():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, abstain_threshold=1.5)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError` / `llm_temperature == 0.7`

- [ ] **Step 3: Viết lại `src/config.py`**

```python
from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "KLAW API"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # OpenRouter — MỘT key, ba endpoint (spec 7b.1, 8.1)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_name: str = "mistralai/mistral-nemo"
    openrouter_generate_model_name: str = "google/gemini-2.5-flash-lite"
    openrouter_judge_model_name: str = "mistralai/mistral-small-3.2-24b-instruct"
    openrouter_embedding_model_name: str = "baai/bge-m3"
    openrouter_embedding_dim: int = Field(default=1024, gt=0)
    openrouter_rerank_model_name: str = "cohere/rerank-4-fast"
    openrouter_rerank_enabled: bool = False

    # temperature 0.0 — spec 8.1: bảng ablation phải tái lập được
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # Database
    database_url: str = "postgresql://klaw:klaw@localhost:5432/klaw"

    # Retrieval & chunking
    chunk_max_tokens: int = Field(default=1500, gt=0)
    retrieve_bm25_topk: int = Field(default=20, gt=0)
    retrieve_dense_topk: int = Field(default=20, gt=0)
    rrf_k: int = Field(default=60, gt=0)
    retrieve_final_topk: int = Field(default=10, gt=0)
    expand_reference_hops: int = Field(default=1, ge=0)

    # Verifier
    verify_tier2_enabled: bool = True
    abstain_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    as_of_date: date | None = None

    # Eval
    eval_config_name: str = "full"
    eval_dataset_dir: str = "./eval/datasets"
    eval_result_dir: str = "./eval/results"

    # Data & ingest
    data_raw_dir: str = "./data/raw"
    data_seed_dir: str = "./data/seed"
    moj_api_base: str = "https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public"
    moj_rate_limit_sleep: float = Field(default=1.5, ge=0.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_config.py -v`
Expected: PASS (5 test)

- [ ] **Step 5: Cập nhật `.env.example` VÀ `.env` thật, gỡ 3 biến chết**

Copy nguyên block `dotenv` ở mục **8.1** của spec vào `.env.example`. Rồi dọn `.env` thật:

```bash
# Gỡ 3 biến chết khỏi .env (giữ nguyên các dòng khác)
python3 - <<'PY'
from pathlib import Path
p = Path(".env")
bo = ("OPENAI_API_KEY=", "COHERE_API_KEY=", "CHROMA_PERSIST_DIR=")
keep = [l for l in p.read_text(encoding="utf-8").splitlines()
        if not l.strip().startswith(bo)]
p.write_text("\n".join(keep) + "\n", encoding="utf-8")
print("da go:", bo)
PY
grep -c 'OPENAI_API_KEY' .env || echo "OPENAI_API_KEY da go — dung"
```

`OPENAI_API_KEY` trong `.env` là placeholder `sk-your-...-here`; để lại thì bất kỳ code nào đọc nó sẽ nhận **HTTP 401 rất khó truy nguyên**.

- [ ] **Step 6: Commit**

```bash
git add src/config.py .env.example tests/test_config.py
git commit -m "feat(config): Settings per spec 8.1 — one OpenRouter key, three model roles

Temperature drops from the template's 0.7 to 0.0 because the ablation table has
to be reproducible and structured output degrades at high temperature. A test
asserts generate and judge models differ, since sharing one would inflate
faithfulness through self-preference bias. Removes OPENAI_API_KEY (a placeholder
that returns 401), COHERE_API_KEY (rerank goes through OpenRouter) and
CHROMA_PERSIST_DIR (no Chroma)."
```

---

## Task 3: Schema SQL + migration runner

**Files:**
- Modify: `requirements.txt`
- Create: `migrations/001_init.sql`
- Create: `src/services/db.py`
- Create: `tests/test_infra/test_migrations.py`

**Interfaces:**
- Produces: `src.services.db.get_engine() -> sqlalchemy.Engine`, `src.services.db.run_migrations() -> list[str]` (trả tên file đã chạy).
- 6 bảng: `documents`, `provisions`, `references`, `chunks`, `verified_provisions`, `verified_documents`, `traces`.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_infra/test_migrations.py
import pytest
from sqlalchemy import inspect, text

from src.services.db import get_engine, run_migrations

BANG_BAT_BUOC = {
    "documents", "provisions", "references", "chunks",
    "verified_provisions", "verified_documents", "traces",
}


@pytest.mark.integration
def test_migration_tao_du_7_bang():
    run_migrations()
    names = set(inspect(get_engine()).get_table_names())
    assert BANG_BAT_BUOC <= names, f"thiếu: {BANG_BAT_BUOC - names}"


@pytest.mark.integration
def test_migration_idempotent_chay_hai_lan_khong_loi():
    run_migrations()
    run_migrations()


@pytest.mark.integration
def test_provisions_co_index_tren_duong_dan_va_document_id():
    run_migrations()
    idx = {i["name"] for i in inspect(get_engine()).get_indexes("provisions")}
    assert "ix_provisions_duong_dan" in idx
    assert "ix_provisions_document_id" in idx


@pytest.mark.integration
def test_chunks_mang_embedding_model_de_chay_nhieu_bo_song_song():
    run_migrations()
    cols = {c["name"] for c in inspect(get_engine()).get_columns("chunks")}
    assert {"embedding_model", "embedding_dim"} <= cols


@pytest.mark.integration
def test_bang_references_dung_duoc_ten_khoa_sql():
    # "references" là từ khóa SQL — phải quote được
    run_migrations()
    with get_engine().connect() as c:
        c.execute(text('SELECT count(*) FROM "references"'))
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_infra/test_migrations.py -v`
Expected: FAIL — `ModuleNotFoundError: src.services.db`

- [ ] **Step 3: Bật DB deps trong `requirements.txt`**

Thay block đang comment bằng:

```
# Database
sqlalchemy>=2.0.0
psycopg[binary]>=3.2.0

# Data
pandas>=2.2.0
pyarrow>=17.0.0
beautifulsoup4>=4.12.0
httpx>=0.28.0
```

Gỡ dòng `# chromadb>=0.5.0` và `langchain-openai` giữ nguyên (plan 2 dùng).

- [ ] **Step 4: Viết `migrations/001_init.sql`**

```sql
CREATE TABLE IF NOT EXISTS documents (
    id                  TEXT PRIMARY KEY,          -- moj doc_id
    so_ky_hieu          TEXT NOT NULL,
    loai_van_ban        TEXT NOT NULL,
    ten                 TEXT NOT NULL,
    co_quan_ban_hanh    TEXT,
    ngay_ban_hanh       DATE,
    ngay_hieu_luc       DATE,
    ngay_het_hieu_luc   DATE,
    tinh_trang          TEXT NOT NULL,             -- CHL | HHL | HHL1P | chua_hieu_luc
    depth               TEXT NOT NULL DEFAULT 'deep',   -- deep | shallow
    nguon_url           TEXT,
    checksum            TEXT NOT NULL,
    crawled_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provisions (
    id                  BIGSERIAL PRIMARY KEY,
    document_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_id           BIGINT REFERENCES provisions(id) ON DELETE CASCADE,
    cap                 TEXT NOT NULL,             -- phan|chuong|muc|dieu|khoan|diem
    so_hieu_cap         TEXT NOT NULL,
    tieu_de             TEXT NOT NULL DEFAULT '',
    noi_dung            TEXT NOT NULL DEFAULT '',
    duong_dan           TEXT NOT NULL,
    source_node_id      TEXT,                      -- NULLABLE, KHÔNG UNIQUE (bẫy #2)
    thu_tu              INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_provisions_document_id ON provisions(document_id);
CREATE INDEX IF NOT EXISTS ix_provisions_duong_dan   ON provisions(duong_dan);
CREATE INDEX IF NOT EXISTS ix_provisions_cap         ON provisions(cap);

CREATE TABLE IF NOT EXISTS "references" (
    id                  BIGSERIAL PRIMARY KEY,
    from_document_id    TEXT NOT NULL,
    to_document_id      TEXT,
    from_provision_id   BIGINT REFERENCES provisions(id) ON DELETE CASCADE,
    to_provision_id     BIGINT REFERENCES provisions(id) ON DELETE CASCADE,
    loai                INTEGER NOT NULL,          -- mã 1..15 của MOJ
    raw_text            TEXT
);
CREATE INDEX IF NOT EXISTS ix_references_to_document   ON "references"(to_document_id);
CREATE INDEX IF NOT EXISTS ix_references_from_document ON "references"(from_document_id);

CREATE TABLE IF NOT EXISTS chunks (
    id                  BIGSERIAL PRIMARY KEY,
    provision_id        BIGINT NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
    noi_dung_embed      TEXT NOT NULL,
    embedding           vector(1024),
    embedding_model     TEXT NOT NULL,
    embedding_dim       INTEGER NOT NULL,
    tsv                 tsvector,
    token_count         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_chunks_provision ON chunks(provision_id);
CREATE INDEX IF NOT EXISTS ix_chunks_model     ON chunks(embedding_model);
CREATE INDEX IF NOT EXISTS ix_chunks_tsv       ON chunks USING gin(tsv);

CREATE TABLE IF NOT EXISTS verified_provisions (
    provision_id        BIGINT PRIMARY KEY REFERENCES provisions(id) ON DELETE CASCADE,
    verified_at         DATE NOT NULL,
    verified_by         TEXT NOT NULL,
    nguon_doi_chieu     TEXT NOT NULL,
    ket_luan            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verified_documents (
    document_id            TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    verified_at            DATE NOT NULL,
    verified_by            TEXT NOT NULL,
    nguon_doi_chieu        TEXT NOT NULL,
    ket_luan_hieu_luc      TEXT NOT NULL,
    ghi_chu_lech_voi_moj   TEXT
);

CREATE TABLE IF NOT EXISTS traces (
    id                      TEXT PRIMARY KEY,
    ts                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    endpoint                TEXT NOT NULL,
    query                   TEXT,
    config_name             TEXT NOT NULL,
    result_type             TEXT,
    retrieved_ids           BIGINT[],
    claims_raw              INTEGER,
    claims_after_tier1      INTEGER,
    claims_after_tier2      INTEGER,
    latency_ms              INTEGER,
    token_in                INTEGER,
    token_out               INTEGER,
    cost_usd                NUMERIC(12, 8)
);
CREATE INDEX IF NOT EXISTS ix_traces_config ON traces(config_name);
```

- [ ] **Step 5: Viết `src/services/db.py`**

```python
from pathlib import Path

from sqlalchemy import Engine, create_engine, text

from src.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, future=True)
    return _engine


def run_migrations() -> list[str]:
    """Chạy mọi file migrations/*.sql theo thứ tự tên. Idempotent nhờ IF NOT EXISTS."""
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    applied: list[str] = []
    with get_engine().begin() as conn:
        for f in files:
            conn.execute(text(f.read_text(encoding="utf-8")))
            applied.append(f.name)
    return applied
```

- [ ] **Step 6: Chạy lại test**

```bash
pip install -r requirements.txt
pytest tests/test_infra/test_migrations.py -v
```
Expected: PASS (5 test)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt migrations/001_init.sql src/services/db.py tests/test_infra/test_migrations.py
git commit -m "feat(db): seven-table schema with plain-SQL idempotent migrations

provisions is a tree and chunks are flat, so citations anchor to provisions.id
which survives the re-chunking every ablation row requires; anchoring to chunk ids
would turn earlier eval numbers into garbage. chunks carries embedding_model so
several embedding sets coexist, which is what the week-4 comparison needs.
source_node_id is nullable and non-unique because 157 of the Labour Code's tags
carry no id at all and one id repeats. Skips Alembic: CREATE TABLE IF NOT EXISTS
plus a fifteen-line runner covers a single-environment thesis."
```

---

## Task 4: Domain models

**Files:**
- Create: `src/models/domain.py`
- Create: `tests/test_models/test_domain.py`

**Interfaces:**
- Produces: `Cap` (StrEnum: `phan chuong muc dieu khoan diem`), `ProvisionRow`, `DocumentRow`, `ReferenceRow` — Pydantic. `ProvisionRow` dùng `local_id`/`parent_local_id` (int) vì id thật do Postgres cấp lúc ingest.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_models/test_domain.py
import pytest
from pydantic import ValidationError

from src.models.domain import Cap, DocumentRow, ProvisionRow


def test_cap_co_dung_sau_bac():
    assert [c.value for c in Cap] == ["phan", "chuong", "muc", "dieu", "khoan", "diem"]


def test_cap_bac_tang_dan_de_stack_pop_dung():
    assert Cap.chuong.bac < Cap.dieu.bac < Cap.khoan.bac < Cap.diem.bac


def test_provision_row_cho_phep_noi_dung_rong_nhung_khong_cho_duong_dan_rong():
    ProvisionRow(local_id=0, parent_local_id=None, cap=Cap.dieu, so_hieu_cap="25",
                 tieu_de="Thời gian thử việc", noi_dung="", duong_dan="45/2019/QH14 > Điều 25",
                 source_node_id=None, thu_tu=0)
    with pytest.raises(ValidationError):
        ProvisionRow(local_id=0, parent_local_id=None, cap=Cap.dieu, so_hieu_cap="25",
                     tieu_de="x", noi_dung="", duong_dan="", source_node_id=None, thu_tu=0)


def test_document_row_bat_buoc_so_ky_hieu_khong_dung_ten():
    # doc_id 96117 có title = "Hàng hải" — định danh phải là so_ky_hieu
    d = DocumentRow(id="96117", so_ky_hieu="95/2015/QH13", loai_van_ban="Bộ luật",
                    ten="Hàng hải", tinh_trang="HHL1P", checksum="abc", depth="deep")
    assert d.so_ky_hieu == "95/2015/QH13"
    with pytest.raises(ValidationError):
        DocumentRow(id="96117", so_ky_hieu="", loai_van_ban="Bộ luật", ten="Hàng hải",
                    tinh_trang="HHL1P", checksum="abc", depth="deep")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_models/test_domain.py -v`
Expected: FAIL — `ModuleNotFoundError: src.models.domain`

- [ ] **Step 3: Viết `src/models/domain.py`**

```python
from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Cap(StrEnum):
    phan = "phan"
    chuong = "chuong"
    muc = "muc"
    dieu = "dieu"
    khoan = "khoan"
    diem = "diem"

    @property
    def bac(self) -> int:
        """Bậc trong cây; dùng để pop stack khi parse HTML phẳng."""
        return list(Cap).index(self)


class DocumentRow(BaseModel):
    id: str = Field(..., min_length=1)
    so_ky_hieu: str = Field(..., min_length=1)
    loai_van_ban: str = Field(..., min_length=1)
    ten: str = ""
    co_quan_ban_hanh: str | None = None
    ngay_ban_hanh: date | None = None
    ngay_hieu_luc: date | None = None
    ngay_het_hieu_luc: date | None = None
    tinh_trang: str = Field(..., min_length=1)
    depth: Literal["deep", "shallow"] = "deep"
    nguon_url: str | None = None
    checksum: str = Field(..., min_length=1)


class ProvisionRow(BaseModel):
    local_id: int
    parent_local_id: int | None
    cap: Cap
    so_hieu_cap: str
    tieu_de: str = ""
    noi_dung: str = ""
    duong_dan: str = Field(..., min_length=1)
    source_node_id: str | None = None
    thu_tu: int


class ReferenceRow(BaseModel):
    from_document_id: str
    to_document_id: str | None = None
    loai: int
    raw_text: str | None = None
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_models/test_domain.py -v`
Expected: PASS (4 test)

- [ ] **Step 5: Commit**

```bash
git add src/models/domain.py tests/test_models/
git commit -m "feat(models): domain rows with Cap carrying its own tree depth

Cap.bac exists so the parser can pop its stack by level, which is the only way to
recover hierarchy from MOJ's flat HTML where every <p> is a sibling. DocumentRow
requires a non-empty so_ky_hieu and tolerates any ten, because doc_id 96117's
title is merely 'Hàng hải' and identification must never rest on the title."
```

---

## Task 5: Tải parquet

**Files:**
- Create: `scripts/download_data.py`
- Create: `tests/test_scripts/test_download_data.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `scripts.download_data.FILES` (dict tên→URL), `scripts.download_data.download(dest: Path, only: list[str] | None = None) -> dict[str, Path]`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_scripts/test_download_data.py
from scripts.download_data import FILES


def test_khong_bao_gio_tai_content_parquet_784mb():
    assert "content" not in FILES, (
        "content.parquet là 784 MB và không cần: toàn văn lấy từ API MOJ (spec 4b.3)"
    )


def test_chi_tai_dung_hai_file_can_thiet():
    assert set(FILES) == {"metadata", "relationships"}


def test_khong_tai_thu_muc_legacy_3_5gb():
    assert all("legacy" not in u for u in FILES.values())
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_scripts/test_download_data.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.download_data`

- [ ] **Step 3: Viết `scripts/download_data.py`**

```python
"""Tải 2 file parquet cần thiết từ HuggingFace (~25 MB).

KHÔNG tải data/content.parquet (784 MB): toàn văn lấy từ API MOJ, tươi hơn và
có effStatus tại thời điểm chạy. KHÔNG tải legacy/ (3,5 GB).
"""

import sys
from pathlib import Path

import httpx

BASE = "https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents/resolve/main/data"

FILES = {
    "metadata": f"{BASE}/metadata.parquet",           # 15,1 MB — tra doc_id
    "relationships": f"{BASE}/relationships.parquet",  # 9,4 MB — cạnh ĐI VÀO cho Mức 2
}


def download(dest: Path, only: list[str] | None = None) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for name, url in FILES.items():
        if only and name not in only:
            continue
        path = dest / f"{name}.parquet"
        if path.exists():
            print(f"[skip] {path} đã có ({path.stat().st_size / 1e6:.1f} MB)")
            out[name] = path
            continue
        print(f"[get ] {name} …")
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
            r.raise_for_status()
            with path.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
        print(f"[ok  ] {path} ({path.stat().st_size / 1e6:.1f} MB)")
        out[name] = path
    return out


if __name__ == "__main__":
    from src.config import get_settings

    download(Path(get_settings().data_raw_dir))
    sys.exit(0)
```

Tạo `scripts/__init__.py` và `tests/test_scripts/__init__.py` (rỗng) để import được.

- [ ] **Step 4: Chạy lại test và chạy script thật**

```bash
pytest tests/test_scripts/test_download_data.py -v
python -m scripts.download_data
ls -lh data/raw/
```
Expected: test PASS; `metadata.parquet` ~15 MB, `relationships.parquet` ~9 MB

- [ ] **Step 5: Thêm `data/raw/` vào `.gitignore`**

```bash
grep -qxF 'data/raw/' .gitignore || echo 'data/raw/' >> .gitignore
```

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/download_data.py tests/test_scripts/ .gitignore
git commit -m "feat(data): download only the two parquet files that are needed

A test asserts content.parquet is absent from FILES. It is 784 MB and buys
nothing: full text comes from the MOJ API instead, which arrives from the primary
source with live effStatus rather than a crawl snapshot of unknown vintage. Total
download drops to about 25 MB."
```

---

## Task 6: Client API MOJ

**Files:**
- Create: `src/services/moj_client.py`
- Create: `tests/test_services/test_moj_client.py`

**Interfaces:**
- Produces: `MojClient(base: str, sleep: float)`, `.fetch_doc(doc_id: str) -> dict`, `.fetch_related(doc_id: str) -> list[dict]`, `.fetch_many(doc_ids: list[str], dest: Path) -> dict[str, Path]`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_services/test_moj_client.py
import httpx
import pytest

from src.services.moj_client import MojClient


def _client(handler) -> MojClient:
    c = MojClient(base="https://x/api", sleep=0.0)
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_fetch_doc_boc_lop_data():
    def h(req):
        return httpx.Response(200, json={"data": {"id": "139264", "docNum": "45/2019/QH14"}})

    assert _client(h).fetch_doc("139264")["docNum"] == "45/2019/QH14"


def test_rate_limit_sleep_duoc_goi_giua_cac_request(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr("src.services.moj_client.time.sleep", lambda s: calls.append(s))

    def h(req):
        return httpx.Response(200, json={"data": {"id": "1"}})

    c = _client(h)
    c.sleep = 1.5
    c.fetch_doc("1")
    c.fetch_doc("2")
    assert calls == [1.5, 1.5], "phải nghỉ giữa các request — HTTP 400 sau ~35 request liên tiếp"


def test_http_loi_nem_ra_khong_tra_dict_rong():
    def h(req):
        return httpx.Response(400, text="bad")

    with pytest.raises(httpx.HTTPStatusError):
        _client(h).fetch_doc("1")


def test_response_thieu_data_nem_ValueError_khong_tra_None():
    def h(req):
        return httpx.Response(200, json={"success": False})

    with pytest.raises(ValueError, match="thiếu 'data'"):
        _client(h).fetch_doc("1")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_services/test_moj_client.py -v`
Expected: FAIL — `ModuleNotFoundError: src.services.moj_client`

- [ ] **Step 3: Viết `src/services/moj_client.py`**

```python
import json
import time
from pathlib import Path

import httpx


class MojClient:
    """Client cho API công khai của CSDL quốc gia về VBPL (Bộ Tư pháp).

    Không auth. Quan sát thực: HTTP 400 thoáng qua sau ~35 request liên tiếp,
    nên nghỉ `sleep` giây trước MỖI request.
    """

    def __init__(self, base: str, sleep: float) -> None:
        self.base = base.rstrip("/")
        self.sleep = sleep
        self._http = httpx.Client(timeout=60, headers={"User-Agent": "klaw-thesis/1.0"})

    def _get(self, path: str) -> dict:
        time.sleep(self.sleep)
        r = self._http.get(f"{self.base}{path}")
        r.raise_for_status()
        return r.json()

    def fetch_doc(self, doc_id: str) -> dict:
        payload = self._get(f"/doc/{doc_id}")
        if "data" not in payload or payload["data"] is None:
            raise ValueError(f"response cho doc {doc_id} thiếu 'data'")
        return payload["data"]

    def fetch_related(self, doc_id: str) -> list[dict]:
        payload = self._get(f"/doc/{doc_id}/related?pageNumber=0&pageSize=200")
        return (payload.get("data") or {}).get("items") or []

    def fetch_many(self, doc_ids: list[str], dest: Path) -> dict[str, Path]:
        dest.mkdir(parents=True, exist_ok=True)
        out: dict[str, Path] = {}
        for did in doc_ids:
            p = dest / f"{did}.json"
            if p.exists():
                out[did] = p
                continue
            p.write_text(json.dumps(self.fetch_doc(did), ensure_ascii=False), encoding="utf-8")
            print(f"[ok] {did} → {p.name}")
            out[did] = p
        return out
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_services/test_moj_client.py -v`
Expected: PASS (4 test)

- [ ] **Step 5: Commit**

```bash
git add src/services/moj_client.py tests/test_services/
git commit -m "feat(moj): API client that sleeps before every request and never swallows errors

A missing 'data' key raises ValueError rather than returning an empty dict,
because a silently empty document would parse to zero provisions and look like a
parser bug for the rest of the project. The rate-limit sleep is asserted by test:
the gateway returned a transient HTTP 400 after roughly 35 consecutive requests."
```

---

## Task 7: Parser `prov-*` — bốn cạm bẫy

**Files:**
- Create: `src/services/prov_parser.py`
- Create: `tests/test_services/test_prov_parser.py`

**Interfaces:**
- Consumes: `Cap`, `ProvisionRow` (Task 4)
- Produces: `parse_provisions(html: str, so_ky_hieu: str) -> list[ProvisionRow]`, `parse_tables(html: str) -> list[str]` (mỗi bảng là markdown)

- [ ] **Step 1: Viết test thất bại — năm test, bốn cạm bẫy**

```python
# tests/test_services/test_prov_parser.py
from src.models.domain import Cap
from src.services.prov_parser import parse_provisions, parse_tables

SKH = "45/2019/QH14"

# HTML thật từ documentContent.content của doc_id 139264 (rút gọn)
HTML_DIEU_21 = """
<div class="WordSection1">
<p id="a1" class="MsoNormal prov-chapter"><strong><b>Chương III<br>HỢP ĐỒNG LAO ĐỘNG</b></strong></p>
<p id="a2" class="MsoNormal prov-article"><strong><b>Điều 21. Nội dung hợp đồng lao động</b></strong></p>
<p id="a3" class="MsoNormal prov-clause">1. Hợp đồng lao động phải có những nội dung chủ yếu sau đây:</p>
<p id="a4" class="MsoNormal prov-item">a) Tên, địa chỉ của người sử dụng lao động;</p>
<p id="a5" class="MsoNormal prov-item">b) Họ tên, ngày tháng năm sinh, giới tính;</p>
<p id="a6" class="MsoNormal prov-article"><strong><b>Điều 26. Tiền lương thử việc</b></strong></p>
<p class="MsoNormal prov-content">Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó.</p>
</div>
"""

HTML_BANG = """
<div class="WordSection1">
<p id="b1" class="MsoNormal prov-article"><strong><b>Điều 3. Mức lương tối thiểu</b></strong></p>
<table><tr><td>Vùng</td><td>Mức tháng</td></tr>
<tr><td>Vùng I</td><td>5.310.000</td></tr>
<tr><td>Vùng II</td><td>4.730.000</td></tr></table>
</div>
"""


def test_bay_1_html_phang_van_dung_duoc_cay_theo_class():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    by_path = {r.duong_dan: r for r in rows}
    diem_a = by_path["45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a"]
    khoan_1 = by_path["45/2019/QH14 > Điều 21 > Khoản 1"]
    assert diem_a.parent_local_id == khoan_1.local_id
    assert by_path["45/2019/QH14 > Điều 21"].cap is Cap.dieu


def test_bay_2_prov_content_KHONG_CO_ID_van_giu_duoc_noi_dung_dieu_26():
    """Bẫy nặng nhất: parser đòi id sẽ mất trắng nội dung Điều 26."""
    rows = parse_provisions(HTML_DIEU_21, SKH)
    d26 = next(r for r in rows if r.duong_dan == "45/2019/QH14 > Điều 26")
    assert "85%" in d26.noi_dung, "mất nội dung Điều 26 — prov-content không có id"
    assert d26.source_node_id == "a6"


def test_bay_3_br_khong_lam_dinh_chu():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    chuong = next(r for r in rows if r.cap is Cap.chuong)
    assert "IIIHỢP" not in chuong.tieu_de + chuong.noi_dung
    assert "Chương III" in chuong.tieu_de


def test_bay_4_bang_parse_rieng_giu_hang_cot():
    tables = parse_tables(HTML_BANG)
    assert len(tables) == 1
    assert "Vùng I" in tables[0] and "5.310.000" in tables[0]
    assert tables[0].count("\n") >= 2, "phải giữ nhiều hàng, không bẹp thành 1 dòng"
    # và bảng KHÔNG lọt vào provisions dưới dạng prov-content rời
    rows = parse_provisions(HTML_BANG, "293/2025/NĐ-CP")
    assert not any(r.noi_dung.strip() == "Vùng I" for r in rows)


def test_so_hieu_cap_tach_dung_tu_text():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    assert next(r for r in rows if r.cap is Cap.dieu and r.so_hieu_cap == "21")
    assert next(r for r in rows if r.cap is Cap.khoan and r.so_hieu_cap == "1")
    assert next(r for r in rows if r.cap is Cap.diem and r.so_hieu_cap == "a")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_services/test_prov_parser.py -v`
Expected: FAIL (5 test) — `ModuleNotFoundError: src.services.prov_parser`

- [ ] **Step 3: Viết `src/services/prov_parser.py`**

```python
"""Parse cấu trúc Điều/Khoản/Điểm từ HTML của API MOJ.

Đọc class `prov-*`, KHÔNG regex tiếng Việt. HTML phẳng: mọi <p> là anh em ruột
trong div.WordSection1, cấp bậc chỉ nằm ở tên class → duyệt tuần tự + stack.

Bốn cạm bẫy (spec 4.5), mỗi cái có test riêng:
  1. HTML phẳng          → stack theo Cap.bac
  2. prov-content KHÔNG có id → gắn vào node đỉnh stack, KHÔNG tạo node mới
  3. <br> dính chữ       → thay bằng ' ' TRƯỚC khi strip tag
  4. bảng bị bẹp         → parse <table> bằng đường riêng, loại khỏi luồng prov-*
"""

import re

from bs4 import BeautifulSoup, Tag

from src.models.domain import Cap, ProvisionRow

CLASS_TO_CAP = {
    "prov-part": Cap.phan,
    "prov-chapter": Cap.chuong,
    "prov-section": Cap.muc,
    "prov-article": Cap.dieu,
    "prov-clause": Cap.khoan,
    "prov-item": Cap.diem,
}

NHAN = {Cap.phan: "Phần", Cap.chuong: "Chương", Cap.muc: "Mục",
        Cap.dieu: "Điều", Cap.khoan: "Khoản", Cap.diem: "Điểm"}

RE_SO = {
    Cap.dieu: re.compile(r"^Điều\s+(\d+)"),
    Cap.khoan: re.compile(r"^(\d+)\s*[.)]"),
    Cap.diem: re.compile(r"^([a-zăâđêôơư])\s*\)", re.IGNORECASE),
    Cap.chuong: re.compile(r"^Chương\s+([IVXLCDM\d]+)", re.IGNORECASE),
    Cap.muc: re.compile(r"^Mục\s+([IVXLCDM\d]+)", re.IGNORECASE),
    Cap.phan: re.compile(r"^Phần\s+(\S+)"),  # `re` KHÔNG hỗ trợ \p{L} — dùng \S+
}


def _text(tag: Tag) -> str:
    """Bẫy #3: thay <br> bằng khoảng trắng TRƯỚC khi lấy text."""
    for br in tag.find_all("br"):
        br.replace_with(" ")
    return re.sub(r"\s+", " ", tag.get_text()).strip()


def _cap_of(tag: Tag) -> Cap | None:
    for cls in tag.get("class") or []:
        if cls in CLASS_TO_CAP:
            return CLASS_TO_CAP[cls]
    return None


def _is_content(tag: Tag) -> bool:
    return "prov-content" in (tag.get("class") or [])


def _so_hieu(cap: Cap, text: str) -> str:
    m = RE_SO.get(cap)
    if m is None:
        return ""
    hit = m.match(text)
    return hit.group(1) if hit else ""


def parse_tables(html: str) -> list[str]:
    """Bẫy #4: parse <table> riêng, mỗi bảng thành một markdown table."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for tbl in soup.find_all("table"):
        lines: list[str] = []
        for tr in tbl.find_all("tr"):
            cells = [_text(td) for td in tr.find_all(["td", "th"])]
            if cells:
                lines.append("| " + " | ".join(cells) + " |")
        if lines:
            out.append("\n".join(lines))
    return out


def parse_provisions(html: str, so_ky_hieu: str) -> list[ProvisionRow]:
    soup = BeautifulSoup(html, "html.parser")

    # Bẫy #4: bỏ hẳn <table> khỏi luồng prov-* để ô không lọt vào dạng prov-content rời
    for tbl in soup.find_all("table"):
        tbl.decompose()

    rows: list[ProvisionRow] = []
    stack: list[ProvisionRow] = []
    thu_tu = 0

    for tag in soup.find_all("p"):
        text = _text(tag)
        if not text:
            continue

        if _is_content(tag):
            # Bẫy #2: KHÔNG tạo node mới, KHÔNG đòi id — gắn vào đỉnh stack
            if stack:
                cur = stack[-1]
                cur.noi_dung = (cur.noi_dung + " " + text).strip() if cur.noi_dung else text
            continue

        cap = _cap_of(tag)
        if cap is None:
            continue

        # Bẫy #1: pop stack tới khi đỉnh có bậc nhỏ hơn
        while stack and stack[-1].cap.bac >= cap.bac:
            stack.pop()

        so = _so_hieu(cap, text)
        parent = stack[-1] if stack else None
        duong_dan = (parent.duong_dan if parent else so_ky_hieu) + f" > {NHAN[cap]} {so}".rstrip()

        row = ProvisionRow(
            local_id=len(rows),
            parent_local_id=parent.local_id if parent else None,
            cap=cap,
            so_hieu_cap=so,
            tieu_de=text,
            noi_dung="",
            duong_dan=duong_dan,
            source_node_id=tag.get("id"),
            thu_tu=thu_tu,
        )
        thu_tu += 1
        rows.append(row)
        stack.append(row)

    return rows
```

- [ ] **Step 4: Chạy lại test**

Run: `pytest tests/test_services/test_prov_parser.py -v`
Expected: PASS (5 test)

- [ ] **Step 5: Acceptance test trên BLLĐ thật — 220 Điều**

```python
# thêm vào tests/test_services/test_prov_parser.py
import json
from pathlib import Path

import pytest

from src.models.domain import Cap
from src.services.prov_parser import parse_provisions


@pytest.mark.integration
def test_bo_luat_lao_dong_that_co_dung_220_dieu():
    p = Path("data/raw/moj/139264.json")
    if not p.exists():
        pytest.skip("chạy `python -m scripts.fetch_moj` trước")
    doc = json.loads(p.read_text(encoding="utf-8"))
    rows = parse_provisions(doc["documentContent"]["content"], "45/2019/QH14")
    dieu = [r for r in rows if r.cap is Cap.dieu]
    assert len(dieu) == 220, f"đếm được {len(dieu)} Điều, phải là 220"
    assert dieu[0].so_hieu_cap == "1"
    assert dieu[-1].so_hieu_cap == "220"
    assert all(r.noi_dung or any(c.parent_local_id == r.local_id for c in rows) for r in dieu), (
        "có Điều vừa rỗng nội dung vừa không có con — dấu hiệu mất dữ liệu"
    )
```

- [ ] **Step 6: Commit**

```bash
git add src/services/prov_parser.py tests/test_services/test_prov_parser.py
git commit -m "feat(parser): read prov-* classes with a test per known trap

MOJ's provisionTree is null on all 40 documents checked, but the HTML already
carries structure in CSS classes, so no Vietnamese regex is needed. Each of the
four traps gets its own test because each fails silently. The heaviest is
prov-content without an id: 157 of the Labour Code's 1332 tags have no id, and a
parser that requires one loses the whole text of Article 26 on tiền lương thử
việc without any error. Tables are removed from the prov-* stream and parsed
separately, otherwise the minimum-wage table in NĐ 293/2025 shatters into fifteen
loose fragments."
```

---

## Task 8: Fetch 18 văn bản + build seed

**Files:**
- Create: `scripts/fetch_moj.py`
- Create: `scripts/build_seed.py`
- Create: `tests/test_scripts/test_build_seed.py`

**Interfaces:**
- Consumes: `MojClient` (Task 6), `parse_provisions`/`parse_tables` (Task 7), `DocumentRow`/`ProvisionRow` (Task 4)
- Produces: `scripts.fetch_moj.DOC_IDS` (dict `doc_id` → `("deep"|"shallow", so_ky_hieu)`), `scripts.build_seed.build(raw: Path, out: Path) -> dict[str, int]`
- Ghi `data/seed/documents.jsonl`, `provisions.jsonl`, `references.jsonl`, `checksums.json`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_scripts/test_build_seed.py
from scripts.fetch_moj import DOC_IDS


def test_du_6_bo_luat_o_tang_sau():
    bo_luat = {"95942", "96122", "96115", "96172", "139264", "96117"}
    assert bo_luat <= set(DOC_IDS)
    assert all(DOC_IDS[d][0] == "deep" for d in bo_luat)


def test_co_hai_van_ban_bay_hieu_luc():
    # NĐ 74/2024 hết hiệu lực toàn bộ; NĐ 90/2019 MOJ đánh sai "còn hiệu lực"
    assert "168670" in DOC_IDS and "139094" in DOC_IDS


def test_moi_doc_id_co_so_ky_hieu_khong_rong():
    assert all(skh for _, skh in DOC_IDS.values()), "định danh bằng so_ky_hieu, không bằng title"


def test_khong_co_doc_id_trung():
    assert len(DOC_IDS) == len(set(DOC_IDS))
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_scripts/test_build_seed.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.fetch_moj`

- [ ] **Step 3: Viết `scripts/fetch_moj.py`**

```python
"""Tải toàn văn 18 văn bản từ API MOJ vào data/raw/moj/*.json."""

from pathlib import Path

from src.config import get_settings
from src.services.moj_client import MojClient

# doc_id → (depth, so_ky_hieu).  Xác minh 2026-08-27 qua metadata.parquet + API live.
DOC_IDS: dict[str, tuple[str, str]] = {
    # ── 6 Bộ luật — trục tra cứu (tầng sâu-A) ──
    "95942": ("deep", "91/2015/QH13"),    # Bộ luật Dân sự
    "96122": ("deep", "100/2015/QH13"),   # Bộ luật Hình sự
    "96115": ("deep", "92/2015/QH13"),    # Bộ luật Tố tụng dân sự
    "96172": ("deep", "101/2015/QH13"),   # Bộ luật Tố tụng hình sự
    "139264": ("deep", "45/2019/QH14"),   # Bộ luật Lao động
    "96117": ("deep", "95/2015/QH13"),    # Bộ luật Hàng hải (title CSDL = "Hàng hải")
    # ── Cụm Lao động — trục soạn thảo (tầng sâu-B) ──
    "152668": ("deep", "145/2020/NĐ-CP"),
    "146696": ("deep", "10/2020/TT-BLĐTBXH"),
    "183939": ("deep", "293/2025/NĐ-CP"),
    "185561": ("deep", "337/2025/NĐ-CP"),
    "153913": ("deep", "12/2022/NĐ-CP"),
    "152670": ("deep", "09/2020/TT-BLĐTBXH"),
    "153297": ("deep", "18/2021/TT-BLĐTBXH"),
    "152734": ("deep", "135/2020/NĐ-CP"),
    "134611": ("deep", "29/2019/NĐ-CP"),
    "70811": ("deep", "84/2015/QH13"),
    # ── Tập bẫy hiệu lực: PHẢI ingest dù đã hết hiệu lực (spec 4.3 tầng 3) ──
    "168670": ("deep", "74/2024/NĐ-CP"),  # hết hiệu lực toàn bộ → test Mức 1
    "139094": ("deep", "90/2019/NĐ-CP"),  # MOJ đánh sai "còn hiệu lực" → test Mức 2
}

if __name__ == "__main__":
    s = get_settings()
    client = MojClient(base=s.moj_api_base, sleep=s.moj_rate_limit_sleep)
    client.fetch_many(list(DOC_IDS), Path(s.data_raw_dir) / "moj")
```

- [ ] **Step 4: Viết `scripts/build_seed.py`**

```python
"""Parse JSON thô → data/seed/*.jsonl (VÀO GIT)."""

import hashlib
import json
from pathlib import Path

from scripts.fetch_moj import DOC_IDS
from src.models.domain import DocumentRow, ProvisionRow
from src.services.prov_parser import parse_provisions, parse_tables

TINH_TRANG_MAP = {
    "CHL": "CHL", "HHL": "HHL", "HHL1P": "HHL1P",
}


def _date(v: str | None) -> str | None:
    return v[:10] if v else None


def build(raw: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    docs: list[dict] = []
    provs: list[dict] = []
    refs: list[dict] = []
    checksums: dict[str, str] = {}

    for doc_id, (depth, so_ky_hieu) in DOC_IDS.items():
        p = raw / "moj" / f"{doc_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"chưa fetch {doc_id}; chạy `python -m scripts.fetch_moj`")
        d = json.loads(p.read_text(encoding="utf-8"))
        html = (d.get("documentContent") or {}).get("content") or ""
        if not html:
            raise ValueError(f"doc {doc_id} không có documentContent.content — không được bỏ qua im lặng")

        checksum = hashlib.sha256(html.encode("utf-8")).hexdigest()
        checksums[doc_id] = checksum

        docs.append(DocumentRow(
            id=doc_id,
            so_ky_hieu=so_ky_hieu,
            loai_van_ban=d.get("docType") or "Chưa xác định",
            ten=d.get("title") or "",
            co_quan_ban_hanh=d.get("agencyName"),
            ngay_ban_hanh=_date(d.get("issueDate")),
            ngay_hieu_luc=_date(d.get("effFrom")),
            ngay_het_hieu_luc=_date(d.get("effTo")),
            tinh_trang=TINH_TRANG_MAP.get((d.get("effStatus") or {}).get("code", ""), "chua_xac_dinh"),
            depth=depth,
            nguon_url=f"vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{doc_id}",
            checksum=checksum,
        ).model_dump(mode="json"))

        tables = parse_tables(html)
        for r in parse_provisions(html, so_ky_hieu):
            row = r.model_dump(mode="json")
            row["document_id"] = doc_id
            provs.append(row)
        if tables:
            provs.append({"document_id": doc_id, "local_id": -1, "parent_local_id": None,
                          "cap": "dieu", "so_hieu_cap": "", "tieu_de": "[BẢNG]",
                          "noi_dung": "\n\n".join(tables), "duong_dan": f"{so_ky_hieu} > [Bảng]",
                          "source_node_id": None, "thu_tu": 10**6})

        for ref in d.get("references") or []:
            tgt = ref.get("targetDocument") or {}
            refs.append({"from_document_id": doc_id,
                         "to_document_id": str(tgt.get("id")) if tgt.get("id") else None,
                         "loai": ref.get("referenceType") or 0,
                         "raw_text": tgt.get("docNum")})

    for name, data in (("documents", docs), ("provisions", provs), ("references", refs)):
        (out / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in data) + "\n", encoding="utf-8")
    (out / "checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")

    return {"documents": len(docs), "provisions": len(provs), "references": len(refs)}


if __name__ == "__main__":
    from src.config import get_settings

    s = get_settings()
    print(build(Path(s.data_raw_dir), Path(s.data_seed_dir)))
```

- [ ] **Step 5: Chạy thật và kiểm số**

```bash
pytest tests/test_scripts/test_build_seed.py -v
python -m scripts.fetch_moj          # ~18 × 1,5s
python -m scripts.build_seed
pytest tests/test_services/test_prov_parser.py -v -m integration
python3 -c "
import json
p=[json.loads(l) for l in open('data/seed/provisions.jsonl',encoding='utf-8')]
bl=[r for r in p if r['document_id']=='139264' and r['cap']=='dieu']
print('BLLĐ Điều:',len(bl),'(phải 220)')
print('tổng provisions:',len(p))
"
```
Expected: BLLĐ 220 Điều; tổng provisions vài nghìn

- [ ] **Step 6: Commit (seed VÀO git)**

```bash
git add scripts/fetch_moj.py scripts/build_seed.py tests/test_scripts/test_build_seed.py data/seed/
git commit -m "feat(data): fetch 18 documents and build the seed that goes into git

DOC_IDS carries so_ky_hieu next to every id because doc_id 96117's title in the
national database is merely 'Hàng hải' with the statute name lost, so nothing may
identify a document by title. Two expired decrees are deliberately included: NĐ
74/2024 is fully expired and NĐ 90/2019 is still marked effective by MOJ despite
being superseded. Filtering them out would remove the very documents the
effectivity trap set needs, leaving the three-tier mechanism nothing to measure.
An empty documentContent raises rather than being skipped."
```

---

## Task 9: Ingest vào Postgres, idempotent

**Files:**
- Create: `scripts/ingest.py`
- Create: `tests/test_scripts/test_ingest.py`

**Interfaces:**
- Consumes: `run_migrations`/`get_engine` (Task 3), seed JSONL (Task 8)
- Produces: `scripts.ingest.ingest(seed: Path) -> dict[str, int]` — số dòng đã ghi mỗi bảng. Bỏ qua document có `checksum` không đổi.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_scripts/test_ingest.py
from pathlib import Path

import pytest
from sqlalchemy import text

from scripts.ingest import ingest
from src.services.db import get_engine, run_migrations

SEED = Path("data/seed")


@pytest.mark.integration
def test_ingest_ghi_du_va_parent_id_tro_dung_provision_that():
    run_migrations()
    if not (SEED / "provisions.jsonl").exists():
        pytest.skip("chạy `python -m scripts.build_seed` trước")
    ingest(SEED)
    with get_engine().connect() as c:
        n_dieu = c.execute(text(
            "SELECT count(*) FROM provisions WHERE document_id='139264' AND cap='dieu'"
        )).scalar_one()
        orphan = c.execute(text(
            "SELECT count(*) FROM provisions p WHERE p.parent_id IS NOT NULL"
            " AND NOT EXISTS (SELECT 1 FROM provisions q WHERE q.id = p.parent_id)"
        )).scalar_one()
    assert n_dieu == 220, f"BLLĐ có {n_dieu} Điều, phải 220"
    assert orphan == 0, f"{orphan} provision có parent_id trỏ vào hư không"


@pytest.mark.integration
def test_ingest_lan_hai_khong_nhan_doi_du_lieu():
    run_migrations()
    if not (SEED / "provisions.jsonl").exists():
        pytest.skip("chạy build_seed trước")
    ingest(SEED)
    with get_engine().connect() as c:
        before = c.execute(text("SELECT count(*) FROM provisions")).scalar_one()
    ingest(SEED)
    with get_engine().connect() as c:
        after = c.execute(text("SELECT count(*) FROM provisions")).scalar_one()
    assert before == after, "ingest không idempotent — checksum không chặn được"


@pytest.mark.integration
def test_hai_van_ban_bay_hieu_luc_co_trong_db():
    run_migrations()
    if not (SEED / "documents.jsonl").exists():
        pytest.skip("chạy build_seed trước")
    ingest(SEED)
    with get_engine().connect() as c:
        rows = dict(c.execute(text(
            "SELECT id, tinh_trang FROM documents WHERE id IN ('168670','139094')"
        )).all())
    assert set(rows) == {"168670", "139094"}, "tập bẫy hiệu lực bị lọc mất"
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `pytest tests/test_scripts/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.ingest`

- [ ] **Step 3: Viết `scripts/ingest.py`**

```python
"""Load data/seed/*.jsonl vào Postgres. Idempotent qua documents.checksum."""

import json
from pathlib import Path

from sqlalchemy import text

from src.services.db import get_engine, run_migrations


def _read(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def ingest(seed: Path) -> dict[str, int]:
    run_migrations()
    docs = _read(seed / "documents.jsonl")
    provs = _read(seed / "provisions.jsonl")
    refs = _read(seed / "references.jsonl")
    written = {"documents": 0, "provisions": 0, "references": 0}

    eng = get_engine()
    with eng.begin() as conn:
        existing = dict(conn.execute(text("SELECT id, checksum FROM documents")).all())

        for d in docs:
            if existing.get(d["id"]) == d["checksum"]:
                continue  # không đổi → bỏ qua cả document lẫn provisions của nó

            conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": d["id"]})
            cols = ", ".join(d)
            binds = ", ".join(f":{k}" for k in d)
            conn.execute(text(f"INSERT INTO documents ({cols}) VALUES ({binds})"), d)
            written["documents"] += 1

            # provisions của document này, theo thứ tự để parent luôn có trước con
            mine = sorted((p for p in provs if p["document_id"] == d["id"]), key=lambda x: x["thu_tu"])
            local_to_db: dict[int, int] = {}
            for p in mine:
                parent_db = local_to_db.get(p["parent_local_id"]) if p["parent_local_id"] is not None else None
                new_id = conn.execute(text(
                    "INSERT INTO provisions"
                    " (document_id, parent_id, cap, so_hieu_cap, tieu_de, noi_dung,"
                    "  duong_dan, source_node_id, thu_tu)"
                    " VALUES (:document_id, :parent_id, :cap, :so_hieu_cap, :tieu_de, :noi_dung,"
                    "         :duong_dan, :source_node_id, :thu_tu) RETURNING id"
                ), {**{k: p[k] for k in
                       ("document_id", "cap", "so_hieu_cap", "tieu_de", "noi_dung",
                        "duong_dan", "source_node_id", "thu_tu")},
                    "parent_id": parent_db}).scalar_one()
                local_to_db[p["local_id"]] = new_id
                written["provisions"] += 1

            conn.execute(text('DELETE FROM "references" WHERE from_document_id = :id'), {"id": d["id"]})
            for r in (x for x in refs if x["from_document_id"] == d["id"]):
                conn.execute(text(
                    'INSERT INTO "references" (from_document_id, to_document_id, loai, raw_text)'
                    " VALUES (:from_document_id, :to_document_id, :loai, :raw_text)"), r)
                written["references"] += 1

    return written


if __name__ == "__main__":
    from src.config import get_settings

    print(ingest(Path(get_settings().data_seed_dir)))
```

- [ ] **Step 4: Chạy lại test**

```bash
python -m scripts.ingest
pytest tests/test_scripts/test_ingest.py -v
```
Expected: PASS (3 test)

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest.py tests/test_scripts/test_ingest.py
git commit -m "feat(ingest): load seed into Postgres, idempotent by document checksum

Provisions insert in thu_tu order so a parent always has a database id before its
children need it, and local_id maps to the real id as it goes. A test asserts zero
orphan parent_ids, because a broken tree would silently disable parent-document
retrieval and tier-1 verification alike. Another asserts the two effectivity trap
documents survive ingest - dropping expired documents is the easy mistake that
would leave the trap set empty."
```

---

## Task 10: Cổng A — Data Integrity Audit (CHẶN)

**Files:**
- Create: `scripts/gate_a_audit.py`
- Create: `docs/gate-a-report.md`

**Interfaces:**
- Consumes: `MojClient` (Task 6), Postgres đã ingest (Task 9)
- Produces: `scripts.gate_a_audit.audit(n: int = 30, seed: int = 42) -> dict` và `docs/gate-a-report.md`

**Tiêu chí pass — không pass thì DỪNG, không sang plan 2:**
- **`do_phu_min ≥ 0.98`** trên cả 6 Bộ luật — độ phủ token so với văn bản gốc **đã strip tag**, tức phép kiểm ĐỘC LẬP VỚI PARSER. Đây là tiêu chí bắt được bẫy #2 (`prov-content` không có `id`)
- **`rong_tong == 0`** — không Điều nào vừa rỗng nội dung vừa không có con
- Bảng NĐ 293/2025 giữ đúng hàng/cột (Step 3)

*Vì sao không so với `parse_provisions` chạy lại: cả hai đến từ cùng một parser, phép so đó là hằng đúng và chỉ bắt được lỗi ingest, không bắt được lỗi parser.*

- [ ] **Step 1: Viết script audit**

```python
"""Cổng A — Data Integrity Audit (spec 16.3).

Bắt lỗi parser mất nội dung ÂM THẦM — loại lỗi làm Recall@5 và citation
precision đều xấu mà không để lại dấu vết.

⚠ ĐIỂM THIẾT KẾ QUAN TRỌNG: KHÔNG được kiểm bằng cách chạy lại parse_provisions
rồi so với DB. Cả hai đến từ CÙNG một parser nên phép so đó là hằng đúng — nó
chỉ bắt được lỗi ingest/DB, KHÔNG bắt được lỗi parser.

Phép kiểm thật phải ĐỘC LẬP VỚI PARSER: strip toàn bộ tag khỏi HTML gốc để lấy
tập ký tự "sự thật", rồi đo xem nội dung trong DB phủ được bao nhiêu phần. Nếu
parser bỏ sót prov-content không có id (bẫy #2) thì độ phủ tụt ngay.
"""

import json
import random
import re
from pathlib import Path

from sqlalchemy import text

from bs4 import BeautifulSoup

from scripts.fetch_moj import DOC_IDS
from src.config import get_settings
from src.services.db import get_engine

BO_LUAT = ["95942", "96122", "96115", "96172", "139264", "96117"]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _van_ban_goc(html: str) -> str:
    """Sự thật ĐỘC LẬP VỚI PARSER: bỏ hết tag, chỉ giữ text.

    Bỏ <table> vì bảng được lưu riêng (bẫy #4), không nằm trong provisions.noi_dung
    theo đường prov-*.
    """
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all("table"):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with(" ")
    return _norm(soup.get_text(" "))


def audit(n: int = 30, seed: int = 42) -> dict:
    """Hai phép kiểm độc lập.

    A. ĐỘ PHỦ (độc lập với parser) — trên CẢ 6 Bộ luật, không lấy mẫu:
       ghép mọi tieu_de + noi_dung trong DB, đo xem phủ được bao nhiêu phần
       tập token của văn bản gốc đã strip tag. Đây là phép kiểm bắt được bẫy #2.
    B. RỖNG — Điều nào vừa không có nội dung vừa không có con.
    """
    random.seed(seed)
    raw = Path(get_settings().data_raw_dir) / "moj"
    per_doc: list[dict] = []
    chi_tiet: list[dict] = []
    rong_tong = 0

    with get_engine().connect() as conn:
        for doc_id in BO_LUAT:
            rows = conn.execute(text(
                "SELECT id, cap, so_hieu_cap, tieu_de, noi_dung,"
                " (SELECT count(*) FROM provisions c WHERE c.parent_id = p.id) AS so_con"
                " FROM provisions p WHERE document_id = :d"
            ), {"d": doc_id}).mappings().all()
            if not rows:
                chi_tiet.append({"doc_id": doc_id, "loi": "KHÔNG CÓ provision nào trong DB"})
                per_doc.append({"doc_id": doc_id, "do_phu": 0.0, "rong": 0})
                continue

            html = json.loads((raw / f"{doc_id}.json").read_text(encoding="utf-8"))
            goc_tokens = set(_van_ban_goc(html["documentContent"]["content"]).split())
            db_tokens = set(_norm(" ".join(
                f"{r['tieu_de']} {r['noi_dung']}" for r in rows)).split())

            do_phu = len(goc_tokens & db_tokens) / len(goc_tokens) if goc_tokens else 0.0
            thieu = sorted(goc_tokens - db_tokens)

            rong = [r for r in rows if r["cap"] == "dieu"
                    and not (r["noi_dung"] or "").strip() and r["so_con"] == 0]
            rong_tong += len(rong)
            for r in random.sample(rong, min(5, len(rong))):
                chi_tiet.append({"doc_id": doc_id, "dieu": r["so_hieu_cap"],
                                 "loi": "Điều RỖNG và không có con"})
            if do_phu < 0.98:
                chi_tiet.append({"doc_id": doc_id, "loi": f"độ phủ {do_phu:.2%}",
                                 "token_mat_mau": thieu[:25]})

            per_doc.append({"doc_id": doc_id, "do_phu": round(do_phu, 4),
                            "rong": len(rong), "provisions": len(rows)})

    do_phu_min = min((d["do_phu"] for d in per_doc), default=0.0)
    return {"per_doc": per_doc, "do_phu_min": do_phu_min, "rong_tong": rong_tong,
            "pass": rong_tong == 0 and do_phu_min >= 0.98,
            "chi_tiet": chi_tiet}


if __name__ == "__main__":
    r = audit()
    print(json.dumps({k: v for k, v in r.items() if k != "chi_tiet"}, ensure_ascii=False, indent=2))
    for c in r["chi_tiet"][:40]:
        print(" -", c)
    raise SystemExit(0 if r["pass"] else 1)
```

- [ ] **Step 2: Chạy Cổng A**

```bash
python -m scripts.gate_a_audit
echo "exit=$?"
```
Expected: `pass: true`, `exit=0`. **Nếu `exit=1`: DỪNG, sửa parser, chạy lại. Không sang plan 2.**

- [ ] **Step 3: Kiểm bảng lương tối thiểu giữ hàng/cột**

```bash
python3 -c "
from sqlalchemy import text
from src.services.db import get_engine
with get_engine().connect() as c:
    r=c.execute(text(\"SELECT noi_dung FROM provisions WHERE document_id='183939' AND tieu_de='[BẢNG]'\")).scalar()
print(r[:400] if r else 'KHÔNG CÓ BẢNG — bẫy #4 chưa xử lý')
assert r and 'Vùng I' in r and '5.310.000' in r
"
```

- [ ] **Step 4: Ghi báo cáo Cổng A**

```bash
python3 - <<'PY'
import json
from scripts.gate_a_audit import audit

r = audit()
lines = ["# Cổng A — Data Integrity Audit", "",
         "Phép kiểm ĐỘC LẬP VỚI PARSER: độ phủ token so với văn bản gốc đã strip tag.", "",
         "| Bộ luật | provisions | độ phủ | Điều rỗng |", "|---|---|---|---|"]
for d in r["per_doc"]:
    lines.append(f"| {d['doc_id']} | {d.get('provisions', 0)} | {d['do_phu']:.2%} | {d['rong']} |")
lines += ["", f"- Độ phủ thấp nhất: **{r['do_phu_min']:.2%}** (ngưỡng 98%)",
          f"- Tổng Điều rỗng: **{r['rong_tong']}** (ngưỡng 0)",
          f"- **Kết quả: {'PASS' if r['pass'] else 'FAIL'}**", "", "## Chi tiết", ""]
lines += [f"- {c}" for c in r["chi_tiet"]] or ["(không có)"]
open("docs/gate-a-report.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("đã ghi docs/gate-a-report.md")
PY
```

- [ ] **Step 5: Commit**

```bash
git add scripts/gate_a_audit.py docs/gate-a-report.md
git commit -m "feat(gate-a): blocking data integrity audit before retrieval work

Independently re-parses sampled articles from the original MOJ HTML and compares
character by character against what ingest wrote. This gate exists because silent
content loss depresses both Recall@5 and citation precision while presenting as a
mechanism failure - the class of defect that would invalidate the results chapter
without leaving a trace. Exits non-zero on failure so it cannot be waved past."
```

---

## KHÔNG thuộc plan này — ghi ra để không mất

Hai hạng mục của spec **cố ý hoãn**, không phải bỏ sót:

| Hoãn | Thuộc plan | Vì |
|---|---|---|
| **Resolve dẫn chiếu chéo cấp điều khoản** (spec 4.6): regex bắt `(khoản \d+ )?Điều \d+( của ... này)?` → resolve thành `provision_id` → ghi `references.from_provision_id`/`to_provision_id` | **Plan 2** | Nó chỉ có người tiêu thụ ở `expand` (`EXPAND_REFERENCE_HOPS`). Làm trước thì không có test end-to-end nào chứng minh nó đúng. Plan này chỉ ghi cạnh **cấp văn bản** từ `references[]` của API |
| **Load `relationships.parquet`** (1.033.255 cạnh) để có cạnh **ĐI VÀO** cho cơ chế hiệu lực Mức 2 | **Plan 3** | Phụ thuộc Phase 0 #4: nếu `/doc/{id}/related` trả cạnh đi vào thì **bỏ hẳn được file này**. Tải rồi ở Task 5, chưa load |

Cả hai đã có chỗ chứa trong schema Task 3 (`references.from_provision_id`, `to_provision_id`, `to_document_id`) nên không cần migration mới.

## Sau plan này

**Điều kiện sang plan 2:** Cổng A `pass: true` · `docs/phase0-findings.md` đã trả lời #4 và #6 · BLLĐ đúng 220 Điều trong Postgres.

**Plan 2/5** — Retrieval & eval harness (tuần 3–4): chunking, embedding qua OpenRouter, BM25 + dense + RRF, `golden_qa` 90 câu Lao động, eval harness một lệnh, bảng so sánh 6 embedding.
**Plan 3/5** — Verifier & graph tra cứu (tuần 5–6). **Plan 4/5** — Soạn thảo & tự soát + FE + deploy (tuần 7–8). **Plan 5/5** — Ablation, Cổng B, khóa luận (tuần 9–12).

Mỗi plan viết **sau khi** plan trước xong, để hấp thu kết quả thật thay vì viết nhánh giả định.
