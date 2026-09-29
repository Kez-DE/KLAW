import { createFileRoute, Link, notFound, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Copy, ExternalLink, ListTree, Search, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app/AppShell";
import { NoiDungDieuKhoan } from "@/components/klaw/NoiDungDieuKhoan";
import { BadgeHieuLuc, MoTaHieuLuc } from "@/components/klaw/BadgeHieuLuc";
import { BaoLoi, DanhSachThayThe } from "@/components/klaw/BaoLoi";
import { BanGocCoChuKy } from "@/components/klaw/BanGocCoChuKy";
import { goi, thamSo } from "@/lib/api";
import { gomHangBang } from "@/lib/bang";
import {
  CAP_CHUA_DIEU,
  laTimTrongVanBan,
  laVanBanBiAn,
  laVanBanHieuLuc,
  laVanBanLienQuan,
  laVanBanMucLuc,
  laVanBanProvisions,
  vanBanBiAn,
  type DongTimTrongVanBan,
  type MucLucItem,
  type Provision,
  type VanBanHieuLuc,
  type VanBanLienQuan,
  type VanBanMucLuc,
  type VanBanProvisions,
} from "@/lib/klaw";
import {
  cachTrichHopLe,
  chuoiSaoChep,
  dongThongTin,
  trichDieuKhoan,
  vanBanHopLe,
} from "@/lib/trich-dan";
import { cn, ngayVietNam } from "@/lib/utils";

/**
 * Màn đọc toàn văn — định danh bằng `doc_id`, KHÔNG bằng số hiệu.
 *
 * Tuyến cũ là `/tra-cuu/$soHieu`, và `65/2006/QH11` thuộc **hai** văn bản khác
 * nhau trong CSDL quốc gia: một liên kết dựng từ số hiệu mở đúng văn bản trong
 * phần lớn trường hợp và mở nhầm trong phần còn lại, âm thầm. `documents.id`
 * là khoá duy nhất tuyệt đối, nên tuyến mang chính nó. Số hiệu vẫn là thứ
 * người đọc thấy ở mọi chỗ hiển thị.
 *
 * ## Tải LƯỜI, vì kho buộc phải thế
 *
 * Bộ luật Dân sự có 689 Điều. `GET /van-ban/{doc_id}` không tham số chỉ trả
 * metadata + danh mục Chương/Mục; nội dung tới theo từng Điều (`?so_dieu=`)
 * hoặc theo từng Chương (`?trong_chuong=`). Màn này tôn trọng đúng ranh giới
 * đó thay vì ghép lại thành một lần tải khổng lồ ở FE.
 *
 * ## Hiệu lực đi qua ĐÚNG MỘT đường
 *
 * `GET /van-ban/{doc_id}` cố ý KHÔNG trả `tinh_trang`, dù cột đó nằm cùng dòng
 * `documents`. Nhãn hiệu lực trên trang này đến từ
 * `GET /van-ban/{doc_id}/hieu-luc` — chỗ duy nhất `effectivity.py` chạy.
 */

interface DuLieuTai {
  vanBan: VanBanMucLuc;
}

export const Route = createFileRoute("/tra-cuu/$docId")({
  validateSearch: (tho: Record<string, unknown>): { dieu?: string; quanh?: string } => {
    const dieu = tho["dieu"];
    // `quanh` mang `provision_id` — khoá máy chủ khuyên dùng để mở nguyên văn
    // quanh một kết quả tìm kiếm. Không bóc số Điều ra từ `duong_dan`: dòng
    // khớp thường là một Khoản, và bóc chuỗi ở đây là dựng lại bằng tay đúng
    // phép phân giải mà `?around=` đã làm sẵn phía máy chủ.
    const quanh = tho["quanh"];
    return {
      ...(typeof dieu === "string" && dieu !== "" ? { dieu } : {}),
      ...(typeof quanh === "string" && quanh !== "" ? { quanh } : {}),
    };
  },
  // Tải ở tầng route (chạy cả khi dựng phía máy chủ) chứ không trong hiệu ứng:
  // thẻ <title> và mô tả của trang phải mang đúng tên văn bản. Chỉ metadata +
  // danh mục — đúng dạng rẻ nhất của endpoint.
  loader: async ({ params }): Promise<DuLieuTai> => {
    const ketQua = await goi(`/van-ban/${encodeURIComponent(params.docId)}`, laVanBanMucLuc);
    if (!ketQua.ok) {
      // Văn bản bị ẩn (quyết định 2026-09-28, mục 8) mang câu của máy chủ và
      // văn bản thay thế theo; mã không tồn tại thì `data: null`.
      if (ketQua.error.kind === "not_found") throw notFound({ data: vanBanBiAn(ketQua.error) });
      throw new Error(ketQua.error.message);
    }
    return { vanBan: ketQua.data };
  },
  head: ({ loaderData }) => {
    const vb = loaderData?.vanBan;
    const title = vb === undefined ? "Văn bản — KLAW" : `${vb.so_ky_hieu} — toàn văn | KLAW`;
    const desc =
      vb === undefined
        ? "Đọc toàn văn văn bản pháp luật theo điều, khoản, điểm trên KLAW."
        : `${vb.loai_van_ban} ${vb.so_ky_hieu}${
            vb.co_quan_ban_hanh === null ? "" : ` do ${vb.co_quan_ban_hanh} ban hành`
          }${
            vb.ngay_ban_hanh === null ? "" : ` ngày ${ngayVietNam(vb.ngay_ban_hanh)}`
          }. Đọc toàn văn theo điều, khoản, điểm kèm nhãn hiệu lực của KLAW.`;
    return {
      meta: [
        { title },
        { name: "description", content: desc },
        { property: "og:title", content: title },
        { property: "og:description", content: desc },
        { property: "og:type", content: "article" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: ManDocVanBan,
  notFoundComponent: KhongCoVanBan,
});

function KhongCoVanBan({ data }: { data?: unknown }) {
  // Kiểm lại ở đây: `data` qua ranh giới máy chủ → trình duyệt của router.
  const biAn = laVanBanBiAn(data) ? data : null;
  return (
    <AppShell active="/tra-cuu">
      <div className="mx-auto max-w-xl px-5 py-20 text-center">
        <h1 className="font-display text-2xl font-semibold text-primary">
          {biAn?.thong_diep ?? "Không có văn bản này trong kho"}
        </h1>
        {biAn === null ? (
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            Kho của KLAW gồm 6 Bộ luật cùng cụm văn bản dưới luật về Lao động. Mã văn bản trên đường
            dẫn không trỏ tới văn bản nào trong kho.
          </p>
        ) : (
          <div className="mx-auto inline-block text-left">
            <DanhSachThayThe thayThe={biAn.thay_the} />
          </div>
        )}
        <Link
          to="/tra-cuu"
          className="focus-brass mt-6 inline-flex min-h-11 items-center gap-2 rounded-xl border border-border px-4 text-sm font-medium text-primary transition-colors hover:border-accent"
        >
          Quay lại tra cứu
        </Link>
      </div>
    </AppShell>
  );
}

/* ─────────────────────────── Thanh điều hướng trái ─────────────────────── */

/**
 * Danh mục Chương/Mục, mở từng nhánh bằng `?trong_chuong=`.
 *
 * ĐO ĐƯỢC 11/47 văn bản có toàn văn KHÔNG chia Chương/Mục (nghị định, thông tư
 * ngắn — gồm cả sáu nghị định lương tối thiểu). Với chúng backend trả thẳng
 * DANH SÁCH ĐIỀU trong `muc_luc`, cùng hình dạng nhưng `cap === "dieu"`. Một
 * Điều là LÁ: nó không chứa Điều nào, nên `?trong_chuong=` với id của nó là
 * một câu hỏi vô nghĩa và máy chủ trả 422 — đúng. Xem `MucLa` ngay dưới.
 */
function NhanhChuong({
  docId,
  muc,
  dieuDangMo,
  onChonDieu,
}: {
  docId: string;
  muc: MucLucItem;
  dieuDangMo: string | null;
  onChonDieu: (soDieu: string) => void;
}) {
  const [mo, datMo] = useState(false);
  const [dsDieu, datDsDieu] = useState<Provision[] | null>(null);
  const [dangTai, datDangTai] = useState(false);

  const bat = () => {
    const sapMo = !mo;
    datMo(sapMo);
    if (!sapMo || dsDieu !== null || dangTai) return;
    datDangTai(true);
    void goi(
      `/van-ban/${encodeURIComponent(docId)}?trong_chuong=${muc.id}`,
      laVanBanProvisions,
    ).then((kq) => {
      datDangTai(false);
      // Nhánh không mở được thì để nguyên trạng thái "chưa tải": bấm lại là
      // thử lại. KHÔNG hiện danh sách rỗng — rỗng đọc thành "chương này không
      // có điều nào", một khẳng định về pháp luật, còn sự thật là một lỗi mạng.
      if (kq.ok) datDsDieu(kq.data.provisions);
    });
  };

  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={bat}
        aria-expanded={mo}
        className="focus-brass flex w-full items-start gap-1.5 rounded-md px-1.5 py-1.5 text-left text-[13px] font-semibold text-primary hover:bg-[var(--color-paper-100)]"
      >
        {mo ? (
          <ChevronDown
            className="mt-0.5 size-3.5 shrink-0 text-[var(--color-brass-600)]"
            aria-hidden
          />
        ) : (
          <ChevronRight
            className="mt-0.5 size-3.5 shrink-0 text-[var(--color-brass-600)]"
            aria-hidden
          />
        )}
        <span className={cn(muc.cap === "muc" || muc.cap === "tieu_muc" ? "pl-2 font-normal" : "")}>
          {muc.tieu_de}
        </span>
      </button>

      {mo && (
        <div className="mt-1 ml-3 border-l border-border">
          {dangTai && <p className="px-2.5 py-1.5 text-[12px] text-muted-foreground">Đang mở…</p>}
          {!dangTai && dsDieu === null && (
            <p className="px-2.5 py-1.5 text-[12px] text-muted-foreground">
              Chưa mở được danh sách Điều. Bấm lại để thử.
            </p>
          )}
          {dsDieu?.map((dieu) => (
            <MucLa
              key={dieu.id}
              soHieuCap={dieu.so_hieu_cap}
              tieuDe={dieu.tieu_de}
              dieuDangMo={dieuDangMo}
              onChonDieu={onChonDieu}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Một Điều trong mục lục — LÁ, không mở tiếp được.
 *
 * Dùng ở hai chỗ: dưới một Chương đã mở, và ở gốc mục lục của 11 văn bản
 * không chia Chương/Mục. Cùng một đích đến (`?dieu=<so_hieu_cap>`) ở cả hai,
 * nên cùng một thành phần — một Điều mở từ mục lục phẳng phải cho ra đúng
 * trang với một Điều mở từ trong Chương.
 */
function MucLa({
  soHieuCap,
  tieuDe,
  dieuDangMo,
  onChonDieu,
}: {
  soHieuCap: string;
  tieuDe: string;
  dieuDangMo: string | null;
  onChonDieu: (soDieu: string) => void;
}) {
  const dangMo = dieuDangMo === soHieuCap;
  return (
    <button
      type="button"
      onClick={() => onChonDieu(soHieuCap)}
      aria-current={dangMo ? "true" : undefined}
      className={cn(
        "focus-brass block w-full px-2.5 py-1.5 text-left text-[13px] transition-colors",
        dangMo
          ? "border-l-2 border-[var(--color-brass-500)] font-medium text-[var(--color-brass-600)]"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {tieuDe === "" ? `Điều ${soHieuCap}` : tieuDe}
    </button>
  );
}

/** Ô lọc trong văn bản — `GET /van-ban/{doc_id}/tim`, khớp chuỗi con, không dấu cũng ra. */
function OLoc({ docId, onChonDieu }: { docId: string; onChonDieu: (soDieu: string) => void }) {
  const [q, datQ] = useState("");
  const [ketQua, datKetQua] = useState<DongTimTrongVanBan[]>([]);
  const [tong, datTong] = useState(0);

  useEffect(() => {
    const chu = q.trim();
    if (chu === "") {
      datKetQua([]);
      datTong(0);
      return;
    }
    // Hoãn 200ms: ô lọc hẹp dần theo từng ký tự gõ, và không cần một request
    // cho mỗi ký tự để làm việc đó. `AbortController` huỷ lượt cũ khi lượt mới
    // xuất phát, nên kết quả của một tiền tố cũ không bao giờ ghi đè kết quả mới.
    const dieuKhien = new AbortController();
    const hoan = setTimeout(() => {
      void goi(
        `/van-ban/${encodeURIComponent(docId)}/tim${thamSo([
          ["q", chu],
          ["limit", 60],
        ])}`,
        laTimTrongVanBan,
        { signal: dieuKhien.signal },
      ).then((kq) => {
        if (!kq.ok) return;
        datKetQua(kq.data.ket_qua);
        datTong(kq.data.tong);
      });
    }, 200);
    return () => {
      clearTimeout(hoan);
      dieuKhien.abort();
    };
  }, [q, docId]);

  /** "45/2019/QH14 > Điều 25 > Khoản 1" → "25". Điều là đơn vị mở được. */
  const soDieuTu = (duongDan: string): string | null =>
    /> Điều ([^\s>]+)/.exec(duongDan)?.[1] ?? null;

  return (
    <div>
      <div className="relative">
        <Search
          className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <input
          value={q}
          onChange={(su) => datQ(su.target.value)}
          aria-label="Lọc trong văn bản"
          placeholder="Lọc trong văn bản"
          className="focus-brass h-10 w-full rounded-lg border border-input bg-card pr-2 pl-8 text-[13px] outline-none"
        />
      </div>

      {q.trim() !== "" && (
        <div className="mt-2">
          <p className="mb-1 text-[12px] text-muted-foreground">
            {tong === 0
              ? "Không có điều khoản nào khớp."
              : `${tong} điều khoản khớp${tong > ketQua.length ? `, hiện ${ketQua.length} đầu tiên` : ""}`}
          </p>
          <ul className="m-0 flex list-none flex-col p-0">
            {ketQua.map((dong) => {
              const soDieu = soDieuTu(dong.duong_dan);
              return (
                <li key={dong.provision_id}>
                  <button
                    type="button"
                    disabled={soDieu === null}
                    onClick={() => {
                      if (soDieu !== null) onChonDieu(soDieu);
                    }}
                    className="focus-brass block w-full rounded-md px-1.5 py-1.5 text-left text-[12px] text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-foreground disabled:cursor-default"
                  >
                    <span className="font-jetbrains block text-[11px] text-[var(--color-brass-600)]">
                      {dong.duong_dan}
                    </span>
                    <span className="mt-0.5 block line-clamp-2">{dong.trich}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────── Nguyên văn ────────────────────────────── */

const LE_THEO_CAP: Record<string, string> = { dieu: "0rem", khoan: "1rem", diem: "2rem" };

/**
 * `noi_dung` của một Điều MỞ ĐẦU bằng chính `tieu_de` của nó trong CSDL ("Điều
 * 25. Thời gian thử việc Thời gian thử việc do hai bên…"). In cả tiêu đề lẫn
 * nội dung sẽ lặp lại câu đó hai lần liền nhau.
 *
 * Đây KHÔNG phải sửa nguyên văn: phần cắt đi đã hiện ngay phía trên dưới dạng
 * tiêu đề, nên trên màn hình vẫn còn đủ từng ký tự, chỉ một lần thay vì hai.
 * Chỉ cắt khi thật sự là tiền tố và còn nội dung phía sau — một Điều chỉ có
 * tiêu đề (73,6% số Điều) giữ nguyên, nếu không nó thành một đoạn trống.
 */
function khongLapTieuDe(dieuKhoan: Provision): string {
  const noiDung = dieuKhoan.noi_dung.normalize("NFC");
  const tieuDe = dieuKhoan.tieu_de.normalize("NFC");
  if (tieuDe === "" || !noiDung.startsWith(tieuDe)) return noiDung;
  const con = noiDung.slice(tieuDe.length).trimStart();
  return con === "" ? noiDung : con;
}

function NguyenVanDieu({
  docId,
  vanBan,
  hieuLuc,
  soKyHieu,
}: {
  docId: string;
  vanBan: VanBanProvisions;
  hieuLuc: VanBanHieuLuc | null;
  soKyHieu: string;
}) {
  // Nhãn hiệu lực CẤP ĐIỀU KHOẢN, tra theo `provision_id`. Bản đồ này mới phủ
  // 1/126 văn bản (4 dòng, đều của 45/2019/QH14): không có nhãn nào là trạng
  // thái BÌNH THƯỜNG, không phải thiếu dữ liệu cần lấp bằng phỏng đoán.
  const nhanTheoId = new Map(hieuLuc?.dieu_khoan.map((d) => [d.provision_id, d]) ?? []);

  return (
    <article className="doc-reader mt-6 text-foreground">
      {/* `gomHangBang` thu `hang_bang` về dòng cha để chúng ra một cái BẢNG chứ
          không phải mấy dòng `| … |` rời. Mỗi hàng vẫn giữ nguyên neo riêng —
          `id="dk-<id>"` và liên kết `?quanh=<id>` — vì đó chính là lý do
          backend tách bảng ra. */}
      {gomHangBang(vanBan.provisions).map(({ dieuKhoan, hangCon }) => {
        const nhan = nhanTheoId.get(dieuKhoan.id);
        const trichDan = `${dieuKhoan.duong_dan.replace(`${soKyHieu} > `, "")} ${soKyHieu}`;
        return (
          <section
            key={dieuKhoan.id}
            id={`dk-${dieuKhoan.id}`}
            data-trich-dan={trichDan}
            className="scroll-mt-28"
            style={{ marginInlineStart: LE_THEO_CAP[dieuKhoan.cap] ?? "0rem" }}
          >
            {dieuKhoan.cap === "dieu" && dieuKhoan.tieu_de !== "" && (
              <h2 className="font-display mt-6 text-[20px] leading-snug font-semibold text-primary">
                {dieuKhoan.tieu_de}
              </h2>
            )}
            {/* Quyết định 2026-09-28, mục 10: nhãn và MỘT câu thường nêu văn
                bản sửa đổi kèm link — không `ly_do`, không dòng `sua_boi` với
                nguồn và độ tin cậy (API vẫn trả, cho đo đạc). */}
            {nhan !== undefined && (
              <div className="mt-2">
                <BadgeHieuLuc hieuLuc={nhan.hieu_luc.verdict} gonGang />
                <MoTaHieuLuc hieuLuc={nhan.hieu_luc} className="text-[12px]" />
              </div>
            )}
            <NoiDungDieuKhoan
              dieuKhoan={dieuKhoan}
              noiDung={khongLapTieuDe(dieuKhoan)}
              hangCon={hangCon}
              docId={docId}
            />
          </section>
        );
      })}
      <p className="mt-6 mb-0 text-[12px] leading-5 text-muted-foreground">
        Nguyên văn lấy từ CSDL quốc gia: không rút gọn, không sửa chính tả. Đây là bản GỐC, không
        phải bản hợp nhất.
      </p>
    </article>
  );
}

/* ──────────────────────────── Văn bản liên quan ────────────────────────── */

const MUI_TEN: Record<string, string> = { di_ra: "→", di_vao: "←" };

function KhoiLienQuan({ lienQuan }: { lienQuan: VanBanLienQuan }) {
  return (
    <div className="flex flex-col gap-4">
      {lienQuan.nhom.length === 0 && (
        <p className="m-0 text-[12px] text-muted-foreground">
          CSDL quốc gia không khai quan hệ nào cho văn bản này.
        </p>
      )}
      {lienQuan.nhom.map((nhom) => (
        <div key={`${nhom.loai}-${nhom.chieu}`}>
          <p className="m-0 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
            {nhom.nhan} <span aria-hidden>{MUI_TEN[nhom.chieu] ?? ""}</span> ({nhom.so_luong})
          </p>
          {/* `chieu_da_do: false` — chiều ngữ nghĩa của 242 dòng mã MOJ chưa ai
              đo. Hiện NHÃN quan hệ, tuyệt đối không viết thành câu "Văn bản này
              thay thế X": câu đó có 50% khả năng ngược. */}
          {!nhom.chieu_da_do && (
            <p className="m-0 mt-0.5 text-[11px] text-muted-foreground">
              Chiều của quan hệ này chưa được đối chiếu — nhãn do CSDL quốc gia khai.
            </p>
          )}
          <ul className="mt-1.5 flex list-none flex-col gap-1.5 p-0">
            {nhom.van_ban.map((vb, i) => (
              <li
                key={`${vb.doc_id ?? "ngoai"}-${vb.so_ky_hieu}-${i}`}
                className="rounded-lg border border-border bg-card p-2.5"
              >
                <p className="font-jetbrains m-0 text-[11px] text-[var(--color-brass-600)]">
                  {vb.so_ky_hieu}
                </p>
                {vb.bo_luat !== null && (
                  <p className="mt-0.5 mb-0 text-[13px] text-foreground">{vb.bo_luat}</p>
                )}
                {vb.doc_id === null ? (
                  // `trong_corpus: false` ⇒ KHÔNG dựng link: 273/626 cạnh cấp
                  // văn bản trỏ ra ngoài kho, và link đó sẽ ra 404.
                  <p className="mt-1 mb-0 text-[11px] text-muted-foreground">
                    Không có trong kho của KLAW
                  </p>
                ) : (
                  <Link
                    to="/tra-cuu/$docId"
                    params={{ docId: vb.doc_id }}
                    className="focus-brass mt-1 inline-block text-[12px] text-[var(--color-brass-600)] hover:underline"
                  >
                    Mở toàn văn
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}

      {/* Chỉ là SỐ ĐẾM. Đo được 2.971/2.971 dẫn chiếu cấp điều khoản nằm trong
          CÙNG văn bản, nên chúng không phải "văn bản liên quan". */}
      {lienQuan.dan_chieu_noi_bo.so_luong > 0 && (
        <p className="m-0 border-t border-border pt-3 text-[11px] leading-5 text-muted-foreground">
          {lienQuan.dan_chieu_noi_bo.so_luong} dẫn chiếu nội bộ. {lienQuan.dan_chieu_noi_bo.ghi_chu}
        </p>
      )}
    </div>
  );
}

/* ──────────────────────────────── Trang ────────────────────────────────── */

function ManDocVanBan() {
  const { vanBan } = Route.useLoaderData();
  const { dieu: soDieuTrenUrl, quanh: quanhTrenUrl } = Route.useSearch();
  const { docId } = Route.useParams();
  const navigate = useNavigate();

  const [hieuLuc, datHieuLuc] = useState<VanBanHieuLuc | null>(null);
  const [lienQuan, datLienQuan] = useState<VanBanLienQuan | null>(null);
  const [noiDung, datNoiDung] = useState<VanBanProvisions | null>(null);
  const [loiNoiDung, datLoiNoiDung] = useState<Parameters<typeof BaoLoi>[0]["loi"] | null>(null);
  const [metaMo, datMetaMo] = useState(true);
  const [tab, datTab] = useState<"muc-luc" | "lien-quan">("muc-luc");
  const [railMo, datRailMo] = useState(false);

  useEffect(() => {
    const dieuKhien = new AbortController();
    void goi(`/van-ban/${encodeURIComponent(docId)}/hieu-luc`, laVanBanHieuLuc, {
      signal: dieuKhien.signal,
    }).then((kq) => {
      if (kq.ok) datHieuLuc(kq.data);
    });
    void goi(`/van-ban/${encodeURIComponent(docId)}/lien-quan`, laVanBanLienQuan, {
      signal: dieuKhien.signal,
    }).then((kq) => {
      if (kq.ok) datLienQuan(kq.data);
    });
    return () => dieuKhien.abort();
  }, [docId]);

  useEffect(() => {
    // `?quanh=` (một `provision_id`) đi qua `?around=`: máy chủ tự phân giải về
    // Điều cha rồi trả thêm 2 Điều trước/sau, và đánh dấu `la_tam` cho đúng
    // vùng người dùng vừa bấm vào. `?dieu=` mở đúng một Điều.
    const truyVan =
      quanhTrenUrl !== undefined
        ? thamSo([["around", quanhTrenUrl]])
        : soDieuTrenUrl !== undefined
          ? thamSo([["so_dieu", soDieuTrenUrl]])
          : null;
    if (truyVan === null) {
      datNoiDung(null);
      datLoiNoiDung(null);
      return;
    }
    const dieuKhien = new AbortController();
    datNoiDung(null);
    datLoiNoiDung(null);
    void goi(`/van-ban/${encodeURIComponent(docId)}${truyVan}`, laVanBanProvisions, {
      signal: dieuKhien.signal,
    }).then((kq) => {
      if (kq.ok) datNoiDung(kq.data);
      else if (kq.error.kind !== "aborted") datLoiNoiDung(kq.error);
    });
    return () => dieuKhien.abort();
  }, [docId, soDieuTrenUrl, quanhTrenUrl]);

  const chonDieu = useCallback(
    (soDieu: string) => {
      datRailMo(false);
      void navigate({ to: "/tra-cuu/$docId", params: { docId }, search: { dieu: soDieu } });
    },
    [docId, navigate],
  );

  // Link chính thống đã qua cửa kiểm (https, đúng cổng) — vắng thì KHÔNG có dòng.
  const lienKet = vanBanHopLe(vanBan).lien_ket;
  // Trường NULL = KHÔNG BIẾT, nên cả dòng bỏ đi — không "Không rõ", không "Chưa có".
  const meta = dongThongTin(vanBan);

  const thanhBen = (
    <div>
      <div className="flex gap-1 rounded-full border border-border p-0.5 text-[12px]">
        {(
          [
            ["muc-luc", "Mục lục"],
            ["lien-quan", "Văn bản liên quan"],
          ] as const
        ).map(([id, nhan]) => (
          <button
            key={id}
            type="button"
            onClick={() => datTab(id)}
            aria-pressed={tab === id}
            className={cn(
              "focus-brass flex-1 rounded-full px-2 py-1.5 transition-colors",
              tab === id
                ? "bg-[var(--color-brass-500)]/15 font-medium text-[var(--color-brass-600)]"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {nhan}
          </button>
        ))}
      </div>

      {tab === "muc-luc" ? (
        <div className="mt-3">
          <OLoc docId={docId} onChonDieu={chonDieu} />
          <nav className="mt-3" aria-label="Mục lục văn bản">
            {vanBan.muc_luc.length === 0 ? (
              // Nay chỉ còn văn bản TẦNG METADATA rơi vào đây: 0 điều khoản,
              // nên không có gì để liệt. 11 văn bản không chia Chương/Mục
              // KHÔNG còn rỗng — backend trả thẳng danh sách Điều.
              <p className="m-0 text-[12px] leading-5 text-muted-foreground">
                Kho chỉ có phần thông tin của văn bản này, chưa có toàn văn máy đọc được — nên không
                có mục lục để mở.
              </p>
            ) : (
              vanBan.muc_luc.map((muc) =>
                // Cấp CHỨA Điều mới mở tiếp được bằng `?trong_chuong=`. Mọi cấp
                // khác (hôm nay là `dieu`) là lá và đi thẳng bằng `?dieu=`.
                CAP_CHUA_DIEU.has(muc.cap) ? (
                  <NhanhChuong
                    key={muc.id}
                    docId={docId}
                    muc={muc}
                    dieuDangMo={soDieuTrenUrl ?? null}
                    onChonDieu={chonDieu}
                  />
                ) : (
                  <MucLa
                    key={muc.id}
                    soHieuCap={muc.so_hieu_cap}
                    tieuDe={muc.tieu_de}
                    dieuDangMo={soDieuTrenUrl ?? null}
                    onChonDieu={chonDieu}
                  />
                ),
              )
            )}
          </nav>
        </div>
      ) : (
        <div className="mt-3">
          {lienQuan === null ? (
            <p className="m-0 text-[12px] text-muted-foreground">Đang mở danh sách liên quan…</p>
          ) : (
            <KhoiLienQuan lienQuan={lienQuan} />
          )}
        </div>
      )}
    </div>
  );

  return (
    <AppShell active="/tra-cuu">
      {/* Ngăn kéo mục lục khai `aria-modal`. `AppShell` gỡ điều hướng/header ra
          khỏi vòng Tab, nhưng cột nội dung là CON của <main> nên chỉ trang này
          gỡ được nó — nếu không, Tab vài lần là tiêu điểm đi vào một nút nằm
          khuất sau lớp phủ đặc. */}
      <div inert={railMo} className="flex min-w-0 flex-1">
        <aside
          aria-label="Mục lục và văn bản liên quan"
          className="hidden w-[320px] shrink-0 border-r border-border bg-[var(--color-paper-50)] lg:block"
        >
          <div className="sticky top-[52px] max-h-[calc(100vh-52px)] overflow-y-auto px-3 py-4">
            {thanhBen}
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          {/* KHÔNG sticky. Tên văn bản dài xuống hai, ba dòng, cộng nhãn và câu
              `mo_ta` bên dưới, và một dải cố định cao chừng đó ăn mất một phần
              màn hình đọc. Nhãn cấp ĐIỀU KHOẢN vẫn nằm ngay cạnh từng điều trong
              nguyên văn, nên không có chỗ nào người đọc thấy điều luật mà không
              thấy nhãn. */}
          <div className="border-b border-border bg-background px-5 py-3">
            <div className="mx-auto max-w-[760px]">
              <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
                <Link to="/tra-cuu" className="focus-brass rounded hover:text-foreground">
                  Tra cứu
                </Link>
                <span aria-hidden>/</span>
                <span className="font-jetbrains text-foreground">{vanBan.so_ky_hieu}</span>
              </div>
              <h1 className="font-display mt-1 text-[22px] leading-tight font-bold text-primary">
                {vanBan.bo_luat}
              </h1>
              {/* Nhãn hiệu lực CẤP VĂN BẢN — nguồn duy nhất là `/hieu-luc`. Dưới
                  nhãn chỉ có câu `mo_ta` (quyết định 2026-09-28, mục 10): không
                  lý do nội bộ, không ngày đánh giá, không độ tin cậy. Câu đó ở
                  màu trung tính, không qua `ghiChu` — `ghiChu` mang màu của
                  nhãn, dành cho câu nêu văn bản thay thế trong khung đối chiếu. */}
              {hieuLuc !== null && (
                <div className="mt-2">
                  <BadgeHieuLuc hieuLuc={hieuLuc.van_ban.verdict} gonGang />
                  <MoTaHieuLuc hieuLuc={hieuLuc.van_ban} />
                </div>
              )}
            </div>
          </div>

          <div className="px-5 pb-24">
            <div className="mx-auto max-w-[760px]">
              <div className="mt-4 rounded-xl border border-border bg-[var(--color-paper-50)]">
                <button
                  type="button"
                  onClick={() => datMetaMo((mo) => !mo)}
                  aria-expanded={metaMo}
                  className="focus-brass font-display flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-semibold text-primary"
                >
                  Thông tin văn bản
                  <ChevronDown
                    className={cn(
                      "size-4 text-[var(--color-brass-600)] transition-transform duration-150",
                      !metaMo && "-rotate-90",
                    )}
                    aria-hidden
                  />
                </button>
                {metaMo && (
                  <dl className="grid grid-cols-1 gap-x-6 border-t border-border px-4 py-3 text-[13px] sm:grid-cols-2">
                    {meta.map(([khoa, gia]) => (
                      <div
                        key={khoa}
                        className="flex justify-between gap-3 border-b border-border/60 py-1.5 last:border-0"
                      >
                        <dt className="text-muted-foreground">{khoa}</dt>
                        <dd
                          className={cn(
                            "text-right font-medium text-foreground",
                            khoa === "Số hiệu" && "font-jetbrains",
                          )}
                        >
                          {gia}
                        </dd>
                      </div>
                    ))}
                    {lienKet !== null && (
                      <div className="flex justify-between gap-3 border-b border-border/60 py-1.5 last:border-0">
                        <dt className="text-muted-foreground">Nguồn chính thống</dt>
                        <dd className="text-right font-medium">
                          <a
                            href={lienKet.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="focus-brass inline-flex items-center gap-1 rounded text-[var(--color-brass-600)] underline-offset-2 hover:underline"
                          >
                            Xem trên {lienKet.nhan}
                            <ExternalLink className="size-3.5" aria-hidden />
                            <span className="sr-only"> (mở tab mới)</span>
                          </a>
                        </dd>
                      </div>
                    )}
                    <BanGocCoChuKy vanBan={vanBan} />
                  </dl>
                )}
              </div>

              {soDieuTrenUrl === undefined && quanhTrenUrl === undefined && (
                <p className="mt-8 rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  Chọn một Điều ở mục lục bên trái để đọc nguyên văn. Kho không tải cả văn bản một
                  lượt: văn bản lớn nhất có 689 Điều.
                </p>
              )}
              {loiNoiDung !== null && <BaoLoi loi={loiNoiDung} />}
              {(soDieuTrenUrl !== undefined || quanhTrenUrl !== undefined) &&
                noiDung === null &&
                loiNoiDung === null && (
                  <p role="status" className="mt-8 text-center text-sm text-muted-foreground">
                    Đang mở nguyên văn…
                  </p>
                )}
              {noiDung !== null && (
                <>
                  <div className="mt-6 flex justify-end">
                    <button
                      type="button"
                      onClick={() => {
                        // Dựng từ `duong_dan` của dòng tâm — dữ liệu máy chủ
                        // trả về — chứ không từ tham số trên URL: ở dạng
                        // `?quanh=` không có số Điều nào trên URL cả.
                        // Lối văn bản luật: cụm điều khoản + câu trích dẫn CẤP
                        // VĂN BẢN của máy chủ (vắng thì số hiệu), kèm link.
                        const tam = noiDung.provisions.find((dk) => dk.la_tam);
                        const dau = tam ?? noiDung.provisions[0];
                        const phanVanBan = cachTrichHopLe(vanBan) ?? vanBan.so_ky_hieu;
                        const chuoi = chuoiSaoChep(
                          dau === undefined
                            ? phanVanBan
                            : trichDieuKhoan(dau.duong_dan, phanVanBan),
                          lienKet,
                        );
                        void navigator.clipboard?.writeText(chuoi);
                        toast.success("Đã sao chép trích dẫn", { description: chuoi });
                      }}
                      className="focus-brass inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <Copy className="size-3.5" aria-hidden /> Sao chép trích dẫn
                    </button>
                  </div>
                  <NguyenVanDieu
                    docId={docId}
                    vanBan={noiDung}
                    hieuLuc={hieuLuc}
                    soKyHieu={vanBan.so_ky_hieu}
                  />
                </>
              )}

              {/* KHÔNG render bản sao của thanh bên ở đây cho màn hẹp. Ngăn kéo
                  "Mục lục" phía dưới đã mang đúng nội dung đó, và hai bản sao
                  cùng lúc nghĩa là hai ô lọc cùng gõ, hai vùng cùng nhãn, và
                  hai danh sách quan hệ trong cùng một cây DOM. */}
            </div>
          </div>
        </div>
      </div>

      {/* Mục lục dạng ngăn kéo dưới 1024px. Nút mở BIẾN MẤT khi ngăn kéo đang
          mở: nó là anh em của cột nội dung nên `inert` ở trên không với tới,
          và một nút còn Tab được nằm khuất sau lớp phủ đặc là đúng thứ vừa gỡ. */}
      <button
        type="button"
        hidden={railMo}
        onClick={() => datRailMo(true)}
        aria-expanded={railMo}
        aria-controls="muc-luc-ngan-keo"
        className="focus-brass fixed bottom-[68px] left-4 z-40 min-h-11 cursor-pointer rounded-full border border-[var(--color-brass-500)]/60 bg-card px-4 text-[13px] font-medium text-[var(--color-brass-600)] shadow-soft md:bottom-5 lg:hidden"
      >
        <span className="inline-flex items-center gap-1.5">
          <ListTree className="size-4" aria-hidden />
          Mục lục
        </span>
      </button>
      {railMo && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-[var(--color-ink-950)]/45"
            onClick={() => datRailMo(false)}
            aria-hidden
          />
          <div
            id="muc-luc-ngan-keo"
            role="dialog"
            aria-modal="true"
            aria-label="Mục lục văn bản"
            className="absolute inset-y-0 left-0 w-[86vw] max-w-[340px] overflow-y-auto border-r border-border bg-background px-3 py-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <p className="font-display m-0 text-sm font-semibold text-primary">Mục lục</p>
              <button
                type="button"
                onClick={() => datRailMo(false)}
                aria-label="Đóng mục lục"
                className="focus-brass grid size-11 cursor-pointer place-items-center rounded-md text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
            {thanhBen}
          </div>
        </div>
      )}
    </AppShell>
  );
}
