import { createFileRoute, Link } from "@tanstack/react-router";
import { MarketingShell } from "@/components/marketing/MarketingShell";
import { useTaiMot } from "@/hooks/use-goi-api";
import { laBoLoc, laPhamVi, type BoLoc, type PhamVi } from "@/lib/klaw";
import { SITE_ORIGIN } from "./__root";

/**
 * `/du-lieu` — kho này lấy từ đâu.
 *
 * Trang BẢN KÊ, không phải trang tiếp thị. Mỗi con số ở đây đến từ một
 * endpoint đang chạy (`GET /pham-vi`, `GET /bo-loc`), không một con số nào
 * viết cứng — cùng ràng buộc với trang chủ, và vì lý do mạnh hơn: một trang
 * tự khai nguồn dữ liệu mà nói sai về chính nó thì không còn nghĩa gì.
 *
 * Hai chỗ trang này CỐ Ý không nói:
 *
 * - **Ngày lấy dữ liệu.** Không endpoint nào công bố mốc thời gian thu thập.
 *   Trang nêu khoảng năm BAN HÀNH (`/bo-loc`) và nói thẳng rằng đó là thứ khác
 *   — thay vì in ra một ngày trông như ngày cập nhật.
 * - **Số văn bản có bản đồ sửa đổi từ Công báo.** Cũng không endpoint nào tổng
 *   hợp con số đó. Trang mô tả phạm vi bằng lời và chỉ đường tới một ví dụ
 *   kiểm được, thay vì đếm bằng một con số sẽ trôi.
 */

/** Ví dụ kiểm được cho nguồn thứ hai: Bộ luật Lao động là văn bản duy nhất
 *  hiện có bản đồ sửa đổi cấp điều khoản. `doc_id`, không phải số hiệu. */
const DOC_ID_BLLD = "139264";

function Muc({ tieuDe, children }: { tieuDe: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="font-display m-0 text-[20px] leading-snug font-bold text-primary">{tieuDe}</h2>
      <div className="doc-prose mt-3 text-foreground">{children}</div>
    </section>
  );
}

/** Đếm loại văn bản của MỘT tầng, từ chính danh sách máy chủ trả về. */
function demTheoLoai(vanBan: { loai_van_ban: string }[]): [string, number][] {
  const dem = new Map<string, number>();
  for (const vb of vanBan) dem.set(vb.loai_van_ban, (dem.get(vb.loai_van_ban) ?? 0) + 1);
  return [...dem.entries()].sort((a, b) => b[1] - a[1]);
}

