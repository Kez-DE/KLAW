import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { AppShell } from "@/components/app/AppShell";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { ManChao } from "@/components/klaw/ManChao";
import { MaTruyVet } from "@/components/klaw/MaTruyVet";
import { KhungDoiChieu, useHaiCot } from "@/components/klaw/KhungDoiChieu";
import { OSoanCauHoi } from "@/components/klaw/OSoanCauHoi";
import { TheHetLuot } from "@/components/klaw/TheHetLuot";
import { TheKetQua } from "@/components/klaw/TheKetQua";
import { TrangThaiCho } from "@/components/klaw/TrangThaiCho";
import { KhongGianSoanThao } from "@/components/soan-thao/KhongGianSoanThao";
import { TheTaiKhoanKhoa } from "@/components/tai-khoan/TheTaiKhoanKhoa";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { useDoiChieu } from "@/hooks/use-doi-chieu";
import { useTraCuu } from "@/hooks/use-tra-cuu";
import { goi } from "@/lib/api";
import { dinhDangMoc, laBiKhoa, laKhongGioiHan } from "@/lib/han-muc";
import { layThreadKhach, xoaThreadKhach } from "@/lib/khach";
import type { Citation, TraCuuKetQua } from "@/lib/klaw";
import { chuanHoaLuot, laNhapPhien } from "@/lib/klaw";
import type { LuotDaXong } from "@/lib/lich-su";
import { dungLichSu } from "@/lib/lich-su";
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
      {/* Card cho MỌI câu trả lời (spec soạn-thảo-trong-chat §5.1): bọc ở đây
          nên TheKetQua, TrangThaiCho, BaoLoi cùng hưởng; --card và shadow-soft
          đã đo tương phản trong DESIGN.md. */}
      <div className="mt-4 rounded-xl border border-border bg-card p-5 shadow-soft">{children}</div>
    </div>
  );
}

