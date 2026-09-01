import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronRight, Paperclip, Scale, Send } from "lucide-react";
import { AppShell } from "@/components/app/AppShell";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { MaTruyVet } from "@/components/klaw/MaTruyVet";
import { KhungDoiChieu, useHaiCot } from "@/components/klaw/KhungDoiChieu";
import { TheKetQua } from "@/components/klaw/TheKetQua";
import { TrangThaiCho } from "@/components/klaw/TrangThaiCho";
import { useDoiChieu } from "@/hooks/use-doi-chieu";
import { useTraCuu } from "@/hooks/use-tra-cuu";
import type { Citation, TraCuuKetQua } from "@/lib/klaw";
import { cn } from "@/lib/utils";

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
}

/**
 * Một lượt hỏi–đáp trong dòng hội thoại.
 *
 * `trace_id` đi vào `data-trace` chứ KHÔNG hiện thành chữ. Người dùng bình
 * thường không cần nó, và một chuỗi UUID dưới mỗi câu trả lời là tiếng ồn.
 * Nhưng nó vẫn nằm trong DOM, nên khi có ai báo một câu trả lời sai thì vẫn
 * đối chiếu được với bảng `traces` — không mất gì, không chiếm một pixel nào.
 */
function Luot({
  cauHoi,
  traceId,
  children,
}: {
  cauHoi: string;
  traceId: string | null;
  children?: React.ReactNode;
}) {
  return (
    <div {...(traceId === null ? {} : { "data-trace": traceId })}>
      <div className="flex justify-end">
        <p className="max-w-[70%] rounded-2xl rounded-br-sm bg-[var(--color-ink-900)] px-4 py-2.5 text-sm leading-relaxed text-white">
          {cauHoi}
        </p>
      </div>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function ManHoiKlaw() {
  const { q: cauHoiTrenUrl } = Route.useSearch();
  const traCuu = useTraCuu();
  const doiChieu = useDoiChieu();
  const haiCot = useHaiCot();

  const [nhap, datNhap] = useState("");
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
      datLuuTru((truoc) => [...truoc, { cauHoi: cauHoiCu, ketQua: ketQuaCu }]);
    }

    datDangMo(null);
    doiChieu.dong();
    datNhap("");
    traCuu.hoi(noiDung);
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
                    <Luot cauHoi={traCuu.cauHoi} traceId={traCuu.traceId}>
                      {traCuu.dangChay && (
                        <TrangThaiCho
                          cacBuoc={traCuu.cacBuoc}
                          daPhat={traCuu.daPhat}
                          onHuy={traCuu.huy}
                        />
                      )}
                      {traCuu.loi !== null && (
                        <>
                          <BaoLoi loi={traCuu.loi} onThuLai={traCuu.thuLai} />
                          {/* Ngoại lệ DUY NHẤT còn hiện mã truy vết. Đây đúng
                              là lúc người dùng đi báo lỗi, và một mã chép được
                              là thứ biến "hôm qua nó hỏng" thành một dòng tra
                              được trong bảng `traces`. */}
                          {traCuu.traceId !== null && (
                            <p className="mt-2 mb-0 text-[12px] text-muted-foreground">
                              Kèm mã này khi báo lỗi: <MaTruyVet traceId={traCuu.traceId} />
                            </p>
                          )}
                        </>
                      )}
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
              <p className="mt-1.5 text-[12px] text-muted-foreground">
                Kho văn bản là bản GỐC, không phải bản hợp nhất. Luôn đối chiếu nguyên văn trước khi
                sử dụng.
              </p>
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
