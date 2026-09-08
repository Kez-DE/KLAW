import { useCallback, useEffect, useRef, useState } from "react";
import { apiGoc, goi, tieuDeXacThuc } from "@/lib/api";
import { laDaDanhDau, laHopThu, type ThongBao } from "@/lib/klaw";
import { catCacKhung } from "@/lib/sse-khung";

const NOI_LAI_MS = 5_000;

/** Hộp thư của chính người gọi. Nguồn sự thật là GET; SSE chỉ báo "tải lại". Dùng `fetch` +
 *  `ReadableStream` như `traCuuLuong` vì `EventSource` không gửi được `Authorization`. */
export function useThongBao(kichHoat: boolean) {
  const [items, setItems] = useState<ThongBao[]>([]);
  const [soChuaDoc, setSo] = useState(0);
  const [dangTai, setDangTai] = useState(false);
  const huy = useRef<AbortController | null>(null);

  const taiLai = useCallback(() => {
    if (!kichHoat) return;
    setDangTai(true);
    void goi("/thong-bao", laHopThu).then((r) => {
      setDangTai(false);
      if (r.ok) {
        setItems(r.data.items);
        setSo(r.data.so_chua_doc);
      }
    });
  }, [kichHoat]);

  const danhDauDaDoc = useCallback(
    async (ids: number[]) => {
      if (ids.length === 0) return;
      const r = await goi("/thong-bao/da-doc", laDaDanhDau, { method: "POST", body: { ids } });
      if (r.ok) taiLai();
    },
    [taiLai],
  );

  useEffect(() => {
    taiLai();
  }, [taiLai]);

  useEffect(() => {
    if (!kichHoat) return;
    let dung = false;
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
            // Phiên đã mất — nối lại mỗi 5 giây sẽ chỉ nhận thêm 401/403,
            // nên dừng hẳn thay vì lặp vô ích.
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
            if (cat.khung.some((k) => k.ten === "so_chua_doc" || k.ten === "thong_bao_moi")) {
              taiLai();
            }
          }
        } catch {
          /* mất kết nối hoặc hết 30 phút: nối lại bên dưới */
        }
        if (!dung) await new Promise((r) => setTimeout(r, NOI_LAI_MS));
      }
    };
    void noi();
    return () => {
      dung = true;
      huy.current?.abort();
    };
  }, [kichHoat, taiLai]);

  return { soChuaDoc, items, dangTai, taiLai, danhDauDaDoc };
}