/** `?phien=` chỉ nhận UUID. Dùng ở CẢ `validateSearch` và lúc đọc trong component. */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function ManHoiKlaw() {
  const { q: cauHoiTrenUrl, phien: phienTho } = Route.useSearch();
  // Router (TanStack 1.170, non-strict search) trộn search THÔ của route cha ĐÈ lên
  // kết quả `validateSearch`, nên `?phien=rac` vẫn tới đây — kiểm lại trước khi gọi API.
  const phienId = typeof phienTho === "string" && UUID.test(phienTho) ? phienTho : undefined;
  const traCuu = useTraCuu();
  const doiChieu = useDoiChieu();
  const haiCot = useHaiCot();
  const navigate = useNavigate();
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
    datSoanThao({ slug });
  };

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

  useLayoutEffect(() => {
    cuoi.current?.scrollIntoView({ block: "end" });
  }, [luuTru, traCuu.ketQua, traCuu.dangChay, daTai.length]);

  // `?phien=` là nguồn sự thật về phiên đang mở (tải lại trang giữ được, chia sẻ
  // được). Đổi phiên ⇒ xoá dòng hội thoại, đóng khung, tải lượt đã lưu. Trường
  // hợp đặc biệt: sau `bat_dau` của phiên MỚI ta tự `replace` URL sang id đó —
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
    datLuuTru([]);
    datDangMo(null);
    dongDoiChieu();
    datSoanThao(null);
    datLaiTraCuu();
    if (phienId !== undefined && daDangNhap) taiChiTiet(phienId);
    else xoaChiTiet();
  }, [
    phienId,
    dangKiemPhien,
    daDangNhap,
    traCuu.hoiThoaiId,
    datLaiTraCuu,
    taiChiTiet,
    xoaChiTiet,
    dongDoiChieu,
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
    if (noiDung === "" || traCuu.dangChay) return;

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
    }

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
    if (daDangNhap) {
      const id = phienId ?? traCuu.hoiThoaiId ?? undefined;
      traCuu.hoi(noiDung, id === undefined ? {} : { hoiThoaiId: id });
    } else {
      traCuu.hoi(noiDung, { lichSu: dungLichSu(luotTruoc) });
    }
  };

  // Gợi ý chỉ ĐIỀN, không gửi — người dùng còn sửa câu (spec 2026-09-06 §4.1).
  // Khách cũng điền được: từ 2A họ hỏi thử được thật, nên đá họ sang trang đăng
  // nhập ngay ở cú bấm đầu tiên là hứa một việc rồi làm việc khác.
  const dienGoiY = (cau: string) => {
    datNhap(cau);
    oHoi.current?.focus();
  };

  // `phienMoi` PHẢI tự xoá `traCuu.hoiThoaiId` cùng lúc chuyển `?phien=` về
  // rỗng: nếu chỉ đổi URL, `traCuu.hoiThoaiId` cũ (khác `null`) còn sống qua
  // hết lượt effect của lần render đó, và effect (2) sẽ thấy `phienId ===
  // undefined` + `hoiThoaiId !== null` rồi bật ngược URL về phiên vừa rời —
  // "Phiên mới" lặng lẽ ghi tiếp vào phiên cũ (có thể đã bị xoá).
  const phienMoi = useCallback(() => {
    datLaiTraCuu();
    void navigate({ to: "/dung-thu", search: {} });
  }, [datLaiTraCuu, navigate]);

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

  return (
    <AppShell active="/dung-thu">
      <div className="flex min-h-0 flex-1">
        {/* Ở bố cục MỘT cột, khung nguyên văn khai `aria-modal` và phủ kín màn
            hình. `AppShell` gỡ điều hướng/header/thanh dưới khỏi vòng Tab, nhưng
            cột hội thoại là CON của <main> nên chỉ trang này gỡ được nó — nếu
            không, Tab vài lần là tiêu điểm đi vào một chip trích dẫn nằm khuất
            sau lớp phủ đặc, và Enter ở đó thay cả nội dung khung. */}
        <div
          inert={(doiChieu.dang !== null || soanThao !== null) && !haiCot}
          className={cn(
            "flex min-w-0 flex-1 flex-col",
            soanThao !== null && haiCot && "max-w-[420px]",
          )}
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
            {hetHanPro && (
              <div className="mt-8">
                <TheHetLuot
                  loai="het_han"
                  chiTiet={`Gói Cá nhân đã hết hạn ngày ${ngayHetHan}. Gia hạn 30 ngày để tiếp tục hỏi không giới hạn và soạn 20 bản thảo mỗi ngày.`}
                  onNangGoi={moNangGoi}
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
                    <Luot key={`da-luu-${l.thuTu}`} cauHoi={l.cauHoi} traceId={l.traceId}>
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
                        />
                      )}
                    </Luot>
                  ))}

                  {luuTru.map((luot) => (
                    <Luot
                      key={luot.ketQua.trace_id}
                      cauHoi={luot.cauHoi}
                      traceId={luot.ketQua.trace_id}
                    >
                      <TheKetQua
                        ketQua={luot.ketQua}
                        cauHoiGoc={luot.cauHoi}
                        chiSoDangMo={chiSoDangMoCua(luot.ketQua)}
                        onChonTrichDan={(chiSo) => chonTrichDan(luot.ketQua, chiSo)}
                        onSoanThao={moSoanThao}
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
                          ketQua={traCuu.ketQua}
                          {...(traCuu.cauHoi !== null ? { cauHoiGoc: traCuu.cauHoi } : {})}
                          chiSoDangMo={chiSoDangMoCua(traCuu.ketQua)}
                          onChonTrichDan={(chiSo) => {
                            const kq = traCuu.ketQua;
                            if (kq !== null) chonTrichDan(kq, chiSo);
                          }}
                          onSoanThao={moSoanThao}
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
                        chiTiet={`Bạn đã dùng ${mucChip.han_muc} lượt thử. Đăng nhập miễn phí để tiếp tục, lưu đoạn chat này và có 200 lượt mỗi ngày.`}
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
                <div ref={cuoi} />
              </div>
            )}
          </div>

          <OSoanCauHoi
            oHoi={oHoi}
            nhap={nhap}
            datNhap={datNhap}
            khoa={khoaOHoi}
            onGui={gui}
            mucChip={mucChip}
            dangCho={dangKiemPhien && !chuaCauHinh}
          />
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
      </div>
    </AppShell>
  );
}

export const Route = createFileRoute("/dung-thu")({
  // `?q=` là câu hỏi người dùng vừa gõ ở một cửa vào khác (`/chat`, hoặc một
  // liên kết được chia sẻ). Nó chạy NGAY, vì gõ câu hỏi rồi bấm gửi đã là sự
  // đồng ý — bắt bấm gửi lần thứ hai chỉ để giữ một quy tắc hình thức.
  // `?phien=` là id phiên hội thoại (UUID) cần mở — sai định dạng thì bị bỏ,
  // KHÔNG gửi lên máy chủ để nhận về một 404/422 vô nghĩa.
  validateSearch: (tho: Record<string, unknown>): { q?: string; phien?: string } => {
    const q = tho["q"];
    const phien = tho["phien"];
    return {
      ...(typeof q === "string" && q.trim() !== "" ? { q } : {}),
      ...(typeof phien === "string" && UUID.test(phien) ? { phien } : {}),
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
