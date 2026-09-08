'use client'
import { Button } from '@payloadcms/ui'
import React, { useCallback, useEffect, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { HopXacNhan } from '../components/ui/HopXacNhan'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'
import { dinhDangLuc, nhanLoai, nhanTrangThaiYeuCau, tenGoi } from '../lib/hien-thi'
import { cauXacNhan, type HanhDongTK, type TaiKhoanChiTiet } from './tai-khoan-logic'

type GoiDanhMuc = { goi: { ma: string; ten: string }[]; goi_mac_dinh: string; chu_ky_pro_ngay: number }
type HopCho = { xn: ReturnType<typeof cauXacNhan>; onXacNhan: (lyDo?: string) => void } | null

export function ChiTietTaiKhoan({ sub, vaiTro }: { sub: string; vaiTro: 'doc' | 'quan_tri' }) {
  const [ct, setCt] = useState<KetQua<TaiKhoanChiTiet> | null>(null)
  const [danhMuc, setDanhMuc] = useState<KetQua<GoiDanhMuc> | null>(null)
  const [goiChon, setGoiChon] = useState('')
  const [soNgayNhap, setSoNgayNhap] = useState('')
  const [hopCho, setHopCho] = useState<HopCho>(null)
  const [loi, setLoi] = useState<string | null>(null)

  const taiChiTiet = useCallback(() => {
    void goiQuanTri<TaiKhoanChiTiet>(`/tai-khoan/${sub}`).then((kq) => { setCt(kq); if (kq.ok) setGoiChon(kq.data.plan) })
  }, [sub])
  useEffect(() => { taiChiTiet() }, [taiChiTiet])
  // Danh mục gói tải một lần — setState nằm trong .then, không đồng bộ trong effect.
  useEffect(() => { void goiQuanTri<GoiDanhMuc>('/goi').then((kq) => { setDanhMuc(kq); if (kq.ok) setSoNgayNhap(String(kq.data.chu_ky_pro_ngay)) }) }, [])

  const goiMacDinh = danhMuc?.ok ? danhMuc.data.goi_mac_dinh : undefined
  const dsGoi = danhMuc?.ok ? danhMuc.data.goi : undefined
  const soNgayHieuLuc = (): number | null => (goiChon === goiMacDinh || soNgayNhap.trim() === '' ? null : Number(soNgayNhap))

  const sauThaoTac = (kq: KetQua<unknown>) => {
    setHopCho(null)
    if (kq.ok) { setLoi(null); taiChiTiet() } else setLoi(kq.message)
  }
  const moHop = (hd: HanhDongTK, ctx: { tenGoi?: string; soNgay?: number | null }, onXacNhan: (lyDo?: string) => void) => {
    if (!ct?.ok) return
    setHopCho({ xn: cauXacNhan(hd, { email: ct.data.email ?? '', ...ctx }), onXacNhan })
  }
  const datGoi = () => moHop('dat_goi', { tenGoi: tenGoi(goiChon, dsGoi), soNgay: soNgayHieuLuc() }, (lyDo) => {
    void goiQuanTri(`/tai-khoan/${sub}/goi`, { method: 'PATCH', body: { plan: goiChon, so_ngay: soNgayHieuLuc(), ly_do: lyDo } }).then(sauThaoTac)
  })
  const thuHoi = () => moHop('thu_hoi', {}, (lyDo) => {
    void goiQuanTri(`/tai-khoan/${sub}/thu-hoi`, { method: 'POST', body: { ly_do: lyDo } }).then(sauThaoTac)
  })
  const khoa = () => moHop('khoa', {}, (lyDo) => {
    void goiQuanTri(`/tai-khoan/${sub}/khoa`, { method: 'POST', body: { ly_do: lyDo } }).then(sauThaoTac)
  })
  const moKhoa = () => moHop('mo_khoa', {}, (lyDo) => {
    void goiQuanTri(`/tai-khoan/${sub}/mo-khoa`, { method: 'POST', body: { ly_do: lyDo } }).then(sauThaoTac)
  })

  if (ct === null) return <p>Đang tải…</p>
  if (!ct.ok) return <ThongBaoLoi message={ct.message} onThuLai={taiChiTiet} />
  const d = ct.data
  const cotYc = [
    { khoa: 'loai', nhan: 'Loại' }, { khoa: 'goi', nhan: 'Gói' }, { khoa: 'trang_thai', nhan: 'Trạng thái' },
    { khoa: 'tao_luc', nhan: 'Tạo lúc' }, { khoa: 'xu_ly_luc', nhan: 'Xử lý lúc' }, { khoa: 'ly_do', nhan: 'Lý do' },
  ]
  const hangYc = d.yeu_cau.map((y) => ({
    loai: nhanLoai(y.loai), goi: `${tenGoi(y.goi_hien_tai, dsGoi)} → ${tenGoi(y.goi_muon, dsGoi)}`,
    trang_thai: nhanTrangThaiYeuCau(y.trang_thai), tao_luc: dinhDangLuc(y.tao_luc),
    xu_ly_luc: y.xu_ly_luc ? dinhDangLuc(y.xu_ly_luc) : '—', ly_do: y.ly_do ?? '—',
  }))

  return (
    <div>
      <h2>{d.email ?? '(không có email)'}</h2>
      <p>
        {tenGoi(d.plan, dsGoi)}{d.het_han_luc ? ` · hết hạn ${dinhDangLuc(d.het_han_luc)}` : ' · vô thời hạn'}
        {d.khoa_luc && <><br />Đang khoá từ {dinhDangLuc(d.khoa_luc)} · Lý do: {d.khoa_ly_do}</>}
      </p>
      {loi && <ThongBaoLoi message={loi} />}
      <div style={{ display: 'flex', gap: 24, margin: '16px 0' }}>
        <span>Hỏi đáp: {d.tong_hoi_dap}</span>
        <span>Bản thảo: {d.tong_ban_thao}</span>
        <span>Số phiên: {d.so_phien}</span>
      </div>
      {vaiTro === 'quan_tri' && (
        <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: 16 }}>
          <label>Gói<br />
            <select value={goiChon} onChange={(e) => setGoiChon(e.target.value)}>
              {(dsGoi ?? []).map((g) => <option key={g.ma} value={g.ma}>{g.ten}</option>)}
            </select>
          </label>
          <label>Số ngày (để trống = vô thời hạn)<br />
            <input type="number" min={1} max={3650} value={soNgayNhap} disabled={goiChon === goiMacDinh} onChange={(e) => setSoNgayNhap(e.target.value)} />
          </label>
          <Button onClick={datGoi}>Đặt gói</Button>
          {d.plan !== goiMacDinh && <Button buttonStyle="secondary" onClick={thuHoi}>Thu hồi gói</Button>}
          {d.khoa_luc ? <Button buttonStyle="secondary" onClick={moKhoa}>Mở khoá</Button> : <Button buttonStyle="secondary" onClick={khoa}>Khoá</Button>}
        </div>
      )}
      <Bang cot={cotYc} hang={hangYc} rong="Chưa có yêu cầu nào." />
      <HopXacNhan
        mo={hopCho !== null}
        tieuDe={hopCho?.xn.tieuDe ?? ''}
        moTa={hopCho?.xn.moTa ?? ''}
        nhanXacNhan="Xác nhận"
        canLyDo={hopCho?.xn.canLyDo}
        onXacNhan={(lyDo) => hopCho?.onXacNhan(lyDo)}
        onDong={() => setHopCho(null)}
      />
    </div>
  )
}
