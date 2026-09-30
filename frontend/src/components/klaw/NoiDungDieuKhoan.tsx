import { Link } from "@tanstack/react-router";
import type { Provision } from "@/lib/klaw";
import { soCot, tachDoan, type O } from "@/lib/bang";
import { vungTrichDan, type VungTrichDan } from "@/lib/trich-dan";
import { cn, ngayVietNam } from "@/lib/utils";
import { LinkVanBanDan } from "./BadgeHieuLuc";

/**
 * Nguyên văn MỘT dòng điều khoản: văn xuôi ra `<p>`, bảng ra `<table>` thật.
 *
 * Dùng chung cho cả hai chỗ hiện nguyên văn — khung đối chiếu (click-to-verify)
 * và màn đọc toàn văn. Một bộ dựng, vì một bảng render khác nhau ở hai màn là
 * hai câu trả lời khác nhau cho cùng một điều luật.
 *
 * Bốn điều không được làm sai:
 *
 * 1. **Tô sáng câu trích phải theo được vào trong ô.** Vùng tô là một khoảng vị
 *    trí trong bản NFC của `noiDung` (`vungTrichDan`); mỗi mảnh chữ — đoạn văn
 *    xuôi hay ô `<td>` — giao khoảng ấy với chỗ của riêng nó. Nên `<mark>` rơi
 *    đúng chỗ dù câu trích nằm giữa bảng.
 * 2. **Mỗi hàng đã tách là một neo bấm được.** Backend tách bảng ra thành
 *    `hang_bang` chỉ để có chuyện này: người dùng phải mở được đúng `Vùng III`,
 *    không phải chỉ Khoản 1. Ô ĐẦU của hàng mang liên kết `?quanh=<id>` — đúng
 *    đường mà chip kết quả tìm kiếm dùng để mở nguyên văn.
 * 3. **Bảng cuộn ngang trong khung riêng.** Bảng lương có ba cột dài; ở 390px
 *    mà để nó nong khung ra thì cả trang tràn ngang. Vùng cuộn có `tabIndex`
 *    để người dùng bàn phím cuộn được (WCAG 2.1.1).
 * 4. **Không tự phát minh cột.** Số cột = hàng nhiều ô nhất trong CHÍNH bảng
 *    đó. Hàng thiếu ô nhận ô trống ở cuối, không ghép dồn — bảng tuổi nghỉ hưu
 *    của 135/2020/NĐ-CP có hàng 2 ô và hàng 4 ô trong cùng một bảng.
 *
 * Hàng tiêu đề: chỉ dựng `<thead>` ở dạng A, nơi backend đã nói rõ hàng nào là
 * tiêu đề bằng cách để nó ở lại `noi_dung` của cha và tách riêng hàng dữ liệu.
 * Dạng B không mang tuyên bố đó, nên mọi hàng vào `<tbody>`: đoán hàng đầu là
 * tiêu đề sẽ biến một hàng dữ liệu thành nhãn cột trong một bảng pháp lý.
 */

/** Cắt một mảnh chữ theo vùng tô. Nằm ngoài vùng thì trả nguyên mảnh. */
function ChuCoTo({ text, tu, vung }: { text: string; tu: number; vung: VungTrichDan }) {
  if (vung === null) return <>{text}</>;
  const dau = Math.max(0, vung[0] - tu);
  const cuoi = Math.min(text.length, vung[1] - tu);
  if (cuoi <= dau) return <>{text}</>;
  return (
    <>
      {text.slice(0, dau)}
      <mark className="cau-trich">{text.slice(dau, cuoi)}</mark>
      {text.slice(cuoi)}
    </>
  );
}

/** Neo của một hàng đã tách — nơi bấm để mở đúng hàng đó. */
interface NeoHang {
  docId: string;
  id: number;
  /** "293/2025/NĐ-CP > Điều 3 > Khoản 1 > Vùng I" — đọc cho công nghệ hỗ trợ. */
  duongDan: string;
}

