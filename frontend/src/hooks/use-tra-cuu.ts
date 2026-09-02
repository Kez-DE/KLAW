import { useCallback, useRef, useState } from "react";
import { traCuuLuong } from "@/lib/api";
import type { LuotTruoc } from "@/lib/klaw";
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
  /**
   * Của máy chủ. KHÔNG hiện ra ở màn hình thường — chỉ đi vào `data-trace` của
   * khối kết quả và vào màn báo lỗi, nơi một mã chép được là thứ có ích thật.
   */
  traceId: string | null;
  /** `lichSu`: các lượt ĐÃ XONG, mới nhất SAU CÙNG. Rỗng/vắng ⇒ máy chủ không
   *  chạy `giai_nghia`, tức lượt đầu không tốn thêm token. Nơi gọi tự cắt
   *  bằng `dungLichSu` — quá trần là 422, máy chủ KHÔNG truncate. */
  hoi: (cauHoi: string, lichSu?: LuotTruoc[]) => void;
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
  const luot = useRef(0);
  // `lichSu` của lượt VỪA hỏi, giữ bên cạnh `cauHoi` để `thuLai` phát lại
  // ĐÚNG cùng đối số — thiếu nó thì hỏi lại một câu nối tiếp mất `lich_su`,
  // `_vao_graph` coi như câu ĐỘC LẬP và tái hiện đúng lỗi ban đầu.
  const lichSuGanNhat = useRef<LuotTruoc[] | undefined>(undefined);

  const hoi = useCallback(
    (noiDungTho: string, lichSu?: LuotTruoc[]) => {
      const noiDung = noiDungTho.trim();
      if (noiDung === "") return;

      luot.current += 1;
      const luotNay = luot.current;

      lichSuGanNhat.current = lichSu;
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
          // KHÔNG gửi `as_of_date`. `config.py` phân giải nó là
          // `yeu_cau or settings.as_of_date or date.today()`, nên khoá vắng mặt
          // đã có nghĩa "tính hiệu lực tới hôm nay" — đúng thứ người dùng muốn
          // mà không phải chọn gì. Gửi một ngày do FE tự tính chỉ thêm một
          // nguồn sai lệch (đồng hồ máy khách, múi giờ) cho cùng một kết quả.
          // `lich_su` chỉ đi kèm khi THẬT SỰ có lượt trước: gửi `[]` cũng vô hại
          // (máy chủ kiểm `if req.lich_su`) nhưng khoá vắng mặt nói đúng hơn
          // rằng đây là lượt đầu.
          {
            query: noiDung,
            ...(lichSu !== undefined && lichSu.length > 0 ? { lich_su: lichSu } : {}),
          },
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
    if (cauHoi !== null) hoi(cauHoi, lichSuGanNhat.current);
  }, [cauHoi, hoi]);

  const datLai = useCallback(() => {
    luot.current += 1;
    datCauHoi(null);
    datCacBuoc([]);
    datDaPhat([]);
    datTraceId(null);
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
    hoi,
    huy,
    thuLai,
    datLai,
  };
}
