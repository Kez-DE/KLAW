import { Fragment, useLayoutEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import {
  nhipHangVe,
  soCotThat,
  tiLeCotVe,
  tieuDeDaXuatHienTrongThan,
  type CanLe,
  type Muc,
} from "@/lib/xuat-tep";

/**
 * Fix round 1 (review, CRITICAL #1) — một khối văn xuôi editable, tách riêng
 * để đồng bộ DOM ↦ `noiDung` bằng TAY (`useLayoutEffect`), không qua
 * `children` JSX: trước bản vá này, `{k.noiDung}` là con của `<p>`, nên MỘT
 * lượt render với `noiDung` đã đổi (một lượt chat "Rút gọn"/"Trang trọng
 * hơn" trên CÙNG thanh công cụ vừa ghi đè `banThao`, đúng thứ Half B làm
 * thành chuyện thường) khiến React diff `children` mới vào NGAY LẬP TỨC —
 * xoá sạch chữ người dùng đang gõ dở trong chính khối đó, giữa chừng, không
 * cảnh báo. Component này KHÔNG BAO GIỜ đưa `noiDung` vào JSX `children` —
 * chỉ `useLayoutEffect` (chạy TRƯỚC khi trình duyệt vẽ khung tiếp theo, nên
 * không có một khung nào hiện `<p>` rỗng) mới ghi `textContent`, và bỏ qua
 * lần ghi đó khi khối ĐANG có tiêu điểm (`dangSua`, cập nhật bằng
 * `onFocus`/`onBlur`).
 *
 * Fix round 2 (re-review N1) — TIÊU ĐIỂM không phải DẤU HIỆU ĐÃ SỬA. Bản vá
 * trên chỉ hỏi "khối có đang mở không", nên khi một lượt sửa bằng lời chạy
 * xong TRONG lúc khối này còn mở (bàn tay chưa gõ chữ nào), `onBlur` so
 * chữ-trên-màn-hình (vẫn là chữ CŨ, effect vừa bị bỏ qua) với `noiDung` MỚI
 * vừa đổi — khác nhau dù người dùng không gõ gì — và âm thầm GHI ĐÈ bản mới
 * của mô hình bằng đúng chữ nó vừa thay. Sửa: chụp lại chữ (`vanBanLucFocus`)
 * VÀ phiên bản (`phienBanLucFocus`) tại đúng lúc `onFocus`, không đọc lại lúc
 * `onBlur`. `onBlur` so chữ mới gõ với chữ LÚC BẮT ĐẦU sửa — không đổi thật
 * sự thì đồng bộ lại khối theo `noiDung` mới nhất, không gọi lưu; đổi thật sự
 * thì gửi kèm phiên bản LÚC BẮT ĐẦU (không phải phiên bản mới nhất) để máy
 * chủ tự phát hiện một lượt sửa bằng lời đã chạy xen giữa (I3) — xem
 * `SanKhauBanThao.onSuaKhoi` cho nửa còn lại (N2, tránh từ chối một lượt sửa
 * tay bình thường thứ hai).
 */
function KhoiVanXuoi({
  noiDung,
  canhLe,
  mucKey,
  khoiIndex,
  phienBan,
  onSuaKhoi,
}: {
  noiDung: string;
  canhLe: CanLe;
  mucKey: string;
  khoiIndex: number;
  phienBan: number;
  onSuaKhoi:
    | ((mucKey: string, khoiIndex: number, noiDungMoi: string, phienBanLucSua: number) => void)
    | undefined;
}) {
  const oNoiDung = useRef<HTMLParagraphElement | null>(null);
  const dangSua = useRef(false);
  const vanBanLucFocus = useRef("");
  const phienBanLucFocus = useRef(phienBan);
  const coTheSua = onSuaKhoi !== undefined;

  useLayoutEffect(() => {
    if (dangSua.current) return;
    if (oNoiDung.current && oNoiDung.current.textContent !== noiDung) {
      oNoiDung.current.textContent = noiDung;
    }
  }, [noiDung]);

  return (
    <p
      ref={oNoiDung}
      contentEditable={coTheSua}
      suppressContentEditableWarning={coTheSua}
      // Review #3 — vùng biên tập cần TÊN RIÊNG cho trình đọc màn hình,
      // khác với "Chọn mục N làm đích chỉnh sửa" của `<section>` bao ngoài
      // (một hành động KHÁC: chọn đích cho phím tắt AI, không phải gõ chữ
      // ở đây) — thiếu nó, hai điểm dừng tab đọc ra CÙNG một tên.
      role={coTheSua ? "textbox" : undefined}
      aria-multiline={coTheSua ? true : undefined}
      aria-label={coTheSua ? "Nội dung mục, sửa được" : undefined}
      // Review #2 — bấm VÀO khối để đặt con trỏ (thao tác bình thường trước
      // khi gõ) không được lan lên `<section>` rồi đổi mục đang chọn cho
      // phím tắt AI kế tiếp: đó là một hành động KHÁC "gõ chữ ở đây", và gộp
      // chung khiến "Rút gọn" âm thầm áp nhầm vào mục người dùng chỉ vừa bấm
      // vào để sửa một lỗi chính tả.
      onClick={coTheSua ? (e) => e.stopPropagation() : undefined}
      onFocus={
        coTheSua
          ? () => {
              dangSua.current = true;
              // Fix round 2 (N1) — chụp NGAY lúc bắt đầu sửa, không đọc lại
              // lúc blur: đây là chữ/phiên bản người dùng THẤY khi họ bắt tay
              // vào gõ, và là cái duy nhất máy chủ cần để biết có lượt sửa
              // bằng lời nào chen giữa hay không.
              vanBanLucFocus.current = noiDung;
              phienBanLucFocus.current = phienBan;
            }
          : undefined
      }
      // Review #4 — dán mặc định chèn HTML nguyên văn từ clipboard (định
      // dạng, thẻ, đôi khi ảnh) làm con thật của `<p>`. Ép về chữ thuần: khối
      // này chỉ từng mang một đoạn văn xuôi không định dạng, và
      // `docNoiDungTuDOM`/`docDong` (xuat-tep.ts) đọc `textContent` nên xuất
      // ra vẫn an toàn — nhưng DOM sống trong ứng dụng thì không nên mang
      // thẻ lạ mà không phần nào của app dự tính trước.
      onPaste={
        coTheSua
          ? (e) => {
              e.preventDefault();
              const chu = e.clipboardData.getData("text/plain");
              // ponytail: `execCommand` đã "deprecated" nhưng vẫn là cách
              // duy nhất chèn văn bản mà không xoá sạch lịch sử hoàn tác của
              // trình duyệt trong một contentEditable thuần — nâng lên thao
              // tác Range/Selection thủ công nếu trình duyệt bỏ hỗ trợ này.
              document.execCommand("insertText", false, chu);
            }
          : undefined
      }
      onBlur={
        onSuaKhoi &&
        ((e) => {
          dangSua.current = false;
          // `innerText`, không `textContent`: trình duyệt tự đổi ranh giới
          // khối/`<br>` thành `\n`, đúng hình dạng nhiều dòng một khối
          // letterhead có thể mang (Phase 8/11). Không đổi gì thì KHÔNG gọi
          // — một cú blur không gõ chữ nào không được tiêu một suất
          // `TRAN_SUA` (xem `ban_thao.sua_tay`).
          //
          // Fix round 2 (N1a) — so với chữ LÚC BẮT ĐẦU sửa
          // (`vanBanLucFocus`), không so với `noiDung` (có thể đã bị một lượt
          // sửa bằng lời đổi TRONG lúc khối này còn mở): không gõ gì thật sự
          // thì không gọi lưu, mà đồng bộ lại khối theo bản MỚI NHẤT — hiệu
          // ứng bị bỏ qua lúc còn tiêu điểm, giờ mới chạy tay, thay vì để chữ
          // CŨ ghi đè âm thầm lên bản mới của mô hình.
          const moi = e.currentTarget.innerText;
          if (moi === vanBanLucFocus.current) {
            if (oNoiDung.current) oNoiDung.current.textContent = noiDung;
            return;
          }
          // Fix round 2 (N1b) — gửi phiên bản LÚC BẮT ĐẦU sửa, không phải
          // phiên bản mới nhất: nếu một lượt sửa bằng lời đã chạy xong (và do
          // đó đổi cả `muc_key` theo vị trí), phiên bản cũ không khớp nữa và
          // máy chủ từ chối RÕ RÀNG (`ban_thao.LOI_PHIEN_BAN_DA_DOI`) thay vì
          // âm thầm ghi vào đúng vị trí nhưng sai mục (I3).
          onSuaKhoi(mucKey, khoiIndex, moi, phienBanLucFocus.current);
        })
      }
      className={cn(
        // `break-words` (Phase 11 fix round 1, `overflow-wrap: break-word`)
        // — một dòng trường tự do gõ bằng dấu CHẤM/GẠCH LIỀN NHAU không có
        // khoảng trắng nào ("Nội dung công việc được giao: ………..............")
        // không có chỗ để trình duyệt ngắt dòng theo mặc định (chỉ ngắt ở
        // khoảng trắng), nên cả trang A4 bị đẩy rộng ra theo chiều ngang
        // thay vì xuống dòng. Không xoá dấu chấm/gạch — đó là Ý NGHĨA của
        // biểu mẫu (chỗ để điền) — chỉ cho phép ngắt NGAY TRONG một chuỗi
        // liền không ngắt được cách nào khác.
        "m-0 mt-1 whitespace-pre-wrap break-words font-serif text-[1em] leading-relaxed",
        // Căn lề THẬT của tài liệu nguồn (Phase 9 U5) — đọc ngược lại qua
        // `getComputedStyle(...).textAlign` ở `xuat-tep.ts::docDong`, nên
        // `.docx`/PDF tự khớp theo.
        canhLe === "giua" && "text-center",
        canhLe === "phai" && "text-right",
        coTheSua &&
          "cursor-text rounded-sm outline-none focus:ring-2 focus:ring-[var(--color-brass-600)]",
      )}
    />
  );
}

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
  /**
   * Phase 3 (Half A, R1) — gõ tay một khối VĂN XUÔI, 0 lượt gọi mô hình.
   * Vắng mặt (`undefined`) ⇒ trang chỉ ĐỌC, y hệt trước bản vá này (không
   * đường nào gọi hàm này thì không có gì để lỡ tay đổi).
   *
   * CHỈ khối văn xuôi — khối BẢNG không nhận `contentEditable` (quyết định D
   * ở báo cáo phase 3): `nhip`/`tiLe` của một bảng chỉ sống trong cấu trúc
   * hàng×ô đọc từ nguồn, không có chỗ nào giữ lại hai trường đó nếu ô được
   * gõ đè bằng tay tại đây — sửa bảng cần một biên tập theo Ô, để giai đoạn
   * sau, không phải ghi đè cả `bang` bằng một chuỗi.
   *
   * Fix round 2 (N1) — nay nhận thêm `phienBanLucSua`: phiên bản bản thảo
   * `KhoiVanXuoi` chụp lại lúc `onFocus`, không phải phiên bản mới nhất lúc
   * `onBlur` — xem chú thích tại khai báo `KhoiVanXuoi`.
   */
  onSuaKhoi?: (
    mucKey: string,
    khoiIndex: number,
    noiDungMoi: string,
    phienBanLucSua: number,
  ) => void;
  /** Phiên bản bản thảo hiện tại — bắt buộc cùng `onSuaKhoi` (fix round 2, N1). */
  phienBan?: number;
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
  onSuaKhoi,
  phienBan,
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
                      // Phase 3 (Half A, R1) — đang gõ TRONG một khối
                      // `contentEditable`: Enter xuống dòng, dấu cách gõ chữ
                      // — cả hai KHÔNG được biến thành "chọn mục" rồi nuốt
                      // mất phím người dùng vừa gõ (`preventDefault` dưới
                      // đây, viết trước bản vá này, không phân biệt được
                      // nguồn phím tới từ đâu).
                      if ((e.target as HTMLElement).isContentEditable) return;
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
                  // Phase 3 (Half A, R1) — gõ tay tại chỗ: `contentEditable`
                  // CHỈ khi nơi gọi cho `onSuaKhoi` (bản thảo đã lưu, có `id`
                  // để ghi) — khung xem trước dùng nơi khác (đối chiếu, xem
                  // trước lúc đang dựng) không truyền prop này và giữ nguyên
                  // hành vi CHỈ ĐỌC trước bản vá này. `KhoiVanXuoi` (fix
                  // round 1, review CRITICAL #1) đồng bộ DOM bằng tay, không
                  // qua `children` — xem chú thích ở khai báo component đó.
                  <KhoiVanXuoi
                    key={i}
                    noiDung={k.noiDung}
                    canhLe={k.canhLe}
                    mucKey={m.key}
                    khoiIndex={i}
                    // Fix round 2 (N1) — không dùng khi chỉ đọc; giá trị mặc
                    // định vô hại vì `onSuaKhoi` cũng vắng mặt trong trường
                    // hợp đó nên không đường nào đọc tới `phienBan`.
                    phienBan={phienBan ?? 0}
                    onSuaKhoi={onSuaKhoi}
                  />
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
                  // Số cột LƯỚI THẬT (Phase 11 fix round 3, reviewer I5) —
                  // từ `tiLe` khi bảng có khai lưới nguồn, không phải số Ô
                  // của hàng đầu: một hàng đầu có ô gộp (dòng tiêu đề toàn
                  // bảng) có ÍT ô hơn số cột thật, và lấy nhầm số đó làm
                  // chuẩn khiến `tiLeCotVe` coi tỉ lệ thật là "sai hình dạng"
                  // rồi chia đều oan — đúng bảng R1 tồn tại để giữ tỉ lệ.
                  // `<thead>` giờ cũng áp `colSpan` cho hàng tiêu đề, cùng
                  // luật ô gộp `<tbody>` đã dùng — trước bản vá này, hàng tiêu
                  // đề không có `colSpan` nào nên lệch cột với thân bảng khi
                  // chính nó có ô gộp.
                  (() => {
                    const soCot = soCotThat(k.hang, k.tiLe);
                    const spanTieuDe = nhipHangVe(k.hang[0] ?? [], k.nhip[0], soCot);
                    return (
                      <Fragment key={i}>
                        {/* Quyết định D (R1, phase 3) — bảng CHƯA sửa trực
                            tiếp được ở giai đoạn này (xem ghi chú `onSuaKhoi`
                            ở khai báo `Props`): nói RA thay vì để người dùng
                            tự đoán vì sao gõ vào ô không có tác dụng gì.
                            `data-khong-xuat`: chú thích màn hình, không phải
                            chữ của văn bản — cùng quy ước dòng "Căn cứ" bên
                            dưới. */}
                        {onSuaKhoi !== undefined && (
                          <p
                            data-khong-xuat
                            className="m-0 mt-1 font-mono text-[0.7em] text-muted-foreground"
                          >
                            Bảng — chưa sửa trực tiếp được ở đây, hãy nói với trợ lý điều cần đổi.
                          </p>
                        )}
                        <table
                          className="klaw-bang mt-1 w-full border-collapse text-[0.92em]"
                          style={{ tableLayout: "fixed" }}
                        >
                          <colgroup>
                            {tiLeCotVe(k.tiLe, soCot).map((ti, oi) => (
                              <col key={oi} data-ti-le={ti} style={{ width: `${ti}%` }} />
                            ))}
                          </colgroup>
                          <thead>
                            <tr>
                              {(k.hang[0] ?? []).map((o, oi) => {
                                const cot = spanTieuDe[oi] ?? 1;
                                return (
                                  <th
                                    key={oi}
                                    colSpan={cot > 1 ? cot : undefined}
                                    className="border border-[#999] bg-[var(--color-paper-100)] px-2 py-1 text-center align-middle font-serif font-semibold"
                                  >
                                    {o}
                                  </th>
                                );
                              })}
                            </tr>
                          </thead>
                          <tbody>
                            {k.hang.slice(1).map((hang, hi) => {
                              const span = nhipHangVe(hang, k.nhip[hi + 1], soCot);
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
                      </Fragment>
                    );
                  })()
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
