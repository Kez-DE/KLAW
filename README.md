 Thay vì bắt đầu từ con số không, template này cung cấp:

- **Cấu trúc thư mục chuẩn** — đã được thiết kế theo best practices (separation of concerns)
- **Code mẫu** cho các phần cốt lõi: LangGraph agent, FastAPI API, config, schemas
- **Docker + CI/CD sẵn** — Dockerfile multi-stage, GitHub Actions workflow
- **Hướng dẫn kỹ thuật 10 chương** — từ clone template đến nộp bài Demo Day
- **Checklist 10 deliverables** — đảm bảo không bỏ sót yêu cầu BTC
- **AI Usage Logging tự động** — Pre-configured hooks cho Claude Code, Cursor, Codex, Gemini CLI, Antigravity, và GitHub Copilot

## ⚡ Quick Start

### Bước 1: Fork hoặc Clone

# Xóa git history cũ và khởi tạo lại
rm -rf .git
git init
git add .
git commit -m "feat: khởi tạo dự án từ template"
```

### Bước 2: Setup môi trường

```bash
# Tạo virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Cài dependencies
pip install -e ".[dev]"

# Cấu hình API keys
cp .env.example .env
# Mở .env và thêm OPENAI_API_KEY của bạn
# Đồng thời cập nhật AI_LOG_API_KEY bằng key riêng từ link mời của BTC
# (giá trị trong .env.example chỉ là placeholder)
```

### Bước 3: Cài AI Logging Hooks

```bash
# Linux / macOS / Git Bash
bash scripts/setup_hooks.sh

# Windows PowerShell
# powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```

Hooks tự động log mọi AI prompt khi dùng Claude Code, Cursor, Codex, Gemini CLI, Antigravity, hoặc GitHub Copilot. Không cần thao tác thủ công.

### Bước 4: Chạy server

```bash
# Chạy FastAPI backend
uvicorn src.main:app --reload --port 8000

# Mở Swagger UI
# http://localhost:8000/docs
```

### Bước 5: Đọc hướng dẫn


## 🔒 Cổng bảo vệ trước khi mở công khai

`/tra-cuu` gọi LLM **tối đa 5 lần** mỗi request (p50 10s, p95 50s, tới
**$0,00735**); `/soan-thao` thêm một lượt. Đo trên chính DB của dự án: ngày cao
nhất tới nay 118 request / **$0,18329**. Dự án đã gặp HTTP 429 từ OpenRouter khi
nhiều tiến trình chạy song song. Các biến dưới đây (chú thích đầy đủ trong
`.env.example`) là cái chặn một vòng `curl` rút cạn key trong một buổi.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `KLAW_API_KEY` | rỗng = **MỞ** | Có giá trị ⇒ bắt buộc header `X-API-Key` khớp trên `/tra-cuu` và `/soan-thao`. `/pham-vi`, `/van-ban`, `/mau`, `/soat`, `/health` không cần. |
| `KLAW_TRAN_CHI_PHI_NGAY_USD` | `2.0` | Trần chi phí/ngày (mốc UTC), cộng từ `traces.cost_usd`. Vượt ⇒ HTTP 429 nêu rõ lý do và mốc mở lại. `0` = tắt. |
| `KLAW_RATE_LIMIT_SO_LUOT` / `_CUA_SO_GIAY` | `10` / `60` | Rate limit theo IP, cửa sổ trượt, bộ đếm trong Postgres. `0` lượt = tắt. |
| `KLAW_TIN_PROXY_HEADER` | `false` | Chỉ bật khi **thật sự** có reverse proxy đặt `X-Forwarded-For`. Bật mà không có proxy ⇒ ai cũng giả được IP. |
| `KLAW_CACHE_TTL_NGAY` | `7` | Cache câu trả lời trong bảng `answer_cache`. `0` = tắt — **bắt buộc tắt khi chạy eval**, nếu không số liệu đo được là số của cache. |

**Trước khi deploy công khai, tối thiểu:** đặt `KLAW_API_KEY` bằng một giá trị
ngẫu nhiên (`openssl rand -hex 32`), chốt `CORS_ORIGINS` về domain thật, bỏ port
mapping `5432` khỏi `docker-compose.yml`, và đổi `POSTGRES_PASSWORD`. Danh sách
còn lại: `.superpowers/sdd/2026-08-27-klaw-04-drafting-fe-deploy/hardening-report.md`.

Cache chỉ giữ `answer` và `partial_coverage`. **`abstain` không vào cache**: một
lần thiếu căn cứ do lỗi tạm (OpenRouter 429, DB chậm) mà bị cache 7 ngày sẽ hoá
đá thành "không tìm thấy căn cứ" — `abstain` là hành vi đúng và được tính điểm,
không phải thứ được phép đóng băng. Khoá cache gồm câu hỏi đã chuẩn hoá,
`config_name`, `as_of_date` **đã giải quyết**, và một checksum corpus (suy từ
`count(*)` của `provisions` + `max(crawled_at)` của `documents`) — nên seed lại
corpus là cache tự hết hiệu lực, không cần ai nhớ xoá tay.

## 📁 Cấu trúc dự án

