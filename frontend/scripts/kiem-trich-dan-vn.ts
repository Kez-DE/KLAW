/**
 * Tự kiểm `lib/trichDanVN.ts` — quy tắc trích dẫn §6.2. Sai ở đây thì mọi con
 * số trên giao diện vẫn hiện ra bình thường nhưng chỉ sai địa chỉ, nên không
 * có cách nào phát hiện bằng mắt: phải khoá bằng phép kiểm.
 *
 * Chạy:  node frontend/scripts/kiem-trich-dan-vn.ts
 * (Node ≥ 22.18 tự bóc kiểu; không cần test framework, không cần cài gì thêm.)
 *
 * Mọi `bo_luat` và `so_ky_hieu` dưới đây là NGUYÊN VĂN lấy từ bảng `documents`
 * của DB (57 văn bản), kể cả các chỗ chính tả không nhất quán — `Bộ Luật lao
 * động` chữ L hoa l thường, `Luật sư số 65/2006/QH11`, `Luật Tổ chức Toà án
 * nhân dân số số: 34/2024/QH15`. Không "sửa" chúng trong fixture, vì sản phẩm
 * cũng không được sửa.
 */
import {
  dinhDangTrichDan,
  neoTrichDan,
  chuoiDeSaoChep,
  tenVanBanHienThi,
  soKyHieuTuDuongDan,
} from '../src/lib/trichDanVN.ts';

let hong = 0;

function kiem(ten: string, thuc: string, mong: string): void {
  if (thuc !== mong) {
    hong += 1;
    process.stderr.write(`HONG: ${ten}\n  mong: ${JSON.stringify(mong)}\n  thuc: ${JSON.stringify(thuc)}\n`);
  }
}

function kiemDung(ten: string, dung: boolean): void {
  if (!dung) {
    hong += 1;
    process.stderr.write(`HONG: ${ten}\n`);
  }
}

const BLLD = { skh: '45/2019/QH14', ten: 'Bộ Luật lao động số 45/2019/QH14' };

// ── 1. Ba dạng của §6.2: đọc từ đơn vị nhỏ nhất tới lớn nhất ────────────────
kiem(
  'điểm + khoản + điều',
  dinhDangTrichDan('45/2019/QH14 > Điều 30 > Khoản 1 > Điểm b', BLLD.skh, BLLD.ten),
  'Điểm b khoản 1 Điều 30 Bộ Luật lao động 2019',
);
kiem(
  'khoản + điều',
  dinhDangTrichDan('45/2019/QH14 > Điều 127 > Khoản 2', BLLD.skh, BLLD.ten),
  'Khoản 2 Điều 127 Bộ Luật lao động 2019',
);
kiem(
  'điều',
  dinhDangTrichDan('45/2019/QH14 > Điều 27', BLLD.skh, BLLD.ten),
  'Điều 27 Bộ Luật lao động 2019',
);

// ── 2. Cấm thứ tự Anh ngữ và cấm viết tắt ───────────────────────────────────
{
  const s = dinhDangTrichDan('45/2019/QH14 > Điều 25 > Khoản 2', BLLD.skh, BLLD.ten);
  kiemDung('không dựng thứ tự lớn→nhỏ (Điều trước Khoản)', s.indexOf('Khoản') < s.indexOf('Điều'));
  kiemDung('không viết tắt Đ./K./Art.', !/\bĐ\.|\bK\.|Art\.|Article|Clause/.test(s));
}

// ── 3. `Điều` LUÔN viết hoa chữ Đ, kể cả khi đứng giữa câu ───────────────────
{
  const s = dinhDangTrichDan('45/2019/QH14 > Điều 127 > Khoản 2', BLLD.skh, BLLD.ten);
  kiemDung('Điều hoa khi đứng giữa câu', s.includes(' Điều 127 '));
  kiemDung('không có `điều` chữ thường', !s.includes('điều'));
}

