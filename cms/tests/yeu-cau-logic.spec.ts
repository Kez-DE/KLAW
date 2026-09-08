import { describe, expect, it } from 'vitest'
import { thongDiepSauThaoTac } from '../src/views/yeu-cau-logic'
describe('thông điệp sau duyệt/từ chối (spec §6.5)', () => {
  it('409 là cảnh báo + tải lại, 423 là lỗi có hướng dẫn, 200 là ok', () => {
    expect(thongDiepSauThaoTac(200, 'duyet', '')).toEqual({ kieu: 'ok', chu: 'Đã duyệt. Gói của người dùng đã đổi.', taiLai: true })
    expect(thongDiepSauThaoTac(409, 'duyet', 'x')).toMatchObject({ kieu: 'canh_bao', taiLai: true, chu: expect.stringContaining('người khác') })
    expect(thongDiepSauThaoTac(423, 'duyet', 'x')).toMatchObject({ kieu: 'loi', chu: expect.stringContaining('mở khoá') })
    expect(thongDiepSauThaoTac(500, 'tu_choi', 'Máy bận')).toEqual({ kieu: 'loi', chu: 'Máy bận', taiLai: false })
    expect(thongDiepSauThaoTac(403, 'duyet', '')).toEqual({ kieu: 'loi', chu: 'Vai trò của bạn chỉ được xem, không duyệt được.', taiLai: false })
  })
})
