/**
 * Kiểu dữ liệu của hợp đồng KLAW ↔ FE.
 *
 * Chỉ HÌNH DẠNG dữ liệu và các type guard runtime kiểm hình dạng đó. Lời gọi
 * `fetch` nằm ở `lib/api.ts`; mọi lời gọi ở đó bắt buộc truyền một guard trong
 * file này, nên `invalid_response` là một nhánh có người thi hành chứ không
 * phải một dòng chú thích.
 *
 * Nguyên tắc giữ khi nối: KHÔNG thu hẹp một trường mà hợp đồng để `string`.
 * Backend thêm nhãn thứ bảy là chuyện bình thường; nó phải rơi vào nhánh an
 * toàn chứ không làm sập cả thẻ kết quả.
 */

import type { DuKien } from "./tai-lieu";

/** Mười `result_type` — mười cách hiển thị, không thương lượng. */
export type ResultType =
  | "answer"
  | "partial_coverage"
  | "abstain"
  | "out_of_scope"
  // Loại thứ NĂM: câu hỏi về CHÍNH TRỢ LÝ ("bạn làm được những gì"). Bốn
  // loại trên mô tả điều đã xảy ra với một lượt TRA CỨU; loại này nói rằng
  // câu hỏi không phải một lượt tra cứu. Trước bản này nó về `out_of_scope`
  // và người hỏi nhận "Câu hỏi này nằm ngoài phạm vi của hệ thống".
  | "gioi_thieu"
  // Loại thứ SÁU và thứ BẢY. Thiếu chúng ở đây là lỗi ĐO ĐƯỢC 2026-09-02: backend
  // trả `hoi_ve_kho` thành công (trace 8e32221d, 6.490ms, ghi vào `traces`) nhưng
  // `laTraCuuKetQua` từ chối cả response, và người hỏi nhận "Máy chủ trả về dữ
  // liệu không đúng hình dạng đã thoả thuận". `huong_dan_soan_thao` cũng thiếu,
  // nghĩa là đường bàn giao sang soạn thảo đã hỏng ở đây từ trước đó.
  | "huong_dan_soan_thao"
  | "hoi_ve_kho"
  // Loại thứ TÁM và thứ CHÍN (Task 19, soạn thảo trong chat, backend) — hai
  // nửa của một hội thoại soạn thảo: còn phải hỏi thêm dữ kiện, hoặc bản thảo
  // đã dựng xong. Màn hiển thị riêng cho chúng (`TheSoanThaoHoi`/`TheBanThao`)
  // dựng ở Task 21 — `laTraCuuKetQua` đã chấp nhận MỌI chuỗi không rỗng từ
  // trước nên hai loại này không làm sập response trong lúc chờ FE.
  | "soan_thao_hoi"
  | "ban_thao"
  // Loại thứ MƯỜI — lượt nói về TÀI LIỆU của người hỏi, không về kho luật.
  // Nó phải là một loại riêng vì bằng chứng của nó là một loại khác: `quan_sat`
  // neo vào một đơn vị văn bản trong tệp họ vừa gửi, KHÔNG phải trích dẫn điều
  // luật đã kiểm hai tầng. Trộn hai thứ vào `answer` là để giao diện hứa cho
  // một câu về tờ giấy của họ đúng thứ bảo đảm mà nó chỉ giữ được cho luật.
  | "tai_lieu";

/**
 * Sáu nhãn hiệu lực.
 *
 * Khai bằng union để lúc viết mã có gợi ý, NHƯNG mọi thành phần đọc nhãn đều
 * `switch` trên `string`: ràng buộc thật ở runtime chỉ là `string | null`.
 *
 * `bi_sua_doi` là nhãn mới (backend vừa dựng, `do_tin_cay: cao`) và KHÁC
 * `mot_phan_khong_xac_dinh` ở đúng một điểm, điểm quan trọng nhất: cái trước
 * biết đích danh điều khoản / văn bản / ngày sửa, cái sau nói thẳng là không
 * biết. Hai câu không được rút gọn thành một.
 */
export type HieuLuc =
  | "con_hieu_luc"
  // Chỉ với `as_of_date` trong QUÁ KHỨ mới gặp: văn bản có ngày hiệu lực SAU
  // ngày được hỏi. ĐO ĐƯỢC trên backend thật — hỏi mức lương tối thiểu tại
  // 2019-06-01 trả về ba trích dẫn mang nhãn này (293/2025, 74/2024, 90/2019).
  | "chua_hieu_luc"
  | "bi_thay_the"
  | "bi_sua_doi"
  | "het_hieu_luc"
  | "mot_phan_khong_xac_dinh"
  | "can_doi_chieu_tay";

/**
 * Trích dẫn đầy đủ (quyết định 2026-09-28): văn bản nào, ai ban hành, ngày nào,
 * mở ở đâu. Máy chủ gửi kèm mọi đối tượng trích dẫn khi biết; vắng hoặc `null`
 * là CHƯA BIẾT, và giao diện bỏ đúng phần đó chứ không hiện chỗ giữ chỗ.
 *
 * KHÔNG đọc thẳng các trường này ở nơi hiển thị: đi qua `vanBanHopLe` /
 * `cachTrichHopLe` (`lib/trich-dan.ts`). Đó là cửa DUY NHẤT loại giá trị dị
 * dạng — ngày không phải ISO, link không https hoặc ngoài hai cổng chính thống
 * — vì payload tới từ nhiều đường (stream, lượt đã lưu, trang văn bản) mà
 * guard ở mỗi đường chỉ là predicate thuần.
 */
export interface TrichDanDayDu {
  /** Tên đầy đủ của văn bản. */
  ten_van_ban?: string | null;
  loai_van_ban?: string | null;
  so_ky_hieu?: string | null;
  co_quan_ban_hanh?: string | null;
  /** ISO "2019-11-15" — ngày là DỮ KIỆN của văn bản, không phải phán quyết hiệu lực. */
  ngay_ban_hanh?: string | null;
  ngay_hieu_luc?: string | null;
  /** MỘT link chính thống đã kiểm: vbpl.vn, không có thì vanban.chinhphu.vn. */
  lien_ket?: string | null;
  /**
   * Câu trích dẫn theo lối chính văn bản luật dùng, máy chủ dựng. Mô tả CHÍNH
   * đối tượng mang nó: trên `Citation` có điều khoản ("khoản 1 Điều 3 Nghị định
   * số 90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ"), trên metadata văn bản chỉ
   * có văn bản ("Nghị định số 90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ").
   */
  cach_trich?: string | null;
}

export interface Citation extends TrichDanDayDu {
  /** Điều luật mô hình dẫn. */
  provision_id: number;
  /**
   * Dòng câu trích THẬT SỰ khớp. Khác `provision_id` ở **73,6% số Điều**, vì
   * phần lớn Điều chỉ có tiêu đề còn nội dung nằm ở Khoản/Điểm con. Panel đối
   * chiếu PHẢI mở bằng trường này.
   */
  khop_tai_id: number;
  /** `documents.id` — TEXT ở CSDL, nên `string`, không ép `number`. */
  doc_id: string;
  /** "45/2019/QH14 > Điều 127 > Khoản 2" — một địa chỉ, không phải một cái tên. */
  duong_dan: string;
  bo_luat: string;
  /** Định danh văn bản cho người đọc. KHÔNG BAO GIỜ hiển thị `ten`. */
  so_ky_hieu: string;
  quote: string;
  hieu_luc: HieuLuc | null;
  tin_cay: string | null;
  /**
   * Số thứ tự căn cứ trong văn xuôi — thẻ `[Điều N](cite:K)` trỏ vào đây.
   * `null`/vắng = trích dẫn nằm trong vết kiểm toán nhưng không dùng để hành
   * văn, hoặc payload cache dựng trước 2026-09-06.
   */
  k?: number | null;
  /** Vai trò của căn cứ: `ket_luan` | `dieu_kien` | `ngoai_le` | `che_tai`. `null`/vắng = prompt sinh chưa gắn vai trò. */
  vai_tro?: string | null;
}

/**
 * Văn bản chi phối câu hỏi — KHÔNG phải trích dẫn đã kiểm chứng, không có
 * `quote`, không có nhãn hiệu lực. Chỉ nhánh `partial_coverage` điền, và nhánh
 * đó luôn có `citations: []`, nên đây là thứ DUY NHẤT mở được văn bản đang
 * nói tới. Tuyệt đối không cạo `coverage_note` ra để bịa một liên kết.
 */
export interface Nguon extends TrichDanDayDu {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
}

/** Ba cổng luật; `null` = chưa có link đã kiểm. Giao diện bỏ dòng null. */
export interface LinkVanBan {
  vbpl: string | null;
  chinhphu: string | null;
  tvpl: string | null;
}

/**
 * Văn bản mô hình được phép gắn thẻ `doc:ID` — khớp `DocumentOut` của
 * `src/models/schemas.py`. Quyết định Q2 (không mang ngày) đã được thay bởi
 * quyết định 2026-09-28: trường trích dẫn đầy đủ đi kèm khi máy chủ biết.
 */
export interface VanBanTraLoi extends TrichDanDayDu {
  doc_id: string;
  ten: string;
  so_ky_hieu: string;
  loai_van_ban: string;
  links: LinkVanBan;
}

export interface LoaiGoiY {
  loai: string;
  ten: string;
}

/**
 * Gợi ý loại văn bản khi `result_type === "huong_dan_soan_thao"` — khớp
 * `SoanThaoGoiYOut` của `src/models/schemas.py`. `loai` là mã checklist phía
 * máy chủ; đổi sang slug thẻ bằng `slugCuaLoai()` trong `lib/mau-van-ban.ts`.
 */
