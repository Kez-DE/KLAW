import { describe, expect, it } from 'vitest'
import { bucketFor, duongDanCms, formatBadge, nhomTheoNgay } from '../src/components/ChuongThongBao/bell'

const tb = (id: number, iso: string) => ({ id, loai: 'yeu_cau_moi', tieu_de: 't', noi_dung: 'n', duong_dan: '/admin/yeu-cau', da_doc: false, tao_luc: iso })

describe('bell.ts', () => {
  it('badge: 0 → null, 99+ khi vượt trần', () => {
    expect(formatBadge(0)).toBeNull(); expect(formatBadge(7)).toBe('7'); expect(formatBadge(150)).toBe('99+')
  })
  it('bucket theo NGÀY lịch, không theo giờ trôi', () => {
    const now = new Date(2026, 8, 9, 0, 10)
    expect(bucketFor(new Date(2026, 8, 8, 23, 50).toISOString(), now)).toBe('yesterday')
    expect(bucketFor(new Date(2026, 8, 9, 0, 5).toISOString(), now)).toBe('today')
    expect(bucketFor('rác', now)).toBe('older')
  })
  it('nhóm bỏ nhóm rỗng, giữ thứ tự Hôm nay → Hôm qua → Trước đó', () => {
    const now = new Date(2026, 8, 9, 12)
    const nhom = nhomTheoNgay([tb(1, new Date(2026, 8, 1).toISOString()), tb(2, new Date(2026, 8, 9, 8).toISOString())], now)
    expect(nhom.map((n) => n.nhan)).toEqual(['Hôm nay', 'Trước đó'])
  })
  it('đường dẫn ngoài /admin bị đưa về /admin', () => {
    expect(duongDanCms('/admin/yeu-cau?trang_thai=cho_duyet')).toBe('/admin/yeu-cau?trang_thai=cho_duyet')
    expect(duongDanCms('https://x.y/z')).toBe('/admin')
  })
})
