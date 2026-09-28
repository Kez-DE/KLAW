/**
 * Thẻ kết quả cho `result_type === "tai_lieu"` — lượt nói về TÀI LIỆU của
 * người hỏi, không về kho luật.
 *
 * Quy tắc trình bày duy nhất không thương lượng của thẻ này: **quan sát và suy
 * luận không bao giờ đứng chung một khối.** Quan sát là điều tài liệu viết, đã
 * dò được nguyên văn, bấm vào là mở đúng chỗ đó. Suy luận là cách KLAW đọc chỗ
 * đó — có thể sai, và không có gì trong tệp chứng minh nó. Trộn hai thứ lại là
 * cho phần đoán mượn uy tín của phần đọc được, đúng lỗi mà `KhungDoiChieu` tồn
 * tại để không mắc với trích dẫn điều luật (`CONTEXT.md`, `docs/bo-luat-agent.md`).
 *
 * Thẻ KHÔNG kết luận tài liệu đúng hay sai luật: việc đó thuộc nhánh đối chiếu
 * luật, và cả ở đó câu trả lời cũng chỉ nói luật đòi gì và khác ở đâu (QT-1).
 */
import { useState } from "react";
import { FileText, Sigma, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import type { NeoTaiLieu, TaiLieuDaDung, TraCuuKetQua } from "@/lib/klaw";
import { canhBaoOcr, nhanNeo, type DuKien } from "@/lib/tai-lieu";
import { suaDuKien, xoaDuKien } from "@/lib/tai-lieu-api";
import { cn } from "@/lib/utils";
import { BangDuKien } from "./DongDuKien";
import { KhoiVanXuoi } from "./TheKetQua";

/** Cắt đoạn trích cho vừa một con chip. Chip là để NHẬN RA chỗ cần mở, không
 *  phải để đọc thay nội dung — bản đầy đủ nằm trong khung tài liệu. */
const DAI_TRICH = 80;
function catTrich(chu: string): string {
  const gon = chu.trim().replace(/\s+/g, " ");
  return gon.length <= DAI_TRICH ? gon : `${gon.slice(0, DAI_TRICH - 1)}…`;
}

const CHIP =
  "focus-brass inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-[13px] text-foreground hover:bg-[var(--color-paper-100)]";

/**
 * Con chip mở đúng đơn vị văn bản mà một câu nói dựa vào.
 *
 * Chữ trên chip là VỊ TRÍ trên tờ giấy ("tr. 1 · bảng 1, h5 c2"), không phải số
 * thứ tự nội bộ: người dùng còn phải tìm lại chỗ đó bằng mắt trên bản gốc.
 * Neo đọc bằng OCR mang thêm biểu tượng + chữ "máy đọc" khi độ tin thấp — màu
 * một mình không tới được người không phân biệt được màu.
 */
export function ChipNeo({
  neo,
  onMo,
  them,
  tenTep,
}: {
  neo: NeoTaiLieu;
  onMo?: ((taiLieuId: string, chiSo: number) => void) | undefined;
  /** Chữ phụ sau nhãn vị trí, ví dụ đoạn trích đã cắt. */
  them?: string | undefined;
  /**
   * Tên tệp, đưa vào TÊN TRUY CẬP khi lượt dùng nhiều hơn một tài liệu.
   *
   * Mắt phân biệt hai chip bằng cột chúng đứng; trình đọc màn hình thì không —
   * không có tên tệp, cả hai chip của một dòng khác biệt đọc lên y hệt nhau và
   * người dùng bấm mở nhầm tờ giấy.
   */
  tenTep?: string | undefined;
}) {
  const nhan = nhanNeo(neo);
  const canh = canhBaoOcr(neo.nguon_chu === "ocr", neo.do_tin);
  const noiDung = (
    <>
      {canh !== null && <TriangleAlert aria-hidden className="size-3.5 shrink-0" />}
      <span className="font-jetbrains text-[12px] whitespace-nowrap">{nhan}</span>
      {them !== undefined && them !== "" && (
        <span className="min-w-0 truncate text-muted-foreground">“{them}”</span>
      )}
      {canh !== null && <span className="text-[11px] whitespace-nowrap">máy đọc, chưa chắc</span>}
    </>
  );
  if (onMo === undefined) {
    return (
      <span className={cn(CHIP, "cursor-default")} title={canh ?? undefined}>
        {noiDung}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onMo(neo.tai_lieu_id, neo.chi_so_don_vi)}
      title={canh ?? undefined}
      aria-label={`Mở ${nhan} trong tài liệu${tenTep === undefined ? "" : ` ${tenTep}`}${canh === null ? "" : " — máy đọc từ ảnh, chưa chắc chắn"}`}
      className={cn(CHIP, "max-w-full", canh !== null && "text-[var(--color-status-warn,#9a6b00)]")}
    >
      {noiDung}
    </button>
  );
}

/**
 * Dải "Điều khoản trong tài liệu" dưới một câu trả lời PHÁP LÝ.
 *
 * Nhánh đối chiếu luật giữ nguyên `answer`/`partial_coverage`/`abstain`, nên
 * dải này đứng riêng dưới văn xuôi và mang nhãn nói rõ đây là điều khoản của
 * người hỏi — DỮ KIỆN, không phải căn cứ. Đặt chúng vào dải trích dẫn điều
 * luật sẽ là hứa cho tờ giấy của họ đúng thứ bảo đảm chỉ kho luật mới có.
 */
export function KhoiNeoTaiLieu({
  neo,
  onMoNeoTaiLieu,
}: {
  neo: NeoTaiLieu[];
  onMoNeoTaiLieu?: ((taiLieuId: string, chiSo: number) => void) | undefined;
}) {
  if (neo.length === 0) return null;
  return (
    <section aria-label="Điều khoản trong tài liệu" className="mt-4">
      <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
        Điều khoản trong tài liệu của bạn mà lượt này đã đọc
      </h3>
      <ul className="mt-2 mb-0 flex list-none flex-wrap gap-2 p-0">
        {neo.map((n, i) => (
          <li key={`${n.tai_lieu_id}-${n.chi_so_don_vi}-${i}`} className="max-w-full">
            <ChipNeo
              neo={n}
              onMo={onMoNeoTaiLieu}
              {...(n.trich ? { them: catTrich(n.trich) } : {})}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Ba câu hỏi tiếp theo hay gặp nhất sau khi máy đã đọc xong một tài liệu. */
const HANH_DONG = [
  "Đối chiếu luật với tài liệu này",
  "Trích dữ kiện từ tài liệu này",
  "Tạo văn bản mới từ nội dung này",
];

/**
 * Nhãn cột của một bên trong bảng khác biệt: "A · phieu.docx".
 *
 * Tra theo `tai_lieu_id` của chính cái neo chứ không theo thứ tự trong mảng:
 * backend đánh nhãn "A"/"B" ở `tai_lieu_da_dung`, và một dòng khác biệt hoàn
 * toàn có thể đặt tài liệu B ở vế trái. Cột mang tên tệp SAI là cách nhanh
 * nhất để người đọc sửa nhầm tờ giấy.
 */
function nhanBen(ds: TaiLieuDaDung[], neo: NeoTaiLieu, macDinh: string): string {
  const tl = ds.find((t) => t.id === neo.tai_lieu_id);
  return tl ? `${tl.nhan || macDinh} · ${tl.ten_tep}` : macDinh;
}

export function TheTaiLieu({
  ketQua,
  onChip,
  onMoNeoTaiLieu,
  onHanhDongTaiLieu,
  onMoTaiLieu,
}: {
  ketQua: TraCuuKetQua;
  /** Điền một câu vào ô hỏi. KHÔNG tự gửi — người hỏi còn sửa câu. */
  onChip?: ((chu: string) => void) | undefined;
  onMoNeoTaiLieu?: ((taiLieuId: string, chiSo: number) => void) | undefined;
  /**
   * Điền câu hỏi VÀ đính kèm lại đúng những tài liệu này cho lượt kế tiếp.
   *
   * Nhận cả danh sách chứ không chỉ `id`: nơi gọi phải vẽ được con chip đính
   * kèm với TÊN TỆP, và chỉ thẻ này biết tên đó. Một chip "tài liệu đính kèm"
   * chung chung không nói được người dùng sắp hỏi về tờ giấy nào.
   */
  onHanhDongTaiLieu?: ((cauHoi: string, taiLieu: TaiLieuDaDung[]) => void) | undefined;
  /** Mở chính tài liệu này (bản thảo mới nhất của nó, không thì bản tải lên).
   *  Không có thì dòng tài liệu là chữ thường. */
  onMoTaiLieu?: ((taiLieu: TaiLieuDaDung) => void) | undefined;
}) {
  /**
   * Sửa/xoá của NGƯỜI DÙNG chồng lên `du_kien` của lượt, khoá theo id.
   *
   * Giữ chồng lớp thay vì sao chép cả mảng vào state: `ketQua` là prop, và một
   * bản sao sẽ đứng im khi lượt mới về — người dùng sẽ thấy dữ kiện của lượt
   * TRƯỚC dưới câu trả lời MỚI. `undefined` = chưa đụng tới, `null` = đã xoá.
   */
  const [daSua, datDaSua] = useState<Record<string, DuKien | null>>({});
  const [dangLuu, datDangLuu] = useState<string | null>(null);

  const tl = ketQua.tai_lieu;
  if (!tl) return null;
  const nhieuTaiLieu = tl.tai_lieu_da_dung.length > 1;
  const khacBiet = tl.khac_biet ?? [];

  const duKien = tl.du_kien.flatMap((dk) => {
    if (dk.id === null || !(dk.id in daSua)) return [dk];
    const thay = daSua[dk.id];
    return thay ? [thay] : [];
  });

  const sua = async (dk: DuKien, giaTri: string) => {
    if (dk.id === null || giaTri === dk.gia_tri) return;
    const id = dk.id;
    datDangLuu(id);
    const kq = await suaDuKien(id, giaTri);
    datDangLuu(null);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return;
    }
    // Máy chủ trả bản ghi MỚI (nguồn đổi sang `nguoi_dung_sua`, `trich_goc`
    // giữ đoạn chứng minh giá trị CŨ). Dùng nguyên nó chứ không tự vá giá trị:
    // vá tay sẽ để lại nhãn "Từ tài liệu" trên một con số người dùng vừa gõ.
    datDaSua((truoc) => ({ ...truoc, [id]: kq.data }));
  };

  const xoa = async (dk: DuKien) => {
    if (dk.id === null) return;
    const id = dk.id;
    const kq = await xoaDuKien(id);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return;
    }
    datDaSua((truoc) => ({ ...truoc, [id]: null }));
  };

  /** Bảng dữ kiện — đứng TRƯỚC câu trả lời ở lượt trích dữ kiện, vì ở đó bảng
   *  LÀ câu trả lời và đoạn văn chỉ nói thêm về nó. */
  const khoiDuKien = duKien.length > 0 && (
    <section aria-label="Dữ kiện rút được" className="mt-4">
      <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">Dữ kiện rút được</h3>
      <BangDuKien
        duKien={duKien}
        onSua={(dk, giaTri) => void sua(dk, giaTri)}
        onXoa={(dk) => void xoa(dk)}
        dangSua={dangLuu}
      />
    </section>
  );
  const duKienTruoc = tl.muc_dich === "trich_du_kien";

  /**
   * Tên tệp cho tên truy cập của một chip — CHỈ khi lượt dùng nhiều hơn một
   * tài liệu. Một tài liệu thì tên tệp trong mọi nhãn chỉ là tiếng ồn lặp lại;
   * hai tài liệu thì thiếu nó là hai chip đọc lên y hệt nhau.
   */
  const propTenTep = (neo: NeoTaiLieu): { tenTep?: string } => {
    if (!nhieuTaiLieu) return {};
    const ten = tl.tai_lieu_da_dung.find((t) => t.id === neo.tai_lieu_id)?.ten_tep;
    return ten === undefined ? {} : { tenTep: ten };
  };

  const moTa = tl.mo_ta !== null && tl.mo_ta.trim() !== "" ? tl.mo_ta : null;
  const motTep = nhieuTaiLieu ? undefined : tl.tai_lieu_da_dung[0];
  /** Dòng tài liệu bấm được (chủ dự án 2026-09-28, Q1): mở bản thảo mới nhất
   *  của tệp, không thì bản tải lên. `data-mo-san-khau`: đóng sân khấu ở bố
   *  cục hẹp dựng lại cả cây chat, trang tìm lại ĐÚNG nút này để trả tiêu điểm. */
  const propNutMo = (t: TaiLieuDaDung) => ({
    type: "button" as const,
    onClick: () => onMoTaiLieu?.(t),
    "aria-label": `Mở «${t.ten_tep}»`,
    "data-mo-san-khau": `tai_lieu_dong:${ketQua.trace_id}:${t.id}`,
  });

  return (
    <section aria-label="Kết quả đọc tài liệu">
      {onMoTaiLieu && motTep !== undefined ? (
        <button
          {...propNutMo(motTep)}
          title={motTep.ten_tep}
          className="focus-brass -mx-1 flex min-h-6 max-w-full cursor-pointer items-start gap-2 rounded px-1 text-left text-[13px] leading-5 text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          <FileText aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>{moTa ?? motTep.ten_tep}</span>
        </button>
      ) : (
        moTa !== null && (
          <p className="m-0 flex items-start gap-2 text-[13px] leading-5 text-muted-foreground">
            <FileText aria-hidden className="mt-0.5 size-4 shrink-0" />
            <span>{moTa}</span>
          </p>
        )
      )}

      {/* Nhãn "A"/"B" chỉ có nghĩa khi có hơn một tài liệu để phân biệt. Một
          tài liệu mà vẫn dán nhãn là bắt người đọc giải mã một ký hiệu thừa. */}
      {nhieuTaiLieu && (
        <ul className="mt-2 mb-0 flex list-none flex-wrap gap-2 p-0 text-[12px]">
          {tl.tai_lieu_da_dung.map((t) => {
            const noiDung = (
              <>
                <span className="font-jetbrains">{t.nhan}</span>
                <span className="truncate text-muted-foreground">{t.ten_tep}</span>
              </>
            );
            const vo =
              "inline-flex max-w-full items-center gap-1.5 rounded-full bg-muted px-2.5 py-0.5";
            return onMoTaiLieu ? (
              <li key={t.id} className="max-w-full">
                <button
                  {...propNutMo(t)}
                  className={cn(
                    vo,
                    "focus-brass cursor-pointer hover:bg-[var(--color-paper-100)] hover:underline",
                  )}
                >
                  {noiDung}
                </button>
              </li>
            ) : (
              <li key={t.id} className={vo}>
                {noiDung}
              </li>
            );
          })}
        </ul>
      )}

      {duKienTruoc && khoiDuKien}

      {ketQua.answer !== null && ketQua.answer.trim() !== "" && (
        <div className="doc-prose mt-3 text-foreground">
          <KhoiVanXuoi chu={ketQua.answer} />
        </div>
      )}

      {/* Khác biệt đứng NGAY dưới câu trả lời của một lượt so sánh: nó là thứ
          người hỏi đính kèm tờ thứ hai để xem. Hai cột, mỗi cột mang tên tệp
          của chính nó và một chip mở đúng chỗ — một câu "bên A dài hơn" mà
          không mở được cả hai chỗ thì không kiểm được, nên nó không được phép
          trông giống một quan sát đã neo. */}
      {khacBiet.length > 0 && (
        <section aria-label="Hai tài liệu khác nhau ở đâu" className="mt-4">
          <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
            Hai tài liệu khác nhau ở đâu
          </h3>
          <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">
            {khacBiet.map((kb, i) => (
              <li
                key={`${kb.neo_a.tai_lieu_id}-${kb.neo_a.chi_so_don_vi}-${kb.neo_b.chi_so_don_vi}-${i}`}
                className="rounded-lg border border-border bg-card p-3"
              >
                <p className="m-0 text-[14px] leading-6 text-foreground">{kb.noi_dung}</p>
                {/* `dl` chứ không phải hai `div`: cặp "tên tệp → chỗ trong tệp"
                    là quan hệ thuật ngữ–mô tả, và trình đọc màn hình phải đọc
                    ra được chip nào thuộc tờ nào. Điện thoại thì hai cột xếp
                    chồng — đọc dọc vẫn đúng cặp. */}
                <dl className="mt-2 mb-0 grid gap-2 sm:grid-cols-2">
                  {(
                    [
                      [kb.neo_a, "A"],
                      [kb.neo_b, "B"],
                    ] as const
                  ).map(([neo, macDinh]) => {
                    const nhan = nhanBen(tl.tai_lieu_da_dung, neo, macDinh);
                    return (
                      <div key={macDinh} className="min-w-0">
                        <dt className="truncate text-[12px] text-muted-foreground" title={nhan}>
                          {nhan}
                        </dt>
                        <dd className="mt-1 ml-0">
                          <ChipNeo
                            neo={neo}
                            onMo={onMoNeoTaiLieu}
                            {...propTenTep(neo)}
                            {...(neo.trich ? { them: catTrich(neo.trich) } : {})}
                          />
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tl.quan_sat.length > 0 && (
        <section aria-label="Tài liệu viết gì" className="mt-4">
          <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">Tài liệu viết</h3>
          <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">
            {tl.quan_sat.map((qs, i) => (
              <li
                key={`${qs.neo.tai_lieu_id}-${qs.neo.chi_so_don_vi}-${i}`}
                className="rounded-lg border border-border bg-card p-3"
              >
                <p className="m-0 text-[14px] leading-6 text-foreground">{qs.noi_dung}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <ChipNeo
                    neo={qs.neo}
                    onMo={onMoNeoTaiLieu}
                    them={catTrich(qs.trich)}
                    {...propTenTep(qs.neo)}
                  />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Phép tính do CODE chạy. Khi lệch, hiện CẢ HAI con số: chọn hộ một con
          số rồi tuyên bố nó đúng là việc của người đọc tài liệu, không phải của
          một máy vừa cộng bốn ô bảng. */}
      {tl.phep_tinh.length > 0 && (
        <section aria-label="Phép tính đã kiểm" className="mt-4">
          <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
            Phép tính KLAW tự chạy lại
          </h3>
          <ul className="mt-2 mb-0 flex list-none flex-col gap-1.5 p-0">
            {tl.phep_tinh.map((pt, i) => (
              <li
                key={`${pt.bieu_thuc}-${i}`}
                className="flex flex-wrap items-start gap-2 font-jetbrains text-[13px] leading-6"
              >
                <Sigma aria-hidden className="mt-1 size-3.5 shrink-0 text-muted-foreground" />
                <span>
                  {pt.bieu_thuc} = {pt.ket_qua_code}{" "}
                  {pt.khop ? (
                    <span className="text-muted-foreground">(khớp)</span>
                  ) : (
                    <span style={{ color: "var(--color-status-warn, #9a6b00)" }}>
                      (lệch: tài liệu ghi {pt.ket_qua_tai_lieu})
                    </span>
                  )}
                </span>
                {/* Chip CHỈ khi backend gửi neo. Một phép tính lệch là lúc người
                    dùng cần mở tài liệu nhất, nhưng một chip đoán chỗ còn tệ
                    hơn không có chip: nó mời họ tin một vị trí chưa ai dò. */}
                {pt.neo && <ChipNeo neo={pt.neo} onMo={onMoNeoTaiLieu} {...propTenTep(pt.neo)} />}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Khối suy luận đứng TÁCH hẳn và mang tên người nói. Đây là chỗ duy nhất
          trong thẻ không có neo nào chống đỡ, nên nó phải tự khai điều đó. */}
      {tl.suy_luan.length > 0 && (
        <section
          aria-label="Suy luận của mô hình"
          className="mt-4 rounded-xl bg-[var(--color-paper-50)] px-4 py-3"
        >
          <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">Suy luận của mô hình</h3>
          <ul className="mt-1.5 mb-0 list-disc pl-5 text-[14px] leading-6 text-muted-foreground">
            {tl.suy_luan.map((s, i) => (
              <li key={`${i}-${s.slice(0, 24)}`}>{s}</li>
            ))}
          </ul>
          <p className="mt-2 mb-0 text-[12px] text-muted-foreground">
            Phần này là cách KLAW đọc tài liệu, không phải chữ trong tài liệu.
          </p>
        </section>
      )}

      {!duKienTruoc && khoiDuKien}

      {tl.can_du_kien.length > 0 && onChip && (
        <section aria-label="Dữ kiện còn thiếu" className="mt-4">
          <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">
            Tài liệu không nói, bạn bổ sung giúp
          </h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {tl.can_du_kien.map((c) => (
              <button key={c} type="button" onClick={() => onChip(`${c}: `)} className={CHIP}>
                {c}
              </button>
            ))}
          </div>
        </section>
      )}

      {(onHanhDongTaiLieu ?? onChip) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {HANH_DONG.map((cau) => (
            <button
              key={cau}
              type="button"
              onClick={() =>
                onHanhDongTaiLieu ? onHanhDongTaiLieu(cau, tl.tai_lieu_da_dung) : onChip?.(cau)
              }
              className={CHIP}
            >
              {cau}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
