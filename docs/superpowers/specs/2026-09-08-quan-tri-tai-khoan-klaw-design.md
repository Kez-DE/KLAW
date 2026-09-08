# Gói 2B-1 — Đường quản trị tài khoản phía KLAW

Ngày: 2026-09-08 · Trạng thái: chờ chủ dự án duyệt

Gói này dựng phần backend để một CMS bên ngoài quản lý tài khoản KLAW, và dựng
thông báo hai chiều. Giao diện quản trị nằm ở gói 2B-2 (Payload CMS). Sau gói
này, toàn bộ đường quản trị chạy được bằng `curl`, không cần CMS.

## 1. Mục tiêu

- Một CMS riêng, đăng nhập riêng, gọi được API KLAW để duyệt yêu cầu nâng gói và
  sửa gói của một tài khoản.
- Một đường nâng gói **duy nhất**, chịu được gọi lặp, để sau này webhook thanh
  toán gọi đúng hàm đó mà không viết lại logic.
- Thông báo hai chiều: admin biết có yêu cầu mới; người dùng biết yêu cầu của
  mình được duyệt hay từ chối.
- Không đụng cổng công khai: khách chưa đăng nhập và người dùng thường không đổi
  hành vi một chút nào.

## 2. Hiện trạng

- `users` có sáu cột: `sub`, `email`, `plan`, `created_at`, `last_seen_at`,
  `plan_het_han`. **Không có cột vai trò**, và gói này cố ý không thêm.
- `yeu_cau_nang_goi` (migration 021) có `id`, `user_sub`, `loai`, `goi_hien_tai`,
  `goi_muon`, `trang_thai`, `tao_luc`, `xu_ly_luc`, `xu_ly_boi`. Ba cột cuối
  **luôn rỗng** vì chưa có đường duyệt.
- `src/services/nang_goi.py` có `tao_yeu_cau(sub, goi_muon)`, `moi_nhat(sub)`,
  `GIA_HAN_TRUOC_NGAY = 7` và bốn ngoại lệ `GoiKhongHopLe`, `GoiConHieuLuc`,
  `DangCho`, `ChuaCoHoSo`. Không có hàm duyệt.
- `bao_ve.kiem_api_key` là **cổng toàn cục**: đặt `KLAW_API_KEY` thì MỌI request
  phải mang `X-API-Key`, kể cả khách trình duyệt. Nên khoá đó không dùng làm
  danh tính cho CMS được.
- SSE đã có ở `routes_luong.py`: `StreamingResponse`, khung
  `event: <ten>\ndata: <json>\n\n` qua hàm `_sse`, nhịp tim bằng dòng `: ping`.
  Client là `fetch` + `ReadableStream` (`api.ts` ghi rõ không dùng `EventSource`
  vì nó không gửi được header tuỳ ý).
- Migration mới nhất là `021_nang_goi.sql`; gói này dùng `022`.

## 3. Quyết định

**Vai trò admin không sống trong KLAW.** Danh tính admin nằm ở CMS (gói 2B-2).
KLAW chỉ cần biết "lời gọi này đến từ CMS đã được tin" và "ai là người bấm nút"
để ghi vào `xu_ly_boi`. Vì vậy không thêm `users.role`, không thêm cổng vai trò.

**Khoá dịch vụ riêng cho `/admin/*`.** Thêm `KLAW_ADMIN_API_KEY`. Chỉ router
`/admin` kiểm nó, so sánh bằng `secrets.compare_digest` như `kiem_api_key`. Cổng
công khai không đổi. Rỗng = router `/admin` **từ chối toàn bộ** (503), chứ không
mở toang — ngược quy ước của `KLAW_API_KEY`, và cố ý: một đường quản trị mở khi
quên cấu hình là hỏng nặng hơn một đường quản trị đóng.

**Một kho thông báo, hai người đọc.** KLAW sở hữu toàn bộ bảng `thong_bao`. Sự
kiện sinh ra ở KLAW thì KLAW ghi. CMS đọc qua API chứ không ghi thẳng vào DB.

