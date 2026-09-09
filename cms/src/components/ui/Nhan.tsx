import React from 'react'

export type MauNhan = 'trung-tinh' | 'muc' | 'xanh' | 'do' | 'vang' | 'dong-thau'

/** Pill trạng thái. Màu mang nghĩa, không trang trí: xanh = còn/đang, đỏ = khoá/từ chối, vàng = chờ. */
export function Nhan({ mau = 'trung-tinh', children }: { mau?: MauNhan; children: React.ReactNode }) {
  return <span className={`klaw-nhan${mau === 'trung-tinh' ? '' : ` klaw-nhan--${mau}`}`}>{children}</span>
}

export const mauTrangThaiYeuCau = (t: string): MauNhan => (t === 'da_duyet' ? 'xanh' : t === 'tu_choi' ? 'do' : 'vang')
