import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
describe('bí mật không lọt bundle (spec §4.1, §9)', () => {
  it('.next/static không chứa KLAW_ADMIN_API_KEY', () => {
    const goc = path.resolve(__dirname, '../.next/static')
    if (!fs.existsSync(goc)) { console.warn('chưa build — bỏ qua'); return }
    const tep: string[] = []
    const duyet = (d: string) => { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) duyet(p); else tep.push(p) } }
    duyet(goc)
    for (const f of tep) expect(fs.readFileSync(f, 'utf8')).not.toContain('KLAW_ADMIN_API_KEY')
  })
})
