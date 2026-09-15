-- Spec 2026-09-15 §FR-006, §FR-007, §FR-022, §FR-026..FR-028 — tài liệu người
-- dùng và dữ kiện rút ra từ đó.
--
-- Hai quyết định nằm ở tầng DB chứ không ở tầng ứng dụng:
--
-- 1. `hoi_thoai_id ... ON DELETE CASCADE`. FR-027 nói xoá cuộc hội thoại là xoá
--    theo dữ kiện. Đặt ràng buộc đó ở Postgres nghĩa là nó đúng kể cả khi một
--    đường xoá mới được thêm ở chỗ khác và người viết quên dọn. Cùng hạng với
--    migration 004: đẩy bất biến vào DB thay vì tin vào kỷ luật của người gọi.
--
-- 2. `ck_du_kien_tai_lieu_co_neo`. Một dữ kiện có nguồn `tai_lieu` mà không có
--    trích dẫn hoặc không có vị trí là thứ FR-007 cấm tồn tại. Nếu chỉ chặn ở
--    Python thì một script nạp tay, một lần sửa vội, hay một endpoint tương lai
--    đều mở lại được cửa. Ở đây thì không.

CREATE TABLE IF NOT EXISTS viec_doc_tai_lieu (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_sub        UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    hoi_thoai_id    UUID NOT NULL REFERENCES hoi_thoai(id) ON DELETE CASCADE,
    ten_tep         TEXT NOT NULL,
    dau_van_ban     TEXT NOT NULL,
    so_byte         INTEGER NOT NULL,
    so_trang        INTEGER,
    loai            TEXT,
    trang_thai      TEXT NOT NULL DEFAULT 'dang_doc',
    ly_do_hong      TEXT,
    chi_phi_usd     DOUBLE PRECISION NOT NULL DEFAULT 0,
    so_lan_thu      INTEGER NOT NULL DEFAULT 0,
    tao_luc         TIMESTAMPTZ NOT NULL DEFAULT now(),
    cap_nhat_luc    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_viec_doc_trang_thai
        CHECK (trang_thai IN ('dang_doc', 'xong', 'hong', 'huy')),
    -- Trạng thái `hong` phải nói được hỏng vì gì. Một việc hỏng không có lý do
    -- là một việc người dùng không tự sửa được (FR-003, FR-038).
    CONSTRAINT ck_viec_doc_hong_co_ly_do
        CHECK (trang_thai <> 'hong' OR ly_do_hong IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_viec_doc_hoi_thoai ON viec_doc_tai_lieu(hoi_thoai_id, tao_luc DESC);
CREATE INDEX IF NOT EXISTS ix_viec_doc_user_tao ON viec_doc_tai_lieu(user_sub, tao_luc DESC);

CREATE TABLE IF NOT EXISTS du_kien_tai_lieu (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    viec_id         UUID NOT NULL REFERENCES viec_doc_tai_lieu(id) ON DELETE CASCADE,
    hoi_thoai_id    UUID NOT NULL REFERENCES hoi_thoai(id) ON DELETE CASCADE,
    khoa            TEXT NOT NULL,
    nhan            TEXT,
    gia_tri         TEXT NOT NULL,
    nguon           TEXT NOT NULL DEFAULT 'tai_lieu',
    trich           TEXT,
    trich_goc       TEXT,
    chi_so_don_vi   INTEGER,
    trang           INTEGER,
    offset_dau      INTEGER,
    tao_luc         TIMESTAMPTZ NOT NULL DEFAULT now(),
    xoa_luc         TIMESTAMPTZ,
    CONSTRAINT ck_du_kien_nguon
        CHECK (nguon IN ('tai_lieu', 'nguoi_dung_nhap', 'nguoi_dung_sua')),
    -- FR-007 ở tầng dữ liệu: dữ kiện nói là đến từ tài liệu thì phải chỉ được
    -- chỗ nó đến.
    CONSTRAINT ck_du_kien_tai_lieu_co_neo
        CHECK (
            nguon <> 'tai_lieu'
            OR (trich IS NOT NULL AND length(btrim(trich)) > 0
                AND chi_so_don_vi IS NOT NULL AND trang IS NOT NULL)
        ),
    -- FR-015: sửa một dữ kiện rút từ tài liệu thì trích gốc phải còn để đối
    -- chiếu, và giá trị đã sửa không được trình bày như thể đến từ tài liệu.
    CONSTRAINT ck_du_kien_sua_giu_trich_goc
        CHECK (nguon <> 'nguoi_dung_sua' OR trich_goc IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_du_kien_hoi_thoai ON du_kien_tai_lieu(hoi_thoai_id) WHERE xoa_luc IS NULL;
CREATE INDEX IF NOT EXISTS ix_du_kien_viec ON du_kien_tai_lieu(viec_id) WHERE xoa_luc IS NULL;
