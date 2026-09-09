'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import React from 'react'
import { BtNhatKy, BtTaiKhoan, BtTongQuan, BtYeuCau } from './ui/BieuTuong'

const MUC = [
  ['/admin', 'Tổng quan', BtTongQuan],
  ['/admin/yeu-cau', 'Yêu cầu nâng gói', BtYeuCau],
  ['/admin/tai-khoan', 'Tài khoản', BtTaiKhoan],
  ['/admin/nhat-ky', 'Nhật ký', BtNhatKy],
] as const

export function DieuHuong() {
  const path = usePathname()
  return (
    <nav aria-label="Quản lý tài khoản" className="klaw-dieu-huong">
      {MUC.map(([href, nhan, Bt]) => (
        <Link key={href} href={href} className="nav__link" aria-current={path === href ? 'page' : undefined}>
          <Bt />
          {nhan}
        </Link>
      ))}
    </nav>
  )
}
