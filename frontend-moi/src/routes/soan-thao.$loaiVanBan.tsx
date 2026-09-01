import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  Copy,
  Download,
  FileDown,
  Link2,
  Minus,
  Plus,
  Redo2,
  Save,
  ListPlus,
  Undo2,
} from "lucide-react";
import { AppShell } from "@/components/app/AppShell";
import {
  AreaField,
  BasisChip,
  Group,
  InfoPopover,
  SelectField,
  TextField,
  Toggle,
  fieldId,
  focusField,
} from "@/components/draft/DraftBits";
import { CanCuChuaKiemBanner } from "@/components/legal/LegalBits";
import { SoatBanThao } from "@/components/klaw/SoatBanThao";
import { TINH_THANH, capDuoiCua } from "@/lib/dia-gioi";
import { MAU, laHopDongLaoDong, laThuViec, loaiBackendCua, mauTheoId } from "@/lib/mau-van-ban";
import { MUC_BEN, MUC_KY, MUC_ND, dungKhung, type PhanND } from "@/lib/khung-van-ban";
import { laMau, type CauTruc } from "@/lib/klaw";
import { goi } from "@/lib/api";
// `toanVan` tĩnh được: `docx` và `jspdf` nằm sau `await import()` bên trong
// `xuat-ban.ts`, nên nhập hàm này KHÔNG kéo hai thư viện nặng vào gói đầu tiên.
import { toanVan } from "@/lib/xuat-ban";
import { chiSo, dinhDangTien, docSoThanhChu } from "@/lib/tien-viet";
import { cn, ngayVietNam } from "@/lib/utils";
import { SITE_ORIGIN } from "./__root";

