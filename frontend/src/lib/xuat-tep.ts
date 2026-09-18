/**
 * Xuất bản thảo hợp đồng ra tệp thật (.docx / .pdf) từ khung xem trước A4.
 * Toàn bộ xử lý diễn ra trên trình duyệt — không gửi nội dung bản thảo lên máy chủ.
 */
import type { BanThao, CauTruc } from "./klaw";

export type KieuDong = "quocHieu" | "tieuDe" | "soHieu" | "dieu" | "thuong";

/** `trai` (mặc định) | `giua` | `phai` (Phase 9 U5) — căn lề THẬT đọc từ CSS
 *  `text-align` đã áp trên khung A4 (`docDong`), không phải suy đoán ở đây. */
export type CanLe = "trai" | "giua" | "phai";

export type DongVanBan = {
  text: string;
  kieu: KieuDong;
  canhLe: CanLe;
  inDam: boolean;
  inNghieng: boolean;
  thutLe: number;
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
 */
export type BangThat = {
  hang: string[][];
  nhip: number[][];
  tiLe: number[];
  vien: boolean;
  cao: number[];
  canLeO: CanLe[][];
};

export type KhoiVanBan = { kind: "dong"; d: DongVanBan } | ({ kind: "bang" } & BangThat);

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
};

/**
 * MỘT khối nội dung của một mục, theo ĐÚNG thứ tự tài liệu (Phase 8 R1 —
 * thay "một mục là văn xuôi HOẶC bảng" của Phase 7: giờ một mục là một MẢNG
 * khối, ví dụ câu dẫn / bảng / câu kết, ba khối riêng chứ không nén về hai
 * trường cố định).
 */
export type KhoiMuc =
  { kind: "vanXuoi"; noiDung: string; canhLe: CanLe } | ({ kind: "bang" } & BangThat);

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

const CAN_LE_HOP_LE = new Set(["trai", "giua", "phai"]);

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
    cao?: unknown;
    can_le_o?: unknown;
  };
  const noiDung = typeof o.noi_dung === "string" ? o.noi_dung : "";
  const bang = bangHopLe(o.bang);
  const ra: KhoiMuc[] = [];
  if (noiDung !== "") ra.push({ kind: "vanXuoi", noiDung, canhLe: canLeHopLe(o.can_le) });
  if (bang)
    ra.push({
      kind: "bang",
      hang: bang,
      nhip: nhipHopLe(o.nhip, bang),
      tiLe: tiLeHopLe(o.ti_le),
      vien: vienHopLe(o.vien),
      cao: caoHopLe(o.cao, bang),
      canLeO: canLeOHopLe(o.can_le_o, bang),
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
  if (noiDung !== "") ra.push({ kind: "vanXuoi", noiDung, canhLe: "trai" });
  // Chưa từng có `nhip`/`ti_le` ở hình dạng CŨ này (Phase 7 trở về trước) —
  // `coSpanHang` suy đoán cột như trước Phase 11, không phải một cải thiện
  // ngầm cho dữ liệu đã lưu trước khi hai trường này tồn tại.
  if (bang)
    ra.push({ kind: "bang", hang: bang, nhip: [], tiLe: [], vien: true, cao: [], canLeO: [] });
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
      canCu: m.can_cu || null,
    };
  });
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

