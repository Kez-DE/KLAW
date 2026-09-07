/**
 * Toán ngày và tô mức cho lịch hoạt động 365 ngày
 * (`components/tai-khoan/LichHoatDong.tsx`). Tách khỏi component để
 * `scripts/kiem-lich-hoat-dong.ts` kiểm được bằng `node:assert` thuần — không
 * cần dựng DOM cho một logic không có gì thuộc về DOM.
 *
 * Toàn bộ mốc ngày dựng bằng `Date.UTC`/`getUTC*`, KHÔNG đi qua giờ máy: chuỗi
 * `ngay` của máy chủ chỉ được so khớp bằng so sánh CHUỖI (`Map<string,
 * number>` và so sánh ISO trực tiếp cho biên cửa sổ), không bao giờ bị đưa
 * qua `new Date(...)` rồi đọc lại theo múi giờ trình duyệt.
 *
 * `homNay` là THAM SỐ, không tự đọc `new Date()` bên trong: component truyền
 * `new Date()` mỗi lần dựng (giữ đúng "hôm nay" theo giờ máy người xem), còn
 * `kiem-lich-hoat-dong.ts` truyền một mốc cố định để phép kiểm không phụ
 * thuộc đồng hồ máy chạy kiểm.
 */

export interface HoatDongNgay {
  ngay: string;
  so_luot: number;
}

export interface ONgay {
  t: number;
  ngay: string;
  soLuot: number;
  muc: 0 | 1 | 2 | 3 | 4;
}

export interface LuoiHoatDong {
  /** 53×7 = 371 ô, thứ tự CỘT rồi HÀNG — khớp CSS `grid-flow-col grid-rows-7`. */
  oLuoi: (ONgay | null)[];
  /** Nhãn tháng, một phần tử mỗi cột; rỗng trừ cột đầu tiên chạm mỗi tháng. */
  nhanThang: string[];
}

export const SO_TUAN = 53;
export const SO_NGAY = SO_TUAN * 7 - 6; // 365 — 53 cột chứa đúng 365 ô thật + 6 ô đệm
export const MS_NGAY = 86_400_000;

/** Tên tháng viết tắt tiếng Việt, dựng một lần — không lệ thuộc múi giờ trình duyệt. */
const THANG_NHAN = Array.from({ length: 12 }, (_, m) =>
  new Intl.DateTimeFormat("vi-VN", { month: "short", timeZone: "UTC" }).format(
    new Date(Date.UTC(2000, m, 1)),
  ),
);

function chuoiNgay(t: number): string {
  const d = new Date(t);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`;
}

/** Thứ Hai = 0 .. Chủ nhật = 6, suy từ `getUTCDay()` (Chủ nhật = 0). */
function thuTrongTuan(t: number): number {
  return (new Date(t).getUTCDay() + 6) % 7;
}

/** Giá trị dương KHÔNG TRÙNG trong cửa sổ, sắp tăng dần — nền xếp hạng cho `mucCua`. */
export function hangDuongTinh(gtri: number[]): number[] {
  return [...new Set(gtri.filter((n) => n > 0))].sort((a, b) => a - b);
}

/**
 * Mức tô cho một ô, 0 (không hoạt động) tới 4 (giá trị dương lớn nhất trong
 * cửa sổ).
 *
 * XẾP HẠNG giữa các giá trị dương KHÔNG TRÙNG (`d` từ `hangDuongTinh`), không
 * phải ngưỡng theo GIÁ TRỊ (tứ phân vị cũ). Ngưỡng giá trị tô SAI khi dữ liệu
 * lệch: 10 ngày `so_luot=1` cộng 1 ngày `so_luot=50` có tứ phân vị cùng sụp về
 * 1 (`q1=q2=q3=1`), nên MỌI ngày dương — kể cả 10 ngày yên ắng lẫn ngày đột
 * biến — cùng chạm mức 4, không phân biệt được. Xếp hạng theo THỨ TỰ giữa các
 * giá trị (không phải khoảng cách giữa chúng) không mắc lỗi đó: giá trị nhỏ
 * nhất trong cửa sổ luôn là mức 1, giá trị lớn nhất luôn là mức 4, bất kể
 * chênh lệch giữa chúng lớn hay nhỏ.
 */
export function mucCua(soLuot: number, d: readonly number[]): 0 | 1 | 2 | 3 | 4 {
  if (soLuot <= 0) return 0;
  if (d.length <= 1) return 4;
  const i = d.indexOf(soLuot);
  if (i === -1) return 4;
  return (1 + Math.round((i * 3) / (d.length - 1))) as 1 | 2 | 3 | 4;
}

/**
 * Dựng 371 ô (53 cột × 7 hàng, đệm đầu/cuối) và nhãn tháng cho 365 ngày lùi
 * từ `homNay`. Entry của `hoatDong` có `ngay` NGOÀI cửa sổ 365 ngày bị BỎ
 * HẲN — không chỉ không hiện lên lưới, mà cũng không được tính vào xếp hạng:
 * một ngày đột biến bên ngoài cửa sổ hiển thị không được phép kéo lệch màu
 * của 365 ngày đang hiện ra.
 */
export function dungLuoiHoatDong(hoatDong: HoatDongNgay[], homNay: Date): LuoiHoatDong {
  const mocHomNay = Date.UTC(homNay.getFullYear(), homNay.getMonth(), homNay.getDate());
  const ngayDau = chuoiNgay(mocHomNay - (SO_NGAY - 1) * MS_NGAY);
  const ngayCuoi = chuoiNgay(mocHomNay);
  const trongCuaSo = hoatDong.filter((h) => h.ngay >= ngayDau && h.ngay <= ngayCuoi);

  const theoNgay = new Map(trongCuaSo.map((h) => [h.ngay, h.so_luot]));
  const hang = hangDuongTinh(trongCuaSo.map((h) => h.so_luot));

  const oNgay: ONgay[] = Array.from({ length: SO_NGAY }, (_, i) => {
    const t = mocHomNay - (SO_NGAY - 1 - i) * MS_NGAY;
    const ngay = chuoiNgay(t);
    const soLuot = theoNgay.get(ngay) ?? 0;
    return { t, ngay, soLuot, muc: mucCua(soLuot, hang) };
  });

  const dauTuan = thuTrongTuan(oNgay[0]!.t);
  const oCuoi = 6 - dauTuan;
  const oLuoi: (ONgay | null)[] = [
    ...Array.from({ length: dauTuan }, () => null),
    ...oNgay,
    ...Array.from({ length: oCuoi }, () => null),
  ];

  const nhanThang: string[] = [];
  let thangTruoc = -1;
  for (let c = 0; c < SO_TUAN; c++) {
    let thang = -1;
    for (let r = 0; r < 7; r++) {
      const o = oLuoi[c * 7 + r];
      if (o !== undefined && o !== null) {
        thang = new Date(o.t).getUTCMonth();
        break;
      }
    }
    nhanThang.push(thang !== thangTruoc ? (THANG_NHAN[thang] ?? "") : "");
    thangTruoc = thang;
  }

  return { oLuoi, nhanThang };
}
