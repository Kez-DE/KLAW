import type { Bang, TraCuuKetQua } from "@/lib/klaw";
import { KhoiVanXuoi } from "./TheKetQua";

/**
 * Một bảng trong `TraCuuKetQua.bang` — `<table>` ngữ nghĩa thật (`<thead>` +
 * `<th scope="col">` + `<tbody>`), không phải `div` giả bảng: trình đọc màn
 * hình phải nhận ra đây là một bảng.
 *
 * `tieu_de` thành `<caption>`, không thành một `<p>` rời phía trên — caption
 * là chỗ trình đọc màn hình tìm tên bảng.
 *
 * Khung ngoài `overflow-x-auto` kèm `tabIndex={0}` để cuộn ngang TRONG khung
 * này khi bảng rộng hơn màn hình — thân trang không bao giờ cuộn ngang.
 * `aria-label` nêu tên bảng cho khung cuộn đó.
 *
 * Ô bảng KHÔNG ép `whitespace-nowrap`: bảng lĩnh vực (`dung_bang` phía máy
 * chủ) có nhãn dài tới 76 ký tự trên kho thật, và để chữ tự xuống dòng trong
 * ô là đủ giữ bảng đọc được — không cần thêm CSS riêng cho ca đó. Nhóm "lĩnh
 * vực chưa biết" mang ô đầu là chuỗi rỗng (`linh_vuc IS NULL` gộp về `""`,
 * cố ý không bịa nhãn — xem doc `Bang`); một ô trống KHÔNG render trống thật
 * sự (không phân biệt được với lỗi render) — hiện gạch ngang dài `—` mờ màu
 * kèm tên khả truy cập riêng. Câu `sr-only` đó trung tính về cột (component
 * không biết ngữ nghĩa cột nào cho phép ô trống), không phải một nhãn phân
 * loại như "không xác định lĩnh vực" gán cứng cho MỌI ô rỗng.
 *
 * `role="region"` trên khung cuộn: một `<div>` trần map sang role `generic`,
 * và role đó CẤM tính tên khả truy cập từ `aria-label` — `region` (+
 * `tabIndex={0}` + `aria-label`) là kỹ thuật W3C cho một vùng cuộn nhận focus,
 * để tên được đọc NGAY khi khung nhận focus.
 *
 * Ô chứa thẻ `[Điều N](cite:K)` (Task 15 — bảng so sánh từ luận điểm đã kiểm,
 * nhánh `answer`) render qua ĐÚNG `KhoiVanXuoi` mà văn xuôi dùng, để thẻ bấm
 * được như trong văn xuôi thay vì hiện ra thành cú pháp Markdown thô. Bảng kho
 * (`hoi_ve_kho`) không có thẻ nào trong ô nên đi đường cũ, hiện chuỗi trần —
 * `ketQua`/`onChonTrichDan` bỏ trống vẫn render đúng vì `KhoiVanXuoi` tự rơi
 * về chữ thường khi thiếu chúng.
 */
const GHI_CHU_O_TRONG = "Không có dữ liệu cho ô này";

export function BangKetQua({
  bang,
  ketQua,
  onChonTrichDan,
}: {
  bang: Bang;
  ketQua?: TraCuuKetQua | undefined;
  onChonTrichDan?: ((chiSo: number) => void) | undefined;
}) {
  return (
    <div
      role="region"
      tabIndex={0}
      aria-label={bang.tieu_de}
      className="focus-brass overflow-x-auto rounded-lg border border-border bg-card"
    >
      <table className="w-full border-collapse text-[13px] leading-5">
        <caption className="border-b border-border bg-[var(--color-paper-50)] px-3 py-2 text-left font-semibold text-foreground">
          {bang.tieu_de}
        </caption>
        <thead>
          <tr>
            {bang.cot.map((ten, i) => (
              <th
                key={i}
                scope="col"
                className="border-b border-border bg-[var(--color-paper-50)] px-3 py-2 text-left font-semibold text-foreground"
              >
                {ten}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bang.dong.map((hang, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              {hang.map((o, j) =>
                o === "" ? (
                  <td key={j} className="px-3 py-2 align-top text-foreground">
                    <span className="text-muted-foreground" aria-hidden="true">
                      —
                    </span>
                    <span className="sr-only">{GHI_CHU_O_TRONG}</span>
                  </td>
                ) : (
                  <td key={j} className="px-3 py-2 align-top text-foreground">
                    {o.includes("(cite:") ? (
                      <KhoiVanXuoi chu={o} ketQua={ketQua} onChon={onChonTrichDan} />
                    ) : (
                      o
                    )}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
