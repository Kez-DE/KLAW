/**
 * Tải tài liệu lên và xem dữ kiện rút được (spec 2026-09-15).
 *
 * Lời hứa component này phải giữ: **mỗi dòng nói rõ nó đến từ đâu.** Chữ đọc
 * thẳng từ tệp, chữ máy đoán từ ảnh, và chữ người dùng tự gõ là ba hạng bằng
 * chứng khác nhau. Người dùng sắp đưa những con số này vào một văn bản pháp lý,
 * nên gộp ba hạng thành một bảng phẳng là để giao diện hứa nhiều hơn thứ nó giữ
 * được — cùng lỗi mà `KhungDoiChieu` tồn tại để không mắc với trích dẫn điều luật.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Eye, FilePen, FileText, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { BangDuKien } from "@/components/klaw/DongDuKien";
import {
  nhanNeo,
  nhanVung,
  type DonVi,
  type DonViTaiLieu,
  type DuKien,
  type TaiLieu,
} from "@/lib/tai-lieu";
import { chiTiet, docLai, donVi, sangSoanThao, suaDuKien, xoaDuKien } from "@/lib/tai-lieu-api";
import { LOAI_BACKEND, MAU } from "@/lib/mau-van-ban";
import { cn } from "@/lib/utils";
import type { ApiError } from "@/lib/klaw";

interface Props {
  /** `null` khi chưa đăng nhập hoặc chưa có cuộc trò chuyện — nút bị vô hiệu. */
  hoiThoaiId: string | null;
  /**
   * Loại văn bản đang soạn, theo mã backend. `null` thì người dùng tự chọn ở
   * đây: rút dữ kiện cần biết rút TRƯỜNG GÌ, nhưng bắt họ mở khung soạn thảo
   * trước mới được đính kèm là một ngõ cụt — họ đang cầm tờ giấy trong tay.
   */
  loai: string | null;
  /** Gọi sau khi dữ kiện đã được đưa sang soạn thảo. */
  onDaDungDeSoan?: () => void;
  /** Đóng khung. `undefined` khi khung không tự đóng được (đặt cố định). */
  onDong?: (() => void) | undefined;
  /** Mở "Bản tải lên" (tệp đúng như đã tải lên) trên sân khấu. Chỉ hiện khi
   *  tài liệu có khuôn gốc (`co_khuon_goc`). */
  onMoBanTaiLen?:
    ((taiLieu: { id: string; ten_tep: string; so_trang: number | null }) => void) | undefined;
  /** "Điền biểu mẫu": mở bảng ô điền trên khuôn gốc của tài liệu này. */
  onDienBieuMau?: ((viecId: string) => void) | undefined;
  /** Điền một câu vào ô hỏi (chip câu hỏi đầu tiên). KHÔNG tự gửi. */
  onChip?: ((chu: string) => void) | undefined;
  /** Neo vừa bấm ở thẻ kết quả: mở đúng tài liệu đó và tô đúng đơn vị đó. */
  donViDangMo?: { taiLieuId: string; chiSo: number | null } | null;
}

/** Ba câu hỏi đầu tiên cho một tài liệu chưa biết dùng để làm gì. Chúng phải
 *  chạy được với MỌI tài liệu, nên không câu nào nhắc tới một loại văn bản. */
const CAU_HOI_DAU = ["Tài liệu này nói gì?", "Tóm tắt các mục chính", "Tìm chỗ còn trống"];

/** Loại văn bản chọn được: chỉ những mẫu đã nối backend mới rút dữ kiện được. */
const LOAI_CHON_DUOC = MAU.flatMap((m) => {
  const loai = LOAI_BACKEND[m.id]?.loai;
  return loai ? [{ loai, ten: m.ten }] : [];
}).filter((x, i, ds) => ds.findIndex((y) => y.loai === x.loai) === i);

