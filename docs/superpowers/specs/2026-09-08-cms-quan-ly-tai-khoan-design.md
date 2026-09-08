# Gói 2B — CMS quản lý tài khoản KLAW trên Payload (thiết kế hợp nhất)

Ngày: 2026-09-08 · Trạng thái: chờ chủ dự án duyệt · Gói trước: 2A/3 vỏ ứng dụng và
tài khoản (đã xong, `docs/plans/completed/vo-ung-dung-va-tai-khoan.md`).

Spec này **thay cho** hai bản nháp cùng ngày `2026-09-08-quan-tri-tai-khoan-klaw-design.md`
(2B-1) và `2026-09-08-cms-payload-quan-tri-design.md` (2B-2). Hai bản đó viết trước khi
kiểm chứng thực tế Payload và trước khi đối chiếu cơ chế nâng gói của các sản phẩm lớn;
phần còn đúng được giữ nguyên ở đây, phần sai được sửa và nói rõ vì sao.

## 0. Bảy quyết định cần bạn xác nhận khi duyệt

Mỗi dòng là một lựa chọn có thể đảo ngược bằng một câu. Mặc định ghi trước, lý do ghi ở
mục dẫn.

| # | Quyết định mặc định | Vì sao | Mục |
|---|---|---|---|
| 1 | Payload **3.88.0** (bản ổn định 11/08/2026), không dùng `4.0.0-canary` như dự án tham chiếu | 4.0 đang pre-alpha, nhóm Payload nói rõ không dùng cho production; canary đổi API giữa các bản | §3.2 |
| 2 | CMS dùng **database riêng `klaw_cms`** trên cùng instance Postgres, không dùng `schemaName` | `schemaName` gắn nhãn experimental, có issue #6266 "muốn xoá schema public" và #5822; một database riêng là cách tách rẻ nhất và không có cờ thử nghiệm nào | §4.2 |
| 3 | KLAW **giữ quyền sở hữu mọi bảng tài khoản**; CMS chỉ đi qua API `/admin/*`. Payload chỉ sở hữu `admins` và `nhat_ky_cms` | Cổng hạn mức của KLAW đọc `users` ở mọi request; để Payload quản schema bảng đó là đặt hot path của KLAW dưới `drizzle push`. Đổi lại ta phải tự viết 4 màn hình React thay vì dùng giao diện tự sinh | §4.1 |
| 4 | Thêm **khoá / mở khoá tài khoản** (`users.khoa_luc`, `khoa_ly_do`), cưỡng chế ở cổng KLAW | "Quản lý tài khoản đã đăng ký" mà không chặn được một tài khoản lạm dụng thì không phải quản lý; mọi sản phẩm lớn đều có. Chi phí: một cột đọc thêm trong truy vấn đã có | §5.2, §5.4 |
| 5 | **Lưu lý do từ chối** (`yeu_cau_nang_goi.ly_do`) và người dùng thấy lý do | Từ chối không lý do là hộp đen; bản nháp 2B-1 nhận `ly_do` ở API nhưng không có cột nào để lưu | §5.1 |
| 6 | Thông báo hai chiều và **chuông SSE là giai đoạn 3**, cắt được mà không ảnh hưởng hai giai đoạn trước | Nâng gói phải chạy được bằng danh sách và nút Duyệt trước; chuông là tối ưu hoá trải nghiệm | §12 |
| 7 | **Không có thanh toán trực tuyến** trong gói này; giữ đúng một chỗ cắm `nang_goi.duyet(nguon='thanh_toan')` | Giá 199.000 đ/30 ngày đã công bố, nhưng cổng thanh toán là một dự án riêng có nghĩa vụ pháp lý riêng | §11 |

## 1. Mục tiêu

- Một trang quản trị **độc lập** với ứng dụng KLAW: mã riêng (`cms/`), tiến trình riêng
  (cổng 3001, service Railway riêng), database riêng, đăng nhập riêng bằng auth sẵn có
  của Payload, hai vai trò.
- Quản lý được tài khoản đã đăng ký và đăng nhập vào KLAW: tìm theo email, xem gói,
  hạn, mức dùng, lịch sử yêu cầu; duyệt hoặc từ chối yêu cầu nâng và gia hạn gói; đặt gói
  tay; khoá và mở khoá tài khoản.
- **Một đường nâng gói duy nhất**, idempotent, để webhook thanh toán sau này gọi đúng
  hàm đó mà không viết lại logic.
- Nhật ký quản trị bất biến, xuất được CSV. Thông báo hai chiều (admin biết có yêu cầu
  mới; người dùng biết kết quả) ở giai đoạn 3.
- Không đổi một chút nào hành vi của cổng công khai: khách, người dùng Free và Cá nhân
  không nhìn thấy sự tồn tại của CMS.

## 2. Học gì từ ChatGPT, Claude, Gemini và Stripe

Khảo sát ngày 2026-09-08 bằng Firecrawl trên trang trợ giúp của OpenAI, Anthropic, trang
gói của Gemini (bản tiếng Việt) và tài liệu vòng đời subscription của Stripe. Chỉ ghi
những điều đọc được nguyên văn, không suy diễn.

| Cơ chế | Nguồn | KLAW áp dụng |
|---|---|---|
| Nâng gói **hiệu lực ngay**, chu kỳ tính lại từ lúc nâng, tính tiền chênh ngay | OpenAI: "If you upgrade, your new plan takes effect immediately and your billing cycle starts over." Anthropic: nâng giữa kỳ "reset your billing cycle and receive an immediate invoice" | Duyệt yêu cầu `nang_goi` (Free → Cá nhân): `plan_het_han = now + chu_ky_pro_ngay`. Không có tiền chênh vì không có tiền |
| Hạ gói / huỷ **giữ quyền tới hết kỳ** | OpenAI: "If you move to a lower tier, the change takes effect at your next renewal and you keep your current plan until then." Gemini: "Huỷ bất cứ lúc nào. Không được hoàn tiền cho một phần của kỳ thanh toán." | Không có nút "hạ gói" tự phục vụ: gói Cá nhân hết hạn thì tự về Free (đã có từ 2A). Admin chỉ có **thu hồi** (`thu_hoi`) hiệu lực ngay, bắt buộc lý do, dành cho lạm dụng — tách khỏi "đặt gói" để nhật ký đọc được ý định |
| Gia hạn **cộng dồn** từ hạn hiện tại | Stripe: renewal nối tiếp `current_period_end` | Duyệt yêu cầu `gia_han`: `plan_het_han = max(plan_het_han, now) + chu_ky_pro_ngay` |
| Vòng đời có **trạng thái tên rõ** | Stripe: `trialing` → `incomplete` → `active` → `past_due`/`canceled`; `incomplete_expired` khi không thanh toán trong 23 giờ | Ánh xạ ở bảng dưới. KLAW không thêm bảng subscription: trạng thái suy ra từ `users.plan`, `plan_het_han`, `khoa_luc` và `yeu_cau_nang_goi.trang_thai` |
| **Idempotent** theo mã sự kiện | Stripe: webhook có thể gửi lặp, tích hợp phải chịu được | `yeu_cau_nang_goi.tham_chieu` duy nhất; `duyet` gọi lại cùng `tham_chieu` trả kết quả cũ |
| Nhật ký kiểm toán **bất biến**, ghi cả **đăng nhập thất bại** | OpenAI Audit Logs API (đã dẫn ở bản nháp 2B-1) | `nhat_ky_quan_tri` chỉ ghi thêm, có test grep; Payload `maxLoginAttempts` + ghi `nhat_ky_cms` khi đăng nhập sai |
| Vai trò: tối thiểu **xem** và **quản trị** | Console Anthropic và OpenAI có nhiều vai trò cho khách doanh nghiệp; KLAW lấy đúng lằn ranh có giá trị | `admins.vai_tro ∈ {doc, quan_tri}` |
| Hạn mức Gemini theo cửa sổ 5 giờ, trần tuần; ChatGPT theo cửa sổ trượt | Trang gói Gemini: "Hạn mức sẽ được cập nhật sau mỗi 5 giờ cho đến khi bạn đạt đến hạn mức hằng tuần" | **Không đổi**: 2A đã chốt ngày/tháng và giải thích vì sao. Ghi ở đây để không ai đề xuất lại |
| Nhân viên hỗ trợ **không đọc hội thoại** người dùng | Sản phẩm lớn có "đăng nhập thay" kèm rất nhiều kiểm soát | KLAW cố ý không có endpoint nào trả nội dung `hoi_thoai`, `luot_hoi_thoai` cho admin |

