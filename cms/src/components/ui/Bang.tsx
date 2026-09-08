'use client'
import React from 'react'

export function Bang({
  cot,
  hang,
  rong,
  onChonHang,
  nhanHang,
}: {
  cot: { khoa: string; nhan: string }[]
  hang: Record<string, React.ReactNode>[]
  rong: string
  onChonHang?: (i: number) => void
  /** Nhãn a11y cho hàng bấm được; mặc định lấy chữ của ô đầu tiên nếu là string. */
  nhanHang?: (i: number) => string
}) {
  return (
    <table className="table">
      <thead>
        <tr>
          {cot.map((c) => (
            <th key={c.khoa}>{c.nhan}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {hang.length === 0 ? (
          <tr>
            <td colSpan={cot.length}>{rong}</td>
          </tr>
        ) : (
          hang.map((h, i) => {
            const ganDau = cot[0] ? h[cot[0].khoa] : undefined
            const nhan = onChonHang ? (nhanHang?.(i) ?? (typeof ganDau === 'string' ? ganDau : undefined)) : undefined
            return (
              <tr
                key={i}
                role={onChonHang ? 'button' : undefined}
                aria-label={nhan}
                onClick={onChonHang ? () => onChonHang(i) : undefined}
                onKeyDown={onChonHang ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onChonHang(i) } } : undefined}
                tabIndex={onChonHang ? 0 : undefined}
                style={onChonHang ? { cursor: 'pointer' } : undefined}
              >
                {cot.map((c) => (
                  <td key={c.khoa}>{h[c.khoa]}</td>
                ))}
              </tr>
            )
          })
        )}
      </tbody>
    </table>
  )
}
