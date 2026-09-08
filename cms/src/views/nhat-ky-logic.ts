// Logic thuần cho view Nhật ký (spec 2026-09-08 cms-quan-ly-tai-khoan §6.5). Không React, không fetch.
export type LocNhatKy = { tu?: string; den?: string; hanhDong?: string; doiTuong?: string; trang: number; kichCo: number; csv?: boolean }
const iso = (local?: string): string | undefined => (local ? new Date(local).toISOString() : undefined)
export const queryNhatKy = (l: LocNhatKy): string => {
  const p = new URLSearchParams()
  const tu = iso(l.tu)
  const den = iso(l.den)
  if (tu) p.set('tu', tu)
  if (den) p.set('den', den)
  if (l.hanhDong) p.set('hanh_dong', l.hanhDong)
  if (l.doiTuong) p.set('doi_tuong', l.doiTuong)
  if (l.csv) { p.set('limit', '5000'); p.set('offset', '0'); p.set('dinh_dang', 'csv') }
  else { p.set('limit', String(l.kichCo)); p.set('offset', String((l.trang - 1) * l.kichCo)) }
  return `?${p.toString()}`
}
