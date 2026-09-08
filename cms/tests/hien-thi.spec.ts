import { describe, expect, it } from 'vitest'
import { dinhDangLuc, nhanHanhDong, nhanLoai, nhanTrangThaiYeuCau, soNgayCon, tenGoi } from '../src/lib/hien-thi'

describe('hien-thi (spec §6.5)', () => {
  it('tên gói ưu tiên danh mục KLAW, rơi về bảng cứng, mã lạ giữ mã', () => {
    expect(tenGoi('pro', [{ ma: 'pro', ten: 'Cá nhân' }])).toBe('Cá nhân')
    expect(tenGoi('free')).toBe('Miễn phí'); expect(tenGoi('vip')).toBe('vip')
  })
  it('nhãn tiếng Việt', () => {
    expect(nhanTrangThaiYeuCau('cho_duyet')).toBe('Chờ duyệt'); expect(nhanLoai('gia_han')).toBe('Gia hạn')
    expect(nhanHanhDong('duyet_yeu_cau')).toBe('Duyệt yêu cầu'); expect(nhanHanhDong('duyet_yeu_cau_that_bai')).toBe('Duyệt yêu cầu (thất bại)')
    expect(nhanHanhDong('la')).toBe('la')
  })
  it('thời gian theo Asia/Ho_Chi_Minh, null an toàn', () => {
    expect(dinhDangLuc('2026-09-08T17:00:00Z')).toBe('00:00 09/09/2026'); expect(dinhDangLuc(null)).toBe('')
    expect(soNgayCon(null)).toBeNull(); expect(soNgayCon(new Date(Date.now() + 2.5 * 86_400_000).toISOString())).toBe(3)
  })
})
