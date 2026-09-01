import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { BookOpenText, FileSearch, Info } from "lucide-react";
import type { Citation, Nguon, TraCuuKetQua } from "@/lib/klaw";
import { nhomHieuLuc, xepTrichDan } from "@/lib/trich-dan";
import { cn } from "@/lib/utils";
import { catDoan } from "@/lib/van-xuoi";
import { BadgeHieuLuc } from "./BadgeHieuLuc";

/**
 * Bốn `result_type`, bốn cách hiển thị — không thương lượng.
 *
 * Bản Klaw_FE co bốn nhánh còn hai (`answer` | `nobasis`), làm mất
 * `partial_coverage` — nhánh của tầng metadata, ĐO LẠI hôm nay là 79/126 văn
 * bản trong kho — cùng `nguon[]`,
 * thứ DUY NHẤT mở được văn bản ở nhánh đó; và mất luôn `out_of_scope`.
 *
 * `abstain` là hành vi ĐÚNG và được tính điểm trong đánh giá: một hệ thống thà
 * nói "tôi không đủ căn cứ" còn hơn bịa một điều luật. Nên nó mang màu TRUNG
 * TÍNH, giọng bình thường, KHÔNG icon cảnh báo, KHÔNG đỏ, KHÔNG cam, không
 * rung. Bản Klaw_FE tô nhánh này cam kèm `TriangleAlert` — đó là giao diện
 * tranh luận chống lại chính luận điểm của sản phẩm: nó dạy người dùng rằng sự
 * trung thực là một thất bại.
 *
 * Đỏ chỉ dành cho luật đã bị thay thế hoặc hết hiệu lực.
 */

/** Phạm vi kho, chép từ PRODUCT.md. Không suy đoán thêm lĩnh vực nào. */
const SAU_BO_LUAT = [
  "Dân sự",
  "Tố tụng dân sự",
  "Tố tụng hình sự",
  "Hình sự",
  "Hàng hải",
  "Lao động",
];
const KHONG_PHU = [
  "thuế",
  "đất đai",
  "hôn nhân gia đình",
  "doanh nghiệp",
  "đầu tư",
  "sở hữu trí tuệ",
];

const GOI_Y_DIEN_DAT_LAI = [
  "Nêu rõ vai trò trong quan hệ lao động: người lao động hay người sử dụng lao động.",
  'Dùng từ ngữ của luật thay cho từ thông tục (ví dụ: "đơn phương chấm dứt hợp đồng lao động" thay cho "đuổi việc").',
  "Tách câu hỏi dài thành từng ý riêng, hỏi lần lượt.",
  "Nếu hỏi về một mức tiền cụ thể, nêu rõ năm áp dụng.",
];

/**
 * Khay trung tính dùng cho `abstain` và `out_of_scope`.
 *
 * Cùng một hình dạng với khay `partial_coverage` ngay dưới, khác đúng ở màu
 * viền — để hai nhánh "hệ thống không trả lời" đọc như cùng một loại sự việc,
 * không phải như hai mức báo động.
 */
function KhayTrungTinh({ tieuDe, children }: { tieuDe: string; children?: React.ReactNode }) {
  return (
    <div
      className="rounded-xl border-l-2 bg-[var(--color-paper-50)] py-3 pr-4 pl-4"
      style={{ borderLeftColor: "var(--color-status-neutral)" }}
    >
      <p className="doc-prose m-0 text-foreground">{tieuDe}</p>
      {children}
    </div>
  );
}

/**
 * Cảnh báo hiệu lực — KHÔNG BAO GIỜ giấu vào tooltip hay metadata.
 * Đây là chỗ duy nhất trong thẻ kết quả được dùng màu đỏ.
 */