Ánh xạ trạng thái (để nói cùng một ngôn ngữ với thế giới bên ngoài, không phải để thêm
cột):

| Stripe | KLAW | Suy ra từ |
|---|---|---|
| `trialing` | Khách | không có bearer, có `X-Khach-Id` |
| không có subscription | Miễn phí | `plan_hieu_luc = 'free'`, không có yêu cầu `cho_duyet` |
| `incomplete` | Đang chờ duyệt | `yeu_cau_nang_goi.trang_thai = 'cho_duyet'` |
| `incomplete_expired` | Bị từ chối | `trang_thai = 'tu_choi'`, `ly_do` |
| `active` | Cá nhân còn hiệu lực | `plan = 'pro'`, `plan_het_han > now()` hoặc NULL |
| `canceled` (hết kỳ) | Cá nhân đã hết hạn, đang là Miễn phí | `plan = 'pro'`, `plan_het_han <= now()` |
| `paused` | Bị khoá | `khoa_luc IS NOT NULL` — chặn mọi gói, không đổi `plan` |

## 3. Hiện trạng

### 3.1 KLAW

- `users` có `sub`, `email`, `plan`, `created_at`, `last_seen_at`, `plan_het_han`. Không
  có vai trò, không có trạng thái khoá.
- `yeu_cau_nang_goi` (migration 021) có `id`, `user_sub`, `loai`, `goi_hien_tai`,
  `goi_muon`, `trang_thai`, `tao_luc`, `xu_ly_luc`, `xu_ly_boi`. Ba cột cuối luôn rỗng
  vì chưa có đường duyệt. `xu_ly_boi` là `UUID` — sai kiểu cho email admin, §5.1 sửa.
- `src/services/nang_goi.py`: `tao_yeu_cau`, `moi_nhat`, `GIA_HAN_TRUOC_NGAY = 7`,
  bốn ngoại lệ. Không có `duyet`.
- `bao_ve.kiem_api_key` là cổng toàn cục theo `KLAW_API_KEY`; không dùng được làm danh
  tính cho CMS. `plan_hieu_luc(sub)` đọc `plan, plan_het_han` mỗi request.
- SSE đã có ở `routes_luong.py` (`StreamingResponse`, `event:`/`data:`, `: ping`).
  Frontend đọc bằng `fetch` + `ReadableStream` trong `api.ts` vì cần header `Authorization`.
- `lifespan` áp migration `("019", "020", "021")` qua `db.run_migrations`; gói này thêm `"022"`.
- Test API dùng fixture `cai_dat`, `khoa_ky` (JWKS giả) và `client`; test tích hợp đánh
  dấu `pytest.mark.integration`, dọn dữ liệu theo `sub`.
- Frontend: `AppShell` có `TheTaiKhoan` ở chân sidebar và slot `topRight`; `ModalNangGoi`
  đọc `GET /nang-goi/yeu-cau` để hiện "Đang chờ duyệt"; giá Cá nhân 199.000 đ/30 ngày.
- Railway: KLAW **chưa có service nào** (kiểm ngày 2026-09-08: hai project trên tài khoản
  là `vsf-cms-multiple-sites-backend` và một project không liên quan). Topology Railway ở
  §8 là đích, môi trường kiểm chứng của gói này là local.

### 3.2 Payload (kiểm chứng 2026-09-08)

- Bản ổn định mới nhất: **3.88.0** (11/08/2026, tập trung hardening). 4.0 là pre-alpha,
  nhóm Payload khuyến cáo không dùng cho production; beta mới được nhắm cho quý này.
  `create-payload-app` mới nhất trên npm là 3.84.1.
- `auth` của collection có `maxLoginAttempts`, `lockTime`, `tokenExpiration`, `cookies`
  (`secure`, `sameSite`), `useSessions` (mặc định bật), `verify`.
- Custom root view: `admin.components.views.<khoa> = {Component, path}`; **mọi custom view
  đều công khai mặc định**, phải tự kiểm `initPageResult.req.user`. `DefaultTemplate`
  từ `@payloadcms/next/templates` giữ khung điều hướng.
- Slot `admin.components.actions` render trên mọi trang admin — đúng chỗ cho chuông,
  dự án tham chiếu đã dùng chính slot này.
- `postgresAdapter`: `pool.connectionString` bắt buộc; `schemaName` ghi "experimental";
  `push` chỉ bật ở development, production dùng `payload migrate`.
- Custom endpoint của Payload nhận `PayloadRequest` đã có `req.user` từ cookie; dự án
  tham chiếu đã stream SSE từ một endpoint như vậy (`notificationStream.ts`) bằng
  `ReadableStream`, có nhịp tim và dọn khi `cancel()`.

### 3.3 Dự án tham chiếu `~/VF_TTS/vsf-cms-multiple-sites-backend`

Chuyển sang được gần nguyên vẹn, chỉ đổi phiên bản và nguồn dữ liệu:

- `src/payload/components/NotificationBell/` (`index.tsx`, `bell.ts`, `index.scss`) —
  badge, gộp theo ngày, `EventSource` tự nối lại, badge trên tiêu đề tab. `bell.ts`
  tách logic thuần để vitest chạy được ở `environment: 'node'`.
- `src/payload/endpoints/notificationStream.ts` — khuôn SSE.
- `src/payload/hooks/exposeErrorReason.ts` — hook `afterError` để admin panel không nuốt
  lỗi thành "An unknown error has occurred".
- `scripts/start.sh` — chạy `payload migrate`, đọc lại `migrate:status`, **từ chối khởi
  động** nếu còn migration `No`. Bài học từ sự cố 2026-08-17 của chính dự án đó.
- `vitest.config.ts` — `fileParallelism: false` vì Payload mở pool Postgres.
- `Users.ts` — `cookies.secure` theo `NODE_ENV`, `sameSite: 'Lax'`; `versions: false`
  cho collection tài khoản.
- Không chuyển: hệ vai trò theo site, workspace strategy, Memberships, Lexical, Media —
  KLAW không có nội dung biên tập.

## 4. Kiến trúc

