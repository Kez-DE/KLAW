-- Task 10 (Plan 3): bốn cột mới cho `traces`, để khoá luận CHỨNG MINH được
-- generate/judge khác họ và đo được đóng góp của bước `expand` bằng số liệu
-- thật, không phải tuyên bố suông.
--
--   generate_model / judge_model — tên model THẬT dùng ở tầng 2 cho request
--     này (ghi từ state["traces"]["tier2_generate_model"/"tier2_judge_model"],
--     do Task 6 đặt). NULL khi tầng 2 không chạy cho request đó (route ra
--     ngoai_pham_vi, insufficient_evidence, hoặc VERIFY_TIER2_ENABLED=false) —
--     NULL nghĩa là "không chạy", không phải "quên ghi".
--   expand_before / expand_after — kích thước tập provision NGAY TRƯỚC và
--     NGAY SAU node `expand` (after = |deep|, tập thật sự đưa cho
--     generate_claims — `shallow` không tính vì nó không chảy xuống hạ nguồn).
--     NULL khi node `expand` không chạy (nhánh ngoai_pham_vi rẽ thẳng từ route
--     sang assemble).
--
-- Bốn cột đều NULLABLE, không NOT NULL/DEFAULT: một request có thể hợp lệ mà
-- không đi qua tầng 2 hay expand (xem trên), ép NOT NULL sẽ buộc phải bịa một
-- giá trị mặc định cho "không áp dụng" — chính điều Global Constraint "không
-- bịa số" cấm.
--
-- `ADD COLUMN IF NOT EXISTS` tự idempotent trong Postgres (không như
-- CHECK/FK) — không cần vũ điệu DROP-rồi-ADD của `005`/`007`. Test vẫn chèn
-- một dòng thật vào `traces` rồi chạy migration hai lần
-- (`test_migration_idempotent_KHI_DA_CO_DONG_traces`), theo đúng quy tắc Plan 1
-- "bảng rỗng không bắt được lỗi" — dù ở đây rủi ro thấp hơn hẳn constraint vì
-- thêm cột NULLABLE không kiểm tra dữ liệu đã có.

ALTER TABLE traces ADD COLUMN IF NOT EXISTS generate_model TEXT;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS judge_model    TEXT;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS expand_before  INTEGER;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS expand_after   INTEGER;
