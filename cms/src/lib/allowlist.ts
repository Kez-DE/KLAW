// cms/src/lib/allowlist.ts
/** Bảng §5.3 của spec chuyển sang mã. Mỗi hàng sinh MỘT endpoint Payload (endpoints/klaw.ts),
 *  nên không có đường ký tự đại diện: đường lạ tự 404 do không có route. */
export type VaiTro = 'doc' | 'quan_tri'
export type Hang = { method: 'get' | 'post' | 'patch'; duong: string; vaiTro: VaiTro; sse?: boolean; hanhDong?: string }

export const ALLOWLIST: readonly Hang[] = [
  { method: 'get', duong: '/tong-quan', vaiTro: 'doc' },
  { method: 'get', duong: '/truc-tuyen', vaiTro: 'doc' },
  { method: 'get', duong: '/goi', vaiTro: 'doc' },
  { method: 'get', duong: '/yeu-cau', vaiTro: 'doc' },
  { method: 'post', duong: '/yeu-cau/:id/duyet', vaiTro: 'quan_tri', hanhDong: 'duyet_yeu_cau' },
  { method: 'post', duong: '/yeu-cau/:id/tu-choi', vaiTro: 'quan_tri', hanhDong: 'tu_choi_yeu_cau' },
  { method: 'get', duong: '/tai-khoan', vaiTro: 'doc' },
  { method: 'get', duong: '/tai-khoan/:sub', vaiTro: 'doc' },
  { method: 'patch', duong: '/tai-khoan/:sub/goi', vaiTro: 'quan_tri', hanhDong: 'dat_goi' },
  { method: 'post', duong: '/tai-khoan/:sub/thu-hoi', vaiTro: 'quan_tri', hanhDong: 'thu_hoi_goi' },
  { method: 'post', duong: '/tai-khoan/:sub/khoa', vaiTro: 'quan_tri', hanhDong: 'khoa_tai_khoan' },
  { method: 'post', duong: '/tai-khoan/:sub/mo-khoa', vaiTro: 'quan_tri', hanhDong: 'mo_khoa_tai_khoan' },
  { method: 'get', duong: '/nhat-ky', vaiTro: 'doc' },
  { method: 'get', duong: '/thong-bao', vaiTro: 'doc' },
  { method: 'post', duong: '/thong-bao/da-doc', vaiTro: 'doc', hanhDong: 'da_doc_thong_bao' },
  { method: 'get', duong: '/thong-bao/luong', vaiTro: 'doc', sse: true },
]

export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

/** Chặn tham số đường chứa `..`, `/` đã mã hoá, v.v. trước khi ghép vào URL ngược dòng KLAW. */
export const THAM_SO_HOP_LE = /^[\w-]+$/

export const dienDuong = (mau: string, params: Record<string, string>): string =>
  mau.replace(/:(\w+)/g, (_, k: string) => encodeURIComponent(params[k] ?? ''))
