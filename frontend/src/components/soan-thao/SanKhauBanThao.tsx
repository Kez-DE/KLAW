import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, Download, FileDown, X } from "lucide-react";
import { Toggle } from "@/components/draft/DraftBits";
import { BadgeHieuLuc } from "@/components/klaw/BadgeHieuLuc";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { NoiDungDieuKhoan } from "@/components/klaw/NoiDungDieuKhoan";
import { NganXepDrawer } from "@/components/ui/NganXepDrawer";
import { TayKeo } from "@/components/ui/TayKeo";
import { useDoiChieu } from "@/hooks/use-doi-chieu";
import { dungLaiBanThao, suaMucBanThao, suaODien, taiAnhNguon, taiXuongBanThao } from "@/lib/api";
import { docRongDaLuu, kepRong, luuRong, type Bien } from "@/lib/keo-dan";
import {
  boDaGui,
  CAU_MAY_BAN,
  chiGiuThayDoi,
  DUONG_DAN_KHUON,
  giaTriHienThi,
  khoaO,
  NGHI_DUNG_TRANG_MS,
  oDaDoi,
  type ODienGui,
} from "@/lib/khuon-goc";
import {
  khuonHopLe,
  LOAI_TONG_QUAT,
  neenGuiLaiPhienBan,
  nhanFactDoi,
  nhanMucKiem,
  type BanThao,
  type CauTruc,
  type OTrang,
  type TruongFact,
} from "@/lib/klaw";
import { dongTrenCung, moTam, type Tam } from "@/lib/ngan-xep-drawer";
import {
  anhTuBanThao,
  canCuTuBanThao,
  leTrangTuBanThao,
  mucTuBanThao,
  taiBlob,
  tenTepAnToan,
  tieuDeTuBanThao,
} from "@/lib/xuat-tep";
import { cn } from "@/lib/utils";
import { DrawerSuaMuc } from "./DrawerSuaMuc";
import { KhungTrangAnh, NutChuaDinhVi, ThanhThuPhong, type DienTaiCho } from "./KhungTrangAnh";
import { XemTruocA4 } from "./XemTruocA4";

/**
 * Best-effort: tra `can_cu` (chuỗi `duong_dan` của MỤC checklist) trong các
 * `findings` mà `/soat` đã kèm SẴN trong `banThao.audit_report` — CHỈ những
 * `can_cu` gắn với một phát hiện thật (thiếu nội dung, trái luật…) mang theo
 * `doc_id`/`khop_tai_id` đã được máy chủ tra sẵn (`ban_thao._finding_out`).
 * Đa số mục soát sạch không có phát hiện nào khớp — khi đó trả `null`, và
 * tấm "Căn cứ" chỉ hiện đường dẫn dạng chữ, không giả vờ mở được nguyên văn.
 * ponytail: không có endpoint tra `duong_dan` → id cho MỌI mục (chỉ có cho
 * mục đang mắc lỗi); dựng thêm endpoint đó là việc của một task khác.
 */
function timCanCuKhaDung(
  auditReport: Record<string, unknown>,
  canCu: string,
): { docId: string; khopTaiId: number } | null {
  const findings = auditReport["findings"];
  if (!Array.isArray(findings)) return null;
  for (const f of findings) {
    if (typeof f !== "object" || f === null) continue;
    const r = f as Record<string, unknown>;
    if (
      r["can_cu"] === canCu &&
      typeof r["doc_id"] === "string" &&
      typeof r["khop_tai_id"] === "number"
    ) {
      return { docId: r["doc_id"], khopTaiId: r["khop_tai_id"] };
    }
  }
  return null;
}

/**
 * Nội dung tấm "Căn cứ" (tầng hai của drawer) — CHỈ phần nguyên văn, không tự
 * dựng dialog/Escape/tiêu điểm riêng: `NganXepDrawer` đã lo trọn phần đó cho
 * cả tấm, hai bộ quản lý tiêu điểm chồng nhau (như lồng nguyên `KhungDoiChieu`
 * vào đây) là đúng lỗi "hai chủ sở hữu cho một bất biến".
 */
