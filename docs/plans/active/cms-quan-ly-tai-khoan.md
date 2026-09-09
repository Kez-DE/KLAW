# Execution Plan: CMS quản lý tài khoản (gói 2B)

Date: 2026-09-08

## Status

Active

## Outcome

Một CMS Payload chạy độc lập (`cms/`, cổng 3001, database `klaw_cms`) cho phép
admin KLAW xem tài khoản, duyệt hoặc từ chối yêu cầu nâng gói, đặt gói tay, thu
hồi, khoá và mở khoá tài khoản — mọi thao tác đổi trạng thái đều bắt buộc lý do
và được ghi vào nhật ký chỉ-ghi-thêm của KLAW. Người dùng KLAW thấy lý do từ
chối và thẻ tài khoản bị khoá; hai phía nhận thông báo qua SSE (giai đoạn 3).

## Context

- Spec: `docs/superpowers/specs/2026-09-08-cms-quan-ly-tai-khoan-design.md`
  (thay hai bản nháp 2B cùng ngày).
- Khảo sát console quản trị tổ chức lớn:
  `docs/superpowers/specs/2026-09-08-khao-sat-console-quan-tri-to-chuc-lon.md`
  (đề xuất A, B, C đã đưa vào gói qua Task 7b, 13, 14).
- Plan thực thi: `docs/superpowers/plans/2026-09-08-cms-quan-ly-tai-khoan.md`
  (19 task, 3 giai đoạn).
- Ledger phiên làm việc (git-ignored):
  `.superpowers/sdd/2026-09-08-cms-quan-ly-tai-khoan/progress.md` — mọi
  `Ruling:` và mốc commit từng task nằm ở đó.
- Bất biến kiến trúc liên quan: `docs/patterns/encoding-invariants.md`.

## Scope

In scope:

- KLAW: migration 022, dịch vụ `nhat_ky`, `thong_bao`, `nang_goi` (duyệt, từ
  chối, đặt gói, thu hồi), `tai_khoan_qt` (khoá, mở khoá, tìm, chi tiết), cổng
  `/api/v1/admin/*` sau khoá API server-side, cờ `bi_khoa` trong `/han-muc`.
- CMS Payload 3.88: đăng nhập cục bộ hai vai trò, proxy allowlist tới KLAW,
  bốn view (Tổng quan, Yêu cầu, Tài khoản, Nhật ký), `start.sh` xác minh
  migration, job CI `cms`, runbook `cms/README.md`.
- Frontend KLAW: lý do từ chối trong `ModalNangGoi`, thẻ tài khoản bị khoá,
  cổng soạn thảo tôn trọng trạng thái khoá.
- Giai đoạn 3 (cắt được): hộp thư thông báo hai phía, SSE, chuông CMS và FE.

Out of scope:

- Thanh toán trực tuyến; 2FA cho admin CMS (Payload 3.88 không có sẵn);
  stream nhật ký ra kho ngoài; triển khai Railway thật (KLAW chưa deploy).

## Approach

Thực thi theo superpowers:subagent-driven-development: một implementer mới cho
mỗi task (TDD), một reviewer theo task, vòng fix có phạm vi, review toàn nhánh
ở cuối. Giai đoạn 1 (KLAW) → giai đoạn 2 (CMS) → giai đoạn 3 (thông báo).

## Risks And Recovery

- Khoá admin lọt ra trình duyệt → bí mật chỉ ở `cms/src/lib/klaw-client.ts`,
  `tests/bundle.spec.ts` quét `.next/static` sau mỗi build.
- `/admin` mở khi thiếu khoá → fail-closed 503 khi `KLAW_ADMIN_API_KEY` rỗng;
  guard khởi động từ chối `admin_api_key` kèm `rate_limit_so_luot <= 0`.
- Migration Payload không áp dụng trong production → `scripts/start.sh` đọc
  lại `migrate:status` và từ chối khởi động khi còn dòng `No`.
- Rollback: mọi thay đổi nằm trên nhánh `feat/tro-ly-phap-luat`; migration 022
  chỉ thêm bảng/cột mới; CMS dùng database riêng nên gỡ bằng `DROP DATABASE
  klaw_cms`.

## Progress

- [x] Giai đoạn 1 — KLAW (Task 1–7, 7b): migration 022, dịch vụ, cổng admin,
  lý do bắt buộc cho mọi thao tác đổi trạng thái.
