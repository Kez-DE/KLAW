'use client'
export type KetQua<T> = { ok: true; data: T } | { ok: false; status: number; message: string }

export async function goiQuanTri<T>(duong: string, tuyChon: { method?: 'GET' | 'POST' | 'PATCH'; body?: unknown } = {}): Promise<KetQua<T>> {
  let res: Response
  try {
    res = await fetch(`/api/klaw${duong}`, {
      method: tuyChon.method ?? 'GET',
      credentials: 'same-origin',
      headers: tuyChon.body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: tuyChon.body === undefined ? undefined : JSON.stringify(tuyChon.body),
    })
  } catch {
    return { ok: false, status: 0, message: 'Không nối được tới trang quản trị. Kiểm tra mạng rồi thử lại.' }
  }
  if (!res.ok) {
    let message = `Lỗi ${res.status}.`
    try { const j = await res.json(); if (typeof j.detail === 'string') message = j.detail } catch { /* thân không phải JSON */ }
    return { ok: false, status: res.status, message }
  }
  return { ok: true, data: (await res.json()) as T }
}
