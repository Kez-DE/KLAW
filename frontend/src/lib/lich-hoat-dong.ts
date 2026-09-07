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

/** Tứ phân vị của các giá trị dương — ranh giới bốn mức tô đậm dần. */
export function tuPhanVi(duongTinh: number[]): readonly [number, number, number] {
  const s = [...duongTinh].sort((a, b) => a - b);
  const cuoi = s.length - 1;
  const tai = (p: number) => s[Math.max(0, Math.floor(cuoi * p))] ?? 0;
  return [tai(0.25), tai(0.5), tai(0.75)];
}

/**
 * Mức tô cho một ô, 0 (không hoạt động) tới 4 (tứ phân vị cao nhất).
 *
 * So sánh "≥" theo thứ tự GIẢM DẦN, không phải "≤" tăng dần: giá trị lớn
 * nhất luôn chạm mức 4 — kể cả khi mọi ngày có `so_luot` bằng nhau (khi đó
 * q1=q2=q3=chính giá trị đó). Bản "≤" trước đây bỏ MỌI giá trị dương vào mức
 * 1 trong ca này, khiến "hoạt động đều mỗi ngày" trông nhạt như "vừa mới có
 * hoạt động một lượt" — cùng dữ liệu đầu vào đáng lẽ phải trông "đầy", không
 * "vừa chạm đáy".
 *
 * `ponytail`: tứ phân vị tính trên mẫu nhỏ (365 ngày hiển thị, thường ít ngày
 * có hoạt động thật) — một ngày đột biến giữa nhiều ngày thấp vẫn có thể kéo
 * tứ phân vị xuống thấp và tô nhầm cả cụm ngày thấp lên mức cao. Trần biết
 * trước của cách tính đơn giản này; nâng cấp khi cần là đổi sang bách phân vị
 * trên toàn bộ lịch sử hoạt động thay vì chỉ 365 ngày đang hiển thị.
 */
export function mucCua(
  soLuot: number,
  [q1, q2, q3]: readonly [number, number, number],
): 0 | 1 | 2 | 3 | 4 {
  if (soLuot <= 0) return 0;
  if (soLuot >= q3) return 4;
  if (soLuot >= q2) return 3;
  if (soLuot >= q1) return 2;
  return 1;
}

/**
 * Dựng 371 ô (53 cột × 7 hàng, đệm đầu/cuối) và nhãn tháng cho 365 ngày lùi
 * từ `homNay`. Entry của `hoatDong` có `ngay` NGOÀI cửa sổ 365 ngày bị BỎ
 * HẲN — không chỉ không hiện lên lưới, mà cũng không được tính vào tứ phân
 * vị: một ngày đột biến bên ngoài cửa sổ hiển thị không được phép kéo lệch
 * màu của 365 ngày đang hiện ra.
 */
export function dungLuoiHoatDong(hoatDong: HoatDongNgay[], homNay: Date): LuoiHoatDong {
  const mocHomNay = Date.UTC(homNay.getFullYear(), homNay.getMonth(), homNay.getDate());
  const ngayDau = chuoiNgay(mocHomNay - (SO_NGAY - 1) * MS_NGAY);
  const ngayCuoi = chuoiNgay(mocHomNay);
  const trongCuaSo = hoatDong.filter((h) => h.ngay >= ngayDau && h.ngay <= ngayCuoi);

  const theoNgay = new Map(trongCuaSo.map((h) => [h.ngay, h.so_luot]));
  const nguong = tuPhanVi(trongCuaSo.map((h) => h.so_luot).filter((n) => n > 0));

  const oNgay: ONgay[] = Array.from({ length: SO_NGAY }, (_, i) => {
    const t = mocHomNay - (SO_NGAY - 1 - i) * MS_NGAY;
    const ngay = chuoiNgay(t);
    const soLuot = theoNgay.get(ngay) ?? 0;
    return { t, ngay, soLuot, muc: mucCua(soLuot, nguong) };
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
