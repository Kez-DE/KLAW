'use client'
import { Button } from '@payloadcms/ui'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { BtMuiTenTrai, BtTim } from '../components/ui/BieuTuong'
import { ChamTrucTuyen } from '../components/ui/ChamTrucTuyen'
import { Nhan } from '../components/ui/Nhan'
import { PhanTrang } from '../components/ui/PhanTrang'
import { The } from '../components/ui/The'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { Xuong } from '../components/ui/Xuong'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'
import { chuDau, dinhDangLuc, tenGoi, type DanhSachGoi } from '../lib/hien-thi'
import { tapSubTrucTuyen, useTrucTuyen } from '../lib/truc-tuyen'
import { ChiTietTaiKhoan } from './ChiTietTaiKhoan'
import { hanHienThi, sapHetHan, type TaiKhoanTomTat } from './tai-khoan-logic'

const MOI_TRANG = 50
const CHAM_TIM = 400
const SUB_RE = /^[0-9a-f-]{36}$/i

type Loc = 'het_han' | 'khoa' | 'tren'
const LOC_HOP_LE = new Set<string>(['het_han', 'khoa', 'tren'])
const CHIP: { khoa: Loc | null; nhan: string }[] = [
  { khoa: null, nhan: 'Tất cả' }, { khoa: 'tren', nhan: 'Đang trực tuyến' }, { khoa: 'khoa', nhan: 'Đang khoá' }, { khoa: 'het_han', nhan: 'Hết hạn trong 7 ngày' },
]
const GHI_CHU_LOC: Record<Loc, string> = { het_han: 'hết hạn trong 7 ngày', khoa: 'đang khoá', tren: 'đang trực tuyến' }

