import type { ThongBao } from "./klaw";

/**
 * Thuần, không `fetch`/Supabase/`import.meta.env` — cùng lý do với
 * `sse-khung.ts`: hàm ở đây phải kiểm được bằng `npm run kiem-thong-bao`
 * không cần dựng cả ứng dụng. Cùng logic với `cms/src/components/ChuongThongBao/bell.ts`
 * (Task 17), viết lại vì hai gói không chia sẻ mã.
 */

const TRAN_BADGE = 99;

/** Số chưa đọc thành nhãn hiển thị. `0` không có huy hiệu; trên `99` gộp thành "99+". */
export function formatBadge(n: number): string | null {
  if (n <= 0) return null;
  return n > TRAN_BADGE ? `${TRAN_BADGE}+` : String(n);
}

type NhomNgay = "hom_nay" | "hom_qua" | "truoc_do";
const NHAN: Record<NhomNgay, string> = {
  hom_nay: "Hôm nay",
  hom_qua: "Hôm qua",
  truoc_do: "Trước đó",
};

function dauNgay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function nhomCua(taoLuc: string, now: Date): NhomNgay {
  const luc = new Date(taoLuc);
  if (Number.isNaN(luc.getTime())) return "truoc_do";
  const homNay = dauNgay(now);
  const homQua = dauNgay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1));
  const ngayCuaLuc = dauNgay(luc);
  if (ngayCuaLuc >= homNay) return "hom_nay";
  if (ngayCuaLuc >= homQua) return "hom_qua";
  return "truoc_do";
}

/** Nhóm thông báo theo "Hôm nay" / "Hôm qua" / "Trước đó", bỏ nhóm rỗng. */
export function nhomTheoNgay(items: ThongBao[], now: Date): { nhan: string; items: ThongBao[] }[] {
  const thuTu: NhomNgay[] = ["hom_nay", "hom_qua", "truoc_do"];
  return thuTu
    .map((nhom) => ({
      nhan: NHAN[nhom],
      items: items.filter((tb) => nhomCua(tb.tao_luc, now) === nhom),
    }))
    .filter((n) => n.items.length > 0);
}

/**
 * Đường điều hướng khi bấm một thông báo. `duong_dan` đến từ dữ liệu máy chủ
 * (do CMS ghi khi tạo thông báo), nên một giá trị lạ không được phép kéo
 * người dùng ra khỏi ứng dụng — chỉ nhận `/tai-khoan` hoặc `/dung-thu` (và các
 * đường con/`?query` của chúng).
 */
export function duongDanTrongApp(duong: string): string {
  const anToan =
    duong === "/tai-khoan" ||
    duong === "/dung-thu" ||
    duong.startsWith("/tai-khoan?") ||
    duong.startsWith("/tai-khoan/") ||
    duong.startsWith("/dung-thu?") ||
    duong.startsWith("/dung-thu/");
  return anToan ? duong : "/tai-khoan";
}