export interface SoanThaoGoiY {
  loai: string | null;
  ten: string | null;
  ly_do: string;
  thay_the: LoaiGoiY[];
  ho_tro: boolean;
}

/**
 * Một bảng của nhánh `hoi_ve_kho` xin bảng — khớp `Bang` của
 * `src/models/schemas.py:95`. `dung_bang` (`src/services/kho.py:492`) luôn trả
 * HAI bảng cho một câu hỏi xin bảng: một phân theo loại văn bản, một phân theo
 * lĩnh vực pháp luật.
 *
 * Bảng lĩnh vực gộp `linh_vuc IS NULL` về khoá `""` (cố ý — xem `dung_bang`:
 * một ô trống nói đúng "không có giá trị", một nhãn bịa nói một điều không
 * kiểm được), nên `cot`/`dong` của Bảng đó có thể mang một hàng với ô đầu là
 * chuỗi rỗng. Đây là dữ liệu kho THẬT, không phải lỗi cần "sửa" ở tầng hiển
 * thị — `BangKetQua` hiện gạch ngang `—` mờ kèm tên khả truy cập `sr-only` cho
 * ô đó (không để trống thật, dễ lẫn với lỗi render), và câu `sr-only` đó trung
 * tính về cột chứ không tự bịa nhãn phân loại thay cho dữ liệu thiếu.
 */
export interface Bang {
  tieu_de: string;
  cot: string[];
  dong: string[][];
}

/**
 * Một dữ kiện về NGƯỜI HỎI mà lượt này đã dùng — khớp `HoSoDaDungOut` của
 * `src/models/schemas.py`. Chỉ `TheKetQua` đọc, để dựng dòng "Dựa trên" (spec
 * 2026-09-09 §6.6). `gia_dinh: true` = máy chủ ĐOÁN dữ kiện này chứ người hỏi
 * chưa nói thẳng — `DuaTren` phải in nghiêng kèm "(tôi đoán)" cho đúng.
 */
export interface HoSoDaDung {
  khoa: string;
  nhan: string;
  gia_tri: string;
  gia_dinh: boolean;
}

/**
 * `SoanThaoHoi.con_thieu` — cùng hình dạng với `Mau.facts` (`TruongFact`,
 * khai ở phần `/mau/{loai}` bên dưới); dùng lại thay vì khai một interface
 * trùng lặp thứ hai cho đúng một hình dạng.
 */
export type TruongDuKien = TruongFact;

/**
 * `result_type === "soan_thao_hoi"` (Task 21) — assemble còn thiếu dữ kiện,
 * hoặc người hỏi chưa đăng nhập, hoặc đã hết hạn mức soạn thảo, nên hỏi lại
 * thay vì dựng bản thảo — khớp `SoanThaoHoiOut` của `src/models/schemas.py`.
 * `chip` gợi ý nhanh cho từng khoá có `lua_chon`; `answer` (của
 * `TraCuuKetQua`) đã mang nguyên văn lời hỏi/lý do, nên card chỉ vẽ thêm chip
 * và (khi `can_dang_nhap`) một nút đăng nhập.
 */
export interface SoanThaoHoi {
  loai: string;
  ten: string;
  da_co: Record<string, string>;
  con_thieu: TruongDuKien[];
  chip: Record<string, string[]>;
  het_han_muc: string | null;
  can_dang_nhap: boolean;
}

/**
 * `result_type === "ban_thao"` (Task 21) — bản thảo vừa dựng/sửa xong ngay
 * trong hội thoại, khớp `BanThaoOut`. `doi_so_voi_truoc` liệt kê tên các
 * trường vừa đổi so với phiên bản trước; `[]` ở bản thảo mới dựng lần đầu.
 */
export interface BanThao {
  id: string;
  loai: string;
  ten: string;
  phien_ban: number;
  /** Markdown. */
  document: string;
  clauses: unknown[];
  audit_report: Record<string, unknown>;
  facts: Record<string, string>;
  doi_so_voi_truoc: string[];
  /**
   * Bản thảo trên khuôn gốc (quyết định 2026-09-26) — THÔ như máy chủ gửi,
   * `null`/vắng ở bản thảo HTML. Chỉ đọc qua `khuonHopLe`: bản thảo tới từ năm
   * đường (tải, lùi, lưu, stream, lượt đã lưu), và `unknown` bắt mọi chỗ đọc
   * đi qua đúng một cửa kiểm thay vì năm bản chép của nó.
   */
  khuon?: unknown;
}

/** Một ô điền được trên khuôn gốc, theo thứ tự đọc — khớp một phần tử
 *  `cho_trong` của `BanThaoOut.khuon`. `gia_tri` `null` là còn dãy chấm; ô
 *  `tab` lưu giá trị có một dấu cách đầu (máy chủ chuẩn hoá, xem
 *  `ban_thao.chuan_hoa_dien`). `kieu` để `string`: một kiểu backend thêm sau
 *  không được làm rơi cả ô. */
export interface ChoTrongKhuon {
  don_vi: number;
  so: number;
  kieu: string;
  nhan: string;
  gia_tri: string | null;
}

/** `BanThaoOut.khuon` đã qua `khuonHopLe`. */
export interface KhuonBanThao {
  viec_id: string;
  dinh_dang: "docx" | "pdf";
  so_trang: number;
  cho_trong: ChoTrongKhuon[];
}

/** Thân của `GET /tai-lieu/{id}/trang` và `GET /ban-thao/{id}/trang`: khổ từng
 *  trang (`[rộng, cao]` pt) và ảnh PNG base64 TRẦN của đúng trang đó. */
export interface TrangAnh {
  kho: [number, number][];
  trang: string[];
  /** Chỗ trống của ĐÚNG phiên bản vừa dựng — THÔ như máy chủ gửi, vắng ở máy
   *  chủ cũ. Chỉ đọc qua `oHopLe`. */
  o?: unknown;
}

/** Một chỗ trống trên ảnh trang (phần tử `o` của payload trang), theo thứ tự
 *  đọc. `trang`/`hop` cùng `null` khi máy chủ không đo được vị trí. */
export interface OTrang {
  don_vi: number;
  so: number;
  /** Chỉ số trang (0-based) trong `TrangAnh.trang`. */
  trang: number | null;
  /** `[x0, y0, x1, y1]` pt, gốc trên-trái của trang đó — cùng hệ với `kho`. */
  hop: [number, number, number, number] | null;
  nhan: string;
  gia_tri: string | null;
}

/**
 * Nhãn người-đọc-được cho `BanThao.doi_so_voi_truoc` (Task 24 fix — coordinator
 * review). `doi_so_voi` ở `src/services/ban_thao.py` so `facts` cũ/mới, KHÔNG
 * so `clauses`, nên khoá trong mảng này LÀ khoá field (`TruongFact.key`, không
 * gian của `GET /mau/{loai}`), KHÔNG PHẢI khoá mục (`MucCauTruc.key`/`Muc.key`,
 * không gian của `cau_truc.muc`/`draft_generate`'s `DraftClause.key`). Hai
 * checklist do trùng tên field/mục (`luong` là ví dụ thật) khiến việc tô "mục
 * vừa đổi" trông có vẻ đúng ở một vài trường hợp rồi sai âm thầm ở phần còn
 * lại — không có bảng field→mục nào trong dữ liệu để ánh xạ đúng, nên đây là
 * "đổi Ý NGHĨA của việc hiển thị" (liệt kê FACT đã đổi), không phải tô mục.
 *
 * Chữ ký nhận `TruongFact[]`, không nhận `Muc[]`/`CauTruc` — khoá hai không
 * gian lại với nhau qua tham số là đúng lỗi bản vá này sửa, nên kiểu ở đây cố
 * tình không cho biên dịch nếu ai đó nối nhầm.
 */
export function nhanFactDoi(doiSoVoiTruoc: string[], truong: TruongFact[]): string[] {
  const nhan = new Map(truong.map((t) => [t.key, t.nhan]));
  return doiSoVoiTruoc.map((k) => nhan.get(k) ?? k);
}

/** Một dòng của `GET /ban-thao` (Task 21) — khớp `BanThaoTomTatOut`: đủ để vẽ
 *  danh sách "Bản thảo" và mở lại đúng loại, không kèm nội dung đầy đủ như
 *  `BanThao` (`document`/`clauses`/`audit_report`). */
export interface BanThaoTomTat {
  id: string;
  loai: string;
  ten: string;
  phien_ban: number;
  cap_nhat_luc: string;
  hoi_thoai_id: string | null;
}

/**
 * **Neo tài liệu** — con trỏ ĐÃ KIỂM từ một câu nói về tài liệu tới đúng một
 * đơn vị văn bản (`CONTEXT.md`).
 *
 * Backend chỉ phát neo sau khi dò được `trich` nguyên văn trong đơn vị mang chỉ
 * số này; câu nào không dò ra thì bị bỏ hẳn, không tới đây. Vì vậy giao diện
 * được phép cho bấm vào neo — và PHẢI cho bấm: một neo không mở được chỗ nó
 * chỉ tới thì chỉ là một dòng chữ tự nhận là bằng chứng.
 *
 * Nó KHÔNG phải trích dẫn điều luật (`Citation`) và không bao giờ được trộn
 * chung dải: cái kia qua hai tầng kiểm chứng trên kho luật, cái này chỉ nói
 * "tờ giấy bạn gửi có viết câu đó".
 */
export interface NeoTaiLieu {
  tai_lieu_id: string;
  chi_so_don_vi: number;
  trang: number | null;
  vung: "than" | "dau_trang" | "chan_trang";
  /** `[bảng, hàng, cột]` khi neo rơi vào một ô bảng. */
  bang: [number, number, number] | null;
  nguon_chu: "lop_chu" | "ocr";
  /** 0–1, CHỈ có với `ocr`. Chữ đọc thẳng không có gì để đoán. */
  do_tin: number | null;
  /** Nguyên văn đoạn đã dò khớp. Vắng ở payload cũ. */
  trich?: string | null;
  /** Nhánh đối chiếu luật: câu hỏi pháp lý mà điều khoản này đặt ra. */
  cau_hoi_phap_ly?: string | null;
}

