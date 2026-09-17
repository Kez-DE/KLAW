/** Tay kéo theo W3C Window Splitter (spec 2026-09-09 §9.1): kẹp bề rộng, tính
 *  phần trăm cho `aria-valuenow`, biên panel đối chiếu theo bề rộng cửa sổ, và
 *  độ rộng nhớ được sống sót qua một lượt tải lại trang (hoặc một localStorage
 *  không đọc/ghi được). Chạy: `npm run kiem-keo-dan`. */
import assert from "node:assert/strict";
import {
  BUOC_PHIM,
  RONG_DOI_CHIEU_MAC_DINH,
  RONG_SAN_KHAU_MAC_DINH,
  bienPanelDoiChieu,
  docRongDaLuu,
  kepRong,
  luuRong,
  phanTram,
} from "../src/lib/keo-dan.ts";

assert.equal(RONG_DOI_CHIEU_MAC_DINH, 420);
assert.equal(RONG_SAN_KHAU_MAC_DINH, 640);
assert.deepEqual(bienPanelDoiChieu(1440), { min: 320, max: 864 });
assert.deepEqual(bienPanelDoiChieu(1000), { min: 320, max: 520 }); // 1000 - 480 chat tối thiểu
assert.deepEqual(bienPanelDoiChieu(700), { min: 320, max: 320 });
assert.equal(kepRong(100, { min: 320, max: 864 }), 320);
assert.equal(kepRong(900, { min: 320, max: 864 }), 864);
assert.equal(kepRong(500, { min: 320, max: 864 }), 500);
assert.equal(phanTram(320, { min: 320, max: 864 }), 0);
assert.equal(phanTram(864, { min: 320, max: 864 }), 100);
assert.equal(phanTram(592, { min: 320, max: 864 }), 50);
assert.equal(BUOC_PHIM, 24);

// Vòng đời "tải lại trang": một localStorage thật (giả bằng Map) đứng ở giữa
// `luuRong` (lúc kéo/thu gọn/về mặc định) và `docRongDaLuu` (lúc trang mở
// lại). Thu gọn về biên rồi tải lại phải VỀ ĐÚNG biên đó; về mặc định rồi tải
// lại phải VỀ ĐÚNG mặc định — hai hành động này đi qua `datRongVaLuu` ở
// `dung-thu.tsx`, không có nhánh riêng nào bỏ qua `luuRong`.
const kho = new Map<string, string>();
globalThis.localStorage = {
  getItem: (khoa: string) => (kho.has(khoa) ? (kho.get(khoa) ?? null) : null),
  setItem: (khoa: string, gt: string) => {
    kho.set(khoa, gt);
  },
} as Storage;

const BIEN_1440 = bienPanelDoiChieu(1440);
luuRong("klaw.doi-chieu.rong", BIEN_1440.min); // thu gọn
assert.equal(docRongDaLuu("klaw.doi-chieu.rong", RONG_DOI_CHIEU_MAC_DINH), BIEN_1440.min);
luuRong("klaw.doi-chieu.rong", RONG_DOI_CHIEU_MAC_DINH); // về mặc định
assert.equal(docRongDaLuu("klaw.doi-chieu.rong", RONG_DOI_CHIEU_MAC_DINH), RONG_DOI_CHIEU_MAC_DINH);

// Khoá chưa từng ghi (lần mở đầu tiên, chưa ai kéo) → mặc định, không phải lỗi.
assert.equal(docRongDaLuu("chua-tung-ghi", RONG_DOI_CHIEU_MAC_DINH), RONG_DOI_CHIEU_MAC_DINH);

// Độ rộng lưu từ một màn RỘNG HƠN, mở lại trên màn hẹp hơn (không cần resize
// trong phiên): giá trị đọc ra phải được KẸP theo biên hiện tại ngay lúc khởi
// tạo state, không phải giá trị thô đã lưu — đây là đúng lỗi "hồi sinh" mà
// bản vá này sửa (kẹp ngay biểu thức khởi tạo state, không đợi resize).
kho.set("khoa-rong", "900");
assert.equal(kepRong(docRongDaLuu("khoa-rong", RONG_DOI_CHIEU_MAC_DINH), BIEN_1440), BIEN_1440.max);

// Giá trị lưu không phải số (dữ liệu hỏng, hoặc bị ai đó ghi tay) → mặc định.
kho.set("khong-phai-so", "khong-phai-so");
assert.equal(docRongDaLuu("khong-phai-so", RONG_DOI_CHIEU_MAC_DINH), RONG_DOI_CHIEU_MAC_DINH);

// localStorage có tồn tại nhưng ĐỌC/GHI đều ném lỗi (chế độ riêng tư, quyền bị
// chặn…): đọc phải rơi về mặc định, ghi phải im lặng — cả hai KHÔNG được ném.
globalThis.localStorage = {
  getItem: () => {
    throw new Error("khong-doc-duoc");
  },
  setItem: () => {
    throw new Error("khong-ghi-duoc");
  },
} as unknown as Storage;
assert.equal(docRongDaLuu("klaw.doi-chieu.rong", RONG_DOI_CHIEU_MAC_DINH), RONG_DOI_CHIEU_MAC_DINH);
assert.doesNotThrow(() => luuRong("klaw.doi-chieu.rong", 500));

console.log("kiem-keo-dan: 19/19 OK");
