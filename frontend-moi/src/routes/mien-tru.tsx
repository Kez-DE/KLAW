import { createFileRoute, Link } from "@tanstack/react-router";
import { MarketingShell } from "@/components/marketing/MarketingShell";
import { useTaiMot } from "@/hooks/use-goi-api";
import { laPhamVi, type PhamVi } from "@/lib/klaw";
import { SITE_ORIGIN } from "./__root";

/**
 * `/mien-tru` — giới hạn và miễn trừ.
 *
 * Trang này nói về SỰ THẬT CỦA HỆ THỐNG, nên sai một câu ở đây là hứa sai với
 * người đang định dựa vào một câu trả lời để quyết định điều gì đó thật. Ba
 * quy tắc khi sửa nó:
 *
 * 1. **Không câu rào đón cho có.** Mỗi đoạn dưới đây nêu một giới hạn ĐO ĐƯỢC,
 *    không phải một câu bảo hiểm trách nhiệm. Một trang miễn trừ toàn lời sáo
 *    dạy người đọc bỏ qua nó, và lần sau họ bỏ qua cả cảnh báo thật.
 * 2. **Số lấy từ `GET /pham-vi`.** Không viết cứng. Con số viết cứng sai ngay
 *    lần seed tiếp theo và không ai biết — đúng loại khẳng định không kiểm
 *    chứng được mà cả sản phẩm này tồn tại để chống.
 * 3. **Ranh giới bảo đảm phải nói thẳng:** KLAW bảo đảm *nguồn gốc* và *đúng
 *    nguyên văn*; KLAW **không** bảo đảm *là bản hiện hành*. Không được làm
 *    mềm câu thứ ba.
 */

/**
 * Bốn nghị định CSDL quốc gia đánh `CHL` (còn hiệu lực) mà `effectivity.py`
 * kết luận đã bị thay thế. ĐO TRÊN MÁY CHỦ ĐANG CHẠY hôm nay: cột
 * `tinh_trang_moj` của `/pham-vi` so với `verdict` của
 * `/van-ban/{doc_id}/hieu-luc`.
 *
 * `doc_id` là khoá duy nhất tuyệt đối, nên liên kết dựng từ nó — mỗi dòng mở
 * ra chính trang có nhãn và lý do sống, để người đọc tự kiểm chứ không phải
 * tin trang này.
 */
const BON_NGHI_DINH: { docId: string; soKyHieu: string; theoKlaw: string }[] = [
  { docId: "92898", soKyHieu: "122/2015/NĐ-CP", theoKlaw: "bị 153/2016/NĐ-CP thay thế" },
  { docId: "126319", soKyHieu: "141/2017/NĐ-CP", theoKlaw: "bị 157/2018/NĐ-CP thay thế" },
  { docId: "132862", soKyHieu: "157/2018/NĐ-CP", theoKlaw: "bị 90/2019/NĐ-CP thay thế" },
  { docId: "139094", soKyHieu: "90/2019/NĐ-CP", theoKlaw: "bị 74/2024/NĐ-CP thay thế" },
];

function Muc({ tieuDe, children }: { tieuDe: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="font-display m-0 text-[20px] leading-snug font-bold text-primary">{tieuDe}</h2>
      <div className="doc-prose mt-3 text-foreground">{children}</div>
    </section>
  );
}

function SoKho({ phamVi }: { phamVi: PhamVi }) {
  const tong = phamVi.sau.so_van_ban + phamVi.nong.so_van_ban;
  return (
    <p className="m-0">
      Kho hiện có <strong className="font-semibold">{tong}</strong> văn bản. Trong đó{" "}
      <strong className="font-semibold">{phamVi.sau.so_van_ban}</strong> văn bản có toàn văn máy đọc
      được ({phamVi.sau.so_dieu_khoan.toLocaleString("vi-VN")} điều khoản) — đây là phần duy nhất
      trích dẫn được tới điều, khoản, điểm. {phamVi.nong.so_van_ban} văn bản còn lại chỉ có phần
      thông tin văn bản; hỏi về chúng, KLAW nêu đích danh văn bản chi phối rồi dừng lại thay vì diễn
      giải.
    </p>
  );
}