/**
 * **Quan sát** — một câu về điều tài liệu VIẾT, buộc vào một neo đã kiểm.
 * Không neo thì backend bỏ, nên mọi quan sát tới đây đều mở được bằng chứng.
 */
export interface QuanSat {
  noi_dung: string;
  trich: string;
  neo: NeoTaiLieu;
}

/**
 * Một phép tính do CODE chạy, đặt cạnh con số tài liệu tự ghi.
 *
 * `ket_qua_code` là của máy tính, không phải của mô hình — đó là toàn bộ lý do
 * khối này tồn tại. Giao diện phải nói ra cả hai con số khi chúng lệch, chứ
 * không chọn hộ một con số rồi tuyên bố nó đúng.
 */
export interface PhepTinh {
  bieu_thuc: string;
  ket_qua_code: string;
  ket_qua_tai_lieu: string;
  khop: boolean;
  /**
   * Chỗ trong tài liệu ghi con số đã bị đem ra đối chiếu. Tuỳ chọn: payload
   * cache ghi trước S4 không có, và một phép tính gộp nhiều ô có thể không quy
   * về đúng MỘT đơn vị nào — lúc đó thà không có chip còn hơn có một chip trỏ
   * sai chỗ, vì chip ở đây tự nhận là bằng chứng cho con số bên cạnh nó.
   */
  neo?: NeoTaiLieu | null;
}

/**
 * Một điểm khác nhau giữa HAI tài liệu, với neo ở CẢ hai bên.
 *
 * Hai neo là bắt buộc chứ không phải tiện lợi: câu "bên A ghi 90 ngày, bên B
 * ghi 60 ngày" chỉ kiểm được khi mở được cả hai chỗ. Một bên không dò ra thì
 * backend bỏ cả dòng — nửa bằng chứng cho một câu so sánh là không có bằng chứng.
 */
export interface KhacBiet {
  noi_dung: string;
  neo_a: NeoTaiLieu;
  neo_b: NeoTaiLieu;
}

/** Tài liệu đã dùng cho lượt này. `nhan` là chữ cái ngắn ("A", "B") để đối
 *  chiếu hai tài liệu mà không phải nhắc lại cả tên tệp ở mỗi dòng. */
export interface TaiLieuDaDung {
  id: string;
  ten_tep: string;
  nhan: string;
}

/**
 * Thân của `result_type === "tai_lieu"`.
 *
 * Hai danh sách, hai hạng bằng chứng, KHÔNG gộp: `quan_sat` là điều tài liệu
 * viết (có neo), `suy_luan` là cách KLAW đọc chỗ đó (không có neo, và phải
 * mang nhãn nói rõ nó là của mô hình).
 */
export interface TaiLieuKetQua {
  /** `tom_tat|hoi|phan_tich|trich_du_kien|so_sanh` — mục đích của LƯỢT, không
   *  phải loại tài liệu (`CONTEXT.md`). Để `string`: một mục đích backend thêm
   *  sau phải suy biến về cách trình bày chung, không làm hỏng cả thẻ. */
  muc_dich: string;
  mo_ta: string | null;
  quan_sat: QuanSat[];
  suy_luan: string[];
  phep_tinh: PhepTinh[];
  /** Dữ kiện còn thiếu mà lượt này cần người dùng cấp. */
  can_du_kien: string[];
  du_kien: DuKien[];
  /** CHỈ ở `muc_dich === "so_sanh"`. Tuỳ chọn: mọi mục đích khác bỏ khoá này,
   *  và payload cache ghi trước S4 chưa biết tới nó. */
  khac_biet?: KhacBiet[];
  tai_lieu_da_dung: TaiLieuDaDung[];
}

export interface TraCuuKetQua {
  result_type: ResultType;
  answer: string | null;
  citations: Citation[];
  nguon: Nguon[];
  warnings: string[];
  coverage_note: string | null;
  trace_id: string;
  /**
   * Câu hỏi sau khi máy chủ giải nghĩa một lượt hỏi NỐI TIẾP, hoặc `null` khi
   * không giải nghĩa (lượt đầu) hoặc không cần.
   *
   * PHẢI hiện ra khi nó khác câu người dùng gõ. Giải nghĩa sai là chuyện chắc
   * chắn xảy ra, và không có dòng này thì người hỏi nhận câu trả lời cho một câu
   * HỌ KHÔNG HỎI mà không có cách nào biết, cũng không có cách nào sửa.
   */
  cau_hoi_day_du: string | null;
  /**
   * Hai bảng của nhánh xin bảng, `[]` ở mọi nhánh khác. Máy chủ nay LUÔN gửi
   * khoá này, nhưng `laTraCuuKetQua` vẫn khoan dung khi nó vắng mặt — một
   * response cũ nằm trong cache (dựng trước khi trường này tồn tại) phải đọc
   * được thay vì làm sập cả thẻ kết quả.
   */
  bang: Bang[];
  /** `[]` ở mọi nhánh trừ `answer`; `chuanHoaDocuments` điền khi máy chủ cũ không gửi. */
  documents: VanBanTraLoi[];
  /** Nhánh `huong_dan_soan_thao`, và từ Task 13 cả nhánh `answer` khi ý định phụ
   *  là soạn thảo; vắng/null ở mọi nhánh khác và với payload cache cũ. */
  soan_thao?: SoanThaoGoiY | null;
  /** Dữ kiện về người hỏi mà lượt này đã dùng — dòng "Dựa trên" (spec 2026-09-09
   *  §6.6). Tuỳ chọn: payload cache cũ (dựng trước trường này tồn tại) không có. */
  ho_so_da_dung?: HoSoDaDung[];
  /** Nhánh `soan_thao_hoi` (Task 21) — còn thiếu dữ kiện để dựng bản thảo.
   *  Tuỳ chọn/null: mọi nhánh khác, và payload cache ghi trước Task 21. */
  soan_thao_hoi?: SoanThaoHoi | null;
  /** Nhánh `ban_thao` (Task 21) — bản thảo vừa dựng/sửa xong trong hội thoại.
   *  Tuỳ chọn/null cùng lý do `soan_thao_hoi`. */
  ban_thao?: BanThao | null;
  /** Nhánh `tai_lieu` — lượt nói về tài liệu người dùng gửi. Tuỳ chọn/null ở
   *  mọi nhánh khác và với payload cache ghi trước khi loại này tồn tại. */
  tai_lieu?: TaiLieuKetQua | null;
  /**
   * Điều khoản trong tài liệu mà lượt này đã đánh giá — CHỈ ở nhánh đối chiếu
   * luật, nơi `result_type` vẫn là `answer`/`partial_coverage`/`abstain`.
   *
   * Nó đứng riêng khỏi `citations` vì nó là DỮ KIỆN của người hỏi, không phải
   * căn cứ: câu trả lời nói luật đòi gì và điều khoản khác ở đâu, nó không bao
   * giờ tuyên bố điều khoản đó hợp pháp hay không (QT-1).
   */
  tai_lieu_neo?: NeoTaiLieu[];
}

/**
 * Một lượt hỏi-đáp ĐÃ XONG, gửi lên để máy chủ giải nghĩa câu nối tiếp.
 *
 * Khớp `LuotTruoc` của `src/models/schemas.py`. Lịch sử CHỈ dùng để làm câu hỏi
 * tự đứng được — nó không chống đỡ khẳng định nào, nên câu đã giải nghĩa vẫn
 * phải qua đủ hai tầng kiểm chứng như một câu hỏi mới.
 */
export interface LuotTruoc {
  cau_hoi: string;
  tra_loi: string;
  duong_dan: string[];
}

/** Trần của `TraCuuRequest.lich_su` phía máy chủ — quá là **422**, không truncate. */
export const TOI_DA_LUOT_LICH_SU = 10;
/** Khớp `giai_nghia.TOI_DA_TRA_LOI`: máy chủ cắt còn đúng bấy nhiêu khi dựng
 *  prompt, nên gửi nhiều hơn là tiêu băng thông cho chữ bị bỏ — và một câu trả
 *  lời ba tầng dài hơn 2.000 ký tự sẽ làm cả lượt nối tiếp bị 422. */
export const TOI_DA_TRA_LOI_LICH_SU = 400;

/**
 * `string`, KHÔNG một union đóng — cùng bài học đã ghi ở `MucLucItem.cap`.
 *
 * Union ba cấp `dieu | khoan | diem` đã thiếu ngay lúc viết: cùng endpoint này
 * còn trả `mo_dau` và `phu_luc` (đo trên kho thật), và nay thêm `hang_bang`.
 * Union đóng không chặn được gì — `laVanBanProvisions` chỉ kiểm mảng — nó chỉ
 * khiến TypeScript từ chối đúng phép so sánh cần viết khi cấp mới xuất hiện.
 * Cấp thứ bảy nào backend thêm sau cũng phải rơi vào nhánh AN TOÀN của nơi gọi
 * (`LE_THEO_CAP[cap] ?? "0rem"`), chứ không phải làm đỏ kiểu.
 */
export type CapProvision = string;

export interface Provision {
  id: number;
  cap: CapProvision;
  so_hieu_cap: string;
  duong_dan: string;
  tieu_de: string;
  noi_dung: string;
  /**
   * Dòng cha; NULL ở cấp Điều. Thu `hang_bang` về đúng bảng của nó đi qua
   * trường này — xem `gomHangBang` trong `lib/bang.ts`.
   */
  parent_id: number | null;
  /**
   * true cho Điều được hỏi VÀ mọi Khoản/Điểm con của nó. Dùng để tô cả **VÙNG**
   * đang xem, không phải một dòng đơn lẻ. false cho các Điều lân cận.
   */
  la_tam: boolean;
}

