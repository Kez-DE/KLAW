/**
 * Định vị câu trích (`Citation.quote`) bên trong nguyên văn điều luật
 * (`Provision.noi_dung`).
 *
 * Không so chuỗi thô. Quote lấy từ chính CSDL nên nội dung trùng khớp, nhưng
 * khoảng trắng có thể lệch (xuống dòng, tab, khoảng trắng kép trong bản gốc) và
 * dấu tiếng Việt có thể ở dạng tổ hợp (NFD) ở một bên. So khớp trên bản đã
 * chuẩn hoá — NFC, gộp mọi chuỗi khoảng trắng thành một dấu cách — rồi ánh xạ
 * vị trí tìm được NGƯỢC về chuỗi gốc, để phần tô sáng cắt đúng nguyên văn chứ
 * không cắt bản đã bị sửa.
 *
 * Chuỗi trả về là bản NFC của `noiDung`. NFC là dạng chuẩn tắc — cùng ký tự,
 * cùng cách hiển thị — nên đây KHÔNG phải "sửa văn bản gốc".
 *
 * Kiểm chạy được: `npm run kiem-trich-dan`.
 */

interface BanChuanHoa {
  chuoi: string;
  /** `banDo[i]` = vị trí trong bản NFC của ký tự thứ i trong `chuoi`. */
  banDo: number[];
}

const KHOANG_TRANG = /\s/;

function chuanHoa(goc: string): BanChuanHoa {
  const nfc = goc.normalize("NFC");
  let chuoi = "";
  const banDo: number[] = [];
  let dangTrongChuoiTrang = false;

  for (let i = 0; i < nfc.length; i += 1) {
    const kyTu = nfc.charAt(i);
    if (KHOANG_TRANG.test(kyTu)) {
      // Một chuỗi khoảng trắng liên tiếp thu về đúng một dấu cách, neo vào ký
      // tự đầu tiên của chuỗi đó. Khoảng trắng mở đầu bị bỏ hẳn.
      if (!dangTrongChuoiTrang && chuoi.length > 0) {
        chuoi += " ";
        banDo.push(i);
      }
      dangTrongChuoiTrang = true;
      continue;
    }
    chuoi += kyTu;
    banDo.push(i);
    dangTrongChuoiTrang = false;
  }

  // Khoảng trắng cuối chuỗi không mang thông tin; bỏ để `indexOf` không trượt.
  if (chuoi.endsWith(" ")) {
    chuoi = chuoi.slice(0, -1);
    banDo.pop();
  }
  return { chuoi, banDo };
}

export interface LatCatTrichDan {
  /** Phần nguyên văn trước câu trích. */
  truoc: string;
  /** Chính câu trích, cắt từ nguyên văn. Rỗng khi không định vị được. */
  trung: string;
  /** Phần nguyên văn sau câu trích. */
  sau: string;
  /** false khi câu trích không nằm trong nguyên văn này. */
  timThay: boolean;
}

/**
 * Cắt `noiDung` thành ba phần quanh `quote`.
 *
 * Khi không định vị được, trả toàn bộ nguyên văn ở `truoc` kèm `timThay: false`
 * — nơi gọi PHẢI nói thật là chưa tô sáng được, không được im lặng bỏ qua.
 */
export function catTheoTrichDan(noiDung: string, quote: string): LatCatTrichDan {
  const nguyenVan = noiDung.normalize("NFC");
  const nen = chuanHoa(noiDung);
  const kim = chuanHoa(quote).chuoi;

  const khongThay: LatCatTrichDan = { truoc: nguyenVan, trung: "", sau: "", timThay: false };
  if (kim.length === 0) return khongThay;

  const viTri = nen.chuoi.indexOf(kim);
  if (viTri < 0) return khongThay;

  const batDau = nen.banDo[viTri];
  const cuoi = nen.banDo[viTri + kim.length - 1];
  // Bản đồ luôn dài bằng chuỗi đã chuẩn hoá, nên hai giá trị này không thể
  // thiếu. Kiểm vẫn ở đây vì `noUncheckedIndexedAccess` đúng khi bắt buộc: một
  // chỉ số hụt phải làm phần tô sáng tắt đi, không được cắt nhầm nguyên văn.
  if (batDau === undefined || cuoi === undefined) return khongThay;

  return {
    truoc: nguyenVan.slice(0, batDau),
    trung: nguyenVan.slice(batDau, cuoi + 1),
    sau: nguyenVan.slice(cuoi + 1),
    timThay: true,
  };
}
