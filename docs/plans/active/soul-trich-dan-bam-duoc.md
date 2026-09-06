# Execution Plan: SOUL và trích dẫn bấm được

Date: 2026-09-06

## Status

Active

## Outcome

Trên `/dung-thu`: câu trả lời giọng luật sư xưng "tôi"; tên văn bản và số Điều
trong văn xuôi là nút bấm mở `KhungDoiChieu`; khối "Liên kết tra cứu toàn văn"
dựng từ `documents[].links`; chân trang ⚖️ ở `answer` và `partial_coverage`;
một thẻ sai hoặc một URL trong `answer` hạ lượt xuống `abstain` và ghi
`traces.assemble_the_loi`.

## Context

- Spec: `docs/superpowers/specs/2026-09-06-soul-trich-dan-bam-duoc-design.md`
- Plan từng bước: `docs/superpowers/plans/2026-09-06-soul-trich-dan-bam-duoc.md`
- Lý luận nền: `docs/soul-va-trich-dan-bam-duoc.md`
- Authority hành vi agent: `docs/bo-luat-agent.md` (dòng 7–9 chờ bẫy đo được)

## Scope

In scope: hợp đồng `k`/`documents`, SOUL vào 5 node, assemble.v2 + phép kiểm
thẻ/URL, rewrite.v2 + cộng điểm lĩnh vực (mặc định tắt), migration 019 + seed
link kiểm bằng Chrome, parser/nút thẻ/khối liên kết FE, bẫy mới, ghi token.

Out of scope: gộp `/chat` vào `/dung-thu`; lưu hội thoại theo tài khoản; mở
kho HN&GĐ; stream chữ; đo lường để bật `linh_vuc_bonus`.

## Approach

Bước 0 khoá hợp đồng trên nhánh hiện tại → Bước 1 ba worktree song song
(`wt-be-soul`, `wt-fe-the`, `wt-db-link`) → Bước 2 gộp, chạy bẫy v1/v2, đổi
mặc định prompt.

## Risks And Recovery

- Mô hình không theo cú pháp thẻ → `assemble_the_loi` tăng; giữ mặc định v1,
  sửa prompt, không nới phép kiểm.
- `documents` bị LangGraph loại → `test_moi_field_TraCuuResponse_deu_duoc_KLawState_khai`.
- vbpl.vn chặn bot → chỉ nạp link người đã mở bằng Chrome; NULL nếu không.
- Rollback: `ASSEMBLE_PROMPT=prompts/assemble.v1.md` (env) hoặc revert commit đổi mặc định.

## Progress

- [ ] Bước 0: Task 1–4
- [ ] Bước 1 BE: Task 5–12
- [ ] Bước 1 FE: Task 13–15
- [ ] Bước 1 DB: Task 16–18
- [ ] Bước 2: Task 19–22

## Decisions

- 2026-09-06: Q1 xưng "tôi" toàn bộ; Q2 bỏ ngày khỏi văn xuôi; Q3 kiểm link
  bằng Chrome + seed; Q4 hợp đồng trước, ba worktree; Q5 thẻ `doc` mở
  `KhungDoiChieu` tại điều khoản đầu của văn bản. Chủ dự án chọn.
- 2026-09-06: A/B prompt bằng env `ASSEMBLE_PROMPT`/`REWRITE_PROMPT` qua
  `eval.run_trap`, không thêm preset — `eval.run` không chạy graph.

## Validation

- Focused proof: pytest `tests/test_agents/test_assemble.py`, `test_rewrite_query.py`,
  `test_soul.py`, `tests/test_services/test_prompts.py`, `test_retrieval.py`,
  `tests/test_scripts/test_nap_link_cong_luat.py`, `tests/test_eval/test_run_trap.py`;
  `npm run kiem-van-xuoi`, `kiem-trich-dan`, `kiem-documents`.
- Integration / end-to-end proof: `pytest -m integration tests/test_api/test_tra_cuu.py`;
  `eval.run_trap` v1 và v2; ảnh `.tham-dinh-shots/04-the-bam.png`.
- Repository-required checks: `make check`, `cd frontend && npm run kiem`.

## Result

Chưa xong.
