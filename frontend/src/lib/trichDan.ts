/**
 * Định vị câu trích (`Citation.quote`) bên trong nguyên văn điều luật
 * (`Provision.noi_dung`).
 *
 * Không so chuỗi thô: quote lấy từ DB nên nội dung trùng khớp, nhưng khoảng
 * trắng có thể lệch (xuống dòng, tab, khoảng trắng kép trong bản gốc), và dấu
 * tiếng Việt có thể ở dạng tổ hợp (NFD) ở một bên. So khớp trên bản đã chuẩn
 * hoá — NFC + gộp mọi chuỗi khoảng trắng thành một dấu cách — rồi ánh xạ vị trí
 * tìm được ngược về chuỗi gốc, để phần tô sáng cắt đúng nguyên văn chứ không
 * cắt bản đã bị sửa.
 *
 * Chuỗi trả về là bản NFC của `noi_dung`. NFC là dạng chuẩn tắc: cùng ký tự,
 * cùng cách hiển thị — không phải "sửa văn bản gốc" theo nghĩa DESIGN.md cấm.
 */

interface BanChuanHoa {
  chuoi: string;
  /** `banDo[i]` = vị trí trong bản NFC của ký tự thứ i trong `chuoi`. */
  banDo: number[];
}

const KHOANG_TRANG = /\s/;

function chuanHoa(goc: string): BanChuanHoa {
  const nfc = goc.normalize('NFC');
  let chuoi = '';
  const banDo: number[] = [];
  let dangTrongChuoiTrang = false;

  for (let i = 0; i < nfc.length; i += 1) {
    const kyTu = nfc[i];
    if (KHOANG_TRANG.test(kyTu)) {
      // Một chuỗi khoảng trắng liên tiếp thu về đúng một dấu cách, neo vào ký
      // tự đầu tiên của chuỗi đó. Khoảng trắng mở đầu bị bỏ hẳn.
      if (!dangTrongChuoiTrang && chuoi.length > 0) {
        chuoi += ' ';
        banDo.push(i);
      }
      dangTrongChuoiTrang = true;
      continue;
    }
    chuoi += kyTu;
    banDo.push(i);
    dangTrongChuoiTrang = false;
  }

  // Khoảng trắng cuối chuỗi không mang thông tin, bỏ để `indexOf` không trượt.
  if (chuoi.endsWith(' ')) {
    chuoi = chuoi.slice(0, -1);
    banDo.pop();
  }
  return { chuoi, banDo };
}

export interface LatCatTrichDan {
  /** Phần nguyên văn trước câu trích. */
  truoc: string;
  /** Chính câu trích, cắt từ nguyên văn (rỗng nếu không định vị được). */
  trung: string;
  /** Phần nguyên văn sau câu trích. */
  sau: string;
  /** false khi câu trích không nằm trong nguyên văn này. */
  timThay: boolean;
}

/**
 * Cắt `noiDung` thành ba phần quanh `quote`. Khi không định vị được, trả về
 * toàn bộ nguyên văn ở `truoc` và `timThay: false` — người gọi phải nói thật
 * là chưa tô sáng được, KHÔNG được im lặng bỏ qua.
 */
export function catTheoTrichDan(noiDung: string, quote: string): LatCatTrichDan {
  const nen = chuanHoa(noiDung);
  const kim = chuanHoa(quote).chuoi;
  const nguyenVan = noiDung.normalize('NFC');

  if (kim.length === 0) {
    return { truoc: nguyenVan, trung: '', sau: '', timThay: false };
  }
  const viTri = nen.chuoi.indexOf(kim);
  if (viTri < 0) {
    return { truoc: nguyenVan, trung: '', sau: '', timThay: false };
  }

  const batDau = nen.banDo[viTri];
  const ketThuc = nen.banDo[viTri + kim.length - 1] + 1;
  return {
    truoc: nguyenVan.slice(0, batDau),
    trung: nguyenVan.slice(batDau, ketThuc),
    sau: nguyenVan.slice(ketThuc),
    timThay: true,
  };
}

/**
 * Các câu trong `warnings[]` mở đầu bằng `so_ky_hieu` của văn bản chúng nói tới
 * ("45/2019/QH14 hết hiệu lực một phần: bị 19/2023/QH15 sửa đổi…"), nên gắn
 * được cảnh báo vào đúng khung phim. Cảnh báo không khớp văn bản nào vẫn phải
 * hiện ở khối cảnh báo chung — hàm này KHÔNG dùng để lọc bớt cảnh báo.
 */
export function canhBaoChoVanBan(warnings: string[], soKyHieu: string): string[] {
  return warnings.filter((canhBao) => canhBao.startsWith(soKyHieu));
}
