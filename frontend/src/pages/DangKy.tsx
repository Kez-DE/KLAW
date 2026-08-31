import { useState } from 'react';
import { NutBrass } from '../components/NutBrass';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { BaoLoi } from '../components/BaoLoi';
import { BangXong } from '../components/xac-thuc/BangXong';
import { TruongNhap } from '../components/xac-thuc/TruongNhap';
import { KhoiOAuth, VoXacThuc } from '../components/xac-thuc/VoXacThuc';
import {
  LOI,
  NHAN_DO_MANH,
  doMatKhau,
  loiEmail,
  loiHoTen,
  loiMatKhau,
  loiVaiTro,
  useGuiTam,
} from '../components/xac-thuc/xacThuc';
import './trang-moi.css';

/**
 * `/dang-ky` — mode Persuade, chia 45/55 (BUILD-SPEC §9.2 · copy §15.4).
 *
 * HAI RÀNG BUỘC KHÔNG ĐƯỢC NỚI, cả hai là pháp lý chứ không phải giao diện:
 *
 *   1. Ô đồng ý xử lý dữ liệu cá nhân KHÔNG tick sẵn, và nút gửi bị vô hiệu
 *      tới khi nó được tick (§14.3 — Luật Bảo vệ dữ liệu cá nhân 2025 và Nghị
 *      định 356/2025/NĐ-CP). Sự đồng ý phải là một hành động của người dùng;
 *      một ô đã tick sẵn không phải là sự đồng ý.
 *   2. Không có xác thực, không token giả, không cờ `isLoggedIn`, không log dữ
 *      liệu biểu mẫu ra console (§14.2 · §14.3). Người dùng nhập họ tên, email
 *      công việc và mật khẩu vào đây.
 */

const VAI_TRO = [
  'Luật sư',
  'Pháp chế nội bộ',
  'Nhân sự',
  'Kế toán',
  'Chủ doanh nghiệp',
  'Khác',
];

/** Thanh đo 4 đoạn. Chỉ dấu, KHÔNG phải cổng chặn — `loiMatKhau` mới chặn. */
function ThanhDoMatKhau({ diem }: { diem: number }) {
  return (
    <div className="mt-2">
      <div className="flex gap-1.5" aria-hidden="true">
        {[1, 2, 3, 4].map((doan) => (
          <span
            key={doan}
            className="h-1 flex-1 rounded-tron transition-colors duration-[var(--thoi-luong-nhanh)] ease-chuan"
            style={{
              background:
                doan <= diem
                  ? 'var(--den-sang)'
                  : 'color-mix(in srgb, var(--muc-nhat) 30%, transparent)',
            }}
          />
        ))}
      </div>
      {/* Độ mạnh nói bằng CHỮ, không chỉ bằng số đoạn được tô: bốn vệt sáng
          không đọc được với người không phân biệt được chúng. */}
      <p className="mt-1.5 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
        {diem === 0 ? 'Tối thiểu 8 ký tự, gồm chữ và số.' : `Độ mạnh: ${NHAN_DO_MANH[diem]}.`}
      </p>
    </div>
  );
}

interface LoiBieuMau {
  hoTen: string | null;
  email: string | null;
  vaiTro: string | null;
  matKhau: string | null;
}

const KHONG_LOI: LoiBieuMau = { hoTen: null, email: null, vaiTro: null, matKhau: null };

const ID_THEO_LOI: [keyof LoiBieuMau, string][] = [
  ['hoTen', 'dk-ho-ten'],
  ['email', 'dk-email'],
  ['vaiTro', 'dk-vai-tro'],
  ['matKhau', 'dk-mat-khau'],
];

