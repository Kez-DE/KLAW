import type { AdminViewServerProps } from 'payload'
import React from 'react'
import { KhungQuanTri } from './khung'
import { TongQuanClient } from './TongQuanClient'
export function TongQuan(props: AdminViewServerProps) {
  return <KhungQuanTri props={props} tieuDe="Tổng quan"><TongQuanClient /></KhungQuanTri>
}
