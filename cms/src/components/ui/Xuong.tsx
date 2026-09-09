import React from 'react'

/** Khung xương khi đang tải — thay cho vòng quay giữa nội dung. */
export function Xuong({ dong = 4 }: { dong?: number }) {
  return (
    <div className="klaw-xuong" aria-busy="true" aria-label="Đang tải">
      {Array.from({ length: dong }, (_, i) => <span key={i} style={{ width: `${88 - (i % 3) * 14}%` }} />)}
    </div>
  )
}
