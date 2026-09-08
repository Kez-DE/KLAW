import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import type { Payload } from 'payload'
import { getTestPayload, taoAdmin } from './helpers/payload'
import { ghiDangNhapThatBai, ghiNhatKyCms, ipCua } from '../src/hooks/nhatKyCms'

let payload: Payload
const rac: (number | string)[] = []
beforeAll(async () => {
  payload = await getTestPayload()
})
afterAll(async () => {
  for (const id of rac)
    await payload.delete({ collection: 'admins', id, overrideAccess: true }).catch(() => undefined)
})

describe('nhat_ky_cms (spec §6.3)', () => {
  it('không ai tạo/sửa/xoá qua access; admin hoạt động đọc được', async () => {
    const doc = await taoAdmin(payload, { vai_tro: 'doc' })
    rac.push(doc.id)
    await expect(
      payload.create({
        collection: 'nhat_ky_cms',
        data: { hanh_dong: 'x', boi: 'a' },
        user: doc,
        overrideAccess: false,
      }),
    ).rejects.toThrow()
    await ghiNhatKyCms(payload, { hanh_dong: 'thu', boi: 'qa@klaw.test' })
    const r = await payload.find({
      collection: 'nhat_ky_cms',
      where: { hanh_dong: { equals: 'thu' } },
      user: doc,
      overrideAccess: false,
    })
    expect(r.totalDocs).toBeGreaterThan(0)
    await expect(
      payload.update({
        collection: 'nhat_ky_cms',
        id: r.docs[0].id,
        data: { boi: 'khac' },
        user: doc,
        overrideAccess: false,
      }),
    ).rejects.toThrow()
    await expect(
      payload.delete({ collection: 'nhat_ky_cms', id: r.docs[0].id, user: doc, overrideAccess: false }),
    ).rejects.toThrow()
  })

  it('afterError trên /api/admins/login với 401 ghi dang_nhap_that_bai kèm email và IP', async () => {
    const req = {
      payload,
      url: 'http://cms.local/api/admins/login',
      headers: new Headers({ 'x-forwarded-for': '1.2.3.4' }),
      data: { email: 'sai@klaw.test' },
    }
    await ghiDangNhapThatBai({ error: Object.assign(new Error('x'), { status: 401 }), req } as never)
    const r = await payload.find({
      collection: 'nhat_ky_cms',
      where: { and: [{ hanh_dong: { equals: 'dang_nhap_that_bai' } }, { boi: { equals: 'sai@klaw.test' } }] },
      sort: '-createdAt',
      overrideAccess: true,
    })
    expect(r.totalDocs).toBeGreaterThan(0)
    expect(r.docs[0].ip).toBe('1.2.3.4')
    expect(ipCua({ headers: new Headers() } as never)).toBeNull()
  })

  it('afterError trên đường khác không ghi gì', async () => {
    const truoc = (await payload.count({ collection: 'nhat_ky_cms', overrideAccess: true })).totalDocs
    await ghiDangNhapThatBai({
      error: Object.assign(new Error('x'), { status: 401 }),
      req: { payload, url: 'http://cms.local/api/admins/me', headers: new Headers() },
    } as never)
    expect((await payload.count({ collection: 'nhat_ky_cms', overrideAccess: true })).totalDocs).toBe(truoc)
  })
})
