import { cn } from "@/lib/utils";
import { phanHienThiMuc, type Muc } from "@/lib/xuat-tep";

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

  return (
    <div className="mx-auto w-full max-w-[794px]" style={{ fontSize: `${thuPhong}%` }}>
      <article className="aspect-[210/297] overflow-y-auto rounded-md border border-border bg-white px-[8%] py-[7%] text-[#111] shadow-soft">
        {/* `<h1>`, không `<h2>`: đây là tiêu đề CHÍNH của văn bản đang xem
            trước, và `docNoiDungTuDOM` (xuat-tep.ts) chỉ nhận diện tiêu đề
            xuất ra Word/PDF qua đúng thẻ `H1`. */}
        <h1 className="m-0 text-center font-serif text-[1.25em] font-bold uppercase tracking-wide">
          {tieuDe}
        </h1>
        {kyHieu && (
          <p className="mt-1 text-center font-mono text-[0.85em] text-[#555]">Số: {kyHieu}</p>
        )}
        <div className="mt-6 space-y-4">
          {muc.map((m) => {
            const { coNoiDung, coBang } = phanHienThiMuc(m);
            return (
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
                aria-label={
                  onChonMuc ? `Chọn mục ${m.stt}. ${m.ten} làm đích chỉnh sửa` : undefined
                }
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
                  không đổi gì trên màn hình của khung xem trước này. */}
                <p className="dieu-head m-0 font-serif text-[1em] font-semibold">
                  {laTongQuat ? m.ten : `Mục ${m.stt}. ${m.ten}`}
                </p>
                {/* Hai điều kiện ĐỘC LẬP, không phải một nhánh either/or: rule 15
                  của prompt XIN mô hình để `noi_dung` rỗng khi dùng `bang`,
                  nhưng schema/`lam_sach_van_ban` chỉ chặn ca CẢ HAI rỗng, không
                  chặn ca CẢ HAI có mặt. Một `noi_dung` (câu dẫn) cùng `bang`
                  (bảng) trên MỘT mục vẫn phải ra màn hình cả hai — một ternary
                  ở đây từng làm câu dẫn biến mất khỏi màn hình, `.docx` lẫn bản
                  sao chép văn bản thuần mà không một dấu vết nào (review round 1). */}
                {coNoiDung && (
                  <p className="m-0 mt-1 whitespace-pre-wrap font-serif text-[1em] leading-relaxed">
                    {m.noiDung}
                  </p>
                )}
                {coBang && m.bang && (
                  // Mục là BẢNG trong tài liệu nguồn (Phase 7 R1/R2) — `<table>`
                  // THẬT, không phải chữ `|` improv: hàng đầu là tiêu đề, viền
                  // thấy được, `table-auto` để cột không co lại thành một chữ.
                  <table className="klaw-bang mt-1 w-full table-auto border-collapse text-[0.92em]">
                    <thead>
                      <tr>
                        {(m.bang[0] ?? []).map((o, i) => (
                          <th
                            key={i}
                            className="border border-[#999] bg-[var(--color-paper-100)] px-2 py-1 text-center align-middle font-serif font-semibold"
                          >
                            {o}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {m.bang.slice(1).map((hang, hi) => (
                        <tr key={hi}>
                          {hang.map((o, oi) => (
                            <td
                              key={oi}
                              className="border border-[#999] px-2 py-1 align-top font-serif"
                            >
                              {o}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
            );
          })}
        </div>
      </article>
    </div>
  );
}
