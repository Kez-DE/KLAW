'use client'
import { Button } from '@payloadcms/ui'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { BtTim } from '../components/ui/BieuTuong'
import { HopXacNhan } from '../components/ui/HopXacNhan'
import { mauTrangThaiYeuCau, Nhan } from '../components/ui/Nhan'
import { PhanTrang } from '../components/ui/PhanTrang'
import { The } from '../components/ui/The'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { Xuong } from '../components/ui/Xuong'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'
import { chuDau, dinhDangLuc, nhanLoai, nhanTrangThaiYeuCau, tenGoi, type DanhSachGoi } from '../lib/hien-thi'
import { thongDiepSauThaoTac, type ThongDiep, type YeuCauAdmin } from './yeu-cau-logic'

type Tab = 'cho_duyet' | 'da_duyet' | 'tu_choi'
const TABS: { khoa: Tab; nhan: string }[] = [{ khoa: 'cho_duyet', nhan: 'Chờ duyệt' }, { khoa: 'da_duyet', nhan: 'Đã duyệt' }, { khoa: 'tu_choi', nhan: 'Từ chối' }]
const MOI_TRANG = 50
const CHAM_TIM = 400
const LOP_TRANG_THAI: Record<ThongDiep['kieu'], string> = { ok: 'klaw-trang-thai--ok', canh_bao: 'klaw-trang-thai--canh-bao', loi: 'klaw-trang-thai--loi' }

export function YeuCauClient({ vaiTro }: { vaiTro: 'doc' | 'quan_tri' }) {
  const router = useRouter()
  const thamSo = useSearchParams()
  const tabTuUrl = thamSo.get('trang_thai')
  const qTuUrl = thamSo.get('q') ?? '' // Tổng quan mở thẳng danh sách đã lọc theo email.
  const [tab, setTab] = useState<Tab>(tabTuUrl === 'da_duyet' || tabTuUrl === 'tu_choi' ? tabTuUrl : 'cho_duyet')
  const [qNhap, setQNhap] = useState(qTuUrl)
  const [q, setQ] = useState(qTuUrl)
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

  const chonTab = (t: Tab) => { setTab(t); setTrang(0); setThongDiep(null); router.replace(`/admin/yeu-cau?trang_thai=${t}`) }
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
    { khoa: 'tai_khoan', nhan: 'Tài khoản' }, { khoa: 'goi', nhan: 'Gói' }, { khoa: 'loai', nhan: 'Loại', phu: true },
    { khoa: 'tao_luc', nhan: 'Gửi lúc', phu: true }, { khoa: 'trang_thai', nhan: 'Trạng thái', phu: true },
    ...(coHanhDong ? [{ khoa: 'hanh_dong', nhan: 'Hành động' }] : []),
  ]
  const items = ds?.ok ? ds.data.items : []
  const hang = items.map((r) => ({
    tai_khoan: (
      <span className="klaw-tai-khoan-o">
        <span className="klaw-avatar" aria-hidden="true">{chuDau(r.email)}</span>
        <Link href={`/admin/tai-khoan?sub=${r.user_sub}`} className="klaw-chinh" onClick={(e) => e.stopPropagation()}>{r.email ?? '(không có email)'}</Link>
      </span>
    ),
    goi: <>{tenGoi(r.plan_hieu_luc, goi)} <span className="klaw-phu">→ {tenGoi(r.goi_muon, goi)}</span></>,
    loai: nhanLoai(r.loai),
    tao_luc: <span className="klaw-ma">{dinhDangLuc(r.tao_luc)}</span>,
    trang_thai: (
      <span className="klaw-dinh-danh__nhan">
        <Nhan mau={mauTrangThaiYeuCau(r.trang_thai)}>{nhanTrangThaiYeuCau(r.trang_thai)}</Nhan>
        {r.khoa_luc && <Nhan mau="do">Đang khoá</Nhan>}
      </span>
    ),
    hanh_dong: coHanhDong && (
      <span className="klaw-hanh-dong__nut">
        <Button size="small" onClick={() => duyet(r)}>Duyệt</Button>
        <Button buttonStyle="secondary" size="small" onClick={() => setHopTuChoi(r.id)}>Từ chối</Button>
      </span>
    ),
  }))
  const tong = ds?.ok ? ds.data.tong : 0

  return (
    <div className="klaw-chong">
      <The
        tieuDe="Danh sách yêu cầu"
        moTa={vaiTro === 'quan_tri' ? 'Tab Chờ duyệt là nơi hành động; hai tab còn lại để tra lại quyết định đã ra.' : 'Vai trò của bạn chỉ xem — các nút duyệt và từ chối không hiện.'}
        sat
      >
        <div className="klaw-thanh-cong-cu">
          <div className="klaw-phan-doan" aria-label="Trạng thái yêu cầu">
            {TABS.map((t) => (
              <button key={t.khoa} type="button" aria-pressed={tab === t.khoa} onClick={() => chonTab(t.khoa)}>{t.nhan}</button>
            ))}
          </div>
          <div className="klaw-o-tim">
            <BtTim />
            <input
              className="klaw-nhap"
              type="search"
              value={qNhap}
              onChange={(e) => setQNhap(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') apDungTim() }}
              placeholder="Tìm theo email…"
              aria-label="Tìm theo email"
            />
          </div>
        </div>

        {thongDiep && (
          <div className="klaw-o-lot" style={{ paddingBottom: 0 }}>
            <p role="status" className={`klaw-trang-thai ${LOP_TRANG_THAI[thongDiep.kieu]}`}>
              {thongDiep.chu}
              {subKhoa && <> <Link href={`/admin/tai-khoan?sub=${subKhoa}`}>Mở khoá tài khoản</Link></>}
            </p>
          </div>
        )}

        {ds === null ? <Xuong /> : !ds.ok ? <div className="klaw-o-lot"><ThongBaoLoi message={ds.message} onThuLai={taiDanhSach} /></div> : (
          <>
            <Bang
              cot={cot}
              hang={hang}
              rong={tab === 'cho_duyet' ? 'Không có yêu cầu nào chờ duyệt' : 'Không có yêu cầu nào ở trạng thái này'}
              goiYRong={tab === 'cho_duyet' ? 'Khi người dùng gửi yêu cầu nâng gói, nó hiện ở đây và chuông sẽ báo.' : q ? 'Thử bỏ từ khoá tìm kiếm.' : undefined}
            />
            <PhanTrang
              tuDong={trang * MOI_TRANG + 1}
              denDong={Math.min(tong, (trang + 1) * MOI_TRANG)}
              tong={tong}
              coTruoc={trang > 0}
              coSau={(trang + 1) * MOI_TRANG < tong}
              onTruoc={() => setTrang((t) => t - 1)}
              onSau={() => setTrang((t) => t + 1)}
            />
          </>
        )}
      </The>

      <HopXacNhan
        mo={hopTuChoi !== null}
        tieuDe="Từ chối yêu cầu"
        moTa="Nhập lý do từ chối — người dùng sẽ thấy nội dung này và có thể gửi lại ngay."
        nhanXacNhan="Từ chối"
        canLyDo
        onXacNhan={tuChoi}
        onDong={() => setHopTuChoi(null)}
      />
    </div>
  )
}
