import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/app/AppShell";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { ChipTaiLieu, type HanhDongTep, type TepDinhKem } from "@/components/klaw/ChipTaiLieu";
import { ManChao } from "@/components/klaw/ManChao";
import { MaTruyVet } from "@/components/klaw/MaTruyVet";
import { KhungDoiChieu, useHaiCot } from "@/components/klaw/KhungDoiChieu";
import { OSoanCauHoi } from "@/components/klaw/OSoanCauHoi";
import { TheHetLuot } from "@/components/klaw/TheHetLuot";
import { TheKetQua } from "@/components/klaw/TheKetQua";
import { TrangThaiCho } from "@/components/klaw/TrangThaiCho";
import { KhongGianSoanThao } from "@/components/soan-thao/KhongGianSoanThao";
import { TaiLieuDuKien } from "@/components/klaw/TaiLieuDuKien";
import {
  apNeuCungBan,
  banThaoTuMo,
  chiMoiNhat,
  dongKhiDoiPhien,
  thamSoSanKhau,
  urlCoBanThao,
  urlTroBanKhac,
  vanNham,
  viecMoTaiLieu,
  type SanKhau,
} from "@/lib/san-khau";
import { loiTruocKhiGui, seDungOcr } from "@/lib/tai-lieu";
import { chiTiet as chiTietTaiLieu, taiLen } from "@/lib/tai-lieu-api";
import { loaiBackendCua } from "@/lib/mau-van-ban";
import { daTat, ghiNhoDaTat, khoaHetHan } from "@/lib/tat-thong-bao";
import { noiTraTieuDiem } from "@/lib/tieu-diem";
import { SanKhauBanThao } from "@/components/soan-thao/SanKhauBanThao";
import { SanKhauBanTaiLen } from "@/components/soan-thao/KhungTrangAnh";
import { TheTaiKhoanKhoa } from "@/components/tai-khoan/TheTaiKhoanKhoa";
import { NganXepDrawer } from "@/components/ui/NganXepDrawer";
import { TayKeo } from "@/components/ui/TayKeo";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { useDoiChieu } from "@/hooks/use-doi-chieu";
import { useTraCuu } from "@/hooks/use-tra-cuu";
import {
  banThaoCuaTaiLieu,
  goi,
  layBanThao,
  luiBanThao,
  moBanThaoKhuon,
  suaHoSoPhien,
} from "@/lib/api";
import { dinhDangMoc, laBiKhoa, laKhongGioiHan } from "@/lib/han-muc";
import { layThreadKhach, xoaThreadKhach } from "@/lib/khach";
import {
  RONG_DOI_CHIEU_MAC_DINH,
  RONG_SAN_KHAU_MAC_DINH,
  bienPanelDoiChieu,
  docRongDaLuu,
  kepRong,
  luuRong,
  sanRongChat,
} from "@/lib/keo-dan";
import type {
  BanThao,
  CauTruc,
  Citation,
  HoSoDaDung,
  TaiLieuDaDung,
  TraCuuKetQua,
  TruongFact,
} from "@/lib/klaw";
import { chuanHoaLuot, laMau, laNhapPhien, LOAI_TONG_QUAT } from "@/lib/klaw";
import type { LuotDaXong } from "@/lib/lich-su";
import { dungLichSu } from "@/lib/lich-su";
import { cn } from "@/lib/utils";
import { mucTuBanThao } from "@/lib/xuat-tep";

/** Ba phím tắt của sân khấu bản thảo — câu gửi thẳng vào chat qua `traCuu.hoi`,
 *  y hệt người dùng tự gõ (spec 2026-09-09 §9.4). */
const CAU_PHIM_TAT_SAN_KHAU: Record<"rut_gon" | "trang_trong" | "soat_luat", string> = {
  rut_gon: "Rút gọn bản thảo, giữ đủ các mục bắt buộc",
  trang_trong: "Viết lại bản thảo trang trọng hơn, không đổi dữ kiện",
  soat_luat: "Soát lại bản thảo theo luật trong kho",
};

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
  tepDinhKem,
  hanhDongTep,
  children,
}: {
  cauHoi: string;
  traceId: string | null;
  /** Tài liệu đã đi kèm ĐÚNG lượt này. Câu trả lời dựa một phần vào tệp đó, nên
   *  lượt phải nói ra là nó có tệp — nếu không, đọc lại dòng hội thoại sẽ thấy
   *  một câu trả lời về một tài liệu không xuất hiện ở đâu cả. Một MẢNG vì lượt
   *  so sánh mang hai tờ, và "tài liệu nào" là nửa câu hỏi ở lượt đó. */
  tepDinhKem?: TepDinhKem[] | undefined;
  /** Menu của con chip (xem `ChipTaiLieu`) — cùng việc như chip ở ô soạn. */
  hanhDongTep?: HanhDongTep;
  children?: React.ReactNode;
}) {
  return (
    <div {...(traceId === null ? {} : { "data-trace": traceId })}>
      <div className="flex flex-col items-end gap-1.5">
        {hanhDongTep !== undefined &&
          (tepDinhKem ?? []).map((tep) => (
            <span key={tep.id} className="max-w-[70%]">
              <ChipTaiLieu tep={tep} hanhDong={hanhDongTep} moLen={false} />
            </span>
          ))}
        <p className="max-w-[70%] rounded-2xl rounded-br-sm bg-[var(--color-ink-900)] px-4 py-2.5 text-sm leading-relaxed text-white">
          {cauHoi}
        </p>
      </div>
      {/* Card cho MỌI câu trả lời (spec soạn-thảo-trong-chat §5.1): bọc ở đây
          nên TheKetQua, TrangThaiCho, BaoLoi cùng hưởng; --card và shadow-soft
          đã đo tương phản trong DESIGN.md. */}
      <div className="mt-4 rounded-xl border border-border bg-card p-5 shadow-soft">{children}</div>
    </div>
  );
}

/** `?phien=` và `?ban_thao=` chỉ nhận UUID. Dùng ở CẢ `validateSearch` và lúc đọc trong component. */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Trần của `TraCuuRequest.tai_lieu_ids` phía máy chủ (`max_length=2`). Gửi tờ
 *  thứ ba là **422** — chặn ở đây để người dùng biết ngay lúc đính kèm, chứ
 *  không biết sau khi đã gõ xong câu hỏi. */
const TOI_DA_DINH_KEM = 2;

