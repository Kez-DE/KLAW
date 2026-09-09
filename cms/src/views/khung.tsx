import type { AdminViewServerProps } from 'payload'
import { DefaultTemplate } from '@payloadcms/next/templates'
import { Gutter } from '@payloadcms/ui'
import React from 'react'

/** Mọi view tuỳ biến của Payload là CÔNG KHAI mặc định — khung này là chỗ duy nhất kiểm phiên. */
export function KhungQuanTri({
  props,
  tieuDe,
  moTa,
  hanhDong,
  children,
  khongBocTemplate,
}: {
  props: AdminViewServerProps
  tieuDe: string
  /** Một câu dưới tiêu đề: view này để làm gì. */
  moTa?: string
  /** Cụm bên phải tiêu đề (pill trực tuyến, nút xuất…). */
  hanhDong?: React.ReactNode
  children: React.ReactNode
  /** Route dashboard (`/admin`) đã được Payload tự bọc trong MỘT DefaultTemplate của
   *  riêng nó (kèm viewActions) trước khi gọi component đăng ký — mọi view tuỳ biến khác
   *  (có `path` riêng) thì không. Bọc thêm một DefaultTemplate nữa ở đây cho dashboard sẽ
   *  ra hai khung, hai chuông, hai EventSource. `TongQuan` truyền `true` để bỏ qua. */
  khongBocTemplate?: boolean
}) {
  const { initPageResult, params, searchParams } = props
  if (!initPageResult.req.user) return <Gutter><p>Bạn cần đăng nhập vào trang quản trị.</p></Gutter>
  const than = (
    <Gutter>
      <div className="klaw-dau-trang">
        <div>
          <h1>{tieuDe}</h1>
          {moTa && <p className="klaw-dau-trang__mo-ta">{moTa}</p>}
        </div>
        {hanhDong && <div className="klaw-dau-trang__hanh-dong">{hanhDong}</div>}
      </div>
      {children}
    </Gutter>
  )
  if (khongBocTemplate) return than
  return (
    <DefaultTemplate
      i18n={initPageResult.req.i18n} locale={initPageResult.locale} params={params} payload={initPageResult.req.payload}
      permissions={initPageResult.permissions} searchParams={searchParams} user={initPageResult.req.user} visibleEntities={initPageResult.visibleEntities}
      // DefaultTemplate không tự đọc payload.config.admin.components.actions — nó chỉ vẽ
      // những gì `viewActions` truyền vào, và Payload đã tính sẵn giá trị đó cho ta trên
      // `props`. Thiếu dòng này, chuông thông báo chỉ hiện trên `/admin`.
      viewActions={props.viewActions}
    >
      {than}
    </DefaultTemplate>
  )
}
