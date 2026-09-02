import { useEffect, useState } from "react";

/**
 * true khi trên trang có một thành phần khai `aria-modal="true"`.
 *
 * Khai `aria-modal` là nói với công nghệ hỗ trợ rằng **phần còn lại của trang
 * không tồn tại**. Nhưng lời khai đó chỉ đổi cách trình đọc màn hình đọc; nó
 * KHÔNG chặn phím Tab. Ở bố cục một cột, khung đối chiếu phủ kín màn hình, và
 * Tab vài lần là tiêu điểm đi ra một liên kết điều hướng đang nằm khuất sau
 * lớp phủ đặc — Enter ở đó mất trắng cả khung lẫn kết quả, trên đúng thao tác
 * trung tâm của sản phẩm.
 *
 * Vỏ trang (`AppShell`, `MarketingShell`) là **anh em** của nội dung, nằm ngoài
 * tầm với của mọi bản vá cấp trang, nên bản vá phải nằm ở vỏ. Một cơ chế duy
 * nhất, đọc thẳng lời khai trong DOM, thay vì một bản vá trong từng khung:
 * lời khai và việc thi hành lời khai không thể lệch nhau, và khung modal thêm
 * về sau tự động được phủ mà không ai phải nhớ đi nối dây.
 *
 * `inert` là cách gốc của trình duyệt — nó gỡ cả tiêu điểm, cả con trỏ, cả cây
 * trợ năng cùng lúc. Không tự dựng bẫy tiêu điểm bằng tay.
 */
export function useKhungModalDangMo(): boolean {
  const [dangMo, datDangMo] = useState(false);

  useEffect(() => {
    const doLai = () => datDangMo(document.querySelector('[aria-modal="true"]') !== null);
    doLai();
    const quanSat = new MutationObserver(doLai);
    quanSat.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-modal"],
    });
    return () => quanSat.disconnect();
  }, []);

  return dangMo;
}
