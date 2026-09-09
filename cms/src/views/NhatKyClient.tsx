'use client'
import { Button } from '@payloadcms/ui'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { BtTaiXuong } from '../components/ui/BieuTuong'
import { PhanTrang } from '../components/ui/PhanTrang'
import { The } from '../components/ui/The'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { Xuong } from '../components/ui/Xuong'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'
import { dinhDangLuc, HANH_DONG, nhanHanhDong } from '../lib/hien-thi'
import { queryNhatKy } from './nhat-ky-logic'

type Tab = 'klaw' | 'cms'
const MOI_TRANG = 50
const CHAM_TIM = 400
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

type DongKlaw = {
  id: number
  hanh_dong: string
  doi_tuong: string | null
  chi_tiet: Record<string, unknown>
  boi: string
  tac_nhan_loai: string
  ip: string | null
  tao_luc: string
}
type DongCms = { id: number | string; createdAt: string; hanh_dong: string; boi: string; ip: string | null }
type TrangCms = { docs: DongCms[]; hasNextPage: boolean; hasPrevPage: boolean }

export function NhatKyClient() {
  const [tab, setTab] = useState<Tab>('klaw')

  // Bộ lọc — giá trị gõ (áp debounce) và giá trị đã áp (đưa vào truy vấn).
  const [tuNhap, setTuNhap] = useState('')
  const [denNhap, setDenNhap] = useState('')
  const [doiTuongNhap, setDoiTuongNhap] = useState('')
  const [hanhDong, setHanhDong] = useState('')
  const [tu, setTu] = useState('')
  const [den, setDen] = useState('')
  const [doiTuong, setDoiTuong] = useState('')
  const [trang, setTrang] = useState(1)
  const [dsKlaw, setDsKlaw] = useState<KetQua<{ tong: number; items: DongKlaw[] }> | null>(null)
  const [xuatDangTai, setXuatDangTai] = useState(false)
  const [xuatLoi, setXuatLoi] = useState<string | null>(null)

  const [trangCms, setTrangCms] = useState(1)
  const [dsCms, setDsCms] = useState<{ ok: true; data: TrangCms } | { ok: false; message: string } | null>(null)

  const doiTuongLoi = doiTuongNhap !== '' && !UUID_RE.test(doiTuongNhap)

  const theHeKlaw = useRef(0)
  // Phản hồi cũ tới sau không được ghi đè danh sách của lần gọi mới hơn.
  const taiKlaw = useCallback(() => {
    const qs = queryNhatKy({ tu, den, hanhDong, doiTuong, trang, kichCo: MOI_TRANG })
    const the = ++theHeKlaw.current
    void goiQuanTri<{ tong: number; items: DongKlaw[] }>(`/nhat-ky${qs}`).then((kq) => { if (the === theHeKlaw.current) setDsKlaw(kq) })
  }, [tu, den, hanhDong, doiTuong, trang])
  useEffect(() => { if (tab === 'klaw') taiKlaw() }, [taiKlaw, tab])

  const theHeCms = useRef(0)
  const taiCms = useCallback(() => {
    const the = ++theHeCms.current
    fetch(`/api/nhat_ky_cms?sort=-createdAt&limit=${MOI_TRANG}&page=${trangCms}`, { credentials: 'same-origin' })
      .then(async (res) => {
        if (!res.ok) return { ok: false as const, message: `Lỗi ${res.status}.` }
        return { ok: true as const, data: (await res.json()) as TrangCms }
      })
      .catch(() => ({ ok: false as const, message: 'Không nối được tới trang quản trị. Kiểm tra mạng rồi thử lại.' }))
      .then((kq) => { if (the === theHeCms.current) setDsCms(kq) })
  }, [trangCms])
  useEffect(() => { if (tab === 'cms') taiCms() }, [taiCms, tab])

  // Debounce 400ms cho ô nhập tự do; đối tượng sai định dạng UUID không được áp vào bộ lọc
  // (bỏ qua truy vấn cho tới khi sửa đúng). setState nằm trong callback setTimeout, không
  // đồng bộ trong effect (react-hooks/set-state-in-effect).
  useEffect(() => {
    const id = setTimeout(() => {
      setTrang(1)
      setTu(tuNhap)
      setDen(denNhap)
      if (doiTuongNhap === '' || UUID_RE.test(doiTuongNhap)) setDoiTuong(doiTuongNhap)
    }, CHAM_TIM)
    return () => clearTimeout(id)
  }, [tuNhap, denNhap, doiTuongNhap])

  const chonHanhDong = (v: string) => { setHanhDong(v); setTrang(1) }

  const xuatCsv = async () => {
    setXuatDangTai(true)
    setXuatLoi(null)
    const qs = queryNhatKy({ tu, den, hanhDong, doiTuong, trang: 1, kichCo: MOI_TRANG, csv: true })
    try {
      const res = await fetch(`/api/klaw/nhat-ky${qs}`, { credentials: 'same-origin' })
      if (!res.ok) {
        let message = `Lỗi ${res.status}.`
        try { const j = await res.json(); if (typeof j.detail === 'string') message = j.detail } catch { /* thân không phải JSON */ }
        setXuatLoi(message)
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'nhat-ky-quan-tri.csv'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      setXuatLoi('Không nối được tới trang quản trị. Kiểm tra mạng rồi thử lại.')
    } finally {
      setXuatDangTai(false)
    }
  }

  const congKlaw = [
    { khoa: 'tao_luc', nhan: 'Thời điểm' }, { khoa: 'hanh_dong', nhan: 'Hành động' }, { khoa: 'boi', nhan: 'Người thực hiện' },
    { khoa: 'doi_tuong', nhan: 'Đối tượng', boc: true }, { khoa: 'chi_tiet', nhan: 'Chi tiết' },
  ]
  const hangKlaw = dsKlaw?.ok ? dsKlaw.data.items.map((r) => ({
    tao_luc: <span className="klaw-ma">{dinhDangLuc(r.tao_luc)}</span>,
    hanh_dong: <span className="klaw-chinh">{nhanHanhDong(r.hanh_dong)}</span>,
    // Loại tác nhân và IP xếp thành dòng phụ dưới người thực hiện để cột Chi tiết luôn nằm trong khung.
    boi: (
      <>
        {r.boi}
        <span className="klaw-dong-phu">{r.tac_nhan_loai} · <span className="klaw-ma">{r.ip ?? '—'}</span></span>
      </>
    ),
    doi_tuong: <span className="klaw-ma">{r.doi_tuong ?? '—'}</span>,
    chi_tiet: (
      <details className="klaw-chi-tiet-json">
        <summary>Xem</summary>
        <pre>{JSON.stringify(r.chi_tiet, null, 2)}</pre>
      </details>
    ),
  })) : []
  const tongKlaw = dsKlaw?.ok ? dsKlaw.data.tong : 0

  const congCms = [
    { khoa: 'createdAt', nhan: 'Thời điểm' }, { khoa: 'hanh_dong', nhan: 'Hành động' }, { khoa: 'boi', nhan: 'Bởi' }, { khoa: 'ip', nhan: 'IP' },
  ]
  const hangCms = dsCms?.ok ? dsCms.data.docs.map((r) => ({
    createdAt: <span className="klaw-ma">{dinhDangLuc(r.createdAt)}</span>,
    hanh_dong: <span className="klaw-chinh">{nhanHanhDong(r.hanh_dong)}</span>,
    boi: r.boi,
    ip: <span className="klaw-ma">{r.ip ?? '—'}</span>,
  })) : []

  return (
    <div className="klaw-chong">
      <The
        tieuDe={tab === 'klaw' ? 'Nhật ký KLAW' : 'Nhật ký CMS'}
        moTa={tab === 'klaw' ? 'Bản pháp lý: mọi thao tác admin trên tài khoản người dùng, chỉ ghi thêm.' : 'Đăng nhập và đăng nhập sai vào trang quản trị này.'}
        hanhDong={tab === 'klaw' && (
          <Button buttonStyle="secondary" size="small" disabled={xuatDangTai || doiTuongLoi} onClick={() => void xuatCsv()}>
            <span className="klaw-tai-khoan-o"><BtTaiXuong /> {xuatDangTai ? 'Đang xuất…' : 'Xuất CSV'}</span>
          </Button>
        )}
        sat
      >
        <div className="klaw-thanh-cong-cu">
          <div className="klaw-phan-doan" aria-label="Nguồn nhật ký">
            <button type="button" aria-pressed={tab === 'klaw'} onClick={() => setTab('klaw')}>Nhật ký KLAW</button>
            <button type="button" aria-pressed={tab === 'cms'} onClick={() => setTab('cms')}>Nhật ký CMS</button>
          </div>
        </div>

        {tab === 'klaw' && (
          <>
            <div className="klaw-thanh-cong-cu" style={{ justifyContent: 'flex-start', alignItems: 'flex-start' }}>
              <label className="klaw-truong">
                <span>Từ</span>
                <input className="klaw-nhap" type="datetime-local" value={tuNhap} onChange={(e) => setTuNhap(e.target.value)} aria-label="Từ ngày giờ" />
              </label>
              <label className="klaw-truong">
                <span>Đến</span>
                <input className="klaw-nhap" type="datetime-local" value={denNhap} onChange={(e) => setDenNhap(e.target.value)} aria-label="Đến ngày giờ" />
              </label>
              <label className="klaw-truong">
                <span>Hành động</span>
                <select className="klaw-chon" value={hanhDong} onChange={(e) => chonHanhDong(e.target.value)} aria-label="Hành động">
                  <option value="">Tất cả hành động</option>
                  {Object.entries(HANH_DONG).map(([ma, nhan]) => <option key={ma} value={ma}>{nhan}</option>)}
                </select>
              </label>
              <label className="klaw-truong">
                <span>Đối tượng</span>
                <input
                  className="klaw-nhap"
                  value={doiTuongNhap}
                  onChange={(e) => setDoiTuongNhap(e.target.value)}
                  placeholder="Mã UUID…"
                  aria-label="Đối tượng"
                  aria-invalid={doiTuongLoi}
                />
                {doiTuongLoi && <span role="alert" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 500, color: 'var(--klaw-do)' }}>Đối tượng phải là mã UUID.</span>}
              </label>
            </div>

            {dsKlaw === null ? <Xuong /> : !dsKlaw.ok ? <div className="klaw-o-lot"><ThongBaoLoi message={dsKlaw.message} onThuLai={taiKlaw} /></div> : (
              <>
                <Bang cot={congKlaw} hang={hangKlaw} rong="Không có dòng nhật ký nào" goiYRong="Nới khoảng thời gian hoặc bỏ bộ lọc hành động." />
                <PhanTrang
                  tuDong={(trang - 1) * MOI_TRANG + 1}
                  denDong={Math.min(tongKlaw, trang * MOI_TRANG)}
                  tong={tongKlaw}
                  coTruoc={trang > 1}
                  coSau={trang * MOI_TRANG < tongKlaw}
                  onTruoc={() => setTrang((t) => t - 1)}
                  onSau={() => setTrang((t) => t + 1)}
                />
              </>
            )}
            {xuatLoi && <div className="klaw-o-lot"><ThongBaoLoi message={xuatLoi} /></div>}
          </>
        )}

        {tab === 'cms' && (
          dsCms === null ? <Xuong /> : !dsCms.ok ? <div className="klaw-o-lot"><ThongBaoLoi message={dsCms.message} onThuLai={taiCms} /></div> : (
            <>
              <Bang cot={congCms} hang={hangCms} rong="Không có dòng nhật ký nào" goiYRong="Lần đăng nhập đầu tiên vào trang này sẽ tạo dòng đầu tiên." />
              <PhanTrang
                tuDong={0}
                denDong={0}
                nhanTong={`Trang ${trangCms}`}
                coTruoc={dsCms.data.hasPrevPage}
                coSau={dsCms.data.hasNextPage}
                onTruoc={() => setTrangCms((t) => t - 1)}
                onSau={() => setTrangCms((t) => t + 1)}
              />
            </>
          )
        )}
      </The>

      <div className="klaw-phu">
        <p style={{ margin: '0 0 0.35rem' }}>IP là địa chỉ qua CMS khi KLAW không tin proxy.</p>
        <p style={{ margin: '0 0 0.35rem' }}>Xuất tối đa 5.000 dòng mỗi lần theo bộ lọc đang chọn; thu hẹp khoảng thời gian nếu cần đủ.</p>
        <p style={{ margin: 0 }}>Nhật ký được giữ vô thời hạn và chưa có bản sao tự động — xuất CSV định kỳ để giữ bằng chứng.</p>
      </div>
    </div>
  )
}
