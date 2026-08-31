/**
 * Tự kiểm `src/lib/facts.ts` — phép đổi giữa ô nhập và `facts`, cùng phép
 * nhân hoá tên fact trong thông điệp phát hiện.
 *
 * Hai chỗ sai thì hỏng LẶNG LẼ, không ai thấy:
 *   1. `dungFacts` gửi nhầm một ô trống thành giá trị → rule bị kiểm bằng dữ
 *      liệu bịa, hoặc nhận 422 mà không rõ vì sao.
 *   2. `nhanHoaFact` nuốt hoặc làm hỏng chữ tiếng Việt quanh tên fact → thông
 *      điệp vẫn hiện, chỉ là sai.
 *
 * Chạy:  node frontend/scripts/kiem-facts.ts
 */
import { banNhanFact, dungFacts, nhanHoaFact, oSoHong } from '../src/lib/facts.ts';
import type { FactField } from '../src/types.ts';

let hong = 0;

function kiem(ten: string, dung: boolean): void {
  if (!dung) {
    hong += 1;
    process.stderr.write(`HONG: ${ten}\n`);
  }
}

function truong(key: string, kieu: string, nhan = key): FactField {
  return { key, nhan, kieu, bat_buoc: false, lua_chon: null };
}

const MAU: FactField[] = [
  truong('thoi_gian_thu_viec_ngay', 'int', 'Thời gian thử việc (ngày)'),
  truong('nhom_chuc_danh', 'str', 'Nhóm chức danh'),
  truong('luong_thang', 'int', 'Lương tháng (đồng/tháng)'),
  // Khoá MỘT TỪ, không gạch dưới — chỗ mà một quy tắc theo hình dạng chuỗi bỏ sót.
  truong('vung', 'str', 'Vùng lương tối thiểu'),
  truong('co_dieu_khoan_dat_coc', 'bool', 'Có điều khoản buộc đặt cọc'),
];

// 1. Ô trống bị BỎ HẲN, không gửi chuỗi rỗng: fact vắng mặt là "chưa kiểm
//    được" (một kết quả thật), còn "" là một giá trị SAI và nhận 422.
{
  const ra = dungFacts(MAU, { luong_thang: '5000000', nhom_chuc_danh: '   ' });
  kiem('ô trống: không có mặt trong facts', !('nhom_chuc_danh' in ra));
  kiem('ô số: gửi đúng number', ra.luong_thang === 5_000_000);
  kiem('ô chưa điền: không có mặt', !('thoi_gian_thu_viec_ngay' in ra));
}

// 2. bool LUÔN có mặt: không tick nghĩa là "không có điều khoản đó" — một câu
//    trả lời, khác hẳn "chưa biết".
{
  const ra = dungFacts(MAU, {});
  kiem('bool: luôn có mặt kể cả khi chưa tick', ra.co_dieu_khoan_dat_coc === false);
  kiem('bool: tick thành true', dungFacts(MAU, { co_dieu_khoan_dat_coc: 'true' }).co_dieu_khoan_dat_coc === true);
}

// 3. Ô số không đọc được phải NÓI RA, không lặng lẽ bỏ đi.
{
  kiem('ô số hỏng: bị bắt', oSoHong(MAU, { luong_thang: 'năm triệu' })?.key === 'luong_thang');
  kiem('ô số trống: không phải lỗi', oSoHong(MAU, { luong_thang: '' }) === null);
  kiem('ô số đúng: không phải lỗi', oSoHong(MAU, { luong_thang: '5000000' }) === null);
}

// 4. Nhân hoá tên fact trong đúng câu backend sinh ra.
{
  const nhan = banNhanFact(MAU);
  const thoBackend =
    'Thời gian thử việc vượt mức tối đa theo chức danh — không kiểm được: thiếu thoi_gian_thu_viec_ngay, nhom_chuc_danh';
  const ra = nhanHoaFact(thoBackend, nhan);
  kiem('nhân hoá: đổi đúng cả hai tên', ra.endsWith('thiếu Thời gian thử việc (ngày), Nhóm chức danh'));
  kiem('nhân hoá: không còn tên máy', !ra.includes('thoi_gian_thu_viec_ngay'));
  kiem('nhân hoá: giữ nguyên phần tiếng Việt phía trước', ra.startsWith('Thời gian thử việc vượt mức tối đa theo chức danh — không kiểm được: '));
}

// 5. Câu của rule VI PHẠM (`key='giá trị'`) cũng đọc được, và giá trị không bị đụng.
{
  const ra = nhanHoaFact("Mức lương tháng thấp hơn lương tối thiểu vùng — luong_thang=3000000, vung='IV'", banNhanFact(MAU));
  kiem('vi phạm: đổi tên fact có trong mẫu', ra.includes('Lương tháng (đồng/tháng)=3000000'));
  kiem('vi phạm: khoá MỘT TỪ cũng được đổi', ra.includes("Vùng lương tối thiểu='IV'"));
  kiem('vi phạm: không còn tên máy `vung=`', !ra.includes('vung='));
  kiem('vi phạm: giữ nguyên giá trị', ra.includes("'IV'"));
  kiem('vi phạm: không đụng chữ có dấu "vùng" trong câu', ra.includes('lương tối thiểu vùng —'));
}

// 6. Mã KHÔNG có trong mẫu thì GIỮ NGUYÊN — tra bảng, không đoán. Một fact mới
//    thêm vào YAML mà mẫu chưa trả về không được biến thành một nhãn bịa.
{
  const ra = nhanHoaFact('không kiểm được: thiếu mot_fact_moi_toanh', banNhanFact(MAU));
  kiem('mã lạ: giữ nguyên', ra.includes('mot_fact_moi_toanh'));
}

// 7. Không đụng vào chữ thường tiếng Việt (dấu nằm ngoài [a-z0-9_]) và chữ
//    không có gạch dưới.
{
  const cau = 'Thiếu nội dung bắt buộc: Chế độ nâng bậc, nâng lương';
  kiem('câu không có tên fact: giữ nguyên từng ký tự', nhanHoaFact(cau, banNhanFact(MAU)) === cau);
}

// 8. Mẫu chưa tải xong: bảng nhãn rỗng, thông điệp giữ nguyên thay vì mất chữ.
{
  const cau = 'không kiểm được: thiếu luong_thang';
  kiem('mẫu chưa về: giữ nguyên', nhanHoaFact(cau, banNhanFact(null)) === cau);
}

if (hong > 0) {
  process.stderr.write(`${hong} phép kiểm HỎNG\n`);
  process.exit(1);
}
process.stdout.write('kiem-facts: tất cả phép kiểm ĐẠT\n');
