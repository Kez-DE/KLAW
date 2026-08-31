/**
 * Trích dẫn theo thứ tự tiếng Việt (§6.2 BUILD-SPEC) — logic quan trọng nhất
 * của sản phẩm: sai ở đây là hỏng toàn bộ uy tín.
 *
 * Đọc từ đơn vị NHỎ NHẤT tới LỚN NHẤT, ngược với `duong_dan` của DB:
 *
 *   duong_dan  "45/2019/QH14 > Điều 127 > Khoản 2"
 *   trích dẫn  "Khoản 2 Điều 127 Bộ Luật lao động 2019"
 *
 * Chỉ token ĐẦU TIÊN viết hoa chữ cái đầu; các token sau viết thường — TRỪ
 * `Điều`, luôn viết hoa chữ Đ kể cả khi đứng giữa câu (quy ước trình bày văn
 * bản pháp luật Việt Nam). Cấm viết tắt `Đ.25`, `K.2`, `Art. 25` và cấm thứ tự
 * Anh ngữ `Article 25, Clause 2`.
 *
 * Module thuần: không phụ thuộc React, không đọc DOM. Đây chỉ là tầng HIỂN
 * THỊ — `so_ky_hieu` vẫn là khoá định danh bên trong, không hàm nào ở đây thay
 * đổi điều đó.
 */

/**
 * Đơn vị cấu trúc có THẬT trong `provisions.duong_dan` (đã đối chiếu DB: 9 giá
 * trị `cap` — khoan, diem, dieu, chuong, muc, phan, tieu_muc, mo_dau, phu_luc).
 * Đơn vị nằm ngoài bảng này làm cả đường dẫn rơi về nguyên văn, xem
 * `dinhDangTrichDan`.
 */
interface DonVi {
  /** Dạng dùng khi đứng ĐẦU chuỗi trích dẫn. */
  dauCau: string;
  /** Dạng dùng khi đứng GIỮA chuỗi. Riêng `Điều` không đổi. */
  giuaCau: string;
  /**
   * Mảnh neo deep-link. Rỗng = đơn vị không nằm trong ba dạng neo §6.2
   * (`dieu-25` | `dieu-25-khoan-2` | `dieu-25-khoan-2-diem-a`), nên không được
   * dựng neo cho nó — chương/mục/phần là bao cấu trúc, không phải điều khoản
   * được dẫn.
   */
  neo: string;
}

/**
 * Khớp theo tiền tố, dài trước ngắn, để `Tiểu mục` không bị `Mục` giành.
 * `Mở đầu` và `Phụ lục` không có phần số đi kèm.
 */
const DON_VI: readonly (readonly [string, DonVi])[] = [
  ['Tiểu mục', { dauCau: 'Tiểu mục', giuaCau: 'tiểu mục', neo: '' }],
  ['Mở đầu', { dauCau: 'Mở đầu', giuaCau: 'mở đầu', neo: '' }],
  ['Phụ lục', { dauCau: 'Phụ lục', giuaCau: 'phụ lục', neo: '' }],
  ['Chương', { dauCau: 'Chương', giuaCau: 'chương', neo: '' }],
  ['Phần', { dauCau: 'Phần', giuaCau: 'phần', neo: '' }],
  ['Mục', { dauCau: 'Mục', giuaCau: 'mục', neo: '' }],
  // `Điều` viết hoa ở MỌI vị trí — dauCau và giuaCau cố ý giống nhau.
  ['Điều', { dauCau: 'Điều', giuaCau: 'Điều', neo: 'dieu' }],
  ['Khoản', { dauCau: 'Khoản', giuaCau: 'khoản', neo: 'khoan' }],
  ['Điểm', { dauCau: 'Điểm', giuaCau: 'điểm', neo: 'diem' }],
];

/** Dấu phân cách đoạn trong `duong_dan`, đúng như DB sinh ra. */
const NGAN = ' > ';

/** '45/2019/QH14', '356/2025/NĐ-CP', '07/2026/TTLT-VKSNDTC-TANDTC'. */
const SO_KY_HIEU_RE = /\d{1,4}\/(?:19|20)\d{2}\/[A-ZĐ][A-ZĐ0-9-]*/;

/** Số hiệu neo ở CUỐI chuỗi — dùng để không dán năm ngay sau một số hiệu khác. */
const KET_BANG_SO_KY_HIEU_RE = new RegExp(`${SO_KY_HIEU_RE.source}\\s*$`);

