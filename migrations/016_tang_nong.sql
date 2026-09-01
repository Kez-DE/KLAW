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
