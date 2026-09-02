import { nhanHoaFact } from '../../lib/facts';
import type { AuditReport, Finding } from '../../types';
import { DuongDan } from '../DuongDan';

/**
 * Báo cáo tự soát — dùng chung bởi `/soan-thao` (KLAW soát output của chính
 * nó) và `/soat` (soát văn bản người dùng dán vào).
 *
 * `self_audit` do SERVER đặt, không phải client gửi lên. Phân biệt hai chế độ
 * đó là số liệu đánh giá của khoá luận (self-audit catch rate), nên nó được
 * nói thẳng ra chứ không giấu đi.
 *
 * MÀU: `chan` KHÔNG dùng `--do-thay`. Đỏ trong bảng màu này dành riêng cho
 * luật đã bị thay thế (DESIGN.md); mượn nó cho một loại tín hiệu khác thì
 * nhãn đỏ mất nghĩa. Mức độ ở đây mang nghĩa bằng CHỮ ("Chặn"/"Cảnh báo"),
 * màu chỉ nhắc lại — cùng bất biến "không trạng thái nào được truyền đạt chỉ
 * bằng màu".
 */

/**
 * Dấu hiệu một rule KHÔNG ĐƯỢC KIỂM, do `src/services/rules.py` tự ghép vào
 * `chi_tiet` khi `check()` trả `None`.
 *
 * Phân biệt "thiếu dữ liệu" với "văn bản sai" là bất biến của cả dự án
 * (`check() -> bool | None`), nhưng `FindingOut` không mang cờ
 * `khong_kiem_duoc` — nó chết ở `services/rules.py`. Nên chỗ này phải đọc lại
 * từ chính câu backend đã cam kết viết ra. Đây là một mối buộc vào chuỗi, có
 * chủ ý và được ghi lại: cách sửa đúng ở tầng dưới là đưa `khong_kiem_duoc`
 * vào `FindingOut` rồi đọc cờ đó thay cho chuỗi này.
 *
 * Không đọc được cờ thì giao diện gắn nhãn "Trái quy định" cho một quy tắc
 * CHƯA HỀ được kiểm — tức nói văn bản sai trong khi máy chỉ đang thiếu dữ
 * liệu. Đó là đúng lời nói dối mà phân biệt `None`/`False` sinh ra để tránh.
 */
const MOC_KHONG_KIEM = ' — không kiểm được: thiếu ';

interface MucDo {
  chu: string;
  mau: string;
  giaiThich: string;
}

function docMucDo(mucDo: string): MucDo {
  switch (mucDo) {
    case 'chan':
      return {
        chu: 'Chặn',
        mau: 'var(--vang-mo)',
        giaiThich: 'Không đạt: phải sửa trước khi dùng văn bản này.',
      };
    case 'canh_bao':
      return {
        chu: 'Cảnh báo',
        mau: 'var(--xam-cho)',
        giaiThich: 'Cần xem lại, không tự động coi là sai.',
      };
    case 'goi_y':
      return { chu: 'Gợi ý', mau: 'var(--xam-cho)', giaiThich: 'Đề xuất cải thiện.' };
    default:
      // Nhãn mới backend thêm sau hiện thành chính chuỗi đó, không làm sập danh sách.
      return { chu: mucDo, mau: 'var(--xam-cho)', giaiThich: '' };
  }
}

/** Chỉ ba loại này có thật trong `draft_audit.py`; loại lạ hiện nguyên chuỗi. */
const TEN_LOAI: Record<string, string | undefined> = {
  thieu_noi_dung: 'Thiếu nội dung bắt buộc',
  trai_luat: 'Trái quy định',
  citation_khong_hop_le: 'Căn cứ không tồn tại',
};

interface DongPhatHienProps {
  phatHien: Finding;
  chiSo: number;
  dangMo: boolean;
  /** `key` → nhãn người đọc được, từ `GET /api/v1/mau/{loai}`. */
  nhanFact: Record<string, string>;
  onChon: (chiSo: number) => void;
}

