import { Paperclip, Send, X } from "lucide-react";
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
  tepDaDinhKem,
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
  /** Đang đọc một tệp — khoá nút cho tới khi xong. */
  dangDocTep?: boolean | undefined;
  /**
   * Tài liệu sẽ đi kèm câu hỏi sắp gửi — tối đa hai (nhánh so sánh).
   *
   * Một MẢNG chứ không phải một tệp: mỗi tệp có con chip và nút bỏ RIÊNG, vì
   * một nút "bỏ đính kèm" chung không nói được người dùng sắp bỏ tờ nào. Rỗng
   * hoặc vắng ⇒ lượt sau là một câu hỏi thường.
   */
  tepDaDinhKem?: { id: string; ten_tep: string }[] | null;
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
              <ul className="mb-2 flex list-none flex-wrap gap-2 p-0">
                {daDinhKem.map((tep) => (
                  <li
                    key={tep.id}
                    className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-[12px]"
                  >
                    <Paperclip aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 truncate" title={tep.ten_tep}>
                      {tep.ten_tep}
                    </span>
                    {onBoDinhKem && (
                      <button
                        type="button"
                        onClick={() => onBoDinhKem(tep.id)}
                        aria-label={`Bỏ đính kèm ${tep.ten_tep}`}
                        title="Bỏ đính kèm"
                        className="focus-brass -mr-1 grid size-5 shrink-0 place-items-center rounded-full hover:bg-background"
                      >
                        <X aria-hidden className="size-3.5" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
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
                    onGui();
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
                onClick={() => onGui()}
                disabled={nhap.trim() === "" || khoa}
                aria-label="Gửi câu hỏi"
                className="focus-brass bg-gradient-ink mb-0.5 cursor-pointer rounded-lg p-2 text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-40"
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
