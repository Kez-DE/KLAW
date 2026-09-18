/**
 * Xuất bản thảo hợp đồng ra tệp thật (.docx / .pdf) từ khung xem trước A4.
 * Toàn bộ xử lý diễn ra trên trình duyệt — không gửi nội dung bản thảo lên máy chủ.
 */
import type { BanThao, CauTruc } from "./klaw";

export type KieuDong = "quocHieu" | "tieuDe" | "soHieu" | "dieu" | "thuong";

/** `trai` (mặc định) | `giua` | `phai` | `deu` (Phase 9 U5) — căn lề THẬT đọc
 *  từ CSS `text-align` đã áp trên khung A4 (`docDong`), không phải suy đoán ở
 *  đây. `deu` (căn đều hai lề) là giá trị thứ tư từ 2026-09-19: nguồn khai
 *  `w:jc="both"`, hoặc thân bài của một văn bản KLAW tự soạn theo thể thức
 *  NĐ 30/2020 (`hieu_tai_lieu._the_thuc_hanh_chinh`). */
export type CanLe = "trai" | "giua" | "phai" | "deu";

/**
 * MỘT khoảng định dạng chữ trên `noiDung` của một khối văn xuôi — `[dau,
 * cuoi)` tính bằng ký tự, đọc từ `w:rPr` của tài liệu nguồn (quyết định
 * 2026-09-18, xem `DonViVanBan.dinh_dang` phía máy chủ).
 *
 * Khoảng chứ không phải chuỗi đã đánh dấu: `noiDung` vẫn là đúng chữ thuần
 * mà mọi phép neo trích dẫn và làm sạch phía máy chủ đang tra, và đây chỉ là
 * một lớp chỉ dẫn nằm CẠNH nó. Các khoảng KHÔNG phủ kín `noiDung`: chỗ trống
 * là chỗ nguồn không khai gì, và ở đó chữ giữ nguyên định dạng thường.
 *
 * `co` là NỬA điểm (`w:sz`, đơn vị của chính OOXML) — `.docx` dùng lại đúng
 * đơn vị này; `0` nghĩa là nguồn không khai cỡ. `phong` là tên phông NGUỒN
 * khai, `""` khi không khai: màn hình ánh xạ nó về một họ chữ có thật trong
 * kho (`phongTrenManHinh`), còn `.docx` ghi lại nguyên tên.
 */
export type KhoangChu = {
  dau: number;
  cuoi: number;
  dam: boolean;
  nghieng: boolean;
  gach: boolean;
  co: number;
  phong: string;
};

/**
 * Một ĐOẠN chữ liền mạch đã đọc lại TỪ DOM đã vẽ — cùng vai trò `BangThat`
 * với `docBangTuPhanTu`: màn hình vẽ trước, tệp đọc lại đúng thứ đã vẽ, nên
 * `.docx` không thể nói khác `XemTruocA4`.
 *
 * Khác `KhoangChu` (offset, đi TỪ máy chủ RA màn hình) ở chỗ đây đã là chữ
 * thật của từng đoạn — đường về, và là thứ `TextRun` của `docx` cần.
 */
/**
 * MỘT mốc tab (`w:pPr/w:tabs/w:tab`) — chỗ con trỏ nhảy tới, và đường vẽ lấp
 * khoảng nhảy qua.
 *
 * `pos` là twip tính từ mép TRÁI của cột chữ. `leader` rỗng nghĩa là nhảy
 * suông, không vẽ gì (mặc định của chính OOXML); `dot` là thứ vẽ ra dòng
 * "…………" mà một biểu mẫu tiếng Việt chừa cho người điền tay.
 */
export type MocTab = { val: string; pos: number; leader: string };

/** Một mốc tab kèm CHỖ nó đứng trong `noiDung` — offset ký tự, không phải một
 *  ký tự: `<w:tab/>` chưa bao giờ nằm trong `noi_dung` (xem `GianCach.tab`
 *  phía máy chủ), và bản vá này không được thêm nó vào. */
export type KhoangTab = MocTab & { o: number };

/**
 * Giãn cách và thụt lề của MỘT đoạn (`w:spacing` + `w:ind`) — twip, `0` khi
 * nguồn không khai.
 *
 * `dong` đọc cùng `luatDong`: `auto` (mặc định OOXML) thì `dong` là BỘI SỐ của
 * 240 (360 = 1,5 dòng), `exact`/`atLeast` thì `dong` là twip tuyệt đối. Một
 * con số không tự nói nó đang đo cái gì, nên hai trường đi liền nhau.
 */
export type GianCachDoan = {
  truoc: number;
  sau: number;
  dong: number;
  luatDong: string;
  trai: number;
  phai: number;
  dauDong: number;
  treo: number;
};

/** Những gì máy chủ gửi xuống cho MỘT khối văn xuôi: nhịp của đoạn cộng chỗ
 *  đứng của từng mốc tab. Đường VỀ (`DongVanBan`) không mang `tab` vì lúc ấy
 *  mốc đã thành một đoạn `DoanChu` trên DOM — xem `DoanChu.tab`. */
export type GianCachKhoi = GianCachDoan & { tab: KhoangTab[] };

export type DoanChu = {
  text: string;
  inDam: boolean;
  inNghieng: boolean;
  gachChan: boolean;
  /** Nửa điểm (`w:sz`), `0` = theo cỡ mặc định của chính dòng (`coChuPt`). */
  coChu: number;
  phong: string;
  /**
   * Khác `null` thì đoạn này KHÔNG phải chữ mà là một ký tự TAB (`text` luôn
   * rỗng): con trỏ nhảy tới `pos`, vẽ `leader` trên đường nhảy.
   *
   * Đi chung một dãy với các đoạn chữ chứ không một mảng riêng vì tab nằm
   * GIỮA chữ, và một dãy giữ được thứ tự ấy mà hai mảng song song thì không.
   * `.docx` ghi nó thành một `w:r` chứa `<w:tab/>`, PDF vẽ đường dẫn rồi đẩy
   * con trỏ, màn hình vẽ đường dẫn với bề rộng bằng 0 (xem `XemTruocA4`).
   */
  tab: MocTab | null;
};

export type DongVanBan = {
  text: string;
  kieu: KieuDong;
  canhLe: CanLe;
  inDam: boolean;
  inNghieng: boolean;
  thutLe: number;
  /**
   * Định dạng chữ theo từng đoạn trong dòng. RỖNG nghĩa là dòng đồng nhất —
   * `inDam`/`inNghieng` ở trên nói hết, và mọi nhánh xuất tệp chạy đúng như
   * trước bản vá này. Khác rỗng thì các đoạn phủ KÍN dòng theo thứ tự, nối
   * lại bằng đúng `text`.
   */
  doan: DoanChu[];
  /**
   * Giãn cách/thụt lề NGUỒN của đoạn (2026-09-18), đọc lại từ `data-*` trên
   * chính thẻ `<p>` mà `XemTruocA4` đã vẽ — không phải từ `getComputedStyle`:
   * màn hình quy twip ra `pt` để vẽ, và đọc ngược `px` đã tính rồi quy lại
   * twip sẽ làm tròn hai lần, trong khi `.docx` cần đúng con số nguồn.
   *
   * `null` = nguồn không khai gì (và mọi bản thảo lưu trước bản vá này) —
   * mọi nhánh xuất tệp khi đó chạy y như trước.
   */
  gianCach: GianCachDoan | null;
};

/**
 * Một khối nội dung theo ĐÚNG thứ tự xuất hiện trong khung A4 — hoặc một
 * đoạn/tiêu đề (`dong`), hoặc một bảng thật (`bang`, Phase 7 R3: hàng×ô nguyên
 * văn, hàng đầu là tiêu đề). Union thay vì hai mảng song song vì thứ tự CHUNG
 * giữa đoạn văn và bảng mới là thứ `xuatWord` cần để không đẩy một bảng giữa
 * tài liệu (như bảng đánh giá) xuống cuối, như `oKy` cố ý làm cho khối ký.
 */
/**
 * Một bảng đã đọc — hàng×ô nguyên văn cộng hai sự thật cấu trúc riêng của
 * NGUỒN (Phase 11 R1/R6), không suy đoán lại từ số ô:
 *
 * - `nhip`: số cột mỗi ô CHIẾM, CÙNG hình dạng `hang` — đọc thẳng
 *   `bang_nhip`/`w:gridSpan` qua backend. Rỗng khi bảng không có lưới nguồn
 *   (mô hình tự soạn) — `coSpanHang` khi đó vẫn suy đoán từ số ô như trước
 *   Phase 11, đúng "quy tắc cho ca không khai lưới" R6 giữ lại.
 * - `tiLe`: % mỗi cột lưới trên bề rộng bảng, đọc `w:tblGrid`. Rỗng khi
 *   không khai lưới → chia đều (R1).
 * - `vien`: nguồn có VẼ viền cho bảng này không (`w:tblBorders`/`w:tcBorders`/
 *   `w:tblStyle`). Biểu mẫu tiếng Việt xếp cột bằng bảng KHÔNG viền — khối
 *   ký cuối trang, letterhead "tên đơn vị trái / quốc hiệu phải" — nên một
 *   bảng không viền phải ra BỐ CỤC: cột nọ cạnh cột kia, không nét nào, không
 *   hàng đầu tô đậm. `true` cho bảng mô hình tự soạn (không có nguồn nào để
 *   đọc) và cho clause lưu trước trường này: giữ đúng hành vi cũ.
 * - `cao`: chiều cao KHAI BÁO mỗi hàng theo twip (`w:trHeight`), `0` khi hàng
 *   không khai. Đây là chỗ trống để ký tay của một hàng ký.
 * - `canLeO`: căn lề TỪNG Ô (`w:jc` của đoạn đầu ô), cùng hình dạng `hang`.
 *   Rỗng khi không đọc được — ô khi đó về `trai` như mọi nhánh fail-closed
 *   khác ở tệp này.
 * - `chuO`: các ĐOẠN chữ của TỪNG Ô (`w:rPr`), cùng hình dạng `hang`. Mảng
 *   rỗng ở một ô nghĩa là ô ĐỒNG NHẤT — cùng quy ước `DongVanBan.doan` dùng
 *   cho một dòng văn xuôi, nên ba nơi vẽ chỉ phải biết một luật: có đoạn thì
 *   vẽ từng đoạn, không có thì vẽ cả ô một kiểu như trước bản vá này.
 *
 *   Là `DoanChu[]` (chữ đã cắt) chứ không `KhoangChu[]` (offset) vì `BangThat`
 *   đi CẢ HAI chiều — từ máy chủ ra màn hình, và từ DOM đã vẽ vào tệp — còn
 *   offset chỉ có nghĩa ở chiều đi: `docBangTuPhanTu` đọc lại từ DOM đã chuẩn
 *   hoá khoảng trắng, ở đó không còn chuỗi gốc nào để đo offset lên. Cắt ngay
 *   tại cửa vào (`chuOHopLe`) cho hai chiều CÙNG một kiểu.
 */
export type BangThat = {
  hang: string[][];
  nhip: number[][];
  tiLe: number[];
  vien: boolean;
  /**
   * Viền TỪNG CẠNH của từng ô, cùng hình dạng `hang` — mỗi ô MỘT chuỗi
   * `"trên|phải|dưới|trái"`, mỗi phần là `"w:val/w:sz"` nguyên văn nguồn
   * (phần rỗng = cạnh đó không có nét). Backend đã ghép bảng+ô+vị trí ở
   * `hieu_tai_lieu._vien_o_bang`; ba nơi vẽ chỉ còn đọc và quy đổi.
   *
   * RỖNG nghĩa là nguồn không nói gì về hình dạng viền — `vien` ở trên nói
   * hết, và ba nơi vẽ kẻ MỘT nét đều cho mọi ô y như trước bản vá này. Cũng
   * là câu trả lời khi một cạnh khai `w:sz` không đọc ra số: nửa bảng theo
   * nguồn, nửa kia đoán bừa là tệ hơn cả bảng lùi về nét đều.
   */
  vienO: string[][];
  cao: number[];
  /**
   * `w:trHeight/@w:hRule` của từng hàng — `"exact"`, `"atLeast"`, `"auto"`,
   * hoặc `""` khi hàng không khai. Rỗng cả mảng với bản thảo lưu trước bản vá.
   *
   * `auto` BỎ con số `cao` (Word bỏ nó ở đó). `exact` vẽ như chiều cao TỐI
   * THIỂU, KHÔNG cắt chữ — xem `DonViVanBan.bang_cao_luat`: cắt mất chữ của
   * người dùng hỏng hơn một hàng cao dôi vài milimét, và ba nơi vẽ chọn
   * giống nhau nên tệp tải về không bao giờ khác màn hình.
   */
  caoLuat: string[];
  canLeO: CanLe[][];
  chuO: DoanChu[][][];
};

/** Lề trang NGUỒN (`w:sectPr/w:pgMar`), twip — `null` khi tệp không khai, và
 *  khi đó ba nơi vẽ giữ đúng lề mặc định của chính chúng. */
export type LeTrang = {
  tren: number;
  phai: number;
  duoi: number;
  trai: number;
  dauTrang: number;
  chanTrang: number;
};

/**
 * MỘT ảnh đã tách khỏi tài liệu nguồn (quyết định 2026-09-18) — logo
 * letterhead, con dấu, chữ ký quét.
 *
 * `url` trỏ về `/tai-lieu/{viec}/anh/{tên}`, endpoint DUY NHẤT phát bytes và
 * là chỗ kiểm chủ sở hữu. Không phải data URI: nhúng bytes vào bản thảo sẽ
 * đẩy con dấu của bên thứ ba vào mọi phản hồi và mọi khung SSE.
 *
 * `rong`/`cao` là EMU (914400 EMU = 1 inch), đúng đơn vị `wp:extent` của
 * nguồn — cùng lý lẽ `KhoangChu.co` giữ nửa điểm và `LeTrang` giữ twip: quy
 * đổi ở cửa vào thì `.docx` phải quy ngược lại và làm tròn hai lần. `0` nghĩa
 * là nguồn KHÔNG khai cỡ, và ở đó ba nơi vẽ dùng cỡ thật của chính ảnh.
 */
export type AnhNguon = {
  url: string;
  rong: number;
  cao: number;
  vung: "than" | "dau_trang" | "chan_trang";
  thuTu: number;
};

/** 1pt = 12700 EMU — mốc quy `wp:extent` sang đơn vị ba nơi vẽ dùng được. */
export const EMU_MOI_PT = 12700;

/** 1px = 9525 EMU (96 dpi) — đơn vị `docx.IMediaTransformation` nhận, và là
 *  hệ quy chiếu của `HTMLImageElement.naturalWidth`. */
export const EMU_MOI_PX = 9525;

export type KhoiVanBan =
  { kind: "dong"; d: DongVanBan } | ({ kind: "bang" } & BangThat) | { kind: "anh"; a: AnhNguon };

export type NoiDungXuat = {
  khoi: KhoiVanBan[];
  /**
   * Các cột của khối ký. MỘT cột là hợp lệ, không phải hai.
   *
   * Trước đây `xuatWord` chỉ dựng bảng ký khi `oKy.length === 2`, vì bộ dựng
   * thân văn bản cũ luôn ra đúng hai bên. Nay khối ký chỉ hiện khi chính
   * `cau_truc` có mục chữ ký, và với công văn hay đơn khiếu nại thì mục ấy có
   * MỘT người ký. Giữ điều kiện `=== 2` sẽ nuốt trọn khối ký ra khỏi tệp `.docx`
   * người dùng tải về, mà trên màn hình vẫn thấy nó.
   */
  oKy: DongVanBan[][];
  /** Lề trang NGUỒN đã vẽ trên khung A4 (`data-le-*`), đọc lại để `.docx` và
   *  PDF đặt ĐÚNG lề màn hình đang dùng — `null` khi khung không mang lề nguồn
   *  nào, và khi đó hai tệp giữ lề mặc định cũ của chúng. */
  leTrang: LeTrang | null;
};

/**
 * MỘT khối nội dung của một mục, theo ĐÚNG thứ tự tài liệu (Phase 8 R1 —
 * thay "một mục là văn xuôi HOẶC bảng" của Phase 7: giờ một mục là một MẢNG
 * khối, ví dụ câu dẫn / bảng / câu kết, ba khối riêng chứ không nén về hai
 * trường cố định).
 */
export type KhoiMuc =
  | {
      kind: "vanXuoi";
      noiDung: string;
      canhLe: CanLe;
      chu: KhoangChu[];
      gianCach: GianCachKhoi | null;
    }
  | ({ kind: "bang" } & BangThat);

/** Một mục dựng sẵn cho `XemTruocA4`: nội dung của `clauses` ghép vào khung `cau_truc.muc`. */
export interface Muc {
  stt: number;
  key: string;
  ten: string;
  /**
   * Tên mục này có phải chữ THẬT của tài liệu nguồn hay do mô hình đặt ra để
   * TỔ CHỨC bản thảo (Phase 9 U1) — `false` thì `XemTruocA4` không in `ten`
   * ra trang (bản thảo `tong_quat` mới, `laTongQuat` mới đọc trường này; bản
   * thảo checklist luôn `true` vì tên mục ở đó đến từ chính checklist, không
   * phải mô hình bịa). Vắng mặt (clause lưu trước Phase 9) mặc định `true`:
   * an toàn hơn ẩn oan một tiêu đề thật.
   */
  tenThat: boolean;
  /**
   * Giữ lại CHỈ cho `DrawerSuaMuc` (bản thảo checklist — không bao giờ có
   * `khoi`/`bang`, xem `SanKhauBanThao.laTongQuat`) và cho tương thích ngược
   * với mã đã đọc hai trường này trước Phase 8. `XemTruocA4` (bản thảo tổng
   * quát) không đọc hai trường này nữa — nó render `khoi` bên dưới.
   */
  noiDung: string;
  /** @deprecated dùng `khoi` — giữ vì lý do tương thích nêu trên. */
  bang: string[][] | null;
  /**
   * Nội dung mục theo ĐÚNG THỨ TỰ khối (Phase 8 R1) — nguồn RENDER chính của
   * `XemTruocA4`. Quy về ĐÚNG MỘT hình dạng dù `clauses[i]` mang khoá `khoi`
   * (Phase 8), `noi_dung`+`bang` rời (Phase 7), hay chỉ `noi_dung` (trước cả
   * hai) — ba hình dạng đó là BA THỜI ĐIỂM khác nhau của cùng cột JSONB
   * `ban_thao.clauses`, không migration nào viết lại hàng cũ (xem
   * `khoiTuClause`).
   */
  khoi: KhoiMuc[];
  /**
   * `DonViVanBan.vung` mang qua (Phase 8 R2) — `than` (thân bài, mặc định),
   * `dau_trang`/`chan_trang` khi mục lấy từ đầu/chân trang thật của tài
   * liệu nguồn. Chỉ mô tả, `XemTruocA4` không render khác đi theo trường
   * này — skipped: kiểu dáng riêng cho đầu/chân trang, thêm khi đo thấy một
   * bản dựng lại trông sai nếu thiếu nó.
   */
  vung: "than" | "dau_trang" | "chan_trang";
  /**
   * Trang NGUỒN mục này nằm trên — số trang tệp KHAI (`w:br w:type="page"` và
   * ngắt phân đoạn, xem `doc_tai_lieu._DemTrang`), mang qua từ
   * `DonViVanBan.trang` của đơn vị mà khối đầu của mục định vị được.
   *
   * `XemTruocA4` cắt tờ A4 ở CHÍNH chỗ trường này tăng — đó là "ngắt đúng chỗ
   * nguồn khai ngắt". 1 cho mọi bản thảo lưu trước bản vá này và cho bản thảo
   * KLAW tự soạn; khi đó khung xem trước ra đúng MỘT tờ như trước.
   */
  trang: number;
  canCu: string | null;
}

/**
 * Hình dạng THẬT của một phần tử `BanThao.clauses` (kiểu `unknown[]` chưa gõ ở FE) —
 * khớp `dataclasses.asdict(DraftClause)` (`src/agents/nodes/draft_generate.py` +
 * `src/services/ban_thao.py` dòng ghi `clauses`): `key`, `ten`, `noi_dung`,
 * `can_cu_provision_id`. KHÔNG có trường `text` — chỉ `noi_dung` mang nội dung.
 * `bang` (Phase 7) và `khoi`/`vung` (Phase 8) chỉ có ở `clauses` do
 * `dung_ban_thao_tong_quat.clauses_tu` dựng — BA hình dạng cùng một cột JSONB,
 * từ ba thời điểm khác nhau, không migration nào viết lại hàng cũ.
 */
