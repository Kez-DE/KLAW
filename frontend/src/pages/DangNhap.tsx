import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { BaoLoi } from '../components/BaoLoi';
import { BangXong } from '../components/xac-thuc/BangXong';
import { TruongNhap } from '../components/xac-thuc/TruongNhap';
import { KhoiOAuth, VoXacThuc } from '../components/xac-thuc/VoXacThuc';
import { LOI, loiEmail, useGuiTam } from '../components/xac-thuc/xacThuc';
import './trang-moi.css';

/**
 * `/dang-nhap` — mode Persuade, chia 45/55 (BUILD-SPEC §9.2 · copy §15.4).
 *
 * KHÔNG CÓ XÁC THỰC Ở ĐÂY, và đó là yêu cầu, không phải việc còn thiếu
 * (§14.2): không token giả, không cờ `isLoggedIn`, không so mật khẩu, không
 * ghi gì vào localStorage, và không log dữ liệu biểu mẫu ra console (§14.3).
 * Toàn bộ phần chờ backend nằm trong `useGuiTam`, mang đúng một
 * `TODO(backend)`.
 */
export default function DangNhap() {
  const [email, datEmail] = useState('');
  const [matKhau, datMatKhau] = useState('');
  const [ghiNho, datGhiNho] = useState(false);
  const [loi, datLoi] = useState<{ email: string | null; matKhau: string | null }>({
    email: null,
    matKhau: null,
  });
  const { trangThai, gui, datLai } = useGuiTam();

  const dangGui = trangThai === 'dang-gui';

  const napGui = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    const lEmail = loiEmail(email);
    const lMatKhau = matKhau === '' ? LOI.matKhauTrong : null;
    datLoi({ email: lEmail, matKhau: lMatKhau });

    if (lEmail !== null || lMatKhau !== null) {
      // Đưa tiêu điểm về trường sai đầu tiên: thông báo lỗi nằm trong
      // `aria-describedby` của chính ô nhập, nên đứng ở đó là nghe được nó.
      document.getElementById(lEmail !== null ? 'dn-email' : 'dn-mat-khau')?.focus();
      return;
    }
    gui();
  };

  return (
    <VoXacThuc
      tieuDe="Đăng nhập vào KLAW"
      phuDe={
        <>
          Chưa có tài khoản?{' '}
          <Link
            to="/dang-ky"
            className="text-den-sang underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          >
            Đăng ký miễn phí
          </Link>
        </>
      }
    >
      {trangThai === 'xong' ? (
        <BangXong cau="Đã nhận biểu mẫu đăng nhập của bạn." />
      ) : (
        <>
          <KhoiOAuth hanhDong="đăng nhập" />

          <form onSubmit={napGui} noValidate className="mt-6 flex flex-col gap-4">
            <TruongNhap
              id="dn-email"
              nhan="Email công việc"
              loai="email"
              giaTri={email}
              doiGiaTri={(gia) => {
                datEmail(gia);
                if (loi.email !== null) datLoi((cu) => ({ ...cu, email: null }));
              }}
              loi={loi.email}
              batBuoc
              tuDong="email"
            />
            <TruongNhap
              id="dn-mat-khau"
              nhan="Mật khẩu"
              loai="password"
              giaTri={matKhau}
              doiGiaTri={(gia) => {
                datMatKhau(gia);
                if (loi.matKhau !== null) datLoi((cu) => ({ ...cu, matKhau: null }));
              }}
              loi={loi.matKhau}
              batBuoc
              tuDong="current-password"
            />

            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex min-h-[var(--vung-cham-toi-thieu)] cursor-pointer items-center gap-2.5 text-[0.9375rem] text-phim">
                <input
                  type="checkbox"
                  name="dn-ghi-nho"
                  checked={ghiNho}
                  onChange={(su) => datGhiNho(su.target.checked)}
                  className="size-4 accent-[var(--den-sang)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
                />
                Ghi nhớ đăng nhập
              </label>

              {/* `<details>` gốc thay cho một liên kết tới trang chưa tồn tại:
                  một liên kết chết còn tệ hơn một câu nói thật. */}
              <details className="tm-hoi">
                <summary className="flex min-h-[var(--vung-cham-toi-thieu)] items-center text-[0.9375rem] text-den-sang underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang">
                  Quên mật khẩu?
                </summary>
                <p className="mt-2 mb-0 max-w-[32ch] text-[0.8125rem] leading-5 text-muc-nhat">
                  Đặt lại mật khẩu sẽ có cùng lúc với backend xác thực. Hiện KLAW dùng được không
                  cần tài khoản.
                </p>
              </details>
            </div>

            <button
              type="submit"
              disabled={dangGui}
              aria-busy={dangGui}
              className="min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:cursor-wait disabled:opacity-70"
              style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
            >
              {dangGui ? 'Đang xác thực…' : 'Đăng nhập'}
            </button>
          </form>

          {/* Lỗi hệ thống KHÔNG mượn `--do-thay`: đỏ trong bảng màu này dành
              riêng cho luật đã bị thay thế (DESIGN.md). Dùng lại `BaoLoi` đã
              có, để một lỗi mạng ở đây trông đúng như một lỗi mạng ở mọi màn
              hình khác. */}
          {trangThai === 'loi' && (
            <BaoLoi loi={{ kind: 'network', message: LOI.mang }} onThuLai={datLai} />
          )}

          <p className="mt-6 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
            Điều khoản sử dụng và Chính sách bảo vệ dữ liệu cá nhân đang được hoàn thiện, sẽ công bố
            trước khi KLAW mở đăng ký. Trong lúc đó,{' '}
            <Link
              to="/mien-tru"
              className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            >
              Miễn trừ trách nhiệm
            </Link>{' '}
            nói rõ giới hạn của hệ thống.
          </p>
        </>
      )}
    </VoXacThuc>
  );
}
