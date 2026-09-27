import { Send } from "lucide-react";
import { ChipTaiLieu, type HanhDongTep, type TepDinhKem } from "@/components/klaw/ChipTaiLieu";
import { MenuDinhKem } from "@/components/klaw/MenuDinhKem";
import { cauChip, mucMau, phanTram } from "@/lib/han-muc";
import type { MucHanMuc } from "@/lib/klaw";
import { cn } from "@/lib/utils";

/**
 * Ba mức của chip hạn mức: còn thoải mái, sắp cạn (≥80%), đã cạn.
 *
 * Cả ba lấy token đã ĐO tương phản làm chữ (`styles.css`) — `brass-600` 4,43:1
 * trên chính nó pha 10%, `status-partial` 13,97:1, `status-expired` 10,32:1.
 * Chip là chữ 11px nên đây là chỗ dễ trượt ngưỡng nhất màn hình.
 */
const MAU_CHIP: Record<"brass" | "amber" | "do", string> = {
  brass: "bg-brass-500/20 text-brass-600",
  amber: "bg-status-partial/10 text-status-partial",
  do: "bg-status-expired/10 text-status-expired",
};

/** Câu "đang tải tệp" — nút gửi trỏ `aria-describedby` vào đây. */
const ID_DANG_TAI = "o-soan-dang-tai-tep";

/**
 * Ô soạn câu hỏi của màn hỏi, kèm chip hạn mức và câu miễn trừ.
 *
 * Ở riêng một tệp vì nó là khối giao diện DUY NHẤT của màn hỏi không dính gì
 * tới dòng hội thoại: nó chỉ cần biết đang gõ gì, có bị khoá không, và còn bao
 * nhiêu lượt. Tách ra giữ `dung-thu.tsx` nói về hội thoại.
 *
 * `oHoi` đi từ ngoài vào vì trang giữ hai việc trên chính DOM node này: tự giãn
 * chiều cao theo nội dung, và đặt tiêu điểm khi người dùng bấm một gợi ý.
 */
