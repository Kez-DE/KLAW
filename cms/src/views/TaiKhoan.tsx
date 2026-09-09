import type { AdminViewServerProps } from 'payload'
import React from 'react'
import type { Admin } from '../access/vaiTro'
import { PillTrucTuyen } from '../components/PillTrucTuyen'
import { KhungQuanTri } from './khung'
import { TaiKhoanClient } from './TaiKhoanClient'
export function TaiKhoan(props: AdminViewServerProps) {
  const vaiTro = (props.initPageResult.req.user as Admin | null)?.vai_tro ?? 'doc'
  return (
    <KhungQuanTri props={props} tieuDe="Tài khoản" moTa="Tìm theo email, xem gói và trạng thái, đặt gói tay, khoá hoặc mở khoá — mỗi việc kèm một lý do." hanhDong={<PillTrucTuyen />}>
      <TaiKhoanClient vaiTro={vaiTro} />
    </KhungQuanTri>
  )
}
