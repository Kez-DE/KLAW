import type { AdminViewServerProps } from 'payload'
import React from 'react'
import type { Admin } from '../access/vaiTro'
import { KhungQuanTri } from './khung'
import { YeuCauClient } from './YeuCauClient'
export function YeuCau(props: AdminViewServerProps) {
  const vaiTro = (props.initPageResult.req.user as Admin | null)?.vai_tro ?? 'doc'
  return (
    <KhungQuanTri props={props} tieuDe="Yêu cầu nâng gói" moTa="Duyệt để đổi gói ngay; từ chối thì ghi lý do và người dùng sẽ thấy lý do đó.">
      <YeuCauClient vaiTro={vaiTro} />
    </KhungQuanTri>
  )
}
