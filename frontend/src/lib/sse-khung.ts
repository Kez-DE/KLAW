/**
 * Tách khung Server-Sent Events.
 *
 * Ở riêng một file, không import gì, vì hai lý do:
 *
 * 1. **Đây là một bộ phân tích cú pháp**, tức thứ sai âm thầm được: một khung
 *    bị bỏ sót không ném lỗi, nó chỉ làm một bước biến mất khỏi thanh tiến
 *    trình — hoặc tệ hơn, làm `ket_qua` không bao giờ tới và màn hình chờ quay
 *    mãi. Nên nó phải có kiểm chạy được (`npm run kiem-sse`), và kiểm đó chỉ
 *    chạy được khi file không kéo theo `fetch`, Supabase hay `import.meta.env`.
 * 2. Nó không biết gì về KLAW. Giữ nó thuần cũng là giữ nó đọc được cạnh
 *    đặc tả SSE.
 *
 * KHÔNG thêm thư viện: bộ tách khung là chừng này dòng, và
 * `@microsoft/fetch-event-source` sẽ là một phụ thuộc mới cho đúng chừng đó.
 */

export interface KhungSSE {
  ten: string;
  duLieu: unknown;
}

/**
 * Tách MỘT khung (phần văn bản giữa hai dòng trống) thành tên sự kiện và
 * payload đã parse.
 *
 * Trả `null` khi khung không dùng được: thiếu `event:`, thiếu `data:`, hoặc
 * JSON hỏng. Nơi gọi bỏ qua khung đó và đọc tiếp — một khung rác không được
 * phép giết cả stream, nhưng cũng không được phép giả vờ là một sự kiện hợp lệ.
 */
export function tachKhungSSE(khung: string): KhungSSE | null {
  let ten = "";
  const dongData: string[] = [];

  for (const dong of khung.split("\n")) {
    // Dòng mở đầu bằng ':' là chú thích — đặc tả SSE dùng nó làm heartbeat
    // (`: ping`). Máy chủ KLAW chưa gửi, nhưng một reverse proxy có thể chèn,
    // và một chú thích bị đọc thành dữ liệu sẽ làm hỏng cả khung.
    if (dong.startsWith(":")) continue;
    if (dong.startsWith("event:")) ten = dong.slice(6).trim();
    // Đặc tả bỏ ĐÚNG MỘT dấu cách sau `data:`, không phải trim: một payload
    // JSON không bao giờ mở đầu bằng khoảng trắng có nghĩa, nhưng cắt nhiều
    // hơn một ký tự là làm sai đặc tả ở chỗ khác cũng sẽ sai.
    else if (dong.startsWith("data:")) dongData.push(dong.slice(5).replace(/^ /, ""));
  }

  if (ten === "" || dongData.length === 0) return null;
  try {
    // Nhiều dòng `data:` nối lại bằng `\n`, theo đặc tả.
    return { ten, duLieu: JSON.parse(dongData.join("\n")) };
  } catch {
    return null;
  }
}

/**
 * Cắt bộ đệm thành các khung đã hoàn chỉnh, trả phần đuôi còn dang dở.
 *
 * `ReadableStream` cắt theo ranh giới GÓI TIN, không theo ranh giới khung: một
 * sự kiện SSE có thể về làm hai lần đọc, và hai sự kiện có thể về cùng một lần.
 * Hàm này là chỗ duy nhất biết điều đó.
 */
export function catCacKhung(dem: string): { khung: KhungSSE[]; con: string } {
  // `\r\n` chuẩn hoá về `\n` để một máy chủ (hay proxy) dùng CRLF không làm
  // ranh giới khung biến mất.
  const chuan = dem.replace(/\r\n/g, "\n");
  const khung: KhungSSE[] = [];
  let con = chuan;

  for (let ranh = con.indexOf("\n\n"); ranh !== -1; ranh = con.indexOf("\n\n")) {
    const mot = tachKhungSSE(con.slice(0, ranh));
    con = con.slice(ranh + 2);
    if (mot !== null) khung.push(mot);
  }
  return { khung, con };
}