function ManHoiKlaw() {
  const { q: cauHoiTrenUrl, phien: phienTho, ban_thao: banThaoTho } = Route.useSearch();
  // Router (TanStack 1.170, non-strict search) trộn search THÔ của route cha ĐÈ lên
  // kết quả `validateSearch`, nên `?phien=rac` vẫn tới đây — kiểm lại trước khi gọi API.
  const phienId = typeof phienTho === "string" && UUID.test(phienTho) ? phienTho : undefined;
  const banThaoTrenUrl =
    typeof banThaoTho === "string" && UUID.test(banThaoTho) ? banThaoTho : undefined;
  const traCuu = useTraCuu();
  const doiChieu = useDoiChieu();
  const haiCot = useHaiCot();
  const navigate = useNavigate();
  // Bề rộng THẬT còn lại cho hàng chat+splitter+panel (Phase 9 U4 fix round 1)
  // — đo trực tiếp trên chính khung bọc (`ref={khungHang}` dưới, con của
  // `<main>` trong `AppShell`), KHÔNG phải `window.innerWidth`. Cột trái của
  // `AppShell` (dải icon 64px hay đầy đủ 260px, tuỳ ngưỡng bề rộng VÀ lựa
  // chọn tay qua localStorage — xem `AppShell.tsx`) đứng CẠNH khung này, nên
  // `window.innerWidth` luôn lớn hơn phần thật sự còn lại đúng bằng bề rộng
  // cột trái. `bienPanelDoiChieu` từng nhận thẳng `window.innerWidth`, nên
  // trần nó tính cho panel bên phải (đối chiếu hay sân khấu bản thảo) có thể
  // LỚN HƠN chỗ thật sự còn lại — panel đứng `shrink-0` với bề rộng cố định
  // đúng bằng trần đó thì tổng bề rộng vượt khung nhìn (tràn ngang), không chỉ
  // ép cột chat co lại nữa. `ResizeObserver` bắt được CẢ resize cửa sổ LẪN đổi
  // cỡ cột trái (rail ↔ đầy đủ) — hai việc không phát cùng một sự kiện.
  const khungHang = useRef<HTMLDivElement | null>(null);
  const [rongHang, datRongHang] = useState(() =>
    typeof window === "undefined" ? 1440 : window.innerWidth,
  );
  useLayoutEffect(() => {
    const el = khungHang.current;
    if (!el) return;
    datRongHang(el.getBoundingClientRect().width);
    const ro = new ResizeObserver((muc) => {
      const rong = muc[0]?.contentRect.width;
      if (rong) datRongHang(rong);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Độ rộng khung điều chiếu do người dùng kéo (Task 22, spec 2026-09-09 §9.1)
  // — nhớ qua localStorage, kẹp lại theo biên hiện tại. Biên đổi theo
  // `rongHang`: khung thu hẹp không được để độ rộng đã lưu tràn ra ngoài.
  // `useLayoutEffect` (không phải `useEffect`) để kẹp XONG TRƯỚC lần vẽ đầu,
  // giữ đúng cam kết cũ "khớp giá trị hiển thị ngay từ khung hình đầu tiên"
  // dù giờ biên phụ thuộc một phép đo DOM, không còn tính được ngay lúc khởi
  // tạo state. Tính biên MỘT LẦN rồi dùng chung cho cả hai state — gọi
  // `bienPanelDoiChieu` hai lần với hai giả định khác nhau là hai câu trả lời
  // có thể lệch nhau.
  const [bienDoiChieu, datBienDoiChieu] = useState(() => bienPanelDoiChieu(rongHang));
  const [rongDoiChieu, datRongDoiChieu] = useState(() =>
    kepRong(docRongDaLuu("klaw.doi-chieu.rong", RONG_DOI_CHIEU_MAC_DINH), bienDoiChieu),
  );
  useLayoutEffect(() => {
    const bienMoi = bienPanelDoiChieu(rongHang);
    datBienDoiChieu(bienMoi);
    datRongDoiChieu((r) => kepRong(r, bienMoi));
  }, [rongHang]);
  // MỘT cửa duy nhất để đổi độ rộng — kéo, thu gọn (Enter), và về mặc định
  // (bấm đôi) đều là CÙNG một hành động dưới góc nhìn người dùng ("tôi chọn
  // khung này rộng bao nhiêu"), nên cả ba phải cùng nhớ. Gom vào một hàm thay
  // vì gọi `luuRong` riêng ở từng nơi: ba chỗ tự nhớ lưu là ba chỗ lần sau có
  // thể quên một.
  const datRongVaLuu = (px: number) => {
    datRongDoiChieu(px);
    luuRong("klaw.doi-chieu.rong", px);
  };
  // Bề rộng khung bản thảo (sân khấu) ở bố cục hai cột (D5, canvas-tai-lieu
  // Phase 2) — CÙNG khuôn kẹp/nhớ với khung đối chiếu ngay trên, khoá
  // localStorage RIÊNG. Dùng lại NGUYÊN `bienPanelDoiChieu`: hàm đó chỉ tính
  // "còn lại bao nhiêu cho panel bên phải mà cột chat vẫn còn tối thiểu
  // 480px" — một phép tính đúng cho BẤT KỲ panel nào đứng bên phải chat, không
  // phải hàm riêng cho khung đối chiếu dù tên gọi vậy; viết thêm một hàm kẹp
  // thứ hai chỉ để đổi tên là nhân đôi cùng một phép tính.
  const [bienSanKhau, datBienSanKhau] = useState(() => bienPanelDoiChieu(rongHang));
  const [rongSanKhau, datRongSanKhauRaw] = useState(() =>
    kepRong(docRongDaLuu("klaw.san-khau.rong", RONG_SAN_KHAU_MAC_DINH), bienSanKhau),
  );
  useLayoutEffect(() => {
    const bienMoi = bienPanelDoiChieu(rongHang);
    datBienSanKhau(bienMoi);
    datRongSanKhauRaw((r) => kepRong(r, bienMoi));
  }, [rongHang]);
  const datRongSanKhauVaLuu = (px: number) => {
    datRongSanKhauRaw(px);
    luuRong("klaw.san-khau.rong", px);
  };
  // Một nguồn duy nhất cho danh tính + hạn mức (spec 2A §7). Màn này KHÔNG còn
  // khoá ô hỏi khi chưa đăng nhập: khách hỏi thử 10 lượt/24 giờ với `X-Khach-Id`
  // (spec 2A §8) và chỉ gặp thẻ mời đăng nhập khi thật sự hết lượt — bắt đăng
  // nhập trước câu hỏi đầu tiên là đòi cam kết trước khi cho thấy giá trị.
  const {
    daDangNhap,
    laKhach,
    chuaCauHinh,
    dangKiemPhien,
    hoiThoai,
    hanMuc,
    moNangGoi,
    datHanhDongPhienMoi,
    datLayThreadKhach,
    catThreadTruocKhiRoi,
  } = useTaiKhoan();

  const [nhap, datNhap] = useState("");
  const [luuTru, datLuuTru] = useState<LuotDaXong[]>([]);
  /** Đoạn chat khách không mang được sang tài khoản — nói ra, không nuốt. */
  const [loiNhap, datLoiNhap] = useState<string | null>(null);
  /** Trích dẫn đang mở, định danh theo `trace_id` của thẻ + chỉ số trong thẻ. */
  const [dangMo, datDangMo] = useState<{ trace: string; chiSo: number } | null>(null);
  /** Khung soạn thảo bên phải; loại trừ với khung đối chiếu — một khung một lúc. */
  const [soanThao, datSoanThao] = useState<{ slug: string | null } | null>(null);
  const moSoanThao = (slug: string | null) => {
    datDangMo(null);
    doiChieu.dong();
    onDongSanKhau(); // ba khung (đối chiếu/soạn thảo/sân khấu) loại trừ nhau — xoá sân khấu qua ĐÚNG một cửa (xem chú thích ở đó)
    datSoanThao({ slug });
  };

  // ── Sân khấu bản thảo + cửa sổ trợ lý nổi (Task 24, spec 2026-09-09 §9.4) ──
  // Nhánh `ban_thao` giờ mở SÂN KHẤU thật (bản thảo chiếm toàn `<main>`, trợ
  // lý lùi thành cửa sổ nổi) thay vì mượn tạm khung soạn thảo theo mẫu (Task
  // 21) — đúng như ghi chú "tạm thời cho tới khi giai đoạn 5" ở đó đã báo trước.
  /** Sân khấu đang mở: bản thảo, hoặc "Bản tải lên" (khuôn gốc đúng như tệp,
   *  chỉ xem). MỘT state cho cả hai nên chúng loại trừ nhau và dùng chung một
   *  cửa đóng (`onDongSanKhau`), một bố cục (cột phải/dialog hẹp), một Esc. */
  const [sanKhau, datSanKhau] = useState<SanKhau>(null);
  /** `sanKhau` mới nhất cho phản hồi bất đồng bộ về muộn (`vanNham`). */
  const sanKhauRef = useRef(sanKhau);
  sanKhauRef.current = sanKhau;
  const banThaoIdSanKhau = sanKhau?.loai === "ban_thao" ? sanKhau.banThaoId : null;
  const [banThaoMo, datBanThaoMo] = useState<BanThao | null>(null);
  /** Bản thảo vừa lưu/lùi/dựng lại xong lên sân khấu — CHỈ khi sân khấu vẫn là
   *  chính bản đó: một lượt lưu về muộn của bản trước không thay bản vừa mở. */
  const capNhatBanThaoMo = useCallback(
    (bt: BanThao) => datBanThaoMo((cu) => apNeuCungBan(cu, bt)),
    [],
  );
  /** Chữ đã gõ trên trang biểu mẫu mà chưa lưu xong, theo id bản thảo. Ở ĐÂY,
   *  không trong sân khấu: tab "Trợ lý" ở bố cục hẹp, vượt ngưỡng 68rem và đóng
   *  sân khấu đều tháo nó ra — giữ trong đó là bắt gõ lại mọi chỗ (WCAG 3.3.7).
   *  Mất khi rời trang, như chữ đang gõ ở ô hỏi. */
  const [nhapODien, datNhapODien] = useState<Record<string, Record<string, string>>>({});
  /** Nút đã mở sân khấu — ghi trong HANDLER mở (`ghiNoiMoSanKhau`), lúc nút
   *  còn trong DOM và còn tiêu điểm: ở bố cục hẹp lượt vẽ mở sân khấu tháo cả
   *  cây chat, nên tới lúc một effect chạy thì `activeElement` đã là `<body>`. */
  const noiMoSanKhau = useRef<HTMLElement | null>(null);
  /** Chỉ ghi khi sân khấu đang ĐÓNG: đổi chế độ lúc đang mở ("Điền biểu mẫu"
   *  từ "Bản tải lên") vẫn trả tiêu điểm về nút mở ban đầu. */
  const ghiNoiMoSanKhau = () => {
    if (sanKhau !== null) return;
    const n = document.activeElement;
    noiMoSanKhau.current = n instanceof HTMLElement && n !== document.body ? n : null;
  };
  const [mucDangChonSanKhau, datMucDangChonSanKhau] = useState<string | null>(null);
  /** Tab đang hiện ở bố cục hẹp (Task 26, spec 2026-09-09 §9.7): dưới 68rem
   *  sân khấu không còn chỗ cho cửa sổ trợ lý nổi, nên nó lùi thành một trong
   *  hai tab dưới cùng. Reset về "ban_thao" mỗi lần MỞ sân khấu (`moSanKhau`) —
   *  mở một bản thảo mới thì thứ người dùng cần thấy trước là chính bản thảo. */
  const [tabHep, datTabHep] = useState<"ban_thao" | "tro_ly">("ban_thao");
  /** Khung + nhãn field của loại văn bản này (`GET /mau/{loai}`) — loại không
   *  đổi giữa các phiên bản của CÙNG một bản thảo, nên khoá effect theo
   *  `loaiSanKhau` (một string nguyên thuỷ) chứ không theo `banThaoMo` (đổi
   *  tham chiếu sau mỗi lượt sửa) — cùng khuôn `loaiBackendKhung` của
   *  `KhongGianSoanThao`. `truongMauSanKhau` (`Mau.facts`) chỉ phục vụ
   *  `nhanFactDoi` — hiện tên field đã đổi, KHÔNG phải tô mục (xem `klaw.ts`). */
  const loaiSanKhau = banThaoMo?.loai;
  /** Loại văn bản (mã backend) đang soạn, từ sân khấu hoặc từ khung soạn thảo. */
  const loaiDangSoan =
    loaiSanKhau ?? (soanThao?.slug == null ? null : (loaiBackendCua(soanThao.slug) ?? null));
  const [cauTrucSanKhau, datCauTrucSanKhau] = useState<CauTruc | null>(null);
  const [truongMauSanKhau, datTruongMauSanKhau] = useState<TruongFact[]>([]);
  const [dangTaiKhungSanKhau, datDangTaiKhungSanKhau] = useState(false);
  /** Hỏng khung mục KHÔNG phải lỗi ngoài da: không có `facts` của mẫu thì
   *  `DrawerSuaMuc` mở ra một biểu mẫu RỖNG, bấm Lưu là gửi lại y nguyên dữ
   *  kiện cũ và dựng lại bản thảo cho không. Nói thẳng ra thay vì để im. */
  const [loiKhungSanKhau, datLoiKhungSanKhau] = useState<string | null>(null);
  /** Đếm lần gọi lại cho nút "Thử lại": tăng số này là chạy lại ĐÚNG effect
   *  bên dưới — cùng một lời gọi, cùng một đường huỷ, cùng cờ đang tải — thay
   *  vì chép lại lần gọi thứ hai ở nơi khác rồi để hai bản trôi khỏi nhau. */
  const [lanTaiKhungSanKhau, datLanTaiKhungSanKhau] = useState(0);
  useEffect(() => {
    // `tong_quat` KHÔNG có `GET /mau/{loai}` (bản thảo tổng quát không đi
    // checklist nào), nên gọi là nhận 404 rồi hiện "Thử lại" cho một khung
    // không bao giờ tồn tại. Đi đúng đường "chưa có khung": `mucTuBanThao`
    // dựng mục thẳng từ `clauses` khi `cauTruc` là null.
    if (loaiSanKhau === undefined || loaiSanKhau === LOAI_TONG_QUAT) {
      datCauTrucSanKhau(null);
      datTruongMauSanKhau([]);
      datLoiKhungSanKhau(null);
      datDangTaiKhungSanKhau(false);
      return;
    }
    const dieuKhien = new AbortController();
    datDangTaiKhungSanKhau(true);
    datLoiKhungSanKhau(null);
    void goi(`/mau/${encodeURIComponent(loaiSanKhau)}`, laMau, {
      signal: dieuKhien.signal,
    }).then((kq) => {
      if (dieuKhien.signal.aborted) return;
      datCauTrucSanKhau(kq.ok ? kq.data.cau_truc : null);
      datTruongMauSanKhau(kq.ok ? kq.data.facts : []);
      datLoiKhungSanKhau(kq.ok ? null : kq.error.message);
      datDangTaiKhungSanKhau(false);
    });
    return () => dieuKhien.abort();
  }, [loaiSanKhau, lanTaiKhungSanKhau]);

  /** Hồ sơ tình huống SAU khi bút chì của `DuaTren` sửa xong: `PATCH /ho-so`
   *  trả về mảng mới, còn `ketQua` của lượt đã chạy thì không đổi nữa — không
   *  giữ mảng này thì người dùng sửa xong chỉ thấy đúng giá trị cũ. Ghim theo
   *  `trace_id` để bản vá của lượt này không dính sang lượt trả lời kế tiếp. */
  const [hoSoDaSua, datHoSoDaSua] = useState<{ trace: string; hoSo: HoSoDaDung[] } | null>(null);

  /** Đóng sân khấu — nút X, Esc, bị một khung khác (đối chiếu/soạn thảo) thay
   *  chỗ, HOẶC `layBanThao` thất bại (bản thảo đã xoá/không truy cập được).
   *  BẤT BIẾN: sân khấu đóng ⇒ không còn `?ban_thao=` trên URL. R6
   *  (canvas-tai-lieu Phase 2) giữ tham số ở LẠI trong lúc sân khấu MỞ (xem
   *  effect đọc `banThaoTrenUrl` bên dưới) — đây là nơi DUY NHẤT gỡ nó khi
   *  đóng, nên ĐÂY PHẢI là nơi DUY NHẤT xoá `sanKhau`/`banThaoMo`. Thiếu bất
   *  biến đó thì một liên kết `?ban_thao=` trỏ tới bản thảo đã xoá tải lại
   *  mãi mãi, thử lại, báo lỗi, không có đường thoát trong ứng dụng — đúng lỗi
   *  fix round 1 báo lại (`moSanKhau`'s nhánh lỗi từng gọi thẳng
   *  `datSanKhau(null)`, không qua đây). Mọi chỗ khác cần đóng sân khấu phải
   *  gọi hàm NÀY, không tự `datSanKhau(null)` riêng. `useCallback` vì hiệu ứng
   *  Esc (R5, bên dưới) mang nó trong dependency — không bọc thì listener bị
   *  gỡ/gắn lại ở MỌI lần dựng lại của trang thay vì chỉ khi các giá trị nó
   *  đọc thật sự đổi. */
  const onDongSanKhau = useCallback(() => {
    datSanKhau(null);
    datBanThaoMo(null);
    datMucDangChonSanKhau(null);
    if (urlCoBanThao(banThaoTrenUrl, sanKhauRef.current)) {
      void navigate({
        to: "/dung-thu",
        search: thamSoSanKhau(cauHoiTrenUrl, phienId, null),
        replace: true,
      });
    }
  }, [banThaoTrenUrl, cauHoiTrenUrl, phienId, navigate]);
  const onLuiSanKhau = async () => {
    if (banThaoMo === null) return false;
    const kq = await luiBanThao(banThaoMo.id);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return false;
    }
    capNhatBanThaoMo(kq.data);
    return true;
  };
  const onPhimTatSanKhau = (loai: "rut_gon" | "trang_trong" | "soat_luat") => {
    const mucChon =
      banThaoMo !== null && mucDangChonSanKhau !== null
        ? mucTuBanThao(banThaoMo, cauTrucSanKhau).find((m) => m.key === mucDangChonSanKhau)
        : undefined;
    const tienTo = mucChon !== undefined ? `Ở mục ${mucChon.stt} (${mucChon.ten}): ` : "";
    gui(tienTo + CAU_PHIM_TAT_SAN_KHAU[loai]);
  };

  /** Nhánh `ban_thao` (Task 21 → Task 24): mở sân khấu thật với bản thảo vừa
   *  dựng/sửa xong. `TheBanThao` gọi `onMo(bt.id)`, nên `id` ở đây LÀ
   *  `ban_thao.id`, không phải id lượt hỏi hay id phiên. `coSan`: bản thảo
   *  vừa về từ chính lời gọi mở ("Điền biểu mẫu") — không tải lại lần hai.
   *
   *  Sân khấu đang mở bản KHÁC thì CHUYỂN sang bản này, không bỏ qua cú bấm:
   *  bản cũ đóng qua đúng cửa đóng (`urlTroBanKhac`), và phản hồi của bản cũ
   *  về muộn không đè lên bản mới (`vanNham`). `?ban_thao=` rồi ghi bản NÀY
   *  (`thamSoSanKhau`, thay mục lịch sử hiện tại): tải lại trang mở lại đúng nó. */
  const moSanKhau = (id: string, coSan?: BanThao) => {
    ghiNoiMoSanKhau();
    datDangMo(null);
    doiChieu.dong();
    datSoanThao(null);
    if (urlTroBanKhac(banThaoTrenUrl, id)) onDongSanKhau();
    datMucDangChonSanKhau(null);
    datTabHep("ban_thao");
    datSanKhau({ loai: "ban_thao", banThaoId: id });
    if (banThaoTrenUrl !== id) {
      daMoTuUrl.current = id; // hiệu ứng đọc URL không mở (tải lại) nó lần hai
      void navigate({
        to: "/dung-thu",
        search: thamSoSanKhau(cauHoiTrenUrl, phienId, id),
        replace: true,
      });
    }
    if (coSan !== undefined) {
      datBanThaoMo(coSan);
      return;
    }
    void layBanThao(id).then((kq) => {
      if (!vanNham(sanKhauRef.current, id)) return;
      if (kq.ok) datBanThaoMo(kq.data);
      else {
        toast.error(kq.error.message);
        // Bản thảo đã xoá/không truy cập được: đóng qua ĐÚNG một cửa
        // (`onDongSanKhau`) để `?ban_thao=` cũng rời URL — thiếu bước này,
        // một liên kết cũ tải lại là lặp lại y hệt lỗi này mãi mãi, không có
        // đường thoát (fix round 1, Important 1).
        onDongSanKhau();
      }
    });
  };

  /** Kết quả mới của CHÍNH bản thảo đang mở → cập nhật `banThaoMo` (phiên bản
   *  mới, mục vừa đổi tô được qua `doi_so_voi_truoc`). So khớp theo id vì lượt
   *  hỏi tiếp theo có thể không nói gì tới bản thảo (một câu hỏi tra cứu khác).
   *  Bản thảo trên khuôn gốc (lượt điền/sửa/dựng lại, lượt "cho tôi xem"): sân
   *  khấu TỰ MỞ trên nó (chủ dự án 2026-09-28, Q2) — ở bố cục hẹp là tab "Bản
   *  thảo" (`moSanKhau`); chat vẫn giữ lời đáp và thẻ. */
  //
  // CHỈ kết quả MỚI, MỘT lần: một kết quả đã thấy (kể cả lúc sân khấu đóng)
  // không được áp lại khi sân khấu MỞ — mở đã có `layBanThao`/bản vừa trả về.
  // Áp lại thì một phiên bản cũ của lượt chat trước lên sân khấu trước bản mới
  // nhất, và với bản thảo trên khuôn gốc đó là HAI lượt dựng trang chồng nhau
  // (lượt sau 503); và người dùng đóng sân khấu rồi thì lượt đó không mở lại.
  // Lượt đã lưu (`daTai`, `luuTru`) không bao giờ là `traCuu.ketQua`: xem lại
  // lịch sử không mở gì. `moSanKhau` dựng lại mỗi lượt vẽ: gọi bản mới nhất qua
  // ref, để hiệu ứng chỉ chạy khi kết quả đổi.
  const ketQuaDaAp = useRef<TraCuuKetQua | null>(null);
  const moSanKhauMoiNhat = useRef(moSanKhau);
  moSanKhauMoiNhat.current = moSanKhau;
  useEffect(() => {
    if (traCuu.dangChay || traCuu.ketQua === ketQuaDaAp.current) return;
    ketQuaDaAp.current = traCuu.ketQua;
    const bt = traCuu.ketQua?.ban_thao;
    const tuMo = banThaoTuMo(bt);
    if (tuMo !== null) moSanKhauMoiNhat.current(tuMo.id, tuMo);
    else if (banThaoIdSanKhau !== null && bt != null && bt.id === banThaoIdSanKhau)
      datBanThaoMo(bt);
  }, [banThaoIdSanKhau, traCuu.dangChay, traCuu.ketQua]);

  /** "Bản tải lên": khuôn gốc đúng như tệp, trên sân khấu. Đóng sân khấu đang
   *  mở qua ĐÚNG cửa đóng (gỡ `?ban_thao=`), rồi mở chế độ này — cùng lượt vẽ,
   *  nên sân khấu không chớp đóng/mở. */
  const moBanTaiLen = (tl: { id: string; ten_tep: string; so_trang: number | null }) => {
    ghiNoiMoSanKhau();
    datDangMo(null);
    doiChieu.dong();
    datSoanThao(null);
    onDongSanKhau();
    datTabHep("ban_thao");
    datSanKhau({ loai: "ban_tai_len", viecId: tl.id, tenTep: tl.ten_tep, soTrang: tl.so_trang });
  };

  /** "Điền biểu mẫu": bản thảo trên khuôn gốc (mới nhất, hoặc phiên bản 1 rỗng
   *  máy chủ vừa tạo — 0 lượt mô hình, không tính hạn mức) lên sân khấu, điền
   *  được ngay trên trang kể cả khi KLAW chưa điền chỗ nào. */
  const dienBieuMau = async (viecId: string) => {
    const idToast = toast.loading("Đang mở biểu mẫu…");
    const kq = await moBanThaoKhuon(viecId);
    if (!kq.ok) {
      toast.error(kq.error.message, { id: idToast, duration: 6000 });
      return;
    }
    toast.success("Đã mở biểu mẫu — bấm vào chỗ trống trên trang để điền.", {
      id: idToast,
      duration: 4000,
    });
    moSanKhau(kq.data.id, kq.data);
  };

  /** `?ban_thao=`: danh sách "Bản thảo" ở vỏ trang mở sân khấu qua URL — lối
   *  vào bền duy nhất tới việc đã lưu. R6 (canvas-tai-lieu Phase 2): tham số ở
   *  LẠI trên URL suốt lúc sân khấu mở — tải lại trang hay bấm Back phải mở
   *  lại đúng bản thảo đang xem, không phải một trang trắng. `onDongSanKhau`
   *  gỡ tham số khi đóng. `daMoTuUrl` chặn mở lại đúng bản thảo đó lần thứ hai
   *  khi hiệu ứng này chạy lại ở một render khác mà tham số chưa đổi, hay khi
   *  tham số là do chính `moSanKhau` vừa ghi. */
  const daMoTuUrl = useRef<string | null>(null);
  useEffect(() => {
    if (banThaoTrenUrl === undefined) {
      daMoTuUrl.current = null;
      return;
    }
    if (daMoTuUrl.current === banThaoTrenUrl) return;
    daMoTuUrl.current = banThaoTrenUrl;
    moSanKhau(banThaoTrenUrl);
  });

  // Lượt đã tải từ phiên đang mở — chỉ khi chi tiết vừa tải ĐÚNG là phiên
  // đang mở (`?phien=`), không phải chi tiết còn sót lại của phiên trước.
  const daTai =
    phienId !== undefined && hoiThoai.chiTiet !== null && hoiThoai.chiTiet.id === phienId
      ? hoiThoai.chiTiet.luot.map(chuanHoaLuot)
      : [];

  const oHoi = useRef<HTMLTextAreaElement | null>(null);
  const cuoi = useRef<HTMLDivElement | null>(null);
  /** Bọc khung soạn thảo — dò control focus được đầu tiên khi khung mở. */
  const khungSoanThao = useRef<HTMLDivElement | null>(null);
  /** Khung đính kèm tài liệu — nút kẹp giấy mở/đóng nó. Nằm trong cột hội
   *  thoại chứ không trong khung soạn thảo: người dùng đang cầm tờ giấy trong
   *  tay, bắt họ mở khung soạn thảo trước mới được đính kèm là một ngõ cụt. */
  const [moTaiLieu, datMoTaiLieu] = useState(false);
  /** Thẻ "gói hết hạn" đã bị tắt cho ĐÚNG lần hết hạn này. Gia hạn rồi hết hạn
   *  tiếp thì khoá đổi, nên thẻ hiện lại — nếu không người dùng mất lượt mà
   *  không biết vì sao. */
  const [daTatHetHan, datDaTatHetHan] = useState(false);
  const [dangDocTep, datDangDocTep] = useState(false);
  /** Lượt tải đang chạy — nút "Huỷ tải lên" của ô soạn huỷ đúng lượt này. */
  const huyTaiLen = useRef<AbortController | null>(null);
  /** Câu từ chối của lần tải tệp gần nhất — toast tự tắt, câu này đứng lại cạnh
   *  chỗ đính kèm tới lần tải kế tiếp, để lý do (tên tệp, số trang thật) không
   *  mất theo toast. */
  const [loiTaiLen, datLoiTaiLen] = useState<string | null>(null);
  /** Phiên do chính lần ĐÍNH KÈM này mở ra, trong khoảng `?phien=` chưa kịp đổi. */
  const phienVuaTao = useRef<string | null>(null);
  /** Tài liệu đã đọc xong và sẽ đi kèm câu hỏi SẮP gửi — tối đa `TOI_DA_DINH_KEM`.
   *  Đọc xong là đính kèm ngay, kể cả khi tài liệu không khớp mẫu checklist nào. */
  const [tepDaDinhKem, datTepDaDinhKem] = useState<TepDinhKem[]>([]);
  /** Tên tệp của lượt ĐANG chạy, và của các lượt đã lùi vào dòng hội thoại (khoá
   *  theo `trace_id`). Không nhét vào `LuotDaXong`: kiểu đó còn được ghi vào
   *  localStorage của khách, và một tên tệp không có việc gì nằm ở đó. */
  const [tepCuaLuot, datTepCuaLuot] = useState<TepDinhKem[]>([]);
  const [tepDaLuu, datTepDaLuu] = useState<Record<string, TepDinhKem[]>>({});
  /** Tệp đã biết `co_khuon_goc`/`so_trang` — tệp vừa tải lên, và tệp của các
   *  lượt ĐÃ LƯU (tải lại trang, mở lại phiên), nơi con chip và dòng tài liệu
   *  cần biết tệp có khuôn gốc không. Khoá theo id việc đọc, duy nhất toàn hệ
   *  thống, nên giữ qua các phiên (mở lại phiên cũ không gọi lại). */
  const [tepDaBiet, datTepDaBiet] = useState<Record<string, TepDinhKem>>({});
  const daHoiTep = useRef(new Set<string>());
  const idTepDaLuu = [
    ...new Set(daTai.flatMap((l) => l.ketQua?.tai_lieu?.tai_lieu_da_dung.map((t) => t.id) ?? [])),
  ].join(" ");
  useEffect(() => {
    // Một `GET /tai-lieu/{id}` cho mỗi tệp CHƯA biết, mỗi lần mở phiên — không
    // mỗi lượt: giỏ nhịp là 10 lượt gọi / 60 giây mỗi IP. Hỏng thì lần mở phiên
    // sau hỏi lại; tới lúc đó con chip chỉ mời "Dữ kiện đã đọc".
    // ponytail: một lượt gọi mỗi tệp; thêm endpoint liệt kê tài liệu của phiên
    // nếu phiên nhiều tệp chạm giỏ nhịp.
    for (const id of idTepDaLuu.split(" ")) {
      if (id === "" || daHoiTep.current.has(id)) continue;
      daHoiTep.current.add(id);
      void chiTietTaiLieu(id).then((kq) => {
        if (!kq.ok) {
          daHoiTep.current.delete(id);
          return;
        }
        const { ten_tep, co_khuon_goc, so_trang } = kq.data;
        datTepDaBiet((cu) => ({
          ...cu,
          [id]: { id, ten_tep, co_khuon_goc: co_khuon_goc === true, so_trang },
        }));
      });
    }
  }, [idTepDaLuu]);
  /** Con chip của một lượt ĐÃ LƯU: các tài liệu lượt đó dùng — lối vào tệp sau
   *  khi tải lại trang ("Xem bản tải lên", "Điền biểu mẫu" khi tệp có khuôn gốc). */
  const tepCuaLuotDaLuu = (kq: TraCuuKetQua | null): TepDinhKem[] =>
    (kq?.tai_lieu?.tai_lieu_da_dung ?? []).map(
      (t) => tepDaBiet[t.id] ?? { id: t.id, ten_tep: t.ten_tep },
    );
  /** Bản mới nhất của `tepDaDinhKem` cho `ghiNhoDinhKem`, vốn phải ổn định
   *  tham chiếu (xem doc ở đó) nên không đọc được state qua closure. */
  const dsDinhKem = useRef(tepDaDinhKem);
  dsDinhKem.current = tepDaDinhKem;
  /** Neo vừa bấm trong một thẻ kết quả — khung tài liệu mở đúng chỗ đó. */
  const [donViDangMo, datDonViDangMo] = useState<{
    taiLieuId: string;
    /** `null` = mở cả tài liệu, không tô đơn vị nào (bấm con chip đính kèm). */
    chiSo: number | null;
  } | null>(null);

  useLayoutEffect(() => {
    cuoi.current?.scrollIntoView({ block: "end" });
  }, [luuTru, traCuu.ketQua, traCuu.dangChay, daTai.length]);

  // `?phien=` là nguồn sự thật về phiên đang mở (tải lại trang giữ được, chia sẻ
  // được). Đổi phiên ⇒ xoá dòng hội thoại, đóng khung — cả sân khấu của phiên cũ
  // (`dongKhiDoiPhien`) — tải lượt đã lưu. Trường hợp đặc biệt: sau `bat_dau`
  // của phiên MỚI ta tự `replace` URL sang id đó —
  // lúc ấy `traCuu.hoiThoaiId === phienId` và dòng hội thoại đang chạy PHẢI giữ.
  const { datLai: datLaiTraCuu } = traCuu;
  const { dong: dongDoiChieu } = doiChieu; // `useDoiChieu` trả object mới mỗi render; `dong` là useCallback ổn định
  const { taiChiTiet, xoaChiTiet, taiLai: taiLaiPhien } = hoiThoai;
  const { taiLai: taiLaiHanMuc } = hanMuc;
  const phienDangHien = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (dangKiemPhien || phienDangHien.current === phienId) return;
    phienDangHien.current = phienId;
    if (phienId !== undefined && phienId === traCuu.hoiThoaiId) return;
    if (dongKhiDoiPhien(banThaoTrenUrl, sanKhauRef.current)) onDongSanKhau();
    datLuuTru([]);
    datDangMo(null);
    dongDoiChieu();
    datSoanThao(null);
    datLaiTraCuu();
    // Tài liệu thuộc về MỘT cuộc trò chuyện (máy chủ xoá nội dung đã đọc cùng
    // với nó), nên đổi phiên là bỏ hết đính kèm — gửi id của phiên cũ sang
    // phiên mới chỉ đổi lấy một 404 và một câu hỏi mất ngữ cảnh.
    datTepDaDinhKem([]);
    datTepCuaLuot([]);
    datTepDaLuu({});
    datLoiTaiLen(null);
    phienVuaTao.current = null;
    datDonViDangMo(null);
    datMoTaiLieu(false);
    if (phienId !== undefined && daDangNhap) taiChiTiet(phienId);
    else xoaChiTiet();
  }, [
    phienId,
    banThaoTrenUrl,
    dangKiemPhien,
    daDangNhap,
    traCuu.hoiThoaiId,
    datLaiTraCuu,
    taiChiTiet,
    xoaChiTiet,
    dongDoiChieu,
    onDongSanKhau,
  ]);

  // Sau `bat_dau` của phiên MỚI (có danh tính, chưa có `?phien=`) → ghim id lên
  // URL, ĐÚNG MỘT LẦN cho mỗi id (`daGhim`). Thiếu chốt một-lần này thì bấm
  // Back từ `?phien=B` về `/dung-thu` (`phienId` → `undefined`, nhưng
  // `traCuu.hoiThoaiId` vẫn còn B) sẽ bị hiệu ứng này hiểu nhầm là "phiên mới
  // vừa `bat_dau`" và ghim ngược URL về lại B — Back không đưa được người
  // dùng ra khỏi B.
  const daGhim = useRef<string | null>(null);
  useEffect(() => {
    if (!daDangNhap || traCuu.hoiThoaiId === null || traCuu.hoiThoaiId === daGhim.current) return;
    daGhim.current = traCuu.hoiThoaiId; // mỗi id chỉ ghim MỘT lần — Back về /dung-thu không bị kéo lại
    if (phienId !== undefined) return; // đang mở phiên có sẵn: id đã ở trên URL
    phienDangHien.current = traCuu.hoiThoaiId; // để effect trên không xoá dòng đang chạy
    void navigate({ to: "/dung-thu", search: { phien: traCuu.hoiThoaiId }, replace: true });
  }, [daDangNhap, traCuu.hoiThoaiId, phienId, navigate]);

  // Đăng nhập xong quay về đây: đoạn chat khách đã cất trong `sessionStorage`
  // được nhập vào tài khoản, MỘT lần (`daNhap`), rồi URL ghim sang phiên vừa
  // tạo bằng `replace` — nút Back không được đưa người dùng trở lại một trang
  // trống đã nhập xong. `xoaThreadKhach` chạy ở CẢ hai ngả: nhập lỗi mà giữ lại
  // đoạn chat thì lần đăng nhập sau nó lại được nhập, thành hai bản trùng.
  const daNhap = useRef(false);
  useEffect(() => {
    if (!daDangNhap || phienId !== undefined || daNhap.current) return;
    const t = layThreadKhach();
    if (t === null) return;
    daNhap.current = true;
    void goi("/hoi-thoai/nhap", laNhapPhien, {
      method: "POST",
      body: {
        luot: t.map((l) => ({
          cau_hoi: l.cauHoi,
          tra_loi: l.ketQua,
          trace_id: l.ketQua.trace_id,
        })),
      },
    }).then((kq) => {
      xoaThreadKhach();
      if (kq.ok) {
        taiLaiPhien();
        void navigate({ to: "/dung-thu", search: { phien: kq.data.id }, replace: true });
      } else datLoiNhap("Tôi chưa lưu được đoạn chat thử; bạn vẫn hỏi tiếp được.");
    });
  }, [daDangNhap, phienId, navigate, taiLaiPhien]);

  // Hết stream → tải lại danh sách phiên: máy chủ ghi lượt TRƯỚC khi đóng
  // stream, nên lúc `dangChay` về `false` danh sách đã có lượt mới.
  useEffect(() => {
    if (daDangNhap && !traCuu.dangChay && traCuu.cauHoi !== null) taiLaiPhien();
  }, [daDangNhap, traCuu.dangChay, traCuu.cauHoi, taiLaiPhien]);

  // Hạn mức thì tải lại cho CẢ khách: chip "còn N/10 lượt thử" đứng cạnh ô hỏi
  // là thứ duy nhất báo cho khách biết mình sắp hết, và bộ đếm của khách nằm ở
  // máy chủ (khoá theo `X-Khach-Id`) chứ không đếm được từ số lượt trên màn.
  useEffect(() => {
    if (!traCuu.dangChay && traCuu.cauHoi !== null) taiLaiHanMuc();
  }, [traCuu.dangChay, traCuu.cauHoi, taiLaiHanMuc]);

  // Chạy đúng MỘT lần cho mỗi giá trị `?q=`. `hoi` ổn định giữa các lần dựng
  // lại (`useCallback`), nên hiệu ứng này không tự kích hoạt lại và không biến
  // một câu hỏi thành một chuỗi lượt gọi tính tiền.
  const { hoi } = traCuu;
  const daHoiTuUrl = useRef<string | null>(null);
  useEffect(() => {
    if (cauHoiTrenUrl === undefined || dangKiemPhien || daHoiTuUrl.current === cauHoiTrenUrl)
      return;
    daHoiTuUrl.current = cauHoiTrenUrl;
    hoi(cauHoiTrenUrl);
  }, [cauHoiTrenUrl, hoi, dangKiemPhien]);

  const tuGian = () => {
    const el = oHoi.current;
    if (el === null) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 6 * 26 + 20)}px`;
  };
  useEffect(tuGian, [nhap]);

  const gui = (tho?: string) => {
    const noiDung = (tho ?? nhap).trim();
    // Tệp đang tải: câu hỏi sẽ đi thiếu tệp, và ở đoạn chat mới lượt tải lẫn
    // lượt hỏi mỗi bên mở một phiên. Chặn ở đây cho MỌI lối gửi (ô soạn, phím
    // tắt sân khấu); ô soạn tự báo "Đang tải tệp lên…".
    if (noiDung === "" || traCuu.dangChay || dangDocTep) return;

    // Lượt đang hiện được xếp vào lịch sử TRƯỚC khi lượt mới chạy. Không dùng
    // `useEffect` theo dõi `ketQua`: hiệu ứng đó chạy lại mỗi lần React thấy
    // tham chiếu đổi và sẽ đẩy trùng một câu trả lời vào dòng hội thoại.
    const cauHoiCu = traCuu.cauHoi;
    const ketQuaCu = traCuu.ketQua;
    const luotTruoc: LuotDaXong[] =
      cauHoiCu !== null && ketQuaCu !== null
        ? [...luuTru, { cauHoi: cauHoiCu, ketQua: ketQuaCu }]
        : luuTru;
    if (cauHoiCu !== null && ketQuaCu !== null) {
      datLuuTru((truoc) => [...truoc, { cauHoi: cauHoiCu, ketQua: ketQuaCu }]);
      if (tepCuaLuot.length > 0) {
        const ten = tepCuaLuot;
        datTepDaLuu((truoc) => ({ ...truoc, [ketQuaCu.trace_id]: ten }));
      }
    }

    // Tài liệu đi kèm ĐÚNG lượt này rồi thôi: lượt sau vẫn hỏi tiếp về nó được
    // vì máy chủ giữ nội dung trong hội thoại, nên gửi lại id là trả tiền hai
    // lần cho cùng một tài liệu.
    const ids = tepDaDinhKem.map((t) => t.id);
    datTepCuaLuot(tepDaDinhKem);
    datTepDaDinhKem([]);

    datDangMo(null);
    doiChieu.dong();
    datNhap("");
    datLoiNhap(null); // câu mới bắt đầu: lời báo về đoạn chat cũ đã hết việc
    // Có danh tính: máy chủ tự nạp `lich_su` từ phiên, KHÔNG gửi lại từ client.
    // Ẩn danh: giữ nguyên đường cũ — dựng lịch sử từ `luotTruoc` (đã gồm lượt
    // đang hiện) chứ KHÔNG từ `luuTru`: `datLuuTru` là setState, giá trị mới
    // chưa có trong lượt render này, nên đọc `luuTru` ở đây sẽ luôn thiếu ĐÚNG
    // lượt vừa xong — tức câu nối tiếp đầu tiên sau mỗi câu trả lời mất chính
    // ngữ cảnh nó cần nhất.
    const kemTaiLieu = ids.length > 0 ? { taiLieuIds: ids } : {};
    if (daDangNhap) {
      const id = phienId ?? traCuu.hoiThoaiId ?? phienVuaTao.current ?? undefined;
      traCuu.hoi(noiDung, id === undefined ? kemTaiLieu : { hoiThoaiId: id, ...kemTaiLieu });
    } else {
      traCuu.hoi(noiDung, { lichSu: dungLichSu(luotTruoc), ...kemTaiLieu });
    }
  };

  /** Bấm một neo tài liệu: mở khung tài liệu ngay tại đơn vị văn bản đó. */
  const moNeoTaiLieu = (taiLieuId: string, chiSo: number) => {
    datDonViDangMo({ taiLieuId, chiSo });
    datMoTaiLieu(true);
  };

  /** "Dữ kiện đã đọc" trong menu con chip: mở chính tài liệu đó, không tô đơn
   *  vị nào.
   *
   *  Đọc tài liệu là việc NỀN (chủ dự án 2026-09-27): đính kèm không mở khung
   *  nào, chat chỉ trả lời câu hỏi. Bảng dữ kiện là thứ người dùng tự mở. */
  const moTaiLieuDinhKem = (taiLieuId: string) => {
    datDonViDangMo({ taiLieuId, chiSo: null });
    datMoTaiLieu(true);
  };
  const dongTaiLieu = useCallback(() => {
    datMoTaiLieu(false);
    datDonViDangMo(null);
  }, []);
  /** Menu con chip — CÙNG việc ở ô soạn và ở lượt đã gửi. */
  const hanhDongTep: HanhDongTep = {
    onXemBanTaiLen: moBanTaiLen,
    onDienBieuMau: (id) => void dienBieuMau(id),
    onDuKien: moTaiLieuDinhKem,
  };

  /** Bấm dòng tài liệu trên thẻ (chủ dự án 2026-09-28, Q1): bản thảo MỚI NHẤT
   *  của tệp lên sân khấu — đang mở rồi thì chỉ đưa tiêu điểm vào nó; chưa có
   *  bản thảo nào thì "Bản tải lên". Cùng lối ở lượt đang chạy và lượt đã lưu.
   *  `chiBamMoiNhat`: hai cú bấm trước khi GET đầu về — chỉ cú sau được mở. */
  const [chiBamMoiNhat] = useState(chiMoiNhat); // khởi tạo MỘT lần: bộ đếm sống qua các lượt vẽ
  const moTaiLieuCuaLuot = async (t: TaiLieuDaDung) => {
    const biet = tepDaBiet[t.id];
    const viec = await chiBamMoiNhat(
      viecMoTaiLieu(biet?.co_khuon_goc, () => banThaoCuaTaiLieu(t.id)),
    );
    if (viec === null) return;
    if (viec.loai === "loi") toast.error(viec.cau);
    else if (viec.loai === "du_kien") moTaiLieuDinhKem(t.id);
    else if (viec.loai === "ban_tai_len")
      moBanTaiLen({ id: t.id, ten_tep: t.ten_tep, so_trang: biet?.so_trang ?? null });
    else if (vanNham(sanKhauRef.current, viec.banThao.id)) {
      datTabHep("ban_thao"); // bố cục hẹp: về tab "Bản thảo", hiệu ứng tiêu điểm lo phần còn lại
      khungSanKhau.current?.querySelector<HTMLElement>("[data-tieu-de-san-khau]")?.focus();
    } else moSanKhau(viec.banThao.id, viec.banThao);
  };
  const onMoTaiLieu = (t: TaiLieuDaDung) => void moTaiLieuCuaLuot(t);

  /**
   * Đính kèm một tệp: tải lên, gắn chip, KHÔNG mở khung và KHÔNG phân tích.
   *
   * Máy chủ chỉ đọc tài liệu thành đơn vị văn bản. Phần hiểu nó nói gì xảy ra ở
   * lượt hỏi kế tiếp (`hieu_tai_lieu`), đúng như ChatGPT/Claude: kẹp tệp là một
   * cử chỉ, không phải một lệnh chạy.
   *
   * Chưa có phiên nào thì máy chủ mở hộ một phiên và trả id về — đính kèm ở một
   * đoạn chat mới thôi là ngõ cụt.
   */
  const taiTepLen = async (tep: File) => {
    // Khách chưa đăng nhập: chặn NGAY, đừng để họ chờ hết một vòng đọc tệp rồi
    // nhận một câu 401 chung chung. `taiLen` không đi qua `goi()` nên nó không
    // dịch 401 thành câu "cần đăng nhập" như mọi endpoint khác — lời chặn đúng
    // chỗ là ở đây, trước khi tệp rời máy họ.
    if (!daDangNhap) {
      toast.error("Đăng nhập để KLAW đọc tài liệu của bạn.");
      return;
    }
    datLoiTaiLen(null);
    const loiTep = loiTruocKhiGui(tep.name, tep.size);
    if (loiTep) {
      toast.error(loiTep, { duration: 8000 });
      datLoiTaiLen(loiTep);
      return;
    }
    const idToast = toast.loading(
      seDungOcr(tep.name) ? "Đang nhận dạng chữ trong ảnh…" : "Đang đọc tài liệu…",
    );
    // Không hạn giờ (FR-032: không huỷ một lần đọc vì nó chạy lâu), nhưng lượt
    // tải khoá cả lối gửi, nên người dùng phải huỷ được. Huỷ mở khoá NGAY trên
    // sự kiện abort: chỗ treo có thể nằm trước `fetch` (lấy phiên đăng nhập),
    // nơi tín hiệu không với tới. Huỷ chỉ là trình duyệt thôi chờ — máy chủ có
    // thể vẫn đọc xong, như khi tải lại trang. Tệp đó không đi kèm câu hỏi nào
    // (câu hỏi chỉ mang `tai_lieu_ids` của chip), nhưng ở đoạn chat mới thì
    // phiên máy chủ mở hộ vẫn nằm lại.
    const huy = new AbortController();
    huy.signal.addEventListener("abort", () => {
      toast.dismiss(idToast);
      datDangDocTep(false);
    });
    huyTaiLen.current = huy;
    datDangDocTep(true);
    const phienHienCo = phienId ?? traCuu.hoiThoaiId ?? phienVuaTao.current;
    const kq = await taiLen(tep, phienHienCo, loaiDangSoan, huy.signal);
    // Đã huỷ thì lượt về muộn — kể cả về ĐƯỢC — bỏ đi im lặng: người dùng có
    // thể đã tải tệp khác, và cờ đang dựng là của lượt đó.
    if (huy.signal.aborted) return;
    datDangDocTep(false);
    if (!kq.ok) {
      // `duration` TƯỜNG MINH (Phase 9 U3): `toast.loading` mặc định
      // `duration: Infinity` (đúng — một chỉ báo đang tải không tự biến
      // mất), và sonner GIỮ NGUYÊN trường đó khi cùng `id` được cập nhật
      // thành `error`/`success` nếu lượt gọi sau không tự khai lại — toast
      // "kết quả" thừa kế "không bao giờ tắt" của toast "đang tải", và đó là
      // lý do nó nằm lì đè lên nút gửi. Khai lại `duration` ở CẢ hai nhánh.
      // Câu của máy chủ nói tên tệp và số trang thật: đủ lâu để đọc hết (8 giây),
      // và ở lại cạnh chỗ đính kèm sau khi toast tắt.
      toast.error(kq.error.message, { id: idToast, duration: 8000 });
      datLoiTaiLen(kq.error.message);
      return;
    }
    ghiNhoDinhKem({
      id: kq.data.id,
      ten_tep: kq.data.ten_tep || tep.name,
      co_khuon_goc: kq.data.co_khuon_goc === true,
      so_trang: kq.data.so_trang,
    });
    toast.success("Đã đính kèm. Hỏi gì về tài liệu này cũng được.", {
      id: idToast,
      duration: 4000,
    });
    if (phienHienCo !== null || !kq.data.hoi_thoai_id) return;
    // Phiên máy chủ vừa mở hộ. Ghim lên URL để tải lại trang không mất nó, và
    // ghi cả hai cái chốt một-lần (`phienDangHien`, `daGhim`) TRƯỚC khi điều
    // hướng: thiếu chúng, hiệu ứng đổi phiên coi đây là một phiên khác và xoá
    // đúng con chip vừa gắn.
    phienVuaTao.current = kq.data.hoi_thoai_id;
    phienDangHien.current = kq.data.hoi_thoai_id;
    daGhim.current = kq.data.hoi_thoai_id;
    taiLaiPhien();
    void navigate({ to: "/dung-thu", search: { phien: kq.data.hoi_thoai_id }, replace: true });
  };

  /**
   * Quá trần thì đẩy tờ CŨ NHẤT ra, không từ chối tờ mới: người dùng vừa bỏ
   * công tải lên một tệp, và câu trả lời đúng cho "tôi vừa đưa tờ thứ ba" là
   * giữ hai tờ gần nhất chứ không phải vứt việc họ vừa làm. Nói ra bằng toast
   * để không ai mất một tài liệu mà không biết.
   */
  const ghiNhoDinhKem = useCallback((tep: TepDinhKem) => {
    // Đọc danh sách qua ref chứ không qua updater của `setState`: updater phải
    // THUẦN (React gọi nó hai lần ở StrictMode), nên một `toast` bên trong sẽ
    // bật hai lần. Ref cũng giữ `ghiNhoDinhKem` không đổi tham chiếu.
    const conLai = dsDinhKem.current.filter((t) => t.id !== tep.id);
    const day = conLai.length >= TOI_DA_DINH_KEM;
    const giu = day ? conLai.slice(conLai.length - TOI_DA_DINH_KEM + 1) : conLai;
    datTepDaDinhKem([...giu, tep]);
    daHoiTep.current.add(tep.id);
    datTepDaBiet((cu) => ({ ...cu, [tep.id]: tep }));
    if (day) toast.info(`Mỗi lượt gửi được tối đa ${TOI_DA_DINH_KEM} tài liệu`);
  }, []);

  // Gợi ý chỉ ĐIỀN, không gửi — người dùng còn sửa câu (spec 2026-09-06 §4.1).
  // Khách cũng điền được: từ 2A họ hỏi thử được thật, nên đá họ sang trang đăng
  // nhập ngay ở cú bấm đầu tiên là hứa một việc rồi làm việc khác.
  const dienGoiY = (cau: string) => {
    datNhap(cau);
    oHoi.current?.focus();
  };

  /**
   * Nút hành động nhanh trên thẻ tài liệu: điền câu hỏi VÀ gắn lại tệp.
   *
   * Không tự gửi — giống mọi gợi ý khác trong màn này, người hỏi còn sửa câu.
   * Gắn lại TẤT CẢ tài liệu của lượt đó (tối đa `TOI_DA_DINH_KEM`): bấm "đối
   * chiếu luật" dưới một lượt so sánh mà chỉ mang theo tờ A là lặng lẽ đổi câu
   * hỏi thành một câu khác câu người dùng vừa bấm.
   */
  const hanhDongTaiLieu = (cau: string, ds: TaiLieuDaDung[]) => {
    datTepDaDinhKem(ds.slice(0, TOI_DA_DINH_KEM).map((t) => ({ id: t.id, ten_tep: t.ten_tep })));
    dienGoiY(cau);
  };

  /** Nhánh `soan_thao_hoi` khi `can_dang_nhap` (Task 21) — luôn quay lại đúng
   *  màn này sau đăng nhập, "/dung-thu" nằm trong danh sách trắng của `?next=`. */
  const onDangNhapDeSoan = () => void navigate({ to: "/dang-nhap", search: { next: "/dung-thu" } });

  // `phienMoi` PHẢI tự xoá `traCuu.hoiThoaiId` cùng lúc chuyển `?phien=` về
  // rỗng: nếu chỉ đổi URL, `traCuu.hoiThoaiId` cũ (khác `null`) còn sống qua
  // hết lượt effect của lần render đó, và effect (2) sẽ thấy `phienId ===
  // undefined` + `hoiThoaiId !== null` rồi bật ngược URL về phiên vừa rời —
  // "Phiên mới" lặng lẽ ghi tiếp vào phiên cũ (có thể đã bị xoá).
  //
  // Sân khấu (bản thảo, bản tải lên) thuộc về phiên đang rời: đóng qua ĐÚNG cửa
  // đóng, không để nó đứng cạnh một cuộc trò chuyện trắng.
  const phienMoi = useCallback(() => {
    onDongSanKhau();
    datLaiTraCuu();
    void navigate({ to: "/dung-thu", search: {} });
  }, [onDongSanKhau, datLaiTraCuu, navigate]);

  // Vỏ ứng dụng có nút "Phiên mới" riêng và nó phải làm ĐÚNG việc ở trên, không
  // phải chỉ đổi URL — nên trang mượn hàm của mình cho context khi đang đứng ở
  // đây, và trả lại `null` lúc rời đi để nút kia quay về đường điều hướng thường.
  useEffect(() => {
    datHanhDongPhienMoi(phienMoi);
    return () => datHanhDongPhienMoi(null);
  }, [datHanhDongPhienMoi, phienMoi]);

  // Đoạn chat của khách sống trong state trang này, nên chỉ trang này lấy được.
  // Nút Đăng nhập/Đăng ký ở vỏ gọi `catThreadTruocKhiRoi` ngay trước khi rời và
  // cần đúng hàm này để có nội dung mà cất. Kèm cả lượt ĐANG hiện: nó chưa vào
  // `luuTru` (chỉ vào đó khi câu sau bắt đầu), và nó thường là lượt khiến người
  // dùng quyết định đăng nhập.
  useEffect(() => {
    datLayThreadKhach(() =>
      traCuu.cauHoi !== null && traCuu.ketQua !== null
        ? [...luuTru, { cauHoi: traCuu.cauHoi, ketQua: traCuu.ketQua }]
        : luuTru,
    );
    return () => datLayThreadKhach(null);
  }, [datLayThreadKhach, luuTru, traCuu.cauHoi, traCuu.ketQua]);

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
    datSoanThao(null);
    onDongSanKhau(); // ba khung (đối chiếu/soạn thảo/sân khấu) loại trừ nhau — xoá sân khấu qua ĐÚNG một cửa (xem chú thích ở đó)
    doiChieu.mo({
      docId: trichDan.doc_id,
      // `khop_tai_id`, KHÔNG `provision_id`: hai id khác nhau ở 73,6% số Điều.
      khopTaiId: trichDan.khop_tai_id,
      duongDan: trichDan.duong_dan,
      quote: trichDan.quote,
      hieuLuc: trichDan.hieu_luc,
    });
  };

  const chiSoDangMoCua = (ketQua: TraCuuKetQua) =>
    dangMo !== null && dangMo.trace === ketQua.trace_id ? dangMo.chiSo : null;

  const dangMoSoanThao = soanThao !== null;
  // Nhại `KhungDoiChieu` (components/klaw/KhungDoiChieu.tsx:129-169) — TÁCH làm
  // hai effect như bản gốc, không gộp: `haiCot` đổi theo resize (media query
  // sống), nếu chung effect với Esc/tiêu điểm thì mỗi lần vượt ngưỡng 68rem lúc
  // khung đang mở sẽ chạy lại cleanup+effect và giật tiêu điểm ra khỏi ô đang gõ
  // dở về control đầu khung — đây chính là lỗi round 1 để lại.
  useEffect(() => {
    if (!dangMoSoanThao) return;
    const noiMo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    khungSoanThao.current
      ?.querySelector<HTMLElement>("button, [href], input, textarea, select")
      ?.focus();
    const nghe = (su: KeyboardEvent) => {
      // Escape trong ô nhập/chọn của biểu mẫu là để đóng dropdown hay bỏ gõ — không
      // phải để huỷ bản thảo đang điền (không có nơi lưu). Chỉ đóng khung khi phím
      // đến từ ngoài các ô đó và chưa bị ai xử lý.
      if (su.key !== "Escape" || su.defaultPrevented) return;
      if (su.target instanceof HTMLElement && su.target.closest("input, textarea, select")) return;
      datSoanThao(null);
    };
    window.addEventListener("keydown", nghe);
    return () => {
      window.removeEventListener("keydown", nghe);
      if (noiMo !== null && noiMo.isConnected) noiMo.focus();
    };
  }, [dangMoSoanThao]);

  // Khoá cuộn nền RIÊNG, chỉ theo `haiCot`: resize qua ngưỡng không được đụng
  // tới tiêu điểm ở effect trên.
  useEffect(() => {
    if (!dangMoSoanThao || haiCot) return;
    const cuCuon = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = cuCuon;
    };
  }, [dangMoSoanThao, haiCot]);

  // R5 (canvas-tai-lieu Phase 2): sân khấu đứng ngang hàng khung soạn thảo và
  // khung đối chiếu nay phải đóng được như hai khung kia. Bọc gắn ở CẢ hai nơi
  // sân khấu render (cột phải ở bố cục rộng, dialog toàn màn ở bố cục hẹp) —
  // chỉ một trong hai còn trong DOM tại một thời điểm.
  const khungSanKhau = useRef<HTMLDivElement | null>(null);
  const dangMoSanKhau = sanKhau !== null;
  /** Nội dung sân khấu ĐÃ vẽ được: bản thảo đã tải, hoặc bản tải lên. Đổi khoá
   *  (mở, tải xong, chuyển từ "Bản tải lên" sang bản thảo vừa mở) là lúc đưa
   *  tiêu điểm vào tiêu đề — không phải lúc mở khi chỉ có "Đang mở bản thảo…". */
  const noiDungSanKhau =
    sanKhau === null
      ? null
      : sanKhau.loai === "ban_tai_len"
        ? `ban_tai_len:${sanKhau.viecId}`
        : banThaoMo !== null && banThaoMo.id === sanKhau.banThaoId
          ? `ban_thao:${sanKhau.banThaoId}`
          : null;
  // Trả tiêu điểm khi đóng — TÁCH khỏi effect Esc ngay dưới (không gộp theo
  // `onDongSanKhau`, đổi tham chiếu theo URL). Nơi mở đã ghi ở handler mở
  // (`ghiNoiMoSanKhau`). Cleanup chạy SAU lượt commit đóng, nên ở bố cục hẹp
  // cây chat đã dựng lại: nút mở cũ đã rời DOM thì tìm bản dựng lại của nó
  // (`data-mo-san-khau`), không thì ô hỏi — không bao giờ `<body>`.
  useEffect(() => {
    if (!dangMoSanKhau) return;
    return () => {
      const noiTra = noiTraTieuDiem(
        noiMoSanKhau.current,
        (khoa) => document.querySelector<HTMLElement>(`[data-mo-san-khau="${CSS.escape(khoa)}"]`),
        // Cố ý đọc LÚC cleanup: ở bố cục hẹp ô hỏi vừa được dựng lại (nút mới),
        // còn lúc mở thì nó không có trong DOM (`null`).
        // eslint-disable-next-line react-hooks/exhaustive-deps
        oHoi.current,
      );
      noiMoSanKhau.current = null;
      noiTra?.focus();
    };
  }, [dangMoSanKhau]);
  // Tiêu điểm vào TIÊU ĐỀ sân khấu (`data-tieu-de-san-khau`, `tabIndex=-1`):
  // trình đọc màn hình đọc tên thứ vừa mở, Tab đi tiếp vào thanh công cụ. Không
  // giật tiêu điểm khi tab hẹp đang là "Trợ lý" (sân khấu không có trong DOM).
  useEffect(() => {
    if (noiDungSanKhau === null || (!haiCot && tabHep !== "ban_thao")) return;
    const khung = khungSanKhau.current;
    (
      khung?.querySelector<HTMLElement>("[data-tieu-de-san-khau]") ??
      khung?.querySelector<HTMLElement>("button, [href], input, textarea, select")
    )?.focus();
  }, [noiDungSanKhau, haiCot, tabHep]);
  // Esc đóng sân khấu — cùng khuôn `KhungDoiChieu.tsx:132-138`, cộng chốt
  // input/textarea/select của khung soạn thảo: sửa dữ kiện một mục
  // (`DrawerSuaMuc`) cũng là gõ trong ô, Esc ở đó phải thoát dropdown/bỏ gõ chứ
  // không đóng cả sân khấu đang có dữ liệu chưa lưu.
  //
  // `NganXepDrawer` (mở tấm "Sửa mục"/"Căn cứ" TRÊN sân khấu) có listener Esc
  // RIÊNG của nó, cũng ở `window`, và không gọi `preventDefault`. Không chốt
  // thêm thì MỘT lần Esc đóng CẢ tấm lẫn sân khấu cùng lúc — mất luôn bản sửa
  // dữ kiện đang dở, không phải "đóng từng lớp một". Tấm mang `role="dialog"`
  // (NganXepDrawer.tsx) và luôn nằm SÂU HƠN gốc sân khấu trong DOM; gốc sân
  // khấu ở bố cục hẹp CŨNG là `role="dialog"` — nên so sánh với chính
  // `khungSanKhau.current` chứ không chỉ hỏi "có dialog nào không".
  useEffect(() => {
    if (!dangMoSanKhau) return;
    const nghe = (su: KeyboardEvent) => {
      if (su.key !== "Escape" || su.defaultPrevented) return;
      if (su.target instanceof HTMLElement && su.target.closest("input, textarea, select")) return;
      if (su.target instanceof HTMLElement) {
        const dialogGanNhat = su.target.closest('[role="dialog"]');
        if (dialogGanNhat !== null && dialogGanNhat !== khungSanKhau.current) return;
      }
      onDongSanKhau();
    };
    window.addEventListener("keydown", nghe);
    return () => window.removeEventListener("keydown", nghe);
  }, [dangMoSanKhau, onDongSanKhau]);

  // ── Trần lượt mỗi phiên + hạn mức (spec 2A §8) ──────────────────────────
  // Trần phiên là con số của MÁY CHỦ (`GET /han-muc`): khách 10, Miễn phí 20,
  // Cá nhân 50. Đếm ở client chỉ để KHOÁ SỚM ô hỏi và nói trước lý do — máy chủ
  // vẫn là nơi quyết định (403 ở lượt thứ n+1), nên hai bên lệch nhau thì phía
  // máy chủ thắng và người dùng thấy đúng câu nó gửi về.
  const tranPhien = hanMuc.hanMuc?.phien.luot_toi_da ?? null;
  const soLuotPhien = daTai.length + luuTru.length + (traCuu.ketQua !== null ? 1 : 0);
  const phienDay = tranPhien !== null && soLuotPhien >= tranPhien;
  const phienDai = tranPhien !== null && !phienDay && soLuotPhien >= Math.ceil(tranPhien * 0.75);
  // Chip cạnh ô hỏi theo dõi ĐÚNG hạn mức hỏi đáp, không phải "mục ràng buộc
  // đầu tiên": gói Cá nhân hỏi không giới hạn nhưng vẫn có trần bản thảo, và
  // "Còn 3 bản thảo hôm nay" đứng cạnh ô hỏi là một con số nói về việc khác.
  // Không có mục đó, hoặc mục đó không giới hạn ⇒ không chip.
  const mucChat =
    hanMuc.hanMuc?.muc.find((m) => m.khoa === (laKhach ? "khach_24h" : "hoi_dap_ngay")) ?? null;
  const mucChip = mucChat !== null && !laKhongGioiHan(mucChat.han_muc) ? mucChat : null;
  const hetLuot = mucChip !== null && mucChip.da_dung >= mucChip.han_muc;
  const plan = hanMuc.hanMuc?.plan ?? null;
  const biKhoa = laBiKhoa(hanMuc.hanMuc);
  // Gói Cá nhân hết hạn ⇒ máy chủ hạ người dùng về `free` NHƯNG vẫn gửi mốc cũ.
  // Đó là cách duy nhất phân biệt "chưa từng nâng" với "vừa rơi xuống".
  const hetHanPro =
    plan === "free" &&
    hanMuc.hanMuc?.het_han_luc != null &&
    Date.parse(hanMuc.hanMuc.het_han_luc) < Date.now();
  const ngayHetHan =
    hanMuc.hanMuc === null
      ? ""
      : dinhDangMoc(hanMuc.hanMuc.het_han_luc, hanMuc.hanMuc.mui_gio).slice(6);
  /** Khách đã hết lượt thử. Phải hiện được cả khi dòng chat trống — tải lại
   *  trang là mất đoạn chat nhưng KHÔNG được lượt mới, và một ô hỏi xám không
   *  kèm lý do là chỗ người dùng bỏ đi. */
  const khachHetLuot = hetLuot && laKhach;
  /** Ô hỏi đóng khi câu trả lời tiếp theo CHẮC CHẮN bị từ chối VÀ màn hình đã
   *  nói được lối ra ngay tại chỗ. Hết lượt của người ĐÃ đăng nhập không nằm
   *  trong nhóm đó: lối ra của họ (mốc mở lại, nút Nâng cấp) đi kèm 429 của máy
   *  chủ, nên khoá sớm ở client là khoá luôn cả đường đi tiếp (spec §7.3). */
  const khoaOHoi =
    biKhoa || traCuu.dangChay || hoiThoai.loiChiTiet !== null || phienDay || khachHetLuot;

  const chuaHoiGiCa =
    daTai.length === 0 &&
    luuTru.length === 0 &&
    traCuu.cauHoi === null &&
    hoiThoai.loiChiTiet === null &&
    !hoiThoai.dangTaiChiTiet &&
    !khachHetLuot &&
    !biKhoa;

  /** Bản thảo ĐÚNG id đang mở, đã tải xong — khác `banThaoMo` trần trụi để
   *  không thoáng hiện bản thảo CŨ trong khoảnh khắc `layBanThao` của bản MỚI
   *  còn đang chạy (chuyển thẳng từ bản thảo A sang bản thảo B). Dùng chung ở
   *  CẢ hai bố cục (rộng/hẹp, Task 26) — tính một lần, không hai bản chép tay. */
  const banThaoDangTaiXong =
    banThaoIdSanKhau !== null && banThaoMo !== null && banThaoMo.id === banThaoIdSanKhau
      ? banThaoMo
      : null;
  /** Sân khấu chiếm `<main>` chỉ khi CÓ bản thảo đang mở VÀ đủ rộng — dưới
   *  68rem có nhánh riêng (Task 26, tab "Bản thảo | Trợ lý" toàn màn). */
  const dangSanKhau = sanKhau !== null && haiCot;
  const nhanSanKhau = sanKhau?.loai === "ban_tai_len" ? "Bản tải lên" : "Bản thảo";
  /** Nội dung sân khấu — MỘT chỗ cho cả hai bố cục (cột phải / tab hẹp). Đang
   *  tải ĐÚNG bản thảo đang mở, hoặc đang chuyển sang bản khác: trạng thái chờ
   *  thay vì thoáng hiện nội dung của bản trước. */
  const veSanKhau = (toanMan: boolean) =>
    sanKhau?.loai === "ban_tai_len" ? (
      <SanKhauBanTaiLen
        viecId={sanKhau.viecId}
        tenTep={sanKhau.tenTep}
        soTrang={sanKhau.soTrang}
        onDong={onDongSanKhau}
        onDienBieuMau={() => void dienBieuMau(sanKhau.viecId)}
      />
    ) : banThaoDangTaiXong !== null ? (
      <SanKhauBanThao
        // Bản thảo khác = sân khấu mới: lượt lưu, câu lỗi, mức thu phóng và
        // tấm "Sửa mục" của bản trước không sang bản này.
        key={banThaoDangTaiXong.id}
        banThao={banThaoDangTaiXong}
        cauTruc={cauTrucSanKhau}
        truongMau={truongMauSanKhau}
        dangTai={dangTaiKhungSanKhau}
        loiKhung={loiKhungSanKhau}
        onTaiLaiKhung={() => datLanTaiKhungSanKhau((n) => n + 1)}
        mucDangChon={mucDangChonSanKhau}
        onChonMuc={datMucDangChonSanKhau}
        capNhatBanThao={capNhatBanThaoMo}
        onLui={onLuiSanKhau}
        onDong={onDongSanKhau}
        onPhimTat={onPhimTatSanKhau}
        toanMan={toanMan}
        nhapODien={nhapODien[banThaoDangTaiXong.id] ?? {}}
        datNhapODien={(doi) =>
          datNhapODien((cu) => ({
            ...cu,
            [banThaoDangTaiXong.id]: doi(cu[banThaoDangTaiXong.id] ?? {}),
          }))
        }
      />
    ) : (
      <div className="flex h-full items-center justify-center">
        <p className="m-0 text-[14px] text-muted-foreground" role="status">
          Đang mở bản thảo…
        </p>
      </div>
    );

  // Cột chat (dòng hội thoại + ô hỏi) — MỘT cây JSX dùng ở NHIỀU chỗ tuỳ bố
  // cục: bình thường nó đứng một mình; khi sân khấu mở ở bố cục rộng nó là
  // cột TRÁI cạnh `TayKeo` + khung bản thảo; ở bố cục hẹp nó là nội dung tab
  // "Trợ lý". Tách biến thay vì viết lặp nhiều lần — các bản chép tay dễ trôi
  // nhau ở lần sửa sau.
  const noiDungChat = (
    <div
      inert={(doiChieu.dang !== null || soanThao !== null) && !haiCot}
      className={cn("flex min-w-0 flex-1 flex-col", soanThao !== null && haiCot && "max-w-[420px]")}
      // Sàn bề rộng (Phase 9 U4) — xem `sanRongChat`/`keo-dan.ts` cho nguyên
      // nhân đo được (1512px cửa sổ → chat ~215px) và vì sao sửa TẠI ĐÂY.
      style={{ minWidth: sanRongChat(soanThao !== null && haiCot) }}
    >
      <div className="mx-auto flex w-full max-w-[860px] flex-1 flex-col px-4">
        {/* Tiêu đề cấp 1 BỀN, không nhìn thấy. Tiêu đề duy nhất của màn này
                nằm trong trạng thái rỗng ngay dưới và biến mất sau câu hỏi đầu
                tiên, nên nâng nó lên h1 sẽ để lại một trang không có h1 đúng
                lúc trang có nhiều nội dung nhất. Trình đọc màn hình nhảy theo
                h1 để biết mình đang ở đâu. */}
        <h1 className="sr-only">Trợ lý KLAW — tra cứu pháp luật lao động</h1>
        {/* Hai lời báo cấp trang, đứng TRÊN dòng chat vì cả hai đều đúng kể
                cả khi chưa có lượt nào: gói vừa hết hạn, và đoạn chat thử không
                mang sang được. Nằm ngoài nhánh `chuaHoiGiCa` nên không biến mất
                cùng dòng chat. */}
        {hetHanPro && !daTatHetHan && !daTat(khoaHetHan(ngayHetHan)) && (
          <div className="mt-8">
            <TheHetLuot
              loai="het_han"
              chiTiet={`Gói Cá nhân đã hết hạn ngày ${ngayHetHan}. Gia hạn 30 ngày để tiếp tục hỏi 500 lượt mỗi ngày và soạn 20 bản thảo mỗi ngày.`}
              onNangGoi={moNangGoi}
              onTat={() => {
                ghiNhoDaTat(khoaHetHan(ngayHetHan));
                datDaTatHetHan(true);
              }}
            />
          </div>
        )}
        {biKhoa && <TheTaiKhoanKhoa />}
        {loiNhap !== null && (
          <p role="status" className="mt-8 mb-0 text-[13px] text-muted-foreground">
            {loiNhap}
          </p>
        )}
        {chuaHoiGiCa ? (
          <ManChao onChonGoiY={dienGoiY} />
        ) : (
          <div aria-live="polite" aria-label="Hội thoại với KLAW" className="flex-1 py-8">
            {hoiThoai.dangTaiChiTiet && (
              <p className="m-0 mb-6 text-[13px] text-muted-foreground" aria-live="polite">
                Đang mở phiên…
              </p>
            )}
            {hoiThoai.loiChiTiet !== null && (
              <div className="mb-6 rounded-xl border border-dashed border-border px-4 py-3">
                <p className="m-0 text-[14px] leading-6 text-foreground">
                  {hoiThoai.loiChiTiet.message}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={phienMoi}
                    className="focus-brass inline-flex min-h-9 cursor-pointer items-center rounded-lg border border-border px-3 text-[13px] font-medium text-primary hover:bg-[var(--color-paper-100)]"
                  >
                    Phiên mới
                  </button>
                </div>
              </div>
            )}
            <div className="flex flex-col gap-8">
              {daTai.map((l) => (
                <Luot
                  key={`da-luu-${l.thuTu}`}
                  cauHoi={l.cauHoi}
                  traceId={l.traceId}
                  tepDinhKem={tepCuaLuotDaLuu(l.ketQua)}
                  hanhDongTep={hanhDongTep}
                >
                  {l.ketQua === null ? (
                    <p className="m-0 text-[14px] leading-6 text-muted-foreground">
                      Lượt này được lưu ở định dạng cũ nên tôi không hiển thị lại được.
                    </p>
                  ) : (
                    <TheKetQua
                      ketQua={l.ketQua}
                      cauHoiGoc={l.cauHoi}
                      chiSoDangMo={chiSoDangMoCua(l.ketQua)}
                      onChonTrichDan={(chiSo) => {
                        const kq = l.ketQua;
                        if (kq !== null) chonTrichDan(kq, chiSo);
                      }}
                      onSoanThao={moSoanThao}
                      onChip={dienGoiY}
                      onDangNhap={onDangNhapDeSoan}
                      onMoBanThao={moSanKhau}
                      onMoNeoTaiLieu={moNeoTaiLieu}
                      onHanhDongTaiLieu={hanhDongTaiLieu}
                      onMoTaiLieu={onMoTaiLieu}
                    />
                  )}
                </Luot>
              ))}

              {luuTru.map((luot) => (
                <Luot
                  key={luot.ketQua.trace_id}
                  cauHoi={luot.cauHoi}
                  traceId={luot.ketQua.trace_id}
                  tepDinhKem={tepDaLuu[luot.ketQua.trace_id]}
                  hanhDongTep={hanhDongTep}
                >
                  <TheKetQua
                    ketQua={luot.ketQua}
                    cauHoiGoc={luot.cauHoi}
                    chiSoDangMo={chiSoDangMoCua(luot.ketQua)}
                    onChonTrichDan={(chiSo) => chonTrichDan(luot.ketQua, chiSo)}
                    onSoanThao={moSoanThao}
                    onChip={dienGoiY}
                    onDangNhap={onDangNhapDeSoan}
                    onMoBanThao={moSanKhau}
                    onMoNeoTaiLieu={moNeoTaiLieu}
                    onHanhDongTaiLieu={hanhDongTaiLieu}
                    onMoTaiLieu={onMoTaiLieu}
                  />
                </Luot>
              ))}

              {traCuu.cauHoi !== null && (
                <Luot
                  cauHoi={traCuu.cauHoi}
                  traceId={traCuu.traceId}
                  tepDinhKem={tepCuaLuot}
                  hanhDongTep={hanhDongTep}
                >
                  {traCuu.dangChay && (
                    <TrangThaiCho
                      cacBuoc={traCuu.cacBuoc}
                      daPhat={traCuu.daPhat}
                      onHuy={traCuu.huy}
                    />
                  )}
                  {traCuu.loi !== null && (
                    <>
                      {/* 429 của gói Miễn phí là lối cụt DUY NHẤT mở được
                              bằng tiền, nên đó là chỗ duy nhất mời nâng gói.
                              Khách (`plan` chưa phải "free") thì việc cần làm
                              là đăng nhập, không phải trả tiền. */}
                      <BaoLoi
                        loi={traCuu.loi}
                        onThuLai={traCuu.thuLai}
                        {...(traCuu.loi.kind === "rate_limited" && plan === "free"
                          ? { onNangGoi: moNangGoi }
                          : {})}
                      />
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
                      ketQua={
                        hoSoDaSua !== null && hoSoDaSua.trace === traCuu.ketQua.trace_id
                          ? { ...traCuu.ketQua, ho_so_da_dung: hoSoDaSua.hoSo }
                          : traCuu.ketQua
                      }
                      {...(traCuu.cauHoi !== null ? { cauHoiGoc: traCuu.cauHoi } : {})}
                      chiSoDangMo={chiSoDangMoCua(traCuu.ketQua)}
                      onChonTrichDan={(chiSo) => {
                        const kq = traCuu.ketQua;
                        if (kq !== null) chonTrichDan(kq, chiSo);
                      }}
                      onSoanThao={moSoanThao}
                      onChip={dienGoiY}
                      onDangNhap={onDangNhapDeSoan}
                      onMoBanThao={moSanKhau}
                      onMoNeoTaiLieu={moNeoTaiLieu}
                      onHanhDongTaiLieu={hanhDongTaiLieu}
                      onMoTaiLieu={onMoTaiLieu}
                      onSuaHoSo={(khoa, giaTri) => {
                        const id = phienId ?? traCuu.hoiThoaiId;
                        // `error.message` đã là câu tiếng Việt hiển thị thẳng được
                        // (xem `ApiError` trong `klaw.ts`) — 422 "giá trị này giống
                        // một điều luật/số văn bản" của máy chủ phải tới đúng câu
                        // đó, không phải một câu chung chung nuốt mất lý do.
                        if (id === null || id === undefined) {
                          // Hiện chỉ xảy ra khi ẩn danh (khách chưa có
                          // `hoi_thoai_id`); một việc sau trong kế hoạch này sẽ
                          // điền hồ sơ tình huống ngay từ câu hỏi kể cả cho khách,
                          // lúc đó bút chì này bấm được mà không còn ngả rẽ này.
                          toast.error("Cần một cuộc trò chuyện đã đăng nhập để sửa dữ kiện này.");
                          return;
                        }
                        const trace = traCuu.ketQua?.trace_id ?? null;
                        void suaHoSoPhien(id, khoa, giaTri).then((kq) => {
                          if (!kq.ok) toast.error(kq.error.message);
                          else if (trace !== null)
                            datHoSoDaSua({ trace, hoSo: kq.data.ho_so_da_dung });
                        });
                      }}
                    />
                  )}
                  {traCuu.loiLuu !== null && (
                    <p className="mt-3 mb-0 text-[12px] text-muted-foreground" role="status">
                      {traCuu.loiLuu}
                    </p>
                  )}
                  {/* Lượt đã dừng mà KHÔNG có kết quả và KHÔNG có lỗi.
                          Ba nhánh trên đều là `false` sau khi người dùng bấm
                          Huỷ, và cũng sau khi luồng SSE chết giữa chừng — cả
                          hai lần đều để lại câu hỏi nằm trơ một mình, không
                          khác gì một lượt đang chờ mãi mãi. Không đoán xem
                          nguyên nhân nào: nói đúng điều quan sát được, rồi
                          đưa lại đường chạy lại đúng câu đó. */}
                  {!traCuu.dangChay && traCuu.loi === null && traCuu.ketQua === null && (
                    <div className="rounded-xl border border-dashed border-border px-4 py-3">
                      <p className="m-0 text-[14px] leading-6 text-muted-foreground">
                        Lượt tra cứu này đã dừng, chưa có câu trả lời.
                      </p>
                      <button
                        type="button"
                        onClick={traCuu.thuLai}
                        className="focus-brass mt-2 inline-flex min-h-9 cursor-pointer items-center rounded-lg border border-border px-3 text-[13px] font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]"
                      >
                        Hỏi lại câu này
                      </button>
                    </div>
                  )}
                </Luot>
              )}
            </div>

            {/* Cuối dòng chat, ngay trên ô hỏi đang bị khoá — nói lý do ở
                    chỗ người dùng vừa nhìn thấy câu trả lời cuối, không phải ở
                    một góc khác của màn hình.

                    Hết lượt ĐÈ trần phiên: với khách hai ngưỡng cùng là 10 nên
                    chúng chạm cùng lúc, và lúc đó "mở phiên mới" là lời khuyên
                    sai — phiên mới không trả lại lượt nào. */}
            {(khachHetLuot || phienDay || phienDai) && (
              <div className="mt-8 flex flex-col gap-4">
                {khachHetLuot && mucChip !== null && (
                  <TheHetLuot
                    loai="khach"
                    chiTiet={`Bạn đã dùng ${mucChip.han_muc} lượt thử. Đăng nhập miễn phí để tiếp tục, lưu đoạn chat này và có 100 lượt mỗi ngày.`}
                    onCatThread={catThreadTruocKhiRoi}
                  />
                )}
                {!khachHetLuot && phienDay && (
                  <TheHetLuot
                    loai="phien"
                    chiTiet={`Phiên này đã đủ ${tranPhien} lượt. Mở phiên mới để tiếp tục.`}
                    onPhienMoi={phienMoi}
                  />
                )}
                {!khachHetLuot && phienDai && (
                  <p className="m-0 text-[12px] text-muted-foreground">
                    Phiên dài rồi, mở phiên mới để câu trả lời bám sát hơn.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bảng dữ kiện chỉ mở THEO YÊU CẦU ("Dữ kiện đã đọc" trên con chip, hay
          một neo trong câu trả lời) — trong drawer, không chen vào dòng chat. */}
      <NganXepDrawer
        ngan={moTaiLieu ? [{ id: "du-kien", tieuDe: "Dữ kiện đã đọc", noiDung: null }] : []}
        onDong={dongTaiLieu}
        toanMan={!haiCot}
        render={() => (
          <TaiLieuDuKien
            hoiThoaiId={phienId ?? traCuu.hoiThoaiId}
            loai={loaiDangSoan}
            onMoBanTaiLen={(tl) => {
              dongTaiLieu();
              moBanTaiLen(tl);
            }}
            onDienBieuMau={(id) => {
              dongTaiLieu();
              void dienBieuMau(id);
            }}
            onChip={(cau) => {
              dongTaiLieu();
              dienGoiY(cau);
            }}
            donViDangMo={donViDangMo}
          />
        )}
      />
      <OSoanCauHoi
        oHoi={oHoi}
        nhap={nhap}
        datNhap={datNhap}
        khoa={khoaOHoi}
        onGui={gui}
        mucChip={mucChip}
        dangCho={dangKiemPhien && !chuaCauHinh}
        onChonTep={(tep) => void taiTepLen(tep)}
        dangDocTep={dangDocTep}
        onHuyTaiTep={() => huyTaiLen.current?.abort()}
        loiTaiLen={loiTaiLen}
        tepDaDinhKem={tepDaDinhKem}
        hanhDongTep={hanhDongTep}
        onBoDinhKem={(id) => {
          datTepDaDinhKem((truoc) => truoc.filter((t) => t.id !== id));
        }}
      />
      {/* Mốc cuộn SAU ô soạn (sticky bottom-0): cuộn tới đây là tới đáy thật,
          ô soạn về chỗ tĩnh của nó. Đặt trước ô soạn thì đáy thẻ cuối — nút
          "Mở bản thảo" — nằm dưới ô soạn. Màn chào không cuộn. */}
      {!chuaHoiGiCa && <div ref={cuoi} />}
    </div>
  );

  return (
    <AppShell active="/dung-thu">
      <div ref={khungHang} className="flex min-h-0 flex-1">
        {!haiCot && sanKhau !== null ? (
          /* Bố cục hẹp (Task 26, spec 2026-09-09 §9.7): dưới 68rem không đủ
             chỗ cho chat và bản thảo cạnh nhau — toàn màn hình thành một
             trong hai tab. */
          <div
            role="dialog"
            aria-modal
            aria-label={nhanSanKhau}
            ref={khungSanKhau}
            className="fixed inset-0 z-50 flex flex-col bg-background"
          >
            <div className="min-h-0 flex-1">
              {tabHep === "ban_thao" ? (
                veSanKhau(true)
              ) : (
                <div className="h-full overflow-y-auto">{noiDungChat}</div>
              )}
            </div>

            {/* Thanh tab hai nút: trạng thái đang chọn qua `aria-pressed`
                (đọc được bằng trình đọc màn hình, không chỉ tô màu). */}
            {/* `bg-background`: thanh tab nằm trên một lớp phủ toàn màn, không
                tô nền thì chữ của trang bên dưới lộ qua. */}
            <div className="flex shrink-0 border-t border-border bg-background">
              {(
                [
                  ["ban_thao", nhanSanKhau],
                  ["tro_ly", "Trợ lý"],
                ] as const
              ).map(([id, nhan]) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={tabHep === id}
                  onClick={() => datTabHep(id)}
                  className={cn(
                    "focus-brass flex flex-1 cursor-pointer items-center justify-center gap-1.5 border-t-2 py-3 text-[13px] font-medium transition-colors",
                    tabHep === id
                      ? "border-[var(--color-brass-600)] text-[var(--color-brass-600)]"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {nhan}
                </button>
              ))}
            </div>
          </div>
        ) : dangSanKhau ? (
          <>
            {/* Chat trái + `TayKeo` + bản thảo phải (D5, canvas-tai-lieu Phase
                2) — cùng khuôn với khung đối chiếu bên dưới: chat luôn
                `flex-1` (tự co theo phần còn lại), khung bản thảo có độ rộng
                RIÊNG do người dùng kéo. Trợ lý không còn lùi thành cửa sổ nổi
                che tài liệu — đúng điều Phase 2 sửa. */}
            {noiDungChat}
            <TayKeo
              giaTri={rongSanKhau}
              bien={bienSanKhau}
              nhan="Kéo để đổi độ rộng khung bản thảo"
              dieuKhienId="san-khau-ban-thao"
              chieu={-1}
              onDoi={datRongSanKhauVaLuu}
              onThuGon={() =>
                datRongSanKhauVaLuu(
                  rongSanKhau > bienSanKhau.min ? bienSanKhau.min : RONG_SAN_KHAU_MAC_DINH,
                )
              }
              onMacDinh={() => datRongSanKhauVaLuu(RONG_SAN_KHAU_MAC_DINH)}
            />
            <div
              id="san-khau-ban-thao"
              ref={khungSanKhau}
              role="region"
              aria-label={nhanSanKhau}
              className="min-h-0 shrink-0 border-l border-border"
              style={{ width: kepRong(rongSanKhau, bienSanKhau) }}
            >
              {veSanKhau(false)}
            </div>
          </>
        ) : (
          <>
            {noiDungChat}

            {/* Khung nguyên văn. Ở bố cục hai cột nó chiếm một cột thật; dưới ngưỡng
                đó nó tự phủ toàn màn hình, nên thẻ bọc phải KHÔNG có kích thước —
                `hidden` sẽ giấu luôn cả khung ở chế độ phủ màn hình. */}
            {doiChieu.dang !== null && (
              <>
                {haiCot && (
                  <TayKeo
                    giaTri={rongDoiChieu}
                    bien={bienDoiChieu}
                    nhan="Kéo để đổi độ rộng khung điều khoản"
                    dieuKhienId="khung-doi-chieu"
                    chieu={-1}
                    onDoi={datRongVaLuu}
                    onThuGon={() =>
                      datRongVaLuu(
                        rongDoiChieu > bienDoiChieu.min
                          ? bienDoiChieu.min
                          : RONG_DOI_CHIEU_MAC_DINH,
                      )
                    }
                    onMacDinh={() => datRongVaLuu(RONG_DOI_CHIEU_MAC_DINH)}
                  />
                )}
                <div
                  className={cn(
                    "shrink-0",
                    haiCot && "border-l border-border bg-[var(--color-paper-50)] p-3",
                  )}
                  style={haiCot ? { width: kepRong(rongDoiChieu, bienDoiChieu) } : undefined}
                >
                  <KhungDoiChieu
                    id="khung-doi-chieu"
                    khopTaiId={doiChieu.dang.khopTaiId}
                    {...(doiChieu.dang.duongDan === undefined
                      ? {}
                      : { duongDan: doiChieu.dang.duongDan })}
                    quote={doiChieu.dang.quote ?? null}
                    hieuLuc={doiChieu.dang.hieuLuc ?? null}
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
              </>
            )}

            {/* Khung soạn thảo (spec soạn-thảo-trong-chat §5.3). Hai cột: chiếm phần
                còn lại vì màn soạn thảo có hai pane; dưới 68rem: phủ toàn màn như
                KhungDoiChieu. */}
            {soanThao !== null && (
              <div
                ref={khungSoanThao}
                className={cn(
                  haiCot
                    ? "min-w-[640px] flex-1 border-l border-border bg-[var(--color-paper-50)]"
                    : "fixed inset-0 z-50 overflow-y-auto bg-background",
                )}
                role={haiCot ? undefined : "dialog"}
                aria-modal={haiCot ? undefined : true}
                aria-label="Soạn thảo văn bản"
              >
                {/* slug là state khởi tạo từ prop bên trong; key buộc remount khi
                    bấm loại khác trên card đang hiện */}
                <KhongGianSoanThao
                  key={soanThao.slug ?? "luoi"}
                  loaiVanBan={soanThao.slug}
                  trongKhung
                  onDong={() => datSoanThao(null)}
                />
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

export const Route = createFileRoute("/dung-thu")({
  // `?q=` là câu hỏi người dùng vừa gõ ở một cửa vào khác (`/chat`, hoặc một
  // liên kết được chia sẻ). Nó chạy NGAY, vì gõ câu hỏi rồi bấm gửi đã là sự
  // đồng ý — bắt bấm gửi lần thứ hai chỉ để giữ một quy tắc hình thức.
  // `?phien=` là id phiên hội thoại, `?ban_thao=` là bản thảo cần mở thẳng lên
  // sân khấu (đều UUID) — sai định dạng thì bị bỏ, KHÔNG gửi lên máy chủ để
  // nhận về một 404/422 vô nghĩa.
  validateSearch: (
    tho: Record<string, unknown>,
  ): { q?: string; phien?: string; ban_thao?: string } => {
    const q = tho["q"];
    const phien = tho["phien"];
    const banThao = tho["ban_thao"];
    return {
      ...(typeof q === "string" && q.trim() !== "" ? { q } : {}),
      ...(typeof phien === "string" && UUID.test(phien) ? { phien } : {}),
      ...(typeof banThao === "string" && UUID.test(banThao) ? { ban_thao: banThao } : {}),
    };
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
