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

import { laVanBanDan, type Citation, type TraCuuKetQua, type VanBanDan } from "./klaw.ts";
import { ngayVietNam } from "./utils.ts";
import { catManh, type Manh } from "./van-xuoi.ts";

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
 * Câu trích đã định vị, dưới dạng KHOẢNG VỊ TRÍ `[đầu, cuối)` trong bản NFC của
 * `noiDung` — thay cho ba lát cắt chuỗi.
 *
 * Ba lát cắt chỉ dùng được khi cả `noi_dung` render thành MỘT khối chữ. Từ khi
 * nguyên văn có bảng, cùng một `noi_dung` vỡ ra thành đoạn văn xuôi và nhiều ô
 * `<td>` rời nhau; mỗi mảnh cần biết phần nào của RIÊNG nó nằm trong câu trích.
 * Một khoảng vị trí trả lời được câu hỏi đó cho mọi mảnh, ba lát cắt thì không.
 *
 * `truoc`/`trung` là lát cắt của chính bản NFC ấy, nên độ dài của chúng CHÍNH
 * LÀ vị trí — không có phép quy đổi nào ở đây để mà lệch.
 *
 * Trả `null` khi không có câu trích, hoặc có mà không định vị được. Nơi gọi vẫn
 * PHẢI nói thật là chưa tô sáng được (xem `catTheoTrichDan`); `null` ở đây chỉ
 * mang nghĩa "không có gì để tô".
 */
export type VungTrichDan = readonly [number, number] | null;

export function vungTrichDan(noiDung: string, quote: string | null): VungTrichDan {
  if (quote === null || quote.trim() === "") return null;
  const lat = catTheoTrichDan(noiDung, quote);
  if (!lat.timThay) return null;
  return [lat.truoc.length, lat.truoc.length + lat.trung.length];
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
 * Chỉ số trích dẫn mở khi bấm thẻ `doc:ID`: trích dẫn có `k` nhỏ nhất của văn
 * bản đó (điều khoản đầu tiên mô hình dẫn), rơi về trích dẫn đầu tiên cùng
 * `doc_id` khi không có `k` (payload cache cũ), `-1` khi văn bản không có mặt.
 * Thuần — `documents[]` luôn dựng từ chính `citations`, nên một `doc` hợp lệ
 * luôn có ít nhất một trích dẫn.
 */
export function chiSoDauCuaVanBan(citations: readonly Citation[], docId: string): number {
  let tot = -1;
  let kTot = Number.POSITIVE_INFINITY;
  citations.forEach((c, i) => {
    if (c.doc_id !== docId) return;
    const k = typeof c.k === "number" ? c.k : Number.POSITIVE_INFINITY;
    if (tot === -1 || k < kTot) {
      tot = i;
      kTot = k;
    }
  });
  return tot;
}

/**
 * Căn cứ được hiện trong card: bỏ nhóm 4 (hết hiệu lực / bị thay thế) — spec
 * 2026-09-06 §7: câu trả lời chỉ dẫn luật còn hiệu lực. Giữ `chiSoGoc` để nút
 * mở đúng khung theo chỉ số trong `citations` thật.
 */
export function canCuConHieuLuc(
  citations: readonly Citation[],
): { trichDan: Citation; chiSoGoc: number }[] {
  return xepTrichDan(citations).filter((m) => nhomHieuLuc(m.trichDan.hieu_luc) !== 4);
}

/** Chỉ số citation mà một thẻ trỏ tới; −1 khi không trỏ được. Dùng chung cho
 * nút thẻ trong văn xuôi và cho `coTagBamDuoc`, để hai chỗ không lệch nhau. */
export function chiSoCuaThe(
  manh: Extract<Manh, { kieu: "the" }>,
  citations: readonly Citation[],
): number {
  return manh.loai === "cite"
    ? citations.findIndex((c) => c.k === Number(manh.khoa))
    : chiSoDauCuaVanBan(citations, manh.khoa);
}

/** Văn xuôi có ít nhất một thẻ bấm được? `catManh` chạy trên toàn `answer`:
 * nó chỉ tách thẻ, không cần tách đoạn trước. */
export function coTagBamDuoc(answer: string | null, citations: readonly Citation[]): boolean {
  if (answer === null) return false;
  return catManh(answer).some((m) => m.kieu === "the" && chiSoCuaThe(m, citations) >= 0);
}

/* ── Trích dẫn đầy đủ (quyết định 2026-09-28) ─────────────────────────────────
 * Một trích dẫn nói được văn bản nào, ai ban hành, ngày nào và mở ở đâu. Mọi
 * trường tới từ máy chủ đều đi qua `vanBanHopLe` / `cachTrichHopLe`: giá trị dị
 * dạng thành `null`, và `null` nghĩa là giao diện BỎ phần đó — không bao giờ
 * một chỗ giữ chỗ, không bao giờ một link đoán.
 */

/** Hai cổng chính thống, theo thứ tự ưu tiên của quyết định (mục 2). `Map`,
 *  không object: `hostname` "constructor" không được tra ra một hàm. */
const CONG_CHINH_THONG = new Map([
  ["vbpl.vn", "CSDL quốc gia về pháp luật"],
  ["vanban.chinhphu.vn", "Cổng TTĐT Chính phủ"],
]);

export interface LienKet {
  url: string;
  /** Tên cổng cho người đọc, theo host. */
  nhan: string;
}

/**
 * Link chính thống, hoặc `null`. Chỉ https, đúng host của hai cổng, không
 * tài khoản, không cổng mạng lạ — link này mở ra `target="_blank"` dưới tên
 * một cơ quan nhà nước, nên phòng thủ ở đây dù máy chủ đã kiểm trước.
 */
export function lienKetChinhThuc(url: unknown): LienKet | null {
  if (typeof url !== "string") return null;
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return null;
  }
  const nhan = CONG_CHINH_THONG.get(u.hostname);
  const sach = u.protocol === "https:" && u.username === "" && u.password === "" && u.port === "";
  return nhan === undefined || !sach ? null : { url, nhan };
}

