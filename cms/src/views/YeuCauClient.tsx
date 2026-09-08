'use client'
import { Button } from '@payloadcms/ui'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { HopXacNhan } from '../components/ui/HopXacNhan'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'
import { dinhDangLuc, nhanLoai, nhanTrangThaiYeuCau, tenGoi, type DanhSachGoi } from '../lib/hien-thi'
import { thongDiepSauThaoTac, type ThongDiep, type YeuCauAdmin } from './yeu-cau-logic'

type Tab = 'cho_duyet' | 'da_duyet' | 'tu_choi'
const TABS: { khoa: Tab; nhan: string }[] = [{ khoa: 'cho_duyet', nhan: 'Chờ duyệt' }, { khoa: 'da_duyet', nhan: 'Đã duyệt' }, { khoa: 'tu_choi', nhan: 'Từ chối' }]
const MOI_TRANG = 50
const CHAM_TIM = 400

export function YeuCauClient({ vaiTro }: { vaiTro: 'doc' | 'quan_tri' }) {
  const router = useRouter()
  const tabTuUrl = useSearchParams().get('trang_thai')
  const [tab, setTab] = useState<Tab>(tabTuUrl === 'da_duyet' || tabTuUrl === 'tu_choi' ? tabTuUrl : 'cho_duyet')
  const [qNhap, setQNhap] = useState('')
  const [q, setQ] = useState('')
  const [trang, setTrang] = useState(0)
  const [ds, setDs] = useState<KetQua<{ tong: number; items: YeuCauAdmin[] }> | null>(null)
  const [goi, setGoi] = useState<{ ma: string; ten: string }[] | undefined>(undefined)
  const [hopTuChoi, setHopTuChoi] = useState<number | null>(null)
  const [thongDiep, setThongDiep] = useState<ThongDiep | null>(null)
  const [subKhoa, setSubKhoa] = useState<string | null>(null)

  const theHe = useRef(0)
  // Phản hồi cũ tới sau không được ghi đè danh sách của lần gọi mới hơn.
  const taiDanhSach = useCallback(() => {
    const p = new URLSearchParams({ trang_thai: tab, limit: String(MOI_TRANG), offset: String(trang * MOI_TRANG) })
    if (q) p.set('q', q)
    const the = ++theHe.current
    void goiQuanTri<{ tong: number; items: YeuCauAdmin[] }>(`/yeu-cau?${p}`).then((kq) => { if (the === theHe.current) setDs(kq) })
  }, [tab, trang, q])
  useEffect(() => { taiDanhSach() }, [taiDanhSach])
  // Danh mục gói tải một lần — không setState đồng bộ trong effect (chỉ trong .then).
  useEffect(() => { void goiQuanTri<DanhSachGoi>('/goi').then((kq) => { if (kq.ok) setGoi(kq.data.goi) }) }, [])
  // Debounce 400ms; Enter (apDungTim) áp ngay. setState nằm trong callback setTimeout, không đồng bộ trong effect.
  useEffect(() => {
    const id = setTimeout(() => { setTrang(0); setQ(qNhap) }, CHAM_TIM)
    return () => clearTimeout(id)
  }, [qNhap])

  const chonTab = (t: Tab) => { setTab(t); setTrang(0); router.replace(`/admin/yeu-cau?trang_thai=${t}`) }
  const apDungTim = () => { setTrang(0); setQ(qNhap) }

  const xuLyKetQua = useCallback((kq: KetQua<unknown>, loai: 'duyet' | 'tu_choi', userSub: string) => {
    const td = thongDiepSauThaoTac(kq.ok ? 200 : kq.status, loai, kq.ok ? '' : kq.message)
    setThongDiep(td)
    setSubKhoa(!kq.ok && kq.status === 423 ? userSub : null)
    if (td.taiLai) taiDanhSach()
  }, [taiDanhSach])
  const duyet = (r: YeuCauAdmin) => { void goiQuanTri(`/yeu-cau/${r.id}/duyet`, { method: 'POST' }).then((kq) => xuLyKetQua(kq, 'duyet', r.user_sub)) }
  const tuChoi = (lyDo?: string) => {
    const id = hopTuChoi
    if (id === null) return
    const dong = ds?.ok ? ds.data.items.find((r) => r.id === id) : undefined
    setHopTuChoi(null)
    void goiQuanTri(`/yeu-cau/${id}/tu-choi`, { method: 'POST', body: { ly_do: lyDo ?? '' } }).then((kq) => xuLyKetQua(kq, 'tu_choi', dong?.user_sub ?? ''))
  }

  const coHanhDong = vaiTro === 'quan_tri' && tab === 'cho_duyet'
  const cot = [
    { khoa: 'email', nhan: 'Email' }, { khoa: 'goi_hien_tai', nhan: 'Gói hiện tại' }, { khoa: 'loai', nhan: 'Loại' },
    { khoa: 'tao_luc', nhan: 'Tạo lúc' }, { khoa: 'trang_thai', nhan: 'Trạng thái' },
    ...(coHanhDong ? [{ khoa: 'hanh_dong', nhan: 'Hành động' }] : []),
  ]
  const hang = ds?.ok ? ds.data.items.map((r) => ({
    email: r.email ?? '(không có email)',
    goi_hien_tai: tenGoi(r.plan_hieu_luc, goi),
    loai: nhanLoai(r.loai),
    tao_luc: dinhDangLuc(r.tao_luc),
    trang_thai: <>{nhanTrangThaiYeuCau(r.trang_thai)}{r.khoa_luc && <strong> · Đang khoá</strong>}</>,
    hanh_dong: coHanhDong && (
      <span style={{ display: 'flex', gap: 8 }}>
        <Button buttonStyle="secondary" onClick={() => duyet(r)}>Duyệt</Button>
        <Button buttonStyle="secondary" onClick={() => setHopTuChoi(r.id)}>Từ chối</Button>
      </span>
    ),
  })) : []
  const tong = ds?.ok ? ds.data.tong : 0

  return (
    <div>
      <div aria-label="Trạng thái yêu cầu" style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {TABS.map((t) => (
          <button key={t.khoa} type="button" aria-pressed={tab === t.khoa} onClick={() => chonTab(t.khoa)}>{t.nhan}</button>
        ))}
      </div>
      <input
        value={qNhap}
        onChange={(e) => setQNhap(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') apDungTim() }}
        placeholder="Tìm theo email…"
        aria-label="Tìm theo email"
        style={{ marginBottom: 16, display: 'block' }}
      />
      {thongDiep && (
        <p role="status">
          {thongDiep.chu}
          {subKhoa && <> <Link href={`/admin/tai-khoan?sub=${subKhoa}`}>Mở khoá tài khoản</Link></>}
        </p>
      )}
      {ds === null ? <p>Đang tải…</p> : !ds.ok ? <ThongBaoLoi message={ds.message} onThuLai={taiDanhSach} /> : (
        <>
          <Bang cot={cot} hang={hang} rong="Không có yêu cầu nào." />
          <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Button buttonStyle="secondary" disabled={trang === 0} onClick={() => setTrang((t) => t - 1)}>Trước</Button>
            <Button buttonStyle="secondary" disabled={(trang + 1) * MOI_TRANG >= tong} onClick={() => setTrang((t) => t + 1)}>Sau</Button>
            <span>{tong === 0 ? 0 : trang * MOI_TRANG + 1}–{Math.min(tong, (trang + 1) * MOI_TRANG)} trong {tong}</span>
          </div>
        </>
      )}
      <HopXacNhan
        mo={hopTuChoi !== null}
        tieuDe="Từ chối yêu cầu"
        moTa="Nhập lý do từ chối — người dùng sẽ thấy nội dung này."
        nhanXacNhan="Từ chối"
        canLyDo
        onXacNhan={tuChoi}
        onDong={() => setHopTuChoi(null)}
      />
    </div>
  )
}
