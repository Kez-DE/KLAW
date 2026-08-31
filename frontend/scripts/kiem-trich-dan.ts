/**
 * Tự kiểm `catTheoTrichDan` — logic duy nhất trong FE mà sai thì hỏng lặng lẽ:
 * câu trích không được tô sáng, mà giao diện vẫn trông bình thường.
 *
 * Chạy:  node frontend/scripts/kiem-trich-dan.ts
 * (Node ≥ 22.18 tự bóc kiểu; không cần test framework, không cần cài gì thêm.)
 */
import { catTheoTrichDan, canhBaoChoVanBan } from '../src/lib/trichDan.ts';

let hong = 0;

function kiem(ten: string, dung: boolean): void {
  if (!dung) {
    hong += 1;
    process.stderr.write(`HONG: ${ten}\n`);
  }
}

// 1. Khớp thẳng, cắt đúng ba phần và ghép lại đúng nguyên văn.
{
  const noiDung = '3. Tổng số giờ làm thêm trong một năm không quá 300 giờ. Trừ trường hợp khác.';
  const lat = catTheoTrichDan(noiDung, 'Tổng số giờ làm thêm trong một năm không quá 300 giờ.');
  kiem('khớp thẳng: tìm thấy', lat.timThay);
  kiem('khớp thẳng: trung đúng', lat.trung === 'Tổng số giờ làm thêm trong một năm không quá 300 giờ.');
  kiem('khớp thẳng: ghép lại bằng nguyên văn', lat.truoc + lat.trung + lat.sau === noiDung);
  kiem('khớp thẳng: truoc đúng', lat.truoc === '3. ');
}

// 2. Khoảng trắng lệch (xuống dòng, tab, dấu cách kép trong bản gốc) vẫn khớp,
//    và phần cắt ra giữ NGUYÊN khoảng trắng gốc — không bị chuẩn hoá mất.
{
  const noiDung = 'Điều 5.\nNgười lao động\tcó   quyền làm việc.';
  const lat = catTheoTrichDan(noiDung, 'Người lao động có quyền làm việc.');
  kiem('khoảng trắng lệch: tìm thấy', lat.timThay);
  kiem('khoảng trắng lệch: giữ nguyên văn gốc', lat.trung === 'Người lao động\tcó   quyền làm việc.');
  kiem('khoảng trắng lệch: ghép lại bằng nguyên văn', lat.truoc + lat.trung + lat.sau === noiDung);
}

// 3. Dấu tiếng Việt dạng tổ hợp (NFD) một bên vẫn khớp bên NFC.
{
  const nfc = 'Người sử dụng lao động phải trả lương.';
  const lat = catTheoTrichDan(nfc.normalize('NFD'), nfc);
  kiem('NFD vs NFC: tìm thấy', lat.timThay);
  kiem('NFD vs NFC: trung ở dạng NFC', lat.trung === nfc);
}

// 4. Không khớp: nói thật, KHÔNG im lặng tô bừa.
{
  const noiDung = 'Điều 1. Phạm vi điều chỉnh.';
  const lat = catTheoTrichDan(noiDung, 'Một câu không có trong điều này.');
  kiem('không khớp: timThay = false', !lat.timThay);
  kiem('không khớp: trung rỗng', lat.trung === '');
  kiem('không khớp: giữ đủ nguyên văn ở truoc', lat.truoc === noiDung);
}

// 5. Quote rỗng không được khớp mọi thứ.
{
  const lat = catTheoTrichDan('Điều 1.', '   ');
  kiem('quote rỗng: timThay = false', !lat.timThay);
}

// 6. Cảnh báo gắn theo so_ky_hieu mở đầu câu.
{
  const canhBao = [
    '45/2019/QH14 hết hiệu lực một phần: bị 19/2023/QH15 sửa đổi',
    '145/2020/NĐ-CP hết hiệu lực một phần: bị 35/2022/NĐ-CP sửa đổi',
  ];
  kiem('cảnh báo: khớp đúng một', canhBaoChoVanBan(canhBao, '45/2019/QH14').length === 1);
  kiem('cảnh báo: không khớp thì rỗng', canhBaoChoVanBan(canhBao, '10/2012/QH13').length === 0);
}

if (hong > 0) {
  process.stderr.write(`${hong} phép kiểm HỎNG\n`);
  process.exit(1);
}
process.stdout.write('kiem-trich-dan: tất cả phép kiểm ĐẠT\n');