/** Năm nằm trong số hiệu: '45/2019/QH14' → '2019'. */
const NAM_TRONG_SO_KY_HIEU_RE = /\/((?:19|20)\d{2})\//;

/**
 * Chữ `số` (mọi cách viết hoa) và dấu hai chấm còn lại ở đuôi tên sau khi bóc
 * số hiệu ra. Có văn bản ghi `... số số: 34/2024/QH15`, nên phải bóc lặp.
 */
const DUOI_SO_RE = /[\s,:]*\b(?:số|Số|SỐ)\s*:?\s*$/;

interface DoanDaNhan {
  donVi: DonVi;
  /** Phần giá trị giữ NGUYÊN VĂN: '127', 'đ', 'XVI', 'thứ tám', hoặc rỗng. */
  giaTri: string;
}

/** `null` = đoạn không thuộc đơn vị nào đã biết. */
function nhanDoan(doan: string): DoanDaNhan | null {
  const sach = doan.trim();
  for (const [tienTo, donVi] of DON_VI) {
    if (sach === tienTo) return { donVi, giaTri: '' };
    if (sach.startsWith(`${tienTo} `)) {
      return { donVi, giaTri: sach.slice(tienTo.length).trim() };
    }
  }
  return null;
}

/**
 * Bóc các đoạn cấu trúc khỏi `duong_dan`, bỏ đoạn đầu là số hiệu văn bản.
 * `null` = đường dẫn có đoạn lạ; người gọi phải trả về nguyên văn thay vì dựng
 * một trích dẫn sai.
 */
function bocDoan(duongDan: string): DoanDaNhan[] | null {
  const tho = duongDan
    .split(NGAN)
    .map((doan) => doan.trim())
    .filter((doan) => doan !== '');
  if (tho.length === 0) return [];

  // Đoạn đầu của `duong_dan` luôn là `so_ky_hieu` của văn bản. Nó được hiển thị
  // riêng bằng font mono nên không lặp vào chuỗi trích dẫn.
  const conLai = SO_KY_HIEU_RE.test(tho[0]) && nhanDoan(tho[0]) === null ? tho.slice(1) : tho;

  const daNhan: DoanDaNhan[] = [];
  for (const doan of conLai) {
    const nhan = nhanDoan(doan);
    if (nhan === null) return null;
    daNhan.push(nhan);
  }
  return daNhan;
}

/**
 * Số hiệu văn bản nằm ở đoạn ĐẦU của `duong_dan`.
 *
 * Soát và Soạn thảo chỉ có `can_cu` (một `duong_dan` trần), không có field
 * `so_ky_hieu` riêng. Trước đây số hiệu vẫn hiện ra vì cả đường dẫn được in
 * nguyên; nay đoạn đầu bị bóc khỏi chuỗi trích dẫn, nên phải lấy lại được từ
 * đây — nếu không, khoá định danh duy nhất của văn bản biến mất khỏi giao diện.
 *
 * Rỗng khi đoạn đầu không phải số hiệu; không đoán.
 */
export function soKyHieuTuDuongDan(duongDan: string): string {
  const dau = duongDan.split(NGAN)[0]?.trim() ?? '';
  return SO_KY_HIEU_RE.test(dau) && nhanDoan(dau) === null ? dau : '';
}

/** NFD → bỏ dấu phụ → đ/Đ thành d → lowercase → khoảng trắng thành gạch nối. */
function laySlug(giaTri: string): string {
  return giaTri
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-');
}

/**
 * Tên văn bản để hiển thị, dẫn xuất từ `documents.ten` (backend trả ở
 * `bo_luat`).
 *
 * `ten` là tên chính thức từ Cơ sở dữ liệu quốc gia và KHÔNG được sửa chính
 * tả: `Bộ Luật lao động` giữ đúng `Bộ Luật lao động`, dù quy ước trình bày là
 * `Bộ luật Lao động`. Cả sản phẩm này tồn tại để trung thành với nguồn; "sửa"
 * tên văn bản là bắt đầu bịa, dù chỉ bịa chính tả.
 *
 * Chỉ làm ba việc, đều là bóc bỏ chứ không thêm chữ:
 *
 * 1. Bóc cụm `số <so_ky_hieu>` khỏi tên. `documents.ten` nhúng số hiệu
 *    (`Bộ Luật lao động số 45/2019/QH14`); số hiệu đã hiện riêng bằng mono nên
 *    lặp lại chỉ làm trích dẫn khó đọc.
 * 2. Số hiệu nằm ở CUỐI tên → tên là toàn bộ phần trước, thêm năm suy từ số
 *    hiệu: `Bộ Luật lao động 2019`. Số hiệu nằm GIỮA tên, sau nó còn phần mô tả
 *    nội dung (`Nghị định số 141/2017/NĐ-CP Quy định mức lương tối thiểu…`) →
 *    phần trước chỉ là loại văn bản, nên dẫn theo dạng §6.2 dành cho nghị
 *    định/thông tư: `Nghị định 141/2017/NĐ-CP`.
 * 3. Tên ALL-CAPS hạ về dạng câu. Một số văn bản có `ten` viết hoa toàn bộ
 *    (`LUẬT THI HÀNH TẠM GIỮ…`) — đó là artifact định dạng, không phải tên.
 *    Chỉ hạ khi TOÀN BỘ tên không có chữ thường, nên `Bộ Luật lao động` không
 *    bị chạm tới.
 */
