import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

describe('cấu hình (spec §0.1, §0.2)', () => {
  it('không đặt schemaName; không chuỗi kết nối nào tới database klaw', () => {
    const goc = path.resolve(__dirname, '..')
    const tep = ['payload.config.ts', '.env.example', 'tests/setup.ts'].map((t) => fs.readFileSync(path.join(goc, t), 'utf8')).join('\n')
    expect(tep).not.toMatch(/schemaName/)
    expect(tep).not.toMatch(/5432\/klaw(["'\s]|$)/m)
  })
  it('ghim đúng payload 3.88.0', () => {
    const pkg = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../package.json'), 'utf8'))
    for (const k of ['payload', '@payloadcms/next', '@payloadcms/db-postgres', '@payloadcms/ui', '@payloadcms/translations'])
      expect(pkg.dependencies[k]).toBe('3.88.0')
  })
})
