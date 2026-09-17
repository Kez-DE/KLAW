import { cn } from "@/lib/utils";
import { nhipHangVe, tiLeCotVe, tieuDeDaXuatHienTrongThan, type Muc } from "@/lib/xuat-tep";

interface Props {
  tieuDe: string;
  kyHieu?: string | null;
  muc: Muc[];
  thuPhong: number; // 50–150
  hienCanCu: boolean;
  mucDangChon?: string | null;
  onChonMuc?: (key: string) => void;
  /**
   * Bản thảo KHÔNG theo checklist (S6, `loai === "tong_quat"`): mục lấy tên
   * và cách đánh số từ CHÍNH tài liệu nguồn, nên tiền tố "Mục {stt}." của
   * KLAW (đúng cho một bản thảo theo checklist, nơi khung mới là chỗ đặt tên)
   * ở đây chỉ đấu với cách tài liệu tự đánh số (Phase 7 R5).
   */
  laTongQuat?: boolean;
}

/**
 * Trang A4 xem trước cho bản thảo `BanThao` (khung "sân khấu", Task 24).
 *
 * Bấm một mục để đánh dấu nó là đích cho lệnh sửa kế tiếp (khuôn Canvas "chọn vùng").
 * Mục bấm được luôn thao tác được bằng bàn phím (Enter/Space), không chỉ bằng chuột.
 */
