# Execution Plan: Soạn thảo trong chat và card câu trả lời

Date: 2026-09-06

## Status

Active

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

- [ ] Bước 0: Task 1–2
- [ ] Bước 1 BE: Task 3–5
- [ ] Bước 1 FE: Task 6–8
- [ ] Bước 2: Task 9

## Decisions

- 2026-09-06: Q1 mức B (biểu mẫu + bản thảo, không LLM viết điều khoản); Q2
  router LLM chọn loại; Q3 thêm mẫu thoả thuận chấm dứt; Q4 PA1 khung bên
  cạnh; Q5 card cho mọi trả lời. Chủ dự án chọn.

## Validation

- Focused proof: `pytest tests/test_agents/test_route.py tests/test_agents/test_assemble.py
  tests/test_agents/test_huong_dan_soan_thao.py tests/test_services/test_moi_mau.py
  tests/test_eval/test_run_trap.py`; `npm run kiem-khung`, `kiem-goi-y-soan-thao`.
- Integration / end-to-end: `pytest tests/test_api/test_tra_cuu.py`; 3 câu bẫy
  `soan_thao` với route v2; kiểm bằng mắt trên `/dung-thu`.
- Repository-required checks: `make lint`, pytest rộng, `npm run typecheck && npm run lint && npm run build`.

## Result

Chưa xong.