```
 Trình duyệt admin                      Trình duyệt người dùng
        │ cookie Payload                          │ JWT Supabase
        ▼                                         ▼
 ┌─────────────────────┐  X-Admin-Key       ┌─────────────────────┐
 │  CMS  cms/  :3001   │  X-Admin-Boi       │  KLAW FE  :3000     │
 │  Payload 3.88 + Next│ ─────────────────▶ │  TanStack Start     │
 │  DB: klaw_cms       │  /api/v1/admin/*   └──────────┬──────────┘
 │  admins, nhat_ky_cms│                               │ /api/v1/*
 └─────────────────────┘                               ▼
                                            ┌─────────────────────┐
                                            │  KLAW API  :8000    │
                                            │  FastAPI            │
                                            │  DB: klaw (public)  │
                                            │  users, yeu_cau_…,  │
                                            │  thong_bao, nhat_ky_│
                                            │  quan_tri, traces   │
                                            └─────────────────────┘
```

### 4.1 Nguyên tắc

1. **Mỗi bảng một chủ.** Bảng tài khoản, yêu cầu, thông báo, nhật ký pháp lý thuộc KLAW;
   CMS không có collection nào trỏ vào `klaw.public.*` và không có chuỗi kết nối tới
   database `klaw`. Payload chỉ quản `klaw_cms`.
2. **Một đường nâng gói.** Mọi thay đổi `users.plan`/`plan_het_han` đi qua ba hàm trong
   `nang_goi.py`: `duyet`, `dat_goi`, `thu_hoi`. Không có `UPDATE users SET plan` ở nơi
   nào khác trong `src/`; §9 có test grep.
3. **Fail-closed.** `KLAW_ADMIN_API_KEY` rỗng → router `/admin` trả 503 cho mọi request.
   Ngược quy ước của `KLAW_API_KEY` (rỗng = mở), và cố ý: một đường quản trị mở khi quên
   cấu hình hỏng nặng hơn một đường quản trị đóng.
4. **Kiểm quyền ở máy chủ, không ở nút.** Proxy trong CMS chặn theo vai trò trước khi
   chạm KLAW; KLAW kiểm khoá trước khi chạm DB. Ẩn nút chỉ là lịch sự.
5. **Bí mật không ra trình duyệt.** `KLAW_ADMIN_API_KEY` chỉ đọc ở endpoint Payload (chạy
   phía máy chủ Next). Không tiền tố `NEXT_PUBLIC_`.
6. **Hai nhật ký, hai mục đích.** `nhat_ky_quan_tri` (KLAW) là bản pháp lý, bất biến;
   `nhat_ky_cms` (Payload) là để tra trên giao diện và ghi những gì KLAW không thấy
   (đăng nhập CMS sai). Mỗi thao tác ghi thành công thì có mặt ở cả hai.

### 4.2 Vì sao database riêng thay cho `schemaName`

Bản nháp 2B-2 chọn `schemaName: 'cms'` trên cùng database `klaw`. Tài liệu Payload gắn
nhãn tuỳ chọn này "experimental"; issue #6266 mô tả adapter "muốn xoá schema public khi
mở `/admin`" dù đã đặt `schemaName`, issue #5822 mô tả thay đổi không áp vào bảng. Rủi ro
đó rơi đúng vào database chứa `provisions`, `chunks`, `traces` của khoá luận.

`CREATE DATABASE klaw_cms` trên cùng instance không tốn service nào thêm (local: cùng
container `klaw-db-1`; Railway: cùng service Postgres, một lần `CREATE DATABASE` qua
`railway connect`). Payload cũng tự tạo database khi chưa có (`disableCreateDatabase`
mặc định `false`). Hai bộ migration không bao giờ chạm nhau vì không chung catalog.

## 5. Phía KLAW

### 5.1 Migration `022_quan_tri.sql`

```sql
-- Thông báo: KLAW sở hữu, hai người đọc (admin: nguoi_nhan IS NULL; người dùng: sub).
CREATE TABLE IF NOT EXISTS thong_bao (
  id           BIGSERIAL PRIMARY KEY,
  nguoi_nhan   UUID REFERENCES users(sub) ON DELETE CASCADE,
  loai         TEXT NOT NULL CHECK (loai IN (
                 'yeu_cau_moi', 'yeu_cau_duyet', 'yeu_cau_tu_choi',
                 'goi_dat_tay', 'goi_thu_hoi', 'tai_khoan_khoa', 'tai_khoan_mo')),
  tieu_de      TEXT NOT NULL,
  noi_dung     TEXT NOT NULL,
  duong_dan    TEXT NOT NULL,
  khoa_gom     TEXT NOT NULL,
  da_doc       BOOLEAN NOT NULL DEFAULT FALSE,
  het_hieu_luc BOOLEAN NOT NULL DEFAULT FALSE,
  tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_thong_bao_gom
  ON thong_bao (khoa_gom) WHERE NOT het_hieu_luc;
CREATE INDEX IF NOT EXISTS ix_thong_bao_nhan
  ON thong_bao (nguoi_nhan, da_doc, tao_luc DESC);

-- Nhật ký quản trị: CHỈ GHI THÊM. Không đường nào trong src/ UPDATE hay DELETE.
CREATE TABLE IF NOT EXISTS nhat_ky_quan_tri (
  id             BIGSERIAL PRIMARY KEY,
  hanh_dong      TEXT NOT NULL,
  doi_tuong      UUID,
  chi_tiet       JSONB NOT NULL DEFAULT '{}'::jsonb,
  boi            TEXT NOT NULL,
  tac_nhan_loai  TEXT NOT NULL DEFAULT 'admin'
                 CHECK (tac_nhan_loai IN ('admin', 'tu_dong', 'thanh_toan')),
  ip             TEXT,
  tao_luc        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_tao_luc ON nhat_ky_quan_tri (tao_luc DESC);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_hanh_dong ON nhat_ky_quan_tri (hanh_dong, tao_luc DESC);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_doi_tuong ON nhat_ky_quan_tri (doi_tuong, tao_luc DESC);

-- Yêu cầu: nguồn và tham chiếu (idempotent), lý do từ chối, người xử lý là email.
ALTER TABLE yeu_cau_nang_goi
  ADD COLUMN IF NOT EXISTS nguon      TEXT CHECK (nguon IN ('admin', 'thanh_toan')),
  ADD COLUMN IF NOT EXISTS tham_chieu TEXT,
  ADD COLUMN IF NOT EXISTS ly_do      TEXT,
  ALTER COLUMN xu_ly_boi TYPE TEXT USING xu_ly_boi::text;
CREATE UNIQUE INDEX IF NOT EXISTS ux_yeu_cau_tham_chieu
  ON yeu_cau_nang_goi (tham_chieu) WHERE tham_chieu IS NOT NULL;

-- Khoá tài khoản: NULL = bình thường. Không đổi plan; cổng kiểm cột này trước.
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS khoa_luc   TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS khoa_ly_do TEXT;
```

Ghi chú:

- `ALTER COLUMN xu_ly_boi TYPE TEXT` an toàn vì cột luôn NULL tới nay (§3.1); test
  idempotent chạy migration hai lần phải xanh — `ALTER COLUMN TYPE` sang cùng kiểu là
  no-op hợp lệ trong Postgres.
- `khoa_gom` chặn nhân bản: `yeu_cau:{user_sub}` cho hộp thư admin, `ket_qua:{yeu_cau_id}`
  và `tai_khoan:{user_sub}:{loai}` cho người dùng. Đụng chỉ mục duy nhất thì nuốt, không
  tạo dòng thứ hai.
- Bảy giá trị `loai` là tất cả sự kiện gói này sinh ra; không có giá trị dự phòng.
  `sap_het_han` của bản nháp 2B-1 bị bỏ vì không có nơi nào sinh nó (giao diện đã hiện
  "còn N ngày" từ 2A).
- `lifespan` áp `("019", "020", "021", "022")`.

### 5.2 Dịch vụ