function KhoiCanhBao({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <section
      aria-label="Cảnh báo hiệu lực"
      className="mt-4 rounded-lg border-l-2 bg-[var(--color-paper-50)] py-2 pl-3"
      style={{ borderLeftColor: "var(--color-status-expired)" }}
    >
      <h3
        className="m-0 text-[13px] leading-5 font-semibold"
        style={{ color: "var(--color-status-expired)" }}
      >
        Cảnh báo hiệu lực
      </h3>
      <ul className="mt-1 mb-0 list-disc pl-4 text-[14px] leading-6 text-foreground">
        {warnings.map((canhBao) => (
          <li key={canhBao}>{canhBao}</li>
        ))}
      </ul>
    </section>
  );
}

/**
 * `nguon[]` — văn bản chi phối câu hỏi. CHỈ `partial_coverage` điền.
 *
 * Nhánh đó luôn có `citations: []` theo thiết kế, nên đây là thứ DUY NHẤT mở
 * được văn bản đang nói tới. `coverage_note` có nêu tên văn bản trong văn xuôi,
 * nhưng cạo chuỗi đó ra để dựng liên kết là bịa một địa chỉ: mỗi liên kết dưới
 * đây đến từ `doc_id` máy chủ trả về.
 *
 * Đây KHÔNG phải trích dẫn đã kiểm chứng — không `quote`, không nhãn hiệu lực.
 * Câu dẫn phải nói đúng như vậy.
 */
