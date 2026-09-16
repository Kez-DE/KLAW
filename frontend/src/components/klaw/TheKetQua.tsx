import { Fragment } from "react";
import { Link } from "@tanstack/react-router";
import { BookOpenText, FileSearch, Info } from "lucide-react";
import type {
  LinkVanBan,
  Nguon,
  SoanThaoGoiY,
  TaiLieuDaDung,
  TraCuuKetQua,
  VanBanTraLoi,
} from "@/lib/klaw";
import { mauTheoId, slugCuaLoai } from "@/lib/mau-van-ban";
import { canCuConHieuLuc, chiSoCuaThe, coTagBamDuoc } from "@/lib/trich-dan";
import { cn } from "@/lib/utils";
import { catDoan, catManh, type Manh } from "@/lib/van-xuoi";
import { BangKetQua } from "./BangKetQua";
import { DuaTren } from "./DuaTren";
import { TheBanThao } from "./TheBanThao";
import { TheSoanThaoHoi } from "./TheSoanThaoHoi";
import { KhoiNeoTaiLieu, TheTaiLieu } from "./TheTaiLieu";

/**
 * Bốn `result_type`, bốn cách hiển thị — không thương lượng.
 *
 * Bản Klaw_FE co bốn nhánh còn hai (`answer` | `nobasis`), làm mất
 * `partial_coverage` — nhánh của tầng metadata, ĐO LẠI hôm nay là 79/126 văn
 * bản trong kho — cùng `nguon[]`,
 * thứ DUY NHẤT mở được văn bản ở nhánh đó; và mất luôn `out_of_scope`.
 *
 * `abstain` là hành vi ĐÚNG và được tính điểm trong đánh giá: một hệ thống thà
 * nói "tôi không đủ căn cứ" còn hơn bịa một điều luật. Nên nó mang màu TRUNG
 * TÍNH, giọng bình thường, KHÔNG icon cảnh báo, KHÔNG đỏ, KHÔNG cam, không
 * rung. Bản Klaw_FE tô nhánh này cam kèm `TriangleAlert` — đó là giao diện
 * tranh luận chống lại chính luận điểm của sản phẩm: nó dạy người dùng rằng sự
 * trung thực là một thất bại.
 *
 * Đỏ chỉ dành cho luật đã bị thay thế hoặc hết hiệu lực.
 */

/** Phạm vi kho, chép từ PRODUCT.md. Không suy đoán thêm lĩnh vực nào. */
const SAU_BO_LUAT = [
  "Dân sự",
  "Tố tụng dân sự",
  "Tố tụng hình sự",
  "Hình sự",
  "Hàng hải",
  "Lao động",
];
const KHONG_PHU = [
  "thuế",
  "đất đai",
  "hôn nhân gia đình",
  "doanh nghiệp",
  "đầu tư",
  "sở hữu trí tuệ",
];

const GOI_Y_DIEN_DAT_LAI = [
  "Nêu rõ vai trò trong quan hệ lao động: người lao động hay người sử dụng lao động.",
  'Dùng từ ngữ của luật thay cho từ thông tục (ví dụ: "đơn phương chấm dứt hợp đồng lao động" thay cho "đuổi việc").',
  "Tách câu hỏi dài thành từng ý riêng, hỏi lần lượt.",
  "Nếu hỏi về một mức tiền cụ thể, nêu rõ năm áp dụng.",
];

/**
 * Khay trung tính dùng cho `abstain` và `out_of_scope`.
 *
 * Cùng một hình dạng với khay `partial_coverage` ngay dưới, khác đúng ở màu
 * viền — để hai nhánh không có câu trả lời đọc như cùng một loại sự việc,
 * không phải như hai mức báo động.
 */
function KhayTrungTinh({ tieuDe, children }: { tieuDe: string; children?: React.ReactNode }) {
  return (
    <div
      className="rounded-xl border-l-2 bg-[var(--color-paper-50)] py-3 pr-4 pl-4"
      style={{ borderLeftColor: "var(--color-status-neutral)" }}
    >
      <p className="doc-prose m-0 text-foreground">{tieuDe}</p>
      {children}
    </div>
  );
}

