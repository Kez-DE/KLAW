// Logic thuần cho view Tài khoản (spec 2026-09-08 cms-quan-ly-tai-khoan §6.5). Không React, không fetch.
import { dinhDangLuc } from '../lib/hien-thi'

/** Chép từ `TaiKhoanTomTat` (KLAW `src/models/schemas.py`). */
export type TaiKhoanTomTat = {
  sub: string
  email: string | null
  plan: string
  plan_het_han: string | null
  khoa_luc: string | null
  tao_luc: string
  so_phien: number
  luot_30_ngay: number; truc_tuyen?: boolean
}

/** Chép từ `TaiKhoanChiTiet` (KLAW `src/models/schemas.py`). Không render `hoat_dong`/`phan_loai` — không hiện nội dung hội thoại. */
export type TaiKhoanChiTiet = {
  sub: string
  email: string | null
  plan: string
  ten_goi: string
  tao_luc: string
  het_han_luc: string | null
  so_phien: number
  tong_hoi_dap: number
  tong_ban_thao: number
  hoat_dong: unknown[]
  phan_loai: unknown[]
  khoa_luc: string | null
  khoa_ly_do: string | null; truc_tuyen?: boolean
  yeu_cau: {
    id: number
    loai: string
    goi_hien_tai: string
    goi_muon: string
    trang_thai: string
    tao_luc: string
    xu_ly_luc: string | null
    ly_do: string | null
  }[]
}

const NGAY_MS = 86_400_000
const HET_HAN_TRONG_NGAY = 7
/** `?loc=het_han`: hạn trong 7 ngày tới. `now` cho phép test xác định (mặc định lúc gọi). */
export const sapHetHan = (iso: string | null, now: number = Date.now()): boolean => {
  if (!iso) return false
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return false
  const conLai = t - now
  return conLai >= 0 && conLai <= HET_HAN_TRONG_NGAY * NGAY_MS
}

/** Hạn hiển thị (fix review #1): KLAW không xoá `plan_het_han` khi gói hết hạn/bị thu hồi
 * về gói mặc định, nên tài khoản đang ở gói mặc định phải luôn hiện `rong` (vô thời hạn/"—"),
 * bất kể hạn cũ còn sót lại. Dùng chung cho danh sách và chi tiết để hai màn không lệch nhau. */
export const hanHienThi = (plan: string, hetHan: string | null, goiMacDinh: string | undefined, rong: string): string => {
  if (plan === goiMacDinh) return rong
  if (!hetHan || Number.isNaN(Date.parse(hetHan))) return rong
  return dinhDangLuc(hetHan)
}

export type HanhDongTK = 'dat_goi' | 'thu_hoi' | 'khoa' | 'mo_khoa'
export const cauXacNhan = (hd: HanhDongTK, ctx: { email: string; tenGoi?: string; soNgay?: number | null }): { tieuDe: string; moTa: string; canLyDo: boolean } => {
  switch (hd) {
    case 'khoa':
      return { tieuDe: `Khoá tài khoản ${ctx.email}?`, moTa: 'Người dùng sẽ không hỏi và soạn được cho tới khi mở khoá. Tra cứu và soát văn bản vẫn mở.', canLyDo: true }
    case 'mo_khoa':
      return { tieuDe: `Mở khoá tài khoản ${ctx.email}?`, moTa: 'Người dùng hỏi và soạn văn bản lại được ngay. Lý do chỉ ghi vào nhật ký, người dùng không thấy.', canLyDo: true }
    case 'thu_hoi':
      return { tieuDe: `Thu hồi gói trả phí của ${ctx.email}?`, moTa: 'Gói về Miễn phí ngay lập tức; người dùng nhận thông báo kèm lý do. Dùng cho lạm dụng, không dùng thay cho việc để gói hết hạn.', canLyDo: true }
    case 'dat_goi':
      return {
        tieuDe: `Đặt gói ${ctx.tenGoi ?? ''} cho ${ctx.email}?`,
        moTa: `${ctx.soNgay == null ? `Gói ${ctx.tenGoi ?? ''} vô thời hạn (không có ngày hết hạn).` : `Gói ${ctx.tenGoi ?? ''} trong ${ctx.soNgay} ngày tính từ bây giờ.`} Lý do chỉ ghi vào nhật ký, người dùng không thấy.`,
        canLyDo: true,
      }
  }
}
