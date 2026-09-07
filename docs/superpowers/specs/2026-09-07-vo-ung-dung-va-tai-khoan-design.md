# Vỏ ứng dụng, tài khoản và hạn mức theo ngày/tháng — thiết kế (gói 2A/3)

Ngày: 2026-09-07 · Trạng thái: chờ chủ sản phẩm duyệt · Gói trước: `2026-09-07-lich-su-hoi-thoai-design.md` (đã xong) · Gói sau: 2B quản trị và xoá tài khoản.

## 1. Mục tiêu

Người đã đăng nhập thấy một vỏ ứng dụng kiểu ChatGPT (sidebar trái với "Phiên mới",
"Gần đây", thẻ tài khoản), có menu tài khoản với Hồ sơ, Nâng cấp gói, Cá nhân hoá,
Trợ giúp, Đăng xuất; và hạn mức gói Free/Cá nhân được tính theo ngày, tháng và tính
năng, hiển thị bằng thanh đo "đã dùng x% · đặt lại lúc …" ở cả hai gói. Người chưa
đăng nhập dùng thử được 10 lượt hỏi đáp mỗi 24 giờ như ChatGPT, không lưu; đăng nhập
thì đoạn chat đang có được đưa vào tài khoản.

## 2. Hiện trạng

- Hạn mức duy nhất: `han_muc.yaml: goi {free: 50, pro: 500}` lượt LLM/tháng (UTC),
  cưỡng chế ở `bao_ve.kiem_han_muc_thang`; `traces` đếm cả dòng `result_type = 'loi'`
  và `out_of_scope` (người dùng mất lượt vì lỗi máy chủ hoặc hỏi lạc đề).
- `phien_luu` (ẩn phiên theo gói) vừa dựng ở gói 1; chủ sản phẩm chọn bỏ.
- `AppShell` chỉ có điều hướng; danh sách phiên nằm ở cột phải của `/dung-thu`;
  không có menu tài khoản, trang hồ sơ, nâng gói. `HanMucThang.tsx` đọc `/han-muc`
  hình cũ, chỉ còn được render trên `/bang-gia` (sau đăng nhập).
- Bảng giá `/bang-gia` ghi Miễn phí "50 lượt hỏi AI/tháng", Cá nhân 499k "500 lượt
  hỏi AI/tháng · 10 bản thảo/tháng". YAML gọi gói trả phí là `pro`.
- Chi phí đo 60 ngày: hỏi đáp trung bình 0,27 cent/lượt (p95 0,8), bản thảo 0,22
  cent; 9% lượt hỏi trúng bộ đệm. Trần chi phí toàn hệ thống 2 USD/ngày (~740 lượt).

## 3. Quyết định của chủ sản phẩm

- Không dùng cửa sổ trượt kiểu "N lượt/5 giờ". Hạn mức theo ngày (chống lạm dụng,
  bảo vệ trần chi phí chung) và theo tháng (ranh giới cá nhân/công việc).
- Free: 15 lượt hỏi đáp/ngày, 300/tháng; 3 bản thảo/ngày và 20/tháng. Cá nhân (`pro`):
  100 lượt hỏi đáp/ngày (lá chắn chống chia sẻ tài khoản và script: 100 lượt là 30 phút
  chờ máy, không người dùng thật nào chạm; không hạn ngày thì một tài khoản đốt được
  2,7 USD/ngày, vượt trần chi phí chung), 1000/tháng; 20 bản thảo/ngày, không hạn tháng. Mọi gói:
  tối đa 50 lượt trong một phiên (lý do kỹ thuật, ngữ cảnh chỉ nạp 3 lượt). Số phiên và
  lịch sử không giới hạn.
- Căn cứ khảo sát (09/2026): các trợ lý AI lớn đặt hạn free theo NGÀY, đặt lại giờ cố
  định (Claude ~30–50 tin/ngày, Perplexity ~5 tìm kiếm Pro/ngày, Copilot 50 chat/tháng);
  người chạm hạn mức chuyển đổi cao gấp 6,2 lần (ProfitWell 2025), nhưng hạ trần với
  người không bao giờ chạm chỉ gây rời bỏ; điểm nâng gói phải nằm trong luồng làm việc.
  Với KLAW: người lao động hỏi theo đợt 3–10 câu (không được chặn buổi đầu), nhân sự và
  pháp chế hỏi 5–20 câu/ngày và soạn văn bản (nhóm trả tiền, nhóm duy nhất nên chạm trần).
  Trần tháng cho bản thảo tồn tại vì soạn thảo là việc trả tiền rõ nhất; thiếu nó, một
  pháp chế soạn 90 bản thảo/tháng miễn phí.
