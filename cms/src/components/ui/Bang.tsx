'use client'
import React from 'react'

export function Bang({
  cot,
  hang,
  rong,
  onChonHang,
}: {
  cot: { khoa: string; nhan: string }[]
  hang: Record<string, React.ReactNode>[]
  rong: string
  onChonHang?: (i: number) => void
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
          hang.map((h, i) => (
            <tr
              key={i}
              onClick={onChonHang ? () => onChonHang(i) : undefined}
              onKeyDown={onChonHang ? (e) => { if (e.key === 'Enter') onChonHang(i) } : undefined}
              tabIndex={onChonHang ? 0 : undefined}
              style={onChonHang ? { cursor: 'pointer' } : undefined}
            >
              {cot.map((c) => (
                <td key={c.khoa}>{h[c.khoa]}</td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  )
}
