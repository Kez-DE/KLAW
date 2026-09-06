# Execution Plan: Soạn thảo trong chat và card câu trả lời

Date: 2026-09-06

## Status

Completed

## Outcome

Trên `/dung-thu`: mọi câu trả lời nằm trong card; câu "soạn cho tôi hợp đồng
nghỉ việc" ra card gợi ý đúng loại (kèm loại thay thế) với nút "Soạn ngay tại
đây" mở màn soạn thảo ở khung bên cạnh; điền → soát → tải .docx/.pdf không rời
hội thoại. Kho mẫu có thêm "Thoả thuận chấm dứt hợp đồng lao động".

## Context

- Spec: `docs/superpowers/specs/2026-09-06-soan-thao-trong-chat-design.md`
- Plan từng bước: `docs/superpowers/plans/2026-09-06-soan-thao-trong-chat.md`
- Tiếp nối: `docs/plans/completed/soul-trich-dan-bam-duoc.md`

## Scope

In scope: checklist mới; router trả loại văn bản; `soan_thao_goi_y` trong
response; card bọc mọi trả lời; nhánh `huong_dan_soan_thao` có nút; tách
`KhongGianSoanThao`; khung soạn thảo bên phải; bẫy `soan_thao`.

Out of scope: trích dữ kiện từ câu chat; biểu mẫu trọn trong card; lưu hội
thoại; mở kho HN&GĐ.

## Approach

Bước 0 mẫu mới + hợp đồng dữ liệu → Bước 1 hai worktree (BE: router/assemble/
bẫy; FE: card/tách component/khung) → Bước 2 gộp, đo bẫy với
`ROUTE_PROMPT=prompts/route.v2.md`, đổi mặc định nếu xanh, đóng plan.

## Risks And Recovery

- Router chọn sai loại → giữ `route_prompt` v1; card vẫn có "Chọn loại văn bản".
- Tách component vỡ `/soan-thao` → `npm run build`/typecheck đỏ → revert commit tách.
- Khung soạn thảo chật cạnh chat → co cột chat hoặc phủ toàn màn dưới 80rem.
- `can_cu` mẫu mới không tồn tại → `test_moi_mau` integration đỏ → hạ cấp hoặc bỏ mục.

## Progress

- [x] Bước 0: Task 1–2
- [x] Bước 1 BE: Task 3–5
- [x] Bước 1 FE: Task 6–8
- [x] Bước 2: Task 9 — [x] 9a (gộp, đo bẫy, đổi mặc định) · [x] 9b (kiểm
      Chrome, đóng plan — controller)

## Decisions

- 2026-09-06: Q1 mức B (biểu mẫu + bản thảo, không LLM viết điều khoản); Q2
  router LLM chọn loại; Q3 thêm mẫu thoả thuận chấm dứt; Q4 PA1 khung bên
  cạnh; Q5 card cho mọi trả lời. Chủ dự án chọn.
- 2026-09-07 (Task 9a): gộp `wt-be-soan` trước `wt-fe-soan` (BE router/bẫy
  trước, FE tiêu thụ `soan_thao_goi_y` sau) — không xung đột, đúng dự kiến
  addendum.
- 2026-09-07 (Task 9a): `route_prompt` mặc định đổi sang
  `prompts/route.v2.md` — cả `trap-soan-01` và `trap-soan-02` đo `dung=True`,
  đạt ngưỡng bật.

## Validation

- Focused proof: `pytest tests/test_agents/test_route.py tests/test_agents/test_assemble.py
  tests/test_agents/test_huong_dan_soan_thao.py tests/test_services/test_moi_mau.py
  tests/test_eval/test_run_trap.py`; `npm run kiem-khung`, `kiem-goi-y-soan-thao`.
- Integration / end-to-end: `pytest tests/test_api/test_tra_cuu.py`; 3 câu bẫy
  `soan_thao` với route v2; kiểm bằng mắt trên `/dung-thu`.
- Repository-required checks: `make lint`, pytest rộng, `npm run typecheck && npm run lint && npm run build`.

## Result

Task 9a (2026-09-07), đo tại commit `4c0ef96` (sau gộp `wt-be-soan` +
`wt-fe-soan`, trước commit đổi mặc định này):

