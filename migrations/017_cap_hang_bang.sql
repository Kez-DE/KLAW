-- Cấp `hang_bang`: MỘT HÀNG DỮ LIỆU của bảng, và nó TRÍCH DẪN ĐƯỢC.
--
-- Vì sao cần: bảng lương tối thiểu vùng nằm gọn trong `noi_dung` của MỘT Khoản,
-- nên bốn vùng là MỘT neo. Đã đo (trace cbd9f317, dựng lại 2026-09-02 ở
-- 13f3a5ec): mô hình trích hai trong bốn hàng, kết luận "pháp luật quy định HAI
-- mức lương tối thiểu tháng", và bảy phép kiểm đều xanh vì mọi quote đều nguyên
-- văn. Phép so tập con không có gì để so — hai citation trỏ CÙNG một
-- `khop_tai_id`, không phải hai anh em. Người ở Vùng I (5.310.000 đ) đọc được
-- câu trả lời nói mức tối thiểu là 4.140.000.
--
-- Vì sao KHÔNG mượn cấp `diem`: tới `90/2019/NĐ-CP` nhà làm luật tự đánh nhãn
-- `a) b) c) d)` cho bốn vùng (`157/2018`, `141/2017` cũng vậy); từ `74/2024` họ
-- chuyển sang dàn trang bảng và BỎ nhãn, nội dung vẫn là bốn vùng đó. Gán lại
-- `a)…d)` cho bản mới là bịa ký hiệu — ai đối chiếu Công báo sẽ không tìm thấy
-- "điểm a" nào trong Nghị định 293/2025. `so_hieu_cap` ở đây đọc từ CỘT 1 của
-- chính bảng (`Vùng I`), ghép thêm tiêu đề cột khi ô không tự mô tả
-- (`Bậc thuế 1`) — cả hai vế đều là chữ nguồn tự in ra.
--
-- Ba câu lệnh dưới đây là ba constraint của `004`, chép về đây NGUYÊN VẸN trừ
-- việc thêm `hang_bang`. Đúng quy tắc `002:17`: MỘT constraint thì MỘT file sở
-- hữu, và đó là file MỚI NHẤT. Để `004` giữ bản cũ hẹp hơn là để lại đúng cái
-- bẫy mà `003` và `002` đã dọn: một lần DROP tay rồi chạy lại `004` sẽ ném
-- `check_violation` trên các dòng `hang_bang` và rollback cả lượt migrate.
--
-- `provisions_so_hieu_cap_check` (005) KHÔNG cần sửa: nó viết ở dạng đồng nhất
-- "chỉ `mo_dau`/`phu_luc` được rỗng", nên nó đã đòi `hang_bang` có số hiệu —
-- đúng điều ta muốn. Đó là lợi tức của việc `005` không liệt kê tên cấp.
--
-- Migration này KHÔNG chèn/sửa dòng nào: `hang_bang` do parser sinh, và ingest
-- nạp lại ba văn bản có bảng sạch (`293/2025`, `74/2024`, `109/2025`).
-- DROP-rồi-ADD nên chạy lại được nhiều lần trên bảng CÓ dữ liệu.

ALTER TABLE provisions DROP CONSTRAINT IF EXISTS provisions_cap_check;

DO $$ BEGIN
    ALTER TABLE provisions ADD CONSTRAINT provisions_cap_check
        CHECK (cap IN ('phan', 'chuong', 'muc', 'tieu_muc', 'dieu', 'khoan',
                       'diem', 'hang_bang', 'phu_luc', 'mo_dau'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Neo trích dẫn duy nhất. `hang_bang` VÀO index này: hai hàng cùng nhãn trong
-- một Khoản nghĩa là một claim về hàng nọ được "kiểm chứng thành công" trên
-- hàng kia — với bảng lương thì đó là trả nhầm mức tiền. `_tach_bang` đã từ
-- chối tách khi nhãn trùng, index này làm điều đó BẤT KHẢ THI VỀ MẶT VẬT LÝ.
DROP INDEX IF EXISTS ux_provisions_neo_trich_dan;

CREATE UNIQUE INDEX IF NOT EXISTS ux_provisions_neo_trich_dan
    ON provisions (duong_dan)
    WHERE cap IN ('dieu', 'khoan', 'diem', 'hang_bang');

-- `noi_dung` rỗng ở cấp trích dẫn được = phép kiểm "câu trích khớp nguyên văn"
-- không có gì để đối chiếu. Với `hang_bang`, `noi_dung` LÀ hàng markdown
-- (`| Vùng III | 4.140.000 | 20.000 |`) — đúng chuỗi mô hình trích ra và đúng
-- chuỗi `verify_tier1` đối chiếu vào, nên rỗng ở đây là mất hẳn con số.
ALTER TABLE provisions DROP CONSTRAINT IF EXISTS provisions_noi_dung_citable_check;

DO $$ BEGIN
    ALTER TABLE provisions ADD CONSTRAINT provisions_noi_dung_citable_check
        CHECK (cap NOT IN ('dieu', 'khoan', 'diem', 'hang_bang')
               OR btrim(noi_dung) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
