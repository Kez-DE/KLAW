import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { FlaskConical } from "lucide-react";
import { AppShell } from "@/components/app/AppShell";
import { BadgeHieuLuc } from "@/components/klaw/BadgeHieuLuc";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { KhungDoiChieu, useHaiCot } from "@/components/klaw/KhungDoiChieu";
import { TheKetQua } from "@/components/klaw/TheKetQua";
import { TrangThaiCho } from "@/components/klaw/TrangThaiCho";
import { useGoiApi } from "@/hooks/use-goi-api";
import type { ApiErrorKind, TraCuuKetQua, VanBanQuanhDieu } from "@/lib/klaw";
import { cn } from "@/lib/utils";

/**
 * Trang xem thử các thành phần của pha 5. KHÔNG nối máy chủ.
 *
 * MỌI DỮ LIỆU TRÊN TRANG NÀY LÀ GIẢ, và giả một cách cố ý không thể nhầm được:
 * số hiệu là `00/0000/QH00` — một số hiệu không thể tồn tại — và nguyên văn là
 * câu mô tả bố cục, không phải câu luật. Bản Lovable đã từng chở bốn câu trả
 * lời đóng hộp kèm trích dẫn dựng sẵn, một trong số đó gắn nhãn "Còn hiệu lực"
 * cho một nghị định đã hết hiệu lực toàn bộ. Trang này tồn tại để xem BỐ CỤC
 * và MÀU, nên nó phải không thể bị đọc nhầm thành bằng chứng pháp lý.
 */