export function tenVanBanHienThi(soKyHieu: string, boLuat: string): string {
  const ten = boLuat.trim();
  if (ten === '') return '';

  // Xét trên nguyên văn, TRƯỚC khi bóc số hiệu: chữ `SỐ` trong `... SỐ
  // 128/2025/QH15` cũng là bằng chứng của artifact ALL-CAPS.
  const laToanHoa = /\p{L}/u.test(ten) && ten === ten.toLocaleUpperCase('vi');
  const hoaLaiTheoCau = (phan: string): string =>
    laToanHoa
      ? // Không phục hồi được danh từ riêng từ bản ALL-CAPS, mà đoán thì là
        // bịa. Hạ hết về chữ thường là mức trung thực thấp nhất giữ được.
        phan.charAt(0).toLocaleUpperCase('vi') + phan.slice(1).toLocaleLowerCase('vi')
      : phan;

  const soHieu = soKyHieu.trim();
  const viTri = soHieu === '' ? -1 : ten.indexOf(soHieu);
  const nam = NAM_TRONG_SO_KY_HIEU_RE.exec(soHieu)?.[1] ?? '';

  // Số hiệu không nằm trong tên (`Luật Bảo hiểm xã hội` / 41/2024/QH15): tên đã
  // sạch, chỉ cần thêm năm.
  if (viTri < 0) {
    return themNam(hoaLaiTheoCau(ten), nam);
  }

  const truoc = ten.slice(0, viTri).replace(DUOI_SO_RE, '').trim();
  const sau = ten.slice(viTri + soHieu.length).trim();

  // Sau số hiệu còn phần mô tả nội dung → phần trước chỉ là loại văn bản.
  if (sau !== '') {
    const loai = hoaLaiTheoCau(truoc);
    return loai === '' ? soHieu : `${loai} ${soHieu}`;
  }
  return themNam(hoaLaiTheoCau(truoc), nam);
}

/**
 * Năm CHỈ suy từ `so_ky_hieu`, không suy từ tên — một năm sai còn tệ hơn không
 * có năm. Cũng không dán năm ngay sau một số hiệu khác đã nằm ở đuôi tên
 * (`Luật Sửa đổi… Bộ luật Hình sự số 100/2015/QH13`), vì `… /QH13 2017` đọc ra
 * thành một số hiệu khác.
 */
function themNam(ten: string, nam: string): string {
  if (ten === '' || nam === '') return ten;
  if (KET_BANG_SO_KY_HIEU_RE.test(ten)) return ten;
  return `${ten} ${nam}`;
}

/**
 * Chuỗi trích dẫn để HIỂN THỊ, thứ tự nhỏ → lớn.
 *
 *   ('45/2019/QH14 > Điều 127 > Khoản 2', '45/2019/QH14', 'Bộ Luật lao động số 45/2019/QH14')
 *     → 'Khoản 2 Điều 127 Bộ Luật lao động 2019'
 *
 * Thiếu đường dẫn (chỗ chỉ dẫn ở cấp văn bản) → chỉ tên văn bản. Đường dẫn có
 * đoạn lạ → trả về NGUYÊN VĂN `duongDan`: một địa chỉ thô người ta còn tra lại
 * được, một trích dẫn dựng sai thì không.
 */
