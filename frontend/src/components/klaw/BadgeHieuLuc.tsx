import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ExternalLink } from "lucide-react";
import type { HieuLuc, HieuLucChiTiet, VanBanDan } from "@/lib/klaw";
import { lienKetChinhThuc, manhMoTa } from "@/lib/trich-dan";
import { cn } from "@/lib/utils";

/**
 * Nhãn hiệu lực của một trích dẫn hoặc một văn bản.
 *
 * Ba luật của thành phần này:
 *
 * 1. **Luôn thấy được.** Không bao giờ nằm trong tooltip, không bao giờ nằm
 *    trong metadata. Người đọc phải thấy nhãn cùng lúc với câu trích.
 * 2. **Không trạng thái nào truyền đạt chỉ bằng màu.** Mỗi nhãn có CHỮ; nhãn
 *    duy nhất được rút xuống một chấm màu (`con_hieu_luc`) vẫn mang
 *    `nhanDayDu` cho trình đọc màn hình. Bốn màu phủ sáu nhãn nên chữ là thứ
 *    phân biệt thật, màu chỉ nhắc lại.
 * 3. **`switch` trên `string`, không `Record<HieuLuc, …>`.** Hợp đồng chỉ bảo
 *    đảm `string | null`. Một nhãn thứ bảy backend thêm sau phải rơi vào
 *    `default` an toàn — hiện chính chuỗi đó, màu trung tính — chứ không ném
 *    lỗi và hạ cả thẻ kết quả. Đây là lý do file này không dùng bảng tra.
 *
 * Đỏ (`--color-status-expired`) dành riêng cho luật KHÔNG còn dùng được: đó là
 * thứ duy nhất khiến người dùng hành động sai. Lỗi mạng, lỗi máy chủ, và
 * `abstain` đều KHÔNG được mượn màu đó.
 */

type KieuNhan = "cham" | "vien";

interface Nhan {
  kieu: KieuNhan;
  /** Biến CSS của màu, không phải giá trị — bảng màu đổi thì nhãn đổi theo. */
  mau: string;
  /** Chữ hiển thị. Rỗng nghĩa là chỉ hiện một chấm màu. */
  chu: string;
  /** Trình đọc màn hình luôn đọc được, kể cả khi `chu` rỗng. */
  nhanDayDu: string;
  /** Câu nói ra giới hạn của chính nhãn. Hiện dưới nhãn, không giấu đi. */
  giaiThich?: string;
  /**
   * Nền chip, khi nền pha từ chính `mau` mất hết sắc.
   *
   * `--color-status-partial` phải xuống `L 0.295` mới đạt 4,5:1 làm chữ, và ở
   * độ sáng đó hue vàng 78° gần như không còn chroma: pha 10% lên nền trắng ra
   * một mảng XÁM ẤM, không phải một chip màu hổ phách. Tín hiệu "coi chừng" mất
   * sạch dù số đo vẫn đẹp. Nên hai nhãn dùng màu đó lấy nền từ
   * `--color-brass-400` — nền KHÔNG cần đạt ngưỡng tương phản, chỉ chữ cần, và
   * chữ trên nền này đo được **12,16:1**.
   */
  nenNhat?: string;
}

const MAU = {
  active: "var(--color-status-active)",
  partial: "var(--color-status-partial)",
  expired: "var(--color-status-expired)",
  neutral: "var(--color-status-neutral)",
} as const;

