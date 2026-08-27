CREATE TABLE IF NOT EXISTS documents (
    id                  TEXT PRIMARY KEY,          -- moj doc_id
    so_ky_hieu          TEXT NOT NULL,
    loai_van_ban        TEXT NOT NULL,
    ten                 TEXT NOT NULL,
    co_quan_ban_hanh    TEXT,
    ngay_ban_hanh       DATE,
    ngay_hieu_luc       DATE,
    ngay_het_hieu_luc   DATE,
    tinh_trang          TEXT NOT NULL,             -- CHL | HHL | HHL1P | chua_hieu_luc
    depth               TEXT NOT NULL DEFAULT 'deep',   -- deep | shallow
    nguon_url           TEXT,
    checksum            TEXT NOT NULL,
    crawled_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provisions (
    id                  BIGSERIAL PRIMARY KEY,
    document_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_id           BIGINT REFERENCES provisions(id) ON DELETE CASCADE,
    cap                 TEXT NOT NULL,             -- phan|chuong|muc|dieu|khoan|diem
    so_hieu_cap         TEXT NOT NULL,
    tieu_de             TEXT NOT NULL DEFAULT '',
    noi_dung            TEXT NOT NULL DEFAULT '',
    duong_dan           TEXT NOT NULL,
    source_node_id      TEXT,                      -- NULLABLE, KHÔNG UNIQUE (bẫy #2)
    thu_tu              INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_provisions_document_id ON provisions(document_id);
CREATE INDEX IF NOT EXISTS ix_provisions_duong_dan   ON provisions(duong_dan);
CREATE INDEX IF NOT EXISTS ix_provisions_cap         ON provisions(cap);

CREATE TABLE IF NOT EXISTS "references" (
    id                  BIGSERIAL PRIMARY KEY,
    from_document_id    TEXT NOT NULL,
    to_document_id      TEXT,
    from_provision_id   BIGINT REFERENCES provisions(id) ON DELETE CASCADE,
    to_provision_id     BIGINT REFERENCES provisions(id) ON DELETE CASCADE,
    loai                INTEGER NOT NULL,          -- mã 1..15 của MOJ
    raw_text            TEXT
);
CREATE INDEX IF NOT EXISTS ix_references_to_document   ON "references"(to_document_id);
CREATE INDEX IF NOT EXISTS ix_references_from_document ON "references"(from_document_id);

CREATE TABLE IF NOT EXISTS chunks (
    id                  BIGSERIAL PRIMARY KEY,
    provision_id        BIGINT NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
    noi_dung_embed      TEXT NOT NULL,
    embedding           vector(1024),
    embedding_model     TEXT NOT NULL,
    embedding_dim       INTEGER NOT NULL,
    tsv                 tsvector,
    token_count         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_chunks_provision ON chunks(provision_id);
CREATE INDEX IF NOT EXISTS ix_chunks_model     ON chunks(embedding_model);
CREATE INDEX IF NOT EXISTS ix_chunks_tsv       ON chunks USING gin(tsv);

CREATE TABLE IF NOT EXISTS verified_provisions (
    provision_id        BIGINT PRIMARY KEY REFERENCES provisions(id) ON DELETE CASCADE,
    verified_at         DATE NOT NULL,
    verified_by         TEXT NOT NULL,
    nguon_doi_chieu     TEXT NOT NULL,
    ket_luan            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verified_documents (
    document_id            TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    verified_at            DATE NOT NULL,
    verified_by            TEXT NOT NULL,
    nguon_doi_chieu        TEXT NOT NULL,
    ket_luan_hieu_luc      TEXT NOT NULL,
    ghi_chu_lech_voi_moj   TEXT
);

CREATE TABLE IF NOT EXISTS traces (
    id                      TEXT PRIMARY KEY,
    ts                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    endpoint                TEXT NOT NULL,
    query                   TEXT,
    config_name             TEXT NOT NULL,
    result_type             TEXT,
    retrieved_ids           BIGINT[],
    claims_raw              INTEGER,
    claims_after_tier1      INTEGER,
    claims_after_tier2      INTEGER,
    latency_ms              INTEGER,
    token_in                INTEGER,
    token_out               INTEGER,
    cost_usd                NUMERIC(12, 8)
);
CREATE INDEX IF NOT EXISTS ix_traces_config ON traces(config_name);

-- Ràng buộc giá trị. Idempotent: chạy được cả trên DB mới và DB đã tồn tại.
-- Postgres không hỗ trợ ADD CONSTRAINT IF NOT EXISTS cho CHECK/FK.
DO $$ BEGIN
    ALTER TABLE documents ADD CONSTRAINT documents_tinh_trang_check
        CHECK (tinh_trang IN ('CHL', 'HHL', 'HHL1P', 'chua_hieu_luc', 'chua_xac_dinh'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- `provisions_cap_check` CỐ Ý KHÔNG CÓ Ở ĐÂY. Nó do `004_bat_bien_neo_trich_dan.sql`
-- — file MỚI NHẤT — sở hữu, và chỉ nó. Bản cũ ở file này chỉ liệt kê 6 cấp, tức
-- nó là bản HẸP HƠN bản đang chạy; giữ lại là vi phạm quy tắc `002_cap_tieu_muc.sql`
-- đặt ra và mở một đường vỡ thật: nếu constraint vắng mặt lúc file này chạy trên
-- bảng đã có dữ liệu thì `ADD` bản hẹp ném check_violation (23514) trên các dòng
-- `tieu_muc`/`phu_luc`/`mo_dau` — mã đó không nằm trong EXCEPTION, và
-- `run_migrations()` bọc mọi file trong MỘT transaction nên tất cả rollback.

DO $$ BEGIN
    -- 0 = MOJ không cung cấp referenceType; 1..15 là bảng mã quan hệ của MOJ
    ALTER TABLE "references" ADD CONSTRAINT references_loai_check
        CHECK (loai BETWEEN 0 AND 15);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE "references" ADD CONSTRAINT references_from_document_fk
        FOREIGN KEY (from_document_id) REFERENCES documents(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
