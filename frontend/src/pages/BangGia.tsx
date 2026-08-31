import { useState } from 'react';
import { Link } from 'react-router-dom';
import { IconDaXong } from '../brand/icons';
import { HoiDapGia } from '../components/bang-gia/HoiDapGia';
import './trang-moi.css';

/**
 * `/bang-gia` — mode Persuade (BUILD-SPEC §9.7).
 *
 * PHÁN QUYẾT ĐIỀU PHỐI, đọc trước khi sửa số: giá và nội dung gói ở đây là
 * **dự kiến, chưa chốt**. `499.000 ₫/tháng` cùng các hạn mức trong spec là ví
 * dụ định dạng, không phải giá đã quyết. Một trang giá sai còn tệ hơn không có
 * trang giá — nên dòng "Giá dự kiến, chưa áp dụng" nằm NGAY ĐẦU TRANG, thấy
 * được, không giấu xuống chân trang.
 *
 * Kèm theo đó, mỗi tính năng mang một cờ `daCo` nói rõ nó **đang chạy hôm nay**
 * hay **chưa có**. Đây không phải chi tiết trang trí: phần lớn nội dung gói
 * trong spec (hạn mức, nhiều người dùng, phân quyền, xuất Word/PDF, theo dõi
 * hiệu lực, thư viện biểu mẫu của tổ chức) chưa tồn tại, và một dự án tồn tại
 * để chống khẳng định không kiểm chứng được thì không được bán một danh sách
 * tính năng chưa kiểm chứng được. Cờ này biến trang giá thành một bản đồ năng
 * lực trung thực thay vì một tờ hứa.
 *
 * BỎ so với spec, kèm lý do:
 *   - "Cam kết SLA" — một cam kết chất lượng dịch vụ có hệ quả pháp lý, và
 *     `/mien-tru` (đã phát hành) nói ngược lại: KLAW không có đội hỗ trợ hay
 *     cam kết chất lượng dịch vụ nào. §14.4 cấm mọi câu ngụ ý KLAW chịu trách
 *     nhiệm pháp lý.
 *   - Ribbon "Phổ biến nhất" — một khẳng định về mức độ phổ biến trong khi
 *     chưa có người dùng nào. Đổi thành nhãn mô tả đối tượng.
 *   - "Tra cứu không giới hạn" đứng cạnh "50 lượt hỏi AI/tháng" — ở KLAW một
 *     lượt tra cứu CHÍNH LÀ một lượt gọi mô hình, nên hai dòng đó phủ định
 *     nhau. Gộp thành một hạn mức duy nhất.
 */

interface TinhNang {
  nhan: string;
  /** true = đang chạy hôm nay. false = chưa có, nằm trong kế hoạch. */
  daCo: boolean;
}

interface Goi {
  ten: string;
  doiTuong: string;
  /** Giá dự kiến theo tháng. `null` = chưa có số nào được chốt. */
  giaThang: number | null;
  /** Giá dự kiến theo tháng khi trả năm — spec nêu "Tiết kiệm 20%". */
  giaThangTraNam: number | null;
  /** Dùng khi `giaThang` là null. */
  thayGia: string;
  nhanNoiBat: string | null;
  gomGoiTruoc: string | null;
  tinhNang: TinhNang[];
}

const CAC_GOI: Goi[] = [
  {
    ten: 'Cá nhân',
    doiTuong: 'Luật sư và chuyên viên độc lập',
    // 499.000 là con số spec dùng làm ví dụ định dạng. Giá trả năm suy ra từ
    // chính "Tiết kiệm 20%" của spec (499.000 × 0,8 ≈ 399.000) — phép tính,
    // không phải một con số mới bịa thêm.
    giaThang: 499_000,
    giaThangTraNam: 399_000,
    thayGia: '',
    nhanNoiBat: null,
    gomGoiTruoc: null,
    tinhNang: [
      { nhan: 'Tra cứu có trích dẫn tới cấp Điều, Khoản, Điểm', daCo: true },
      { nhan: 'Nhãn hiệu lực trên từng trích dẫn, nêu đích danh văn bản thay thế', daCo: true },
      { nhan: 'Soạn thảo hợp đồng lao động, nội quy lao động, quyết định kỷ luật', daCo: true },
      { nhan: 'Soát văn bản có sẵn, mỗi phát hiện neo vào một điều luật', daCo: true },
      { nhan: '50 lượt tra cứu mỗi tháng', daCo: false },
      { nhan: '10 bản thảo mỗi tháng', daCo: false },
      { nhan: 'Xuất bản thảo ra Word và PDF', daCo: false },
    ],
  },
  {
    ten: 'Doanh nghiệp',
    doiTuong: 'Doanh nghiệp vừa và nhỏ',
    giaThang: null,
    giaThangTraNam: null,
    thayGia: 'Đang chốt giá',
    nhanNoiBat: 'Dành cho đội nhóm',
    gomGoiTruoc: 'Gồm mọi tính năng gói Cá nhân, cộng thêm:',
    tinhNang: [
      { nhan: '5 người dùng trong một tổ chức', daCo: false },
      { nhan: '500 lượt tra cứu mỗi tháng', daCo: false },
      { nhan: 'Bản thảo không giới hạn', daCo: false },
      { nhan: 'Thư viện biểu mẫu riêng của tổ chức', daCo: false },
      { nhan: 'Theo dõi hiệu lực văn bản đã lưu, báo khi có thay đổi', daCo: false },
      { nhan: 'Hỗ trợ ưu tiên', daCo: false },
    ],
  },
  {
    ten: 'Tổ chức lớn',
    doiTuong: 'Hãng luật, tập đoàn',
    giaThang: null,
    giaThangTraNam: null,
    thayGia: 'Liên hệ báo giá',
    nhanNoiBat: null,
    gomGoiTruoc: 'Gồm mọi tính năng gói Doanh nghiệp, cộng thêm:',
    tinhNang: [
      { nhan: 'Không giới hạn người dùng', daCo: false },
      { nhan: 'Tích hợp vào hệ thống nội bộ qua API', daCo: false },
      { nhan: 'Triển khai trên hạ tầng riêng của tổ chức', daCo: false },
      { nhan: 'Quản trị phân quyền theo vai trò', daCo: false },
      { nhan: 'Đào tạo và hỗ trợ chuyên trách', daCo: false },
    ],
  },
];

