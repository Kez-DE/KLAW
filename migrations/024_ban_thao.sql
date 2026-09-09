-- Spec 2026-09-09 §8 — bản thảo đã lưu (gói 3 của spec lịch sử hội thoại §10) và trạng thái
-- soạn thảo đang mở của phiên. `phien_ban_truoc` giữ tối đa 10 bản {phien_ban, document, facts}.
ALTER TABLE hoi_thoai ADD COLUMN IF NOT EXISTS soan_thao JSONB;

CREATE TABLE IF NOT EXISTS ban_thao (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_sub        UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    hoi_thoai_id    UUID REFERENCES hoi_thoai(id) ON DELETE SET NULL,
    loai            TEXT NOT NULL,
    facts           JSONB NOT NULL DEFAULT '{}'::jsonb,
    document        TEXT NOT NULL,
    clauses         JSONB NOT NULL DEFAULT '[]'::jsonb,
    audit           JSONB NOT NULL DEFAULT '{}'::jsonb,
    phien_ban       INTEGER NOT NULL DEFAULT 1,
    phien_ban_truoc JSONB NOT NULL DEFAULT '[]'::jsonb,
    tao_luc         TIMESTAMPTZ NOT NULL DEFAULT now(),
    cap_nhat_luc    TIMESTAMPTZ NOT NULL DEFAULT now(),
    xoa_luc         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_ban_thao_user_cap_nhat ON ban_thao(user_sub, cap_nhat_luc DESC) WHERE xoa_luc IS NULL;