// ── 4. Token sau token đầu viết thường (khoản, điểm) ─────────────────────────
{
  const s = dinhDangTrichDan('45/2019/QH14 > Điều 30 > Khoản 1 > Điểm b', BLLD.skh, BLLD.ten);
  kiemDung('token đầu `Điểm` hoa', s.startsWith('Điểm b '));
  kiemDung('`khoản` giữa câu viết thường', s.includes(' khoản 1 '));
  kiemDung('không còn `Khoản`/`Điểm` hoa ở giữa', !s.includes('Khoản') && !s.slice(1).includes('Điểm'));
}

// Cùng đơn vị, khi đứng ĐẦU thì phải hoa: `Khoản` mở đầu chuỗi.
kiem(
  'Khoản đứng đầu thì hoa',
  dinhDangTrichDan('45/2019/QH14 > Điều 99 > Khoản 1', BLLD.skh, ''),
  'Khoản 1 Điều 99',
);

// ── 5. Đơn vị cấu trúc khác vẫn đảo đúng, không nổ ──────────────────────────
kiem(
  'chương',
  dinhDangTrichDan('45/2019/QH14 > Chương XVI', BLLD.skh, BLLD.ten),
  'Chương XVI Bộ Luật lao động 2019',
);
kiem(
  'phần > chương > mục > tiểu mục (bốn cấp, đảo hết)',
  dinhDangTrichDan(
    '91/2015/QH13 > Phần thứ ba > Chương XVI > Mục 5 > Tiểu mục 1',
    '91/2015/QH13',
    'Bộ luật Dân sự số 91/2015/QH13',
  ),
  'Tiểu mục 1 mục 5 chương XVI phần thứ ba Bộ luật Dân sự 2015',
);
kiem(
  'đơn vị không có phần số (Mở đầu)',
  dinhDangTrichDan('100/2015/QH13 > Mở đầu', '100/2015/QH13', 'Bộ luật Hình sự số 100/2015/QH13'),
  'Mở đầu Bộ luật Hình sự 2015',
);

// ── 6. Tên văn bản: NGUYÊN VĂN, không sửa chính tả ──────────────────────────
kiem(
  'giữ nguyên `Bộ Luật lao động` (L hoa, l thường) — KHÔNG sửa thành `Bộ luật Lao động`',
  tenVanBanHienThi(BLLD.skh, BLLD.ten),
  'Bộ Luật lao động 2019',
);
kiem(
  'giữ nguyên `Bộ luật Hàng hải`',
  tenVanBanHienThi('95/2015/QH13', 'Bộ luật Hàng hải số 95/2015/QH13'),
  'Bộ luật Hàng hải 2015',
);
kiem(
  'tên không nhúng số hiệu thì vẫn thêm năm',
  tenVanBanHienThi('41/2024/QH15', 'Luật Bảo hiểm xã hội'),
  'Luật Bảo hiểm xã hội 2024',
);
kiem(
  'tên ngắn lạ (`Luật sư`) vẫn giữ nguyên văn',
  tenVanBanHienThi('65/2006/QH11', 'Luật sư số 65/2006/QH11'),
  'Luật sư 2006',
);
kiem(
  'số hiệu méo `số: 34/2024/QH15` — bóc cả chữ `số` lặp',
  tenVanBanHienThi('số: 34/2024/QH15', 'Luật Tổ chức Toà án nhân dân số số: 34/2024/QH15'),
  'Luật Tổ chức Toà án nhân dân 2024',
);

// Nghị định/thông tư: sau số hiệu còn phần mô tả nội dung → dẫn theo dạng
// `<loại> <số hiệu>` của §6.2, không dán năm vào một cụm chỉ có loại văn bản.
kiem(
  'nghị định dẫn theo loại + số hiệu',
  dinhDangTrichDan(
    '141/2017/NĐ-CP > Điều 3',
    '141/2017/NĐ-CP',
    'Nghị định số 141/2017/NĐ-CP Quy định mức lương tối thiểu vùng đối với người lao động làm việc theo hợp đồng lao động',
  ),
  'Điều 3 Nghị định 141/2017/NĐ-CP',
);
kiem(
  'thông tư liên tịch: số hiệu trong tên không kèm chữ `số`',
  tenVanBanHienThi(
    '07/2026/TTLT-VKSNDTC-TANDTC',
    'Thông tư liên tịch 07/2026/TTLT-VKSNDTC-TANDTC quy định việc phối hợp giữa Viện kiểm sát nhân dân và Tòa án nhân dân trong thi hành quy định của Bộ luật Tố tụng dân sự',
  ),
  'Thông tư liên tịch 07/2026/TTLT-VKSNDTC-TANDTC',
);

