'use client'
import { Button } from '@payloadcms/ui'
import React from 'react'

export function ThongBaoLoi({ message, onThuLai }: { message: string; onThuLai?: () => void }) {
  return (
    <div role="alert">
      <p>{message}</p>
      {onThuLai && <Button buttonStyle="secondary" onClick={onThuLai}>Thử lại</Button>}
    </div>
  )
}
