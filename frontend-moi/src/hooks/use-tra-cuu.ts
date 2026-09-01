import { useCallback, useRef, useState } from "react";
import { traCuuLuong } from "@/lib/api";
import type { ApiError, BuocKhai, SuKienBuoc, TraCuuKetQua } from "@/lib/klaw";
import { useGoiApi } from "./use-goi-api";

/**
 * Một lượt hỏi KLAW qua `POST /tra-cuu/luong`.
 *
 * Vòng đời (huỷ thật, lượt mới thay lượt cũ, tháo component thì huỷ) mượn
 * nguyên `useGoiApi` — nó đã đúng từ pha 5 và không có lý do gì để viết lại.
 * Cái hook này thêm đúng một việc mà `useGoiApi` không làm được: giữ các sự
 * kiện TRUNG GIAN của stream, vì `useGoiApi` chỉ biết một kết quả cuối.
 *
 * `luot` chống việc sự kiện của lượt CŨ ghi đè bảng bước của lượt mới: stream
 * cũ có thể còn vài khung trên đường khi người dùng đã hỏi câu khác, và
 * `AbortController` cắt được `fetch` chứ không cắt được một callback đã lên
 * lịch. `useGoiApi` đã bảo vệ phần kết quả; phần bước phải tự bảo vệ.
 */
export interface TrangThaiTraCuu {
  /** Câu hỏi của lượt đang chạy hoặc vừa xong. */
  cauHoi: string | null;
  dangChay: boolean;
  /** Bước do máy chủ khai. Rỗng cho tới khi `event: bat_dau` tới. */
  cacBuoc: BuocKhai[];
  daPhat: SuKienBuoc[];
  ketQua: TraCuuKetQua | null;
  loi: ApiError | null;
  /** Của máy chủ, dùng để đối chiếu với bảng `traces` khi cần truy vết. */
  traceId: string | null;
  /**
   * Ngày dùng để tính hiệu lực cho lượt đang chạy, ISO `2026-09-01`. `null` là
   * "hôm nay" — máy chủ tự lấy ngày hiện tại và FE KHÔNG gửi trường này.
   *
   * Giữ lại theo LƯỢT chứ không đọc thẳng từ ô chọn ngày: người dùng đổi ngày
   * sau khi đã hỏi thì câu trả lời cũ vẫn phải khai đúng ngày nó được tính.
   */
  asOfDate: string | null;
  hoi: (cauHoi: string, asOfDate?: string) => void;
  huy: () => void;
  /** Hỏi lại ĐÚNG câu vừa rồi. Không có câu nào thì không làm gì. */
  thuLai: () => void;
  datLai: () => void;
}

export function useTraCuu(): TrangThaiTraCuu {
  const goi = useGoiApi<TraCuuKetQua>();
  const { chay, huy: huyGoi, datLai: datLaiGoi } = goi;

  const [cauHoi, datCauHoi] = useState<string | null>(null);
  const [cacBuoc, datCacBuoc] = useState<BuocKhai[]>([]);
  const [daPhat, datDaPhat] = useState<SuKienBuoc[]>([]);
  const [traceId, datTraceId] = useState<string | null>(null);
  const [asOfDate, datAsOfDate] = useState<string | null>(null);
  const luot = useRef(0);

  const hoi = useCallback(
    (noiDungTho: string, ngay?: string) => {
      const noiDung = noiDungTho.trim();
      if (noiDung === "") return;
      // Chuỗi rỗng của <input type="date"> nghĩa là "chưa chọn", không phải một
      // ngày. Gửi nó đi sẽ ăn 422 từ pydantic.
      const asOf = ngay !== undefined && ngay !== "" ? ngay : null;

      luot.current += 1;
      const luotNay = luot.current;

      datAsOfDate(asOf);
      datCauHoi(noiDung);
      datCacBuoc([]);
      datDaPhat([]);
      datTraceId(null);
      // Xoá kết quả cũ TRƯỚC khi chạy: `useGoiApi` giữ kết quả trước cho tới
      // khi có kết quả mới, đúng cho một lần tải lại, nhưng ở đây nó sẽ để câu
      // trả lời của câu hỏi TRƯỚC nằm dưới câu hỏi MỚI trong lúc chờ.
      datLaiGoi();

      void chay((signal) =>
        traCuuLuong(
          // Không có ngày thì KHÔNG gửi khoá: `as_of_date: null` và khoá vắng
          // mặt đều về "hôm nay" ở pydantic, nhưng khoá vắng mặt là thứ duy
          // nhất nói đúng rằng người dùng chưa chọn gì.
          { query: noiDung, ...(asOf === null ? {} : { as_of_date: asOf }) },
          {
            onBatDau: (su) => {
              if (luotNay !== luot.current) return;
              datCacBuoc(su.cac_buoc);
              datTraceId(su.trace_id);
            },
            onBuoc: (su) => {
              if (luotNay !== luot.current) return;
              datDaPhat((truoc) => [...truoc, su]);
            },
          },
          signal,
        ),
      );
    },
    [chay, datLaiGoi],
  );

  const huy = useCallback(() => {
    luot.current += 1; // vô hiệu hoá mọi khung còn trên đường của lượt vừa huỷ
    huyGoi();
  }, [huyGoi]);

  const thuLai = useCallback(() => {
    // Hỏi lại ĐÚNG câu vừa rồi nghĩa là hỏi lại cả ở đúng ngày vừa rồi. Bỏ
    // `asOfDate` ở đây sẽ âm thầm đổi câu hỏi thành một câu khác.
    if (cauHoi !== null) hoi(cauHoi, asOfDate ?? undefined);
  }, [asOfDate, cauHoi, hoi]);

  const datLai = useCallback(() => {
    luot.current += 1;
    datCauHoi(null);
    datCacBuoc([]);
    datDaPhat([]);
    datTraceId(null);
    datAsOfDate(null);
    datLaiGoi();
  }, [datLaiGoi]);

  return {
    cauHoi,
    dangChay: goi.dangChay,
    cacBuoc,
    daPhat,
    ketQua: goi.ketQua,
    loi: goi.loi,
    traceId,
    asOfDate,
    hoi,
    huy,
    thuLai,
    datLai,
  };
}