function ODuLieu({
  o,
  vung,
  neo,
  nhanHang,
}: {
  o: O;
  vung: VungTrichDan;
  neo: NeoHang | null;
  /** Ô đầu của một hàng ĐÃ TÁCH — ô mang định danh của hàng. */
  nhanHang: boolean;
}) {
  const chu = <ChuCoTo text={o.text} tu={o.tu} vung={vung} />;
  return (
    <td
      className={cn(
        "border border-border px-2.5 py-1.5 align-top tabular-nums",
        // Nhãn hàng ("Vùng II", "Bậc thuế 3") là ĐỊNH DANH của hàng, và ở dạng
        // A nó cũng là chỗ bấm. Để nó gãy làm hai dòng ở màn hẹp là bẻ đôi một
        // nhãn pháp lý. Chỉ nhãn hàng mới nowrap — ô dữ liệu dài vẫn xuống dòng
        // bình thường, và dạng B không có nhãn hàng nào để mà giữ.
        nhanHang && "whitespace-nowrap",
      )}
    >
      {neo === null || o.text === "" ? (
        chu
      ) : (
        <Link
          to="/tra-cuu/$docId"
          params={{ docId: neo.docId }}
          search={{ quanh: String(neo.id) }}
          hash={`dk-${neo.id}`}
          aria-label={`Mở nguyên văn ${neo.duongDan}`}
          className="focus-brass rounded text-[var(--color-brass-600)] underline decoration-dotted underline-offset-4 hover:decoration-solid"
        >
          {chu}
        </Link>
      )}
    </td>
  );
}

interface HangBang {
  /** Khoá React ổn định: id của hàng đã tách, hoặc vị trí trong khối bảng. */
  khoa: string;
  /**
   * `provision_id` của hàng, nếu hàng là một dòng thật. Dựng `id="dk-<id>"` để
   * liên kết sâu tới đúng hàng — tách khỏi `neo` vì một hàng vẫn phải neo được
   * ở nơi không muốn bấm để điều hướng đi chỗ khác.
   */
  id: number | null;
  o: O[];
  vung: VungTrichDan;
  neo: NeoHang | null;
}