/** Nguyên văn quanh một điều cho khung đối chiếu. Trường trích dẫn đầy đủ là
 *  metadata CẤP VĂN BẢN (`cach_trich` không có điều khoản). */
export interface VanBanQuanhDieu extends TrichDanDayDu {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  provisions: Provision[];
}

/**
 * Tám nhánh lỗi. Bản Klaw_FE chỉ có một trạng thái `error` chung, và một thông
 * báo chung nói được đúng một câu vô dụng cho tám tình huống rất khác nhau.
 *
 * `invalid_response` là nhánh dễ mất nhất và nguy hiểm nhất: máy chủ trả 2xx
 * nhưng body sai hình dạng. Nếu không có nhánh này thì giao diện hoặc sập, hoặc
 * — tệ hơn — render một câu trả lời rỗng như thể đó là câu trả lời thật.
 */
export type ApiErrorKind =
  | "network" // fetch() tự nó thất bại: mất mạng, DNS, CORS bị chặn
  | "timeout" // vượt thời gian chờ nội bộ
  | "aborted" // người dùng bấm huỷ, hoặc một lượt gọi mới thay thế lượt cũ
  | "not_implemented" // 501: loại văn bản chưa có nội dung pháp lý
  | "not_found" // 404 có nghĩa "không có"
  | "unauthorized" // 401/403: thiếu API key, hoặc chưa đăng nhập
  | "rate_limited" // 429: quá nhịp, hết hạn mức tháng, hoặc chạm trần chi phí ngày
  | "invalid_request" // 4xx khác, vd 422 sai định dạng as_of_date
  | "server_error" // 5xx
  | "invalid_response"; // 2xx nhưng body sai hình dạng

/*
 * Hai nhánh `unauthorized` / `rate_limited` thêm ở pha nối backend, sau khi đọc
 * `bao_ve.py`: cổng bảo vệ trả 401 (API key / bearer) và 429 (nhịp, hạn mức
 * tháng, trần chi phí ngày) như hai tình huống riêng biệt, kèm `Retry-After`.
 * Gộp chúng vào `invalid_request` sẽ khiến `BaoLoi` khuyên "kiểm tra lại nội
 * dung đã nhập" — một câu SAI về câu hỏi của người dùng khi nguyên nhân thật là
 * hết lượt hoặc chưa đăng nhập. Đúng loại khẳng định không kiểm chứng được mà
 * dự án này tồn tại để loại bỏ, chỉ khác là ở tầng thông báo lỗi.
 */