**Duyệt là idempotent theo `tham_chieu`.** Cùng một `tham_chieu` gọi lại không
cộng thêm chu kỳ. Đây là điều kiện để webhook thanh toán dùng lại được.

## 4. Dữ liệu — migration `022_quan_tri.sql`

```sql
CREATE TABLE IF NOT EXISTS thong_bao (
  id           BIGSERIAL PRIMARY KEY,
  nguoi_nhan   UUID REFERENCES users(sub) ON DELETE CASCADE,  -- NULL = gửi admin
  loai         TEXT NOT NULL CHECK (loai IN (
                 'yeu_cau_moi', 'yeu_cau_duyet', 'yeu_cau_tu_choi', 'sap_het_han')),
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

CREATE TABLE IF NOT EXISTS nhat_ky_quan_tri (
  id          BIGSERIAL PRIMARY KEY,
  hanh_dong   TEXT NOT NULL,
  doi_tuong   UUID,
  chi_tiet    JSONB NOT NULL DEFAULT '{}'::jsonb,
  boi         TEXT NOT NULL,
  tao_luc     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_tao_luc ON nhat_ky_quan_tri (tao_luc DESC);

ALTER TABLE yeu_cau_nang_goi
  ADD COLUMN IF NOT EXISTS nguon TEXT,          -- 'admin' | 'thanh_toan'
  ADD COLUMN IF NOT EXISTS tham_chieu TEXT;     -- id yêu cầu hoặc id giao dịch
CREATE UNIQUE INDEX IF NOT EXISTS ux_yeu_cau_tham_chieu
  ON yeu_cau_nang_goi (tham_chieu) WHERE tham_chieu IS NOT NULL;
```

`khoa_gom` chặn nhân bản: yêu cầu lặp của cùng một người trong lúc chưa xử lý
không tạo thêm dòng. Quy ước: `yeu_cau:{user_sub}` cho thông báo admin,
`ket_qua:{yeu_cau_id}` cho thông báo người dùng.

`nguon` và `tham_chieu` nằm trên `yeu_cau_nang_goi` chứ không ở bảng riêng, vì
một lần duyệt luôn gắn với đúng một yêu cầu. Chỉ mục duy nhất trên `tham_chieu`
là thứ làm cho việc gọi lặp trở nên vô hại.

`nhat_ky_quan_tri.boi` là chuỗi tự do (email admin từ CMS), không phải khoá
ngoại, vì admin không phải người dùng KLAW.

## 5. Dịch vụ

### 5.1 `nang_goi.duyet` — đường nâng gói duy nhất

```python
def duyet(yeu_cau_id: int, nguon: str, tham_chieu: str, boi: str) -> dict:
    """Duyệt một yêu cầu và nâng gói. Idempotent theo `tham_chieu`.

    `nguon` ∈ {'admin', 'thanh_toan'}. Gọi lại với cùng `tham_chieu` trả về
    kết quả cũ, KHÔNG cộng thêm chu kỳ.
    """
```

Trong một transaction:

1. Nếu đã có dòng `yeu_cau_nang_goi` với `tham_chieu` này và `trang_thai =
   'da_duyet'`, trả về ngay trạng thái hiện tại. Không ghi gì thêm.
2. Khoá dòng yêu cầu (`SELECT … FOR UPDATE`). Nếu `trang_thai` không phải
   `cho_duyet`, ném `DaXuLy`.
3. Tính hạn mới: `moc = max(plan_het_han, now())` khi `plan_het_han` còn hiệu
   lực, ngược lại `now()`; `plan_het_han = moc + chu_ky_pro_ngay ngày`. Số ngày
   lấy từ `config/han_muc.yaml` (`chu_ky_pro_ngay: 30`), không viết cứng.
4. `UPDATE users SET plan = :goi, plan_het_han = :han WHERE sub = :sub`.
5. `UPDATE yeu_cau_nang_goi SET trang_thai='da_duyet', xu_ly_luc=now(),
   xu_ly_boi=:boi, nguon=:nguon, tham_chieu=:tham_chieu`.
