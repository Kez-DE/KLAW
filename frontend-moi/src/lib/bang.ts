import type { Provision } from "./klaw";

/**
 * Bảng nằm trong nguyên văn điều luật — HAI hình dạng, một bộ đọc.
 *
 * Bảng trong CSDL quốc gia là markdown thô: mỗi hàng một dòng `| ô | ô | ô |`,
 * KHÔNG có dòng gạch ngăn `|---|` (đã soát toàn kho: 0 dòng như vậy). Render
 * bằng `whitespace-pre-wrap` thì bảng lương tối thiểu — điều khoản được hỏi
 * nhiều nhất của cả dự án — ra một dãy ký tự `|`.
 *
 * ## Dạng A — backend đã tách thành hàng con
 *
 * ```
 * khoan     258770  '1. …như sau:\n\n| Vùng | Mức lương tháng | Mức lương giờ |'
 * hang_bang 258771  parent_id=258770  '| Vùng I | 5.310.000 | 25.500 |'
 * hang_bang 258772  parent_id=258770  '| Vùng II | 4.730.000 | 22.700 |'
 * ```
 *
 * HÀNG TIÊU ĐỀ ở lại trong `noi_dung` của cha; chỉ hàng dữ liệu được tách.
 * Mỗi hàng tách ra là một `provision` thật, có `duong_dan` riêng
 * (`… > Khoản 1 > Vùng I`) — tức một neo trích dẫn riêng, bấm được.
 *
 * ## Dạng B — chưa tách
 *
 * Cả bảng vẫn là nhiều dòng `|…|` liền nhau trong `noi_dung` của MỘT dòng.
 * Ba trong sáu bảng của kho ở dạng này, và bị từ chối tách CÓ CHỦ ĐÍCH: số ô
 * không đều, cột 1 rỗng do ô gộp, hoặc chỉ một hàng dữ liệu. Chúng vẫn phải ra
 * bảng thật — chủ dự án yêu cầu **tất cả** bảng hiển thị được.
 *
 * ## Vì sao phải mang theo VỊ TRÍ ký tự (`O.tu`)
 *
 * Tô sáng câu trích (`catTheoTrichDan`) cắt `noi_dung` theo vị trí ký tự trong
 * bản NFC. Khi một hàng bảng thành các ô trong `<td>`, phần tô phải theo được
 * vào trong ô — click-to-verify là đóng góp trung tâm của đề tài. Nên mỗi ô
 * nhớ vị trí ký tự đầu của nó trong chính bản NFC ấy: bất biến là
 * `text.charAt(i) === noiDung.normalize("NFC").charAt(tu + i)`. Nơi gọi giao
 * vùng tô với `[tu, tu + text.length)` là ra đúng phần cần `<mark>`.
 *
 * Kiểm chạy được: `npm run kiem-bang`.
 */

/** Một ô của hàng bảng. */
export interface O {
  /** Nội dung ô, đã cắt khoảng trắng hai đầu. */
  text: string;
  /** Vị trí ký tự đầu của `text` trong bản NFC của `noi_dung`. */
  tu: number;
}

/** `noi_dung` chia thành các đoạn văn xuôi và các khối bảng, đúng thứ tự gốc. */
export type Doan = { loai: "van"; text: string; tu: number } | { loai: "bang"; hang: O[][] };

function laHangBang(dong: string): boolean {
  const gon = dong.trim();
  return gon.length > 1 && gon.startsWith("|") && gon.endsWith("|");
}

/**
 * Cắt một dòng `| a | b |` thành các ô, kèm vị trí.
 *
 * Ô lấy từ khoảng GIỮA hai dấu `|` liên tiếp, nên `| a | b |` ra đúng hai ô —
 * không có ô rỗng ảo ở hai đầu.
 */
function tachO(dong: string, tu: number): O[] {
  const o: O[] = [];
  let mo = dong.indexOf("|");
  for (;;) {
    const dong2 = dong.indexOf("|", mo + 1);
    if (dong2 < 0) break;
    const tho = dong.slice(mo + 1, dong2);
    const le = tho.length - tho.trimStart().length;
    o.push({ text: tho.trim(), tu: tu + mo + 1 + le });
    mo = dong2;
  }
  return o;
}

/**
 * Chia `noi_dung` thành đoạn văn xuôi và khối bảng.
 *
 * Các dòng `|…|` LIỀN NHAU gộp thành một bảng. Một dòng thường xen giữa cắt
 * bảng làm đôi — đúng, vì đó là hai bảng khác nhau trong nguyên văn.
 */
export function tachDoan(noiDung: string): Doan[] {
  const nfc = noiDung.normalize("NFC");
  const doan: Doan[] = [];
  let van: { text: string; tu: number } | null = null;
  let bang: O[][] | null = null;
  let tu = 0;

  const xaVan = () => {
    // Cắt khoảng trắng CUỐI thôi: cắt đầu sẽ làm lệch `tu` khỏi bản NFC, và
    // vùng tô sáng tính theo đúng bản đó.
    if (van !== null && van.text.trim() !== "") {
      doan.push({ loai: "van", text: van.text.trimEnd(), tu: van.tu });
    }
    van = null;
  };
  const xaBang = () => {
    if (bang !== null) doan.push({ loai: "bang", hang: bang });
    bang = null;
  };

  for (const dong of nfc.split("\n")) {
    if (laHangBang(dong)) {
      xaVan();
      (bang ??= []).push(tachO(dong, tu));
    } else {
      xaBang();
      if (van === null) van = { text: dong, tu };
      else van.text += `\n${dong}`;
    }
    tu += dong.length + 1;
  }
  xaVan();
  xaBang();
  return doan;
}

/** Số cột = hàng NHIỀU ô nhất. Hàng thiếu ô để trống, không ghép dồn. */
export function soCot(hang: readonly O[][]): number {
  return hang.reduce((nhieu, h) => Math.max(nhieu, h.length), 0);
}

/** Một dòng nguyên văn cùng những hàng bảng đã tách khỏi chính nó. */
export interface DongCoBang {
  dieuKhoan: Provision;
  /** `hang_bang` con, đúng thứ tự backend trả. Rỗng ở mọi dòng không có bảng tách. */
  hangCon: Provision[];
}

/**
 * Thu `hang_bang` về dòng cha của nó.
 *
 * Hàng nào không tìm thấy cha trong CÙNG payload thì đứng riêng như một dòng
 * thường — nguyên văn không được biến mất chỉ vì cha nằm ngoài cửa sổ tải.
 */
export function gomHangBang(provisions: readonly Provision[]): DongCoBang[] {
  const ra: DongCoBang[] = [];
  const theoId = new Map<number, DongCoBang>();
  for (const dieuKhoan of provisions) {
    if (dieuKhoan.cap === "hang_bang" && dieuKhoan.parent_id !== null) {
      const cha = theoId.get(dieuKhoan.parent_id);
      if (cha !== undefined) {
        cha.hangCon.push(dieuKhoan);
        continue;
      }
    }
    const dong: DongCoBang = { dieuKhoan, hangCon: [] };
    theoId.set(dieuKhoan.id, dong);
    ra.push(dong);
  }
  return ra;
}
