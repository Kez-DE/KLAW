import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import type { Payload } from 'payload'
import { ALLOWLIST } from '../src/lib/allowlist'
import { quyetDinh, taoEndpoint } from '../src/endpoints/klaw'
import { getTestPayload } from './helpers/payload'

const DOC = { id: 1, email: 'doc@klaw.test', vai_tro: 'doc', hoat_dong: true }
const QT = { id: 2, email: 'qt@klaw.test', vai_tro: 'quan_tri', hoat_dong: true }
const SUB = '7c9e6679-7425-40de-944b-e07fc1f90ae7'
const hang = (d: string) => ALLOWLIST.find((h) => h.duong === d)!
let payload: Payload
beforeAll(async () => { payload = await getTestPayload() })
afterEach(() => vi.unstubAllGlobals())

const req = (user: unknown, url: string, params: Record<string, string>, body = '') =>
  ({ user, url, routeParams: params, headers: new Headers({ 'x-forwarded-for': '9.9.9.9' }), text: async () => body, payload }) as never

describe('proxy (spec §6.4)', () => {
  it('quyetDinh: 401 không phiên, 403 doc ghi, 404 sub sai, null khi hợp lệ', () => {
    expect(quyetDinh(null, hang('/tong-quan'), {})).toBe(401)
    expect(quyetDinh({ ...DOC, hoat_dong: false }, hang('/tong-quan'), {})).toBe(401)
    expect(quyetDinh(DOC, hang('/yeu-cau/:id/duyet'), { id: '1' })).toBe(403)
    expect(quyetDinh(QT, hang('/tai-khoan/:sub'), { sub: 'x' })).toBe(404)
    expect(quyetDinh(DOC, hang('/tai-khoan/:sub'), { sub: SUB })).toBeNull()
    expect(quyetDinh(QT, hang('/yeu-cau/:id/duyet'), { id: '1' })).toBeNull()
    expect(quyetDinh(QT, hang('/yeu-cau/:id/duyet'), { id: '..' })).toBe(404)
    expect(quyetDinh(QT, hang('/yeu-cau/:id/duyet'), { id: '1' })).toBeNull()
  })

  it('không phiên → 401 và KHÔNG gọi KLAW; doc POST → 403 và KHÔNG gọi KLAW', async () => {
    const f = vi.fn(); vi.stubGlobal('fetch', f)
    const ep = taoEndpoint(hang('/yeu-cau/:id/duyet'))
    expect((await ep.handler(req(null, 'http://cms.local/api/klaw/yeu-cau/1/duyet', { id: '1' }))).status).toBe(401)
    expect((await ep.handler(req(DOC, 'http://cms.local/api/klaw/yeu-cau/1/duyet', { id: '1' }))).status).toBe(403)
    expect(f).not.toHaveBeenCalled()
  })

  it('tham số dạng ../ (path traversal) → 404 và KHÔNG gọi KLAW', async () => {
    const f = vi.fn(); vi.stubGlobal('fetch', f)
    const r = await taoEndpoint(hang('/yeu-cau/:id/duyet')).handler(req(QT, 'http://cms.local/api/klaw/yeu-cau/../duyet', { id: '..' }))
    expect(r.status).toBe(404)
    expect(f).not.toHaveBeenCalled()
  })

  it('quan_tri → chuyển tiếp đúng URL, hai header, body, query; ghi nhat_ky_cms khi 2xx', async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ sub: SUB, plan: 'pro' }), { status: 200, headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', f)
    const r = await taoEndpoint(hang('/tai-khoan/:sub/goi')).handler(req(QT, `http://cms.local/api/klaw/tai-khoan/${SUB}/goi?x=1`, { sub: SUB }, '{"plan":"pro"}'))
    expect(r.status).toBe(200); expect(await r.json()).toEqual({ sub: SUB, plan: 'pro' })
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`http://klaw.test/api/v1/admin/tai-khoan/${SUB}/goi?x=1`)
    expect(init.method).toBe('PATCH'); expect(init.body).toBe('{"plan":"pro"}')
    const h = new Headers(init.headers)
    expect(h.get('x-admin-key')).toBe(process.env.KLAW_ADMIN_API_KEY); // tests/setup.ts đặt 'khoa-test' khi shell không xuất expect(h.get('x-admin-boi')).toBe('qt@klaw.test'); expect(h.get('x-forwarded-for')).toBe('9.9.9.9')
    const nk = await payload.find({ collection: 'nhat_ky_cms', where: { and: [{ hanh_dong: { equals: 'dat_goi' } }, { boi: { equals: 'qt@klaw.test' } }] }, overrideAccess: true })
    expect(nk.totalDocs).toBeGreaterThan(0)
  })

  it('KLAW 503 giữ nguyên mã và thân; fetch ném → 502', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Đường quản trị chưa được cấu hình.' }), { status: 503, headers: { 'content-type': 'application/json' } })))
    let r = await taoEndpoint(hang('/tong-quan')).handler(req(DOC, 'http://cms.local/api/klaw/tong-quan', {}))
    expect(r.status).toBe(503); expect((await r.json()).detail).toMatch(/chưa được cấu hình/)
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('ECONNREFUSED') }))
    r = await taoEndpoint(hang('/tong-quan')).handler(req(DOC, 'http://cms.local/api/klaw/tong-quan', {}))
    expect(r.status).toBe(502)
  })

  it('SSE trả thẳng body với text/event-stream', async () => {
    const body = new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode('event: so_chua_doc\ndata: 1\n\n')); c.close() } })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } })))
    const r = await taoEndpoint(hang('/thong-bao/luong')).handler(req(DOC, 'http://cms.local/api/klaw/thong-bao/luong', {}))
    expect(r.headers.get('content-type')).toBe('text/event-stream'); expect(await r.text()).toContain('so_chua_doc')
  })
})
