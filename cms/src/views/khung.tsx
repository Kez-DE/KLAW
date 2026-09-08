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
    >
      <Gutter><h1 style={{ marginBottom: 24 }}>{tieuDe}</h1>{children}</Gutter>
    </DefaultTemplate>
  )
}