/** Siêu dữ liệu CẤP VĂN BẢN đã qua cửa kiểm — gộp được giữa nhiều nguồn. */
export interface VanBanDaKiem {
  ten_van_ban: string | null;
  so_ky_hieu: string | null;
  co_quan_ban_hanh: string | null;
  /** ISO — in ra bằng `ngayVietNam`. */
  ngay_ban_hanh: string | null;
  ngay_hieu_luc: string | null;
  lien_ket: LienKet | null;
}

const chuHopLe = (v: unknown): string | null =>
  typeof v === "string" && v.trim() !== "" ? v.trim() : null;
const ngayHopLe = (v: unknown): string | null =>
  typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null;
const banGhi = (x: unknown): Record<string, unknown> =>
  typeof x === "object" && x !== null ? (x as Record<string, unknown>) : {};

/**
 * Gộp siêu dữ liệu văn bản từ nhiều nguồn: trường nào nguồn trước không biết
 * (vắng hoặc dị dạng) thì lấy của nguồn sau. Tên rơi về `bo_luat` — chính
 * `documents.ten`, thứ mọi payload cũ đã mang.
 *
 * KHÔNG gộp `cach_trich`: câu đó mô tả chính đối tượng mang nó (trích dẫn có
 * điều khoản, metadata văn bản thì không), nên đọc riêng qua `cachTrichHopLe`.
 */
