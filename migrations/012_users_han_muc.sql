-- Plan 4b — danh tính người dùng + hạn mức THÁNG theo người, thay hạn mức theo IP.
--
-- Lệch pha mà file này đóng: frontend có đăng ký/đăng nhập/bảng giá, backend chỉ
-- có MỘT API key dùng chung (`010`). Ba hệ quả đo được của việc đó:
--   * rate limit theo IP KHÔNG phân biệt hai người sau cùng một NAT
--   * trần chi phí toàn hệ thống KHÔNG tính tiền được cho ai
--   * bảng giá bán "50 lượt hỏi AI/tháng" mà không có gì cưỡng chế con số đó
--
-- Supabase chỉ làm AUTH (Google + Microsoft). Nó phát JWT, FastAPI xác minh
-- (`src/services/xac_thuc.py`), dữ liệu ở lại Postgres này. KHÔNG nhân bản dữ
-- liệu người dùng, KHÔNG thêm một data plane thứ hai.
--
-- `012` SỞ HỮU `users` và `traces.user_sub` — theo quy tắc "một object, một
-- owner, file mới nhất" mà `002:17` đặt ra và `005`/`007`/`008`/`009`/`010` đã tuân.

-- ── users — khoá theo Supabase `sub` ────────────────────────────────────────
-- NĂM cột, và mỗi cột phải trả lời được câu "cưỡng chế hạn mức hay liên hệ?".
-- Dự án chịu ràng buộc Luật Bảo vệ dữ liệu cá nhân 2025: mỗi cột thêm là một
-- nghĩa vụ thêm (thông báo, lưu trữ, xoá theo yêu cầu), nên bảng này CỐ Ý không
-- có `ho_ten`, `avatar_url`, `provider`, `raw_user_meta` — Supabase đã giữ tất
-- cả những thứ đó và nhân bản chúng sang đây chỉ tạo ra một bản sao thứ hai
-- phải bảo vệ, phải đồng bộ, và phải xoá.
--
-- `sub` là UUID chứ không TEXT: Supabase phát `sub` dạng uuid, và cột uuid tự
-- chặn rác ở tầng DB thay vì tin tầng ứng dụng luôn kiểm đúng. (`xac_thuc`
-- cũng kiểm ở biên — 401, không phải 503 — nhưng hai tầng cùng chặn là đúng.)
--
-- KHÔNG có FK nào tới Supabase (khác hệ thống) và KHÔNG có FK từ `traces` sang
-- đây: xem ghi chú ở `traces.user_sub` dưới.
CREATE TABLE IF NOT EXISTS users (
    sub          UUID PRIMARY KEY,
    -- Để LIÊN HỆ (thông báo hạn mức, hoá đơn). NULL được: đăng nhập bằng số
    -- điện thoại không mang email, và đó không phải lý do từ chối một người dùng.
    email        TEXT,
    -- Khoá tra `config/han_muc.yaml`. TEXT + DEFAULT chứ không enum: tên gói là
    -- quyết định SẢN PHẨM chưa chốt, và đổi một enum trong Postgres là một
    -- migration, còn đổi một dòng YAML thì không.
    plan         TEXT        NOT NULL DEFAULT 'free',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Người dùng còn hoạt động hay không — cần cho việc dọn tài khoản chết
    -- (nghĩa vụ hạn chế thời gian lưu trữ), và là dữ liệu vận hành duy nhất ở đây.
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── traces.user_sub — gán request cho người, để ĐẾM được ────────────────────
-- Không đếm được lượt của một người thì không cưỡng chế được hạn mức của họ.
-- Đếm TỪ `traces` chứ không dựng bộ đếm thứ hai, đúng lý lẽ `010` đã dùng cho
-- trần chi phí: hai bộ đếm sẽ lệch nhau và không cách nào biết bên nào đúng.
-- `traces.cache_hit` (do `010` thêm) là thứ làm điều này khả thi — cache hit
-- không gọi LLM nên không được trừ lượt.
--
-- NULL = request KHÔNG xác thực: eval, dev local khi chưa cấu hình Supabase, và
-- các endpoint đọc thuần. NULL phải hợp lệ, không phải một khiếm khuyết —
-- đường không-xác-thực là đường `eval/run.py` đang chạy.
--
-- KHÔNG có `REFERENCES users(sub)`: một FK ở đây biến mọi lượt ghi traces
-- (best-effort, không được chặn response) thành phụ thuộc vào việc dòng `users`
-- tồn tại đúng lúc đó, và một `ON DELETE` sai sẽ xoá dữ liệu ĐO LƯỜNG của khoá
-- luận khi xoá một tài khoản. Bảng này là số liệu, không phải quan hệ nghiệp vụ.
--
-- ⚠ NGHĨA VỤ KÈM THEO (ghi ra để không ai phát hiện muộn): cột này tạo LIÊN KẾT
-- giữa câu hỏi của người dùng (`traces.query`) và danh tính của họ. `traces` vẫn
-- CHƯA có thời hạn lưu trữ (mục B8 còn mở trong hardening-report §8.5). Liên kết
-- này làm mục đó cấp thiết hơn, không phải bớt.
ALTER TABLE traces ADD COLUMN IF NOT EXISTS user_sub UUID;

-- Index PHẦN: phần lớn dòng có `user_sub IS NULL` (eval, dev, endpoint đọc
-- thuần) và không dòng nào trong số đó bao giờ được truy vấn theo cột này.
CREATE INDEX IF NOT EXISTS ix_traces_user_sub_ts
    ON traces(user_sub, ts) WHERE user_sub IS NOT NULL;
