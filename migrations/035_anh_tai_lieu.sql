-- Quyết định 2026-09-18 `docs/decisions/2026-09-18-trung-thuc-bieu-mau-va-media.md`
-- — lưu MEDIA ĐÃ TÁCH khỏi tệp khách tải lên (logo letterhead, con dấu, chữ ký
-- quét). Quyết định ấy sửa HẸP quyết định 2026-09-16: media đã tách là ngoại lệ
-- được gọi tên; hai lệnh cấm còn lại giữ nguyên chữ — KHÔNG lưu bytes tệp gốc,
-- KHÔNG lưu OOXML. Bảng này chỉ chở bytes của từng ẢNH, không một mảnh XML nào.
--
-- Vì sao MỘT BẢNG RIÊNG chứ không thêm một cột cạnh `don_vi` (031): `don_vi` là
-- cột JSONB được đọc lại mỗi lần có người neo một trích dẫn, và
-- `tai_lieu.tai_lieu_cua_hoi_thoai` còn tra `don_vi @> …` trên nó. Nhét vài trăm
-- KB bytes ảnh vào đó là bắt mọi lượt đọc biểu diễn kéo theo con dấu của bên thứ
-- ba qua dây — ngược hẳn ghi chú `_COT_VIEC` ("mỗi lần kéo nó ra là một lần nội
-- dung của bên thứ ba đi qua dây mà không ai cần").
--
-- Vì sao chỉ MỘT khoá ngoại tới `viec_doc_tai_lieu`, không thêm `hoi_thoai_id`
-- như `du_kien_tai_lieu` (026): cả hai đường xoá đã đi qua đúng dòng việc đọc.
-- Xoá CỨNG một cuộc hội thoại cascade `hoi_thoai` → `viec_doc_tai_lieu` (026) →
-- bảng này. Xoá MỀM đi qua `tai_lieu.xoa_theo_hoi_thoai`, vốn DELETE chính dòng
-- việc đọc chứ không rỗng hoá cột — nên cascade ở đây bắt luôn. Thêm một cột
-- `hoi_thoai_id` thứ hai chỉ đẻ ra một đường hai nguồn sự thật có thể lệch nhau.
-- Không có `user_sub`: chủ sở hữu đọc từ `viec_doc_tai_lieu.user_sub` qua JOIN,
-- đúng cách `du_kien_cua_hoi_thoai`/`sua_du_kien` đã làm — một nguồn sự thật cho
-- quyền sở hữu, không phải hai cột phải nhớ giữ đồng bộ.
--
-- `kieu` là MIME nhận ra từ BYTES ĐẦU (`doc_tai_lieu._kieu_anh`), không phải từ
-- đuôi tệp trong tài liệu của người lạ, và ràng buộc dưới đây khoá nó lại ở bốn
-- kiểu ba nơi vẽ cùng dựng được. SVG cố ý KHÔNG có mặt: nó là XML chạy được
-- script, và phát lại nó từ một tệp người lạ tải lên là một đường XSS.
--
-- `so_byte` là một cột riêng chứ không `length(du_lieu)`: mọi truy vấn kiểm tra
-- hạn mức hay thống kê đọc được kích thước mà KHÔNG phải kéo bytes ra khỏi
-- Postgres — cùng lý lẽ `_COT_VIEC` không bao giờ đi cùng `don_vi`.
--
-- UNIQUE (viec_id, phan): một logo dùng ở hai chỗ trong cùng tài liệu là MỘT
-- ảnh (`word/media/image1.png` xuất hiện hai lần trong biểu diễn, một dòng
-- bytes). Chỉ mục ấy cũng phục vụ luôn phép tra theo `viec_id`, nên không cần
-- chỉ mục thứ hai.
--
-- Idempotent như mọi migration ở đây (`src/main.py::MIGRATIONS_KHOI_DONG` chạy
-- LẠI toàn bộ danh sách ở MỖI lần khởi động): `CREATE TABLE IF NOT EXISTS` cho
-- bảng, và ràng buộc `CHECK` khai INLINE trong chính lệnh đó nên không có
-- `ALTER TABLE ADD CONSTRAINT` nào chạy lần thứ hai.
CREATE TABLE IF NOT EXISTS anh_tai_lieu (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    viec_id     UUID NOT NULL REFERENCES viec_doc_tai_lieu(id) ON DELETE CASCADE,
    phan        TEXT NOT NULL,
    kieu        TEXT NOT NULL,
    so_byte     INTEGER NOT NULL,
    du_lieu     BYTEA NOT NULL,
    tao_luc     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_anh_tai_lieu_kieu
        CHECK (kieu IN ('image/png', 'image/jpeg', 'image/gif', 'image/bmp')),
    -- Trần MỖI ảnh ở tầng DB, không chỉ ở Python (`doc_tai_lieu.TRAN_ANH_BYTE`):
    -- cùng hạng với `ck_du_kien_tai_lieu_co_neo` của 026 — một script nạp tay
    -- hay một endpoint tương lai không mở lại được cửa này.
    CONSTRAINT ck_anh_tai_lieu_kich_thuoc
        CHECK (so_byte > 0 AND so_byte <= 2 * 1024 * 1024 AND octet_length(du_lieu) = so_byte),
    UNIQUE (viec_id, phan)
);
