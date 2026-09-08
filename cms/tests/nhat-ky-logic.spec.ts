import { describe, expect, it } from 'vitest'
import { queryNhatKy } from '../src/views/nhat-ky-logic'
describe('query nhật ký', () => {
  it('bỏ trống, phân trang, csv lấy tối đa 5000', () => {
    expect(queryNhatKy({ trang: 2, kichCo: 50 })).toBe('?limit=50&offset=50')
    expect(queryNhatKy({ hanhDong: 'dat_goi', doiTuong: 'abc', trang: 1, kichCo: 50 })).toBe('?hanh_dong=dat_goi&doi_tuong=abc&limit=50&offset=0')
    expect(queryNhatKy({ tu: '2026-09-08T00:00', trang: 1, kichCo: 50, csv: true })).toBe('?tu=2026-09-07T17%3A00%3A00.000Z&limit=5000&offset=0&dinh_dang=csv')
  })
  it('lọc theo đến', () => {
    expect(queryNhatKy({ den: '2026-09-08T23:59', trang: 1, kichCo: 50 })).toBe('?den=2026-09-08T16%3A59%3A00.000Z&limit=50&offset=0')
  })
})
