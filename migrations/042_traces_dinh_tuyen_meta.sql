-- Quyết định 2026-09-30 `docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md`
-- mục 8 — cờ định tuyến và khía cạnh câu hỏi meta được ghi vào `traces`, để một
-- lượt bị ép sai nhánh (trace 88117154: câu tranh chấp nhà đất bị ép vào giới
-- thiệu) đọc được từ bảng thay vì phải dựng lại từ log.
--
--   route_ep_meta        — `route` ép phán quyết của model về `gioi_thieu`
--                          (`gioi_thieu.chac_chan_meta`).
--   route_ep_luat        — `route` trả một phán quyết meta về `tra_cuu` (câu hỏi
--                          về hệ thống pháp luật, hoặc câu kể tình huống).
--   gioi_thieu_khia_canh — các khía cạnh của câu hỏi meta, theo thứ tự hỏi.
--
-- Cả ba NULLABLE: NULL nghĩa là lượt đó không đi qua `route` / không phải câu
-- hỏi meta (`/soat`, `/soan-thao`, lượt đính kèm tài liệu), không phải "quên ghi".
-- Cộng thêm, idempotent (`ADD COLUMN IF NOT EXISTS`), không viết lại dòng nào.
ALTER TABLE traces ADD COLUMN IF NOT EXISTS route_ep_meta BOOLEAN;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS route_ep_luat BOOLEAN;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS gioi_thieu_khia_canh TEXT[];
