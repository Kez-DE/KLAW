import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowRight, Copy, Search, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app/AppShell";
import { BadgeHieuLuc } from "@/components/klaw/BadgeHieuLuc";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { Chip } from "@/components/legal/VanBanUI";
import { goi, thamSo } from "@/lib/api";
import {
  laBoLoc,
  laTimKiem,
  type ApiError,
  type BoLoc,
  type DongTimKiem,
  type GiaTriLoc,
  type TimKiem,
} from "@/lib/klaw";
import { cn } from "@/lib/utils";

/**
 * Tìm kiếm điều khoản — `GET /tim-kiem` + `GET /bo-loc`.
 *
 * ## Đây là tìm kiếm TỪ KHOÁ, và trang nói thẳng như vậy
 *
 * `/tim-kiem` chỉ dùng BM25. Không phải vì thiếu embedding — `chunks.embedding`
 * có sẵn — mà vì dùng nó buộc phải embed câu truy vấn ở MỖI lượt gõ: ô tìm kiếm
 * biến thành một khoản chi cho nhà cung cấp, độ trễ 20ms thành ~400ms, và một
 * lỗi 429 của họ làm chết ô tìm kiếm. `eval-baseline-moi.md` đo được nhánh từ
 * vựng xếp hạng kém hẳn nhánh dense trên bộ golden.
 *
 * Hệ quả bắt buộc với giao diện: **không nhãn nào ở đây được gọi là "hỏi AI"**.
 * Câu hỏi tự nhiên đi qua `/dung-thu`, và trang có một lối rẽ rõ ràng sang đó.
 *
 * ## `/bo-loc` là nguồn DUY NHẤT của giá trị lọc
 *
 * Không viết cứng một giá trị nào — kể cả 8 loại văn bản đang có thật hôm nay:
 * lần mở rộng kho tiếp theo sẽ đổi danh sách đó. Một chip trỏ vào giá trị bịa
 * mà trả rỗng thì người dùng đọc thành "KLAW không có văn bản nào về việc này",
 * một khẳng định sai phát ra trong im lặng. Máy chủ chặn trước bằng 422 kèm
 * NGUYÊN danh sách thật, và trang hiện đúng câu đó thay vì nuốt nó thành
 * "không có kết quả".
 */

const MOI_TRANG = 20;

const NHAN_SAP_XEP: Record<string, string> = {
  lien_quan: "Liên quan nhất",
  moi_nhat: "Mới nhất",
  con_hieu_luc_truoc: "Còn hiệu lực trước",
};

interface BoLocUrl {
  q?: string;
  loai?: string[];
  co_quan?: string[];
  tu_nam?: number;
  den_nam?: number;
  sap_xep?: string;
  trang?: number;
}

/**
 * Bản vá bộ lọc. `exactOptionalPropertyTypes` cấm gán `undefined` tường minh
 * vào một trường tuỳ chọn, nhưng ở đây `undefined` là một MỆNH LỆNH — "xoá
 * khoá này khỏi URL" — chứ không phải "không nói gì". Hai ý nghĩa khác nhau nên
 * dùng hai kiểu khác nhau.
 */
type SuaBoLoc = { [K in keyof BoLocUrl]?: BoLocUrl[K] | undefined };

/** URL là chữ của người dùng: một tham số lặp có thể về dạng chuỗi đơn. */
function mangChuoi(tho: unknown): string[] | undefined {
  if (typeof tho === "string" && tho !== "") return [tho];
  if (!Array.isArray(tho)) return undefined;
  const sach = tho.filter((x): x is string => typeof x === "string" && x !== "");
  return sach.length === 0 ? undefined : sach;
}

function soNguyen(tho: unknown): number | undefined {
  const so = typeof tho === "string" ? Number(tho) : typeof tho === "number" ? tho : NaN;
  return Number.isInteger(so) ? so : undefined;
}