export function vanBanHopLe(...nguon: unknown[]): VanBanDaKiem {
  const ban = nguon.map(banGhi);
  const dau = <T>(doc: (r: Record<string, unknown>) => T | null): T | null => {
    for (const r of ban) {
      const v = doc(r);
      if (v !== null) return v;
    }
    return null;
  };
  return {
    ten_van_ban: dau((r) => chuHopLe(r["ten_van_ban"]) ?? chuHopLe(r["bo_luat"])),
    so_ky_hieu: dau((r) => chuHopLe(r["so_ky_hieu"])),
    co_quan_ban_hanh: dau((r) => chuHopLe(r["co_quan_ban_hanh"])),
    ngay_ban_hanh: dau((r) => ngayHopLe(r["ngay_ban_hanh"])),
    ngay_hieu_luc: dau((r) => ngayHopLe(r["ngay_hieu_luc"])),
    lien_ket: dau((r) => lienKetChinhThuc(r["lien_ket"])),
  };
}

/** `cach_trich` của CHÍNH `x`, hoặc `null`. */
export function cachTrichHopLe(x: unknown): string | null {
  return chuHopLe(banGhi(x)["cach_trich"]);
}

/**
 * "Do Chính phủ ban hành ngày 15/11/2019 · hiệu lực từ 01/01/2020" — thiếu phần
 * nào bỏ đúng phần đó; không biết gì thì `null`. Ngày hiệu lực là DỮ KIỆN của
 * văn bản; kết luận hiệu lực vẫn chỉ nằm ở nhãn (`BadgeHieuLuc`).
 */
export function dongBanHanh(v: VanBanDaKiem): string | null {
  const banHanh =
    v.co_quan_ban_hanh === null && v.ngay_ban_hanh === null
      ? null
      : [
          v.co_quan_ban_hanh === null ? null : `do ${v.co_quan_ban_hanh}`,
          "ban hành",
          v.ngay_ban_hanh === null ? null : `ngày ${ngayVietNam(v.ngay_ban_hanh)}`,
        ]
          .filter((p) => p !== null)
          .join(" ");
  const hieuLuc = v.ngay_hieu_luc === null ? null : `hiệu lực từ ${ngayVietNam(v.ngay_hieu_luc)}`;
  const dong = [banHanh, hieuLuc].filter((p) => p !== null).join(" · ");
  return dong === "" ? null : dong.charAt(0).toUpperCase() + dong.slice(1);
}

const DON_VI_TRICH = /^(Điều|Khoản|Điểm) (\S+)$/;

/**
 * `duong_dan` → cụm điều khoản theo lối văn bản luật: "45/2019/QH14 > Điều 21 >
 * Khoản 1 > Điểm a" → "điểm a khoản 1 Điều 21" (1.623 điều khoản trong kho viết
 * "khoản N Điều M", 0 viết "Điều M > Khoản"). Đoạn đầu là số hiệu, bỏ. Hàng
 * bảng ("Vùng I") không phải đơn vị trích dẫn nên dẫn tới khoản chứa nó; đường
 * không có Điều/Khoản/Điểm nào ("Phụ lục") giữ nguyên chữ.
 */
export function cumDieuKhoan(duongDan: string): string {
  const doan = duongDan.normalize("NFC").split(" > ").slice(1);
  const donVi = doan.flatMap((d) => {
    const m = DON_VI_TRICH.exec(d.trim());
    if (m === null) return [];
    return [m[1] === "Điều" ? d.trim() : `${(m[1] ?? "").toLowerCase()} ${m[2] ?? ""}`];
  });
  return donVi.length > 0 ? donVi.reverse().join(" ") : doan.join(" ");
}

/** Cụm điều khoản + phần văn bản (câu `cach_trich` CẤP VĂN BẢN, hoặc số hiệu). */
export function trichDieuKhoan(duongDan: string, vanBan: string): string {
  return `${cumDieuKhoan(duongDan)} ${vanBan}`.trim();
}

/** Thứ "Sao chép trích dẫn" chép: câu trích dẫn, kèm link chính thống khi có. */
export function chuoiSaoChep(cachTrich: string, lienKet: LienKet | null): string {
  return lienKet === null ? cachTrich : `${cachTrich} — ${lienKet.url}`;
}

