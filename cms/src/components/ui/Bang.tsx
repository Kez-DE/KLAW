'use client'
import React from 'react'
import { Trong } from './Trong'

/** Bảng dữ liệu trong thẻ: đầu cột dính, hàng bấm được có vai trò nút và tiêu điểm đồng thau. */
export function Bang({
  cot,
  hang,
  rong,
  goiYRong,
  onChonHang,
  nhanHang,
}: {
  cot: { khoa: string; nhan: string; rong?: string | number; boc?: boolean; phu?: boolean }[]
  hang: Record<string, React.ReactNode>[]
  rong: string
  /** Câu gợi ý dưới tiêu đề trạng thái rỗng — nói làm gì tiếp. */
  goiYRong?: string
  onChonHang?: (i: number) => void
  /** Nhãn a11y cho hàng bấm được; mặc định lấy chữ của ô đầu tiên nếu là string. */
  nhanHang?: (i: number) => string
}) {
  // boc: cột chữ dài được xuống dòng; phu: cột phụ ẩn dưới 60rem (chi tiết xem ở trang tài khoản).
  const lop = (c: { boc?: boolean; phu?: boolean }) =>
    [c.boc && 'klaw-bang__o--boc', c.phu && 'klaw-bang__o--phu'].filter(Boolean).join(' ') || undefined
  return (
    <div className="klaw-bang-khung">
      <table className="klaw-bang">
        <thead>
          <tr>
            {cot.map((c) => (
              <th key={c.khoa} className={lop(c)} style={c.rong ? { width: c.rong } : undefined}>{c.nhan}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {hang.length === 0 ? (
            <tr>
              <td colSpan={cot.length} className="klaw-bang__rong">
                <Trong tieuDe={rong} goiY={goiYRong} />
              </td>
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
                >
                  {cot.map((c) => (
                    <td key={c.khoa} className={lop(c)}>{h[c.khoa]}</td>
                  ))}
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    </div>
  )
}
