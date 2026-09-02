-- Cổng chặn: một neo trích dẫn HỨA một danh sách mà không giao gì cả.
--
-- ── Lỗi đã ship ─────────────────────────────────────────────────────────────
-- `prov_parser.parse_tables()` không có caller nào ngoài test của chính nó:
-- `parse_provisions` gọi `tbl.decompose()`, nên cả 133 <table> của corpus ra
-- khỏi cây và biến mất. Đo được trên DB: 5 provision cấp trích dẫn được kết
-- thúc bằng dấu hai chấm mà KHÔNG có con nào — tức chúng nói "… như sau:" rồi
-- không trỏ vào đâu cả. Hai trong số đó là BẢNG LƯƠNG TỐI THIỂU VÙNG
-- (293/2025/NĐ-CP và 74/2024/NĐ-CP, Điều 3 Khoản 1).
--
-- Vì sao đây là lỗi NGHIÊM TRỌNG chứ không phải một thiếu sót nhỏ: người lao
-- động hỏi "lương tối thiểu vùng I bao nhiêu" nhận một trích dẫn tới điều luật
-- KHÔNG CHỨA CON SỐ NÀO. Mô hình có thể viết ra một con số từ trí nhớ huấn
-- luyện rồi dẫn Điều 3 Khoản 1, và trích dẫn đó QUA ĐƯỢC CẢ HAI TẦNG KIỂM: điều
-- luật có thật (tầng 1 phép kiểm 1-2) và câu văn xuôi dẫn vào bảng khớp nguyên
-- văn (phép kiểm 3). Tầng 1 kiểm CÂU TRÍCH, nó không kiểm con số trong văn xuôi
-- — nên đúng ở chỗ nguy hiểm nhất, cơ chế chống ảo giác của khoá luận im lặng.
--
-- ── Vì sao là cổng ở tầng DB ────────────────────────────────────────────────
-- `004` đã ghi lý do: `scripts/ingest.py` KHÔNG parse qua pydantic, KHÔNG gọi
-- lại `_kiem_bat_bien`. Mọi bất biến chỉ sống trong parser đều có thể bị đi
-- vòng bằng cách sửa tay `provisions.jsonl` rồi bump checksum. Cổng này canh
-- đúng đường ingest đó.
--
-- Phép kiểm CHÍNH LÀ truy vấn đã dùng để đo thiệt hại — không phải một phép
-- xấp xỉ của nó. Sau khi bảng vào `noi_dung`, provision có bảng kết thúc bằng
-- '|' chứ không còn '.…:', nên nó tự rơi ra khỏi tập vi phạm mà không cần một
-- điều kiện thứ hai về '|'.
--
-- KHÔNG dùng CHECK constraint, và KHÔNG dùng khối `DO $$` chạy lúc migrate:
--
--   * CHECK không truy vấn được bảng khác, mà "không có con nào" thì cần.
--   * `004` đã ghi đúng lý do trigger THƯỜNG không dùng được ở đây: `ingest`
--     chèn cha TRƯỚC con, nên tại INSERT của một Khoản thì Điểm con của nó chưa
--     tồn tại và mọi Khoản đều trông như "không có con".
--   * Một khối `DO $$` chạy lúc migrate thì KHÓA CHÍNH LẦN NẠP SỬA LỖI:
--     `run_migrations()` chạy TRƯỚC khi `ingest` ghi dòng nào, nên nó đọc dữ
--     liệu CŨ, thấy 2 vi phạm và ném — đúng lần nạp lẽ ra chữa được chúng.
--     (Đã đo, không phải lo xa: bản đầu của file này viết như vậy và nó chặn
--     ngay lần ingest đầu tiên.)
--
-- `CONSTRAINT TRIGGER … DEFERRABLE INITIALLY DEFERRED` giải cả ba: nó chỉ chạy
-- khi CÓ GHI (nên DB cũ không bị khoá), và nó chạy lúc COMMIT — thời điểm cha
-- và con đã nằm đủ trong transaction, tức đúng lúc "có con hay không" mới có
-- nghĩa. Đây chính là câu trả lời cho phản đối mà `004` nêu ra.
--
-- ── Idempotent ──────────────────────────────────────────────────────────────
-- `CREATE OR REPLACE FUNCTION` + `DROP TRIGGER IF EXISTS` rồi `CREATE`: chạy
-- hai lần cho cùng một trigger, không nhân bản. Cùng khuôn `006_tsv.sql`.
-- File này KHÔNG đọc và KHÔNG ghi dòng dữ liệu nào lúc migrate, nên nó vô hại
-- với DB rỗng (lần khởi động đầu) lẫn DB đã nạp.
--
-- Chi phí: một lookup theo `ix_provisions_parent_id` (migration 009) cho mỗi
-- dòng cấp trích dẫn được, tại COMMIT của lần ingest. Đo trên corpus 19.138
-- dòng: dưới một giây.
--
-- ── Ba ngoại lệ: KHIẾM KHUYẾT CỦA NGUỒN, không phải của parser ──────────────
-- Đã mở HTML gốc của MOJ và đọc tay từng ca:
--
--   100/2015/QH13 > Điều 200 > Khoản 3   lỗi gõ ':' đáng lẽ là '.' — nguồn đi
--   100/2015/QH13 > Điều 236 > Khoản 3   thẳng sang "4. Người phạm tội còn có
--                                        thể…", không có bảng, không có Điểm
--   145/2020/NĐ-CP > Điều 56 > Khoản 2   hứa công thức lương làm đêm theo sản
--                                        phẩm nhưng HTML nguồn KHÔNG có bảng
--                                        nào trong phạm vi Điều 56 (đã đếm: 0).
--                                        Hai bảng công thức của văn bản này
--                                        thuộc Điều 55 và đã vào đúng chỗ.
--
-- Ghi TƯỜNG MINH từng `duong_dan` thay vì nới điều kiện: một ngoại lệ theo mẫu
-- ("bỏ qua mọi Khoản của BLHS") sẽ âm thầm nuốt luôn ca thứ tư khi nó xuất
-- hiện. Thêm dòng vào đây là hành vi CÓ Ý THỨC, đòi người thêm phải mở nguồn ra
-- đọc — đúng như ta vừa làm.