function Bang({
  tieuDe,
  than,
  nhan,
}: {
  tieuDe: { o: O[]; vung: VungTrichDan } | null;
  than: HangBang[];
  nhan: string;
}) {
  const cot = Math.max(soCot(tieuDe === null ? [] : [tieuDe.o]), soCot(than.map((h) => h.o)));
  if (cot === 0) return null;
  // Ô trống bù vào CUỐI hàng thiếu ô. Dồn nội dung sang cột khác để "cho đủ" là
  // đọc lại bảng theo ý mình — trong một bảng lương thì đó là bịa số liệu.
  const bu = (o: O[]) => [...o, ...Array.from({ length: cot - o.length }, () => null)];

  return (
    <div
      // Cuộn ngang nằm TRONG khung này, không đẩy trang. `tabIndex` vì một vùng
      // cuộn không có phần tử focus được bên trong thì bàn phím không tới được.
      tabIndex={0}
      role="region"
      aria-label={nhan}
      className="focus-brass my-3 max-w-full overflow-x-auto rounded-lg border border-border"
    >
      {/* `min-w` là thứ BIẾN vùng cuộn trên thành cuộn thật. Không có nó, bảng
          co lại vừa 332px của màn 390px và "Vùng I" gãy làm hai dòng — một nhãn
          pháp lý bị bẻ đôi. 30rem cho mỗi cột đủ chỗ cho một mốc lương trên một
          dòng; rộng hơn nữa thì bảng ba cột phải cuộn hết hai màn mới đọc xong.
          ponytail: một ngưỡng chung cho mọi bảng — nếu sau này có bảng nhiều cột
          hơn cần ngưỡng riêng thì tính theo số cột. */}
      <table className="w-full min-w-[30rem] border-collapse text-[14px] leading-[1.6]">
        {tieuDe !== null && (
          <thead>
            <tr className="bg-[var(--color-paper-100)]">
              {bu(tieuDe.o).map((o, i) => (
                <th
                  key={i}
                  scope="col"
                  className="border border-border px-2.5 py-1.5 text-left align-top font-semibold"
                >
                  {o !== null && <ChuCoTo text={o.text} tu={o.tu} vung={tieuDe.vung} />}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {than.map((hang) => (
            <tr key={hang.khoa} id={hang.id === null ? undefined : `dk-${hang.id}`}>
              {bu(hang.o).map((o, i) =>
                o === null ? (
                  <td key={i} className="border border-border px-2.5 py-1.5" />
                ) : (
                  <ODuLieu
                    key={i}
                    o={o}
                    vung={hang.vung}
                    // Chỉ ô ĐẦU mang liên kết: cả hàng là một neo, và biến mọi
                    // ô số tiền thành liên kết thì bảng đọc thành một rừng gạch
                    // chân.
                    neo={i === 0 ? hang.neo : null}
                    nhanHang={i === 0 && hang.id !== null}
                  />
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export interface NoiDungDieuKhoanProps {
  dieuKhoan: Provision;
  /**
   * Nguyên văn để hiện. Tách khỏi `dieuKhoan.noi_dung` vì màn đọc toàn văn cắt
   * phần tiêu đề lặp ở đầu Điều trước khi in.
   */
  noiDung: string;
  /** `hang_bang` đã tách khỏi dòng này. Rỗng ở dạng B và ở mọi dòng không bảng. */
  hangCon?: readonly Provision[];
  /** Có → tô sáng câu trích trong chính dòng này. */
  quote?: string | null;
  /** Có → hàng đã tách bấm được. Không có → bảng vẫn hiện, chỉ không bấm. */
  docId?: string | null;
  /** Thụt lề theo cấp, do nơi gọi quyết định. */
  style?: React.CSSProperties;
}

export function NoiDungDieuKhoan({
  dieuKhoan,
  noiDung,
  hangCon = [],
  quote = null,
  docId = null,
  style,
}: NoiDungDieuKhoanProps) {
  // Điều khoản đã bị bãi bỏ: backend không gửi nội dung, chỉ câu bãi bỏ. Một chỗ cho cả
  // khung đối chiếu lẫn màn đọc toàn văn (quyết định 2026-09-30 mục 9).
  const baiBo = dieuKhoan.bai_bo;
  if (baiBo) {
    const so =
      dieuKhoan.cap === "khoan"
        ? `${dieuKhoan.so_hieu_cap}. `
        : dieuKhoan.cap === "diem"
          ? `${dieuKhoan.so_hieu_cap}) `
          : "";
    return (
      <p
        data-bai-bo
        style={style}
        className="my-2 text-[15px] leading-[1.75] text-muted-foreground italic"
      >
        {so}Đã bị bãi bỏ bởi {baiBo.boi_dieu_khoan}{" "}
        <LinkVanBanDan vanBan={baiBo.van_ban}>{baiBo.ten_goi}</LinkVanBanDan> từ ngày{" "}
        {ngayVietNam(baiBo.tu_ngay)}.
      </p>
    );
  }
  const doan = tachDoan(noiDung);
  const vung = vungTrichDan(noiDung, quote);

  // Dạng A: hàng tiêu đề là khối bảng CUỐI CÙNG trong `noi_dung` của cha —
  // backend để nó ở lại đúng chỗ đó khi tách hàng dữ liệu ra. Không có khối
  // bảng nào thì các hàng con vẫn ra bảng, chỉ không có `<thead>`.
  const chiSoTieuDe = hangCon.length === 0 ? -1 : doan.map((d) => d.loai).lastIndexOf("bang");

  const thanTach: HangBang[] = hangCon.map((hang) => {
    const [khoiDau] = tachDoan(hang.noi_dung).flatMap((d) => (d.loai === "bang" ? d.hang : []));
    return {
      khoa: String(hang.id),
      id: hang.id,
      o: khoiDau ?? [],
      vung: vungTrichDan(hang.noi_dung, quote),
      neo: docId === null ? null : { docId, id: hang.id, duongDan: hang.duong_dan },
    };
  });

  const nhanBang = `Bảng trong ${dieuKhoan.duong_dan}`;

  return (
    <div style={style}>
      {doan.map((d, i) => {
        if (d.loai === "van") {
          return (
            <p key={i} className="my-2 text-[16px] leading-[1.75] whitespace-pre-wrap">
              <ChuCoTo text={d.text} tu={d.tu} vung={vung} />
            </p>
          );
        }
        if (i === chiSoTieuDe) {
          const [tieuDe] = d.hang;
          return (
            <Bang
              key={i}
              tieuDe={tieuDe === undefined ? null : { o: tieuDe, vung }}
              than={thanTach}
              nhan={nhanBang}
            />
          );
        }
        // Dạng B — cả bảng nằm trong một `noi_dung`, không hàng nào được khai
        // là tiêu đề, nên tất cả vào `<tbody>`.
        return (
          <Bang
            key={i}
            tieuDe={null}
            than={d.hang.map((o, j) => ({ khoa: String(j), id: null, o, vung, neo: null }))}
            nhan={nhanBang}
          />
        );
      })}

      {/* Có hàng tách nhưng `noi_dung` của cha không còn khối bảng nào: vẫn
          phải dựng bảng, nếu không 4 hàng lương biến mất khỏi màn hình. */}
      {chiSoTieuDe < 0 && thanTach.length > 0 && (
        <Bang tieuDe={null} than={thanTach} nhan={nhanBang} />
      )}
    </div>
  );
}
