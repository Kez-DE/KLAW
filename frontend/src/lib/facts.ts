import type { FactField } from '../types';

/**
 * Chuyển đổi giữa giá trị ô nhập (luôn là chuỗi) và `facts` mà server chờ,
 * cùng phép nhân hoá tên fact trong thông điệp trả về.
 *
 * Ở đây chứ không trong một trang: `/soan-thao` và `/soat` gửi CÙNG một bộ
 * fact, sinh từ cùng `GET /api/v1/mau/{loai}`. Hai bản sao của cùng phép đổi
 * kiểu sẽ trôi lệch nhau ngay lần thêm một `kieu` mới vào `config/rules.yaml`,
 * và cái lệch đó biểu hiện thành một rule im lặng không được kiểm.
 */

/**
 * Ô trống bị BỎ HẲN khỏi `facts` thay vì gửi chuỗi rỗng: fact vắng mặt là một
 * input hợp lệ — rule engine trả `None` ("không kiểm được"), một kết quả thật
 * và khác hẳn "văn bản sai". Gửi `""` biến nó thành một giá trị sai và nhận 422.
 */
export function dungFacts(
  facts: FactField[],
  giaTri: Record<string, string>,
): Record<string, unknown> {
  const ra: Record<string, unknown> = {};
  for (const truong of facts) {
    const tho = (giaTri[truong.key] ?? '').trim();
    if (truong.kieu === 'bool') {
      ra[truong.key] = tho === 'true';
      continue;
    }
    if (tho === '') continue;
    if (truong.kieu === 'int') {
      ra[truong.key] = Number(tho);
      continue;
    }
    ra[truong.key] = tho;
  }
  return ra;
}

/** Chặn tại biên: một ô số không đọc được thì NÓI RA, không lặng lẽ bỏ đi. */
export function oSoHong(facts: FactField[], giaTri: Record<string, string>): FactField | null {
  for (const truong of facts) {
    if (truong.kieu !== 'int') continue;
    const tho = (giaTri[truong.key] ?? '').trim();
    if (tho !== '' && !Number.isFinite(Number(tho))) return truong;
  }
  return null;
}

/** `key` → `nhan` của mọi trường trong mẫu. Rỗng khi mẫu chưa tải xong. */
export function banNhanFact(facts: FactField[] | null): Record<string, string> {
  const ra: Record<string, string> = {};
  for (const truong of facts ?? []) ra[truong.key] = truong.nhan;
  return ra;
}

/** Tên fact đến từ dữ liệu máy chủ; thoát ký tự đặc biệt trước khi dựng regex. */
function thoatRegex(chuoi: string): string {
  return chuoi.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Đổi tên fact của MÁY thành nhãn NGƯỜI ĐỌC ĐƯỢC trong một thông điệp phát
 * hiện.
 *
 * `src/services/rules.py` ghép tên fact thô vào câu — "không kiểm được: thiếu
 * thoi_gian_thu_viec_ngay, nhom_chuc_danh" — và người dùng không có cách nào
 * biết đó là ô nào để điền. Nhãn thật đã có sẵn ở `facts_meta` của cùng file
 * YAML, đi tới FE qua `GET /api/v1/mau/{loai}`; đây chỉ là ghép hai đầu đó lại.
 *
 * Khớp theo ĐÚNG BẢNG KHOÁ, không theo hình dạng chuỗi. Một quy tắc kiểu
 * "định danh phải có gạch dưới" bỏ sót đúng những khoá một từ như `vung` — đã
 * đo thấy `vung='IV'` lọt nguyên tên máy ra giao diện — và bỏ sót nghĩa là
 * người dùng nhận lại một cái tên không giải mã được. Khoá dài xếp trước để
 * một khoá không nuốt mất phần đầu của khoá khác.
 *
 * Một lượt duy nhất: nhãn tiếng Việt chèn vào không chứa khoá nào nên không có
 * đường thay chồng lên nhau. Mã không có trong bảng thì giữ nguyên — tra bảng,
 * không đoán. Không sửa gì ở `src/**`.
 */
export function nhanHoaFact(thongDiep: string, nhan: Record<string, string>): string {
  const khoa = Object.keys(nhan).sort((mot, hai) => hai.length - mot.length);
  if (khoa.length === 0) return thongDiep;
  const mau = new RegExp(`\\b(?:${khoa.map(thoatRegex).join('|')})\\b`, 'g');
  return thongDiep.replace(mau, (ma) => nhan[ma] ?? ma);
}