export default function DangKy() {
  const [hoTen, datHoTen] = useState('');
  const [email, datEmail] = useState('');
  const [toChuc, datToChuc] = useState('');
  const [vaiTro, datVaiTro] = useState('');
  const [matKhau, datMatKhau] = useState('');
  const [dongY, datDongY] = useState(false); // KHÔNG tick sẵn — §14.3
  const [loi, datLoi] = useState<LoiBieuMau>(KHONG_LOI);
  const { trangThai, gui, datLai } = useGuiTam();

  const dangGui = trangThai === 'dang-gui';
  const xoaLoi = (truong: keyof LoiBieuMau) => {
    if (loi[truong] !== null) datLoi((cu) => ({ ...cu, [truong]: null }));
  };

  const napGui = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    const moi: LoiBieuMau = {
      hoTen: loiHoTen(hoTen),
      email: loiEmail(email),
      vaiTro: loiVaiTro(vaiTro),
      matKhau: loiMatKhau(matKhau),
    };
    datLoi(moi);

    const sai = ID_THEO_LOI.find(([truong]) => moi[truong] !== null);
    if (sai !== undefined) {
      document.getElementById(sai[1])?.focus();
      return;
    }
    gui();
  };

  return (
    <VoXacThuc
      tieuDe="Tạo tài khoản KLAW"
      phuDe={
        <>
          Đã có tài khoản?{' '}
          <Link
            to="/dang-nhap"
            className="text-den-sang underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
            Đăng nhập
          </Link>
        </>
      }
        >
      {trangThai === 'xong' ? (
        <BangXong cau="Đã nhận biểu mẫu đăng ký của bạn." />
      ) : (
        <>
          <KhoiOAuth hanhDong="đăng ký" />

          <form onSubmit={napGui} noValidate className="mt-6 flex flex-col gap-4">
            <TruongNhap
              id="dk-ho-ten"
              nhan="Họ và tên"
              giaTri={hoTen}
              doiGiaTri={(gia) => {
                datHoTen(gia);
                xoaLoi('hoTen');
              }}
              loi={loi.hoTen}
              batBuoc
              tuDong="name"
            />
            <TruongNhap
              id="dk-email"
              nhan="Email công việc"
              loai="email"
              giaTri={email}
              doiGiaTri={(gia) => {
                datEmail(gia);
                xoaLoi('email');
              }}
              loi={loi.email}
              batBuoc
              tuDong="email"
            />
            <TruongNhap
              id="dk-to-chuc"
              nhan="Tên tổ chức"
              moTa="Không bắt buộc"
              giaTri={toChuc}
              doiGiaTri={datToChuc}
              tuDong="organization"
            />

            <div>
              <label
                htmlFor="dk-vai-tro"
                className="mat-doc block max-w-none text-[0.9375rem] font-medium text-phim"
        >
                Vai trò
                <span aria-hidden="true" className="ms-1 text-den-sang">
                  *
                </span>
              </label>
              <select
                id="dk-vai-tro"
                name="dk-vai-tro"
                value={vaiTro}
                onChange={(su) => {
                  datVaiTro(su.target.value);
                  xoaLoi('vaiTro');
                }}
                required
                aria-invalid={loi.vaiTro !== null}
                aria-describedby={loi.vaiTro !== null ? 'dk-vai-tro-loi' : undefined}
                className="mat-doc min-h-[var(--vung-cham-toi-thieu)] w-full max-w-none rounded-vua border bg-nen p-3 text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
                style={{
                  borderColor:
                    loi.vaiTro === null
                      ? 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)'
                      : 'var(--do-thay)',
                }}
        >
                <option value="">— Chọn vai trò —</option>
                {VAI_TRO.map((mot) => (
                  <option key={mot} value={mot}>
                    {mot}
                  </option>
                ))}
              </select>
              {loi.vaiTro !== null && (
                <p
                  id="dk-vai-tro-loi"
                  className="mt-1.5 mb-0 text-[0.8125rem] leading-5 text-do-thay"
        >
                  {loi.vaiTro}
                </p>
              )}
            </div>

            <TruongNhap
              id="dk-mat-khau"
              nhan="Mật khẩu"
              loai="password"
              giaTri={matKhau}
              doiGiaTri={(gia) => {
                datMatKhau(gia);
                xoaLoi('matKhau');
              }}
              loi={loi.matKhau}
              batBuoc
              tuDong="new-password"
        >
              <ThanhDoMatKhau diem={doMatKhau(matKhau)} />
            </TruongNhap>

            {/* ── Đồng ý xử lý dữ liệu cá nhân — §14.3 ──────────────────── */}
            <div className="rounded-vua border p-3" style={{ borderColor: 'var(--vien)' }}>
              <label className="flex cursor-pointer items-start gap-2.5 text-[0.9375rem] leading-6 text-phim">
                <input
                  type="checkbox"
                  name="dk-dong-y"
                  checked={dongY}
                  onChange={(su) => datDongY(su.target.checked)}
                  aria-describedby="dk-dong-y-ghi-chu"
                  className="mt-1.5 size-4 shrink-0 accent-[var(--den-sang)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
                />
                <span>
                  Tôi đồng ý cho KLAW xử lý dữ liệu cá nhân của tôi theo Chính sách bảo vệ dữ liệu
                  cá nhân.
                </span>
              </label>
              <p
                id="dk-dong-y-ghi-chu"
                className="mt-2 mb-0 text-[0.8125rem] leading-5 text-muc-nhat"
              >
                Chính sách này đang được hoàn thiện; sẽ công bố trước khi KLAW mở đăng ký. Trong lúc
                đó,{' '}
                <Link
                  to="/du-lieu"
                  className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
                >
                  bản kê dữ liệu KLAW xử lý
                </Link>{' '}
                nói rõ hệ thống chạm tới dữ liệu gì, gửi đi đâu, lưu bao lâu — và những gì chưa có.
                Đó là bản kê, không phải chính sách.
              </p>
            </div>

            <NutBrass
              type="submit"
              disabled={!dongY || dangGui}
              aria-busy={dangGui}
              // Vô hiệu tới khi ô đồng ý được tick (§14.3). `disabled` thật,
              // không phải một lớp mờ đi rồi vẫn gửi được.
        >
              {dangGui ? 'Đang xác thực…' : 'Tạo tài khoản'}
            </NutBrass>
            {!dongY && (
              <p className="m-0 text-[0.8125rem] leading-5 text-muc-nhat">
                Cần tick ô đồng ý ở trên trước khi tạo được tài khoản.
              </p>
            )}
          </form>

          {trangThai === 'loi' && (
            <BaoLoi loi={{ kind: 'network', message: LOI.mang }} onThuLai={datLai} />
          )}

          <p className="mt-6 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
            KLAW là công cụ tra cứu và soạn thảo, không phải tư vấn pháp lý và không thay thế luật
            sư —{' '}
            <Link
              to="/mien-tru"
              className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
              đọc giới hạn đầy đủ
            </Link>
            .
          </p>
        </>
      )}
    </VoXacThuc>
  );
}
