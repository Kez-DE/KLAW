'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import React from 'react'

const MUC = [['/admin', 'Tổng quan'], ['/admin/yeu-cau', 'Yêu cầu nâng gói'], ['/admin/tai-khoan', 'Tài khoản'], ['/admin/nhat-ky', 'Nhật ký']] as const
export function DieuHuong() {
  const path = usePathname()
  return (
    <nav aria-label="Quản lý tài khoản" style={{ display: 'grid', gap: 4, padding: '8px 0' }}>
      {MUC.map(([href, nhan]) => (
        <Link key={href} href={href} className="nav__link" aria-current={path === href ? 'page' : undefined} style={{ fontWeight: path === href ? 700 : 400 }}>{nhan}</Link>
      ))}
    </nav>
  )
}
