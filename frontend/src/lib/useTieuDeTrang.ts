import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Đặt <title>/meta description/og:* theo tuyến, VÀ xử lý phần khả năng tiếp
 * cận mà một SPA không tự làm: reset tiêu điểm bàn phím về <h1> của trang
 * mới, thông báo qua aria-live (site-spec.md, "Vỏ chung mọi trang" +
 * "Khả năng tiếp cận"). Tự viết, không thêm thư viện.
 *
 * `useTieuDeTrang` gọi MỘT LẦN ở App.tsx — không gọi lại trong từng trang.
 * Tập trung logic ở gốc là cách duy nhất để TẤT CẢ tuyến có title/meta/
 * canonical/focus-reset nhất quán; mỗi lần một trang tự vá lấy một mảnh của
 * việc này là một lần bốn mảnh còn lại bị bỏ quên.
 *
 * Trang có định danh chỉ biết sau khi tải xong (`/van-ban/:docId`) nộp định
 * danh đó qua `useTieuDeDong` ở cuối file — vẫn là cùng một đường ghi.
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
  '/du-lieu': {
    tieuDe: 'Dữ liệu KLAW xử lý',
    moTa:
      'Bản kê dữ liệu hệ thống thật sự chạm tới: gửi đi đâu, lưu bao lâu, và những gì chưa có. Không phải chính sách — chính sách chính thức chưa công bố.',
  },
  '/mien-tru': {
    tieuDe: 'Miễn trừ trách nhiệm',
    moTa:
      'KLAW không phải tư vấn pháp lý. Đọc rõ giới hạn của corpus và cách đối chiếu trước khi dựa vào một câu trả lời để hành động.',
  },
  // Ba tuyến Persuade. Mô tả nói đúng hiện trạng — giá chưa chốt, xác thực
  // chưa nối: một `og:description` hứa "đăng ký ngay" là lời hứa hộ ngay ở bề
  // mặt chia sẻ, nơi không ai đọc được phần đính chính bên trong trang.
  '/bang-gia': {
    tieuDe: 'Bảng giá',
    moTa:
      'Ba gói dự kiến của KLAW, ghi rõ tính năng nào đang chạy hôm nay và tính năng nào chưa có. Giá dự kiến, chưa áp dụng và chưa bao gồm thuế GTGT.',
  },
  '/dang-nhap': {
    tieuDe: 'Đăng nhập',
    moTa:
      'Đăng nhập vào KLAW — tra cứu pháp luật lao động Việt Nam có trích dẫn kiểm chứng được. Backend xác thực chưa được nối; KLAW hiện dùng được không cần tài khoản.',
  },
  '/dang-ky': {
    tieuDe: 'Đăng ký',
    moTa:
      'Tạo tài khoản KLAW. Việc xử lý dữ liệu cá nhân cần bạn đồng ý rõ ràng; chính sách bảo vệ dữ liệu cá nhân sẽ công bố trước khi KLAW mở đăng ký.',
  },
};

/**
 * Tuyến ĐỘNG — đường dẫn không khớp tuyệt đối bảng trên. Thiếu bảng này thì
 * `/van-ban/:docId`, một trang CÓ THẬT, rơi về MAC_DINH: chia sẻ một trích dẫn
 * lên Zalo/Facebook hiện preview "Đường dẫn này không tồn tại trên KLAW", và
 * trình đọc màn hình loan báo "Không tìm thấy trang" cho một trang mở được.
 *
 * Mô tả ở đây là mô tả TRUNG LẬP dùng trong lúc đang tải; định danh thật của
 * văn bản chỉ biết sau khi metadata về, và trang tự nộp qua `useTieuDeDong`.
 */
const TUYEN_DONG: { mau: RegExp; mo: MoTaTuyen }[] = [
  {
    mau: /^\/van-ban\/[^/]+$/,
    mo: {
      tieuDe: 'Văn bản',
      moTa:
        'Mục lục Chương/Mục và nguyên văn từng Điều của một văn bản trong corpus KLAW — lấy thẳng từ cơ sở dữ liệu, không rút gọn, không sửa chính tả.',
    },
  },
];

const MAC_DINH: MoTaTuyen = {
  tieuDe: 'Không tìm thấy trang',
  moTa: 'Đường dẫn này không tồn tại trên KLAW. Quay lại trang chủ hoặc tra cứu ngay.',
};

