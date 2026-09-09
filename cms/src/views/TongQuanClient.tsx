'use client'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import React, { useCallback, useEffect, useState } from 'react'
import { Bang } from '../components/ui/Bang'
import { ChamTrucTuyen } from '../components/ui/ChamTrucTuyen'
import { Nhan } from '../components/ui/Nhan'
import { The } from '../components/ui/The'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { Trong } from '../components/ui/Trong'
import { Xuong } from '../components/ui/Xuong'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'
import { chuDau, dinhDangGio, dinhDangLuc, nhanLoai, tenGoi, type DanhSachGoi } from '../lib/hien-thi'
import { CHU_KY_MS, useTrucTuyen } from '../lib/truc-tuyen'
import type { YeuCauAdmin } from './yeu-cau-logic'

type TongQuan = {
  tong_tai_khoan: number
  dang_ca_nhan: number
  cho_duyet: number
  het_han_7_ngay: number
  moi_7_ngay: number
  dang_khoa: number
  hoi_dap_hom_nay: number
  dang_truc_tuyen: number
}
type DsCho = { tong: number; items: YeuCauAdmin[] }

const O: [keyof TongQuan, string, string?][] = [
  ['tong_tai_khoan', 'Tài khoản', '/admin/tai-khoan'],
  ['dang_ca_nhan', 'Đang dùng gói Cá nhân'],
  ['cho_duyet', 'Chờ duyệt', '/admin/yeu-cau?trang_thai=cho_duyet'],
  ['het_han_7_ngay', 'Hết hạn trong 7 ngày', '/admin/tai-khoan?loc=het_han'],
  ['moi_7_ngay', 'Mới trong 7 ngày'],
  ['dang_khoa', 'Đang khoá', '/admin/tai-khoan?loc=khoa'],
  ['hoi_dap_hom_nay', 'Lượt hỏi hôm nay'],
]

