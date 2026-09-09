/** Đáp ứng `/goi` (proxy KLAW) — dùng chung cho TaiKhoanClient, YeuCauClient, ChiTietTaiKhoan
 * để tránh khai ba lần cùng một hình dạng. */
export type DanhSachGoi = { goi: { ma: string; ten: string }[]; goi_mac_dinh: string; chu_ky_pro_ngay: number }

const GOI_CUNG: Record<string, string> = { free: 'Miễn phí', pro: 'Cá nhân' }
export const tenGoi = (ma: string, goi?: { ma: string; ten: string }[]): string => goi?.find((g) => g.ma === ma)?.ten ?? GOI_CUNG[ma] ?? ma

export const nhanTrangThaiYeuCau = (t: string): string => ({ cho_duyet: 'Chờ duyệt', da_duyet: 'Đã duyệt', tu_choi: 'Từ chối' } as Record<string, string>)[t] ?? t
export const nhanLoai = (l: string): string => ({ nang_goi: 'Nâng gói', gia_han: 'Gia hạn' } as Record<string, string>)[l] ?? l

export const HANH_DONG: Record<string, string> = {
  duyet_yeu_cau: 'Duyệt yêu cầu', tu_choi_yeu_cau: 'Từ chối yêu cầu', dat_goi: 'Đặt gói', thu_hoi_goi: 'Thu hồi gói',
  khoa_tai_khoan: 'Khoá tài khoản', mo_khoa_tai_khoan: 'Mở khoá tài khoản', xac_thuc_that_bai: 'Xác thực thất bại',
  dang_nhap: 'Đăng nhập', dang_xuat: 'Đăng xuất', dang_nhap_that_bai: 'Đăng nhập thất bại', da_doc_thong_bao: 'Đánh dấu đã đọc',
}
const HAU_TO = '_that_bai'
export const nhanHanhDong = (hd: string): string => {
  if (HANH_DONG[hd]) return HANH_DONG[hd]
  const goc = hd.endsWith(HAU_TO) ? hd.slice(0, -HAU_TO.length) : ''
  return goc && HANH_DONG[goc] ? `${HANH_DONG[goc]} (thất bại)` : hd
}

const FMT = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric', hour12: false, timeZone: 'Asia/Ho_Chi_Minh' })
export const dinhDangLuc = (iso: string | null): string => {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const p = Object.fromEntries(FMT.formatToParts(t).map((x) => [x.type, x.value]))
  return `${p.hour}:${p.minute} ${p.day}/${p.month}/${p.year}`
}
export const soNgayCon = (iso: string | null): number | null => {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : Math.max(0, Math.ceil((t - Date.now()) / 86_400_000))
}

const FMT_GIO = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Ho_Chi_Minh' })
/** Chỉ giờ:phút theo giờ Việt Nam — cho "từ 10:31" trong danh sách trực tuyến. */
export const dinhDangGio = (iso: string | null): string => {
  if (!iso) return ''
  const t = Date.parse(iso)
  return Number.isNaN(t) ? '' : FMT_GIO.format(t)
}
/** Chữ cái đầu cho avatar: phần trước @ của email, viết hoa; rỗng → "?" */
export const chuDau = (email: string | null | undefined): string => (email?.trim() ? email.trim()[0].toUpperCase() : '?')
