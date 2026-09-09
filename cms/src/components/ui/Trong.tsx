import React from 'react'

/** Trạng thái rỗng dạy cách dùng: nói vì sao trống và làm gì tiếp. */
export function Trong({ tieuDe, goiY }: { tieuDe: string; goiY?: string }) {
  return (
    <div className="klaw-trong" role="status">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <rect x="3.5" y="5.5" width="17" height="13" rx="2.5" />
        <path d="M3.5 10.5h17" />
        <path d="M8 14.5h4" />
      </svg>
      <strong>{tieuDe}</strong>
      {goiY && <p>{goiY}</p>}
    </div>
  )
}
