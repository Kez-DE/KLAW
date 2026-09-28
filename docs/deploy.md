# Triển khai production (Railway) và CI/CD

Cập nhật 2026-09-10. Mọi thứ dưới đây đã chạy thật trên project Railway `klaw`
(workspace của chủ dự án). Tên miền do Railway cấp; đổi sang tên miền riêng bằng
`railway domain` hoặc trong dashboard, rồi cập nhật ba biến chéo ở mục 3.

## 1. Kiến trúc

| Service | Nguồn build | Cổng / start | Tên miền |
|---|---|---|---|
| `klaw-api` | `Dockerfile` ở gốc repo (Python 3.11, uvicorn) | 8000, `railway.json` healthcheck `/health` | `klaw-api-production-fbd1.up.railway.app` |
| `klaw-web` | Railpack, root directory `/frontend` | `npm start` → `node .output/server/index.mjs` (nitro `node-server`, đọc `PORT`) | `klaw-web-production.up.railway.app` |
| `klaw-cms` | Railpack, root directory `/cms` (pnpm) | `pnpm start` → `scripts/start.sh` (migrate, kiểm `migrate:status`, `next start`) | `klaw-cms-production.up.railway.app` |
| `pgvector` | template Railway `pgvector` (mã `3jJFCA`, image `pgvector/pgvector:pg18`, volume 5 GB) | 5432 nội bộ + TCP proxy công khai | — |

Một Postgres, hai database: `railway` (mặc định của template) cho API, `klaw_cms`
cho CMS (tạo tay một lần: `CREATE DATABASE klaw_cms`). Supabase chỉ dùng cho Auth
(JWT), như local.

Mỗi service nối thẳng repo GitHub `Kez-DE/KLAW`, nhánh `main`: **push lên `main` là
deploy**. GitHub Actions (`.github/workflows/ci.yml`) chỉ chạy test (backend có
Postgres pgvector + migration; CMS có Postgres; frontend chạy `npm run kiem`).
Railway KHÔNG chờ CI xanh (`checkSuites: false`); nếu muốn chặn deploy khi CI đỏ,
bật "Wait for CI" trong Settings của từng service.

## 2. Vì sao có những file này

- `railway.json` (gốc, `frontend/`, `cms/`): builder + start + healthcheck. Railway
  báo Config-as-Code sẽ ngừng hỗ trợ sau 2026-12-01 (chuyển sang
  `.railway/railway.ts`, `railway config migrate`). Vẫn chạy tới lúc đó.
- `Dockerfile`: cài gói bằng `pip --user` ở stage build rồi chép vào
  `/home/appuser/.local` (KHÔNG phải `/root/.local` — thư mục đó 0700, container
  chết với "exec uvicorn: Permission denied" ngay lần deploy đầu).
- `.dockerignore`: loại `frontend/`, `cms/`, `node_modules/`, `data/raw/` khỏi image
  API. `data/seed/` (21 MB, có trong git) vẫn vào image để `scripts.ingest` chạy được
  trong container khi cần.
- `frontend/package.json`: thêm `start` và `engines.node >= 22` cho Railpack.

## 3. Biến môi trường

Tham chiếu Railway (`${{service.VAR}}`) để không chép mật khẩu. Template pgvector
phát `DATABASE_URL` dạng `postgres://…` — SQLAlchemy chỉ nhận `postgresql://`, nên
API ghép URL từ các phần thay vì dùng thẳng.

`klaw-api` (controller đặt): `APP_ENV=production`, `LOG_LEVEL=info`,
`KLAW_API_KEY=` (rỗng: frontend không gửi X-API-Key; bảo vệ bằng Supabase JWT + rate
limit), `KLAW_TIN_PROXY_HEADER=1`, `KLAW_SO_HOP_PROXY_TIN_CAY=1` (một proxy Railway
đứng trước), `CORS_ORIGINS=https://${{klaw-web.RAILWAY_PUBLIC_DOMAIN}},https://${{klaw-cms.RAILWAY_PUBLIC_DOMAIN}}`,
`DATABASE_URL=postgresql://${{pgvector.PGUSER}}:${{pgvector.PGPASSWORD}}@${{pgvector.PGHOST_PRIVATE}}:${{pgvector.PGPORT_PRIVATE}}/${{pgvector.PGDATABASE}}`.
Chủ dự án đặt (bí mật, từ `.env.local`): `OPENROUTER_API_KEY`, `OPENROUTER_*` (model
names, dim, rerank), `KLAW_SUPABASE_URL`, `KLAW_SUPABASE_JWT_AUD`,
`KLAW_ADMIN_API_KEY` (64 hex, PHẢI trùng với CMS), `KLAW_TRAN_CHI_PHI_NGAY_USD`.
Thiếu `KLAW_SUPABASE_URL` thì `APP_ENV=production` từ chối khởi động (main.py).

