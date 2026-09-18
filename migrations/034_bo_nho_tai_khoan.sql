-- Phase 12 (R1) — điều KLAW nhớ về TÀI KHOẢN: dữ kiện người dùng tự khai
-- trong một lượt soạn thảo (họ tên, mã SV, nơi thực tập...) và thói quen soạn
-- (văn phong, cách xưng hô, mẫu hay dùng). Chỉ NHỚ, không tự điền: bảng này
-- không bao giờ chảy vào `facts`/`clauses` của một văn bản mới nếu lượt của
-- người dùng không gọi tới nó.
--
-- Vì sao KHÔNG mở rộng `ho_so_tai_khoan` (023): bảng đó là hồ sơ TÌNH HUỐNG
-- pháp lý, chỉ Pro, bảy khoá cố định và lưới chặn của nó LOẠI mọi dấu vết định
-- danh (chuỗi 9–12 chữ số = đúng hình dạng một mã sinh viên). Yêu cầu mới đảo
-- ngược đúng điểm đó (chủ dự án đã sửa phạm vi: tên và mã SV PHẢI được nhớ),
-- nên nhồi chung sẽ hoặc phá lưới chặn của hồ sơ pháp lý, hoặc phải đục lỗ nó.
--
-- Vì sao `nguon_hoi_thoai_id` KHÔNG có khoá ngoại: `ban_thao` và
-- `viec_doc_tai_lieu` chết theo hội thoại (D10, 032). Ký ức về tài khoản thì
-- KHÔNG được chết theo — một FK `ON DELETE CASCADE` tới `hoi_thoai` sẽ để một
-- lần xoá hội thoại lặng lẽ mang ký ức đi. Cột chỉ để biết dữ kiện tới từ đâu.
-- Khoá theo `users(sub)` thì cascade là ĐÚNG: xoá tài khoản phải xoá luôn dữ
-- liệu cá nhân của nó, cùng cách mọi bảng theo người dùng ở đây đã làm.
--
-- UNIQUE (user_sub, loai, khoa): nói lại một dữ kiện là đè bản cũ, không sinh
-- dòng thứ hai — và chỉ mục đó cũng phục vụ luôn truy vấn liệt kê theo `user_sub`
-- (cột dẫn đầu), nên không cần chỉ mục riêng.
CREATE TABLE IF NOT EXISTS bo_nho_tai_khoan (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_sub           UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    loai               TEXT NOT NULL CHECK (loai IN ('ca_nhan', 'thoi_quen')),
    khoa               TEXT NOT NULL,
    gia_tri            TEXT NOT NULL,
    nguon_hoi_thoai_id UUID,
    tao_luc            TIMESTAMPTZ NOT NULL DEFAULT now(),
    cap_nhat_luc       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_sub, loai, khoa)
);
