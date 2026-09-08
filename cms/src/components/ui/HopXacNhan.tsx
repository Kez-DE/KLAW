'use client'
import { Button } from '@payloadcms/ui'
import React, { useEffect, useId, useRef, useState } from 'react'

export function HopXacNhan({
  mo,
  tieuDe,
  moTa,
  nhanXacNhan,
  canLyDo,
  onXacNhan,
  onDong,
}: {
  mo: boolean
  tieuDe: string
  moTa: string
  nhanXacNhan: string
  canLyDo?: boolean
  onXacNhan: (lyDo?: string) => void
  onDong: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const [lyDo, setLyDo] = useState('')
  const tieuDeId = useId()
  const moTaId = useId()

  // Chỉ gọi phương thức DOM ở đây — KHÔNG setState trong effect (react-hooks/set-state-in-effect).
  // Việc trả `lyDo` về rỗng dời sang lúc đóng/xác nhận, xem `dong`/`xacNhan` bên dưới.
  useEffect(() => {
    if (mo) ref.current?.showModal()
    else ref.current?.close()
  }, [mo])

  const dong = () => { setLyDo(''); onDong() }
  const xacNhan = () => { const gt = canLyDo ? lyDo : undefined; setLyDo(''); onXacNhan(gt) }
  const thieuLyDo = Boolean(canLyDo) && lyDo.trim().length === 0

  return (
    <dialog ref={ref} onCancel={dong} aria-labelledby={tieuDeId} aria-describedby={moTaId}>
      <h2 id={tieuDeId}>{tieuDe}</h2>
      <p id={moTaId}>{moTa}</p>
      {canLyDo && (
        <label>
          Lý do
          <textarea
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value.slice(0, 500))}
            minLength={1}
            maxLength={500}
            required
          />
        </label>
      )}
      <Button buttonStyle="secondary" onClick={dong}>Huỷ</Button>
      <Button disabled={thieuLyDo} onClick={xacNhan}>{nhanXacNhan}</Button>
    </dialog>
  )
}
