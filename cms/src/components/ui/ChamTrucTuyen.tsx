import React from 'react'

/** Chấm trực tuyến: xanh thở chậm khi đang mở luồng thông báo, xám khi không. Chữ đi kèm để không dựa vào màu. */
export function ChamTrucTuyen({ tren, gon }: { tren: boolean; gon?: boolean }) {
  const chu = tren ? 'Đang trực tuyến' : 'Ngoại tuyến'
  return (
    <span className={`klaw-cham${tren ? ' klaw-cham--tren' : ''}`} role="status" aria-label={chu}>
      <span className="klaw-cham__dot" aria-hidden="true" />
      {!gon && chu}
    </span>
  )
}