// ── 7. ALL-CAPS hạ về dạng câu — và KHÔNG nuốt tên bình thường ───────────────
kiem(
  'ALL-CAPS hạ về dạng câu',
  tenVanBanHienThi('128/2025/QH15', 'LUẬT THI HÀNH TẠM GIỮ, TẠM GIAM VÀ CẤM ĐI KHỎI NƠI CƯ TRÚ SỐ 128/2025/QH15'),
  'Luật thi hành tạm giữ, tạm giam và cấm đi khỏi nơi cư trú 2025',
);
// Khoá ngoại lệ ALL-CAPS: mọi tên có chữ thường phải đi qua nguyên vẹn.
for (const [skh, ten, mong] of [
  ['45/2019/QH14', 'Bộ Luật lao động số 45/2019/QH14', 'Bộ Luật lao động 2019'],
  ['100/2015/QH13', 'Bộ luật Hình sự số 100/2015/QH13', 'Bộ luật Hình sự 2015'],
  ['16/2023/QH15', 'Luật Giá số 16/2023/QH15', 'Luật Giá 2023'],
  ['84/2015/QH13', 'Luật An toàn, vệ sinh lao động số 84/2015/QH13', 'Luật An toàn, vệ sinh lao động 2015'],
  ['13/2022/QH15', 'Luật Phòng, chống bạo lực gia đình số 13/2022/QH15', 'Luật Phòng, chống bạo lực gia đình 2022'],
] as const) {
  kiem(`ngoại lệ ALL-CAPS không nuốt tên thường: ${ten}`, tenVanBanHienThi(skh, ten), mong);
}

// ── 8. Số hiệu thiếu năm → BỎ năm, không đoán ───────────────────────────────
kiem(
  'số hiệu không khớp mẫu có năm → bỏ năm',
  tenVanBanHienThi('QH14', 'Bộ Luật lao động số QH14'),
  'Bộ Luật lao động',
);
kiem(
  'số hiệu rỗng → bỏ năm, giữ nguyên tên',
  tenVanBanHienThi('', 'Bộ Luật lao động'),
  'Bộ Luật lao động',
);
kiem(
  'năm suy từ số hiệu, KHÔNG suy từ tên (tên chứa 1999, số hiệu 2019)',
  tenVanBanHienThi('45/2019/QH14', 'Bộ luật lao động 1999 số 45/2019/QH14'),
  'Bộ luật lao động 1999 2019',
);
// Chốt quan trọng nhất của quy tắc "năm suy từ số hiệu": số hiệu KHÔNG có năm
// mà tên LẠI có. Đây đúng chỗ một cách viết "cho tiện" sẽ vớt năm trong tên và
// dán ra một năm sai. Thiếu phép kiểm này thì cả điều 8 xanh giả — đã dựng đột
// biến để xác nhận.
kiem(
  'số hiệu không có năm mà tên có → vẫn BỎ năm, không vớt từ tên',
  tenVanBanHienThi('QH14', 'Bộ luật lao động 2019 số QH14'),
  'Bộ luật lao động 2019',
);
kiem(
  'số hiệu rỗng mà tên có năm → không vớt năm từ tên',
  tenVanBanHienThi('', 'Luật Thương mại 2005'),
  'Luật Thương mại 2005',
);
kiem(
  'không dán năm ngay sau một số hiệu khác ở đuôi tên',
  tenVanBanHienThi('12/2017/QH14', 'Luật Sửa đổi, bổ sung một số điều của Bộ luật Hình sự số 100/2015/QH13 số 12/2017/QH14'),
  'Luật Sửa đổi, bổ sung một số điều của Bộ luật Hình sự số 100/2015/QH13',
);
// Chữ "số" trong "một số điều" KHÔNG được nhận là chữ `số` của số hiệu.
kiem(
  'cụm `một số điều` không bị bóc mất',
  tenVanBanHienThi('02/2021/QH15', 'Luật sửa đổi, bổ sung một số điều của Bộ luật Tố tụng hình sự số 02/2021/QH15'),
  'Luật sửa đổi, bổ sung một số điều của Bộ luật Tố tụng hình sự 2021',
);