/**
 * Tiêu đề này có xuất hiện lại NHƯ CHỮ THÂN BÀI ở một khối văn xuôi nào
 * không (Phase 11 R4) — dùng để quyết định `XemTruocA4` có in `<h1>{tieuDe}`
 * lên trang hay không.
 *
 * Một bản thảo TÁI HIỆN nguyên văn một biểu mẫu thì chính biểu mẫu đó đã in
 * tiêu đề của nó ra như một dòng thân bài (quốc hiệu/tên biểu mẫu…) — `<h1>`
 * của KLAW khi đó là MỘT BẢN SAO thứ hai của cùng một dòng, không phải chữ
 * thật thứ hai. So khớp từng DÒNG của một khối (một khối có thể gộp nhiều
 * dòng nguồn bằng `\n`, ví dụ quốc hiệu + tiêu ngữ + tên biểu mẫu), và đòi
 * MỘT dòng đó BẰNG HẲN tiêu đề — không phải "tiêu đề nằm ở đâu đó trong
 * khối" (Phase 11 fix round 1): đo được thật trên BM.M05, câu "(Kèm theo Giấy
 * tiếp nhận thực hành/thực tập số … ngày … tháng … năm …)" CHỨA đúng cụm chữ
 * của tiêu đề như một cách NHẮC TỚI tài liệu, không phải IN LẠI tiêu đề —
 * `.includes()` cũ coi câu này là "tiêu đề đã in", ẩn oan `<h1>` trên một
 * form mà tiêu đề THẬT SỰ chưa từng xuất hiện ở đâu khác. Đòi bằng hẳn từng
 * dòng vẫn khớp đúng ca joined-by-`\n` (dòng đó, sau khi tách, bằng hẳn tiêu
 * đề), chỉ không còn khớp một CÂU KHÁC tình cờ chứa cùng cụm chữ.
 *
 * Một bản thảo KLAW SOẠN TỪ ĐẦU (không tái hiện tài liệu nào) không có lý do
 * gì để lặp lại tiêu đề trong thân bài — hàm này trả `false`, và `XemTruocA4`
 * GIỮ `<h1>` để trang không trở thành vô đề, đúng cảnh báo của brief.
 */
