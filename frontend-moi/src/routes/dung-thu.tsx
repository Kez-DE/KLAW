import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { CalendarClock, ChevronRight, Paperclip, Scale, Send, X } from "lucide-react";
import { AppShell } from "@/components/app/AppShell";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { MaTruyVet } from "@/components/klaw/MaTruyVet";
import { KhungDoiChieu, useHaiCot } from "@/components/klaw/KhungDoiChieu";
import { TheKetQua } from "@/components/klaw/TheKetQua";
import { TrangThaiCho } from "@/components/klaw/TrangThaiCho";
import { useDoiChieu } from "@/hooks/use-doi-chieu";
import { useTraCuu } from "@/hooks/use-tra-cuu";
import type { Citation, TraCuuKetQua } from "@/lib/klaw";
import { cn, ngayVietNam } from "@/lib/utils";

/**
 * Màn hỏi KLAW — nối vào `POST /api/v1/tra-cuu/luong` (SSE).
 *
 * Bốn điều màn này phải giữ đúng:
 *
 * 1. **Bốn `result_type`, bốn cách hiển thị.** `TheKetQua` lo phần đó;
 *    `abstain` mang màu TRUNG TÍNH vì nó là hành vi ĐÚNG và được tính điểm
 *    trong đánh giá — tô nó như lỗi là dựng một giao diện tranh luận chống lại
 *    chính luận điểm của sản phẩm.
 * 2. **Bước là đo được.** `TrangThaiCho` nhận bước THẬT từ stream, không ước
 *    lượng theo thời gian. Khoảng lặng 9,1 giây ở `tier2` là bình thường.
 * 3. **Click-to-verify mở bằng `khop_tai_id`**, không bao giờ `provision_id` —
 *    xem `useDoiChieu`.
 * 4. **Không có câu trả lời đóng hộp.** Bản Lovable chở bốn câu dựng sẵn khớp
 *    bằng regex, phát ra từng token một qua `setInterval` để trông như đang suy
 *    nghĩ; một trong bốn dẫn Nghị định 13/2023/NĐ-CP như luật đang điều chỉnh,
 *    gắn nhãn "Còn hiệu lực", trong khi nghị định đó hết hiệu lực toàn bộ từ
 *    01/01/2026. Mọi chữ trên màn này nay đến từ máy chủ.
 */

const GOI_Y = [
  "Thời gian thử việc tối đa với công việc của người quản lý doanh nghiệp là bao lâu?",
  "Người sử dụng lao động phải báo trước bao nhiêu ngày khi đơn phương chấm dứt hợp đồng lao động?",
  "Mức lương tối thiểu vùng đang áp dụng cho vùng I là bao nhiêu?",
  "Người lao động được nghỉ hằng năm bao nhiêu ngày và tính lương thế nào?",
];

interface LuotDaXong {
  cauHoi: string;
  ketQua: TraCuuKetQua;
  /** Ngày hiệu lực của LƯỢT đó, không phải của ô chọn ngày lúc này. */
  asOfDate: string | null;
}

/** Một lượt hỏi–đáp trong dòng hội thoại. */
function Luot({
  cauHoi,
  asOfDate,
  traceId,
  children,
}: {
  cauHoi: string;
  asOfDate: string | null;
  traceId: string | null;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex justify-end">
        <p className="max-w-[70%] rounded-2xl rounded-br-sm bg-[var(--color-ink-900)] px-4 py-2.5 text-sm leading-relaxed text-white">
          {cauHoi}
        </p>
      </div>
      <div className="mt-4">{children}</div>

      {/* Chân lượt: phạm vi thời gian của các nhãn hiệu lực ở trên, rồi mã truy
          vết. Câu ngày KHÔNG phải trang trí — ĐO ĐƯỢC trên backend thật: hỏi
          cùng một câu tại 2019-06-01 thì 157/2018/NĐ-CP mang nhãn "Còn hiệu
          lực", còn hôm nay nó mang nhãn "Đã bị thay thế". Không nói ra ngày,
          nhãn xanh kia đọc thành một lời khẳng định về HÔM NAY. */}
      {(asOfDate !== null || traceId !== null) && (
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
          {asOfDate !== null && (
            <span>
              Nhãn hiệu lực tính tại ngày{" "}
              <strong className="font-semibold text-foreground">{ngayVietNam(asOfDate)}</strong>,
              không phải hôm nay.
            </span>
          )}
          {traceId !== null && <MaTruyVet traceId={traceId} />}
        </p>
      )}
    </div>
  );
}