- [x] Giai đoạn 2 — CMS Payload (Task 8–14): khởi tạo, vai trò, proxy, bốn
  view, `start.sh`, CI, README, migration đầu tiên. HEAD sau giai đoạn: `a7dedd7`.
- [x] Task 15 — Frontend KLAW: lý do từ chối và thẻ tài khoản bị khoá
  (commit `6780dbb` + fix `bcbc403`; trạng thái giao diện chưa quan sát trên
  trình duyệt vì cần phiên Supabase thật).
- [x] Task 16 — KLAW: thông báo admin khi có yêu cầu, sáu endpoint hộp thư, SSE
  (commits `27abeb8`, `92b2b25`, fix `7f3c76f`; suite rộng 1285 passed / 0 failed).
- [x] Task 17 — chuông CMS (commit `b1f65e3` + fix `6e22935`: dashboard một
  header/một chuông/một kết nối SSE, không rung ở lần tải đầu, token CSS thật).
- [x] Task 18 — chuông frontend (commit `018ebec` + fix `ab24a37`, re-review
  sạch; trạng thái giao diện chưa quan sát trên trình duyệt vì cần phiên
  Supabase thật).
- [ ] Review toàn nhánh ba ghế: KLAW (xong, đợt sửa `a0db9fe`, re-review
  sạch), CMS + CI (xong, đợt sửa đang chạy), frontend + hợp đồng liên ranh
  giới (xong — ma trận hợp đồng khớp toàn bộ; đợt sửa `33f8a27`: vị trí
  popover chuông theo `viTri`, một luồng SSE dùng chung qua `TaiKhoanProvider`,
  backoff nối lại, thẻ khoá trên `/tai-khoan`, gate bảng xem trước soạn thảo;
  re-review sạch, vòng 2 `e4850ce` memo kết quả hook để context ổn định).

## Decisions

- 2026-09-08: Payload 3.88.0 thay vì 4.0 canary (pre-alpha); database
  `klaw_cms` riêng thay vì `schemaName` (còn gắn nhãn experimental).
- 2026-09-08: Đưa đề xuất A (lý do bắt buộc cả khi mở khoá và đặt gói tay), B
  (công bố trần xuất CSV 5.000 dòng), C (chính sách lưu nhật ký) vào gói 2B.
- 2026-09-09: Job CI `cms` chạy không lọc đường dẫn (lọc ở mức workflow sẽ
  chặn cả job Python); `pnpm/action-setup@v4` đọc `cms/package.json` qua
  `package_json_file`.
- 2026-09-09: Kiểm migration trên database tạm `klaw_cms_kiem_migrate` (tạo
  rồi xoá), không đụng `klaw_cms` dev.
- 2026-09-09: Không duyệt yêu cầu nâng gói thật nào bằng agent; việc "duyệt
  một yêu cầu thật từ giao diện" ở cuối giai đoạn 2 để chủ dự án tự làm.
- 2026-09-09: Cổng soạn thảo nằm ở `frontend/src/components/soan-thao/
  KhongGianSoanThao.tsx` (plan trỏ sai `routes/soan-thao.index.tsx`); không
  dùng `baogia@klaw.vn` (địa chỉ báo giá) làm email hỗ trợ.
- 2026-09-09: Thẻ tài khoản bị khoá trên `/dung-thu` đặt ở vùng banner luôn
  render (cùng cấp banner `hetHanPro`) và loại `biKhoa` khỏi điều kiện màn
  chào — mốc plan "ngay trước `traCuu.loi`" nằm trong khối chỉ hiện sau khi đã
  gửi câu hỏi, mà người bị khoá không gửi được.
- 2026-09-09: Ba endpoint hộp thư người dùng (`/thong-bao*`) dùng
  `nguoi_dung_ke_ca_khoa` (xác thực bắt buộc, không `kiem_khoa`): người bị khoá
  phải đọc được chính thông báo "tài khoản bị khoá"; đọc thông báo không tốn
  LLM nên thuộc nhóm vẫn mở như `/han-muc`, `/nguoi-dung`.
- 2026-09-09: Chuông frontend ở rail icon hẹp (48–80 rem) xếp dọc với thẻ tài
  khoản thay cho hàng ngang của plan (rail rộng 48 px, hàng ngang cần ≈ 88 px);
  nút "Đã đọc tất cả" gate theo `so_chua_doc` của máy chủ và đánh dấu các mục
  đã tải, bấm lại để xử lý phần còn lại — không đổi backend.
