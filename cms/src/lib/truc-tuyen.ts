'use client'
import { useEffect, useState } from 'react'
import { goiQuanTri, type KetQua } from './goi-klaw'

export type NguoiTrucTuyen = { sub: string; email: string | null; tu_luc: string }
export type TrucTuyen = { so: number; items: NguoiTrucTuyen[] }

export const CHU_KY_MS = 15_000

// Một bộ hỏi dùng chung cho cả trang: pill ở đầu trang, thẻ ở Tổng quan và cột trạng thái
// cùng đọc một kết quả, nên mỗi tab chỉ tốn một lượt gọi KLAW mỗi 15 giây dù có bao nhiêu
// nơi hiển thị. Lá chắn IP của KLAW là 60 lượt/60 giây cho cả CMS — nhiều tab, nhiều thành
// phần cùng hỏi riêng lẻ đã từng vượt mức đó.
type NgheKetQua = (kq: KetQua<TrucTuyen>) => void
let ketQuaCuoi: KetQua<TrucTuyen> | null = null
let ketQuaTot: KetQua<TrucTuyen> | null = null
const nguoiNghe = new Set<NgheKetQua>()
let henGio: number | null = null
let theHe = 0

const phat = (kq: KetQua<TrucTuyen>) => {
  // Lỗi tạm (429, mất mạng) không được xoá con số đang đúng — giữ lần đọc tốt gần nhất.
  ketQuaCuoi = kq.ok ? kq : (ketQuaTot ?? kq)
  if (kq.ok) ketQuaTot = kq
  for (const n of nguoiNghe) n(ketQuaCuoi)
}
const tai = () => {
  const t = ++theHe
  void goiQuanTri<TrucTuyen>('/truc-tuyen').then((kq) => { if (t === theHe) phat(kq) })
}
const khiHien = () => { if (document.visibilityState === 'visible') tai() }
const batDau = () => {
  if (henGio !== null) return
  tai()
  henGio = window.setInterval(() => { if (document.visibilityState === 'visible') tai() }, CHU_KY_MS)
  document.addEventListener('visibilitychange', khiHien)
}
const dungLai = () => {
  if (henGio === null) return
  window.clearInterval(henGio)
  henGio = null
  document.removeEventListener('visibilitychange', khiHien)
}

/** Ai đang mở KLAW — đọc từ bộ hỏi dùng chung; nguồn là sổ luồng SSE trong KLAW. */
export function useTrucTuyen(): KetQua<TrucTuyen> | null {
  const [kq, setKq] = useState<KetQua<TrucTuyen> | null>(ketQuaCuoi)
  useEffect(() => {
    // setState chỉ chạy trong callback của bộ hỏi — không đồng bộ trong effect (react-hooks/set-state-in-effect).
    const nghe: NgheKetQua = (r) => setKq(r)
    nguoiNghe.add(nghe)
    batDau()
    return () => {
      nguoiNghe.delete(nghe)
      if (nguoiNghe.size === 0) dungLai()
    }
  }, [])
  return kq
}

export const tapSubTrucTuyen = (kq: KetQua<TrucTuyen> | null): Set<string> => new Set(kq?.ok ? kq.data.items.map((x) => x.sub) : [])
