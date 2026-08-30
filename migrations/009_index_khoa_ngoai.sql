-- HIGH (silent-failure review round 2, đo bằng EXPLAIN ANALYZE — xem
-- task-10-report.md): ba cột FK không có index:
--   provisions.parent_id, "references".from_provision_id, "references".to_provision_id
--
-- Dùng tại expand.py (_SQL_PARENT/_SQL_CHILDREN/_SQL_HOP) và
-- verify_tier1.py (_SQL_CAY, CTE đệ quy của nap_provisions()). Đo được:
-- CTE đệ quy quét lại TOÀN BỘ `provisions` (Seq Scan, 19.135 dòng) ở MỖI vòng
-- lặp đệ quy (3 vòng cho 10 id đầu vào) vì `p.parent_id = c.id` không có
-- index để dùng — 10,034ms cho chỉ 10 id. Đường nóng chạy MỌI request; dưới
-- 15ms nên chưa hỏng hôm nay, nhưng sẽ lộ rõ khi corpus lớn gấp 10 (hướng
-- phát triển hiển nhiên của đề tài).
--
-- `CREATE INDEX IF NOT EXISTS` tự idempotent (không như CHECK/FK) — không cần
-- vũ điệu DROP-rồi-ADD của `005`/`007`. `009` sở hữu ba index này và chỉ nó,
-- không đụng `001`.

CREATE INDEX IF NOT EXISTS ix_provisions_parent_id ON provisions(parent_id);
CREATE INDEX IF NOT EXISTS ix_references_from_provision_id ON "references"(from_provision_id);
CREATE INDEX IF NOT EXISTS ix_references_to_provision_id ON "references"(to_provision_id);