// ── 9. duong_dan hình dạng lạ: KHÔNG nổ, KHÔNG bịa ──────────────────────────
for (const la of [
  '45/2019/QH14 > Article 25 > Clause 2',
  '45/2019/QH14 > Đ.25 > K.2',
  'một chuỗi hoàn toàn không phải đường dẫn',
  '45/2019/QH14 > Điều 25 > Tiết a',
]) {
  kiem(`đường dẫn lạ trả về nguyên văn: ${la}`, dinhDangTrichDan(la, BLLD.skh, BLLD.ten), la);
}
kiem('đường dẫn rỗng → chỉ tên văn bản', dinhDangTrichDan('', BLLD.skh, BLLD.ten), 'Bộ Luật lao động 2019');
kiem('đường dẫn chỉ có số hiệu → chỉ tên văn bản', dinhDangTrichDan('45/2019/QH14', BLLD.skh, BLLD.ten), 'Bộ Luật lao động 2019');
kiem('thiếu cả tên và đường dẫn → rỗng, không nổ', dinhDangTrichDan('', '', ''), '');
kiem(
  'thiếu bo_luat (CitationChip) → vẫn ra trích dẫn, không có tên',
  dinhDangTrichDan('45/2019/QH14 > Điều 127 > Khoản 2', BLLD.skh, ''),
  'Khoản 2 Điều 127',
);
kiem(
  'chỉ có duong_dan (Soát/Soạn thảo truyền can_cu) → bỏ số hiệu đầu, không nổ',
  dinhDangTrichDan('45/2019/QH14 > Điều 127 > Khoản 2', '', ''),
  'Khoản 2 Điều 127',
);

// ── 9b. Lấy lại số hiệu từ đường dẫn trần (Soát / Soạn thảo) ────────────────
kiem('số hiệu từ đường dẫn', soKyHieuTuDuongDan('45/2019/QH14 > Điều 127 > Khoản 2'), '45/2019/QH14');
kiem('số hiệu từ đường dẫn có gạch nối dài', soKyHieuTuDuongDan('07/2026/TTLT-VKSNDTC-TANDTC > Điều 3'), '07/2026/TTLT-VKSNDTC-TANDTC');
kiem('đường dẫn không mở đầu bằng số hiệu → rỗng, không đoán', soKyHieuTuDuongDan('Điều 127 > Khoản 2'), '');
kiem('đường dẫn rỗng → rỗng', soKyHieuTuDuongDan(''), '');

// ── 10. Neo deep-link §6.2 — chiều lớn → nhỏ ────────────────────────────────
kiem('neo điều', neoTrichDan('45/2019/QH14 > Điều 25'), 'dieu-25');
kiem('neo điều + khoản', neoTrichDan('45/2019/QH14 > Điều 25 > Khoản 2'), 'dieu-25-khoan-2');
kiem('neo điều + khoản + điểm', neoTrichDan('45/2019/QH14 > Điều 25 > Khoản 2 > Điểm a'), 'dieu-25-khoan-2-diem-a');
kiem('neo bỏ dấu tiếng Việt ở giá trị điểm (đ → d)', neoTrichDan('45/2019/QH14 > Điều 25 > Khoản 2 > Điểm đ'), 'dieu-25-khoan-2-diem-d');
kiem('neo bỏ bao cấu trúc, chỉ giữ điều/khoản/điểm', neoTrichDan('91/2015/QH13 > Phần thứ ba > Chương XVI > Điều 100 > Khoản 1'), 'dieu-100-khoan-1');
kiem('không có Điều → không có neo', neoTrichDan('45/2019/QH14 > Chương XVI'), '');
kiem('đường dẫn lạ → không có neo', neoTrichDan('45/2019/QH14 > Article 25'), '');
kiem('đường dẫn rỗng → không có neo', neoTrichDan(''), '');

