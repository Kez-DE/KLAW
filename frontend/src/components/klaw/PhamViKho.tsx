import { useEffect, useState } from "react";
import { goi } from "@/lib/api";
import { laPhamVi, type PhamVi } from "@/lib/klaw";

/**
 * Kích thước kho, ĐẾM TỪ MÁY CHỦ (`GET /pham-vi`).
 *
 * Trang chủ cũ ghi "12+ lĩnh vực · 30+ mẫu · < 10s cho một bản dự thảo". Cả ba
 * đều sai, và cái sai nguy hiểm nhất không phải độ lệch mà là chỗ đứng: một con
 * số viết cứng trong JSX sai ngay lần seed tiếp theo và không ai biết. Dự án
 * này tồn tại để chống đúng loại khẳng định không kiểm chứng được đó, nên số
 * của chính nó phải đi qua API.
 *
 * **Hai tầng, vì kho thật có hai tầng.** `sau` có toàn văn và trả lời được
 * thành `answer`; `nong` chỉ có metadata và CHÍNH LÀ thứ sinh ra
 * `partial_coverage`. Gộp hai con số thành một "N văn bản" là hứa chiều sâu mà
 * 79/126 văn bản không có.
 *
 * Chưa lấy được số thì KHÔNG hiện gì. Một con số dự phòng viết cứng ở đây sẽ là
 * đúng thứ vừa gỡ bỏ, chỉ khác là nó chỉ xuất hiện lúc mạng hỏng.
 */
export function PhamViKho({ className }: { className?: string }) {
  const [phamVi, datPhamVi] = useState<PhamVi | null>(null);

  useEffect(() => {
    const dieuKhien = new AbortController();
    void goi("/pham-vi", laPhamVi, { signal: dieuKhien.signal }).then((kq) => {
      if (kq.ok) datPhamVi(kq.data);
    });
    return () => dieuKhien.abort();
  }, []);

  if (phamVi === null) return null;

  const tongVanBan = phamVi.sau.so_van_ban + phamVi.nong.so_van_ban;

  return (
    <dl className={className}>
      <div>
        <dt className="text-[13px] text-muted-foreground">Văn bản trong kho</dt>
        <dd className="font-display m-0 text-2xl font-bold text-primary">{tongVanBan}</dd>
      </div>
      <div>
        <dt className="text-[13px] text-muted-foreground">Có toàn văn, tra cứu tới điều khoản</dt>
        <dd className="font-display m-0 text-2xl font-bold text-primary">
          {phamVi.sau.so_van_ban}
          <span className="ml-1.5 font-sans text-[13px] font-normal text-muted-foreground">
            {phamVi.sau.so_dieu_khoan.toLocaleString("vi-VN")} điều khoản
          </span>
        </dd>
      </div>
      <div>
        <dt className="text-[13px] text-muted-foreground">Chỉ có thông tin văn bản</dt>
        <dd className="font-display m-0 text-2xl font-bold text-primary">
          {phamVi.nong.so_van_ban}
        </dd>
      </div>
      <p className="col-span-full m-0 text-[12px] leading-5 text-muted-foreground">
        {phamVi.nong.so_van_ban} văn bản trong kho mới có thông tin văn bản, chưa có toàn văn. Hỏi
        về chúng, KLAW nêu đích danh văn bản chi phối và dừng lại ở đó thay vì diễn giải.
      </p>
    </dl>
  );
}
