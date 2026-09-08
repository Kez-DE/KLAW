import type { AdminViewServerProps } from 'payload'
import React from 'react'
import { KhungQuanTri } from './khung'
import { NhatKyClient } from './NhatKyClient'
export function NhatKy(props: AdminViewServerProps) {
  return <KhungQuanTri props={props} tieuDe="Nhật ký"><NhatKyClient /></KhungQuanTri>
}