export function dinhDangTrichDan(duongDan: string, soKyHieu: string, boLuat: string): string {
  const tenVB = tenVanBanHienThi(soKyHieu, boLuat);
  const duong = duongDan.trim();
  if (duong === '') return tenVB;

  const doan = bocDoan(duong);
  if (doan === null) return duong;

  // Thứ tự tiếng Việt: đơn vị nhỏ nhất đứng trước. `duong_dan` xếp lớn → nhỏ.
  const nguoc = [...doan].reverse();
  const cumTu = nguoc.map(({ donVi, giaTri }, i) => {
    const tuDonVi = i === 0 ? donVi.dauCau : donVi.giuaCau;
    return giaTri === '' ? tuDonVi : `${tuDonVi} ${giaTri}`;
  });

  if (tenVB !== '') cumTu.push(tenVB);
  return cumTu.join(' ');
}

/**
 * Neo deep-link theo §6.2: `dieu-25` | `dieu-25-khoan-2` | `dieu-25-khoan-2-diem-a`.
 * Thứ tự neo giữ chiều LỚN → NHỎ của `duong_dan` (khác chiều đọc của trích dẫn).
 *
 * Rỗng khi không dựng được neo đúng ba dạng trên — đường dẫn lạ, hoặc chỉ trỏ
 * tới bao cấu trúc (Chương/Mục/Phần/Phụ lục) chứ không tới một Điều. Neo bịa ra
 * thì trỏ vào chỗ không tồn tại, nên thà không có neo.
 */
export function neoTrichDan(duongDan: string): string {
  const doan = bocDoan(duongDan.trim());
  if (doan === null) return '';

  const manh: string[] = [];
  for (const { donVi, giaTri } of doan) {
    if (donVi.neo === '') continue;
    manh.push(giaTri === '' ? donVi.neo : `${donVi.neo}-${laySlug(giaTri)}`);
  }
  // Ba dạng neo đều mở đầu bằng `dieu-`; không có Điều thì không có neo.
  if (manh.length === 0 || !manh[0].startsWith('dieu')) return '';
  return manh.join('-');
}

/**
 * Nhãn hiệu lực bằng tiếng người, cho chuỗi sao chép.
 *
 * ponytail: 5 nhãn này lặp lại phần chữ của `components/BadgeHieuLuc.tsx`. Cố ý
 * lặp — bảng bên đó gắn chữ với màu và kiểu viền trong cùng một switch, tách ra
 * sẽ thành hai switch cùng khoá, tệ hơn là lặp 5 hằng chuỗi. Đổi nhãn thì sửa
 * cả hai chỗ.
 */
const NHAN_HIEU_LUC: Readonly<Record<string, string>> = {
  con_hieu_luc: 'Còn hiệu lực',
  bi_thay_the: 'Đã bị thay thế',
  het_hieu_luc: 'Hết hiệu lực',
  mot_phan_khong_xac_dinh: 'Một phần không xác định',
  can_doi_chieu_tay: 'Cần đối chiếu tay',
};

/**
 * Chuỗi đầy đủ để SAO CHÉP: trích dẫn + tên đầy đủ + tình trạng hiệu lực.
 *
 * `so_ky_hieu` là khoá định danh duy nhất của văn bản (Global Constraint) nên
 * KHÔNG được biến mất khỏi bản sao chép: người dán chuỗi này vào hồ sơ phải tra
 * lại được văn bản gốc. Ở đây dùng `bo_luat` NGUYÊN VĂN, không rút gọn — và nếu
 * tên nguyên văn không chứa số hiệu thì gắn thêm `số <so_ky_hieu>`.
 */
export function chuoiDeSaoChep(
  duongDan: string,
  soKyHieu: string,
  boLuat: string,
  hieuLuc?: string | null,
): string {
  const trichDan = dinhDangTrichDan(duongDan, soKyHieu, boLuat);
  const soHieu = soKyHieu.trim();
  const tenDayDu = boLuat.trim();

  let dinhDanh: string;
  if (tenDayDu === '') {
    dinhDanh = soHieu;
  } else if (soHieu === '' || tenDayDu.includes(soHieu)) {
    dinhDanh = tenDayDu;
  } else {
    dinhDanh = `${tenDayDu} số ${soHieu}`;
  }

  const phan = [trichDan];
  if (dinhDanh !== '' && dinhDanh !== trichDan) phan.push(dinhDanh);
  const chuoi = phan.filter((p) => p !== '').join(' — ');

  if (hieuLuc === undefined || hieuLuc === null || hieuLuc === '') return chuoi;
  return `${chuoi} (${NHAN_HIEU_LUC[hieuLuc] ?? hieuLuc})`;
}
