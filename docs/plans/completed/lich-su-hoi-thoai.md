# Execution Plan: Lịch sử hội thoại theo tài khoản

Date: 2026-09-07

## Status

Completed

## Spec / Plan

- docs/superpowers/specs/2026-09-07-lich-su-hoi-thoai-design.md
- docs/superpowers/plans/2026-09-07-lich-su-hoi-thoai.md

## Progress

- [x] Task 1 hợp đồng + migration 020 + phien_luu
- [x] Task 2 dịch vụ hoi_thoai
- [x] Task 3 stream/POST ghi lượt
- [x] Task 4 router /hoi-thoai
- [x] Task 5 helper + hook FE
- [x] Task 6 use-tra-cuu + ?phien=
- [x] Task 7 DanhSachPhien
- [x] Task 8 gộp, kiểm, Chrome, đóng

## Decisions

- Chuỗi lỗi dùng chung nằm ở `src/services/hoi_thoai.py` (`LOI_KHONG_THAY`,
  `LOI_PHIEN_AN`); Task 3 và Task 4 import thay vì chép nguyên văn — đổi lại là
  một module dịch vụ giữ chữ hiển thị của tầng HTTP (mùi phân tầng nhẹ).
- Giữ `TRA_LOI_TOI_DA = 2000` trong `lich_su_gan_nhat` (trần theo dây, hợp với
  pydantic) dù FE `dungLichSu` cắt ở 400: `giai_nghia` tự cắt lại theo ngân sách
  prompt của nó, nên lịch sử phía máy chủ là tập cha chứ không phải một mức lệch
  — sai thì tốn vài trăm token prompt mỗi lượt nối tiếp.
- `_chuan_bi_phien` KHÔNG nuốt lỗi DB: chính Postgres đó đã gác request ở
  `cong_bao_ve` (`ghi_nhan_nguoi_dung`, `kiem_han_muc_thang`), nên hỏng ở đây là
  sự cố thật và FE đã hiện lỗi máy chủ thử lại được; hạ xuống `hoi_thoai_id=None`
  là âm thầm đánh rơi một lượt của người đã đăng nhập khỏi lịch sử.
- Nút mở bottom sheet dùng khoảng chừa cố định `bottom-[156px]` thay vì đo khớp
  chân trang — sai thì nút nổi cao hơn ô soạn ~20–40px trên máy rộng.
- Bỏ mục kiểm `tieuDeMacDinh` phía FE trong spec §8, thay bằng test Python ở
  Task 2 (máy chủ sở hữu tiêu đề, FE không giữ bản sao); `kiem-phien` phía FE lo
  phần chữ và các vị từ.
- Câu đếm phiên ẩn dùng tên gói thật qua `tenGoi(plan)` thay vì cố định
  "Miễn phí" — tránh chữ sai cho tài khoản pro.

## Result

- Merge: fc3af29 (backend, wt-be-phien) + 51960c6 (frontend, wt-fe-phien), rồi
  đợt sửa cuối 8556f9a (`fix: address final-review findings for conversation
  history`).
- `pytest` lúc gộp nhánh: 1583 passed / 1 xfailed / 1 lỗi nền đã biết (file bẩn
  `tests/test_services/test_moi_mau.py` của chủ repo).
- `pytest` chạy lại sau đợt sửa cuối (2026-09-07): 1669 passed / 1 xfailed /
  3 failed — ngoài `test_moi_mau.py` còn
  `test_infra/test_bat_bien_dinh_danh.py::test_tang_sau_moi_so_ky_hieu_la_duy_nhat`
  và `test_services/test_effectivity.py::test_chi_nhung_canh_ngay_mau_thuan_DA_BIET_moi_duoc_bo`.
  Cả hai đọc corpus trong DB và đỏ vì DỮ LIỆU đã nạp thêm, không liên quan tới
  mã của gói việc này (xem "Nợ để lại").
- `npm run kiem` (frontend): exit 0.
- Chứng cứ Chrome (tab chủ tài khoản đã đăng nhập, backend chạy với
  `KLAW_SUPABASE_URL`): tạo phiên + ghim id lên URL; hỏi nối tiếp được giải nghĩa
  bằng lịch sử từ máy chủ; chuyển qua lại giữa các phiên; tải lại trang vẫn giữ
  `?phien=`; đổi tên tại chỗ; danh sách báo phiên ẩn theo gói và chặn 403 (đặt
  tạm `phien_luu.free=1`, đã khôi phục); xoá tại chỗ → xoá mềm.
- Ảnh chụp: `.tham-dinh-shots/15-cot-phien-phien-dau.jpg`,
  `16-hoi-noi-tiep-trong-phien.jpg`, `17-tai-lai-giu-phien.jpg`,
  `18-doi-ten-tai-cho.jpg`, `19-phien-an-theo-goi-danh-sach.jpg`,
  `20-phien-an-403.jpg`, `21-xoa-xac-nhan-tai-cho.jpg`.

## Nợ để lại

- `GET /hoi-thoai?limit=50` chưa phân trang: tài khoản pro có hơn 50 phiên bị cắt
  im lặng → gói 2.
- `src/api/routes.py` dài 1034 dòng (quy tắc >800): tách ra sẽ tạo vòng import
  với `routes_luong`.
- Bottom sheet chưa đóng được bằng Escape (giống ngăn lọc ở tra cứu) → gộp vào
  một đợt a11y sau.
- `dang-nhap.tsx` cũng đọc `next` THÔ qua search non-strict của router (danh sách
  cho phép `locNext` không chạy lúc đọc) → vé riêng.
- Chỉ ở máy dev: FE thấy đã đăng nhập trong khi backend coi là ẩn danh khi
  `KLAW_SUPABASE_URL` rỗng.
- Hai test đỏ theo DỮ LIỆU corpus (`test_bat_bien_dinh_danh`,
  `test_effectivity`) — trùng `so_ky_hieu` và cạnh ngày mâu thuẫn mới sau đợt nạp
  văn bản gần nhất; cần mở dữ liệu ra xem, không thuộc gói việc này.