- Không tính lượt: câu trả lời từ bộ đệm, câu ngoài phạm vi, lượt lỗi máy chủ.
- Free và Cá nhân đều có thanh đo mức dùng: tiêu đề, thanh tiến độ, "x% đã dùng",
  "Đặt lại HH:MM (Asia/Ho_Chi_Minh)".
- Gói `pro` hiển thị là "Cá nhân" để khớp bảng giá; bảng giá sửa số theo cơ chế mới.
- Menu tài khoản: Hồ sơ, Nâng cấp gói, Cá nhân hoá (tên hiển thị, đổi mật khẩu),
  Trợ giúp, Đăng xuất. Ngôn ngữ và xoá tài khoản để gói 2B.
- Nâng cấp: gửi yêu cầu, admin duyệt (trang duyệt thuộc 2B; tạm thời đổi gói bằng
  SQL). Không có thanh toán trực tuyến.
- Tên hiển thị lưu ở Supabase `user_metadata`; KLAW không thêm cột (giữ quyết định
  migration 012).
- Đảo quyết định của spec 2026-09-06 (khoá ô hỏi khi chưa đăng nhập): khách dùng thử
  được hỏi đáp 10 lượt/24 giờ theo mã khách của trình duyệt, một đoạn chat trong bộ nhớ
  trang (tải lại là mất), không lưu máy chủ; soạn thảo yêu cầu đăng nhập; khi đăng
  nhập/đăng ký, đoạn chat hiện tại được lưu thành phiên đầu tiên của tài khoản. Căn cứ
  ChatGPT (trợ giúp OpenAI, qua chatai.guide 05/2026): chưa đăng nhập có một cuộc trò
  chuyện, chỉ trong phiên trình duyệt, không lưu; đăng nhập thì đoạn mới nhất vào tài
  khoản; không công bố số lượt cố định, chạm ngưỡng thì yêu cầu đăng nhập.
- Form đăng ký bỏ trường "Vai trò" (hiện chỉ là giao diện, không gửi đi đâu).

## 4. Hạn mức

### 4.1 `config/han_muc.yaml` (hình mới, thay toàn bộ)

```yaml
goi_mac_dinh: free
# Mốc "ngày" và "tháng" tính theo múi giờ này, không theo UTC.
mui_gio: Asia/Ho_Chi_Minh
# 0 = không cho lượt nào; "không giới hạn" = một số lớn (cùng quy ước cũ).
goi:
  free:
    hoi_dap_ngay: 15
    hoi_dap_thang: 300
    soan_thao_ngay: 3
    soan_thao_thang: 20
    luot_moi_phien: 50
  pro:
    hoi_dap_ngay: 100
    hoi_dap_thang: 1000
    soan_thao_ngay: 20
    soan_thao_thang: 100000
    luot_moi_phien: 50
# Khách chưa đăng nhập (chỉ khi Supabase đã cấu hình): đếm theo cửa sổ 24 giờ trượt,
# vì khách không có mốc "ngày" nào gắn với tài khoản.
khach:
  hoi_dap_24h: 10      # theo mã khách của trình duyệt
  ip_24h: 30           # lá chắn: mọi mã khách sau cùng một IP
```

`_doc_han_muc` fail loud khi: thiếu `goi`/`goi_mac_dinh`/`mui_gio`/`khach` (hai khoá); một gói thiếu
bất kỳ khoá nào trong năm khoá; `mui_gio` không phải tên vùng hợp lệ. Khoá `phien_luu`
bị gỡ; nếu còn trong file → lỗi rõ "khoá không còn dùng".

### 4.2 Đếm

- Nguồn đếm là `traces` (không thêm bảng), lọc `user_sub = :sub`, `NOT cache_hit`,
  `endpoint` tương ứng, và `(result_type IS NULL OR result_type NOT IN ('loi',
  'out_of_scope'))` — `/soan-thao` ghi `result_type` NULL khi thành công, nên thiếu
  nhánh `IS NULL` là không đếm bản thảo nào.
- `hoi_dap_*` đếm `endpoint = '/api/v1/tra-cuu'` (stream và không stream cùng endpoint);
  `soan_thao_*` đếm `endpoint = '/api/v1/soan-thao'`. `/soat`, `/van-ban`, `/mau`
  không bao giờ đếm.
