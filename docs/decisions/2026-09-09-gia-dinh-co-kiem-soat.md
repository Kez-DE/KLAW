# Từ "hỏi lại" sang "giả định có kiểm soát"

Ngày: 2026-09-09

## Status

Accepted

## Bối cảnh

Trước bản này, một câu hỏi thiếu dữ kiện quyết định kết quả bị KLAW hỏi lại
TRƯỚC khi trả lời. Với câu hỏi lao động thật, dữ kiện thiếu gần như luôn là vai
người hỏi — thứ mà chính câu hỏi đã nói ra ("tôi bị công ty trừ lương" chỉ có
một cách đọc). Kết quả là người dùng phải trả lời một câu hỏi mà hệ thống đã
biết đáp án, và một lượt hỏi đáp thành hai.

## Quyết định

Thiếu dữ kiện thì **trả lời theo nhánh phổ biến nhất, nêu giả định thành một
dòng, rồi hỏi đúng dữ kiện đó ở cuối** cho lượt sau. Hỏi lại trước khi trả lời
chỉ còn cho trường hợp hai cách hiểu dẫn tới hai câu trả lời trái nhau.

Ràng buộc riêng của KLAW đi kèm: giả định phải hiện thành chữ trên giao diện và
sửa được một chạm (`ho_so_da_dung`, nguồn `suy_dien`); giả định không bao giờ là
căn cứ pháp luật.

## Căn cứ

Hai tài liệu chuẩn mực của ngành, đã dẫn ở `docs/bo-luat-agent.md` (QT-5):

- OpenAI Model Spec 2026-08-18 — "provide a robust answer or a safe guess if it
  can, stating assumptions and asking clarifying questions as appropriate";
  "avoiding unnecessary or trivial clarifying questions".
- Hiến pháp của Claude — "identify the most plausible interpretation"; "ask for
  clarification in cases of genuine ambiguity".

## Bằng chứng

- `eval/datasets/mo_ho.yaml` — 20 câu mơ hồ, chấm "không abstain oan + đúng vai
  trong hồ sơ + answer nêu đúng dòng giả định" (`eval/run_mo_ho.py`).
- `eval/datasets/hoi_thoai_nhieu_luot.yaml` — 10 hội thoại nhiều lượt, chấm
  `ty_le_giu_du_kien` (`eval/run_hoi_thoai.py`).

## Số đo

Chưa chạy — chờ chủ dự án khoá chi phí OpenRouter.

## Hệ quả

Tích cực: một lượt hỏi đáp trả lời được ngay; giả định hiện ra và sửa được nên
người dùng kiểm soát được cách hệ thống hiểu mình.

Đánh đổi: một giả định sai đi kèm một câu trả lời đúng-cho-vai-khác. Chặn bằng
ba thứ: giả định luôn hiện thành chữ, luôn sửa được, và không bao giờ được dùng
làm căn cứ (`prompts/assemble.v3.md`, `prompts/generate_claims.v2.md` đều gắn
nhãn "KHÔNG phải căn cứ" cho khối tình huống).

## Việc còn lại

- Chạy `eval.run_mo_ho` và `eval.run_hoi_thoai` rồi điền mục "Số đo".
