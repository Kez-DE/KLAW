import { flushSync } from 'react-dom';

/**
 * "Tiến tới khung" — View Transitions API gốc trình duyệt, không thư viện
 * animation (motion-spec.md §1).
 *
 * Ràng buộc của API: `view-transition-name` phải DUY NHẤT tại một thời điểm.
 * Chip trích dẫn mang tên ở ảnh chụp CŨ, khung trong panel mang tên ở ảnh chụp
 * MỚI — nên tên phải được gỡ khỏi chip ngay bên trong callback cập nhật DOM,
 * chứ không phải sau khi chuyển cảnh xong. Hai phần tử cùng tên trong một lượt
 * chuyển sẽ làm hỏng nó.
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
  chip.style.viewTransitionName = TEN_KHUNG_DANG_MO; // có mặt ở ảnh CŨ
  batDauChuyen(
    () => {
      chip.style.viewTransitionName = ''; // gỡ trước khi chụp ảnh MỚI
      capNhat();
    },
    () => {
      chip.style.viewTransitionName = '';
    },
  );
}

/** Thoái lui: khung trong panel morph ngược về chip trích dẫn. */
export function dongKhung(chiSo: number, capNhat: () => void): void {
  const chip = timChip(chiSo);
  if (!coTheChuyenCanh() || !chip) {
    capNhat();
    return;
  }
  batDauChuyen(
    () => {
      chip.style.viewTransitionName = TEN_KHUNG_DANG_MO; // có mặt ở ảnh MỚI
      capNhat();
    },
    () => {
      chip.style.viewTransitionName = '';
    },
  );
}
