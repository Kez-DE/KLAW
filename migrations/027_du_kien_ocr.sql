-- Spec 2026-09-15b — dữ kiện neo vào chữ do OCR đọc ra.
--
-- `tai_lieu_ocr` là một NGUỒN RIÊNG, không phải một cờ phụ của `tai_lieu`.
-- Neo vào lớp chữ thật chứng minh "tài liệu viết đúng câu này"; neo vào chữ OCR
-- chỉ chứng minh "máy đọc ảnh ra câu này". Hai hạng bằng chứng khác nhau, và
-- gộp chúng lại là để giao diện hứa nhiều hơn thứ nó giữ được — cùng lý do dự
-- án giữ riêng `answer` với `partial_coverage`.
--
-- `do_tin` chỉ có nghĩa với `tai_lieu_ocr`: ở lớp chữ thật không có gì để đoán.
-- Ràng buộc bên dưới cưỡng chế đúng điều đó, thay vì tin vào kỷ luật người gọi.

ALTER TABLE du_kien_tai_lieu ADD COLUMN IF NOT EXISTS do_tin DOUBLE PRECISION;

ALTER TABLE du_kien_tai_lieu DROP CONSTRAINT IF EXISTS ck_du_kien_nguon;
ALTER TABLE du_kien_tai_lieu ADD CONSTRAINT ck_du_kien_nguon
    CHECK (nguon IN ('tai_lieu', 'tai_lieu_ocr', 'nguoi_dung_nhap', 'nguoi_dung_sua'));

-- Yêu cầu neo áp cho CẢ HAI nguồn đến từ tài liệu: OCR yếu hơn nhưng không được
-- miễn nghĩa vụ chỉ ra chỗ nó đọc được.
ALTER TABLE du_kien_tai_lieu DROP CONSTRAINT IF EXISTS ck_du_kien_tai_lieu_co_neo;
ALTER TABLE du_kien_tai_lieu ADD CONSTRAINT ck_du_kien_tai_lieu_co_neo
    CHECK (
        nguon NOT IN ('tai_lieu', 'tai_lieu_ocr')
        OR (trich IS NOT NULL AND length(btrim(trich)) > 0
            AND chi_so_don_vi IS NOT NULL AND trang IS NOT NULL)
    );

-- `do_tin` bắt buộc với OCR, và cấm với lớp chữ thật: một độ tin cậy gắn vào
-- chữ đọc thẳng là một con số vô nghĩa mà giao diện sẽ hiển thị như thật.
ALTER TABLE du_kien_tai_lieu DROP CONSTRAINT IF EXISTS ck_du_kien_do_tin;
ALTER TABLE du_kien_tai_lieu ADD CONSTRAINT ck_du_kien_do_tin
    CHECK (
        (nguon = 'tai_lieu_ocr' AND do_tin IS NOT NULL AND do_tin BETWEEN 0 AND 1)
        OR (nguon <> 'tai_lieu_ocr' AND do_tin IS NULL)
    );
