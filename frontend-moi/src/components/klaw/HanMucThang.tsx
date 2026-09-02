import { useEffect, useState } from "react";
import { goi } from "@/lib/api";
import { laHanMuc, type HanMuc } from "@/lib/klaw";

/**
 * Hạn mức tháng — `GET /han-muc`.
 *
 * `ap_dung: false` ⇒ **ẩn hẳn**. Bốn trường số về `null` chứ không phải 0, và
 * backend nói rõ vì sao: 0 đọc thành "bạn chưa dùng lượt nào", một khẳng định
 * sai về một thứ hệ thống không hề đo. Vỏ ứng dụng từng có một `TrialMeter`
 * hiện "còn N/20 lượt hỏi" trong khi không có hệ thống hạn mức nào tồn tại —
 * đó chính là chế độ hỏng mà thành phần này thay thế.
 *
 * `ghi_chu` của máy chủ được hiện NGUYÊN VĂN kể cả khi `ap_dung: false`: câu đó
 * nói ra thứ vẫn còn hiệu lực (trần chi phí ngày, giới hạn tần suất), và giấu
 * nó đi sẽ để người đọc tưởng không có giới hạn nào.
 */
export function HanMucThang({ className }: { className?: string }) {
  const [hanMuc, datHanMuc] = useState<HanMuc | null>(null);

  useEffect(() => {
    const dieuKhien = new AbortController();
    void goi("/han-muc", laHanMuc, { signal: dieuKhien.signal }).then((kq) => {
      if (kq.ok) datHanMuc(kq.data);
    });
    return () => dieuKhien.abort();
  }, []);

  if (hanMuc === null) return null;

  const datLai = new Date(hanMuc.dat_lai_luc).toLocaleDateString("vi-VN");

  if (!hanMuc.ap_dung) {
    return (
      <div className={className}>
        <p className="m-0 text-[13px] leading-5 text-muted-foreground">
          <span className="font-semibold text-foreground">
            Bản triển khai này chưa đếm lượt theo tài khoản.
          </span>{" "}
          {hanMuc.ghi_chu}
        </p>
      </div>
    );
  }

  const conLai = hanMuc.con_lai;
  const tong = hanMuc.han_muc;

  return (
    <div className={className}>
      <p className="m-0 text-[13px] text-muted-foreground">
        Gói <span className="font-medium text-foreground">{hanMuc.plan ?? "không rõ"}</span> · đặt
        lại ngày {datLai}
      </p>
      {conLai !== null && tong !== null && (
        <>
          <p className="font-display m-0 mt-1 text-2xl font-bold text-primary">
            {conLai}
            <span className="ml-1.5 font-sans text-[13px] font-normal text-muted-foreground">
              / {tong} lượt còn lại
            </span>
          </p>
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={tong}
            aria-valuenow={conLai}
            aria-valuetext={`Còn ${conLai} trên ${tong} lượt trong tháng này`}
            className="mt-2 h-1 w-full overflow-hidden rounded-full bg-[var(--color-paper-200)]"
          >
            <div
              className="h-full origin-left bg-primary"
              style={{ transform: `scaleX(${tong === 0 ? 0 : conLai / tong})` }}
            />
          </div>
        </>
      )}
      <p className="mt-2 mb-0 text-[12px] leading-5 text-muted-foreground">{hanMuc.ghi_chu}</p>
    </div>
  );
}
