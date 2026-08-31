/**
 * Tự kiểm "tiến tới khung" (`src/lib/chuyenCanh.ts`) — bất biến DUY NHẤT mà
 * View Transitions API đòi: tại mỗi ảnh chụp, một `view-transition-name` chỉ
 * được thuộc về MỘT phần tử. Vi phạm thì trình duyệt không báo lỗi vào mặt ai
 * cả, nó chỉ huỷ lượt chuyển — dữ liệu vẫn đúng, động tác trung tâm của sản
 * phẩm im lặng biến mất.
 *
 * Chạy:  node frontend/scripts/kiem-chuyen-canh.ts
 * (Node ≥ 22.18 tự bóc kiểu; không cần test framework, không cần cài gì thêm.)
 *
 * DOM giả ở đây mô phỏng đúng hai điều thật sự quan trọng:
 *   1. Khung trong panel nhận tên từ CSS (`.khung-nguyen-van`), chip nhận tên
 *      từ inline style — nên gỡ tên bằng chuỗi rỗng KHÔNG đủ cho khung.
 *   2. Ảnh CŨ chụp trước callback cập nhật DOM, ảnh MỚI chụp sau.
 */

const TEN = 'khung-dang-mo';

interface PhanTuGia {
  khop: string[];
  tenCss: string | null;
  style: { viewTransitionName: string };
}

function taoPhanTu(khop: string[], tenCss: string | null = null): PhanTuGia {
  return { khop, tenCss, style: { viewTransitionName: '' } };
}

let trongCay: PhanTuGia[] = [];
/** Mỗi phần tử: [nhãn ảnh, tên mà từng phần tử đang mang]. */
const anhChup: { nhan: string; ten: string[] }[] = [];

function tenHienTai(phanTu: PhanTuGia): string {
  // Inline thắng CSS; chuỗi rỗng nghĩa là "không có khai báo inline" nên CSS
  // thắng lại — đúng như cascade thật.
  if (phanTu.style.viewTransitionName !== '') return phanTu.style.viewTransitionName;
  return phanTu.tenCss ?? 'none';
}

function chupAnh(nhan: string): void {
  anhChup.push({
    nhan,
    ten: trongCay.map(tenHienTai).filter((ten) => ten !== 'none'),
  });
}

const capNhatDaChay: string[] = [];

/** `defineProperty` chứ không phải gán thẳng: `globalThis.document` có kiểu
 *  `Document`, và gán một DOM giả vào đó cần một `as any` — thứ mà quy ước của
 *  dự án cấm. Đây là cùng một việc, không nói dối trình biên dịch. */
function datToanCuc(ten: string, gia: unknown): void {
  Object.defineProperty(globalThis, ten, { value: gia, configurable: true, writable: true });
}

datToanCuc('document', {
  documentElement: { classList: { add() {}, remove() {} } },
  querySelector(chon: string) {
    return trongCay.find((phanTu) => phanTu.khop.includes(chon)) ?? null;
  },
  querySelectorAll(chon: string) {
    const cac = chon.split(',').map((phan) => phan.trim());
    return trongCay.filter((phanTu) => cac.some((mot) => phanTu.khop.includes(mot)));
  },
  startViewTransition(capNhat: () => void) {
    chupAnh('CŨ');
    capNhat();
    chupAnh('MỚI');
    return { finished: Promise.resolve() };
  },
});

datToanCuc('window', { matchMedia: () => ({ matches: false }) });
datToanCuc('getComputedStyle', (phanTu: PhanTuGia) => ({
  viewTransitionName: tenHienTai(phanTu),
}));

const { moKhung, dongKhung } = await import('../src/lib/chuyenCanh.ts');

let hong = 0;

function kiem(ten: string, dung: boolean): void {
  if (!dung) {
    hong += 1;
    process.stderr.write(`HONG: ${ten}\n`);
  }
}

function batDauCanh(): void {
  anhChup.length = 0;
  capNhatDaChay.length = 0;
}

/** Bất biến của API, kiểm trên MỌI ảnh vừa chụp. */
function kiemDuyNhat(canh: string): void {
  for (const anh of anhChup) {
    const soLan = anh.ten.filter((ten) => ten === TEN).length;
    kiem(`${canh} · ảnh ${anh.nhan}: chỉ một phần tử mang "${TEN}" (đếm ${soLan})`, soLan <= 1);
  }
}

const CHIP_0 = '[data-khung="0"]';
const CHIP_1 = '[data-khung="1"]';
const KHUNG = '.khung-nguyen-van';