export function tieuDeDaXuatHienTrongThan(tieuDe: string, muc: Muc[]): boolean {
  const t = tieuDe.trim().toLocaleLowerCase("vi-VN");
  if (!t) return false;
  return muc.some((m) =>
    m.khoi.some(
      (k) =>
        k.kind === "vanXuoi" &&
        k.noiDung.split("\n").some((dong) => chuanHoa(dong).toLocaleLowerCase("vi-VN") === t),
    ),
  );
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
export function canhLeThanhHuong(canhLe: CanLe): "left" | "center" | "right" {
  return canhLe === "giua" ? "center" : canhLe === "phai" ? "right" : "left";
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
  return "trai";
}

/**
 * Đọc MỘT bảng đã render thành hàng×ô, nguyên văn từng ô (đã chuẩn hoá khoảng
 * trắng) — hàng đầu tiên là hàng tiêu đề, đúng quy ước `bang` phía máy chủ
 * (`hieu_tai_lieu.schema_hieu`, Phase 7 R1); không cần phân biệt `<th>`/`<td>`.
 *
 * Cũng đọc lại `nhip` (thuộc tính `colSpan` đã render, Phase 11 R6), `tiLe`
 * (`data-ti-le` trên mỗi `<col>` của `<colgroup>`, Phase 11 R1), `vien`
 * (`data-vien` trên chính `<table>`), `cao` (`data-cao` trên mỗi `<tr>`) và
 * `canLeO` (`data-can-le` trên mỗi ô) — CÙNG một bảng đã vẽ trên màn hình,
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
    }>;
  }>;
}): BangThat {
  const hang: string[][] = [];
  const nhip: number[][] = [];
  const cao: number[] = [];
  const canLeO: CanLe[][] = [];
  for (const tr of Array.from(bang.querySelectorAll("tr"))) {
    const o = Array.from(tr.querySelectorAll("th, td"));
    hang.push(o.map((c) => chuanHoa(c.textContent ?? "")));
    nhip.push(o.map((c) => (typeof c.colSpan === "number" && c.colSpan > 0 ? c.colSpan : 1)));
    canLeO.push(o.map((c) => canLeHopLe(c.getAttribute("data-can-le"))));
    const twip = Number(tr.getAttribute("data-cao"));
    cao.push(Number.isFinite(twip) && twip > 0 ? twip : 0);
  }
  const tiLe = Array.from(bang.querySelectorAll("col"))
    .map((c) => Number(c.getAttribute("data-ti-le")))
    .filter((v) => Number.isFinite(v) && v > 0);
  // `data-vien="khong"` là dấu DUY NHẤT của bảng không viền; mọi bảng khác
  // (kể cả bảng vẽ trước bản vá này, không có thuộc tính nào) vẫn có viền.
  return { hang, nhip, tiLe, vien: bang.getAttribute("data-vien") !== "khong", cao, canLeO };
}

/** Đọc một thẻ thành dòng có định dạng, lấy đậm/nghiêng từ chính CSS đang áp. */
function docDong(el: HTMLElement): DongVanBan {
  const text = chuanHoa(el.textContent ?? "");
  const cs = getComputedStyle(el);
  const laDieu = el.classList.contains("dieu-head");
  return {
    text: cs.textTransform === "uppercase" ? text.toLocaleUpperCase("vi-VN") : text,
    kieu:
      el.tagName === "H1" ? "tieuDe" : laDieu ? "dieu" : /^Số:/.test(text) ? "soHieu" : "thuong",
    canhLe: canhLeTuStyle(el),
    inDam: Number(cs.fontWeight) >= 600 || laDieu,
    inNghieng: cs.fontStyle === "italic",
    thutLe: Math.round(parseFloat(cs.marginLeft || "0")),
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
  const blocks = sheet.querySelectorAll<HTMLElement>("h1, p, table");
  for (const el of Array.from(blocks)) {
    if (boQuaKhiXuat(el)) continue;
    if (khoiKy && khoiKy.contains(el)) continue;
    if (el.tagName === "TABLE") {
      const bang = docBangTuPhanTu(el);
      if (bang.hang.length > 0) khoi.push({ kind: "bang", ...bang });
      continue;
    }
    const d = docDong(el);
    if (d.text === "") continue;
    khoi.push({ kind: "dong", d });
  }

  return { khoi, oKy };
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
  const net = coVien
    ? { style: BorderStyle.SINGLE, size: 4, color: "999999" }
    : { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const canhLeDocx = {
    left: AlignmentType.LEFT,
    center: AlignmentType.CENTER,
    right: AlignmentType.RIGHT,
  } as const;
  const soCotTieuDe = soCotThat(hang, tiLe);
  const tiLeVe = tiLeCotVe(tiLe, soCotTieuDe);
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: net,
      bottom: net,
      left: net,
      right: net,
      insideHorizontal: net,
      insideVertical: net,
    },
    rows: hang.map((o, hi) => {
      const span = nhipHangVe(o, nhip[hi], soCotTieuDe);
      const laTieuDe = coVien && hi === 0;
      const twip = cao[hi] ?? 0;
      let cotDauTien = 0;
      return new TableRow({
        // `HeightRule.ATLEAST`, không `EXACT`: nguồn có thể khai `exact` (Word
        // cắt chữ tràn), nhưng cắt mất chữ của người dùng hỏng tệ hơn một hàng
        // cao hơn khai báo vài milimét — cùng lựa chọn `doc_tai_lieu._cao_hang`.
        ...(twip > 0 ? { height: { value: twip, rule: HeightRule.ATLEAST } } : {}),
        children: o.map((c, oi) => {
          const cot = span[oi] ?? 1;
          const rongO = tiLeVe.slice(cotDauTien, cotDauTien + cot).reduce((a, b) => a + b, 0);
          cotDauTien += cot;
          return new TableCell({
            width: { size: rongO, type: WidthType.PERCENTAGE },
            borders: { top: net, bottom: net, left: net, right: net },
            // `exactOptionalPropertyTypes`: `shading`/`columnSpan` phải VẮNG
            // MẶT khi không dùng, không gán `undefined` — spread có điều
            // kiện, không gán.
            ...(laTieuDe ? { shading: { fill: "F0F0F0" } } : {}),
            ...(cot > 1 ? { columnSpan: cot } : {}),
            children: [
              new Paragraph({
                alignment: canhLeDocx[canhLeThanhHuong(canLeO[hi]?.[oi] ?? "trai")],
                children: [
                  new TextRun({ text: c, bold: laTieuDe, font: "Times New Roman", size: 24 }),
                ],
              }),
            ],
          });
        }),
      });
    }),
  });
}