/**
 * `nguon[]` — văn bản chi phối câu hỏi. CHỈ `partial_coverage` điền.
 *
 * Nhánh đó luôn có `citations: []` theo thiết kế, nên đây là thứ DUY NHẤT mở
 * được văn bản đang nói tới. `coverage_note` có nêu tên văn bản trong văn xuôi,
 * nhưng cạo chuỗi đó ra để dựng liên kết là bịa một địa chỉ: mỗi liên kết dưới
 * đây đến từ `doc_id` máy chủ trả về.
 *
 * Đây KHÔNG phải trích dẫn đã kiểm chứng — không `quote`, không nhãn hiệu lực.
 * Câu dẫn phải nói đúng như vậy.
 */
function KhoiNguon({
  nguon,
  onMoVanBan,
}: {
  nguon: Nguon[];
  onMoVanBan?: (docId: string) => void;
}) {
  if (nguon.length === 0) return null;
  return (
    <section aria-label="Văn bản chi phối câu hỏi" className="mt-4">
      <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
        Văn bản chi phối câu hỏi này — mở để tự đối chiếu
      </h3>
      <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">
        {nguon.map((vanBan) => {
          const noiDung = (
            <>
              <BookOpenText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              <span className="font-jetbrains text-[13px] text-foreground">
                {vanBan.so_ky_hieu}
              </span>
              <span className="text-[13px] text-muted-foreground">{vanBan.bo_luat}</span>
            </>
          );
          // Điều hướng đi qua CALLBACK, không phải một <Link> viết cứng.
          // Tuyến duy nhất mở văn bản trong bản dựng này là `/tra-cuu/$soHieu`,
          // tức định danh bằng SỐ HIỆU — mà `65/2006/QH11` thuộc HAI văn bản
          // khác nhau, nên một liên kết dựng từ số hiệu có thể mở nhầm văn bản.
          // Khoá duy nhất tuyệt đối là `doc_id`. Thành phần này giao `doc_id`
          // cho nơi gọi và không tự chọn tuyến; nợ tuyến đó thuộc pha nối FE.
          return (
            <li key={vanBan.doc_id}>
              {onMoVanBan === undefined ? (
                <div className="flex min-h-11 items-center gap-2 rounded-lg border border-border bg-card p-3">
                  {noiDung}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => onMoVanBan(vanBan.doc_id)}
                  className="focus-brass flex min-h-11 w-full cursor-pointer items-center gap-2 rounded-lg border border-border bg-card p-3 text-left transition-colors hover:bg-[var(--color-paper-100)]"
                >
                  {noiDung}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Thứ tự và nhãn cổng — vbpl → chinhphu → tvpl (spec §4.3). Biểu tượng là của
 *  giao diện; `assemble.v2` quy tắc 17 cấm mô hình dùng chúng. */
const NHAN_CONG: ReadonlyArray<[keyof LinkVanBan, string]> = [
  ["vbpl", "Cơ sở dữ liệu quốc gia về văn bản pháp luật (Bộ Tư pháp)"],
  ["chinhphu", "Cổng Thông tin điện tử Chính phủ"],
  ["tvpl", "Thư Viện Pháp Luật"],
];

/**
 * Liên kết toàn văn tới cổng luật, dựng từ `documents[].links` — DB điền, mô
 * hình không bao giờ viết URL (phép kiểm thứ chín). Dòng nào `null` thì không
 * render; không văn bản nào có link thì cả khối ẩn.
 */
function KhoiLienKet({ documents }: { documents: VanBanTraLoi[] }) {
  const dong = documents.flatMap((d) =>
    NHAN_CONG.flatMap(([khoa, nhan]) => {
      const url = d.links[khoa];
      // Phòng thủ chiều sâu cho một <a target="_blank">: chỉ render nếu url
      // đúng là chuỗi https, dù DB/loader đã đảm bảo điều đó ở tầng trước.
      return typeof url === "string" && url.startsWith("https://")
        ? [{ key: `${d.doc_id}-${khoa}`, url, ten: d.ten, nhan }]
        : [];
    }),
  );
  if (dong.length === 0) return null;
  return (
    <section aria-label="Liên kết tra cứu toàn văn" className="mt-4">
      <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
        <span aria-hidden="true">📖</span> Liên kết tra cứu toàn văn
      </h3>
      <ol className="mt-1 mb-0 list-decimal pl-5 text-[13px] leading-6">
        {dong.map((d) => (
          <li key={d.key}>
            <span aria-hidden="true">🔗</span>{" "}
            <a
              href={d.url}
              target="_blank"
              rel="noopener noreferrer"
              className="focus-brass rounded underline underline-offset-2"
            >
              Toàn văn {d.ten} — {d.nhan}
              <span className="sr-only"> (mở tab mới)</span>
            </a>
          </li>
        ))}
      </ol>
    </section>
  );
}

/**
 * Chốt an toàn cho căn cứ (spec 2026-09-06 §7.1): chỉ hiện khi văn xuôi KHÔNG
 * có thẻ nào bấm được — mô hình quên gắn thẻ thì bằng chứng vẫn còn đường mở.
 * Chỉ căn cứ còn hiệu lực; nhóm đã hết hiệu lực/bị thay thế không hiện ở đâu
 * trong card. Không nhãn hiệu lực ở đây: nhãn nằm trong khung khi mở.
 */
function KhoiCanCu({
  ketQua,
  chiSoDangMo,
  onChon,
}: {
  ketQua: TraCuuKetQua;
  chiSoDangMo: number | null;
  onChon: (chiSo: number) => void;
}) {
  if (coTagBamDuoc(ketQua.answer, ketQua.citations)) return null;
  const canCu = canCuConHieuLuc(ketQua.citations);
  if (canCu.length === 0) return null;
  return (
    <section aria-label="Căn cứ" className="mt-4">
      <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">Căn cứ</h3>
      <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">
        {canCu.map(({ trichDan, chiSoGoc }) => (
          <li key={`${trichDan.doc_id}-${trichDan.khop_tai_id}-${chiSoGoc}`}>
            <button
              type="button"
              onClick={() => onChon(chiSoGoc)}
              aria-expanded={chiSoDangMo === chiSoGoc}
              className={cn(
                "focus-brass block w-full cursor-pointer rounded-lg border p-3 text-left transition-colors",
                chiSoDangMo === chiSoGoc
                  ? "border-[var(--ring)] bg-[var(--color-paper-100)]"
                  : "border-border bg-card hover:bg-[var(--color-paper-50)]",
              )}
            >
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="font-jetbrains text-[13px] text-foreground">
                  {trichDan.so_ky_hieu}
                </span>
                <span className="text-[13px] text-muted-foreground">{trichDan.duong_dan}</span>
              </span>
              <span className="serif-body mt-1.5 block text-[14px] leading-6 text-foreground">
                “{trichDan.quote}”
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Nhắc miễn trừ — ở nhánh `answer` VÀ `partial_coverage`.
 *
 * Đây là hai nhánh DUY NHẤT nêu tên một văn bản pháp luật cụ thể mà người dùng
 * có thể hành động theo (answer bằng khẳng định pháp lý, partial_coverage
 * bằng `nguon[]`) mà không nhận ra kho là văn bản GỐC chứ không phải bản hợp
 * nhất. `abstain`/`out_of_scope`/`gioi_thieu` không nêu tên văn bản nào nên
 * không cần nhắc này. Nhắc ở chân trang là không đủ: người ta đọc rồi đóng
 * tab, nên nó lặp lại ở mỗi nhánh có nêu văn bản, không dồn về một chỗ chung.
 * Dòng ⚖️ là hằng số giao diện, không bao giờ là lời mô hình sinh ra (spec
 * 2026-09-06 §7.3).
 */
function NhacMienTru() {
  return (
    <p className="mt-6 mb-0 text-[13px] leading-5 text-muted-foreground">
      Câu trả lời dựa trên văn bản gốc, không phải bản hợp nhất — KLAW bảo đảm nguồn gốc và đúng
      nguyên văn, không bảo đảm đây là bản hiện hành.{" "}
      <Link to="/mien-tru" className="focus-brass rounded underline underline-offset-2">
        Giới hạn của KLAW
      </Link>
      .
      <br />
      ⚖️ Thông tin chỉ mang tính tham khảo, không thay thế tư vấn của luật sư.
    </p>
  );
}

/**
 * Văn xuôi máy chủ gửi về, cắt thành đoạn và danh sách.
 *
 * Dùng ở BỐN nhánh (`answer`, `gioi_thieu`, và `coverage_note` của `abstain` +
 * `partial_coverage`). Nằm ở cấp module chứ không trong thân component: từ
 * 2026-09-02 `coverage_note` có HAI NỬA ngăn bằng dòng trắng cộng một danh sách
 * gạch đầu dòng, mà hai nhánh cần nó lại `return` TRƯỚC chỗ khai báo cũ.
 *
 * `catDoan` chỉ CẮT, không sửa chữ: câu trả lời mang số Điều ngay trong lời văn
 * (`… (Điều 25, Khoản 1)`) và đó là căn cứ, không phải trang trí.
 */

/**
 * Một thẻ trong văn xuôi. `cite:K` → trích dẫn có `k === K`; `doc:ID` → trích dẫn
 * đầu của văn bản đó (Q5). Cả hai đi qua ĐÚNG `onChon(chiSo)` mà dải trích dẫn
 * đang dùng, nên `dangMo`/`aria-expanded` trong `dung-thu.tsx` dùng lại nguyên.
 * Thẻ không khớp gì (backend đã chặn; đây là lưới phụ) rơi về chữ thường.
 */
function TheTrichDan({
  manh,
  ketQua,
  onChon,
}: {
  manh: Extract<Manh, { kieu: "the" }>;
  ketQua?: TraCuuKetQua | undefined;
  onChon?: ((chiSo: number) => void) | undefined;
}) {
  if (ketQua === undefined || onChon === undefined) return <>{manh.chu}</>;
  const chiSo = chiSoCuaThe(manh, ketQua.citations);
  if (chiSo < 0) return <>{manh.chu}</>;
  return (
    <button type="button" className="the-luat" onClick={() => onChon(chiSo)}>
      {manh.chu}
    </button>
  );
}

function ManhVanXuoi({
  chu,
  ketQua,
  onChon,
}: {
  chu: string;
  ketQua?: TraCuuKetQua | undefined;
  onChon?: ((chiSo: number) => void) | undefined;
}) {
  return (
    <>
      {catManh(chu).map((m, i) =>
        m.kieu === "chu" ? (
          <Fragment key={i}>{m.chu}</Fragment>
        ) : (
          <TheTrichDan key={i} manh={m} ketQua={ketQua} onChon={onChon} />
        ),
      )}
    </>
  );
}

/**
 * Xuất khẩu (Task 15): `BangKetQua` render ô bảng so sánh qua ĐÚNG bộ cắt/thẻ
 * này, để thẻ `cite:K` trong ô bảng bấm được y hệt thẻ trong văn xuôi — không
 * dựng một cách hiển thị thẻ thứ hai riêng cho bảng.
 */
export function KhoiVanXuoi({
  chu,
  ketQua,
  onChon,
}: {
  chu: string;
  ketQua?: TraCuuKetQua | undefined;
  onChon?: ((chiSo: number) => void) | undefined;
}) {
  return (
    <>
      {catDoan(chu).map((doan, i) =>
        doan.kieu === "danh_sach" ? (
          <ul key={`ds-${i}`} className={cn("list-disc pl-5", i === 0 ? "m-0" : "mt-3 mb-0")}>
            {doan.muc.map((muc, j) => (
              <li key={`${j}-${muc.slice(0, 24)}`} className={j === 0 ? "" : "mt-1"}>
                <ManhVanXuoi chu={muc} ketQua={ketQua} onChon={onChon} />
              </li>
            ))}
          </ul>
        ) : (
          <p key={`d-${i}`} className={i === 0 ? "m-0" : "mt-3 mb-0"}>
            <ManhVanXuoi chu={doan.chu} ketQua={ketQua} onChon={onChon} />
          </p>
        ),
      )}
    </>
  );
}

/**
 * Card gợi ý soạn thảo (spec soạn-thảo-trong-chat §5.2). Văn xuôi của máy chủ
 * nói loại và lý do; nút chính mở khung bên cạnh với slug của loại đó, chip mở
 * loại thay thế, nút cuối mở lưới chọn tay. `hdld` có hai thẻ → hai nút.
 */
function TheGoiYSoanThao({
  ketQua,
  onSoanThao,
}: {
  ketQua: TraCuuKetQua;
  onSoanThao?: ((slug: string | null) => void) | undefined;
}) {
  const gy = ketQua.soan_thao ?? null;
  const chinh = gy?.ho_tro && gy.loai ? slugCuaLoai(gy.loai) : [];
  const nutPhu =
    "focus-brass cursor-pointer rounded-full border border-border bg-card px-3 py-1.5 text-[13px] text-foreground hover:bg-[var(--color-paper-100)]";
  return (
    <section aria-label="Gợi ý soạn thảo">
      <div className="doc-prose text-foreground">
        <KhoiVanXuoi chu={ketQua.answer ?? ""} />
      </div>
      {onSoanThao && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {chinh.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onSoanThao(s)}
              className="focus-brass bg-gradient-ink cursor-pointer rounded-lg px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              {chinh.length > 1 ? `Soạn ${mauTheoId(s)?.ten ?? s}` : "Soạn ngay tại đây"}
            </button>
          ))}
          {(gy?.thay_the ?? []).flatMap((t) =>
            slugCuaLoai(t.loai)
              .filter((s) => !chinh.includes(s))
              .map((s) => (
                <button key={s} type="button" onClick={() => onSoanThao(s)} className={nutPhu}>
                  {mauTheoId(s)?.ten ?? t.ten}
                </button>
              )),
          )}
          <button
            type="button"
            onClick={() => onSoanThao(null)}
            className={cn(nutPhu, "text-muted-foreground")}
          >
            Chọn loại văn bản
          </button>
        </div>
      )}
    </section>
  );
}

/**
 * Nút gợi ý soạn thảo trong nhánh `answer` (Task 13 — ý định phụ `soan_thao`).
 * Câu hỏi vừa hỏi luật vừa nhờ soạn: `answer` vẫn là câu trả lời tra cứu,
 * KHÔNG bị thay bởi văn xuôi gợi ý — chỉ thêm một nút mở khung soạn thảo,
 * tái dùng đúng `slugCuaLoai`/`mauTheoId` của `TheGoiYSoanThao` ở trên.
 */
function NutSoanTiep({
  goiY,
  onSoanThao,
}: {
  goiY: SoanThaoGoiY;
  onSoanThao: (slug: string | null) => void;
}) {
  if (!goiY.ho_tro || !goiY.loai) return null;
  const slug = slugCuaLoai(goiY.loai)[0] ?? null;
  return (
    <button
      type="button"
      onClick={() => onSoanThao(slug)}
      className="focus-brass bg-gradient-ink mt-4 cursor-pointer rounded-lg px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
    >
      Soạn {(slug && mauTheoId(slug)?.ten) ?? goiY.ten}
    </button>
  );
}

interface TheKetQuaProps {
  ketQua: TraCuuKetQua;
  /** Chỉ số trích dẫn đang mở trong panel đối chiếu, hoặc null. */
  chiSoDangMo?: number | null;
  onChonTrichDan?: (chiSo: number) => void;
  /** Nhận `doc_id` — khoá duy nhất tuyệt đối. Xem ghi chú ở `KhoiNguon`. */
  onMoVanBan?: (docId: string) => void;
  /** Câu người dùng GÕ. Cần để so với `cau_hoi_day_du` — xem `CauHoiDaHieu`. */
  cauHoiGoc?: string;
  /** Mở khung soạn thảo bên cạnh với slug thẻ, hoặc `null` để chọn loại tại chỗ. */
  onSoanThao?: ((slug: string | null) => void) | undefined;
  /** Sửa (hoặc xoá, với `giaTri: null`) một dữ kiện trong dòng "Dựa trên". */
  onSuaHoSo?: (khoa: string, giaTri: string | null) => void;
  /** Điền chip "Nhãn: giá trị" vào ô hỏi (nhánh `soan_thao_hoi`, Task 21). */
  onChip?: (chu: string) => void;
  /** Mở trang đăng nhập khi `soan_thao_hoi.can_dang_nhap` (nhánh `soan_thao_hoi`). */
  onDangNhap?: () => void;
  /** Mở khung soạn thảo với bản thảo vừa dựng (nhánh `ban_thao`). */
  onMoBanThao?: (id: string) => void;
  /** Mở khung tài liệu đúng tại đơn vị văn bản một neo chỉ tới. Không có nó thì
   *  neo hiện thành nhãn chết — xem `ChipNeo`. */
  onMoNeoTaiLieu?: (taiLieuId: string, chiSo: number) => void;
  /** Điền câu hỏi VÀ đính kèm lại tài liệu cho lượt kế (nhánh `tai_lieu`). */
  onHanhDongTaiLieu?: (cauHoi: string, taiLieu: TaiLieuDaDung[]) => void;
}

/**
 * "Mình hiểu câu hỏi của bạn là…" — chỉ hiện khi máy chủ ĐÃ giải nghĩa lại câu
 * hỏi, và câu đó KHÁC câu người dùng gõ.
 *
 * Vì sao bắt buộc có: một lượt hỏi nối tiếp ("liệt kê bảng cho tôi") được máy
 * chủ viết lại thành một câu tự đứng được trước khi đi tra. Giải nghĩa sai là
 * chuyện chắc chắn xảy ra, và không có dòng này thì người hỏi nhận câu trả lời
 * cho một câu HỌ KHÔNG HỎI mà không có cách nào biết — cũng không có cách nào
 * sửa. Hiện nó ra là biến một lỗi im lặng thành một lỗi họ đọc được và gõ lại.
 *
 * So sau khi chuẩn hoá khoảng trắng: máy chủ trả về câu đã qua LLM nên khác biệt
 * duy nhất là một dấu cách cuối câu vẫn sẽ hiện một dòng nói "mình hiểu là" kèm
 * đúng câu người ta vừa gõ — nhiễu, không phải thông tin.
 */
function CauHoiDaHieu({ goc, dayDu }: { goc: string | undefined; dayDu: string | null }) {
  if (dayDu === null || dayDu.trim() === "") return null;
  const gon = (x: string) => x.trim().replace(/\s+/g, " ");
  if (goc !== undefined && gon(goc) === gon(dayDu)) return null;
  return (
    <p className="mb-3 text-[13px] leading-6 text-muted-foreground">
      Tôi hiểu câu hỏi của bạn là: <span className="text-foreground italic">{dayDu}</span>
    </p>
  );
}

export function TheKetQua(props: TheKetQuaProps) {
  return (
    <>
      <CauHoiDaHieu goc={props.cauHoiGoc} dayDu={props.ketQua.cau_hoi_day_du} />
      <DuaTren
        muc={props.ketQua.ho_so_da_dung ?? []}
        {...(props.onSuaHoSo ? { onSua: props.onSuaHoSo } : {})}
      />
      <NoiDungKetQua {...props} />
    </>
  );
}

function NoiDungKetQua({
  ketQua,
  chiSoDangMo = null,
  onChonTrichDan,
  onMoVanBan,
  onSoanThao,
  onChip,
  onDangNhap,
  onMoBanThao,
  onMoNeoTaiLieu,
  onHanhDongTaiLieu,
}: TheKetQuaProps) {
  const { result_type: loai, answer, citations, nguon, coverage_note: ghiChuPhamVi, bang } = ketQua;
  const chon = onChonTrichDan ?? (() => undefined);
  // Nhánh đối chiếu luật giữ nguyên `answer`/`partial_coverage`/`abstain` và chỉ
  // thêm dải neo này, nên nó dựng một lần ở đây cho cả ba nhánh dùng lại.
  const daiNeo = <KhoiNeoTaiLieu neo={ketQua.tai_lieu_neo ?? []} onMoNeoTaiLieu={onMoNeoTaiLieu} />;

  if (loai === "abstain") {
    return (
      <section aria-label="Kết quả tra cứu">
        {/* Câu "Hệ thống dừng ở đây thay vì suy đoán. Đây là hành vi được thiết
            kế, không phải lỗi." đã gỡ: từ 2026-09-02 `coverage_note` tự nói
            việc đó bằng giọng người trả lời ("nên mình dừng ở đây thay vì
            đoán"), và một hệ thống tự thuật về thiết kế của chính nó là đúng
            giọng mà pha này bỏ. Khay vẫn TRUNG TÍNH — abstain là hành vi đúng,
            không phải một mức báo động. */}
        <KhayTrungTinh tieuDe="Tôi chưa trả lời chắc được câu hỏi này.">
          {ghiChuPhamVi !== null && ghiChuPhamVi !== "" && (
            <div className="mt-2 text-[14px] leading-6 text-muted-foreground">
              <KhoiVanXuoi chu={ghiChuPhamVi} />
            </div>
          )}
        </KhayTrungTinh>
        {/* Đứng SAU câu hỏi lại, và mang chữ "Hoặc": `coverage_note` nay đã hỏi
            đúng dữ kiện còn thiếu của chính câu hỏi này, nên bốn gợi ý chung
            dưới đây là một lối KHÁC chứ không phải một chỉ dẫn thứ hai tranh
            chỗ với nó. Vẫn giữ vì chúng nói được thứ câu hỏi lại không nói:
            cách viết lại câu hỏi. */}
        <div className="mt-4">
          <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
            Hoặc thử diễn đạt lại câu hỏi
          </h3>
          <ul className="doc-prose mt-1 mb-0 list-disc pl-5 text-foreground">
            {GOI_Y_DIEN_DAT_LAI.map((goiY) => (
              <li key={goiY}>{goiY}</li>
            ))}
          </ul>
        </div>
        {daiNeo}
      </section>
    );
  }

  // `gioi_thieu` KHÔNG mượn `KhayTrungTinh`. Khay đó nói "chưa trả lời được" —
  // dùng nó ở đây là vẫn đóng khung một câu trả lời hợp lệ như một lời từ chối,
  // tức vẫn phạm đúng lỗi vừa sửa ở backend, chỉ dịch xuống một tầng. Đây là
  // câu trả lời, nên nó trông như câu trả lời.
  if (loai === "gioi_thieu") {
    return (
      <section aria-label="Giới thiệu trợ lý">
        <div className="doc-prose text-foreground">
          <KhoiVanXuoi chu={ketQua.answer ?? ""} />
        </div>
      </section>
    );
  }

  if (loai === "out_of_scope") {
    return (
      <section aria-label="Kết quả tra cứu">
        <KhayTrungTinh tieuDe="Câu hỏi này nằm ngoài phạm vi tôi phủ.">
          {ghiChuPhamVi !== null && ghiChuPhamVi !== "" && (
            <p className="mt-2 mb-0 text-[14px] leading-6 text-muted-foreground">{ghiChuPhamVi}</p>
          )}
        </KhayTrungTinh>
        <div className="mt-4 text-[14px] leading-6 text-foreground">
          <p className="m-0">
            Tôi tra được <strong className="font-semibold">6 Bộ luật</strong>:{" "}
            {SAU_BO_LUAT.join(", ")} — cùng cụm văn bản dưới luật về Lao động.
          </p>
          <p className="mt-2 mb-0 text-muted-foreground">
            Tôi chưa phủ: {KHONG_PHU.join(", ")}. Chiều sâu cũng không đều giữa các lĩnh vực: chỉ
            riêng Lao động có đủ luật, nghị định, thông tư và chế tài.
          </p>
        </div>
      </section>
    );
  }

  if (loai === "huong_dan_soan_thao") {
    return <TheGoiYSoanThao ketQua={ketQua} onSoanThao={onSoanThao} />;
  }

  if (loai === "soan_thao_hoi") {
    return (
      <TheSoanThaoHoi
        ketQua={ketQua}
        onChip={onChip ?? (() => undefined)}
        {...(onDangNhap ? { onDangNhap } : {})}
      />
    );
  }

  if (loai === "ban_thao") {
    return <TheBanThao ketQua={ketQua} onMo={onMoBanThao ?? (() => undefined)} />;
  }

  if (loai === "tai_lieu") {
    return (
      <TheTaiLieu
        ketQua={ketQua}
        onChip={onChip}
        onMoNeoTaiLieu={onMoNeoTaiLieu}
        onHanhDongTaiLieu={onHanhDongTaiLieu}
      />
    );
  }

  if (loai === "partial_coverage") {
    return (
      <section aria-label="Kết quả tra cứu">
        <div
          className="rounded-xl border-l-2 bg-[var(--color-paper-50)] py-3 pr-4 pl-4"
          style={{ borderLeftColor: "var(--color-status-partial)" }}
        >
          <p className="m-0 flex items-start gap-2 text-[14px] leading-6 text-muted-foreground">
            <Info
              className="mt-0.5 size-4 shrink-0"
              style={{ color: "var(--color-status-partial)" }}
              aria-hidden
            />
            <span>
              Tôi tìm được văn bản chi phối câu hỏi của bạn, nhưng chưa đọc được nội dung của nó nên
              chưa giải thích được cho bạn.
            </span>
          </p>
          {ghiChuPhamVi !== null && ghiChuPhamVi !== "" && (
            <div className="doc-prose mt-2 text-foreground">
              <KhoiVanXuoi chu={ghiChuPhamVi} />
            </div>
          )}
        </div>
        <KhoiNguon nguon={nguon} {...(onMoVanBan ? { onMoVanBan } : {})} />
        {/* Backend hiện luôn trả citations rỗng ở nhánh này, nên KhoiCanCu (danh
            sách căn cứ dự phòng, chỉ còn hiệu lực) tự ẩn. Giữ lời gọi để ngày
            endpoint kèm trích dẫn thì màn hình có sẵn chỗ — KHÔNG dựng liên kết
            giả từ chuỗi coverage_note. */}
        <KhoiCanCu ketQua={ketQua} chiSoDangMo={chiSoDangMo} onChon={chon} />
        {daiNeo}
        <NhacMienTru />
      </section>
    );
  }

  return (
    <section aria-label="Kết quả tra cứu">
      <div className="doc-prose text-foreground">
        {answer === null || answer.trim() === "" ? (
          <p className="m-0 flex items-start gap-2 text-muted-foreground">
            <FileSearch className="mt-1 size-4 shrink-0" aria-hidden />
            <span>
              {canCuConHieuLuc(citations).length > 0
                ? "Lượt này tôi đối chiếu được trích dẫn nhưng chưa viết ra được lời giải thích. Bạn đọc nguyên văn các điều khoản ngay dưới đây."
                : "Lượt này tôi chưa có nội dung nào để hiển thị. Bạn thử hỏi lại bằng cách khác, hoặc mô tả cụ thể hơn tình huống của bạn."}
            </span>
          </p>
        ) : (
          <KhoiVanXuoi chu={answer} ketQua={ketQua} onChon={chon} />
        )}
      </div>
      {/* Task 14: một câu trả lời ĐÃ CÓ luận điểm được phép mang thêm đúng MỘT
          đuôi hỏi thêm ngắn ở cuối, đi qua `coverage_note` (backend
          `duoi_hoi_them`) — không spliced vào `answer`. */}
      {ghiChuPhamVi && (
        <div className="mt-3 text-[13px] leading-6 text-muted-foreground">
          <KhoiVanXuoi chu={ghiChuPhamVi} />
        </div>
      )}
      <KhoiLienKet documents={ketQua.documents} />
      <KhoiCanCu ketQua={ketQua} chiSoDangMo={chiSoDangMo} onChon={chon} />
      {daiNeo}
      {ketQua.soan_thao?.ho_tro && ketQua.soan_thao.loai && onSoanThao && (
        <NutSoanTiep goiY={ketQua.soan_thao} onSoanThao={onSoanThao} />
      )}
      {bang.length > 0 && (
        <div className="mt-4 space-y-3">
          {bang.map((mot) => (
            <BangKetQua key={mot.tieu_de} bang={mot} ketQua={ketQua} onChonTrichDan={chon} />
          ))}
        </div>
      )}
      <NhacMienTru />
    </section>
  );
}
