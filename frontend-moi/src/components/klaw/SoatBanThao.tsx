import { useCallback, useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { CheckCircle2, HelpCircle, ScanSearch, TriangleAlert } from "lucide-react";
import { goi, HAN_GIO_TRA_CUU } from "@/lib/api";
import { laMau, type BaoCaoSoat, type Mau, type PhatHien, type TruongFact } from "@/lib/klaw";
import { trangThaiSoat } from "@/lib/soat";
import { cn } from "@/lib/utils";
import { useGoiApi } from "@/hooks/use-goi-api";
import { BaoLoi } from "./BaoLoi";
import { MaTruyVet } from "./MaTruyVet";

/**
 * Soát bản thảo với KLAW — `GET /mau/{loai}` + `POST /soat`.
 *
 * ## Ba nhánh, và trang phải phân biệt được cả ba
 *
 * 1. **Đúng quy định** — rule đã chạy và bản thảo qua.
 * 2. **Trái quy định** — rule đã chạy và bản thảo trượt.
 * 3. **`khong_kiem_duoc`** — rule KHÔNG chạy được vì thiếu dữ kiện. Đây
 *    **không phải** một vi phạm, và tô nó như vi phạm là nói với người dùng
 *    rằng văn bản của họ trái luật trong khi máy chỉ thiếu một con số. Nhánh
 *    này mang màu TRUNG TÍNH và nói thẳng ra là chưa kiểm được.
 *
 * ## Danh sách dữ kiện do MÁY CHỦ khai
 *
 * Form dưới đây dựng từ `GET /mau/{loai}`, không viết cứng một trường nào —
 * cùng nguyên tắc với `/bo-loc`. `config/rules.yaml` thêm một rule mới thì form
 * dài thêm mà không ai phải nhớ sửa ở đây, và một trường bị bỏ sót sẽ thành
 * `khong_kiem_duoc` chứ không thành một kết luận sai.
 *
 * Dữ kiện không điền thì KHÔNG gửi. Đoán một giá trị mặc định (vùng lương tối
 * thiểu, có/không điều khoản phạt tiền) là bịa ra dữ kiện rồi nhận về một phán
 * quyết dựa trên chính thứ mình vừa bịa.
 */

type GiaTriFact = string | number | boolean;

interface SoatBanThaoProps {
  /** `hdld` · `noi_quy` · `quyet_dinh_ky_luat`. */
  loaiBackend: string;
  /** Toàn văn bản thảo, lấy từ khung xem trước. Máy chủ đòi tối thiểu 20 ký tự. */
  layToanVan: () => string | null;
  /**
   * Dữ kiện suy được CHẮC CHẮN từ biểu mẫu. Chỉ những khoá ánh xạ một–một;
   * khoá mơ hồ để trống cho người dùng chọn.
   */
  factTuBieuMau?: Record<string, GiaTriFact>;
}

const MUC_DO_NANG = new Set(["chan", "cao", "nghiem_trong"]);

function OFact({
  truong,
  giaTri,
  onDoi,
}: {
  truong: TruongFact;
  giaTri: GiaTriFact | undefined;
  onDoi: (gia: GiaTriFact | undefined) => void;
}) {
  const id = `fact-${truong.key}`;

  if (truong.kieu === "bool") {
    return (
      <label htmlFor={id} className="flex items-start gap-2 text-[13px] text-foreground">
        <input
          id={id}
          type="checkbox"
          // `indeterminate` thật: chưa trả lời KHÁC "trả lời là không". Ô chưa
          // đụng tới sẽ không gửi gì, và rule tương ứng về `khong_kiem_duoc`.
          ref={(o) => {
            if (o !== null) o.indeterminate = giaTri === undefined;
          }}
          checked={giaTri === true}
          onChange={(su) => onDoi(su.target.checked)}
          className="mt-0.5 size-4 accent-[var(--color-brass-500)]"
        />
        <span>
          {truong.nhan}
          {giaTri === undefined && (
            <span className="block text-[12px] text-muted-foreground">Chưa trả lời</span>
          )}
        </span>
      </label>
    );
  }

  if (truong.lua_chon !== null && truong.lua_chon.length > 0) {
    return (
      <label htmlFor={id} className="block text-[13px] text-muted-foreground">
        {truong.nhan}
        <select
          id={id}
          value={typeof giaTri === "string" ? giaTri : ""}
          onChange={(su) => onDoi(su.target.value === "" ? undefined : su.target.value)}
          className="focus-brass mt-1 h-11 w-full rounded-lg border border-input bg-card px-2 text-[14px] text-foreground outline-none"
        >
          <option value="">— chưa chọn —</option>
          {/* Giá trị NGUYÊN VĂN của `config/rules.yaml`. Không dịch lại thành
              nhãn đẹp: một bản dịch ở FE sẽ trôi khỏi bản gốc, và lúc đó người
              dùng chọn một thứ còn máy chủ kiểm một thứ khác. */}
          {truong.lua_chon.map((chon) => (
            <option key={chon} value={chon}>
              {chon}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <label htmlFor={id} className="block text-[13px] text-muted-foreground">
      {truong.nhan}
      <input
        id={id}
        type={truong.kieu === "int" ? "number" : "text"}
        value={giaTri === undefined ? "" : String(giaTri)}
        onChange={(su) => {
          const tho = su.target.value;
          if (tho === "") {
            onDoi(undefined);
            return;
          }
          onDoi(truong.kieu === "int" ? Number(tho) : tho);
        }}
        className="focus-brass mt-1 h-11 w-full rounded-lg border border-input bg-card px-2 text-[14px] text-foreground outline-none"
      />
    </label>
  );
}

function DongPhatHien({ phatHien }: { phatHien: PhatHien }) {
  const chuaKiem = phatHien.khong_kiem_duoc;
  const nang = !chuaKiem && MUC_DO_NANG.has(phatHien.muc_do);
  const mau = chuaKiem
    ? "var(--color-status-neutral)"
    : nang
      ? "var(--color-status-expired)"
      : "var(--color-status-partial)";
  const Icon = chuaKiem ? HelpCircle : TriangleAlert;

  // Mở được nguyên văn khi máy chủ giao ĐỦ hai khoá. `citation_khong_hop_le`
  // để cả hai là null — chính căn cứ đó không tồn tại, nên không có gì để mở.
  const docId = phatHien.doc_id;
  const khopTaiId = phatHien.khop_tai_id;

  return (
    <li
      className="rounded-lg border-l-2 bg-[var(--color-paper-50)] py-2.5 pr-3 pl-3"
      style={{ borderLeftColor: mau }}
    >
      <p className="m-0 flex items-start gap-2 text-[14px] leading-6 text-foreground">
        <Icon className="mt-1 size-4 shrink-0" style={{ color: mau }} aria-hidden />
        <span>
          {chuaKiem && (
            // Nói ra TRƯỚC nội dung: một dòng bắt đầu bằng "Thiếu…" mà không có
            // câu này sẽ bị đọc thành một lỗi của bản thảo.
            <strong className="font-semibold">Chưa kiểm được — không phải vi phạm. </strong>
          )}
          {phatHien.thong_diep}
        </span>
      </p>
      {phatHien.can_cu !== null && (
        <p className="font-jetbrains m-0 mt-1 text-[11px] text-muted-foreground">
          Căn cứ: {phatHien.can_cu}
        </p>
      )}
      {docId !== null && khopTaiId !== null && (
        <Link
          to="/tra-cuu/$docId"
          params={{ docId }}
          // `khop_tai_id`, KHÔNG `provision_id` — cùng lý do với trích dẫn của
          // `/tra-cuu`. `PhatHien` thậm chí không mang `provision_id`.
          search={{ quanh: String(khopTaiId) }}
          className="focus-brass mt-1.5 inline-block rounded text-[12px] font-medium text-[var(--color-brass-600)] hover:underline"
        >
          Mở nguyên văn điều luật
        </Link>
      )}
    </li>
  );
}

function KetQuaSoat({ baoCao }: { baoCao: BaoCaoSoat }) {
  const chuaKiem = baoCao.findings.filter((mot) => mot.khong_kiem_duoc);
  const thatSu = baoCao.findings.filter((mot) => !mot.khong_kiem_duoc);

  // Ba trạng thái, ba hình dạng. Xem `lib/soat.ts`: `dat` một mình không đủ,
  // vì nó im lặng về số rule đã KHÔNG chạy được.
  const trangThai = trangThaiSoat(baoCao.dat, chuaKiem.length);

  const MAU_KHAY = {
    dat: "var(--color-status-active)",
    dat_mot_phan: "var(--color-status-neutral)",
    khong_dat: "var(--color-status-expired)",
  } as const;

  const TIEU_DE = {
    dat: "Bản thảo qua toàn bộ rule của KLAW.",
    // KHÔNG viết "qua toàn bộ rule đã kiểm được" rồi thôi: mệnh đề phụ đó đúng
    // về mặt chữ nghĩa nhưng đọc lướt vẫn ra "đạt". Phải nói ra con số.
    dat_mot_phan: `Không thấy vi phạm trong phần soát được — còn ${chuaKiem.length} rule CHƯA kiểm được.`,
    khong_dat: `${thatSu.length} điểm cần sửa trước khi ký.`,
  } as const;

  return (
    <div className="mt-4">
      <div
        className="flex items-start gap-2 rounded-lg border-l-2 bg-[var(--color-paper-50)] p-3"
        style={{ borderLeftColor: MAU_KHAY[trangThai] }}
      >
        {trangThai === "dat" ? (
          <CheckCircle2
            className="mt-0.5 size-4 shrink-0"
            style={{ color: MAU_KHAY.dat }}
            aria-hidden
          />
        ) : trangThai === "dat_mot_phan" ? (
          // Dấu hỏi, KHÔNG dấu tích và KHÔNG tam giác cảnh báo: bản thảo chưa
          // được tuyên là sạch, mà cũng chưa bị phát hiện sai điều gì.
          <HelpCircle
            className="mt-0.5 size-4 shrink-0"
            style={{ color: MAU_KHAY.dat_mot_phan }}
            aria-hidden
          />
        ) : (
          <TriangleAlert
            className="mt-0.5 size-4 shrink-0"
            style={{ color: MAU_KHAY.khong_dat }}
            aria-hidden
          />
        )}
        <div>
          <p className="m-0 text-[14px] leading-6 font-medium text-foreground">
            {TIEU_DE[trangThai]}
          </p>
          <p className="m-0 mt-1 text-[12px] leading-5 text-muted-foreground">
            Máy chủ đọc được {baoCao.so_dieu_khoan} điều khoản trong bản thảo · độ đầy đủ so với
            checklist: {Math.round(baoCao.completeness * 100)}%
          </p>
          {trangThai === "dat_mot_phan" && (
            <p className="m-0 mt-1 text-[12px] leading-5 text-muted-foreground">
              Độ đầy đủ nói bản thảo có đủ các nội dung bắt buộc hay không. Nó KHÔNG nói những rule
              dưới đây đã chạy — điền nốt dữ kiện chúng cần rồi soát lại.
            </p>
          )}
        </div>
      </div>

      {thatSu.length > 0 && (
        <ul className="mt-3 flex list-none flex-col gap-2 p-0">
          {thatSu.map((mot, i) => (
            <DongPhatHien
              key={`${mot.loai}-${mot.rule_id ?? i}-${mot.thong_diep.slice(0, 24)}`}
              phatHien={mot}
            />
          ))}
        </ul>
      )}

      {chuaKiem.length > 0 && (
        <div className="mt-4">
          <h4 className="m-0 text-[13px] leading-5 text-muted-foreground">
            Chưa kiểm được — điền thêm dữ kiện ở trên rồi soát lại
          </h4>
          <ul className="mt-2 flex list-none flex-col gap-2 p-0">
            {chuaKiem.map((mot, i) => (
              <DongPhatHien
                key={`ck-${mot.rule_id ?? i}-${mot.thong_diep.slice(0, 24)}`}
                phatHien={mot}
              />
            ))}
          </ul>
        </div>
      )}

      <p className="mt-4 mb-0 text-[12px] leading-5 text-muted-foreground">
        Bộ soát chỉ kiểm những rule đã được dựng cho loại văn bản này. Qua hết rule KHÔNG có nghĩa
        là bản thảo hợp pháp toàn diện — nó có nghĩa là không rule nào trong số đã kiểm bị vi phạm.
      </p>
    </div>
  );
}

export function SoatBanThao({ loaiBackend, layToanVan, factTuBieuMau = {} }: SoatBanThaoProps) {
  const [mau, datMau] = useState<Mau | null>(null);
  const [fact, datFact] = useState<Record<string, GiaTriFact>>({});
  const goiSoat = useGoiApi<{ audit_report: BaoCaoSoat; trace_id: string }>();
  const { chay } = goiSoat;

  useEffect(() => {
    const dieuKhien = new AbortController();
    void goi(`/mau/${encodeURIComponent(loaiBackend)}`, laMau, {
      signal: dieuKhien.signal,
    }).then((kq) => {
      if (kq.ok) datMau(kq.data);
    });
    return () => dieuKhien.abort();
  }, [loaiBackend]);

  // Điền sẵn từ biểu mẫu, nhưng KHÔNG đè lên thứ người dùng đã tự sửa.
  useEffect(() => {
    datFact((truoc) => {
      const gop = { ...truoc };
      for (const [khoa, gia] of Object.entries(factTuBieuMau)) {
        if (!(khoa in gop)) gop[khoa] = gia;
      }
      return gop;
    });
    // `factTuBieuMau` là một object mới ở mỗi lần dựng lại; khoá theo NỘI DUNG.
  }, [JSON.stringify(factTuBieuMau)]); // eslint-disable-line react-hooks/exhaustive-deps

  const soat = useCallback(() => {
    const toanVan = layToanVan();
    if (toanVan === null || toanVan.trim().length < 20) return;
    void chay((signal) =>
      goi(
        "/soat",
        (x): x is { audit_report: BaoCaoSoat; trace_id: string } =>
          typeof x === "object" &&
          x !== null &&
          Array.isArray((x as { audit_report?: { findings?: unknown } }).audit_report?.findings),
        {
          signal,
          method: "POST",
          hanGioMs: HAN_GIO_TRA_CUU,
          body: { loai_van_ban: loaiBackend, text: toanVan, facts: fact },
        },
      ),
    );
  }, [chay, fact, layToanVan, loaiBackend]);

  const thieu = (mau?.facts ?? []).filter((truong) => truong.bat_buoc && !(truong.key in fact));

  return (
    <section aria-label="Soát bản thảo với KLAW" className="rounded-xl border border-border p-4">
      <h3 className="font-display m-0 flex items-center gap-2 text-[15px] font-semibold text-primary">
        <ScanSearch className="size-4 text-[var(--color-brass-600)]" aria-hidden />
        Soát với kho văn bản của KLAW
      </h3>
      <p className="m-0 mt-1 text-[12px] leading-5 text-muted-foreground">
        Gửi toàn văn bản thảo lên máy chủ để đối chiếu với rule và checklist dựng từ chính văn bản
        gốc trong kho. Bản thảo KHÔNG được lưu lại.
      </p>

      {mau === null ? (
        <p className="mt-3 mb-0 text-[13px] text-muted-foreground">Đang lấy danh sách dữ kiện…</p>
      ) : mau.facts.length === 0 ? (
        // `/mau/noi_quy` trả `facts: []` — kiểu văn bản có tồn tại nhưng chưa có
        // rule nào. Nói đúng điều đó thay vì hiện một form trống.
        <p className="mt-3 mb-0 text-[13px] leading-5 text-muted-foreground">
          KLAW chưa dựng rule hay checklist nào cho loại văn bản này, nên chưa soát được. Bản thảo
          vẫn soạn và xuất tệp bình thường.
        </p>
      ) : (
        <>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {mau.facts.map((truong) => (
              <OFact
                key={truong.key}
                truong={truong}
                giaTri={fact[truong.key]}
                onDoi={(gia) =>
                  datFact((truoc) => {
                    const moi = { ...truoc };
                    if (gia === undefined) delete moi[truong.key];
                    else moi[truong.key] = gia;
                    return moi;
                  })
                }
              />
            ))}
          </div>

          {thieu.length > 0 && (
            <p className="mt-3 mb-0 text-[12px] leading-5 text-muted-foreground">
              Còn {thieu.length} dữ kiện chưa điền. Vẫn soát được — rule cần chúng sẽ báo là{" "}
              <strong className="font-medium">chưa kiểm được</strong>, không báo là vi phạm.
            </p>
          )}

          <button
            type="button"
            onClick={soat}
            disabled={goiSoat.dangChay}
            className="focus-brass mt-3 inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-50"
          >
            <ScanSearch className="size-4" aria-hidden />
            {goiSoat.dangChay ? "Đang soát…" : "Soát bản thảo"}
          </button>

          {goiSoat.loi !== null && <BaoLoi loi={goiSoat.loi} onThuLai={soat} />}
          {goiSoat.ketQua !== null && <KetQuaSoat baoCao={goiSoat.ketQua.audit_report} />}
          {goiSoat.ketQua !== null && (
            <p className="mt-3 mb-0 text-[12px] text-muted-foreground">
              <MaTruyVet traceId={goiSoat.ketQua.trace_id} />
            </p>
          )}
        </>
      )}
    </section>
  );
}
