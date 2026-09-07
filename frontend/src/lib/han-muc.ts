import type { HanMuc, MucHanMuc } from "./klaw";

export const KHONG_GIOI_HAN = 100_000;
export const laKhongGioiHan = (hanMuc: number): boolean => hanMuc >= KHONG_GIOI_HAN;

export function phanTram(m: MucHanMuc): number {
  if (laKhongGioiHan(m.han_muc) || m.han_muc <= 0) return 0;
  return Math.min(100, Math.round((m.da_dung / m.han_muc) * 100));
}

export function mucMau(pt: number): "brass" | "amber" | "do" {
  return pt >= 100 ? "do" : pt >= 80 ? "amber" : "brass";
}

export function dinhDangMoc(iso: string | null, muiGio: string): string {
  if (iso === null) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const gio = new Intl.DateTimeFormat("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: muiGio,
  }).format(t);
  // ICU `vi-VN` dùng dấu "-" khi định dạng ngày/tháng KHÔNG kèm năm, nhưng dùng
  // "/" khi có năm (đo trên Node 22 đang chạy) — cùng quirk `thoiGianTuongDoi`
  // đã né. Dựng kèm năm rồi cắt bỏ, thay vì tin dạng "Md" không kèm năm.
  const ngayNam = new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: muiGio,
  }).format(t);
  const ngay = ngayNam.slice(0, ngayNam.lastIndexOf("/"));
  return `${gio} ${ngay}`;
}

export function soNgayCon(iso: string | null): number | null {
  if (iso === null) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : Math.max(0, Math.ceil((t - Date.now()) / 86_400_000));
}

/** Mục đầu tiên có trần thật — chip cạnh ô hỏi theo dõi mục này. */
export function mucRangBuoc(hm: HanMuc | null): MucHanMuc | null {
  return hm?.muc.find((m) => !laKhongGioiHan(m.han_muc)) ?? null;
}

const DON_VI: Record<string, [string, string]> = {
  hoi_dap_ngay: ["lượt", "hôm nay"],
  soan_thao_ngay: ["bản thảo", "hôm nay"],
  soan_thao_thang: ["bản thảo", "tháng này"],
};

export function cauChip(m: MucHanMuc): string {
  const con = Math.max(0, m.han_muc - m.da_dung);
  if (m.khoa === "khach_24h") return `Còn ${con}/${m.han_muc} lượt thử`;
  const [dv, ky] = DON_VI[m.khoa] ?? ["lượt", ""];
  return (con === 0 ? `Hết ${dv} ${ky}` : `Còn ${con} ${dv} ${ky}`).trim();
}