const CHIP =
  "focus-brass cursor-pointer rounded-full border border-border bg-card px-3 py-1 text-[13px] text-foreground hover:bg-[var(--color-paper-100)]";

const NUT_KHUON =
  "focus-brass inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium text-primary hover:bg-[var(--color-paper-100)]";

export function TaiLieuDuKien({
  hoiThoaiId,
  loai,
  onDaDungDeSoan,
  onDong,
  onMoBanTaiLen,
  onDienBieuMau,
  onChip,
  donViDangMo,
}: Props) {
  const oTep = useRef<HTMLInputElement | null>(null);
  const [tep, datTep] = useState<TaiLieu | null>(null);
  const [dangKeo, datDangKeo] = useState(false);
  const [dangSua, datDangSua] = useState<string | null>(null);
  const [dangDung, datDangDung] = useState(false);
  // Gọi tay chứ không qua `useGoiApi`: hook đó đẩy kết quả vào state của chính
  // nó, còn ở đây phải phản ứng NGAY với kết quả (đóng toast, đếm dữ kiện).
  // Cùng khuôn `DanhSachPhien.tsx`.
  const [dangTai, datDangTai] = useState(false);
  const [loiTai, datLoiTai] = useState<ApiError | null>(null);
  const [loaiChon, datLoaiChon] = useState<string>("");
  const [doiLoai, datDoiLoai] = useState(false);
  /** Nguyên văn đã đọc của tài liệu đang xem — nền của danh sách đơn vị và của
   *  mọi neo bấm được. Tách khỏi `tep` vì neo có thể trỏ tới một tài liệu của
   *  lượt TRƯỚC, khi khung này chưa từng tải lên gì trong lần mở hiện tại. */
  const [banDoc, datBanDoc] = useState<DonViTaiLieu | null>(null);
  const oDonViDangMo = useRef<HTMLLIElement | null>(null);
  /** Tài liệu `tep` đang mô tả — để không xin lại chi tiết của chính nó. */
  const tepIdHienTai = useRef<string | null>(null);
  tepIdHienTai.current = tep?.id ?? null;

  const loaiDung = loai ?? (loaiChon || null);
  const san = hoiThoaiId !== null && loaiDung !== null;

  /**
   * Rút lại theo loại vừa chọn trên CHÍNH việc đọc đã lưu (`POST …/doc-lai`):
   * không tải tệp lên lần hai, không mở việc mới, không trừ hạn mức ngày — nên
   * không cần giữ `File` nào trong bộ nhớ, và chạy được cả với tài liệu mở từ
   * một lượt trước. 409/429/422 mang câu tiếng Việt của máy chủ.
   */
  const rutLai = useCallback(
    async (viecId: string) => {
      if (loaiDung === null) return;
      const id = toast.loading("Đang rút dữ kiện theo mẫu…");
      datDangTai(true);
      datLoiTai(null);
      const kq = await docLai(viecId, loaiDung);
      datDangTai(false);
      if (!kq.ok) {
        datLoiTai(kq.error);
        toast.error(kq.error.message, { id });
        return;
      }
      datTep(kq.data);
      const n = kq.data.du_kien.length;
      toast.success(
        kq.data.loai === null
          ? "Đọc xong tài liệu. Bạn hỏi gì về nó cũng được."
          : n > 0
            ? `Đọc xong, rút được ${n} dữ kiện.`
            : "Đọc xong, không rút được dữ kiện nào.",
        { id },
      );
    },
    [loaiDung],
  );

  // Người dùng vừa chọn loại: rút lại chính tài liệu đó với loại đã chọn.
  // `tep.loai === null` là đường mới (tài liệu ngoài mẫu, đã đọc xong) — họ vẫn
  // rút được dữ kiện theo mẫu, chỉ là bằng một lựa chọn chứ không bằng một cửa
  // chắn. Chỉ chạy theo `loaiChon`: rút phải là việc người dùng vừa yêu cầu,
  // không phải một phản ứng với state.
  useEffect(() => {
    if (
      loaiChon &&
      tep &&
      (tep.trang_thai === "can_chon_loai" || doiLoai || tep.du_kien.length === 0)
    ) {
      datDoiLoai(false);
      void rutLai(tep.id);
    }
    // `rutLai` đọc `loaiDung`, vốn đã bao gồm `loaiChon`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaiChon]);

  /**
   * Tài liệu đang cần nguyên văn: cái neo vừa bấm trỏ tới, hoặc cái vừa đọc
   * xong mà không khớp mẫu nào (lúc đó danh sách đơn vị LÀ nội dung của khung).
   */
  const idCanDoc =
    donViDangMo?.taiLieuId ??
    // `trang_thai === "xong"` là bắt buộc: bản ghi CŨ dừng ở `can_chon_loai`
    // không có nguyên văn nào để lấy — gọi `/don-vi` cho chúng chỉ đổi lấy một
    // 404 và một toast vô cớ.
    (tep !== null && tep.trang_thai === "xong" ? tep.id : null);

  useEffect(() => {
    if (idCanDoc === null) return;
    let boQua = false;
    void donVi(idCanDoc).then((kq) => {
      if (boQua) return;
      if (kq.ok) datBanDoc(kq.data);
      // Không dựng một khung trống im lặng: đọc được tài liệu mà không lấy được
      // nguyên văn là một việc người dùng phải biết để còn bấm lại.
      else toast.error(kq.error.message);
    });
    // Dữ kiện của tài liệu đó, khi khung mở từ một con chip chứ không từ một
    // lần tải lên. Lỗi ở đây IM LẶNG có chủ đích: nguyên văn ở trên mới là nội
    // dung của khung, và một tài liệu chưa ai hỏi tới thì chưa có dữ kiện nào.
    if (idCanDoc !== tepIdHienTai.current)
      void chiTiet(idCanDoc).then((kq) => {
        if (!boQua && kq.ok) datTep(kq.data);
      });
    return () => {
      boQua = true;
    };
  }, [idCanDoc]);

  // Neo vừa bấm: kéo đúng đơn vị đó vào giữa màn. Chạy sau khi nguyên văn về,
  // nên `banDoc` nằm trong danh sách phụ thuộc.
  useEffect(() => {
    if (donViDangMo) oDonViDangMo.current?.scrollIntoView({ block: "center" });
  }, [donViDangMo, banDoc]);

  const sua = async (dk: DuKien, giaTri: string) => {
    if (!dk.id || giaTri === dk.gia_tri) return;
    datDangSua(dk.id);
    const kq = await suaDuKien(dk.id, giaTri);
    datDangSua(null);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return;
    }
    datTep((t) =>
      t ? { ...t, du_kien: t.du_kien.map((x) => (x.id === dk.id ? kq.data : x)) } : t,
    );
  };

  const xoa = async (dk: DuKien) => {
    if (!dk.id) return;
    const kq = await xoaDuKien(dk.id);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return;
    }
    datTep((t) => (t ? { ...t, du_kien: t.du_kien.filter((x) => x.id !== dk.id) } : t));
  };

  const dungDeSoan = async () => {
    if (!san) return;
    datDangDung(true);
    const kq = await sangSoanThao(hoiThoaiId, loaiDung, true);
    datDangDung(false);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return;
    }
    const thieu = kq.data.con_thieu.length;
    toast.success(
      thieu === 0
        ? "Đã đưa dữ kiện sang soạn thảo. Không còn trường bắt buộc nào trống."
        : `Đã đưa dữ kiện sang soạn thảo. Còn ${thieu} trường bắt buộc cần bạn điền.`,
    );
    onDaDungDeSoan?.();
  };

  // Bản ghi CŨ (trước 2026-09-16) còn dừng ở `can_chon_loai`; bản mới không bao
  // giờ tới đó nữa. Giữ nhánh này để một lượt đã lưu vẫn mở lại được.
  const canChonLoai = loai === null && (tep?.trang_thai === "can_chon_loai" || doiLoai);
  /**
   * Đọc xong nhưng CHƯA rút dữ kiện theo mẫu nào — đường đi CHÍNH từ 2026-09-16.
   *
   * Không còn hỏi `tep.loai === null`: từ 2026-09-17 đính kèm không rút dữ kiện
   * nữa, kể cả khi hệ thống tự nhận ra loại văn bản. Thứ quyết định màn hình này
   * hiện gì là CÓ DỮ KIỆN HAY KHÔNG, không phải có đoán ra loại hay không.
   */
  const ngoaiMau =
    loai === null &&
    tep !== null &&
    tep.trang_thai === "xong" &&
    tep.du_kien.length === 0 &&
    !doiLoai;

  /**
   * Dòng dưới tên tệp. Nó là chỗ agent nói ra nó ĐÃ HIỂU tài liệu là gì —
   * `docs/bo-luat-agent.md` QT-5: giả định phải hiện thành chữ và sửa được một
   * chạm, chứ không nằm im trong đầu hệ thống.
   */
  const phuDe = dangTai
    ? "Đang đọc…"
    : tep?.trang_thai === "can_chon_loai"
      ? "Chưa nhận ra loại văn bản"
      : tep?.loai_ten
        ? tep.loai_tu_doan
          ? `${tep.loai_ten} · tự nhận ra`
          : tep.loai_ten
        : (tep?.mo_ta ?? "Tệp");

  /** Tên tài liệu đang xem: từ `/don-vi`, hoặc từ chi tiết khi nguyên văn chưa về. */
  const tenHienThi = banDoc?.ten_tep || tep?.ten_tep || null;
  const soDonVi = banDoc !== null ? banDoc.don_vi.length : (tep?.so_don_vi ?? 0);
  const soTrang = banDoc?.so_trang ?? tep?.so_trang ?? null;
  /** Nguyên văn nhóm theo trang, đúng thứ tự tài liệu. */
  const trangDaDoc = [
    ...(banDoc?.don_vi ?? [])
      .reduce((gom, dv) => {
        const cu = gom.get(dv.trang);
        if (cu) cu.push(dv);
        else gom.set(dv.trang, [dv]);
        return gom;
      }, new Map<number | null, DonVi[]>())
      .entries(),
  ];

  /** Ô chọn loại văn bản — dùng ở CẢ hai chỗ, nên chỉ có một bản mã. */
  const oChonLoai = (nhan: string) => (
    <label className="block text-xs">
      <span className="mb-1 block text-muted-foreground">{nhan}</span>
      <select
        value={loaiChon}
        onChange={(e) => datLoaiChon(e.target.value)}
        className="focus-brass min-h-11 w-full rounded border border-border bg-background px-2 text-sm"
      >
        <option value="">— Chọn loại văn bản —</option>
        {LOAI_CHON_DUOC.map((x) => (
          <option key={x.loai} value={x.loai}>
            {x.ten}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <section
      aria-label="Tài liệu và dữ kiện"
      className="rounded-lg border border-border bg-[var(--color-paper-50)] p-4"
    >
      {/* Đặt trong drawer ("Dữ kiện đã đọc") thì drawer đã có tiêu đề và nút
          đóng — không lặp lại hàng này. */}
      {onDong && (
        <div className="mb-3 flex items-center gap-2">
          <h2 className="flex flex-1 items-center gap-2 text-sm font-semibold">
            <FileText aria-hidden className="size-4" />
            Đọc dữ kiện từ tài liệu
          </h2>
          <button
            type="button"
            aria-label="Đóng khung đính kèm tài liệu"
            onClick={onDong}
            className="focus-brass grid size-11 place-items-center rounded border border-border"
          >
            <X aria-hidden className="size-4" />
          </button>
        </div>
      )}

      {tenHienThi !== null && (
        <div className="mb-3 flex items-center gap-3 rounded-xl border border-border bg-background px-3 py-2.5">
          <FileText aria-hidden className="size-5 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium" title={tenHienThi}>
              {tenHienThi}
            </span>
            <span className="block truncate text-xs text-muted-foreground">{phuDe}</span>
          </span>
          {dangTai && <Loader2 aria-hidden className="size-4 shrink-0 animate-spin" />}
          {tep?.loai_ten && !doiLoai && (
            <button
              type="button"
              onClick={() => datDoiLoai(true)}
              className="focus-brass shrink-0 rounded px-2 py-1 text-xs text-muted-foreground underline"
            >
              Đổi
            </button>
          )}
        </div>
      )}

      {/* Khuôn gốc (quyết định 2026-09-26): tệp được giữ nguyên, nên xem được
          đúng như đã tải lên và điền được tại chỗ. "Bản tải lên", không phải
          "bản gốc" — chữ đó là nguyên văn luật (`CONTEXT.md`). */}
      {tep?.co_khuon_goc === true && (onMoBanTaiLen || onDienBieuMau) && (
        <div className="mb-3 flex flex-wrap gap-2">
          {onMoBanTaiLen && (
            <button
              type="button"
              onClick={() =>
                onMoBanTaiLen({ id: tep.id, ten_tep: tep.ten_tep, so_trang: tep.so_trang })
              }
              className={NUT_KHUON}
            >
              <Eye aria-hidden className="size-4 text-[var(--color-brass-600)]" />
              Bản tải lên
            </button>
          )}
          {onDienBieuMau && (
            <button type="button" onClick={() => onDienBieuMau(tep.id)} className={NUT_KHUON}>
              <FilePen aria-hidden className="size-4 text-[var(--color-brass-600)]" />
              Điền biểu mẫu
            </button>
          )}
        </div>
      )}

      {canChonLoai && (
        <div className="mb-3">
          {oChonLoai(
            tep?.trang_thai === "can_chon_loai"
              ? "Chưa nhận ra tài liệu này thuộc loại nào. Bạn định soạn văn bản gì?"
              : "Đổi loại văn bản:",
          )}
        </div>
      )}

      {hoiThoaiId === null && (
        <p className="mb-3 text-xs text-muted-foreground">
          Cần đăng nhập và có một cuộc trò chuyện để đọc tài liệu.
        </p>
      )}

      {loiTai && (
        <div className="mt-3">
          <BaoLoi loi={loiTai} />
        </div>
      )}

      {tep?.co_ocr && (
        <p
          role="status"
          className="mt-3 border-l-4 px-3 py-2 text-xs"
          style={{ borderLeftColor: "var(--color-status-warn, #9a6b00)" }}
        >
          Tài liệu này được đọc bằng nhận dạng chữ từ ảnh. Chữ máy đọc ra không phải chữ gốc của tài
          liệu — hãy đối chiếu trước khi dùng.
        </p>
      )}

      {/* Đọc xong một tài liệu ngoài 29 mẫu. Câu đầu tiên phải nói máy ĐÃ LÀM
          ĐƯỢC GÌ ("đã đọc 34 đơn vị · 1 trang"), không nói nó KHÔNG nhận ra cái
          gì: người dùng vừa đưa một tờ giấy hợp lệ, và một lời từ chối ở đây là
          sai sự thật — nội dung đã nằm sẵn trong hội thoại, hỏi là trả lời được. */}
      {(ngoaiMau || banDoc !== null) && (
        <div className="mt-3 rounded-lg border border-border bg-background p-3">
          <p className="m-0 text-sm font-medium">
            Đã đọc {soDonVi} đơn vị{soTrang !== null && ` · ${soTrang} trang`}
          </p>
          {tep?.mo_ta && <p className="mt-1 mb-0 text-xs text-muted-foreground">{tep.mo_ta}</p>}
          {onChip && (
            <div className="mt-2 flex flex-wrap gap-2">
              {CAU_HOI_DAU.map((cau) => (
                <button key={cau} type="button" onClick={() => onChip(cau)} className={CHIP}>
                  {cau}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {trangDaDoc.length > 0 && (
        <section aria-label="Nội dung đã đọc" className="mt-3">
          <h3 className="m-0 text-xs text-muted-foreground">Nội dung đã đọc</h3>
          <ul className="mt-2 space-y-3">
            {trangDaDoc.map(([trang, dsDonVi]) => (
              <li key={trang ?? "khac"}>
                <p className="mb-1 text-xs text-muted-foreground">
                  {trang === null ? "Không thuộc trang nào" : `Trang ${trang}`}
                </p>
                <ul className="space-y-1.5">
                  {dsDonVi.map((dv) => {
                    const dangMo =
                      donViDangMo !== null &&
                      donViDangMo !== undefined &&
                      donViDangMo.chiSo === dv.chi_so &&
                      donViDangMo.taiLieuId === banDoc?.id;
                    return (
                      <li
                        key={dv.chi_so}
                        ref={dangMo ? oDonViDangMo : null}
                        {...(dangMo ? { "aria-current": "true" as const } : {})}
                        className={cn(
                          "rounded-md border bg-background p-2.5",
                          dangMo
                            ? "border-[var(--ring)] ring-2 ring-[var(--ring)]"
                            : "border-border",
                        )}
                      >
                        <p className="m-0 flex flex-wrap items-center gap-2 font-jetbrains text-[11px] text-muted-foreground">
                          <span>{nhanNeo({ ...dv, chi_so_don_vi: dv.chi_so })}</span>
                          {dv.vung !== "than" && <span>{nhanVung(dv.vung)}</span>}
                          {dv.nguon_chu === "ocr" && (
                            <span style={{ color: "var(--color-status-warn, #9a6b00)" }}>
                              máy đọc từ ảnh
                              {dv.do_tin !== null && ` · ${Math.round(dv.do_tin * 100)}%`}
                            </span>
                          )}
                        </p>
                        <p className="mt-1 mb-0 text-[13px] leading-6 whitespace-pre-wrap">
                          {dv.noi_dung}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Rút dữ kiện theo mẫu vẫn còn nguyên, chỉ thôi đứng chắn đường: nó là
          MỘT việc làm được với tài liệu, không phải cửa vào. */}
      {ngoaiMau && (
        <details className="mt-3 rounded-lg border border-border bg-background p-3">
          <summary className="focus-brass cursor-pointer text-sm">Rút dữ kiện theo mẫu</summary>
          <p className="mt-2 mb-2 text-xs text-muted-foreground">
            Chọn loại văn bản bạn định soạn, KLAW đọc lại tài liệu và rút đúng những trường loại đó
            cần.
          </p>
          {oChonLoai("Loại văn bản:")}
        </details>
      )}

      {tep && tep.du_kien.length === 0 && !ngoaiMau && (
        <p className="mt-3 text-sm text-muted-foreground">
          Không rút được dữ kiện nào từ tài liệu này. Có thể tài liệu không chứa các thông tin mà
          loại văn bản đang soạn cần.
        </p>
      )}

      {(tep?.du_kien.length ?? 0) > 0 && (
        <>
          <BangDuKien
            duKien={tep?.du_kien ?? []}
            onSua={(dk, giaTri) => void sua(dk, giaTri)}
            onXoa={(dk) => void xoa(dk)}
            dangSua={dangSua}
          />

          <button
            type="button"
            disabled={dangDung}
            onClick={() => void dungDeSoan()}
            className="focus-brass mt-3 inline-flex min-h-11 items-center gap-2 rounded-md border border-border px-4 disabled:opacity-50"
          >
            {dangDung && <Loader2 aria-hidden className="size-4 animate-spin" />}
            Dùng dữ kiện này để soạn thảo
          </button>
        </>
      )}
    </section>
  );
}
