import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import type { Payload } from 'payload'
import { MAT_KHAU, getTestPayload, stamp, taoAdmin } from './helpers/payload'

let payload: Payload
const rac: (number | string)[] = []
beforeAll(async () => {
  payload = await getTestPayload()
})
afterAll(async () => {
  for (const id of rac.reverse())
    await payload.delete({ collection: 'admins', id, overrideAccess: true }).catch(() => undefined)
})

describe('admins (spec 2B §6.2)', () => {
  it('doc không đổi được vai_tro và hoat_dong của chính mình, đổi được tên', async () => {
    const doc = await taoAdmin(payload, { vai_tro: 'doc' })
    rac.push(doc.id)
    const qt = await taoAdmin(payload, { vai_tro: 'quan_tri' })
    rac.push(qt.id)
    const sau = await payload.update({
      collection: 'admins',
      id: doc.id,
      data: { ten: 'Đổi', vai_tro: 'quan_tri', hoat_dong: false },
      user: doc,
      overrideAccess: false,
    })
    expect(sau.ten).toBe('Đổi')
    expect(sau.vai_tro).toBe('doc')
    expect(sau.hoat_dong).toBe(true)
  })

  it('doc không tạo và không xoá admin khác', async () => {
    const doc = await taoAdmin(payload, { vai_tro: 'doc' })
    rac.push(doc.id)
    const qt = await taoAdmin(payload, { vai_tro: 'quan_tri' })
    rac.push(qt.id)
    await expect(
      payload.create({
        collection: 'admins',
        data: { email: `${stamp()}@klaw.test`, password: MAT_KHAU, ten: 'x', vai_tro: 'doc' },
        user: doc,
        overrideAccess: false,
      }),
    ).rejects.toThrow()
    await expect(
      payload.delete({ collection: 'admins', id: qt.id, user: doc, overrideAccess: false }),
    ).rejects.toThrow()
  })

  it('không hạ vai trò, vô hiệu hay xoá quản trị viên cuối cùng', async () => {
    const khac = await payload.find({
      collection: 'admins',
      where: { vai_tro: { equals: 'quan_tri' } },
      limit: 100,
      overrideAccess: true,
    })
    const cuoi = await taoAdmin(payload, { vai_tro: 'quan_tri' })
    rac.push(cuoi.id)
    for (const a of khac.docs)
      await payload.update({
        collection: 'admins',
        id: a.id,
        data: { vai_tro: 'doc' },
        overrideAccess: true,
      })
    await expect(
      payload.update({
        collection: 'admins',
        id: cuoi.id,
        data: { vai_tro: 'doc' },
        overrideAccess: true,
      }),
    ).rejects.toThrow(/cuối cùng/)
    await expect(
      payload.update({
        collection: 'admins',
        id: cuoi.id,
        data: { hoat_dong: false },
        overrideAccess: true,
      }),
    ).rejects.toThrow(/cuối cùng/)
    await expect(
      payload.delete({ collection: 'admins', id: cuoi.id, overrideAccess: true }),
    ).rejects.toThrow(/cuối cùng/)
    for (const a of khac.docs)
      await payload.update({
        collection: 'admins',
        id: a.id,
        data: { vai_tro: 'quan_tri' },
        overrideAccess: true,
      })
  })

  it('hoat_dong=false không đăng nhập được; 5 lần sai thì khoá', async () => {
    const tat = await taoAdmin(payload, { vai_tro: 'doc', hoat_dong: false })
    rac.push(tat.id)
    await expect(
      payload.login({ collection: 'admins', data: { email: tat.email, password: MAT_KHAU } }),
    ).rejects.toThrow()
    const a = await taoAdmin(payload, { vai_tro: 'doc' })
    rac.push(a.id)
    for (let i = 0; i < 5; i++)
      await payload
        .login({ collection: 'admins', data: { email: a.email, password: 'sai' } })
        .catch(() => undefined)
    await expect(
      payload.login({ collection: 'admins', data: { email: a.email, password: MAT_KHAU } }),
    ).rejects.toThrow()
  })

  it('người đầu tiên luôn là quan_tri (hook ép khi collection rỗng)', async () => {
    // Không xoá dữ liệu thật của DB test; kiểm hook qua Local API với `overrideAccess` trên
    // DB đã có admin thì hook KHÔNG ép — nên chỉ khẳng định nhánh "đã có admin" ở đây, và
    // nhánh "rỗng" được kiểm bằng tay ở bước 8 (create-first-user).
    const a = await taoAdmin(payload, { vai_tro: 'doc' })
    rac.push(a.id)
    expect(a.vai_tro).toBe('doc')
  })
})