/** `null` = nhãn không bao giờ được tới người đọc — thành phần không vẽ gì. */
export function docNhanHieuLuc(hieuLuc: string): Nhan | null {
  switch (hieuLuc) {
    case "con_hieu_luc":
      return { kieu: "cham", mau: MAU.active, chu: "Còn hiệu lực", nhanDayDu: "Còn hiệu lực" };

    case "chua_hieu_luc":
      // Nhãn của một câu hỏi đặt ở QUÁ KHỨ: văn bản này có thật, nhưng tại
      // ngày được hỏi nó chưa có hiệu lực. KHÔNG dùng đỏ — đỏ dành riêng cho
      // luật đã bị thay thế hoặc đã hết hiệu lực, và trộn hai thứ vào nhau sẽ
      // dạy người đọc lướt qua cả hai. Cũng KHÔNG dùng xanh: dựa vào một văn
      // bản chưa có hiệu lực tại ngày đang xét là sai luật y như dựa vào một
      // văn bản đã hết.
      return {
        kieu: "vien",
        mau: MAU.partial,
        nenNhat: "color-mix(in oklab, var(--color-brass-400) 40%, var(--card))",
        chu: "Chưa có hiệu lực",
        nhanDayDu: "Chưa có hiệu lực tại ngày được hỏi",
        giaiThich: "Ngày hiệu lực của văn bản này nằm sau ngày bạn đang tra.",
      };

    case "bi_thay_the":
      // Khác `het_hieu_luc` ở chỗ CÓ văn bản kế nhiệm và phải nêu đích danh nó.
      // Câu đó đi qua prop `ghiChu`, lấy từ `warnings[]` của cùng văn bản —
      // không bịa từ phía giao diện.
      return {
        kieu: "vien",
        mau: MAU.expired,
        chu: "Đã bị thay thế",
        nhanDayDu: "Đã bị thay thế bởi văn bản khác",
      };

    case "het_hieu_luc":
      return {
        kieu: "vien",
        mau: MAU.expired,
        chu: "Hết hiệu lực",
        nhanDayDu: "Hết hiệu lực",
      };

    case "bi_sua_doi":
      // `do_tin_cay: cao` — hệ thống BIẾT đích danh điều khoản, văn bản sửa và
      // ngày sửa. Đó là điều phân biệt nó với nhãn ngay dưới đây.
      return {
        kieu: "vien",
        mau: MAU.partial,
        nenNhat: "color-mix(in oklab, var(--color-brass-400) 40%, var(--card))",
        chu: "Đã bị sửa đổi",
        nhanDayDu: "Đã bị sửa đổi, đã xác định được điều khoản sửa",
        giaiThich: "Điều khoản sửa đổi đã xác định được — đọc kèm văn bản sửa.",
      };

    case "mot_phan_khong_xac_dinh":
      // Văn bản HHL1P (còn hiệu lực một phần). Quyết định 2026-09-28, mục 8:
      // nhãn nói điều người đọc cần — văn bản vẫn dùng được, một phần đã đổi —
      // và không bao giờ nói "chưa xác định". Giới hạn vẫn được giữ ở câu đầy
      // đủ: một số điều khoản CÓ THỂ đã đổi, không khẳng định điều này còn
      // nguyên. Câu viết cho cả hai cấp (văn bản, điều khoản): cùng một nhãn
      // hiện ở đầu trang văn bản lẫn trong khung đối chiếu.
      return {
        kieu: "vien",
        mau: MAU.partial,
        nenNhat: "color-mix(in oklab, var(--color-brass-400) 40%, var(--card))",
        chu: "Còn hiệu lực một phần",
        nhanDayDu:
          "Văn bản còn hiệu lực một phần; một số điều khoản có thể đã được sửa đổi hoặc hết hiệu lực",
        giaiThich:
          "Một phần văn bản này đã được sửa đổi hoặc hết hiệu lực. Đối chiếu văn bản sửa đổi trước khi áp dụng điều này.",
      };

    case "can_doi_chieu_tay":
    case "chua_xac_dinh":
      // Quyết định 2026-09-28, mục 8: văn bản chưa rõ tình trạng bị ẩn cho tới
      // khi xác định được, nên hai nhãn này không bao giờ tới người đọc. Lỡ
      // tới thì KHÔNG vẽ nhãn — không bao giờ chữ "Chưa xác định"; chỉ câu
      // `ghiChu` (nếu có) còn hiện, xem `BadgeHieuLuc`.
      return null;

    default:
      // Nhãn backend thêm sau. Hiện nguyên chuỗi, màu trung tính, không đoán
      // nghĩa và không tô màu cảnh báo cho một thứ mình không hiểu.
      return { kieu: "cham", mau: MAU.neutral, chu: hieuLuc, nhanDayDu: hieuLuc };
  }
}

interface BadgeHieuLucProps {
  hieuLuc: HieuLuc | string | null;
  /**
   * Câu nêu ĐÍCH DANH văn bản thay thế / văn bản sửa, lấy từ `warnings[]` của
   * cùng văn bản. Hiện ngay dưới nhãn — không tooltip, không metadata.
   */
  ghiChu?: string;
  /** Ẩn phần giải thích khi nhãn nằm trong danh sách dày (bảng, chip inline). */
  gonGang?: boolean;
  className?: string;
}