**`nang_goi.py` — bốn hàm, cùng một khuôn transaction; ba hàm đổi gói (`duyet`,
`dat_goi`, `thu_hoi`) và một hàm không đụng `users` (`tu_choi`).**

```python
def duyet(yeu_cau_id: int, nguon: str, tham_chieu: str, boi: str, ip: str | None) -> dict:
    """Duyệt một yêu cầu và đổi gói. Idempotent theo `tham_chieu`."""

def tu_choi(yeu_cau_id: int, ly_do: str, boi: str, ip: str | None) -> dict:
    """Từ chối, lưu lý do. Không đụng `users`."""

def dat_goi(sub: str, plan: str, so_ngay: int | None, boi: str, ip: str | None = None, *, ly_do: str) -> dict:
    """Đặt gói tay. `so_ngay=None` với plan trả phí = vô thời hạn (plan_het_han NULL). `ly_do` chỉ vào nhật ký."""

def thu_hoi(sub: str, ly_do: str, boi: str, ip: str | None) -> dict:
    """Thu hồi gói trả phí ngay: plan_het_han = now(), KHÔNG đổi `plan`. Bắt buộc lý do."""
```

`thu_hoi` chỉ đặt `plan_het_han = now()` và để `plan_hieu_luc` tự trả `goi_mac_dinh` —
đúng hàng "`canceled` (hết kỳ)" của bảng trạng thái §2, không cần nhánh riêng ở cổng hay
ở giao diện; người dùng phân biệt "hết hạn" với "bị thu hồi" qua thông báo `goi_thu_hoi`
kèm lý do.

`duyet`, trong một transaction:

1. Nếu đã có dòng với `tham_chieu` này và `trang_thai = 'da_duyet'` → trả trạng thái
   hiện tại, không ghi gì.
2. `SELECT … FOR UPDATE` dòng yêu cầu. Không tồn tại → `KhongTonTai`. `trang_thai` khác
   `cho_duyet` → `DaXuLy`.
3. Người dùng đang bị khoá (`khoa_luc IS NOT NULL`) → `TaiKhoanKhoa`. Duyệt gói cho một
   tài khoản đang khoá là mâu thuẫn; mở khoá trước.
4. Hạn mới: `loai = 'nang_goi'` → `now + chu_ky`; `loai = 'gia_han'` →
   `max(plan_het_han, now) + chu_ky`. `chu_ky` đọc `han_muc.yaml: chu_ky_pro_ngay`.
5. `UPDATE users SET plan = goi_muon, plan_het_han = hạn mới`.
6. `UPDATE yeu_cau_nang_goi SET trang_thai = 'da_duyet', xu_ly_luc = now(), xu_ly_boi,
   nguon, tham_chieu`.
7. `nhat_ky.ghi('duyet_yeu_cau', doi_tuong=sub, chi_tiet={yeu_cau_id, loai, goi, het_han}, boi, tac_nhan_loai, ip)`.
8. `thong_bao.ghi(nguoi_nhan=sub, loai='yeu_cau_duyet', …, khoa_gom=f'ket_qua:{id}')`.
9. `thong_bao.vo_hieu(khoa_gom=f'yeu_cau:{sub}')`.

`tu_choi` đi bước 2, 6 (với `trang_thai = 'tu_choi'`, `ly_do`), 7, 8 (loại
`yeu_cau_tu_choi`, `noi_dung` chứa lý do), 9. `dat_goi` và `thu_hoi` khoá dòng `users`
(`FOR UPDATE`), đổi gói, ghi nhật ký và thông báo; `thu_hoi` từ chối nếu gói hiệu lực đã
là `goi_mac_dinh` (`KhongCoGiDeThuHoi`). `duyet` suy `tac_nhan_loai` từ `nguon`
(`'admin'` → `'admin'`, `'thanh_toan'` → `'thanh_toan'`); ba hàm còn lại chỉ admin gọi
nên ghi cứng `'admin'`.

Ngoại lệ mới: `KhongTonTai`, `DaXuLy`, `TaiKhoanKhoa`, `KhongCoGiDeThuHoi`. `GoiKhongHopLe`
tái dùng cho `dat_goi` với `plan` lạ.

**`tai_khoan_qt.py` (mới) — phía admin của tài khoản.**

- `tim(q: str, limit, offset) -> (tong, list[dict])`: `email ILIKE %q%`, kèm `plan`,
  `plan_het_han`, `khoa_luc`, `created_at`, số phiên, lượt hỏi 30 ngày (đếm `traces`
  theo quy tắc §4.2 của spec 2A).
- `chi_tiet(sub) -> dict | None`: `ho_so.tong_hop(sub)` sẵn có + `khoa_luc`, `khoa_ly_do`
  + lịch sử `yeu_cau_nang_goi` của `sub` (mọi trạng thái, mới nhất trước).
- `khoa(sub, ly_do, boi, ip)` / `mo_khoa(sub, ly_do, boi, ip)`: `UPDATE users SET khoa_luc,
  khoa_ly_do`, nhật ký `khoa_tai_khoan`/`mo_khoa_tai_khoan` (cả hai kèm `chi_tiet.ly_do`),
  thông báo cho người dùng (thông báo mở khoá không mang lý do).
  `khoa` trên tài khoản đã khoá và `mo_khoa` trên tài khoản đang mở → `TrangThaiKhongDoi`
  (409), không ghi gì.
- `tong_quan() -> dict`: tổng tài khoản; đang Cá nhân hiệu lực; yêu cầu `cho_duyet`;
  hết hạn trong 7 ngày; tài khoản mới 7 ngày; đang khoá; lượt hỏi hôm nay (mốc
  `moc_ngay`). Bảy con số, bảy truy vấn đếm; không cache.

**`thong_bao.py` (mới).** `danh_sach(nguoi_nhan, chi_chua_doc, limit)`,
`dem_chua_doc(nguoi_nhan)`, `danh_dau_da_doc(ids, nguoi_nhan) -> int` (chỉ dòng đúng
người nhận), `ghi(...) -> int | None` (None khi đụng `khoa_gom`), `vo_hieu(khoa_gom)`.
`nguoi_nhan is None` nghĩa là hộp thư admin, tường minh, không dùng chuỗi rỗng.

**`nhat_ky.py` (mới).** `ghi(hanh_dong, doi_tuong, chi_tiet, boi, tac_nhan_loai, ip)`,
`danh_sach(tu, den, hanh_dong, doi_tuong, limit, offset) -> (tong, rows)`,
`csv(rows) -> str`. Không có hàm sửa hay xoá — và §9 có test khẳng định.

**`bao_ve.py` — hai đổi nhỏ.**

- `_SQL_PLAN_HIEU_LUC` đọc thêm `khoa_luc`. Hàm mới `kiem_khoa(row)` ném
  `HTTPException(403, LOI_TAI_KHOAN_KHOA)` với câu "Tài khoản của bạn đang bị tạm khoá.
  Liên hệ hỗ trợ để được mở lại." Gọi ở `cong_bao_ve` (mọi request tốn LLM) và
  `nguoi_dung_bat_buoc` (mọi endpoint tài khoản). `/han-muc` vẫn trả lời người bị khoá
  (để giao diện vẽ được thẻ khoá) nhưng thêm trường `bi_khoa: bool` vào `HanMucResponse`.
  Trên hot path LLM không tốn truy vấn thêm (`plan_hieu_luc` đã đọc đúng dòng đó); trên
  các endpoint tài khoản `nguoi_dung_bat_buoc` tốn một truy vấn khoá chính mỗi request —
  chấp nhận, đó không phải đường tốn LLM.
