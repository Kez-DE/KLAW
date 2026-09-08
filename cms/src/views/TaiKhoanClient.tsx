'use client'
import { Button } from '@payloadcms/ui'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'
import { dinhDangLuc, tenGoi } from '../lib/hien-thi'
import { ChiTietTaiKhoan } from './ChiTietTaiKhoan'
import { sapHetHan, type TaiKhoanTomTat } from './tai-khoan-logic'

const MOI_TRANG = 50
const CHAM_TIM = 400
const SUB_RE = /^[0-9a-f-]{36}$/i

export function TaiKhoanClient({ vaiTro }: { vaiTro: 'doc' | 'quan_tri' }) {
  const router = useRouter()
  const sub = useSearchParams().get('sub')
  const loc = useSearchParams().get('loc')

  const [qNhap, setQNhap] = useState('')
  const [q, setQ] = useState('')
  const [trang, setTrang] = useState(0)
  const [ds, setDs] = useState<KetQua<{ tong: number; items: TaiKhoanTomTat[] }> | null>(null)
  const [goi, setGoi] = useState<{ ma: string; ten: string }[] | undefined>(undefined)

  const theHe = useRef(0)
  // Phản hồi cũ tới sau không được ghi đè danh sách của lần gọi mới hơn.
  const taiDanhSach = useCallback(() => {
    const p = new URLSearchParams({ limit: String(MOI_TRANG), offset: String(trang * MOI_TRANG) })
    if (q) p.set('q', q)
    const the = ++theHe.current
    void goiQuanTri<{ tong: number; items: TaiKhoanTomTat[] }>(`/tai-khoan?${p}`).then((kq) => { if (the === theHe.current) setDs(kq) })
  }, [trang, q])
  useEffect(() => { if (!sub) taiDanhSach() }, [taiDanhSach, sub])
  // Danh mục gói tải một lần — không setState đồng bộ trong effect (chỉ trong .then).
  useEffect(() => { void goiQuanTri<{ goi: { ma: string; ten: string }[] }>('/goi').then((kq) => { if (kq.ok) setGoi(kq.data.goi) }) }, [])
  // Debounce 400ms; Enter (apDungTim) áp ngay. setState nằm trong callback setTimeout, không đồng bộ trong effect.
  useEffect(() => {
    const id = setTimeout(() => { setTrang(0); setQ(qNhap) }, CHAM_TIM)
    return () => clearTimeout(id)
  }, [qNhap])

  if (sub) {
    if (!SUB_RE.test(sub)) return <ThongBaoLoi message="Địa chỉ không hợp lệ." />
    return (
      <div>
        <div style={{ marginBottom: 16 }}>
          <Button buttonStyle="secondary" onClick={() => router.push('/admin/tai-khoan')}>← Danh sách</Button>
        </div>
        <ChiTietTaiKhoan sub={sub} vaiTro={vaiTro} />
      </div>
    )
  }

  const apDungTim = () => { setTrang(0); setQ(qNhap) }
  const tong = ds?.ok ? ds.data.tong : 0
  // ponytail: lọc client trên trang hiện tại, chuyển sang query KLAW khi > 500 tài khoản
  const items = ds?.ok ? (loc === 'het_han' ? ds.data.items.filter((r) => sapHetHan(r.plan_het_han)) : ds.data.items) : []

  const cot = [
    { khoa: 'email', nhan: 'Email' }, { khoa: 'goi', nhan: 'Gói' }, { khoa: 'han', nhan: 'Hạn' },
    { khoa: 'trang_thai', nhan: 'Trạng thái' }, { khoa: 'tham_gia', nhan: 'Tham gia' },
    { khoa: 'so_phien', nhan: 'Số phiên' }, { khoa: 'luot_30_ngay', nhan: 'Lượt 30 ngày' },
  ]
  const hang = items.map((r) => ({
    email: r.email ?? '(không có email)',
    goi: tenGoi(r.plan, goi),
    han: r.plan_het_han ? dinhDangLuc(r.plan_het_han) : '—',
    trang_thai: r.khoa_luc ? 'Đang khoá' : 'Bình thường',
    tham_gia: dinhDangLuc(r.tao_luc),
    so_phien: r.so_phien,
    luot_30_ngay: r.luot_30_ngay,
  }))

  return (
    <div>
      {loc === 'het_han' && <p>Đang lọc: hết hạn trong 7 ngày · <Link href="/admin/tai-khoan">Bỏ lọc</Link></p>}
      <input
        type="search"
        value={qNhap}
        onChange={(e) => setQNhap(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') apDungTim() }}
        placeholder="Tìm theo email…"
        aria-label="Tìm theo email"
        style={{ marginBottom: 16, display: 'block' }}
      />
      {ds === null ? <p>Đang tải…</p> : !ds.ok ? <ThongBaoLoi message={ds.message} onThuLai={taiDanhSach} /> : (
        <>
          <Bang cot={cot} hang={hang} rong="Không có tài khoản nào." onChonHang={(i) => router.push(`/admin/tai-khoan?sub=${items[i].sub}`)} />
          <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Button buttonStyle="secondary" disabled={trang === 0} onClick={() => setTrang((t) => t - 1)}>Trước</Button>
            <Button buttonStyle="secondary" disabled={(trang + 1) * MOI_TRANG >= tong} onClick={() => setTrang((t) => t + 1)}>Sau</Button>
            <span>{tong === 0 ? 0 : trang * MOI_TRANG + 1}–{Math.min(tong, (trang + 1) * MOI_TRANG)} trong {tong}</span>
          </div>
        </>
      )}
    </div>
  )
}