function DongPhatHien({ phatHien, chiSo, dangMo, nhanFact, onChon }: DongPhatHienProps) {
  const [truocMoc, sauMoc] = phatHien.thong_diep.split(MOC_KHONG_KIEM);
  const canThongTin = sauMoc === undefined ? null : nhanHoaFact(sauMoc, nhanFact);
  const mucDo =
    canThongTin === null
      ? docMucDo(phatHien.muc_do)
      : {
          chu: 'Chưa kiểm được',
          mau: 'var(--xam-cho)',
          giaiThich: 'Máy chưa có đủ thông tin để chạy quy tắc này — KHÔNG phải văn bản sai.',
        };
  // Mở được panel đối chiếu CHỈ khi có đủ hai id. Cả hai null nghĩa là chính
  // căn cứ đó không tồn tại trong CSDL — dựng link ở đó là dựng link hỏng.
  const moDuoc = phatHien.doc_id !== null && phatHien.khop_tai_id !== null;

  const than = (
    <>
      <span className="flex flex-wrap items-center gap-2">
        <span
          className="inline-flex min-h-6 items-center rounded-tron border px-2 py-0.5 text-[0.75rem] leading-5"
          style={{ borderColor: mucDo.mau, color: mucDo.mau }}
        >
          {mucDo.chu}
        </span>
        <span className="text-[0.75rem] leading-5 text-muc-nhat">
          {canThongTin === null ? (TEN_LOAI[phatHien.loai] ?? phatHien.loai) : 'Cần thông tin'}
        </span>
      </span>
      <span className="mat-doc mt-2 block text-[0.9375rem] text-phim">
        {canThongTin === null ? nhanHoaFact(phatHien.thong_diep, nhanFact) : truocMoc}
      </span>
      {canThongTin !== null && (
        <span className="mt-1 block text-[0.8125rem] leading-5 text-muc-nhat">
          {/* Câu này hiện ở CẢ /soan-thao lẫn /soat, nên không được nêu tên một
              khối chỉ tồn tại ở một trong hai màn hình. */}
          Cần thông tin: {canThongTin}. Điền những ô đó rồi chạy lại để máy kiểm được quy tắc này.
        </span>
      )}
      {phatHien.can_cu !== null && (
        <span className="mt-2 block">
          <DuongDan duongDan={phatHien.can_cu} />
        </span>
      )}
    </>
  );

  return (
    <li
      className="rounded-vua border-s-2 py-3 ps-3"
      style={{ borderColor: mucDo.mau, background: 'var(--nen-cao)' }}
    >
      {moDuoc ? (
        <button
          type="button"
          data-khung={chiSo}
          aria-expanded={dangMo}
          onClick={() => onChon(chiSo)}
          className="block w-full cursor-pointer rounded-vua p-1 text-start transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
          {than}
          <span className="mt-2 block text-[0.75rem] leading-5" style={{ color: 'var(--den-sang)' }}>
            {dangMo ? 'Đang mở nguyên văn căn cứ' : 'Mở nguyên văn căn cứ'}
          </span>
        </button>
      ) : (
        <div className="p-1">
          {than}
          <p className="mt-2 mb-0 text-[0.75rem] leading-5 text-muc-nhat">
            {phatHien.loai === 'citation_khong_hop_le'
              ? 'Không mở được nguyên văn: chính căn cứ được dẫn không tồn tại trong cơ sở dữ liệu.'
              : 'Không mở được nguyên văn: phát hiện này không kèm định danh điều khoản.'}
          </p>
        </div>
      )}

      {phatHien.dieu_khoan_lien_quan !== null && (
        <p className="mt-2 mb-0 ps-1 text-[0.8125rem] leading-5 text-muc-nhat">
          Trích đoạn điều khoản trong văn bản đang soát: “{phatHien.dieu_khoan_lien_quan}”
        </p>
      )}
    </li>
  );
}

interface BaoCaoSoatProps {
  baoCao: AuditReport;
  /** Chỉ số phát hiện đang mở panel đối chiếu, hoặc null. */
  chiSoDangMo: number | null;
  /** `key` → nhãn, từ mẫu `/mau/{loai}`. Rỗng khi mẫu chưa về: thông điệp giữ
   *  nguyên tên máy thay vì hiện một nhãn đoán bừa. */
  nhanFact: Record<string, string>;
  onChonPhatHien: (chiSo: number) => void;
}

export function BaoCaoSoat({ baoCao, chiSoDangMo, nhanFact, onChonPhatHien }: BaoCaoSoatProps) {
  const tyLe = Math.round(baoCao.completeness * 100);

  return (
    <section aria-label="Báo cáo soát">
      <div
        className="rounded-lon border-s-2 py-3 ps-4"
        style={{
          borderColor: baoCao.dat ? 'var(--xanh-that)' : 'var(--vang-mo)',
          background: 'var(--nen-cao)',
        }}
      >
        <h2 className="m-0 text-[1rem] leading-6 font-medium text-phim">
          {baoCao.dat ? 'Đạt' : 'Chưa đạt'}
        </h2>
        <p className="mt-2 mb-0 text-[0.875rem] leading-6 text-muc-nhat">
          Đủ {tyLe}% nội dung bắt buộc · {baoCao.so_dieu_khoan} điều khoản đọc được ·{' '}
          {baoCao.findings.length} phát hiện
        </p>
        <p className="mt-2 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
          {baoCao.self_audit
            ? 'Tự soát: KLAW đang soát chính văn bản mình vừa sinh ra. Cùng bộ quy tắc dùng cho văn bản bên ngoài, không nới lỏng.'
            : 'Soát văn bản bạn cung cấp: KLAW không sinh ra văn bản này.'}
        </p>
        <p className="mt-2 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
          Bốn phép kiểm đều tra bảng, không suy đoán: đủ mục bắt buộc, định dạng, đối chiếu quy
          tắc pháp lý, và căn cứ được dẫn có tồn tại thật hay không.
        </p>
      </div>

      {baoCao.findings.length === 0 ? (
        <p className="mat-doc mt-4 mb-0 text-muc-nhat">
          Không có phát hiện nào. Điều đó không có nghĩa văn bản chắc chắn hợp pháp — chỉ nghĩa là
          bốn phép kiểm trên không tìm thấy vi phạm nào trong phạm vi quy tắc hiện có.
        </p>
      ) : (
        <ul className="mt-4 mb-0 flex list-none flex-col gap-3 p-0">
          {baoCao.findings.map((phatHien, chiSo) => (
            <DongPhatHien
              key={`${phatHien.loai}-${phatHien.rule_id ?? ''}-${chiSo}`}
              phatHien={phatHien}
              chiSo={chiSo}
              dangMo={chiSo === chiSoDangMo}
              nhanFact={nhanFact}
              onChon={onChonPhatHien}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
