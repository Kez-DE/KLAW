import { useId, useState, type FormEvent } from "react";
import { giaTriHienThi, khoaO, nhanO, oDaDoi, type ODienGui } from "@/lib/khuon-goc";
import type { KhuonBanThao } from "@/lib/klaw";
import { cn } from "@/lib/utils";

interface Props {
  khuon: KhuonBanThao;
  /** Lưu MỌI ô đổi thành MỘT phiên bản. `true` = đã lưu (bảng bỏ chữ đang gõ
   *  và đọc lại giá trị từ phiên bản mới); `false` = bị từ chối — chữ người
   *  dùng gõ PHẢI còn nguyên để sửa rồi lưu lại. Nơi gọi báo lỗi. */
  onLuu: (doi: ODienGui[]) => Promise<boolean>;
}

/**
 * Bảng ô điền — một ô nhập có nhãn cho mỗi chỗ trống của khuôn gốc, theo thứ
 * tự đọc (kế hoạch `khuon-goc-dien-tai-cho.md`, Outcome 4).
 *
 * Chỉ giữ chữ của ô người dùng ĐÃ chạm; ô chưa chạm luôn đọc giá trị của phiên
 * bản đang có, nên một lượt chat vừa điền ô khác hiện ra ngay mà không xoá chữ
 * đang gõ dở ở ô này. Nơi gọi đặt `key={banThao.id}`: sang bản thảo khác là
 * một bảng mới.
 */
export function BangODien({ khuon, onLuu }: Props) {
  const goc = useId();
  const [nhap, datNhap] = useState<Record<string, string>>({});
  const [dangLuu, datDangLuu] = useState(false);
  const doi = oDaDoi(khuon.cho_trong, nhap);
  const daDien = khuon.cho_trong.filter((o) => giaTriHienThi(o) !== "").length;

  const luu = async (e: FormEvent) => {
    e.preventDefault();
    if (dangLuu || doi.length === 0) return;
    datDangLuu(true);
    const ok = await onLuu(doi);
    datDangLuu(false);
    if (ok) datNhap({});
  };

  if (khuon.cho_trong.length === 0) {
    return (
      <p className="m-0 text-[13px] leading-5 text-muted-foreground">
        KLAW không tìm thấy chỗ trống nào điền được trên tài liệu này. Bạn vẫn nhờ trợ lý sửa bằng
        lời được.
      </p>
    );
  }

  return (
    <form onSubmit={(e) => void luu(e)} aria-labelledby={`${goc}-tieu-de`} noValidate>
      <h3 id={`${goc}-tieu-de`} className="m-0 text-[13px] font-semibold text-foreground">
        Ô điền
      </h3>
      <p className="m-0 mt-1 text-[12px] text-muted-foreground">
        Đã điền {daDien}/{khuon.cho_trong.length} ô
        {doi.length > 0 && ` · ${doi.length} thay đổi chưa lưu`}
      </p>
      <ol className="m-0 mt-3 flex list-none flex-col gap-3 p-0">
        {khuon.cho_trong.map((o) => {
          const khoa = khoaO(o);
          const id = `${goc}-o-${o.don_vi}-${o.so}`;
          return (
            <li key={khoa}>
              <label htmlFor={id} className="mb-1 block text-[12.5px] text-foreground">
                {nhanO(o)}
              </label>
              <input
                id={id}
                type="text"
                value={nhap[khoa] ?? giaTriHienThi(o)}
                onChange={(e) => {
                  const v = e.target.value;
                  datNhap((cu) => ({ ...cu, [khoa]: v }));
                }}
                maxLength={500}
                autoComplete="off"
                spellCheck={false}
                lang="vi"
                className="focus-brass min-h-10 w-full rounded-md border border-[var(--input)] bg-background px-2.5 text-[13.5px] text-foreground"
              />
            </li>
          );
        })}
      </ol>
      <button
        type="submit"
        // `aria-disabled`, không `disabled`: nút đang nhận tiêu điểm mà bị
        // `disabled` thì trình duyệt thả tiêu điểm về `<body>` giữa lúc lưu, và
        // nút khoá hẳn thì rời vòng Tab — người dùng bàn phím không tìm ra nó.
        // `luu` tự chặn khi đang lưu hay chưa đổi gì.
        aria-disabled={dangLuu || doi.length === 0}
        className={cn(
          "focus-brass mt-4 inline-flex min-h-10 cursor-pointer items-center rounded-lg bg-primary px-4 text-[13px] font-medium text-primary-foreground transition-opacity hover:opacity-90",
          "aria-disabled:cursor-not-allowed aria-disabled:opacity-60",
        )}
      >
        {dangLuu ? "Đang lưu…" : "Lưu"}
      </button>
    </form>
  );
}
