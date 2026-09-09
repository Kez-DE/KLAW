'use client'
import { Button } from '@payloadcms/ui'
import React from 'react'

/** Hàng phân trang dưới bảng: Trước/Sau và "x–y trong tổng" (tabular). */
export function PhanTrang({
  tuDong,
  denDong,
  tong,
  coTruoc,
  coSau,
  onTruoc,
  onSau,
  nhanTong,
}: {
  tuDong: number
  denDong: number
  tong?: number
  coTruoc: boolean
  coSau: boolean
  onTruoc: () => void
  onSau: () => void
  nhanTong?: string
}) {
  return (
    <div className="klaw-phan-trang">
      <span>
        {tong === undefined ? nhanTong : tong === 0 ? 'Không có dòng nào' : `${tuDong}–${denDong} trong ${tong.toLocaleString('vi-VN')}`}
      </span>
      <div className="klaw-phan-trang__nut">
        <Button buttonStyle="secondary" size="small" disabled={!coTruoc} onClick={onTruoc}>Trước</Button>
        <Button buttonStyle="secondary" size="small" disabled={!coSau} onClick={onSau}>Sau</Button>
      </div>
    </div>
  )
}
