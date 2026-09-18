import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { cn } from "@/lib/utils";
import {
  catTheoChu,
  kieuNetCSS,
  netCanh,
  nhipHangVe,
  phongTrenManHinh,
  PT_MOI_TWIP,
  soCotThat,
  THUOC_TINH_BANG,
  THUOC_TINH_CHU,
  THUOC_TINH_GIAN_CACH,
  THUOC_TINH_LE,
  THUOC_TINH_TAB,
  tiLeCotVe,
  type CanLe,
  type DoanChu,
  type GianCachKhoi,
  type KhoangChu,
  type KhoangTab,
  type LeTrang,
  type MocTab,
  type Muc,
} from "@/lib/xuat-tep";

/** Bề rộng trang A4 theo twip (210mm) — mẫu số quy `w:pgMar` ra % của khung
 *  xem trước. Phần trăm chứ không `pt`: khung A4 ở đây co theo bề rộng nơi
 *  đặt nó (`w-full max-w-[794px]`), nên một lề đo tuyệt đối sẽ lệch ngay khi
 *  khung hẹp lại. CSS tính MỌI `padding` theo phần trăm trên BỀ RỘNG, kể cả
 *  trên/dưới — nên cả bốn lề cùng chia cho con số này, đúng cách lớp
 *  `px-[8%] py-[7%]` cũ vẫn làm. */
const RONG_A4_TWIP = 11906;

/** Cỡ chữ "thường" của thể thức hành chính, điểm — mốc quy `w:sz` (nửa điểm)
 * ra `em`. Khớp `xuat-tep.ts::coChuPt("thuong")` và `size: 26` của `.docx`,
 * nên ba nơi vẽ cùng gọi một cỡ là "cỡ thường". */
const CO_THUONG_PT = 13;

/** `w:leader` → kiểu nét CSS vẽ ra nó. `dot`/`middleDot` là hàng chấm quen
 *  thuộc của một dòng điền tay, `hyphen` là gạch ngắn, `underscore` là nét
 *  liền. Giá trị nào không có ở đây thì không vẽ gì — mặc định của chính
 *  `w:leader` là `none`, và đoán thêm một nét là vẽ thứ tệp không hề nói. */
const NET_DAN: Record<string, NonNullable<CSSProperties["borderBottomStyle"]>> = {
  dot: "dotted",
  middleDot: "dotted",
  hyphen: "dashed",
  underscore: "solid",
};

/**
 * MỘT mốc tab → thuộc tính `data-*` (tệp tải về đọc lại) và `style` (màn hình
 * vẽ) của `<span>` chở nó.
 *
 * Bề rộng ĐẨY bằng 0 (`margin-right` âm đúng bằng `width`): đường dẫn phải vẽ
 * dài tới mốc mà KHÔNG được tự đẩy mình xuống dòng — một hộp rộng 468pt trong
 * một dòng còn trống 100pt sẽ xuống dòng, và cả đường dẫn rơi xuống một dòng
 * trống của riêng nó. Phần vẽ tràn quá mép chữ bị `<p>` cắt (`overflow:
 * hidden`, xem `kieuGianCach`).
 *
 * ponytail: màn hình vẫn vẽ đường dẫn DÀI bằng chính toạ độ mốc rồi để trang
 * cắt, chứ không nhảy con trỏ tới đúng mốc như Word (`.docx`) và PDF làm.
 *
 * Lề trang nguồn (`w:pgMar`) nay ĐÃ đọc được, và nó sửa đúng nửa vấn đề mà
 * ghi chú cũ nêu: chỗ CẮT. Trước bản vá lề, `<p>` rộng bằng khung xem trước
 * trừ lề 8% tự đặt (≈16,8mm trên A4), nên một dòng "……" điền tay chạy quá mép
 * chữ THẬT của biểu mẫu (lề phải 20mm) vài milimét — nay `<article>` lấy đúng
 * `w:pgMar`, nên mép cắt LÀ mép cột chữ của nguồn. Với mốc tab phải ở cuối
 * dòng — 68/134 mốc `dot` đo trên tám biểu mẫu thật — đường dẫn giờ dừng đúng
 * chỗ Word dừng.
 *
 * Nửa còn lại KHÔNG phải lề trang mở ra được: một mốc nằm GIỮA cột chữ vẫn bị
 * vẽ quá tới mép phải, vì điểm BẮT ĐẦU là chỗ con trỏ đang đứng, và biết chỗ
 * đó thì phải ĐO chữ đã vẽ (JS, sau khi trình duyệt dựng xong) — CSS thuần
 * không có cách nào. Nâng lên khi có một phép đo như vậy, không phải khi có
 * thêm một sự thật nguồn.
 */