- `kiem_admin_key(request)` (mới, §5.3).

Người bị khoá vẫn đăng nhập được ở Supabase (KLAW không có service-role key để vô hiệu
phiên Supabase, và cố ý không giữ). Khoá ở KLAW nghĩa là: không hỏi, không soạn, không
xem hồ sơ; tra cứu văn bản và soát văn bản (không tốn LLM, không cần danh tính) vẫn mở
như với khách.

### 5.3 Router `/admin` — `src/api/routes_admin.py`

Cổng `Depends(kiem_admin_key)`, dừng ở bước đầu tiên hỏng:

1. Lá chắn IP: `kiem_rate_limit(f"chan-ip:{ip_goi(request)}", rate_limit_ip_so_luot)` —
   cùng giỏ cổng công khai đang dùng.
2. `KLAW_ADMIN_API_KEY` rỗng → 503 "Đường quản trị chưa được cấu hình."
3. `X-Admin-Key` so bằng `secrets.compare_digest`; sai → 401, ghi
   `nhat_ky_quan_tri(hanh_dong='xac_thuc_that_bai', boi='(không rõ)', ip)`.
4. `X-Admin-Boi` (email admin từ CMS) thiếu → 400. Trả `{"boi": ..., "ip": ...}` cho handler.

| Method | Đường dẫn | Việc | Vai trò CMS |
|---|---|---|---|
| GET | `/admin/tong-quan` | Bảy con số §5.2 | doc |
| GET | `/admin/goi` | Danh sách gói từ YAML: mã, tên hiển thị, hạn mức, `chu_ky_pro_ngay` — để CMS không chép cứng | doc |
| GET | `/admin/yeu-cau` | Lọc `trang_thai`, `q` (email), `limit`/`offset`; mỗi dòng kèm email, gói hiệu lực, `khoa_luc` của người yêu cầu | doc |
| POST | `/admin/yeu-cau/{id}/duyet` | `duyet(id, 'admin', f'yeu_cau:{id}', boi, ip)` → 200 gói và hạn mới | quan_tri |
| POST | `/admin/yeu-cau/{id}/tu-choi` | Body `{ly_do}` (1–500 ký tự) → 200 | quan_tri |
| GET | `/admin/tai-khoan` | `tim(q, limit, offset)` | doc |
| GET | `/admin/tai-khoan/{sub}` | `chi_tiet(sub)` | doc |
| PATCH | `/admin/tai-khoan/{sub}/goi` | Body `{plan, so_ngay}` → `dat_goi` | quan_tri |
| POST | `/admin/tai-khoan/{sub}/thu-hoi` | Body `{ly_do}` → `thu_hoi` | quan_tri |
| POST | `/admin/tai-khoan/{sub}/khoa` | Body `{ly_do}` → `khoa` | quan_tri |
| POST | `/admin/tai-khoan/{sub}/mo-khoa` | → `mo_khoa` | quan_tri |
| GET | `/admin/nhat-ky` | Lọc `tu`/`den`/`hanh_dong`/`doi_tuong`, phân trang; `dinh_dang=csv` → `text/csv` + `Content-Disposition: attachment` | doc |
| GET | `/admin/thong-bao` | Hộp thư admin, `chi_chua_doc` | doc (GĐ3) |
| POST | `/admin/thong-bao/da-doc` | Body `{ids}` | doc (GĐ3) |
| GET | `/admin/thong-bao/luong` | SSE hộp thư admin | doc (GĐ3) |

Cột "Vai trò CMS" là điều proxy cưỡng chế (§6.4); KLAW không biết vai trò và không cần
biết — nó tin CMS đã lọc, và ghi `boi` để truy vết.

**Mọi thao tác đổi trạng thái đều bắt buộc `ly_do` (1–500 ký tự)** — duyệt là ngoại lệ duy
nhất vì lý do đã nằm trong yêu cầu của người dùng. Bổ sung 2026-09-08 theo khảo sát console
quản trị (đề xuất A trong `2026-09-08-khao-sat-console-quan-tri-to-chuc-lon.md`): GitHub bắt
ghi lý do cả khi treo lẫn khi bỏ treo tài khoản. Lý do của từ chối, thu hồi, khoá đi vào thông
báo cho người dùng; lý do của đặt gói tay và mở khoá là ghi chú nội bộ, **chỉ** vào
`nhat_ky_quan_tri.chi_tiet`, không vào thông báo.

**Không có** endpoint nào đọc `hoi_thoai` hay `luot_hoi_thoai`. Admin thấy *bao nhiêu
lượt*, không thấy *hỏi gì*. Ai muốn đổi phải sửa spec này trước.

Mã lỗi: 404 không tồn tại; 409 `DaXuLy`/`TrangThaiKhongDoi`/`KhongCoGiDeThuHoi`; 422
`GoiKhongHopLe`, `ly_do` rỗng hoặc quá dài; 423 `TaiKhoanKhoa` khi duyệt cho người đang
khoá (mã 423 Locked nói đúng nghĩa và không đụng 409 đã dùng cho "đã xử lý"). Mọi
endpoint ghi nhật ký kể cả khi ném lỗi nghiệp vụ — `hanh_dong` mang hậu tố `_that_bai`
và `chi_tiet.loi` là tên ngoại lệ (vd `duyet_yeu_cau_that_bai`, `{"loi": "DaXuLy"}`) —
trừ lỗi xác thực (đã ghi ở cổng) và lỗi 422 của Pydantic (chưa vào handler).

### 5.4 Endpoint người dùng (thêm vào `routes_tai_khoan.py`)

- `GET /nang-goi/yeu-cau` trả thêm `ly_do` (null khi không bị từ chối). `YeuCauNangGoiOut`
  thêm trường; `YeuCauNangGoiRequest` không đổi.
- `GET /han-muc` thêm `bi_khoa: bool`.
- Giai đoạn 3: `GET /thong-bao`, `POST /thong-bao/da-doc`, `GET /thong-bao/luong` sau
  `nguoi_dung_bat_buoc`.

### 5.5 Hình SSE (giai đoạn 3)

Khuôn `routes_luong.py`: `StreamingResponse(media_type="text/event-stream")`, khung
`event: <ten>\ndata: <json>\n\n`, `: ping` mỗi 15 giây. Hai sự kiện: `so_chua_doc`
(số nguyên) và `thong_bao_moi` (một dòng). Máy chủ hỏi DB mỗi 5 giây, chỉ phát khi số
đếm đổi; đóng sau 30 phút, client tự nối lại. Nguồn sự thật là `GET /…/thong-bao`; SSE
chỉ đẩy nhanh.

## 6. Phía CMS (`cms/`)

### 6.1 Stack và bố cục

Scaffold bằng `pnpm create payload-app@latest` (template `blank`, database Postgres, không
Sharp vì không có upload), rồi ghim `payload`, `@payloadcms/next`, `@payloadcms/db-postgres`,
`@payloadcms/ui`, `@payloadcms/translations` về **đúng `3.88.0`**; giữ Next 15.x mà
template chọn và ghim exact. Node ≥ 20, pnpm 9, React 19. Gỡ khỏi template: collection
`media`, `sharp`, GraphQL playground (`graphQL.disable: true`).