/** Xuất tệp Word (.docx) đúng thể thức: Times New Roman 13pt, lề 2cm/3cm. */
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

  const { khoi, oKy } = docNoiDungTuDOM(sheet);

  const CANH_LE_DOCX = {
    left: AlignmentType.LEFT,
    center: AlignmentType.CENTER,
    right: AlignmentType.RIGHT,
  } as const;
  const para = (d: DongVanBan) =>
    new Paragraph({
      alignment: CANH_LE_DOCX[canhLeThanhHuong(d.canhLe)],
      ...(d.kieu === "tieuDe" ? { heading: HeadingLevel.HEADING_1 } : {}),
      spacing: { after: 120, line: 312 },
      ...(d.thutLe > 0 ? { indent: { left: convertMillimetersToTwip(d.thutLe / 3.78) } } : {}),
      children: [
        new TextRun({
          text: d.text,
          bold: d.inDam,
          italics: d.inNghieng,
          size: d.kieu === "tieuDe" ? 32 : d.kieu === "dieu" ? 28 : 26,
          font: "Times New Roman",
        }),
      ],
    });

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
    khoi.map((k) =>
      k.kind === "dong"
        ? Promise.resolve(para(k.d))
        : bangThanhTable(k.hang, k.nhip, k.tiLe, k.vien, k.cao, k.canLeO),
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
          page: {
            margin: {
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

/** Lề trang PDF — khớp NGUYÊN `xuatWord` (trên/dưới 20mm, trái 30mm, phải
 * 20mm): R4 nói hai tệp chỉ nên khác nhau ở font, không khác ở bố cục. */
const LE_PDF = { tren: 20, duoi: 20, trai: 30, phai: 20 };
const RONG_A4 = 210;
const CAO_A4 = 297;
const RONG_NOI_DUNG_PDF = RONG_A4 - LE_PDF.trai - LE_PDF.phai;

/** % mỗi cột (đã qua `tiLeCotVe`, chia đều khi rỗng) → bề rộng mm trong PDF
 * (Phase 11 R1) — MỘT chỗ quy đổi, dùng cho cả chiều cao đo và hình vẽ. */
function rongCotPDF(tiLe: number[], soCot: number): number[] {
  return tiLeCotVe(tiLe, soCot).map((p) => (p / 100) * RONG_NOI_DUNG_PDF);
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
  /** twip (`w:trHeight`) → mm. 1 twip = 1/20 pt. */
  const caoKhaiMm = (twip: number | undefined) => ((twip ?? 0) / 20) * MM_MOI_PT;

  /**
   * Chiều cao (mm) MỘT hàng bảng sẽ chiếm — đo THẬT bằng `splitTextToSize`
   * trên đúng font/cỡ chữ hàng đó dùng, không phải một hằng số ước lượng.
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
  ): number => {
    const span = nhipHangVe(o, nhipHang, soCotTieuDe);
    pdf.setFont(HO_CHU_PDF, laTieuDe ? "bold" : "normal");
    pdf.setFontSize(CO_CHU_BANG_PDF);
    let cotDauTien = 0;
    const soDongToiDa = o.reduce((max, c, oi) => {
      const cot = span[oi] ?? 1;
      const rongO = rongCotMm.slice(cotDauTien, cotDauTien + cot).reduce((a, b) => a + b, 0);
      cotDauTien += cot;
      const dong = pdf.splitTextToSize(c, rongO - 2 * DEM_O_PDF) as string[];
      return Math.max(max, dong.length);
    }, 1);
    // Chiều cao khai báo của hàng là SÀN, không phải giá trị thay thế: một
    // hàng ký khai 1499 twip cần đúng chỗ trống đó, còn một hàng khai thấp
    // hơn chữ của nó vẫn phải đủ cao để không cắt chữ.
    return Math.max(
      soDongToiDa * (CO_CHU_BANG_PDF * MM_MOI_PT * HE_SO_DONG_PDF) + 2 * DEM_O_PDF,
      caoKhaiMm(caoKhai),
    );
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
  ) => {
    // `nhipHangVe` — CÙNG luật ô gộp dùng cho màn hình (`XemTruocA4`) và
    // `.docx` (`bangThanhTable`): nhịp THẬT khi bảng có khai lưới nguồn (Phase
    // 11 R6), suy từ số ô khi không. Ba nơi vẽ bảng, MỘT luật đặt cột.
    const span = nhipHangVe(o, nhipHang, soCotTieuDe);
    pdf.setFont(HO_CHU_PDF, laTieuDe ? "bold" : "normal");
    pdf.setFontSize(CO_CHU_BANG_PDF);
    const rongO_: number[] = [];
    {
      let cotDauTien = 0;
      for (const cot of o.map((_, oi) => span[oi] ?? 1)) {
        rongO_.push(rongCotMm.slice(cotDauTien, cotDauTien + cot).reduce((a, b) => a + b, 0));
        cotDauTien += cot;
      }
    }
    const dongO = o.map((c, oi) => pdf.splitTextToSize(c, rongO_[oi]! - 2 * DEM_O_PDF) as string[]);
    const soDongToiDa = dongO.reduce((max, d) => Math.max(max, d.length), 1);
    const caoHang = Math.max(
      soDongToiDa * (CO_CHU_BANG_PDF * MM_MOI_PT * HE_SO_DONG_PDF) + 2 * DEM_O_PDF,
      caoKhaiMm(caoKhai),
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
      // sự thật đọc từ `w:tblBorders`.
      if (coVien) pdf.rect(xO, y, rongO, caoHang);
      const huong = canhLeThanhHuong(canLeHang[oi] ?? "trai");
      const xChu =
        huong === "center"
          ? xO + rongO / 2
          : huong === "right"
            ? xO + rongO - DEM_O_PDF
            : xO + DEM_O_PDF;
      pdf.text(dongO[oi]!, xChu, y + DEM_O_PDF + CO_CHU_BANG_PDF * MM_MOI_PT, {
        align: huong,
        maxWidth: rongO - 2 * DEM_O_PDF,
        lineHeightFactor: HE_SO_DONG_PDF,
      });
      xO += rongO;
    }
    y += caoHang;
  };

  /** Một bảng — trả về số trang đã BẮT ĐẦU vẽ (hàng tiêu đề của nó). */
  const veBang = (
    hang: string[][],
    nhip: number[][],
    tiLe: number[],
    coVien: boolean,
    cao: number[],
    canLeO: CanLe[][],
  ): number => {
    const soCotTieuDe = soCotThat(hang, tiLe);
    if (soCotTieuDe === 0) return trang;
    const rongCotMm = rongCotPDF(tiLe, soCotTieuDe);
    let trangBatDau: number | null = null;

    for (let hi = 0; hi < hang.length; hi++) {
      const o = hang[hi]!;
      // Hàng ĐẦU chỉ là hàng tiêu đề khi bảng CÓ viền — bảng bố cục không có
      // hàng tiêu đề của gì cả (xem `bangThanhTable`).
      const laTieuDe = coVien && hi === 0;
      const caoHang = chieuCaoHangBang(o, soCotTieuDe, laTieuDe, rongCotMm, nhip[hi], cao[hi]);
      if (!conCho(caoHang)) {
        trangMoi();
        // Chẻ giữa bảng (không phải ngay hàng tiêu đề) — lặp lại hàng tiêu
        // đề ở đầu trang mới trước khi vẽ tiếp hàng vừa bị đẩy sang. Bảng
        // không viền không lặp: nó không có hàng tiêu đề để mang theo, và
        // lặp lại hàng đầu của một khối ký là in tên người ký hai lần.
        if (hi > 0 && coVien)
          veMotHangBang(hang[0]!, soCotTieuDe, true, rongCotMm, nhip[0], coVien, cao[0], canLeO[0]);
      }
      trangBatDau ??= trang;
      veMotHangBang(o, soCotTieuDe, laTieuDe, rongCotMm, nhip[hi], coVien, cao[hi], canLeO[hi]);
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
      pdf.setFont(HO_CHU_PDF, kieuChuPDF(d));
      pdf.setFontSize(coChuPt(d.kieu));
      const thutLeMm = d.canhLe !== "trai" || d.thutLe <= 0 ? 0 : d.thutLe / 3.78;
      const dong = pdf.splitTextToSize(d.text, RONG_NOI_DUNG_PDF - thutLeMm) as string[];
      return dong.length * caoDongPt(d.kieu);
    }
    const soCotTieuDe = soCotThat(ketiep.hang, ketiep.tiLe);
    if (soCotTieuDe === 0) return 0;
    return chieuCaoHangBang(
      ketiep.hang[0]!,
      soCotTieuDe,
      ketiep.vien,
      rongCotPDF(ketiep.tiLe, soCotTieuDe),
      ketiep.nhip[0],
      ketiep.cao[0],
    );
  };

  /** Một dòng (đoạn/tiêu đề) — trả về số trang đã vẽ lên. */
  const veDong = (d: DongVanBan, ketiep: KhoiKeTiep): number => {
    const laTieuDe = d.kieu === "tieuDe" || d.kieu === "dieu";
    // Đo khối kế tiếp TRƯỚC khi đặt font/cỡ chữ cho chính dòng này — đo có
    // thể tạm đổi font (bảng dùng 12pt, đoạn kế tiếp dùng cỡ của riêng nó).
    const buffer = laTieuDe ? chieuCaoKeTiep(ketiep) : 0;

    pdf.setFont(HO_CHU_PDF, kieuChuPDF(d));
    pdf.setFontSize(coChuPt(d.kieu));
    const thutLeMm = d.canhLe !== "trai" || d.thutLe <= 0 ? 0 : d.thutLe / 3.78;
    const rong = RONG_NOI_DUNG_PDF - thutLeMm;
    const dong = pdf.splitTextToSize(d.text, rong) as string[];
    const cao = dong.length * caoDongPt(d.kieu);

    // Luật mồ côi (R3): một tiêu đề (kieu tieuDe/dieu) không bao giờ là thứ
    // CUỐI CÙNG trên trang — phải còn đủ chỗ cho tiêu đề VÀ khối kế tiếp mới
    // vẽ tại đây; không thì sang trang mới rồi vẽ tiêu đề ở đầu trang đó.
    if (!conCho(cao + buffer)) trangMoi();

    // `x`/`align` theo CanLe (Phase 9 U5): trái neo mép trái + thụt lề, giữa
    // neo tâm trang, phải neo MÉP PHẢI (jsPDF đặt chữ kết thúc tại `x` khi
    // `align: "right"`) — cùng ba giá trị `.docx` (`para`) đã dùng.
    const x =
      d.canhLe === "giua"
        ? LE_PDF.trai + RONG_NOI_DUNG_PDF / 2
        : d.canhLe === "phai"
          ? LE_PDF.trai + RONG_NOI_DUNG_PDF
          : LE_PDF.trai + thutLeMm;
    const align = canhLeThanhHuong(d.canhLe);
    pdf.text(dong, x, y + coChuPt(d.kieu) * MM_MOI_PT, {
      align,
      maxWidth: rong,
      lineHeightFactor: HE_SO_DONG_PDF,
    });
    y += cao + SAU_DOAN_PDF;
    return trang;
  };

  const trangCuaKhoi: number[] = noiDung.khoi.map((k, i) => {
    const ketiep: KhoiKeTiep =
      i < noiDung.khoi.length - 1 ? noiDung.khoi[i + 1]! : soCotKy > 0 ? { kind: "oKy" } : null;
    return k.kind === "dong"
      ? veDong(k.d, ketiep)
      : veBang(k.hang, k.nhip, k.tiLe, k.vien, k.cao, k.canLeO);
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
    .map((k) => (k.kind === "dong" ? k.d.text : k.hang.map((o) => o.join(" | ")).join("\n")))
    .join("\n");
  const ky = oKy.map((cot) => cot.map((d) => d.text).join("\n")).join("\n\n");
  return ky ? `${than}\n\n${ky}\n` : `${than}\n`;
}
