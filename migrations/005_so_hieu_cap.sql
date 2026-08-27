-- Mọi cấp CẤU TRÚC phải có số hiệu; chỉ hai cấp TÀI LIỆU được rỗng.
--
-- Vì sao dạng ĐỒNG NHẤT chứ không liệt kê `khoan`/`diem`: liệt kê chỉ đúng cho
-- cấp đang có bug, dạng đồng nhất đúng cho cả cấp sẽ thêm về sau. `mo_dau` và
-- `phu_luc` là chữ không thuộc điều luật nào nên chúng không có số hiệu để mang
-- — đó là toàn bộ ngoại lệ, và nó là ngoại lệ về BẢN CHẤT, không phải về dữ liệu.
--
-- Cái nó chặn: neo `"91/2015/QH13 > Điều 33 > Khoản"` — không phải một dẫn chiếu
-- pháp luật Việt Nam. Nếu tầng truy hồi đưa row đó lên và hệ thống hiển thị
-- `duong_dan` của nó làm citation thì người dùng nhận một trích dẫn KHÔNG THỂ
-- TRA. Trước file này, bất biến đó chỉ tồn tại ở parser (`SO_HIEU_BAT_BUOC`,
-- vốn cố ý loại Khoản/Điểm) và ở test trên file đã commit — DB nhận hết, và
-- unique index của `004` chỉ bắt được khi có HAI neo như vậy trùng nhau.
--
-- Đã đo trước khi thêm: `so_hieu_cap` rỗng ở `phan`/`chuong`/`muc`/`tieu_muc`/
-- `dieu`/`khoan`/`diem` = 0 trên cả 19.135 dòng, nên constraint xanh ngay.
--
-- Constraint này MỚI nên `005` sở hữu nó và chỉ nó — không đụng `004`, đúng quy
-- tắc "một constraint thì một file sở hữu, và đó là file mới nhất" (002:17).
-- DROP-rồi-ADD nên chạy lại được nhiều lần trên bảng CÓ dữ liệu.

ALTER TABLE provisions DROP CONSTRAINT IF EXISTS provisions_so_hieu_cap_check;

DO $$ BEGIN
    ALTER TABLE provisions ADD CONSTRAINT provisions_so_hieu_cap_check
        CHECK (cap IN ('mo_dau', 'phu_luc') OR btrim(so_hieu_cap) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
