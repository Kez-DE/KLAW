'use client'
import { useAuth } from '@payloadcms/ui'
import React from 'react'
import { chuDau } from '../../lib/hien-thi'

/** Avatar góc phải header (admin.avatar): chữ đầu email admin trên nền mực — thay gravatar và
 *  đồ hoạ mặc định của Payload, vốn là vật thể đen duy nhất trong bảng màu trắng + sapphire. */
export function AvatarKlaw() {
  const { user } = useAuth()
  return (
    <span className="klaw-avatar klaw-avatar--muc" aria-hidden="true">
      {chuDau(user?.email ?? null)}
    </span>
  )
}
