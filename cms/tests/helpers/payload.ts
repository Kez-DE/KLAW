import { getPayload, type Payload } from 'payload'
import config from '@payload-config'

// Bảo vệ chống trỏ nhầm: test xoá/sửa dữ liệu thật (vd. hạ vai trò mọi quan_tri trong
// admins.spec.ts) — một DATABASE_URI xuất khỏi shell (thắng `??=` ở tests/setup.ts) mà
// không phải database test sẽ phá dữ liệu thật.
if (!/_test(\?|$)/.test(process.env.DATABASE_URI ?? '')) {
  throw new Error('DATABASE_URI của test phải trỏ tới database có hậu tố _test')
}

let cached: Promise<Payload> | undefined
export const getTestPayload = (): Promise<Payload> => (cached ??= getPayload({ config }))

export const MAT_KHAU = 'test1234'
export const stamp = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

export const taoAdmin = async (
  payload: Payload,
  d: { email?: string; vai_tro: 'doc' | 'quan_tri'; hoat_dong?: boolean },
) =>
  payload.create({
    collection: 'admins',
    data: {
      email: d.email ?? `${stamp()}@klaw.test`,
      password: MAT_KHAU,
      ten: 'Test',
      vai_tro: d.vai_tro,
      hoat_dong: d.hoat_dong ?? true,
    },
    overrideAccess: true,
  })
