// cms/payload.config.ts
import path from 'path'
import { fileURLToPath } from 'url'
import { buildConfig } from 'payload'
import { postgresAdapter } from '@payloadcms/db-postgres'
import { vi } from '@payloadcms/translations/languages/vi'

import { Admins } from './src/collections/Admins'
import { NhatKyCms } from './src/collections/NhatKyCms'
import { klawEndpoints } from './src/endpoints/klaw'
import { exposeErrorReason } from './src/hooks/exposeErrorReason'
import { ghiDangNhapThatBai } from './src/hooks/nhatKyCms'

const dirname = path.dirname(fileURLToPath(import.meta.url))

// Gốc công khai: Railway bơm RAILWAY_PUBLIC_DOMAIN; PAYLOAD_PUBLIC_SERVER_URL ghi đè cho
// host khác. Local để trống → URL tương đối. Dùng `||` (không phải `??`) vì
// PAYLOAD_PUBLIC_SERVER_URL='' (chuỗi rỗng, giá trị mặc định trong .env.example) vẫn phải
// rơi xuống RAILWAY_PUBLIC_DOMAIN — production BẮT BUỘC đặt một trong hai, nếu không
// origins rỗng ở production khiến `csrf: []`, vô hiệu hoá bảo vệ CSRF.
const serverURL =
  process.env.PAYLOAD_PUBLIC_SERVER_URL ||
  (process.env.RAILWAY_PUBLIC_DOMAIN ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}` : '')
const laProd = process.env.NODE_ENV === 'production'
const origins = laProd
  ? [serverURL].filter(Boolean)
  : ['http://localhost:3001', 'http://127.0.0.1:3001']

export default buildConfig({
  admin: {
    user: 'admins',
    meta: { titleSuffix: '— KLAW quản trị' },
    avatar: { Component: '@/components/thuong-hieu/AvatarKlaw#AvatarKlaw' },
    components: {
      views: {
        dashboard: { Component: '@/views/TongQuan#TongQuan' },
        yeuCau: { Component: '@/views/YeuCau#YeuCau', path: '/yeu-cau', exact: true },
        taiKhoan: { Component: '@/views/TaiKhoan#TaiKhoan', path: '/tai-khoan', exact: true },
        nhatKy: { Component: '@/views/NhatKy#NhatKy', path: '/nhat-ky', exact: true },
      },
      afterNavLinks: ['@/components/DieuHuong#DieuHuong'],
      actions: ['@/components/ChuongThongBao#ChuongThongBao'],
      graphics: { Logo: '@/components/thuong-hieu/DauKlaw#DauKlaw', Icon: '@/components/thuong-hieu/DauKlaw#DauKlawNho' },
      beforeLogin: ['@/components/thuong-hieu/LoiChaoDangNhap#LoiChaoDangNhap'],
    },
  },
  // Chỉ tiếng Việt: có `en` trong danh sách thì Payload chọn theo Accept-Language của trình duyệt
  // (thường en-US) và vỏ ngoài (đăng nhập, nhóm nav, ô ngày) ra tiếng Anh dù fallback là vi.
  i18n: { supportedLanguages: { vi }, fallbackLanguage: 'vi' },
  serverURL,
  cors: origins,
  // Dev để RỖNG: allowlist csrf làm rớt phiên trên LAN plain-HTTP (kinh nghiệm dự án
  // tham chiếu). Production phải có allowlist.
  csrf: laProd ? origins : [],
  collections: [Admins, NhatKyCms],
  endpoints: klawEndpoints,
  graphQL: { disable: true },
  hooks: { afterError: [exposeErrorReason, ghiDangNhapThatBai] },
  // Database RIÊNG `klaw_cms` (spec §4.2). KHÔNG cấu hình schema Postgres tùy biến.
  // KHÔNG bao giờ trỏ vào database `klaw` — tests/config.spec.ts khẳng định.
  db: postgresAdapter({
    pool: { connectionString: process.env.DATABASE_URI },
    migrationDir: path.resolve(dirname, 'migrations'),
  }),
  secret: process.env.PAYLOAD_SECRET || '',
  typescript: { outputFile: path.resolve(dirname, 'src/payload-types.ts') },
})