function thuocTinhTab(m: MocTab): { thuoc: Record<string, string>; style: CSSProperties } {
  const thuoc: Record<string, string> = {
    [THUOC_TINH_CHU.moc]: "",
    [THUOC_TINH_TAB.moc]: "",
    [THUOC_TINH_TAB.val]: m.val,
    [THUOC_TINH_TAB.pos]: String(m.pos),
  };
  if (m.leader) thuoc[THUOC_TINH_TAB.leader] = m.leader;
  const net = NET_DAN[m.leader];
  if (!net) return { thuoc, style: {} };
  const rong = `${m.pos * PT_MOI_TWIP}pt`;
  return {
    thuoc,
    style: {
      display: "inline-block",
      width: rong,
      marginRight: `-${rong}`,
      borderBottomWidth: "1px",
      borderBottomStyle: net,
      verticalAlign: "baseline",
    },
  };
}

/**
 * Giãn cách/thụt lề NGUỒN của một khối → `data-*` (tệp tải về đọc lại) và
 * `style` (màn hình vẽ) của thẻ `<p>` chở nó.
 *
 * Đơn vị `pt`, không `em`: trang A4 ở đây rộng cố định và `thuPhong` chỉ phóng
 * CỠ CHỮ, nên một khoảng cách đo bằng `em` sẽ trôi theo mức phóng — đúng lý lẽ
 * `caoTrenTrang` đã theo cho `w:trHeight`.
 *
 * `text-indent` mang HIỆU `firstLine − hanging`, một số duy nhất: hai thuộc
 * tính ấy loại trừ nhau trong OOXML và cùng nói về dòng ĐẦU, còn `margin-left`
 * đã chở `w:ind/@w:left` cho mọi dòng. Đây cũng đúng `lechDau` mà PDF dùng.
 *
 * Khối CÓ khai nhịp thì nhịp nguồn thắng HẲN, kể cả chỗ nó khai 0: `mt-1` của
 * lớp CSS là thể thức của một bản thảo KLAW tự soạn, không phải câu trả lời
 * về tài liệu của khách — cùng luật `.docx`/PDF đặt.
 */
function kieuGianCach(g: GianCachKhoi | null): {
  thuoc: Record<string, string>;
  style: CSSProperties;
} {
  if (!g) return { thuoc: {}, style: {} };
  const pt = (twip: number) => `${twip * PT_MOI_TWIP}pt`;
  const thuoc: Record<string, string> = {};
  const style: CSSProperties = { marginTop: pt(g.truoc), marginBottom: pt(g.sau) };
  if (g.truoc) thuoc[THUOC_TINH_GIAN_CACH.truoc] = String(g.truoc);
  if (g.sau) thuoc[THUOC_TINH_GIAN_CACH.sau] = String(g.sau);
  if (g.dong > 0) {
    thuoc[THUOC_TINH_GIAN_CACH.dong] = String(g.dong);
    if (g.luatDong) thuoc[THUOC_TINH_GIAN_CACH.luatDong] = g.luatDong;
    // `auto` đo theo BỘI SỐ của 240 (một hệ số không đơn vị); `exact`/`atLeast`
    // là twip tuyệt đối. `line-height` của CSS nhận đúng hai hình dạng ấy.
    style.lineHeight = g.luatDong === "auto" || !g.luatDong ? String(g.dong / 240) : pt(g.dong);
  }
  if (g.trai) {
    thuoc[THUOC_TINH_GIAN_CACH.trai] = String(g.trai);
    style.marginLeft = pt(g.trai);
  }
  if (g.phai) {
    thuoc[THUOC_TINH_GIAN_CACH.phai] = String(g.phai);
    style.marginRight = pt(g.phai);
  }
  if (g.dauDong) thuoc[THUOC_TINH_GIAN_CACH.dauDong] = String(g.dauDong);
  if (g.treo) thuoc[THUOC_TINH_GIAN_CACH.treo] = String(g.treo);
  if (g.dauDong || g.treo) style.textIndent = pt(g.dauDong - g.treo);
  // Đường dẫn của một mốc tab cố tình vẽ dài quá mép chữ (xem `thuocTinhTab`);
  // chính thẻ này là chỗ cắt nó lại đúng bề rộng cột chữ.
  if (g.tab.length > 0) style.overflow = "hidden";
  return { thuoc, style };
}