6. Ghi `nhat_ky_quan_tri`.
7. Ghi `thong_bao` cho `nguoi_nhan = user_sub`, loại `yeu_cau_duyet`.
8. Đánh `het_hieu_luc = TRUE` cho thông báo admin cùng `khoa_gom`.

`tu_choi(yeu_cau_id, ly_do, boi)` đi cùng khuôn: đổi trạng thái, ghi nhật ký,
ghi thông báo loại `yeu_cau_tu_choi`, vô hiệu thông báo admin. Không đụng `users`.

### 5.2 `nang_goi.tao_yeu_cau` — thêm một việc

Sau khi tạo yêu cầu thành công, ghi `thong_bao` với `nguoi_nhan = NULL`, loại
`yeu_cau_moi`, `khoa_gom = f"yeu_cau:{sub}"`. Xung đột chỉ mục duy nhất nghĩa là
đã có thông báo chưa xử lý cho người này — nuốt xung đột, không nhân bản.

### 5.3 `thong_bao.py` (mới)

- `danh_sach(nguoi_nhan: str | None, chi_chua_doc: bool, limit: int) -> list[dict]`
- `dem_chua_doc(nguoi_nhan: str | None) -> int`
- `danh_dau_da_doc(ids: list[int], nguoi_nhan: str | None) -> int` — chỉ đánh dấu
  dòng đúng người nhận; ai đó gửi id của người khác thì không có tác dụng.
- `ghi(nguoi_nhan, loai, tieu_de, noi_dung, duong_dan, khoa_gom) -> int | None` —
  trả `None` khi đụng khoá gộp.

Quy ước `nguoi_nhan is None` nghĩa là hộp thư admin. Mọi hàm nhận `None` một
cách tường minh, không dùng chuỗi rỗng hay giá trị đặc biệt.

## 6. Endpoint

### 6.1 Router `/admin` — `src/api/routes_admin.py`

Cổng: `Depends(kiem_admin_key)`. Header `X-Admin-Key` phải khớp
`KLAW_ADMIN_API_KEY`; thiếu cấu hình → 503 với câu "Đường quản trị chưa được cấu
hình."; sai khoá → 401. Mọi endpoint nhận thêm header `X-Admin-Boi` (email admin
từ CMS) và từ chối 400 nếu thiếu, vì không có nó thì không ghi được `xu_ly_boi`.

| Method | Đường dẫn | Việc |
|---|---|---|
| GET | `/admin/yeu-cau` | Danh sách yêu cầu, lọc `trang_thai`, phân trang `limit`/`offset`, kèm email và gói hiện tại của người yêu cầu |
| POST | `/admin/yeu-cau/{id}/duyet` | Gọi `duyet(id, 'admin', f'yeu_cau:{id}', boi)` → 200 kèm gói và hạn mới |
| POST | `/admin/yeu-cau/{id}/tu-choi` | Body `{ly_do}` → 200 |
| GET | `/admin/tai-khoan` | Tìm theo email (`q`), phân trang; trả `sub`, `email`, `plan`, `plan_het_han`, `tao_luc`, số phiên, số lượt 30 ngày |
| GET | `/admin/tai-khoan/{sub}` | Chi tiết một tài khoản: đúng hình `HoSoResponse` sẵn có, cộng lịch sử yêu cầu |
| PATCH | `/admin/tai-khoan/{sub}/goi` | Body `{plan, so_ngay}` → đặt gói tay, ghi nhật ký, ghi thông báo cho người dùng |
| GET | `/admin/thong-bao` | Hộp thư admin (`nguoi_nhan IS NULL`), `chi_chua_doc` tuỳ chọn |
| POST | `/admin/thong-bao/da-doc` | Body `{ids}` |
| GET | `/admin/thong-bao/luong` | SSE hộp thư admin |

**Không có** endpoint nào đọc nội dung `hoi_thoai` hay `luot_hoi_thoai`. Admin
thấy *bao nhiêu lượt*, không thấy *hỏi gì*. Đây là ranh giới cố ý, không phải
thiếu sót; ai muốn đổi phải sửa spec này trước.

### 6.2 Thông báo cho người dùng — thêm vào `routes_tai_khoan.py`

