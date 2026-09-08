// cms/src/hooks/nhatKyCms.ts
import type { Config, Payload, PayloadRequest } from 'payload'

type AfterErrorHook = NonNullable<NonNullable<Config['hooks']>['afterError']>[number]

export const ipCua = (req: Pick<PayloadRequest, 'headers'>): string | null => {
  const xff = req.headers?.get?.('x-forwarded-for') ?? ''
  const phan = xff.split(',').map((s) => s.trim()).filter(Boolean)
  return phan.length > 0 ? phan[phan.length - 1] : null
}

/** Ghi một dòng; KHÔNG ném — một dòng nhật ký hỏng không được làm hỏng thao tác chính. */
export const ghiNhatKyCms = async (
  payload: Payload,
  d: { hanh_dong: string; boi: string; ip?: string | null; chi_tiet?: Record<string, unknown> },
): Promise<void> => {
  try {
    await payload.create({
      collection: 'nhat_ky_cms',
      data: { hanh_dong: d.hanh_dong, boi: d.boi, ip: d.ip ?? null, chi_tiet: d.chi_tiet ?? {} },
      overrideAccess: true,
    })
  } catch (error) {
    payload.logger.warn({ err: error }, 'nhat_ky_cms: không ghi được')
  }
}

/** `afterError` cấp config: lỗi 401/403/423 trên `/api/admins/login` = đăng nhập sai, tài
 *  khoản bị vô hiệu (403 — `Admins.ts` `beforeLogin` sau khi mật khẩu đã đúng, không phải
 *  oracle dò tài khoản), hoặc bị khoá (spec §6.3). Chuỗi thất bại liên tiếp là tín hiệu dò
 *  mật khẩu — thông lệ audit log của OpenAI. */
export const ghiDangNhapThatBai: AfterErrorHook = async ({ error, req }) => {
  const url = (req as { url?: string }).url ?? ''
  const status = (error as { status?: number }).status
  if (!url.includes('/api/admins/login') || (status !== 401 && status !== 403 && status !== 423)) return
  const data = (req as { data?: { email?: unknown } }).data
  const email = typeof data?.email === 'string' ? data.email : '(không rõ)'
  await ghiNhatKyCms(req.payload, { hanh_dong: 'dang_nhap_that_bai', boi: email, ip: ipCua(req), chi_tiet: { status } })
}