export function BadgeHieuLuc({ hieuLuc, ghiChu, gonGang, className }: BadgeHieuLucProps) {
  if (hieuLuc === null || hieuLuc === "") return null;
  const nhan = docNhanHieuLuc(hieuLuc);
  const coGhiChu = !gonGang && ghiChu !== undefined && ghiChu !== "";
  if (nhan === null) {
    // Không nhãn (`can_doi_chieu_tay`), nhưng câu cảnh báo cho người đọc thì
    // vẫn hiện: một điều khoản có văn bản sửa đổi không được mất cảnh báo
    // trong im lặng. Màu "coi chừng" của nhãn sửa đổi, không đỏ.
    return coGhiChu ? (
      <span className={cn("block text-[12px] leading-5", className)} style={{ color: MAU.partial }}>
        {ghiChu}
      </span>
    ) : null;
  }

  return (
    <span className={cn("block", className)}>
      <span
        className={cn(
          "inline-flex min-h-6 items-center gap-1.5 rounded-full px-2 py-0.5 text-[12px] leading-5 font-medium",
          nhan.kieu === "vien" && "border",
        )}
        style={{
          color: nhan.mau,
          ...(nhan.kieu === "vien"
            ? {
                borderColor: `color-mix(in oklab, ${nhan.mau} 45%, transparent)`,
                background: nhan.nenNhat ?? `color-mix(in oklab, ${nhan.mau} 10%, var(--card))`,
              }
            : {}),
        }}
      >
        <span
          aria-hidden="true"
          className="size-1.5 shrink-0 rounded-full"
          style={{ background: nhan.mau }}
        />
        <span>{nhan.chu}</span>
        {nhan.chu !== nhan.nhanDayDu && <span className="sr-only">. {nhan.nhanDayDu}</span>}
      </span>

      {!gonGang && nhan.giaiThich !== undefined && (
        <span className="mt-1 block text-[12px] leading-5 text-muted-foreground">
          {nhan.giaiThich}
        </span>
      )}

      {coGhiChu && (
        // Màu của CHÍNH nhãn, không phải đỏ cố định. Với `bi_thay_the` và
        // `het_hieu_luc` hai màu trùng nhau nên không đổi gì; với
        // `chua_hieu_luc` thì đỏ là sai — đỏ dành riêng cho luật đã chết, còn
        // đây là luật sắp có hiệu lực.
        <span className="mt-1 block text-[12px] leading-5" style={{ color: nhan.mau }}>
          {ghiChu}
        </span>
      )}
    </span>
  );
}

const LOP_LINK =
  "focus-brass rounded font-medium text-[var(--color-brass-600)] underline-offset-2 hover:underline";

/**
 * Tên một văn bản được nêu trong câu cho người đọc. `doc_id` có ⇒ văn bản đó
 * đang được hiện ⇒ link nội bộ; không thì link chính thống (qua đúng cửa kiểm
 * của trích dẫn đầy đủ), mở tab mới; không có cả hai thì chữ trần.
 */
export function LinkVanBanDan({ vanBan, children }: { vanBan: VanBanDan; children: ReactNode }) {
  if (vanBan.doc_id !== null) {
    return (
      <Link to="/tra-cuu/$docId" params={{ docId: vanBan.doc_id }} className={LOP_LINK}>
        {children}
      </Link>
    );
  }
  const lienKet = lienKetChinhThuc(vanBan.lien_ket);
  if (lienKet === null) return <>{children}</>;
  return (
    <a
      href={lienKet.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(LOP_LINK, "inline-flex items-center gap-1")}
    >
      {children}
      <ExternalLink className="size-3.5" aria-hidden />
      <span className="sr-only"> (mở tab mới)</span>
    </a>
  );
}

/**
 * Câu thường dưới nhãn hiệu lực (`HieuLucOut.mo_ta`, quyết định 2026-09-28,
 * mục 10): văn bản sửa đổi, hoặc ngày bắt đầu có hiệu lực — tên văn bản bấm
 * được. Không có câu thì không có gì; không bao giờ `ly_do` hay độ tin cậy.
 */
export function MoTaHieuLuc({
  hieuLuc,
  className,
}: {
  hieuLuc: HieuLucChiTiet;
  className?: string;
}) {
  const manh = manhMoTa(hieuLuc);
  if (manh === null) return null;
  return (
    <p
      data-mo-ta-hieu-luc
      className={cn("mt-1 mb-0 text-[13px] leading-5 text-muted-foreground", className)}
    >
      {manh.map((m, i) =>
        typeof m === "string" ? (
          m
        ) : (
          <LinkVanBanDan key={i} vanBan={m.vanBan}>
            {m.chu}
          </LinkVanBanDan>
        ),
      )}
    </p>
  );
}
