/** Tay kéo theo W3C Window Splitter (spec 2026-09-09 §9.1): kẹp bề rộng, tính
 *  phần trăm cho `aria-valuenow`, biên panel đối chiếu theo bề rộng cửa sổ, và
 *  độ rộng nhớ được sống sót qua một lượt tải lại trang (hoặc một localStorage
 *  không đọc/ghi được). Chạy: `npm run kiem-keo-dan`. */
import assert from "node:assert/strict";
import {
  BUOC_PHIM,
  CHAT_TOI_THIEU,
  RONG_DOI_CHIEU_MAC_DINH,
  RONG_SAN_KHAU_MAC_DINH,
  RONG_TAY_KEO_PX,
  RONG_TOI_THIEU,
  bienPanelDoiChieu,
  docRongDaLuu,
  kepRong,
  luuRong,
  phanTram,
  sanRongChat,
} from "../src/lib/keo-dan.ts";

assert.equal(RONG_DOI_CHIEU_MAC_DINH, 420);
assert.equal(RONG_SAN_KHAU_MAC_DINH, 640);
assert.deepEqual(bienPanelDoiChieu(1440), { min: 320, max: 864 });
assert.deepEqual(bienPanelDoiChieu(1000), { min: 320, max: 512 }); // 1000 - 480 chat - 8 TayKeo
assert.deepEqual(bienPanelDoiChieu(700), { min: 320, max: 320 });

// Không tràn ngang (Phase 9 U4 fix round 1) — panel đứng ở ĐÚNG trần nó tự
// báo (`bien.max`), cộng sàn chat (`CHAT_TOI_THIEU`, `sanRongChat`) cộng
// `TayKeo`, không bao giờ được vượt bề rộng THẬT đưa vào `bienPanelDoiChieu`.
// Đo được thật TRƯỚC bản vá này: cửa sổ 1467px trừ cột trái 260px ra
// `rongHang=1207`, panel đứng ở trần tự báo 724 + sàn chat 480 + TayKeo 8 =
// 1212 > 1207 — tràn 5px (`document.documentElement.scrollWidth >
// clientWidth`). Chỉ đo từ ngưỡng "đủ chỗ cho cả ba phần ở mức tối thiểu"
// trở lên (`NGUONG_KHONG_TRAN`) — dưới ngưỡng đó `RONG_TOI_THIEU` VÀ
// `CHAT_TOI_THIEU` cùng đòi chỗ tối thiểu vượt quá khung nhìn, một ràng buộc
// không thể giải quyết bằng công thức (khi đó `haiCot` đã tắt bố cục hai cột
// từ trước, xem `useHaiCot` trong `KhungDoiChieu.tsx`), không phải lỗi của
// hàm này.
const NGUONG_KHONG_TRAN = RONG_TOI_THIEU + CHAT_TOI_THIEU + RONG_TAY_KEO_PX;
for (const w of [NGUONG_KHONG_TRAN, 1000, 1207, 1440, 2000]) {
  const bien = bienPanelDoiChieu(w);
  assert.ok(
    bien.max + CHAT_TOI_THIEU + RONG_TAY_KEO_PX <= w,
    `bienPanelDoiChieu(${w}).max=${bien.max} cộng sàn chat cộng TayKeo phải vừa trong ${w}`,
  );
}
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

// Sàn cột chat (Phase 9 U4) — mọi trường hợp bình thường (kể cả sân khấu bản
// thảo mở cạnh chat) phải có sàn CỨNG bằng đúng `CHAT_TOI_THIEU`, bất kể
// `bienPanelDoiChieu` tính trần khung bên cạnh đúng hay sai (đo được cửa sổ
// 1512px vẫn ra chat ~215px trước bản vá này). Khung hẹp CHỌN LOẠI văn bản
// (420px, tính năng khác) là ngoại lệ DUY NHẤT — sàn ở đó sẽ đè mất đúng chủ
// đích hẹp của nó.
assert.equal(sanRongChat(false), CHAT_TOI_THIEU);
assert.equal(sanRongChat(true), undefined);
assert.equal(CHAT_TOI_THIEU, 480);

console.log("kiem-keo-dan: 27/27 OK");
