import React from 'react'

/** Thẻ nội dung: viền mảnh, bo 12 px, bóng mềm. Không lồng thẻ trong thẻ. */
export function The({
  tieuDe,
  moTa,
  hanhDong,
  sat,
  chan,
  children,
  className,
}: {
  tieuDe?: React.ReactNode
  moTa?: React.ReactNode
  hanhDong?: React.ReactNode
  /** Thân không đệm — dùng cho bảng và danh sách tự đệm. */
  sat?: boolean
  chan?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={`klaw-the${className ? ` ${className}` : ''}`}>
      {(tieuDe || hanhDong) && (
        <header className="klaw-the__dau">
          <div>
            {tieuDe && <h2>{tieuDe}</h2>}
            {moTa && <p>{moTa}</p>}
          </div>
          {hanhDong && <div className="klaw-the__hanh-dong">{hanhDong}</div>}
        </header>
      )}
      <div className={`klaw-the__than${sat ? ' klaw-the__than--sat' : ''}`}>{children}</div>
      {chan && <footer className="klaw-the__chan">{chan}</footer>}
    </section>
  )
}