export const Route = createFileRoute("/thanh-phan")({
  head: () => ({
    meta: [
      { title: "Thành phần giao diện — KLAW" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: TrangThanhPhan,
});

const SO_HIEU_GIA = "00/0000/QH00";

const SAU_NHAN = [
  "con_hieu_luc",
  "bi_thay_the",
  "bi_sua_doi",
  "het_hieu_luc",
  "mot_phan_khong_xac_dinh",
  "can_doi_chieu_tay",
] as const;

const TY_LE: Record<string, string> = {
  con_hieu_luc: "status-active · 7,64:1 trên --card",
  bi_thay_the: "status-expired · 10,32:1",
  bi_sua_doi: "status-partial · 13,97:1",
  het_hieu_luc: "status-expired · 10,32:1",
  mot_phan_khong_xac_dinh: "status-partial · 13,97:1",
  can_doi_chieu_tay: "status-neutral · 5,49:1",
};

const TAM_LOI: ApiErrorKind[] = [
  "network",
  "timeout",
  "aborted",
  "not_implemented",
  "not_found",
  "invalid_request",
  "server_error",
  "invalid_response",
];

const THONG_DIEP_LOI: Record<ApiErrorKind, string> = {
  network: "Không gọi được máy chủ KLAW.",
  timeout: "Lượt tra cứu quá hạn chờ.",
  aborted: "Lượt tra cứu đã dừng.",
  not_implemented: "Loại văn bản này chưa được hỗ trợ.",
  not_found: "Không tìm thấy văn bản này.",
  invalid_request: "Yêu cầu không hợp lệ.",
  server_error: "Máy chủ KLAW gặp sự cố.",
  invalid_response: "Không đọc được phản hồi của máy chủ.",
};

const MA_HTTP: Partial<Record<ApiErrorKind, number>> = {
  not_implemented: 501,
  not_found: 404,
  invalid_request: 422,
  server_error: 500,
  invalid_response: 200,
};

const BON_KET_QUA: { nhan: string; ketQua: TraCuuKetQua }[] = [
  {
    nhan: "answer — có căn cứ, có trích dẫn kiểm chứng được",
    ketQua: {
      result_type: "answer",
      answer:
        "Đoạn câu trả lời mẫu để xem bố cục và khoảng thở giữa các đoạn. Nội dung này không phải nội dung pháp luật.\nĐoạn thứ hai, để thấy khoảng cách giữa hai đoạn trong mặt đọc.",
      citations: [
        {
          provision_id: 1,
          khop_tai_id: 12,
          doc_id: "mau-1",
          duong_dan: `${SO_HIEU_GIA} > Điều 1 > Khoản 2`,
          bo_luat: "Văn bản mẫu",
          so_ky_hieu: SO_HIEU_GIA,
          quote: "câu trích mẫu nằm trong nguyên văn mẫu",
          hieu_luc: "con_hieu_luc",
          tin_cay: null,
        },
        {
          provision_id: 3,
          khop_tai_id: 31,
          doc_id: "mau-2",
          duong_dan: `${SO_HIEU_GIA} > Điều 3`,
          bo_luat: "Văn bản mẫu",
          so_ky_hieu: SO_HIEU_GIA,
          quote: "một câu trích mẫu khác, ở một điều khác",
          hieu_luc: "bi_thay_the",
          tin_cay: null,
        },
      ],
      nguon: [],
      warnings: [`${SO_HIEU_GIA} đã bị thay thế bởi một văn bản mẫu khác kể từ 01/01/2000.`],
      coverage_note: null,
      trace_id: "mau-answer",
    },
  },
  {
    nhan: "partial_coverage — chỉ có văn bản, KHÔNG diễn giải (63% kho rơi vào đây)",
    ketQua: {
      result_type: "partial_coverage",
      answer: null,
      citations: [],
      nguon: [
        { doc_id: "mau-1", so_ky_hieu: SO_HIEU_GIA, bo_luat: "Văn bản mẫu" },
        { doc_id: "mau-2", so_ky_hieu: SO_HIEU_GIA, bo_luat: "Văn bản mẫu khác" },
      ],
      warnings: [],
      coverage_note:
        "Kho có văn bản chi phối câu hỏi này nhưng chưa có toàn văn tới cấp điều khoản, nên hệ thống dừng ở việc nêu đích danh văn bản.",
      trace_id: "mau-partial",
    },
  },
  {
    nhan: "abstain — hành vi ĐÚNG, trung tính, không icon cảnh báo",
    ketQua: {
      result_type: "abstain",
      answer: null,
      citations: [],
      nguon: [],
      warnings: [],
      coverage_note: null,
      trace_id: "mau-abstain",
    },
  },
  {
    nhan: "out_of_scope — ngoài phạm vi, cũng trung tính",
    ketQua: {
      result_type: "out_of_scope",
      answer: null,
      citations: [],
      nguon: [],
      warnings: [],
      coverage_note: null,
      trace_id: "mau-out",
    },
  },
];

/**
 * Nguyên văn mẫu. `la_tam` bật cho Điều 2 VÀ hai Khoản con của nó — đây chính
 * là điểm phải nhìn thấy: vùng rọi sáng là một KHỐI, không phải một dòng.
 */
const VAN_BAN_MAU: VanBanQuanhDieu = {
  doc_id: "mau-1",
  so_ky_hieu: SO_HIEU_GIA,
  bo_luat: "Văn bản mẫu",
  provisions: [
    {
      id: 10,
      cap: "dieu",
      so_hieu_cap: "1",
      duong_dan: `${SO_HIEU_GIA} > Điều 1`,
      tieu_de: "Điều lân cận phía trước",
      noi_dung: "Đoạn nguyên văn mẫu của một điều lân cận, để thấy nó mờ đi so với vùng đang xem.",
      la_tam: false,
    },
    {
      id: 11,
      cap: "dieu",
      so_hieu_cap: "2",
      duong_dan: `${SO_HIEU_GIA} > Điều 2`,
      tieu_de: "Điều đang được kiểm chứng",
      noi_dung: "Điều này chỉ có tiêu đề; nội dung thật nằm ở các Khoản con bên dưới.",
      la_tam: true,
    },
    {
      id: 12,
      cap: "khoan",
      so_hieu_cap: "2",
      duong_dan: `${SO_HIEU_GIA} > Điều 2 > Khoản 2`,
      tieu_de: "",
      noi_dung:
        "Đây là dòng mang câu trích: câu trích mẫu nằm trong nguyên văn mẫu, và phần được đánh dấu phải trùng khít với câu trích trên chip.",
      la_tam: true,
    },
    {
      id: 13,
      cap: "diem",
      so_hieu_cap: "a",
      duong_dan: `${SO_HIEU_GIA} > Điều 2 > Khoản 2 > Điểm a`,
      tieu_de: "",
      noi_dung: "Điểm con vẫn nằm trong vùng rọi sáng vì cùng thuộc Điều đang xem.",
      la_tam: true,
    },
    {
      id: 14,
      cap: "dieu",
      so_hieu_cap: "3",
      duong_dan: `${SO_HIEU_GIA} > Điều 3`,
      tieu_de: "Điều lân cận phía sau",
      noi_dung: "Một điều lân cận nữa, cũng nằm ngoài vùng rọi sáng.",
      la_tam: false,
    },
  ],
};

function Muc({
  so,
  tieuDe,
  chuThich,
  children,
}: {
  so: string;
  tieuDe: string;
  chuThich?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-border pt-8">
      <h2 className="font-display text-xl font-semibold text-primary">
        <span className="font-jetbrains mr-2 text-[13px] text-muted-foreground">{so}</span>
        {tieuDe}
      </h2>
      {chuThich !== undefined && (
        <p className="mt-1 max-w-[65ch] text-[14px] leading-6 text-muted-foreground">{chuThich}</p>
      )}
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** Gọi giả có tôn trọng `AbortSignal` — để nút huỷ được thử là huỷ THẬT. */
function goiGia(signal: AbortSignal, msTre: number): Promise<{ ok: true; data: string }> {
  return new Promise((giaiQuyet, tuChoi) => {
    const dong = setTimeout(() => giaiQuyet({ ok: true, data: "xong" }), msTre);
    signal.addEventListener("abort", () => {
      clearTimeout(dong);
      tuChoi(signal.reason as Error);
    });
  });
}

function TrangThanhPhan() {
  const [chiSoTrichDan, datChiSoTrichDan] = useState<number | null>(null);
  const haiCot = useHaiCot();
  const cho = useGoiApi<string>();

  const trichDanDangMo =
    chiSoTrichDan === null ? null : (BON_KET_QUA[0]?.ketQua.citations[chiSoTrichDan] ?? null);

  const batDauCho = () => {
    void cho.chay(async (signal) => {
      try {
        return await goiGia(signal, 45_000);
      } catch {
        // Đúng nhánh `aborted`: `useGoiApi` nuốt nó, không nhá lỗi vào mặt
        // người vừa bấm huỷ.
        return { ok: false as const, error: { kind: "aborted" as const, message: "Đã huỷ." } };
      }
    });
  };

  return (
    <AppShell>
      {/*
        Ở bố cục MỘT CỘT, khung đối chiếu phủ kín màn hình và khai `aria-modal`.
        `useKhungModalDangMo` trong vỏ trang đã bọc `inert` quanh điều hướng và
        thanh dưới, nhưng cột nội dung này là con của <main> nên nằm ngoài tầm
        với của vỏ — trang gọi phải tự gỡ nó khỏi vòng Tab. Nếu không, Tab vài
        lần là tiêu điểm rơi xuống một nút đang nằm khuất sau lớp phủ đặc.
        Khung đối chiếu nằm NGOÀI div này nên không tự bọc `inert` lên chính nó.
      */}
      <div
        inert={trichDanDangMo !== null && !haiCot}
        className="mx-auto w-full max-w-3xl px-4 py-8"
      >
        <header>
          <h1 className="font-display text-2xl font-bold text-primary">Thành phần giao diện</h1>
          <div
            className="mt-3 flex items-start gap-2 rounded-xl border border-border bg-[var(--color-paper-100)] p-3"
            role="note"
          >
            <FlaskConical className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            <p className="m-0 text-[14px] leading-6 text-foreground">
              Trang xem thử, <strong className="font-semibold">chưa nối máy chủ</strong>. Mọi số
              hiệu, câu trích và nguyên văn dưới đây là dữ liệu giả dựng để xem bố cục — số hiệu{" "}
              <span className="font-jetbrains">{SO_HIEU_GIA}</span> cố ý không thể tồn tại. Không có
              dòng nào ở đây là nội dung pháp luật.
            </p>
          </div>
        </header>

        <div className="mt-8 flex flex-col gap-8">
          <Muc
            so="01"
            tieuDe="Sáu nhãn hiệu lực"
            chuThich="Bốn màu phủ sáu nhãn. Chữ là thứ phân biệt thật; màu chỉ nhắc lại. Xem ở ảnh xám: bốn màu tách nhau tối thiểu 1,35:1."
          >
            <ul className="flex list-none flex-col gap-4 p-0">
              {SAU_NHAN.map((nhan) => (
                <li key={nhan} className="rounded-xl border border-border bg-card p-3">
                  <p className="font-jetbrains m-0 text-[12px] text-muted-foreground">
                    {nhan} · {TY_LE[nhan]}
                  </p>
                  <div className="mt-2">
                    <BadgeHieuLuc
                      hieuLuc={nhan}
                      {...(nhan === "bi_thay_the"
                        ? { ghiChu: `Bị thay thế bởi ${SO_HIEU_GIA} kể từ 01/01/2000.` }
                        : {})}
                    />
                  </div>
                </li>
              ))}
              <li className="rounded-xl border border-dashed border-border bg-card p-3">
                <p className="font-jetbrains m-0 text-[12px] text-muted-foreground">
                  nhan_thu_bay_backend_moi_them · rơi vào nhánh default
                </p>
                <div className="mt-2">
                  <BadgeHieuLuc hieuLuc="nhan_thu_bay_backend_moi_them" />
                </div>
              </li>
            </ul>
          </Muc>

          <Muc
            so="02"
            tieuDe="Bốn result_type"
            chuThich="abstain và out_of_scope dùng cùng một khay trung tính: hai nhánh 'hệ thống không trả lời' phải đọc như cùng một loại sự việc, không phải hai mức báo động."
          >
            <div className="flex flex-col gap-6">
              {BON_KET_QUA.map(({ nhan, ketQua }, i) => (
                <div key={ketQua.trace_id} className="rounded-xl border border-border bg-card p-4">
                  <p className="font-jetbrains m-0 mb-3 text-[12px] text-muted-foreground">
                    {nhan}
                  </p>
                  <TheKetQua
                    ketQua={ketQua}
                    chiSoDangMo={i === 0 ? chiSoTrichDan : null}
                    {...(i === 0 ? { onChonTrichDan: datChiSoTrichDan } : {})}
                  />
                </div>
              ))}
            </div>
          </Muc>

          <Muc
            so="03"
            tieuDe="Trạng thái chờ — bốn bước, tiến trình xác định, huỷ thật"
            chuThich="Nút huỷ gọi abort() trên một AbortController thật, không chỉ ẩn khay đi. Bấm 'Gửi thử' rồi bấm 'Huỷ lượt tra cứu' — tiêu điểm phải quay về ô nhập, không rơi về đầu trang."
          >
            {cho.dangChay ? (
              <TrangThaiCho onHuy={cho.huy} />
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <label className="sr-only" htmlFor="o-hoi-mau">
                  Ô hỏi mẫu
                </label>
                <input
                  id="o-hoi-mau"
                  type="text"
                  placeholder="Ô hỏi mẫu — tiêu điểm quay về đây sau khi huỷ"
                  className="focus-brass min-h-11 flex-1 rounded-lg border border-input bg-card px-3 text-[15px]"
                />
                <button
                  type="button"
                  onClick={batDauCho}
                  className="focus-brass min-h-11 cursor-pointer rounded-lg bg-primary px-4 text-[15px] font-medium text-primary-foreground"
                >
                  Gửi thử
                </button>
              </div>
            )}
          </Muc>

          <Muc
            so="04"
            tieuDe="Tám nhánh lỗi"
            chuThich="Không nhánh nào mượn màu hiệu lực. invalid_response là nhánh 2xx-nhưng-sai-hình-dạng: không có nó thì giao diện hoặc sập, hoặc render một câu trả lời rỗng như thể đó là câu trả lời thật."
          >
            <div className="flex flex-col gap-4">
              {TAM_LOI.map((kind) => (
                <div key={kind}>
                  <p className="font-jetbrains m-0 text-[12px] text-muted-foreground">{kind}</p>
                  <BaoLoi
                    loi={{
                      kind,
                      message: THONG_DIEP_LOI[kind],
                      ...(MA_HTTP[kind] !== undefined ? { status: MA_HTTP[kind] } : {}),
                    }}
                    onThuLai={() => undefined}
                  />
                </div>
              ))}
            </div>
          </Muc>

          <Muc
            so="05"
            tieuDe="Khung đối chiếu — mở bằng khop_tai_id, tô cả vùng la_tam"
            chuThich="Bấm một trích dẫn ở mục 02 để mở khung. Ở dưới 68rem khung phủ toàn màn hình và khai aria-modal, nên điều hướng bị bọc inert — thử Tab để kiểm."
          >
            <p className="m-0 text-[14px] leading-6 text-muted-foreground">
              Bố cục hiện tại: {haiCot ? "hai cột (khung dính bên phải)" : "một cột (khung phủ)"}.
              Khung đang {chiSoTrichDan === null ? "đóng" : "mở"}.
            </p>
          </Muc>
        </div>
      </div>

      {trichDanDangMo !== null && (
        <div className={cn(haiCot && "fixed top-16 right-6 z-40 w-[30rem]")}>
          <KhungDoiChieu
            khopTaiId={trichDanDangMo.khop_tai_id}
            duongDan={trichDanDangMo.duong_dan}
            quote={trichDanDangMo.quote}
            trangThai="xong"
            vanBan={VAN_BAN_MAU}
            onDong={() => datChiSoTrichDan(null)}
          />
        </div>
      )}
    </AppShell>
  );
}