```
cms/
  package.json                # payload 3.88.0 + next 15 + react 19; scripts: dev(-p 3001) build start lint type-check test migrate
  payload.config.ts
  next.config.mjs             # withPayload
  scripts/start.sh            # migrate → verify migrate:status → next start (chuyển từ dự án tham chiếu)
  src/
    collections/Admins.ts
    collections/NhatKyCms.ts
    endpoints/klaw.ts         # proxy có allowlist, kiểm vai trò, stream SSE
    lib/klaw-client.ts        # fetch KLAW, chỉ chạy máy chủ; đọc KLAW_API_URL, KLAW_ADMIN_API_KEY
    lib/allowlist.ts          # bảng đường dẫn ↔ vai trò (một nguồn cho proxy và cho test)
    hooks/exposeErrorReason.ts
    hooks/ghiDangNhap.ts      # afterLogin + afterError(AuthenticationError) → NhatKyCms
    components/ChuongThongBao/   # GĐ3, chuyển từ NotificationBell
    components/DieuHuong.tsx  # afterNavLinks: 4 liên kết tới view tuỳ biến
    views/TongQuan.tsx        # thay dashboard
    views/YeuCau.tsx
    views/TaiKhoan.tsx        # danh sách + chi tiết theo ?sub=
    views/NhatKy.tsx
  app/(payload)/…             # sinh bởi create-payload-app
  tests/                      # vitest, fileParallelism: false
  migrations/                 # payload migrate:create, commit
  README.md                   # runbook local + Railway
```

`cms/` là gói pnpm độc lập trong repo KLAW (không workspace với `frontend/` chạy npm).
Người đọc mã cần biết: `frontend/` npm, `cms/` pnpm, gốc Python.

### 6.2 Collection `admins`

```ts
auth: {
  tokenExpiration: 8 * 60 * 60,     // một ca làm việc
  maxLoginAttempts: 5,
  lockTime: 10 * 60 * 1000,
  cookies: { secure: process.env.NODE_ENV === 'production', sameSite: 'Lax' },
},
versions: false,
fields: [
  { name: 'ten', type: 'text', required: true },
  { name: 'vai_tro', type: 'select', options: ['doc', 'quan_tri'], required: true, defaultValue: 'doc' },
  { name: 'hoat_dong', type: 'checkbox', defaultValue: true },
]
```

Access: `read` — mọi admin đang `hoat_dong`; `create`/`delete` — chỉ `quan_tri`; `update`
— `quan_tri` với mọi dòng, `doc` chỉ dòng của mình và **không** đổi được `vai_tro`/
`hoat_dong` (field-level `access.update`). Hook `beforeChange`/`beforeDelete` chặn hạ vai
trò hoặc vô hiệu **quản trị viên cuối cùng** (chuyển `guardLastAdmin` từ dự án tham
chiếu, rút gọn). `beforeLogin` từ chối `hoat_dong = false` với thông điệp tiếng Việt.

Người đầu tiên tạo bằng màn `create-first-user` của Payload (collection rỗng) và phải
được đặt `vai_tro = 'quan_tri'` — hook `beforeChange` ép giá trị này khi `total = 0`.

### 6.3 Collection `nhat_ky_cms`

`hanh_dong`, `boi` (email), `ip`, `chi_tiet` (json), `tao_luc`. `access.read` cho mọi
admin đang `hoat_dong` (view Nhật ký đọc qua REST `/api/nhat_ky_cms`); `access.create/
update/delete: () => false`; chỉ hook ghi với `overrideAccess: true`; `admin.hidden: true`
(xem qua view Nhật ký, không qua list view tự sinh). Ghi: `dang_nhap`, `dang_nhap_that_bai`
(qua `afterError` khi lỗi là `AuthenticationError` trên `/api/admins/login`, kèm email đã
gõ và IP), `dang_xuat`, và bản sao của mỗi thao tác ghi thành công qua proxy (`hanh_dong`
trùng tên với KLAW).

### 6.4 Proxy `/api/klaw/*` — endpoint Payload

`allowlist.ts` là bảng §5.3 chuyển sang mã: mỗi hàng `{method, duong, vaiTro}` với
`duong` là mẫu Payload (`/klaw/tai-khoan/:sub/khoa`). `endpoints: allowlist.map(taoEndpoint)`
sinh **một endpoint Payload cho mỗi hàng**, cùng một handler. Không có endpoint ký tự đại
diện, nên đường lạ tự 404 do không có route — cấu trúc cưỡng chế, không phải một phép
kiểm có thể quên. Handler, dừng ở bước đầu hỏng:

1. `req.user` rỗng hoặc `hoat_dong = false` → 401. **Không** phát request nào sang KLAW.
2. `req.routeParams.sub` (nếu có) phải là UUID → không thì 404.
3. Hàng yêu cầu `quan_tri` mà `req.user.vai_tro = 'doc'` → 403, trước khi chạm KLAW.
4. Chuyển tiếp tới `${KLAW_API_URL}/admin/${duong}` với query string nguyên vẹn, body
   nguyên vẹn, header `X-Admin-Key`, `X-Admin-Boi: req.user.email`, `X-Forwarded-For`
   IP của admin (để `nhat_ky_quan_tri.ip` là IP người bấm, không phải IP của CMS; KLAW
   chỉ tin header này khi `KLAW_TIN_PROXY_HEADER` bật — local tắt thì ghi IP của CMS,
   chấp nhận).
5. Phản hồi: chuyển mã trạng thái và thân nguyên vẹn. Với `Content-Type: text/event-stream`
   trả `new Response(res.body, { headers })` không đệm — khuôn `notificationStream.ts`.
6. Thao tác ghi (POST/PATCH) trả 2xx → ghi `nhat_ky_cms` một dòng.

KLAW 503 (khoá chưa cấu hình) → giao diện hiện đúng câu của KLAW, không dịch thành
"không có dữ liệu". KLAW không nối được → 502 "Không nối được tới KLAW." và nút Thử lại.

### 6.5 Màn hình

Bốn view tuỳ biến, mỗi view là một component máy chủ bọc `DefaultTemplate`, tự kiểm
`initPageResult.req.user` (Payload để view tuỳ biến công khai mặc định) và render một
component khách gọi `/api/klaw/*` bằng `fetch` cùng gốc (cookie đi kèm tự động).
Liên kết tới bốn view đặt ở `admin.components.afterNavLinks`. Chữ hiển thị tiếng Việt,
tuân quy ước từ ngữ của KLAW (không "hệ thống", không "máy chủ trả về"; xưng "tôi";
`pro` hiện "Cá nhân", `free` hiện "Miễn phí", tên lấy từ `GET /admin/goi`).

**Tổng quan** (`/admin`, thay dashboard): bảy ô số từ `/admin/tong-quan`; ô "Yêu cầu chờ
duyệt" và "Hết hạn trong 7 ngày" là liên kết sang màn tương ứng đã lọc.

**Yêu cầu** (`/admin/yeu-cau`): tab Chờ duyệt / Đã duyệt / Từ chối; dòng: email, gói
hiện tại, loại (Nâng gói / Gia hạn), thời điểm tạo, huy hiệu "đang khoá" nếu có. Nút
Duyệt và Từ chối chỉ hiện với `quan_tri` và tab Chờ duyệt. Từ chối mở hộp nhập lý do
(bắt buộc). 409 → "Yêu cầu này vừa được người khác xử lý." rồi tải lại; 423 → "Tài khoản
đang bị khoá, mở khoá trước khi duyệt." với liên kết sang chi tiết tài khoản.

