# Lịch sử hội thoại theo tài khoản — thiết kế (gói 1/3)

Ngày: 2026-09-07. Nhánh: `feat/tro-ly-phap-luat` (sau PR #1). Trạng thái: đã duyệt hướng A và
các quyết định ở §3.

Ba gói được tách từ một yêu cầu: **(1) lịch sử hội thoại theo tài khoản** (spec này),
(2) trang tài khoản + vai trò user/admin, (3) workspace = phiên chat + bản thảo đã lưu.
Gói 2 và 3 có spec riêng sau; §10 ghi các quyết định đã chốt cho chúng để không hỏi lại.

## 1. Mục tiêu

Người đã đăng nhập thấy các phiên hội thoại của mình, mở lại một phiên và hỏi tiếp trong
đó như ChatGPT hay Claude; card trả lời mở lại y hệt lúc trả lời, thẻ trích dẫn vẫn bấm
được. Máy chủ giữ dữ liệu; gói free giữ 10 phiên gần nhất, gói pro không giới hạn.

## 2. Hiện trạng

- `users(sub, email, plan, created_at, last_seen_at)`; `plan` ∈ {free, pro}, mặc định free
  (`config/han_muc.yaml`, `goi_mac_dinh`). Không có cột vai trò.
- `traces` ghi telemetry từng lượt kèm `user_sub` và `query`, không ghi câu trả lời.
  `answer_cache.tra_loi` lưu payload theo câu hỏi chuẩn hoá, không theo người.
- Frontend giữ hội thoại trong bộ nhớ trang (`luuTru` ở `dung-thu.tsx`), gửi tối đa ba
  lượt gần nhất lên máy chủ dưới dạng `lich_su` (`LuotTruoc{cau_hoi, tra_loi ≤2000,
  duong_dan ≤50}`); `giai_nghia` chỉ chạy khi `lich_su` khác rỗng; câu nối tiếp không đi
  qua cache. Cột "Lịch sử phiên" chỉ liệt kê câu hỏi của phiên trình duyệt hiện tại.
- `POST /tra-cuu/luong` (SSE): `bat_dau{trace_id, config_name, cac_buoc}` → `buoc`… →
  `ket_qua` (payload = `TraCuuResponse`) hoặc `loi`. `_chay_nen` ghi traces best-effort.
- Xác thực: `cong_bao_ve` trả `sub` hoặc `None` khi Supabase chưa cấu hình; test có
  fixture `cai_dat`, `khoa_ky`, `_bearer(khoa, sub)` (`tests/test_api/test_xac_thuc_han_muc.py`).

## 3. Quyết định của chủ sản phẩm

| # | Câu hỏi | Quyết định |
|---|---|---|
| 1 | Thứ tự ba gói | Lịch sử chat → tài khoản/vai trò → workspace. |
| 2 | Lưu gì mỗi lượt | Toàn bộ payload `TraCuuResponse` (JSON) + câu hỏi + `trace_id`. |
| 3 | Hướng kỹ thuật | A: máy chủ sở hữu phiên; endpoint stream nhận `hoi_thoai_id`, tự tạo phiên, tự nạp ngữ cảnh, tự ghi lượt. Không lưu qua Supabase SDK (dữ liệu ở lại Postgres của KLAW, quyết định của migration 012). |
| 4 | Bậc tài khoản | Tài khoản đăng nhập mặc định gói free; có đường nâng lên pro (đổi `users.plan`; thanh toán chưa có, admin đổi ở gói 2). Người chưa đăng nhập không có lịch sử. |
| 5 | Hạn mức phiên | free giữ **10 phiên gần nhất**, phiên cũ hơn bị **ẩn** (không xoá; nâng gói thì hiện lại); pro không giới hạn. Số đặt trong `config/han_muc.yaml`, cùng chỗ với hạn mức tháng. |
| 6 | Vai trò | Hai vai trò user/admin — làm ở gói 2; gói này không thêm cột `role`. |

## 4. Dữ liệu

### 4.1 Migration `migrations/020_hoi_thoai.sql`

```sql
CREATE TABLE IF NOT EXISTS hoi_thoai (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_sub     UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    tieu_de      TEXT NOT NULL,
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    cap_nhat_luc TIMESTAMPTZ NOT NULL DEFAULT now(),
    xoa_luc      TIMESTAMPTZ            -- xoá mềm; NULL = còn
);
CREATE INDEX IF NOT EXISTS ix_hoi_thoai_user_cap_nhat
    ON hoi_thoai(user_sub, cap_nhat_luc DESC) WHERE xoa_luc IS NULL;

CREATE TABLE IF NOT EXISTS luot_hoi_thoai (
    id           BIGSERIAL PRIMARY KEY,
    hoi_thoai_id UUID NOT NULL REFERENCES hoi_thoai(id) ON DELETE CASCADE,
    thu_tu       INTEGER NOT NULL,
    cau_hoi      TEXT NOT NULL,
    tra_loi      JSONB NOT NULL,       -- nguyên payload TraCuuResponse
    trace_id     TEXT,
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (hoi_thoai_id, thu_tu)
);
```

`pgcrypto`/`gen_random_uuid()` có sẵn trên Postgres 13+. `lifespan` áp thêm `"020"` cạnh
`"019"` (một danh sách, không phải hai lời gọi rời).

### 4.2 Hạn mức phiên — `config/han_muc.yaml`

Thêm khoá cùng cấp với `goi`:

```yaml
# Số phiên hội thoại gần nhất được HIỆN cho mỗi gói. Phiên cũ hơn không bị xoá,
# chỉ ẩn khỏi danh sách và không mở/hỏi tiếp được; nâng gói thì hiện lại.
# Cùng quy ước với `goi`: 0 = không hiện phiên nào; "không giới hạn" = một số lớn.
phien_luu:
  free: 10
  pro: 100000
```

`bao_ve._doc_han_muc()` kiểm khoá này có đủ mọi gói trong `goi` (fail loud như hiện nay).
Hàm mới `bao_ve.phien_luu_toi_da(plan) -> int` cùng khuôn `han_muc_thang`.

### 4.3 Quy tắc hiển thị

"Hiện" = N phiên mới nhất theo `cap_nhat_luc` trong các phiên chưa xoá của người đó, N =
`phien_luu_toi_da(plan)`. Phiên ngoài N là "ẩn": không có trong danh sách; mở/hỏi tiếp/đổi
tên trả **403** với `detail` chuỗi nói rõ (FE nhận biết theo mã 403). Xoá phiên hiện thì phiên ẩn
gần nhất lại hiện. Hỏi trong một phiên hiện làm nó lên đầu (đổi `cap_nhat_luc`).

Tiêu đề mặc định = câu hỏi đầu, cắt còn 80 ký tự tại ranh giới từ, thêm "…" nếu cắt.

## 5. Backend

### 5.1 Dịch vụ `src/services/hoi_thoai.py`

`tao_phien(sub, cau_hoi) -> str`; `lay_phien(sub, id) -> dict | None` (None khi không của
`sub` hoặc đã xoá); `phien_bi_an(sub, plan, id) -> bool`; `lich_su_gan_nhat(id, n=3) ->
list[dict]` (mỗi dict đúng hình `LuotTruoc`: `cau_hoi`, `tra_loi` = `answer` cắt 2000,
`duong_dan` = danh sách đường dẫn trích dẫn duy nhất, tối đa 50 — cùng cách `dungLichSu`
làm ở FE);
`ghi_luot(id, cau_hoi, tra_loi: dict, trace_id) -> int` (thu_tu = max+1, cập nhật
`cap_nhat_luc`, một transaction); `danh_sach(sub, plan, limit, offset) -> (items, tong_hien,
tong_an)`; `chi_tiet(sub, id) -> dict` (phiên + lượt theo `thu_tu`); `doi_ten(sub, id,
tieu_de)`; `xoa_mem(sub, id)`. Tất cả nhận `sub` và lọc theo `user_sub` — không có hàm nào
đọc phiên mà không có `sub`.

### 5.2 Stream `POST /tra-cuu/luong`

- `TraCuuRequest.hoi_thoai_id: UUID | None = None` (additive).
- Có `user_sub`:
  - không `hoi_thoai_id` → `tao_phien` trước khi phát `bat_dau`; `bat_dau` mang
    `hoi_thoai_id` (chuỗi). Phiên mới không tính vào hạn mức lượt; chỉ lượt LLM tính.
  - có `hoi_thoai_id` → `lay_phien` (không có → **404**), `phien_bi_an` (→ **403**); `lich_su` = `lich_su_gan_nhat(id, 3)`, **bỏ qua** `lich_su` client gửi;
    câu nối tiếp vẫn không đi qua cache như hiện nay.
  - Sau khi có payload (kể cả từ cache): `ghi_luot`. Ghi lỗi → vẫn phát `ket_qua`, rồi phát
    thêm `event: loi_luu` `{hoi_thoai_id, detail}` và log. Không im lặng.
- Không `user_sub` (ẩn danh hoặc auth chưa cấu hình): `hoi_thoai_id` bị bỏ qua, không tạo,
  không ghi; `bat_dau.hoi_thoai_id = null`. Hành vi hiện tại giữ nguyên.
- `POST /tra-cuu` (không stream) nhận cùng trường và cùng hành vi ghi; `TraCuuResponse`
  không đổi (id phiên chỉ ở `bat_dau` với stream; với `/tra-cuu` trả trong header
  `X-Hoi-Thoai-Id`).

### 5.3 Router `src/api/routes_hoi_thoai.py`

Phụ thuộc `nguoi_dung_bat_buoc` (mới, trong `bao_ve`): trả `sub` hoặc **401** "Cần đăng
nhập để dùng tính năng này." — kể cả khi Supabase chưa cấu hình (không có ai để gán phiên).

| Endpoint | Trả về |
|---|---|
| `GET /hoi-thoai?limit=20&offset=0` (limit ≤ 50) | `{plan, gioi_han, tong_hien, tong_an, items:[{id, tieu_de, so_luot, tao_luc, cap_nhat_luc}]}` |
| `GET /hoi-thoai/{id}` | `{id, tieu_de, tao_luc, cap_nhat_luc, luot:[{thu_tu, cau_hoi, tra_loi, trace_id, tao_luc}]}`; 404 không của mình/đã xoá; 403 ẩn theo gói |
| `PATCH /hoi-thoai/{id}` `{tieu_de}` (1–120 ký tự, trim) | phiên đã đổi; 404/403 như trên |
| `DELETE /hoi-thoai/{id}` | 204; xoá mềm; 404 nếu không của mình |

Không cổng `cong_bao_ve` (không LLM), nhưng có `cong_nhe` (rate limit theo IP) như các
endpoint đọc khác.

## 6. Frontend

- `lib/klaw.ts`: `PhienTomTat`, `DanhSachPhien`, `LuotDaLuu`, `ChiTietPhien` + predicate
  `laDanhSachPhien`, `laChiTietPhien`; `tra_loi` của lượt đi qua `chuanHoaBang`/
  `chuanHoaDocuments` rồi `laTraCuuKetQua` như payload nhận từ stream.
- `lib/api.ts` `traCuuLuong`: thêm `hoi_thoai_id` vào body; đọc `bat_dau.hoi_thoai_id`;
  sự kiện `loi_luu` → callback `onLoiLuu`.
- `hooks/use-hoi-thoai.ts`: `danhSach`, `taiLai`, `chiTiet(id)`, `doiTen`, `xoa`, trạng thái
  tải/lỗi; gọi qua `goi`.
- `routes/dung-thu.tsx`: `validateSearch` thêm `phien?: string` (UUID); state `phienId`.
  Mở với `?phien=` → tải chi tiết → `luuTru` = các lượt (card render như thường, thẻ trích
  dẫn bấm được); 403 → thông báo "Gói Miễn phí giữ 10 phiên gần nhất; phiên này đang ẩn."
  kèm link `/bang-gia`; 404 → "Không tìm thấy phiên này." + nút Phiên mới. `hoi()` truyền
  `hoi_thoai_id`; sau `bat_dau` của phiên mới → `navigate({ search: { phien: id },
  replace: true })`. Khi đăng nhập: không gửi `lich_su` client (máy chủ tự nạp). Khi
  chưa đăng nhập hoặc `chuaCauHinh`: mọi thứ như hiện nay.
- `components/klaw/DanhSachPhien.tsx` thay cột "Lịch sử phiên" trong bộ nhớ: nút "Phiên
  mới"; danh sách (tiêu đề, thời gian tương đối, số lượt); phiên đang mở nổi bật; menu đổi
  tên (sửa tại chỗ, Enter lưu, Esc huỷ) và xoá (xác nhận tại chỗ, không `confirm()`); dòng
  cuối khi `tong_an > 0`: "Gói Miễn phí giữ {gioi_han} phiên gần nhất. {tong_an} phiên cũ
  hơn đang ẩn." + link Bảng giá. Trống: "Chưa có phiên nào. Hỏi một câu để bắt đầu."
  Dưới 80rem: nút "Phiên" mở sheet, cùng khuôn sheet bộ lọc của trang Tra cứu. Khung đối
  chiếu/soạn thảo đang mở thì cột này ẩn như hiện nay.
- Chữ hiển thị mới không dùng cụm bị cấm trong test giọng; xưng "tôi".

## 7. Lỗi và an toàn

- Sở hữu kiểm ở mọi đường bằng `user_sub`; phiên của người khác trả 404 (không tiết lộ
  tồn tại). Id là UUID v4.
- Payload lưu nguyên JSON đã qua pydantic; không lưu token, không lưu IP.
- Xoá mềm; xoá tài khoản (gói 2) cascade theo khoá ngoại.
- Ghi lượt lỗi không làm mất câu trả lời; `loi_luu` báo cho người dùng.
- Đổi tên và câu hỏi là chữ của người dùng, render bằng text node như mọi chuỗi khác.

## 8. Kiểm chứng

- pytest tích hợp (`tests/test_api/test_hoi_thoai.py`, dùng `cai_dat` + `khoa_ky` +
  `_bearer`): tạo phiên qua stream với `graph_gia_lap`; `bat_dau` có id; lượt được ghi với
  payload đủ; hỏi tiếp trong phiên → `lich_su` do máy chủ nạp (kiểm state vào graph); người
  B đọc phiên của A → 404; gói free với 11 phiên → phiên thứ 11 cũ nhất ẩn, GET → 403,
  danh sách `tong_an = 1`; xoá một phiên hiện → phiên ẩn hiện lại; đổi tên hợp lệ/không
  hợp lệ; ẩn danh → không ghi, `bat_dau.hoi_thoai_id = null`; `nguoi_dung_bat_buoc` 401.
- pytest cho `phien_luu_toi_da` và kiểm YAML thiếu khoá → lỗi rõ.
- FE `scripts/kiem-phien.ts`: `tieuDeMacDinh` (cắt 80 ranh giới từ), câu "đang ẩn" theo
  số, `laDanhSachPhien`/`laChiTietPhien` với payload thiếu trường; `npm run kiem`.
- Chrome thật: đăng nhập, tạo hai phiên, chuyển qua lại, hỏi nối tiếp trong phiên cũ (câu
  "còn ở khoản mấy?" hiểu đúng), đổi tên, xoá, tải lại trang giữ `?phien=`.

## 9. Ngoài phạm vi gói 1

Tìm trong lịch sử; chia sẻ phiên; xuất phiên; dọn phiên đã xoá mềm; đồng bộ phiên ẩn danh
sang tài khoản; trang tài khoản và admin (gói 2); bản thảo đã lưu và workspace (gói 3);
thanh toán nâng gói.

## 10. Quyết định đã chốt cho gói 2 và 3 (ghi để không hỏi lại)

- Gói 2: cột `users.role` ∈ {user, admin}, mặc định user; trang tài khoản (email, gói, hạn
  mức tháng, số phiên, đăng xuất); trang quản trị cho admin: danh sách người dùng, đổi
  `plan` (đường nâng free → pro khi chưa có thanh toán), xem lượt dùng. Khách = tài khoản
  free mặc định.
- Gói 3: workspace = phiên hội thoại + bản thảo đã lưu của tài khoản; cần bảng bản thảo
  và nút "Lưu bản thảo" hiện đang "chưa dựng".