type ClauseTho = {
  key?: string;
  ten?: string;
  ten_that?: unknown;
  noi_dung?: string;
  bang?: unknown;
  khoi?: unknown;
  vung?: unknown;
  trang?: unknown;
  le_trang?: unknown;
  anh?: unknown;
};

/** `c.bang` thô (kiểu chưa biết, tới từ `unknown[]`) → hàng×ô hợp lệ, hoặc
 * `null` khi rỗng/vắng/sai hình dạng — một mục cũ không có khoá này phải rơi
 * đúng vào nhánh văn xuôi, không phải một bảng 0 hàng. Hàng NGẮN hơn hàng đầu
 * (Phase 8 R4, ô gộp trong tài liệu nguồn) đi qua NGUYÊN — đây chỉ gõ kiểu,
 * không đệm/cắt; `coSpanHang` mới quyết định cách VẼ một hàng ngắn. */
function bangHopLe(bang: unknown): string[][] | null {
  if (!Array.isArray(bang) || bang.length === 0) return null;
  return bang.map((hang) => (Array.isArray(hang) ? hang.map((o) => String(o)) : []));
}

const VUNG_HOP_LE = new Set(["than", "dau_trang", "chan_trang"]);

/** `c.vung` thô → nhãn hợp lệ, mặc định `than` khi vắng/lạ (Phase 8 R2) —
 * cùng luật fail-closed với `lam_sach_van_ban` phía máy chủ. */
function vungHopLe(vung: unknown): Muc["vung"] {
  return typeof vung === "string" && VUNG_HOP_LE.has(vung) ? (vung as Muc["vung"]) : "than";
}

/**
 * `c.trang` thô → số trang NGUỒN của mục, mặc định 1 khi vắng/lạ.
 *
 * Fail closed về phía MỘT trang: một bản thảo lưu trước bản vá dòng chảy trang
 * (và mọi bản thảo KLAW tự soạn, vốn không có tài liệu nguồn nào để khai ngắt)
 * không có khoá này, và ở đó "tất cả trên một tờ" là đúng hành vi cũ. Vẽ thêm
 * một ngắt trang không có thật xé đôi tài liệu ở chỗ nguồn không hề ngắt — tệ
 * hơn hẳn thiếu một ngắt, cùng lý lẽ `leTrangHopLe` đã đặt cho lề.
 */
function trangHopLe(trang: unknown): number {
  const n = Number(trang);
  return Number.isInteger(n) && n >= 1 ? n : 1;
}

const CAN_LE_HOP_LE = new Set(["trai", "giua", "phai", "deu"]);

/** `k.can_le` thô → nhãn hợp lệ, mặc định `trai` khi vắng/lạ (Phase 9 U5) —
 * cùng luật fail-closed với `vungHopLe`/`lam_sach_van_ban` phía máy chủ. */
function canLeHopLe(canLe: unknown): CanLe {
  return typeof canLe === "string" && CAN_LE_HOP_LE.has(canLe) ? (canLe as CanLe) : "trai";
}

/** `c.ten_that` thô → `boolean`, mặc định `true` khi vắng/không phải boolean
 * (clause lưu trước Phase 9, hoặc `muc` viết tay của test) — an toàn hơn ẩn
 * oan một tiêu đề thật (xem `Muc.tenThat`). */
function tenThatHopLe(tenThat: unknown): boolean {
  return typeof tenThat === "boolean" ? tenThat : true;
}

/** `k.ti_le` thô → mảng % cột hợp lệ, hoặc `[]` khi rỗng/vắng/sai hình dạng
 * (Phase 11 R1) — bảng không khai lưới thì không suy đoán tỉ lệ, render
 * chia đều (xem `BangThat`). */
function tiLeHopLe(tiLe: unknown): number[] {
  if (!Array.isArray(tiLe) || tiLe.length === 0) return [];
  const ra = tiLe.map((v) => Number(v));
  return ra.every((v) => Number.isFinite(v) && v > 0) ? ra : [];
}

/** `k.nhip` thô → mảng-hàng số cột mỗi ô CHIẾM, CÙNG hình dạng `hang` (Phase
 * 11 R6) — một hàng lệch số ô so với `hang` cùng hàng làm CẢ khối mất `nhip`
 * (về `[]`, `coSpanHang` suy đoán như trước Phase 11): một nhịp sai hình
 * dạng gây lệch cột còn tệ hơn không có nhịp nào cả. */
/** `k.vien` thô → có vẽ viền không, mặc định `true` khi vắng/không phải
 * boolean: một clause lưu TRƯỚC trường này không nói gì về viền, và vẽ viền
 * như trước bản vá là câu trả lời không đổi hành vi — ngược lại (`false`) sẽ
 * xoá viền của mọi bảng dữ liệu đã lưu. */
function vienHopLe(vien: unknown): boolean {
  return typeof vien === "boolean" ? vien : true;
}

/** Một ô của `k.vien_o`: ĐÚNG bốn phần ngăn bởi `|`, mỗi phần RỖNG (cạnh không
 *  có nét) hoặc `"w:val/w:sz"` với `w:sz` rỗng hay toàn chữ số. Backend luôn
 *  ghép đúng bốn phần (`_vien_o_bang`), nên một chuỗi lệch khuôn là dữ liệu
 *  hỏng, không phải một hình dạng cũ nào cần đỡ. */
const O_VIEN_HOP_LE = /^(?:[^|/]*\/\d*)?(?:\|(?:[^|/]*\/\d*)?){3}$/;

/** `k.vien_o` thô → viền từng cạnh mỗi Ô, CÙNG hình dạng `hang`, hoặc `[]`
 *  khi vắng/sai hình dạng — fail-closed CẢ BẢNG như `nhipHopLe`/`caoHopLe`:
 *  nửa bảng kẻ theo nguồn, nửa kia kẻ nét đều là tệ hơn cả bảng kẻ nét đều. */
function vienOHopLe(vienO: unknown, hang: string[][]): string[][] {
  if (!Array.isArray(vienO) || vienO.length !== hang.length) return [];
  const ra: string[][] = [];
  for (let h = 0; h < hang.length; h++) {
    const dong = vienO[h];
    if (!Array.isArray(dong) || dong.length !== hang[h]!.length) return [];
    if (!dong.every((o) => typeof o === "string" && O_VIEN_HOP_LE.test(o))) return [];
    ra.push(dong as string[]);
  }
  return ra;
}

/** `k.cao_luat` thô → `@w:hRule` mỗi HÀNG, hoặc `[]` khi vắng/sai hình dạng —
 *  cùng luật `caoHopLe`: một luật gán nhầm hàng tệ hơn không có luật nào. */
function caoLuatHopLe(caoLuat: unknown, hang: string[][]): string[] {
  if (!Array.isArray(caoLuat) || caoLuat.length !== hang.length) return [];
  return caoLuat.every((v) => typeof v === "string") ? (caoLuat as string[]) : [];
}

/**
 * MỘT cạnh `"w:val/w:sz"` → nét vẽ được, `null` khi cạnh không có nét.
 *
 * Chỗ DUY NHẤT dịch một cạnh nguồn thành hình: màn hình, `.docx` và PDF gọi
 * chung, nên không nơi nào tự nhớ một quy ước riêng rồi lệch nhau.
 *
 * - Phần rỗng = cạnh KHÔNG được khai ở đâu cả → không nét.
 * - `w:val` `none`/`nil` = tệp nói RÕ là không vẽ → không nét. Mọi giá trị
 *   khác (kể cả rỗng, tức `w:val` thiếu — `doc_tai_lieu._co_net` cũng đọc
 *   như vậy) là một nét thật; không đoán thêm ở đây.
 * - `w:sz` rỗng → 4 (½pt, bề dày viền bảng mặc định của Word). Đây là giá trị
 *   duy nhất phải ĐOÁN trong cả bản vá, và nói thẳng ra ở đây: một cạnh có
 *   kiểu mà không có bề dày vẫn phải vẽ ra được một thứ gì đó.
 */
export function netCanh(tho: string): { val: string; sz: number } | null {
  const [val = "", sz = ""] = tho.split("/");
  if (tho === "" || val === "none" || val === "nil") return null;
  const n = Number(sz);
  return { val, sz: sz !== "" && Number.isFinite(n) && n > 0 ? n : 4 };
}

/** `w:val` → `border-style` của CSS. Giá trị lạ vẽ nét liền: nó LÀ một nét
 *  thật, và vẽ sai kiểu vẫn đúng hơn không vẽ gì (xem `netCanh`). */
export function kieuNetCSS(val: string): "solid" | "double" | "dotted" | "dashed" {
  if (val === "double") return "double";
  if (val.startsWith("dot")) return "dotted";
  if (val.startsWith("dash")) return "dashed";
  return "solid";
}

/** Bốn cạnh của một ô, theo thứ tự CSS — cùng thứ tự `hieu_tai_lieu._CSS_CANH`
 *  ghép ra, để hai phía không phải thoả thuận gì thêm. */
export const CANH_O = ["top", "right", "bottom", "left"] as const;

/** `k.cao` thô → chiều cao twip mỗi HÀNG, hoặc `[]` khi rỗng/vắng/sai hình
 * dạng — một mảng lệch số hàng so với `hang` làm cả khối mất chiều cao, cùng
 * luật `nhipHopLe`: một chiều cao gán nhầm hàng còn tệ hơn không có. */
function caoHopLe(cao: unknown, hang: string[][]): number[] {
  if (!Array.isArray(cao) || cao.length !== hang.length) return [];
  const ra = cao.map((v) => Number(v));
  return ra.every((v) => Number.isFinite(v) && v >= 0) ? ra : [];
}

/** `k.can_le_o` thô → căn lề mỗi Ô, CÙNG hình dạng `hang` — lệch hình dạng
 * thì cả khối về `[]` (mọi ô `trai`), cùng luật `nhipHopLe`. */
function canLeOHopLe(canLeO: unknown, hang: string[][]): CanLe[][] {
  if (!Array.isArray(canLeO) || canLeO.length !== hang.length) return [];
  const ra: CanLe[][] = [];
  for (let h = 0; h < hang.length; h++) {
    const dong = canLeO[h];
    if (!Array.isArray(dong) || dong.length !== hang[h]!.length) return [];
    ra.push(dong.map(canLeHopLe));
  }
  return ra;
}

/**
 * `k.chu` thô → khoảng định dạng hợp lệ, hoặc `[]` khi vắng/sai hình dạng.
 *
 * Fail-closed CẢ KHỐI, cùng luật `nhipHopLe`/`caoHopLe`: một khoảng chồng
 * lên khoảng trước, tràn khỏi `noiDung`, hay đảo đầu-cuối sẽ cắt chữ sai chỗ
 * — in đậm nửa từ còn khó đọc hơn không in đậm gì. Một khoảng sai làm cả khối
 * về chữ thường, không phải làm cả khối sai.
 */
function chuHopLe(chu: unknown, noiDung: string): KhoangChu[] {
  if (!Array.isArray(chu) || chu.length === 0) return [];
  const ra: KhoangChu[] = [];
  let het = 0;
  for (const k of chu) {
    if (typeof k !== "object" || k === null) return [];
    const o = k as {
      dau?: unknown;
      cuoi?: unknown;
      dam?: unknown;
      nghieng?: unknown;
      gach?: unknown;
      co?: unknown;
      phong?: unknown;
    };
    const dau = Number(o.dau);
    const cuoi = Number(o.cuoi);
    if (!Number.isInteger(dau) || !Number.isInteger(cuoi)) return [];
    if (dau < het || cuoi <= dau || cuoi > noiDung.length) return [];
    const co = Number(o.co ?? 0);
    if (!Number.isFinite(co) || co < 0) return [];
    ra.push({
      dau,
      cuoi,
      dam: o.dam === true,
      nghieng: o.nghieng === true,
      gach: o.gach === true,
      co,
      phong: typeof o.phong === "string" ? o.phong : "",
    });
    het = cuoi;
  }
  return ra;
}

/** `w:lineRule` mà `docx` ghi được. Giá trị lạ thì KHÔNG ghi `lineRule` nào —
 *  Word rơi về `auto`, đúng mặc định của chính OOXML. */
const LUAT_DONG_DOCX = new Set(["auto", "atLeast", "exact", "exactly"]);

/** `w:tab/@w:val` nguồn → `TabStopType` của `docx`. `start`/`end` là tên OOXML
 *  strict của `left`/`right`, cùng nghĩa. */
const CAN_TAB_DOCX = {
  left: "left",
  start: "left",
  center: "center",
  right: "right",
  end: "right",
  decimal: "decimal",
} as const;

/** `w:leader` nguồn → `LeaderType` của `docx`. Giá trị vắng/lạ thì không ghi
 *  `leader` nào: Word rơi về `none`, đúng mặc định của chính `w:leader`. */
const DAN_TAB_DOCX = {
  dot: "dot",
  hyphen: "hyphen",
  underscore: "underscore",
  middleDot: "middleDot",
} as const;

/** Bốn kiểu canh của một mốc tab OOXML mà ba nơi vẽ đều hiểu. `bar`/`num`/
 *  `clear` KHÔNG có ở đây: `clear` đã bị bộ đọc loại, còn hai kiểu kia vẽ ra
 *  thứ khác hẳn một chỗ nhảy — coi chúng là `left` sẽ đặt chữ sai chỗ. */
const CAN_TAB_HOP_LE = new Set(["left", "start", "center", "right", "end", "decimal"]);

/** Kiểu đường dẫn OOXML vẽ được. Rỗng/`none`/lạ = không vẽ gì — mặc định của
 *  chính `w:leader`, cùng luật `w:u` không suy ra gạch chân khi thiếu giá trị. */
const DAN_TAB_HOP_LE = new Set(["dot", "hyphen", "underscore", "middleDot"]);

/**
 * `k.gian_cach` thô → nhịp đoạn + mốc tab, hoặc `null` khi vắng/sai hình dạng.
 *
 * Fail-closed CẢ KHỐI, cùng luật `chuHopLe`: một con số không đọc ra, một
 * offset tab nằm ngoài `noiDung`, hay một mốc `pos` âm sẽ đặt chữ và đường dẫn
 * sai chỗ — và một bố cục sai chỗ khó đọc hơn hẳn một bố cục mặc định. Giãn
 * cách âm được (`w:ind` âm là cách một biểu mẫu thật tràn ra ngoài lề), nhưng
 * `pos` thì không: một mốc ở toạ độ âm không tồn tại trên trang nào.
 */
function gianCachHopLe(gc: unknown, noiDung: string): GianCachKhoi | null {
  if (typeof gc !== "object" || gc === null) return null;
  const o = gc as Record<string, unknown>;
  const so = (v: unknown): number | null => {
    const n = Number(v ?? 0);
    return Number.isFinite(n) ? n : null;
  };
  const ra: Record<string, number> = {};
  for (const ten of ["truoc", "sau", "dong", "trai", "phai", "dauDong", "treo"] as const) {
    const n = so(o[ten === "dauDong" ? "dau_dong" : ten]);
    if (n === null) return null;
    ra[ten] = n;
  }
  if (ra["dong"]! < 0 || ra["truoc"]! < 0 || ra["sau"]! < 0) return null;

  const tab: KhoangTab[] = [];
  const tho = o["tab"];
  if (tho !== undefined) {
    if (!Array.isArray(tho)) return null;
    for (const t of tho) {
      if (typeof t !== "object" || t === null) return null;
      const m = t as Record<string, unknown>;
      const vi = so(m["o"]);
      const pos = so(m["pos"]);
      if (vi === null || pos === null) return null;
      if (!Number.isInteger(vi) || vi < 0 || vi > noiDung.length || pos <= 0) return null;
      const val = String(m["val"] ?? "left");
      if (!CAN_TAB_HOP_LE.has(val)) return null;
      const leader = String(m["leader"] ?? "");
      tab.push({ o: vi, pos, val, leader: DAN_TAB_HOP_LE.has(leader) ? leader : "" });
    }
  }
  return {
    truoc: ra["truoc"]!,
    sau: ra["sau"]!,
    dong: ra["dong"]!,
    luatDong: typeof o["luat_dong"] === "string" ? o["luat_dong"] : "",
    trai: ra["trai"]!,
    phai: ra["phai"]!,
    dauDong: ra["dauDong"]!,
    treo: ra["treo"]!,
    tab: tab.sort((a, b) => a.o - b.o),
  };
}

/**
 * `k.chu_o` thô → các ĐOẠN chữ của từng ô, CÙNG hình dạng `hang`.
 *
 * Hai tầng fail-closed, mỗi tầng ở đúng chỗ nó chứng minh được điều gì:
 * lệch HÌNH DẠNG (thiếu hàng, thiếu ô) làm cả khối về `[]` như `canLeOHopLe`
 * — ở đó không còn biết khoảng nào thuộc ô nào; còn một ô có khoảng HỎNG chỉ
 * mất định dạng của CHÍNH nó (`chuHopLe` trả `[]`), vì offset của một ô chỉ
 * nói về chữ của ô đó, và bắt cả bảng về chữ thường vì một ô là phạt quá tay.
 * Cả hai đều fail-closed: không bao giờ vẽ một phần một ô.
 *
 * Cắt ngay tại đây (`catTheoChu`) thay vì mang offset xuống render: xem
 * `BangThat.chuO` cho lý do hai chiều.
 */
function chuOHopLe(chuO: unknown, hang: string[][]): DoanChu[][][] {
  if (!Array.isArray(chuO) || chuO.length !== hang.length) return [];
  const ra: DoanChu[][][] = [];
  for (let h = 0; h < hang.length; h++) {
    const dong = chuO[h];
    if (!Array.isArray(dong) || dong.length !== hang[h]!.length) return [];
    ra.push(
      dong.map((o, oi) => {
        const chu = chuHopLe(o, hang[h]![oi]!);
        // Ô không khoảng nào (hoặc khoảng hỏng) giữ `[]` — "đồng nhất", chứ
        // không phải MỘT đoạn phủ kín: hai thứ đó vẽ ra khác nhau ở `.docx`
        // (một `w:r` mang `w:sz` mặc định thay vì không `w:r` riêng nào).
        return chu.length > 0 ? catTheoChu(hang[h]![oi]!, chu) : [];
      }),
    );
  }
  return ra;
}

/**
 * Tên phông NGUỒN khai → họ chữ CÓ THẬT trong kho, hoặc `""` khi không nhận
 * ra (chỗ gọi khi đó không đặt `font-family` và chữ giữ phông của trang).
 *
 * Ánh xạ theo HẠNG chữ (có chân / không chân / đều nét), không theo tên: kho
 * này tự host đúng bốn họ (`styles.css`) và không có họ nào trong số đó tên
 * là "Times New Roman". Dựng một stack `"Times New Roman", serif` thay vào
 * sẽ cho ra một kết quả KHÁC NHAU trên từng máy — máy có Times thì hiện
 * Times, máy không có thì rơi về `serif` của hệ điều hành — tức màn hình
 * không còn là thứ `.docx`/PDF phải khớp nữa. `.docx` mới là nơi giữ nguyên
 * tên nguồn (`para`/`bangThanhTable`), vì ở đó Word có chính phông ấy.
 */
export function phongTrenManHinh(phong: string): string {
  const t = phong.toLowerCase();
  if (/mono|courier|consolas|menlo|monaco/.test(t))
    return '"JetBrains Mono", ui-monospace, monospace';
  if (/arial|helvetica|calibri|tahoma|verdana|segoe|roboto|gothic|sans|\.vnarial/.test(t))
    return '"Be Vietnam Pro", system-ui, sans-serif';
  if (/times|georgia|cambria|garamond|palatino|book antiqua|minion|serif|\.vntime|vni/.test(t))
    return '"Source Serif 4", Georgia, serif';
  return "";
}

function nhipHopLe(nhip: unknown, hang: string[][]): number[][] {
  if (!Array.isArray(nhip) || nhip.length !== hang.length) return [];
  const ra: number[][] = [];
  for (let h = 0; h < hang.length; h++) {
    const hangNhip = nhip[h];
    if (!Array.isArray(hangNhip) || hangNhip.length !== hang[h]!.length) return [];
    const so = hangNhip.map((v) => Number(v));
    if (!so.every((v) => Number.isInteger(v) && v > 0)) return [];
    ra.push(so);
  }
  return ra;
}

