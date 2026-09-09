import React from 'react'

/** Bộ biểu tượng nét 1.75, vẽ tay cho đúng một nét — không dùng emoji hay glyph Unicode. */
// width/height 1em là cỡ nội tại: trong nút hay flex không có luật CSS riêng, svg chỉ có viewBox sẽ co về 0.
const NET = { width: '1em', height: '1em', fill: 'none', stroke: 'currentColor', strokeWidth: 1.75, strokeLinecap: 'round', strokeLinejoin: 'round' } as const

export function BtTim() {
  return <svg viewBox="0 0 24 24" {...NET} aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></svg>
}
export function BtTongQuan() {
  return <svg viewBox="0 0 24 24" {...NET} aria-hidden="true"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></svg>
}
export function BtYeuCau() {
  return <svg viewBox="0 0 24 24" {...NET} aria-hidden="true"><path d="M12 20V7" /><path d="m6.5 12.5 5.5-5.5 5.5 5.5" /><path d="M4 4h16" /></svg>
}
export function BtTaiKhoan() {
  return <svg viewBox="0 0 24 24" {...NET} aria-hidden="true"><circle cx="12" cy="8.5" r="3.5" /><path d="M5 19.5c1.2-3.5 3.6-5 7-5s5.8 1.5 7 5" /></svg>
}
export function BtNhatKy() {
  return <svg viewBox="0 0 24 24" {...NET} aria-hidden="true"><path d="M6 4.5h9l3.5 3.5v11.5H6z" /><path d="M15 4.5V8h3.5" /><path d="M9 12.5h6M9 16h6" /></svg>
}
export function BtMuiTenTrai() {
  return <svg viewBox="0 0 24 24" {...NET} aria-hidden="true"><path d="M19 12H5" /><path d="m11 18-6-6 6-6" /></svg>
}
export function BtTaiXuong() {
  return <svg viewBox="0 0 24 24" {...NET} aria-hidden="true"><path d="M12 4v11" /><path d="m7 10.5 5 5 5-5" /><path d="M4.5 19.5h15" /></svg>
}