`klaw-web`: `NODE_ENV=production`, `VITE_API_GOC=https://${{klaw-api.RAILWAY_PUBLIC_DOMAIN}}/api/v1`,
`VITE_SITE_ORIGIN=https://${{RAILWAY_PUBLIC_DOMAIN}}`; chủ dự án đặt
`VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (từ `frontend/.env.local`).
`VITE_*` nướng vào bundle lúc build → đổi giá trị là phải deploy lại.

`klaw-cms`: `NODE_ENV=production`, `KLAW_API_URL=https://${{klaw-api.RAILWAY_PUBLIC_DOMAIN}}/api/v1`,
`PAYLOAD_PUBLIC_SERVER_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}`,
`DATABASE_URI=postgresql://${{pgvector.PGUSER}}:${{pgvector.PGPASSWORD}}@${{pgvector.PGHOST_PRIVATE}}:${{pgvector.PGPORT_PRIVATE}}/klaw_cms`;
chủ dự án đặt `PAYLOAD_SECRET` (mới, `openssl rand -hex 32`) và `KLAW_ADMIN_API_KEY`.

Lệnh đặt bí mật không để giá trị lọt ra terminal (chạy ở gốc repo, CLI đã
`railway link` vào project `klaw`):

```sh
args=(); for k in OPENROUTER_API_KEY OPENROUTER_BASE_URL OPENROUTER_MODEL_NAME \
  OPENROUTER_GENERATE_MODEL_NAME OPENROUTER_JUDGE_MODEL_NAME OPENROUTER_EMBEDDING_MODEL_NAME \
  OPENROUTER_EMBEDDING_DIM OPENROUTER_RERANK_MODEL_NAME OPENROUTER_RERANK_ENABLED \
  KLAW_SUPABASE_URL KLAW_SUPABASE_JWT_AUD KLAW_ADMIN_API_KEY KLAW_TRAN_CHI_PHI_NGAY_USD; do
  v=$(grep -E "^$k=" .env.local | head -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//' | tr -d "\"'"); [ -n "$v" ] && args+=(--set "$k=$v"); done
railway variables -s klaw-api "${args[@]}" >/dev/null

args=(); for k in VITE_SUPABASE_URL VITE_SUPABASE_PUBLISHABLE_KEY; do
  v=$(grep -E "^$k=" frontend/.env.local | head -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//' | tr -d "\"'"); [ -n "$v" ] && args+=(--set "$k=$v"); done
railway variables -s klaw-web "${args[@]}" >/dev/null

k=$(grep -E "^KLAW_ADMIN_API_KEY=" .env.local | head -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//' | tr -d "\"'")
railway variables -s klaw-cms --set "PAYLOAD_SECRET=$(openssl rand -hex 32)" --set "KLAW_ADMIN_API_KEY=$k" >/dev/null
```

Supabase → Authentication → URL Configuration: thêm `https://klaw-web-production.up.railway.app`
(và `/**`) vào Site URL / Redirect URLs, nếu không đăng nhập sẽ quay về localhost.

## 4. Database: migration và dữ liệu

- Lần đầu (DB rỗng): chạy TẤT CẢ migration một lần từ máy, qua URL công khai của
  template (đổi scheme):
  `railway run -s pgvector -- sh -c 'export DATABASE_URL="$(printf %s "$DATABASE_URL" | sed "s#^postgres://#postgresql://#")"; KLAW_SUPABASE_URL= .venv/bin/python -c "from src.services.db import run_migrations; print(run_migrations())"'`
  (26 file, có `000_extensions.sql` tạo `vector` + `unaccent`). Các migration-cổng
  (RAISE khi corpus vi phạm bất biến) đi qua vì bảng còn rỗng — KHÔNG chạy lại toàn
  bộ trên DB đã có dữ liệu.
- Sau đó: API tự áp `MIGRATIONS_KHOI_DONG` (019+) lúc khởi động; migration mới thêm
  vào tuple đó trong `src/main.py` (test guard bắt buộc).
- Kho luật: sao chép từ DB local (đã có embedding, không tốn OpenRouter):
  `docker exec klaw-db-1 pg_dump -U klaw -d klaw --data-only --no-owner --no-privileges -t documents -t provisions -t '"references"' -t chunks -t sua_doi_dieu_khoan > corpus.sql`
  rồi `railway run -s pgvector -- sh -c 'psql "$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction -q -f corpus.sql'`
  (240 MB, vài phút). Không chép các bảng người dùng/runtime (`hoi_thoai`,
  `ban_thao`, `traces`, `users`, `answer_cache`, `verified_*`, …). Xem mục 6 cho
  bẫy trigger tsvector khi COPY.
- Cách 2 (không có DB local): `railway ssh -s klaw-api -- python -m scripts.ingest`
  rồi `python -m scripts.build_chunks` (embedding qua OpenRouter, tốn tiền thật) và
  `scripts.nap_link_cong_luat`; `nap_linh_vuc`, `nap_nguoi_ky`, `nap_co_quan_tang_nong`,
  `load_incoming_edges` cần `data/raw/` nên chạy từ máy có raw qua `railway run`.
