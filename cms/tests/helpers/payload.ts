import { getPayload, type Payload } from 'payload'
import config from '@payload-config'

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
