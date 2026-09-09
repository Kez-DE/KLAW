# Execution Plan: Bộ nhớ hội thoại, tính cách trả lời, soạn thảo hội thoại và không gian làm việc

Date: 2026-09-09

## Status

Active

## Outcome

Quan sát được qua giao diện thật, sau khi xong (chép nguyên văn mục 1 của spec
`2026-09-09-bo-nho-tinh-cach-soan-thao-design.md`):

1. Trong một phiên, ở lượt thứ 8 người hỏi nói "vậy tôi được bao nhiêu ngày báo trước"
   và KLAW trả lời theo đúng vai và loại hợp đồng đã nói ở lượt 1, không hỏi lại.
2. Tài khoản Pro mở phiên mới, hỏi "trợ cấp thôi việc của tôi tính sao", KLAW dùng dữ
   kiện đã biết từ phiên trước và ghi rõ "Dựa trên: bạn là người lao động · làm 3 năm".
   Người dùng xem, sửa, xoá từng dữ kiện trong Cá nhân hoá. Free không có bộ nhớ xuyên
   phiên và không thấy mục đó.
3. Câu "tôi sắp nghỉ việc, hãy đưa cho tôi luật để đảm bảo quyền lợi cho tôi, văn bản
   nghỉ việc" nhận câu trả lời ngay ở lượt đầu: một dòng giả định, quyền và nghĩa vụ
   có trích dẫn đã kiểm, phần đuôi hỏi đúng dữ kiện còn làm đổi kết quả, và một nút
   "Soạn đơn xin nghỉ việc". Không còn màn abstain kèm danh sách tám văn bản.
4. "So sánh trợ cấp thôi việc và trợ cấp mất việc" trả về một bảng thật, mỗi ô có
   trích dẫn bấm được.
5. "Tôi cần đơn xin nghỉ việc" → KLAW hỏi một lần các dữ kiện còn thiếu; người dùng
   trả lời tự nhiên; bản thảo hiện trên sân khấu toàn bề rộng, chat thu thành cửa sổ
   nổi; "đổi ngày nghỉ thành 15/10" sửa đúng mục 3 và tạo phiên bản 2; tải .docx/.pdf
   tại chỗ.
6. Panel điều khoản kéo dãn trái phải bằng chuột và bàn phím, nhớ độ rộng. Bấm "Sửa"
   một mục của bản thảo mở drawer bên phải xếp chồng; mục lồng mở drawer thứ hai; Esc
   đóng tấm trên cùng.
7. Bảng giá ghi Cá nhân ₫69.000 / 30 ngày; thanh đo Free ghi 100 lượt/ngày và 30
   lượt/phiên; Pro 500 lượt/ngày, không có trần lượt mỗi phiên.
8. Golden 77 câu lao động có số đo trước và sau; hai bộ đo mới (hội thoại nhiều lượt,
   câu mơ hồ) có số ban đầu ghi trong plan.

## Context

- Authority thiết kế: `docs/superpowers/specs/2026-09-09-bo-nho-tinh-cach-soan-thao-design.md`
  (§1 Mục tiêu, §11 Rủi ro chép ở trên/dưới; §5–§9 là năm gói tương ứng năm giai đoạn
  ở Scope). Spec này sửa đè §4 và bảng giá của
  `docs/superpowers/specs/2026-09-07-vo-ung-dung-va-tai-khoan-design.md` (xem mục
  "Sửa 2026-09-09" ở cuối file đó) và mở rộng phiên của
  `docs/superpowers/specs/2026-09-07-lich-su-hoi-thoai-design.md` §5.2 thành bộ nhớ
  ba lớp; nó cũng thêm QT-5 và sửa QT-4 trong `docs/bo-luat-agent.md`.
- Plan thi công chi tiết theo TDD, 26 task chia thành năm giai đoạn:
  `docs/superpowers/plans/2026-09-09-bo-nho-tinh-cach-soan-thao.md` (§10 của spec có
  bảng phụ thuộc giữa các giai đoạn). Đây là plan superpowers dùng để lấy đúng lệnh
  test/file cho từng task; plan active này chỉ theo dõi tiến độ và validation ở mức
  giai đoạn.
- Bàn giao từ `docs/plans/active/tro-ly-8-linh-vuc.md`: quyết định 2026-09-09 trong
  mục Decisions của plan đó chuyển P4 (phần bảng trong câu trả lời pháp luật), P5 (ý
  "xin dạng bảng") và P6 (câu đóng) sang giai đoạn 3 (mục 7) của plan này; plan đó còn
  giữ P0–P3 (mở kho 8 lĩnh vực, đồng bộ phạm vi, tách DANH_TINH) và phần bảng cho câu
  hỏi về kho — không thuộc phạm vi ở đây.
- Task 1 (số hạn mức YAML, gỡ lá chắn Pro) và Task 2 (giá 69.000đ + copy hạn mức FE)
  của giai đoạn 1 đã xong, commit `211e239`, `2482e46`, `5de84b6`. Task 3 (ghi authority
  — chính là commit này) đóng nốt giai đoạn 1.

