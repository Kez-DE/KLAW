-- Spec 2026-09-17 Phase 4 (D11, R1) — lịch sử phiên bản KHÔNG PHÁ HUỶ (`lui`
-- không còn xoá hẳn bản bị rời đi, xem `ban_thao.lui`) đòi một nguồn số phiên
-- bản KHÔNG BAO GIỜ cấp lại: nếu vẫn tính `phien_ban = cu["phien_ban"] + 1`
-- như trước, một nhánh bị bỏ được GIỮ LẠI sẽ trùng số với phiên bản mới do một
-- lần sửa sau đó sinh ra (đúng ca `ban_thao.lui` docstring cũ đã cảnh báo).
-- `phien_ban_ke_tiep` là bộ đếm riêng, chỉ ĐI LÊN, tách khỏi cột `phien_ban`
-- (cột này VẪN lùi được bởi `lui`) — không phải bảng thứ hai, D11 đã chốt.
ALTER TABLE ban_thao ADD COLUMN IF NOT EXISTS phien_ban_ke_tiep INTEGER;

-- Backfill = phien_ban + 1, KHÔNG PHẢI phien_ban + độ dài phien_ban_truoc:
-- mảng đó bị TRAN_SUA (10) chặn trên, nên với một bản thảo đã sửa hơn 10 lần
-- công thức "+ độ dài" nhảy số vô cớ; còn với một bản thảo CHƯA từng sửa
-- (phien_ban=1, phien_ban_truoc=[]) nó cho đúng 1 — TRÙNG với chính số đang
-- sống, tức lần sửa đầu tiên sau migration này sẽ cấp lại số 1. Mọi số nhỏ
-- hơn phien_ban (kể cả trong phien_ban_truoc, xem bất biến ở `ban_thao.lui`)
-- luôn nhỏ hơn phien_ban, nên "+ 1" là số nhỏ nhất chắc chắn CHƯA từng cấp.
UPDATE ban_thao SET phien_ban_ke_tiep = phien_ban + 1 WHERE phien_ban_ke_tiep IS NULL;

-- Bản thảo MỚI (`ban_thao.tao`) luôn khởi tạo phien_ban = 1 (default cột có
-- sẵn), nên số kế tiếp mặc định phải là 2 — cùng công thức backfill ở trên.
ALTER TABLE ban_thao ALTER COLUMN phien_ban_ke_tiep SET DEFAULT 2;
ALTER TABLE ban_thao ALTER COLUMN phien_ban_ke_tiep SET NOT NULL;
