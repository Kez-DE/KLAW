export type ThongBao = { id: number; loai: string; tieu_de: string; noi_dung: string; duong_dan: string; da_doc: boolean; tao_luc: string }
export const BADGE_CAP = 99
export const formatBadge = (n: number): string | null => (n <= 0 ? null : n > BADGE_CAP ? `${BADGE_CAP}+` : String(n))

export type DayBucket = 'today' | 'yesterday' | 'older'
const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
export const bucketFor = (iso: string, now: Date): DayBucket => {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'older'
  const today = startOfDay(now)
  const yesterday = startOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1))
  const day = startOfDay(then)
  return day >= today ? 'today' : day >= yesterday ? 'yesterday' : 'older'
}
const NHAN: Record<DayBucket, string> = { today: 'Hôm nay', yesterday: 'Hôm qua', older: 'Trước đó' }
export const nhomTheoNgay = (items: ThongBao[], now: Date) =>
  (['today', 'yesterday', 'older'] as DayBucket[])
    .map((b) => ({ nhan: NHAN[b], items: items.filter((t) => bucketFor(t.tao_luc, now) === b) }))
    .filter((n) => n.items.length > 0)

/** Chỉ điều hướng trong admin: một `duong_dan` lạ từ dữ liệu không được kéo trình duyệt đi đâu khác. */
export const duongDanCms = (duong: string): string => (duong === '/admin' || duong.startsWith('/admin/') ? duong : '/admin')