export const Route = createFileRoute("/soan-thao/$loaiVanBan")({
  head: ({ params }) => {
    const m = MAU.find((x) => x.id === params.loaiVanBan);
    const ten = m?.ten ?? "Văn bản pháp lý";
    return {
      meta: [
        { title: `Soạn thảo ${ten} — KLAW` },
        {
          name: "description",
          content:
            m?.moTa ??
            "Soạn thảo văn bản pháp lý theo thể thức Việt Nam với biểu mẫu thông minh, xem trước A4 và rà soát rủi ro.",
        },
        { property: "og:title", content: `Soạn thảo ${ten} — KLAW` },
        {
          property: "og:description",
          content:
            m?.moTa ?? "Điền thông tin các bên, chọn điều khoản và xuất bản thảo hoàn chỉnh.",
        },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
      links: [
        {
          rel: "canonical",
          href: `${SITE_ORIGIN}/soan-thao/${encodeURIComponent(params.loaiVanBan)}`,
        },
      ],
    };
  },
  component: KhongGianSoanThao,
});

/* ------------------------------- state model ------------------------------ */

type BenLoai = "to-chuc" | "ca-nhan";

type Ben = {
  loai: BenLoai;
  tenToChuc: string;
  mst: string;
  hoTen: string;
  ngaySinh: string;
  cccd: string;
  ngayCap: string;
  noiCap: string;
  tinh: string;
  phuongXa: string;
  soNhaDuong: string;
  nguoiDaiDien: string;
  chucVu: string;
  dienThoai: string;
  email: string;
  soTaiKhoan: string;
  nganHang: string;
};

type Dot = { id: number; tyLe: string; moc: string };

type NoiDung = {
  tenDichVu: string;
  phamVi: string;
  giaTri: number | "";
  thueGTGT: string;
  tuNgay: string;
  denNgay: string;
  diaDiem: string;
  dot: Dot[];
  // lao động
  chucDanh: string;
  soNgayThuViec: string;
  luongChinhThuc: number | "";
  luongThuViec: number | "";
  // phạt
  mucPhat: string;
};

type DieuKhoan = {
  phat: boolean;
  boiThuong: boolean;
  baoMat: boolean;
  batKhaKhang: boolean;
  chamDutTruocHan: boolean;
  sohuuTriTue: boolean;
  tranhChap: boolean;
  hieuLuc: boolean;
  coQuanTranhChap: "toa-an" | "trong-tai" | "";
  soBan: string;
};

type Draft = { A: Ben; B: Ben; nd: NoiDung; dk: DieuKhoan };

const benRong = (loai: BenLoai): Ben => ({
  loai,
  tenToChuc: "",
  mst: "",
  hoTen: "",
  ngaySinh: "",
  cccd: "",
  ngayCap: "",
  noiCap: "",
  tinh: "",
  phuongXa: "",
  soNhaDuong: "",
  nguoiDaiDien: "",
  chucVu: "",
  dienThoai: "",
  email: "",
  soTaiKhoan: "",
  nganHang: "",
});

const draftRong: Draft = {
  A: benRong("to-chuc"),
  B: benRong("to-chuc"),
  nd: {
    tenDichVu: "",
    phamVi: "",
    giaTri: "",
    thueGTGT: "",
    tuNgay: "",
    denNgay: "",
    diaDiem: "",
    dot: [
      { id: 1, tyLe: "50", moc: "Trong 05 ngày làm việc kể từ ngày ký hợp đồng" },
      { id: 2, tyLe: "50", moc: "Trong 10 ngày kể từ ngày nghiệm thu" },
    ],
    chucDanh: "",
    soNgayThuViec: "",
    luongChinhThuc: "",
    luongThuViec: "",
    mucPhat: "",
  },
  dk: {
    phat: true,
    boiThuong: true,
    baoMat: true,
    batKhaKhang: true,
    chamDutTruocHan: false,
    sohuuTriTue: false,
    tranhChap: false,
    hieuLuc: true,
    coQuanTranhChap: "",
    soBan: "02",
  },
};

const CHUC_DANH = [
  "Người lao động phổ thông",
  "Nhân viên chuyên môn, kỹ thuật",
  "Người quản lý doanh nghiệp",
  "Công việc dưới 01 tháng",
];

const BUOC = ["Loại văn bản", "Thông tin các bên", "Nội dung chính", "Điều khoản", "Xem trước"];

/* --------------------------------- page ---------------------------------- */

function KhongGianSoanThao() {
  const { loaiVanBan } = Route.useParams();
  const mau = mauTheoId(loaiVanBan);

  const [draft, setDraft] = useState<Draft>(draftRong);
  const [buoc, setBuoc] = useState(1);
  const [leftPct, setLeftPct] = useState(46);
  const [zoom, setZoom] = useState(0.72);
  const khungRef = useRef<HTMLDivElement | null>(null);
  const [dangXuat, setDangXuat] = useState<"docx" | "pdf" | null>(null);
  const [chuThich, setChuThich] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  // Declared with the other hooks, above the "mẫu không tồn tại" early return.
  // Sitting below that return made the hook order depend on whether the route
  // param matched a template — the exact shape React refuses to render twice.
  const [pane, setPane] = useState<"nhap" | "xem">("nhap");
  const undoRef = useRef<Draft[]>([]);
  const redoRef = useRef<Draft[]>([]);
  const [, forceTick] = useState(0);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const apply = useCallback((key: string, fn: (d: Draft) => Draft) => {
    setDraft((prev) => {
      undoRef.current = [...undoRef.current.slice(-49), prev];
      redoRef.current = [];
      return fn(prev);
    });
    setFlash(key);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(null), 420);
    forceTick((t) => t + 1);
  }, []);

  const setBen = (which: "A" | "B", patch: Partial<Ben>, key: string) =>
    apply(key, (d) => ({ ...d, [which]: { ...d[which], ...patch } }));
  const setND = (patch: Partial<NoiDung>, key: string) =>
    apply(key, (d) => ({ ...d, nd: { ...d.nd, ...patch } }));
  const setDK = (patch: Partial<DieuKhoan>, key: string) =>
    apply(key, (d) => ({ ...d, dk: { ...d.dk, ...patch } }));

  const undo = () => {
    const prev = undoRef.current.pop();
    if (!prev) return;
    setDraft((cur) => {
      redoRef.current.push(cur);
      return prev;
    });
    forceTick((t) => t + 1);
  };
  const redo = () => {
    const next = redoRef.current.pop();
    if (!next) return;
    setDraft((cur) => {
      undoRef.current.push(cur);
      return next;
    });
    forceTick((t) => t + 1);
  };

  /**
   * Bộ khung của loại văn bản này, đọc MỘT LẦN từ `GET /mau/{loai}`.
   *
   * Gọi ở đây chứ không ở mỗi phím gõ: `cau_truc` chỉ phụ thuộc LOẠI văn bản,
   * nên tải một lần rồi dựng lại khung tại chỗ giữ được xem trước tức thời khi
   * gõ mà không chạm mạng lần nào nữa — và không gọi mô hình nào.
   */
  const loaiBackendKhung = loaiBackendCua(loaiVanBan);
  const [cauTruc, datCauTruc] = useState<CauTruc | null>(null);
  const [dangTaiKhung, datDangTaiKhung] = useState(loaiBackendKhung !== undefined);

  useEffect(() => {
    if (loaiBackendKhung === undefined) {
      datCauTruc(null);
      datDangTaiKhung(false);
      return;
    }
    const dieuKhien = new AbortController();
    datDangTaiKhung(true);
    void goi(`/mau/${encodeURIComponent(loaiBackendKhung)}`, laMau, {
      signal: dieuKhien.signal,
    }).then((kq) => {
      if (dieuKhien.signal.aborted) return;
      datCauTruc(kq.ok ? kq.data.cau_truc : null);
      datDangTaiKhung(false);
    });
    return () => dieuKhien.abort();
  }, [loaiBackendKhung]);

  // draggable divider
  useEffect(() => {
    let dragging = false;
    const onMove = (e: MouseEvent) => {
      if (!dragging || !wrapRef.current) return;
      const r = wrapRef.current.getBoundingClientRect();
      const pct = ((e.clientX - r.left) / r.width) * 100;
      setLeftPct(Math.min(70, Math.max(28, pct)));
    };
    const onUp = () => {
      dragging = false;
      document.body.style.userSelect = "";
    };
    const onDown = (e: Event) => {
      if ((e.target as HTMLElement)?.dataset?.["divider"] === "1") {
        dragging = true;
        document.body.style.userSelect = "none";
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, []);

  if (!mau) {
    return (
      <AppShell active="/soan-thao">
        <div className="mx-auto max-w-xl px-6 py-20 text-center">
          <h1 className="font-display text-2xl font-bold text-primary">
            Không tìm thấy mẫu văn bản
          </h1>
          <Link
            to="/soan-thao"
            className="mt-4 inline-flex items-center gap-2 text-sm text-[var(--color-brass-600)]"
          >
            <ArrowLeft className="size-4" /> Quay lại danh mục mẫu
          </Link>
        </div>
      </AppShell>
    );
  }

  const laLaoDong = laHopDongLaoDong(mau);

  const layKhung = () => khungRef.current?.querySelector<HTMLElement>(".a4-sheet") ?? null;

  const loaiBackend = loaiBackendCua(mau.id);

  /** Toàn văn bản thảo, đọc từ chính khung xem trước người dùng đang nhìn. */
  const layToanVanBanThao = (): string | null => {
    const sheet = layKhung();
    if (sheet === null) return null;
    return toanVan(sheet);
  };

  /**
   * Dữ kiện suy từ biểu mẫu — CHỈ những khoá ánh xạ một–một.
   *
   * Cố ý KHÔNG suy `nhom_chuc_danh`: bốn nhãn của biểu mẫu ("Nhân viên chuyên
   * môn, kỹ thuật") không khớp một–một với bốn giá trị của `rules.yaml`
   * (`cao_dang_tro_len` / `trung_cap_cnkt_nghiep_vu`), và đoán sai giữa hai giá
   * trị đó là đổi giới hạn thử việc từ 60 ngày thành 30 ngày — một phán quyết
   * sai sinh ra từ một phép đoán của giao diện. Người dùng chọn ở khối soát.
   *
   * Cũng KHÔNG suy `co_dieu_khoan_phat_tien` từ `dk.phat`: `dk.phat` là phạt vi
   * phạm hợp đồng thương mại, còn khoá kia là phạt tiền NGƯỜI LAO ĐỘNG (Điều 17
   * cấm). Hai chế định khác nhau mang tên gần giống nhau.
   */
  const factTuBieuMau: Record<string, string | number | boolean> = {};
  if (draft.nd.soNgayThuViec !== "") {
    factTuBieuMau["thoi_gian_thu_viec_ngay"] = Number(draft.nd.soNgayThuViec);
  }
  if (draft.nd.luongThuViec !== "") factTuBieuMau["luong_thu_viec"] = draft.nd.luongThuViec;
  if (draft.nd.luongChinhThuc !== "") {
    factTuBieuMau["luong_chinh_thuc"] = draft.nd.luongChinhThuc;
  }

  const xuatTep = async (dinhDang: "docx" | "pdf") => {
    const sheet = layKhung();
    if (!sheet) {
      toast.error("Chưa tải được khung xem trước. Vui lòng thử lại.");
      return;
    }
    setDangXuat(dinhDang);
    const id = toast.loading(dinhDang === "docx" ? "Đang tạo tệp Word…" : "Đang tạo tệp PDF…");
    try {
      const { xuatWord, xuatPDF } = await import("@/lib/xuat-ban");
      if (dinhDang === "docx") await xuatWord(sheet, mau.ten);
      else await xuatPDF(sheet, mau.ten);
      toast.success(dinhDang === "docx" ? "Đã tải tệp .docx." : "Đã tải tệp .pdf.", {
        id,
        description: "Bản thảo cần được pháp chế rà soát trước khi ký kết.",
      });
    } catch {
      // Thất bại đi ra bằng toast, không bằng console: người dùng thấy được, và
      // bản dựng công khai không nhả stack ra console trình duyệt.
      toast.error("Xuất tệp thất bại. Vui lòng thử lại.", { id });
    } finally {
      setDangXuat(null);
    }
  };

  const saoChepToanVan = async () => {
    const sheet = layKhung();
    if (!sheet) return;
    try {
      const { toanVan } = await import("@/lib/xuat-ban");
      await navigator.clipboard.writeText(toanVan(sheet));
      toast.success("Đã sao chép toàn văn bản thảo.");
    } catch {
      toast.error("Trình duyệt không cho phép truy cập clipboard.");
    }
  };

  return (
    <AppShell active="/soan-thao">
      {/* Chuyển pane dưới 1024px */}
      <div
        role="tablist"
        aria-label="Chế độ soạn thảo"
        className="sticky top-[52px] z-30 flex gap-1 border-b border-border bg-background/95 px-4 py-2 backdrop-blur lg:hidden"
      >
        {(
          [
            ["nhap", "Nhập thông tin"],
            ["xem", "Xem trước"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={pane === id}
            onClick={() => setPane(id)}
            className={cn(
              "focus-brass flex-1 rounded-lg px-3 py-2 text-[13px] transition-colors",
              pane === id
                ? "bg-[var(--color-brass-500)]/15 font-semibold text-[var(--color-brass-600)]"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div ref={wrapRef} className="flex h-screen flex-col lg:flex-row">
        {/* LEFT — wizard */}
        <div
          className={cn(
            "min-w-0 flex-1 flex-col overflow-hidden border-b border-border lg:flex lg:flex-none lg:basis-[var(--pane-basis)] lg:border-r lg:border-b-0",
            pane === "nhap" ? "flex" : "hidden",
          )}
          style={{ ["--pane-basis" as string]: `${leftPct}%` }}
        >
          <div className="shrink-0 border-b border-border bg-background px-5 pt-4 pb-3">
            <Link
              to="/soan-thao"
              className="inline-flex min-h-6 items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="size-3.5" /> Tất cả mẫu văn bản
            </Link>
            <h1 className="mt-1.5 font-display text-[22px] leading-tight font-bold text-primary">
              {mau.ten}
            </h1>
            <ol className="mt-3 flex flex-wrap items-center gap-1.5">
              {BUOC.map((b, i) => {
                const n = i + 1;
                const done = n < buoc;
                const active = n === buoc;
                return (
                  <li key={b}>
                    <button
                      type="button"
                      onClick={() => setBuoc(n)}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11.5px] transition-colors",
                        active
                          ? "border-[var(--color-brass-500)] bg-[var(--color-brass-500)]/14 text-[var(--color-brass-600)]"
                          : done
                            ? "border-[var(--color-brass-500)]/40 text-[var(--color-brass-600)]"
                            : "border-border text-muted-foreground hover:bg-[var(--color-paper-100)]",
                      )}
                    >
                      <span className="font-jetbrains text-[10px]">{done ? "✓" : n}</span>
                      {b}
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
            <CanCuChuaKiemBanner />

            {buoc === 1 && (
              <Group title="1 · Loại văn bản">
                <p className="text-sm text-muted-foreground">{mau.moTa}</p>
                <div className="rounded-lg border border-border bg-background p-3 text-[13px]">
                  <p className="text-muted-foreground">
                    Ký hiệu số văn bản:{" "}
                    <span className="font-jetbrains text-foreground">…/{mau.kyHieu}</span>
                  </p>
                  <p className="mt-2 text-muted-foreground">Căn cứ pháp lý mẫu:</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {mau.canCu.map((c) => (
                      <BasisChip key={c.soHieu} soHieu={c.soHieu} label={c.ten} />
                    ))}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setBuoc(2)}
                  className="rounded-lg bg-[var(--color-brass-500)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
                >
                  Tiếp tục — Thông tin các bên
                </button>
              </Group>
            )}

            {buoc === 2 && (
              <>
                <BenForm
                  nhan="Bên A"
                  ben={draft.A}
                  onChange={(p, k) => setBen("A", p, k)}
                  prefix="A"
                />
                <BenForm
                  nhan="Bên B"
                  ben={draft.B}
                  onChange={(p, k) => setBen("B", p, k)}
                  prefix="B"
                />
              </>
            )}

            {buoc === 3 && (
              <Group title="3 · Nội dung chính">
                <TextField
                  name="nd.tenDichVu"
                  label={laLaoDong ? "Vị trí công việc" : "Tên dịch vụ"}
                  value={draft.nd.tenDichVu}
                  onChange={(v) => setND({ tenDichVu: v }, "nd.tenDichVu")}
                  placeholder={laLaoDong ? "Chuyên viên pháp chế" : "Tư vấn triển khai hệ thống"}
                />
                <AreaField
                  name="nd.phamVi"
                  label="Phạm vi công việc"
                  value={draft.nd.phamVi}
                  onChange={(v) => setND({ phamVi: v }, "nd.phamVi")}
                  placeholder="Mô tả chi tiết các hạng mục công việc, sản phẩm bàn giao…"
                  action={
                    <button
                      type="button"
                      onClick={() =>
                        setND(
                          {
                            phamVi: goiYPhamVi(draft.nd.tenDichVu),
                          },
                          "nd.phamVi",
                        )
                      }
                      className="inline-flex items-center gap-1 rounded-md border border-[var(--color-brass-500)]/50 px-2 py-1 text-[11.5px] font-medium text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/12"
                    >
                      <ListPlus className="size-3" /> Chèn dàn ý mẫu
                    </button>
                  }
                />
                <TextField
                  name="nd.giaTri"
                  label="Giá trị hợp đồng"
                  value={draft.nd.giaTri === "" ? "" : dinhDangTien(draft.nd.giaTri)}
                  onChange={(v) => setND({ giaTri: chiSo(v) }, "nd.giaTri")}
                  placeholder="500.000.000 ₫"
                  hint={
                    draft.nd.giaTri !== "" ? (
                      <span className="serif-body text-[12.5px] text-foreground">
                        Bằng chữ: {docSoThanhChu(Number(draft.nd.giaTri))}
                      </span>
                    ) : (
                      "Nhập số tiền, hệ thống tự định dạng và đọc thành chữ."
                    )
                  }
                />
                <SelectField
                  name="nd.thueGTGT"
                  label="Thuế GTGT"
                  value={draft.nd.thueGTGT}
                  onChange={(v) => setND({ thueGTGT: v }, "nd.thueGTGT")}
                  options={["0%", "5%", "8%", "10%"]}
                />
                <div className="grid grid-cols-2 gap-3">
                  <TextField
                    name="nd.tuNgay"
                    label="Thực hiện từ ngày"
                    type="date"
                    value={draft.nd.tuNgay}
                    onChange={(v) => setND({ tuNgay: v }, "nd.tuNgay")}
                  />
                  <TextField
                    name="nd.denNgay"
                    label="Đến ngày"
                    type="date"
                    value={draft.nd.denNgay}
                    onChange={(v) => setND({ denNgay: v }, "nd.denNgay")}
                  />
                </div>

                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-[12.5px] font-medium">Số đợt thanh toán</span>
                    <button
                      type="button"
                      onClick={() =>
                        setND(
                          {
                            dot: [...draft.nd.dot, { id: Date.now(), tyLe: "", moc: "" }],
                          },
                          "nd.dot",
                        )
                      }
                      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11.5px] hover:bg-[var(--color-paper-100)]"
                    >
                      <Plus className="size-3" /> Thêm đợt
                    </button>
                  </div>
                  <div className="space-y-2">
                    {draft.nd.dot.map((d, i) => (
                      <div key={d.id} className="flex items-center gap-2">
                        <span className="font-jetbrains w-12 shrink-0 text-[12px] text-muted-foreground">
                          Đợt {i + 1}
                        </span>
                        <input
                          value={d.tyLe}
                          onChange={(e) =>
                            setND(
                              {
                                dot: draft.nd.dot.map((x) =>
                                  x.id === d.id
                                    ? { ...x, tyLe: e.target.value.replace(/\D/g, "") }
                                    : x,
                                ),
                              },
                              "nd.dot",
                            )
                          }
                          placeholder="%"
                          className="w-16 rounded-lg border border-border bg-background px-2 py-1.5 text-sm outline-none focus:border-[var(--color-brass-500)]"
                        />
                        <input
                          value={d.moc}
                          onChange={(e) =>
                            setND(
                              {
                                dot: draft.nd.dot.map((x) =>
                                  x.id === d.id ? { ...x, moc: e.target.value } : x,
                                ),
                              },
                              "nd.dot",
                            )
                          }
                          placeholder="Mốc thanh toán"
                          className="min-w-0 flex-1 rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-[var(--color-brass-500)]"
                        />
                        <button
                          type="button"
                          aria-label="Xoá đợt"
                          onClick={() =>
                            setND({ dot: draft.nd.dot.filter((x) => x.id !== d.id) }, "nd.dot")
                          }
                          className="rounded-md border border-border p-1.5 text-muted-foreground hover:bg-[var(--color-paper-100)]"
                        >
                          <Minus className="size-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                    Tổng tỷ lệ:{" "}
                    <span
                      className={cn(
                        "font-jetbrains",
                        tongTyLe(draft.nd.dot) !== 100 && "text-[var(--color-brass-600)]",
                      )}
                    >
                      {tongTyLe(draft.nd.dot)}%
                    </span>
                  </p>
                </div>

                <TextField
                  name="nd.diaDiem"
                  label="Địa điểm thực hiện"
                  value={draft.nd.diaDiem}
                  onChange={(v) => setND({ diaDiem: v }, "nd.diaDiem")}
                  placeholder="Trụ sở Bên A và trực tuyến"
                />

                {laLaoDong && (
                  <div className="space-y-3 rounded-lg border border-border bg-background p-3">
                    <p className="text-[12px] font-medium text-muted-foreground">
                      Thông tin lao động {laThuViec(mau) ? "(thử việc)" : ""}
                    </p>
                    <SelectField
                      name="nd.chucDanh"
                      label="Chức danh / tính chất công việc"
                      value={draft.nd.chucDanh}
                      onChange={(v) => setND({ chucDanh: v }, "nd.chucDanh")}
                      options={CHUC_DANH}
                    />
                    <TextField
                      name="nd.soNgayThuViec"
                      label="Thời gian thử việc (ngày)"
                      value={draft.nd.soNgayThuViec}
                      onChange={(v) =>
                        setND({ soNgayThuViec: v.replace(/\D/g, "") }, "nd.soNgayThuViec")
                      }
                      placeholder="60"
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <TextField
                        name="nd.luongChinhThuc"
                        label="Lương chính thức"
                        value={
                          draft.nd.luongChinhThuc === ""
                            ? ""
                            : dinhDangTien(draft.nd.luongChinhThuc)
                        }
                        onChange={(v) => setND({ luongChinhThuc: chiSo(v) }, "nd.luongChinhThuc")}
                        placeholder="20.000.000 ₫"
                      />
                      <TextField
                        name="nd.luongThuViec"
                        label="Lương thử việc"
                        value={
                          draft.nd.luongThuViec === "" ? "" : dinhDangTien(draft.nd.luongThuViec)
                        }
                        onChange={(v) => setND({ luongThuViec: chiSo(v) }, "nd.luongThuViec")}
                        placeholder="17.000.000 ₫"
                      />
                    </div>
                  </div>
                )}
              </Group>
            )}

            {buoc === 4 && (
              <Group title="4 · Điều khoản">
                <DieuKhoanRow
                  bat={draft.dk.phat}
                  onChange={(v) => setDK({ phat: v }, "dk.phat")}
                  ten="Phạt vi phạm hợp đồng"
                  moTa="Ấn định mức phạt khi một bên vi phạm nghĩa vụ."
                  giaiThich="Phạt vi phạm chỉ áp dụng nếu các bên có thỏa thuận trong hợp đồng. Với hợp đồng thương mại, mức phạt tối đa là 8% giá trị phần nghĩa vụ bị vi phạm."
                >
                  {draft.dk.phat && (
                    <TextField
                      name="nd.mucPhat"
                      label="Mức phạt (% giá trị phần nghĩa vụ bị vi phạm)"
                      value={draft.nd.mucPhat}
                      onChange={(v) => setND({ mucPhat: v.replace(/[^\d.]/g, "") }, "nd.mucPhat")}
                      placeholder="8"
                    />
                  )}
                </DieuKhoanRow>
                <DieuKhoanRow
                  bat={draft.dk.boiThuong}
                  onChange={(v) => setDK({ boiThuong: v }, "dk.boiThuong")}
                  ten="Bồi thường thiệt hại"
                  moTa="Bù đắp tổn thất thực tế, trực tiếp do vi phạm gây ra."
                  giaiThich="Bồi thường thiệt hại phát sinh theo luật ngay cả khi không thỏa thuận, nhưng ghi rõ giúp xác định phạm vi và cách tính."
                />
                <DieuKhoanRow
                  bat={draft.dk.baoMat}
                  onChange={(v) => setDK({ baoMat: v }, "dk.baoMat")}
                  ten="Bảo mật thông tin"
                  moTa="Ràng buộc không tiết lộ thông tin trong và sau hợp đồng."
                  giaiThich="Không có điều khoản bảo mật, việc chứng minh nghĩa vụ giữ bí mật kinh doanh sẽ khó khăn khi xảy ra tranh chấp."
                />
                <DieuKhoanRow
                  bat={draft.dk.batKhaKhang}
                  onChange={(v) => setDK({ batKhaKhang: v }, "dk.batKhaKhang")}
                  ten="Bất khả kháng"
                  moTa="Miễn trách nhiệm khi có sự kiện khách quan không thể lường trước."
                  giaiThich="Điều khoản này xác định rõ thủ tục thông báo và hệ quả, tránh tranh cãi về việc sự kiện có phải bất khả kháng hay không."
                />
                <DieuKhoanRow
                  bat={draft.dk.chamDutTruocHan}
                  onChange={(v) => setDK({ chamDutTruocHan: v }, "dk.chamDutTruocHan")}
                  ten="Chấm dứt hợp đồng trước hạn"
                  moTa="Các trường hợp, thời hạn báo trước và hậu quả pháp lý."
                  giaiThich="Nếu không quy định, việc đơn phương chấm dứt có thể bị coi là vi phạm hợp đồng và phát sinh bồi thường."
                />
                <DieuKhoanRow
                  bat={draft.dk.sohuuTriTue}
                  onChange={(v) => setDK({ sohuuTriTue: v }, "dk.sohuuTriTue")}
                  ten="Sở hữu trí tuệ"
                  moTa="Xác định ai sở hữu sản phẩm, tài liệu, mã nguồn tạo ra."
                  giaiThich="Nếu không thỏa thuận, quyền tác giả thường thuộc về bên tạo ra sản phẩm, không tự động thuộc bên trả tiền."
                />
                <DieuKhoanRow
                  bat={draft.dk.tranhChap}
                  onChange={(v) => setDK({ tranhChap: v }, "dk.tranhChap")}
                  ten="Luật áp dụng và giải quyết tranh chấp"
                  moTa="Chọn cơ quan giải quyết khi thương lượng không thành."
                  giaiThich="Thỏa thuận trọng tài phải được lập bằng văn bản; nếu không có, tranh chấp mặc định thuộc thẩm quyền của tòa án."
                >
                  {draft.dk.tranhChap && (
                    <div id={fieldId("dk.coQuanTranhChap")} tabIndex={-1} className="flex gap-4">
                      {[
                        { v: "toa-an", l: "Tòa án có thẩm quyền" },
                        { v: "trong-tai", l: "Trọng tài — VIAC" },
                      ].map((o) => (
                        <label key={o.v} className="flex items-center gap-2 text-[13px]">
                          <input
                            type="radio"
                            name="coQuanTranhChap"
                            checked={draft.dk.coQuanTranhChap === o.v}
                            onChange={() =>
                              setDK(
                                { coQuanTranhChap: o.v as DieuKhoan["coQuanTranhChap"] },
                                "dk.coQuanTranhChap",
                              )
                            }
                            className="accent-[var(--color-brass-500)]"
                          />
                          {o.l}
                        </label>
                      ))}
                    </div>
                  )}
                </DieuKhoanRow>
                <DieuKhoanRow
                  bat={draft.dk.hieuLuc}
                  onChange={(v) => setDK({ hieuLuc: v }, "dk.hieuLuc")}
                  ten="Hiệu lực và số bản"
                  moTa="Thời điểm phát sinh hiệu lực và số bản có giá trị như nhau."
                  giaiThich="Ghi rõ số bản và giá trị pháp lý mỗi bản giúp tránh tranh chấp về bản gốc khi thực hiện hợp đồng."
                >
                  {draft.dk.hieuLuc && (
                    <TextField
                      name="dk.soBan"
                      label="Số bản"
                      value={draft.dk.soBan}
                      onChange={(v) => setDK({ soBan: v.replace(/\D/g, "") }, "dk.soBan")}
                      placeholder="02"
                    />
                  )}
                </DieuKhoanRow>
              </Group>
            )}

            {buoc === 5 && (
              <Group title="5 · Xem trước & xuất bản">
                <p className="text-sm text-muted-foreground">
                  Bản thảo đã sẵn sàng ở khung xem trước bên phải. Kiểm tra các ô còn để trống (gạch
                  nét đứt màu đồng) trước khi xuất bản. Phần đối chiếu pháp lý nằm ở khối soát bên
                  dưới — và chỉ khối đó, không có bộ quy tắc nào chạy song song.
                </p>
                <ul className="space-y-1.5 text-[13px] text-muted-foreground">
                  <li>· Số trường còn trống: {demTrong(draft, laLaoDong)}</li>
                  <li>· Điều khoản được chọn: {demDieuKhoan(draft.dk)}</li>
                </ul>
              </Group>
            )}

            {/* Soát THẬT với kho văn bản. Khác hẳn khối "rà soát rủi ro" ngay
                dưới: khối đó là năm quy tắc viết cứng trong giao diện, khối này
                gọi `POST /soat` và đối chiếu với rule + checklist dựng từ chính
                văn bản gốc trong CSDL. Hai khối để tách bạch, không trộn, vì
                nguồn thẩm quyền của chúng khác nhau. */}
            {buoc === 5 &&
              (loaiBackend === undefined ? (
                <section
                  aria-label="Soát bản thảo với KLAW"
                  className="rounded-xl border border-dashed border-border p-4"
                >
                  <p className="m-0 text-[13px] leading-5 text-muted-foreground">
                    <span className="font-semibold text-foreground">
                      KLAW chưa soát được loại văn bản này.
                    </span>{" "}
                    Bộ soát chưa dựng rule và checklist cho loại văn bản này. Bản thảo vẫn soạn và
                    xuất tệp bình thường — nhưng phần đối chiếu pháp lý phải do người làm.
                  </p>
                </section>
              ) : (
                <SoatBanThao
                  loaiBackend={loaiBackend}
                  layToanVan={layToanVanBanThao}
                  factTuBieuMau={factTuBieuMau}
                />
              ))}

            {/* Bảng "rà soát rủi ro" đã GỠ — nó là bộ quy tắc pháp lý THỨ HAI.

                Năm quy tắc viết cứng trong JSX, mỗi quy tắc kèm một chuỗi trích
                dẫn cũng viết cứng ("Điều 25 Bộ luật Lao động 2019"), và không
                một chuỗi nào đi qua kho văn bản. Đó đúng là loại khẳng định
                pháp lý không kiểm chứng được mà cả sản phẩm này tồn tại để
                chống: nếu KLAW không chấp nhận một câu trả lời không có trích
                dẫn đã xác minh, nó cũng không được tự phát một cảnh báo như vậy.

                Hai trong năm (giới hạn thử việc Điều 25, sàn 85% Điều 26) TRÙNG
                với rule máy chủ chạy trên `hdld`, nên bản thảo bị soát hai lần
                bởi hai thẩm quyền có thể trôi khỏi nhau. Ba quy tắc còn lại
                (trần phạt 8% Điều 301 và điều khoản giải quyết tranh chấp Điều
                317, Luật Thương mại) KHÔNG trùng — máy chủ chưa có checklist
                cho hợp đồng thương mại. Việc mất chúng được ghi vào báo cáo
                pha, để chúng quay lại bằng đường đúng: một checklist ở
                `config/rules.yaml`, không phải một mảng trong JSX. */}

            <div className="flex items-center justify-between pb-6">
              <button
                type="button"
                disabled={buoc === 1}
                onClick={() => setBuoc((b) => Math.max(1, b - 1))}
                className="rounded-lg border border-border px-3.5 py-2 text-sm disabled:opacity-40"
              >
                Quay lại
              </button>
              <button
                type="button"
                disabled={buoc === 5}
                onClick={() => setBuoc((b) => Math.min(5, b + 1))}
                className="rounded-lg bg-[var(--color-brass-500)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
              >
                Bước tiếp theo
              </button>
            </div>
          </div>
        </div>

        {/* divider */}
        <div
          data-divider="1"
          className="drag-divider hidden w-1.5 shrink-0 bg-[var(--color-paper-200)] transition-colors hover:bg-[var(--color-brass-500)]/50 lg:block"
        />

        {/* RIGHT — preview */}
        <div
          className={cn(
            "min-w-0 flex-1 flex-col bg-[var(--color-paper-100)] lg:flex",
            pane === "xem" ? "flex" : "hidden",
          )}
        >
          <div className="flex flex-wrap items-center gap-2 border-b border-border bg-background/85 px-4 py-2">
            <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
              <button
                type="button"
                aria-label="Thu nhỏ"
                onClick={() => setZoom((z) => Math.max(0.4, +(z - 0.08).toFixed(2)))}
                className="rounded-md p-1.5 hover:bg-[var(--color-paper-100)]"
              >
                <Minus className="size-3.5" />
              </button>
              <span className="font-jetbrains w-12 text-center text-[11px]">
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                aria-label="Phóng to"
                onClick={() => setZoom((z) => Math.min(1.3, +(z + 0.08).toFixed(2)))}
                className="rounded-md p-1.5 hover:bg-[var(--color-paper-100)]"
              >
                <Plus className="size-3.5" />
              </button>
            </div>
            <label className="flex items-center gap-2 text-[12px]">
              <Toggle
                checked={chuThich}
                onChange={setChuThich}
                label="Hiển thị chú thích căn cứ pháp lý"
              />
              Hiển thị chú thích căn cứ pháp lý
            </label>
            <div className="ml-auto flex items-center gap-1">
              <button
                type="button"
                onClick={undo}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[12px] hover:bg-[var(--color-paper-100)]"
              >
                <Undo2 className="size-3.5" /> Hoàn tác
              </button>
              <button
                type="button"
                onClick={redo}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[12px] hover:bg-[var(--color-paper-100)]"
              >
                <Redo2 className="size-3.5" /> Làm lại
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-auto p-6">
            <div
              style={{
                width: 794 * zoom,
                height: "auto",
                margin: "0 auto",
              }}
            >
              <div
                ref={khungRef}
                style={{ transform: `scale(${zoom})`, transformOrigin: "top left", width: 794 }}
              >
                <A4
                  draft={draft}
                  mau={mau}
                  cauTruc={cauTruc}
                  dangTaiKhung={dangTaiKhung}
                  flash={flash}
                  chuThich={chuThich}
                  onGoto={(truong, buocDich) => {
                    setBuoc(buocDich);
                    setTimeout(() => focusField(truong), 60);
                  }}
                />
              </div>
            </div>
          </div>

          <div className="shrink-0 border-t border-border bg-background">
            <p className="px-4 pt-2 text-[12px] text-muted-foreground">
              Bản thảo do KLAW tạo ra là tài liệu tham khảo. Vui lòng để luật sư hoặc bộ phận pháp
              chế rà soát trước khi ký kết.
            </p>
            <div className="flex flex-wrap gap-2 px-4 py-2.5" aria-live="polite">
              {[
                {
                  l: dangXuat === "docx" ? "Đang tạo tệp Word…" : "Tải Word (.docx)",
                  i: FileDown,
                  onClick: () => void xuatTep("docx"),
                  busy: dangXuat === "docx",
                },
                {
                  l: dangXuat === "pdf" ? "Đang tạo tệp PDF…" : "Tải PDF",
                  i: Download,
                  onClick: () => void xuatTep("pdf"),
                  busy: dangXuat === "pdf",
                },
                {
                  l: "Sao chép toàn văn",
                  i: Copy,
                  onClick: () => void saoChepToanVan(),
                  busy: false,
                },
                // Hai nút dưới đây CHƯA DỰNG, và nói ra điều đó TRƯỚC khi bị
                // bấm chứ không sau. Trước đây chúng trông y hệt ba nút chạy
                // được rồi mới nhả một toast "sẽ khả dụng sau khi đăng nhập" —
                // câu đó còn sai chỗ nữa: thiếu không phải là đăng nhập, mà là
                // chỗ lưu bản thảo, thứ chưa tồn tại ở cả FE lẫn máy chủ.
                {
                  l: "Lưu bản thảo — chưa dựng",
                  i: Save,
                  onClick: () => undefined,
                  busy: false,
                  chuaDung: "KLAW chưa có nơi lưu bản thảo. Xuất tệp .docx hoặc .pdf để giữ lại.",
                },
                {
                  l: "Chia sẻ liên kết — chưa dựng",
                  i: Link2,
                  onClick: () => undefined,
                  busy: false,
                  chuaDung: "Bản thảo chỉ nằm trên máy bạn, nên chưa có liên kết nào để chia sẻ.",
                },
              ].map(({ l, i: Icon, onClick, busy, chuaDung }) => (
                <button
                  key={l}
                  type="button"
                  onClick={onClick}
                  title={chuaDung}
                  aria-description={chuaDung}
                  disabled={dangXuat !== null || chuaDung !== undefined}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[12.5px] transition-colors hover:bg-[var(--color-paper-100)] disabled:opacity-60"
                >
                  <Icon
                    className={cn(
                      "size-3.5 text-[var(--color-brass-600)]",
                      busy && "animate-pulse",
                    )}
                  />{" "}
                  {l}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

/* ------------------------------- sub-forms -------------------------------- */

function BenForm({
  nhan,
  ben,
  prefix,
  onChange,
}: {
  nhan: string;
  ben: Ben;
  prefix: "A" | "B";
  onChange: (patch: Partial<Ben>, key: string) => void;
}) {
  const k = (f: string) => `${prefix}.${f}`;

  return (
    <Group
      title={nhan}
      right={
        <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
          {(["to-chuc", "ca-nhan"] as BenLoai[]).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => onChange({ loai: l }, k("loai"))}
              className={cn(
                "rounded-md px-2.5 py-1 text-[11.5px] transition-colors",
                ben.loai === l
                  ? "bg-[var(--color-brass-500)]/15 text-[var(--color-brass-600)]"
                  : "text-muted-foreground",
              )}
            >
              {l === "to-chuc" ? "Tổ chức" : "Cá nhân"}
            </button>
          ))}
        </div>
      }
    >
      {ben.loai === "to-chuc" ? (
        <>
          <TextField
            name={k("tenToChuc")}
            label="Tên tổ chức"
            value={ben.tenToChuc}
            onChange={(v) => onChange({ tenToChuc: v }, k("tenToChuc"))}
            placeholder="Công ty TNHH …"
          />
          <TextField
            name={k("mst")}
            label="Mã số thuế"
            value={ben.mst}
            onChange={(v) => onChange({ mst: v }, k("mst"))}
          />
          <DiaChi ben={ben} onChange={onChange} k={k} nhanDiaChi="Địa chỉ trụ sở" />
          <div className="grid grid-cols-2 gap-3">
            <TextField
              name={k("nguoiDaiDien")}
              label="Người đại diện theo pháp luật"
              value={ben.nguoiDaiDien}
              onChange={(v) => onChange({ nguoiDaiDien: v }, k("nguoiDaiDien"))}
            />
            <TextField
              name={k("chucVu")}
              label="Chức vụ"
              value={ben.chucVu}
              onChange={(v) => onChange({ chucVu: v }, k("chucVu"))}
            />
          </div>
        </>
      ) : (
        <>
          <TextField
            name={k("hoTen")}
            label="Họ và tên"
            value={ben.hoTen}
            onChange={(v) => onChange({ hoTen: v }, k("hoTen"))}
          />
          <div className="grid grid-cols-2 gap-3">
            <TextField
              name={k("ngaySinh")}
              label="Ngày sinh"
              type="date"
              value={ben.ngaySinh}
              onChange={(v) => onChange({ ngaySinh: v }, k("ngaySinh"))}
            />
            <TextField
              name={k("cccd")}
              label="Số CCCD/Hộ chiếu"
              value={ben.cccd}
              onChange={(v) => onChange({ cccd: v }, k("cccd"))}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <TextField
              name={k("ngayCap")}
              label="Ngày cấp"
              type="date"
              value={ben.ngayCap}
              onChange={(v) => onChange({ ngayCap: v }, k("ngayCap"))}
            />
            <TextField
              name={k("noiCap")}
              label="Nơi cấp"
              value={ben.noiCap}
              onChange={(v) => onChange({ noiCap: v }, k("noiCap"))}
              placeholder="Cục Cảnh sát QLHC về TTXH"
            />
          </div>
          <DiaChi ben={ben} onChange={onChange} k={k} nhanDiaChi="Địa chỉ thường trú" />
        </>
      )}

      <div className="grid grid-cols-2 gap-3">
        <TextField
          name={k("dienThoai")}
          label="Điện thoại"
          value={ben.dienThoai}
          onChange={(v) => onChange({ dienThoai: v }, k("dienThoai"))}
        />
        <TextField
          name={k("email")}
          label="Email"
          value={ben.email}
          onChange={(v) => onChange({ email: v }, k("email"))}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <TextField
          name={k("soTaiKhoan")}
          label="Số tài khoản"
          value={ben.soTaiKhoan}
          onChange={(v) => onChange({ soTaiKhoan: v }, k("soTaiKhoan"))}
        />
        <TextField
          name={k("nganHang")}
          label="Ngân hàng"
          value={ben.nganHang}
          onChange={(v) => onChange({ nganHang: v }, k("nganHang"))}
        />
      </div>
    </Group>
  );
}

function DiaChi({
  ben,
  onChange,
  k,
  nhanDiaChi,
}: {
  ben: Ben;
  onChange: (patch: Partial<Ben>, key: string) => void;
  k: (f: string) => string;
  nhanDiaChi: string;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border bg-background p-3">
      <p className="text-[12px] font-medium text-muted-foreground">
        {nhanDiaChi} — đơn vị hành chính 2 cấp (từ 01/7/2025)
      </p>
      <div className="grid grid-cols-2 gap-3">
        <SelectField
          name={k("tinh")}
          label="Tỉnh/Thành phố"
          value={ben.tinh}
          onChange={(v) => onChange({ tinh: v, phuongXa: "" }, k("tinh"))}
          options={TINH_THANH.map((t) => t.ten)}
        />
        <SelectField
          name={k("phuongXa")}
          label="Phường/Xã/Đặc khu"
          value={ben.phuongXa}
          onChange={(v) => onChange({ phuongXa: v }, k("phuongXa"))}
          options={capDuoiCua(ben.tinh)}
          placeholder={ben.tinh ? "— Chọn —" : "Chọn tỉnh/thành trước"}
        />
      </div>
      <TextField
        name={k("soNhaDuong")}
        label="Số nhà, đường"
        value={ben.soNhaDuong}
        onChange={(v) => onChange({ soNhaDuong: v }, k("soNhaDuong"))}
        placeholder="Số 18 Duy Tân"
      />
    </div>
  );
}

function DieuKhoanRow({
  bat,
  onChange,
  ten,
  moTa,
  giaiThich,
  children,
}: {
  bat: boolean;
  onChange: (v: boolean) => void;
  ten: string;
  moTa: string;
  giaiThich: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-start gap-3">
        <Toggle checked={bat} onChange={onChange} label={ten} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="text-[13.5px] font-medium">{ten}</p>
            <InfoPopover>{giaiThich}</InfoPopover>
          </div>
          <p className="mt-0.5 text-[12px] text-muted-foreground">{moTa}</p>
        </div>
      </div>
      {children && <div className="mt-3 space-y-3 pl-12">{children}</div>}
    </div>
  );
}

/* ------------------------------ A4 preview -------------------------------- */

type MauT = NonNullable<ReturnType<typeof mauTheoId>>;

function A4({
  draft,
  mau,
  cauTruc,
  dangTaiKhung,
  flash,
  chuThich,
  onGoto,
}: {
  draft: Draft;
  mau: MauT;
  cauTruc: CauTruc | null;
  dangTaiKhung: boolean;
  flash: string | null;
  chuThich: boolean;
  onGoto: (truong: string, buoc: number) => void;
}) {
  const Ph = ({ k, label, buoc = 2 }: { k: string; label: string; buoc?: number }) => (
    <span className="ph-slot" onClick={() => onGoto(k, buoc)}>
      [{label}]
    </span>
  );

  const V = ({
    k,
    value,
    label,
    buoc = 2,
  }: {
    k: string;
    value: string;
    label: string;
    buoc?: number;
  }) =>
    value ? (
      <span className={cn(flash === k && "flash-brass")}>{value}</span>
    ) : (
      <Ph k={k} label={label} buoc={buoc} />
    );

  const diaChi = (b: Ben) => [b.soNhaDuong, b.phuongXa, b.tinh].filter(Boolean).join(", ");

  /**
   * Chưa có khung thì NÓI ra, không dựng bừa một khuôn nào khác.
   *
   * Đây chính là chỗ lỗi cũ sinh ra: khi không biết dựng gì, bộ dựng cũ rơi về
   * khuôn hợp đồng thương mại hai bên và in nó dưới tiêu đề CÔNG VĂN. Một khung
   * trống có lời giải thích thì người dùng sửa được; một bản hợp đồng sai loại
   * thì họ mang đi dùng.
   */
  if (!cauTruc) {
    return (
      <article className="a4-sheet">
        <div style={{ textAlign: "center" }}>
          <h1
            className="font-display"
            style={{ marginTop: 34, fontSize: 22, fontWeight: 700, textTransform: "uppercase" }}
          >
            {mau.ten}
          </h1>
        </div>
        <p style={{ marginTop: 28 }}>
          {dangTaiKhung
            ? "Đang tải bộ khung của loại văn bản này từ máy chủ…"
            : "Chưa lấy được bộ khung của loại văn bản này từ máy chủ, nên khung xem trước để trống. Bộ khung quyết định văn bản gồm những mục nào và mỗi mục dựa trên điều luật nào — dựng thân văn bản mà thiếu nó thì bản thảo sẽ sai loại. Kiểm tra kết nối rồi tải lại trang."}
        </p>
      </article>
    );
  }

  const muc = dungKhung(cauTruc);

  const khoiBen = (p: "A" | "B") => {
    const b = draft[p];
    return (
      <>
        {b.loai === "to-chuc" ? (
          <>
            <p>
              Tên tổ chức: <V k={`${p}.tenToChuc`} value={b.tenToChuc} label="Tên tổ chức" />
            </p>
            <p>
              Mã số thuế: <V k={`${p}.mst`} value={b.mst} label="Mã số thuế" />
            </p>
            <p>
              Địa chỉ trụ sở: <V k={`${p}.soNhaDuong`} value={diaChi(b)} label="Địa chỉ trụ sở" />
            </p>
            <p>
              Người đại diện theo pháp luật:{" "}
              <V k={`${p}.nguoiDaiDien`} value={b.nguoiDaiDien} label="Người đại diện" /> — Chức vụ:{" "}
              <V k={`${p}.chucVu`} value={b.chucVu} label="Chức vụ" />
            </p>
          </>
        ) : (
          <>
            <p>
              Họ và tên: <V k={`${p}.hoTen`} value={b.hoTen} label="Họ và tên" />
            </p>
            <p>
              Sinh ngày: <V k={`${p}.ngaySinh`} value={ngayVietNam(b.ngaySinh)} label="Ngày sinh" />{" "}
              — CCCD/Hộ chiếu số: <V k={`${p}.cccd`} value={b.cccd} label="Số CCCD" />, cấp ngày{" "}
              <V k={`${p}.ngayCap`} value={ngayVietNam(b.ngayCap)} label="Ngày cấp" /> tại{" "}
              <V k={`${p}.noiCap`} value={b.noiCap} label="Nơi cấp" />
            </p>
            <p>
              Địa chỉ thường trú:{" "}
              <V k={`${p}.soNhaDuong`} value={diaChi(b)} label="Địa chỉ thường trú" />
            </p>
          </>
        )}
        <p>
          Điện thoại: <V k={`${p}.dienThoai`} value={b.dienThoai} label="Điện thoại" /> — Email:{" "}
          <V k={`${p}.email`} value={b.email} label="Email" />
        </p>
      </>
    );
  };

  const khoiND = (phan: PhanND): React.ReactNode => {
    switch (phan) {
      case "cong_viec":
        return (
          <>
            <p>
              Vị trí công việc:{" "}
              <V k="nd.tenDichVu" value={draft.nd.tenDichVu} label="Vị trí công việc" buoc={3} />.
            </p>
            <p>
              Địa điểm làm việc:{" "}
              <V k="nd.diaDiem" value={draft.nd.diaDiem} label="Địa điểm làm việc" buoc={3} />.
            </p>
          </>
        );
      case "dich_vu":
        return (
          <>
            <p>
              Bên cung ứng thực hiện:{" "}
              <V k="nd.tenDichVu" value={draft.nd.tenDichVu} label="Tên dịch vụ" buoc={3} />.
            </p>
            <p>
              Phạm vi công việc:{" "}
              <V k="nd.phamVi" value={draft.nd.phamVi} label="Phạm vi công việc" buoc={3} />
            </p>
            <p>
              Địa điểm thực hiện:{" "}
              <V k="nd.diaDiem" value={draft.nd.diaDiem} label="Địa điểm thực hiện" buoc={3} />.
            </p>
          </>
        );
      case "thoi_han":
        return (
          <p>
            Từ ngày{" "}
            <V k="nd.tuNgay" value={ngayVietNam(draft.nd.tuNgay)} label="ngày bắt đầu" buoc={3} />{" "}
            đến ngày{" "}
            <V
              k="nd.denNgay"
              value={ngayVietNam(draft.nd.denNgay)}
              label="ngày kết thúc"
              buoc={3}
            />
            .
          </p>
        );
      case "thu_viec":
        return (
          <p>
            Thời gian thử việc:{" "}
            <V
              k="nd.soNgayThuViec"
              value={draft.nd.soNgayThuViec ? `${draft.nd.soNgayThuViec} ngày` : ""}
              label="số ngày thử việc"
              buoc={3}
            />
            .
          </p>
        );
      case "luong": {
        const luong = draft.nd.luongChinhThuc;
        const thu = draft.nd.luongThuViec;
        return (
          <>
            <p>
              Mức lương:{" "}
              <V
                k="nd.luongChinhThuc"
                value={luong === "" ? "" : `${dinhDangTien(luong)} đồng/tháng`}
                label="mức lương"
                buoc={3}
              />
              .
            </p>
            {thu !== "" && <p>Mức lương thử việc: {dinhDangTien(thu)} đồng/tháng.</p>}
          </>
        );
      }
      case "tien":
        return (
          <>
            <p>
              Tổng giá trị:{" "}
              <V
                k="nd.giaTri"
                value={draft.nd.giaTri === "" ? "" : dinhDangTien(draft.nd.giaTri)}
                label="giá trị hợp đồng"
                buoc={3}
              />
              {draft.nd.giaTri !== "" && (
                <> (Bằng chữ: {docSoThanhChu(Number(draft.nd.giaTri))}) </>
              )}
              , thuế GTGT <V k="nd.thueGTGT" value={draft.nd.thueGTGT} label="Thuế GTGT" buoc={3} />
              .
            </p>
            <p>Thanh toán theo các đợt sau:</p>
            {draft.nd.dot.map((d, i) => (
              <p key={d.id} style={{ marginLeft: 32 }}>
                {i + 1}. {d.tyLe || "…"}% giá trị — {d.moc || "…"}
              </p>
            ))}
          </>
        );
      default: {
        // Thêm một `PhanND` mà quên viết khối hiển thị cho nó là LỖI BIÊN DỊCH
        // ở đây, không phải một mục lặng lẽ trống trên bản thảo tải về.
        const chuaXuLy: never = phan;
        return chuaXuLy;
      }
    }
  };

  const nguoiKy = draft.A.loai === "to-chuc" ? draft.A.nguoiDaiDien : draft.A.hoTen;

  return (
    <article className="a4-sheet">
      <div style={{ textAlign: "center" }}>
        <h1
          className="font-display"
          style={{ marginTop: 8, fontSize: 22, fontWeight: 700, textTransform: "uppercase" }}
        >
          {cauTruc.tieu_de}
        </h1>
        <p className="font-jetbrains" style={{ fontSize: 13, marginTop: 6 }}>
          Số: …/{mau.kyHieu}
        </p>
      </div>

      {muc.map((m) => {
        const ben = MUC_BEN[m.key];
        const phan = MUC_ND[m.key];
        const laKy = MUC_KY.has(m.key);
        return (
          <div key={m.key} style={{ position: "relative", marginTop: 14 }}>
            <p className="dieu-head">
              <span style={{ color: "var(--color-brass-600)" }}>
                {cauTruc.don_vi_muc} {m.stt}.
              </span>{" "}
              {m.ten}
            </p>

            {ben !== undefined && khoiBen(ben)}
            {phan !== undefined && khoiND(phan)}
            {laKy && (
              <div data-xuat="ky" style={{ marginTop: 10 }}>
                <div style={{ width: "45%", marginLeft: "auto", textAlign: "center" }}>
                  <p style={{ fontStyle: "italic", fontSize: 13 }}>(Ký, ghi rõ họ tên, đóng dấu)</p>
                  <p style={{ marginTop: 60, fontWeight: 700 }}>{nguoiKy || "…………………"}</p>
                </div>
              </div>
            )}
            {ben === undefined && phan === undefined && !laKy && (
              <p>
                <Ph k={`muc.${m.key}`} label={`nội dung mục “${m.ten}”`} buoc={3} />
              </p>
            )}

            {chuThich && m.canCu && (
              <p style={{ marginTop: 4 }}>
                <BasisChip soHieu={m.canCu.soHieu} label={m.canCu.nhan} />
              </p>
            )}
          </div>
        );
      })}
    </article>
  );
}

/* --------------------------------- logic ---------------------------------- */

function tongTyLe(dot: Dot[]) {
  return dot.reduce((s, d) => s + (Number(d.tyLe) || 0), 0);
}

function demDieuKhoan(dk: DieuKhoan) {
  return [
    dk.phat,
    dk.boiThuong,
    dk.baoMat,
    dk.batKhaKhang,
    dk.chamDutTruocHan,
    dk.sohuuTriTue,
    dk.tranhChap,
    dk.hieuLuc,
  ].filter(Boolean).length;
}

function demTrong(d: Draft, laLaoDong: boolean) {
  const ben = (b: Ben) =>
    b.loai === "to-chuc"
      ? [b.tenToChuc, b.mst, b.soNhaDuong, b.tinh, b.phuongXa, b.nguoiDaiDien, b.chucVu]
      : [b.hoTen, b.cccd, b.soNhaDuong, b.tinh, b.phuongXa];
  const nd = [d.nd.tenDichVu, d.nd.phamVi, String(d.nd.giaTri), d.nd.thueGTGT, d.nd.diaDiem];
  const ld = laLaoDong ? [d.nd.chucDanh, d.nd.soNgayThuViec] : [];
  return [...ben(d.A), ...ben(d.B), ...nd, ...ld].filter((v) => !v || v === "").length;
}

/**
 * Năm dòng hằng, chèn tên dịch vụ vào dòng đầu. Không có mô hình nào ở đây, nên
 * nút gọi nó cũng không được gắn nhãn AI.
 */
function goiYPhamVi(ten: string) {
  const t = ten || "dịch vụ theo yêu cầu của Bên A";
  return [
    `1. Khảo sát hiện trạng và thống nhất yêu cầu chi tiết đối với ${t}.`,
    "2. Xây dựng kế hoạch triển khai, phân công nhân sự phụ trách và mốc thời gian cụ thể.",
    "3. Thực hiện công việc theo kế hoạch đã duyệt, báo cáo tiến độ định kỳ hằng tuần.",
    "4. Bàn giao sản phẩm, tài liệu hướng dẫn và nghiệm thu theo biên bản có chữ ký hai bên.",
    "5. Hỗ trợ, bảo hành trong 30 ngày kể từ ngày nghiệm thu.",
  ].join("\n");
}
