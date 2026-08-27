-- Đẩy hai bất biến nền tảng XUỐNG DB, và nhận cấp `mo_dau`.
--
-- Vì sao ở DB chứ không ở app code: hai bất biến "neo trích dẫn duy nhất" và
-- "`noi_dung` không rỗng ở cấp trích dẫn được" trước file này chỉ tồn tại ở
-- `prov_parser._kiem_bat_bien` (chạy lúc BUILD) và `tests/test_scripts/
-- test_seed_committed.py` (chạy trên FILE ĐÃ COMMIT). KHÔNG cái nào nằm trên
-- đường INGEST — đường thật sự nạp dữ liệu mà verifier tầng 1 sẽ đọc.
-- `scripts/ingest.py` không parse qua pydantic, không gọi lại `_kiem_bat_bien`,
-- không đọc `checksums.json`. Sửa tay `provisions.jsonl` rồi bump checksum là
-- nạp được dòng hỏng vào DB mà không qua một phép kiểm nào.
--
-- `provisions_cap_check` cũng chuyển hẳn về file này (M6): `001` giữ bản CŨ, HẸP
-- của constraint mà `003` sở hữu, vi phạm chính quy tắc `002` đặt ra. Đường vỡ
-- cụ thể: nếu constraint vắng mặt lúc `001` chạy trên bảng đã có dữ liệu (ai đó
-- DROP tay, hoặc một migration tương lai đánh số giữa 001 và 002 có DROP) thì
-- `ADD` bản hẹp ném `check_violation` (23514) trên các dòng `tieu_muc`/`phu_luc`
-- — mã đó KHÔNG nằm trong danh sách `EXCEPTION`, và `run_migrations()` bọc mọi
-- file trong MỘT transaction nên toàn bộ migration rollback.
--
-- Quy tắc (002:17): MỘT constraint thì MỘT file sở hữu, và đó là file mới nhất.
-- Cả ba câu lệnh dưới đây DROP trước rồi ADD, nên chúng chạy lại được nhiều lần
-- trên bảng CÓ dữ liệu: `ADD` kiểm lại dữ liệu đang có và dữ liệu đúng thì qua.

ALTER TABLE provisions DROP CONSTRAINT IF EXISTS provisions_cap_check;

DO $$ BEGIN
    ALTER TABLE provisions ADD CONSTRAINT provisions_cap_check
        CHECK (cap IN ('phan', 'chuong', 'muc', 'tieu_muc', 'dieu', 'khoan',
                       'diem', 'phu_luc', 'mo_dau'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Neo trích dẫn duy nhất Ở CẤP TRÍCH DẪN ĐƯỢC. Partial index vì cấp Chương có
-- một ngoại lệ đã chấp nhận: NĐ 145/2020 thật sự đánh số hai Chương cùng là
-- "Chương XI", và bịa "XII" để né là bịa ký hiệu không có trong nguồn. Partial
-- index làm trùng ở cấp trích dẫn được thành BẤT KHẢ THI VỀ MẶT VẬT LÝ, không
-- phụ thuộc việc ai có nhớ chạy Cổng A hay không.
CREATE UNIQUE INDEX IF NOT EXISTS ux_provisions_neo_trich_dan
    ON provisions (duong_dan) WHERE cap IN ('dieu', 'khoan', 'diem');

-- `noi_dung` rỗng ở cấp trích dẫn được = phép kiểm "câu trích khớp nguyên văn"
-- không có gì để đối chiếu: hoặc luôn thất bại (ABSTAIN mọi câu hỏi), hoặc được
-- viết cho "rỗng thì bỏ qua" và khi đó nó không kiểm gì cả. `btrim` vì một chuỗi
-- chỉ có khoảng trắng cũng rỗng theo nghĩa này.
ALTER TABLE provisions DROP CONSTRAINT IF EXISTS provisions_noi_dung_citable_check;

DO $$ BEGIN
    ALTER TABLE provisions ADD CONSTRAINT provisions_noi_dung_citable_check
        CHECK (cap NOT IN ('dieu', 'khoan', 'diem') OR btrim(noi_dung) <> '');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
