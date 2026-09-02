-- `linh_vuc` — lĩnh vực pháp luật, đọc VERBATIM từ `data/raw/metadata.parquet`
-- (cột `linh_vuc`; rỗng thì lấy `nganh`). Mở kho từ lao động sang 8 lĩnh vực
-- (Task 1, `.superpowers/sdd/tro-ly-8-linh-vuc/`) — cột này là thứ Task sau
-- dùng để giới hạn phạm vi truy hồi theo lĩnh vực.
--
-- KHÔNG tự đặt taxonomy: `metadata.parquet` đến từ dataset HuggingFace bên thứ
-- ba (cảnh báo nguồn ở `scripts/load_incoming_edges.py`), và giá trị của nó là
-- chữ NGUYÊN VĂN nguồn công bố, không chuẩn hoá — trừ MỘT ngoại lệ: nhãn mặc
-- định "Chưa phân loại" (nguồn tự gắn cho văn bản chưa gắn lĩnh vực nào) bị coi
-- như rỗng, không phải một lĩnh vực thật (xem `scripts/nap_linh_vuc.py`).
--
-- Cùng lý do NULL với `nguoi_ky` (migration 015): một số văn bản không có CẢ
-- `linh_vuc` LẪN `nganh` trong metadata.parquet (đo được, xem
-- `scripts/nap_linh_vuc.py`), và văn bản nguồn `vanban.chinhphu.vn` (tiền tố
-- `cp-`) cố ý KHÔNG tra `metadata.parquet` bằng id trần — id đó có thể trùng
-- một văn bản HOÀN TOÀN KHÁC trong dải id số của MOJ (đo được: `162374` trong
-- `metadata.parquet` là một Nghị quyết HĐND, không phải Luật Khiếu nại đứng sau
-- `cp-162374`) — tra nhầm sẽ gán linh_vực SAI cho đúng văn bản, còn NULL chỉ là
-- KHÔNG BIẾT.
--
-- Cùng lý do UPDATE-không-qua-ingest với 015: thêm cột metadata không làm
-- `checksum` đổi nên `ingest` bỏ qua mọi document đã có; `scripts/nap_linh_vuc.py`
-- đọc lại `metadata.parquet` trên đĩa rồi UPDATE thẳng, tránh `DELETE FROM
-- documents` CASCADE xoá `provisions` (đổi toàn bộ id).

ALTER TABLE documents ADD COLUMN IF NOT EXISTS linh_vuc TEXT;

-- Chuỗi rỗng KHÔNG được phép — cùng lý do với `documents_nguoi_ky_khong_rong_check`
-- (015): "" và NULL đọc giống nhau trên giao diện nhưng khác nhau ở `IS NULL`.
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_linh_vuc_khong_rong_check;
ALTER TABLE documents ADD CONSTRAINT documents_linh_vuc_khong_rong_check
    CHECK (linh_vuc IS NULL OR btrim(linh_vuc) <> '');