```
├── src/
│   ├── agents/           # 🧠 LangGraph Agent
│   │   ├── graph.py      #    State graph (nodes + edges)
│   │   ├── state.py      #    State schema (TypedDict)
│   │   ├── nodes/        #    Node functions
│   │   └── tools/        #    Agent tools (@tool)
│   ├── api/              # 🌐 FastAPI Backend
│   │   └── routes.py     #    API endpoints
│   ├── models/           # 📋 Pydantic schemas
│   ├── services/         # 🔧 Business logic (LLM, etc.)
│   ├── config.py         # ⚙️ Pydantic Settings
│   └── main.py           # 🚀 App entry point
├── tests/                # 🧪 pytest suite
│   ├── test_agents/      #    Agent/graph tests
│   └── test_api/         #    API endpoint tests
├── scripts/              # 🔌 AI Logging Hooks
│   ├── log_hook.py       #    Auto-log cho Claude/Cursor/Codex/Gemini/Copilot
│   ├── log_antigravity.py#    Antigravity IDE prompt scanner
│   ├── log_manual.py     #    Manual log cho ChatGPT / web tools
│   ├── submit_log.py     #    Submit logs on git push
│   └── setup_hooks.sh    #    One-time hook installer
├── .claude/ .codex/ .cursor/ .gemini/  # Per-tool hook configs
├── .agents/              # Antigravity rules + workflows
├── .ai-log/              # 📊 AI usage logs (auto-generated)
├── docs/
│   ├── guide/            # 📖 Technical Guidebook (10 chapters)
│   └── architecture_diagram.md
├── eval/                 # 📊 Evaluation results
├── presentation/         # 🎤 Demo Day slides
├── .github/workflows/    # ⚡ CI/CD (GitHub Actions)
├── .github/hooks/        # 🪝 Copilot hook config
├── Dockerfile            # 🐳 Multi-stage build
├── docker-compose.yml    # 🐙 Full stack orchestration
└── README_boilerplate.md # 📝 README template cho đội của bạn
```

## 📚 Technical Guidebook — 10 Chương

| Chương | Nội dung | Thời gian |
|---------|----------|-----------|
| 1 | Lời mở đầu — Mục tiêu, cách sử dụng | 15 phút |
| 2 | Khởi tạo dự án — Clone, setup, git workflow | 4 giờ |
| 3 | Thiết kế kiến trúc — 3-tier, diagrams, ADR | 6 giờ |
| 4 | **LangGraph Agent** — State, nodes, edges, tools, RAG | 8 giờ |
| 5 | FastAPI — Routes, validation, error handling, streaming | 6 giờ |
| 6 | Giao diện — Next.js + Streamlit quickstart | 6 giờ |
| 7 | DevOps — Docker, CI/CD, deploy, logging | 6 giờ |
| 8 | Kiểm thử — Unit test, integration test, RAGAS | 4 giờ |
| 9 | Demo Day — 10 deliverables, checklist, tips | 2 giờ |
| 10 | Tài nguyên — Khóa học, docs, BMAD method | tham khảo |

📖 **Đọc online:** [phoenix.note.transformerlabs.ai/technical-book](https://phoenix.note.transformerlabs.ai/technical-book)

## 📋 10 Deliverables cho Demo Day

| # | Deliverable | File vị trí | Template có sẵn |
|---|-------------|-------------|:---:|
| 1 | Source Code | `src/` | ✅ |
| 2 | README.md | `README_boilerplate.md` → copy thành `README.md` | ✅ |
| 3 | Architecture Diagram | `docs/architecture_diagram.md` | ✅ |
| 4 | AI Logs | LangSmith (3 env vars) + Auto AI Usage Logging | ✅ |
| 5 | Live URL | Deploy lên Render/Vercel | ⚡ CI/CD sẵn |
| 6 | Video Demo | `presentation/` | 📝 |
| 7 | Pitch Deck | `presentation/` | 📝 |
| 8 | Development Journal | `JOURNAL.md` | ✅ |
| 9 | Worklog | `WORKLOG.md` | ✅ |
| 10 | Evaluation Evidence | `eval/` | 📝 |

## 🛠 Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| AI Agent | LangGraph + LangChain | Latest |
| Backend | FastAPI + Uvicorn | 0.100+ |
| LLM | OpenAI GPT-4o-mini | API |
| Frontend | Next.js / Streamlit | 14+ / 1.30+ |
| Database | SQLite (dev) / PostgreSQL (prod) | — |
| DevOps | Docker + GitHub Actions | — |
| Testing | pytest + pytest-asyncio | 8+ |

## 📊 AI Usage Logging

Template đã tích hợp sẵn auto-logging hooks cho 6 AI tools:

| Tool | Cơ chế | Config |
|------|--------|--------|
| Claude Code | `.claude/settings.json` hooks | Tự động |
| Cursor | `.cursor/hooks.json` | Tự động |
| OpenAI Codex CLI | `.codex/hooks.json` | Tự động |
| Gemini CLI | `.gemini/settings.json` | Tự động |
| GitHub Copilot | `.github/hooks/hooks.json` | Tự động |
| Antigravity IDE | Pre-push scan transcript | Tự động trên `git push` |

Tất cả prompts và tool calls được log vào `.ai-log/session.jsonl` và tự động submit lên grading server mỗi khi `git push`.

**ChatGPT / web tools khác** — log thủ công:
```bash
bash scripts/_pyrun.sh scripts/log_manual.py --tool chatgpt --prompt "What you asked"
```

> ⚠️ Chạy `bash scripts/setup_hooks.sh` một lần sau khi clone để cài pre-push hook.


## 📄 License

MIT — Sử dụng tự do cho mục đích giáo dục.