function timTuyen(pathname: string): MoTaTuyen {
  return (
    TUYEN[pathname] ?? TUYEN_DONG.find((tuyen) => tuyen.mau.test(pathname))?.mo ?? MAC_DINH
  );
}

function datMeta(selector: string, noiDung: string): void {
  document.querySelector(selector)?.setAttribute('content', noiDung);
}

/**
 * Canonical = origin + pathname, BỎ query.
 *
 * `/tra-cuu?q=…` sinh vô hạn URL biến thể mang y hệt title và description —
 * không có canonical thì công cụ tìm kiếm phải tự chọn một bản, và nó thường
 * chọn sai. Giá trị tuyệt đối tự sinh từ `location.origin`, nên nó đúng ở dev
 * lẫn ở domain thật mà không cần chép cứng domain vào mã.
 */
function datCanonical(pathname: string): void {
  let the = document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (the === null) {
    the = document.createElement('link');
    the.rel = 'canonical';
    document.head.appendChild(the);
  }
  the.href = `${window.location.origin}${pathname}`;
}

/** Đặt title/description/og:* cho một lượt — dùng chung cho tuyến tĩnh và
 *  tuyến động, để không tồn tại đường nào chỉ sửa `document.title` rồi bỏ quên
 *  `og:title` (bản vá cũ ở VanBan.tsx đã đúng như vậy). */
function datTheTrang(tieuDe: string, moTa: string, pathname: string): void {
  const tieuDeDayDu = pathname === '/' ? tieuDe : `${tieuDe}${HAU_TO}`;
  document.title = tieuDeDayDu;
  datMeta('meta[name="description"]', moTa);
  datMeta('meta[property="og:title"]', tieuDeDayDu);
  datMeta('meta[property="og:description"]', moTa);
}

// Tuyến Read nạp bằng React.lazy chưa có h1 trong DOM lúc chunk đang tải, nên
// focus-reset phải CHỜ. Nhưng không chờ vô thời hạn: một trang không có h1 nào
// (hoặc chunk hỏng) thì hết hạn rồi rơi về chính <main>, vốn có vòng tiêu điểm
// riêng trong index.css.
const HET_HAN_CHO_H1_MS = 1000;

function thongBao(cau: string): void {
  const vungThongBao = document.getElementById('thong-bao-chuyen-trang');
  if (vungThongBao !== null) vungThongBao.textContent = cau;
}

/** Focus + thông báo MỘT LẦN cho một lượt chuyển trang. */
function datTieuDiem(phanTu: HTMLElement, tieuDe: string): void {
  if (!phanTu.hasAttribute('tabindex')) phanTu.setAttribute('tabindex', '-1');
  phanTu.focus();
  thongBao(`Đã chuyển đến trang ${tieuDe}`);
}

export function useTieuDeTrang(): void {
  const { pathname } = useLocation();

  useEffect(() => {
    const { tieuDe, moTa } = timTuyen(pathname);
    datTheTrang(tieuDe, moTa, pathname);
    datCanonical(pathname);

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
    // tuyến. Nhưng KHÔNG chờ vô thời hạn: hết hạn thì rơi về chính <main>.
    // (Cả bảy tuyến nay đều có h1 — nhánh dưới là lưới an toàn, không phải
    // đường đi thường ngày.)
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

/**
 * Tuyến động: nộp ĐỊNH DANH THẬT sau khi tải xong, để thay bản mô tả trung
 * lập mà `useTieuDeTrang` đã đặt lúc chưa biết gì.
 *
 * Ở đây chứ không ở trang: một bản vá cấp trang chỉ với tới `document.title`
 * và bỏ quên `og:title`, `og:description`, `meta description` cùng thông báo
 * `aria-live` — đúng bốn thứ mà bề mặt chia sẻ và trình đọc màn hình đọc.
 * `null` (chưa tải xong, hoặc tải hỏng) thì KHÔNG đụng gì: mô tả trung lập
 * vẫn tốt hơn một định danh bịa ra.
 */
export function useTieuDeDong(ten: string | null, moTa: string | null = null): void {
  const { pathname } = useLocation();

  useEffect(() => {
    if (ten === null) return;
    datTheTrang(ten, moTa ?? timTuyen(pathname).moTa, pathname);
    thongBao(`Đã chuyển đến ${ten}`);
  }, [ten, moTa, pathname]);
}