## Scope

In scope — năm giai đoạn theo spec §5–§9:

- Giai đoạn 1 — Giá và hạn mức (spec §5): số hạn mức mới, gỡ lá chắn Pro riêng, giá
  ₫69.000/30 ngày, copy hạn mức ở frontend, ghi authority (mục này).
- Giai đoạn 2 — Bộ nhớ phiên và bộ nhớ tài khoản (spec §6): migration bộ nhớ, dịch vụ
  gộp hồ sơ/tóm tắt cuộn, nối vào đường tra cứu và các node agent, API bộ nhớ, frontend
  dòng "Dựa trên" và thẻ "KLAW nhớ về bạn", bộ đo hội thoại nhiều lượt.
- Giai đoạn 3 — Tính cách trả lời (spec §7): QT-5, node `suy_dien` suy luận câu mơ hồ,
  router v3, bảng so sánh từ luận điểm đã kiểm, bộ đo câu mơ hồ.
- Giai đoạn 4 — Soạn thảo hội thoại (spec §8): migration bản thảo, node gom dữ kiện
  bằng structured output, hai kiểu kết quả mới nối vào graph, API bản thảo, frontend
  hỏi dữ kiện + bàn giao bản thảo.
- Giai đoạn 5 — Không gian làm việc (spec §9): tay kéo panel điều khoản, tách xem
  trước/xuất khỏi `KhongGianSoanThao`, sân khấu bản thảo + cửa sổ trợ lý nổi, drawer
  xếp chồng để sửa từng mục, bố cục màn hẹp.

Out of scope:

- Mở kho sang 8 lĩnh vực và bảng cho câu hỏi về kho — ở
  `docs/plans/active/tro-ly-8-linh-vuc.md` (P0–P3), không phải plan này.
- Thanh toán thật cho gói ₫69.000; vẫn là yêu cầu nâng gói do admin duyệt.
- Tra lại nội dung phiên cũ theo ngữ nghĩa (embedding lịch sử); nhiều worker uvicorn;
  markdown trong `answer`; thư viện kéo thả hay trình soạn thảo rich-text trong drawer.
  Chi tiết ở spec mục 12.

## Approach

Năm giai đoạn chạy tuần tự 1 → 5, mỗi giai đoạn là một loạt commit tự đứng được
(dựng, kiểm, commit trước khi qua giai đoạn kế) theo TDD trong plan superpowers:

1. Giai đoạn 1 không phụ thuộc gì — đã xong (Task 1–2), Task 3 (commit này) đóng nốt.
2. Giai đoạn 2 phụ thuộc giai đoạn 1 (trần lượt mỗi phiên của Pro đã bỏ, nếu không bộ
   nhớ xuyên phiên vô nghĩa).
3. Giai đoạn 3 phụ thuộc giai đoạn 2 (`ho_so` bộ nhớ là đầu vào cho `suy_dien`).
4. Giai đoạn 4 phụ thuộc giai đoạn 2 và 3 (dữ kiện gom được lấy từ bộ nhớ và từ suy
   luận câu mơ hồ).
5. Giai đoạn 5 phụ thuộc giai đoạn 4 (`ban_thao` phải tồn tại trước khi có sân khấu và
   drawer sửa mục).

Xong một giai đoạn thì tick Progress và ghi số đo thật vào Validation trước khi bắt
đầu giai đoạn kế; không gộp hai giai đoạn vào một loạt commit.

## Risks And Recovery

Chép nguyên văn mục 11 của spec `2026-09-09-bo-nho-tinh-cach-soan-thao-design.md`:

- **Chi phí**: thêm một lời gọi nền rẻ mỗi lượt (ước 15–25% chi phí lượt). Lùi:
  `KLAW_BO_NHO_NEN=0`.
- **Sai giả định**: `suy_dien` gán sai vai. Giảm: dòng giả định luôn hiện và sửa được
  một chạm; eval mơ hồ đo tỷ lệ gán sai; bảng mẫu chỉ bắt ngôi thứ nhất rõ ràng.
- **Bộ nhớ chứa quy tắc luật hoặc dữ liệu định danh**: lưới chặn 0 token trước khi
  ghi, test âm cho từng mẫu; giá trị ≤ 120 ký tự; prompt chỉ lấy dữ kiện bền.
- **Rò bộ nhớ giữa tài khoản hoặc từ Pro sang Free**: mọi truy vấn lọc `user_sub`;
  test API khẳng định Free không có dòng nào; cascade khi xoá tài khoản.
- **Câu chuyện đồ án**: từ "hỏi lại" sang "giả định có kiểm soát" — ghi vào
  `docs/decisions/` với hai bộ eval mới làm bằng chứng, trích Model Spec và Hiến pháp
  Claude làm cơ sở so sánh.
