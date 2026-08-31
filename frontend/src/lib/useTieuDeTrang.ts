import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Đặt <title>/meta description/og:* theo tuyến, VÀ xử lý phần khả năng tiếp
 * cận mà một SPA không tự làm: reset tiêu điểm bàn phím về <h1> của trang
 * mới, thông báo qua aria-live (site-spec.md, "Vỏ chung mọi trang" +
 * "Khả năng tiếp cận"). Tự viết, không thêm thư viện.
 *
 * Gọi MỘT LẦN ở App.tsx — không gọi lại trong từng trang — vì bảng TUYEN bên
 * dưới phủ cả ba màn hình Operate (Tra cứu/Soạn thảo/Soát) mà file này không
 * được sửa. Tập trung logic ở gốc là cách duy nhất cho TẤT CẢ bảy tuyến có
 * title/meta/focus-reset nhất quán mà không đụng vào các trang thuộc agent
 * khác.
 */

interface MoTaTuyen {
  /** Không kèm hậu tố " — KLAW"; hook tự thêm (trừ "/", đã là tên đầy đủ). */
  tieuDe: string;
  moTa: string;
}

const HAU_TO = ' — KLAW';

const TUYEN: Record<string, MoTaTuyen> = {
  '/': {
    tieuDe: 'KLAW — Tra cứu pháp luật lao động Việt Nam',
    moTa:
      'KLAW tra cứu pháp luật lao động Việt Nam và soạn thảo văn bản pháp lý. Mọi câu trả lời đều neo vào trích dẫn nguyên văn kiểm chứng được, kèm nhãn hiệu lực rõ ràng.',
  },
  '/tra-cuu': {
    tieuDe: 'Tra cứu pháp luật',
    moTa:
      'Hỏi về pháp luật lao động Việt Nam bằng lời thường, nhận câu trả lời kèm trích dẫn nguyên văn kiểm chứng được và nhãn hiệu lực cho từng điều luật.',
  },
  '/soan-thao': {
    tieuDe: 'Soạn thảo văn bản',
    moTa:
      'Soạn hợp đồng lao động, nội quy lao động và quyết định kỷ luật — mỗi điều khoản do hệ thống sinh ra đều kèm căn cứ pháp lý riêng.',
  },
  '/soat': {
    tieuDe: 'Soát văn bản',
    moTa:
      'Dán một văn bản có sẵn để hệ thống rà soát; mỗi phát hiện đều neo vào một điều luật cụ thể, không phải nhận xét chung chung.',
  },
  '/huong-dan': {
    tieuDe: 'Hướng dẫn sử dụng',
    moTa:
      'Cách đặt câu hỏi cho ra kết quả tốt, ý nghĩa của bốn loại kết quả và nhãn hiệu lực, và vì sao một lượt tra cứu mất 10–60 giây.',
  },
  '/pham-vi': {
    tieuDe: 'Phạm vi dữ liệu và giới hạn',
    moTa:
      'Corpus của KLAW gồm sáu Bộ luật và cụm văn bản dưới luật về Lao động — phạm vi thật, độ sâu không đều, và những lĩnh vực chưa được phủ.',
  },
  '/mien-tru': {
    tieuDe: 'Miễn trừ trách nhiệm',
    moTa:
      'KLAW không phải tư vấn pháp lý. Đọc rõ giới hạn của corpus và cách đối chiếu trước khi dựa vào một câu trả lời để hành động.',
  },
};

const MAC_DINH: MoTaTuyen = {
  tieuDe: 'Không tìm thấy trang',
  moTa: 'Đường dẫn này không tồn tại trên KLAW. Quay lại trang chủ hoặc tra cứu ngay.',
};

function datMeta(selector: string, noiDung: string): void {
  document.querySelector(selector)?.setAttribute('content', noiDung);
}

// TraCuu/SoanThao/Soat (Operate, file này không được sửa) không có <h1> nào —
// đợi mãi một h1 không bao giờ xuất hiện thì focus-reset âm thầm vô tác dụng
// trên đúng màn hình được dùng nhiều nhất. Hết hạn thì rơi về chính <main>.
const HET_HAN_CHO_H1_MS = 1000;

/** Focus + thông báo MỘT LẦN cho một lượt chuyển trang. */
function datTieuDiem(phanTu: HTMLElement, tieuDe: string): void {
  if (!phanTu.hasAttribute('tabindex')) phanTu.setAttribute('tabindex', '-1');
  phanTu.focus();
  const vungThongBao = document.getElementById('thong-bao-chuyen-trang');
  if (vungThongBao !== null) vungThongBao.textContent = `Đã chuyển đến trang ${tieuDe}`;
}

export function useTieuDeTrang(): void {
  const { pathname } = useLocation();

  useEffect(() => {
    const { tieuDe, moTa } = TUYEN[pathname] ?? MAC_DINH;
    const tieuDeDayDu = pathname === '/' ? tieuDe : `${tieuDe}${HAU_TO}`;

    document.title = tieuDeDayDu;
    datMeta('meta[name="description"]', moTa);
    datMeta('meta[property="og:title"]', tieuDeDayDu);
    datMeta('meta[property="og:description"]', moTa);

    const noiDungChinh = document.getElementById('noi-dung-chinh');
    if (noiDungChinh === null) return;

    const h1CoSan = noiDungChinh.querySelector<HTMLElement>('h1');
    if (h1CoSan !== null) {
      datTieuDiem(h1CoSan, tieuDe);
      return;
    }

    // Tuyến Read nạp bằng React.lazy: h1 thật chưa có trong DOM lúc chunk
    // đang tải (chỗ này đang là Suspense fallback) — chờ nó xuất hiện thay vì
    // bỏ cuộc ngay, để focus-reset không âm thầm thất bại lần đầu ghé một
    // tuyến. Nhưng KHÔNG chờ vô thời hạn: TraCuu/SoanThao/Soat không có h1
    // nào để chờ, nên hết hạn thì rơi về chính <main>.
    let daXuLy = false;
    let hetHan: ReturnType<typeof setTimeout>;
    const quanSat = new MutationObserver(() => {
      const h1 = noiDungChinh.querySelector<HTMLElement>('h1');
      if (h1 === null || daXuLy) return;
      daXuLy = true;
      clearTimeout(hetHan);
      quanSat.disconnect();
      datTieuDiem(h1, tieuDe);
    });
    quanSat.observe(noiDungChinh, { childList: true, subtree: true });

    hetHan = setTimeout(() => {
      if (daXuLy) return;
      daXuLy = true;
      quanSat.disconnect();
      datTieuDiem(noiDungChinh, tieuDe);
    }, HET_HAN_CHO_H1_MS);

    return () => {
      quanSat.disconnect();
      clearTimeout(hetHan);
    };
  }, [pathname]);
}
