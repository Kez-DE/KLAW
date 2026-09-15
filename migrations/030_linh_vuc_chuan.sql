-- Spec 2026-09-15d — trục thứ hai: 27 lĩnh vực.
--
-- Ba cột, ba việc khác nhau, đừng gộp:
--   * `linh_vuc`        — giá trị NGUYÊN VĂN từ nguồn. 56 giá trị tự do trên
--                          88/1634 dòng. Là ĐẦU VÀO của phép xếp, không phải
--                          kết quả; ghi đè lên nó là tự xoá nguồn của mình.
--   * `nganh_luat`      — 12 ngành luật, phân loại học thuật (migration 029).
--   * `linh_vuc_chuan`  — 27 lĩnh vực, phân loại thực dụng. Mịn hơn nên bộ lọc
--                          retrieval dùng cột này.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS linh_vuc_chuan TEXT;

ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_linh_vuc_chuan;
ALTER TABLE documents ADD CONSTRAINT ck_documents_linh_vuc_chuan
    CHECK (linh_vuc_chuan IS NULL OR linh_vuc_chuan IN ('thu_tuc_to_tung', 'trach_nhiem_hinh_su', 'lao_dong_tien_luong', 'so_huu_tri_tue', 'chung_khoan', 'bao_hiem', 'ke_toan_kiem_toan', 'thue_phi_le_phi', 'tien_te_ngan_hang', 'xuat_nhap_khau', 'bat_dong_san', 'xay_dung_do_thi', 'cong_nghe_thong_tin', 'dich_vu_phap_ly', 'vi_pham_hanh_chinh', 'giao_thong_van_tai', 'tai_nguyen_moi_truong', 'the_thao_y_te', 'giao_duc', 'dau_tu', 'doanh_nghiep', 'thuong_mai', 'tai_chinh_nha_nuoc', 'quyen_dan_su', 'van_hoa_xa_hoi', 'phap_luat_hanh_chinh', 'linh_vuc_khac'));

CREATE INDEX IF NOT EXISTS ix_documents_linh_vuc_chuan
    ON documents(linh_vuc_chuan) WHERE linh_vuc_chuan IS NOT NULL;
