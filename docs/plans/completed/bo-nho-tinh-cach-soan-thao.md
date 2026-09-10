# Execution Plan: Bộ nhớ hội thoại, tính cách trả lời, soạn thảo hội thoại và không gian làm việc

Date: 2026-09-09

## Status

Completed

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
- [x] Giai đoạn 4 — Soạn thảo hội thoại: Task 17–21 done (bản thảo lưu theo
  phiên bản với "lùi" một chiều không mất dữ liệu, gom dữ kiện qua hội thoại
  không hỏi lại hai lần, hai kiểu kết quả agent mới nối vào graph, API bản
  thảo theo từng người dùng, thẻ bản thảo trong khung chat).
- [x] Giai đoạn 5 — Không gian làm việc: Task 22–25 done trước đó (tay kéo
  panel điều khoản có nhớ độ rộng, tách xem trước/xuất khỏi
  `KhongGianSoanThao`, sân khấu bản thảo + cửa sổ trợ lý nổi, drawer xếp
  chồng sửa từng mục); Task 26 (commit này) đóng nốt bằng bố cục màn hẹp: tab
  "Bản thảo | Trợ lý" toàn màn, drawer và danh sách mục gấp lại cho vừa.

## Decisions

Rút từ mọi dòng `Ruling:` tính đến lúc đóng plan trong
`.superpowers/sdd/2026-09-09-bo-nho-tinh-cach-soan-thao/progress.md`, theo thứ
tự xuất hiện — vài ruling ra đời sau khi đóng plan nên không có ở đây. Vài dòng không gắn số task tường minh trong ledger — ghi rõ
thay vì đoán số task.

- Task 22: thêm prop tuỳ chọn `onMacDinh` nối vào bấm đôi, vì Bước 4 của brief
  cần trong khi mã Bước 3 của chính brief lại thiếu.
- Task 4: đưa migration `023_bo_nho.sql` vào đúng danh sách migration mà
  lifespan tự áp dụng lúc khởi động — mã dùng một tuple tiền tố cố định chứ
  không áp dụng mọi migration như plan giả định.
- Task 5: siết thêm một quy tắc để tóm tắt bộ nhớ không mang định danh nhạy
  cảm, theo đúng quy tắc bộ nhớ của spec thay vì chỉ kiểm Điều/số hiệu như mã
  ban đầu.
- Task 5: giữ dòng trace chi phí nhưng loại nó khỏi hai truy vấn thống kê
  hoạt động/phân loại hồ sơ, dù file đó nằm ngoài danh sách file gốc của
  Task 5.
- Task 5: giữ nguyên quy tắc bắt trích dẫn theo hướng rộng — thà bắt nhầm một
  địa chỉ dạng "Đ. 35, Quận 1" còn hơn bỏ sót một trích dẫn thật.
- Task 7: coi các lượt test báo hạn mức cũ (trước Task 1) là lỗi thật cần sửa
  trong vòng sửa của Task 7, không phải lỗi có sẵn không liên quan.
- Task 9: dồn việc xác nhận bằng mắt qua Chrome vào đúng một đợt chụp gộp ở
  cuối kế hoạch (Task 26) thay vì dựng lại backend riêng cho từng task.
- Task 9: sửa luôn nhánh khách chưa đăng nhập bấm sửa hồ sơ (hiện chưa ai
  chạm tới) vì Task 12 sắp khiến suy luận điền hồ sơ cho cả khách ẩn danh,
  làm nhánh đó sống lại.
- Task 10: sửa cả phép so khớp chuỗi con gây nhầm "xác định thời hạn" với
  "không xác định thời hạn" lẫn việc bộ chấm điểm thiếu cách ly lỗi từng câu.
- Task 12: mở rộng cả quy tắc suy vai lẫn bộ test theo cả ba phát hiện của
  reviewer, vì suy sai vai còn tệ hơn im lặng.