/**
 * MỘT khối thô (từ `khoi` mới, Phase 8) → 0, 1, hay 2 `KhoiMuc` hợp lệ, ĐÚNG
 * thứ tự văn xuôi rồi bảng.
 *
 * Trả MẢNG, không một giá trị: rule 15 XIN mô hình để mỗi khối MỘT trong hai
 * (`noi_dung` HOẶC `bang`), nhưng schema strict không ép được điều đó — một
 * khối vẫn có thể tới đây với CẢ HAI khác rỗng. Review round 1 [IMPORTANT]:
 * bản trước của hàm này ưu tiên `bang` (bỏ `noi_dung`), trong khi
 * `dung_ban_thao_tong_quat._khoi_thanh_van_ban` phía máy chủ lại ưu tiên
 * NGƯỢC LẠI — chứng tỏ luật "một khối một loại" chưa từng được ép, chỉ được
 * TIN, và hai phía đọc cùng một dữ liệu ra hai kết quả khác nhau. Trả CẢ HAI
 * làm hai khối riêng (văn xuôi trước) xoá luôn nhu cầu chọn ưu tiên — đúng
 * cách Phase 7 R1 fix round 1 đã sửa lỗi này một lần ở cấp MỤC.
 */
function khoiMotHopLe(k: unknown): KhoiMuc[] {
  if (typeof k !== "object" || k === null) return [];
  const o = k as {
    noi_dung?: unknown;
    bang?: unknown;
    can_le?: unknown;
    nhip?: unknown;
    ti_le?: unknown;
    vien?: unknown;
    vien_o?: unknown;
    cao?: unknown;
    cao_luat?: unknown;
    can_le_o?: unknown;
    chu?: unknown;
    chu_o?: unknown;
    gian_cach?: unknown;
  };
  const noiDung = typeof o.noi_dung === "string" ? o.noi_dung : "";
  const bang = bangHopLe(o.bang);
  const ra: KhoiMuc[] = [];
  if (noiDung !== "")
    ra.push({
      kind: "vanXuoi",
      noiDung,
      canhLe: canLeHopLe(o.can_le),
      // `chu` VẮNG MẶT ở một khối không có định dạng nào tra được (máy chủ
      // chỉ thêm khoá này khi có) và ở mọi clause lưu TRƯỚC trường này —
      // `chuHopLe` trả `[]` cho cả hai, đúng hành vi trước bản vá.
      chu: chuHopLe(o.chu, noiDung),
      // `gian_cach` VẮNG MẶT ở khối không tra được nhịp nguồn (máy chủ chỉ
      // thêm khoá này khi có) và ở mọi clause lưu TRƯỚC trường này — `null`
      // cho cả hai, đúng hành vi trước bản vá.
      gianCach: gianCachHopLe(o.gian_cach, noiDung),
    });
  if (bang)
    ra.push({
      kind: "bang",
      hang: bang,
      nhip: nhipHopLe(o.nhip, bang),
      tiLe: tiLeHopLe(o.ti_le),
      vien: vienHopLe(o.vien),
      // `vien_o`/`cao_luat` VẮNG MẶT ở bảng không có chi tiết theo cạnh (máy
      // chủ chỉ thêm khoá khi có), ở bảng mô hình TỰ GÕ, và ở mọi clause lưu
      // TRƯỚC hai trường này — `[]` cho cả ba, đúng hành vi trước bản vá.
      vienO: vienOHopLe(o.vien_o, bang),
      cao: caoHopLe(o.cao, bang),
      caoLuat: caoLuatHopLe(o.cao_luat, bang),
      canLeO: canLeOHopLe(o.can_le_o, bang),
      // `chu_o` VẮNG MẶT ở một bảng không ô nào có định dạng (máy chủ chỉ
      // thêm khoá này khi có), ở bảng mô hình TỰ GÕ, và ở mọi clause lưu
      // TRƯỚC trường này — `chuOHopLe` trả `[]` cho cả ba, đúng hành vi
      // trước bản vá.
      chuO: chuOHopLe(o.chu_o, bang),
    });
  return ra;
}

/**
 * `clauses[i]` → `KhoiMuc[]` theo ĐÚNG thứ tự — chỗ DUY NHẤT phải biết cả BA
 * hình dạng `clauses` từng có (Phase 8 `khoi`; Phase 7 `noi_dung`+`bang` rời;
 * trước đó chỉ `noi_dung`, hoặc không có clause nào cho mục này). Mọi nơi
 * khác (`XemTruocA4`, `docNoiDungTuDOM`) chỉ đọc `Muc.khoi` đã quy về một
 * hình dạng, không phải tự phân biệt phiên bản dữ liệu.
 */
function khoiTuClause(c: ClauseTho | undefined): KhoiMuc[] {
  if (Array.isArray(c?.khoi)) {
    return c.khoi.flatMap(khoiMotHopLe);
  }
  // Phase 7 trở về trước: câu dẫn (nếu có) RỒI bảng (nếu có) — đúng thứ tự
  // `XemTruocA4` từng render (fix round 1, Phase 7) trước khi có `khoi`. Chưa
  // từng có `can_le` ở hình dạng này — về `trai` (Phase 9 U5 không đọc ngược
  // lại được căn lề một clause đã lưu trước khi trường này tồn tại).
  const bang = bangHopLe(c?.bang);
  const noiDung = c?.noi_dung ?? (bang ? "" : "[…]");
  const ra: KhoiMuc[] = [];
  if (noiDung !== "")
    ra.push({ kind: "vanXuoi", noiDung, canhLe: "trai", chu: [], gianCach: null });
  // Chưa từng có `nhip`/`ti_le` ở hình dạng CŨ này (Phase 7 trở về trước) —
  // `coSpanHang` suy đoán cột như trước Phase 11, không phải một cải thiện
  // ngầm cho dữ liệu đã lưu trước khi hai trường này tồn tại.
  if (bang)
    ra.push({
      kind: "bang",
      hang: bang,
      nhip: [],
      tiLe: [],
      vien: true,
      vienO: [],
      cao: [],
      caoLuat: [],
      canLeO: [],
      chuO: [],
    });
  return ra;
}

/**
 * Ghép `clauses` (nội dung LLM sinh, từ `draft_generate`) vào khung `cau_truc.muc` (thứ
 * tự và căn cứ, từ chính `checklist_*.yaml`) thành mảng `Muc[]` cho `XemTruocA4`.
 *
 * Khung quyết định thứ tự mục và `canCu`; `clauses` chỉ góp `noiDung`. Mục nào khung có
 * mà `clauses` chưa sinh (model bỏ sót, hoặc đang chờ) thì hiện "[…]" — không suy đoán
 * nội dung để lấp chỗ trống.
 */
/**
 * `muc` → các TỜ A4, mỗi tờ một mảng mục theo đúng thứ tự văn bản.
 *
 * Hàm THUẦN, không đo DOM: đây là nửa mà tài liệu NGUỒN trả lời được — cắt ở
 * chính chỗ `Muc.trang` tăng, tức chỗ tệp KHAI một ngắt (`w:br w:type="page"`
 * hoặc ngắt phân đoạn). Nửa còn lại — nội dung dài quá một tờ — chỉ đo được
 * sau khi trình duyệt dựng xong, và đi vào đây qua `catThem`: chỉ số những mục
 * phải MỞ một tờ mới. Tách hai nửa vì chỉ nửa đầu kiểm được mà không cần trình
 * duyệt, và nửa đầu là nửa có một câu trả lời ĐÚNG duy nhất.
 *
 * Chỉ TIẾN, không lùi (`Math.max`): mô hình có thể đảo thứ tự mục, và một
 * trang lùi lại sẽ cắt ra một tờ mới ở chỗ nguồn không hề ngắt.
 *
 * `muc` rỗng vẫn cho MỘT tờ — khung xem trước của một bản thảo chưa có mục nào
 * vẫn là một tờ giấy trắng, đúng hành vi trước bản vá này.
 */
export function chiaTrang<T extends { trang: number }>(
  muc: readonly T[],
  catThem: readonly number[] = [],
): T[][] {
  if (muc.length === 0) return [[]];
  const cat = new Set(catThem);
  const to: T[][] = [[]];
  let trang = muc[0]!.trang;
  muc.forEach((m, i) => {
    if (i > 0 && (m.trang > trang || cat.has(i))) to.push([]);
    trang = Math.max(trang, m.trang);
    to[to.length - 1]!.push(m);
  });
  return to;
}

export function mucTuBanThao(banThao: BanThao, cauTruc: CauTruc | null): Muc[] {
  const clauses = banThao.clauses as ClauseTho[];
  const theoKey = new Map<string, ClauseTho>();
  for (const c of clauses) if (c.key) theoKey.set(c.key, c);

  const khung = cauTruc?.muc ?? [];
  if (khung.length === 0) {
    // Chưa có `cau_truc` (chưa tải xong, hoặc loại văn bản chưa có checklist) — dựng
    // tạm theo đúng thứ tự `clauses`, không có `canCu` vì khung mới là nguồn của nó.
    return clauses.map((c, i) => ({
      stt: i + 1,
      key: c.key ?? `m${i + 1}`,
      ten: c.ten ?? c.key ?? `Mục ${i + 1}`,
      tenThat: tenThatHopLe(c.ten_that),
      noiDung: c.noi_dung ?? "[…]",
      bang: bangHopLe(c.bang),
      khoi: khoiTuClause(c),
      vung: vungHopLe(c.vung),
      trang: trangHopLe(c.trang),
      canCu: null,
    }));
  }
  return khung.map((m) => {
    const c = theoKey.get(m.key);
    return {
      stt: m.stt,
      key: m.key,
      ten: m.ten,
      // Tên mục checklist đến từ chính `checklist_*.yaml`, không phải mô
      // hình bịa — luôn `true`, bất kể `c.ten_that` (trường đó chỉ có nghĩa
      // ở nhánh `tong_quat` phía trên).
      tenThat: true,
      noiDung: c?.noi_dung ?? "[…]",
      bang: bangHopLe(c?.bang),
      khoi: khoiTuClause(c),
      vung: vungHopLe(c?.vung),
      trang: trangHopLe(c?.trang),
      canCu: m.can_cu || null,
    };
  });
}

/**
 * `c.le_trang` thô (`[["top", 1134], …]`, twip) → lề trang, `null` khi vắng
 * hoặc thiếu một trong BỐN lề thân trang.
 *
 * Fail-closed cả bộ, không lấp `0` cho lề thiếu: `0` nghĩa là "sát mép giấy",
 * một câu khẳng định — còn thiếu nghĩa là "không biết", và ở đó giữ lề mặc
 * định của khung xem trước mới là câu trả lời trung thực. `header`/`footer`
 * thì `0` được: OOXML coi chúng là 0 khi vắng, và chúng không đẩy chữ thân bài.
 */
function leTrangHopLe(tho: unknown): LeTrang | null {
  if (!Array.isArray(tho)) return null;
  const so = new Map<string, number>();
  for (const x of tho) {
    if (!Array.isArray(x) || x.length !== 2 || typeof x[0] !== "string") continue;
    const n = Number(x[1]);
    if (Number.isFinite(n)) so.set(x[0], n);
  }
  const [tren, phai, duoi, trai] = ["top", "right", "bottom", "left"].map((k) => so.get(k));
  if (tren === undefined || phai === undefined || duoi === undefined || trai === undefined)
    return null;
  return {
    tren,
    phai,
    duoi,
    trai,
    dauTrang: so.get("header") ?? 0,
    chanTrang: so.get("footer") ?? 0,
  };
}

/**
 * Lề trang NGUỒN của bản thảo — `null` khi tài liệu gốc không khai `w:pgMar`
 * (và với mọi bản thảo lưu TRƯỚC trường này).
 *
 * Đọc ở clause ĐẦU TIÊN có khoá: lề là sự thật của cả TÀI LIỆU, backend chép
 * nó lên mọi mục vì `clauses` là kênh duy nhất ra giao diện (xem
 * `dung_ban_thao_tong_quat.clauses_tu`). Hàm riêng chứ không thêm một trường
 * vào `Muc`: `Muc` là MỘT mục, và một sự thật cấp tài liệu nằm trên nó sẽ lặp
 * lại y hệt ở mọi phần tử rồi có ngày lệch nhau.
 */
export function leTrangTuBanThao(banThao: BanThao): LeTrang | null {
  for (const c of banThao.clauses as ClauseTho[]) {
    const le = leTrangHopLe(c.le_trang);
    if (le) return le;
  }
  return null;
}

/**
 * `c.anh` thô → danh sách ảnh nguồn, bỏ RIÊNG phần tử sai hình dạng.
 *
 * Fail-closed từng phần tử chứ không cả bộ (khác `leTrangHopLe`): bốn lề của
 * một trang là MỘT sự thật — nửa theo nguồn nửa theo mặc định là một trang
 * không tồn tại ở đâu cả — còn hai tấm ảnh là HAI sự thật độc lập, và mất
 * con dấu không phải lý do để mất luôn logo.
 *
 * `url` phải là đường dẫn TƯƠNG ĐỐI bắt đầu bằng `/tai-lieu/`: đây là chuỗi
 * đi thẳng vào `src` của một `<img>`, nên một `javascript:` hay một tên miền
 * lạ lọt vào `clauses` không được có đường nào ra tới đó.
 */
function anhHopLe(tho: unknown): AnhNguon[] {
  if (!Array.isArray(tho)) return [];
  const ra: AnhNguon[] = [];
  for (const x of tho) {
    if (typeof x !== "object" || x === null) continue;
    const a = x as Record<string, unknown>;
    const url = typeof a["url"] === "string" ? (a["url"] as string) : "";
    if (!/^\/tai-lieu\/[^/]+\/anh\/[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,8}$/.test(url)) continue;
    const so = (v: unknown) => (Number.isFinite(Number(v)) ? Math.max(0, Number(v)) : 0);
    ra.push({
      url,
      rong: so(a["rong"]),
      cao: so(a["cao"]),
      vung: vungHopLe(a["vung"]),
      thuTu: so(a["thu_tu"]),
    });
  }
  // Theo VÙNG rồi theo thứ tự nguồn: ba nơi vẽ đặt logo đầu trang lên trước
  // thân bài và con dấu chân trang xuống sau, và trong mỗi vùng giữ đúng thứ
  // tự chúng đứng trong tệp.
  const hang = { dau_trang: 0, than: 1, chan_trang: 2 };
  return ra.sort((x, y) => hang[x.vung] - hang[y.vung] || x.thuTu - y.thuTu);
}

/**
 * Ảnh NGUỒN của bản thảo — rỗng khi tài liệu gốc không có ảnh nào (và với mọi
 * bản thảo lưu TRƯỚC trường này).
 *
 * Đọc ở clause ĐẦU TIÊN có khoá, đúng khuôn `leTrangTuBanThao`: ảnh là sự thật
 * của cả TÀI LIỆU và backend chép nó lên mọi mục vì `clauses` là kênh duy nhất
 * ra giao diện. Đọc gộp mọi mục sẽ vẽ cùng một logo N lần.
 */
export function anhTuBanThao(banThao: BanThao): AnhNguon[] {
  for (const c of banThao.clauses as ClauseTho[]) {
    const anh = anhHopLe(c.anh);
    if (anh.length > 0) return anh;
  }
  return [];
}

/**
 * Tiêu đề THẬT của bản thảo — dòng H1 đầu tiên trong `document` (Markdown),
 * đúng cách `ban_thao._render_markdown` dựng từ `tieu_de` mô hình soạn (Phase
 * 7 R4). `BanThao.ten` KHÔNG mang tiêu đề này: nó trả lời "bản thảo này THUỘC
 * LOẠI gì" ("Bản thảo tổng quát"), một câu hỏi khác — trộn hai trường đó là
 * đúng lỗi đã sửa ở `dung_ban_thao_tong_quat.py`.
 */
export function tieuDeTuBanThao(document: string): string | null {
  const dong = document.split("\n")[0] ?? "";
  const m = /^#\s+(.+)$/.exec(dong.trim());
  return m?.[1]?.trim() ?? null;
}

const BO_QUA = new Set(["SCRIPT", "STYLE"]);

/**
 * Phần tử KHÔNG được vào tệp tải về: thẻ kỹ thuật, và mọi thứ nằm trong một
 * khối đánh dấu `data-khong-xuat`.
 *
 * Cần cái thứ hai vì khung xem trước có những dòng chỉ dành cho MÀN HÌNH —
 * dòng `Căn cứ:` bật/tắt bằng công tắc "Hiển thị căn cứ" là một `<p>` như mọi
 * đoạn khác, nên nếu không đánh dấu thì một công tắc xem trước lại đổi nội
 * dung văn bản pháp lý người dùng tải về.
 */
export function boQuaKhiXuat(el: { tagName: string; closest(chon: string): unknown }): boolean {
  return BO_QUA.has(el.tagName) || el.closest("[data-khong-xuat]") !== null;
}

/**
 * `CanLe` → hướng căn lề dùng chung cho `.docx` (`xuatWord.para`) và PDF
 * (`noiDungThanhPDF.veDong`) — MỘT chỗ quyết định, hai nơi dùng, thay vì hai
 * ternary có thể lệch nhau (Phase 11 R2/R8).
 *
 * `trai` KHÔNG phải "hãy căn đều" — nó là giá trị khi tài liệu nguồn không
 * xác định được căn lề (vắng `w:jc`, hoặc chính là `both`, xem `_JC_RA_CAN_LE`
 * phía máy chủ). Ánh xạ nó sang "justify" từng khiến một bản `.docx` KLAW
 * dựng thật ra gần như toàn bộ đoạn văn `w:jc="both"` dù nguồn phần lớn
 * không khai `jc` — đo trực tiếp trên tệp tải về, không phải suy đoán.
 */
export function canhLeThanhHuong(canhLe: CanLe): "left" | "center" | "right" | "justify" {
  return canhLe === "giua"
    ? "center"
    : canhLe === "phai"
      ? "right"
      : canhLe === "deu"
        ? "justify"
        : "left";
}

function chuanHoa(s: string) {
  return s.replace(/\s+/g, " ").trim();
}

/** Căn lề THẬT của một thẻ, đọc từ `text-align` đã tính (Phase 9 U5) — cùng
 *  nguồn sự thật XemTruocA4 dùng để hiển thị, không suy đoán lại từ dữ liệu. */
function canhLeTuStyle(el: HTMLElement): CanLe {
  const ta = getComputedStyle(el).textAlign;
  if (ta === "center") return "giua";
  if (ta === "right" || ta === "end") return "phai";
  // `justify-all` cũng là căn đều, chỉ khác ở DÒNG CUỐI — phía tệp không có ô
  // nào để chở sự khác biệt ấy, nên cả hai về `deu`.
  if (ta === "justify" || ta === "justify-all") return "deu";
  return "trai";
}

/**
 * Đọc MỘT bảng đã render thành hàng×ô, nguyên văn từng ô (đã chuẩn hoá khoảng
 * trắng) — hàng đầu tiên là hàng tiêu đề, đúng quy ước `bang` phía máy chủ
 * (`hieu_tai_lieu.schema_hieu`, Phase 7 R1); không cần phân biệt `<th>`/`<td>`.
 *
 * Cũng đọc lại `nhip` (thuộc tính `colSpan` đã render, Phase 11 R6), `tiLe`
 * (`data-ti-le` trên mỗi `<col>` của `<colgroup>`, Phase 11 R1), `vien`
 * (`data-vien` trên chính `<table>`), `cao` (`data-cao` trên mỗi `<tr>`),
 * `canLeO` (`data-can-le` trên mỗi ô) và `chuO` (các `<span data-chu>` bên
 * TRONG mỗi ô, đọc bằng chính `docDoanChu` mà một dòng văn xuôi dùng) — CÙNG
 * một bảng đã vẽ trên màn hình,
 * không phải hai nguồn tách rời có thể lệch nhau: `XemTruocA4` đặt những
 * thuộc tính đó khi vẽ, hàm này đọc lại đúng những gì đã vẽ. Đó là điều giữ
 * cho tệp tải về khớp màn hình: một khối ký không viền trên trang không được
 * mọc lại viền trong `.docx`.
 *
 * Chữ ký hàm chỉ đòi `querySelectorAll`/`textContent`/`getAttribute` — KHÔNG
 * `getComputedStyle` như `docDong` — nên gọi được với một đối tượng giả tối
 * thiểu, không cần DOM thật (kiểm bằng `kiem-xuat-tep.ts`, không có `jsdom`
 * trong repo này).
 */