function KhoiNguon({
  nguon,
  onMoVanBan,
}: {
  nguon: Nguon[];
  onMoVanBan?: (docId: string) => void;
}) {
  if (nguon.length === 0) return null;
  return (
    <section aria-label="Văn bản chi phối câu hỏi" className="mt-4">
      <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
        Văn bản chi phối câu hỏi này — mở để tự đối chiếu
      </h3>
      <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">
        {nguon.map((vanBan) => {
          const noiDung = (
            <>
              <BookOpenText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              <span className="font-jetbrains text-[13px] text-foreground">
                {vanBan.so_ky_hieu}
              </span>
              <span className="text-[13px] text-muted-foreground">{vanBan.bo_luat}</span>
            </>
          );
          // Điều hướng đi qua CALLBACK, không phải một <Link> viết cứng.
          // Tuyến duy nhất mở văn bản trong bản dựng này là `/tra-cuu/$soHieu`,
          // tức định danh bằng SỐ HIỆU — mà `65/2006/QH11` thuộc HAI văn bản
          // khác nhau, nên một liên kết dựng từ số hiệu có thể mở nhầm văn bản.
          // Khoá duy nhất tuyệt đối là `doc_id`. Thành phần này giao `doc_id`
          // cho nơi gọi và không tự chọn tuyến; nợ tuyến đó thuộc pha nối FE.
          return (
            <li key={vanBan.doc_id}>
              {onMoVanBan === undefined ? (
                <div className="flex min-h-11 items-center gap-2 rounded-lg border border-border bg-card p-3">
                  {noiDung}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => onMoVanBan(vanBan.doc_id)}
                  className="focus-brass flex min-h-11 w-full cursor-pointer items-center gap-2 rounded-lg border border-border bg-card p-3 text-left transition-colors hover:bg-[var(--color-paper-100)]"
                >
                  {noiDung}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * Dải trích dẫn. Mỗi chip mở panel đối chiếu bằng `khop_tai_id` — xem
 * `KhungDoiChieu`. Nhãn hiệu lực nằm NGAY trên chip, không phải trong panel:
 * người đọc phải thấy "điều này đã bị thay thế" trước khi quyết định có mở ra
 * đọc hay không.
 */
function DaiTrichDan({
  citations,
  chiSoDangMo,
  onChon,
}: {
  citations: Citation[];
  chiSoDangMo: number | null;
  onChon: (chiSo: number) => void;
}) {
  const [moLichSu, datMoLichSu] = useState(false);

  const daSap = xepTrichDan(citations);
  const conDung = daSap.filter((muc) => nhomHieuLuc(muc.trichDan.hieu_luc) !== 4);
  const lichSu = daSap.filter((muc) => nhomHieuLuc(muc.trichDan.hieu_luc) === 4);

  // Chỉ thu gọn khi CÒN thứ khác để đọc. Một lượt mà mọi trích dẫn đều đã chết
  // vẫn phải bày bằng chứng ra — thu gọn hết thì người dùng không còn gì.
  const chiCoLichSu = conDung.length === 0;
  const hienLichSu = chiCoLichSu || moLichSu || lichSu.some((muc) => muc.chiSoGoc === chiSoDangMo);

  if (citations.length === 0) return null;

  const chip = ({ trichDan, chiSoGoc }: { trichDan: Citation; chiSoGoc: number }) => (
    <li key={`${trichDan.doc_id}-${trichDan.khop_tai_id}`}>
      <button
        type="button"
        onClick={() => onChon(chiSoGoc)}
        aria-expanded={chiSoDangMo === chiSoGoc}
        className={cn(
          "focus-brass block w-full cursor-pointer rounded-lg border p-3 text-left transition-colors",
          chiSoDangMo === chiSoGoc
            ? "border-[var(--ring)] bg-[var(--color-paper-100)]"
            : "border-border bg-card hover:bg-[var(--color-paper-50)]",
        )}
      >
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-jetbrains text-[13px] text-foreground">{trichDan.so_ky_hieu}</span>
          <span className="text-[13px] text-muted-foreground">{trichDan.duong_dan}</span>
        </span>
        <BadgeHieuLuc hieuLuc={trichDan.hieu_luc} className="mt-1.5" />
        <span className="serif-body mt-1.5 block text-[14px] leading-6 text-foreground">
          “{trichDan.quote}”
        </span>
      </button>
    </li>
  );

  return (
    <section aria-label="Trích dẫn đã kiểm chứng" className="mt-4">
      <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
        Trích dẫn — bấm để mở nguyên văn và tự đối chiếu
      </h3>

      {conDung.length > 0 && (
        <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">{conDung.map(chip)}</ul>
      )}

      {lichSu.length > 0 && (
        <div className={cn(conDung.length > 0 && "mt-4")}>
          {/* Nhóm lịch sử luôn mang tiêu đề nói rõ nó là gì, kể cả khi đang mở:
              một chip "Đã bị thay thế" lẫn giữa các chip khác chỉ khác nhau ở
              màu nhãn, còn một mục nằm dưới tiêu đề này thì không đọc nhầm
              thành câu trả lời được. */}
          {chiCoLichSu ? (
            <h4 className="m-0 text-[13px] leading-5 font-semibold text-muted-foreground">
              Quy định cũ — đã hết hiệu lực hoặc bị thay thế ({lichSu.length})
            </h4>
          ) : (
            <button
              type="button"
              onClick={() => datMoLichSu((truoc) => !truoc)}
              aria-expanded={hienLichSu}
              className="focus-brass -mx-1 min-h-6 cursor-pointer rounded px-1 text-left text-[13px] leading-5 font-semibold text-muted-foreground underline underline-offset-2"
            >
              Quy định cũ — đã hết hiệu lực hoặc bị thay thế ({lichSu.length})
            </button>
          )}
          {chiCoLichSu && (
            <p className="mt-1 mb-0 text-[13px] leading-5 text-muted-foreground">
              Lượt này không tìm được điều khoản nào còn hiệu lực. Dưới đây là những gì tìm được —
              đối chiếu văn bản thay thế trước khi dùng.
            </p>
          )}
          {hienLichSu && (
            <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">{lichSu.map(chip)}</ul>
          )}
        </div>
      )}
    </section>
  );
}

/**
 * Nhắc miễn trừ — CHỈ ở nhánh `answer`.
 *
 * Ba nhánh kia đã tự nói ra giới hạn của chúng. `answer` là nhánh DUY NHẤT đưa
 * ra một khẳng định pháp lý, và cũng là nhánh duy nhất người dùng hành động
 * theo mà không nhận ra kho là văn bản GỐC chứ không phải bản hợp nhất. Nhắc ở
 * chân trang là không đủ: người ta đọc câu trả lời rồi đóng tab.
 */
function NhacMienTru() {
  return (
    <p className="mt-6 mb-0 text-[13px] leading-5 text-muted-foreground">
      Câu trả lời dựa trên văn bản gốc, không phải bản hợp nhất — KLAW bảo đảm nguồn gốc và đúng
      nguyên văn, không bảo đảm đây là bản hiện hành.{" "}
      <Link to="/mien-tru" className="focus-brass rounded underline underline-offset-2">
        Giới hạn của hệ thống
      </Link>
      .
    </p>
  );
}

interface TheKetQuaProps {
  ketQua: TraCuuKetQua;
  /** Chỉ số trích dẫn đang mở trong panel đối chiếu, hoặc null. */
  chiSoDangMo?: number | null;
  onChonTrichDan?: (chiSo: number) => void;
  /** Nhận `doc_id` — khoá duy nhất tuyệt đối. Xem ghi chú ở `KhoiNguon`. */
  onMoVanBan?: (docId: string) => void;
}

export function TheKetQua({
  ketQua,
  chiSoDangMo = null,
  onChonTrichDan,
  onMoVanBan,
}: TheKetQuaProps) {
  const {
    result_type: loai,
    answer,
    citations,
    nguon,
    warnings,
    coverage_note: ghiChuPhamVi,
  } = ketQua;
  const chon = onChonTrichDan ?? (() => undefined);

  if (loai === "abstain") {
    return (
      <section aria-label="Kết quả tra cứu">
        <KhayTrungTinh tieuDe="Không tìm thấy căn cứ pháp lý cho câu hỏi này.">
          <p className="mt-2 mb-0 text-[14px] leading-6 text-muted-foreground">
            Hệ thống dừng ở đây thay vì suy đoán. Đây là hành vi được thiết kế, không phải lỗi.
          </p>
          {ghiChuPhamVi !== null && ghiChuPhamVi !== "" && (
            <p className="mt-2 mb-0 text-[14px] leading-6 text-muted-foreground">{ghiChuPhamVi}</p>
          )}
        </KhayTrungTinh>
        <div className="mt-4">
          <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">Thử diễn đạt lại</h3>
          <ul className="doc-prose mt-1 mb-0 list-disc pl-5 text-foreground">
            {GOI_Y_DIEN_DAT_LAI.map((goiY) => (
              <li key={goiY}>{goiY}</li>
            ))}
          </ul>
        </div>
        <KhoiCanhBao warnings={warnings} />
      </section>
    );
  }

  /**
   * Văn xuôi máy chủ trả về, cắt thành đoạn và danh sách.
   *
   * Dùng ở HAI nhánh (`answer` và `gioi_thieu`). Tách ra thay vì chép: đây là
   * chỗ duy nhất biết `catDoan` trả về hai loại đoạn, và hai bản sao của tri
   * thức đó sẽ lệch nhau đúng lúc thêm loại thứ ba.
   *
   * `catDoan` chỉ CẮT, không sửa chữ: câu trả lời mang số Điều ngay trong lời
   * văn (`… (Điều 25, Khoản 1)`) và đó là căn cứ, không phải trang trí.
   */
  function KhoiVanXuoi({ chu }: { chu: string }) {
    return (
      <>
        {catDoan(chu).map((doan, i) =>
          doan.kieu === "danh_sach" ? (
            <ul key={`ds-${i}`} className={cn("list-disc pl-5", i === 0 ? "m-0" : "mt-3 mb-0")}>
              {doan.muc.map((muc, j) => (
                <li key={`${j}-${muc.slice(0, 24)}`} className={j === 0 ? "" : "mt-1"}>
                  {muc}
                </li>
              ))}
            </ul>
          ) : (
            <p key={`d-${i}`} className={i === 0 ? "m-0" : "mt-3 mb-0"}>
              {doan.chu}
            </p>
          ),
        )}
      </>
    );
  }

  // `gioi_thieu` KHÔNG mượn `KhayTrungTinh`. Khay đó nói "hệ thống không trả
  // lời được" — dùng nó ở đây là vẫn đóng khung một câu trả lời hợp lệ như một
  // lời từ chối, tức vẫn phạm đúng lỗi vừa sửa ở backend, chỉ dịch xuống một
  // tầng. Đây là câu trả lời, nên nó trông như câu trả lời.
  if (loai === "gioi_thieu") {
    return (
      <section aria-label="Giới thiệu trợ lý">
        <div className="doc-prose text-foreground">
          <KhoiVanXuoi chu={ketQua.answer ?? ""} />
        </div>
      </section>
    );
  }

  if (loai === "out_of_scope") {
    return (
      <section aria-label="Kết quả tra cứu">
        <KhayTrungTinh tieuDe="Câu hỏi này nằm ngoài phạm vi của hệ thống.">
          {ghiChuPhamVi !== null && ghiChuPhamVi !== "" && (
            <p className="mt-2 mb-0 text-[14px] leading-6 text-muted-foreground">{ghiChuPhamVi}</p>
          )}
        </KhayTrungTinh>
        <div className="mt-4 text-[14px] leading-6 text-foreground">
          <p className="m-0">
            Hệ thống phủ <strong className="font-semibold">6 Bộ luật</strong>:{" "}
            {SAU_BO_LUAT.join(", ")} — cùng cụm văn bản dưới luật về Lao động.
          </p>
          <p className="mt-2 mb-0 text-muted-foreground">
            Không phủ: {KHONG_PHU.join(", ")}. Chiều sâu cũng không đều giữa các lĩnh vực: chỉ riêng
            Lao động có đủ luật, nghị định, thông tư và chế tài.
          </p>
        </div>
        <KhoiCanhBao warnings={warnings} />
      </section>
    );
  }

  if (loai === "partial_coverage") {
    return (
      <section aria-label="Kết quả tra cứu">
        <div
          className="rounded-xl border-l-2 bg-[var(--color-paper-50)] py-3 pr-4 pl-4"
          style={{ borderLeftColor: "var(--color-status-partial)" }}
        >
          <p className="m-0 flex items-start gap-2 text-[14px] leading-6 text-muted-foreground">
            <Info
              className="mt-0.5 size-4 shrink-0"
              style={{ color: "var(--color-status-partial)" }}
              aria-hidden
            />
            <span>
              Chỉ tìm được văn bản liên quan, chưa đủ căn cứ để diễn giải thành câu trả lời. Hệ
              thống KHÔNG diễn giải trong trường hợp này — văn bản gốc được nêu đích danh dưới đây
              để bạn tự đối chiếu.
            </span>
          </p>
          {ghiChuPhamVi !== null && ghiChuPhamVi !== "" && (
            <p className="doc-prose mt-2 mb-0 text-foreground">{ghiChuPhamVi}</p>
          )}
        </div>
        <KhoiCanhBao warnings={warnings} />
        <KhoiNguon nguon={nguon} {...(onMoVanBan ? { onMoVanBan } : {})} />
        {/* Backend hiện luôn trả citations rỗng ở nhánh này, nên dải tự ẩn. Giữ
            lời gọi để ngày endpoint kèm trích dẫn thì màn hình có sẵn chỗ —
            KHÔNG dựng liên kết giả từ chuỗi coverage_note. */}
        <DaiTrichDan citations={citations} chiSoDangMo={chiSoDangMo} onChon={chon} />
      </section>
    );
  }

  return (
    <section aria-label="Kết quả tra cứu">
      <div className="doc-prose text-foreground">
        {answer === null || answer.trim() === "" ? (
          <p className="m-0 flex items-start gap-2 text-muted-foreground">
            <FileSearch className="mt-1 size-4 shrink-0" aria-hidden />
            <span>
              Máy chủ trả về trạng thái có căn cứ nhưng không kèm nội dung câu trả lời. Đọc nguyên
              văn các trích dẫn bên dưới.
            </span>
          </p>
        ) : (
          <KhoiVanXuoi chu={answer} />
        )}
      </div>
      <KhoiCanhBao warnings={warnings} />
      <DaiTrichDan citations={citations} chiSoDangMo={chiSoDangMo} onChon={chon} />
      <NhacMienTru />
    </section>
  );
}