export function TongQuanClient() {
  const router = useRouter()
  const [kq, setKq] = useState<KetQua<TongQuan> | null>(null)
  const [cho, setCho] = useState<KetQua<DsCho> | null>(null)
  const [goi, setGoi] = useState<{ ma: string; ten: string }[] | undefined>(undefined)
  const tt = useTrucTuyen()

  // napLai không setState đồng bộ (chỉ trong .then) nên dùng được thẳng trong effect
  // (react-hooks/set-state-in-effect); `tai` (nút Tải lại) đặt lại về null trước khi gọi lại.
  const napLai = useCallback(() => {
    void goiQuanTri<TongQuan>('/tong-quan').then(setKq)
    void goiQuanTri<DsCho>('/yeu-cau?trang_thai=cho_duyet&limit=5&offset=0').then(setCho)
  }, [])
  useEffect(() => { napLai() }, [napLai])
  useEffect(() => { void goiQuanTri<DanhSachGoi>('/goi').then((r) => { if (r.ok) setGoi(r.data.goi) }) }, [])
  const tai = useCallback(() => { setKq(null); setCho(null); napLai() }, [napLai])

  const cotCho = [
    { khoa: 'tai_khoan', nhan: 'Tài khoản' }, { khoa: 'goi', nhan: 'Gói' }, { khoa: 'loai', nhan: 'Loại' }, { khoa: 'tao_luc', nhan: 'Gửi lúc' },
  ]
  const hangCho = cho?.ok ? cho.data.items.map((r) => ({
    tai_khoan: (
      <span className="klaw-tai-khoan-o">
        <span className="klaw-avatar" aria-hidden="true">{chuDau(r.email)}</span>
        <span className="klaw-chinh">{r.email ?? '(không có email)'}</span>
      </span>
    ),
    goi: <>{tenGoi(r.plan_hieu_luc, goi)} <span className="klaw-phu">→ {tenGoi(r.goi_muon, goi)}</span></>,
    loai: <Nhan mau="vang">{nhanLoai(r.loai)}</Nhan>,
    tao_luc: <span className="klaw-ma">{dinhDangLuc(r.tao_luc)}</span>,
  })) : []

  return (
    <div className="klaw-chong">
      <div className="klaw-luoi">
        <The
          className="klaw-luoi__8"
          tieuDe="Việc chờ xử lý"
          moTa={cho?.ok ? `${cho.data.tong.toLocaleString('vi-VN')} yêu cầu đang chờ duyệt — hiện năm yêu cầu mới nhất.` : 'Yêu cầu nâng gói đang chờ duyệt.'}
          hanhDong={<Link className="klaw-nut-lien-ket" href="/admin/yeu-cau?trang_thai=cho_duyet">Mở Yêu cầu</Link>}
          sat
        >
          {cho === null ? <Xuong /> : !cho.ok ? <div className="klaw-o-lot"><ThongBaoLoi message={cho.message} onThuLai={tai} /></div> : (
            <Bang
              cot={cotCho}
              hang={hangCho}
              rong="Không có yêu cầu nào chờ duyệt"
              goiYRong="Khi người dùng gửi yêu cầu nâng gói, nó hiện ở đây và chuông sẽ báo."
              onChonHang={(i) => router.push(`/admin/yeu-cau?trang_thai=cho_duyet&q=${encodeURIComponent(cho.data.items[i]?.email ?? '')}`)}
              nhanHang={(i) => `Mở yêu cầu của ${cho.data.items[i]?.email ?? 'tài khoản'}`}
            />
          )}
        </The>

        <The
          className="klaw-luoi__4"
          tieuDe={<>Đang trực tuyến{tt?.ok && <> <Nhan mau={tt.data.so > 0 ? 'xanh' : 'trung-tinh'}>{tt.data.so.toLocaleString('vi-VN')}</Nhan></>}</>}
          moTa="Tính theo kết nối thông báo đang mở."
          chan={`Làm mới mỗi ${CHU_KY_MS / 1000} giây khi tab đang hiện.`}
          sat
        >
          {tt === null ? <Xuong dong={3} /> : !tt.ok ? <div className="klaw-o-lot"><ThongBaoLoi message={tt.message} /></div> : tt.data.items.length === 0 ? (
            <Trong tieuDe="Không ai đang mở KLAW" goiY="Người dùng đăng nhập và mở ứng dụng sẽ hiện ở đây trong vài giây." />
          ) : (
            <ul className="klaw-ds-truc-tuyen">
              {tt.data.items.map((n) => (
                <li key={n.sub}>
                  <span className="klaw-avatar" aria-hidden="true">{chuDau(n.email)}</span>
                  <Link href={`/admin/tai-khoan?sub=${n.sub}`}>{n.email ?? n.sub}</Link>
                  <span className="klaw-ds-truc-tuyen__tu klaw-ma">từ {dinhDangGio(n.tu_luc)}</span>
                  <ChamTrucTuyen tren gon />
                </li>
              ))}
            </ul>
          )}
        </The>
      </div>

      <The
        tieuDe="Số liệu"
        moTa="Đếm trên KLAW lúc tải trang; ô có “Mở danh sách” dẫn tới bộ lọc tương ứng."
        hanhDong={<button type="button" className="klaw-nut-lien-ket" onClick={tai}>Tải lại</button>}
        sat
      >
        {kq === null ? <Xuong dong={2} /> : !kq.ok ? <div className="klaw-o-lot"><ThongBaoLoi message={kq.message} onThuLai={tai} /></div> : (
          <div className="klaw-dai-so">
            {O.map(([k, nhan, href]) => {
              const noiDung = (
                <>
                  <span className="klaw-dai-so__nhan">{nhan}</span>
                  <span className="klaw-dai-so__gia-tri">{kq.data[k].toLocaleString('vi-VN')}</span>
                  {href && <span className="klaw-dai-so__ghi-chu">Mở danh sách</span>}
                </>
              )
              return href
                ? <Link key={k} href={href} className="klaw-dai-so__o">{noiDung}</Link>
                : <div key={k} className="klaw-dai-so__o">{noiDung}</div>
            })}
          </div>
        )}
      </The>
    </div>
  )
}
