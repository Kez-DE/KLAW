# Gói 2B-2 — CMS Payload quản trị tài khoản

Ngày: 2026-09-08 · Trạng thái: chờ chủ dự án duyệt

Gói này dựng giao diện quản trị: một ứng dụng Payload CMS riêng, đăng nhập
riêng, dùng chung một database với KLAW nhưng ở schema tách biệt. Nó tiêu thụ
đường quản trị mà gói 2B-1 dựng. **Phải làm 2B-1 trước**, vì không có API thì
CMS không có gì để hiển thị.

Spec đi kèm: `docs/superpowers/specs/2026-09-08-quan-tri-tai-khoan-klaw-design.md`.

## 1. Mục tiêu

- Một trang quản trị tách biệt hoàn toàn với ứng dụng KLAW, có đăng nhập riêng.
- Duyệt hoặc từ chối yêu cầu nâng gói; tìm và xem một tài khoản; đặt gói tay.
- Chuông thông báo có badge, cập nhật sống, theo cơ chế đã dùng ở dự án
  `vsf-cms-multiple-sites-backend`.
- Không bao giờ ghi thẳng vào bảng của KLAW.

## 2. Hiện trạng và nguồn tham khảo

Dự án `vsf-cms-multiple-sites-backend` của chính chủ dự án đã có sẵn cơ chế cần
chuyển sang:

- `src/payload/collections/Notifications.ts` — collection với `recipient`,
  `actor`, `type`, `titleSnapshot`, `message`, `link`, `groupKey`, `isRead`,
  `isStale`.
- `src/payload/notifications/notify.ts` — hàm `notify()` và `groupKeyFor()`.
- `src/payload/endpoints/notificationStream.ts` — SSE với nhịp tim
  `setInterval`; chú thích trong mã nói rõ SSE là "tối ưu hoá trên nền polling,
  không phải nguồn sự thật".
- `src/payload/components/NotificationBell/` — `index.tsx`, `bell.ts`,
  `index.scss`; badge, `EventSource` tự nối lại, badge trên tiêu đề tab.

Stack ở đó: Payload `4.0.0-canary.14`, Next `^16.2.12`, React `^19`, Node
`>=20`, pnpm `9.15.9`, `postgresAdapter` với `pool.connectionString` và **không**
đặt `schemaName`.

KLAW: Python 3.11, FastAPI, Postgres `klaw` ở `localhost:5432`, migration riêng
tới `021`. Frontend KLAW là TanStack Start, npm, cổng 3000.

## 3. Quyết định

**Payload sống trong schema `cms`.** `postgresAdapter({ schemaName: 'cms', … })`.
Mọi bảng của Payload — collection, `payload_migrations`, `payload_preferences` —
nằm trong `cms.*`. `payload migrate` không bao giờ chạm `public.*`. Đây là điều
kiện để hai bộ migration cùng tồn tại trên một database.

**CMS không có collection nào ánh xạ bảng KLAW.** Màn hình tài khoản và yêu cầu
là view tuỳ biến gọi API `/admin/*` của KLAW. Đổi lại việc mất giao diện tự sinh,
ta giữ được nguyên tắc mỗi bảng một chủ.

**Đăng nhập riêng.** Collection `admins` dùng auth sẵn có của Payload
(`auth: true`), cookie, không liên quan Supabase. Người đầu tiên tạo bằng luồng
`create-first-user` của Payload trên máy local, hoặc script seed chạy tay.

**Chuông đọc từ KLAW, không từ Payload.** Bảng thông báo do KLAW sở hữu (gói
2B-1). Thành phần `NotificationBell` chuyển sang gần như nguyên vẹn nhưng đổi
nguồn: gọi `/admin/thong-bao` và `/admin/thong-bao/luong` của KLAW qua một route
proxy trong Next, thay vì `/api/notifications` của Payload.

**Proxy thay vì gọi thẳng từ trình duyệt.** `KLAW_ADMIN_API_KEY` là bí mật máy
chủ. Trình duyệt không được giữ nó. Nên Next có
`app/api/klaw/[...duong]/route.ts` chạy phía máy chủ: kiểm phiên Payload, gắn
`X-Admin-Key` và `X-Admin-Boi`, rồi chuyển tiếp sang KLAW. Trình duyệt chỉ nói
chuyện với Next.

## 4. Bố cục

```
cms/                          # ứng dụng Payload, pnpm workspace riêng
  package.json                # payload 4, next 16, react 19, @payloadcms/db-postgres
  payload.config.ts
  src/
    payload/
      collections/Admins.ts
      collections/NhatKy.ts            # nhật ký thao tác của chính CMS
      components/ChuongThongBao/       # chuyển từ NotificationBell
      views/YeuCau.tsx                 # danh sách + duyệt/từ chối
      views/TaiKhoan.tsx               # tìm + chi tiết + đặt gói
    lib/klaw.ts                        # client gọi API KLAW, chỉ chạy máy chủ
  app/
    (payload)/…                        # khung admin của Payload
    api/klaw/[...duong]/route.ts       # proxy
```

CMS nằm trong cùng repo KLAW, thư mục `cms/`. Một job CI riêng chạy
`pnpm install`, `pnpm lint`, `pnpm build`. Không đụng job Python hiện có.

Cổng local: 3001 (KLAW frontend giữ 3000, backend giữ 8000).

## 5. Biến môi trường

