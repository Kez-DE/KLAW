// Logic thuần cho view Yêu cầu (spec 2026-09-08 cms-quan-ly-tai-khoan §6.5). Không React, không fetch.

/** Chép từ `YeuCauAdminOut` (KLAW `src/models/schemas.py`, Task 1). */
export type YeuCauAdmin = {
  id: number
  user_sub: string
  email: string | null
  loai: 'nang_goi' | 'gia_han'
  goi_hien_tai: string
  goi_muon: string
  trang_thai: 'cho_duyet' | 'da_duyet' | 'tu_choi'
  tao_luc: string
  xu_ly_luc: string | null
  xu_ly_boi: string | null
  ly_do: string | null
  plan_hieu_luc: string
  khoa_luc: string | null
}

export type ThongDiep = { kieu: 'ok' | 'canh_bao' | 'loi'; chu: string; taiLai: boolean }
export const thongDiepSauThaoTac = (status: number, loai: 'duyet' | 'tu_choi', chuMayChu: string): ThongDiep => {
  if (status >= 200 && status < 300) return { kieu: 'ok', chu: loai === 'duyet' ? 'Đã duyệt. Gói của người dùng đã đổi.' : 'Đã từ chối. Người dùng sẽ thấy lý do.', taiLai: true }
  if (status === 409) return { kieu: 'canh_bao', chu: 'Yêu cầu này vừa được người khác xử lý.', taiLai: true }
  if (status === 423) return { kieu: 'loi', chu: 'Tài khoản đang bị khoá, mở khoá trước khi duyệt.', taiLai: false }
  if (status === 403) return { kieu: 'loi', chu: 'Vai trò của bạn chỉ được xem, không duyệt được.', taiLai: false }
  return { kieu: 'loi', chu: chuMayChu || `Lỗi ${status}.`, taiLai: false }
}