function ManHoiKlaw() {
  const { q: cauHoiTrenUrl } = Route.useSearch();
  const traCuu = useTraCuu();
  const doiChieu = useDoiChieu();
  const haiCot = useHaiCot();

  const [nhap, datNhap] = useState("");
  /**
   * Ô chọn ngày hiệu lực — bảo đảm #15, `as_of_date` của `POST /tra-cuu`.
   * Chuỗi rỗng = chưa chọn = hỏi tại HÔM NAY (máy chủ tự lấy ngày hiện tại).
   * Không đặt sẵn ngày hôm nay vào ô: một ô đã điền sẵn đọc thành "người dùng
   * đã chọn", và sẽ được gửi đi như một lựa chọn có chủ đích.
   */
  const [ngayHieuLuc, datNgayHieuLuc] = useState("");
  const [luuTru, datLuuTru] = useState<LuotDaXong[]>([]);
  const [panelMo, datPanelMo] = useState(true);
  /** Trích dẫn đang mở, định danh theo `trace_id` của thẻ + chỉ số trong thẻ. */
  const [dangMo, datDangMo] = useState<{ trace: string; chiSo: number } | null>(null);

  const oHoi = useRef<HTMLTextAreaElement | null>(null);
  const cuoi = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    cuoi.current?.scrollIntoView({ block: "end" });
  }, [luuTru, traCuu.ketQua, traCuu.dangChay]);

  // Chạy đúng MỘT lần cho mỗi giá trị `?q=`. `hoi` ổn định giữa các lần dựng
  // lại (`useCallback`), nên hiệu ứng này không tự kích hoạt lại và không biến
  // một câu hỏi thành một chuỗi lượt gọi tính tiền.
  const { hoi } = traCuu;
  const daHoiTuUrl = useRef<string | null>(null);
  useEffect(() => {
    if (cauHoiTrenUrl === undefined || daHoiTuUrl.current === cauHoiTrenUrl) return;
    daHoiTuUrl.current = cauHoiTrenUrl;
    hoi(cauHoiTrenUrl);
  }, [cauHoiTrenUrl, hoi]);

  const tuGian = () => {
    const el = oHoi.current;
    if (el === null) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 6 * 26 + 20)}px`;
  };
  useEffect(tuGian, [nhap]);

  const gui = (tho?: string) => {
    const noiDung = (tho ?? nhap).trim();
    if (noiDung === "" || traCuu.dangChay) return;

    // Lượt đang hiện được xếp vào lịch sử TRƯỚC khi lượt mới chạy. Không dùng
    // `useEffect` theo dõi `ketQua`: hiệu ứng đó chạy lại mỗi lần React thấy
    // tham chiếu đổi và sẽ đẩy trùng một câu trả lời vào dòng hội thoại.
    const cauHoiCu = traCuu.cauHoi;
    const ketQuaCu = traCuu.ketQua;
    if (cauHoiCu !== null && ketQuaCu !== null) {
      datLuuTru((truoc) => [
        ...truoc,
        { cauHoi: cauHoiCu, ketQua: ketQuaCu, asOfDate: traCuu.asOfDate },
      ]);
    }

    datDangMo(null);
    doiChieu.dong();
    datNhap("");
    traCuu.hoi(noiDung, ngayHieuLuc);
  };

  const chonTrichDan = (ketQua: TraCuuKetQua, chiSo: number) => {
    const trichDan: Citation | undefined = ketQua.citations[chiSo];
    if (trichDan === undefined) return;
    // Bấm lại đúng chip đang mở thì ĐÓNG: chip mang `aria-expanded`, nên nó
    // phải mở/đóng được cả hai chiều.
    if (dangMo !== null && dangMo.trace === ketQua.trace_id && dangMo.chiSo === chiSo) {
      datDangMo(null);
      doiChieu.dong();
      return;
    }
    datDangMo({ trace: ketQua.trace_id, chiSo });
    doiChieu.mo({
      docId: trichDan.doc_id,
      // `khop_tai_id`, KHÔNG `provision_id`: hai id khác nhau ở 73,6% số Điều.
      khopTaiId: trichDan.khop_tai_id,
      duongDan: trichDan.duong_dan,
      quote: trichDan.quote,
    });
  };

  const chiSoDangMoCua = (ketQua: TraCuuKetQua) =>
    dangMo !== null && dangMo.trace === ketQua.trace_id ? dangMo.chiSo : null;

  const chuaHoiGiCa = luuTru.length === 0 && traCuu.cauHoi === null;
  const lichSu = [
    ...luuTru.map((luot) => luot.cauHoi),
    ...(traCuu.cauHoi === null ? [] : [traCuu.cauHoi]),
  ];

  return (
    <AppShell active="/dung-thu">
      <div className="flex min-h-0 flex-1">
        {/* Ở bố cục MỘT cột, khung nguyên văn khai `aria-modal` và phủ kín màn
            hình. `AppShell` gỡ điều hướng/header/thanh dưới khỏi vòng Tab, nhưng
            cột hội thoại là CON của <main> nên chỉ trang này gỡ được nó — nếu
            không, Tab vài lần là tiêu điểm đi vào một chip trích dẫn nằm khuất
            sau lớp phủ đặc, và Enter ở đó thay cả nội dung khung. */}
        <div inert={doiChieu.dang !== null && !haiCot} className="flex min-w-0 flex-1 flex-col">
          <div className="mx-auto flex w-full max-w-[860px] flex-1 flex-col px-4">
            {chuaHoiGiCa ? (
              <div className="soft-fade flex flex-1 flex-col items-center justify-center py-14">
                <span className="bg-gradient-ink flex size-14 items-center justify-center rounded-2xl text-primary-foreground shadow-soft">
                  <Scale className="size-7" aria-hidden />
                </span>
                <h2 className="font-display mt-5 max-w-xl text-center text-3xl font-semibold text-primary">
                  Bạn cần tra cứu điều gì hôm nay?
                </h2>
                <p className="mt-2 max-w-lg text-center text-sm text-muted-foreground">
                  Mỗi câu trả lời kèm điều, khoản, điểm và nhãn hiệu lực để bạn tự đối chiếu với văn
                  bản gốc. Hệ thống dừng lại khi không đủ căn cứ thay vì suy đoán.
                </p>
                <div className="mt-7 grid w-full gap-3 sm:grid-cols-2">
                  {GOI_Y.map((cau) => (
                    <button
                      key={cau}
                      type="button"
                      onClick={() => gui(cau)}
                      className="focus-brass cursor-pointer border-l-2 border-[var(--color-brass-500)] bg-[var(--color-paper-100)] px-4 py-3.5 text-left text-sm leading-relaxed text-foreground transition-colors hover:bg-[var(--color-paper-200)]"
                    >
                      {cau}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div aria-live="polite" aria-label="Hội thoại với KLAW" className="flex-1 py-8">
                <div className="flex flex-col gap-8">
                  {luuTru.map((luot) => (
                    <Luot
                      key={luot.ketQua.trace_id}
                      cauHoi={luot.cauHoi}
                      asOfDate={luot.asOfDate}
                      traceId={luot.ketQua.trace_id}
                    >
                      <TheKetQua
                        ketQua={luot.ketQua}
                        chiSoDangMo={chiSoDangMoCua(luot.ketQua)}
                        onChonTrichDan={(chiSo) => chonTrichDan(luot.ketQua, chiSo)}
                      />
                    </Luot>
                  ))}

                  {traCuu.cauHoi !== null && (
                    <Luot
                      cauHoi={traCuu.cauHoi}
                      asOfDate={traCuu.asOfDate}
                      traceId={traCuu.traceId}
                    >
                      {traCuu.dangChay && (
                        <TrangThaiCho
                          cacBuoc={traCuu.cacBuoc}
                          daPhat={traCuu.daPhat}
                          onHuy={traCuu.huy}
                        />
                      )}
                      {traCuu.loi !== null && <BaoLoi loi={traCuu.loi} onThuLai={traCuu.thuLai} />}
                      {traCuu.ketQua !== null && (
                        <TheKetQua
                          ketQua={traCuu.ketQua}
                          chiSoDangMo={chiSoDangMoCua(traCuu.ketQua)}
                          onChonTrichDan={(chiSo) => {
                            const kq = traCuu.ketQua;
                            if (kq !== null) chonTrichDan(kq, chiSo);
                          }}
                        />
                      )}
                    </Luot>
                  )}
                </div>
                <div ref={cuoi} />
              </div>
            )}
          </div>

          {/* Ô soạn câu hỏi */}
          <div className="sticky bottom-0 border-t border-border bg-background/95 backdrop-blur">
            <div className="mx-auto w-full max-w-[860px] px-4 py-3">
              <div className="flex items-end gap-2 rounded-xl border border-border bg-card p-2 shadow-soft">
                <button
                  type="button"
                  title="Đính kèm văn bản — chưa có trong hệ thống"
                  aria-label="Đính kèm văn bản (chưa có trong hệ thống)"
                  disabled
                  className="mb-0.5 rounded-lg p-2 text-muted-foreground disabled:opacity-40"
                >
                  <Paperclip className="size-4" aria-hidden />
                </button>
                <textarea
                  ref={oHoi}
                  rows={1}
                  value={nhap}
                  disabled={traCuu.dangChay}
                  onChange={(su) => datNhap(su.target.value)}
                  onKeyDown={(su) => {
                    if (su.key === "Enter" && !su.shiftKey) {
                      su.preventDefault();
                      gui();
                    }
                  }}
                  aria-label="Câu hỏi pháp lý"
                  placeholder="Nhập câu hỏi pháp lý — ví dụ: thời gian thử việc tối đa là bao lâu?"
                  className="max-h-[176px] flex-1 resize-none bg-transparent py-2 text-sm leading-[26px] outline-none placeholder:text-muted-foreground disabled:opacity-60"
                />
                <button
                  type="button"
                  onClick={() => gui()}
                  disabled={nhap.trim() === "" || traCuu.dangChay}
                  aria-label="Gửi câu hỏi"
                  className="focus-brass bg-gradient-ink mb-0.5 cursor-pointer rounded-lg p-2 text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-40"
                >
                  <Send className="size-4" aria-hidden />
                </button>
              </div>
              {/* Ô chọn ngày hiệu lực — `<input type="date">` của trình duyệt,
                  không thư viện lịch: nó đã có bàn phím, trình đọc màn hình,
                  định dạng theo locale và lịch gốc của hệ điều hành. */}
              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
                <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                  <CalendarClock
                    className="size-3.5 shrink-0 text-[var(--color-brass-600)]"
                    aria-hidden
                  />
                  <label htmlFor="ngay-hieu-luc">Tính hiệu lực tại ngày</label>
                  <input
                    id="ngay-hieu-luc"
                    type="date"
                    value={ngayHieuLuc}
                    disabled={traCuu.dangChay}
                    onChange={(su) => datNgayHieuLuc(su.target.value)}
                    aria-describedby="ngay-hieu-luc-mo-ta"
                    className="focus-brass rounded-md border border-border bg-card px-1.5 py-0.5 font-jetbrains text-[12px] text-foreground disabled:opacity-60"
                  />
                  {ngayHieuLuc === "" ? (
                    <span id="ngay-hieu-luc-mo-ta">— để trống là hôm nay</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => datNgayHieuLuc("")}
                      disabled={traCuu.dangChay}
                      aria-label="Bỏ ngày đã chọn, quay về hôm nay"
                      className="focus-brass inline-flex cursor-pointer items-center gap-0.5 rounded-md px-1 py-0.5 text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10 disabled:cursor-default disabled:opacity-60"
                    >
                      <X className="size-3" aria-hidden />
                      <span id="ngay-hieu-luc-mo-ta">về hôm nay</span>
                    </button>
                  )}
                </div>
                <p className="m-0 text-[12px] text-muted-foreground">
                  Kho văn bản là bản GỐC, không phải bản hợp nhất. Luôn đối chiếu nguyên văn trước
                  khi sử dụng.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Khung nguyên văn. Ở bố cục hai cột nó chiếm một cột thật; dưới ngưỡng
            đó nó tự phủ toàn màn hình, nên thẻ bọc phải KHÔNG có kích thước —
            `hidden` sẽ giấu luôn cả khung ở chế độ phủ màn hình. */}
        {doiChieu.dang !== null && (
          <div
            className={cn(
              "shrink-0",
              haiCot && "w-[420px] border-l border-border bg-[var(--color-paper-50)] p-3",
            )}
          >
            <KhungDoiChieu
              khopTaiId={doiChieu.dang.khopTaiId}
              {...(doiChieu.dang.duongDan === undefined
                ? {}
                : { duongDan: doiChieu.dang.duongDan })}
              quote={doiChieu.dang.quote ?? null}
              trangThai={doiChieu.trangThai}
              vanBan={doiChieu.vanBan}
              loi={doiChieu.loi}
              onThuLai={doiChieu.thuLai}
              onDong={() => {
                datDangMo(null);
                doiChieu.dong();
              }}
            />
          </div>
        )}

        {/* Lịch sử phiên. Nhường chỗ cho khung nguyên văn khi khung mở — hai cột
            phụ cạnh nhau đẩy mặt đọc xuống dưới bề rộng đọc được. */}
        {doiChieu.dang === null && (
          <aside
            aria-label="Lịch sử phiên"
            className={cn(
              "hidden shrink-0 border-l border-border bg-[var(--color-paper-50)] transition-[width] duration-150 xl:block",
              panelMo ? "w-[300px]" : "w-[52px]",
            )}
          >
            <div className="sticky top-[49px] p-3">
              <button
                type="button"
                onClick={() => datPanelMo((mo) => !mo)}
                aria-label={panelMo ? "Thu gọn lịch sử phiên" : "Mở lịch sử phiên"}
                aria-expanded={panelMo}
                className="focus-brass mb-3 cursor-pointer rounded-md p-1.5 text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10"
              >
                <ChevronRight
                  className={cn(
                    "size-4 transition-transform duration-150",
                    panelMo && "rotate-180",
                  )}
                  aria-hidden
                />
              </button>

              {panelMo && (
                <div className="soft-fade">
                  <p className="border-b border-border pb-2 text-[12px] font-semibold text-primary">
                    Lịch sử phiên
                  </p>
                  <div className="mt-3 space-y-2">
                    {lichSu.length === 0 ? (
                      <p className="text-[12px] text-muted-foreground">
                        Chưa có câu hỏi nào trong phiên này.
                      </p>
                    ) : (
                      lichSu.map((cau, i) => (
                        <div
                          key={`${i}-${cau}`}
                          className="rounded-lg border border-border bg-card p-2.5 text-[12px] text-muted-foreground"
                        >
                          <span className="font-jetbrains text-[var(--color-brass-600)]">
                            {String(i + 1).padStart(2, "0")}
                          </span>{" "}
                          {cau}
                        </div>
                      ))
                    )}
                  </div>
                  {/* `trace_id` của máy chủ. Không phải trang trí: đây là khoá
                      duy nhất đối chiếu được một câu trả lời trên màn hình với
                      dòng tương ứng trong bảng `traces`. */}
                  {traCuu.traceId !== null && (
                    <p className="mt-3 font-jetbrains text-[11px] break-all text-muted-foreground">
                      trace {traCuu.traceId}
                    </p>
                  )}
                </div>
              )}
            </div>
          </aside>
        )}
      </div>
    </AppShell>
  );
}

export const Route = createFileRoute("/dung-thu")({
  // `?q=` là câu hỏi người dùng vừa gõ ở một cửa vào khác (`/chat`, hoặc một
  // liên kết được chia sẻ). Nó chạy NGAY, vì gõ câu hỏi rồi bấm gửi đã là sự
  // đồng ý — bắt bấm gửi lần thứ hai chỉ để giữ một quy tắc hình thức.
  validateSearch: (tho: Record<string, unknown>): { q?: string } => {
    const q = tho["q"];
    return typeof q === "string" && q.trim() !== "" ? { q } : {};
  },
  component: ManHoiKlaw,
  head: () => {
    const title = "Hỏi KLAW — tra cứu pháp luật lao động có trích dẫn kiểm chứng được";
    const description =
      "Đặt câu hỏi pháp lý và nhận câu trả lời kèm điều, khoản, điểm, nhãn hiệu lực và nguyên văn để tự đối chiếu. Hệ thống dừng lại khi không đủ căn cứ thay vì suy đoán.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
});