export function docBangTuPhanTu(bang: {
  getAttribute(ten: string): string | null;
  querySelectorAll(sel: string): ArrayLike<{
    getAttribute(ten: string): string | null;
    querySelectorAll(sel: string): ArrayLike<{
      textContent: string | null;
      colSpan?: number;
      getAttribute(ten: string): string | null;
      querySelectorAll(sel: string): ArrayLike<{
        textContent: string | null;
        getAttribute(ten: string): string | null;
      }>;
    }>;
  }>;
}): BangThat {
  const hang: string[][] = [];
  const nhip: number[][] = [];
  const cao: number[] = [];
  const caoLuat: string[] = [];
  const canLeO: CanLe[][] = [];
  const chuO: DoanChu[][][] = [];
  const vienO: string[][] = [];
  for (const tr of Array.from(bang.querySelectorAll("tr"))) {
    const o = Array.from(tr.querySelectorAll("th, td"));
    hang.push(o.map((c) => chuanHoa(c.textContent ?? "")));
    nhip.push(o.map((c) => (typeof c.colSpan === "number" && c.colSpan > 0 ? c.colSpan : 1)));
    canLeO.push(o.map((c) => canLeHopLe(c.getAttribute("data-can-le"))));
    vienO.push(o.map((c) => c.getAttribute(THUOC_TINH_BANG.vienO) ?? ""));
    caoLuat.push(tr.getAttribute(THUOC_TINH_BANG.caoLuat) ?? "");
    // `docDoanChu` trả `[]` cho một ô không có `<span data-chu>` nào — ô
    // đồng nhất, đúng đường cũ.
    chuO.push(o.map(docDoanChu));
    const twip = Number(tr.getAttribute("data-cao"));
    cao.push(Number.isFinite(twip) && twip > 0 ? twip : 0);
  }
  const tiLe = Array.from(bang.querySelectorAll("col"))
    .map((c) => Number(c.getAttribute("data-ti-le")))
    .filter((v) => Number.isFinite(v) && v > 0);
  // `data-vien="khong"` là dấu DUY NHẤT của bảng không viền; mọi bảng khác
  // (kể cả bảng vẽ trước bản vá này, không có thuộc tính nào) vẫn có viền.
  return {
    hang,
    nhip,
    tiLe,
    vien: bang.getAttribute("data-vien") !== "khong",
    // Fail-closed CẢ BẢNG, cùng luật `vienOHopLe` ở cửa vào: một ô thiếu
    // `data-vien-o` (hoặc mang chuỗi lệch khuôn) làm cả bảng về `[]`, tức
    // `.docx`/PDF kẻ nét đều như màn hình cũng đang kẻ.
    vienO: vienO.every((d) => d.every((o) => O_VIEN_HOP_LE.test(o))) ? vienO : [],
    cao,
    caoLuat,
    canLeO,
    chuO,
  };
}

/**
 * Tên thuộc tính DOM chở từng sự thật định dạng — MỘT bảng, HAI phía dùng:
 * `XemTruocA4.veChuVaoThe` ghi, `docDoanChu` ngay dưới đây đọc. Gõ thẳng tên
 * ở hai nơi là cách chắc chắn nhất để màn hình và tệp tải về nói khác nhau
 * sau một lần đổi tên — đúng chế độ hỏng mà `data-can-le`/`data-cao` đã tránh
 * bằng cách chỉ có một chỗ đặt và một chỗ đọc.
 */
export const THUOC_TINH_CHU = {
  moc: "data-chu",
  dam: "data-dam",
  nghieng: "data-nghieng",
  gach: "data-gach",
  co: "data-co",
  phong: "data-phong",
} as const;

/** Tên thuộc tính chở viền TỪNG CẠNH của một ô và luật chiều cao của một hàng
 *  — cùng luật `THUOC_TINH_CHU`: `XemTruocA4` ghi, `docBangTuPhanTu` đọc,
 *  không nơi nào gõ lại tên bằng tay. (`data-vien`/`data-cao`/`data-can-le`/
 *  `data-ti-le` có trước bộ này và vẫn gõ thẳng tên ở hai chỗ — đổi chúng là
 *  một lượt sửa không liên quan tới bản vá này.) */
export const THUOC_TINH_BANG = {
  vienO: "data-vien-o",
  caoLuat: "data-cao-luat",
} as const;

/** Tên thuộc tính chở LỀ TRANG nguồn trên chính thẻ `<article>` của khung A4 —
 *  `XemTruocA4` ghi (và vẽ bằng `padding` cùng con số ấy), `docNoiDungTuDOM`
 *  đọc lại để `.docx`/PDF đặt đúng lề màn hình đang dùng. Twip, không `pt`:
 *  cùng lý lẽ `THUOC_TINH_GIAN_CACH` — đọc ngược `px` đã tính rồi quy lại sẽ
 *  làm tròn hai lần, trong khi `.docx` cần đúng con số nguồn. */
export const THUOC_TINH_LE = {
  tren: "data-le-tren",
  phai: "data-le-phai",
  duoi: "data-le-duoi",
  trai: "data-le-trai",
  dauTrang: "data-le-dau-trang",
  chanTrang: "data-le-chan-trang",
} as const;

/** Tên thuộc tính chở MỘT ảnh nguồn trên chính thẻ `<img>` — cùng luật
 *  `THUOC_TINH_LE`: `XemTruocA4` ghi (và vẽ bằng `width`/`height` cùng con số
 *  ấy), `docNoiDungTuDOM` đọc lại để `.docx`/PDF đặt ĐÚNG cỡ màn hình đang
 *  dùng. EMU, không `pt`: `.docx` ghi lại chính đơn vị nguồn, và đọc ngược
 *  `px` đã tính rồi quy lại là làm tròn hai lần. */
export const THUOC_TINH_ANH = {
  moc: "data-anh",
  rong: "data-anh-rong",
  cao: "data-anh-cao",
} as const;

/** Tên thuộc tính chở MỘT mốc tab — cùng luật `THUOC_TINH_CHU`: `XemTruocA4`
 *  ghi, `docDoanChu` đọc, không nơi nào gõ lại tên bằng tay. `moc` nằm TRÊN
 *  cùng `<span>` với `data-chu`, nên một đoạn tab vẫn đi qua đúng bộ chọn cũ
 *  và `docDoanChu` không phải duyệt DOM hai lượt. */
export const THUOC_TINH_TAB = {
  moc: "data-tab",
  val: "data-tab-val",
  pos: "data-tab-pos",
  leader: "data-tab-leader",
} as const;

/** Tên thuộc tính chở nhịp của một ĐOẠN (`w:spacing`/`w:ind`) trên chính thẻ
 *  `<p>` — cùng khuôn `data-cao`/`data-can-le` của bảng: màn hình vẽ và ghi,
 *  `docDong` đọc lại đúng con số NGUỒN (twip) chứ không đọc `px` đã tính. */
export const THUOC_TINH_GIAN_CACH = {
  truoc: "data-truoc",
  sau: "data-sau",
  dong: "data-dong",
  luatDong: "data-luat-dong",
  trai: "data-thut-trai",
  phai: "data-thut-phai",
  dauDong: "data-dau-dong",
  treo: "data-treo",
} as const;

/** 1 twip = 1/20 pt — cùng phép quy đổi `caoTrenTrang` (`w:trHeight`) dùng cho
 *  màn hình: trang A4 xem trước rộng cố định và `thuPhong` chỉ phóng CỠ CHỮ,
 *  nên một khoảng cách đo bằng `em` sẽ trôi theo mức phóng còn `pt` thì không. */
export const PT_MOI_TWIP = 1 / 20;

/**
 * Đọc lại nhịp đoạn từ `data-*` của một thẻ — `null` khi thẻ không mang thuộc
 * tính nào (đoạn KLAW tự soạn, hoặc bản thảo lưu trước bản vá này).
 *
 * Một con số đọc không ra làm CẢ nhóm về `null`, cùng luật fail-closed
 * `gianCachHopLe` ở cửa vào: nửa bộ nhịp đặt sai chỗ tệ hơn nhịp mặc định.
 */
