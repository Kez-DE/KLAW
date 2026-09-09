'use client'
import React from 'react'
import { useTrucTuyen } from '../lib/truc-tuyen'
import { Nhan } from './ui/Nhan'

/** Pill "Đang trực tuyến · N" cạnh tiêu đề trang; tự làm mới theo chu kỳ CHU_KY_MS của sổ luồng. */
export function PillTrucTuyen() {
  const tt = useTrucTuyen()
  if (tt === null) return <Nhan>Đang trực tuyến · …</Nhan>
  if (!tt.ok) return <Nhan>Trực tuyến: chưa đọc được</Nhan>
  return (
    <Nhan mau={tt.data.so > 0 ? 'xanh' : 'trung-tinh'}>
      <span className={`klaw-cham${tt.data.so > 0 ? ' klaw-cham--tren' : ''}`} aria-hidden="true"><span className="klaw-cham__dot" /></span>
      Đang trực tuyến · {tt.data.so.toLocaleString('vi-VN')}
    </Nhan>
  )
}
