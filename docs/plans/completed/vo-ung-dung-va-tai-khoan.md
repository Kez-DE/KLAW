# Execution Plan: Vỏ ứng dụng, tài khoản và hạn mức ngày/tháng (gói 2A)

Date: 2026-09-07

## Status

Completed

## Spec / Plan

- docs/superpowers/specs/2026-09-07-vo-ung-dung-va-tai-khoan-design.md
- docs/superpowers/plans/2026-09-07-vo-ung-dung-va-tai-khoan.md

## Progress

- [x] Task 1 hợp đồng: YAML v3, gói hiệu lực, migration 021, schema, header khách
- [x] Task 2 gỡ ẩn phiên, trần lượt mỗi phiên
- [x] Task 3 hạn mức ngày/tháng/lá chắn, cổng khách
- [x] Task 4 /han-muc v2, /ho-so, /nang-goi, /hoi-thoai/nhap
- [x] Task 5 FE khách + hạn mức + thanh đo
- [x] Task 6 TaiKhoanProvider + AppShell ChatGPT
- [x] Task 7 /dung-thu: khách, trần phiên, 429, hết hạn
- [x] Task 8 /tai-khoan, cá nhân hoá, bỏ Vai trò
- [x] Task 9 ModalNangGoi + bảng giá
- [x] Task 10 soạn thảo: khách → đăng nhập
- [x] Task 11 gộp, kiểm, Chrome, đóng

## Decisions

Phán quyết trong lúc thi công (spec là thẩm quyền, plan là lập luận của spec):

1. **Hai hàm cùng tên `dem_luot`** ở hai module (`hoi_thoai.dem_luot(id)` đếm lượt trong phiên,
   `bao_ve.dem_luot(sub, endpoint, tu_luc)` đếm traces) được giữ nguyên tên; mọi lời gọi ghi rõ
   module.
2. **Giao diện soạn thảo không gọi `POST /soan-thao`** — nó gọi `GET /mau/{loai}` và `POST /soat`,
   cả hai qua cổng nhẹ. Toàn bộ 514 traces `/soan-thao` trong 30 ngày đều `user_sub` rỗng (script).
   Vì vậy hạn mức bản thảo hiện chỉ cưỡng chế được với client gọi API, chưa cưỡng chế qua giao diện.
   **Việc của chủ dự án:** chọn (a) đưa `/soat` qua `cong_bao_ve` và tính vào `soan_thao_*`, hoặc
   (b) cho giao diện đi qua `/soan-thao`.
3. **`het_han_luc` trả về bất cứ khi nào `users.plan_het_han` có giá trị** (kể cả đã hết hạn, khi
   `plan` đã về free) để giao diện hiện được thẻ "Gói Cá nhân đã hết hạn". Spec §6.1 đã sửa cho khớp.
4. **Lá chắn `ip-ngay:` giữ nguyên vị trí trước xác thực** cho cả tài khoản và khách (spec §4.2 nói
   rõ), nhưng **`la_chan.ip_ngay` nâng 400 → 1500**: lá chắn đếm lượt gọi ở cổng (kể cả cache hit và
   lỗi) còn hạn mức gói đếm lượt tính tiền, nên ở 400 một tài khoản Cá nhân trên IP cố định không bao
   giờ chạm nổi 500/ngày đã quảng cáo, và hai người dùng Miễn phí sau một NAT văn phòng không thể
   cùng dùng hết 200/ngày.
5. **Chip cạnh ô hỏi bám hạn mức hỏi đáp** (`khach_24h` với khách, `hoi_dap_ngay` với tài khoản),
   không dùng "mục ràng buộc đầu tiên" — nếu không, người dùng Cá nhân thấy hạn mức bản thảo cạnh ô chat.
6. **Người đã đăng nhập hết lượt KHÔNG bị khoá ô nhập**: 429 của máy chủ là trạng thái hết hạn mức và
   `BaoLoi` mang nút "Nâng cấp" (spec §7.3 đòi mọi trạng thái đều có nút hành động). Khách vẫn bị khoá
   kèm thẻ đăng nhập.
7. **Mức nhiệt của lịch hoạt động chia theo THỨ HẠNG giá trị phân biệt**, không theo tứ phân vị giá trị
   (tứ phân vị sụp khi phần lớn ngày có cùng số nhỏ — hình dạng thường gặp của số câu hỏi mỗi ngày).