- Task 13: giữ bản rewrite mặc định ở phiên bản mới vì tín hiệu lĩnh vực cần
  cho toàn bộ tính năng, và rủi ro đã biết luôn báo lỗi rõ chứ không âm thầm
  trả lời sai; phép đo tốn tiền còn lại để chủ dự án tự quyết định chạy.
- Task 13: vẫn sửa hai dòng chú thích lỗi thời dù nằm ngoài phạm vi file của
  Task 13, vì một bước xử lý mới đã làm chú thích đó không còn đúng.
- Task 14: sửa cả ba phát hiện của reviewer cho nhánh hỏi thêm dữ kiện (bỏ
  qua trần khi lỗi hệ thống, thiếu kiểm kiểu dữ liệu, trần viết cứng thay vì
  dùng hằng số).
- Task 15: sửa cả ba phát hiện của reviewer cho bộ dựng bảng so sánh (cổng
  chặn bảng không so sánh thật, mô tả ô sai dạng có thể làm vỡ luồng, test
  còn thiếu các trường hợp rủi ro).
- Task 16: sửa ngay việc bộ đo câu mơ hồ chỉ đo được nửa sau của câu trả lời
  (đoán vai) mà bỏ sót nửa đầu (không hỏi lại), thay vì hoãn sang việc khác.
- Task 17: coi việc lùi phiên bản làm mất nội dung phiên bản vừa rời là lỗi
  mất dữ liệu thật, phải mở rộng hình dạng lịch sử để giữ đủ tài liệu và điều
  khoản của cả hai phiên bản.
- Task 17: bắt hai hàm truy cập bộ nhớ mới phải lọc theo người dùng ngay từ
  đầu, theo đúng quy ước an toàn hơn cùng file đã có từ Task 4.
- Task 17: định nghĩa lại "Lùi" là một bước đi lùi thật — bỏ hẳn phiên bản
  vừa rời, không giữ đường quay lại — thay vì một công tắc bật/tắt qua lại
  giữa hai phiên bản.
- Task 18: xác nhận việc suy luận vai chạy trước bước phân loại đường đi là
  chủ đích và đúng theo review của Task 12, nên cập nhật lại hai test còn
  khẳng định lộ trình cũ.
- Task 18: theo đúng khối mã năm cụm từ kích hoạt soạn thảo trong brief thay
  vì gạch đầu dòng mô tả bốn cụm từ của chính brief — coi mã là đặc tả thật.
- Task 19: bỏ quy tắc "đang có bản thảo mở thì mọi lượt sau đều vào nhánh
  soạn thảo", chỉ định tuyến theo đúng ý định của LƯỢT HIỆN TẠI, để một câu
  hỏi pháp luật thật giữa chừng không bị hiểu nhầm thành xin nốt dữ kiện.
- Task 22: bắt cả ba thao tác đổi bề rộng panel (kéo, thu gọn, bấm đôi về
  mặc định) đều lưu qua đúng một chỗ, không chỉ lưu mỗi thao tác kéo.
- Task 23: giữ nguyên quyết định KHÔNG bắt `KhongGianSoanThao` dùng lại
  `XemTruocA4`, vì yêu cầu đó của brief tự mâu thuẫn với chính yêu cầu giữ
  nguyên hành vi wizard, và sẽ phá chữ đậm khi xuất .docx.
- Task 24: tô phần đã đổi ở phía frontend chứ không phải backend; vì không
  có ánh xạ thật từ dữ kiện sang mục, đổi sang nêu tên các DỮ KIỆN đã đổi
  thay vì cố tô nhầm mục.
- Task 25: bắt endpoint sửa mục từ chối giá trị nằm ngoài danh sách lựa chọn
  hợp lệ của trường đó, dùng chung một chỗ kiểm với đường chat.
- Task 25: các tấm drawer không nằm trên cùng phải mang `inert`/`aria-hidden`,
  không theo đúng component tham chiếu của brief vốn thiếu thuộc tính đó.