- **Kích cỡ `KhongGianSoanThao`** (1.804 dòng): chỉ tách phần render/xuất, không viết
  lại wizard; route `/soan-thao/$loai` giữ nguyên hành vi.
- **Lùi toàn bộ**: mọi cột mới có mặc định, `TraCuuResponse` chỉ thêm trường mặc định
  rỗng, payload cache cũ vẫn tuần tự hoá; frontend đọc trường mới theo kiểu tuỳ chọn.

## Progress

- [x] Giai đoạn 1 — Giá và hạn mức: Task 1–2 done, Task 3 this commit.
- [x] Giai đoạn 2 — Bộ nhớ phiên và bộ nhớ tài khoản: Task 4–9 done, Task 10 (bộ đo
  hội thoại nhiều lượt + test hồi quy "lượt 8 vẫn nhớ") this commit đóng nốt.
- [x] Giai đoạn 3 — Tính cách trả lời: Task 11–15 done, Task 16 (`assemble.v3`
  trả lời trước + bộ đo câu mơ hồ `eval/run_mo_ho.py`) this commit đóng nốt.
- [ ] Giai đoạn 4 — Soạn thảo hội thoại.
- [ ] Giai đoạn 5 — Không gian làm việc.

## Decisions

Rỗng — ghi dần khi mỗi giai đoạn phát sinh quyết định cục bộ. Chuyển quyết định có
tính lâu dài về sản phẩm/kiến trúc vào `docs/decisions/`.

## Validation

- Giai đoạn 1 (đã chạy ở Task 1–2): `KLAW_SUPABASE_URL= .venv/bin/python -m pytest -q
  tests/test_api/test_han_muc_yaml.py tests/test_api/test_han_muc_ngay.py
  tests/test_api/test_han_muc_dua.py tests/test_api/test_xac_thuc_han_muc.py`;
  `.venv/bin/ruff check` + `.venv/bin/ruff format --check` trên file đã đổi;
  `cd frontend && npm run typecheck && npm run lint && node scripts/kiem-goi.ts &&
  node scripts/kiem-han-muc.ts`.
- Giai đoạn 2: `KLAW_SUPABASE_URL= .venv/bin/python -m pytest -q --deselect
  tests/test_services/test_moi_mau.py`; `.venv/bin/ruff check` + `ruff format --check`
  trên file đã đổi; `cd frontend && npm run typecheck && npm run lint && node
  scripts/kiem-bo-nho.ts`; `.venv/bin/python -m eval.run_hoi_thoai` (tốn tiền thật,
  cần khoá OpenRouter — nếu chưa có khoá thì ghi "chưa chạy", không bịa số).
  Task 10 (`hoi_thoai_nhieu_luot.yaml` + `eval/run_hoi_thoai.py`): **chưa chạy** —
  kỷ luật chi phí của phiên làm việc cấm gọi OpenRouter thật khi thực hiện task
  này; lệnh tái lập: `.venv/bin/python -m eval.run_hoi_thoai`. Test hồi quy
  `test_luot_8_van_biet_vai_va_loai_hop_dong` (dùng `LlmGia`, không gọi mạng) đã
  PASS.
- Giai đoạn 3: cùng bộ pytest/ruff trên file đã đổi. Task 16 (`assemble.v3` +
  `eval/run_mo_ho.py`): `KLAW_SUPABASE_URL= .venv/bin/python -m pytest -q
  tests/test_eval tests/test_agents -m "not integration"` — 423 passed;
  `.venv/bin/ruff check` + `ruff format --check` trên file đã đổi — sạch.
  `.venv/bin/python -m eval.run --config hybrid` (golden 77, số trước giai đoạn
  3), `.venv/bin/python -m eval.run_trap --limit 20`, `.venv/bin/python -m
  eval.run_mo_ho` (bộ 20 câu mơ hồ mới): **chưa chạy** — kỷ luật chi phí của
  phiên làm việc cấm gọi OpenRouter thật khi thực hiện Task 16; ba lệnh trên là
  lệnh tái lập, cần khoá OpenRouter. `eval/datasets/mo_ho.yaml` đã xác minh khớp
  `suy_dien.suy_vai` cho cả 20 câu (chạy trực tiếp qua hàm đó, không đoán bằng
  mắt); scoring (`run_mo_ho.dung`/`tom_tat`, kể cả cách ly lỗi hạ tầng khỏi tỉ lệ
  đúng) đã đo trên input tổng hợp, không qua mạng — xem `test_run_mo_ho.py`.
- Giai đoạn 4: cùng bộ pytest/ruff trên file đã đổi; `cd frontend && npm run
  typecheck && npm run lint && node scripts/kiem-ban-thao.ts`.
- Giai đoạn 5: cùng bộ pytest/ruff trên file đã đổi; `cd frontend && npm run
  typecheck && npm run lint && node scripts/kiem-keo-dan.ts && node
  scripts/kiem-ngan-xep.ts`; ảnh chụp bốn trạng thái vào `.tham-dinh-shots/`
  (không stage).

## Result

Chưa xong.