export const Route = createFileRoute("/tra-cuu/")({
  validateSearch: (tho: Record<string, unknown>): BoLocUrl => {
    const q = tho["q"];
    const sapXep = tho["sap_xep"];
    const loai = mangChuoi(tho["loai"]);
    const coQuan = mangChuoi(tho["co_quan"]);
    const tuNam = soNguyen(tho["tu_nam"]);
    const denNam = soNguyen(tho["den_nam"]);
    const trang = soNguyen(tho["trang"]);
    return {
      ...(typeof q === "string" && q !== "" ? { q } : {}),
      ...(loai === undefined ? {} : { loai }),
      ...(coQuan === undefined ? {} : { co_quan: coQuan }),
      ...(tuNam === undefined ? {} : { tu_nam: tuNam }),
      ...(denNam === undefined ? {} : { den_nam: denNam }),
      ...(typeof sapXep === "string" && sapXep !== "" ? { sap_xep: sapXep } : {}),
      ...(trang === undefined ? {} : { trang }),
    };
  },
  head: () => ({
    meta: [
      { title: "Tìm kiếm điều khoản trong văn bản pháp luật — KLAW" },
      {
        name: "description",
        content:
          "Tìm theo từ khoá tới từng điều, khoản, điểm trong kho văn bản pháp luật lao động của KLAW, kèm nhãn hiệu lực do hệ thống tự đánh giá.",
      },
      { property: "og:title", content: "Tìm kiếm điều khoản — KLAW" },
      {
        property: "og:description",
        content:
          "Tìm chính xác điều, khoản, điểm trong kho văn bản pháp luật Việt Nam kèm nhãn hiệu lực kiểm chứng được.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ManTimKiem,
});

/* ──────────────────────────────── Bộ lọc ───────────────────────────────── */

function NhomLoc({
  tieuDe,
  giaTri,
  daChon,
  onBat,
}: {
  tieuDe: string;
  giaTri: GiaTriLoc[];
  daChon: string[];
  onBat: (gia: string) => void;
}) {
  if (giaTri.length === 0) return null;
  return (
    <div className="border-b border-border py-3">
      <p className="mb-2 text-[12px] font-semibold tracking-wide text-primary uppercase">
        {tieuDe}
      </p>
      <div className="flex flex-col gap-1.5">
        {giaTri.map((mot) => (
          <label
            key={mot.gia_tri}
            className="flex cursor-pointer items-start gap-2 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
          >
            <input
              type="checkbox"
              checked={daChon.includes(mot.gia_tri)}
              onChange={() => onBat(mot.gia_tri)}
              className="mt-0.5 size-3.5 accent-[var(--color-brass-500)]"
            />
            <span className="flex-1">{mot.gia_tri}</span>
            {/* Số đếm THẬT từ CSDL, không phải ước lượng. */}
            <span className="font-jetbrains text-[11px] text-muted-foreground">
              {mot.so_van_ban}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

function ThanBoLoc({
  boLoc,
  hienTai,
  onDoi,
}: {
  boLoc: BoLoc | null;
  hienTai: BoLocUrl;
  onDoi: (moi: SuaBoLoc) => void;
}) {
  if (boLoc === null) {
    return (
      <p className="py-3 text-[12px] text-muted-foreground">
        Đang lấy danh sách giá trị lọc từ máy chủ…
      </p>
    );
  }

  const bat = (khoa: "loai" | "co_quan", gia: string) => {
    const dang = hienTai[khoa] ?? [];
    const moi = dang.includes(gia) ? dang.filter((x) => x !== gia) : [...dang, gia];
    onDoi({ [khoa]: moi.length === 0 ? undefined : moi, trang: undefined });
  };

  return (
    <div>
      <NhomLoc
        tieuDe="Loại văn bản"
        giaTri={boLoc.loai_van_ban}
        daChon={hienTai.loai ?? []}
        onBat={(gia) => bat("loai", gia)}
      />
      <NhomLoc
        tieuDe="Cơ quan ban hành"
        giaTri={boLoc.co_quan_ban_hanh}
        daChon={hienTai.co_quan ?? []}
        onBat={(gia) => bat("co_quan", gia)}
      />
      {/* Tổng theo cơ quan KHÔNG bằng tổng kho, và con số đó phải nói ra trước
          khi ai đó đọc danh sách trên như một bức tranh đầy đủ. */}
      {boLoc.co_quan_khong_ro > 0 && (
        <p className="border-b border-border py-3 text-[12px] leading-5 text-muted-foreground">
          {boLoc.co_quan_khong_ro}/{boLoc.tong_van_ban} văn bản không khai cơ quan ban hành trong
          CSDL quốc gia. Lọc theo cơ quan sẽ bỏ qua toàn bộ số đó.
        </p>
      )}

      {/* KHÔNG có nhóm "Tình trạng hiệu lực": `/bo-loc` cố ý không trả khoá đó.
          Lọc theo tuyên bố của CSDL quốc gia là đúng lỗi hệ thống này tồn tại
          để chữa; xếp theo hiệu lực đi qua `sap_xep`. */}

      {boLoc.nam_min !== null && boLoc.nam_max !== null && (
        <div className="py-3">
          <p className="mb-2 text-[12px] font-semibold tracking-wide text-primary uppercase">
            Năm ban hành
          </p>
          <div className="flex items-center gap-2">
            <label className="flex-1 text-[12px] text-muted-foreground">
              Từ
              <input
                type="number"
                min={boLoc.nam_min}
                max={boLoc.nam_max}
                value={hienTai.tu_nam ?? ""}
                placeholder={String(boLoc.nam_min)}
                onChange={(su) =>
                  onDoi({
                    tu_nam: su.target.value === "" ? undefined : Number(su.target.value),
                    trang: undefined,
                  })
                }
                className="focus-brass font-jetbrains mt-1 h-10 w-full rounded-lg border border-input bg-card px-2 text-[13px] outline-none"
              />
            </label>
            <label className="flex-1 text-[12px] text-muted-foreground">
              Đến
              <input
                type="number"
                min={boLoc.nam_min}
                max={boLoc.nam_max}
                value={hienTai.den_nam ?? ""}
                placeholder={String(boLoc.nam_max)}
                onChange={(su) =>
                  onDoi({
                    den_nam: su.target.value === "" ? undefined : Number(su.target.value),
                    trang: undefined,
                  })
                }
                className="focus-brass font-jetbrains mt-1 h-10 w-full rounded-lg border border-input bg-card px-2 text-[13px] outline-none"
              />
            </label>
          </div>
          <p className="mt-1.5 mb-0 text-[11px] text-muted-foreground">
            Kho hiện có văn bản từ {boLoc.nam_min} đến {boLoc.nam_max}.
          </p>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────── Một kết quả ───────────────────────────── */

function TheDong({ dong }: { dong: DongTimKiem }) {
  const trichDan = `${dong.duong_dan.replace(`${dong.so_ky_hieu} > `, "")} ${dong.so_ky_hieu}`;
  return (
    <article className="rounded-xl border border-border bg-card p-4 transition-colors duration-150 hover:border-[var(--color-brass-500)]/50">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px] text-muted-foreground">
        <span className="font-jetbrains text-[12px] text-foreground">{dong.so_ky_hieu}</span>
        <span className="text-border" aria-hidden>
          ·
        </span>
        <span>{dong.loai_van_ban}</span>
        {dong.co_quan_ban_hanh !== null && (
          <>
            <span className="text-border" aria-hidden>
              ·
            </span>
            <span>{dong.co_quan_ban_hanh}</span>
          </>
        )}
        {dong.ngay_ban_hanh !== null && (
          <>
            <span className="text-border" aria-hidden>
              ·
            </span>
            <span>Ban hành {dong.ngay_ban_hanh}</span>
          </>
        )}
      </div>

      {/* Nhãn hiệu lực của CHÍNH văn bản chứa điều khoản này, do
          `effectivity.py` kết luận — không phải cột `tinh_trang` của MOJ. */}
      {/* `ly_do` đi ra dưới dạng chữ TRUNG TÍNH, không qua prop `ghiChu`:
          `ghiChu` tô đỏ vì nó dành cho câu nêu ĐÍCH DANH văn bản thay thế, còn
          đây là một LÝ DO. Đưa lý do của một nhãn hổ phách vào khay đỏ là dán
          mức báo động của nhãn nặng nhất lên mọi nhãn. */}
      <BadgeHieuLuc hieuLuc={dong.hieu_luc.verdict} gonGang className="mt-2" />
      <p className="m-0 mt-1 line-clamp-2 text-[12px] leading-5 text-muted-foreground">
        {dong.hieu_luc.ly_do}
      </p>

      <h3 className="font-display mt-2 text-[18px] leading-snug font-semibold text-primary">
        <Link
          to="/tra-cuu/$docId"
          params={{ docId: dong.doc_id }}
          search={{ quanh: String(dong.provision_id) }}
          className="focus-brass rounded hover:underline"
        >
          {dong.tieu_de === "" ? dong.duong_dan : dong.tieu_de}
        </Link>
      </h3>
      <p className="font-jetbrains m-0 mt-0.5 text-[11px] text-muted-foreground">
        {dong.duong_dan}
      </p>

      <div className="mt-2.5 border-l-2 border-[var(--color-brass-500)] pl-3">
        <p className="serif-body m-0 text-[15px] leading-[1.8] text-foreground">{dong.trich}</p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-border pt-3 text-[12px]">
        <Link
          to="/tra-cuu/$docId"
          params={{ docId: dong.doc_id }}
          search={{ quanh: String(dong.provision_id) }}
          className="focus-brass inline-flex items-center gap-1 rounded font-medium text-[var(--color-brass-600)] hover:underline"
        >
          Mở nguyên văn <ArrowRight className="size-3.5" aria-hidden />
        </Link>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard?.writeText(trichDan);
            toast.success("Đã sao chép trích dẫn", { description: trichDan });
          }}
          className="focus-brass inline-flex cursor-pointer items-center gap-1 rounded text-muted-foreground hover:text-foreground"
        >
          <Copy className="size-3.5" aria-hidden /> Sao chép trích dẫn
        </button>
      </div>
    </article>
  );
}

/* ──────────────────────────────── Trang ────────────────────────────────── */

function ManTimKiem() {
  const timTrenUrl = Route.useSearch();
  const navigate = useNavigate();

  const [boLoc, datBoLoc] = useState<BoLoc | null>(null);
  const [ketQua, datKetQua] = useState<TimKiem | null>(null);
  const [loi, datLoi] = useState<ApiError | null>(null);
  const [dangChay, datDangChay] = useState(false);
  const [nhap, datNhap] = useState(timTrenUrl.q ?? "");
  const [sheetMo, datSheetMo] = useState(false);

  useEffect(() => {
    const dieuKhien = new AbortController();
    void goi("/bo-loc", laBoLoc, { signal: dieuKhien.signal }).then((kq) => {
      if (kq.ok) datBoLoc(kq.data);
    });
    return () => dieuKhien.abort();
  }, []);

  useEffect(() => {
    datNhap(timTrenUrl.q ?? "");
  }, [timTrenUrl.q]);

  const q = timTrenUrl.q ?? "";
  const trang = timTrenUrl.trang ?? 1;
  // Khoá phụ thuộc dạng chuỗi: mảng trên URL là một tham chiếu MỚI ở mỗi lần
  // dựng lại, nên đưa thẳng nó vào danh sách phụ thuộc sẽ gọi lại API vô hạn.
  const loaiKhoa = (timTrenUrl.loai ?? []).join("|");
  const coQuanKhoa = (timTrenUrl.co_quan ?? []).join("|");
  const { tu_nam: tuNam, den_nam: denNam, sap_xep: sapXep } = timTrenUrl;

  useEffect(() => {
    if (q.trim() === "") {
      datKetQua(null);
      datLoi(null);
      return;
    }
    const dieuKhien = new AbortController();
    datDangChay(true);
    const duongDan = `/tim-kiem${thamSo([
      ["q", q],
      ...(loaiKhoa === "" ? [] : loaiKhoa.split("|").map((v): [string, string] => ["loai", v])),
      ...(coQuanKhoa === ""
        ? []
        : coQuanKhoa.split("|").map((v): [string, string] => ["co_quan", v])),
      ["tu_nam", tuNam],
      ["den_nam", denNam],
      ["sap_xep", sapXep],
      ["limit", MOI_TRANG],
      ["offset", (trang - 1) * MOI_TRANG],
    ])}`;
    void goi(duongDan, laTimKiem, { signal: dieuKhien.signal }).then((kq) => {
      datDangChay(false);
      if (kq.ok) {
        datKetQua(kq.data);
        datLoi(null);
        return;
      }
      if (kq.error.kind === "aborted") return;
      // KHÔNG nuốt lỗi thành danh sách rỗng. 422 của `/tim-kiem` mang nguyên
      // danh sách giá trị lọc thật trong CSDL — nó là câu trả lời hữu ích nhất
      // trang này có thể đưa ra, còn "không có kết quả" là một câu SAI.
      datKetQua(null);
      datLoi(kq.error);
    });
    return () => dieuKhien.abort();
  }, [q, loaiKhoa, coQuanKhoa, tuNam, denNam, sapXep, trang]);

  const doi = (moi: SuaBoLoc) => {
    void navigate({
      to: "/tra-cuu",
      search: (cu: BoLocUrl) => {
        const gop: SuaBoLoc = { ...cu, ...moi };
        // Xoá hẳn khoá mang `undefined` để URL không đọng lại `?tu_nam=`.
        // `validateSearch` chạy lại trên kết quả này nên hình dạng vẫn được
        // kiểm ở đúng một chỗ.
        return Object.fromEntries(
          Object.entries(gop).filter(([, gia]) => gia !== undefined),
        ) as BoLocUrl;
      },
    });
  };

  const gui = () => doi({ q: nhap.trim() === "" ? undefined : nhap.trim(), trang: undefined });

  const chipDangBat: { khoa: "loai" | "co_quan"; gia: string }[] = [
    ...(timTrenUrl.loai ?? []).map((gia) => ({ khoa: "loai" as const, gia })),
    ...(timTrenUrl.co_quan ?? []).map((gia) => ({ khoa: "co_quan" as const, gia })),
  ];

  const boChip = (khoa: "loai" | "co_quan", gia: string) => {
    const con = (timTrenUrl[khoa] ?? []).filter((x) => x !== gia);
    doi({ [khoa]: con.length === 0 ? undefined : con, trang: undefined });
  };

  // "Đi thẳng tới văn bản": CHỈ khi số hiệu người dùng gõ trùng khớp số hiệu
  // của kết quả. Một số hiệu có thể thuộc HAI văn bản (65/2006/QH11), nên đây
  // là một DANH SÁCH chứ không phải một liên kết — đoán lấy một cái là mở nhầm.
  const trungSoHieu = new Map(
    (ketQua?.ket_qua ?? [])
      .filter((dong) => dong.so_ky_hieu.toLowerCase() === q.trim().toLowerCase())
      .map((dong) => [dong.doc_id, dong] as const),
  );

  const tongTrang =
    ketQua === null ? 0 : Math.max(1, Math.ceil(ketQua.tong_dieu_khoan / MOI_TRANG));
  const sapXepCoThe = boLoc?.sap_xep ?? [];

  return (
    <AppShell active="/tra-cuu">
      <div className="flex min-w-0 flex-1">
        <aside
          aria-label="Bộ lọc"
          className="hidden w-[280px] shrink-0 border-r border-border bg-[var(--color-paper-50)] px-4 py-4 xl:block"
        >
          <p className="font-display flex items-center gap-1.5 text-sm font-semibold text-primary">
            <SlidersHorizontal className="size-4" aria-hidden /> Bộ lọc
          </p>
          <ThanBoLoc boLoc={boLoc} hienTai={timTrenUrl} onDoi={doi} />
        </aside>

        {/* Ngăn kéo bộ lọc khai `aria-modal`; cột này là con của <main> nên chỉ
            trang này gỡ được nó khỏi vòng Tab. */}
        <div inert={sheetMo} className="min-w-0 flex-1 px-4 py-6 lg:px-8">
          <div className="mx-auto max-w-[900px]">
            <h1 className="font-display text-[28px] font-bold text-primary">Tìm kiếm điều khoản</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Tìm theo <strong className="font-semibold">từ khoá</strong> tới từng điều, khoản,
              điểm. Không dấu cũng ra.
            </p>

            <div className="relative mt-4">
              <Search
                className="absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <input
                value={nhap}
                onChange={(su) => datNhap(su.target.value)}
                onKeyDown={(su) => su.key === "Enter" && gui()}
                aria-label="Từ khoá tìm kiếm"
                placeholder="Ví dụ: thử việc, thai sản, lương tối thiểu, 45/2019/QH14"
                className="serif-body focus-brass h-14 w-full rounded-xl border border-input bg-card pr-24 pl-11 text-[15px] text-foreground outline-none placeholder:text-muted-foreground/80"
              />
              <button
                type="button"
                onClick={gui}
                className="bg-gradient-ink focus-brass absolute top-1/2 right-2 min-h-11 -translate-y-1/2 cursor-pointer rounded-lg px-4 text-sm font-medium text-primary-foreground"
              >
                Tìm
              </button>
            </div>

            {/* Lối rẽ sang đường HỎI. Đặt cạnh ô tìm kiếm và gọi đúng tên, vì ô
                trên là so khớp từ khoá: gọi nó là "hỏi AI" sẽ khiến người dùng
                gõ một câu hỏi tự nhiên vào một hệ thống xếp hạng theo từ, rồi
                đọc kết quả kém như một kết luận về pháp luật. */}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[13px] text-muted-foreground">
              <span>Có câu hỏi thành câu, cần câu trả lời kèm căn cứ?</span>
              <Link
                to="/dung-thu"
                className="focus-brass inline-flex min-h-9 items-center gap-1.5 rounded-full border border-[var(--color-brass-500)]/60 px-3 font-medium text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10"
              >
                <Sparkles className="size-3.5" aria-hidden /> Hỏi KLAW
              </Link>
            </div>

            {chipDangBat.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {chipDangBat.map((chip) => (
                  <Chip
                    key={`${chip.khoa}-${chip.gia}`}
                    onRemove={() => boChip(chip.khoa, chip.gia)}
                  >
                    {chip.gia}
                  </Chip>
                ))}
              </div>
            )}

            {trungSoHieu.size > 0 && (
              <div className="mt-3 flex flex-col gap-2">
                {[...trungSoHieu.values()].map((dong) => (
                  <Link
                    key={dong.doc_id}
                    to="/tra-cuu/$docId"
                    params={{ docId: dong.doc_id }}
                    className="focus-brass flex flex-wrap items-center gap-2 rounded-lg border border-[var(--color-brass-500)]/50 bg-[var(--color-brass-500)]/10 px-3 py-2 text-[13px] text-foreground"
                  >
                    <ArrowRight className="size-4 text-[var(--color-brass-600)]" aria-hidden />
                    <span className="font-medium text-[var(--color-brass-600)]">
                      Đi thẳng tới văn bản
                    </span>
                    <span className="font-jetbrains text-[12px]">{dong.so_ky_hieu}</span>
                    <span className="truncate text-muted-foreground">{dong.bo_luat}</span>
                  </Link>
                ))}
                {trungSoHieu.size > 1 && (
                  <p className="m-0 text-[12px] text-muted-foreground">
                    Số hiệu này thuộc {trungSoHieu.size} văn bản khác nhau trong CSDL quốc gia. Chọn
                    đúng văn bản bạn cần.
                  </p>
                )}
              </div>
            )}

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
              <p className="m-0 text-[13px] text-muted-foreground">
                {q.trim() === "" ? (
                  "Nhập từ khoá để bắt đầu."
                ) : dangChay ? (
                  "Đang tìm…"
                ) : ketQua === null ? (
                  ""
                ) : (
                  <>
                    <span className="font-medium text-foreground">
                      {ketQua.tong_dieu_khoan} điều khoản
                    </span>{" "}
                    trong{" "}
                    <span className="font-medium text-foreground">
                      {ketQua.tong_van_ban} văn bản
                    </span>{" "}
                    cho “<span className="text-foreground">{ketQua.q}</span>”
                  </>
                )}
              </p>

              {/* Cách sắp xếp do MÁY CHỦ khai (`/bo-loc.sap_xep`), không viết cứng. */}
              {sapXepCoThe.length > 0 && (
                <div className="flex items-center gap-1 rounded-full border border-border p-0.5">
                  {sapXepCoThe.map((cach) => {
                    const dangBat = (sapXep ?? "lien_quan") === cach;
                    return (
                      <button
                        key={cach}
                        type="button"
                        onClick={() => doi({ sap_xep: cach, trang: undefined })}
                        aria-pressed={dangBat}
                        className={cn(
                          "focus-brass cursor-pointer rounded-full px-2.5 py-1.5 text-[12px] transition-colors",
                          dangBat
                            ? "bg-[var(--color-brass-500)]/15 font-medium text-[var(--color-brass-600)]"
                            : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {NHAN_SAP_XEP[cach] ?? cach}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {sapXep === "con_hieu_luc_truoc" && (
              // Ba bậc, không phải hai. Bậc giữa gộp `mot_phan_khong_xac_dinh`,
              // `bi_sua_doi`, `can_doi_chieu_tay`, `chua_xac_dinh` — đọc nó
              // thành "đã chết" là vứt 27/126 văn bản còn hiệu lực phần lớn
              // xuống đáy.
              <p className="mt-3 mb-0 text-[12px] leading-5 text-muted-foreground">
                Thứ tự ba bậc: còn hiệu lực → chưa kết luận được → đã hết hiệu lực. Bậc giữa nghĩa
                là hệ thống chưa xác định được, không phải văn bản đã chết.
              </p>
            )}

            {loi !== null && <BaoLoi loi={loi} />}

            <div className="mt-4 flex flex-col gap-3 pb-16">
              {ketQua !== null && ketQua.ket_qua.length === 0 && (
                <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  Không có điều khoản nào khớp từ khoá này. Đây là tìm kiếm theo từ, nên thử dùng từ
                  ngữ của luật (“đơn phương chấm dứt hợp đồng lao động”) thay cho từ thông tục, hoặc
                  bỏ bớt bộ lọc.
                </p>
              )}
              {ketQua?.ket_qua.map((dong) => (
                <TheDong key={`${dong.doc_id}-${dong.provision_id}`} dong={dong} />
              ))}

              {tongTrang > 1 && (
                <nav
                  aria-label="Phân trang kết quả"
                  className="flex items-center justify-between gap-3 pt-2"
                >
                  <button
                    type="button"
                    disabled={trang <= 1}
                    onClick={() => doi({ trang: trang - 1 })}
                    className="focus-brass min-h-11 cursor-pointer rounded-lg border border-border px-4 text-[13px] text-foreground transition-colors hover:bg-[var(--color-paper-100)] disabled:cursor-default disabled:opacity-40"
                  >
                    Trang trước
                  </button>
                  <span className="text-[13px] text-muted-foreground">
                    Trang {trang}/{tongTrang}
                  </span>
                  <button
                    type="button"
                    disabled={trang >= tongTrang}
                    onClick={() => doi({ trang: trang + 1 })}
                    className="focus-brass min-h-11 cursor-pointer rounded-lg border border-border px-4 text-[13px] text-foreground transition-colors hover:bg-[var(--color-paper-100)] disabled:cursor-default disabled:opacity-40"
                  >
                    Trang sau
                  </button>
                </nav>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bộ lọc dạng ngăn kéo dưới 1280px */}
      <button
        type="button"
        hidden={sheetMo}
        onClick={() => datSheetMo(true)}
        aria-expanded={sheetMo}
        aria-controls="bo-loc-ngan-keo"
        className="focus-brass fixed bottom-[68px] left-1/2 z-40 min-h-11 -translate-x-1/2 cursor-pointer rounded-full border border-[var(--color-brass-500)]/60 bg-card px-4 text-[13px] font-medium text-[var(--color-brass-600)] shadow-soft md:bottom-5 xl:hidden"
      >
        <span className="inline-flex items-center gap-1.5">
          <SlidersHorizontal className="size-4" aria-hidden />
          Bộ lọc ({chipDangBat.length})
        </span>
      </button>
      {sheetMo && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <div
            className="absolute inset-0 bg-[var(--color-ink-950)]/45"
            onClick={() => datSheetMo(false)}
            aria-hidden
          />
          <div
            id="bo-loc-ngan-keo"
            role="dialog"
            aria-modal="true"
            aria-label="Bộ lọc văn bản"
            className="rise-in absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-2xl border-t border-border bg-background px-4 pt-4 pb-8"
          >
            <div className="mb-2 flex items-center justify-between">
              <p className="font-display m-0 text-sm font-semibold text-primary">
                Bộ lọc ({chipDangBat.length})
              </p>
              <button
                type="button"
                onClick={() => datSheetMo(false)}
                aria-label="Đóng bộ lọc"
                className="focus-brass grid size-11 cursor-pointer place-items-center rounded-md text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
            <ThanBoLoc boLoc={boLoc} hienTai={timTrenUrl} onDoi={doi} />
          </div>
        </div>
      )}
    </AppShell>
  );
}
