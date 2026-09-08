// cms/payload.config.ts
import path from 'path'
import { fileURLToPath } from 'url'
import { buildConfig } from 'payload'
import { postgresAdapter } from '@payloadcms/db-postgres'
import { en } from '@payloadcms/translations/languages/en'
import { vi } from '@payloadcms/translations/languages/vi'

import { Admins } from './src/collections/Admins'

const dirname = path.dirname(fileURLToPath(import.meta.url))

// Gốc công khai: Railway bơm RAILWAY_PUBLIC_DOMAIN; PAYLOAD_PUBLIC_SERVER_URL ghi đè cho
// host khác. Local để trống → URL tương đối.
const serverURL =
  process.env.PAYLOAD_PUBLIC_SERVER_URL ??
  (process.env.RAILWAY_PUBLIC_DOMAIN ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}` : '')
const laProd = process.env.NODE_ENV === 'production'
const origins = laProd ? [serverURL].filter(Boolean) : ['http://localhost:3001', 'http://127.0.0.1:3001']

export default buildConfig({
  admin: {
    user: 'admins',
    meta: { titleSuffix: '— KLAW quản trị' },
    components: {},
  },
  i18n: { supportedLanguages: { vi, en }, fallbackLanguage: 'vi' },
  serverURL,
  cors: origins,
  // Dev để RỖNG: allowlist csrf làm rớt phiên trên LAN plain-HTTP (kinh nghiệm dự án
  // tham chiếu). Production phải có allowlist.
  csrf: laProd ? origins : [],
  collections: [Admins],
  graphQL: { disable: true },
  // Database RIÊNG `klaw_cms` (spec §4.2). KHÔNG cấu hình schema Postgres tùy biến.
  // KHÔNG bao giờ trỏ vào database `klaw` — tests/config.spec.ts khẳng định.
  db: postgresAdapter({
    pool: { connectionString: process.env.DATABASE_URI },
    migrationDir: path.resolve(dirname, 'migrations'),
  }),
  secret: process.env.PAYLOAD_SECRET || '',
  typescript: { outputFile: path.resolve(dirname, 'src/payload-types.ts') },
})
