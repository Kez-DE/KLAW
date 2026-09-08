import type { AdminViewServerProps } from 'payload'
import React from 'react'
import type { Admin } from '../access/vaiTro'
import { KhungQuanTri } from './khung'
import { TaiKhoanClient } from './TaiKhoanClient'
export function TaiKhoan(props: AdminViewServerProps) {
  const vaiTro = (props.initPageResult.req.user as Admin | null)?.vai_tro ?? 'doc'
  return <KhungQuanTri props={props} tieuDe="Tài khoản"><TaiKhoanClient vaiTro={vaiTro} /></KhungQuanTri>
}
