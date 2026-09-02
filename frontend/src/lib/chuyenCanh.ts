import { flushSync } from 'react-dom';

/**
 * "Tiến tới khung" — View Transitions API gốc trình duyệt, không thư viện
 * animation (motion-spec.md §1).
 *
 * Ràng buộc của API: `view-transition-name` phải DUY NHẤT tại một thời điểm.
 * Chip trích dẫn mang tên ở ảnh chụp CŨ, khung trong panel mang tên ở ảnh chụp
 * MỚI — nên tên phải được gỡ khỏi chip ngay bên trong callback cập nhật DOM,
 * chứ không phải sau khi chuyển cảnh xong.
 *
 * Ràng buộc đó nay được THI HÀNH bằng `datTenDuyNhat`, không còn dựa vào việc
 * mỗi người gọi nhớ tự gỡ: `scripts/kiem-chuyen-canh.ts` chụp lại cả hai ảnh
 * của cả ba kịch bản và hỏng nếu có ảnh nào chứa hai phần tử cùng tên.
 */
const TEN_KHUNG_DANG_MO = 'khung-dang-mo';

/** Lớp bật trong lúc chuyển cảnh nội bộ, để hiệu ứng "đổi khay" (chuyển giữa
 *  ba màn hình) không chạy lây sang mỗi lần bấm một trích dẫn. */
const LOP_CHUYEN_TRONG_TRANG = 'chuyen-trong-trang';

function giamChuyenDong(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function coTheChuyenCanh(): boolean {
  // prefers-reduced-motion: bỏ hẳn View Transition, cuộn thẳng tới khung
  // (motion-spec.md §6) — trạng thái vẫn đổi, chỉ không có chuyển động.
  return 'startViewTransition' in document && !giamChuyenDong();
}

function batDauChuyen(capNhat: () => void, donDep: () => void): void {
  const goc = document.documentElement;
  goc.classList.add(LOP_CHUYEN_TRONG_TRANG);
  const luot = document.startViewTransition(() => {
    flushSync(capNhat);
  });
  void luot.finished.finally(() => {
    goc.classList.remove(LOP_CHUYEN_TRONG_TRANG);
    donDep();
  });
}

function timChip(chiSo: number): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[data-khung="${chiSo}"]`);
}

/**
 * Mọi phần tử ĐANG mang tên: chip (gán inline ở đây) và khung nguyên văn
 * trong panel (gán bằng CSS, `.khung-nguyen-van`). Đọc computed style chứ
 * không đọc `style.viewTransitionName`, vì nguồn gán của hai bên khác nhau.
 */
function dangMangTen(): HTMLElement[] {
  const ungVien = document.querySelectorAll<HTMLElement>('[data-khung], .khung-nguyen-van');
  return [...ungVien].filter(
    (phanTu) => getComputedStyle(phanTu).viewTransitionName === TEN_KHUNG_DANG_MO,
  );
}

/**
 * Gán tên cho ĐÚNG một phần tử, gỡ khỏi mọi phần tử khác đang mang nó; trả về
 * hàm hoàn nguyên.
 *
 * Vì sao phải có: khi panel ĐANG MỞ mà bấm sang trích dẫn khác, khung trong
 * panel vẫn mang tên từ CSS còn chip sắp mang tên từ đây — hai phần tử cùng
 * tên trong một ảnh chụp. Trình duyệt không animate mà HUỶ THẲNG cả lượt
 * chuyển (`InvalidStateError: Transition was aborted because of invalid
 * state`), nên từ lần chuyển thứ hai trở đi động tác trung tâm của sản phẩm
 * biến mất. `'none'` (chứ không phải chuỗi rỗng) mới đè được lên khai báo
 * CSS; chuỗi rỗng chỉ xoá lớp inline và để CSS thắng lại.
 */
function datTenDuyNhat(giu: HTMLElement | null): () => void {
  const khac = dangMangTen().filter((phanTu) => phanTu !== giu);
  for (const phanTu of khac) phanTu.style.viewTransitionName = 'none';
  if (giu !== null) giu.style.viewTransitionName = TEN_KHUNG_DANG_MO;
  return () => {
    if (giu !== null) giu.style.viewTransitionName = '';
    for (const phanTu of khac) phanTu.style.viewTransitionName = '';
  };
}

/** Chuyển cảnh chung (ô hỏi trượt lên đầu, kết quả hiện ra…). */
export function chuyenCanh(capNhat: () => void): void {
  if (!coTheChuyenCanh()) {
    capNhat();
    return;
  }
  batDauChuyen(capNhat, () => {});
}

/** Tiến tới khung: chip trích dẫn morph thành khung nguyên văn trong panel. */
export function moKhung(chiSo: number, capNhat: () => void): void {
  const chip = timChip(chiSo);
  if (!coTheChuyenCanh() || !chip) {
    capNhat();
    return;
  }
  // Ảnh CŨ: chỉ chip mang tên — panel đang mở (nếu có) bị gỡ tên ở đây.
  const hoanNguyen = datTenDuyNhat(chip);
  batDauChuyen(
    () => {
      // Ảnh MỚI: trả tên về cho khung trong panel, gỡ khỏi chip. Hoàn nguyên
      // Ở ĐÂY chứ không ở `donDep`, vì `donDep` chạy SAU khi chụp ảnh mới —
      // lúc đó khung mới đã bị chụp mà không có tên, tức không có gì để morph
      // tới.
      hoanNguyen();
      capNhat();
    },
    hoanNguyen,
  );
}

/** Thoái lui: khung trong panel morph ngược về chip trích dẫn. */
export function dongKhung(chiSo: number, capNhat: () => void): void {
  const chip = timChip(chiSo);
  if (!coTheChuyenCanh() || !chip) {
    capNhat();
    return;
  }
  let hoanNguyen = () => {};
  batDauChuyen(
    () => {
      // `capNhat` gỡ panel trước, rồi chip mới nhận tên — thứ tự này bảo đảm
      // ảnh MỚI cũng chỉ có đúng một phần tử mang tên.
      capNhat();
      hoanNguyen = datTenDuyNhat(chip);
    },
    () => hoanNguyen(),
  );
}
