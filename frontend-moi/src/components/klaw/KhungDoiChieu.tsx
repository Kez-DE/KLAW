import { useEffect, useRef, useSyncExternalStore } from "react";
import { X } from "lucide-react";
import type { ApiError, VanBanQuanhDieu } from "@/lib/klaw";
import { gomHangBang, type DongCoBang } from "@/lib/bang";
import { catTheoTrichDan } from "@/lib/trich-dan";
import { cn } from "@/lib/utils";
import { BaoLoi } from "./BaoLoi";
import { NoiDungDieuKhoan } from "./NoiDungDieuKhoan";

/**
 * Khung đối chiếu — nguyên văn điều luật, câu trích được đánh dấu.
 *
 * Đây LÀ click-to-verify, đóng góp trung tâm của đề tài. Bốn điểm không được
 * làm sai, và ba trong bốn điểm đã từng bị làm sai ở đâu đó:
 *
 * 1. **Mở bằng `khop_tai_id`, KHÔNG phải `provision_id`.** `provision_id`
 *    thường chỉ trỏ tới TIÊU ĐỀ của Điều; nội dung nằm ở Khoản/Điểm con. Hai
 *    id khác nhau ở **73,6% số Điều**. Mở bằng `provision_id` nghĩa là ba phần
 *    tư số lần bấm "kiểm chứng" sẽ mở ra một tiêu đề trống — đúng thao tác
 *    trung tâm của sản phẩm, hỏng ở gần như mọi lần dùng. Prop tên
 *    `khopTaiId`, không có prop `provisionId`, để không ai truyền nhầm.
 * 2. **`la_tam` tô cả VÙNG.** Cờ đó bật cho Điều tâm VÀ mọi Khoản/Điểm con của
 *    nó, nên vùng rọi sáng là một khối liên tục, không phải một dòng.
 * 3. **`quote` là TUỲ CHỌN.** Một trích dẫn có câu trích thật; một phát hiện
 *    của bộ soát thì không (`can_cu` chỉ là địa chỉ điều luật). Không có quote
 *    thì mở đúng Điều rồi IM LẶNG — không báo "không định vị được câu trích"
 *    về một câu trích chưa từng tồn tại.
 * 4. **Điều lân cận mờ đi bằng `opacity`, không bằng màu.** Chữ nguyên văn
 *    không bao giờ đổi màu theo trạng thái; màu trong khung này chỉ nói "chỗ
 *    này là chỗ bạn đang kiểm", không nói "điều luật này tốt hay xấu".
 *
 * Pha 5 dựng phần TRÌNH BÀY: dữ liệu và vòng đời tải vào qua props. Ngày nối
 * endpoint, nơi gọi chỉ cần bơm `GET /van-ban/{doc_id}?around={khop_tai_id}`
 * vào đúng ba props `trangThai` / `vanBan` / `loi`.
 */

/**
 * Điểm gãy theo NỘI DUNG, không theo tên thiết bị: hai cột chỉ bật khi còn đủ
 * chỗ cho mặt đọc VÀ một khung nguyên văn đọc được cạnh nó.
 */
const TRUY_VAN_HAI_COT = "(min-width: 68rem)";

function dangKyHaiCot(doiY: () => void): () => void {
  const truyVan = window.matchMedia(TRUY_VAN_HAI_COT);
  truyVan.addEventListener("change", doiY);
  return () => truyVan.removeEventListener("change", doiY);
}

/** true khi đọc được câu trả lời và nguyên văn CÙNG LÚC. */
export function useHaiCot(): boolean {
  return useSyncExternalStore(
    dangKyHaiCot,
    () => window.matchMedia(TRUY_VAN_HAI_COT).matches,
    // Máy chủ không biết bề rộng cửa sổ. Đoán một cột là đoán an toàn: bố cục
    // một cột không bao giờ tràn ngang, còn đoán hai cột thì có.
    () => false,
  );
}

const LE_THEO_CAP: Record<string, string> = {
  dieu: "0rem",
  khoan: "1rem",
  diem: "2rem",
};

interface Khoi {
  laTam: boolean;
  dong: DongCoBang[];
}

/**
 * Gộp các dòng liên tiếp cùng trạng thái `la_tam` thành một VÙNG.
 *
 * Chạy SAU `gomHangBang`: hàng bảng mang đúng `la_tam` của dòng cha (đã đo trên
 * kho thật), nên thu hàng về cha trước rồi mới chia vùng thì không vùng nào bị
 * cắt đôi giữa một cái bảng.
 */
function tachTheoTam(dong: readonly DongCoBang[]): Khoi[] {
  const khoi: Khoi[] = [];
  for (const mot of dong) {
    const cuoi = khoi[khoi.length - 1];
    if (cuoi !== undefined && cuoi.laTam === mot.dieuKhoan.la_tam) cuoi.dong.push(mot);
    else khoi.push({ laTam: mot.dieuKhoan.la_tam, dong: [mot] });
  }
  return khoi;
}