/**
 * Câu cảnh báo hiệu lực của ĐÚNG trích dẫn — nó nêu đích danh văn bản thay
 * thế/sửa đổi (`assemble`: `"{số hiệu} {nhãn}: {lý do}"`), và là `ghiChu` của
 * `BadgeHieuLuc`.
 *
 * `canh_bao` (máy chủ gắn vào CHÍNH trích dẫn) thắng: hiệu lực tính theo điều
 * khoản, nên dò `warnings[]` theo số hiệu có thể đặt câu của điều đã bị thay
 * thế cạnh một điều còn hiệu lực cùng văn bản. Dò chỉ cho payload lưu trước
 * trường này; so cả dấu cách sau số hiệu: "2/2022/NĐ-CP" không được nhận câu
 * của "12/2022/NĐ-CP". Câu nào cũng qua `laCauChoNguoiDoc`: câu chẩn đoán thì
 * không có ghi chú.
 */
export function ghiChuHieuLuc(
  warnings: readonly string[],
  trichDan: { so_ky_hieu: string; canh_bao?: string | null },
): string | undefined {
  const cau =
    trichDan.canh_bao !== undefined
      ? (trichDan.canh_bao ?? undefined)
      : warnings.find((w) => w.startsWith(`${trichDan.so_ky_hieu} `));
  return cau !== undefined && laCauChoNguoiDoc(cau) ? cau : undefined;
}

const DAU_CHAN_DOAN =
  /MOJ|(?<![\p{L}\p{N}])(?:CHL|HHL1P|HHL)(?![\p{L}\p{N}])|độ tin cậy|tín hiệu|đồ thị|corpus|bảng mã|(?:chưa|không) xác định|đánh giá tại ngày|\p{L}+_\p{L}+/iu;

/**
 * Câu hiệu lực có được hiện cho người đọc không — ĐỊNH NGHĨA DUY NHẤT của
 * quyết định 2026-09-28, mục 10: không mã tình trạng nội bộ (MOJ, CHL, HHL…),
 * không "độ tin cậy", không "tín hiệu", không "đồ thị"/"corpus", không "chưa/
 * không xác định", không định danh máy (`chua_xac_dinh`). Câu không đạt thì
 * BỎ HẲN, không sửa lại: nhãn vẫn đứng đó và vẫn đúng.
 *
 * Mọi câu hiệu lực từ máy chủ (`canh_bao`, `warnings[]`, `mo_ta`) qua đây. Nó
 * bắt được cả lượt đã lưu trước khi máy chủ viết lời cho người đọc — các lượt
 * đó mang nguyên `ly_do` chẩn đoán của `effectivity.py`.
 */
export function laCauChoNguoiDoc(cau: string): boolean {
  const chu = cau.normalize("NFC");
  return chu.trim() !== "" && !DAU_CHAN_DOAN.test(chu);
}

/** Một mảnh của câu `mo_ta`: chữ thường, hoặc tên một văn bản bấm được. */
export type ManhMoTa = string | { chu: string; vanBan: VanBanDan };

/**
 * `HieuLucOut.mo_ta` cắt thành mảnh: tên mỗi văn bản của `van_ban_lien_quan`
 * (số hiệu, không thấy thì tên đầy đủ) thành mảnh bấm được, theo đúng thứ tự
 * danh sách. `null` = không hiện gì: vắng, rỗng, hoặc không phải câu cho người
 * đọc. Câu không nêu tên một văn bản thì văn bản đó KHÔNG thành link — giao
 * diện không chèn chữ nào máy chủ không viết.
 */
