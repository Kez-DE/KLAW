-- Bản đồ sửa đổi CẤP ĐIỀU KHOẢN, suy từ footnote văn bản hợp nhất của Công báo.
--
-- Vấn đề nó giải, bằng đúng một ví dụ đo được:
--
--   DB   45/2019/QH14 > Điều 139 > Khoản 1  "…nghỉ thai sản … là 06 tháng"
--        documents.tinh_trang = HHL1P       ← nhãn KHÔNG nói phần nào bị sửa
--   VBHN "…trường hợp sinh con thứ hai … là 07 tháng"
--        sửa bởi khoản 1 Điều 29 Luật Dân số 113/2025/QH15, hiệu lực 01/7/2026
--
-- Hôm nay 01/9/2026 sửa đổi đã có hiệu lực, nhưng hệ thống trả "06 tháng" kèm
-- trích dẫn QUA ĐƯỢC CẢ HAI TẦNG KIỂM. Nó trung thực (gắn
-- `mot_phan_khong_xac_dinh`) nhưng đó là dạng yếu nhất của sự thật. Bảng này
-- biến nhãn mù đó thành "Khoản 1 Điều 139 bị sửa bởi 113/2025/QH15 từ 01/7/2026".
--
-- ── VBHN KHÔNG thay thế corpus ──────────────────────────────────────────────
-- Không cột nào ở đây chứa text hợp nhất, và `provisions.noi_dung` KHÔNG bị
-- đụng tới. `PRODUCT.md` tuyên bố corpus là văn bản GỐC và hệ thống bảo đảm
-- nguồn gốc + đúng nguyên văn, KHÔNG bảo đảm là bản hiện hành; VBHN là tài liệu
-- tham khảo, không phải văn bản có hiệu lực pháp lý. Bảng này chỉ mang QUAN HỆ.
--
-- ── Vì sao `provision_id` chứ không (document, số điều, số khoản) ────────────
-- Neo là thứ DUY NHẤT trong footnote mang tính cấu trúc: `<w:footnoteReference>`
-- nằm trong `<w:p>` nào thì `<w:p>` đó CHÍNH LÀ khoản bị sửa. Phân giải nó ra
-- `provisions.id` một lần lúc nạp, rồi để FK giữ, là cách duy nhất bảo đảm mọi
-- dòng ở đây trỏ tới một điều khoản CÓ THẬT trong corpus. Trỏ bằng chuỗi thì
-- một lỗi chính tả thành một bản ghi mồ côi không ai phát hiện.
--
-- `sua_boi_so_ky_hieu` KHÔNG có FK sang `documents`: đo được 2/3 văn bản đi sửa
-- (113/2025/QH15 Luật Dân số, 124/2025/QH15 Luật Giáo dục nghề nghiệp) NẰM
-- NGOÀI corpus 57 văn bản. FK ở đây sẽ vứt bỏ đúng ca Điều 139 — ca trung tâm.
-- Việc đối chiếu chéo vì thế là TÍN HIỆU TIN CẬY (`do_tin_cay`), không phải bộ
-- lọc: xem CHECK bên dưới.
--
-- ── `do_tin_cay`, ba mức, mỗi mức một phát biểu ─────────────────────────────
--   cao               — khuôn khớp VÀ `sua_boi_so_ky_hieu` đối chiếu được với
--                       một `documents.so_ky_hieu` có thật ⇒ nguồn thứ hai xác nhận.
--   trung_binh        — khuôn khớp, nhưng văn bản đi sửa ngoài corpus nên không
--                       đối chiếu được. Neo vị trí vẫn là cấu trúc.
--   can_doi_chieu_tay — câu trích dẫn LỆCH khuôn. Giữ vị trí (vẫn tin được),
--                       ba cột kia để NULL. Không đoán.
--
-- CHECK dưới đây biến quy tắc "không đoán" thành bất biến của lược đồ: đã khai
-- `can_doi_chieu_tay` thì KHÔNG được đồng thời mang số hiệu/ngày, và ngược lại
-- `cao`/`trung_binh` thì phải có đủ cả ba. Không có nó, một loader về sau ghi
-- nửa vời — "bị sửa bởi 113/2025/QH15 từ ngày NULL" — và `effectivity.py` sẽ
-- nêu tên một văn bản kèm một ngày trống.
--
-- ── Idempotent ──────────────────────────────────────────────────────────────
-- `run_migrations()` chạy MỌI file mỗi lần khởi động (xem `011`). File này
-- thuần DDL nên `IF NOT EXISTS` là đủ; nó KHÔNG nạp dữ liệu — dữ liệu do
-- `scripts/nap_sua_doi_vbhn.py` nạp, và script đó tự idempotent qua unique
-- index `ux_sua_doi_neo` + ON CONFLICT.

CREATE TABLE IF NOT EXISTS sua_doi_dieu_khoan (
    id                  BIGSERIAL PRIMARY KEY,
    provision_id        BIGINT NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
    vi_tri              TEXT NOT NULL,   -- vị trí VBHN nêu, vd "Điều 154 > Khoản 8a"
    sua_boi_so_ky_hieu  TEXT,            -- "113/2025/QH15"
    sua_boi_duong_dan   TEXT,            -- "khoản 1 Điều 29"
    tu_ngay             DATE,
    nguon               TEXT NOT NULL,   -- "congbao.chinhphu.vn — 18/VBHN-VPQH"
    do_tin_cay          TEXT NOT NULL,
    ghi_chu             TEXT             -- nguyên văn footnote, để đối chiếu tay
);

CREATE INDEX IF NOT EXISTS ix_sua_doi_provision ON sua_doi_dieu_khoan(provision_id);

-- Khoá tự nhiên của một điểm sửa: (điều khoản bị sửa, nguồn, vị trí nguồn nêu).
-- `vi_tri` nằm trong khoá vì một khoản MỚI ("8a") phân giải về Điều cha, nên
-- hai điểm sửa khác nhau của cùng một Điều có cùng `provision_id`.
CREATE UNIQUE INDEX IF NOT EXISTS ux_sua_doi_neo
    ON sua_doi_dieu_khoan(provision_id, nguon, vi_tri);

ALTER TABLE sua_doi_dieu_khoan DROP CONSTRAINT IF EXISTS sua_doi_do_tin_cay_check;
ALTER TABLE sua_doi_dieu_khoan ADD CONSTRAINT sua_doi_do_tin_cay_check CHECK (
    (do_tin_cay IN ('cao', 'trung_binh')
        AND sua_boi_so_ky_hieu IS NOT NULL
        AND sua_boi_duong_dan IS NOT NULL
        AND tu_ngay IS NOT NULL)
    OR
    (do_tin_cay = 'can_doi_chieu_tay'
        AND sua_boi_so_ky_hieu IS NULL
        AND sua_boi_duong_dan IS NULL
        AND tu_ngay IS NULL)
);