export interface KhungDoiChieuProps {
  /**
   * Dòng khớp THẬT SỰ — `Citation.khop_tai_id`. Xem điểm 1 ở đầu file.
   * Chỉ dòng này được tô câu trích; cả VÙNG `la_tam` được rọi sáng.
   */
  khopTaiId: number;
  /** "45/2019/QH14 > Điều 127 > Khoản 2" — hiện ngay, kể cả khi còn đang tải. */
  duongDan?: string;
  /** Có → tô sáng câu trích. Không có → chỉ mở đúng Điều, và im lặng. */
  quote?: string | null;
  trangThai: "dang-tai" | "loi" | "xong";
  vanBan?: VanBanQuanhDieu | null;
  loi?: ApiError | null;
  onDong: () => void;
  onThuLai?: () => void;
}

export function KhungDoiChieu({
  khopTaiId,
  duongDan,
  quote = null,
  trangThai,
  vanBan = null,
  loi = null,
  onDong,
  onThuLai,
}: KhungDoiChieuProps) {
  const haiCot = useHaiCot();
  const tieuDe = useRef<HTMLHeadingElement>(null);
  const vungCuon = useRef<HTMLDivElement>(null);
  /** Chip đã mở khung — nơi tiêu điểm phải quay về khi khung đóng. */
  const noiMo = useRef<HTMLElement | null>(null);

  // Chuỗi rỗng KHÔNG phải một câu trích. Quy về null một lần ở đây để không
  // nhánh nào bên dưới phải tự nhớ phân biệt.
  const cauTrich = quote !== null && quote.trim() !== "" ? quote : null;

  // Esc đóng khung, kể cả khi tiêu điểm đã đi ra ngoài.
  useEffect(() => {
    const nghe = (su: KeyboardEvent) => {
      if (su.key === "Escape") onDong();
    };
    window.addEventListener("keydown", nghe);
    return () => window.removeEventListener("keydown", nghe);
  }, [onDong]);

  // Mở khung — hoặc đổi sang một trích dẫn khác khi khung đang mở: ghi lại
  // phần tử vừa mở nó (lúc bấm, chính chip đó đang giữ tiêu điểm) rồi đưa tiêu
  // điểm vào tiêu đề. Đổi trích dẫn mà KHÔNG dời tiêu điểm là đổi nội dung
  // khung trong im lặng — trình đọc màn hình không có gì báo là đã đổi.
  useEffect(() => {
    const dangGiu = document.activeElement;
    if (dangGiu instanceof HTMLElement && dangGiu !== tieuDe.current && dangGiu !== document.body) {
      noiMo.current = dangGiu;
    }
    tieuDe.current?.focus();
  }, [khopTaiId]);

  // Đóng khung: trả tiêu điểm về đúng cái chip đã mở nó. Không trả thì tiêu
  // điểm rơi về `<body>`, và người dùng bàn phím phải Tab lại từ đầu trang qua
  // toàn bộ điều hướng để về chỗ cũ. Chip có thể đã biến mất (lượt tra cứu
  // mới), nên kiểm `isConnected` trước khi gọi.
  useEffect(
    () => () => {
      const ve = noiMo.current;
      if (ve !== null && ve.isConnected) ve.focus();
    },
    [],
  );

  // Một cột: khung phủ toàn màn hình nên khoá cuộn nền phía sau.
  useEffect(() => {
    if (haiCot) return;
    const cu = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = cu;
    };
  }, [haiCot]);

  // Nguyên văn về kèm các Điều liền TRƯỚC, nên mở ra là thấy Điều lân cận chứ
  // không phải điều đang được kiểm chứng. Kéo vùng tâm lên đầu khung đọc.
  // Cuộn TAY thay vì `scrollIntoView`: hàm đó cuộn cả các vùng cuộn tổ tiên,
  // tức kéo luôn cả trang đi chỗ khác và đẩy phần đầu khung ra khỏi mép trên.
  useEffect(() => {
    if (vanBan === null) return;
    const khung = requestAnimationFrame(() => {
      const boc = vungCuon.current;
      if (boc === null) return;
      const tam = boc.querySelector("[data-vung-tam]");
      if (tam === null) return;
      boc.scrollTop += tam.getBoundingClientRect().top - boc.getBoundingClientRect().top - 16;
    });
    return () => cancelAnimationFrame(khung);
  }, [vanBan]);

  const dongKhop = vanBan?.provisions.find((dieuKhoan) => dieuKhoan.id === khopTaiId) ?? null;
  // Chỉ nói "không định vị được" khi CÓ một câu trích để định vị.
  const khongDinhVi =
    cauTrich !== null && dongKhop !== null && !catTheoTrichDan(dongKhop.noi_dung, cauTrich).timThay;

  return (
    <aside
      // `aria-modal` là lời khai với công nghệ hỗ trợ rằng PHẦN CÒN LẠI CỦA
      // TRANG KHÔNG TỒN TẠI. Chỉ khai ở bố cục một cột, nơi khung thật sự phủ
      // kín màn hình. Khai xong thì `useKhungModalDangMo` ở __root.tsx tự bọc
      // `inert` quanh điều hướng và chân trang — lời khai và việc thi hành lời
      // khai không thể lệch nhau.
      role={haiCot ? "region" : "dialog"}
      aria-modal={haiCot ? undefined : true}
      aria-label="Nguyên văn điều luật"
      className={cn(
        haiCot ? "sticky top-4 self-start" : "fixed inset-0 z-50 flex flex-col bg-background p-3",
      )}
    >
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-elegant">
        <header className="flex items-start gap-3 border-b border-border p-3">
          <h2
            ref={tieuDe}
            tabIndex={-1}
            className="focus-brass m-0 min-w-0 flex-1 rounded text-[15px] leading-6 font-medium"
          >
            <span className="mb-1 block text-[12px] font-normal text-muted-foreground">
              Nguyên văn
            </span>
            <span className="font-jetbrains block text-[13px] text-foreground">
              {vanBan?.so_ky_hieu ?? ""}
            </span>
            {duongDan !== undefined && duongDan !== "" && (
              <span className="block text-[13px] font-normal text-muted-foreground">
                {duongDan}
              </span>
            )}
          </h2>
          <button
            type="button"
            onClick={onDong}
            aria-label="Đóng khung nguyên văn"
            className="focus-brass grid size-11 shrink-0 cursor-pointer place-items-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)]"
          >
            <X className="size-4" aria-hidden />
          </button>
        </header>

        <div
          ref={vungCuon}
          className={cn(
            "min-h-0 flex-1 overflow-y-auto p-3",
            haiCot && "max-h-[calc(100svh-9rem)]",
          )}
        >
          {trangThai === "dang-tai" && (
            <p role="status" className="m-0 text-[15px] text-muted-foreground">
              Đang mở nguyên văn…
            </p>
          )}

          {trangThai === "loi" && loi !== null && (
            <BaoLoi loi={loi} {...(onThuLai ? { onThuLai } : {})} />
          )}

          {trangThai === "xong" && vanBan !== null && (
            <>
              {khongDinhVi && (
                <p className="mt-0 mb-3 text-[13px] leading-5 text-muted-foreground">
                  Không định vị được câu trích trong nguyên văn bên dưới, nên chưa đánh dấu. Câu
                  trích hệ thống dẫn: “{cauTrich}”
                </p>
              )}

              <div className="doc-reader rounded-lg bg-[var(--color-paper-50)] p-3 text-foreground">
                {tachTheoTam(gomHangBang(vanBan.provisions)).map((khoi) => {
                  const dauKhoi = khoi.dong[0];
                  if (dauKhoi === undefined) return null;
                  return (
                    <section
                      key={dauKhoi.dieuKhoan.id}
                      data-vung-tam={khoi.laTam ? "true" : undefined}
                      className={cn(
                        "rounded-lg px-2 py-1",
                        khoi.laTam ? "vung-doi-chieu" : "ngoai-vung-doi-chieu",
                      )}
                    >
                      {khoi.dong.map(({ dieuKhoan, hangCon }) => (
                        <div key={dieuKhoan.id}>
                          {dieuKhoan.cap === "dieu" && (
                            <p className="mt-2 mb-1 font-sans text-[13px] font-semibold text-muted-foreground">
                              {dieuKhoan.duong_dan}
                              {dieuKhoan.tieu_de !== "" && ` — ${dieuKhoan.tieu_de}`}
                            </p>
                          )}
                          <NoiDungDieuKhoan
                            dieuKhoan={dieuKhoan}
                            noiDung={dieuKhoan.noi_dung}
                            hangCon={hangCon}
                            // Trích dẫn có thể trỏ thẳng vào MỘT HÀNG bảng
                            // (`hang_bang` là dòng thật, có `duong_dan` riêng).
                            // Hàng đó nay nằm trong khối của dòng cha, nên câu
                            // trích phải đi vào cả khối; `vungTrichDan` tự tìm
                            // ra nó nằm ở mảnh nào.
                            quote={
                              dieuKhoan.id === khopTaiId ||
                              hangCon.some((hang) => hang.id === khopTaiId)
                                ? cauTrich
                                : null
                            }
                            // KHÔNG dựng liên kết ở đây: khung này là chỗ kiểm
                            // chứng một câu trả lời, và bấm một hàng để rời
                            // trang là vứt mất câu trả lời đang kiểm. Hàng vẫn
                            // neo được bằng `id="dk-<id>"`.
                            style={{ marginInlineStart: LE_THEO_CAP[dieuKhoan.cap] ?? "0rem" }}
                          />
                        </div>
                      ))}
                    </section>
                  );
                })}
              </div>

              <p className="mt-3 mb-0 text-[12px] leading-5 text-muted-foreground">
                Hiển thị Điều được dẫn cùng các Điều liền trước và liền sau. Nguyên văn lấy từ CSDL:
                không rút gọn, không sửa chính tả.
              </p>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