export function manhMoTa(hieuLuc: unknown): ManhMoTa[] | null {
  const r = banGhi(hieuLuc);
  const moTa = chuHopLe(r["mo_ta"])?.normalize("NFC") ?? null;
  if (moTa === null || !laCauChoNguoiDoc(moTa)) return null;
  const dsTho = r["van_ban_lien_quan"];
  const ra: ManhMoTa[] = [];
  let con = moTa;
  for (const vanBan of Array.isArray(dsTho) ? dsTho.filter(laVanBanDan) : []) {
    const chu = [vanBan.so_ky_hieu, vanBan.ten_van_ban]
      .map((c) => chuHopLe(c)?.normalize("NFC"))
      .find((c): c is string => c !== undefined && con.includes(c));
    if (chu === undefined) continue;
    const i = con.indexOf(chu);
    if (i > 0) ra.push(con.slice(0, i));
    ra.push({ chu, vanBan });
    con = con.slice(i + chu.length);
  }
  if (con !== "") ra.push(con);
  return ra;
}

/**
 * Các dòng "Thông tin văn bản" của trang văn bản. Trường vắng hoặc dị dạng thì
 * BỎ dòng — quyết định 2026-09-28, mục 8: không "Không rõ", không "Chưa có".
 * Ngày dd/mm/yyyy.
 */
export function dongThongTin(vanBan: unknown): [string, string][] {
  const r = banGhi(vanBan);
  const ngay = (khoa: string) => {
    const iso = ngayHopLe(r[khoa]);
    return iso === null ? null : ngayVietNam(iso);
  };
  const dong: [string, string | null][] = [
    ["Số hiệu", chuHopLe(r["so_ky_hieu"])],
    ["Loại văn bản", chuHopLe(r["loai_van_ban"])],
    ["Cơ quan ban hành", chuHopLe(r["co_quan_ban_hanh"])],
    ["Người ký", chuHopLe(r["nguoi_ky"])],
    ["Chức danh người ký", chuHopLe(r["chuc_danh_nguoi_ky"])],
    ["Ngày ban hành", ngay("ngay_ban_hanh")],
    ["Ngày có hiệu lực", ngay("ngay_hieu_luc")],
    ["Ngày hết hiệu lực", ngay("ngay_het_hieu_luc")],
  ];
  return dong.filter((d): d is [string, string] => d[1] !== null);
}

/**
 * Mục "Căn cứ pháp lý" cuối câu trả lời: MỖI điều khoản được dẫn một dòng, theo
 * thứ tự thẻ xuất hiện trong văn xuôi rồi trong ô bảng. Văn xuôi không có thẻ
 * nào bấm được → đúng tập của lưới an toàn `canCuConHieuLuc`.
 *
 * Bỏ nhóm 4 (bị thay thế / hết hiệu lực) như `canCuConHieuLuc` — spec
 * 2026-09-06 §7: thẻ trả lời chỉ dẫn luật còn hiệu lực. Thẻ trong văn xuôi vẫn
 * mở được chúng trong khung đối chiếu, nơi nhãn và câu nêu văn bản thay thế
 * hiện ra. Gộp theo `doc_id` + `duong_dan`: hai câu trích của cùng một khoản
 * là MỘT căn cứ.
 */
export function canCuPhapLy(
  ketQua: Pick<TraCuuKetQua, "answer" | "citations" | "bang">,
): { trichDan: Citation; chiSoGoc: number }[] {
  const { citations } = ketQua;
  const theoThe = [ketQua.answer ?? "", ...ketQua.bang.flatMap((b) => b.dong.flat())]
    .flatMap(catManh)
    .flatMap((m) => (m.kieu === "the" ? [chiSoCuaThe(m, citations)] : []))
    .filter((i) => i >= 0);
  const thuTu = theoThe.length > 0 ? theoThe : canCuConHieuLuc(citations).map((m) => m.chiSoGoc);
  const daCo = new Set<string>();
  const ra: { trichDan: Citation; chiSoGoc: number }[] = [];
  for (const chiSoGoc of thuTu) {
    const trichDan = citations[chiSoGoc];
    if (trichDan === undefined || nhomHieuLuc(trichDan.hieu_luc) === 4) continue;
    const khoa = `${trichDan.doc_id}\u0000${trichDan.duong_dan}`;
    if (daCo.has(khoa)) continue;
    daCo.add(khoa);
    ra.push({ trichDan, chiSoGoc });
  }
  return ra;
}
