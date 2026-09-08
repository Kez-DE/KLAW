# KLAW CMS

Trang quản trị Payload 3.88 độc lập cho tài khoản KLAW: mã riêng (`cms/`), tiến trình
riêng (cổng 3001), database riêng (`klaw_cms`), đăng nhập riêng bằng auth sẵn có của
Payload. Mọi thao tác dữ liệu người dùng đi qua proxy `/api/klaw/*` tới KLAW — CMS không
sở hữu bảng tài khoản.

Ba gốc quản lý gói khác nhau trong cùng kho: `frontend/` dùng npm, `cms/` dùng pnpm,
gốc dự án (Python/KLAW) dùng pip. Không trộn trình quản lý gói giữa ba gốc.

## Cài đặt local

```bash
createdb -h localhost -U klaw klaw_cms              # một lần, role `klaw` (cùng container klaw-db-1)
createdb -h localhost -U klaw klaw_cms_test         # cho `pnpm test` — xem bảng biến DATABASE_URI
cd cms && pnpm install && cp .env.example .env      # điền năm biến — xem bảng dưới
pnpm dev                                            # next dev -p 3001, push schema ở dev
# KLAW: thêm KLAW_ADMIN_API_KEY vào .env.local, khởi động lại uvicorn
```

Mở `http://localhost:3001/admin` → `create-first-user` → tài khoản đầu tiên luôn là
`quan_tri` (collection `admins` rỗng ép vai trò này).

Biến môi trường (`.env.example`):

| Biến | Ý nghĩa |
|---|---|
| `DATABASE_URI` | Kết nối Postgres tới database `klaw_cms` (riêng với `klaw`). |
| `PAYLOAD_SECRET` | Khoá ký phiên Payload — sinh bằng `openssl rand -hex 32`. |
| `PAYLOAD_PUBLIC_SERVER_URL` | Gốc công khai; để trống ở local. **Bắt buộc ở production** (hoặc `RAILWAY_PUBLIC_DOMAIN`) — thiếu cả hai thì allowlist CSRF rỗng, chấp nhận mọi Origin; `scripts/start.sh` từ chối khởi động trong trường hợp đó. |
| `KLAW_API_URL` | Gốc API quản trị của KLAW (`/admin/*`). |
| `KLAW_ADMIN_API_KEY` | Khoá gọi KLAW — phải cùng giá trị với `.env.local` của KLAW. |

Khi đổi một collection (`Admins`, `NhatKyCms`), chạy `pnpm migrate:create <tên>` để sinh
migration trước khi commit — dev dùng push schema tự động nhưng production chạy migration
thật (xem `scripts/start.sh`).

## Railway (đích, khi KLAW được deploy)

- Service `klaw-cms`, Root Directory `cms`, builder Railpack, start `pnpm start`
  (= `bash scripts/start.sh`: chạy migration, xác minh đã áp hết, rồi mới `next start`).
  Healthcheck `/api/admins/me` trả 200 với `user: null` là sống (Payload không trả 401 ở
  `me`).
- Database: cùng service Postgres với KLAW; tạo `klaw_cms` một lần qua `railway connect`.
  `DATABASE_URI` là variable reference tới service Postgres, đổi tên database.
- `KLAW_API_URL` dùng private networking
  (`http://klaw-api.railway.internal:8000/api/v1`); đặt `KLAW_TIN_PROXY_HEADER=true` và
  `KLAW_SO_HOP_PROXY_TIN_CAY=1` ở KLAW — CMS luôn chuyển tiếp đúng một giá trị
  `X-Forwarded-For` (IP admin, xem `ipCua` trong `src/hooks/nhatKyCms.ts`), không phải
  chuỗi hop gốc, nên số hop tin cậy phải là 1 để IP admin được ghi đúng trong nhật ký.
- RAM: Payload + Next ước 512 MB – 1 GB — đây là chi phí định kỳ thật, không phải miễn phí.

## CI

Job `cms` trong `.github/workflows/ci.yml` chạy trên mọi push/PR (không lọc theo đường
dẫn thay đổi — chi phí khoảng 3 phút CI mỗi lần, chấp nhận đổi lấy việc không phải gắn
action bên thứ ba để lọc riêng job): service container Postgres 16, `pnpm install
--frozen-lockfile`, `pnpm lint`, `pnpm type-check`, `pnpm build`, `pnpm test` (theo đúng
thứ tự này — `pnpm build` phải chạy trước `pnpm test` để bài kiểm tra bí mật bundle có
`.next/static` để đọc). Không đụng job Python, không cài hook git, không đổi branch
protection. Chạy cục bộ cũng theo đúng thứ tự này: thiếu `.next/static`,
`tests/bundle.spec.ts` báo lỗi thay vì bỏ qua.

## Lưu trữ nhật ký

KLAW giữ hai bảng nhật ký — `nhat_ky_quan_tri` (bản pháp lý, mọi thao tác admin) và
`nhat_ky_cms` (đăng nhập/đăng nhập sai phía CMS) — **vô thời hạn**, không có job dọn tự
động. Bản sao duy nhất admin có thể giữ là CSV tự xuất từ màn hình Nhật ký, trần 5.000
dòng mỗi lần theo bộ lọc đang chọn; khuyến nghị xuất một lần mỗi tháng để có bằng chứng
ngoài database. Stream nhật ký ra kho lưu trữ ngoài (S3, BigQuery…) nằm ngoài phạm vi
gói này.