**Tài khoản** (`/admin/tai-khoan`, `?sub=` mở chi tiết): ô tìm email; bảng: email, gói,
hạn, trạng thái (Bình thường / Đang khoá), ngày tham gia, số phiên, lượt 30 ngày. Chi
tiết: thẻ định danh + trạng thái khoá và lý do; thanh đo mức dùng (tái dùng hình
`HoSoResponse`); lịch sử yêu cầu; ba hành động cho `quan_tri`: Đặt gói (chọn gói từ
`/admin/goi`, số ngày; để trống = vô thời hạn với gói trả phí), Thu hồi gói, Khoá / Mở
khoá. **Cả bốn hành động đều bắt buộc lý do** trong hộp xác nhận, và hộp xác nhận nêu rõ
hậu quả ("Người dùng sẽ không hỏi và soạn được cho tới khi mở khoá."). Với đặt gói và mở
khoá, hộp nói rõ "Lý do chỉ ghi vào nhật ký, người dùng không thấy."

Màn chi tiết **không** có chỗ nào hiện nội dung hội thoại; không có API để vượt ranh giới.

**Nhật ký** (`/admin/nhat-ky`): bảng từ `/admin/nhat-ky`, lọc khoảng thời gian, hành
động, đối tượng; phân trang; nút Xuất CSV gọi cùng endpoint với `dinh_dang=csv` và tải
tệp. **Trần xuất công bố ngay cạnh nút**: "Xuất tối đa 5.000 dòng mỗi lần theo bộ lọc
đang chọn; thu hẹp khoảng thời gian nếu cần đủ" (GitHub giới hạn 100 MB mỗi 10 phút,
Google 100.000 dòng — đề xuất B của khảo sát). Mở cho cả hai vai trò — đây là lý do vai
`doc` tồn tại. Tab thứ hai "Nhật ký CMS" đọc `nhat_ky_cms` qua REST (đăng nhập, đăng
nhập sai).

**Chính sách lưu trữ nhật ký** (đề xuất C của khảo sát, viết ra chứ chưa thi công cơ chế):
KLAW giữ `nhat_ky_quan_tri` và `nhat_ky_cms` **vô thời hạn**, không có job dọn; bản sao
giữ được duy nhất là tệp CSV do admin tự xuất, khuyến nghị mỗi tháng một lần. Stream ra
kho ngoài (S3, webhook) nằm ngoài phạm vi. Câu này xuất hiện ở `cms/README.md` và ở chân
màn Nhật ký.

**Chuông** (giai đoạn 3, slot `actions`): chuyển `NotificationBell` gần nguyên vẹn; nguồn
`/api/klaw/thong-bao` và `/api/klaw/thong-bao/luong`. Ở CMS dùng được `EventSource` vì
xác thực bằng cookie cùng gốc, không cần header tuỳ ý. Badge là số chưa đọc; nguồn sự
thật là lần gọi danh sách; `EventSource` tự nối lại nên không viết logic thử lại.

### 6.6 Biến môi trường

| Biến | Ở đâu | Việc |
|---|---|---|
| `DATABASE_URI` | `cms/.env` | `postgres://…/klaw_cms` — database riêng |
| `PAYLOAD_SECRET` | `cms/.env` | Khoá ký phiên; `openssl rand -hex 32` |
| `PAYLOAD_PUBLIC_SERVER_URL` | `cms/.env` (prod) | Gốc công khai của CMS; local để trống |
| `KLAW_API_URL` | `cms/.env` | `http://127.0.0.1:8000/api/v1` local; URL nội bộ Railway khi deploy |
| `KLAW_ADMIN_API_KEY` | `cms/.env` **và** `.env.local` của KLAW | Cùng một giá trị hai phía; chỉ đọc phía máy chủ |

`cors` và `csrf` của Payload: production = `[PAYLOAD_PUBLIC_SERVER_URL]`; development =
`[]` cho `csrf` (lý do ghi trong config dự án tham chiếu: allowlist làm rớt phiên trên
LAN plain-HTTP) và `['http://localhost:3001']` cho `cors`. CMS không cần CORS tới KLAW
FE — hai ứng dụng không nói chuyện với nhau.

## 7. Frontend KLAW (người dùng)

- `ModalNangGoi`: khi `trang_thai = 'tu_choi'` hiện "Yêu cầu trước bị từ chối: {ly_do}"
  và cho gửi lại (unique index chỉ chặn `cho_duyet`).
- Thẻ tài khoản bị khoá: `BaoLoi` nhận 403 `LOI_TAI_KHOAN_KHOA` → thẻ trên đầu dòng chat
  với câu của máy chủ và nút "Liên hệ hỗ trợ" (mailto địa chỉ trong `bang-gia.tsx`);
  ô nhập khoá; tra cứu và soát vẫn mở. `useHanMuc` đọc `bi_khoa` để vẽ thẻ ngay khi
  tải, không đợi tới lượt hỏi đầu.
- Giai đoạn 3: `use-thong-bao.ts` (đếm, danh sách, đánh dấu, SSE bằng bộ đọc
  `fetch` + `ReadableStream` sẵn có), `ChuongThongBao.tsx` cạnh `TheTaiKhoan` trong
  `AppShell`, chỉ khi `daDangNhap`; `role="menu"`, Escape đóng, trả tiêu điểm — cùng
  khuôn `MenuTaiKhoan`. Bấm thông báo `yeu_cau_duyet`/`yeu_cau_tu_choi` mở `/tai-khoan`.

## 8. Vận hành

### 8.1 Local

```
createdb -h localhost -U postgres klaw_cms          # một lần, cùng container klaw-db-1
cd cms && pnpm install && cp .env.example .env      # điền 5 biến §6.6
pnpm dev                                            # next dev -p 3001, push schema ở dev
# KLAW: thêm KLAW_ADMIN_API_KEY vào .env.local, khởi động lại uvicorn
```

Mở `http://localhost:3001/admin` → `create-first-user` → tài khoản đầu là `quan_tri`.

### 8.2 Railway (đích, khi KLAW được deploy)

- Service `klaw-cms`, Root Directory `cms`, builder Railpack, start `pnpm start`
  (= `bash scripts/start.sh`: migrate, verify, `next start`). Healthcheck `/api/admins/me`
  trả 200 với `user: null` là sống (Payload không trả 401 ở `me`).
- Database: cùng service Postgres với KLAW; `CREATE DATABASE klaw_cms` một lần qua
  `railway connect`. `DATABASE_URI` là variable reference tới service Postgres với tên
  database đổi.
- `KLAW_API_URL` dùng private networking `http://klaw-api.railway.internal:8000/api/v1`;
  `KLAW_TIN_PROXY_HEADER=true` và `KLAW_SO_HOP_PROXY_TIN_CAY` đúng số hop ở KLAW để IP
  admin được ghi đúng.
- RAM: Payload + Next ước 512 MB – 1 GB; ghi chú khoá luận tính ~10 USD/GB/tháng → đây là
  chi phí định kỳ thật, không phải miễn phí.

### 8.3 CI

Job `cms` mới trong `.github/workflows/ci.yml`, chạy khi có thay đổi dưới `cms/**`:
service container Postgres 16, `pnpm install --frozen-lockfile`, `pnpm lint`,
`pnpm type-check`, `pnpm test`, `pnpm build`. Không đụng job Python. Không cài hook git,
không đổi branch protection (ngoài thẩm quyền, theo `docs/WORKFLOW.md`).

## 9. Kiểm chứng

**KLAW (pytest, `tests/test_api/test_admin_*.py`, `tests/test_services/test_nang_goi_duyet.py`):**

