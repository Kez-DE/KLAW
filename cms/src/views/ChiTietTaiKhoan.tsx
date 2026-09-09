'use client'
import { Button } from '@payloadcms/ui'
import React, { useCallback, useEffect, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { ChamTrucTuyen } from '../components/ui/ChamTrucTuyen'
import { HopXacNhan } from '../components/ui/HopXacNhan'
import { mauTrangThaiYeuCau, Nhan } from '../components/ui/Nhan'
import { The } from '../components/ui/The'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { Xuong } from '../components/ui/Xuong'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'
import { chuDau, dinhDangLuc, nhanLoai, nhanTrangThaiYeuCau, tenGoi, type DanhSachGoi } from '../lib/hien-thi'
import { cauXacNhan, hanHienThi, type HanhDongTK, type TaiKhoanChiTiet } from './tai-khoan-logic'

type HopCho = { xn: ReturnType<typeof cauXacNhan>; onXacNhan: (lyDo?: string) => void } | null

export function ChiTietTaiKhoan({ sub, vaiTro, trenLive }: { sub: string; vaiTro: 'doc' | 'quan_tri'; trenLive?: boolean }) {
  const [ct, setCt] = useState<KetQua<TaiKhoanChiTiet> | null>(null)
  const [danhMuc, setDanhMuc] = useState<KetQua<DanhSachGoi> | null>(null)
  const [goiChon, setGoiChon] = useState('')
  const [soNgayNhap, setSoNgayNhap] = useState('')
  const [hopCho, setHopCho] = useState<HopCho>(null)
  const [loi, setLoi] = useState<string | null>(null)

  const taiChiTiet = useCallback(() => {
    void goiQuanTri<TaiKhoanChiTiet>(`/tai-khoan/${sub}`).then((kq) => { setCt(kq); if (kq.ok) setGoiChon(kq.data.plan) })
  }, [sub])
  useEffect(() => { taiChiTiet() }, [taiChiTiet])
  // Danh mục gói tải một lần — setState nằm trong .then, không đồng bộ trong effect.
  useEffect(() => { void goiQuanTri<DanhSachGoi>('/goi').then((kq) => { setDanhMuc(kq); if (kq.ok) setSoNgayNhap(String(kq.data.chu_ky_pro_ngay)) }) }, [])

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

  if (ct === null) return <The sat><Xuong dong={5} /></The>
  if (!ct.ok) return <ThongBaoLoi message={ct.message} onThuLai={taiChiTiet} />
  const d = ct.data
  const han = hanHienThi(d.plan, d.het_han_luc, goiMacDinh, '')
  const laMacDinh = goiMacDinh !== undefined && d.plan === goiMacDinh
  const tren = trenLive || d.truc_tuyen === true

  const cotYc = [
    { khoa: 'loai', nhan: 'Loại' }, { khoa: 'goi', nhan: 'Gói' }, { khoa: 'trang_thai', nhan: 'Trạng thái' },
    { khoa: 'tao_luc', nhan: 'Gửi lúc' }, { khoa: 'xu_ly_luc', nhan: 'Xử lý lúc' }, { khoa: 'ly_do', nhan: 'Lý do', boc: true },
  ]
  const hangYc = d.yeu_cau.map((y) => ({
    loai: nhanLoai(y.loai),
    goi: <>{tenGoi(y.goi_hien_tai, dsGoi)} <span className="klaw-phu">→ {tenGoi(y.goi_muon, dsGoi)}</span></>,
    trang_thai: <Nhan mau={mauTrangThaiYeuCau(y.trang_thai)}>{nhanTrangThaiYeuCau(y.trang_thai)}</Nhan>,
    tao_luc: <span className="klaw-ma">{dinhDangLuc(y.tao_luc)}</span>,
    xu_ly_luc: <span className="klaw-ma">{y.xu_ly_luc ? dinhDangLuc(y.xu_ly_luc) : '—'}</span>,
    ly_do: y.ly_do ?? <span className="klaw-phu">—</span>,
  }))

  return (
    <div className="klaw-chong">
      {loi && <ThongBaoLoi message={loi} />}
      <div className="klaw-luoi">
        <The className="klaw-luoi__7" sat>
          <div className="klaw-o-lot" style={{ padding: '1.25rem' }}>
            <div className="klaw-dinh-danh">
              <span className="klaw-avatar klaw-avatar--lon" aria-hidden="true">{chuDau(d.email)}</span>
              <div className="klaw-dinh-danh__chu">
                <h2>{d.email ?? '(không có email)'}</h2>
                <div className="klaw-dinh-danh__nhan">
                  <Nhan mau={laMacDinh ? 'trung-tinh' : 'muc'}>{tenGoi(d.plan, dsGoi)}</Nhan>
                  {d.khoa_luc && <Nhan mau="do">Đang khoá</Nhan>}
                  <ChamTrucTuyen tren={tren} />
                </div>
              </div>
            </div>
            <dl className="klaw-dong" style={{ marginTop: '1.25rem' }}>
              <dt>Mã tài khoản</dt>
              <dd className="klaw-ma">{d.sub}</dd>
              <dt>Tham gia</dt>
              <dd>{dinhDangLuc(d.tao_luc)}</dd>
              <dt>Hạn gói</dt>
              <dd>{laMacDinh ? 'Gói mặc định, không có hạn' : han ? `Hết hạn ${han}` : 'Vô thời hạn'}</dd>
              {d.khoa_luc && (
                <>
                  <dt>Khoá từ</dt>
                  <dd>{dinhDangLuc(d.khoa_luc)}</dd>
                  <dt>Lý do khoá</dt>
                  <dd>{d.khoa_ly_do}</dd>
                </>
              )}
            </dl>
          </div>
          <div className="klaw-tom-tat">
            <div><span>Hỏi đáp</span><strong>{d.tong_hoi_dap.toLocaleString('vi-VN')}</strong></div>
            <div><span>Bản thảo</span><strong>{d.tong_ban_thao.toLocaleString('vi-VN')}</strong></div>
            <div><span>Phiên</span><strong>{d.so_phien.toLocaleString('vi-VN')}</strong></div>
          </div>
        </The>

        <The
          className="klaw-luoi__5"
          tieuDe="Hành động"
          moTa={vaiTro === 'quan_tri' ? 'Mỗi thao tác cần một lý do. Lý do đặt gói và mở khoá chỉ vào nhật ký; lý do thu hồi và khoá thì người dùng thấy.' : 'Vai trò của bạn chỉ xem — không đổi được gói hay trạng thái.'}
        >
          {vaiTro === 'quan_tri' ? (
            <div className="klaw-hanh-dong">
              <div className="klaw-hanh-dong__hang">
                <label className="klaw-truong">
                  <span>Gói</span>
                  <select className="klaw-chon" value={goiChon} onChange={(e) => setGoiChon(e.target.value)}>
                    {(dsGoi ?? []).map((g) => <option key={g.ma} value={g.ma}>{g.ten}</option>)}
                  </select>
                </label>
                <label className="klaw-truong">
                  <span>Số ngày</span>
                  <input
                    className="klaw-nhap"
                    type="number"
                    min={1}
                    max={3650}
                    value={soNgayNhap}
                    disabled={goiChon === goiMacDinh}
                    placeholder="Trống = vô thời hạn"
                    onChange={(e) => setSoNgayNhap(e.target.value)}
                  />
                </label>
              </div>
              <div className="klaw-hanh-dong__nut">
                <Button onClick={datGoi}>Đặt gói</Button>
                {!laMacDinh && <Button buttonStyle="secondary" onClick={thuHoi}>Thu hồi gói</Button>}
              </div>
              <div className="klaw-hanh-dong__nhom">
                <h3>Trạng thái tài khoản</h3>
                <p className="klaw-phu" style={{ margin: 0 }}>
                  {d.khoa_luc ? 'Đang khoá: người dùng không hỏi và không soạn được; tra cứu và soát văn bản vẫn mở.' : 'Bình thường: dùng đủ tính năng theo gói.'}
                </p>
                <div className="klaw-hanh-dong__nut">
                  {d.khoa_luc
                    ? <Button buttonStyle="secondary" onClick={moKhoa}>Mở khoá</Button>
                    : <Button buttonStyle="secondary" onClick={khoa}>Khoá tài khoản</Button>}
                </div>
              </div>
            </div>
          ) : (
            <p className="klaw-phu" style={{ margin: 0 }}>Cần vai trò quản trị để đặt gói, thu hồi, khoá hoặc mở khoá.</p>
          )}
        </The>
      </div>

      <The tieuDe="Yêu cầu nâng gói" moTa="Toàn bộ yêu cầu của tài khoản này, mới nhất trước." sat>
        <Bang cot={cotYc} hang={hangYc} rong="Chưa có yêu cầu nào" goiYRong="Khi người dùng gửi yêu cầu nâng gói, nó hiện ở đây cùng quyết định và lý do." />
      </The>

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
