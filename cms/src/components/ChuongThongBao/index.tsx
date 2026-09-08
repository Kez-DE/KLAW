'use client'

import { useRouter } from 'next/navigation'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { ThongBaoLoi } from '../ui/ThongBaoLoi'
import { goiQuanTri, type KetQua } from '../../lib/goi-klaw'
import { duongDanCms, formatBadge, nhomTheoNgay, type ThongBao } from './bell'
import './index.scss'

type HopThu = { so_chua_doc: number; items: ThongBao[] }

const BellIcon = ({ ringing }: { ringing: boolean }) => (
  <svg
    aria-hidden="true"
    className={`chuong-thong-bao__icon${ringing ? ' chuong-thong-bao__icon--ringing' : ''}`}
    fill="currentColor"
    focusable="false"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Dome, flared lip and flat base as one solid body; the stem at the crown is part of
        the same path so the silhouette stays closed at any size. */}
    <path d="M12 2a1.65 1.65 0 0 1 1.65 1.65v.52a6.7 6.7 0 0 1 5.05 6.49v2.16c0 1.3.52 2.55 1.44 3.47l.42.42A.95.95 0 0 1 19.89 18.3H4.11a.95.95 0 0 1-.67-1.62l.42-.42a4.9 4.9 0 0 0 1.44-3.47v-2.16a6.7 6.7 0 0 1 5.05-6.49v-.52A1.65 1.65 0 0 1 12 2Z" />
    {/* Clapper: a half disc hanging below the lip. */}
    <path d="M9.35 19.5h5.3a2.65 2.65 0 0 1-5.3 0Z" />
  </svg>
)

export function ChuongThongBao() {
  const router = useRouter()
  const [dl, setDl] = useState<KetQua<HopThu> | null>(null)
  const [mo, setMo] = useState(false)

  // tai() không setState đồng bộ (chỉ trong .then) nên dùng được thẳng trong effect
  // (react-hooks/set-state-in-effect).
  const tai = useCallback(() => {
    void goiQuanTri<HopThu>('/thong-bao').then(setDl)
  }, [])

  useEffect(() => {
    tai()
  }, [tai])

  // SSE chỉ báo "có gì đó thay đổi" — GET /thong-bao vẫn là nguồn sự thật, không đọc payload sự kiện.
  useEffect(() => {
    const nguon = new EventSource('/api/klaw/thong-bao/luong')
    nguon.addEventListener('so_chua_doc', tai)
    nguon.addEventListener('thong_bao_moi', tai)
    nguon.onerror = () => {
      // Trình duyệt tự nối lại (EventSource mặc định); không cần retry tay ở đây.
    }
    return () => nguon.close()
  }, [tai])

  useEffect(() => {
    const khiHienLai = () => {
      if (document.visibilityState === 'visible') tai()
    }
    document.addEventListener('visibilitychange', khiHienLai)
    return () => document.removeEventListener('visibilitychange', khiHienLai)
  }, [tai])

  const soChuaDoc = dl?.ok ? dl.data.so_chua_doc : 0
  const items = dl?.ok ? dl.data.items : []

  // Tiêu đề tab mang số đếm; tiêu đề gốc chụp một lần lúc mount và khôi phục lúc unmount.
  const gocRef = useRef<string | null>(null)
  useEffect(() => {
    gocRef.current = document.title
    return () => {
      if (gocRef.current !== null) document.title = gocRef.current
    }
  }, [])
  useEffect(() => {
    const goc = gocRef.current
    if (goc !== null) document.title = soChuaDoc > 0 ? `(${soChuaDoc}) ${goc}` : goc
  }, [soChuaDoc])

  // Chuông rung một nhịp khi số TĂNG — không rung khi giảm hay khi mới mount. `null` nghĩa
  // "chưa thấy dữ liệu thật lần nào": khoá theo `dl` (không phải `soChuaDoc`, vốn đã là 0
  // giả trong lúc `dl` còn null) và bỏ qua hẳn khi chưa có phản hồi thật, để lần tải đầu
  // ghi nhận mốc mà không rung, chỉ rung từ lần đổi kế tiếp trở đi.
  const soTruocRef = useRef<number | null>(null)
  const [rung, setRung] = useState(false)
  useEffect(() => {
    if (!dl?.ok) return
    const truoc = soTruocRef.current
    soTruocRef.current = dl.data.so_chua_doc
    if (truoc === null || dl.data.so_chua_doc <= truoc) return
    setRung(true)
    const hen = window.setTimeout(() => setRung(false), 620)
    return () => window.clearTimeout(hen)
  }, [dl])

  const moThongBao = (tb: ThongBao) => {
    setMo(false)
    if (!tb.da_doc) void goiQuanTri('/thong-bao/da-doc', { method: 'POST', body: { ids: [tb.id] } }).then(() => tai())
    router.push(duongDanCms(tb.duong_dan))
  }

  const idsChuaDoc = items.filter((tb) => !tb.da_doc).map((tb) => tb.id)
  const danhDauTatCa = () => {
    if (idsChuaDoc.length > 0) void goiQuanTri('/thong-bao/da-doc', { method: 'POST', body: { ids: idsChuaDoc } }).then(() => tai())
  }

  const badge = formatBadge(soChuaDoc)
  const nhom = nhomTheoNgay(items, new Date())

  return (
    <div className="chuong-thong-bao">
      <button
        type="button"
        className="chuong-thong-bao__trigger"
        aria-label={`Thông báo${soChuaDoc > 0 ? `, ${soChuaDoc} chưa đọc` : ''}`}
        aria-expanded={mo}
        onClick={() => setMo((v) => !v)}
      >
        <BellIcon ringing={rung} />
        {badge ? <span className="chuong-thong-bao__badge">{badge}</span> : null}
      </button>

      {mo ? (
        <div className="chuong-thong-bao__panel" role="menu" aria-label="Thông báo">
          <div className="chuong-thong-bao__head">
            <strong>Thông báo</strong>
            <button type="button" onClick={danhDauTatCa} disabled={idsChuaDoc.length === 0}>
              Đánh dấu tất cả đã đọc
            </button>
          </div>

          {dl === null ? (
            <ul className="chuong-thong-bao__skeleton" aria-hidden="true">
              <li />
              <li />
              <li />
            </ul>
          ) : null}

          {dl && !dl.ok ? <ThongBaoLoi message={dl.message} onThuLai={tai} /> : null}

          {dl?.ok && nhom.length === 0 ? <p className="chuong-thong-bao__empty">Chưa có thông báo nào</p> : null}

          {dl?.ok
            ? nhom.map((n) => (
                <section key={n.nhan} className="chuong-thong-bao__group">
                  <h4>{n.nhan}</h4>
                  <ul>
                    {n.items.map((tb) => (
                      <li key={tb.id} className="chuong-thong-bao__card" data-read={tb.da_doc}>
                        <button
                          type="button"
                          role="menuitem"
                          className="chuong-thong-bao__open"
                          onClick={() => moThongBao(tb)}
                        >
                          <strong>{tb.tieu_de}</strong>
                          <span>{tb.noi_dung}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ))
            : null}
        </div>
      ) : null}
    </div>
  )
}