type ChuKy = 'thang' | 'nam';

function tienVN(dong: number): string {
  return dong.toLocaleString('vi-VN');
}

/** Dấu tích = đang chạy hôm nay; chữ "dự kiến" = chưa có. Trạng thái nói bằng
 *  HÌNH và CHỮ, không bao giờ chỉ bằng màu (DESIGN.md). */
function DongTinhNang({ mot }: { mot: TinhNang }) {
  return (
    <li className="flex items-start gap-2.5">
      {mot.daCo ? (
        <span className="mt-0.5 shrink-0 text-den-sang">
          <IconDaXong size={17} />
          <span className="sr-only">Đang chạy hôm nay: </span>
        </span>
      ) : (
        <span
          aria-hidden="true"
          className="mt-2 size-1.5 shrink-0 rounded-tron"
          style={{ background: 'var(--xam-cho)' }}
        />
      )}
      <span className="mat-doc max-w-none text-[0.9375rem] text-phim">
        {mot.nhan}
        {!mot.daCo && (
          <span
            className="ms-2 rounded-nho px-1.5 py-0.5 align-middle text-[0.75rem] whitespace-nowrap"
            style={{ background: 'var(--nen)', color: 'var(--xam-cho)' }}
          >
            dự kiến
          </span>
        )}
      </span>
    </li>
  );
}

