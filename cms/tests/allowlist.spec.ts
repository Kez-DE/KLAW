import { describe, expect, it } from 'vitest'
import { ALLOWLIST, UUID_RE, dienDuong } from '../src/lib/allowlist'

describe('allowlist (spec §5.3, §6.4)', () => {
  it('có đủ 16 hàng đúng method/đường; mọi thao tác ghi ngoài thông báo cần quan_tri', () => {
    expect(ALLOWLIST.map((h) => `${h.method} ${h.duong}`).sort()).toEqual([
      'get /goi', 'get /nhat-ky', 'get /tai-khoan', 'get /tai-khoan/:sub', 'get /thong-bao', 'get /thong-bao/luong', 'get /tong-quan', 'get /truc-tuyen', 'get /yeu-cau',
      'patch /tai-khoan/:sub/goi',
      'post /tai-khoan/:sub/khoa', 'post /tai-khoan/:sub/mo-khoa', 'post /tai-khoan/:sub/thu-hoi', 'post /thong-bao/da-doc', 'post /yeu-cau/:id/duyet', 'post /yeu-cau/:id/tu-choi',
    ])
    expect(ALLOWLIST.filter((h) => h.method !== 'get' && !h.duong.startsWith('/thong-bao')).every((h) => h.vaiTro === 'quan_tri')).toBe(true)
    expect(ALLOWLIST.find((h) => h.duong === '/thong-bao/luong')?.sse).toBe(true)
  })
  it('dienDuong thay tham số và mã hoá; UUID_RE', () => {
    expect(dienDuong('/tai-khoan/:sub/khoa', { sub: 'abc' })).toBe('/tai-khoan/abc/khoa')
    expect(dienDuong('/yeu-cau/:id/duyet', { id: '5 6' })).toBe('/yeu-cau/5%206/duyet')
    expect(UUID_RE.test('7c9e6679-7425-40de-944b-e07fc1f90ae7')).toBe(true)
    expect(UUID_RE.test('khong-phai')).toBe(false)
  })
})