- Migration 022 chạy hai lần xanh; `xu_ly_boi` là `text` sau khi chạy.
- `duyet` hai lần cùng `tham_chieu` chỉ cộng chu kỳ một lần — test chính.
- `nang_goi` tính từ `now`; `gia_han` cộng dồn từ hạn còn hiệu lực; hạn đã qua tính từ `now`.
- Hai `duyet` song song trên cùng yêu cầu: một thắng, một 409.
- `duyet` cho người đang khoá → 423, không đổi `users`.
- `tu_choi` lưu `ly_do`; `GET /nang-goi/yeu-cau` của người đó trả `ly_do`; gửi yêu cầu
  mới sau từ chối → 201.
- `dat_goi` với `so_ngay=None` → `plan_het_han IS NULL`; `thu_hoi` khi đang Free → 409.
- `khoa` → `/tra-cuu` 403 với câu khoá, `/soan-thao` 403, `/ho-so` 403, `/han-muc` 200 với
  `bi_khoa: true`, `/van-ban` và `/soat` 200; `mo_khoa` → trở lại bình thường; `khoa` hai
  lần → 409.
- `/admin/*` không khoá → 401 và có dòng `xac_thuc_that_bai`; `KLAW_ADMIN_API_KEY` rỗng →
  503; thiếu `X-Admin-Boi` → 400; vượt trần IP → 429.
- `tong_quan` đếm đúng trên dữ liệu dựng sẵn (một Pro hiệu lực, một hết hạn, một khoá, một
  yêu cầu chờ).
- `GET /admin/nhat-ky?dinh_dang=csv` cùng số dòng với JSON cùng bộ lọc; `Content-Disposition` attachment.
- Grep trong test: không file nào trong `src/` chứa `UPDATE nhat_ky_quan_tri`, `DELETE FROM
  nhat_ky_quan_tri`; ngoài `src/services/nang_goi.py` không file nào trong `src/` chứa
  `UPDATE users SET plan`.
- Bộ test khách, hạn mức, tài khoản hiện có vẫn xanh (cổng công khai không đổi).
- Giai đoạn 3: `tao_yeu_cau` hai lần → một thông báo admin; `danh_dau_da_doc` với id của
  người khác → 0 dòng; SSE phát `so_chua_doc` khi có dòng mới, có `: ping`.

**CMS (vitest + kiểm bằng tay ghi vào plan):**

- `allowlist.ts`: mọi hàng của bảng §5.3 có mặt (test đếm số hàng và so từng cặp
  method/đường); `GET /api/klaw/duong-la` → 404; `sub` không phải UUID → 404.
- Proxy không cookie → 401 và **không** gọi KLAW (mock `fetch`, đếm 0 lời gọi); admin
  `doc` POST duyệt → 403 và 0 lời gọi; admin `quan_tri` → 1 lời gọi với đúng hai header.
- `admins`: `doc` không đổi được `vai_tro` của mình; không hạ được `quan_tri` cuối cùng;
  `hoat_dong = false` không đăng nhập được; sai mật khẩu 5 lần → khoá 10 phút và có 5
  dòng `dang_nhap_that_bai`.
- `grep -r KLAW_ADMIN_API_KEY cms/.next/static` rỗng sau `pnpm build`.
- `payload migrate` trên `klaw_cms` sạch tạo bảng; đếm bảng trong database `klaw` trước và
  sau bằng nhau.
- Bằng tay trên Chrome (ghi ảnh vào `.tham-dinh-shots/`): duyệt một yêu cầu → `users.plan`
  đổi, người dùng thấy "Cá nhân · còn 30 ngày"; bấm Duyệt hai lần nhanh → thông điệp 409,
  gói không cộng thêm; khoá tài khoản → ứng dụng KLAW của người đó hiện thẻ khoá; xuất
  CSV đúng số dòng; giai đoạn 3: badge tăng trong vài giây khi có yêu cầu mới.
- `pnpm lint`, `pnpm type-check`, `pnpm test`, `pnpm build` xanh trong CI.

## 10. Chi phí và rủi ro đã biết

- Service Railway thứ hai với RAM thật (§8.2). Cắt được bằng cách chỉ chạy CMS local khi
  cần duyệt — kiến trúc không đổi, chỉ đổi nơi chạy.
- Payload 3.88 là bản ổn định nhưng 4.0 sắp ra; chuyển sang 4.0 sau này đụng chủ yếu vào
  custom view và SCSS của chuông. Bốn view đều mỏng (gọi API, vẽ bảng), chi phí chuyển
  thấp.
- Hai hệ công cụ (pnpm ở `cms/`, npm ở `frontend/`) cạnh Python. Ghi rõ ở `cms/README.md`
  và `docs/README.md`.
- `X-Forwarded-For` từ CMS chỉ được KLAW tin khi cờ proxy bật; local nhật ký ghi IP của
  CMS. Chấp nhận, nói rõ trong giao diện Nhật ký ("IP qua CMS").
- Khoá tài khoản không vô hiệu phiên Supabase (không có service-role key, cố ý). Người bị
  khoá vẫn đăng nhập được vào vỏ ứng dụng và thấy thẻ khoá — đó là hành vi mong muốn.

## 11. Ngoài phạm vi

- Thanh toán trực tuyến (VietQR, PayOS, Stripe) và mọi thứ liên quan tiền thật, hoàn tiền,
  hoá đơn. Gói này chỉ chuẩn bị `duyet(..., nguon='thanh_toan', tham_chieu=<mã giao dịch>)`.
- Xoá tài khoản (cần service-role key của Supabase và chính sách lưu trữ).
- Gửi email thật cho người dùng hay admin.
- Quản trị nội dung: KLAW không có nội dung biên tập; CMS này chỉ quản lý tài khoản.
- Đồng bộ `cms.admins` với `klaw.users`: hai tập người khác nhau, cố ý không nối.
- Sửa hạn mức gói từ CMS: hạn mức là YAML có kiểm tra fail-loud lúc khởi động; CMS chỉ
  đọc qua `/admin/goi`.
- Đọc nội dung hội thoại của người dùng — loại trừ vĩnh viễn khỏi đường quản trị.

## 12. Thi công

Ba giai đoạn, mỗi giai đoạn tự đứng và kiểm chứng được; giai đoạn 3 cắt được.

1. **KLAW backend** (worktree riêng): migration 022, `nang_goi` bốn hàm, `tai_khoan_qt`,
   `nhat_ky`, cổng `kiem_admin_key`, router `/admin` (trừ ba endpoint thông báo), khoá ở
   `bao_ve`, `ly_do` và `bi_khoa` ở endpoint người dùng, test. Kết thúc: toàn bộ đường
   quản trị chạy được bằng `curl`.
2. **CMS Payload** (thư mục `cms/`, có thể song song với 1 sau task hợp đồng): scaffold
   3.88, `admins`, `nhat_ky_cms`, allowlist + proxy, bốn view, `start.sh`, CI, README.
   Kết thúc: duyệt một yêu cầu thật từ giao diện.
3. **Thông báo hai chiều**: `thong_bao.py`, ba endpoint admin + ba endpoint người dùng,
   SSE, chuông CMS, chuông FE, thẻ từ chối và thẻ khoá ở FE.

Task hợp đồng đầu tiên (chạy trước, chung cho 1 và 2): bảng endpoint §5.3 thành
`allowlist.ts` và `routes_admin.py` rỗng cùng model Pydantic; hai luồng cùng đọc một hình.
Kế hoạch thi công: `docs/superpowers/plans/2026-09-08-cms-quan-ly-tai-khoan.md` — 18 task
(7 KLAW, 7 CMS, 1 frontend, 3 thông báo), mỗi task một implementer và một review như gói 2A.