- 2026-09-09 (review toàn nhánh, cần chủ dự án quyết): (a) probe `/admin`
  không có khoá vẫn ghi một dòng nhật ký mỗi lần dưới bucket chung 60/60s —
  đề xuất bucket riêng `chan-admin:{ip}` chặt hơn cho các lần xác thực thất
  bại; đây là chính sách quan sát được từ ngoài chưa có trong spec nên chưa
  sửa; (b) job CI `cms` chưa từng chạy trên GitHub — cần một lần push để
  chứng minh; nếu `pnpm build` lỗi vì `klaw_cms_test` chưa có schema, thêm
  bước `pnpm migrate` trước build.
- Follow-up (2C): luồng SSE `luong_thong_bao.phat` chỉ so sánh SỐ chưa đọc,
  nên khi một thông báo cùng loại thay thế thông báo chưa đọc (đặt gói lần
  hai, mở khoá lần hai) số không đổi và không có sự kiện đẩy; REST vẫn là
  nguồn sự thật. Sửa: so sánh `(count, max id chưa đọc)` bằng một truy vấn
  trong `thong_bao` và chỉnh unit test của `phat`.
- Follow-up (2C): lọc "hết hạn trong 7 ngày" ở view Tài khoản chạy phía
  client trên 50 tài khoản mới nhất; cần tham số `sap_het_han` ở
  `GET /admin/tai-khoan` để khớp số trên dashboard khi vượt 50 tài khoản.
- Follow-up (ngoài phạm vi gói này): bảng xem trước A4 trong
  `KhongGianSoanThao.tsx` gọi `setBuoc` không qua cổng `laKhach`/`biKhoa`
  (lỗ hổng có sẵn cho khách trước gói 2B); cần một ticket riêng.
- 2026-09-09 (thiết kế lại giao diện CMS, theo yêu cầu chủ dự án): thẻ trắng
  bo góc 12 px trên nền giấy lạnh, mực sapphire, đồng thau chỉ làm điểm nhấn
  (viền tiêu điểm, chip đang chọn, huy hiệu); token Payload được ánh xạ lại
  trong `cms/src/app/(payload)/custom.scss`, thành phần dùng chung `klaw-*`
  trong `cms/src/styles/thanh-phan.scss` (`.klaw-the`, `.klaw-luoi`,
  `.klaw-dai-so` dùng subgrid để số liệu cùng baseline, `.klaw-bang` ô không
  xuống dòng và cuộn ngang trong thẻ, cột chữ dài opt-in `boc`). Header dùng
  khoá hiệu dấu + chữ KLAW (`DauKlawNho`), nới hộp `.step-nav__home` của
  Payload vốn 16–18 px và ẩn phần tràn. Font Be Vietnam Pro và JetBrains Mono
  tự host trong `cms/public/fonts/`. Chỉ một chuyển động được viết tay: chấm
  trực tuyến thở, tắt khi `prefers-reduced-motion`.
