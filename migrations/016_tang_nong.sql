-- Tầng nông: văn bản BIẾT là có, nhưng không có toàn văn máy đọc được.
--
-- `partial_coverage` là nhánh trả lời "văn bản X chi phối câu hỏi của bạn,
-- nhưng tôi chỉ có metadata nên không diễn giải". Nó được thiết kế và được
-- dựng, và tới 2026-09-01 CHƯA BAO GIỜ kích được: điều kiện là
-- `not deep and shallow`, mà DB có deep=47, metadata=79, shallow=0.
--
-- Lý do thật không phải thiếu nhãn — mà là 79 văn bản metadata có 0 điều
-- khoản, nên truy hồi không có gì để chạm tới. Migration này cho mỗi văn bản
-- một hàng `mo_dau` mang TÊN nó, thứ duy nhất đánh chỉ mục được khi không có
-- toàn văn.
--
-- 74/79, không phải 79: năm văn bản có `ten` ngắn hơn 25 ký tự (chỉ số hiệu,
-- không mô tả) — một chunk như vậy không mang tín hiệu liên quan nào, chỉ
-- thêm nhiễu.
--
-- Lời hứa "nêu văn bản, KHÔNG diễn giải" do SCHEMA giữ, không cần code:
-- `ux_provisions_neo_trich_dan` và `provisions_noi_dung_citable_check` chỉ phủ
-- `dieu`/`khoan`/`diem`, nên một hàng `mo_dau` không bao giờ trở thành trích
-- dẫn nguyên văn được.
--
-- Idempotent: `WHERE NOT EXISTS` cho chèn, và `depth` chỉ đổi cho đúng những
-- văn bản vừa có hàng.

INSERT INTO provisions (document_id, parent_id, cap, so_hieu_cap, tieu_de, noi_dung, duong_dan, thu_tu)
SELECT d.id, NULL, 'mo_dau', '', '', d.ten, d.so_ky_hieu || ' > Mở đầu', 0
FROM documents d
WHERE d.depth = 'metadata'
  AND length(d.ten) >= 25
  AND NOT EXISTS (SELECT 1 FROM provisions p WHERE p.document_id = d.id);

UPDATE documents d SET depth = 'shallow'
WHERE d.depth = 'metadata'
  AND EXISTS (SELECT 1 FROM provisions p WHERE p.document_id = d.id AND p.cap = 'mo_dau');

-- Sửa 2026-09-02: INSERT ở trên xếp hàng trigger DEFERRED của `013`
-- (`provisions_hua_danh_sach`, AFTER INSERT ON provisions) cho MỖI dòng
-- `mo_dau` vừa chèn. `run_migrations()` bọc MỌI file trong MỘT transaction,
-- nên khi có dòng mới để chèn (idempotent — không phải mọi lần chạy), sự
-- kiện đó còn "pending" lúc `017` (và các migration sau) chạy `ALTER TABLE
-- provisions` — Postgres từ chối thẳng: "cannot ALTER TABLE provisions
-- because it has pending trigger events". Bắt gặp thật: sau khi
-- `scripts/load_incoming_edges.py` nạp một mẻ cạnh mới (corpus lấy trực
-- tiếp từ DB thay vì hằng số `DOC_IDS`, xem sửa cùng ngày ở file đó), 016 có
-- 98 văn bản `metadata` mới để nâng cấp, và `run_migrations()` vỡ ngay ở
-- `017`, trước khi chạm một chunk nào — icon cảnh báo trong `017` từng đo
-- đúng TRIỆU CHỨNG này nhưng ở nhánh CheckViolation; đây là một đường vỡ
-- KHÁC, cùng cơ chế "016 rồi ALTER trong cùng transaction".
--
-- Trigger AN TOÀN để ép chạy sớm: nó no-op ngay dòng đầu cho mọi `cap`
-- khác `dieu`/`khoan`/`diem` (xem `013`), mà `mo_dau` không thuộc tập đó —
-- ép nó chạy lúc này không đổi kết quả, chỉ đổi THỜI ĐIỂM (COMMIT → ngay
-- đây), giải phóng `provisions` cho các `ALTER TABLE` phía sau trong CÙNG
-- transaction.
SET CONSTRAINTS provisions_hua_danh_sach IMMEDIATE;
