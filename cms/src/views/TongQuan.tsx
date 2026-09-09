import type { AdminViewServerProps } from 'payload'
import React from 'react'
import { PillTrucTuyen } from '../components/PillTrucTuyen'
import { KhungQuanTri } from './khung'
import { TongQuanClient } from './TongQuanClient'
export function TongQuan(props: AdminViewServerProps) {
  return (
    <KhungQuanTri props={props} tieuDe="Tổng quan" moTa="Ai đang mở KLAW, việc gì đang chờ, và các con số của hôm nay." hanhDong={<PillTrucTuyen />} khongBocTemplate>
      <TongQuanClient />
    </KhungQuanTri>
  )
}
