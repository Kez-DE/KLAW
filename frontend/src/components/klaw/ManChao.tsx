import { FileSignature, Gavel, Landmark, Scale, Search } from "lucide-react";

/**
 * Màn chào của trợ lý — chuyển nguyên từ `KlawChat` (route `/chat`, đã xoá:
 * spec 2026-09-06 §4). Bấm gợi ý thì ĐIỀN vào ô soạn, không gửi — người dùng
 * còn sửa câu trước khi hỏi; ô soạn và cổng đăng nhập là việc của `/dung-thu`.
 */
const GOI_Y = [
  {
    icon: Search,
    tieuDe: "Tra cứu quy định",
    cau: "Thời gian thử việc tối đa với công việc của người quản lý doanh nghiệp là bao lâu?",
  },
  {
    icon: FileSignature,
    tieuDe: "Soạn hợp đồng",
    cau: "Soạn giúp tôi hợp đồng lao động xác định thời hạn 12 tháng cho vị trí nhân viên kinh doanh.",
  },
  {
    icon: Landmark,
    tieuDe: "Nghĩa vụ của người sử dụng lao động",
    cau: "Người sử dụng lao động phải báo trước bao nhiêu ngày khi đơn phương chấm dứt hợp đồng lao động?",
  },
  {
    icon: Gavel,
    tieuDe: "Soạn đơn",
    cau: "Soạn giúp tôi đơn xin nghỉ việc theo đúng thời hạn báo trước của Bộ luật Lao động 2019.",
  },
] as const;

export function ManChao({ onChonGoiY }: { onChonGoiY: (cau: string) => void }) {
  return (
    <div className="soft-fade mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center py-14 text-center">
      <span className="bg-gradient-ink flex size-16 items-center justify-center rounded-2xl text-primary-foreground shadow-soft">
        <Scale className="size-8" aria-hidden />
      </span>
      <h2 className="font-display mt-5 text-3xl font-bold text-primary">Xin chào, tôi là KLAW</h2>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Tôi tra cứu quy định pháp luật Việt Nam theo điều, khoản, điểm — sâu nhất ở lĩnh vực lao
        động — và soạn thảo văn bản pháp lý. Mỗi câu trả lời nêu rõ văn bản và điều khoản để bạn tự
        kiểm chứng.
      </p>
      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
        {GOI_Y.map((g) => (
          <button
            key={g.tieuDe}
            type="button"
            onClick={() => onChonGoiY(g.cau)}
            className="focus-brass group cursor-pointer rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-all duration-150 hover:-translate-y-1 hover:border-[var(--color-brass-500)]/60 hover:shadow-lg motion-reduce:hover:translate-y-0"
          >
            <span className="flex items-center gap-2 text-primary">
              <g.icon className="size-4" aria-hidden />
              <span className="font-display text-sm font-semibold">{g.tieuDe}</span>
            </span>
            <span className="mt-2 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
              {g.cau}
            </span>
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Chọn một gợi ý để điền vào ô soạn bên dưới.
      </p>
    </div>
  );
}