- 2026-09-09 (trạng thái trực tuyến, chủ dự án chọn phương án "theo kết nối
  thông báo đang mở"): một tài khoản "đang trực tuyến" khi có ít nhất một luồng
  SSE `luong_thong_bao.phat` đang mở; sổ đếm trong tiến trình (`_TRUC_TUYEN`,
  đăng ký/huỷ trong `try/finally` của `phat`), không thêm dữ liệu theo dõi mới.
  Lộ ra qua `GET /admin/truc-tuyen`, cờ `truc_tuyen` trên danh sách và chi tiết
  tài khoản, `dang_truc_tuyen` trên tổng quan; CMS cho vai trò `doc` đọc được.
  CMS thăm dò mỗi 15 giây qua một poller dùng chung (`cms/src/lib/truc-tuyen.ts`),
  giữ kết quả tốt cuối cùng khi lỗi. Trần đã biết (`ponytail:`): sổ đếm nằm
  trong một tiến trình, chạy nhiều worker uvicorn sẽ đếm thiếu — nâng lên
  Redis hoặc bảng `phien_sse` khi triển khai nhiều worker.
- 2026-09-09 (cần chủ dự án quyết): lá chắn IP 60 lượt/60 giây của `/admin/*`
  tính theo IP nguồn, mà mọi lời gọi từ CMS tới KLAW đều đi từ một IP máy chủ
  CMS — nhiều admin làm việc cùng lúc (hoặc dev hot-reload nhiều tab) sẽ đụng
  429 chung. Đề xuất: bucket theo admin (header định danh do CMS gắn) hoặc nới
  trần cho IP của CMS; là chính sách quan sát được từ ngoài nên chưa sửa.

## Validation

- Focused proof: pytest cho từng dịch vụ và route admin (`tests/test_services/
  test_{migration_022,nhat_ky,thong_bao,nang_goi_duyet,tai_khoan_qt}.py`,
  `tests/test_api/test_{admin_routes,admin_cong,tai_khoan_khoa,guard_khoi_dong,
  luong_thong_bao,thong_bao_api}.py`); vitest trong `cms/tests/` (36 test sau
  đợt sửa cuối, gồm quét bí mật trong `.next/static` và guard database test);
  `frontend/scripts/kiem-han-muc.ts` 5/5, `kiem-thong-bao.ts` 8/8, `kiem-sse.ts` 9/9.
- Hai test bất biến tự chứng minh chiều dương (regex bắt được vi phạm giả)
  trước khi quét cây: chỉ `nang_goi.py` được `UPDATE users SET plan`; không
  `UPDATE`/`DELETE` lên `nhat_ky_quan_tri` trong `src/`.
- Integration or end-to-end proof: curl qua proxy CMS với cookie admin (403 cho
  vai trò `doc`, 409/423 nghiệp vụ), Chrome DevTools trên bốn view với dữ liệu
  dùng một lần — ảnh `.tham-dinh-shots/cms-02-yeu-cau.png`, `cms-03-tu-choi.png`,
  `cms-04-tai-khoan.png`, `cms-05-chi-tiet-khoa.png`, `cms-06-nhat-ky.png`.
  Frontend (Task 15) chưa quan sát trên trình duyệt vì cần phiên Supabase thật.
- Repository-required checks: `ruff check src/ tests/`; bộ pytest rộng với
  `KLAW_SUPABASE_URL=` (0 failed sau Task 7b); `cd cms && pnpm lint && pnpm
  type-check && pnpm build && pnpm test`; `cd frontend && npm run typecheck &&
  npm run lint && npm run build`. CI job `cms` chưa chạy trên GitHub (chưa push).

## Result

Hoàn tất mã nguồn trên nhánh `feat/tro-ly-phap-luat` (40 commit từ mốc
`8910401`, HEAD `dbef66a`): 19 task, mỗi task một review riêng và tối đa một
vòng sửa; review toàn nhánh ba ghế (KLAW, CMS + CI, frontend + hợp đồng) đều
"With fixes", không có Critical; ba đợt sửa cuối (`a0db9fe`, `33f8a27` +
`e4850ce`, `dbef66a`) đã qua re-review có phạm vi.

Kết quả đã xác minh:

- KLAW: suite rộng 1286 passed / 0 failed (với `KLAW_SUPABASE_URL=` để bỏ
  auth thật của `.env.local`); cổng `/admin` fail-closed, một đường đổi gói,
  nhật ký chỉ ghi thêm, hộp thư cách ly theo người nhận, người bị khoá vẫn
  đọc được thông báo của mình.
- CMS: 36 test vitest xanh; bí mật không lọt `.next/static`; proxy allowlist
  15 hàng khớp 1:1 với 15 route admin; `start.sh` từ chối khởi động khi
  migration chưa áp dụng hoặc production thiếu origin.
- Frontend: typecheck, lint, build và ba script kiểm xanh; hợp đồng với
  backend khớp toàn bộ (kiểu, guard, khung SSE, đường dẫn).

Giới hạn còn lại:

- Chưa quan sát giao diện frontend trên trình duyệt (cần đăng nhập Supabase
  thật); thứ tự nên kiểm: popover chuông ở ba cỡ màn hình, `/tai-khoan` của
  tài khoản bị khoá, chiều cao hai card trong `ModalNangGoi`.
- Job CI `cms` chưa chạy trên GitHub (cần push); yêu cầu nâng gói thật
  (`dev@gmail.com`) chưa được duyệt từ giao diện — hai việc này và bucket riêng
  cho probe `/admin` chờ chủ dự án quyết (xem Decisions).
- Follow-up 2C đã liệt kê ở Decisions (SSE khi thông báo thay thế, lọc hết
  hạn phía máy chủ).

Sau khi chủ dự án xem và làm các kiểm tay trên, chuyển file này sang
`docs/plans/completed/`.
