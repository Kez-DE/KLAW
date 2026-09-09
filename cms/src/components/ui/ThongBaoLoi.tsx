'use client'
import { Button } from '@payloadcms/ui'
import React from 'react'

/** Lỗi nêu đúng câu của KLAW/proxy và một nút thử lại khi có đường phục hồi. */
export function ThongBaoLoi({ message, onThuLai }: { message: string; onThuLai?: () => void }) {
  return (
    <div role="alert" className="klaw-loi">
      <p>{message}</p>
      {onThuLai && <Button buttonStyle="secondary" size="small" onClick={onThuLai}>Thử lại</Button>}
    </div>
  )
}
