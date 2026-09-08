import type { AdminViewServerProps } from 'payload'
import { DefaultTemplate } from '@payloadcms/next/templates'
import { Gutter } from '@payloadcms/ui'
import React from 'react'

/** Mọi view tuỳ biến của Payload là CÔNG KHAI mặc định — khung này là chỗ duy nhất kiểm phiên. */
export function KhungQuanTri({ props, tieuDe, children }: { props: AdminViewServerProps; tieuDe: string; children: React.ReactNode }) {
  const { initPageResult, params, searchParams } = props
  if (!initPageResult.req.user) return <Gutter><p>Bạn cần đăng nhập vào trang quản trị.</p></Gutter>
  return (
    <DefaultTemplate
      i18n={initPageResult.req.i18n} locale={initPageResult.locale} params={params} payload={initPageResult.req.payload}
      permissions={initPageResult.permissions} searchParams={searchParams} user={initPageResult.req.user} visibleEntities={initPageResult.visibleEntities}
      // DefaultTemplate không tự đọc payload.config.admin.components.actions — nó chỉ vẽ
      // những gì `viewActions` truyền vào, và Payload đã tính sẵn giá trị đó cho ta trên
      // `props`. Thiếu dòng này, chuông thông báo (đăng ký ở payload.config.ts) chỉ hiện
      // trên `/admin` (route dashboard do Payload tự bọc thêm một template ở NGOÀI khung
      // này) và biến mất trên mọi view tuỳ biến khác (yêu cầu, tài khoản, nhật ký) — vì
      // các view đó chỉ có đúng khung DefaultTemplate do KhungQuanTri dựng ở đây.
      viewActions={props.viewActions}
    >
      <Gutter><h1 style={{ marginBottom: 24 }}>{tieuDe}</h1>{children}</Gutter>
    </DefaultTemplate>
  )
}