export function XemTruocA4({
  tieuDe,
  kyHieu,
  muc,
  thuPhong,
  hienCanCu,
  mucDangChon = null,
  onChonMuc,
  laTongQuat = false,
}: Props) {
  const chonMuc = (key: string) => onChonMuc?.(key);

  // Phase 11 R4 — một bản thảo TỔNG QUÁT tái hiện nguyên văn một tài liệu đã
  // in tiêu đề của nó ra như chữ thân bài (quốc hiệu, tên biểu mẫu…); `<h1>`
  // ở đây khi đó là bản sao KLAW tự thêm, không phải chữ thứ hai của tài
  // liệu — bỏ nó khỏi TRANG, không chỉ ẩn bằng CSS, để `docNoiDungTuDOM`
  // (dùng chung cho `.docx` và PDF) cũng không thấy nó. Một bản thảo KLAW
  // soạn từ đầu (tiêu đề không lặp lại trong thân bài) thì GIỮ `<h1>` — nếu
  // không, trang sẽ vô đề vì không còn chỗ nào khác in ra tên văn bản đó.
  const anTieuDe = laTongQuat && tieuDeDaXuatHienTrongThan(tieuDe, muc);

  return (
    <div className="mx-auto w-full max-w-[794px]" style={{ fontSize: `${thuPhong}%` }}>
      <article className="aspect-[210/297] overflow-y-auto rounded-md border border-border bg-white px-[8%] py-[7%] text-[#111] shadow-soft">
        {/* `<h1>`, không `<h2>`: đây là tiêu đề CHÍNH của văn bản đang xem
            trước, và `docNoiDungTuDOM` (xuat-tep.ts) chỉ nhận diện tiêu đề
            xuất ra Word/PDF qua đúng thẻ `H1`. */}
        {!anTieuDe && (
          <h1 className="m-0 text-center font-serif text-[1.25em] font-bold uppercase tracking-wide">
            {tieuDe}
          </h1>
        )}
        {kyHieu && (
          <p className="mt-1 text-center font-mono text-[0.85em] text-[#555]">Số: {kyHieu}</p>
        )}
        <div className="mt-6 space-y-4">
          {muc.map((m) => (
            <section
              key={m.key}
              data-muc={m.key}
              onClick={onChonMuc ? () => chonMuc(m.key) : undefined}
              onKeyDown={
                onChonMuc
                  ? (e) => {
                      if (e.key !== "Enter" && e.key !== " ") return;
                      e.preventDefault();
                      chonMuc(m.key);
                    }
                  : undefined
              }
              role={onChonMuc ? "button" : undefined}
              tabIndex={onChonMuc ? 0 : undefined}
              aria-current={mucDangChon === m.key ? "true" : undefined}
              aria-label={onChonMuc ? `Chọn mục ${m.stt}. ${m.ten} làm đích chỉnh sửa` : undefined}
              className={cn(
                "rounded-sm px-2 py-1 -mx-2",
                onChonMuc && "cursor-pointer hover:bg-[var(--color-paper-50)]",
                mucDangChon === m.key && "ring-2 ring-[var(--color-brass-600)]",
              )}
            >
              {/* `dieu-head`: dấu hiệu DUY NHẤT mà `docNoiDungTuDOM`
                  (xuat-tep.ts) đọc để biết đây là đầu mục, nên tệp Word/PDF
                  tải về mới có tiêu đề mục thay vì một đoạn thường in đậm.
                  Lớp này chỉ có kiểu dáng trong `.a4-sheet` (styles.css) nên
                  không đổi gì trên màn hình của khung xem trước này.

                  Bản thảo tổng quát (`laTongQuat`) mà tên mục KHÔNG phải chữ
                  thật của tài liệu (`!m.tenThat`, Phase 9 U1) thì KHÔNG render
                  dòng này — đó là nhãn KLAW tự đặt để tổ chức bản thảo, không
                  phải chữ trên trang. Bỏ hẳn `<p>` (không chỉ ẩn bằng CSS) để
                  `docNoiDungTuDOM` — dùng chung cho cả `.docx` và PDF — cũng
                  không thấy nó, đúng yêu cầu "sửa ở một chỗ, đúng cả ba nơi".
                  Bản thảo checklist (`!laTongQuat`) luôn hiện: tên mục ở đó
                  đến từ chính checklist, chưa từng là chữ mô hình bịa. */}
              {(!laTongQuat || m.tenThat) && (
                <p className="dieu-head m-0 font-serif text-[1em] font-semibold">
                  {laTongQuat ? m.ten : `Mục ${m.stt}. ${m.ten}`}
                </p>
              )}
              {/* Nội dung mục là một MẢNG khối theo đúng thứ tự tài liệu
                  (Phase 8 R1, thay hai điều kiện độc lập noiDung/bang cố định
                  của Phase 7): câu dẫn, bảng, câu kết là BA khối riêng, render
                  lần lượt — không còn nén về "văn xuôi rồi bảng" cứng nhắc. */}
              {m.khoi.map((k, i) =>
                k.kind === "vanXuoi" ? (
                  <p
                    key={i}
                    className={cn(
                      // `break-words` (Phase 11 fix round 1, `overflow-wrap:
                      // break-word`) — một dòng trường tự do gõ bằng dấu
                      // CHẤM/GẠCH LIỀN NHAU không có khoảng trắng nào ("Nội
                      // dung công việc được giao: ………...............") không
                      // có chỗ để trình duyệt ngắt dòng theo mặc định (chỉ
                      // ngắt ở khoảng trắng), nên cả trang A4 bị đẩy rộng ra
                      // theo chiều ngang thay vì xuống dòng. Không xoá dấu
                      // chấm/gạch — đó là Ý NGHĨA của biểu mẫu (chỗ để điền)
                      // — chỉ cho phép ngắt NGAY TRONG một chuỗi liền không
                      // ngắt được cách nào khác.
                      "m-0 mt-1 whitespace-pre-wrap break-words font-serif text-[1em] leading-relaxed",
                      // Căn lề THẬT của tài liệu nguồn (Phase 9 U5) — đọc
                      // ngược lại qua `getComputedStyle(...).textAlign` ở
                      // `xuat-tep.ts::docDong`, nên `.docx`/PDF tự khớp theo.
                      k.canhLe === "giua" && "text-center",
                      k.canhLe === "phai" && "text-right",
                    )}
                  >
                    {k.noiDung}
                  </p>
                ) : (
                  // Khối BẢNG trong tài liệu nguồn (Phase 7 R1/R2) — `<table>`
                  // THẬT, không phải chữ `|` improv: hàng đầu là tiêu đề, viền
                  // thấy được. Hàng ngắn hơn hàng tiêu đề (Phase 8 R4, ô gộp
                  // trong tài liệu nguồn) dùng `colSpan` qua `k.nhip` — nhịp
                  // THẬT khi bảng có khai lưới nguồn (Phase 11 R6, đọc
                  // `w:gridSpan`), suy từ số ô khi không (`nhipHangVe` rơi về
                  // `coSpanHang` cũ). `<colgroup>` đặt bề rộng % mỗi cột từ
                  // `w:tblGrid` (Phase 11 R1, `tiLeCotVe` chia đều khi bảng
                  // không khai lưới) — `table-layout: fixed` để trình duyệt
                  // theo ĐÚNG tỉ lệ đó thay vì tự co theo nội dung. `data-ti-le`
                  // trên mỗi `<col>` là chỗ `docBangTuPhanTu` (xuat-tep.ts) đọc
                  // lại % đã vẽ khi xuất `.docx`/PDF — một nguồn, ba nơi dùng.
                  <table
                    key={i}
                    className="klaw-bang mt-1 w-full border-collapse text-[0.92em]"
                    style={{ tableLayout: "fixed" }}
                  >
                    <colgroup>
                      {tiLeCotVe(k.tiLe, k.hang[0]?.length ?? 0).map((ti, oi) => (
                        <col key={oi} data-ti-le={ti} style={{ width: `${ti}%` }} />
                      ))}
                    </colgroup>
                    <thead>
                      <tr>
                        {(k.hang[0] ?? []).map((o, oi) => (
                          <th
                            key={oi}
                            className="border border-[#999] bg-[var(--color-paper-100)] px-2 py-1 text-center align-middle font-serif font-semibold"
                          >
                            {o}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {k.hang.slice(1).map((hang, hi) => {
                        const soCotTieuDe = k.hang[0]?.length ?? hang.length;
                        const span = nhipHangVe(hang, k.nhip[hi + 1], soCotTieuDe);
                        return (
                          <tr key={hi}>
                            {hang.map((o, oi) => {
                              const cot = span[oi] ?? 1;
                              return (
                                <td
                                  key={oi}
                                  colSpan={cot > 1 ? cot : undefined}
                                  className="border border-[#999] px-2 py-1 align-top font-serif"
                                >
                                  {o}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ),
              )}
              {/* `data-khong-xuat`: dòng căn cứ là chú thích cho người ĐỌC
                  MÀN HÌNH, không phải một phần của văn bản. Thiếu dấu này thì
                  công tắc "Hiển thị căn cứ" đổi luôn nội dung tệp tải về. */}
              {hienCanCu && m.canCu && (
                <p
                  data-khong-xuat
                  className="m-0 mt-1 font-mono text-[0.75em] text-[var(--color-brass-600)]"
                >
                  Căn cứ: {m.canCu}
                </p>
              )}
            </section>
          ))}
        </div>
      </article>
    </div>
  );
}