/**
 * MỘT đoạn chữ → thuộc tính `data-*` (tệp tải về đọc lại) và `style` (màn
 * hình vẽ) của `<span>` chở nó.
 *
 * Chỗ DUY NHẤT dịch một sự thật định dạng thành hình: HAI đường vẽ span dùng
 * chung nó — `veChuVaoThe` (khối văn xuôi, dựng DOM bằng tay vì khối gõ
 * được) và `OChu` (ô bảng, dựng bằng JSX vì ô chỉ đọc). Hai cách dựng không
 * được ra hai kết quả; `docDoanChu` chỉ biết một bộ thuộc tính.
 *
 * Cỡ chữ ra `em` chứ không `pt`: `thuPhong` phóng CỠ CHỮ của cả trang (không
 * phóng trang), nên một cỡ tuyệt đối sẽ đứng yên trong khi chữ quanh nó to
 * lên — ngược hẳn `caoTrenTrang`, nơi `pt` mới đúng vì đó là kích thước vật
 * lý. `data-co` vẫn chở nửa-điểm NGUỒN để tệp tải về ghi đúng con số ấy.
 *
 * Phông: `data-phong` giữ TÊN NGUỒN cho `.docx`, còn màn hình chỉ đặt
 * `font-family` khi `phongTrenManHinh` nhận ra hạng chữ — không nhận ra thì
 * giữ phông của trang thay vì khai một họ chữ kho này không có.
 */
function thuocTinhChu(o: DoanChu): { thuoc: Record<string, string>; style: CSSProperties } {
  if (o.tab) return thuocTinhTab(o.tab);
  const thuoc: Record<string, string> = { [THUOC_TINH_CHU.moc]: "" };
  const style: CSSProperties = {};
  if (o.inDam) {
    thuoc[THUOC_TINH_CHU.dam] = "1";
    style.fontWeight = "700";
  }
  if (o.inNghieng) {
    thuoc[THUOC_TINH_CHU.nghieng] = "1";
    style.fontStyle = "italic";
  }
  if (o.gachChan) {
    thuoc[THUOC_TINH_CHU.gach] = "1";
    style.textDecoration = "underline";
  }
  if (o.coChu > 0) {
    thuoc[THUOC_TINH_CHU.co] = String(o.coChu);
    style.fontSize = `${o.coChu / 2 / CO_THUONG_PT}em`;
  }
  if (o.phong) {
    thuoc[THUOC_TINH_CHU.phong] = o.phong;
    const ho = phongTrenManHinh(o.phong);
    if (ho) style.fontFamily = ho;
  }
  return { thuoc, style };
}

/**
 * Vẽ `noiDung` vào một thẻ, cắt theo `chu` thành các `<span data-chu>`.
 *
 * Mọi đoạn đều là một `<span data-chu>`, KỂ CẢ đoạn không định dạng gì: nhờ
 * vậy `docDoanChu` (xuat-tep.ts) nối `textContent` của chúng lại là được
 * đúng chữ của dòng, không phải đi qua `childNodes` để nhặt phần chữ nằm
 * ngoài span nào — cùng khuôn `data-*` mà `docBangTuPhanTu` đã dùng để
 * `.docx`/PDF đọc lại đúng thứ màn hình đã vẽ.
 */
function veChuVaoThe(el: HTMLElement, noiDung: string, chu: KhoangChu[], tab: KhoangTab[] = []) {
  if (chu.length === 0 && tab.length === 0) {
    el.textContent = noiDung;
    return;
  }
  el.textContent = "";
  for (const o of catTheoChu(noiDung, chu, tab)) {
    const s = document.createElement("span");
    const { thuoc, style } = thuocTinhChu(o);
    for (const [ten, giaTri] of Object.entries(thuoc)) s.setAttribute(ten, giaTri);
    Object.assign(s.style, style);
    s.textContent = o.text;
    el.appendChild(s);
  }
}