- CMS: `scripts/start.sh` tự `payload migrate` và từ chối start nếu còn migration
  pending.

## 5. Kiểm chứng lần deploy đầu (2026-09-10)

- `GET /health` → `{"status":"ok"}`; `GET /api/v1/mau/don_xin_nghi_viec` → 200 (8 mục);
  `GET /api/v1/tim-kiem?q=…` → 200, 20 kết quả từ kho thật.
- `POST /api/v1/tra-cuu` với header khách `X-Khach-Id` (UUID; người chưa đăng nhập có 10
  lượt/24 giờ; không header → 401 "Cần đăng nhập"): 200 sau ~14 giây, `result_type=answer`,
  4 trích dẫn đã kiểm (45/2019/QH14 Điều 35 Khoản 1; 145/2020/NĐ-CP Điều 7), có `trace_id`.
- Kho luật production sau restore: 1.634 văn bản, 43.720 điều khoản, 14.770 chunk, 7.419
  quan hệ, 4 bản đồ sửa đổi.
- `klaw-api` chỉ tự build lại khi đổi `src/ migrations/ prompts/ config/ scripts/ data/seed/
  requirements.txt Dockerfile .dockerignore railway.json` (watch patterns); `klaw-web` và
  `klaw-cms` chỉ theo thư mục gốc của mình. Đổi docs không tốn build.

## 6. Vận hành

- Xem: `railway status`, `railway logs -s klaw-api`, dashboard project `klaw`.
- Rollback: Deployments → Redeploy bản trước, hoặc `git revert` rồi push `main`.
- Đổi biến `VITE_*` hay `KLAW_API_URL` → cần deploy lại service tương ứng (Railway tự
  làm khi đổi biến, trừ khi đặt với `--skip-deploys`).
- Chi phí đáng chú ý: mỗi push `main` build lại cả ba service; RAM Railway ~10
  USD/GB/tháng; embedding chỉ tốn khi chạy `build_chunks`.
- Làm mới hiệu lực + link vbpl.vn (chạy tay, không theo lịch — quyết định
  2026-09-28 mục 6), trên DB local rồi đưa lên bằng đường dump/restore ở mục 4:
  `.venv/bin/python -m scripts.lam_moi_hieu_luc --dry-run` (xem thay đổi), rồi bỏ
  `--dry-run` để ghi `documents` + `data/seed/link_vbpl_da_kiem.yaml` (commit seed).
  `--chi-deep`: chỉ tầng sâu (~3 phút). Cả kho ~1 giờ (gateway ≤1 request/1,5 giây,
  vbpl.vn ≤1 request/giây, chạy song song; đo 2026-09-28 với 1.658 văn bản). Response
  giữ ở `data/raw/lam_moi/<ngày>/` (hoặc `--cache DIR`): ngắt giữa chừng thì chạy lại
  cùng lệnh, id đã có không tải lại; `--tu-id ID` bỏ qua các id trước. Văn bản
  gateway trả lỗi được liệt kê, dòng DB giữ nguyên (không đoán), lần chạy sau thử lại.

## 7. Bẫy đã gặp ngày 2026-09-10

- Template pgvector: biến là `DATABASE_URL` (công khai), `DATABASE_URL_PRIVATE`,
  `PGHOST_PRIVATE`, `PGPORT_PRIVATE` — không phải `RAILWAY_PRIVATE_DOMAIN` như
  template Postgres chuẩn; scheme `postgres://` phải đổi cho SQLAlchemy.
- `railway up` từ thư mục con vẫn deploy từ gốc repo; đặt root directory cho service.
- macOS không có `timeout`; dùng `timeout` của Bash tool hoặc `gtimeout`.
- Dòng `.env` có ghi chú đuôi (`KEY=value   # …`) sẽ chép nguyên ghi chú vào Railway nếu chỉ `cut`;
  `OPENROUTER_JUDGE_MODEL_NAME` đã vấp vậy (OpenRouter trả 400 ở tầng judge). Lệnh ở mục 3 đã cắt
  phần `# …` bằng `sed`.
- `LOG_LEVEL` phải viết in (`INFO`); `Settings` là `Literal['DEBUG','INFO','WARNING','ERROR']`,
  đặt `info` là API từ chối khởi động (ValidationError) — đã vấp lần deploy thứ hai.
- `pg_dump --data-only` mở đầu bằng `set_config('search_path', '', false)`; trigger
  `chunks_tsv_trigger` gọi `klaw_tsv(...)` không có tiền tố schema nên COPY vào `chunks`
  chết với "function klaw_tsv(text) does not exist". Đổi dòng đó thành
  `'public'` (hoặc `sed` như runbook) trước khi `psql -f`.
