-- Spec 2026-09-08 cms-quan-ly-tai-khoan §5.1 — đường quản trị: thông báo, nhật ký,
-- idempotent theo tham_chieu, lý do từ chối, khoá tài khoản. Idempotent (IF NOT EXISTS;
-- ALTER TYPE text trên cột đã là text là no-op hợp lệ).

CREATE TABLE IF NOT EXISTS thong_bao (
  id           BIGSERIAL PRIMARY KEY,
  nguoi_nhan   UUID REFERENCES users(sub) ON DELETE CASCADE,   -- NULL = hộp thư admin
  loai         TEXT NOT NULL CHECK (loai IN (
                 'yeu_cau_moi', 'yeu_cau_duyet', 'yeu_cau_tu_choi',
                 'goi_dat_tay', 'goi_thu_hoi', 'tai_khoan_khoa', 'tai_khoan_mo')),
  tieu_de      TEXT NOT NULL,
  noi_dung     TEXT NOT NULL,
  duong_dan    TEXT NOT NULL,
  khoa_gom     TEXT NOT NULL,
  da_doc       BOOLEAN NOT NULL DEFAULT FALSE,
  het_hieu_luc BOOLEAN NOT NULL DEFAULT FALSE,
  tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_thong_bao_gom
  ON thong_bao (khoa_gom) WHERE NOT het_hieu_luc;
CREATE INDEX IF NOT EXISTS ix_thong_bao_nhan
  ON thong_bao (nguoi_nhan, da_doc, tao_luc DESC);

-- CHỈ GHI THÊM. Không đường nào trong src/ UPDATE hay DELETE bảng này (test grep).
CREATE TABLE IF NOT EXISTS nhat_ky_quan_tri (
  id             BIGSERIAL PRIMARY KEY,
  hanh_dong      TEXT NOT NULL,
  doi_tuong      UUID,
  chi_tiet       JSONB NOT NULL DEFAULT '{}'::jsonb,
  boi            TEXT NOT NULL,
  tac_nhan_loai  TEXT NOT NULL DEFAULT 'admin'
                 CHECK (tac_nhan_loai IN ('admin', 'tu_dong', 'thanh_toan')),
  ip             TEXT,
  tao_luc        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_tao_luc ON nhat_ky_quan_tri (tao_luc DESC);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_hanh_dong ON nhat_ky_quan_tri (hanh_dong, tao_luc DESC);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_doi_tuong ON nhat_ky_quan_tri (doi_tuong, tao_luc DESC);

ALTER TABLE yeu_cau_nang_goi
  ADD COLUMN IF NOT EXISTS nguon      TEXT CHECK (nguon IN ('admin', 'thanh_toan')),
  ADD COLUMN IF NOT EXISTS tham_chieu TEXT,
  ADD COLUMN IF NOT EXISTS ly_do      TEXT,
  ALTER COLUMN xu_ly_boi TYPE TEXT USING xu_ly_boi::text;   -- cột luôn NULL tới nay
CREATE UNIQUE INDEX IF NOT EXISTS ux_yeu_cau_tham_chieu
  ON yeu_cau_nang_goi (tham_chieu) WHERE tham_chieu IS NOT NULL;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS khoa_luc   TIMESTAMPTZ,   -- NULL = bình thường
  ADD COLUMN IF NOT EXISTS khoa_ly_do TEXT;