// 1. Mở trích dẫn khi CHƯA có panel nào — lượt chuyển đầu tiên, vốn vẫn chạy
//    đúng trước khi sửa. Giữ lại để bản sửa không đánh đổi lượt đầu lấy lượt sau.
{
  batDauCanh();
  const chip0 = taoPhanTu(['[data-khung]', CHIP_0]);
  const chip1 = taoPhanTu(['[data-khung]', CHIP_1]);
  trongCay = [chip0, chip1];
  const panel = taoPhanTu(['.khung-nguyen-van'], TEN);
  moKhung(0, () => {
    trongCay = [chip0, chip1, panel]; // panel mở ra
    capNhatDaChay.push('mo-0');
  });
  kiemDuyNhat('mở khi chưa có panel');
  kiem('mở khi chưa có panel: capNhat đã chạy', capNhatDaChay.length === 1);
  kiem('mở khi chưa có panel: ảnh CŨ là chip', anhChup[0].ten.includes(TEN));
  kiem('mở khi chưa có panel: ảnh MỚI có khung', anhChup[1].ten.includes(TEN));
  kiem('mở khi chưa có panel: chip nhả tên sau khi chụp MỚI', chip0.style.viewTransitionName === '');
}

// 2. LỖI ĐÃ TÁI HIỆN TRÊN TRÌNH DUYỆT: bấm sang trích dẫn khác KHI PANEL ĐANG
//    MỞ. Trước khi sửa, ảnh CŨ có hai phần tử mang tên (chip + khung của panel
//    cũ) và trình duyệt huỷ lượt chuyển.
{
  batDauCanh();
  const chip0 = taoPhanTu(['[data-khung]', CHIP_0]);
  const chip1 = taoPhanTu(['[data-khung]', CHIP_1]);
  const panelCu = taoPhanTu([KHUNG], TEN);
  const panelMoi = taoPhanTu([KHUNG], TEN);
  trongCay = [chip0, chip1, panelCu];
  moKhung(1, () => {
    trongCay = [chip0, chip1, panelMoi]; // panel remount theo `key`
    capNhatDaChay.push('mo-1');
  });
  kiemDuyNhat('đổi trích dẫn khi panel đang mở');
  kiem('đổi trích dẫn: capNhat đã chạy', capNhatDaChay.length === 1);
  // Chính chỗ này là lỗi: TRƯỚC khi sửa, ảnh CŨ đếm được 2 (chip + khung của
  // panel đang mở), và trình duyệt huỷ cả lượt chuyển.
  kiem('đổi trích dẫn: ảnh CŨ mang tên (là chip)', anhChup[0].ten.filter((t) => t === TEN).length === 1);
  kiem('đổi trích dẫn: ảnh MỚI mang tên (là khung mới)', anhChup[1].ten.filter((t) => t === TEN).length === 1);
  kiem('đổi trích dẫn: chip nhả tên ở ảnh MỚI', chip1.style.viewTransitionName === '');
  kiem('đổi trích dẫn: panel cũ được hoàn nguyên', panelCu.style.viewTransitionName === '');
}

// 3. Thoái lui: khung morph ngược về chip. Ảnh MỚI phải có đúng chip mang tên.
{
  batDauCanh();
  const chip0 = taoPhanTu(['[data-khung]', CHIP_0]);
  const panel = taoPhanTu([KHUNG], TEN);
  trongCay = [chip0, panel];
  dongKhung(0, () => {
    trongCay = [chip0]; // panel đóng
    capNhatDaChay.push('dong-0');
  });
  kiemDuyNhat('đóng panel');
  kiem('đóng panel: capNhat đã chạy', capNhatDaChay.length === 1);
  kiem('đóng panel: ảnh CŨ là khung', anhChup[0].ten.filter((t) => t === TEN).length === 1);
  kiem('đóng panel: ảnh MỚI là chip', anhChup[1].ten.filter((t) => t === TEN).length === 1);
}

// 4. Không có chip (dải khung đã bị thay bởi kết quả khác): không chuyển cảnh,
//    nhưng trạng thái VẪN phải đổi — mất animation không được kéo theo mất dữ liệu.
{
  batDauCanh();
  trongCay = [taoPhanTu([KHUNG], TEN)];
  moKhung(7, () => capNhatDaChay.push('mo-7'));
  kiem('không có chip: capNhat vẫn chạy', capNhatDaChay.length === 1);
  kiem('không có chip: không mở lượt chuyển nào', anhChup.length === 0);
}

if (hong > 0) {
  process.stderr.write(`${hong} phép kiểm HỎNG\n`);
  process.exit(1);
}
process.stdout.write('kiem-chuyen-canh: tất cả phép kiểm ĐẠT\n');
