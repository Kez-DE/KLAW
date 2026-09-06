-- Spec 2026-09-06 §4 — link trang CÔNG KHAI của ba cổng luật. `nguon_url` là
-- endpoint API MOJ, không phải trang người đọc mở được, nên cần ba cột riêng.
-- NULL = chưa có link đã kiểm; giao diện không render dòng NULL. Chỉ
-- `scripts/nap_link_cong_luat.py` ghi vào đây, từ `data/seed/link_cong_luat.yaml`.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_vbpl     TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_chinhphu TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_tvpl     TEXT;
