-- Spec 2026-09-07 vo-ung-dung-va-tai-khoan §5 — yêu cầu nâng/gia hạn gói và chu kỳ
-- gói trả phí. Duyệt (gói 2B; tạm SQL tay): UPDATE users SET plan='pro',
-- plan_het_han = greatest(now(), coalesce(plan_het_han, now())) + interval '30 days'.
CREATE TABLE IF NOT EXISTS yeu_cau_nang_goi (
    id           BIGSERIAL PRIMARY KEY,
    user_sub     UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    loai         TEXT NOT NULL CHECK (loai IN ('nang_goi', 'gia_han')),
    goi_hien_tai TEXT NOT NULL,
    goi_muon     TEXT NOT NULL,
    trang_thai   TEXT NOT NULL DEFAULT 'cho_duyet'
                 CHECK (trang_thai IN ('cho_duyet', 'da_duyet', 'tu_choi')),
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    xu_ly_luc    TIMESTAMPTZ,
    xu_ly_boi    UUID
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_yeu_cau_nang_goi_cho_duyet
    ON yeu_cau_nang_goi(user_sub) WHERE trang_thai = 'cho_duyet';

-- Chu kỳ gói trả phí: NULL = không hết hạn (free, hoặc pro cấp tay vô thời hạn).
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_het_han TIMESTAMPTZ;
