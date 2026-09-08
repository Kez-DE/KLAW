// cms/src/lib/klaw-client.ts
/** Gọi KLAW `/admin/*` — CHỈ chạy phía máy chủ. `KLAW_ADMIN_API_KEY` không có tiền tố
 *  NEXT_PUBLIC_ nên không bao giờ vào bundle trình duyệt (tests/bundle.spec.ts). */
export type YeuCauKlaw = { method: string; duong: string; body?: string; boi: string; ip?: string | null; sse?: boolean; signal?: AbortSignal }

export const goiKlaw = async (y: YeuCauKlaw, fetchFn: typeof fetch = fetch): Promise<Response> => {
  const goc = process.env.KLAW_API_URL
  const khoa = process.env.KLAW_ADMIN_API_KEY
  if (!goc || !khoa) return Response.json({ detail: 'CMS chưa cấu hình KLAW_API_URL hoặc KLAW_ADMIN_API_KEY.' }, { status: 503 })
  const headers: Record<string, string> = { 'X-Admin-Key': khoa, 'X-Admin-Boi': y.boi }
  if (y.ip) headers['X-Forwarded-For'] = y.ip
  if (y.body) headers['Content-Type'] = 'application/json'
  if (y.sse) headers.Accept = 'text/event-stream'
  try {
    return await fetchFn(`${goc}/admin${y.duong}`, {
      method: y.method.toUpperCase(),
      headers,
      body: y.body,
      // SSE: theo tín hiệu huỷ của yêu cầu gốc — client đóng tab thì dừng luồng thượng nguồn
      // thay vì rò rỉ kết nối. Không timeout 30s vì stream sống lâu hơn giá trị đó có chủ đích.
      signal: y.sse ? y.signal : AbortSignal.timeout(30_000),
    })
  } catch {
    return Response.json({ detail: 'Không nối được tới KLAW.' }, { status: 502 })
  }
}
