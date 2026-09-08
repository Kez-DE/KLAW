import { describe, expect, it } from 'vitest'
import { nenEpQuanTri } from '../src/access/vaiTro'

describe('nenEpQuanTri (không cần DB)', () => {
  it('collection rỗng → ép quan_tri', () => {
    expect(nenEpQuanTri(0)).toBe(true)
  })
  it('đã có admin → không ép', () => {
    expect(nenEpQuanTri(1)).toBe(false)
  })
})
