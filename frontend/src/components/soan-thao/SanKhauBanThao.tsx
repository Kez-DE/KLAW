import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, Download, FileDown, Minus, Plus, X } from "lucide-react";
import { Toggle } from "@/components/draft/DraftBits";
import { BadgeHieuLuc } from "@/components/klaw/BadgeHieuLuc";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { NoiDungDieuKhoan } from "@/components/klaw/NoiDungDieuKhoan";
import { NganXepDrawer } from "@/components/ui/NganXepDrawer";
import { TayKeo } from "@/components/ui/TayKeo";
import { useDoiChieu } from "@/hooks/use-doi-chieu";
import { dungLaiBanThao, suaMucBanThao } from "@/lib/api";
import { docRongDaLuu, kepRong, luuRong, type Bien } from "@/lib/keo-dan";
import {
  LOAI_TONG_QUAT,
  neenGuiLaiPhienBan,
  nhanFactDoi,
  nhanMucKiem,
  type BanThao,
  type CauTruc,
  type TruongFact,
} from "@/lib/klaw";
import { dongTrenCung, moTam, type Tam } from "@/lib/ngan-xep-drawer";
import { mucTuBanThao, tieuDeTuBanThao } from "@/lib/xuat-tep";
import { cn } from "@/lib/utils";
import { DrawerSuaMuc } from "./DrawerSuaMuc";
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
  onLui: () => void;
  onDong: () => void;
  onPhimTat: (loai: "rut_gon" | "trang_trong" | "soat_luat") => void;
  /** Dưới ngưỡng hai cột (Task 26, spec 2026-09-09 §9.7): cột mục cố định bề
   *  rộng không còn chỗ đứng — gấp lại thành `<details>` phía trên xem trước,
   *  và drawer sửa mục bên dưới phủ toàn màn (xem `NganXepDrawer.toanMan`). */
  toanMan: boolean;
}

const KHOA_RONG_MUC = "klaw.san-khau.muc";
const RONG_MUC_MAC_DINH = 320;
const BIEN_MUC: Bien = { min: 240, max: 480 };
const BIEN_ZOOM: Bien = { min: 50, max: 150 };
const BUOC_ZOOM = 10;

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
}: Props) {
  const muc = mucTuBanThao(banThao, cauTruc);
  const nhanDoi = nhanFactDoi(banThao.doi_so_voi_truoc, truongMau);
  const [hienThayDoi, datHienThayDoi] = useState(false);
  const [thuPhong, datThuPhongRaw] = useState(100);
  const datThuPhong = (delta: number) => datThuPhongRaw((z) => kepRong(z + delta, BIEN_ZOOM));
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
  // Component này không được cấp `key={banThao.id}` từ nơi gọi (chuyển bản
  // thảo có thể chỉ đổi prop, không remount) — mốc trên phải reset về bản
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
    const nhanTruoc = nhanMucKiem(banThaoLucGoi.audit_report);
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
      const nhanSau = nhanMucKiem(kq.data.audit_report);
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
      if (dinhDang === "docx") await xuatWord(sheet, banThao.ten);
      else await xuatPDF(sheet, banThao.ten);
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
          <h2 className="m-0 min-w-0 flex-1 truncate font-display text-base font-semibold text-primary">
            {banThao.ten}
          </h2>
          <span className="font-jetbrains text-[12.5px] text-muted-foreground">
            v{banThao.phien_ban}
          </span>
          {/* Mức kiểm đứng NGAY cạnh tên bản thảo, không nằm trong một khay
              đóng/mở được: người dùng tải tệp về từ chính thanh này, và nhãn
              phải ở trong tầm mắt lúc họ bấm (CONTEXT.md "mức kiểm"). */}
          {nhanMucKiem(banThao.audit_report) !== null && (
            <span className="rounded-md bg-[var(--color-paper-50)] px-2 py-0.5 text-[12px] text-muted-foreground">
              {nhanMucKiem(banThao.audit_report)}
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
                onClick={onLui}
                title={CANH_BAO_LUI}
                aria-describedby="san-khau-canh-bao-lui"
                className={NUT_PHU}
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
          <button
            type="button"
            onClick={() => void xuatTep("docx")}
            disabled={dangXuat !== null || soLuuDangCho > 0}
            className={NUT_PHU}
          >
            <FileDown className="size-3.5 text-[var(--color-brass-600)]" aria-hidden />
            {dangXuat === "docx" ? "Đang tạo tệp Word…" : "Tải Word (.docx)"}
          </button>
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
        {!laTongQuat &&
          (toanMan ? (
            <details className="shrink-0 border-b border-border p-3">
              <summary className="cursor-pointer text-[13px] font-medium text-foreground">
                Các mục
              </summary>
              <div className="mt-2">{danhSachMuc}</div>
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
          <div className="flex flex-wrap items-center gap-3 border-b border-border px-3 py-2">
            <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
              <button
                type="button"
                aria-label="Thu nhỏ"
                onClick={() => datThuPhong(-BUOC_ZOOM)}
                className="focus-brass cursor-pointer rounded-md p-1.5 hover:bg-[var(--color-paper-100)]"
              >
                <Minus className="size-3.5" aria-hidden />
              </button>
              <span className="font-jetbrains w-10 text-center text-[11px]">{thuPhong}%</span>
              <button
                type="button"
                aria-label="Phóng to"
                onClick={() => datThuPhong(BUOC_ZOOM)}
                className="focus-brass cursor-pointer rounded-md p-1.5 hover:bg-[var(--color-paper-100)]"
              >
                <Plus className="size-3.5" aria-hidden />
              </button>
            </div>
            <label className="flex items-center gap-2 text-[12px]">
              <Toggle checked={hienCanCu} onChange={datHienCanCu} label="Hiển thị căn cứ pháp lý" />
              Hiển thị căn cứ
            </label>
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
          </div>
          <div
            ref={khungRef}
            className="min-h-0 flex-1 overflow-y-auto bg-[var(--color-paper-100)] p-6"
          >
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
              muc={muc}
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