| Biến | Ở đâu | Việc |
|---|---|---|
| `DATABASE_URI` | `cms/.env` | Cùng database `klaw`, Payload dùng schema `cms` |
| `PAYLOAD_SECRET` | `cms/.env` | Khoá ký phiên của Payload |
| `KLAW_API_URL` | `cms/.env` | `http://127.0.0.1:8000/api/v1` khi local |
| `KLAW_ADMIN_API_KEY` | `cms/.env` **và** `.env.local` của KLAW | Cùng một giá trị hai phía |

`KLAW_ADMIN_API_KEY` chỉ đọc ở phía máy chủ của Next. Không có tiền tố
`NEXT_PUBLIC_`, không bao giờ lọt vào bundle trình duyệt.

## 6. Màn hình

### 6.1 Yêu cầu nâng gói

Danh sách lấy từ `GET /admin/yeu-cau?trang_thai=cho_duyet`. Mỗi dòng: email, gói
hiện tại, loại (nâng gói hay gia hạn), thời điểm tạo. Hai nút: Duyệt và Từ chối.
Từ chối mở hộp nhập lý do.

Sau khi bấm, gọi `POST /admin/yeu-cau/{id}/duyet` hoặc `.../tu-choi` qua proxy,
rồi tải lại danh sách. Nhận 409 nghĩa là người khác vừa xử lý — hiện thông báo
và tải lại, không coi là lỗi của người bấm.

### 6.2 Tài khoản

Ô tìm theo email gọi `GET /admin/tai-khoan?q=`. Bảng: email, gói, hạn, ngày tham
gia, số phiên, lượt 30 ngày. Bấm một dòng mở chi tiết từ
`GET /admin/tai-khoan/{sub}`: các thanh đo mức dùng, lịch sử yêu cầu, và một form
đặt gói tay gọi `PATCH /admin/tai-khoan/{sub}/goi`.

Màn hình chi tiết **không** có chỗ nào hiện nội dung hội thoại. Ranh giới này
thuộc spec 2B-1 và CMS không có API để vượt qua nó.

### 6.3 Chuông

Chuyển từ `NotificationBell` của dự án tham khảo, giữ nguyên ba ý:

- Badge là số chưa đọc, không cần chính xác từng mili-giây.
- Nguồn sự thật là lần gọi danh sách; SSE chỉ đẩy nhanh.
- `EventSource` tự nối lại, nên không viết logic thử lại.

Đổi hai chỗ: nguồn là `/api/klaw/thong-bao` và `/api/klaw/thong-bao/luong` (proxy
Next), và chữ hiển thị dịch sang tiếng Việt cho hợp KLAW.

Proxy phải chuyển tiếp được luồng SSE: đọc `body` của phản hồi KLAW dưới dạng
stream và trả lại nguyên vẹn với `Content-Type: text/event-stream`, không đệm.

## 7. Lỗi và an toàn

- Proxy từ chối mọi request không có phiên Payload hợp lệ (401), trước khi chạm
  KLAW.
- Proxy chỉ cho qua danh sách đường dẫn đã khai (`thong-bao`, `yeu-cau`,
  `tai-khoan`), không phải bộ chuyển tiếp mở cho mọi đường dẫn.
- KLAW trả 503 khi `KLAW_ADMIN_API_KEY` rỗng; CMS hiện đúng câu đó chứ không
  dịch thành "không có dữ liệu".
- Mọi thao tác ghi đều ghi `NhatKy` phía CMS **và** `nhat_ky_quan_tri` phía KLAW.
  Hai bản ghi cùng một sự kiện là cố ý: bản của KLAW là bản pháp lý, bản của CMS
  là để tra trên giao diện.
- Không có collection nào của Payload trỏ vào bảng `public.*`.

## 8. Kiểm chứng

- `payload migrate` trên database sạch chỉ tạo bảng trong schema `cms`; đếm bảng
  trong `public` trước và sau, phải bằng nhau.
- Proxy không phiên → 401 và **không** phát request nào sang KLAW.
- `KLAW_ADMIN_API_KEY` không lọt vào bundle: grep thư mục build.
- Duyệt một yêu cầu từ giao diện làm đổi `plan` và `plan_het_han` trong
  `public.users`, và sinh một dòng `thong_bao` cho người dùng.
- Bấm Duyệt hai lần liên tiếp trên cùng một yêu cầu: lần hai nhận 409, gói không
  bị cộng thêm chu kỳ.
- Chuông: mở CMS, tạo một yêu cầu từ ứng dụng KLAW, badge tăng trong vòng vài
  giây mà không cần tải lại trang.
- `pnpm lint`, `pnpm build` xanh trong CI.

## 9. Chi phí và rủi ro đã biết

- Trên Railway đây là service thứ hai. Một instance Payload với Next cần khoảng
  512 MB tới 1 GB RAM. Ghi chú phạm vi khoá luận đã chốt rằng RAM tính khoảng
  10 USD mỗi GB mỗi tháng, nên đây là chi phí định kỳ thật, không phải miễn phí.
- Payload dùng bản `4.0.0-canary`. Bản canary có thể đổi API giữa các phiên bản;
  ghim đúng phiên bản trong `package.json` và không nâng trong lúc thi công.
- Repo có thêm một hệ công cụ thứ hai (Node, pnpm) cạnh Python. Người đọc mã cần
  biết `cms/` chạy bằng pnpm còn `frontend/` chạy bằng npm.

## 10. Ngoài phạm vi

- Webhook thanh toán và mọi thứ liên quan tới tiền thật.
- Xoá tài khoản (cần khoá service-role của Supabase).
- Quản trị nội dung: KLAW không có nội dung biên tập, CMS này chỉ quản lý tài
  khoản.
- Đồng bộ hai chiều giữa `cms.admins` và `public.users`. Hai tập người dùng khác
  nhau, cố ý không nối.