- Gộp: `git merge --no-ff wt-be-soan` (`8a949f7`) rồi
  `git merge --no-ff wt-fe-soan` (`4c0ef96`) trên `feat/tro-ly-phap-luat` —
  không xung đột (đúng dự kiến; `mau-van-ban.ts` auto-merge sạch).
- `make lint`: đạt (`ruff check src/ tests/` — All checks passed!).
- `python -m pytest -q --ignore=tests/test_infra
  --ignore=tests/test_services/test_effectivity.py`: 1563 passed, 1 failed, 1
  xfailed. Fail duy nhất là `test_KHONG_THEM_muc_moi_tu_khoa_khong_khop_than`
  trong `tests/test_services/test_moi_mau.py` — file test đang bẩn (chưa
  commit) của chủ dự án, không phải do gộp; không sửa, không stage. 1 xfailed
  là baseline đã biết (`test_han_muc_thang_KHONG_ro_khi_co_chum_song_song`).
- `cd frontend && npm run kiem`: đạt toàn bộ (`typecheck`, `eslint` — 0 lỗi/5
  warning fast-refresh không liên quan, 12 script `kiem-*` đều "đạt"/"OK",
  đối chiếu tương phản màu tự-kiểm OK, `vite build` client+ssr+nitro thành
  công).
- Đo bẫy `soan_thao` với `ROUTE_PROMPT=prompts/route.v2.md`
  (`eval/results/trap_soan_thao_4c0ef96.json`):

  | id | result_type | soan_thao_goi_y.loai | dung |
  |---|---|---|---|
  | trap-soan-01 | huong_dan_soan_thao | don_xin_nghi_viec (thay_the: thoa_thuan_cham_dut_hdld) | True |
  | trap-soan-02 | huong_dan_soan_thao | hdld | True |
  | trap-soan-03 | huong_dan_soan_thao | null (đúng — ngoài danh sách mẫu) | True |

  Ngưỡng bật (`trap-soan-01` và `trap-soan-02` đều `dung=True`) đạt → đổi
  `route_prompt` mặc định sang `prompts/route.v2.md` trong `src/config.py`;
  đổi tên/kỳ vọng test `tests/test_config.py::test_route_prompt_mac_dinh_v1`
  → `test_route_prompt_mac_dinh_v2`. `pytest tests/test_config.py -q`: 13
  passed.
Task 9b (2026-09-07), kiểm bằng mắt qua Chrome:

- Chrome (hồ sơ mới, chưa đăng nhập, :3000 auth bật): ô hỏi được thay bằng thẻ "Đăng nhập để hỏi KLAW. Tài khoản mới dùng gói Miễn phí." với hai nút mang `?next=/dung-thu` — đóng luôn mục còn nợ của gói trước. Ảnh `.tham-dinh-shots/09b-man-chao-khoa-dang-nhap.png`.
- Chrome (cặp server phụ :3001/:8001, auth tắt để không cần đăng nhập): gõ "soạn cho tôi hợp đồng nghỉ việc" → card "Gợi ý soạn thảo": "Tôi hiểu bạn cần đơn xin nghỉ việc: …", nút "Soạn ngay tại đây", chip "Thoả thuận chấm dứt hợp đồng lao động", nút "Chọn loại văn bản". Ảnh `12-card-goi-y-soan-thao.png`.
- Bấm "Soạn ngay tại đây" → khung soạn thảo mở bên cạnh chat (URL không đổi), tiêu điểm vào nút Đóng, năm bước + xem trước + nút tải .docx/.pdf, lịch sử phiên ẩn. Ảnh `13-khung-soan-thao-ben-canh.png`. Escape đóng khung và trả tiêu điểm về nút mở. Bấm chip → khung remount sang mẫu "Thoả thuận chấm dứt hợp đồng lao động" (7 Điều).
- Ghi nhận để xử lý sau: `ly_do` do router sinh viết ở ngôi thứ ba ("Người dùng yêu cầu…") trong câu "tôi/bạn"; mẫu thoả thuận đang gán Bên B là "(TỔ CHỨC)" trong khi người lao động là cá nhân.

Final fix wave (2026-09-07), sau khi neo giọng `ly_do` trong `prompts/route.v2.md` (gọi "bạn", không mở đầu bằng "Người dùng"/"Yêu cầu"): đo lại 3 câu bẫy `soan_thao`, kết quả 3/3 `dung=True` (`eval/results/trap_soan_thao_final_fix.json`).
