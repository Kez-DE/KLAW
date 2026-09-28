import { useCallback, useState } from "react";
import { goi as goiApi } from "@/lib/api";
import { laVanBanProvisions, type TrichDanDayDu, type VanBanProvisions } from "@/lib/klaw";
import { useGoiApi } from "./use-goi-api";

/**
 * Click-to-verify: mở nguyên văn điều luật quanh một trích dẫn.
 *
 * **Khoá mở là `khop_tai_id`, KHÔNG phải `provision_id`.** Hai id khác nhau ở
 * 73,6% số Điều: `provision_id` thường chỉ trỏ tới TIÊU ĐỀ của Điều, còn nội
 * dung nằm ở Khoản/Điểm con. Mở bằng `provision_id` nghĩa là ba phần tư số lần
 * bấm "kiểm chứng" sẽ mở ra một tiêu đề trống — đúng thao tác trung tâm của sản
 * phẩm, hỏng ở gần như mọi lần dùng.
 *
 * Kiểu `MoDoiChieu` vì thế KHÔNG có trường `provisionId`. Không ai truyền nhầm
 * được thứ không tồn tại.
 */
export interface MoDoiChieu {
  docId: string;
  /** `Citation.khop_tai_id` hoặc `PhatHien.khop_tai_id`. */
  khopTaiId: number;
  /** "45/2019/QH14 > Điều 127 > Khoản 2" — hiện ngay, kể cả khi còn đang tải. */
  duongDan?: string;
  /**
   * Có → tô sáng câu trích. Không có → chỉ mở đúng Điều rồi im lặng. Phát hiện
   * của bộ soát chỉ có địa chỉ điều luật, không có câu trích nào để định vị.
   */
  quote?: string | null;
  /** Nhãn hiệu lực của căn cứ đang mở — hiện ở header khung (spec 2026-09-06 §7). */
  hieuLuc?: string | null;
  /** Trích dẫn đầy đủ của căn cứ đang mở (quyết định 2026-09-28). */
  trichDan?: TrichDanDayDu;
  /** Câu `warnings[]` của cùng văn bản — `ghiChu` của nhãn hiệu lực. */
  ghiChu?: string | undefined;
}

export interface TrangThaiDoiChieu {
  /** null = khung đóng. */
  dang: MoDoiChieu | null;
  trangThai: "dang-tai" | "loi" | "xong";
  vanBan: VanBanProvisions | null;
  loi: ReturnType<typeof useGoiApi<VanBanProvisions>>["loi"];
  mo: (yeuCau: MoDoiChieu) => void;
  dong: () => void;
  thuLai: () => void;
}

export function useDoiChieu(): TrangThaiDoiChieu {
  const api = useGoiApi<VanBanProvisions>();
  const { chay, datLai } = api;
  const [dang, datDang] = useState<MoDoiChieu | null>(null);

  const tai = useCallback(
    (yeuCau: MoDoiChieu) => {
      void chay((signal) =>
        goiApi(
          `/van-ban/${encodeURIComponent(yeuCau.docId)}?around=${yeuCau.khopTaiId}`,
          laVanBanProvisions,
          { signal },
        ),
      );
    },
    [chay],
  );

  const mo = useCallback(
    (yeuCau: MoDoiChieu) => {
      datDang(yeuCau);
      // Xoá nguyên văn của trích dẫn TRƯỚC: nếu không, bấm sang trích dẫn thứ
      // hai sẽ hiện nguyên văn của trích dẫn thứ nhất trong lúc chờ — tức tô
      // sáng một câu trích trong một điều luật không phải điều luật của nó.
      datLai();
      tai(yeuCau);
    },
    [datLai, tai],
  );

  const dong = useCallback(() => {
    datDang(null);
    datLai();
  }, [datLai]);

  const thuLai = useCallback(() => {
    if (dang !== null) tai(dang);
  }, [dang, tai]);

  const trangThai: TrangThaiDoiChieu["trangThai"] =
    api.loi !== null ? "loi" : api.ketQua !== null ? "xong" : "dang-tai";

  return { dang, trangThai, vanBan: api.ketQua, loi: api.loi, mo, dong, thuLai };
}