- Mốc ngày = 00:00 hôm nay theo `mui_gio`; mốc tháng = 00:00 ngày 1 tháng này theo
  `mui_gio`. Hàm `moc_ngay(now)`, `moc_thang(now)`, `moc_ngay_sau`, `moc_thang_sau`
  trong `bao_ve` dùng `zoneinfo`.
- Kiểm TRƯỚC khi chạy graph, trong `cong_bao_ve`, thay `kiem_han_muc_thang`:
  `kiem_han_muc(sub, plan, endpoint)`: với `/tra-cuu` kiểm ngày rồi tháng; với
  `/soan-thao` cũng kiểm ngày rồi tháng. Vượt → 429 với `detail` một câu tiếng Việt nêu mốc mở lại
  ("Hôm nay bạn đã dùng 15 lượt hỏi đáp của gói Miễn phí. Mở lại lúc 00:00 ngày
  08/09.") và header `Retry-After` = giây tới mốc. Lỗi DB khi đếm → 503 (như cũ).
- Trần lượt mỗi phiên kiểm trong `routes._chuan_bi_phien` khi có `hoi_thoai_id`:
  `count(luot_hoi_thoai) >= luot_moi_phien(plan)` → 403 `hoi_thoai.LOI_PHIEN_DAY`
  = "Phiên này đã đủ 50 lượt. Mở phiên mới để tiếp tục." (số lấy từ YAML).
- Kết quả cache hit, ngoài phạm vi, lỗi vẫn được ghi `traces` như cũ; chỉ khác ở
  câu đếm.

### 4.3 Gỡ cơ chế ẩn phiên

Xoá `phien_luu_toi_da`, `hoi_thoai.phien_bi_an`, `_SQL_HANG`, nhánh 403 "phiên
đang ẩn" ở `_chuan_bi_phien` và `routes_hoi_thoai._phien_mo_duoc`; `LOI_PHIEN_AN` bỏ.
`DanhSachPhienResponse` thành `{plan, luot_moi_phien, tong, items}` (bỏ `gioi_han`,
`tong_hien`, `tong_an`). FE bỏ `cauPhienAn`, dòng "phiên cũ hơn đang ẩn", nhánh 403
"Xem bảng giá" trong `dung-thu.tsx`. Test tương ứng cập nhật.

## 5. Dữ liệu

Migration `021_nang_goi.sql`:

```sql
CREATE TABLE IF NOT EXISTS yeu_cau_nang_goi (
    id           BIGSERIAL PRIMARY KEY,
    user_sub     UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    goi_hien_tai TEXT NOT NULL,
    goi_muon     TEXT NOT NULL,
    trang_thai   TEXT NOT NULL DEFAULT 'cho_duyet'
                 CHECK (trang_thai IN ('cho_duyet', 'da_duyet', 'tu_choi')),
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    xu_ly_luc    TIMESTAMPTZ,
    xu_ly_boi    UUID
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_yeu_cau_nang_goi_cho_duyet
    ON yeu_cau_nang_goi(user_sub) WHERE trang_thai = 'cho_duyet';
```

`lifespan` áp `("019", "020", "021")`. Không đổi `users`, `hoi_thoai`, `traces`.

## 6. Backend

### 6.1 `GET /han-muc` (hình mới, thay hình cũ)

Cổng như cũ (`_nguoi_goi`: ẩn danh → `ap_dung=false`). Có danh tính:

```json
{
  "ap_dung": true,
  "plan": "free",
  "ten_goi": "Miễn phí",
  "mui_gio": "Asia/Ho_Chi_Minh",
  "muc": [
    {"khoa": "hoi_dap_ngay",   "nhan": "Hỏi đáp hôm nay",   "da_dung": 9,   "han_muc": 15,  "dat_lai_luc": "2026-09-08T00:00:00+07:00"},
    {"khoa": "hoi_dap_thang",  "nhan": "Hỏi đáp tháng này", "da_dung": 120, "han_muc": 300, "dat_lai_luc": "2026-10-01T00:00:00+07:00"},
    {"khoa": "soan_thao_ngay", "nhan": "Bản thảo hôm nay",  "da_dung": 1,   "han_muc": 3,   "dat_lai_luc": "2026-09-08T00:00:00+07:00"},
    {"khoa": "soan_thao_thang", "nhan": "Bản thảo tháng này", "da_dung": 4,  "han_muc": 20,  "dat_lai_luc": "2026-10-01T00:00:00+07:00"}
  ],
  "phien": {"luot_toi_da": 50},
  "ghi_chu": "Lượt trả lời từ bộ đệm, câu ngoài phạm vi và lượt lỗi không tính. Tra cứu luật, soát văn bản không bao giờ tính."
}
```

`han_muc >= 100000` nghĩa là không giới hạn; FE quyết định cách hiển thị. Model
`HanMucResponse` viết lại theo hình này; `HanMucThang.tsx` và `laHanMuc` cũ bị gỡ,
`/bang-gia` hiện `ThuocMucDung` (§7.2) ở đúng chỗ đó.

### 6.2 `GET /ho-so` (mới, `nguoi_dung_bat_buoc`)

```json
{
  "email": "…", "plan": "free", "ten_goi": "Miễn phí", "tao_luc": "…",
  "so_phien": 12, "tong_hoi_dap": 87, "tong_ban_thao": 4,
  "hoat_dong": [{"ngay": "2026-09-07", "so_luot": 3}],
  "phan_loai": [
    {"khoa": "answer", "nhan": "Trả lời có căn cứ", "so": 60},
    {"khoa": "partial_coverage", "nhan": "Trả lời một phần", "so": 12},
    {"khoa": "abstain", "nhan": "Dừng vì thiếu căn cứ", "so": 9},
    {"khoa": "out_of_scope", "nhan": "Ngoài phạm vi", "so": 6},
    {"khoa": "soan_thao", "nhan": "Bản thảo", "so": 4}
  ]
}
```

`hoat_dong` là 365 ngày gần nhất theo `mui_gio`, chỉ ngày có lượt; đếm cùng quy tắc
§4.2 nhưng KHÔNG loại `out_of_scope` (hoạt động là hoạt động). `tao_luc` = `users.created_at`.

### 6.3 Nâng gói

- `POST /nang-goi/yeu-cau` body `{goi_muon}`: `goi_muon` phải là khoá trong YAML và
  khác gói hiện tại (422); đã có yêu cầu `cho_duyet` → 409 với `detail` "Bạn đã có một
  yêu cầu đang chờ duyệt."; thành công 201 trả `YeuCauNangGoiOut{id, goi_hien_tai,
  goi_muon, trang_thai, tao_luc, xu_ly_luc}`.
- `GET /nang-goi/yeu-cau`: yêu cầu mới nhất của người gọi hoặc `null`.
- Router `src/api/routes_tai_khoan.py` mở rộng (đã có `/han-muc`, `/nguoi-dung`).

### 6.4 Phiên

`GET /hoi-thoai` trả thêm `luot_moi_phien`; `PhienTomTatOut.so_luot` đã có nên FE khoá
được trước khi gửi. `/tra-cuu*` 403 `LOI_PHIEN_DAY` tại lượt thứ 51.

## 7. Frontend

### 7.1 Vỏ ứng dụng (`AppShell`)

- ≥1280px, đã đăng nhập: cột trái 260px gồm logo; nút "Phiên mới" (điều hướng
  `/dung-thu` không tham số; nếu đang ở đó thì gọi cùng hàm `phienMoi`); điều hướng
  Trợ lý KLAW, Tra cứu luật, Soạn thảo; mục "Gần đây" = danh sách phiên (component
  `DanhSachPhien` tách từ `CotPhien`, giữ đổi tên/xoá tại chỗ; `CotPhien` và sheet
  bên phải bị gỡ); chân là `TheTaiKhoan`: vòng chữ cái đầu, tên hiển thị (hoặc email),
  nhãn gói, nút "Nâng cấp" (ẩn với `pro`). Bấm thẻ mở `MenuTaiKhoan` (popover, đóng
  bằng Escape/click ngoài, `role="menu"`): Hồ sơ → `/tai-khoan`; Nâng cấp gói → mở
  `ModalNangGoi`; Cá nhân hoá → `/tai-khoan/ca-nhan-hoa`; Trợ giúp → `/huong-dan`;
  Đăng xuất → `signOut` rồi về `/`.
- ≥1280px, chưa đăng nhập: cột trái như hiện nay (điều hướng gồm Hướng dẫn) + nút
  "Đăng nhập" ở chân; không có Gần đây.
- 768–1280px: cột icon 64px; Gần đây không hiện; header của `/dung-thu` có nút
  "Phiên" mở sheet danh sách (tái dùng sheet hiện có, chuyển vào AppShell); chân cột
  là avatar mở `MenuTaiKhoan`.
- <768px: thanh dưới bốn mục Trợ lý, Tra cứu, Soạn thảo, Tài khoản (mở sheet gồm
  `MenuTaiKhoan` và Gần đây).
- `useHoiThoai(daDangNhap)` chuyển lên `AppShell` để danh sách sống qua mọi trang;
  `dung-thu.tsx` nhận `hoiThoai` qua context `TaiKhoanContext` (cung cấp `user`,
  `hoiThoai`, `hanMuc`, `moModalNangGoi`). Effect đồng bộ `?phien=` và các sửa lỗi
  của gói 1 giữ nguyên.

### 7.2 Thanh đo mức dùng (`ThuocMucDung`)

Một dòng cho mỗi mục trong `han_muc.muc`: tiêu đề (`nhan`), thanh tiến độ, "x% đã
dùng", "Đặt lại HH:MM DD/MM (Asia/Ho_Chi_Minh)". Màu: <80% brass, 80–99% amber,
100% `destructive`. `han_muc >= 100000` → chữ "Không giới hạn", không có thanh.
Nơi hiện: trang Hồ sơ (đủ bốn dòng + "Phiên này: 12/50 lượt" khi có phiên mở);
`MenuTaiKhoan` (dòng đầu tiên chưa đủ 100%, rút gọn); chip cạnh ô soạn câu hỏi
"Còn 6 lượt hôm nay" (đổi màu theo ngưỡng). Hook `useHanMuc()` gọi `/han-muc` khi
đăng nhập và sau mỗi lượt hỏi/soạn kết thúc (`!dangChay`).

### 7.3 Ba trạng thái hết hạn mức (đều có nút hành động)

- Phiên đủ 50 lượt: ô nhập khoá, thẻ "Phiên này đã đủ 50 lượt. Mở phiên mới để tiếp
  tục." + nút Phiên mới. Từ lượt 30 hiện dòng nhỏ "Phiên dài rồi, mở phiên mới để câu
  trả lời bám sát hơn".
- 429 ngày/tháng: `BaoLoi` hiện `detail` máy chủ (đã có mốc mở lại) + nút "Nâng cấp"
  (Free) hoặc chỉ mốc mở lại (Cá nhân, kể cả khi chạm 100/ngày). Không có nút "Thử lại"
  cho 429.
- Bản thảo hết lượt ngày: cùng khuôn ở màn Soạn thảo.
Tra cứu luật, soát văn bản, xem lại phiên, xuất Word/PDF không bao giờ bị khoá.

### 7.4 Trang tài khoản

- `/tai-khoan` (Hồ sơ): thẻ định danh (chữ cái đầu, tên, email, nhãn gói, ngày tham
  gia); `ThuocMucDung` đủ; bốn ô số (số phiên, tổng hỏi đáp, tổng bản thảo, lượt
  tháng này); lịch hoạt động 52 tuần × 7 ngày bằng CSS grid từ `hoat_dong` (bốn mức
  đậm theo tứ phân vị, `title` mỗi ô "07/09: 3 lượt"); bảng `phan_loai`; nút Nâng cấp
  (Free) và Cá nhân hoá.
- `/tai-khoan/ca-nhan-hoa`: form tên hiển thị (`supabase.auth.updateUser({data:
  {ten_hien_thi}})`, 1–60 ký tự); đổi mật khẩu (`updateUser({password})`, chỉ hiện khi
  `user.app_metadata.provider === "email"`; Supabase yêu cầu đăng nhập lại → chuyển tới
  `/dang-nhap?next=/tai-khoan/ca-nhan-hoa`); dòng "Xoá tài khoản và ngôn ngữ: sắp có".
- Cả hai route yêu cầu đăng nhập; chưa đăng nhập → `/dang-nhap?next=…`
  (`DICH_QUAY_LAI` thêm hai đường này).

### 7.5 Nâng cấp (`ModalNangGoi`)

Cửa sổ giữa màn, nút đóng góc phải, hai card cạnh nhau (xếp dọc dưới 768px), mỗi
card cùng khuôn: nhãn gói nhỏ → tiêu đề lớn → một câu mô tả → giá "₫0 / tháng" →
nút → tiêu đề danh sách → danh sách tính năng có icon (lucide). Nội dung:

| | Card Miễn phí | Card Cá nhân |
|---|---|---|
| Nhãn | Miễn phí | Cá nhân |
| Tiêu đề | Dùng thử KLAW | Dùng cho công việc |
| Mô tả | Hỏi pháp luật lao động và nhận câu trả lời có căn cứ kiểm chứng được, soạn văn bản mẫu, tra cứu luật. | Cho luật sư, chuyên viên nhân sự và pháp chế hỏi nhiều mỗi ngày và soạn văn bản thường xuyên. |
| Giá | ₫0 / tháng | ₫499.000 / tháng (số từ `bang-gia.tsx`, cùng nguồn dữ liệu) |
| Nút | Free: viền mờ, khoá, "Gói hiện tại của bạn". Pro: không hiện nút. | Free: nút đặc "Yêu cầu nâng lên Cá nhân" → `POST /nang-goi/yeu-cau`; sau khi gửi hoặc đã có yêu cầu: khoá, "Đang chờ duyệt". Pro: viền mờ, khoá, "Gói hiện tại của bạn". |
| Tiêu đề danh sách | Bắt đầu với những điều cơ bản: | Mọi thứ trong gói Miễn phí, cộng thêm: |
| Danh sách | 15 lượt hỏi đáp mỗi ngày, 300 mỗi tháng · 3 bản thảo mỗi ngày, 20 mỗi tháng · Phiên và lịch sử không giới hạn · Tra cứu luật, soát văn bản không giới hạn · Xuất Word, PDF | 100 lượt hỏi đáp mỗi ngày, 1000 mỗi tháng · 20 bản thảo mỗi ngày, không giới hạn tháng |

Dưới nút của card Cá nhân, chữ nhỏ: "Chưa có thanh toán trực tuyến. Tôi sẽ báo qua
email khi gói được mở." Số trong danh sách lấy từ một hằng dùng chung với `/bang-gia`
(không chép tay hai nơi); chỉ liệt kê tính năng đã có thật. Mở từ `MenuTaiKhoan`, nút
Nâng cấp ở chân sidebar, thẻ 429, trang Hồ sơ. Đóng bằng Escape, click nền, nút X;
tiêu điểm quay về nơi mở.

### 7.6 Bảng giá

`bang-gia.tsx`: Miễn phí = "15 lượt hỏi/ngày, 300 lượt/tháng · 3 bản thảo/ngày, 20/tháng
· Phiên và lịch sử không giới hạn · Tra cứu, soát văn bản không giới hạn"; Cá nhân =
"100 lượt hỏi/ngày, 1000/tháng · 20 bản thảo/ngày, không hạn tháng · …"; hàng so sánh "Phiên lưu" bỏ
số 10 → "Không giới hạn"; FAQ hạn mức viết lại theo §4. Giá tiền giữ nguyên.
`tenGoi("pro")` → "Cá nhân".

## 8. Chế độ khách (chưa đăng nhập, Supabase đã cấu hình)

### 8.1 Danh tính khách

FE sinh `khach_id` (UUID v4) lần đầu, lưu `localStorage["klaw.khach_id"]`, gửi header
`X-Khach-Id` ở mọi lời gọi `/tra-cuu*` và `/han-muc` khi không có bearer. Đoạn chat
của khách chỉ ở state React: tải lại trang là mất (đúng ChatGPT); bộ đếm KHÔNG mất,
vì nó nằm ở máy chủ theo `khach_id` và theo IP.

### 8.2 Cổng máy chủ

`cong_bao_ve` nhận tham số `cho_khach: bool` (factory). `/tra-cuu` và `/tra-cuu/luong`
dùng `cho_khach=True`; `/soan-thao` giữ `False` (401 "Cần đăng nhập để soạn văn bản.").
Khi không có bearer và `cho_khach`:
- thiếu `X-Khach-Id` hoặc không phải UUID → 401 "Cần đăng nhập để dùng tính năng này.";
- `kiem_rate_limit(f"khach:{id}", so_luot=khach.hoi_dap_24h, cua_so_giay=86400)` rồi
  `kiem_rate_limit(f"khach-ip:{ip}", khach.ip_24h, 86400)`; vượt → 429 với `detail`
  "Bạn đã dùng 10 lượt thử trong 24 giờ. Đăng nhập miễn phí để tiếp tục và lưu đoạn
  chat này." và `Retry-After` tính từ lượt cũ nhất trong cửa sổ; `kiem_tran_chi_phi`;
  trả `None` (đường ẩn danh hiện có: không tạo phiên, không ghi lượt, `traces.user_sub`
  NULL).
- `kiem_rate_limit` đếm lúc vào cổng (tính cả lượt trúng bộ đệm) — chấp nhận cho khách
  vì đơn giản; hạn mức tài khoản vẫn đếm theo kết quả (§4.2).
- `kiem_rate_limit` sửa để dọn hàng cũ THEO KHOÁ (`WHERE ip = :khoa AND ts < …`) vì bảng
  `rate_limit_luot` nay chứa nhiều cửa sổ khác nhau; nhận thêm `cua_so_giay`.
Chưa cấu hình Supabase (máy dev, eval): mọi thứ như trước, không đếm khách.

### 8.3 `/han-muc` cho khách

Không bearer, có `X-Khach-Id` → `{ap_dung: true, plan: "khach", ten_goi: "Dùng thử",
muc: [{khoa: "khach_24h", nhan: "Lượt thử 24 giờ", da_dung, han_muc: 10, dat_lai_luc:
<lượt cũ nhất + 24h, hoặc null khi chưa dùng>}], phien: {luot_toi_da: 10}, ghi_chu:
"Đăng nhập miễn phí để có 15 lượt mỗi ngày, lưu phiên và soạn văn bản."}`.

### 8.4 Mang đoạn chat vào tài khoản

`POST /hoi-thoai/nhap` (`nguoi_dung_bat_buoc`), body `{luot: [{cau_hoi, tra_loi,
trace_id}]}`, 1–10 lượt, mỗi `tra_loi` phải parse được thành `TraCuuResponse` (422 nếu
không), `cau_hoi` ≤ 2000 ký tự. Tạo phiên (`tieu_de_mac_dinh` từ câu đầu), ghi lượt theo
thứ tự, trả `{id}`. Không đụng `traces` (lượt khách đã tính vào ngân sách khách, không
tính lại vào tài khoản). Không ràng buộc số lần nhập; kích cỡ body đã bị chặn bởi trần
10 lượt và kiểm hình `TraCuuResponse`; nhịp theo tài khoản (10 lượt/phút) là lá chắn đủ.

FE: khi khách bấm Đăng nhập/Đăng ký (header, thẻ mời, thẻ hết lượt) mà đoạn chat có
≥ 1 lượt đã xong, lưu `sessionStorage["klaw.khach_thread"]` = các lượt (cau_hoi, ketQua,
trace_id) rồi điều hướng với `next=/dung-thu`. Trên `/dung-thu`, khi `daDangNhap` và
sessionStorage có thread: gọi `/hoi-thoai/nhap`, xoá sessionStorage, điều hướng
`?phien=<id>`; lỗi → thông báo "Tôi chưa lưu được đoạn chat thử; bạn vẫn hỏi tiếp được."
và xoá sessionStorage (không lặp).

### 8.5 Giao diện khách

- Header: hai nút góc phải "Đăng nhập" (đặc) và "Đăng ký miễn phí" (viền), dùng slot
  `topRight` của `AppShell`.
- Sidebar: logo; "Phiên mới" (xoá đoạn chat trong bộ nhớ); điều hướng Trợ lý, Tra cứu,
  Soạn thảo; chân: "Xem các gói dịch vụ" (→ `/bang-gia`), "Trợ giúp" (→ `/huong-dan`), thẻ
  mời "Đăng nhập để lưu phiên, hỏi tiếp nhiều ngày và soạn văn bản." + nút Đăng nhập.
  Không có Gần đây.
- Ô hỏi mở; chip "Còn 7/10 lượt thử trong 24 giờ" từ `/han-muc`. Hết lượt: thẻ trong
  dòng chat "Bạn đã dùng 10 lượt thử. Đăng nhập miễn phí để tiếp tục, lưu đoạn chat này
  và có 15 lượt mỗi ngày." + hai nút; ô hỏi khoá. Khoá này KHÔNG áp cho tra cứu luật,
  soát văn bản.
- Màn Soạn thảo cho khách: xem biểu mẫu được, nút "Soạn bản thảo" → `TheDangNhap`
  (giữ component hiện có).
- `TheDangNhap` không còn khoá ô hỏi ở `/dung-thu`; `canDangNhap` chỉ còn dùng cho soạn
  thảo. `?q=` từ trang chủ chạy ngay cho khách như trước gói truy cập.
- `dang-ky.tsx`: bỏ `ROLES`, trường "Vai trò" và `form.role`.

## 9. Lỗi và an toàn

- Mọi endpoint tài khoản qua `nguoi_dung_bat_buoc`; yêu cầu nâng gói chỉ đọc/ghi theo
  `user_sub`; một yêu cầu chờ duyệt mỗi người (unique index).
- Mọi trần đều cưỡng chế ở máy chủ; khoá ở giao diện chỉ là báo sớm.
- Mật khẩu và tên hiển thị đi thẳng Supabase từ trình duyệt; backend KLAW không nhận,
  không lưu. Tên hiển thị render dạng text node.
- 429/403 không tiết lộ gì ngoài hạn mức của chính người gọi.
- Xoá cơ chế ẩn phiên không xoá dữ liệu; chỉ bỏ quy tắc hiện.
- Khách: `khach_id` là chuỗi do trình duyệt sinh, không phải danh tính; máy chủ chỉ dùng
  nó làm khoá đếm, không trả dữ liệu theo nó. Xoá localStorage để lấy mã mới thì vẫn còn
  lá chắn 30 lượt/24h/IP và lá chắn nhịp theo IP. `/hoi-thoai/nhap` chỉ ghi vào phiên của
  chính người gọi và chỉ nhận payload đúng hình `TraCuuResponse`.

## 10. Kiểm chứng

- pytest: YAML thiếu khoá/`phien_luu` còn sót/`mui_gio` sai → lỗi rõ; mốc ngày/tháng
  theo `Asia/Ho_Chi_Minh` (23:30 UTC = 06:30 hôm sau VN); đếm loại `loi`,
  `out_of_scope`, cache hit; 429 ngày trước tháng, `detail` chứa mốc, `Retry-After`;
  `soan-thao` 429 theo ngày rồi tháng; 403 tại lượt 51; `/han-muc` hình mới; `/ho-so` tổng hợp;
  yêu cầu nâng gói 201/409/422; test gói 1 cập nhật sau khi gỡ ẩn phiên; khách: thiếu
  `X-Khach-Id` → 401, lượt 11 trong 24h → 429 kèm `Retry-After`, `/soan-thao` khách → 401,
  `kiem_rate_limit` hai khoá khác cửa sổ không dọn dữ liệu nhau, `/han-muc` khách, `/hoi-thoai/nhap`
  201/422 và giới hạn 10 lượt.
- FE: `scripts/kiem-han-muc.ts` (phần trăm, ngưỡng màu, "Không giới hạn", định dạng
  mốc theo VN, câu chip "Còn N lượt hôm nay"); typecheck, lint, build; `kiem-phien`
  cập nhật.
- Chrome cửa sổ ẩn danh: hỏi 2 câu như khách, chip lượt thử giảm, tải lại mất đoạn chat,
  hạ tạm `khach.hoi_dap_24h: 2` để thấy thẻ hết lượt; đăng nhập từ thẻ đó và thấy đoạn chat
  thành phiên đầu tiên.
- Chrome với tài khoản chủ dự án: sidebar đủ ba khối; menu tài khoản; hồ sơ có lịch
  hoạt động; gửi yêu cầu nâng gói rồi thấy "Đang chờ duyệt"; hạ tạm
  `luot_moi_phien: 2` và `hoi_dap_ngay: 2` để thấy ba trạng thái hết hạn mức; trả lại.

## 11. Đo lường và điều kiện vận hành

- Sau 30 ngày mở đăng ký, đo bằng `traces` + `yeu_cau_nang_goi`: tỷ lệ tài khoản đã
  kích hoạt (≥1 lượt) chạm hạn ngày, chạm hạn tháng, chạm hạn bản thảo; số yêu cầu nâng
  gói; số tài khoản không quay lại sau lần chạm hạn đầu. Số không ai chạm thì nới; số
  chặn người dùng một lần rồi mất họ thì nới trước. Đây là dữ liệu, không phải mã: chỉ
  đổi YAML.
- Điều kiện vận hành trước khi mở đăng ký rộng: `KLAW_TRAN_CHI_PHI_NGAY_USD` nâng lên
  khoảng 10 (ở 2 USD, 50 tài khoản free dùng hết hạn ngày là mọi người khác bị chặn);
  Supabase bật xác nhận email khi đăng ký (chống tài khoản rác đẻ hàng loạt); lá chắn IP
  và nhịp 10 lượt/phút theo tài khoản giữ nguyên.
- Điểm nâng gói nằm trong luồng: thẻ 429 và thẻ đủ 50 lượt mở thẳng `ModalNangGoi`,
  không chuyển sang trang giá.

## 12. Thi công

Một plan, hai luồng song song như gói 1: backend (§4–§6, worktree riêng) và frontend
(§7–§8, worktree riêng) sau một task hợp đồng chung (YAML mới gồm `khach`, model
`HanMucResponse`, kiểu TS, migration 021, header `X-Khach-Id`). Ước lượng 12–14 task.

## 13. Ngoài phạm vi (2B và sau)

Vai trò admin và trang duyệt yêu cầu; xoá tài khoản (cần service-role key); ngôn ngữ;
thanh toán; thưởng tuần đầu, mời bạn; nâng trần chi phí hệ thống (biến môi trường,
khuyến nghị 10 USD/ngày khi mở rộng).