function TrangMienTru() {
  const phamVi = useTaiMot("/pham-vi", laPhamVi);

  return (
    <MarketingShell>
      <article className="mx-auto w-full max-w-[46rem] px-5 py-12">
        <h1 className="font-display m-0 text-[32px] leading-tight font-bold text-primary">
          Giới hạn và miễn trừ
        </h1>
        <p className="doc-prose mt-4 text-foreground">
          Đọc trang này trước khi dựa vào một câu trả lời của KLAW để quyết định điều gì đó. Không
          đoạn nào dưới đây là câu rào đón cho có — đây là những giới hạn đo được của hệ thống.
        </p>

        <Muc tieuDe="Hai điều KLAW bảo đảm, và một điều KLAW không bảo đảm">
          <p className="m-0">
            <strong className="font-semibold">Bảo đảm nguồn gốc:</strong> mỗi trích dẫn bạn thấy trỏ
            tới một điều khoản có thật trong kho, và địa chỉ của nó — số hiệu văn bản, Điều, Khoản,
            Điểm — là địa chỉ thật. KLAW không dựng được một trích dẫn tới điều luật không tồn tại:
            phép kiểm đó là một lượt tra bảng, không phải một phán đoán của mô hình.
          </p>
          <p>
            <strong className="font-semibold">Bảo đảm đúng nguyên văn:</strong> câu trích hiện ra
            đúng như trong kho — không rút gọn, không sửa chính tả, không diễn đạt lại.
          </p>
          <p>
            <strong className="font-semibold">
              KLAW KHÔNG bảo đảm đây là bản đang có hiệu lực.
            </strong>{" "}
            Đây là giới hạn quan trọng nhất trên trang này, và nó không mềm đi được. Một điều luật
            có thật, trích đúng nguyên văn, vẫn có thể đã bị một văn bản khác sửa đổi hoặc thay thế.
            Vì vậy mỗi trích dẫn mang một nhãn hiệu lực, và nhãn đó luôn nằm cạnh câu trích — không
            bao giờ giấu trong tooltip hay metadata.
          </p>
        </Muc>

        <Muc tieuDe="Kho là văn bản gốc, không phải bản hợp nhất">
          <p className="m-0">
            “Bản hợp nhất” là bản đã gộp mọi lần sửa đổi thành một bản duy nhất. Kho của KLAW{" "}
            <strong className="font-semibold">không chứa bản hợp nhất</strong> — chỉ chứa văn bản
            gốc, tức bản được công bố tại thời điểm ban hành. Lý do rất cụ thể: các bản hợp nhất
            công bố trên cổng của Bộ Tư pháp là PDF quét, không có toàn văn máy đọc được.
          </p>
          <p>
            Hệ quả thật, nói thẳng: hệ thống ngày càng nói đúng được rằng một câu trả lời{" "}
            <em>không còn hiện hành</em>, nhưng phần lớn trường hợp nó vẫn{" "}
            <strong className="font-semibold">chưa nói được câu trả lời hiện hành là gì</strong> —
            vì văn bản sửa đổi thường chưa nằm trong kho.
          </p>
          {phamVi.ketQua !== null && <SoKho phamVi={phamVi.ketQua} />}
        </Muc>

        <Muc tieuDe="Chiều sâu không đều giữa các lĩnh vực">
          <p className="m-0">
            Riêng cụm Lao động có đủ luật, nghị định hướng dẫn, thông tư và chế tài xử phạt. Các
            lĩnh vực còn lại phần lớn chỉ có bản thân bộ luật, không có văn bản dưới luật. Một câu
            trả lời về lao động và một câu trả lời về lĩnh vực khác{" "}
            <strong className="font-semibold">không có cùng độ tin cậy</strong>, dù giao diện trình
            bày chúng giống nhau.
          </p>
          <p>
            KLAW không phủ thuế, đất đai, hôn nhân gia đình, doanh nghiệp, đầu tư, sở hữu trí tuệ.
            Hỏi về chúng, hệ thống trả lời “ngoài phạm vi” thay vì đoán.
          </p>
        </Muc>

        <Muc tieuDe="Ngay cả cơ sở dữ liệu chính thức cũng sai">
          <p className="m-0">
            Cơ sở dữ liệu quốc gia về văn bản quy phạm pháp luật — nguồn mà KLAW và nhiều hệ thống
            khác dựa vào — đánh dấu{" "}
            <strong className="font-semibold">bốn nghị định lương tối thiểu</strong> là “còn hiệu
            lực” dù cả bốn đã bị thay thế. KLAW phát hiện và sửa cả bốn. Bấm từng dòng để đọc nhãn
            và lý do trên chính trang văn bản, thay vì tin trang này:
          </p>
          <ul className="mt-3 mb-0 list-none space-y-1.5 p-0">
            {BON_NGHI_DINH.map((nd) => (
              <li key={nd.docId} className="text-[15px] leading-6">
                <Link
                  to="/tra-cuu/$docId"
                  params={{ docId: nd.docId }}
                  className="focus-brass font-jetbrains rounded text-[14px] font-medium text-[var(--color-brass-600)] underline-offset-2 hover:underline"
                >
                  {nd.soKyHieu}
                </Link>
                <span className="text-muted-foreground">
                  {" "}
                  — CSDL quốc gia ghi “còn hiệu lực”, KLAW kết luận {nd.theoKlaw}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-5">
            Đây không phải lời khẳng định rằng KLAW không thể sai. Ngược lại: nó là bằng chứng đo
            được rằng ngay cả nguồn chính thức cũng sai, nên đừng coi bất kỳ nguồn nào — kể cả KLAW
            — là đúng tuyệt đối.
          </p>
        </Muc>

        <Muc tieuDe="KLAW không phải tư vấn pháp lý">
          <p className="m-0">
            KLAW không thay thế luật sư, cán bộ công đoàn hay thanh tra lao động. Đây là công cụ tra
            cứu và soạn thảo: nó giúp bạn tìm nhanh điều luật liên quan và đọc đúng nguyên văn,
            không đưa ra ý kiến pháp lý cho tình huống cụ thể của bạn.
          </p>
          <p>
            Với bất kỳ quyết định nào có hậu quả thật — bị sa thải, tranh chấp lương, khởi kiện, ký
            một văn bản ràng buộc — hãy để người có chuyên môn kiểm tra lại trước khi hành động.
          </p>
        </Muc>

        <Muc tieuDe="Khi hệ thống dừng lại, đó là hành vi đúng">
          <p className="m-0">
            Khi không đủ căn cứ, KLAW nói thẳng là không đủ căn cứ và dừng ở đó. Trạng thái đó mang
            màu trung tính và giọng bình thường vì{" "}
            <strong className="font-semibold">nó không phải lỗi</strong>: một hệ thống thà nhận
            không biết còn hơn bịa một điều luật. Đừng đọc nó như một trục trặc cần thử lại bằng
            cách khác cho tới khi ra được một câu trả lời.
          </p>
        </Muc>

        <Muc tieuDe="Đây là sản phẩm khoá luận tốt nghiệp">
          <p className="m-0">
            KLAW được xây như một sản phẩm dùng thật, với cơ chế kiểm chứng trích dẫn thật và được
            đo lường nghiêm túc — nhưng nó không phải một dịch vụ pháp lý thương mại có đội ngũ hỗ
            trợ hay cam kết chất lượng dịch vụ. Hãy cân nhắc điều đó khi quyết định mức độ tin cậy
            đặt vào một câu trả lời.
          </p>
        </Muc>

        <p className="mt-10 mb-0 text-[13px] leading-6 text-muted-foreground">
          Muốn biết dữ liệu trong kho lấy từ đâu?{" "}
          <Link to="/du-lieu" className="focus-brass rounded underline underline-offset-2">
            Xem trang nguồn dữ liệu
          </Link>
          .
        </p>
      </article>
    </MarketingShell>
  );
}

export const Route = createFileRoute("/mien-tru")({
  component: TrangMienTru,
  head: () => {
    const title = "Giới hạn và miễn trừ — KLAW";
    const description =
      "KLAW bảo đảm nguồn gốc và đúng nguyên văn của mỗi trích dẫn, không bảo đảm đây là bản đang có hiệu lực. Kho là văn bản gốc, không phải bản hợp nhất.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "article" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
      links: [{ rel: "canonical", href: `${SITE_ORIGIN}/mien-tru` }],
    };
  },
});