export function OSoanCauHoi({
  oHoi,
  nhap,
  datNhap,
  khoa,
  onGui,
  mucChip,
  dangCho,
  onChonTep,
  dangDocTep,
  loiTaiLen = null,
  tepDaDinhKem,
  hanhDongTep,
  onBoDinhKem,
}: {
  oHoi: React.RefObject<HTMLTextAreaElement | null>;
  nhap: string;
  datNhap: (gia: string) => void;
  /** Câu tiếp theo chắc chắn bị từ chối (đang chạy, phiên đầy, hết hạn mức). */
  khoa: boolean;
  onGui: () => void;
  mucChip: MucHanMuc | null;
  /** Đang kiểm phiên: giữ chỗ đúng chiều cao thay vì để ô hỏi nhảy vào. */
  dangCho: boolean;
  /** Người dùng vừa chọn một tệp từ máy. */
  onChonTep: (tep: File) => void;
  /** Đang đọc một tệp — khoá nút đính kèm VÀ lối gửi (chữ đã gõ vẫn giữ) cho
   *  tới khi xong, dù được hay bị từ chối. */
  dangDocTep?: boolean | undefined;
  /** Câu từ chối của lần tải tệp gần nhất (máy chủ nói tên tệp, số trang thật)
   *  — nơi gọi giữ tới lần tải kế tiếp. */
  loiTaiLen?: string | null;
  /**
   * Tài liệu sẽ đi kèm câu hỏi sắp gửi — tối đa hai (nhánh so sánh).
   *
   * Một MẢNG chứ không phải một tệp: mỗi tệp có con chip và nút bỏ RIÊNG, vì
   * một nút "bỏ đính kèm" chung không nói được người dùng sắp bỏ tờ nào. Rỗng
   * hoặc vắng ⇒ lượt sau là một câu hỏi thường.
   */
  tepDaDinhKem?: TepDinhKem[] | null;
  /** Việc làm được với tệp — menu của con chip. Đính kèm KHÔNG tự mở khung
   *  nào — con chip là đường duy nhất vào đó, nên nó phải bấm được. */
  hanhDongTep: HanhDongTep;
  /** Bỏ ĐÚNG một tệp khỏi lượt sắp gửi. */
  onBoDinhKem?: ((id: string) => void) | undefined;
}) {
  const daDinhKem = tepDaDinhKem ?? [];
  return (
    <div className="sticky bottom-0 border-t border-border bg-background/95 backdrop-blur">
      <div className="mx-auto w-full max-w-[860px] px-4 py-3">
        {dangCho ? (
          <div aria-hidden className="min-h-[56px] rounded-xl border border-border bg-card" />
        ) : (
          <div className="rounded-xl border border-border bg-card p-2 shadow-soft">
            {/* Con chip đứng NGAY TRÊN ô gõ, không nằm trong khung tài liệu:
                nó trả lời câu hỏi "câu tôi sắp gửi có kèm tệp này không" đúng
                lúc người dùng đang gõ câu đó. Khung tài liệu có thể đã đóng. */}
            {daDinhKem.length > 0 && (
              // `relative`: menu của mỗi chip neo vào mép trái danh sách này,
              // không tràn khỏi màn hẹp (xem `ChipTaiLieu`).
              <ul className="relative mb-2 flex list-none flex-wrap gap-2 p-0">
                {daDinhKem.map((tep) => (
                  <li key={tep.id} className="max-w-full">
                    <ChipTaiLieu tep={tep} hanhDong={hanhDongTep} onBo={onBoDinhKem} />
                  </li>
                ))}
              </ul>
            )}
            {/* Ngay trên nút đính kèm: toast từ chối tự tắt sau 8 giây, câu này
                ở lại để người dùng còn đọc được vì sao tệp không vào. Không
                `role="alert"`: toast đã đọc nó lên một lần. */}
            {loiTaiLen !== null && (
              <p className="m-0 mb-2 px-1 text-[12.5px] leading-5 text-destructive">{loiTaiLen}</p>
            )}
            {dangDocTep === true && (
              <p
                id={ID_DANG_TAI}
                className="m-0 mb-2 px-1 text-[12.5px] leading-5 text-muted-foreground"
              >
                Đang tải tệp lên…
              </p>
            )}
            <div className="flex items-end gap-2">
              <MenuDinhKem onChonTep={onChonTep} khoa={dangDocTep} />
              <textarea
                ref={oHoi}
                rows={1}
                value={nhap}
                disabled={khoa}
                onChange={(su) => datNhap(su.target.value)}
                onKeyDown={(su) => {
                  if (su.key === "Enter" && !su.shiftKey) {
                    su.preventDefault();
                    if (!dangDocTep) onGui();
                  }
                }}
                aria-label="Câu hỏi pháp lý"
                // Hai tệp thì gợi thẳng việc chỉ hai tệp mới làm được: người
                // dùng vừa đính kèm tờ thứ hai hiếm khi muốn hỏi riêng về tờ
                // thứ nhất, và không ai đoán được rằng KLAW so sánh được.
                placeholder={
                  daDinhKem.length === 0
                    ? "Hỏi về quy định pháp luật hoặc yêu cầu soạn văn bản…"
                    : daDinhKem.length === 1
                      ? "Hỏi về tài liệu vừa đính kèm…"
                      : "So sánh hai tài liệu…"
                }
                className="max-h-[176px] flex-1 resize-none bg-transparent py-2 text-sm leading-[26px] outline-none placeholder:text-muted-foreground disabled:opacity-60"
              />
              {/* Chip đứng NGAY cạnh nút gửi: đó là nơi mắt đã nhìn lúc bấm, nên
                "còn 2/10 lượt thử" tới TRƯỚC cú bấm cuối chứ không phải sau nó.
                `role="status"` để số mới sau mỗi lượt được đọc lên mà không
                cướp tiêu điểm khỏi ô đang gõ. */}
              {mucChip !== null && (
                <span
                  role="status"
                  className={cn(
                    "mb-2 rounded-full px-2 py-0.5 text-[11px]",
                    MAU_CHIP[mucMau(phanTram(mucChip))],
                  )}
                >
                  {cauChip(mucChip)}
                </span>
              )}
              <button
                type="button"
                // `() =>` chứ không truyền thẳng `onGui`: React đưa MouseEvent vào
                // đối số thứ nhất, và nơi gọi có thể nhận một tham số tuỳ chọn ở
                // đúng chỗ đó.
                onClick={() => {
                  if (!dangDocTep) onGui();
                }}
                disabled={nhap.trim() === "" || khoa}
                // Tệp đang tải: gửi lúc này là câu hỏi đi THIẾU tệp, và ở đoạn
                // chat mới thì lượt tải lẫn lượt hỏi mỗi bên mở một phiên.
                // `aria-disabled` chứ không `disabled`: nút đang giữ tiêu điểm
                // không đánh rơi nó về `<body>`; hai lối gửi tự chặn ở trên.
                aria-disabled={dangDocTep}
                aria-describedby={dangDocTep === true ? ID_DANG_TAI : undefined}
                aria-label="Gửi câu hỏi"
                className="focus-brass bg-gradient-ink mb-0.5 cursor-pointer rounded-lg p-2 text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-40 aria-disabled:cursor-default aria-disabled:opacity-40"
              >
                <Send className="size-4" aria-hidden />
              </button>
            </div>
          </div>
        )}
        <p className="mt-1.5 text-[12px] text-muted-foreground">
          KLAW cung cấp thông tin tham khảo, không thay thế tư vấn của luật sư. Vui lòng kiểm chứng
          với văn bản quy phạm pháp luật đang có hiệu lực.
        </p>
      </div>
    </div>
  );
}
