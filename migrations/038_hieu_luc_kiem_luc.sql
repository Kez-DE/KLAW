-- Quyết định 2026-09-28 `docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`
-- mục 6 và 8 — THỜI ĐIỂM tình trạng hiệu lực của dòng này được đọc từ gateway Bộ
-- Tư pháp (`scripts/lam_moi_hieu_luc.py`). NULL = chưa từng đọc từ gateway: tình
-- trạng đang lưu (nếu có) đến từ lần nạp đầu hoặc parquet, không phải một lần kiểm.
--
-- Cộng thêm, không đổi dòng nào: chỉ script làm mới ghi vào đây.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS hieu_luc_kiem_luc TIMESTAMPTZ;
