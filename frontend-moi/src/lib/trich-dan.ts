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

/**
 * Bốn nhóm theo mức liên quan tới HIỆN TẠI. Số nhỏ đọc trước.
 *
 * Backend trả `citations[]` KHÔNG lọc và KHÔNG sắp — cố ý, để nó làm vết kiểm
 * toán đầy đủ. Nhưng người hỏi "lương tối thiểu bao nhiêu" đọc dải trích dẫn
 * từ trên xuống như đọc câu trả lời, nên một lượt trả bốn mức lương đã chết
 * xếp TRƯỚC mức đang áp dụng sẽ đọc ra bốn câu trả lời mâu thuẫn cho một câu
 * hỏi. Hình dạng danh sách truyền đi sự lộn xộn đó trước cả khi ai kịp đọc
 * nhãn hiệu lực.
 *
 * Sắp lại, KHÔNG xoá: mấy nghị định lương tối thiểu bị CSDL quốc gia đánh sai
 * hiệu lực là phát hiện trung tâm của dự án. Giấu chúng đi là vứt mất đúng thứ
 * cần chứng minh; việc phải làm chỉ là thôi để chúng đứng đầu.
 *
 * Kiểm chạy được: `npm run kiem-xep-trich-dan`.
 */
export function nhomHieuLuc(hieuLuc: string | null): 1 | 2 | 3 | 4 {
  switch (hieuLuc) {
    case "con_hieu_luc":
      return 1;
    case "chua_hieu_luc":
      return 2;
    case "bi_thay_the":
    case "het_hieu_luc":
      return 4;
    default:
      // `bi_sua_doi`, `mot_phan_khong_xac_dinh`, `can_doi_chieu_tay`, `null`,
      // và MỌI nhãn backend thêm sau. Không rơi xuống nhóm 4: nhóm đó tuyên bố
      // "đã hết hiệu lực hoặc bị thay thế", và tuyên bố ấy về một nhãn mình
      // không hiểu là bịa. Nhóm 3 chỉ nói "còn dùng được nhưng có điều kiện".
      return 3;
  }
}

/**
 * Sắp trích dẫn theo nhóm, giữ nguyên thứ tự tương đối trong mỗi nhóm.
 *
 * `chiSoGoc` đi kèm vì `onChon`/`chiSoDangMo` đánh số theo MẢNG GỐC — nơi gọi
 * tra `ketQua.citations[chiSo]`. Sắp lại mà quên mang chỉ số gốc theo thì bấm
 * một chip sẽ mở nguyên văn của một điều KHÁC: đúng thứ sản phẩm này tồn tại
 * để không bao giờ xảy ra.
 *
 * `Array.prototype.sort` ổn định theo đặc tả từ ES2019, nên thứ tự liên quan
 * mà backend đã xếp bên trong từng nhóm được giữ nguyên.
 */
export function xepTrichDan<T extends { hieu_luc: string | null }>(
  citations: readonly T[],
): { trichDan: T; chiSoGoc: number }[] {
  return citations
    .map((trichDan, chiSoGoc) => ({ trichDan, chiSoGoc }))
    .sort((a, b) => nhomHieuLuc(a.trichDan.hieu_luc) - nhomHieuLuc(b.trichDan.hieu_luc));
}

/**
 * Câu cảnh báo của ĐÚNG văn bản này trong `warnings[]`, nếu có.
 *
 * `Citation` không mang ngày — đo trên backend thật, chín trường và không
 * trường nào là ngày hiệu lực. Ngày chỉ tồn tại trong câu cảnh báo:
 * "293/2025/NĐ-CP chưa có hiệu lực: ngày hiệu lực 2026-01-01 còn ở tương lai
 * so với 2019-06-01". Nên nhãn "Chưa có hiệu lực" muốn nói ra TỪ BAO GIỜ thì
 * phải lấy câu đó.
 *
 * Trả về nguyên câu, KHÔNG cạo ngày ra: định dạng câu này do backend viết và
 * có thể đổi, một bộ tách ngày sẽ hỏng trong im lặng còn câu nguyên thì không.
 *
 * Khớp bằng `so_ky_hieu` kèm dấu cách để "90/2019/NĐ-CP" không nuốt câu của
 * một số hiệu khác dài hơn có cùng phần đầu.
 */
export function ghiChuHieuLuc(soKyHieu: string, warnings: readonly string[]): string | undefined {
  return warnings.find((canhBao) => canhBao.startsWith(`${soKyHieu} `));
}