// ── 11. Chuỗi sao chép: so_ky_hieu KHÔNG ĐƯỢC biến mất ──────────────────────
kiem(
  'chuỗi sao chép đầy đủ: trích dẫn — tên nguyên văn (có số hiệu) — hiệu lực',
  chuoiDeSaoChep('45/2019/QH14 > Điều 127 > Khoản 2', BLLD.skh, BLLD.ten, 'con_hieu_luc'),
  'Khoản 2 Điều 127 Bộ Luật lao động 2019 — Bộ Luật lao động số 45/2019/QH14 (Còn hiệu lực)',
);
kiem(
  'không có hiệu lực thì không dựng ngoặc rỗng',
  chuoiDeSaoChep('45/2019/QH14 > Điều 27', BLLD.skh, BLLD.ten),
  'Điều 27 Bộ Luật lao động 2019 — Bộ Luật lao động số 45/2019/QH14',
);
kiem(
  'tên không chứa số hiệu → gắn thêm `số <so_ky_hieu>`',
  chuoiDeSaoChep('41/2024/QH15 > Điều 5', '41/2024/QH15', 'Luật Bảo hiểm xã hội', 'bi_thay_the'),
  'Điều 5 Luật Bảo hiểm xã hội 2024 — Luật Bảo hiểm xã hội số 41/2024/QH15 (Đã bị thay thế)',
);
kiem(
  'thiếu bo_luat → số hiệu vẫn phải có mặt',
  chuoiDeSaoChep('45/2019/QH14 > Điều 127 > Khoản 2', BLLD.skh, ''),
  'Khoản 2 Điều 127 — 45/2019/QH14',
);
kiem(
  'nhãn hiệu lực lạ vẫn hiện nguyên văn, không im lặng bỏ',
  chuoiDeSaoChep('45/2019/QH14 > Điều 27', BLLD.skh, BLLD.ten, 'mot_nhan_moi_cua_backend'),
  'Điều 27 Bộ Luật lao động 2019 — Bộ Luật lao động số 45/2019/QH14 (mot_nhan_moi_cua_backend)',
);
// Bất biến chốt: mọi chuỗi sao chép có số hiệu đều phải chứa số hiệu đó.
for (const [duongDan, skh, ten] of [
  ['45/2019/QH14 > Điều 127 > Khoản 2', '45/2019/QH14', 'Bộ Luật lao động số 45/2019/QH14'],
  ['141/2017/NĐ-CP > Điều 3', '141/2017/NĐ-CP', 'Nghị định số 141/2017/NĐ-CP Quy định mức lương tối thiểu vùng'],
  ['41/2024/QH15 > Điều 5', '41/2024/QH15', 'Luật Bảo hiểm xã hội'],
  ['128/2025/QH15 > Điều 1', '128/2025/QH15', 'LUẬT THI HÀNH TẠM GIỮ, TẠM GIAM VÀ CẤM ĐI KHỎI NƠI CƯ TRÚ SỐ 128/2025/QH15'],
  ['số: 34/2024/QH15 > Điều 2', 'số: 34/2024/QH15', 'Luật Tổ chức Toà án nhân dân số số: 34/2024/QH15'],
] as const) {
  kiemDung(
    `số hiệu ${skh} có mặt trong chuỗi sao chép`,
    chuoiDeSaoChep(duongDan, skh, ten).includes(skh),
  );
}

if (hong > 0) {
  process.stderr.write(`${hong} phép kiểm HỎNG\n`);
  process.exit(1);
}
process.stdout.write('kiem-trich-dan-vn: tất cả phép kiểm ĐẠT\n');
