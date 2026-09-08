// cms/src/endpoints/klaw.ts
import type { Endpoint, PayloadRequest } from 'payload'
import { dangHoatDong, laQuanTri } from '../access/vaiTro'
import { ghiNhatKyCms, ipCua } from '../hooks/nhatKyCms'
import { ALLOWLIST, THAM_SO_HOP_LE, UUID_RE, dienDuong, type Hang } from '../lib/allowlist'
import { goiKlaw } from '../lib/klaw-client'

const THONG_DIEP: Record<number, string> = {
  401: 'Bạn cần đăng nhập vào trang quản trị.',
  403: 'Vai trò của bạn chỉ được xem, không thực hiện được thao tác này.',
  404: 'Không tìm thấy.',
}

/** Thứ tự kiểm §6.4: phiên → tham số → vai trò. Thuần, test riêng. */
export const quyetDinh = (user: unknown, hang: Hang, params: Record<string, string>): 401 | 403 | 404 | null => {
  if (!dangHoatDong(user)) return 401
  if (Object.values(params).some((v) => !THAM_SO_HOP_LE.test(String(v)))) return 404
  if ('sub' in params && !UUID_RE.test(params.sub ?? '')) return 404
  if (hang.vaiTro === 'quan_tri' && !laQuanTri(user)) return 403
  return null
}

export const taoEndpoint = (hang: Hang): Endpoint => ({
  path: `/klaw${hang.duong}`,
  method: hang.method,
  handler: async (req: PayloadRequest) => {
    const params = (req.routeParams ?? {}) as Record<string, string>
    const ma = quyetDinh(req.user, hang, params)
    if (ma !== null) return Response.json({ detail: THONG_DIEP[ma] }, { status: ma })
    const user = req.user as { email: string }
    const url = new URL(req.url ?? 'http://cms.local/')
    const body = hang.method === 'get' || typeof req.text !== 'function' ? undefined : await req.text()
    const duong = dienDuong(hang.duong, params)
    const res = await goiKlaw({ method: hang.method, duong: duong + url.search, body: body || undefined, boi: user.email, ip: ipCua(req), sse: hang.sse })
    if (hang.sse && res.ok) {
      return new Response(res.body, { status: 200, headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', Connection: 'keep-alive' } })
    }
    const than = await res.text()
    if (res.ok && hang.method !== 'get' && hang.hanhDong) {
      await ghiNhatKyCms(req.payload, { hanh_dong: hang.hanhDong, boi: user.email, ip: ipCua(req), chi_tiet: { duong } })
    }
    const headers: Record<string, string> = { 'Content-Type': res.headers.get('content-type') ?? 'application/json' }
    const cd = res.headers.get('content-disposition')
    if (cd) headers['Content-Disposition'] = cd
    return new Response(than, { status: res.status, headers })
  },
})

export const klawEndpoints: Endpoint[] = ALLOWLIST.map(taoEndpoint)
