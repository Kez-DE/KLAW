import { Fragment, useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { nhipHangVe, soCotThat, tiLeCotVe, type CanLe, type Muc } from "@/lib/xuat-tep";

/** `CanLe` của MỘT Ô bảng → lớp căn lề. Ô giữ căn lề nguồn của chính nó
 * (`w:jc`, đọc qua `BangThat.canLeO`) thay vì bị căn giữa cả bảng: khối ký và
 * letterhead của biểu mẫu tiếng Việt căn giữa TỪNG cột, còn một bảng dữ liệu
 * căn trái phần chữ — cùng một quy tắc đọc ra cả hai. */
const CAN_LE_O: Record<CanLe, string> = {
  trai: "text-left",
  giua: "text-center",
  phai: "text-right",
};

/**
 * Chiều cao KHAI BÁO của một hàng (twip, `w:trHeight`) → chiều cao TỐI THIỂU
 * để vẽ, cộng con số gốc để `docBangTuPhanTu` đọc lại khi xuất tệp.
 *
 * Đơn vị `pt`, không `em`: trang A4 ở đây rộng cố định 794px (≈210mm ở 96dpi)
 * và `thuPhong` chỉ phóng CỠ CHỮ, không phóng trang — nên một chiều cao đo
 * bằng `em` sẽ trôi theo mức phóng, còn `pt` giữ đúng kích thước vật lý mà
 * `.docx`/PDF cũng dùng. 1 twip = 1/20 pt.
 */
function caoTrenTrang(
  twip: number | undefined,
): { twip: number; style: { height: string } } | undefined {
  return twip && twip > 0 ? { twip, style: { height: `${twip / 20}pt` } } : undefined;
}

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
    | ((
        mucKey: string,
        khoiIndex: number,
        noiDungMoi: string,
        phienBanLucSua: number,
      ) => Promise<boolean>)
    | undefined;
}) {
  const oNoiDung = useRef<HTMLParagraphElement | null>(null);
  const dangSua = useRef(false);
  const vanBanLucFocus = useRef("");
  const phienBanLucFocus = useRef(phienBan);
  // Phase 15 R5 — lượt lưu gần nhất của ĐÚNG khối này hỏng (toast đã tắt,
  // nhưng khối không được trông y như đã lưu). Xoá ở lượt blur kế tiếp.
  const [luuHong, datLuuHong] = useState(false);
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
      aria-invalid={luuHong ? true : undefined}
      // Phase 15 R4 — chữ tiếng Việt của một VĂN BẢN PHÁP LÝ không được bị
      // trình duyệt hay bàn phím di động âm thầm "sửa": bộ kiểm chính tả mặc
      // định không có từ điển tiếng Việt (gạch đỏ khắp trang), còn autocorrect/
      // autocapitalize trên iOS đổi chữ người dùng vừa gõ mà không hỏi.
      // `lang="vi"` để trình đọc màn hình chọn đúng giọng đọc cho khối này.
      lang="vi"
      spellCheck={false}
      autoCorrect="off"
      autoCapitalize="off"
      // Review #2 — bấm VÀO khối để đặt con trỏ (thao tác bình thường trước
      // khi gõ) không được lan lên `<section>` rồi đổi mục đang chọn cho
      // phím tắt AI kế tiếp: đó là một hành động KHÁC "gõ chữ ở đây", và gộp
      // chung khiến "Rút gọn" âm thầm áp nhầm vào mục người dùng chỉ vừa bấm
      // vào để sửa một lỗi chính tả.
      onClick={coTheSua ? (e) => e.stopPropagation() : undefined}
      // Phase 15 R6 — Escape = HUỶ. Trả khối về đúng chữ LÚC BẮT ĐẦU sửa
      // (`vanBanLucFocus`, KHÔNG phải `noiDung`: bản mới nhất có thể đã bị một
      // lượt sửa bằng lời đổi trong lúc khối còn mở — N1 — và trả về đó sẽ
      // khiến `onBlur` thấy "khác" rồi lưu chữ của mô hình như một sửa tay với
      // phiên bản cũ), rồi rời khối: `onBlur` bên dưới thấy chữ bằng nhau nên
      // chỉ đồng bộ theo bản mới nhất, KHÔNG gọi lưu. Trước bản vá này, gõ
      // nhầm chỉ có một đường lui là gõ lại bằng tay.
      onKeyDown={
        coTheSua
          ? (e) => {
              if (e.key !== "Escape") return;
              e.currentTarget.textContent = vanBanLucFocus.current;
              e.currentTarget.blur();
            }
          : undefined
      }
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
          // Phase 15 R5 — một lượt blur mới (dù lưu hay chỉ đồng bộ) là lúc
          // dấu lỗi của lượt trước hết hiệu lực; lượt này hỏng thì đặt lại.
          datLuuHong(false);
          if (moi === vanBanLucFocus.current) {
            if (oNoiDung.current) oNoiDung.current.textContent = noiDung;
            return;
          }
          // Fix round 2 (N1b) — gửi phiên bản LÚC BẮT ĐẦU sửa, không phải
          // phiên bản mới nhất: nếu một lượt sửa bằng lời đã chạy xong (và do
          // đó đổi cả `muc_key` theo vị trí), phiên bản cũ không khớp nữa và
          // máy chủ từ chối RÕ RÀNG (`ban_thao.LOI_PHIEN_BAN_DA_DOI`) thay vì
          // âm thầm ghi vào đúng vị trí nhưng sai mục (I3).
          void onSuaKhoi(mucKey, khoiIndex, moi, phienBanLucFocus.current).then((daLuu) => {
            if (daLuu) return;
            // Phase 15 R5 — lưu hỏng: đánh dấu ĐÚNG khối này (`aria-invalid`
            // → viền đỏ, xem className) và đưa tiêu điểm về đây để người
            // dùng sửa tiếp ngay chỗ hỏng thay vì đi tìm. Chữ vừa gõ vẫn còn
            // trong khối; lượt blur kế tiếp sẽ thử lưu lại (`onFocus` chụp
            // lại `noiDung` của máy chủ nên phép so ở trên vẫn thấy "khác").
            datLuuHong(true);
            oNoiDung.current?.focus();
          });
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
        // Phase 15 R2 — khối gõ được phải TỰ báo "gõ ở đây" TRƯỚC khi bấm,
        // tách khỏi hover/ring của `<section>` bao ngoài (đó là "chọn mục làm
        // đích cho trợ lý", một hành động khác trên cùng vùng rê chuột): viền
        // ĐỨT nét quanh đoạn khi rê, đậm hơn khi có tiêu điểm — section dùng
        // nền + ring LIỀN nét, hai ngôn ngữ hình không lẫn nhau.
        // Màu rê là `--ring` (3,20:1), không phải brass-500 (1,93:1): cùng lý do
        // `focus-brass` ở styles.css — viền 1px tương phản thấp là thứ không ai thấy.
        coTheSua &&
          "cursor-text rounded-sm outline-1 outline-dashed outline-offset-2 outline-transparent hover:outline-[var(--ring)] focus-within:outline-2 focus-within:outline-[var(--color-brass-600)]",
        // Phase 15 R5 — lưu hỏng: viền đỏ LIỀN nét theo `aria-invalid` (đặt ở
        // `onBlur` bên trên) cho tới lượt lưu kế tiếp; một thuộc tính, một
        // chỗ đọc, trình đọc màn hình cũng nhận được cùng tín hiệu.
        coTheSua &&
          "aria-invalid:outline-2 aria-invalid:outline-solid aria-invalid:outline-destructive",
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
   *
   * Phase 15 R5 — trả `true` khi máy chủ đã ghi, `false` khi lượt lưu hỏng:
   * khối vừa blur cần biết kết quả để tự đánh dấu và kéo tiêu điểm về mình.
   * Không đổi HỢP ĐỒNG lưu (vẫn chỉ ở blur, không debounce).
   */
  onSuaKhoi?: (
    mucKey: string,
    khoiIndex: number,
    noiDungMoi: string,
    phienBanLucSua: number,
  ) => Promise<boolean>;
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

  // Một bản thảo TỔNG QUÁT dựng lại một tài liệu NGƯỜI DÙNG đưa vào: tên văn
  // bản là chữ của tài liệu đó, in ra ở đúng chỗ tài liệu in nó (thường trong
  // letterhead hoặc một dòng thân bài). `<h1>` ở đây là dòng KLAW tự thêm,
  // nên bỏ hẳn khỏi trang — chủ dự án chọn bỏ ở CẢ hai nơi (2026-09-18), màn
  // hình và tệp tải về, sau khi được hỏi riêng về tệp.
  //
  // Bỏ khỏi DOM chứ không ẩn bằng CSS: `docNoiDungTuDOM` (dùng chung cho
  // `.docx` và PDF) nhận diện tiêu đề qua đúng thẻ `H1`, nên một `<h1>` ẩn
  // vẫn đi vào tệp — màn hình và tệp khi đó nói hai điều khác nhau.
  //
  // Hệ quả nhận rõ: một bản thảo KLAW soạn từ đầu, mà thân bài KHÔNG tự nhắc
  // tên văn bản, giờ ra trang không có dòng tên nào và tệp tải về cũng vậy.
  // Tên văn bản vẫn còn ở thẻ hội thoại và ở thanh tiêu đề của khung soạn
  // thảo; không dựng một thẻ tiêu đề thay thế ở đây.
  //
  // Bản thảo THEO CHECKLIST không đi qua đây (`KhongGianSoanThao` có `<h1>`
  // riêng), nên nhánh `H1` của `docNoiDungTuDOM` vẫn còn đường chạy thật.
  const anTieuDe = laTongQuat;

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
                  // THẬT, không phải chữ `|` improv. NGUỒN quyết định nó trông
                  // như một bảng hay như một khối BỐ CỤC: `k.vien` (đọc
                  // `w:tblBorders`/`w:tcBorders`/`w:tblStyle`) bật/tắt CÙNG
                  // LÚC nét viền và hàng tiêu đề giả (tô nền + in đậm + căn
                  // giữa) — biểu mẫu tiếng Việt xếp cột bằng bảng KHÔNG viền
                  // (letterhead "tên đơn vị trái / quốc hiệu phải", khối ký
                  // cuối trang), và ở đó hàng đầu không phải tiêu đề của gì
                  // cả. Mỗi ô giữ căn lề NGUỒN của nó (`k.canLeO`, `w:jc`),
                  // mỗi hàng giữ chiều cao khai báo (`k.cao`, `w:trHeight` —
                  // chỗ để ký tay). Ba thứ đó đi ra DOM thành `data-vien`/
                  // `data-can-le`/`data-cao` để `docBangTuPhanTu` đọc lại khi
                  // xuất `.docx`/PDF: một nguồn, ba nơi dùng.
                  // Hàng ngắn hơn hàng tiêu đề (Phase 8 R4, ô gộp
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
                    // Phase 15 R9 — nối ghi chú với bảng bằng `aria-describedby`:
                    // người dùng trình đọc màn hình nhảy theo bảng (phím T)
                    // không đi qua dòng chữ đứng TRƯỚC nó. `m.key`+`i` là đủ
                    // duy nhất trong một trang; ghi chú chỉ render khi sửa
                    // được, nên id chỉ được trỏ tới trong đúng trường hợp đó.
                    const idChuThichBang = `bang-chua-sua-${m.key}-${i}`;
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
                            id={idChuThichBang}
                            className="m-0 mt-1 font-mono text-[0.7em] text-muted-foreground"
                          >
                            Bảng — chưa sửa trực tiếp được ở đây, hãy nói với trợ lý điều cần đổi.
                          </p>
                        )}
                        <table
                          aria-describedby={onSuaKhoi !== undefined ? idChuThichBang : undefined}
                          className="klaw-bang mt-1 w-full border-collapse text-[0.92em]"
                          data-vien={k.vien ? undefined : "khong"}
                          style={{ tableLayout: "fixed" }}
                        >
                          <colgroup>
                            {tiLeCotVe(k.tiLe, soCot).map((ti, oi) => (
                              <col key={oi} data-ti-le={ti} style={{ width: `${ti}%` }} />
                            ))}
                          </colgroup>
                          {k.vien && (
                            <thead>
                              <tr data-cao={caoTrenTrang(k.cao?.[0])?.twip}>
                                {(k.hang[0] ?? []).map((o, oi) => {
                                  const cot = spanTieuDe[oi] ?? 1;
                                  return (
                                    <th
                                      key={oi}
                                      colSpan={cot > 1 ? cot : undefined}
                                      data-can-le={k.canLeO?.[0]?.[oi] ?? "trai"}
                                      className="border border-[#999] bg-[var(--color-paper-100)] px-2 py-1 text-center align-middle font-serif font-semibold"
                                    >
                                      {o}
                                    </th>
                                  );
                                })}
                              </tr>
                            </thead>
                          )}
                          <tbody>
                            {(k.vien ? k.hang.slice(1) : k.hang).map((hang, hi) => {
                              const hiThat = k.vien ? hi + 1 : hi;
                              const span = nhipHangVe(hang, k.nhip[hiThat], soCot);
                              const cao = caoTrenTrang(k.cao?.[hiThat]);
                              return (
                                <tr key={hi} data-cao={cao?.twip} style={cao?.style}>
                                  {hang.map((o, oi) => {
                                    const cot = span[oi] ?? 1;
                                    const canLe = k.canLeO?.[hiThat]?.[oi] ?? "trai";
                                    return (
                                      <td
                                        key={oi}
                                        colSpan={cot > 1 ? cot : undefined}
                                        data-can-le={canLe}
                                        className={`px-2 py-1 align-top font-serif ${CAN_LE_O[canLe]} ${
                                          k.vien ? "border border-[#999]" : ""
                                        }`}
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
