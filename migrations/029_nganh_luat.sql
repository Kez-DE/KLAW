-- Spec 2026-09-15d — 12 ngành luật.
--
-- Cột MỚI chứ không sửa `linh_vuc`: `linh_vuc` là giá trị NGUYÊN VĂN từ nguồn
-- (56 giá trị tự do, 88/1634 dòng có dữ liệu). Nó vẫn là tín hiệu đầu vào cho
-- phép xếp ngành, nên ghi đè lên nó là tự xoá nguồn của chính mình — và mất
-- luôn khả năng chạy lại phép xếp sau khi sửa bộ từ khoá.
--
-- CHECK liệt kê đúng 12 ngành: một slug gõ sai phải nổ lúc ghi, không phải im
-- lặng tạo ra một "ngành" thứ 13 mà bộ lọc không bao giờ khớp.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS nganh_luat TEXT;

ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_nganh_luat;
ALTER TABLE documents ADD CONSTRAINT ck_documents_nganh_luat
    CHECK (nganh_luat IS NULL OR nganh_luat IN (
        'hien_phap', 'hanh_chinh', 'hinh_su', 'to_tung_hinh_su',
        'dan_su', 'to_tung_dan_su', 'dat_dai', 'tai_chinh',
        'ngan_hang', 'hon_nhan_gia_dinh', 'lao_dong', 'kinh_te'
    ));

CREATE INDEX IF NOT EXISTS ix_documents_nganh_luat ON documents(nganh_luat) WHERE nganh_luat IS NOT NULL;