| Method | Đường dẫn | Việc |
|---|---|---|
| GET | `/thong-bao` | Thông báo của chính người gọi, sau `nguoi_dung_bat_buoc` |
| POST | `/thong-bao/da-doc` | Body `{ids}` |
| GET | `/thong-bao/luong` | SSE cho chính người gọi |

### 6.3 Hình SSE

Dùng lại khuôn của `routes_luong.py`: `StreamingResponse` với
`media_type="text/event-stream"`, khung `event: <ten>\ndata: <json>\n\n`, nhịp
tim `: ping` mỗi 15 giây. Hai loại sự kiện: `so_chua_doc` (số nguyên) và
`thong_bao_moi` (một dòng thông báo). Server hỏi DB mỗi 5 giây và chỉ phát khi
số đếm đổi — đây là polling ở phía máy chủ, đổi lấy việc client không phải hỏi.
Kết nối đóng sau 30 phút để không giữ tài nguyên vô hạn; client tự nối lại.

## 7. Frontend KLAW — chuông cho người dùng

- `frontend/src/hooks/use-thong-bao.ts`: đếm chưa đọc, danh sách, đánh dấu đã
  đọc, và một kết nối SSE dùng bộ đọc `fetch` + `ReadableStream` sẵn có trong
  `api.ts`. Nguồn sự thật là lần gọi `GET`; SSE chỉ để đẩy nhanh.
- `frontend/src/components/tai-khoan/ChuongThongBao.tsx`: nút chuông có badge,
  popover danh sách, `role="menu"`, Escape đóng, trả tiêu điểm về nút — cùng
  khuôn `MenuTaiKhoan` đã có.
- Gắn vào `AppShell` cạnh thẻ tài khoản, chỉ hiện khi `daDangNhap`.
- Bấm một thông báo loại `yeu_cau_duyet` thì mở `/tai-khoan`.

## 8. Lỗi và an toàn

- Khoá quản trị sai hoặc thiếu: 401, thân câu không tiết lộ khoá có tồn tại hay
  không.
- Duyệt một yêu cầu đã xử lý: 409 "Yêu cầu này đã được xử lý."
- Duyệt một yêu cầu không tồn tại: 404.
- `PATCH .../goi` với `plan` lạ: 422, danh sách gói hợp lệ đọc từ YAML.
- Mọi endpoint `/admin` ghi nhật ký kể cả khi ném lỗi, trừ lỗi xác thực.
- Chữ hiển thị không chứa "hệ thống", "không diễn giải", "chưa đủ căn cứ", "truy
  hồi", "database", "để bạn tự đối chiếu", "máy chủ trả về"; xưng "tôi". Gói
  `pro` hiển thị "Cá nhân".

## 9. Kiểm chứng

- `duyet` gọi hai lần cùng `tham_chieu` chỉ cộng chu kỳ một lần — test chính của
  gói này.
- Duyệt khi `plan_het_han` còn hiệu lực thì cộng dồn; đã hết thì tính từ hiện tại.
- Hai lời gọi `duyet` chạy song song trên cùng yêu cầu: một thắng, một nhận 409.
- `tao_yeu_cau` hai lần liên tiếp chỉ sinh một thông báo admin.
- `danh_dau_da_doc` với id của người khác không đổi dòng nào.
- `/admin/*` không có khoá → 401; `KLAW_ADMIN_API_KEY` rỗng → 503.
- Cổng công khai không đổi: bộ test khách và hạn mức hiện có vẫn xanh.
- Chuông người dùng: `npm run typecheck`, `lint`, `build`, và một script kiểm cho
  logic gộp và đếm.

## 10. Ngoài phạm vi

- Giao diện quản trị (gói 2B-2).
- Webhook thanh toán. Gói này chỉ chuẩn bị chỗ cắm:
  `duyet(..., nguon='thanh_toan', ...)`.
- Gửi email thật.
- Xoá tài khoản, đổi ngôn ngữ.
- Đọc nội dung hội thoại của người dùng — cố ý loại trừ vĩnh viễn khỏi đường
  quản trị.
