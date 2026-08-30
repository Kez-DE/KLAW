-- Nới `references_loai_check` từ 0..15 lên 0..31, và dành riêng dải 20..23 cho
-- các quan hệ HIỆU LỰC được TỰ SUY RA từ `relationships.parquet` (T1, plan 3 —
-- xem `scripts/load_incoming_edges.py`), khác với 0..15 là bảng mã MOJ trả về
-- qua API:
--   20 = Sửa đổi, bổ sung          22 = Văn bản quy định hết hiệu lực
--   21 = Thay thế                  23 = Văn bản quy định hết hiệu lực 1 phần
-- 24..31 để trống — chỗ cho quan hệ tự suy ra khác nếu phát sinh về sau.
--
-- Vì sao một dải RIÊNG thay vì lấp các mã trống của MOJ (0,2,5,6,7,8,11,13,14,15):
-- MOJ đang dùng 1,3,4,9,10,12 nhưng có thể dùng lại bất kỳ mã trống nào ở lần
-- fetch sau với NGHĨA KHÁC của riêng họ — trộn namespace khi đó sẽ sai ÂM THẦM
-- (một dòng loai=11 không còn phân biệt được "MOJ nói gì" với "ta tự suy ra gì").
-- 20..31 nằm ngoài 0..15 mà MOJ từng dùng nên không thể đụng.
--
-- `references_loai_check` CHUYỂN HẲN về file này: `001` giữ bản CŨ, HẸP (0..15).
-- Theo đúng quy tắc "một constraint thì một file sở hữu, và đó là file mới nhất"
-- (002:17, đã áp dụng lại ở 004, 005) — câu lệnh tạo nó ở `001` đã được gỡ, thay
-- bằng một ghi chú trỏ về đây. Lý do gỡ hẳn chứ không để cả hai cùng tồn tại:
-- nếu constraint vắng mặt lúc `001` chạy trên bảng đã có dòng loai>=20 (ai đó
-- DROP tay, hoặc một migration tương lai đánh số giữa 001 và 007 có DROP) thì
-- `ADD` bản hẹp của `001` ném `check_violation` (23514) trên chính các dòng đó
-- — mã đó KHÔNG nằm trong danh sách `EXCEPTION`, và `run_migrations()` bọc mọi
-- file trong MỘT transaction nên toàn bộ migration rollback. Đây đúng là bug
-- Plan 1 đã gặp với `provisions_cap_check` (xem `004`). DROP-rồi-ADD dưới đây
-- nên chạy lại được nhiều lần trên bảng CÓ dữ liệu — xem
-- `tests/test_infra/test_migrations.py::test_migration_idempotent_KHI_DA_CO_DONG_loai_hieu_luc_suy_ra`.

ALTER TABLE "references" DROP CONSTRAINT IF EXISTS references_loai_check;

DO $$ BEGIN
    ALTER TABLE "references" ADD CONSTRAINT references_loai_check
        CHECK (loai BETWEEN 0 AND 31);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
