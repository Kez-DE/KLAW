# Execution Plan: Truy cập bằng tài khoản và dọn giao diện trả lời

Date: 2026-09-06

## Status

Completed

## Spec / Plan

- docs/superpowers/specs/2026-09-06-truy-cap-va-giao-dien-tra-loi-design.md
- docs/superpowers/plans/2026-09-06-truy-cap-va-giao-dien-tra-loi.md

## Progress

- [x] Task 1 GET /van-ban
- [x] Task 2 nhãn hiệu lực sang KhungDoiChieu, helper căn cứ
- [x] Task 3 TheKetQua chỉ luật còn hiệu lực
- [x] Task 4 ManChao trong /dung-thu
- [x] Task 5 xoá Trò chuyện, /chat redirect
- [x] Task 6 khoá ô hỏi khi chưa đăng nhập, next=
- [x] Task 7 chữ "dùng thử", 401, bảng giá
- [x] Task 8 Tra cứu duyệt kho
- [x] Task 9 kiểm chung, chụp màn, đóng plan

## Decisions

- Thứ tự BE→card→gộp→truy cập→tra cứu
- next whitelist hai giá trị /dung-thu, /soan-thao
- Cột Miễn phí trong bảng so sánh
- Nhãn chua_xac_dinh thêm ở Task 9

## Result

Kiểm bằng Chrome (controller thực hiện ở Task 9, nguyên văn):

- `/tra-cuu` không từ khoá: "1626 văn bản", chỉ chip Mới nhất / Còn hiệu lực trước; tick Nghị định → "696 văn bản · Nghị định" (khớp `/bo-loc`). Ảnh `.tham-dinh-shots/10-tra-cuu-duyet-kho.jpg`, `10b-tra-cuu-loc-nghi-dinh.png`.
- `/chat?q=abc` → `/dung-thu?q=abc`, câu hỏi tự gửi (phiên đã đăng nhập) → card `partial_coverage` không còn khối đỏ.
- Câu "Thời gian thử việc tối đa với công việc của người quản lý doanh nghiệp là bao lâu?" → văn xuôi có thẻ `doc`/`cite`, khối "Liên kết tra cứu toàn văn", dòng miễn trừ; KHÔNG có "Cảnh báo hiệu lực", KHÔNG có danh sách trích dẫn; bấm "Khoản 1 Điều 25" → khung đối chiếu, dưới số ký hiệu 45/2019/QH14 có nhãn "Một phần không xác định". Ảnh `11-card-chi-luat-con-hieu-luc.jpg`.
- `/dung-thu` trống: màn chào đúng Image 6. Ảnh `09-man-chao.jpg`.
- CHƯA kiểm: ô hỏi bị khoá khi ĐÃ ĐĂNG XUẤT (controller không đăng xuất phiên của chủ dự án). Ghi vào Result là "chủ dự án tự kiểm: đăng xuất → /dung-thu".
- Lỗi phát hiện và sửa ở mục A: nhãn `chua_xac_dinh` in thô.

Kiểm chung Task 9 (foreground, 2026-09-06):

- `make lint`: `ruff check src/ tests/` — All checks passed.
- `python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py`: 1534 passed, 0 failed, 1 xfailed (hai fail đã biết nằm trong hai đường dẫn bị ignore).
- `cd frontend && npm run kiem`: xanh hết chuỗi (typecheck, lint, kiem-trich-dan, kiem-xep-trich-dan, kiem-sse, kiem-font, kiem-lich-su, kiem-van-xuoi, kiem-ngay, kiem-soat, kiem-khung, kiem-bang, kiem-bang-ket-qua, kiem-documents, kiem-quay-lai, do-tuong-phan.py, build) — `kiem-quay-lai`: 9/9 đạt; `kiem-xep-trich-dan`: 8 nhóm kiểm — ĐẠT.

Commit các Task 1–8: a3ad070, 4e5db09, 3a832da+69e9d55+074de04, b66e03c, 76b334d+7ab79da, 5ea4e6e, f824c45, 884cc61.
Commit phụ lục Task 9 (ba sửa nhỏ A+B): 0f7dfd8.
