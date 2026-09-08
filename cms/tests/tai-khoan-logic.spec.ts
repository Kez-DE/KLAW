import { describe, expect, it } from 'vitest'
import { cauXacNhan } from '../src/views/tai-khoan-logic'
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
