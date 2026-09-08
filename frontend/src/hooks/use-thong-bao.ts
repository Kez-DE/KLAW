import { useCallback, useEffect, useRef, useState } from "react";
import { apiGoc, goi, tieuDeXacThuc } from "@/lib/api";
import { laDaDanhDau, laHopThu, type ThongBao } from "@/lib/klaw";
import { catCacKhung } from "@/lib/sse-khung";

const NOI_LAI_MS = 5_000;
const TRAN_NOI_LAI_MS = 60_000;
const SO_ID_DANH_DAU_TOI_DA = 200; // trần của POST /thong-bao/da-doc
const LOI_DANH_DAU_MAC_DINH = "Không đánh dấu được. Thử lại.";

/**
 * `setTimeout` huỷ được: hết giờ HOẶC `signal` báo huỷ (unmount ngay lúc đang
 * chờ nối lại) — thứ nào tới trước. Không có nhánh huỷ thì một khoảng chờ tới
 * 60 giây (`TRAN_NOI_LAI_MS`) treo lại vô ích sau khi component đã gỡ.
 */
function nghiCho(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((giaiQuyet) => {
    if (signal.aborted) {
      giaiQuyet();
      return;
    }
    const boHen = () => {
      clearTimeout(hen);
      giaiQuyet();
    };
    const hen = setTimeout(() => {
      signal.removeEventListener("abort", boHen);
      giaiQuyet();
    }, ms);
    signal.addEventListener("abort", boHen, { once: true });
  });
}

/** Hộp thư của chính người gọi. Nguồn sự thật là GET; SSE chỉ báo "tải lại". Dùng `fetch` +
 *  `ReadableStream` như `traCuuLuong` vì `EventSource` không gửi được `Authorization`.
 *  `khiCoSuKien` (tuỳ chọn): gọi thêm mỗi khi một khung `so_chua_doc`/`thong_bao_moi` tới —
 *  `TaiKhoanProvider` dùng để tải lại `hanMuc` (khoá/mở tài khoản báo qua đúng luồng này). */
export function useThongBao(kichHoat: boolean, khiCoSuKien?: () => void) {
  const [items, setItems] = useState<ThongBao[]>([]);
  const [soChuaDoc, setSo] = useState(0);
  const [dangTai, setDangTai] = useState(false);
  const [loiDanhDau, setLoiDanhDau] = useState<string | null>(null);
  const huy = useRef<AbortController | null>(null);
  // Bảo vệ phản hồi cũ: SSE bắn `taiLai` dồn dập, hoặc "Đã đọc tất cả" gọi lại
  // ngay sau một lượt tải đang chạy, có thể khiến hai phản hồi GET về không
  // đúng thứ tự gửi đi. Chỉ lượt gọi MỚI NHẤT được phép ghi vào state.
  const theHe = useRef(0);

  const taiLai = useCallback(() => {
    if (!kichHoat) return;
    const the = ++theHe.current;
    setDangTai(true);
    void goi("/thong-bao", laHopThu).then((r) => {
      if (the !== theHe.current) return; // đã có lượt gọi mới hơn, bỏ phản hồi này
      setDangTai(false);
      if (r.ok) {
        setItems(r.data.items);
        setSo(r.data.so_chua_doc);
        setLoiDanhDau(null); // một lượt tải mới thành công cũng coi như đã qua lỗi cũ
      }
    });
  }, [kichHoat]);

  const danhDauDaDoc = useCallback(
    async (ids: number[]) => {
      if (ids.length === 0) return;
      const r = await goi("/thong-bao/da-doc", laDaDanhDau, { method: "POST", body: { ids } });
      if (r.ok) {
        setLoiDanhDau(null);
        taiLai();
      } else {
        setLoiDanhDau(r.error.message || LOI_DANH_DAU_MAC_DINH);
      }
    },
    [taiLai],
  );

  // M1: trang đang hiển thị là 50 dòng MỚI NHẤT bất kể đã đọc hay chưa, nên
  // dòng cũ chưa đọc có thể không nằm trong đó. Hỏi lại máy chủ đúng tập
  // `chi_chua_doc=true` rồi mới đánh dấu — không đoán từ những gì đã tải.
  const danhDauTatCa = useCallback(async () => {
    const r = await goi("/thong-bao?chi_chua_doc=true", laHopThu);
    if (!r.ok) {
      setLoiDanhDau(r.error.message || LOI_DANH_DAU_MAC_DINH);
      return;
    }
    setLoiDanhDau(null);
    const ids = r.data.items.map((tb) => tb.id).slice(0, SO_ID_DANH_DAU_TOI_DA);
    if (ids.length === 0) {
      taiLai(); // không còn gì chưa đọc — chỉ cần đồng bộ lại badge
      return;
    }
    await danhDauDaDoc(ids);
  }, [danhDauDaDoc, taiLai]);

  useEffect(() => {
    taiLai();
  }, [taiLai]);

  useEffect(() => {
    if (!kichHoat) return;
    let dung = false;
    // I3: `/thong-bao/luong` nằm sau cùng một hạn mức IP với mọi endpoint
    // khác — nối lại đều đặn mỗi 5s trong lúc luồng ĐANG hỏng sẽ chiếm hết
    // hạn mức đó của cả IP. Lùi theo cấp số nhân tới trần 60s; hễ nhận được
    // một khung hợp lệ (luồng còn sống) thì trả khoảng chờ về mốc 5s.
    let choMs = NOI_LAI_MS;
    const noi = async () => {
      while (!dung) {
        const ac = new AbortController();
        huy.current = ac;
        try {
          const res = await fetch(`${apiGoc()}/thong-bao/luong`, {
            headers: { ...(await tieuDeXacThuc()), Accept: "text/event-stream" },
            signal: ac.signal,
          });
          if (res.status === 401 || res.status === 403) {
            // Phiên đã mất — nối lại chỉ nhận thêm 401/403, nên dừng hẳn thay
            // vì lặp vô ích.
            dung = true;
            break;
          }
          if (!res.ok || res.body === null) throw new Error(String(res.status));
          const doc = res.body.getReader();
          const giaiMa = new TextDecoder();
          let dem = "";
          for (;;) {
            const { done, value } = await doc.read();
            if (done) break;
            const cat = catCacKhung(`${dem}${giaiMa.decode(value, { stream: true })}`);
            dem = cat.con;
            if (cat.khung.length > 0) choMs = NOI_LAI_MS; // ít nhất một khung parse được: luồng sống
            if (cat.khung.some((k) => k.ten === "so_chua_doc" || k.ten === "thong_bao_moi")) {
              taiLai();
              khiCoSuKien?.();
            }
          }
        } catch {
          /* mất kết nối hoặc hết 30 phút: nối lại bên dưới, cách xa dần */
        }
        if (dung) break;
        await nghiCho(choMs, ac.signal);
        choMs = Math.min(choMs * 2, TRAN_NOI_LAI_MS);
      }
    };
    void noi();
    return () => {
      dung = true;
      huy.current?.abort();
    };
  }, [kichHoat, taiLai, khiCoSuKien]);

  return { soChuaDoc, items, dangTai, loiDanhDau, taiLai, danhDauDaDoc, danhDauTatCa };
}
