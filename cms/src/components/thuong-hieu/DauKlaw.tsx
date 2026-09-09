import React from 'react'

/** Dấu KLAW: ô vuông bo góc mực sapphire, chữ K, chấm đồng thau — vẽ bằng SVG, không tải ảnh.
 *  Không truyền kichCo thì co theo hộp chứa. */
function Dau({ kichCo }: { kichCo?: number }) {
  const cs = kichCo ? { width: kichCo, height: kichCo } : { width: '100%', height: '100%' }
  return (
    <svg viewBox="0 0 40 40" style={{ display: 'block', ...cs }} aria-hidden="true" focusable="false">
      <rect width="40" height="40" rx="10" fill="#20436e" />
      <path d="M13 10.5v19M13 20l12-9.5M14.5 19.5 26 29.5" fill="none" stroke="#ffffff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="30" cy="10.5" r="3" fill="#dab157" />
    </svg>
  )
}

/** Logo trên trang đăng nhập (graphics.Logo). */
export function DauKlaw() {
  return (
    <div className="klaw-logo" role="img" aria-label="KLAW quản trị">
      <Dau kichCo={44} />
      <div className="klaw-logo__chu">
        <strong>KLAW</strong>
        <span>quản trị</span>
      </div>
    </div>
  )
}

/** Khoá hiệu ở header (graphics.Icon): dấu 24 px + chữ KLAW. Payload bọc nó trong `.step-nav__home`
 *  16–18 px, overflow ẩn — custom.scss nới hộp đó ra để chữ không bị cắt. */
export function DauKlawNho() {
  return (
    <span className="klaw-logo klaw-logo--nho" role="img" aria-label="KLAW quản trị">
      <Dau kichCo={24} />
      <strong>KLAW</strong>
    </span>
  )
}
