import type { HieuLuc } from "@/lib/klaw";
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

export function docNhanHieuLuc(hieuLuc: string): Nhan {
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
      // KHÔNG phải "Hết hiệu lực một phần". Câu đó nói hệ thống BIẾT phần nào
      // đã hết hiệu lực. Sự thật ngược lại: CSDL quốc gia không công bố dữ
      // liệu cấp điều khoản cho văn bản này, nên hệ thống KHÔNG biết — và
      // nhãn phải nói ra đúng điều đó. Rút gọn cho vừa chip là bỏ mất chính
      // lời thú nhận giới hạn, tức bỏ mất thứ khiến nhãn này trung thực.
      return {
        kieu: "vien",
        mau: MAU.partial,
        nenNhat: "color-mix(in oklab, var(--color-brass-400) 40%, var(--card))",
        chu: "Một phần không xác định",
        nhanDayDu: "Bị sửa một phần, chưa xác định được điều này còn hiệu lực hay không",
        giaiThich:
          "Văn bản đã bị sửa một phần. CSDL quốc gia không công bố dữ liệu cấp điều khoản, nên chưa xác định được điều này còn hiệu lực hay không.",
      };

    case "can_doi_chieu_tay":
      // Trung tính: đây là lời nhờ, không phải lời cảnh báo.
      return {
        kieu: "cham",
        mau: MAU.neutral,
        chu: "Cần đối chiếu tay",
        nhanDayDu: "Cần đối chiếu tay với văn bản gốc",
      };

    case "chua_xac_dinh":
      // CSDL quốc gia không có mã tình trạng cho văn bản này (thường là văn bản
      // mới ban hành). Trung tính: "chưa biết", không phải "đã chết" — nên không
      // đỏ, không xanh.
      return {
        kieu: "cham",
        mau: MAU.neutral,
        chu: "Chưa xác định",
        nhanDayDu: "Chưa xác định được hiệu lực",
      };

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

      {!gonGang && ghiChu !== undefined && ghiChu !== "" && (
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
