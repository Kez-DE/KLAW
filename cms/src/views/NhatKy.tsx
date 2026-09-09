import type { AdminViewServerProps } from 'payload'
import React from 'react'
import { KhungQuanTri } from './khung'
import { NhatKyClient } from './NhatKyClient'
export function NhatKy(props: AdminViewServerProps) {
  return (
    <KhungQuanTri props={props} tieuDe="Nhật ký" moTa="Mọi thao tác admin trên KLAW và mọi lần đăng nhập vào trang này, giữ vô thời hạn.">
      <NhatKyClient />
    </KhungQuanTri>
  )
}