CREATE OR REPLACE FUNCTION provisions_hua_danh_sach_thi_phai_giao()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- Trigger DEFERRED chạy lúc COMMIT, và sự kiện đã được xếp hàng từ lúc
    -- INSERT — nên một dòng được chèn RỒI XOÁ trong CÙNG transaction vẫn bị
    -- kiểm, và sẽ luôn trông như "không có con". Bỏ qua dòng không còn tồn tại:
    -- không có dòng thì không có neo trích dẫn nào để hỏng.
    IF NOT EXISTS (SELECT 1 FROM provisions WHERE id = NEW.id) THEN
        RETURN NULL;
    END IF;
    IF NEW.cap NOT IN ('dieu', 'khoan', 'diem') THEN
        RETURN NULL;
    END IF;
    IF rtrim(NEW.noi_dung) NOT LIKE '%:' THEN
        RETURN NULL;
    END IF;
    IF NEW.duong_dan IN ('100/2015/QH13 > Điều 200 > Khoản 3',
                         '100/2015/QH13 > Điều 236 > Khoản 3',
                         '145/2020/NĐ-CP > Điều 56 > Khoản 2') THEN
        RETURN NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM provisions ch WHERE ch.parent_id = NEW.id) THEN
        RETURN NULL;
    END IF;

    RAISE EXCEPTION
        'BẢNG BỊ MẤT tại %: neo trích dẫn hứa một danh sách ("… như sau:") mà '
        'không có con NÀO và không có bảng trong noi_dung. Một câu trả lời dẫn '
        'nó sẽ không chứa con số nào, còn verify tầng 1 vẫn đóng dấu đã kiểm '
        'chứng vì câu văn xuôi khớp nguyên văn. Kiểm parse_tables() có còn được '
        'parse_provisions() gọi không; nếu nguồn MOJ thật sự thiếu bảng thì mở '
        'HTML ra xác nhận rồi thêm duong_dan vào danh sách ngoại lệ của '
        'migrations/013.', NEW.duong_dan;
END $$;

DROP TRIGGER IF EXISTS provisions_hua_danh_sach ON provisions;
CREATE CONSTRAINT TRIGGER provisions_hua_danh_sach
    AFTER INSERT OR UPDATE OF noi_dung ON provisions
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION provisions_hua_danh_sach_thi_phai_giao();
