/**
 * Bỏ dấu tiếng Việt và bung viết tắt, dùng cho việc TÔ SÁNG phía client.
 *
 * Máy chủ cố ý không tô sáng: `chunks.tsv` dựng trên `unaccent(...)` nên
 * `ts_headline` chạy trên bản không dấu sẽ trả về tiếng Việt mất dấu, không đọc
 * được. Tô sáng vì vậy là việc của FE, và nó chỉ cần hai hàm ở đây.
 *
 * Đây là phần còn lại của `lib/van-ban.ts` sau khi nối backend. Module đó là
 * kho văn bản GIẢ (`VAN_BAN: []`) cùng một bộ tìm kiếm chạy trên chính kho rỗng
 * ấy; toàn bộ đã chết khi `/tim-kiem` và `/van-ban/{doc_id}` lên thay. Giữ lại
 * một module rỗng ruột mang tên "van-ban" sẽ mời người sau đổ dữ liệu vào đó
 * lần nữa.
 */

export const boDau = (s: string) =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/gi, "d").toLowerCase();

/** Viết tắt thông dụng của giới hành nghề, để tô sáng bắt được cả bản đầy đủ. */
const VIET_TAT: Record<string, string> = {
  bllđ: "Bộ luật Lao động",
  blld: "Bộ luật Lao động",
  blds: "Bộ luật Dân sự",
  blhs: "Bộ luật Hình sự",
  ldn: "Luật Doanh nghiệp",
  ltm: "Luật Thương mại",
  nđ: "Nghị định",
  nd: "Nghị định",
  tt: "Thông tư",
  qđ: "Quyết định",
  qd: "Quyết định",
  nq: "Nghị quyết",
  vbhn: "Văn bản hợp nhất",
};

/** Mở rộng truy vấn: bỏ dấu + bung viết tắt. Chỉ phục vụ tô sáng, KHÔNG truy hồi. */
export function moRongTruyVan(q: string): string[] {
  const tho = q.trim();
  const cum = new Set<string>();
  if (tho !== "") cum.add(boDau(tho));
  for (const tu of tho.split(/\s+/)) {
    const khoa = tu.toLowerCase();
    const day = VIET_TAT[khoa] ?? VIET_TAT[boDau(khoa)];
    if (day !== undefined) cum.add(boDau(day));
  }
  return [...cum];
}