export interface ApiError {
  kind: ApiErrorKind;
  /** Tiếng Việt, hiển thị thẳng được cho người dùng. */
  message: string;
  status?: number;
  /** Chỉ để gỡ lỗi — không hiển thị thẳng. */
  detail?: unknown;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

/* ═══════════════════════════════════════════════════════════════════════════
 * Hợp đồng 8 endpoint của Pha 2 — chép từ `src/models/schemas.py`.
 *
 * Ngày tháng là `string` ISO ("2019-11-20"), KHÔNG phải `Date`: đó là thứ JSON
 * mang được, và mọi phép so sánh/hiển thị ở FE làm trên chuỗi ISO là đủ. Ép
 * sang `Date` ở tầng kiểu sẽ nói dối về thứ `JSON.parse` thật sự trả về.
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Phán quyết hiệu lực của KLAW (`effectivity.py`).
 *
 * `verdict` để `string`, KHÔNG thu hẹp về `HieuLuc`: backend nói thẳng rằng
 * nhãn mới có thể xuất hiện, và `BadgeHieuLuc` đã có nhánh `default` cho đúng
 * việc đó. Thu hẹp ở đây chỉ chuyển một nhãn lạ từ "hiện nguyên chuỗi" thành
 * "TypeScript nói dối là chuyện đó không xảy ra được".
 */
export interface HieuLucChiTiet {
  verdict: string;
  tin_cay: string;
  ly_do: string;
}

/* ── GET /bo-loc — nguồn DUY NHẤT cho giá trị bộ lọc ─────────────────────── */

export interface GiaTriLoc {
  gia_tri: string;
  so_van_ban: number;
}

export interface BoLoc {
  tong_van_ban: number;
  loai_van_ban: GiaTriLoc[];
  co_quan_ban_hanh: GiaTriLoc[];
  /** 79/126 văn bản KHÔNG khai cơ quan: tổng theo cơ quan ≠ tổng corpus. */
  co_quan_khong_ro: number;
  nam_min: number | null;
  nam_max: number | null;
  sap_xep: string[];
}

/* ── GET /tim-kiem — BM25, chất lượng TỪ KHOÁ (không phải ngữ nghĩa) ─────── */

/** `cach_trich` (nếu máy chủ gửi) mô tả CHÍNH dòng này, tức một điều khoản. */
export interface DongTimKiem extends TrichDanDayDu {
  provision_id: number;
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  loai_van_ban: string;
  co_quan_ban_hanh: string | null;
  ngay_ban_hanh: string | null;
  cap: string;
  so_hieu_cap: string;
  duong_dan: string;
  tieu_de: string;
  trich: string;
  score: number;
  hieu_luc: HieuLucChiTiet;
}

export interface TimKiem {
  q: string;
  /** Của TOÀN tập khớp, không phải của trang đang xem. */
  tong_dieu_khoan: number;
  tong_van_ban: number;
  limit: number;
  offset: number;
  sap_xep: string;
  ket_qua: DongTimKiem[];
}

/* ── GET /van-ban — danh sách văn bản theo bộ lọc, không cần từ khoá ─────── */
export interface VanBanTomTat {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  loai_van_ban: string;
  co_quan_ban_hanh: string | null;
  ngay_ban_hanh: string | null;
  hieu_luc: HieuLucChiTiet;
}

export interface DanhSachVanBan {
  tong: number;
  limit: number;
  offset: number;
  sap_xep: string;
  ket_qua: VanBanTomTat[];
}

/* ── GET /van-ban/{doc_id}/hieu-luc — nguồn hiệu lực DUY NHẤT ────────────── */

export interface SuaBoi {
  /** Vị trí VBHN nêu; có thể KHÁC `duong_dan` khi là khoản mới thêm ("8a"). */
  vi_tri: string;
  so_ky_hieu: string | null;
  duong_dan: string | null;
  tu_ngay: string | null;
  nguon: string;
  do_tin_cay: string;
}

export interface DieuKhoanHieuLuc {
  provision_id: number;
  duong_dan: string;
  cap: string;
  so_hieu_cap: string;
  tieu_de: string;
  hieu_luc: HieuLucChiTiet;
  sua_boi: SuaBoi[];
}

export interface VanBanHieuLuc {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  as_of: string;
  van_ban: HieuLucChiTiet;
  /**
   * Bản đồ sửa đổi cấp điều khoản mới phủ 1/126 văn bản (4 dòng, đều của
   * `45/2019/QH14`). **Rỗng là BÌNH THƯỜNG, không phải lỗi** — giao diện phải
   * đọc mảng rỗng như "chưa có bằng chứng cấp điều khoản", không như "hỏng".
   */
  dieu_khoan: DieuKhoanHieuLuc[];
}

/* ── GET /van-ban/{doc_id}/lien-quan — bản đồ ĐIỀU HƯỚNG, không phán quyết ─ */

export interface VanBanLienQuanItem {
  /** null ⇒ văn bản nằm NGOÀI corpus ⇒ KHÔNG dựng link (link đó ra 404). */
  doc_id: string | null;
  so_ky_hieu: string;
  bo_luat: string | null;
  trong_corpus: boolean;
}

export interface NhomLienQuan {
  loai: number;
  nhan: string;
  chieu: "di_ra" | "di_vao";
  /**
   * false ⇒ chiều ngữ nghĩa CHƯA ĐO. Hiện nhãn quan hệ, tuyệt đối không viết
   * thành câu "Văn bản này thay thế X" — câu đó có 50% khả năng ngược.
   */
  chieu_da_do: boolean;
  so_luong: number;
  van_ban: VanBanLienQuanItem[];
}

export interface VanBanLienQuan {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  nhom: NhomLienQuan[];
  dan_chieu_noi_bo: { so_luong: number; ghi_chu: string };
}

/* ── GET /van-ban/{doc_id} — metadata 10 trường, KHÔNG có `tinh_trang` ───── */

/** Kèm trường trích dẫn đầy đủ CẤP VĂN BẢN (`cach_trich` không có điều khoản). */
export interface VanBanMeta extends TrichDanDayDu {
  doc_id: string;
  so_ky_hieu: string;
  /** = `documents.ten`. HIỂN THỊ, không bao giờ là khoá định danh. */
  bo_luat: string;
  loai_van_ban: string;
  /** NULL trên 79/126: KHÔNG BIẾT, không phải "không có cơ quan". */
  co_quan_ban_hanh: string | null;
  ngay_ban_hanh: string | null;
  ngay_hieu_luc: string | null;
  /** NULL trên 95/126. Trường của CHÍNH CSDL quốc gia và tin được. */
  ngay_het_hieu_luc: string | null;
  nguoi_ky: string | null;
  chuc_danh_nguoi_ky: string | null;
}

export interface MucLucItem {
  id: number;
  /**
   * `string`, KHÔNG một union đóng — cùng lý do với `hieu_luc`.
   *
   * Mục lục từng chỉ mang bốn cấp CHỨA Điều. Backend nay trả thêm `"dieu"` cho
   * 11/47 văn bản không chia Chương/Mục, và union đóng đã không chặn được điều
   * đó (`laVanBanMucLuc` chỉ kiểm mảng): `?trong_chuong=` nhận id của một Điều
   * và ăn 422. Cấp thứ sáu nào backend thêm sau cũng phải rơi vào nhánh AN
   * TOÀN — xem `CAP_CHUA_DIEU`.
   */
  cap: string;
  so_hieu_cap: string;
  tieu_de: string;
  thu_tu: number;
}

/**
 * Cấp mở tiếp được bằng `?trong_chuong=`. Mọi cấp khác là LÁ: đi tới bằng
 * `?dieu=<so_hieu_cap>` — đường đó không bao giờ 422 vì nó không khẳng định
 * mục này chứa Điều nào.
 */
export const CAP_CHUA_DIEU = new Set(["phan", "chuong", "muc", "tieu_muc"]);

export type VanBanMucLuc = VanBanMeta & { muc_luc: MucLucItem[] };
export type VanBanProvisions = VanBanMeta & { provisions: Provision[] };

/* ── GET /van-ban/{doc_id}/tim — ô lọc mục lục ───────────────────────────── */

export interface DongTimTrongVanBan {
  provision_id: number;
  cap: string;
  so_hieu_cap: string;
  duong_dan: string;
  tieu_de: string;
  trich: string;
  /** Thứ tự TRONG CÂY — khoá sắp xếp. Đây là mục lục, không phải bảng xếp hạng. */
  thu_tu: number;
}

export interface TimTrongVanBan {
  doc_id: string;
  so_ky_hieu: string;
  q: string;
  tong: number;
  limit: number;
  ket_qua: DongTimTrongVanBan[];
}

/* ── GET /han-muc ───────────────────────────────────────────────────────── */

export interface MucHanMuc {
  khoa: string;
  nhan: string;
  da_dung: number;
  han_muc: number;
  dat_lai_luc: string | null;
}

export interface HanMuc {
  ap_dung: boolean;
  plan: string | null;
  ten_goi: string | null;
  mui_gio: string;
  muc: MucHanMuc[];
  phien: { luot_toi_da: number | null };
  het_han_luc: string | null;
  ghi_chu: string;
  bi_khoa: boolean;
}

/* ── GET /pham-vi — hai tầng, vì corpus thật có hai tầng ─────────────────── */

export interface VanBanPhamVi {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  loai_van_ban: string;
  so_dieu_khoan: number;
  /** Tuyên bố của CSDL quốc gia, KHÔNG phải phán quyết của KLAW. */
  tinh_trang_moj: string | null;
}

export interface TangPhamVi {
  so_van_ban: number;
  so_dieu_khoan: number;
  van_ban: VanBanPhamVi[];
}

export interface PhamVi {
  /** Có toàn văn — trả lời được thành `answer`. */
  sau: TangPhamVi;
  /** Chỉ metadata — CHÍNH LÀ thứ sinh ra `partial_coverage`. */
  nong: TangPhamVi;
}

/* ── GET /mau/{loai} · POST /soan-thao · POST /soat ──────────────────────── */

export type LoaiVanBanBackend = "hdld" | "noi_quy" | "quyet_dinh_ky_luat";

export interface TruongFact {
  key: string;
  nhan: string;
  kieu: string;
  bat_buoc: boolean;
  lua_chon: string[] | null;
}

/** Một mục bắt buộc của văn bản, kèm căn cứ pháp lý của riêng nó. */
export interface MucCauTruc {
  stt: number;
  key: string;
  ten: string;
  /** Đường dẫn căn cứ, ví dụ `45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a`. */
  can_cu: string;
  bat_buoc: boolean;
}

/**
 * Bộ khung của một loại văn bản, đọc từ chính `checklist_*.yaml` mà `/soan-thao`
 * và `/soat` dùng — MỘT nguồn sự thật cho cả dựng lẫn soát.
 *
 * KHÔNG có phần khung nào ngoài `muc`. Máy chủ sinh đúng `# {tieu_de}` rồi
 * `## {don_vi_muc} {stt}. {ten}`. Với `cong_van`, quốc hiệu / nơi nhận / chữ ký
 * CHÍNH LÀ các `muc`; với `hdld` chúng vắng mặt vì BLLĐ Điều 21 không đòi. Mọi
 * khối `BÊN A / BÊN B / Mã số thuế` dựng thêm ở giao diện đều là phát minh của
 * giao diện, không có thẩm quyền pháp lý nào.
 */
export interface CauTruc {
  ten: string;
  tieu_de: string;
  /** Đơn vị đánh số mục: `Điều`, `Mục`, hay `Thành phần`. */
  don_vi_muc: string;
  muc_do_thieu: string;
  /** `the_thuc` hoặc `noi_dung`. */
  pham_vi_soat: string;
  chi_soat_the_thuc: boolean;
  /**
   * `true` = checklist này dựng trên chế định hợp đồng. Tính ở SERVER, vì chỉ ở
   * đó mới biết: `can_cu_goc` không phân biệt được (BLDS `91/2015/QH13` chứa cả
   * Đ430 mua bán lẫn Đ138 giấy uỷ quyền; BLLĐ chứa cả Đ21 HĐLĐ lẫn Đ118 nội
   * quy), và suy từ `muc` sai cả hai chiều (`giay_uy_quyen` có mục `ben_*` mà
   * KHÔNG phải hợp đồng; `hdld` và `hop_dong_mua_ban` không có mục nào nhắc
   * "bên" mà vẫn là hợp đồng).
   */
  la_hop_dong: boolean;
  /**
   * Hai mục mà mọi hợp đồng bằng văn bản cần nhưng checklist riêng không liệt
   * kê: các bên giao kết (BLDS Đ385) và chữ ký (BLDS Đ400.4 — chưa ký thì chưa
   * giao kết).
   *
   * **ĐỪNG giả định hai phần tử.** Máy chủ lọc bỏ key mà checklist đã tự có:
   * `hop_dong_hop_tac` chỉ nhận `chu_ky`, vì nó đã có mục `cac_ben` riêng với
   * căn cứ cụ thể hơn (Đ505.2) và mục đó NẰM TRONG mẫu số completeness. Vẽ
   * thêm một khối "các bên" nữa là in hai lần, một lần được tính vào tỷ lệ và
   * một lần không.
   *
   * `stt` ở đây đánh số theo MẢNG, không phải theo văn bản — `chu_ky` của
   * `hop_dong_hop_tac` mang `stt=1`. Đừng dùng nó làm số Điều.
   *
   * **`null`, không phải `[]`, khi `la_hop_dong=false`** — ĐO TRÊN MÁY CHỦ ĐANG
   * CHẠY, cả 15 loại không-hợp-đồng đều trả `null`. Khai `MucCauTruc[]` rồi gọi
   * `.map()` là ném `TypeError` trên mọi công văn, đơn và quyết định. Đây là lần
   * THỨ HAI kiểu ở FE chặt hơn API thật (xem `can_cu_chi_tiet`).
   */
  khung_hop_dong: MucCauTruc[] | null;
  can_cu_goc: string;
  /**
   * `null` được — ĐO TRÊN MÁY CHỦ ĐANG CHẠY: `hop_dong_thu_viec`,
   * `hop_dong_thue_tai_san`, `hop_dong_vay` và `don_khoi_kien` đều trả về
   * `null` ở khoá này. Khai `string` là nói dối kiểu, và nơi đầu tiên đọc nó
   * mà không kiểm sẽ in ra chữ "null" giữa một văn bản pháp lý.
   */
  can_cu_chi_tiet: string | null;
  muc: MucCauTruc[];
}

export interface Mau {
  loai_van_ban: string;
  facts: TruongFact[];
  /** `null` khi `ho_tro=false` — loại văn bản chưa có checklist nào. */
  cau_truc: CauTruc | null;
}

export interface PhatHien {
  loai: string;
  muc_do: string;
  thong_diep: string;
  dieu_khoan_lien_quan: string | null;
  can_cu: string | null;
  rule_id: string | null;
  doc_id: string | null;
  /** Mở panel đối chiếu bằng trường này. null cho `citation_khong_hop_le`. */
  khop_tai_id: number | null;
  /**
   * true = rule KHÔNG được kiểm (thiếu fact), **không phải** văn bản sai. Tô
   * nó như một vi phạm là nói với người dùng rằng văn bản của họ trái luật
   * trong khi máy chỉ thiếu dữ liệu.
   */
  khong_kiem_duoc: boolean;
}

export interface BaoCaoSoat {
  dat: boolean;
  completeness: number;
  so_dieu_khoan: number;
  self_audit: boolean;
  findings: PhatHien[];
}

export interface SoanThaoKetQua {
  /** Markdown. */
  document: string;
  clauses: unknown[];
  audit_report: BaoCaoSoat;
  trace_id: string;
}

/* ── POST /tra-cuu/luong — SSE, stream BƯỚC (không stream token) ─────────── */

export interface BuocKhai {
  buoc: string;
  nhan: string;
  thu_tu: number;
}

export interface SuKienBatDau {
  trace_id: string;
  config_name: string;
  cac_buoc: BuocKhai[];
  hoi_thoai_id: string | null;
}

export interface SuKienBuoc {
  buoc: string;
  nhan: string;
  thu_tu: number | null;
  tong: number;
  chi_tiet: Record<string, number | string | null>;
}

/* ── /hoi-thoai — phiên hội thoại theo tài khoản (spec 2026-09-07) ─────────── */
export interface PhienTomTat {
  id: string;
  tieu_de: string;
  so_luot: number;
  tao_luc: string;
  cap_nhat_luc: string;
  /** Phiên này bị đánh dấu "không ghi nhớ" (spec 2026-09-09 §6.6) — công tắc
   *  trong `DanhSachPhien`. Tuỳ chọn: backend cũ chưa gửi trường này. */
  khong_ghi_nho?: boolean;
}

export interface DanhSachPhien {
  plan: string;
  luot_moi_phien: number;
  tong: number;
  items: PhienTomTat[];
}

/* ── /tai-khoan/bo-nho — bộ nhớ tài khoản, CHỈ gói trả phí (spec 2026-09-09 §6.6) ── */

/** Một dữ kiện KLAW đang nhớ về tài khoản. Bảy khoá cố định: `chu_the`,
 *  `loai_hop_dong`, `tham_nien`, `vung_luong`, `thoi_diem`, `van_ban_da_co`,
 *  `vu_viec`. Không bao giờ mang giấy tờ, số tài khoản, địa chỉ — hợp đồng
 *  máy chủ đã loại những khoá đó trước khi tới đây. */
export interface MucBoNho {
  khoa: string;
  nhan: string;
  gia_tri: string;
  nguon_hoi_thoai_id: string | null;
  cap_nhat_luc: string;
}

export interface BoNhoTaiKhoan {
  ghi_nho: boolean;
  muc: MucBoNho[];
}

/* ── /tai-khoan/da-nho — điều KLAW đã nhớ về tài khoản (Phase 12, R2) ── */

/** Một dữ kiện người dùng đã khai trong lượt soạn (họ tên, mã SV, nơi thực
 *  tập...) hoặc một thói quen soạn. KHÁC `MucBoNho`: có `id` riêng để xoá từng
 *  dòng, mở cho mọi tài khoản, và chỉ được dùng khi người dùng yêu cầu. */
export interface MucDaNho {
  id: string;
  loai: "ca_nhan" | "thoi_quen";
  khoa: string;
  nhan: string;
  gia_tri: string;
  nguon_hoi_thoai_id: string | null;
  cap_nhat_luc: string;
}

export interface DanhSachDaNho {
  muc: MucDaNho[];
}

export interface HoSo {
  email: string | null;
  plan: string;
  ten_goi: string;
  tao_luc: string;
  het_han_luc: string | null;
  so_phien: number;
  tong_hoi_dap: number;
  tong_ban_thao: number;
  hoat_dong: { ngay: string; so_luot: number }[];
  phan_loai: { khoa: string; nhan: string; so: number }[];
}

export interface YeuCauNangGoi {
  id: number;
  loai: "nang_goi" | "gia_han";
  goi_hien_tai: string;
  goi_muon: string;
  trang_thai: "cho_duyet" | "da_duyet" | "tu_choi";
  tao_luc: string;
  xu_ly_luc: string | null;
  ly_do: string | null;
}

export interface ThongBao {
  id: number;
  loai: string;
  tieu_de: string;
  noi_dung: string;
  duong_dan: string;
  da_doc: boolean;
  tao_luc: string;
}

export interface HopThu {
  so_chua_doc: number;
  items: ThongBao[];
}

export interface LuotDaLuu {
  thu_tu: number;
  cau_hoi: string;
  tra_loi: unknown;
  trace_id: string | null;
  tao_luc: string;
}

export interface ChiTietPhien {
  id: string;
  tieu_de: string;
  tao_luc: string;
  cap_nhat_luc: string;
  luot: LuotDaLuu[];
}

export interface SuKienLoiLuu {
  hoi_thoai_id: string;
  detail: string;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Kiểm hình dạng runtime.
 *
 * `ApiErrorKind.invalid_response` chỉ có nghĩa nếu có ai đó thật sự kiểm. Kiểm
 * ĐÚNG những trường mà sai đi sẽ hỏng ÂM THẦM — mảng thiếu render thành màn
 * trống đọc như "không có gì", `result_type` lạ rơi vào nhánh `answer` và hiện
 * một câu trả lời rỗng như thể đó là câu trả lời. Không kiểm những trường mà
 * sai đi thì thấy ngay bằng mắt (một tiêu đề trống là một tiêu đề trống).
 * ═══════════════════════════════════════════════════════════════════════════ */

const laBanGhi = (x: unknown): x is Record<string, unknown> =>
  typeof x === "object" && x !== null && !Array.isArray(x);

/** Mười loại backend biết trả. So khớp với `ResultType` của `src/models/schemas.py`
 *  bằng `test_FE_biet_moi_gia_tri_ResultType_cua_backend` (Python đọc file này). */
const LOAI_KET_QUA: readonly string[] = [
  "answer",
  "partial_coverage",
  "abstain",
  "out_of_scope",
  "gioi_thieu",
  "huong_dan_soan_thao",
  "hoi_ve_kho",
  "soan_thao_hoi",
  "ban_thao",
  "tai_lieu",
];

/**
 * Một `Bang` hợp lệ: `dong` phải khớp SỐ CỘT của `cot`, hàng nào lệch bị loại
 * ở đây — xem lời gọi trong `laTraCuuKetQua`.
 */
function laBang(x: unknown): x is Bang {
  if (!laBanGhi(x) || typeof x["tieu_de"] !== "string" || !Array.isArray(x["cot"])) return false;
  const cot = x["cot"];
  if (!cot.every((o) => typeof o === "string")) return false;
  const dong = x["dong"];
  return (
    Array.isArray(dong) &&
    dong.every(
      (hang) =>
        Array.isArray(hang) &&
        hang.length === cot.length &&
        hang.every((o) => typeof o === "string"),
    )
  );
}

export function laVanBanTraLoi(x: unknown): x is VanBanTraLoi {
  return (
    laBanGhi(x) &&
    typeof x["doc_id"] === "string" &&
    typeof x["ten"] === "string" &&
    typeof x["so_ky_hieu"] === "string" &&
    typeof x["loai_van_ban"] === "string" &&
    laBanGhi(x["links"])
  );
}

/**
 * Cùng khuôn `chuanHoaBang`: chạy TRƯỚC `laTraCuuKetQua`, thuần, không sửa `x`.
 * Khoá vắng → `[]` (payload cache cũ); phần tử sai hình dạng → loại.
 */
export function chuanHoaDocuments(x: unknown): unknown {
  if (!laBanGhi(x)) return x;
  const tho = x["documents"];
  return { ...x, documents: Array.isArray(tho) ? tho.filter(laVanBanTraLoi) : [] };
}

/**
 * Chuẩn hoá trường `bang` trên một bản ghi thô — THUẦN: trả về bản ghi MỚI,
 * không sửa `x`. Trường vắng mặt hoặc không phải mảng rơi về `[]`; một `Bang`
 * có `dong` lệch số cột với `cot` bị loại NGUYÊN CẢ BẢNG (xem `laBang`) — một
 * hàng thiếu ô hiện ra thành bảng méo chứ không thành lỗi và không ai biết,
 * còn một bảng biến mất thì thấy ngay.
 *
 * Gọi hàm này ở CHỖ GỌI (api.ts), TRƯỚC khi đưa kết quả cho `laTraCuuKetQua` —
 * xem doc ngay trên guard đó vì sao việc chuẩn hoá không còn nằm bên trong nó.
 * `x` không phải bản ghi thì trả nguyên `x`, để `laTraCuuKetQua` tự từ chối.
 */
export function chuanHoaBang(x: unknown): unknown {
  if (!laBanGhi(x)) return x;
  const bangTho = x["bang"];
  return { ...x, bang: Array.isArray(bangTho) ? bangTho.filter(laBang) : [] };
}

export function laTraCuuKetQua(x: unknown): x is TraCuuKetQua {
  // `result_type` chỉ cần là CHUỖI KHÔNG RỖNG — cố ý KHÔNG đòi nằm trong
  // `LOAI_KET_QUA`. Bản trước đòi, và một loại backend biết trả mà danh sách này
  // chưa biết làm cả response bị từ chối: người hỏi nhận "Máy chủ trả về dữ liệu
  // không đúng hình dạng" trong khi backend đã dựng xong câu trả lời (đo được
  // 2026-09-02, trace 8e32221d, `hoi_ve_kho`).
  //
  // FE và BE nay deploy RIÊNG (SPA mount đã gỡ khỏi `src/main.py`), nên backend đi
  // trước một nhịp là chuyện bình thường — và một nhãn lạ phải suy biến, đúng như
  // docstring đầu file này vẫn hứa, chứ không làm sập cả thẻ kết quả.
  //
  // Lo ngại cũ ("loại lạ rơi vào nhánh answer và hiện một câu trả lời rỗng như
  // thể đó là câu trả lời") nay do NHÁNH MẶC ĐỊNH của `TheKetQua` chịu: nó chỉ
  // hành văn khi có `answer`, còn không thì nói thật là chưa có. `LOAI_KET_QUA`
  // vẫn giữ để `test_FE_biet_moi_gia_tri_ResultType_cua_backend` so hai tập —
  // lỗi thiếu nhãn bị bắt ở CI, không bị bắt trên mặt người dùng.
  //
  // THUẦN — không sửa `x`. `bang` (T5) cố ý KHÔNG kiểm ở đây: hình dạng của nó
  // là việc của `chuanHoaBang`, hàm chuẩn hoá chạy Ở CHỖ GỌI trước khi `x` tới
  // được đây (xem `api.ts`). Một predicate mà tự sửa đối tượng nó đang kiểm là
  // mìn cho người sau — ai gọi một hàm `laX` trong `.filter()` hoặc để thăm dò
  // không cam kết sẽ không ngờ nó đổi dữ liệu.
  return (
    laBanGhi(x) &&
    typeof x["result_type"] === "string" &&
    x["result_type"].trim() !== "" &&
    Array.isArray(x["citations"]) &&
    Array.isArray(x["warnings"]) &&
    typeof x["trace_id"] === "string"
  );
}

export function laVanBanProvisions(x: unknown): x is VanBanProvisions {
  return laBanGhi(x) && typeof x["doc_id"] === "string" && Array.isArray(x["provisions"]);
}

export function laVanBanMucLuc(x: unknown): x is VanBanMucLuc {
  return laBanGhi(x) && typeof x["doc_id"] === "string" && Array.isArray(x["muc_luc"]);
}

export function laVanBanHieuLuc(x: unknown): x is VanBanHieuLuc {
  const vb = laBanGhi(x) ? x["van_ban"] : null;
  return (
    laBanGhi(x) &&
    laBanGhi(vb) &&
    typeof vb["verdict"] === "string" &&
    Array.isArray(x["dieu_khoan"])
  );
}

export function laVanBanLienQuan(x: unknown): x is VanBanLienQuan {
  return laBanGhi(x) && Array.isArray(x["nhom"]) && laBanGhi(x["dan_chieu_noi_bo"]);
}

export function laDanhSachPhien(x: unknown): x is DanhSachPhien {
  return laBanGhi(x) && Array.isArray(x["items"]) && typeof x["luot_moi_phien"] === "number";
}

export function laHoSo(x: unknown): x is HoSo {
  return (
    laBanGhi(x) &&
    Array.isArray(x["hoat_dong"]) &&
    Array.isArray(x["phan_loai"]) &&
    typeof x["plan"] === "string"
  );
}

export function laYeuCauNangGoi(x: unknown): x is YeuCauNangGoi {
  return (
    laBanGhi(x) &&
    typeof x["id"] === "number" &&
    typeof x["trang_thai"] === "string" &&
    (x["ly_do"] === null || typeof x["ly_do"] === "string")
  );
}

export function laYeuCauNangGoiHoacNull(x: unknown): x is YeuCauNangGoi | null {
  return x === null || laYeuCauNangGoi(x);
}

export function laHopThu(x: unknown): x is HopThu {
  return laBanGhi(x) && typeof x["so_chua_doc"] === "number" && Array.isArray(x["items"]);
}

export function laDaDanhDau(x: unknown): x is { da_danh_dau: number } {
  return laBanGhi(x) && typeof x["da_danh_dau"] === "number";
}

export function laNhapPhien(x: unknown): x is { id: string } {
  return laBanGhi(x) && typeof x["id"] === "string";
}

export function laPhienTomTat(x: unknown): x is PhienTomTat {
  return (
    laBanGhi(x) &&
    typeof x["id"] === "string" &&
    typeof x["tieu_de"] === "string" &&
    typeof x["so_luot"] === "number"
  );
}

export function laBoNhoTaiKhoan(x: unknown): x is BoNhoTaiKhoan {
  return laBanGhi(x) && typeof x["ghi_nho"] === "boolean" && Array.isArray(x["muc"]);
}

export function laDanhSachDaNho(x: unknown): x is DanhSachDaNho {
  return (
    laBanGhi(x) &&
    Array.isArray(x["muc"]) &&
    x["muc"].every(
      (m: unknown) =>
        laBanGhi(m) &&
        typeof m["id"] === "string" &&
        typeof m["nhan"] === "string" &&
        typeof m["gia_tri"] === "string",
    )
  );
}

/** Thân của `PATCH /hoi-thoai/{id}/ho-so` — chỉ kiểm mảng `ho_so_da_dung`
 *  tồn tại; hình dạng từng phần tử là việc của `TheKetQua`/`DuaTren`. */
export function laHoSoPhienOut(x: unknown): x is { ho_so_da_dung: HoSoDaDung[] } {
  return laBanGhi(x) && Array.isArray(x["ho_so_da_dung"]);
}

export function laChiTietPhien(x: unknown): x is ChiTietPhien {
  return laBanGhi(x) && typeof x["id"] === "string" && Array.isArray(x["luot"]);
}

/** Một lượt đã lưu → lượt render được. `tra_loi` đi đúng đường chuẩn hoá của stream
 *  (`chuanHoaBang` → `chuanHoaDocuments` → `laTraCuuKetQua`); payload cũ thiếu trường
 *  thì `ketQua: null` và card không render — không bịa. */
export function chuanHoaLuot(l: LuotDaLuu): {
  thuTu: number;
  cauHoi: string;
  ketQua: TraCuuKetQua | null;
  traceId: string | null;
} {
  const du = chuanHoaDocuments(chuanHoaBang(l.tra_loi));
  return {
    thuTu: l.thu_tu,
    cauHoi: l.cau_hoi,
    ketQua: laTraCuuKetQua(du) ? du : null,
    traceId: l.trace_id,
  };
}

export function laTimKiem(x: unknown): x is TimKiem {
  return (
    laBanGhi(x) &&
    Array.isArray(x["ket_qua"]) &&
    typeof x["tong_dieu_khoan"] === "number" &&
    typeof x["tong_van_ban"] === "number"
  );
}

export function laDanhSachVanBan(x: unknown): x is DanhSachVanBan {
  return laBanGhi(x) && Array.isArray(x["ket_qua"]) && typeof x["tong"] === "number";
}

export function laBoLoc(x: unknown): x is BoLoc {
  return (
    laBanGhi(x) &&
    Array.isArray(x["loai_van_ban"]) &&
    Array.isArray(x["co_quan_ban_hanh"]) &&
    Array.isArray(x["sap_xep"])
  );
}

export function laTimTrongVanBan(x: unknown): x is TimTrongVanBan {
  return laBanGhi(x) && Array.isArray(x["ket_qua"]) && typeof x["tong"] === "number";
}

export function laMau(x: unknown): x is Mau {
  return laBanGhi(x) && Array.isArray(x["facts"]);
}

export function laSoanThaoKetQua(x: unknown): x is SoanThaoKetQua {
  const bc = laBanGhi(x) ? x["audit_report"] : null;
  return (
    laBanGhi(x) &&
    typeof x["document"] === "string" &&
    laBanGhi(bc) &&
    Array.isArray(bc["findings"])
  );
}

/**
 * Mã loại của một bản thảo KHÔNG theo checklist nào (`src/agents/nodes/
 * dung_ban_thao_tong_quat.py`). Không có `GET /mau/tong_quat`, nên mọi chỗ nạp
 * khung mẫu theo `loai` phải bỏ qua giá trị này.
 */
export const LOAI_TONG_QUAT = "tong_quat";

/**
 * Nhãn MỨC KIỂM của một bản thảo (CONTEXT.md "mức kiểm") — `null` khi bản thảo
 * đi đường checklist + rules + audit như trước (ở đó `SoatBanThao` đã nói rõ
 * từng rule đã chạy hay chưa, nên thêm một nhãn nữa chỉ làm loãng).
 *
 * Phase 14 (quyết định owner D14-A) — bản thảo TỔNG QUÁT (mô hình soạn trong
 * chat) KHÔNG còn đeo nhãn nào: từ phase này chat soạn được mọi loại văn bản,
 * và owner đã chọn bỏ nhãn đó với cái giá đã nói rõ (người dùng tải về một văn
 * bản lao động mà không thấy phân biệt "chưa qua checklist"). Chỉ NHÃN biến
 * mất — `audit_report.muc_kiem` phía backend vẫn ghi đúng đường đã chạy, nên
 * hệ thống, trace và mọi lần soát sau vẫn phân biệt được.
 *
 * Phase 3 (Half A, R3/D3) GIỮ NGUYÊN: `sua_tay` (`src/services/ban_thao.py`)
 * đặt cùng giá trị `muc_kiem` khi một sửa TAY hạ cấp một bản thảo CHECKLIST
 * (đã qua rule/audit thật). Đó là một sự thật KHÁC — "đã bị viết đè SAU khi
 * kiểm", không phải "chưa từng kiểm" — và nó nói về một bản thảo checklist,
 * không phải bản thảo soạn trong chat, nên D14-A không chạm tới nó.
 *
 * `loai` là thứ PHÂN BIỆT được hai ca đó, và nó BẮT BUỘC: `sua_tay` ghi cùng
 * một `audit_report` cho cả hai loại bản thảo, nên riêng `audit_report` không
 * nói được bản thảo này sinh ra từ chat hay từ checklist.
 */
export function nhanMucKiem(
  auditReport: Record<string, unknown> | undefined,
  loai: string | undefined,
): string | null {
  if (loai === LOAI_TONG_QUAT) return null;
  if (auditReport?.["muc_kiem"] !== LOAI_TONG_QUAT) return null;
  return auditReport["sua_tay"] === true ? "Đã sửa tay — chưa kiểm pháp lý" : null;
}

/**
 * Fix round 2 (re-review N2) — bản sao NGUYÊN VĂN của `ban_thao.
 * LOI_PHIEN_BAN_DA_DOI` phía backend, để `SanKhauBanThao.onSuaKhoi` phân biệt
 * được lỗi NÀY (retry một lần an toàn được, nếu tự mình vừa gây ra) với ba lỗi
 * 422 khác cùng route (khối là bảng, mục không thấy, hết trần sửa — không nên
 * retry). `docDetail`/`loiTheoStatus` (`api.ts`) đưa nguyên câu `detail` của
 * FastAPI vào `error.message`, nên so chuỗi ở đây là đúng hợp đồng, không
 * phải suy đoán mã trạng thái. Sống ở đây (không phải `api.ts`, vốn kéo theo
 * `@/integrations`) để `kiem-ban-thao.ts` import thẳng được, không cần một
 * bundler phân giải alias.
 */
export const LOI_PHIEN_BAN_DA_DOI =
  "Bản thảo đã đổi (một lượt sửa khác vừa chạy) — tải lại bản thảo trước khi sửa tiếp.";

/**
 * Fix round 2 (N1/N2) — có nên tự động gửi lại MỘT lần một PATCH `/ban-thao/
 * {id}/muc` vừa bị từ chối vì lệch phiên bản hay không. Hàm THUẦN, tách khỏi
 * `SanKhauBanThao.onSuaKhoi` để kiểm được không cần dựng React/DOM (xem
 * `kiem-ban-thao.ts`) — sai điều kiện này tái mở N1 (ghi đè lên đúng vị trí
 * nhưng sai mục, vì `muc_key` bị cấp lại theo vị trí sau một lượt sửa bằng
 * lời) hoặc N2 (từ chối một lượt sửa tay bình thường thứ hai của cùng
 * client), nên xứng một bài kiểm riêng hơn một `if` trần lẫn trong callback.
 *
 * Chỉ retry khi CẢ BỐN đúng: có lỗi, lỗi đó CHÍNH XÁC là lệch phiên bản
 * (không phải khối-là-bảng/mục-không-thấy/hết-trần-sửa — ba lỗi 422 khác
 * cùng route, không nên retry), phiên bản đã gửi thật sự khác phiên bản hiện
 * tại, VÀ phiên bản hiện tại khớp đúng phiên bản do CHÍNH client này tạo ra ở
 * lần lưu thành công gần nhất — điều kiện cuối là thứ phân biệt "một khối
 * khác của chính mình vừa lưu xong" (an toàn để gửi lại) khỏi "một lượt sửa
 * bằng lời vừa chạy xong nơi khác" (N1b — không được gửi lại).
 */
export function neenGuiLaiPhienBan(
  loi: { message: string } | null,
  phienBanDaGui: number,
  phienBanHienTai: number,
  phienBanTuSuaTayGanNhat: number,
): boolean {
  return (
    loi !== null &&
    loi.message === LOI_PHIEN_BAN_DA_DOI &&
    phienBanDaGui !== phienBanHienTai &&
    phienBanTuSuaTayGanNhat === phienBanHienTai
  );
}

/* ── /ban-thao — bản thảo đã lưu của tài khoản (Task 21) ─────────────────── */

export function laBanThao(x: unknown): x is BanThao {
  return laBanGhi(x) && typeof x["id"] === "string" && typeof x["document"] === "string";
}

const laSoTuNhien = (x: unknown): x is number => Number.isInteger(x) && (x as number) >= 0;

/**
 * `BanThao.khuon` → khuôn dùng được, hoặc `null` (bản thảo HTML, hay vỏ sai:
 * không biết định dạng thì không biết tải gì, không vẽ được trang nào).
 *
 * Fail-closed TỪNG Ô, không cả khuôn: một ô dị dạng bị bỏ, các ô còn lại vẫn
 * điền được. Ô trùng `(don_vi, so)` giữ ô ĐẦU — hai ô cùng khoá là hai ô nhập
 * cùng ghi vào một chỗ. Chỉ khoá của hợp đồng đi ra, không khoá lạ nào lọt.
 */
export function khuonHopLe(x: unknown): KhuonBanThao | null {
  if (
    !laBanGhi(x) ||
    typeof x["viec_id"] !== "string" ||
    x["viec_id"] === "" ||
    (x["dinh_dang"] !== "docx" && x["dinh_dang"] !== "pdf") ||
    !Number.isInteger(x["so_trang"]) ||
    (x["so_trang"] as number) < 1
  )
    return null;
  const daCo = new Set<string>();
  const choTrong: ChoTrongKhuon[] = [];
  for (const c of Array.isArray(x["cho_trong"]) ? x["cho_trong"] : []) {
    if (
      !laBanGhi(c) ||
      !laSoTuNhien(c["don_vi"]) ||
      !laSoTuNhien(c["so"]) ||
      typeof c["kieu"] !== "string" ||
      typeof c["nhan"] !== "string" ||
      (c["gia_tri"] !== undefined && c["gia_tri"] !== null && typeof c["gia_tri"] !== "string")
    )
      continue;
    const khoa = `${c["don_vi"]}.${c["so"]}`;
    if (daCo.has(khoa)) continue;
    daCo.add(khoa);
    choTrong.push({
      don_vi: c["don_vi"],
      so: c["so"],
      kieu: c["kieu"],
      nhan: c["nhan"],
      gia_tri: typeof c["gia_tri"] === "string" ? c["gia_tri"] : null,
    });
  }
  return {
    viec_id: x["viec_id"],
    dinh_dang: x["dinh_dang"],
    so_trang: x["so_trang"] as number,
    cho_trong: choTrong,
  };
}

/** Base64 TRẦN (không tiền tố `data:`, không khoảng trắng) — thứ duy nhất được
 *  ghép vào `data:image/png;base64,…`. */
const BASE64 = /^[A-Za-z0-9+/]+={0,2}$/;
/** Khổ trang máy chủ đã kiểm (ISO 32000-1 Annex C, `routes_tai_lieu.trang`). */
const KHO_TOI_DA_PT = 14_400;
const laKhoPt = (n: unknown) =>
  typeof n === "number" && Number.isFinite(n) && n > 0 && n <= KHO_TOI_DA_PT;

/** Payload trang: cả gói hoặc không gì — một ảnh thiếu khổ (hay ngược lại) là
 *  trang vẽ sai tỉ lệ hoặc sai thứ tự, tệ hơn một lời báo lỗi. */
export function laTrangAnh(x: unknown): x is TrangAnh {
  if (!laBanGhi(x) || !Array.isArray(x["kho"]) || !Array.isArray(x["trang"])) return false;
  const kho: unknown[] = x["kho"];
  const trang: unknown[] = x["trang"];
  return (
    kho.length > 0 &&
    kho.length === trang.length &&
    kho.every((k) => Array.isArray(k) && k.length === 2 && laKhoPt(k[0]) && laKhoPt(k[1])) &&
    trang.every((t) => typeof t === "string" && BASE64.test(t))
  );
}

/**
 * `TrangAnh.o` → chỗ trống dùng được, hoặc `null` khi payload không mang `o`
 * (máy chủ cũ: nơi gọi tự lùi về `khuon.cho_trong`, không để người dùng mất
 * đường điền).
 *
 * Fail-closed TỪNG ô như `khuonHopLe`: ô dị dạng bị bỏ, ô trùng `(don_vi, so)`
 * giữ ô ĐẦU. Vị trí không tin được (trang ngoài `kho`, hộp ngược hay ra ngoài
 * trang) KHÔNG làm rơi ô — ô vẫn điền được, chỉ thành "chưa định vị".
 */
export function oHopLe(x: unknown, kho: readonly [number, number][]): OTrang[] | null {
  if (!Array.isArray(x)) return null;
  const daCo = new Set<string>();
  const ra: OTrang[] = [];
  for (const c of x as unknown[]) {
    if (
      !laBanGhi(c) ||
      !laSoTuNhien(c["don_vi"]) ||
      !laSoTuNhien(c["so"]) ||
      typeof c["nhan"] !== "string" ||
      (c["gia_tri"] !== undefined && c["gia_tri"] !== null && typeof c["gia_tri"] !== "string")
    )
      continue;
    const khoa = `${c["don_vi"]}.${c["so"]}`;
    if (daCo.has(khoa)) continue;
    daCo.add(khoa);
    const t = c["trang"];
    const h = c["hop"];
    const khoTrang = laSoTuNhien(t) ? kho[t] : undefined;
    const hop =
      khoTrang !== undefined &&
      Array.isArray(h) &&
      h.length === 4 &&
      h.every((v) => typeof v === "number" && Number.isFinite(v)) &&
      h[0] >= 0 &&
      h[1] >= 0 &&
      h[0] < h[2] &&
      h[1] < h[3] &&
      h[2] <= khoTrang[0] &&
      h[3] <= khoTrang[1]
        ? (h as [number, number, number, number])
        : null;
    ra.push({
      don_vi: c["don_vi"],
      so: c["so"],
      trang: hop === null ? null : (t as number),
      hop,
      nhan: c["nhan"],
      gia_tri: typeof c["gia_tri"] === "string" ? c["gia_tri"] : null,
    });
  }
  return ra;
}

export function laDanhSachBanThao(x: unknown): x is { tong: number; items: BanThaoTomTat[] } {
  return laBanGhi(x) && Array.isArray(x["items"]);
}

export function laHanMuc(x: unknown): x is HanMuc {
  return (
    laBanGhi(x) &&
    typeof x["ap_dung"] === "boolean" &&
    Array.isArray(x["muc"]) &&
    laBanGhi(x["phien"]) &&
    // Backend cũ có thể chưa gửi `bi_khoa` — `laBiKhoa` đã coi `undefined` là
    // "không khoá", nên không chặn cả thanh đo hạn mức chỉ vì thiếu trường này.
    (x["bi_khoa"] === undefined || typeof x["bi_khoa"] === "boolean")
  );
}

export function laPhamVi(x: unknown): x is PhamVi {
  const sau = laBanGhi(x) ? x["sau"] : null;
  const nong = laBanGhi(x) ? x["nong"] : null;
  return laBanGhi(sau) && laBanGhi(nong) && Array.isArray(sau["van_ban"]);
}

/**
 * `tin_cay` / `do_tin_cay` là ĐỊNH DANH MÁY, không phải chữ cho người đọc.
 *
 * Backend gửi `trung_binh`; in thẳng lên màn hình thì người dùng đọc được dấu
 * gạch dưới của một enum ngay dưới nhãn hiệu lực — đúng chỗ sản phẩm đang xin
 * người ta tin mình. Lược đồ khai trường này là `string` tự do, nên nhãn lạ
 * trả về NGUYÊN CHUỖI: cùng lối an toàn với `BadgeHieuLuc`, không đoán nghĩa
 * một giá trị mình chưa biết.
 */
export function docDoTinCay(giaTri: string): string {
  switch (giaTri) {
    case "cao":
      return "cao";
    case "trung_binh":
      return "trung bình";
    case "thap":
      return "thấp";
    default:
      return giaTri;
  }
}