function NoiDungCanCu({
  canCu,
  doiChieu,
}: {
  canCu: string;
  doiChieu: ReturnType<typeof useDoiChieu>;
}) {
  if (doiChieu.dang === null) {
    return (
      <div>
        <p className="font-jetbrains m-0 text-[12px] text-muted-foreground">{canCu}</p>
        <p className="m-0 mt-2 text-[13px] leading-5 text-muted-foreground">
          Chưa khớp được căn cứ này với một điều luật cụ thể trong lần soát gần nhất của bản thảo.
        </p>
      </div>
    );
  }
  return (
    <div>
      <BadgeHieuLuc hieuLuc={doiChieu.dang.hieuLuc ?? null} gonGang />
      {doiChieu.trangThai === "dang-tai" && (
        <p role="status" className="m-0 mt-2 text-[13px] text-muted-foreground">
          Đang mở nguyên văn…
        </p>
      )}
      {doiChieu.trangThai === "loi" && doiChieu.loi !== null && (
        <BaoLoi loi={doiChieu.loi} onThuLai={doiChieu.thuLai} />
      )}
      {doiChieu.trangThai === "xong" && doiChieu.vanBan !== null && (
        <div className="doc-reader mt-2 rounded-lg bg-[var(--color-paper-50)] p-3 text-foreground">
          {doiChieu.vanBan.provisions.map((dk) => (
            <div key={dk.id} className={dk.la_tam ? undefined : "opacity-60"}>
              {dk.cap === "dieu" && (
                <p className="mt-2 mb-1 font-sans text-[13px] font-semibold text-muted-foreground">
                  {dk.duong_dan}
                  {dk.tieu_de !== "" && ` — ${dk.tieu_de}`}
                </p>
              )}
              <NoiDungDieuKhoan dieuKhoan={dk} noiDung={dk.noi_dung} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface Props {
  banThao: BanThao;
  /** Từ `GET /mau/{loai}` — nạp một lần ở nơi mở sân khấu, không tự tải lại
   *  đây (cùng khung sống qua các phiên bản của một bản thảo). */
  cauTruc: CauTruc | null;
  /** Nhãn field của loại văn bản này (`Mau.facts`, cùng lời gọi `/mau/{loai}`
   *  với `cauTruc`) — CHỈ dùng để hiện tên người-đọc-được cho
   *  `doi_so_voi_truoc` qua `nhanFactDoi`. Xem chú thích ở đó: đây là khoá
   *  FIELD, không phải khoá MỤC, nên không đưa vào `XemTruocA4`. */
  truongMau: TruongFact[];
  /** `cauTruc`/`truongMau` đang tải — cột trái đợi thay vì đoán số mục từ
   *  `clauses` rồi vẽ lại một lần nữa khi khung tới. */
  dangTai: boolean;
  /** `GET /mau/{loai}` hỏng: không có khung mục thì "Sửa" mở ra biểu mẫu rỗng
   *  và lưu đè dữ kiện cũ — nói lỗi ra ở đúng chỗ danh sách mục, không im. */
  loiKhung: string | null;
  /** Gọi lại đúng lần gọi đã hỏng. Lỗi mạng một nhịp không được bắt người dùng
   *  đóng rồi mở lại bản thảo mới sửa được mục. */
  onTaiLaiKhung: () => void;
  mucDangChon: string | null;
  onChonMuc: (key: string) => void;
  /** Bản thảo vừa dựng lại xong (drawer sửa mục, Task 25) → cập nhật state
   *  `banThaoMo` của nơi gọi (cùng việc `onLui` đã làm cho phiên bản lùi). */
  capNhatBanThao: (bt: BanThao) => void;
  /** `true` = đã lùi (bản lùi về đã tới qua state của nơi gọi). */
  onLui: () => Promise<boolean>;
  onDong: () => void;
  onPhimTat: (loai: "rut_gon" | "trang_trong" | "soat_luat") => void;
  /** Dưới ngưỡng hai cột (Task 26, spec 2026-09-09 §9.7): cột mục cố định bề
   *  rộng không còn chỗ đứng — gấp lại thành `<details>` phía trên xem trước,
   *  và drawer sửa mục bên dưới phủ toàn màn (xem `NganXepDrawer.toanMan`). */
  toanMan: boolean;
  /** Chữ đã gõ trên trang mà chưa lưu xong (đang lưu, bị từ chối, hay còn đang
   *  gõ), của bản thảo này — nơi gọi GIỮ nó ở TRÊN sân khấu, vì sân khấu bị tháo
   *  ra ở tab "Trợ lý" của bố cục hẹp, khi vượt ngưỡng 68rem và khi đóng (WCAG
   *  3.3.7: không bắt gõ lại). */
  nhapODien: Readonly<Record<string, string>>;
  datNhapODien: (doi: (cu: Readonly<Record<string, string>>) => Record<string, string>) => void;
}

const KHOA_RONG_MUC = "klaw.san-khau.muc";
const RONG_MUC_MAC_DINH = 320;
const BIEN_MUC: Bien = { min: 240, max: 480 };

const CANH_BAO_LUI = "Lùi về bản trước; bản hiện tại bị bỏ, không làm lại được";

const NUT_PHU =
  "focus-brass inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[12.5px] text-primary transition-colors hover:bg-[var(--color-paper-100)] disabled:cursor-not-allowed disabled:opacity-60";

/**
 * Sân khấu bản thảo (spec 2026-09-09 §9.4, D5 canvas-tai-lieu Phase 2) — cột
 * bên phải của bố cục hai cột khi `toanMan` là `false` (trợ lý đứng cột trái,
 * ngăn cách bằng `TayKeo`), hoặc phủ toàn màn khi `toanMan` là `true` (bố cục
 * hẹp, dưới 68rem).
 *
 * Khung mục (cột trái) quyết định THỨ TỰ và CĂN CỨ của từng mục; `clauses` của
 * `banThao` chỉ góp nội dung — `mucTuBanThao` (xuat-tep.ts) đã gộp hai nguồn
 * này, dùng lại nguyên, không tính lại ở đây.
 */
export function SanKhauBanThao({
  banThao,
  cauTruc,
  truongMau,
  dangTai,
  loiKhung,
  onTaiLaiKhung,
  mucDangChon,
  onChonMuc,
  capNhatBanThao,
  onLui,
  onDong,
  onPhimTat,
  toanMan,
  nhapODien,
  datNhapODien,
}: Props) {
  // Phase 15 R3 — sân khấu render lại trên MỌI pixel kéo `TayKeo` (`datRongMuc`
  // đặt state ngay trong component này) và trên mọi token chat đang stream ở
  // nơi gọi; không memo thì mỗi lượt đó dựng lại toàn bộ `Muc[]` và một tham
  // chiếu mới ép `XemTruocA4` diff lại cả trang — nay là hàng loạt nút
  // `contentEditable`, đắt hơn hẳn `<p>` thuần trước Phase 3.
  const muc = useMemo(() => mucTuBanThao(banThao, cauTruc), [banThao, cauTruc]);
  // Lề trang là sự thật của cả TÀI LIỆU, không của một mục — đọc riêng thay vì
  // thêm một trường vào `Muc` (xem `leTrangTuBanThao`).
  const leTrang = useMemo(() => leTrangTuBanThao(banThao), [banThao]);
  // Ảnh đã tách cũng là sự thật của cả TÀI LIỆU, đọc riêng cùng lý do lề trang.
  const anh = useMemo(() => anhTuBanThao(banThao), [banThao]);
  // Khối "Căn cứ" (quyết định 2026-09-28, mục 5): cấp TÀI LIỆU, cùng lý do.
  const canCuVanBan = useMemo(() => canCuTuBanThao(banThao), [banThao]);
  const nhanDoi = nhanFactDoi(banThao.doi_so_voi_truoc, truongMau);
  const [hienThayDoi, datHienThayDoi] = useState(false);
  const [thuPhong, datThuPhong] = useState(100);
  const [hienCanCu, datHienCanCu] = useState(false);
  const [dangXuat, datDangXuat] = useState<"docx" | "pdf" | null>(null);

  // Drawer xếp chồng sửa từng mục (Task 25, spec 2026-09-09 §9.4).
  const [ngan, datNgan] = useState<Tam[]>([]);
  // PHẢI ổn định (`useCallback`, không phải một hàm mũi tên trần): nó nằm
  // trong dependency của effect "đưa tiêu điểm vào tấm trên cùng" bên trong
  // `NganXepDrawer`. Sân khấu render lại vì nhiều lý do không liên quan tới
  // drawer (một token chat đang stream, đổi zoom…) — một tham chiếu mới mỗi
  // lần đó sẽ chạy lại effect kia dù `ngan` không đổi, và giật tiêu điểm ra
  // khỏi ô đang gõ dở trong `DrawerSuaMuc`, về lại nút Đóng.
  const dongTamTrenCung = useCallback(() => datNgan(dongTrenCung), []);
  const doiChieuCanCu = useDoiChieu();

  const onSuaMuc = (key: string) => {
    const m = muc.find((mm) => mm.key === key);
    if (m === undefined) return;
    datNgan((cur) => moTam(cur, { id: key, tieuDe: `Mục ${m.stt}. ${m.ten}`, noiDung: m }));
  };

  // Fix round 1 (review #7) — `banThao` MỚI NHẤT, đọc được TRONG một callback
  // bất đồng bộ mà không dính closure cũ: `onSuaKhoi` có thể được gọi lại
  // (khối B) trước khi async trước đó (khối A) xong, và closure của A vẫn
  // giữ `banThao` ở render lúc A được tạo — cập nhật MỖI lần dựng, không chỉ
  // trong effect, để giá trị đọc lại luôn là bản MỚI NHẤT ngay lúc đọc.
  const banThaoRef = useRef(banThao);
  banThaoRef.current = banThao;

  // Fix round 1 (review #5) — số lượt sửa tay đang chờ máy chủ trả lời.
  // `xuatTep` (tải Word/PDF) đọc DOM SỐNG ngay lúc bấm; nếu một khối vừa blur
  // và lượt lưu của nó CHƯA VỀ, tệp tải về có thể chứa chữ chưa từng được lưu
  // — chặn xuất trong lúc đó thay vì để hai việc chạy đua.
  const [soLuuDangCho, datSoLuuDangCho] = useState(0);

  // Fix round 2 (re-review N2) — phiên bản do CHÍNH `onSuaKhoi` tạo ra ở lần
  // lưu thành công gần nhất. `KhoiVanXuoi` (N1) nay gửi phiên bản NÓ chụp lúc
  // focus, không phải phiên bản mới nhất — nên hai khối khác nhau, focus gần
  // như cùng lúc, có thể cùng gửi một phiên bản cũ, và khối lưu SAU bị máy chủ
  // từ chối dù không có gì xung đột thật (chỉ là khối TRƯỚC, của CHÍNH client
  // này, vừa lưu xong). Ref này phân biệt "chênh lệch do CHÍNH MÌNH vừa gây
  // ra" (an toàn để tự động gửi lại MỘT lần bằng phiên bản mới) khỏi "chênh
  // lệch do nơi khác" (một lượt sửa bằng lời — N1b — không được tự gửi lại).
  const phienBanTuSuaTayGanNhatRef = useRef(banThao.phien_ban);
  // `dung-thu.tsx` cấp `key={banThao.id}`, nhưng component không dựa vào đó:
  // nơi gọi nào chỉ đổi prop (không remount) thì mốc trên vẫn phải reset về bản
  // thảo MỚI mỗi khi `id` đổi, nếu không một số phiên bản cũ tình cờ trùng số
  // với bản thảo mới có thể khiến retry (dưới) tưởng nhầm một xung đột thật
  // (một lượt sửa bằng lời) là do chính client này gây ra.
  const banThaoIdTruocRef = useRef(banThao.id);
  if (banThaoIdTruocRef.current !== banThao.id) {
    banThaoIdTruocRef.current = banThao.id;
    phienBanTuSuaTayGanNhatRef.current = banThao.phien_ban;
  }

  /**
   * Phase 3 (Half A, R1/R2/R3) — gõ tay MỘT khối trong `XemTruocA4`, 0 lượt
   * gọi mô hình. Lỗi ra bằng toast (khối là bảng, mục không thấy, hết trần
   * sửa, phiên bản đã đổi — I3) — không có gì để hoàn tác trên màn hình (khối
   * vẫn hiện chữ vừa gõ, chỉ là chưa lưu được), nói ra để người dùng biết mà
   * thử lại thay vì tưởng đã lưu.
   *
   * R3 (D3) — báo NGAY tại thời điểm sửa đầu tiên hạ `nhanMucKiem`, không chỉ
   * đợi huy hiệu đổi: so nhãn TRƯỚC/SAU chứ không đọc cờ `sua_tay` một mình,
   * để không báo lặp lại ở LẦN SỬA TAY THỨ HAI của cùng bản thảo (nhãn không
   * đổi nữa vì đã hạ từ lần đầu).
   *
   * Fix round 2 (re-review N1/N2) — `phienBanLucSua` giờ do `KhoiVanXuoi` gửi
   * (phiên bản nó chụp lúc focus, xem chú thích ở đó), KHÔNG phải
   * `banThaoRef.current.phien_ban` đọc ở đây: đọc "mới nhất" ở đây chính là
   * lỗi N1b (một lượt sửa bằng lời chạy xong TRONG lúc khối còn mở đã tự nâng
   * số đó lên, khiến máy chủ so khớp một cách sai — token không còn phát hiện
   * được gì). Vì gửi phiên bản CŨ hơn giờ là chuyện thường (một khối khác của
   * CHÍNH client này vừa lưu xong cũng nâng số lên), một cú từ chối
   * `LOI_PHIEN_BAN_DA_DOI` được retry ĐÚNG MỘT LẦN bằng phiên bản mới nhất —
   * nhưng CHỈ khi biết chắc số mới đó đến từ CHÍNH client này
   * (`phienBanTuSuaTayGanNhatRef`, N2), không phải từ một lượt sửa bằng lời
   * (N1b, nơi `muc_key` đã bị cấp lại và retry sẽ ghi sai mục).
   */
  const onSuaKhoi = async (
    mucKey: string,
    khoiIndex: number,
    noiDungMoi: string,
    phienBanLucSua: number,
  ): Promise<boolean> => {
    const banThaoLucGoi = banThaoRef.current;
    const nhanTruoc = nhanMucKiem(banThaoLucGoi.audit_report, banThaoLucGoi.loai);
    datSoLuuDangCho((n) => n + 1);
    // Phase 15 R1 — cùng khuôn `xuatTep` bên dưới (loading → success/error
    // trên MỘT id), thu về đúng mục vừa lưu. Trước bản vá này lượt lưu im
    // lặng cả ba bước: với bản thảo đã `sua_tay`, chữ trên màn hình không đổi
    // sau khi lưu xong nên không có dấu hiệu nào là đã có một yêu cầu mạng.
    const m = muc.find((mm) => mm.key === mucKey);
    const tenMuc = m === undefined ? "chỗ vừa sửa" : `mục ${m.stt}`;
    const idToast = toast.loading(`Đang lưu ${tenMuc}…`);
    try {
      let phienBanGui = phienBanLucSua;
      let kq = await suaMucBanThao(banThaoLucGoi.id, mucKey, khoiIndex, noiDungMoi, phienBanGui);
      if (
        neenGuiLaiPhienBan(
          kq.ok ? null : kq.error,
          phienBanGui,
          banThaoRef.current.phien_ban,
          phienBanTuSuaTayGanNhatRef.current,
        )
      ) {
        phienBanGui = banThaoRef.current.phien_ban;
        kq = await suaMucBanThao(banThaoLucGoi.id, mucKey, khoiIndex, noiDungMoi, phienBanGui);
      }
      if (!kq.ok) {
        toast.error(kq.error.message, { id: idToast });
        return false;
      }
      toast.success(`Đã lưu ${tenMuc}.`, { id: idToast });
      // Fix round 1 (review #6) — một cập nhật KHÁC (một lượt chat vừa sửa
      // xong, một khối khác vừa lưu) có thể đã tới TRƯỚC phản hồi này và đã
      // đẩy `banThao` lên một phiên bản MỚI HƠN phản hồi đang cầm — áp phản
      // hồi CŨ hơn đó đè lên sẽ kéo màn hình LÙI LẠI (máy chủ vẫn đúng, màn
      // hình thì sai cho tới khi tải lại). Bỏ qua, không phải lỗi.
      if (kq.data.phien_ban < banThaoRef.current.phien_ban) return true;
      phienBanTuSuaTayGanNhatRef.current = kq.data.phien_ban;
      capNhatBanThao(kq.data);
      const nhanSau = nhanMucKiem(kq.data.audit_report, kq.data.loai);
      if (nhanTruoc === null && nhanSau !== null) {
        toast.warning("Bản thảo không còn được coi là đã kiểm pháp lý.", {
          description: "Bạn vừa sửa tay — hãy soát lại trước khi dùng bản thảo này.",
        });
      }
      return true;
    } finally {
      datSoLuuDangCho((n) => n - 1);
    }
  };

  // Khuôn gốc (quyết định 2026-09-26): có thì thân sân khấu là ảnh trang máy
  // chủ dựng, điền NGAY TRÊN trang (chủ dự án 2026-09-27: không bảng ô điền
  // bên cạnh); `null` là bản thảo HTML, giữ nguyên `XemTruocA4`. Memo cùng lý
  // do `muc`: sân khấu vẽ lại trên mọi token/pixel.
  const khuon = useMemo(() => khuonHopLe(banThao.khuon), [banThao.khuon]);
  const tieuDeKhuon = tieuDeTuBanThao(banThao.document) ?? banThao.ten;
  /** Chỗ trống của trang đang hiện, do `KhungTrangAnh` báo lên — kèm id bản
   *  thảo, để chỗ trống của bản thảo trước không lọt sang bản vừa mở. */
  const [oTrang, datOTrang] = useState<{ id: string; o: OTrang[] | null } | null>(null);
  const baoO = useCallback((o: OTrang[] | null) => datOTrang({ id: banThaoRef.current.id, o }), []);
  const oCuaBan = oTrang !== null && oTrang.id === banThao.id ? oTrang : null;
  // Máy chủ cũ không gửi `o`: mọi chỗ của `khuon` thành "chưa định vị" — vẫn
  // điền được, không ngõ cụt.
  const chuaDinhVi: OTrang[] =
    khuon === null || oCuaBan === null
      ? []
      : oCuaBan.o === null
        ? khuon.cho_trong.map((c) => ({ ...c, trang: null, hop: null }))
        : oCuaBan.o.filter((x) => x.hop === null);

  // ── Điền tại chỗ: MỖI chỗ tự lưu (chủ dự án 2026-09-27: "để người dùng
  // trực tiếp thao tác trên" trang; lưu ô điền không tính vào trần sửa). ──
  /** Giá trị ĐÃ LƯU của từng chỗ (đã cắt), theo `khoaO`. */
  const luuO = useMemo(
    () => Object.fromEntries((khuon?.cho_trong ?? []).map((c) => [khoaO(c), giaTriHienThi(c)])),
    [khuon],
  );
  const [dangLuuO, datDangLuuO] = useState<ReadonlySet<string>>(() => new Set());
  /** Câu từ chối theo chỗ — toast tự tắt, câu này đứng lại ĐÚNG chỗ đó tới lần
   *  gõ hay lần lưu kế tiếp (WCAG 3.3.1). */
  const [loiO, datLoiO] = useState<Readonly<Record<string, string>>>({});
  const datLoiMotO = (k: string, cau: string | null) =>
    datLoiO((cu) => {
      if (cau === null && !(k in cu)) return cu;
      const ra = { ...cu };
      if (cau === null) delete ra[k];
      else ra[k] = cau;
      return ra;
    });
  /** Hàng lưu: MỘT `PATCH …/o-dien` một lúc, lượt sau gửi phiên bản lượt trước
   *  vừa tạo — hai lượt cùng gửi một phiên bản thì lượt sau là 422 "đã đổi". */
  const hangLuu = useRef<Promise<unknown>>(Promise.resolve());
  /** Lần lưu được một chỗ gần nhất: lúc nào, ra phiên bản nào — trang của ĐÚNG
   *  phiên bản đó dựng lại `NGHI_DUNG_TRANG_MS` sau. */
  const lanLuuCuoi = useRef({ luc: 0, phienBan: -1 });
  const dangLui = useRef(false);

  /** Lưu MỘT chỗ trống (Enter, Tab, rời ô, bấm sang chỗ khác). Không đổi gì thì
   *  không gửi. Không toast khi lưu được: chữ đã hiện ngay trên trang và nút của
   *  chỗ đó đọc lên giá trị mới; từ chối thì câu lỗi đứng tại chỗ đó (`loiO`)
   *  kèm một toast để trình đọc màn hình nghe thấy. `null` = đã lưu. */
  const luuMotO = (o: Pick<OTrang, "don_vi" | "so">, giaTri: string): Promise<string | null> => {
    const k = khoaO(o);
    const gui: ODienGui[] = [{ don_vi: o.don_vi, cho_trong: o.so, gia_tri: giaTri }];
    if (giaTri.trim() === (luuO[k] ?? "")) {
      datNhapODien((cu) => boDaGui(cu, gui));
      datLoiMotO(k, null);
      return Promise.resolve(null);
    }
    // Lùi và lưu là hai lượt ghi phiên bản độc lập: phản hồi nào về sau thắng
    // trên màn hình, không theo thứ tự máy chủ đã ghi.
    if (dangLui.current) {
      const cau = "Đang lùi một phiên bản — đợi xong rồi lưu lại.";
      datLoiMotO(k, cau);
      return Promise.resolve(cau);
    }
    datLoiMotO(k, null);
    datSoLuuDangCho((n) => n + 1);
    datDangLuuO((cu) => new Set(cu).add(k));
    const lan = hangLuu.current.then(async () => {
      try {
        const lucGoi = banThaoRef.current;
        const kq = await suaODien(lucGoi.id, lucGoi.phien_ban, gui);
        if (!kq.ok) {
          datLoiMotO(k, kq.error.message);
          toast.error(kq.error.message, { duration: 6000 });
          return kq.error.message;
        }
        lanLuuCuoi.current = { luc: Date.now(), phienBan: kq.data.phien_ban };
        // Lượt kế trong hàng gửi phiên bản này, không đợi nơi gọi vẽ lại. Phản
        // hồi cũ hơn bản đang hiện (một lượt chat vừa sửa xong) không kéo màn
        // hình lùi.
        if (kq.data.phien_ban >= banThaoRef.current.phien_ban) {
          banThaoRef.current = kq.data;
          capNhatBanThao(kq.data);
        }
        datNhapODien((cu) => boDaGui(cu, gui));
        return null;
      } finally {
        datSoLuuDangCho((n) => n - 1);
        datDangLuuO((cu) => {
          const ra = new Set(cu);
          ra.delete(k);
          return ra;
        });
      }
    });
    // Một lượt hỏng bất ngờ không được làm hỏng cả hàng: mọi lượt sau vẫn gửi.
    hangLuu.current = lan.catch(() => undefined);
    return lan;
  };
  const dien: DienTaiCho = {
    luu: luuO,
    nhap: nhapODien,
    dangLuu: dangLuuO,
    loi: loiO,
    onNhap: (k, giaTri) => {
      datLoiMotO(k, null);
      datNhapODien((cu) => {
        const ra = { ...cu };
        if (giaTri === undefined) delete ra[k];
        else ra[k] = giaTri;
        return ra;
      });
    },
    onLuu: luuMotO,
  };
  /** Chữ trên trang mà tệp tải về chưa có (bị từ chối, hay còn đang gõ). */
  const doiO = khuon === null ? [] : oDaDoi(khuon.cho_trong, nhapODien);

  // Trang dựng lại MỘT lần khi người dùng dừng tay: `NGHI_DUNG_TRANG_MS` sau lần
  // lưu cuối, không lúc còn lượt lưu chờ — mỗi lượt dựng giữ suất LibreOffice
  // của cả tài khoản. Trong lúc chờ, chữ vừa lưu đè lên ảnh cũ (`dien.luu`).
  // Phiên bản đổi vì việc khác (lượt chat, Lùi) thì dựng ngay, dù vừa lưu xong:
  // chỉ phiên bản do CHÍNH lần lưu cuối tạo ra mới đợi.
  const [phienBanTrang, datPhienBanTrang] = useState(banThao.phien_ban);
  useEffect(() => {
    if (phienBanTrang === banThao.phien_ban || soLuuDangCho > 0) return;
    const { luc, phienBan } = lanLuuCuoi.current;
    const con = phienBan === banThao.phien_ban ? luc + NGHI_DUNG_TRANG_MS - Date.now() : 0;
    if (con <= 0) {
      datPhienBanTrang(banThao.phien_ban);
      return;
    }
    const hen = setTimeout(() => datPhienBanTrang(banThao.phien_ban), con);
    return () => clearTimeout(hen);
  }, [banThao.phien_ban, phienBanTrang, soLuuDangCho]);

  /** Lùi đi qua CÙNG cổng `soLuuDangCho` với lưu và tải tệp: một lượt ghi
   *  phiên bản một lúc — bấm hai lần thì lùi hai bậc, và một lượt lưu chưa về
   *  thì phản hồi nào về sau thắng. Lùi xong, chữ chưa lưu chỉ giữ chỗ ĐỔI THẬT
   *  so với bản vừa bỏ (`chiGiuThayDoi`); câu từ chối cũ nói về bản đã bỏ. */
  const lui = async () => {
    if (soLuuDangCho > 0) {
      toast.error("Đang lưu hay lùi một phiên bản — đợi xong rồi thử lại.");
      return;
    }
    const khuonBo = khuon;
    dangLui.current = true;
    datSoLuuDangCho((n) => n + 1);
    try {
      if ((await onLui()) && khuonBo !== null) {
        datNhapODien((cu) => chiGiuThayDoi(khuonBo.cho_trong, cu));
        datLoiO({});
      }
    } finally {
      dangLui.current = false;
      datSoLuuDangCho((n) => n - 1);
    }
  };

  /** Tải tệp ĐÃ ĐIỀN của đúng phiên bản đang nhìn — máy chủ áp phép lên khuôn
   *  gốc (Word mở được), không đọc DOM như bản thảo HTML. */
  const taiTepKhuon = async (dang: "docx" | "pdf") => {
    if (soLuuDangCho > 0) {
      toast.error("Đang lưu ô điền — đợi lưu xong rồi tải lại.");
      return;
    }
    // Trang đang HIỆN chữ chưa lưu; tệp tải về chỉ có những gì đã lưu.
    if (doiO.length > 0) {
      toast.error(
        `Còn ${doiO.length} chỗ chưa lưu — lưu (Enter) hay bỏ (Esc) ở chỗ đó rồi tải lại.`,
      );
      return;
    }
    datDangXuat(dang);
    const id = toast.loading(dang === "docx" ? "Đang tạo tệp Word…" : "Đang tạo tệp PDF…");
    const kq = await taiXuongBanThao(banThao.id, dang, banThao.phien_ban);
    datDangXuat(null);
    if (!kq.ok) {
      toast.error(kq.error.status === 503 ? CAU_MAY_BAN : kq.error.message, {
        id,
        duration: 6000,
      });
      return;
    }
    taiBlob(kq.data.blob, kq.data.ten ?? `${tenTepAnToan(tieuDeKhuon)}.${dang}`);
    toast.success(dang === "docx" ? "Đã tải tệp .docx." : "Đã tải tệp .pdf.", {
      id,
      duration: 4000,
      description: "Bản thảo cần được pháp chế rà soát trước khi ký kết.",
    });
  };

  const onMoCanCu = (canCu: string) => {
    datNgan((cur) => moTam(cur, { id: "can-cu", tieuDe: "Căn cứ", noiDung: canCu }));
    const kq = timCanCuKhaDung(banThao.audit_report, canCu);
    if (kq !== null)
      doiChieuCanCu.mo({ docId: kq.docId, khopTaiId: kq.khopTaiId, duongDan: canCu });
    else doiChieuCanCu.dong();
  };

  const [rongMuc, datRongMucRaw] = useState(() =>
    kepRong(docRongDaLuu(KHOA_RONG_MUC, RONG_MUC_MAC_DINH), BIEN_MUC),
  );
  const datRongMuc = (px: number) => {
    datRongMucRaw(px);
    luuRong(KHOA_RONG_MUC, px);
  };

  const khungRef = useRef<HTMLDivElement | null>(null);

  /** Danh sách mục — dùng lại NGUYÊN ở cả hai bố cục (cột cố định bề rộng khi
   *  rộng, `<details>` khi hẹp): một cây JSX, không hai bản chép tay dễ trôi
   *  nhau ở lần sửa sau. */
  /** Bản thảo KHÔNG theo checklist (S6): không có `GET /mau/{loai}`, không có
   *  biểu mẫu dữ kiện, và `POST /ban-thao/{id}/dung` từ chối nó. */
  const laTongQuat = banThao.loai === LOAI_TONG_QUAT;
  const danhSachMuc = dangTai ? (
    <p className="m-0 text-[13px] text-muted-foreground">Đang tải khung mục…</p>
  ) : loiKhung !== null ? (
    <div role="alert">
      <p className="m-0 text-[13px] text-destructive">
        Không tải được khung mục của loại văn bản này, nên chưa sửa được từng mục. {loiKhung}
      </p>
      <button type="button" onClick={onTaiLaiKhung} className={cn(NUT_PHU, "mt-2")}>
        Thử lại
      </button>
    </div>
  ) : muc.length === 0 ? (
    <p className="m-0 text-[13px] text-muted-foreground">Loại văn bản này chưa có khung mục.</p>
  ) : (
    <ol className="m-0 flex list-none flex-col gap-2 p-0">
      {muc.map((m) => (
        <li key={m.key} className="rounded-lg border border-border p-2">
          <div className="flex items-start justify-between gap-2">
            <p className="m-0 min-w-0 flex-1 text-[13px] font-medium text-foreground">
              {m.stt}. {m.ten}
              {m.noiDung === "[…]" && (
                <span className="ml-2 inline-block rounded-full bg-[var(--color-paper-100)] px-2 py-0.5 text-[11px] font-normal text-muted-foreground">
                  thiếu
                </span>
              )}
            </p>
            {/* Bản thảo tổng quát không có biểu mẫu dữ kiện nào để mở: nó sửa
                bằng cách nói với trợ lý ("đổi mục 2 thành…"), và máy chủ cũng
                từ chối `POST /ban-thao/{id}/dung` cho loại này. Ẩn nút thay vì
                để nó mở một biểu mẫu rỗng rồi báo lỗi sau khi bấm Lưu. */}
            {!laTongQuat && (
              <button
                type="button"
                onClick={() => onSuaMuc(m.key)}
                className="focus-brass shrink-0 cursor-pointer text-[12px] font-medium text-primary hover:underline"
              >
                Sửa
              </button>
            )}
          </div>
        </li>
      ))}
    </ol>
  );

  const xuatTep = async (dinhDang: "docx" | "pdf") => {
    if (khuon !== null) return taiTepKhuon(dinhDang);
    // Fix round 1 (review #5) — một khối vừa blur còn đang chờ máy chủ trả
    // lời (bấm nút tải đóng vai một cú click ra ngoài khối, TỰ NÓ đã kích
    // hoạt `onBlur`/lượt lưu đó trước khi handler này chạy) thì DOM sống đọc
    // ở đây có thể mang chữ CHƯA TỪNG được ghi vào bản thảo — nếu lượt lưu
    // đó sau đó hỏng (422/mạng), tệp đã tải về mang chữ máy chủ chưa từng
    // thấy. Chặn xuất, không đua với chính lượt lưu vừa kích hoạt.
    if (soLuuDangCho > 0) {
      toast.error("Đang lưu một chỗ vừa sửa — đợi lưu xong rồi tải lại.");
      return;
    }
    const sheet = khungRef.current?.querySelector<HTMLElement>("article") ?? null;
    if (sheet === null) {
      toast.error("Chưa tải được khung xem trước. Vui lòng thử lại.");
      return;
    }
    datDangXuat(dinhDang);
    const id = toast.loading(dinhDang === "docx" ? "Đang tạo tệp Word…" : "Đang tạo tệp PDF…");
    try {
      const { xuatWord, xuatPDF } = await import("@/lib/xuat-tep");
      if (dinhDang === "docx") await xuatWord(sheet, banThao.ten, taiAnhNguon);
      else await xuatPDF(sheet, banThao.ten, taiAnhNguon);
      toast.success(dinhDang === "docx" ? "Đã tải tệp .docx." : "Đã tải tệp .pdf.", {
        id,
        description: "Bản thảo cần được pháp chế rà soát trước khi ký kết.",
      });
    } catch {
      // Lỗi ra bằng toast, không bằng console — bản dựng công khai không nhả
      // stack ra console trình duyệt.
      toast.error("Xuất tệp thất bại. Vui lòng thử lại.", { id });
    } finally {
      datDangXuat(null);
    }
  };

  return (
    <div className="grid h-full min-w-0 flex-1 grid-rows-[auto_1fr]">
      <div className="border-b border-border">
        <header className="flex flex-wrap items-center gap-2 px-4 py-2.5">
          {/* Tiêu điểm vào đây khi sân khấu mở (trang gọi tìm
              `data-tieu-de-san-khau`): người dùng trình đọc màn hình nghe tên
              bản thảo trước, Tab đi tiếp vào thanh công cụ. */}
          <h2
            data-tieu-de-san-khau=""
            tabIndex={-1}
            className="focus-brass m-0 min-w-0 flex-1 truncate rounded-sm font-display text-base font-semibold text-primary"
          >
            {khuon !== null ? tieuDeKhuon : banThao.ten}
          </h2>
          <span className="font-jetbrains text-[12.5px] text-muted-foreground">
            v{banThao.phien_ban}
          </span>
          {/* Mức kiểm đứng NGAY cạnh tên bản thảo, không nằm trong một khay
              đóng/mở được: người dùng tải tệp về từ chính thanh này, và nhãn
              phải ở trong tầm mắt lúc họ bấm (CONTEXT.md "mức kiểm"). */}
          {nhanMucKiem(banThao.audit_report, banThao.loai) !== null && (
            <span className="rounded-md bg-[var(--color-paper-50)] px-2 py-0.5 text-[12px] text-muted-foreground">
              {nhanMucKiem(banThao.audit_report, banThao.loai)}
            </span>
          )}
          {banThao.phien_ban > 1 && (
            // Mũi tên lùi gợi ý "quay lại được", nhưng `POST /ban-thao/{id}/lui`
            // là WALK chứ không phải TOGGLE: bản đang đứng bị bỏ hẳn phía máy
            // chủ (api.ts). Nói ra một lần, cho cả chuột (`title`) lẫn trình
            // đọc màn hình (`aria-describedby`) — không hứa một nút "làm lại"
            // không tồn tại.
            <>
              <button
                type="button"
                onClick={() => void lui()}
                // `aria-disabled`, không `disabled`: nút đang giữ tiêu điểm mà
                // bị `disabled` thì tiêu điểm rơi về `<body>` ngay giữa lượt
                // lùi. `lui` tự chặn.
                aria-disabled={soLuuDangCho > 0}
                title={CANH_BAO_LUI}
                aria-describedby="san-khau-canh-bao-lui"
                className={cn(NUT_PHU, "aria-disabled:cursor-not-allowed aria-disabled:opacity-60")}
              >
                <ChevronLeft className="size-3.5" aria-hidden /> Lùi
              </button>
              <span id="san-khau-canh-bao-lui" className="sr-only">
                {CANH_BAO_LUI}
              </span>
            </>
          )}
          {nhanDoi.length > 0 && (
            <button
              type="button"
              aria-pressed={hienThayDoi}
              onClick={() => datHienThayDoi((v) => !v)}
              className={cn(NUT_PHU, hienThayDoi && "bg-[var(--color-paper-100)]")}
            >
              Hiện thay đổi
            </button>
          )}
          {/* Khuôn PDF không dàn lại được thành Word (`tai-xuong?dang=docx` là
              422): chỉ mời đúng thứ máy chủ làm được. */}
          {khuon?.dinh_dang !== "pdf" && (
            <button
              type="button"
              onClick={() => void xuatTep("docx")}
              disabled={dangXuat !== null || soLuuDangCho > 0}
              className={NUT_PHU}
            >
              <FileDown className="size-3.5 text-[var(--color-brass-600)]" aria-hidden />
              {dangXuat === "docx" ? "Đang tạo tệp Word…" : "Tải Word (.docx)"}
            </button>
          )}
          <button
            type="button"
            onClick={() => void xuatTep("pdf")}
            disabled={dangXuat !== null || soLuuDangCho > 0}
            className={NUT_PHU}
          >
            <Download className="size-3.5 text-[var(--color-brass-600)]" aria-hidden />
            {dangXuat === "pdf" ? "Đang tạo tệp PDF…" : "Tải PDF"}
          </button>
          <button
            type="button"
            onClick={onDong}
            aria-label="Đóng sân khấu bản thảo"
            className="focus-brass cursor-pointer rounded-md border border-border p-1.5 text-muted-foreground hover:bg-[var(--color-paper-100)]"
          >
            <X className="size-4" aria-hidden />
          </button>
        </header>
        {/* "Hiện thay đổi" liệt kê DỮ KIỆN vừa đổi (`doi_so_voi_truoc` so
            `facts` cũ/mới ở máy chủ — `src/services/ban_thao.py::doi_so_voi`),
            KHÔNG phải mục nào trong văn bản vừa đổi: không có bảng field→mục
            nào trong dữ liệu để tô đúng mục, xem `nhanFactDoi` (klaw.ts). */}
        {hienThayDoi && nhanDoi.length > 0 && (
          <p className="m-0 bg-[var(--color-paper-50)] px-4 pb-2.5 text-[12.5px] text-muted-foreground">
            Đã đổi so với phiên bản trước: {nhanDoi.join(", ")}
          </p>
        )}
      </div>

      <div
        className={cn("flex min-h-0", toanMan && "flex-col")}
        style={{ ["--rong-muc" as string]: `${rongMuc}px` }}
      >
        {/* Bản thảo tổng quát (fix round 1, mục 5): không có "Sửa" nào để mở
            (nút đã ẩn ở trên, laTongQuat), nên cột này chỉ lặp lại đúng những
            tiêu đề A4 đã hiện, ăn mất bề rộng tài liệu cần. Ẩn hẳn cột — kể cả
            `<details>` ở bố cục hẹp — và để A4 chiếm trọn; giữ lại cho bản
            thảo theo checklist, nơi "Sửa" vẫn là lối DUY NHẤT vào
            `DrawerSuaMuc` cho tới khi sửa tại chỗ thay được nó. */}
        {/* Khuôn gốc: không cột nào — điền ngay trên trang (chủ dự án
            2026-09-27: "tình trạng ô này thì ko cần thiết"). */}
        {!laTongQuat &&
          khuon === null &&
          (toanMan ? (
            // Tóm tắt là vùng chạm 44px (DESIGN.md, bố cục hẹp); đệm dưới chỉ khi
            // mở, nên lúc gập không cao hơn trước (≈ 12 + dòng chữ + 12).
            <details className="shrink-0 border-b border-border px-3 open:pb-3">
              <summary className="focus-brass min-h-11 cursor-pointer content-center text-[13px] font-medium text-foreground">
                Các mục
              </summary>
              {/* Giới hạn cao + tự cuộn: `<details>` là `shrink-0` và không tổ
                  tiên nào tới dialog cố định cuộn được, nên danh sách dài đẩy
                  khung xem trước ra khỏi màn (WCAG 2.4.11). `p-1` chừa chỗ cho
                  vòng tiêu điểm (2px + offset 2px) khỏi bị cắt. */}
              <div className="mt-2 max-h-[50dvh] overflow-y-auto p-1">{danhSachMuc}</div>
            </details>
          ) : (
            <>
              <div
                id="san-khau-danh-sach-muc"
                className="w-[var(--rong-muc)] shrink-0 overflow-y-auto border-r border-border p-3"
              >
                {danhSachMuc}
              </div>

              <TayKeo
                giaTri={rongMuc}
                bien={BIEN_MUC}
                nhan="Kéo để đổi bề rộng danh sách mục"
                dieuKhienId="san-khau-danh-sach-muc"
                onDoi={datRongMuc}
              />
            </>
          ))}

        <div className="flex min-w-0 flex-1 flex-col">
          {/* `relative`: ở bố cục hẹp danh sách "Chỗ trống chưa định vị" neo
              vào thanh này (xem `NutChuaDinhVi`). */}
          <div className="relative flex flex-wrap items-center gap-3 border-b border-border px-3 py-2">
            <ThanhThuPhong thuPhong={thuPhong} datThuPhong={datThuPhong} />
            {/* Trang ảnh không mang dòng căn cứ nào để bật/tắt. */}
            {khuon === null && (
              <label className="flex items-center gap-2 text-[12px]">
                <Toggle
                  checked={hienCanCu}
                  onChange={datHienCanCu}
                  label="Hiển thị căn cứ pháp lý"
                />
                Hiển thị căn cứ
              </label>
            )}
            {khuon !== null && chuaDinhVi.length > 0 && (
              <NutChuaDinhVi ds={chuaDinhVi} dien={dien} />
            )}
            {/* Ba phím tắt viết lại VĂN BẢN — chỉ bản thảo HTML có văn bản để
                viết lại; khuôn gốc chỉ điền chỗ trống, không rút gọn được. */}
            {khuon === null && (
              <div className="ml-auto flex flex-wrap gap-2">
                <button type="button" onClick={() => onPhimTat("rut_gon")} className={NUT_PHU}>
                  Rút gọn
                </button>
                <button type="button" onClick={() => onPhimTat("trang_trong")} className={NUT_PHU}>
                  Trang trọng hơn
                </button>
                <button type="button" onClick={() => onPhimTat("soat_luat")} className={NUT_PHU}>
                  Soát lại theo luật
                </button>
              </div>
            )}
          </div>
          <div
            ref={khungRef}
            className="min-h-0 flex-1 overflow-y-auto bg-[var(--color-paper-100)] p-6"
          >
            {khuon !== null ? (
              <KhungTrangAnh
                // Bản thảo khác = khung mới: trang cũ đứng chờ bản kế chỉ khi
                // đó là CÙNG bản thảo (xem `KhungTrangAnh`).
                key={banThao.id}
                duongDan={DUONG_DAN_KHUON.trangBanThao(banThao.id, phienBanTrang)}
                soTrang={khuon.so_trang}
                thuPhong={thuPhong}
                nhan="Các trang của bản đã điền — bấm vào chỗ trống để điền"
                dien={dien}
                onO={baoO}
              />
            ) : (
              <XemTruocA4
                // Bản thảo tổng quát không có `cau_truc` (không `GET /mau/tong_quat`)
                // — tiêu đề THẬT của nó nằm ở dòng H1 đầu `document`, do chính mô
                // hình đặt từ tài liệu nguồn (Phase 7 R4), KHÔNG phải `banThao.ten`
                // (đó là tên LOẠI, "Bản thảo tổng quát", một câu hỏi khác).
                tieuDe={
                  laTongQuat
                    ? (tieuDeTuBanThao(banThao.document) ?? banThao.ten)
                    : (cauTruc?.tieu_de ?? banThao.ten)
                }
                kyHieu={null}
                canCuVanBan={canCuVanBan}
                muc={muc}
                // Lề trang NGUỒN của tài liệu khách tải lên (`w:pgMar`,
                // 2026-09-18) — `null` với bản thảo KLAW tự soạn và mọi bản thảo
                // lưu trước trường này, và ở đó trang giữ lề tự đặt như cũ.
                leTrang={leTrang}
                // Ảnh NGUỒN đã tách (logo, con dấu, chữ ký quét — 2026-09-18);
                // rỗng với bản thảo KLAW tự soạn và mọi bản thảo lưu trước
                // trường này, và ở đó trang không có thẻ `<img>` nào.
                anh={anh}
                thuPhong={thuPhong}
                hienCanCu={hienCanCu}
                mucDangChon={mucDangChon}
                onChonMuc={onChonMuc}
                laTongQuat={laTongQuat}
                // Fix round 1 (Q-C2) — CHỈ bản thảo tổng quát, cùng điều kiện
                // đã ẩn nút "Sửa" ở trên (`!laTongQuat`): một bản thảo
                // checklist có CẢ HAI cơ chế sống trên cùng một màn hình nếu
                // không gác — sửa tay mục 2 tại đây, rồi bấm "Sửa" mục 5 →
                // `dungLaiBanThao` chạy `draft_generate` và THAY TOÀN BỘ
                // `clauses` qua `sua()`, xoá câu vừa gõ mà không cảnh báo, và
                // xoá luôn `audit.sua_tay`/`muc_kiem` (huy hiệu cũng biến mất
                // theo). Bản thảo tổng quát không có "Sửa" nào để cạnh tranh
                // (không checklist, không `facts`), nên đây là bề mặt DUY
                // NHẤT sửa tay an toàn tồn tại. Prop bỏ hẳn (không phải
                // `undefined` tường minh) khi `!laTongQuat` — `exactOptionalPropertyTypes`
                // phân biệt hai điều đó. `phienBan` (fix round 2, N1) đi kèm
                // `onSuaKhoi` — `KhoiVanXuoi` cần nó để chụp lại lúc focus.
                {...(laTongQuat ? { onSuaKhoi, phienBan: banThao.phien_ban } : {})}
              />
            )}
          </div>
        </div>
      </div>

      <NganXepDrawer
        ngan={ngan}
        onDong={dongTamTrenCung}
        toanMan={toanMan}
        render={(tam) => {
          if (tam.id === "can-cu") {
            return <NoiDungCanCu canCu={tam.noiDung as string} doiChieu={doiChieuCanCu} />;
          }
          const m = tam.noiDung as (typeof muc)[number];
          return (
            <DrawerSuaMuc
              banThao={banThao}
              muc={m}
              truong={truongMau}
              onHuy={dongTamTrenCung}
              onMoCanCu={onMoCanCu}
              onLuu={async (facts) => {
                const kq = await dungLaiBanThao(banThao.id, facts);
                if (kq.ok) {
                  capNhatBanThao(kq.data);
                  datNgan([]);
                } else {
                  toast.error(kq.error.message);
                }
              }}
            />
          );
        }}
      />
    </div>
  );
}
