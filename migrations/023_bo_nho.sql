-- Spec 2026-09-09 §6 — bộ nhớ ba lớp của phiên và hồ sơ tình huống theo tài khoản (Pro).
-- `tom_tat` gộp các lượt cũ hơn K lượt nguyên văn; `tom_tat_den_thu_tu` là lượt cuối đã gộp.
-- `ho_so` JSONB khoá cố định {khoa: {gia_tri, nguon}} — dữ kiện về NGƯỜI HỎI, không phải quy tắc luật.
-- `khong_ghi_nho` = "phiên không ghi nhớ": không tóm tắt, không gộp vào tài khoản.
ALTER TABLE hoi_thoai ADD COLUMN IF NOT EXISTS tom_tat TEXT;
ALTER TABLE hoi_thoai ADD COLUMN IF NOT EXISTS tom_tat_den_thu_tu INTEGER NOT NULL DEFAULT 0;
ALTER TABLE hoi_thoai ADD COLUMN IF NOT EXISTS ho_so JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE hoi_thoai ADD COLUMN IF NOT EXISTS khong_ghi_nho BOOLEAN NOT NULL DEFAULT false;

-- Công tắc chung của tài khoản (Pro): tắt thì không đọc, không ghi `ho_so_tai_khoan`.
ALTER TABLE users ADD COLUMN IF NOT EXISTS ghi_nho BOOLEAN NOT NULL DEFAULT true;

-- Hồ sơ tình huống theo tài khoản: một dòng một khoá, mới đè cũ, cascade khi xoá tài khoản.
CREATE TABLE IF NOT EXISTS ho_so_tai_khoan (
    user_sub           UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    khoa               TEXT NOT NULL,
    gia_tri            TEXT NOT NULL,
    nguon_hoi_thoai_id UUID,
    cap_nhat_luc       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_sub, khoa)
);
