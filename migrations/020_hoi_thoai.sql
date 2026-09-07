-- Spec 2026-09-07 §4 — phiên hội thoại theo tài khoản. `tra_loi` là NGUYÊN payload
-- `TraCuuResponse` để mở lại phiên render y hệt (thẻ trích dẫn vẫn bấm được).
-- Xoá mềm bằng `xoa_luc`; hạn mức hiện theo gói nằm ở config/han_muc.yaml, không ở DB.
CREATE TABLE IF NOT EXISTS hoi_thoai (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_sub     UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    tieu_de      TEXT NOT NULL,
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    cap_nhat_luc TIMESTAMPTZ NOT NULL DEFAULT now(),
    xoa_luc      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_hoi_thoai_user_cap_nhat
    ON hoi_thoai(user_sub, cap_nhat_luc DESC) WHERE xoa_luc IS NULL;

CREATE TABLE IF NOT EXISTS luot_hoi_thoai (
    id           BIGSERIAL PRIMARY KEY,
    hoi_thoai_id UUID NOT NULL REFERENCES hoi_thoai(id) ON DELETE CASCADE,
    thu_tu       INTEGER NOT NULL,
    cau_hoi      TEXT NOT NULL,
    tra_loi      JSONB NOT NULL,
    trace_id     TEXT,
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (hoi_thoai_id, thu_tu)
);