export function TaiKhoanClient({ vaiTro }: { vaiTro: 'doc' | 'quan_tri' }) {
  const router = useRouter()
  const thamSo = useSearchParams()
  const sub = thamSo.get('sub')
  const locTho = thamSo.get('loc')
  const loc: Loc | null = locTho && LOC_HOP_LE.has(locTho) ? (locTho as Loc) : null

  const [qNhap, setQNhap] = useState('')
  const [q, setQ] = useState('')
  const [trang, setTrang] = useState(0)
  const [ds, setDs] = useState<KetQua<{ tong: number; items: TaiKhoanTomTat[] }> | null>(null)
  const [goi, setGoi] = useState<{ ma: string; ten: string }[] | undefined>(undefined)
  const [goiMacDinh, setGoiMacDinh] = useState<string | undefined>(undefined)
  const tt = useTrucTuyen()
  const tapTren = tapSubTrucTuyen(tt)

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
  useEffect(() => { void goiQuanTri<DanhSachGoi>('/goi').then((kq) => { if (kq.ok) { setGoi(kq.data.goi); setGoiMacDinh(kq.data.goi_mac_dinh) } }) }, [])
  // Debounce 400ms; Enter (apDungTim) áp ngay. setState nằm trong callback setTimeout, không đồng bộ trong effect.
  useEffect(() => {
    const id = setTimeout(() => { setTrang(0); setQ(qNhap) }, CHAM_TIM)
    return () => clearTimeout(id)
  }, [qNhap])

  // Trực tuyến: sổ luồng làm mới theo CHU_KY_MS (tapTren) hoặc cờ chụp lúc tải danh sách.
  const laTren = (r: TaiKhoanTomTat) => tapTren.has(r.sub) || r.truc_tuyen === true

  if (sub) {
    if (!SUB_RE.test(sub)) return <ThongBaoLoi message="Địa chỉ không hợp lệ." />
    return (
      <div className="klaw-chong">
        <div>
          <Button buttonStyle="secondary" size="small" onClick={() => router.push('/admin/tai-khoan')}>
            <span className="klaw-tai-khoan-o"><BtMuiTenTrai /> Danh sách</span>
          </Button>
        </div>
        <ChiTietTaiKhoan sub={sub} vaiTro={vaiTro} trenLive={tapTren.has(sub)} />
      </div>
    )
  }

  const apDungTim = () => { setTrang(0); setQ(qNhap) }
  const chonLoc = (l: Loc | null) => router.replace(l ? `/admin/tai-khoan?loc=${l}` : '/admin/tai-khoan')
  const tong = ds?.ok ? ds.data.tong : 0
  // ponytail: lọc chỉ trong trang 50 tài khoản mới nhất (không quét hết), nâng cấp bằng
  // query `sap_het_han`/`khoa`/`truc_tuyen` trên KLAW khi cần chính xác trên toàn bộ tài khoản.
  const items = ds?.ok
    ? ds.data.items.filter((r) => loc === null ? true : loc === 'het_han' ? sapHetHan(r.plan_het_han) : loc === 'khoa' ? r.khoa_luc !== null : laTren(r))
    : []

  const cot = [
    { khoa: 'tai_khoan', nhan: 'Tài khoản' }, { khoa: 'trang_thai', nhan: 'Trạng thái' }, { khoa: 'goi', nhan: 'Gói', phu: true }, { khoa: 'han', nhan: 'Hạn', phu: true },
    { khoa: 'tham_gia', nhan: 'Tham gia', phu: true }, { khoa: 'so_phien', nhan: 'Phiên', phu: true }, { khoa: 'luot_30_ngay', nhan: 'Lượt 30 ngày', phu: true },
  ]
  const hang = items.map((r) => ({
    tai_khoan: (
      <span className="klaw-tai-khoan-o">
        <span className="klaw-avatar" aria-hidden="true">{chuDau(r.email)}</span>
        <span className="klaw-chinh">
          {r.email ?? '(không có email)'}
          <span className="klaw-dong-phu klaw-dong-phu--di-dong">{tenGoi(r.plan, goi)}</span>
        </span>
      </span>
    ),
    trang_thai: (
      <span className="klaw-dinh-danh__nhan">
        <ChamTrucTuyen tren={laTren(r)} />
        {r.khoa_luc && <Nhan mau="do">Đang khoá</Nhan>}
      </span>
    ),
    goi: <Nhan mau={goiMacDinh !== undefined && r.plan !== goiMacDinh ? 'muc' : 'trung-tinh'}>{tenGoi(r.plan, goi)}</Nhan>,
    han: <span className="klaw-ma">{hanHienThi(r.plan, r.plan_het_han, goiMacDinh, '—')}</span>,
    tham_gia: <span className="klaw-ma">{dinhDangLuc(r.tao_luc)}</span>,
    so_phien: r.so_phien.toLocaleString('vi-VN'),
    luot_30_ngay: r.luot_30_ngay.toLocaleString('vi-VN'),
  }))

  return (
    <div className="klaw-chong">
      <The
        tieuDe="Danh sách tài khoản"
        moTa={ds?.ok ? `${tong.toLocaleString('vi-VN')} tài khoản đã đăng ký — bấm một hàng để mở chi tiết.` : 'Bấm một hàng để mở chi tiết.'}
        sat
      >
        <div className="klaw-thanh-cong-cu">
          <div className="klaw-thanh-cong-cu__nhom" aria-label="Lọc nhanh">
            {CHIP.map((c) => (
              <button key={String(c.khoa)} type="button" className="klaw-chip" aria-pressed={loc === c.khoa} onClick={() => chonLoc(c.khoa)}>
                {c.khoa === 'tren' && <span className="klaw-cham klaw-cham--tren" aria-hidden="true"><span className="klaw-cham__dot" /></span>}
                {c.nhan}
                {c.khoa === 'tren' && tt?.ok ? ` · ${tt.data.so.toLocaleString('vi-VN')}` : ''}
              </button>
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
        {loc && (
          <p className="klaw-ghi-chu-loc">
            Đang lọc: {GHI_CHU_LOC[loc]} — trong {MOI_TRANG} tài khoản mới nhất của trang này.
            <Link href="/admin/tai-khoan">Bỏ lọc</Link>
          </p>
        )}
        {ds === null ? <Xuong /> : !ds.ok ? <div className="klaw-o-lot"><ThongBaoLoi message={ds.message} onThuLai={taiDanhSach} /></div> : (
          <>
            <Bang
              cot={cot}
              hang={hang}
              rong={loc ? 'Không có tài khoản nào khớp bộ lọc' : 'Không có tài khoản nào'}
              goiYRong={loc ? 'Bỏ lọc hoặc chuyển trang để xem thêm.' : q ? 'Thử bỏ từ khoá tìm kiếm.' : undefined}
              onChonHang={(i) => router.push(`/admin/tai-khoan?sub=${items[i].sub}`)}
              nhanHang={(i) => `Mở tài khoản ${items[i]?.email ?? ''}`}
            />
            {loc === null && (
              <PhanTrang
                tuDong={trang * MOI_TRANG + 1}
                denDong={Math.min(tong, (trang + 1) * MOI_TRANG)}
                tong={tong}
                coTruoc={trang > 0}
                coSau={(trang + 1) * MOI_TRANG < tong}
                onTruoc={() => setTrang((t) => t - 1)}
                onSau={() => setTrang((t) => t + 1)}
              />
            )}
          </>
        )}
      </The>
    </div>
  )
}