function gianCachTuThe(el: { getAttribute(ten: string): string | null }): GianCachDoan | null {
  const so = (ten: string): number | null => {
    const v = el.getAttribute(ten);
    if (v === null) return 0;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const g = {
    truoc: so(THUOC_TINH_GIAN_CACH.truoc),
    sau: so(THUOC_TINH_GIAN_CACH.sau),
    dong: so(THUOC_TINH_GIAN_CACH.dong),
    trai: so(THUOC_TINH_GIAN_CACH.trai),
    phai: so(THUOC_TINH_GIAN_CACH.phai),
    dauDong: so(THUOC_TINH_GIAN_CACH.dauDong),
    treo: so(THUOC_TINH_GIAN_CACH.treo),
  };
  if (Object.values(g).some((v) => v === null)) return null;
  const co = Object.values(g).some((v) => v !== 0);
  return co
    ? {
        ...(g as Record<keyof typeof g, number>),
        luatDong: el.getAttribute(THUOC_TINH_GIAN_CACH.luatDong) ?? "",
      }
    : null;
}

/**
 * `noiDung` + các khoảng `KhoangChu` → dãy đoạn PHỦ KÍN chuỗi, theo thứ tự.
 *
 * Chỗ duy nhất biết cách cắt: `XemTruocA4` gọi để vẽ `<span>`, và vì đầu ra
 * đã đúng kiểu `DoanChu` mà `docDoanChu` trả về, hai chiều đi–về so sánh
 * thẳng được với nhau (xem `kiem-dinh-dang-chu.ts`).
 *
 * Kể cả đoạn KHÔNG định dạng gì cũng là một đoạn: nhờ vậy nối `text` của cả
 * dãy lại là được đúng `noiDung`, không sót ký tự nào giữa hai khoảng.
 */
export function catTheoChu(noiDung: string, chu: KhoangChu[], tab: KhoangTab[] = []): DoanChu[] {
  const ra: DoanChu[] = [];
  const moc = [...tab].sort((a, b) => a.o - b.o);
  let iMoc = 0;
  const themChu = (text: string, k: KhoangChu | null) => {
    if (text === "") return;
    ra.push({
      text,
      inDam: k?.dam === true,
      inNghieng: k?.nghieng === true,
      gachChan: k?.gach === true,
      coChu: k && k.co > 0 ? k.co : 0,
      phong: k?.phong ?? "",
      tab: null,
    });
  };
  /** Cắt `[dau, cuoi)` và chèn mọi mốc tab rơi vào bên trong — tab nằm GIỮA
   *  chữ, nên nó cắt một khoảng định dạng làm đôi thay vì kết thúc nó. */
  const them = (dau: number, cuoi: number, k: KhoangChu | null) => {
    let i = dau;
    while (iMoc < moc.length && moc[iMoc]!.o <= cuoi) {
      const m = moc[iMoc]!;
      const o = Math.max(i, m.o);
      themChu(noiDung.slice(i, o), k);
      ra.push({
        text: "",
        inDam: false,
        inNghieng: false,
        gachChan: false,
        coChu: 0,
        phong: "",
        tab: { val: m.val, pos: m.pos, leader: m.leader },
      });
      i = o;
      iMoc += 1;
    }
    themChu(noiDung.slice(i, cuoi), k);
  };
  let i = 0;
  for (const k of chu) {
    them(i, k.dau, null);
    them(k.dau, k.cuoi, k);
    i = k.cuoi;
  }
  them(i, noiDung.length, null);
  return ra;
}

/**
 * Đọc lại các ĐOẠN chữ của một dòng đã vẽ — `[]` khi dòng không có đoạn nào
 * (dòng đồng nhất, hành vi trước bản vá 2026-09-18).
 *
 * Đọc `data-*` chứ không `getComputedStyle` như `docDong`: cùng khuôn
 * `docBangTuPhanTu`, nên kiểm được từ Node với một đối tượng giả tối thiểu
 * (repo này không có `jsdom`). Cũng chính xác hơn — `font-weight` đã tính
 * của một thẻ nằm trong tiêu đề in đậm sẽ nói "đậm" cho cả những đoạn nguồn
 * khai là thường.
 *
 * `XemTruocA4` vẽ các đoạn PHỦ KÍN dòng (kể cả đoạn không định dạng gì), nên
 * nối `textContent` của chúng lại là được đúng chữ của dòng — không cần đi
 * qua `childNodes` để nhặt chữ nằm ngoài đoạn nào.
 */
export function docDoanChu(el: {
  querySelectorAll(sel: string): ArrayLike<{
    textContent: string | null;
    getAttribute(ten: string): string | null;
  }>;
}): DoanChu[] {
  const doan = Array.from(el.querySelectorAll(`span[${THUOC_TINH_CHU.moc}]`));
  if (doan.length === 0) return [];
  const ra: DoanChu[] = doan.map((s) => {
    const co = Number(s.getAttribute(THUOC_TINH_CHU.co));
    const pos = Number(s.getAttribute(THUOC_TINH_TAB.pos));
    return {
      // Gộp khoảng trắng nhưng KHÔNG cắt hai đầu: `chuanHoa` của cả dòng cắt
      // đúng một lần ở hai mép, còn cắt từng đoạn sẽ nuốt dấu cách giữa hai
      // đoạn — "Họ và tên:" dính liền vào "Nguyễn Văn A".
      text: (s.textContent ?? "").replace(/\s+/g, " "),
      inDam: s.getAttribute(THUOC_TINH_CHU.dam) === "1",
      inNghieng: s.getAttribute(THUOC_TINH_CHU.nghieng) === "1",
      gachChan: s.getAttribute(THUOC_TINH_CHU.gach) === "1",
      coChu: Number.isFinite(co) && co > 0 ? co : 0,
      phong: s.getAttribute(THUOC_TINH_CHU.phong) ?? "",
      // Một đoạn TAB mang `data-tab` và không mang chữ. `pos` không đọc ra
      // số thì đoạn ấy về chữ thường rỗng và bị lọc đi ngay dưới đây — không
      // nhảy tới một toạ độ không biết.
      tab:
        s.getAttribute(THUOC_TINH_TAB.moc) !== null && Number.isFinite(pos) && pos > 0
          ? {
              val: s.getAttribute(THUOC_TINH_TAB.val) ?? "left",
              pos,
              leader: s.getAttribute(THUOC_TINH_TAB.leader) ?? "",
            }
          : null,
    };
  });
  if (ra.length > 0) {
    ra[0]!.text = ra[0]!.text.replace(/^ /, "");
    ra[ra.length - 1]!.text = ra[ra.length - 1]!.text.replace(/ $/, "");
  }
  // Đoạn TAB giữ lại dù rỗng chữ: chính nó LÀ dữ kiện, không phải một đoạn
  // chữ trống rơi ra từ phép cắt.
  return ra.filter((d) => d.text !== "" || d.tab !== null);
}

/** Đọc một thẻ thành dòng có định dạng, lấy đậm/nghiêng từ chính CSS đang áp. */
function docDong(el: HTMLElement): DongVanBan {
  const text = chuanHoa(el.textContent ?? "");
  const cs = getComputedStyle(el);
  const laDieu = el.classList.contains("dieu-head");
  const hoa = cs.textTransform === "uppercase";
  const doan = docDoanChu(el);
  return {
    text: hoa ? text.toLocaleUpperCase("vi-VN") : text,
    kieu:
      el.tagName === "H1" ? "tieuDe" : laDieu ? "dieu" : /^Số:/.test(text) ? "soHieu" : "thuong",
    canhLe: canhLeTuStyle(el),
    inDam: Number(cs.fontWeight) >= 600 || laDieu,
    inNghieng: cs.fontStyle === "italic",
    thutLe: Math.round(parseFloat(cs.marginLeft || "0")),
    // `text-transform` là chuyện của CẢ thẻ, nên áp cho từng đoạn y hệt —
    // nếu không, một dòng viết hoa bằng CSS sẽ ra tệp bằng chữ thường ngay
    // khi nó có định dạng theo đoạn.
    doan: hoa ? doan.map((d) => ({ ...d, text: d.text.toLocaleUpperCase("vi-VN") })) : doan,
    gianCach: gianCachTuThe(el),
  };
}

/** Đọc nội dung hiển thị của khung A4 thành danh sách dòng có định dạng. */
export function docNoiDungTuDOM(sheet: HTMLElement): NoiDungXuat {
  const khoi: KhoiVanBan[] = [];
  const oKy: DongVanBan[][] = [];

  /**
   * Khối ký chỉ tách ra thành BẢNG khi nó thật sự có hai cột cạnh nhau.
   *
   * Bảng ấy được ghép vào CUỐI tệp, nên tách một khối ký MỘT cột ra là đẩy nó
   * xuống dưới cùng: công văn có chữ ký ở Thành phần 7 trên màn hình lại ký sau
   * Thành phần 9 trong tệp `.docx` tải về. Một cột thì để nó chảy theo đúng thứ
   * tự văn bản như mọi đoạn khác.
   */
  const khoiHaiCot = sheet.querySelector<HTMLElement>('[data-xuat="ky"]');
  const khoiKy = khoiHaiCot && khoiHaiCot.children.length >= 2 ? khoiHaiCot : null;
  if (khoiKy) {
    for (const cot of Array.from(khoiKy.children) as HTMLElement[]) {
      const dongCot = Array.from(cot.querySelectorAll("p"))
        .filter((el) => !boQuaKhiXuat(el))
        .map(docDong)
        .filter((d) => d.text !== "");
      if (dongCot.length > 0) oKy.push(dongCot);
    }
  }

  // Một truy vấn CHUNG cho cả ba thẻ giữ đúng THỨ TỰ xuất hiện trong tài liệu
  // (`querySelectorAll` luôn trả theo thứ tự DOM, bất kể nhóm nào trong bộ
  // chọn khớp) — một bảng đứng giữa hai đoạn văn (như bảng đánh giá) phải ở
  // ĐÚNG chỗ đó trong tệp `.docx`, không bị dồn hết xuống cuối như `oKy`.
  const blocks = sheet.querySelectorAll<HTMLElement>(`h1, p, table, img[${THUOC_TINH_ANH.moc}]`);
  for (const el of Array.from(blocks)) {
    if (boQuaKhiXuat(el)) continue;
    if (khoiKy && khoiKy.contains(el)) continue;
    if (el.tagName === "IMG") {
      // Ảnh đọc lại từ chính thẻ đã vẽ, cùng bộ chọn với `h1/p/table` nên nó
      // giữ ĐÚNG chỗ nó đứng trong tài liệu — một logo đầu trang không bị dồn
      // xuống cuối tệp như `oKy`.
      const img = el as HTMLImageElement;
      const so = (ten: string) => Number(el.getAttribute(ten) ?? 0) || 0;
      // Cỡ NGUỒN khai thắng; nguồn không khai (`wp:extent` thiếu, ảnh VML
      // không có `style`) thì lùi về cỡ THẬT của chính ảnh — `naturalWidth`
      // là số trình duyệt đã đo, không phải một con số bịa ra. Cả hai cùng 0
      // nghĩa là ảnh chưa tải được: BỎ, và phần còn lại của tệp vẫn đủ.
      const rong = so(THUOC_TINH_ANH.rong) || img.naturalWidth * EMU_MOI_PX;
      const cao = so(THUOC_TINH_ANH.cao) || img.naturalHeight * EMU_MOI_PX;
      const url = img.getAttribute("src") ?? "";
      if (url && rong > 0 && cao > 0) {
        khoi.push({ kind: "anh", a: { url, rong, cao, vung: "than", thuTu: 0 } });
      }
      continue;
    }
    if (el.tagName === "TABLE") {
      const bang = docBangTuPhanTu(el);
      if (bang.hang.length > 0) khoi.push({ kind: "bang", ...bang });
      continue;
    }
    const d = docDong(el);
    if (d.text === "") continue;
    khoi.push({ kind: "dong", d });
  }

  return { khoi, oKy, leTrang: leTrangTuThe(sheet) };
}

/**
 * Lề trang đã vẽ trên khung A4 → `LeTrang`, `null` khi khung không mang lề
 * nguồn (bản thảo cũ, tài liệu không khai `w:pgMar`, hoặc khung soạn thảo
 * checklist vốn không đi qua `XemTruocA4`).
 *
 * Fail-closed CẢ BỘ, cùng luật `leTrangHopLe` ở cửa vào: thiếu hay hỏng một
 * trong bốn lề thân trang thì `.docx`/PDF giữ lề mặc định cũ của chúng, chứ
 * không ghép một trang nửa theo nguồn nửa theo mặc định.
 */
function leTrangTuThe(sheet: { getAttribute(ten: string): string | null }): LeTrang | null {
  const so = (ten: string): number | null => {
    const v = sheet.getAttribute(ten);
    if (v === null) return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const tren = so(THUOC_TINH_LE.tren);
  const phai = so(THUOC_TINH_LE.phai);
  const duoi = so(THUOC_TINH_LE.duoi);
  const trai = so(THUOC_TINH_LE.trai);
  if (tren === null || phai === null || duoi === null || trai === null) return null;
  return {
    tren,
    phai,
    duoi,
    trai,
    dauTrang: so(THUOC_TINH_LE.dauTrang) ?? 0,
    chanTrang: so(THUOC_TINH_LE.chanTrang) ?? 0,
  };
}

export function tenTepAnToan(ten: string) {
  const slug = ten
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/gi, "d")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${slug || "van-ban"}-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`;
}

function taiBlob(blob: Blob, tenTep: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = tenTep;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/**
 * Số cột mỗi ô của một hàng phải chiếm, khi hàng đó NGẮN hơn hàng tiêu đề
 * (Phase 8 R4 — tài liệu nguồn dùng Ô GỘP, ví dụ hàng "Tổng | 10" chỉ có 2 ô
 * thật trong khi hàng tiêu đề có 4). Quyết định biểu diễn: hàng vẫn lưu ĐÚNG
 * số ô thật (`bang`/`hang` không đệm rỗng, xem `_bang_sach` phía máy chủ);
 * hàm này chỉ quyết định cách VẼ nó, theo MỘT quy ước cố định — ô CUỐI luôn ở
 * CỘT CUỐI của bảng (không bao giờ trôi sang trái, "10" không lẫn sang cột
 * khác), ô ngay TRƯỚC nó gánh phần cột còn thiếu bằng colSpan, các ô còn lại
 * giữ nguyên 1 cột. Đúng cách một nhãn gộp ("Tổng") đứng ngay trước ô giá trị
 * trong một biểu mẫu thật; hàng đủ cột (`soO >= soCotTieuDe`) không đổi gì.
 */
export function coSpanHang(soO: number, soCotTieuDe: number): number[] {
  if (soO <= 0) return [];
  if (soO >= soCotTieuDe) return Array(soO).fill(1) as number[];
  if (soO === 1) return [soCotTieuDe];
  const thieu = soCotTieuDe - soO;
  return [...Array(soO - 2).fill(1), 1 + thieu, 1] as number[];
}

/**
 * Số cột LƯỚI THẬT của một bảng — từ `tiLe` (Phase 11 R1, đúng số cột đã khai
 * `w:tblGrid`) khi bảng có khai lưới nguồn, hàng đầu khi không (bảng mô hình
 * tự soạn, không lưới nào để đọc — giữ nguyên suy đoán cũ theo số ô hàng đầu,
 * R6 đòi giữ nhánh này).
 *
 * Phase 11 fix round 3 (reviewer I5) — TRƯỚC hàm này, ba nơi vẽ bảng tự lấy
 * `hang[0]?.length` làm số cột. Khi hàng đầu chính là hàng có Ô GỘP (một dòng
 * tiêu đề toàn bảng, gộp hết chiều rộng — hình dạng biểu mẫu tiếng Việt bình
 * thường), số ô THẬT của nó nhỏ hơn số cột lưới đã khai, nên
 * `tiLe.length !== soCot` và `tiLeCotVe` rơi về chia đều — R1 tồn tại để
 * chính bảng đó KHÔNG mất tỉ lệ thật. `tiLe.length` luôn đúng khi có khai
 * lưới (đọc thẳng `w:tblGrid`, không phụ thuộc hàng nào), nên ưu tiên nó
 * trước, không suy qua hàng đầu.
 */
export function soCotThat(hang: string[][], tiLe: number[]): number {
  return tiLe.length || (hang[0]?.length ?? 0);
}

/**
 * % mỗi cột lưới đã ĐỌC ĐƯỢC (Phase 11 R1) → tỉ lệ dùng để VẼ, chia đều khi
 * rỗng hoặc sai số cột — MỘT chỗ quyết định fallback, dùng cho cả ba nơi vẽ
 * bảng (`XemTruocA4`, `bangThanhTable`, PDF `chieuCaoHangBang`/`veMotHangBang`).
 */
export function tiLeCotVe(tiLe: number[], soCot: number): number[] {
  if (tiLe.length === soCot && tiLe.every((v) => v > 0)) return tiLe;
  return Array(soCot).fill(100 / soCot) as number[];
}

/**
 * Nhịp (số cột mỗi ô CHIẾM) một hàng sẽ dùng để VẼ — nhịp THẬT (Phase 11 R6,
 * đọc từ `w:gridSpan` qua backend) khi có VÀ khớp đúng số ô của hàng; suy
 * đoán bằng `coSpanHang` khi không (bảng mô hình tự soạn, không có lưới
 * nguồn để đọc) — R6 đòi giữ đúng nhánh này cho ca không khai lưới, không
 * được áp cho bảng CÓ khai lưới.
 */
export function nhipHangVe(
  hang: string[],
  nhipHang: number[] | undefined,
  soCotTieuDe: number,
): number[] {
  if (nhipHang && nhipHang.length === hang.length) return nhipHang;
  return coSpanHang(hang.length, soCotTieuDe);
}

/**
 * Một bảng đã đọc (`docBangTuPhanTu`/`Muc.bang`) → `Table` thật của `docx`.
 * KHÔNG đặc cách bảng nào — cùng một hàm cho MỌI `<table>` đã render, kể cả
 * bảng đánh giá. Hàng ngắn hơn hàng tiêu đề (Phase 8 R4, ô gộp) dùng
 * `columnSpan` qua `nhipHangVe`, cùng quy ước `XemTruocA4` dùng để vẽ trên
 * màn hình — một hàng không "trôi" cột giữa xem trước và tệp tải về. `tiLe`
 * (Phase 11 R1) đặt bề rộng từng cột qua `TableCell.width` — chia đều khi
 * rỗng hoặc sai số cột.
 *
 * `vien` quyết định hai thứ đi CÙNG nhau, vì cả hai đều là "KLAW tự thêm một
 * thứ nguồn không có": nét viền, và cách hàng ĐẦU được tô đậm + tô nền như
 * một hàng tiêu đề. Bảng nguồn không viền là một khối BỐ CỤC (khối ký,
 * letterhead) — ở đó hàng đầu không phải tiêu đề của gì cả, và một nền xám
 * quanh chữ "Giảng viên hướng dẫn" là chữ KLAW bịa thêm vào văn bản người
 * dùng tải về. `cao` (twip, `w:trHeight`) giữ chỗ trống để ký tay; `canLeO`
 * giữ căn lề nguồn của từng ô, thay cho việc căn giữa mọi ô như trước.
 *
 * `vienO` khác rỗng → MỖI Ô kẻ đúng bốn cạnh nguồn (`w:tblBorders` +
 * `w:tcBorders` + chỗ ô đứng, đã ghép sẵn ở `hieu_tai_lieu._vien_o_bang`), và
 * viền CẤP BẢNG tắt hẳn để hai khai báo không chồng nhau. Rỗng → nét đều theo
 * `vien` như trước bản vá. `caoLuat` chỉ đổi đúng một điều: `auto` bỏ con số
 * `cao` (Word bỏ nó ở đó) — `exact` vẫn vẽ như tối thiểu, xem chú thích tại
 * `HeightRule.ATLEAST` bên dưới.
 *
 * `chuO` khác rỗng ở một ô → MỖI đoạn một `TextRun` mang đúng đậm/nghiêng/
 * gạch/cỡ/phông màn hình đã vẽ, cùng luật `dongThanhParagraph` dùng cho một
 * dòng văn xuôi. Ô đồng nhất → MỘT `TextRun` như trước bản vá. Hàng tiêu đề
 * của một bảng CÓ viền vẫn in đậm cả ô kể cả khi nguồn khai từng đoạn: đó là
 * thứ màn hình vẽ (`<th class="font-semibold">`), và tệp phải khớp màn hình.
 *
 * Tự `import("docx")` (module đã nạp thì cache lại, không tốn thêm) thay vì
 * nhận các lớp `docx` qua tham số: hàm phải gọi được ĐỘC LẬP với `xuatWord`
 * để kiểm (`kiem-xuat-tep.ts`) mà không cần dựng cả khung DOM thật.
 */
export async function bangThanhTable(
  hang: string[][],
  nhip: number[][] = [],
  tiLe: number[] = [],
  coVien = true,
  cao: number[] = [],
  canLeO: CanLe[][] = [],
  chuO: DoanChu[][][] = [],
  vienO: string[][] = [],
  caoLuat: string[] = [],
) {
  const {
    AlignmentType,
    BorderStyle,
    HeightRule,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    TextRun,
    WidthType,
  } = await import("docx");
  const khongNet = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const net = coVien ? { style: BorderStyle.SINGLE, size: 4, color: "999999" } : khongNet;
  const KIEU_DOCX = {
    solid: BorderStyle.SINGLE,
    double: BorderStyle.DOUBLE,
    dotted: BorderStyle.DOTTED,
    dashed: BorderStyle.DASHED,
  } as const;
  /** Viền một Ô theo NGUỒN — `null` khi bảng không có chi tiết theo cạnh, và
   *  khi đó ô kẻ nét đều `net` như trước bản vá. `w:sz` đi thẳng vào `size`:
   *  cả OOXML lẫn `docx` đo bề dày viền bằng ⅛ điểm, không quy đổi gì. */
  const vienDocx = (hi: number, oi: number) => {
    const tho = vienO[hi]?.[oi];
    if (tho === undefined) return null;
    const canh = tho.split("|").map(netCanh);
    return {
      top: canh[0]
        ? { style: KIEU_DOCX[kieuNetCSS(canh[0].val)], size: canh[0].sz, color: "999999" }
        : khongNet,
      right: canh[1]
        ? { style: KIEU_DOCX[kieuNetCSS(canh[1].val)], size: canh[1].sz, color: "999999" }
        : khongNet,
      bottom: canh[2]
        ? { style: KIEU_DOCX[kieuNetCSS(canh[2].val)], size: canh[2].sz, color: "999999" }
        : khongNet,
      left: canh[3]
        ? { style: KIEU_DOCX[kieuNetCSS(canh[3].val)], size: canh[3].sz, color: "999999" }
        : khongNet,
    };
  };
  const canhLeDocx = {
    left: AlignmentType.LEFT,
    center: AlignmentType.CENTER,
    right: AlignmentType.RIGHT,
    justify: AlignmentType.JUSTIFIED,
  } as const;
  const soCotTieuDe = soCotThat(hang, tiLe);
  const tiLeVe = tiLeCotVe(tiLe, soCotTieuDe);
  // Viền CẤP BẢNG về không khi mọi ô đã tự khai đủ bốn cạnh (`vienO`): hai
  // khai báo cùng nói về một nét là chỗ để chúng lệch nhau, và `w:tcBorders`
  // vốn đã thắng `w:tblBorders` trong Word — bỏ hẳn cái thua cuộc.
  const netBang = vienO.length > 0 ? khongNet : net;
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: netBang,
      bottom: netBang,
      left: netBang,
      right: netBang,
      insideHorizontal: netBang,
      insideVertical: netBang,
    },
    rows: hang.map((o, hi) => {
      const span = nhipHangVe(o, nhip[hi], soCotTieuDe);
      const laTieuDe = coVien && hi === 0;
      // `hRule="auto"` BỎ con số: Word bỏ nó ở đó, và ép một chiều cao tối
      // thiểu mà nguồn bảo đừng ép là vẽ thứ tệp không nói.
      const twip = caoLuat[hi] === "auto" ? 0 : (cao[hi] ?? 0);
      let cotDauTien = 0;
      return new TableRow({
        // `HeightRule.ATLEAST`, không `EXACT`, KỂ CẢ khi nguồn khai `exact`:
        // `exact` nghĩa là Word cắt chữ tràn, và cắt mất chữ của người dùng
        // hỏng tệ hơn một hàng cao hơn khai báo vài milimét — cùng lựa chọn
        // `XemTruocA4.caoTrenTrang` và PDF `caoKhaiMm`, nên tệp không bao giờ
        // khác màn hình. Sự thật `hRule` vẫn được đọc và chấm nguyên vẹn
        // (`DonViVanBan.bang_cao_luat`); chỉ NÉT VẼ là cố ý khác.
        ...(twip > 0 ? { height: { value: twip, rule: HeightRule.ATLEAST } } : {}),
        children: o.map((c, oi) => {
          const cot = span[oi] ?? 1;
          const rongO = tiLeVe.slice(cotDauTien, cotDauTien + cot).reduce((a, b) => a + b, 0);
          cotDauTien += cot;
          return new TableCell({
            width: { size: rongO, type: WidthType.PERCENTAGE },
            borders: vienDocx(hi, oi) ?? { top: net, bottom: net, left: net, right: net },
            // `exactOptionalPropertyTypes`: `shading`/`columnSpan` phải VẮNG
            // MẶT khi không dùng, không gán `undefined` — spread có điều
            // kiện, không gán.
            ...(laTieuDe ? { shading: { fill: "F0F0F0" } } : {}),
            ...(cot > 1 ? { columnSpan: cot } : {}),
            children: [
              new Paragraph({
                alignment: canhLeDocx[canhLeThanhHuong(canLeO[hi]?.[oi] ?? "trai")],
                children:
                  (chuO[hi]?.[oi] ?? []).length > 0
                    ? chuO[hi]![oi]!.map(
                        (d) =>
                          new TextRun({
                            text: d.text,
                            bold: laTieuDe || d.inDam,
                            italics: d.inNghieng,
                            ...(d.gachChan ? { underline: {} } : {}),
                            size: d.coChu > 0 ? d.coChu : 24,
                            font: d.phong || "Times New Roman",
                          }),
                      )
                    : [new TextRun({ text: c, bold: laTieuDe, font: "Times New Roman", size: 24 })],
              }),
            ],
          });
        }),
      });
    }),
  });
}

/**
 * Một dòng đã đọc từ DOM (`docNoiDungTuDOM`) → `Paragraph` thật của `docx`.
 *
 * Tách khỏi `xuatWord` vì ĐÚNG lý do `bangThanhTable` đã tách: gọi được độc
 * lập thì kiểm được (`kiem-dinh-dang-chu.ts`) mà không phải dựng cả một khung
 * DOM thật. Tự `import("docx")` — module đã nạp thì cache lại, không tốn thêm.
 *
 * `doan` khác rỗng (định dạng theo đoạn, 2026-09-18) → mỗi đoạn một `TextRun`
 * mang đúng đậm/nghiêng/gạch/cỡ/phông màn hình đã vẽ. Rỗng → MỘT `TextRun`
 * như trước bản vá, không đổi một byte nào của tệp cũ.
 *
 * Cỡ và phông của một đoạn chỉ ghi theo NGUỒN khi nguồn khai; không khai thì
 * về đúng cỡ/phông mặc định của dòng — không đoán thêm. Tên phông ghi NGUYÊN
 * tên nguồn chứ không phải họ chữ màn hình ánh xạ tới (`phongTrenManHinh`):
 * Word có sẵn phông ấy hoặc tự thay, còn trình duyệt thì không.
 */
export async function dongThanhParagraph(d: DongVanBan) {
  const { AlignmentType, HeadingLevel, Paragraph, Tab, TextRun, convertMillimetersToTwip } =
    await import("docx");
  const canhLeDocx = {
    left: AlignmentType.LEFT,
    center: AlignmentType.CENTER,
    right: AlignmentType.RIGHT,
    justify: AlignmentType.JUSTIFIED,
  } as const;
  const coMacDinh = d.kieu === "tieuDe" ? 32 : d.kieu === "dieu" ? 28 : 26;
  const g = d.gianCach;
  // Nguồn khai nhịp thì nguồn THẮNG, và chỉ ở đúng những thuộc tính nó khai:
  // `spacing: { after: 120, line: 312 }` bên dưới là thể thức của một bản
  // thảo KLAW TỰ soạn, không phải một câu trả lời về tài liệu của khách. Đoạn
  // không khai gì (`g === null`) ra tệp y hệt trước bản vá này, không đổi một
  // byte nào.
  const gianCachDocx = g
    ? {
        ...(g.truoc > 0 ? { before: g.truoc } : {}),
        ...(g.sau > 0 ? { after: g.sau } : {}),
        ...(g.dong > 0
          ? {
              line: g.dong,
              ...(LUAT_DONG_DOCX.has(g.luatDong)
                ? { lineRule: g.luatDong as "auto" | "atLeast" | "exact" | "exactly" }
                : {}),
            }
          : {}),
      }
    : { after: 120, line: 312 };
  // `w:ind` nguồn thay HẲN phép suy từ `margin-left` của màn hình (`thutLe`):
  // con số nguồn là twip THẬT, còn `thutLe` là px đo trên khung xem trước rồi
  // quy ngược — hai lần làm tròn cho cùng một sự thật.
  const thutLeDocx = g
    ? {
        ...(g.trai !== 0 ? { left: g.trai } : {}),
        ...(g.phai !== 0 ? { right: g.phai } : {}),
        ...(g.dauDong > 0 ? { firstLine: g.dauDong } : {}),
        ...(g.treo > 0 ? { hanging: g.treo } : {}),
      }
    : d.thutLe > 0
      ? { left: convertMillimetersToTwip(d.thutLe / 3.78) }
      : {};
  // Mốc tab đi cùng ĐOẠN (`w:pPr/w:tabs`) còn ký tự tab đi trong run, nên hai
  // chỗ đọc cùng một dãy `d.doan`: Word tự vẽ đường dẫn, không nơi nào phải
  // vẽ tay như PDF và màn hình.
  const mocTab = d.doan
    .map((o) => o.tab)
    .filter((m): m is MocTab => m !== null)
    .map((m) => ({
      type: CAN_TAB_DOCX[m.val as keyof typeof CAN_TAB_DOCX] ?? CAN_TAB_DOCX.left,
      position: m.pos,
      ...(m.leader in DAN_TAB_DOCX
        ? { leader: DAN_TAB_DOCX[m.leader as keyof typeof DAN_TAB_DOCX] }
        : {}),
    }));
  const run = (o: DoanChu) =>
    o.tab
      ? new TextRun({ children: [new Tab()] })
      : new TextRun({
          text: o.text,
          bold: o.inDam,
          italics: o.inNghieng,
          ...(o.gachChan ? { underline: {} } : {}),
          size: o.coChu > 0 ? o.coChu : coMacDinh,
          font: o.phong || "Times New Roman",
        });
  return new Paragraph({
    alignment: canhLeDocx[canhLeThanhHuong(d.canhLe)],
    ...(d.kieu === "tieuDe" ? { heading: HeadingLevel.HEADING_1 } : {}),
    spacing: gianCachDocx,
    ...(Object.keys(thutLeDocx).length > 0 ? { indent: thutLeDocx } : {}),
    ...(mocTab.length > 0 ? { tabStops: mocTab } : {}),
    children:
      d.doan.length > 0
        ? d.doan.map(run)
        : [
            new TextRun({
              text: d.text,
              bold: d.inDam,
              italics: d.inNghieng,
              size: coMacDinh,
              font: "Times New Roman",
            }),
          ],
  });
}

/** Xuất tệp Word (.docx) đúng thể thức: Times New Roman 13pt, lề 2cm/3cm. */
/** Bốn kiểu ảnh ba nơi vẽ CÙNG dựng được, nhận theo BYTES ĐẦU — cùng bộ
 *  `doc_tai_lieu._ANH_NHAN_DANG` phía máy chủ khoá lại. Nhận theo bytes chứ
 *  không theo `Content-Type` hay đuôi: đây là tệp của người lạ, và `docx` chỉ
 *  nhận đúng bốn tên này (`"jpg" | "png" | "gif" | "bmp"`). */
const NHAN_DANG_ANH: ReadonlyArray<readonly [readonly number[], "png" | "jpg" | "gif" | "bmp"]> = [
  [[0x89, 0x50, 0x4e, 0x47], "png"],
  [[0xff, 0xd8, 0xff], "jpg"],
  [[0x47, 0x49, 0x46, 0x38], "gif"],
  [[0x42, 0x4d], "bmp"],
];

/**
 * Bytes của MỘT ảnh nguồn, `null` khi không lấy được hoặc không nhận ra kiểu.
 *
 * `fetch` chứ không vẽ lại qua `<canvas>`: canvas mã hoá LẠI ảnh (mất nét ở
 * một con dấu quét, và đổi hẳn kiểu tệp), còn ở đây trình duyệt đã tải chính
 * đường dẫn này để vẽ ra màn hình nên lượt `fetch` thứ hai gần như luôn trúng
 * bộ nhớ đệm. `credentials: "include"` vì endpoint ảnh kiểm chủ sở hữu.
 *
 * FAIL CLOSED: mọi lỗi về `null`, và người gọi bỏ đúng tấm ảnh đó — cả tệp
 * tải về vẫn đủ phần còn lại, đúng luật `leTrangHopLe` đã đặt ở cửa vào.
 */
async function bytesAnh(
  url: string,
): Promise<{ data: Uint8Array; kieu: "png" | "jpg" | "gif" | "bmp" } | null> {
  try {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) return null;
    const data = new Uint8Array(await res.arrayBuffer());
    const kieu = NHAN_DANG_ANH.find(([dau]) => dau.every((b, i) => data[i] === b))?.[1];
    return kieu ? { data, kieu } : null;
  } catch {
    return null;
  }
}

/**
 * MỘT ảnh nguồn → một `Paragraph` chứa `ImageRun`, căn giữa.
 *
 * Cỡ quy từ EMU (đơn vị nguồn `wp:extent`) sang PIXEL vì đó là đơn vị
 * `IMediaTransformation` nhận — `docx` tự nhân 9525 để về lại EMU, nên con số
 * cuối cùng trong tệp đúng bằng con số nguồn khai, không qua một phép làm
 * tròn nào của mình.
 *
 * Lấy bytes không được thì trả về một `Paragraph` RỖNG chứ không ném: một con
 * dấu không tải được không đáng làm hỏng cả tệp người dùng đang tải về —
 * đúng luật fail-closed của cả bản vá.
 *
 * Căn GIỮA: `vung` không đi qua được `docNoiDungTuDOM` (ở đó mọi khối đều
 * thuộc thân trang `.docx`), và một logo letterhead căn giữa là thể thức đúng
 * của văn bản hành chính Việt Nam.
 * ponytail: trần "ảnh nào cũng căn giữa". Nâng lên căn lề nguồn khi
 * `wp:anchor/@positionH` được đọc — việc đó cần một quyết định cho vị trí
 * tuyệt đối, thứ quyết định 2026-09-18 đã để ngoài phạm vi.
 */
export async function anhThanhParagraph(a: AnhNguon) {
  const { AlignmentType, ImageRun, Paragraph } = await import("docx");
  const anh = await bytesAnh(a.url);
  if (!anh) return new Paragraph({ children: [] });
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new ImageRun({
        type: anh.kieu,
        data: anh.data,
        transformation: {
          width: Math.max(1, Math.round(a.rong / EMU_MOI_PX)),
          height: Math.max(1, Math.round(a.cao / EMU_MOI_PX)),
        },
      }),
    ],
  });
}

export async function xuatWord(sheet: HTMLElement, tieuDe: string) {
  const {
    AlignmentType,
    Document,
    HeadingLevel,
    Packer,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    TextRun,
    WidthType,
    BorderStyle,
    convertMillimetersToTwip,
  } = await import("docx");

  const { khoi, oKy, leTrang } = docNoiDungTuDOM(sheet);

  const CANH_LE_DOCX = {
    left: AlignmentType.LEFT,
    center: AlignmentType.CENTER,
    right: AlignmentType.RIGHT,
  } as const;
  const khong = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const bangKy =
    oKy.length > 0
      ? [
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            borders: {
              top: khong,
              bottom: khong,
              left: khong,
              right: khong,
              insideHorizontal: khong,
              insideVertical: khong,
            },
            rows: [
              new TableRow({
                children: oKy.map(
                  (cot) =>
                    new TableCell({
                      width: { size: 100 / oKy.length, type: WidthType.PERCENTAGE },
                      borders: { top: khong, bottom: khong, left: khong, right: khong },
                      children: cot.map(
                        (d, i) =>
                          new Paragraph({
                            alignment: AlignmentType.CENTER,
                            spacing: { before: i === cot.length - 1 ? 1200 : 0, after: 80 },
                            children: [
                              new TextRun({
                                text: d.text,
                                bold: d.inDam,
                                italics: d.inNghieng,
                                size: 26,
                                font: "Times New Roman",
                              }),
                            ],
                          }),
                      ),
                    }),
                ),
              }),
            ],
          }),
        ]
      : [];

  // Đoạn văn dựng NGAY (đồng bộ); bảng dựng bất đồng bộ (`bangThanhTable` tự
  // `import("docx")`) — `Promise.all` giữ ĐÚNG thứ tự `khoi` đã đọc từ DOM.
  const noiDungThan = await Promise.all(
    khoi.map(async (k) =>
      k.kind === "dong"
        ? dongThanhParagraph(k.d)
        : k.kind === "anh"
          ? await anhThanhParagraph(k.a)
          : bangThanhTable(
              k.hang,
              k.nhip,
              k.tiLe,
              k.vien,
              k.cao,
              k.canLeO,
              k.chuO,
              k.vienO ?? [],
              k.caoLuat ?? [],
            ),
    ),
  );

  const doc = new Document({
    creator: "KLAW",
    title: tieuDe,
    description: "Bản thảo văn bản pháp lý do KLAW tạo — cần rà soát pháp chế trước khi ký kết.",
    styles: {
      default: {
        document: { run: { font: "Times New Roman", size: 26 } },
      },
    },
    sections: [
      {
        properties: {
          // Lề NGUỒN (`w:pgMar`, đọc lại từ `data-le-*` màn hình đã vẽ) thắng
          // hẳn lề mặc định của KLAW: một biểu mẫu khai lề trái 1701 twip
          // (30mm) và lề trên 1134 (20mm) phải ra tệp đúng chỗ ấy, không phải
          // chỗ thể thức mặc định của một bản thảo KLAW tự soạn. `header`/
          // `footer` đi cùng vì chúng quyết định chữ đầu/chân trang nằm đâu.
          // Không có lề nguồn → giữ nguyên bộ 20/20/30/20mm cũ.
          page: {
            margin: leTrang
              ? {
                  top: leTrang.tren,
                  bottom: leTrang.duoi,
                  left: leTrang.trai,
                  right: leTrang.phai,
                  header: leTrang.dauTrang,
                  footer: leTrang.chanTrang,
                }
              : {
                  top: convertMillimetersToTwip(20),
                  bottom: convertMillimetersToTwip(20),
                  left: convertMillimetersToTwip(30),
                  right: convertMillimetersToTwip(20),
                },
          },
        },
        children: [...noiDungThan, new Paragraph({ text: "" }), ...bangKy],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  taiBlob(blob, `${tenTepAnToan(tieuDe)}.docx`);
}

/**
 * Phase 5 — PDF vẽ bằng API văn bản của jsPDF (`text`/`splitTextToSize`),
 * không còn `html2canvas` chụp khung xem trước ra ảnh: chữ trong tệp tải về
 * giờ CHỌN/COPY/TÌM được, và không còn trần 30 trang giả (`nhanBanKhung` +
 * vòng cắt ảnh cũ đã bỏ hẳn). `noiDungThanhPDF` vẽ từ ĐÚNG `docNoiDungTuDOM`
 * đọc được — nguồn sự thật DUY NHẤT, giống `.docx` (`xuatWord`) đã dùng.
 */

/** 1pt = 25.4/72 mm — đổi cỡ chữ (pt, đơn vị `setFontSize` của jsPDF) sang mm
 * (đơn vị tài liệu, `unit: "mm"`). */
const MM_MOI_PT = 25.4 / 72;

/** Lề trang PDF MẶC ĐỊNH — khớp NGUYÊN `xuatWord` (trên/dưới 20mm, trái 30mm,
 * phải 20mm): R4 nói hai tệp chỉ nên khác nhau ở font, không khác ở bố cục.
 * Chỉ dùng khi khung A4 KHÔNG mang lề nguồn; có lề nguồn thì cả hai tệp lấy
 * đúng lề ấy, xem `leTrangMm`. */
const LE_PDF_MAC_DINH = { tren: 20, duoi: 20, trai: 30, phai: 20 };
const RONG_A4 = 210;
const CAO_A4 = 297;

/** 1 twip = 1/1440 inch = 25.4/1440 mm — `w:pgMar` (twip) → đơn vị tài liệu
 *  PDF (mm). Cùng con số `convertMillimetersToTwip` của `docx` đi ngược lại,
 *  nên hai tệp đặt lề ở đúng một chỗ. */
const MM_MOI_TWIP = 25.4 / 1440;

/** Lề NGUỒN → lề PDF (mm), hoặc lề mặc định khi không có lề nguồn.
 *  Nhận cả `undefined`: một `NoiDungXuat` dựng bằng tay (kịch bản kiểm, mã gọi
 *  cũ) không có khoá này, và ở đó lề mặc định là câu trả lời đúng. */
function leTrangMm(le: LeTrang | null | undefined): typeof LE_PDF_MAC_DINH {
  return !le
    ? LE_PDF_MAC_DINH
    : {
        tren: le.tren * MM_MOI_TWIP,
        duoi: le.duoi * MM_MOI_TWIP,
        trai: le.trai * MM_MOI_TWIP,
        phai: le.phai * MM_MOI_TWIP,
      };
}

/** % mỗi cột (đã qua `tiLeCotVe`, chia đều khi rỗng) → bề rộng mm trong PDF
 * (Phase 11 R1) — MỘT chỗ quy đổi, dùng cho cả chiều cao đo và hình vẽ.
 * `rongNoiDung` truyền vào chứ không đọc một hằng số module: bề rộng cột chữ
 * giờ phụ thuộc lề NGUỒN, đổi theo từng tài liệu. */
function rongCotPDF(tiLe: number[], soCot: number, rongNoiDung: number): number[] {
  return tiLeCotVe(tiLe, soCot).map((p) => (p / 100) * rongNoiDung);
}

/**
 * Hệ số giãn dòng, truyền NGUYÊN vào `options.lineHeightFactor` của mọi lệnh
 * `text()` đa dòng bên dưới — jsPDF tự tính bước nhảy dòng nội bộ là
 * `activeFontSize * lineHeightFactor` với `activeFontSize` đã quy đổi sang mm
 * (xem `setFontSize` trong `jspdf`), tức CÙNG công thức `coChuPt(...) *
 * MM_MOI_PT * HE_SO_DONG_PDF` mà `caoDongPt` dùng để cộng dồn `y` thủ công.
 * Lệch hệ số này ở một trong hai chỗ là chữ dòng sau đè lên dòng trước.
 */
const HE_SO_DONG_PDF = 1.3;

/** Khoảng cách sau một đoạn — khớp `xuatWord`: `spacing.after: 120` (twip,
 * 1/20pt) = 6pt. */
const SAU_DOAN_PDF = 6 * MM_MOI_PT;

/** Cỡ chữ (pt) theo loại dòng — khớp NGUYÊN bảng size của `xuatWord.para`
 * (32/28/26 nửa-điểm = 16/14/13pt): ba định dạng (màn hình, .docx, .pdf) giữ
 * cùng phân cấp tiêu đề/điều/thường, chỉ khác font (R4). */
function coChuPt(kieu: KieuDong): number {
  return kieu === "tieuDe" ? 16 : kieu === "dieu" ? 14 : 13;
}

function caoDongPt(kieu: KieuDong): number {
  return coChuPt(kieu) * MM_MOI_PT * HE_SO_DONG_PDF;
}

/** Kiểu chữ (một trong bốn tên `setFont` chấp nhận) từ cờ đậm/nghiêng của một
 * dòng đã đọc từ DOM. */
function kieuChuPDF(d: DongVanBan): "normal" | "bold" | "italic" | "bolditalic" {
  if (d.inDam && d.inNghieng) return "bolditalic";
  if (d.inDam) return "bold";
  if (d.inNghieng) return "italic";
  return "normal";
}

const HO_CHU_PDF = "SourceSerif4";

/**
 * Bytes base64 của hai tệp TTF nhúng cho PDF (thường/đậm) — xem
 * `taiPhongChuPDF` (đường trình duyệt, `fetch` từ `public/fonts/`) và
 * `kiem-xuat-tep.ts` (đường Node, đọc thẳng từ đĩa). Cả hai đổ vào MỘT hàm
 * dựng PDF thuần (`noiDungThanhPDF`, không đụng DOM/`fetch`) để kiểm được từ
 * Node — không cần trình duyệt hay `jsdom`.
 *
 * Nguồn (Phase 5 R2): hai tệp `.ttf` này KHÔNG tải font mới nào — chúng được
 * đúc lại từ CHÍNH ba tệp webfont đã tự host, đã có trong kho TRƯỚC Phase 5:
 * `public/fonts/source-serif-4-var-{latin,latin-ext,vietnamese}.woff2`
 * (Source Serif 4, biến thiên, cấp phép OFL 1.1 — SIL Open Font License).
 * jsPDF (`addFileToVFS`/`addFont`) chỉ nhận TTF tĩnh, không nhận woff2 biến
 * thiên, nên ba tệp trên được, ngoại tuyến, một lần: (1) giải nén woff2→ttf
 * bằng `fontTools`, (2) đúc mỗi tệp thành hai lát cắt TĨNH 400/700 bằng
 * `fontTools.varLib.instancer` (font nguồn chỉ có trục `wght`), (3) GỘP ba
 * tập ký tự la-tinh cơ bản + la-tinh mở rộng + tiếng Việt mỗi lát cắt bằng
 * `fontTools.merge` — vì tệp con `-vietnamese.woff2` một mình CHỈ có 115 mã,
 * thiếu gần hết chữ cái/số/dấu câu cơ bản (đã đo: chỉ 'A'/'B' sống sót làm
 * .notdef dự phòng). Không có bước nào lấy nội dung font từ nguồn ngoài kho.
 * Font nguồn không có lát cắt nghiêng — xem ghi chú tại `dangKyPhongChuPDF`.
 */
export type PhongChuPDF = { thuong: string; dam: string };

type JsPDFModule = typeof import("jspdf");
type JsPDF = InstanceType<JsPDFModule["jsPDF"]>;

function dangKyPhongChuPDF(pdf: JsPDF, phongChu: PhongChuPDF) {
  pdf.addFileToVFS("SourceSerif4-Regular.ttf", phongChu.thuong);
  pdf.addFont("SourceSerif4-Regular.ttf", HO_CHU_PDF, "normal");
  pdf.addFileToVFS("SourceSerif4-Bold.ttf", phongChu.dam);
  pdf.addFont("SourceSerif4-Bold.ttf", HO_CHU_PDF, "bold");
  // Font nguồn chỉ đúc từ trục wght, không có trục nghiêng — đăng ký
  // "italic"/"bolditalic" TRỎ VÀO tệp đứng, để jsPDF không rơi về font mặc
  // định (Helvetica, không có dấu tiếng Việt) khi gặp một dòng nghiêng như
  // chú thích chữ ký "(Ký, ghi rõ họ tên, đóng dấu)". Đổi lại dòng đó hiện
  // THẲNG ĐỨNG thay vì nghiêng — mất dấu tiếng Việt là lỗi brief cấm (R2),
  // mất độ nghiêng thì không.
  pdf.addFont("SourceSerif4-Regular.ttf", HO_CHU_PDF, "italic");
  pdf.addFont("SourceSerif4-Bold.ttf", HO_CHU_PDF, "bolditalic");
  pdf.setFont(HO_CHU_PDF, "normal");
}

/**
 * Dựng PDF THẬT từ `{ khoi, oKy }` (Phase 5 R1) — hàm THUẦN: không đụng DOM,
 * không `fetch`, nhận bytes phông chữ qua tham số, để `kiem-xuat-tep.ts` gọi
 * được thẳng từ Node.
 *
 * Trả thêm `trangCuaKhoi`/`trangCuaKy` — số trang (1-based, tính từ lúc BẮT
 * ĐẦU vẽ khối đó) — CHỈ để kiểm luật phân trang (R3) mà không phải bóc PDF
 * nhị phân ra suy ngược trang của một khối.
 */
export async function noiDungThanhPDF(
  noiDung: NoiDungXuat,
  tieuDe: string,
  phongChu: PhongChuPDF,
): Promise<{ pdf: JsPDF; trangCuaKhoi: number[]; trangCuaKy: number | null }> {
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ unit: "mm", format: "a4", compress: true });
  dangKyPhongChuPDF(pdf, phongChu);

  // Lề của LƯỢT XUẤT này, không một hằng số module: một biểu mẫu khai
  // `w:pgMar` thì cả ba nơi vẽ phải đặt khối vào đúng chỗ ấy. Khai báo cục bộ
  // để mọi phép tính bên dưới (`conCho`, bề rộng cột, khối ký) tự đi theo.
  const LE_PDF = leTrangMm(noiDung.leTrang);
  const RONG_NOI_DUNG_PDF = RONG_A4 - LE_PDF.trai - LE_PDF.phai;

  // Bytes ảnh nạp TRƯỚC, một lượt: vòng vẽ `trangCuaKhoi` bên dưới là ĐỒNG BỘ
  // (mỗi khối trả về số trang của nó), nên không có chỗ nào `await` được ở
  // giữa. Ảnh nạp không được vắng mặt khỏi Map và `veAnh` bỏ qua nó — cùng
  // luật fail-closed của `anhThanhParagraph`.
  const byteAnh = new Map<string, { data: Uint8Array; kieu: "png" | "jpg" | "gif" | "bmp" }>();
  for (const k of noiDung.khoi) {
    if (k.kind !== "anh" || byteAnh.has(k.a.url)) continue;
    const b = await bytesAnh(k.a.url);
    if (b) byteAnh.set(k.a.url, b);
  }

  let y = LE_PDF.tren;
  let trang = 1;

  const conCho = (can: number) => y + can <= CAO_A4 - LE_PDF.duoi;
  const trangMoi = () => {
    pdf.addPage();
    trang += 1;
    y = LE_PDF.tren;
  };

  const DEM_O_PDF = 1.5; // mm, đệm trong một ô bảng
  const CO_CHU_BANG_PDF = 12; // pt, khớp `bangThanhTable` (`size: 24` nửa-điểm)
  /** Bước nhảy một dòng chữ trong ô, cỡ MẶC ĐỊNH của bảng. */
  const MOT_DONG_BANG = CO_CHU_BANG_PDF * MM_MOI_PT * HE_SO_DONG_PDF;
  /**
   * twip (`w:trHeight`) → mm. 1 twip = 1/20 pt.
   *
   * `hRule="auto"` trả 0: Word BỎ con số ở đó, nên ép một chiều cao tối thiểu
   * là vẽ thứ tệp không nói. `exact` thì KHÔNG trả về một trần — nó vẫn chỉ
   * là sàn, cùng lựa chọn `bangThanhTable` và `XemTruocA4.caoTrenTrang`: cắt
   * mất chữ của người dùng hỏng hơn một hàng cao dôi vài milimét.
   */
  const caoKhaiMm = (twip: number | undefined, luat = "") =>
    luat === "auto" ? 0 : ((twip ?? 0) / 20) * MM_MOI_PT;

  /**
   * Bố cục chữ của MỘT Ô bảng — MỘT chỗ tính, hai chỗ dùng
   * (`chieuCaoHangBang` đo để phân trang, `veMotHangBang` vẽ), nên chiều cao
   * đo được và hình vẽ ra không lệch nhau được.
   *
   * Ô có định dạng theo đoạn (`doan` khác rỗng) đi qua `boCucDoan` — cùng
   * hàm một dòng văn xuôi dùng — vì `splitTextToSize` chỉ cắt được theo MỘT
   * font và MỘT cỡ chữ, còn một ô letterhead trộn 13pt với 14pt in đậm.
   * Chiều cao trả về khi đó cộng theo cỡ LỚN NHẤT của từng dòng (`boCucDoan`),
   * nên một ô có run to hơn cỡ mặc định của bảng vẫn được dành đủ chỗ.
   *
   * Ô đồng nhất giữ nguyên `splitTextToSize` như trước bản vá — không đổi một
   * milimét nào của mọi bảng đang có.
   */
  const boCucOBang = (
    chu: string,
    rongChu: number,
    laTieuDe: boolean,
    doan: DoanChu[] | undefined,
  ): { cao: number; dong: string[]; manh: ManhChu[][] | null } => {
    if (doan && doan.length > 0) {
      // Hàng tiêu đề của một bảng CÓ viền in đậm CẢ ô, kể cả đoạn nguồn khai
      // thường: đó đúng là thứ màn hình vẽ (`<th class="font-semibold">`) và
      // `bangThanhTable` ghi — ba nơi vẽ, một luật.
      const bo = boCucDoan(
        laTieuDe ? doan.map((o) => ({ ...o, inDam: true })) : doan,
        CO_CHU_BANG_PDF,
        khungMacDinh(rongChu),
      );
      return { cao: bo.cao, dong: [], manh: bo.dong };
    }
    pdf.setFont(HO_CHU_PDF, laTieuDe ? "bold" : "normal");
    pdf.setFontSize(CO_CHU_BANG_PDF);
    const dong = pdf.splitTextToSize(chu, rongChu) as string[];
    return { cao: dong.length * MOT_DONG_BANG, dong, manh: null };
  };

  /**
   * Chiều cao (mm) MỘT hàng bảng sẽ chiếm — đo THẬT qua `boCucOBang` (chính
   * hàm `veMotHangBang` dùng để vẽ), trên đúng font/cỡ chữ từng Ô dùng, không
   * phải một hằng số ước lượng.
   * Dùng CẢ để quyết định phân trang bên trong `veBang` LẪN để luật mồ côi
   * (`chieuCaoKeTiep`) đo hàng tiêu đề của một bảng đứng NGAY sau một tiêu đề
   * — một nơi tính, không phải hai con số có thể lệch nhau.
   */
  const chieuCaoHangBang = (
    o: string[],
    soCotTieuDe: number,
    laTieuDe: boolean,
    rongCotMm: number[],
    nhipHang: number[] | undefined,
    caoKhai = 0,
    chuHang: DoanChu[][] = [],
    luatCao = "",
  ): number => {
    const span = nhipHangVe(o, nhipHang, soCotTieuDe);
    let cotDauTien = 0;
    const caoChu = o.reduce((max, c, oi) => {
      const cot = span[oi] ?? 1;
      const rongO = rongCotMm.slice(cotDauTien, cotDauTien + cot).reduce((a, b) => a + b, 0);
      cotDauTien += cot;
      return Math.max(max, boCucOBang(c, rongO - 2 * DEM_O_PDF, laTieuDe, chuHang[oi]).cao);
    }, MOT_DONG_BANG);
    // Chiều cao khai báo của hàng là SÀN, không phải giá trị thay thế: một
    // hàng ký khai 1499 twip cần đúng chỗ trống đó, còn một hàng khai thấp
    // hơn chữ của nó vẫn phải đủ cao để không cắt chữ.
    return Math.max(caoChu + 2 * DEM_O_PDF, caoKhaiMm(caoKhai, luatCao));
  };

  /**
   * Kẻ bốn cạnh NGUỒN của một ô (`"trên|phải|dưới|trái"`, mỗi phần
   * `"w:val/w:sz"`) thay cho một khung chữ nhật đều.
   *
   * `w:sz` là ⅛ điểm, đổi sang mm bằng đúng `MM_MOI_PT` mà cả tệp dùng — cùng
   * con số `bangThanhTable` đưa thẳng vào `size` của `docx`, nên hai tệp kẻ
   * một nét dày bằng nhau.
   *
   * ponytail: `double` kẻ MỘT nét liền (jsPDF không có kiểu nét đôi; kẻ hai
   * đường song song cần biết khoảng hở Word dùng, thứ `w:sz` không nói). Nâng
   * lên khi đo thấy một biểu mẫu thật dùng viền đôi — tám biểu mẫu của chủ dự
   * án khai `single` ở cả 62 cạnh.
   */
  const veCanhO = (x: number, y0: number, rong: number, cao: number, tho: string) => {
    const canh = tho.split("|").map(netCanh);
    const diem: [number, number, number, number][] = [
      [x, y0, x + rong, y0],
      [x + rong, y0, x + rong, y0 + cao],
      [x, y0 + cao, x + rong, y0 + cao],
      [x, y0, x, y0 + cao],
    ];
    for (let i = 0; i < 4; i++) {
      const n = canh[i];
      if (!n) continue;
      const day = (n.sz / 8) * MM_MOI_PT;
      pdf.setLineWidth(day);
      const kieu = kieuNetCSS(n.val);
      if (kieu === "dotted") pdf.setLineDashPattern([day, day], 0);
      else if (kieu === "dashed") pdf.setLineDashPattern([day * 4, day * 2], 0);
      pdf.line(...diem[i]!);
      if (kieu === "dotted" || kieu === "dashed") pdf.setLineDashPattern([], 0);
    }
    pdf.setLineWidth(0.2);
  };

  /** Vẽ MỘT hàng bảng tại `y` hiện tại (không tự phân trang) — dùng cho hàng
   * thật VÀ để lặp lại hàng tiêu đề ở đầu mỗi trang bảng chẻ sang (R3 fix
   * round 1 #2): thiếu bước lặp này thì trang sau của một bảng dài mất tên
   * cột, không ai biết cột nào là "Điểm tối đa", cột nào là "Điểm đánh giá". */
  const veMotHangBang = (
    o: string[],
    soCotTieuDe: number,
    laTieuDe: boolean,
    rongCotMm: number[],
    nhipHang: number[] | undefined,
    coVien = true,
    caoKhai = 0,
    canLeHang: CanLe[] = [],
    chuHang: DoanChu[][] = [],
    vienHang: string[] = [],
    luatCao = "",
  ) => {
    // `nhipHangVe` — CÙNG luật ô gộp dùng cho màn hình (`XemTruocA4`) và
    // `.docx` (`bangThanhTable`): nhịp THẬT khi bảng có khai lưới nguồn (Phase
    // 11 R6), suy từ số ô khi không. Ba nơi vẽ bảng, MỘT luật đặt cột.
    const span = nhipHangVe(o, nhipHang, soCotTieuDe);
    const rongO_: number[] = [];
    {
      let cotDauTien = 0;
      for (const cot of o.map((_, oi) => span[oi] ?? 1)) {
        rongO_.push(rongCotMm.slice(cotDauTien, cotDauTien + cot).reduce((a, b) => a + b, 0));
        cotDauTien += cot;
      }
    }
    const boCucO = o.map((c, oi) =>
      boCucOBang(c, rongO_[oi]! - 2 * DEM_O_PDF, laTieuDe, chuHang[oi]),
    );
    const caoHang = Math.max(
      boCucO.reduce((max, b) => Math.max(max, b.cao), MOT_DONG_BANG) + 2 * DEM_O_PDF,
      caoKhaiMm(caoKhai, luatCao),
    );

    if (laTieuDe) {
      pdf.setFillColor(240, 240, 240);
      pdf.rect(LE_PDF.trai, y, RONG_NOI_DUNG_PDF, caoHang, "F");
    }
    pdf.setDrawColor(153, 153, 153);
    let xO = LE_PDF.trai;
    for (let oi = 0; oi < o.length; oi++) {
      const rongO = rongO_[oi]!;
      // Bảng nguồn không viền là khối BỐ CỤC (khối ký, letterhead): không kẻ
      // nét nào, đúng như `bangThanhTable` và `XemTruocA4` — ba nơi vẽ, một
      // sự thật đọc từ `w:tblBorders`. Có chi tiết TỪNG CẠNH (`vienHang`) thì
      // kẻ đúng bốn cạnh nguồn thay cho khung chữ nhật đều: một bảng chỉ kẻ
      // khung ngoài không được ra PDF thành một cái lưới kẻ đủ mọi ô.
      const canhO = vienHang[oi];
      if (canhO !== undefined) veCanhO(xO, y, rongO, caoHang, canhO);
      else if (coVien) pdf.rect(xO, y, rongO, caoHang);
      const huong = canhLeThanhHuong(canLeHang[oi] ?? "trai");
      const bo = boCucO[oi]!;
      if (bo.manh) {
        // Ô nhiều định dạng: vẽ theo từng mảnh, tại `y` RIÊNG của ô — con trỏ
        // chung không nhúc nhích, `caoHang` bên dưới mới đẩy nó.
        veManhChu(
          bo.manh,
          xO + DEM_O_PDF,
          khungMacDinh(rongO - 2 * DEM_O_PDF),
          huong,
          y + DEM_O_PDF,
        );
      } else {
        // Đặt lại font/cỡ ngay trước khi vẽ: một ô nhiều định dạng đứng trước
        // trong CÙNG hàng đã đổi trạng thái font của `pdf`.
        pdf.setFont(HO_CHU_PDF, laTieuDe ? "bold" : "normal");
        pdf.setFontSize(CO_CHU_BANG_PDF);
        const xChu =
          huong === "center"
            ? xO + rongO / 2
            : huong === "right"
              ? xO + rongO - DEM_O_PDF
              : xO + DEM_O_PDF;
        pdf.text(bo.dong, xChu, y + DEM_O_PDF + CO_CHU_BANG_PDF * MM_MOI_PT, {
          align: huong,
          maxWidth: rongO - 2 * DEM_O_PDF,
          lineHeightFactor: HE_SO_DONG_PDF,
        });
      }
      xO += rongO;
    }
    y += caoHang;
  };

  /** Một bảng — trả về số trang đã BẮT ĐẦU vẽ (hàng tiêu đề của nó). */
  /** EMU → mm. 914400 EMU = 1 inch = 25.4mm. */
  const emuMm = (emu: number) => (emu / 914400) * 25.4;

  /**
   * MỘT ảnh nguồn lên trang PDF, trả về số trang đã vẽ nó.
   *
   * Không chẻ khối, đúng luật khối ký (R3): một tấm ảnh cắt đôi qua hai trang
   * là một con dấu rách. Không vừa chỗ còn lại thì sang trang mới rồi vẽ trọn.
   * Ảnh CAO hơn cả một trang thì vẫn vẽ (và bị mép trang cắt) thay vì lặp vô
   * hạn `trangMoi()` — một ảnh bìa A4 nằm đúng ca đó.
   *
   * Căn GIỮA theo bề rộng cột chữ, cùng lựa chọn `anhThanhParagraph` của
   * `.docx`: hai tệp phải nói cùng một điều.
   *
   * Nạp bytes không được thì KHÔNG vẽ và KHÔNG chừa chỗ — cùng luật
   * fail-closed, và chừa một khoảng trắng cho một thứ không vẽ ra sẽ đẩy lệch
   * mọi khối sau nó.
   */
  const veAnh = (a: AnhNguon): number => {
    const b = byteAnh.get(a.url);
    if (!b) return trang;
    const rongMax = RONG_NOI_DUNG_PDF;
    let w = emuMm(a.rong);
    let h = emuMm(a.cao);
    // Ảnh rộng hơn cột chữ thu về vừa cột, GIỮ tỉ lệ: méo một con dấu tệ hơn
    // là thu nhỏ nó.
    if (w > rongMax && w > 0) {
      h = (h * rongMax) / w;
      w = rongMax;
    }
    const caoTrang = CAO_A4 - LE_PDF.tren - LE_PDF.duoi;
    if (!conCho(h) && h <= caoTrang) trangMoi();
    try {
      pdf.addImage(b.data, b.kieu.toUpperCase(), LE_PDF.trai + (rongMax - w) / 2, y, w, h);
    } catch {
      // jsPDF từ chối một kiểu ảnh nó không dựng được: bỏ tấm đó, giữ cả tệp.
      return trang;
    }
    const tr = trang;
    y += h;
    return tr;
  };

  const veBang = (
    hang: string[][],
    nhip: number[][],
    tiLe: number[],
    coVien: boolean,
    cao: number[],
    canLeO: CanLe[][],
    chuO: DoanChu[][][],
    // Mặc định `[]`: một `BangThat` dựng bằng tay (kịch bản kiểm, mã gọi cũ)
    // không có hai trường này, và ở đó bảng phải kẻ nét đều như trước bản vá
    // chứ không được ném lỗi giữa lượt xuất tệp.
    vienO: string[][] = [],
    caoLuat: string[] = [],
  ): number => {
    const soCotTieuDe = soCotThat(hang, tiLe);
    if (soCotTieuDe === 0) return trang;
    const rongCotMm = rongCotPDF(tiLe, soCotTieuDe, RONG_NOI_DUNG_PDF);
    let trangBatDau: number | null = null;

    for (let hi = 0; hi < hang.length; hi++) {
      const o = hang[hi]!;
      // Hàng ĐẦU chỉ là hàng tiêu đề khi bảng CÓ viền — bảng bố cục không có
      // hàng tiêu đề của gì cả (xem `bangThanhTable`).
      const laTieuDe = coVien && hi === 0;
      const caoHang = chieuCaoHangBang(
        o,
        soCotTieuDe,
        laTieuDe,
        rongCotMm,
        nhip[hi],
        cao[hi],
        chuO[hi],
        caoLuat[hi],
      );
      if (!conCho(caoHang)) {
        trangMoi();
        // Chẻ giữa bảng (không phải ngay hàng tiêu đề) — lặp lại hàng tiêu
        // đề ở đầu trang mới trước khi vẽ tiếp hàng vừa bị đẩy sang. Bảng
        // không viền không lặp: nó không có hàng tiêu đề để mang theo, và
        // lặp lại hàng đầu của một khối ký là in tên người ký hai lần.
        if (hi > 0 && coVien)
          veMotHangBang(
            hang[0]!,
            soCotTieuDe,
            true,
            rongCotMm,
            nhip[0],
            coVien,
            cao[0],
            canLeO[0],
            chuO[0],
            vienO[0],
            caoLuat[0],
          );
      }
      trangBatDau ??= trang;
      veMotHangBang(
        o,
        soCotTieuDe,
        laTieuDe,
        rongCotMm,
        nhip[hi],
        coVien,
        cao[hi],
        canLeO[hi],
        chuO[hi],
        vienO[hi],
        caoLuat[hi],
      );
    }
    y += SAU_DOAN_PDF;
    return trangBatDau ?? trang;
  };

  // Khớp `xuatWord`: `spacing.before: 1200` twip trước dòng ký cuối (chỗ
  // trống để ký tay), `spacing.after: 80` twip giữa các dòng còn lại.
  const soCotKy = noiDung.oKy.length;
  const rongCotKy = soCotKy > 0 ? RONG_NOI_DUNG_PDF / soCotKy : 0;
  const KHOANG_KY = (1200 / 20) * MM_MOI_PT;
  const SAU_DONG_KY = (80 / 20) * MM_MOI_PT;
  const caoCotKy = (cot: DongVanBan[]) => {
    let cao = 0;
    cot.forEach((d, i) => {
      pdf.setFontSize(coChuPt(d.kieu));
      const dong = pdf.splitTextToSize(d.text, rongCotKy) as string[];
      if (i === cot.length - 1) cao += KHOANG_KY;
      cao += dong.length * caoDongPt(d.kieu);
      if (i < cot.length - 1) cao += SAU_DONG_KY;
    });
    return cao;
  };
  // Tính chiều cao khối ký MỘT lần, dùng CẢ cho luật mồ côi (một tiêu đề
  // đứng NGAY trước khối ký) LẪN cho việc vẽ khối ký thật bên dưới — một số
  // duy nhất, không phải hai phép tính riêng có thể lệch nhau.
  const caoKhoiKy =
    soCotKy > 0 ? noiDung.oKy.reduce((max, cot) => Math.max(max, caoCotKy(cot)), 0) : 0;

  /** Một MẢNH chữ đã đo: một từ, một cụm khoảng trắng, hoặc một chỗ TAB, kèm
   * đúng font và cỡ chữ nó sẽ được vẽ ra. Đơn vị nhỏ nhất phép xuống dòng
   * được cắt. Mảnh TAB có `rong` tính lúc XẾP DÒNG, không lúc đo chữ: nó là
   * quãng nhảy từ chỗ con trỏ đang đứng tới mốc, nên chỉ biết được khi đã
   * biết con trỏ đứng đâu. */
  type ManhChu = {
    text: string;
    pt: number;
    kieu: "normal" | "bold" | "italic" | "bolditalic";
    gach: boolean;
    rong: number;
    tab: MocTab | null;
  };

  const kieuDoanPDF = (o: DoanChu): ManhChu["kieu"] =>
    o.inDam && o.inNghieng ? "bolditalic" : o.inDam ? "bold" : o.inNghieng ? "italic" : "normal";

  /** twip → mm, qua `pt`. Cùng phép quy đổi `caoKhaiMm` dùng cho `w:trHeight`. */
  const twipMm = (twip: number) => twip * PT_MOI_TWIP * MM_MOI_PT;

  /** Bước nhảy một dòng (mm) khi nguồn không khai `w:spacing/@w:line`. */
  const buocMacDinh = (pt: number) => pt * MM_MOI_PT * HE_SO_DONG_PDF;

  /**
   * Bước nhảy một dòng theo `w:spacing` nguồn.
   *
   * `auto` — `w:line` là BỘI SỐ của 240, nên nó thay đúng `HE_SO_DONG_PDF`:
   * 240 = một dòng, 360 = một dòng rưỡi. `exact` là chiều cao TUYỆT ĐỐI (Word
   * cắt chữ tràn; ở đây không cắt — mất chữ hỏng nặng hơn một dòng cao hơn
   * khai báo, cùng lựa chọn `_cao_hang`/`HeightRule.ATLEAST` đã làm cho hàng
   * bảng). `atLeast` là SÀN, đúng nghĩa của nó.
   */
  const buocTheoNguon = (g: GianCachDoan | null): ((pt: number) => number) => {
    if (!g || g.dong <= 0) return buocMacDinh;
    if (g.luatDong === "exact" || g.luatDong === "exactly") return () => twipMm(g.dong);
    if (g.luatDong === "atLeast") return (pt) => Math.max(twipMm(g.dong), buocMacDinh(pt));
    return (pt) => pt * MM_MOI_PT * (g.dong / 240);
  };

  /**
   * Khung xếp chữ của MỘT đoạn: bề rộng, độ lệch dòng ĐẦU (`w:firstLine` trừ
   * `w:hanging`), chỗ đứng của đoạn so với mép trái cột chữ, và bước nhảy dòng.
   *
   * `xGoc` có mặt chỉ vì mốc tab: `w:tab/@w:pos` đo từ mép trái CỘT CHỮ, còn
   * con trỏ thì chạy trong lòng đoạn đã thụt lề — thiếu nó, một đoạn thụt 720
   * twip sẽ vẽ đường dẫn dài thêm đúng 720 twip.
   */
  type KhungDoan = { rong: number; lechDau: number; xGoc: number; buoc: (pt: number) => number };

  const khungMacDinh = (rong: number): KhungDoan => ({
    rong,
    lechDau: 0,
    xGoc: 0,
    buoc: buocMacDinh,
  });

  /** Khung của một dòng văn xuôi — `w:ind` nguồn THẮNG `thutLe` (px đo trên
   *  khung xem trước rồi quy ngược), cùng thứ tự ưu tiên `dongThanhParagraph`
   *  đặt cho `.docx`: hai tệp không được đọc hai con số khác nhau. */
  const khungCuaDong = (d: DongVanBan): KhungDoan => {
    const g = d.gianCach;
    const neoTrai = d.canhLe === "trai" || d.canhLe === "deu";
    const trai = g ? twipMm(g.trai) : !neoTrai || d.thutLe <= 0 ? 0 : d.thutLe / 3.78;
    const phai = g ? twipMm(g.phai) : 0;
    return {
      rong: Math.max(10, RONG_NOI_DUNG_PDF - trai - phai),
      lechDau: g ? twipMm(g.dauDong - g.treo) : 0,
      xGoc: trai,
      buoc: buocTheoNguon(g),
    };
  };

  /**
   * Xếp một dòng CÓ ĐỊNH DẠNG THEO ĐOẠN (2026-09-18) thành các dòng vẽ được,
   * và đo chiều cao cả khối — MỘT phép tính dùng cả cho luật phân trang
   * (`chieuCaoKeTiep`) lẫn cho lúc vẽ thật (`veManhChu`), cùng lý lẽ
   * `chieuCaoHangBang` đã theo.
   *
   * Không dùng được `splitTextToSize`: nó cắt theo MỘT font và MỘT cỡ chữ,
   * còn một dòng ở đây đổi được cả hai giữa chừng ("Họ và tên: NGUYỄN VĂN A"
   * với nửa sau in đậm). Xếp tham lam theo từng từ là thứ nhỏ nhất thay được.
   *
   * ponytail: một TỪ dài hơn cả bề rộng sẽ tràn lề thay vì bị cắt giữa từ
   * (`splitTextToSize` cắt). Nâng lên cắt-trong-từ nếu đo thấy biểu mẫu thật
   * có chuỗi dấu chấm điền liền không khoảng trắng đi kèm định dạng.
   *
   * Nhận `DoanChu[]` + cỡ MẶC ĐỊNH (thay vì cả một `DongVanBan`) để một Ô
   * BẢNG dùng lại được nguyên hàm này: ô có cỡ mặc định riêng
   * (`CO_CHU_BANG_PDF`) và không có `kieu` dòng nào cả.
   */
  const boCucDoan = (
    doan: DoanChu[],
    ptMacDinh: number,
    bo: KhungDoan,
  ): { dong: ManhChu[][]; cao: number } => {
    const manh: ManhChu[] = [];
    for (const o of doan) {
      const pt = o.coChu > 0 ? o.coChu / 2 : ptMacDinh;
      if (o.tab) {
        manh.push({ text: "", pt, kieu: "normal", gach: false, rong: 0, tab: o.tab });
        continue;
      }
      const kieu = kieuDoanPDF(o);
      pdf.setFont(HO_CHU_PDF, kieu);
      pdf.setFontSize(pt);
      for (const t of o.text.split(/(\s+)/)) {
        if (t !== "")
          manh.push({ text: t, pt, kieu, gach: o.gachChan, rong: pdf.getTextWidth(t), tab: null });
      }
    }
    const dong: ManhChu[][] = [];
    let hien: ManhChu[] = [];
    let rongHien = 0;
    const rongCua = () => (dong.length === 0 ? bo.rong - bo.lechDau : bo.rong);
    const gocCua = () => bo.xGoc + (dong.length === 0 ? bo.lechDau : 0);
    for (const m of manh) {
      if (m.tab) {
        // Con trỏ NHẢY tới mốc: quãng nhảy là khoảng cách từ chỗ nó đang đứng
        // (`rongHien`) tới mốc, đo trong CÙNG hệ quy chiếu — mốc tính từ mép
        // trái cột chữ, con trỏ tính từ mép trái đoạn, nên trừ `gocCua()`.
        // Mốc nằm ngoài bề rộng trang thì dừng ở mép phải: một biểu mẫu khổ
        // Letter (mốc 9360 twip) đặt trên trang A4 lề 30/20mm vẫn phải ra một
        // dòng điền chạm lề, không phải một đường tràn khỏi giấy.
        m.rong = Math.max(0, Math.min(twipMm(m.tab.pos) - gocCua(), rongCua()) - rongHien);
        hien.push(m);
        rongHien += m.rong;
        continue;
      }
      const trang = /^\s+$/.test(m.text);
      if (trang && hien.length === 0) continue; // không mở một dòng bằng khoảng trắng
      if (!trang && hien.length > 0 && rongHien + m.rong > rongCua()) {
        while (hien.length > 0 && /^\s+$/.test(hien[hien.length - 1]!.text)) hien.pop();
        dong.push(hien);
        hien = [];
        rongHien = 0;
      }
      hien.push(m);
      rongHien += m.rong;
    }
    if (hien.length > 0) dong.push(hien);
    // Cỡ chữ LỚN NHẤT của dòng quyết định bước nhảy: một dòng trộn 13pt với
    // 16pt mà nhảy theo 13pt thì chữ dòng sau đè lên chữ dòng trước.
    const cao = dong.reduce((s, l) => s + bo.buoc(Math.max(...l.map((m) => m.pt))), 0);
    return { dong, cao };
  };

  /**
   * Vẽ các dòng `boCucDoan` đã xếp, bắt đầu từ `yBatDau`, trả về `y` sau khi
   * vẽ xong.
   *
   * Trả về thay vì đẩy `y` của closure: một Ô BẢNG vẽ tại một `y` RIÊNG (mép
   * trên hàng cộng đệm ô) và KHÔNG được đẩy con trỏ chung — mọi ô cùng hàng
   * bắt đầu ở cùng một chỗ, và chính `veMotHangBang` mới cộng chiều cao hàng.
   */
  /**
   * Đường DẪN của một mốc tab (`w:leader`) — thứ vẽ ra dòng "…………" để điền tay.
   *
   * jsPDF không có khái niệm "một hàng dấu chấm", nên vẽ bằng đúng thứ nó có:
   * một đường NÉT ĐỨT trên đường chân chữ, mắt lưới theo từng kiểu dẫn. Vẽ
   * bằng chuỗi ký tự "." thay vì một đường sẽ nhét chữ KLAW tự bịa vào tệp —
   * và `toanVan`/`docNoiDungTuDOM` sẽ đọc lại chính những dấu chấm đó thành
   * nội dung văn bản.
   */
  const veDanTab = (m: ManhChu, x: number, day: number) => {
    if (!m.tab || !m.tab.leader || m.rong <= 0) return;
    const net = m.pt * MM_MOI_PT * 0.06;
    const duoi = day + m.pt * MM_MOI_PT * 0.12;
    pdf.setLineWidth(net);
    pdf.setLineDashPattern(
      m.tab.leader === "underscore"
        ? []
        : m.tab.leader === "hyphen"
          ? [net * 6, net * 4]
          : [net, net * 3],
      0,
    );
    pdf.line(x, duoi, x + m.rong, duoi);
    pdf.setLineDashPattern([], 0);
  };

  const veManhChu = (
    dong: ManhChu[][],
    xTrai: number,
    bo: KhungDoan,
    // `justify` KHÔNG có nhánh riêng ở đây và vẽ như `left` — xem chú thích
    // trong thân hàm.
    huong: "left" | "center" | "right" | "justify",
    yBatDau: number,
  ): number => {
    const netCu = pdf.getLineWidth();
    let yy = yBatDau;
    dong.forEach((l, li) => {
      const rongDong = l.reduce((s, m) => s + m.rong, 0);
      // Dòng ĐẦU hẹp hơn và bắt đầu lệch đi đúng `w:firstLine` trừ
      // `w:hanging` — hai thuộc tính loại trừ nhau, nên một hiệu là đủ.
      const lech = li === 0 ? bo.lechDau : 0;
      const rongKhung = bo.rong - lech;
      const xKhung = xTrai + lech;
      const ptMax = Math.max(...l.map((m) => m.pt));
      const day = yy + ptMax * MM_MOI_PT;
      // ponytail: `justify` vẽ như `left` ở ĐƯỜNG CÓ ĐỊNH DẠNG. Căn đều thật
      // phải giãn khoảng trắng GIỮA TỪ, mà ở đây một dòng đã là chuỗi mảnh
      // `ManhChu` đo sẵn bề rộng, khoảng trắng nằm BÊN TRONG `m.text` — giãn
      // được thì phải xé lại mảnh theo từ và đo lại từng mảnh. Chênh lệch chỉ
      // thấy ở đoạn NHIỀU dòng (dòng cuối của một đoạn căn đều vốn đã căn
      // trái), nên trần này được chấp nhận. Nâng khi đo thấy nó cắn thật.
      let x = xKhung;
      if (huong === "center") x = xKhung + (rongKhung - rongDong) / 2;
      else if (huong === "right") x = xKhung + rongKhung - rongDong;
      for (const m of l) {
        if (m.tab) {
          veDanTab(m, x, day);
          x += m.rong;
          continue;
        }
        pdf.setFont(HO_CHU_PDF, m.kieu);
        pdf.setFontSize(m.pt);
        pdf.text(m.text, x, day);
        // Gạch chân tự vẽ: jsPDF không có thuộc tính gạch chân nào cả.
        if (m.gach && m.text.trim() !== "") {
          const duoi = day + m.pt * MM_MOI_PT * 0.12;
          pdf.setLineWidth(m.pt * MM_MOI_PT * 0.06);
          pdf.line(x, duoi, x + m.rong, duoi);
        }
        x += m.rong;
      }
      yy += bo.buoc(ptMax);
    });
    // Trả nét về như cũ: `veBang` vẽ khung ô bằng `rect` với nét MẶC ĐỊNH, và
    // một dòng gạch chân đứng trước không được làm dày khung của bảng sau nó.
    pdf.setLineWidth(netCu);
    return yy;
  };

  /** Khối đứng NGAY SAU một vị trí trong `khoi`, hoặc khối ký nếu đó là khối
   * cuối, hoặc không còn gì. Luật mồ côi đo khối THẬT này, không đoán. */
  type KhoiKeTiep = KhoiVanBan | { kind: "oKy" } | null;

  /**
   * Chiều cao (mm) khối kế tiếp SẼ chiếm khi nó bắt đầu vẽ — dùng làm phần
   * "phải còn chỗ" của luật mồ côi (R3 fix round 1 #1). Trước bản vá này,
   * buffer là MỘT hằng số cỡ một dòng "thuong" bất kể khối sau là gì; một
   * tiêu đề đứng ngay trước một BẢNG (bình thường với biểu mẫu này — tiêu đề
   * mục dẫn thẳng vào bảng chấm điểm, không câu dẫn) thì buffer đó nhỏ hơn
   * hàng tiêu đề thật của bảng, nên tiêu đề vẫn có thể bị bỏ lại một mình ở
   * cuối trang trong khi cả bảng (kể cả hàng tiêu đề của nó) nhảy sang trang
   * sau theo luật phân trang RIÊNG của `veBang`.
   *
   * Với bảng, chỉ cần đo hàng ĐẦU (tiêu đề bảng): nếu tiêu đề mục + hàng tiêu
   * đề bảng vừa trang thì đã đủ — phần còn lại của bảng (nếu tràn) tự lặp
   * lại tiêu đề của CHÍNH nó (`veBang` ở trên), không cần luật mồ côi lo tới
   * tận hàng dữ liệu cuối.
   */
  const chieuCaoKeTiep = (ketiep: KhoiKeTiep): number => {
    if (ketiep === null) return 0;
    if (ketiep.kind === "oKy") return caoKhoiKy;
    if (ketiep.kind === "dong") {
      const d = ketiep.d;
      const bo = khungCuaDong(d);
      // Khoảng trống TRÊN đoạn (`w:spacing/@w:before`) là chỗ nó chiếm ngay
      // khi bắt đầu vẽ, nên luật mồ côi phải đo cả nó: một tiêu đề đứng trước
      // một đoạn khai `before` lớn vẫn bị bỏ lại cuối trang nếu bỏ qua.
      const truoc = d.gianCach ? twipMm(Math.max(0, d.gianCach.truoc)) : 0;
      if (d.doan.length > 0) return truoc + boCucDoan(d.doan, coChuPt(d.kieu), bo).cao;
      pdf.setFont(HO_CHU_PDF, kieuChuPDF(d));
      pdf.setFontSize(coChuPt(d.kieu));
      const dong = pdf.splitTextToSize(d.text, bo.rong - bo.lechDau) as string[];
      return truoc + dong.length * bo.buoc(coChuPt(d.kieu));
    }
    // Ảnh là một khối KHÔNG chẻ được: chiều cao của nó là cả tấm ảnh, nên
    // luật mồ côi đo đúng con số ấy — một tiêu đề đứng trước một logo không
    // vừa trang phải đi cùng nó sang trang sau.
    if (ketiep.kind === "anh") return emuMm(ketiep.a.cao);
    const soCotTieuDe = soCotThat(ketiep.hang, ketiep.tiLe);
    if (soCotTieuDe === 0) return 0;
    return chieuCaoHangBang(
      ketiep.hang[0]!,
      soCotTieuDe,
      ketiep.vien,
      rongCotPDF(ketiep.tiLe, soCotTieuDe, RONG_NOI_DUNG_PDF),
      ketiep.nhip[0],
      ketiep.cao[0],
      ketiep.chuO[0],
      ketiep.caoLuat?.[0],
    );
  };

  /** Một dòng (đoạn/tiêu đề) — trả về số trang đã vẽ lên. */
  const veDong = (d: DongVanBan, ketiep: KhoiKeTiep): number => {
    const laTieuDe = d.kieu === "tieuDe" || d.kieu === "dieu";
    // Đo khối kế tiếp TRƯỚC khi đặt font/cỡ chữ cho chính dòng này — đo có
    // thể tạm đổi font (bảng dùng 12pt, đoạn kế tiếp dùng cỡ của riêng nó).
    const buffer = laTieuDe ? chieuCaoKeTiep(ketiep) : 0;
    const g = d.gianCach;
    const bo = khungCuaDong(d);
    const truoc = g ? twipMm(Math.max(0, g.truoc)) : 0;
    // Nguồn khai nhịp thì nguồn THẮNG, kể cả khi nó khai 0 — `SAU_DOAN_PDF`
    // (6pt) là thể thức của một bản thảo KLAW TỰ soạn, không phải một câu trả
    // lời về tài liệu của khách. Cùng luật `dongThanhParagraph` đặt cho
    // `.docx`, nếu không hai tệp cùng nguồn lại giãn khác nhau.
    const sau = g ? twipMm(Math.max(0, g.sau)) : SAU_DOAN_PDF;

    // Dòng có định dạng THEO ĐOẠN (2026-09-18), hoặc có thụt lề dòng ĐẦU: xếp
    // và vẽ theo từng mảnh, vì `splitTextToSize` bên dưới chỉ cắt được theo
    // MỘT font, MỘT cỡ chữ và MỘT bề rộng. Dòng đồng nhất không thụt dòng đầu
    // đi nguyên đường cũ, không đổi một mm nào.
    if (d.doan.length > 0 || bo.lechDau !== 0) {
      const doan: DoanChu[] =
        d.doan.length > 0
          ? d.doan
          : [
              {
                text: d.text,
                inDam: d.inDam,
                inNghieng: d.inNghieng,
                gachChan: false,
                coChu: 0,
                phong: "",
                tab: null,
              },
            ];
      const xep = boCucDoan(doan, coChuPt(d.kieu), bo);
      if (!conCho(truoc + xep.cao + buffer)) trangMoi();
      y += truoc;
      y = veManhChu(xep.dong, LE_PDF.trai + bo.xGoc, bo, canhLeThanhHuong(d.canhLe), y);
      y += sau;
      return trang;
    }

    pdf.setFont(HO_CHU_PDF, kieuChuPDF(d));
    pdf.setFontSize(coChuPt(d.kieu));
    const dong = pdf.splitTextToSize(d.text, bo.rong) as string[];
    const cao = dong.length * bo.buoc(coChuPt(d.kieu));

    // Luật mồ côi (R3): một tiêu đề (kieu tieuDe/dieu) không bao giờ là thứ
    // CUỐI CÙNG trên trang — phải còn đủ chỗ cho tiêu đề VÀ khối kế tiếp mới
    // vẽ tại đây; không thì sang trang mới rồi vẽ tiêu đề ở đầu trang đó.
    if (!conCho(truoc + cao + buffer)) trangMoi();
    y += truoc;

    // `x`/`align` theo CanLe (Phase 9 U5): trái neo mép trái + thụt lề, giữa
    // neo tâm KHUNG ĐOẠN (đã trừ thụt lề hai bên), phải neo MÉP PHẢI của khung
    // (jsPDF đặt chữ kết thúc tại `x` khi `align: "right"`) — cùng ba giá trị
    // `.docx` (`dongThanhParagraph`) đã dùng.
    // `deu` rơi vào nhánh cuối cùng với `trai`: jsPDF căn đều TỪ `x` sang phải
    // theo `maxWidth`, nên mốc neo của nó là mép TRÁI, giống hệt căn trái.
    const x =
      d.canhLe === "giua"
        ? LE_PDF.trai + bo.xGoc + bo.rong / 2
        : d.canhLe === "phai"
          ? LE_PDF.trai + bo.xGoc + bo.rong
          : LE_PDF.trai + bo.xGoc;
    const align = canhLeThanhHuong(d.canhLe);
    pdf.text(dong, x, y + coChuPt(d.kieu) * MM_MOI_PT, {
      align,
      maxWidth: bo.rong,
      // Hệ số nhảy dòng của jsPDF là `bước / (cỡ chữ × mm mỗi pt)` — quy
      // ngược đúng công thức `setFontSize` dùng, để bước nhảy BÊN TRONG một
      // lệnh `text()` nhiều dòng khớp với `cao` vừa cộng ở trên.
      lineHeightFactor: bo.buoc(coChuPt(d.kieu)) / (coChuPt(d.kieu) * MM_MOI_PT),
    });
    y += cao + sau;
    return trang;
  };

  const trangCuaKhoi: number[] = noiDung.khoi.map((k, i) => {
    const ketiep: KhoiKeTiep =
      i < noiDung.khoi.length - 1 ? noiDung.khoi[i + 1]! : soCotKy > 0 ? { kind: "oKy" } : null;
    return k.kind === "dong"
      ? veDong(k.d, ketiep)
      : k.kind === "anh"
        ? veAnh(k.a)
        : veBang(
            k.hang,
            k.nhip,
            k.tiLe,
            k.vien,
            k.cao,
            k.canLeO,
            k.chuO,
            k.vienO ?? [],
            k.caoLuat ?? [],
          );
  });

  let trangCuaKy: number | null = null;
  if (soCotKy > 0) {
    // Luật khối ký nguyên vẹn (R3): không đủ chỗ cho CẢ khối trên trang hiện
    // tại thì sang trang MỚI rồi vẽ trọn — không chẻ khối ký như một khối
    // văn bản thường.
    if (!conCho(caoKhoiKy)) trangMoi();
    trangCuaKy = trang;

    const yBatDau = y;
    noiDung.oKy.forEach((cot, ci) => {
      let yc = yBatDau;
      const xTam = LE_PDF.trai + rongCotKy * ci + rongCotKy / 2;
      cot.forEach((d, i) => {
        pdf.setFont(HO_CHU_PDF, kieuChuPDF(d));
        pdf.setFontSize(coChuPt(d.kieu));
        if (i === cot.length - 1) yc += KHOANG_KY;
        const dong = pdf.splitTextToSize(d.text, rongCotKy) as string[];
        pdf.text(dong, xTam, yc + coChuPt(d.kieu) * MM_MOI_PT, {
          align: "center",
          maxWidth: rongCotKy,
          lineHeightFactor: HE_SO_DONG_PDF,
        });
        yc += dong.length * caoDongPt(d.kieu);
        if (i < cot.length - 1) yc += SAU_DONG_KY;
      });
    });
    y = yBatDau + caoKhoiKy;
  }

  return { pdf, trangCuaKhoi, trangCuaKy };
}

const TEP_PHONG_CHU_PDF = {
  thuong: "/fonts/source-serif-4-pdf-regular.ttf",
  dam: "/fonts/source-serif-4-pdf-bold.ttf",
};

/** `ArrayBuffer` → base64 — định dạng `addFileToVFS` của jsPDF đòi (nó tự
 * `atob()` chuỗi này rồi mới đọc TTF, xem module `ttfsupport` trong `jspdf`). */
function base64TuBytes(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let nhiPhan = "";
  for (const b of bytes) nhiPhan += String.fromCharCode(b);
  return btoa(nhiPhan);
}

/** Tải hai tệp TTF nhúng (Phase 5 R2) từ `public/fonts/` — CHỈ gọi bên trong
 * `xuatPDF`, không import tĩnh, để hai tệp ~105KB này không vào bundle chính. */
async function taiPhongChuPDF(): Promise<PhongChuPDF> {
  const [thuong, dam] = await Promise.all([
    fetch(TEP_PHONG_CHU_PDF.thuong).then((r) => r.arrayBuffer()),
    fetch(TEP_PHONG_CHU_PDF.dam).then((r) => r.arrayBuffer()),
  ]);
  return { thuong: base64TuBytes(thuong), dam: base64TuBytes(dam) };
}

/**
 * Xuất tệp PDF khổ A4 nhiều trang có LỚP CHỮ THẬT (Phase 5) — chọn/copy/tìm
 * được, đọc được bằng trình đọc màn hình. Không còn chụp ảnh khung xem trước
 * (`html2canvas`) và không còn trần trang giả — một tài liệu dài ra bao
 * nhiêu trang thì cần bấy nhiêu (R3).
 */
export async function xuatPDF(sheet: HTMLElement, tieuDe: string) {
  const noiDung = docNoiDungTuDOM(sheet);
  const phongChu = await taiPhongChuPDF();
  const { pdf } = await noiDungThanhPDF(noiDung, tieuDe, phongChu);
  pdf.setProperties({ title: tieuDe, creator: "KLAW" });
  taiBlob(pdf.output("blob"), `${tenTepAnToan(tieuDe)}.pdf`);
}

/** Toàn văn dạng text thuần, dùng cho chức năng sao chép. */
export function toanVan(sheet: HTMLElement) {
  const { khoi, oKy } = docNoiDungTuDOM(sheet);
  const than = khoi
    // Ảnh không góp CHỮ nào: `toanVan` phục vụ nút "sao chép", và một dòng
    // "[ảnh]" sẽ là chữ KLAW tự bịa nằm giữa văn bản người dùng dán đi.
    .map((k) =>
      k.kind === "dong"
        ? k.d.text
        : k.kind === "anh"
          ? ""
          : k.hang.map((o) => o.join(" | ")).join("\n"),
    )
    .filter((t) => t !== "")
    .join("\n");
  const ky = oKy.map((cot) => cot.map((d) => d.text).join("\n")).join("\n\n");
  return ky ? `${than}\n\n${ky}\n` : `${than}\n`;
}