- Phát hiện toàn nhánh, không gắn một task cụ thể (giao cho Task 26 xử lý
  trước phần việc chính, xem addendum): sửa `kiem-lich-su.ts` để nạp nhiều
  lượt hơn trần lịch sử và suy ra phần lượt còn lại từ đúng hằng số đó, thay
  vì giữ nguyên kỳ vọng viết cứng từ khi trần còn thấp hơn.
- Phát hiện toàn nhánh, không gắn một task cụ thể: hai lượt test dữ liệu kho
  (số hiệu văn bản trùng, ngày hiệu lực mâu thuẫn) đỏ vì dữ liệu corpus thật
  của chủ dự án, không phải do các thay đổi của kế hoạch này — nêu lại cho
  chủ dự án xử lý, không sửa trong kế hoạch này.
- Quyết định phạm vi rà soát toàn nhánh cuối kế hoạch, không gắn một task cụ
  thể: chỉ so từ điểm bắt đầu kế hoạch này tới HEAD, không so từ điểm tách
  nhánh chung — nhánh làm việc đã có hàng trăm commit từ trước không thuộc kế
  hoạch này.

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
- Giai đoạn 5 (Task 26, `cd frontend`): `node scripts/kiem-lich-su.ts` — OK
  sau khi sửa lại phép kiểm (hằng số trần lịch sử đã lên 10 từ Task 9, phép
  kiểm cũ nạp 5 lượt nên không còn thử cắt được gì; sửa: nạp nhiều hơn trần
  và suy ra phần lượt còn lại từ đúng hằng số). `npm run typecheck` — sạch.
  `npm run lint` — 0 lỗi (6 cảnh báo react-refresh có sẵn từ trước, không ở
  file task này đổi). `node scripts/kiem-keo-dan.ts` — 18/18 OK + cửa sổ 7/7
  OK. `node scripts/kiem-ngan-xep.ts` — 6/6 OK. `node scripts/kiem-bo-nho.ts`
  — 5/5 OK. `node scripts/kiem-ban-thao.ts` — 9/9 đạt. `node
  scripts/kiem-goi.ts` — 8/8 OK. Toàn chuỗi `npm run kiem` (typecheck, lint,
  mọi `kiem-*`, kiểm tương phản, `npm run build`) — thoát mã 0, kể cả
  `kiem-khung.ts` giờ đối chiếu THẬT với backend đang chạy ở cổng 8000 (do
  controller khởi động cho đợt chụp sau task này): "kiem-khung: đạt · 25 phép
  kiểm khung + 29/29 mẫu khớp cờ máy chủ" — không lệch. `pytest`/`ruff` cho
  backend: **không tự chạy trong Task 26** — task này không đổi file Python
  nào; Task 22–25 (phần backend của giai đoạn 5) đã tự chạy pytest/ruff
  trong phiên làm việc riêng của từng task đó (xem
  `.superpowers/sdd/2026-09-09-bo-nho-tinh-cach-soan-thao/progress.md`), tôi
  không chép lại số liệu ở đây vì không tự mắt thấy trong phiên này. Ảnh chụp
  Chrome bốn trạng thái ở 1440/390 và đi bàn phím qua drawer (Tab, Shift+Tab,
  Esc): **không chạy trong task này** — đây là phần của controller sau khi
  backend và frontend cùng chạy với một phiên đăng nhập thật (đã tách rõ
  trong brief của Task 26).

## Result

Cả năm giai đoạn (26 task) đã landed và validate theo mục Validation ở trên.
Còn lại hai việc ngoài phạm vi việc code, cả hai đã nêu rõ chứ không bịa số:
hai phép đo tốn tiền thật (`eval.run_hoi_thoai`, `eval.run_mo_ho`/`run_trap`
đủ mẫu) chưa chạy vì cần khoá OpenRouter — để chủ dự án tự quyết; và đợt
chụp Chrome bốn trạng thái + đi bàn phím qua drawer do controller làm sau
task này (cần backend, frontend và một phiên đăng nhập thật).
