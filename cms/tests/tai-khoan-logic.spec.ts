import { describe, expect, it } from 'vitest'
import { cauXacNhan, hanHienThi, sapHetHan } from '../src/views/tai-khoan-logic'
describe('câu xác nhận nêu hậu quả (spec §6.5)', () => {
  it('cả bốn hành động bắt buộc lý do; khoá nêu hậu quả; đặt gói nêu số ngày hoặc vô thời hạn', () => {
    expect(cauXacNhan('khoa', { email: 'a@b.c' })).toEqual({ tieuDe: 'Khoá tài khoản a@b.c?', moTa: 'Người dùng sẽ không hỏi và soạn được cho tới khi mở khoá. Tra cứu và soát văn bản vẫn mở.', canLyDo: true })
    expect(cauXacNhan('mo_khoa', { email: 'a@b.c' }).canLyDo).toBe(true)
    expect(cauXacNhan('dat_goi', { email: 'a@b.c', tenGoi: 'Cá nhân', soNgay: 30 }).canLyDo).toBe(true)
    expect(cauXacNhan('dat_goi', { email: 'a@b.c', tenGoi: 'Cá nhân', soNgay: 30 }).moTa).toContain('30 ngày')
    expect(cauXacNhan('dat_goi', { email: 'a@b.c', tenGoi: 'Cá nhân', soNgay: null }).moTa).toContain('vô thời hạn')
    expect(cauXacNhan('thu_hoi', { email: 'a@b.c' })).toMatchObject({ canLyDo: true, moTa: expect.stringContaining('ngay lập tức') })
  })
})

describe('sapHetHan (fix review #1, finding 2)', () => {
  const NGAY_MS = 86_400_000
  const now = Date.parse('2026-01-15T00:00:00Z')
  it('null và chuỗi không hợp lệ là false; 3 ngày tới là true; 8 ngày tới và ngày quá khứ là false', () => {
    expect(sapHetHan(null, now)).toBe(false)
    expect(sapHetHan('không-phải-ngày', now)).toBe(false)
    expect(sapHetHan(new Date(now + 3 * NGAY_MS).toISOString(), now)).toBe(true)
    expect(sapHetHan(new Date(now + 8 * NGAY_MS).toISOString(), now)).toBe(false)
    expect(sapHetHan(new Date(now - NGAY_MS).toISOString(), now)).toBe(false)
  })
})

describe('hanHienThi (fix review #1, finding 1)', () => {
  it('gói mặc định luôn trả rong dù còn hạn cũ; gói trả phí có hạn hợp lệ trả chuỗi đã định dạng; hạn null trả rong', () => {
    const haiNgayTruoc = new Date(Date.now() - 2 * 86_400_000).toISOString()
    expect(hanHienThi('free', haiNgayTruoc, 'free', 'vô thời hạn')).toBe('vô thời hạn')
    const ketQua = hanHienThi('pro', haiNgayTruoc, 'free', 'vô thời hạn')
    expect(ketQua).not.toBe('vô thời hạn')
    expect(ketQua.length).toBeGreaterThan(0)
    expect(hanHienThi('pro', null, 'free', 'vô thời hạn')).toBe('vô thời hạn')
  })
})
