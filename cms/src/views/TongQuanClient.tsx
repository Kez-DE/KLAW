'use client'
import Link from 'next/link'
import React, { useCallback, useEffect, useState } from 'react'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'

type TongQuan = { tong_tai_khoan: number; dang_ca_nhan: number; cho_duyet: number; het_han_7_ngay: number; moi_7_ngay: number; dang_khoa: number; hoi_dap_hom_nay: number }
const O: [keyof TongQuan, string, string?][] = [
  ['tong_tai_khoan', 'Tài khoản'], ['dang_ca_nhan', 'Đang dùng gói Cá nhân'], ['cho_duyet', 'Yêu cầu chờ duyệt', '/admin/yeu-cau?trang_thai=cho_duyet'],
  ['het_han_7_ngay', 'Hết hạn trong 7 ngày', '/admin/tai-khoan?loc=het_han'], ['moi_7_ngay', 'Tài khoản mới 7 ngày'], ['dang_khoa', 'Đang khoá'], ['hoi_dap_hom_nay', 'Lượt hỏi hôm nay'],
]
export function TongQuanClient() {
  const [kq, setKq] = useState<KetQua<TongQuan> | null>(null)
  // napLai không setState đồng bộ (chỉ trong .then) nên dùng được thẳng trong effect
  // (react-hooks/set-state-in-effect); `tai` (nút Thử lại) đặt lại về null trước khi gọi lại.
  const napLai = useCallback(() => { void goiQuanTri<TongQuan>('/tong-quan').then(setKq) }, [])
  useEffect(() => { napLai() }, [napLai])
  const tai = useCallback(() => { setKq(null); napLai() }, [napLai])
  if (kq === null) return <p>Đang tải…</p>
  if (!kq.ok) return <ThongBaoLoi message={kq.message} onThuLai={tai} />
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
      {O.map(([k, nhan, href]) => {
        const so = <strong style={{ fontSize: 32 }}>{kq.data[k].toLocaleString('vi-VN')}</strong>
        return <div key={k} className="card" style={{ padding: 16 }}>{href ? <Link href={href}>{so}</Link> : so}<div>{nhan}</div></div>
      })}
    </div>
  )
}