/**
 * Chữ của MỘT Ô bảng — từng đoạn một `<span data-chu>` khi nguồn khai định
 * dạng (`BangThat.chuO`), chữ trần khi không.
 *
 * Dựng bằng JSX chứ không `veChuVaoThe`: ô bảng CHỈ ĐỌC (không
 * `contentEditable`, xem `Props.onSuaKhoi`), nên không có lý do nào phải
 * đồng bộ DOM bằng tay như khối văn xuôi gõ được. Cả hai vẫn đi qua CÙNG
 * `thuocTinhChu`, nên `docBangTuPhanTu`/`docDoanChu` đọc lại được y hệt.
 */
function OChu({ noiDung, chu }: { noiDung: string; chu: DoanChu[] }) {
  if (chu.length === 0) return <>{noiDung}</>;
  return (
    <>
      {chu.map((o, i) => {
        const { thuoc, style } = thuocTinhChu(o);
        return (
          <span key={i} {...thuoc} style={style}>
            {o.text}
          </span>
        );
      })}
    </>
  );
}

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
  luat = "",
): { twip: number; style: { height: string } } | undefined {
  // `hRule="auto"` BỎ con số: Word bỏ nó ở đó, nên ép một chiều cao tối thiểu
  // là vẽ thứ tệp không nói. `exact` vẫn chỉ là SÀN (`height` của CSS trên một
  // `<tr>` là tối thiểu, không cắt chữ) — cùng lựa chọn `bangThanhTable` và
  // PDF `caoKhaiMm`, xem `DonViVanBan.bang_cao_luat`.
  if (luat === "auto") return undefined;
  return twip && twip > 0 ? { twip, style: { height: `${twip / 20}pt` } } : undefined;
}

/**
 * Viền NGUỒN của MỘT Ô (`"trên|phải|dưới|trái"`, mỗi phần `"w:val/w:sz"`) →
 * `style` (màn hình vẽ) và `data-vien-o` (tệp tải về đọc lại) — `null` khi
 * bảng không có chi tiết theo cạnh, và khi đó ô giữ lớp viền đều như trước.
 *
 * Bốn cạnh viết THẲNG ra chứ không lặp qua tên: `CSSProperties` của React
 * không nhận khoá dựng bằng chuỗi mà vẫn giữ được kiểu, và mười hai dòng rõ
 * ràng đáng hơn một vòng lặp phải `as` bốn lần để qua mặt trình kiểm kiểu.
 */