8. **Hàng "Phiên lưu" plan nhắc không tồn tại** trong `bang-gia.tsx` (gói 1 đã gỡ cơ chế ẩn phiên);
   thay bằng hàng bản thảo, không đổi nhãn hàng.
9. **Gói Cá nhân hiện "₫499.000 / 30 ngày" ở CẢ hai trạng thái công tắc theo tháng/theo năm** — spec
   §7.6 bán Pro theo chu kỳ 30 ngày, quảng cáo giá năm cho gói chưa có thanh toán là lời hứa không giữ được.
10. **Hai gói chưa mở bán không công bố con số hạn mức nào** (ô bảng "Sắp công bố", gạch đầu dòng không
    mang số) — không có số v3 cho chúng.
11. **Đóng luôn lối vòng của cổng soạn thảo**: khi là khách, các bước 2-5 và nút "Bước tiếp theo" bị vô
    hiệu, thay vì chỉ ẩn nút bắt đầu. Tra cứu, soát văn bản và xuất file vẫn mở theo §7.3.
12. **Không kiểm được giao diện khách bằng trình duyệt** (công cụ không mở được cửa sổ ẩn danh và tôi
    không đăng xuất tài khoản của chủ dự án). Hành vi khách được kiểm ở mức API: `GET /han-muc` với
    `X-Khach-Id` trả `plan: "khach"`, `ten_goi: "Dùng thử"`, `khach_24h` 10, `phien.luot_toi_da` 10;
    không header → 401. **Việc của chủ dự án:** một lượt xem bằng mắt ở cửa sổ ẩn danh.

## Result

Nhánh `feat/tro-ly-phap-luat`, 24 commit từ `0f8ff8b` tới `559d0c0` (gồm hai commit gộp `e82a067`
`d95ef60` và làn sóng sửa cuối `925c08e` `559d0c0`).

Kiểm chứng trên nhánh đã gộp:

- `.venv/bin/ruff check src/ tests/` — sạch.
- `pytest` (bỏ `tests/test_infra`, `test_effectivity.py`) — 1615 đạt, 1 xfail, 1 đỏ:
  `tests/test_services/test_moi_mau.py` (file bẩn có sẵn của chủ dự án, đỏ từ trước nhánh này).
  `tests/test_api/` riêng: 317 đạt, 1 xfail.
- `frontend: npm run kiem` — exit 0 (16 script kiểm, gồm `kiem-han-muc` 4/4, `kiem-lich-hoat-dong`
  18/18, `kiem-quay-lai` 11/11, `kiem-phien` 3/3).
- Chrome trên mã đã gộp, tài khoản đã đăng nhập: vỏ ứng dụng (Phiên mới, Gần đây, thẻ tài khoản),
  menu tài khoản kèm thanh đo, modal nâng gói hai card, luồng gửi yêu cầu tới "Đang chờ duyệt"
  (hàng thử đã xoá), `/tai-khoan` với ba thanh đo và lịch hoạt động, `/bang-gia` giữ
  "₫499.000 / 30 ngày" ở cả hai trạng thái công tắc.

Quy trình: 11 task, mỗi task một implementer riêng và một review riêng; 9 vòng sửa; một review toàn
nhánh (0 Critical, 8 Important) và một làn sóng sửa duy nhất, tất cả đã được re-review xác nhận.

## Nợ kỹ thuật đã ghi nhận

- `rate_limit_luot` không có bộ dọn: hàng của mã khách không quay lại nằm mãi. Cách rẻ nhất là một
  `DELETE` theo tuổi trong `lifespan` của `main.py`.
- `src/services/bao_ve.py` 776 dòng, có sẵn đường tách (`han_muc` helpers → `src/services/han_muc.py`).
- `ENDPOINT_TON_LLM` không còn dùng trong `src/`, chỉ còn hai test giữ bất biến "/soat không tốn lượt".
- Dưới 48rem, `signOut` của `useAuth` đổi danh tính mỗi lần render nên memo của context không giữ được.
- Chưa có test cho `khach.ts` (không có script kiểm nào phủ file này).
- Ngoài phạm vi gói này: admin duyệt yêu cầu nâng gói (2B), xoá tài khoản, đổi ngôn ngữ, trí nhớ xuyên
  phiên cho Cá nhân (gói 3), "Hướng dẫn" đã rời khỏi NAV (vẫn ở menu Trợ giúp).