function TheGoi({ goi, chuKy }: { goi: Goi; chuKy: ChuKy }) {
  const gia = chuKy === 'nam' ? goi.giaThangTraNam : goi.giaThang;

  return (
    <li
      className="tm-len flex flex-col rounded-lon border p-5"
      style={{
        background: 'var(--nen-cao)',
        borderColor: goi.nhanNoiBat === null ? 'var(--vien)' : 'var(--den-sang)',
      }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="mat-doc m-0 max-w-none text-lg font-medium text-phim">{goi.ten}</h3>
        {goi.nhanNoiBat !== null && (
          <span
            className="rounded-tron px-2.5 py-0.5 text-[0.75rem] font-medium"
            style={{ background: 'var(--nen)', color: 'var(--den-sang)' }}
          >
            {goi.nhanNoiBat}
          </span>
        )}
      </div>
      <p className="m-0 mt-1 text-[0.8125rem] leading-5 text-muc-nhat">{goi.doiTuong}</p>

      <p className="m-0 mt-4">
        {gia === null ? (
          <span className="mat-doc max-w-none text-xl font-medium text-phim">{goi.thayGia}</span>
        ) : (
          <>
            <span className="font-dia-chi text-2xl font-medium text-phim">{tienVN(gia)} ₫</span>
            <span className="text-[0.875rem] text-muc-nhat">/tháng</span>
            {chuKy === 'nam' && (
              <span className="mt-1 block text-[0.8125rem] leading-5 text-muc-nhat">
                khi trả trước một năm
              </span>
            )}
          </>
        )}
      </p>

      {goi.gomGoiTruoc !== null && (
        <p className="mat-doc mt-4 mb-0 max-w-none text-[0.875rem] text-muc-nhat">
          {goi.gomGoiTruoc}
        </p>
      )}
      <ul className="mt-3 flex list-none flex-col gap-2.5 p-0">
        {goi.tinhNang.map((mot) => (
          <DongTinhNang key={mot.nhan} mot={mot} />
        ))}
      </ul>

      <Link
        to="/tra-cuu"
        className="mt-6 inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center justify-center rounded-vua px-4 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
      >
        Dùng KLAW ngay
      </Link>
      {/* CTA nói đúng thứ có thật hôm nay: KLAW mở, không cần tài khoản, không
          thu phí. Một nút "Mua gói này" dẫn tới cổng thanh toán không tồn tại
          sẽ là nút giả (§14.2). */}
      <p className="m-0 mt-2 text-[0.8125rem] leading-5 text-muc-nhat">
        Miễn phí, không cần tài khoản — gói trả phí chưa mở bán.
      </p>
    </li>
  );
}

export default function BangGia() {
  const [chuKy, datChuKy] = useState<ChuKy>('thang');

  return (
    <div className="mx-auto w-full max-w-[64rem] px-4 py-10">
      <h1 className="mat-doc text-2xl font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4 md:text-3xl">
        Bảng giá
      </h1>
      <p className="mat-doc mt-3 text-phim">
        Ba gói dự kiến cho ba nhóm người dùng khác nhau. Trang này nói rõ tính năng nào{' '}
        <em>đang chạy hôm nay</em> và tính năng nào <em>chưa có</em> — thay vì trộn cả hai vào một
        danh sách dấu tích.
      </p>

      {/* ── Giá chưa chốt: nói ở đây, không giấu xuống chân trang ────────── */}
      <div
        role="note"
        className="mt-6 rounded-lon border-s-4 p-4"
        style={{ background: 'var(--nen-cao)', borderColor: 'var(--den-sang)' }}
      >
        <p className="mat-doc m-0 font-medium text-phim">Giá dự kiến, chưa áp dụng.</p>
        <p className="mat-doc mt-2 mb-0 text-[0.9375rem] text-phim">
          KLAW chưa mở đăng ký và chưa nhận thanh toán. Các con số và hạn mức dưới đây là dự kiến,
          sẽ chốt và công bố trước khi mở bán. Giá hiển thị chưa bao gồm thuế GTGT.
        </p>
      </div>

      {/* ── Chu kỳ thanh toán ────────────────────────────────────────────── */}
      <fieldset className="mt-8 border-0 p-0">
        <legend className="text-[0.8125rem] leading-5 text-muc-nhat">Chu kỳ thanh toán</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {(
            [
              ['thang', 'Theo tháng'],
              ['nam', 'Theo năm — tiết kiệm 20%'],
            ] as [ChuKy, string][]
          ).map(([ma, nhan]) => (
            <label
              key={ma}
              className="flex min-h-[var(--vung-cham-toi-thieu)] cursor-pointer items-center gap-2.5 rounded-vua border px-4 text-[0.9375rem]"
              style={{
                borderColor: chuKy === ma ? 'var(--den-sang)' : 'var(--vien)',
                background: 'var(--nen-cao)',
                color: chuKy === ma ? 'var(--den-sang)' : 'var(--phim)',
              }}
            >
              <input
                type="radio"
                name="chu-ky"
                value={ma}
                checked={chuKy === ma}
                onChange={() => datChuKy(ma)}
                className="size-4 accent-[var(--den-sang)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
              />
              {nhan}
            </label>
          ))}
        </div>
      </fieldset>

      <ul className="mt-6 grid list-none grid-cols-1 gap-4 p-0 lg:grid-cols-3">
        {CAC_GOI.map((goi) => (
          <TheGoi key={goi.ten} goi={goi} chuKy={chuKy} />
        ))}
      </ul>

      <p className="mat-doc mt-6 text-[0.875rem] text-muc-nhat">
        Dấu tích brass: tính năng đang chạy hôm nay, dùng được ngay. Nhãn{' '}
        <span style={{ color: 'var(--xam-cho)' }}>dự kiến</span>: chưa có, nằm trong kế hoạch. Chưa
        có cổng thanh toán, chưa có chính sách hoàn tiền để công bố — điều khoản thanh toán sẽ ra
        cùng lúc với giá chính thức.
      </p>
      <p className="mat-doc mt-3 text-[0.875rem] text-muc-nhat">
        Biểu mẫu tạo tài khoản đã dựng sẵn tại{' '}
        <Link
          to="/dang-ky"
          className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
          trang đăng ký
        </Link>{' '}
        và sẽ hoạt động khi backend xác thực được nối.
      </p>

      {/* ── Câu hỏi thường gặp (§15.6) ───────────────────────────────────── */}
      <section className="mt-14" aria-labelledby="hoi-dap">
        <h2 id="hoi-dap" className="tm-len mat-doc text-xl font-medium text-phim md:text-2xl">
          Câu hỏi thường gặp
        </h2>
        <HoiDapGia />
      </section>

      <p className="mat-doc mt-10 text-[0.875rem] text-muc-nhat">
        KLAW là công cụ hỗ trợ tra cứu và soạn thảo. Nội dung do KLAW tạo ra không phải ý kiến tư
        vấn pháp lý và không thay thế tư vấn của luật sư có thẩm quyền —{' '}
        <Link
          to="/mien-tru"
          className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
          đọc miễn trừ trách nhiệm đầy đủ
        </Link>
        .
      </p>
    </div>
  );
}