function kieuVienO(
  tho: string | undefined,
): { thuoc: Record<string, string>; style: CSSProperties } | null {
  if (tho === undefined) return null;
  const c = tho.split("|").map(netCanh);
  // `w:sz` là ⅛ điểm — cùng phép quy đổi `bangThanhTable` (`size` của `docx`
  // nhận thẳng `w:sz`) và PDF `veCanhO` dùng, nên ba nơi kẻ một nét dày bằng nhau.
  const day = (i: number) => (c[i] ? `${c[i]!.sz / 8}pt` : "0");
  const kieu = (i: number) => (c[i] ? kieuNetCSS(c[i]!.val) : ("none" as const));
  return {
    thuoc: { [THUOC_TINH_BANG.vienO]: tho },
    style: {
      borderTopWidth: day(0),
      borderTopStyle: kieu(0),
      borderTopColor: "#999",
      borderRightWidth: day(1),
      borderRightStyle: kieu(1),
      borderRightColor: "#999",
      borderBottomWidth: day(2),
      borderBottomStyle: kieu(2),
      borderBottomColor: "#999",
      borderLeftWidth: day(3),
      borderLeftStyle: kieu(3),
      borderLeftColor: "#999",
    },
  };
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
  chu,
  gianCach,
  mucKey,
  khoiIndex,
  phienBan,
  onSuaKhoi,
}: {
  noiDung: string;
  canhLe: CanLe;
  /**
   * Định dạng chữ NGUỒN của khối (2026-09-18) — vẽ bằng `veChuVaoThe`, cùng
   * đường `useLayoutEffect` mà `noiDung` đi, không qua `children` JSX.
   *
   * Một lượt gõ TAY vào khối làm mất định dạng của chính khối đó: chữ đã đổi
   * thì `_chu_theo_dong` phía máy chủ không tra được dòng nào nữa và trả về
   * rỗng. Đó là câu trả lời đúng — khoảng `[dau, cuoi)` đo trên chữ CŨ mà áp
   * lên chữ MỚI sẽ in đậm nửa từ, tệ hơn hẳn chữ thường.
   */
  chu: KhoangChu[];
  /**
   * Giãn cách/thụt lề/mốc tab NGUỒN của khối (2026-09-18) — đi ra `style` và
   * `data-*` của chính thẻ `<p>` này qua `kieuGianCach`, để `docDong`
   * (`xuat-tep.ts`) đọc lại đúng con số nguồn khi xuất `.docx`/PDF.
   *
   * `null` khi khối không tra được dòng nguồn nào: cùng luật `chu` — chữ đã
   * đổi thì mọi sự thật đo trên chữ CŨ đều không còn áp được.
   */
  gianCach: GianCachKhoi | null;
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
  // Khoá SO SÁNH của định dạng, không phải chính mảng: `chu` là một mảng mới
  // ở mỗi lượt render (`khoiMotHopLe` dựng lại), nên so tham chiếu sẽ vẽ lại
  // khối ở mọi lượt — kể cả những lượt không đổi gì.
  const chuKhoa = JSON.stringify([chu, gianCach?.tab ?? []]);
  const { thuoc: thuocNhip, style: kieuNhip } = kieuGianCach(gianCach);

  useLayoutEffect(() => {
    if (dangSua.current) return;
    const el = oNoiDung.current;
    if (!el) return;
    if (el.textContent === noiDung && el.getAttribute("data-chu-khoa") === chuKhoa) return;
    veChuVaoThe(el, noiDung, chu, gianCach?.tab ?? []);
    el.setAttribute("data-chu-khoa", chuKhoa);
  }, [noiDung, chuKhoa, chu, gianCach]);

  return (
    <p
      ref={oNoiDung}
      {...thuocNhip}
      style={kieuNhip}
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
            // Vẽ LẠI cả định dạng, không chỉ chữ: gán `textContent` ở đây sẽ
            // xoá sạch các `<span data-chu>` mà hiệu ứng đã dựng, và khối
            // mất định dạng chỉ vì người dùng bấm vào rồi bấm ra.
            if (oNoiDung.current) {
              veChuVaoThe(oNoiDung.current, noiDung, chu, gianCach?.tab ?? []);
              oNoiDung.current.setAttribute("data-chu-khoa", chuKhoa);
            }
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
  /**
   * Lề trang NGUỒN (`w:sectPr/w:pgMar`, twip) của tài liệu khách tải lên —
   * `null`/vắng mặt thì trang giữ lề 8%/7% tự đặt của khung xem trước, đúng
   * hành vi trước bản vá này (và đúng cho một bản thảo KLAW tự soạn, vốn
   * không có tài liệu nguồn nào để lấy lề).
   *
   * Đặt bằng `padding` trên chính `<article>` — không phải một khung lồng
   * thêm: `docNoiDungTuDOM` nhận đúng thẻ này làm `sheet`, nên lề đọc lại cho
   * `.docx`/PDF và lề vẽ ra màn hình là MỘT con số, không hai.
   */
  leTrang?: LeTrang | null;
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
  leTrang = null,
}: Props) {
  const chonMuc = (key: string) => onChonMuc?.(key);

  // Lề trang: `padding` (vẽ) và `data-le-*` (tệp tải về đọc lại) đến từ CÙNG
  // một bộ số, cùng khuôn `data-cao`/`data-can-le` của bảng. Không có lề nguồn
  // thì cả hai vắng mặt và lớp `px-[8%] py-[7%]` cũ giữ nguyên trang.
  const pcLe = (twip: number) => `${(twip / RONG_A4_TWIP) * 100}%`;
  const kieuLe: CSSProperties | undefined = leTrang
    ? {
        paddingTop: pcLe(leTrang.tren),
        paddingRight: pcLe(leTrang.phai),
        paddingBottom: pcLe(leTrang.duoi),
        paddingLeft: pcLe(leTrang.trai),
      }
    : undefined;
  const thuocLe: Record<string, string> = leTrang
    ? {
        [THUOC_TINH_LE.tren]: String(leTrang.tren),
        [THUOC_TINH_LE.phai]: String(leTrang.phai),
        [THUOC_TINH_LE.duoi]: String(leTrang.duoi),
        [THUOC_TINH_LE.trai]: String(leTrang.trai),
        [THUOC_TINH_LE.dauTrang]: String(leTrang.dauTrang),
        [THUOC_TINH_LE.chanTrang]: String(leTrang.chanTrang),
      }
    : {};

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
      <article
        className={cn(
          "aspect-[210/297] overflow-y-auto rounded-md border border-border bg-white text-[#111] shadow-soft",
          leTrang === null && "px-[8%] py-[7%]",
        )}
        style={kieuLe}
        {...thuocLe}
      >
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
                    chu={k.chu}
                    gianCach={k.gianCach}
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
                  // chỗ để ký tay), và chữ TRONG ô giữ định dạng run của
                  // nguồn (`k.chuO`, `w:rPr` — `OChu` vẽ từng `<span
                  // data-chu>`, xem chú thích ở đó). Bốn thứ đó đi ra DOM
                  // thành `data-vien`/`data-can-le`/`data-cao`/`data-chu` để
                  // `docBangTuPhanTu` đọc lại khi xuất `.docx`/PDF: một
                  // nguồn, ba nơi dùng.
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
                    // Không có ghi chú "bảng chưa sửa trực tiếp được" ở đây
                    // nữa (chủ dự án bỏ, 2026-09-18): nó lặp lại trên MỖI
                    // bảng — hai lần trên một trang biểu mẫu bình thường — và
                    // đứng chen giữa hai khối của chính văn bản. Bảng vẫn chỉ
                    // đọc như trước, không đổi gì ở đó; `aria-describedby`
                    // (Phase 15 R9) đi theo vì nó chỉ tồn tại để trỏ vào ghi
                    // chú đó.
                    return (
                      <table
                        key={i}
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
                            {/* Hàng tiêu đề cũng mang chiều cao khai báo: nó
                                đi vào tệp qua `data-cao`, nên màn hình phải
                                dành đúng chỗ đó — nếu không, hai bên lệch. */}
                            <tr
                              data-cao={caoTrenTrang(k.cao?.[0], k.caoLuat?.[0])?.twip}
                              style={caoTrenTrang(k.cao?.[0], k.caoLuat?.[0])?.style}
                              {...(k.caoLuat?.[0]
                                ? { [THUOC_TINH_BANG.caoLuat]: k.caoLuat[0] }
                                : {})}
                            >
                              {(k.hang[0] ?? []).map((o, oi) => {
                                const cot = spanTieuDe[oi] ?? 1;
                                const vienO = kieuVienO(k.vienO?.[0]?.[oi]);
                                return (
                                  <th
                                    key={oi}
                                    colSpan={cot > 1 ? cot : undefined}
                                    data-can-le={k.canLeO?.[0]?.[oi] ?? "trai"}
                                    {...(vienO?.thuoc ?? {})}
                                    style={vienO?.style}
                                    className={cn(
                                      "bg-[var(--color-paper-100)] px-2 py-1 text-center align-middle font-serif font-semibold",
                                      vienO === null && "border border-[#999]",
                                    )}
                                  >
                                    <OChu noiDung={o} chu={k.chuO?.[0]?.[oi] ?? []} />
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
                            const luat = k.caoLuat?.[hiThat] ?? "";
                            const cao = caoTrenTrang(k.cao?.[hiThat], luat);
                            return (
                              <tr
                                key={hi}
                                data-cao={cao?.twip}
                                style={cao?.style}
                                {...(luat ? { [THUOC_TINH_BANG.caoLuat]: luat } : {})}
                              >
                                {hang.map((o, oi) => {
                                  const cot = span[oi] ?? 1;
                                  const canLe = k.canLeO?.[hiThat]?.[oi] ?? "trai";
                                  // Viền TỪNG CẠNH nguồn thắng lớp viền đều:
                                  // một biểu mẫu chỉ kẻ khung ngoài không được
                                  // ra màn hình thành lưới kẻ đủ mọi ô. Không
                                  // đọc được cạnh nào (bảng mô hình tự gõ, bản
                                  // thảo cũ) thì giữ nguyên lớp cũ.
                                  const vienO = kieuVienO(k.vienO?.[hiThat]?.[oi]);
                                  return (
                                    <td
                                      key={oi}
                                      colSpan={cot > 1 ? cot : undefined}
                                      data-can-le={canLe}
                                      {...(vienO?.thuoc ?? {})}
                                      style={vienO?.style}
                                      className={cn(
                                        "px-2 py-1 align-top font-serif",
                                        CAN_LE_O[canLe],
                                        vienO === null && k.vien && "border border-[#999]",
                                      )}
                                    >
                                      <OChu noiDung={o} chu={k.chuO?.[hiThat]?.[oi] ?? []} />
                                    </td>
                                  );
                                })}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
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
