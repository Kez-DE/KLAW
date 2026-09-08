'use client'
import { Button } from '@payloadcms/ui'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
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
    { khoa: 'tac_nhan_loai', nhan: 'Loại tác nhân' }, { khoa: 'ip', nhan: 'IP' }, { khoa: 'doi_tuong', nhan: 'Đối tượng' },
    { khoa: 'chi_tiet', nhan: 'Chi tiết' },
  ]
  const hangKlaw = dsKlaw?.ok ? dsKlaw.data.items.map((r) => ({
    tao_luc: dinhDangLuc(r.tao_luc),
    hanh_dong: nhanHanhDong(r.hanh_dong),
    boi: r.boi,
    tac_nhan_loai: r.tac_nhan_loai,
    ip: r.ip ?? '—',
    doi_tuong: r.doi_tuong ?? '—',
    chi_tiet: <details><summary>Xem</summary><pre>{JSON.stringify(r.chi_tiet, null, 2)}</pre></details>,
  })) : []
  const tongKlaw = dsKlaw?.ok ? dsKlaw.data.tong : 0

  const congCms = [
    { khoa: 'createdAt', nhan: 'Thời điểm' }, { khoa: 'hanh_dong', nhan: 'Hành động' }, { khoa: 'boi', nhan: 'Bởi' }, { khoa: 'ip', nhan: 'IP' },
  ]
  const hangCms = dsCms?.ok ? dsCms.data.docs.map((r) => ({
    createdAt: dinhDangLuc(r.createdAt),
    hanh_dong: nhanHanhDong(r.hanh_dong),
    boi: r.boi,
    ip: r.ip ?? '—',
  })) : []

  return (
    <div>
      <div aria-label="Nguồn nhật ký" style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button type="button" aria-pressed={tab === 'klaw'} onClick={() => setTab('klaw')}>Nhật ký KLAW</button>
        <button type="button" aria-pressed={tab === 'cms'} onClick={() => setTab('cms')}>Nhật ký CMS</button>
      </div>

      {tab === 'klaw' && (
        <div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 16 }}>
            <label>
              <div>Từ</div>
              <input type="datetime-local" value={tuNhap} onChange={(e) => setTuNhap(e.target.value)} aria-label="Từ ngày giờ" />
            </label>
            <label>
              <div>Đến</div>
              <input type="datetime-local" value={denNhap} onChange={(e) => setDenNhap(e.target.value)} aria-label="Đến ngày giờ" />
            </label>
            <label>
              <div>Hành động</div>
              <select value={hanhDong} onChange={(e) => chonHanhDong(e.target.value)} aria-label="Hành động">
                <option value="">Tất cả hành động</option>
                {Object.entries(HANH_DONG).map(([ma, nhan]) => <option key={ma} value={ma}>{nhan}</option>)}
              </select>
            </label>
            <label>
              <div>Đối tượng</div>
              <input value={doiTuongNhap} onChange={(e) => setDoiTuongNhap(e.target.value)} placeholder="Mã UUID…" aria-label="Đối tượng" />
              {doiTuongLoi && <div role="alert">Đối tượng phải là mã UUID.</div>}
            </label>
          </div>

          {dsKlaw === null ? <p>Đang tải…</p> : !dsKlaw.ok ? <ThongBaoLoi message={dsKlaw.message} onThuLai={taiKlaw} /> : (
            <>
              <Bang cot={congKlaw} hang={hangKlaw} rong="Không có dòng nhật ký nào." />
              <p>IP là địa chỉ qua CMS khi KLAW không tin proxy.</p>
              <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
                <Button buttonStyle="secondary" disabled={trang === 1} onClick={() => setTrang((t) => t - 1)}>Trước</Button>
                <Button buttonStyle="secondary" disabled={trang * MOI_TRANG >= tongKlaw} onClick={() => setTrang((t) => t + 1)}>Sau</Button>
                <span>{tongKlaw === 0 ? 0 : (trang - 1) * MOI_TRANG + 1}–{Math.min(tongKlaw, trang * MOI_TRANG)} trong {tongKlaw}</span>
              </div>
            </>
          )}

          <div style={{ marginTop: 24, display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button buttonStyle="secondary" disabled={xuatDangTai || doiTuongLoi} onClick={() => void xuatCsv()}>Xuất CSV</Button>
            <span>Xuất tối đa 5.000 dòng mỗi lần theo bộ lọc đang chọn; thu hẹp khoảng thời gian nếu cần đủ.</span>
          </div>
          {xuatLoi && <ThongBaoLoi message={xuatLoi} />}
        </div>
      )}

      {tab === 'cms' && (
        dsCms === null ? <p>Đang tải…</p> : !dsCms.ok ? <ThongBaoLoi message={dsCms.message} onThuLai={taiCms} /> : (
          <>
            <Bang cot={congCms} hang={hangCms} rong="Không có dòng nhật ký nào." />
            <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
              <Button buttonStyle="secondary" disabled={!dsCms.data.hasPrevPage} onClick={() => setTrangCms((t) => t - 1)}>Trước</Button>
              <Button buttonStyle="secondary" disabled={!dsCms.data.hasNextPage} onClick={() => setTrangCms((t) => t + 1)}>Sau</Button>
            </div>
          </>
        )
      )}

      <p style={{ marginTop: 32 }}>Nhật ký được giữ vô thời hạn và chưa có bản sao tự động — xuất CSV định kỳ để giữ bằng chứng.</p>
    </div>
  )
}