function BangTang({ phamVi }: { phamVi: PhamVi }) {
  const tang = [
    {
      ten: "Có toàn văn",
      giaiThich: "trích dẫn được tới điều, khoản, điểm",
      so: phamVi.sau.so_van_ban,
      dieuKhoan: phamVi.sau.so_dieu_khoan,
      loai: demTheoLoai(phamVi.sau.van_ban),
    },
    {
      ten: "Chỉ có thông tin văn bản",
      giaiThich: "nêu được đích danh, không diễn giải",
      so: phamVi.nong.so_van_ban,
      dieuKhoan: phamVi.nong.so_dieu_khoan,
      loai: demTheoLoai(phamVi.nong.van_ban),
    },
  ];
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      {tang.map((t) => (
        <section key={t.ten} className="rounded-xl border border-border bg-card p-4">
          <h3 className="m-0 text-[13px] leading-5 font-medium text-muted-foreground">
            {t.ten}
            <span className="block font-normal">{t.giaiThich}</span>
          </h3>
          <p className="font-display m-0 mt-2 text-2xl font-bold text-primary">
            {t.so}
            <span className="ml-1.5 font-sans text-[13px] font-normal text-muted-foreground">
              văn bản · {t.dieuKhoan.toLocaleString("vi-VN")} điều khoản
            </span>
          </p>
          <ul className="mt-3 mb-0 flex list-none flex-wrap gap-x-3 gap-y-1 p-0 text-[12.5px] text-muted-foreground">
            {t.loai.map(([loai, so]) => (
              <li key={loai}>
                {loai} <span className="font-jetbrains text-foreground">{so}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function TrangDuLieu() {
  const phamVi = useTaiMot("/pham-vi", laPhamVi);
  const boLoc = useTaiMot<BoLoc>("/bo-loc", laBoLoc);

  return (
    <MarketingShell>
      <article className="mx-auto w-full max-w-[46rem] px-5 py-12">
        <h1 className="font-display m-0 text-[32px] leading-tight font-bold text-primary">
          Dữ liệu trong kho lấy từ đâu
        </h1>
        <p className="doc-prose mt-4 text-foreground">
          Đây là <strong className="font-semibold">bản kê</strong>. Mọi con số trên trang đọc thẳng
          từ máy chủ đang chạy, không chép tay — nên nếu kho thay đổi mà trang này không đổi theo
          thì đó là lỗi, không phải sự ổn định.
        </p>

        <Muc tieuDe="Nguồn thứ nhất — Cơ sở dữ liệu quốc gia về văn bản quy phạm pháp luật">
          <p className="m-0">
            Nguyên văn và phần thông tin của các văn bản có toàn văn đến từ API công khai của{" "}
            <strong className="font-semibold">Bộ Tư pháp</strong> — riêng Luật Khiếu nại
            02/2011/QH13 lấy từ Cổng Thông tin điện tử Chính phủ. Mọi câu trích KLAW hiện ra đều là
            chữ của hai nguồn nhà nước đó, giữ nguyên văn.
          </p>
          <p>
            Nguồn này cũng có một cột trạng thái hiệu lực. KLAW{" "}
            <strong className="font-semibold">không hiển thị cột đó</strong> — nó đánh dấu bốn nghị
            định lương tối thiểu đã bị thay thế là “còn hiệu lực”. Mọi nhãn hiệu lực trên giao diện
            là kết luận của KLAW, không phải tuyên bố của nguồn.{" "}
            <Link to="/mien-tru" className="focus-brass rounded underline underline-offset-2">
              Xem bốn trường hợp đó
            </Link>
            .
          </p>
        </Muc>

        <Muc tieuDe="Nguồn thứ hai — Công báo Chính phủ">
          <p className="m-0">
            <span className="font-jetbrains text-[14px]">congbao.chinhphu.vn</span> phát hành văn
            bản hợp nhất dạng <span className="font-jetbrains text-[14px]">.docx</span> gốc. KLAW
            dùng nguồn này cho <strong className="font-semibold">đúng một việc</strong>: suy ra bản
            đồ sửa đổi ở cấp điều khoản — điều nào bị sửa, bởi văn bản nào, từ ngày nào.
          </p>
          <p>
            <strong className="font-semibold">
              Không một chữ nguyên văn nào lấy từ nguồn này.
            </strong>{" "}
            Bản hợp nhất chỉ dùng để suy ra quan hệ sửa đổi; chữ vẫn là chữ của văn bản gốc.
          </p>
          <p>
            Phạm vi hôm nay rất hẹp: mới{" "}
            <Link
              to="/tra-cuu/$docId"
              params={{ docId: DOC_ID_BLLD }}
              className="focus-brass rounded font-medium text-[var(--color-brass-600)] underline-offset-2 hover:underline"
            >
              Bộ luật Lao động
            </Link>{" "}
            có bản đồ này. Các văn bản khác chỉ có nhãn ở mức cả văn bản, và khi hệ thống không biết
            điều khoản nào bị sửa thì nó nói thẳng là không biết.
          </p>
        </Muc>

        {/* Ghi nguồn theo điều kiện CC BY 4.0 (tác giả, tên, link, giấy phép) —
            giấy phép đã đối chiếu trên trang bộ dữ liệu ngày 2026-09-28. */}
        <Muc tieuDe="Nguồn thứ ba — bộ dữ liệu mở Vietnamese Legal Documents">
          <p className="m-0">
            Phần thông tin của các văn bản <em>chỉ có tên</em> (tầng “Chỉ có thông tin văn bản” ở
            dưới) và đồ thị quan hệ giữa các văn bản — thay thế, sửa đổi, bãi bỏ, hướng dẫn — được
            nạp hàng loạt từ{" "}
            <a
              href="https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents"
              target="_blank"
              rel="noopener noreferrer"
              className="focus-brass rounded underline underline-offset-2"
            >
              th1nhng0/vietnamese-legal-documents (HuggingFace, CC-BY-4.0)
              <span className="sr-only"> (mở tab mới)</span>
            </a>
            , bộ dữ liệu do Thịnh Ngô biên soạn từ vbpl.vn, phát hành theo giấy phép{" "}
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className="focus-brass rounded underline underline-offset-2"
            >
              Creative Commons Ghi công 4.0
              <span className="sr-only"> (mở tab mới)</span>
            </a>
            .
          </p>
          <p>
            <strong className="font-semibold">
              Không một chữ nguyên văn điều khoản nào lấy từ bộ dữ liệu này.
            </strong>{" "}
            Toàn văn vẫn đến từ nguồn thứ nhất.
          </p>
        </Muc>

        <Muc tieuDe="Kho có gì, tính đến lúc bạn mở trang này">
          {phamVi.ketQua === null ? (
            <p className="m-0 text-muted-foreground">Đang đọc số liệu từ máy chủ…</p>
          ) : (
            <BangTang phamVi={phamVi.ketQua} />
          )}
          {boLoc.ketQua !== null &&
            boLoc.ketQua.nam_min !== null &&
            boLoc.ketQua.nam_max !== null && (
              <p className="mt-4 mb-0">
                Phần có toàn văn gồm văn bản{" "}
                <strong className="font-semibold">
                  ban hành từ {boLoc.ketQua.nam_min} đến {boLoc.ketQua.nam_max}
                </strong>
                .
              </p>
            )}
        </Muc>

        <Muc tieuDe="Kho được lấy về khi nào — câu trang này không trả lời được">
          <p className="m-0">
            Không endpoint nào của KLAW công bố mốc thời gian thu thập, nên trang này{" "}
            <strong className="font-semibold">không in ra một ngày cập nhật</strong>. Khoảng năm ở
            trên là năm <em>ban hành</em> của văn bản, một thứ khác hẳn: một kho lấy về từ lâu vẫn
            hiện đúng khoảng năm ấy.
          </p>
          <p>
            Điều đó có nghĩa là bạn không thể biết, từ giao diện này, kho có bỏ sót văn bản mới ban
            hành hay không. Đây là một giới hạn thật, và in một ngày đoán ra sẽ tệ hơn im lặng.
          </p>
        </Muc>

        <Muc tieuDe="Bản quyền — văn bản quy phạm pháp luật không thuộc phạm vi bảo hộ">
          <p className="m-0">
            Theo <strong className="font-semibold">Điều 15 Luật Sở hữu trí tuệ</strong>, văn bản quy
            phạm pháp luật, văn bản hành chính, văn bản khác thuộc lĩnh vực tư pháp và bản dịch
            chính thức của những văn bản đó{" "}
            <strong className="font-semibold">không thuộc đối tượng bảo hộ quyền tác giả</strong>.
            Đó là cơ sở để KLAW lưu và hiển thị nguyên văn.
          </p>
          <p
            className="m-0 mt-3 rounded-lg border-l-2 py-2 pl-3 text-[14px] leading-6 text-muted-foreground"
            style={{ borderLeftColor: "var(--color-status-neutral)" }}
          >
            Nói cho hết:{" "}
            <strong className="font-medium">
              Luật Sở hữu trí tuệ không nằm trong kho của KLAW
            </strong>
            , nên chính câu vừa rồi là câu KLAW không tự kiểm chứng được theo cách nó kiểm chứng mọi
            câu trả lời khác. Hãy đối chiếu với nguồn chính thức nếu bạn cần dựa vào nó.
          </p>
        </Muc>

        <Muc tieuDe="Trang này không nói về dữ liệu của bạn">
          <p className="m-0">
            Đây là bản kê nguồn của kho văn bản. Nội dung bạn nhập — câu hỏi, bản thảo — là chuyện
            khác, và KLAW chưa công bố chính sách bảo vệ dữ liệu cá nhân đã qua pháp chế. Trang này
            không thay thế chính sách đó và không giả vờ có nó.
          </p>
        </Muc>

        <p className="mt-10 mb-0 text-[13px] leading-6 text-muted-foreground">
          Giới hạn của những câu trả lời dựng trên kho này:{" "}
          <Link to="/mien-tru" className="focus-brass rounded underline underline-offset-2">
            xem trang giới hạn và miễn trừ
          </Link>
          .
        </p>
      </article>
    </MarketingShell>
  );
}

export const Route = createFileRoute("/du-lieu")({
  component: TrangDuLieu,
  head: () => {
    const title = "Nguồn dữ liệu — KLAW";
    const description =
      "Kho văn bản của KLAW lấy từ API công khai của Bộ Tư pháp, Công báo Chính phủ và bộ dữ liệu mở th1nhng0/vietnamese-legal-documents (CC BY 4.0). Bản kê số lượng, loại văn bản và cơ sở pháp lý để lưu trữ nguyên văn.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "article" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
      links: [{ rel: "canonical", href: `${SITE_ORIGIN}/du-lieu` }],
    };
  },
});
