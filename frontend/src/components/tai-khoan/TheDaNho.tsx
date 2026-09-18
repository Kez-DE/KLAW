import { useEffect, useState } from "react";
import { layDaNho, xoaDaNho, xoaHetDaNho } from "@/lib/api";
import type { ApiResult, DanhSachDaNho } from "@/lib/klaw";

/**
 * "Điều KLAW đã nhớ về bạn" (Phase 12, R2) — dữ kiện cá nhân và thói quen soạn
 * mà người dùng đã khai trong một lượt soạn thảo. Chỉ XEM và XOÁ: sửa là nói
 * lại trong lượt soạn, không có biểu mẫu thứ hai. Khác `TheBoNho` (hồ sơ tình
 * huống pháp lý, chỉ Pro): thẻ này mở cho mọi tài khoản, vì đây là dữ liệu cá
 * nhân và quyền xoá nó không thuộc một gói.
 *
 * Xác nhận "Xoá tất cả" là hai lần bấm tại chỗ, không `window.confirm`: hộp
 * thoại trình duyệt chặn tự động hoá và không theo giao diện.
 */
export function TheDaNho() {
  const [ds, datDs] = useState<DanhSachDaNho | null>(null);
  const [loi, datLoi] = useState<string | null>(null);
  const [loiHanhDong, datLoiHanhDong] = useState<string | null>(null);
  const [xacNhanXoaHet, datXacNhanXoaHet] = useState(false);
  const nap = () => {
    void layDaNho().then((kq) =>
      kq.ok ? datDs(kq.data) : datLoi("Tôi chưa đọc được những điều KLAW đã nhớ về bạn."),
    );
  };
  useEffect(nap, []);
  if (loi !== null)
    return (
      <p role="status" className="mt-6 text-[13px] text-muted-foreground">
        {loi}
      </p>
    );
  if (ds === null) return null;
  const chay = <T,>(p: Promise<ApiResult<T>>) =>
    void p.then((kq) => {
      if (kq.ok) {
        datLoiHanhDong(null);
        nap();
      } else datLoiHanhDong(kq.error.message);
    });
  return (
    <section
      className="mt-6 space-y-3 rounded-xl border border-border bg-card p-4"
      aria-labelledby="da-nho-tieu-de"
    >
      <div>
        <h2 id="da-nho-tieu-de" className="font-display m-0 text-[16px] font-bold text-primary">
          Điều KLAW đã nhớ về bạn
        </h2>
        <p className="m-0 mt-1 text-[13px] text-muted-foreground">
          Những gì bạn đã khai khi soạn văn bản, để lần sau không phải gõ lại. KLAW chỉ dùng khi bạn
          yêu cầu, không tự điền vào văn bản mới.
        </p>
      </div>
      {loiHanhDong !== null && (
        <p role="alert" className="m-0 text-[13px] text-destructive">
          {loiHanhDong}
        </p>
      )}
      {ds.muc.length === 0 ? (
        <p className="m-0 text-[13px] text-muted-foreground">
          Chưa có gì. Khi bạn khai họ tên, mã sinh viên hay nơi thực tập trong một lượt soạn, KLAW
          sẽ ghi lại ở đây.
        </p>
      ) : (
        <ul className="m-0 list-none divide-y divide-border p-0">
          {ds.muc.map((m) => (
            <li key={m.id} className="flex items-center gap-2 py-2 text-[14px]">
              <span className="w-36 shrink-0 text-muted-foreground">{m.nhan}</span>
              <span className="flex-1 break-words px-2 py-1 text-foreground">{m.gia_tri}</span>
              <button
                type="button"
                aria-label={`Xoá ${m.nhan}`}
                onClick={() => chay(xoaDaNho(m.id))}
                className="focus-brass cursor-pointer rounded px-2 py-1 text-[13px] text-muted-foreground hover:text-foreground"
              >
                Xoá
              </button>
            </li>
          ))}
        </ul>
      )}
      {ds.muc.length > 0 &&
        (xacNhanXoaHet ? (
          <div className="flex items-center gap-2 text-[13px]">
            <span>Xoá toàn bộ những gì KLAW đã nhớ về bạn?</span>
            <button
              type="button"
              autoFocus
              onClick={() => {
                chay(xoaHetDaNho());
                datXacNhanXoaHet(false);
              }}
              className="focus-brass cursor-pointer rounded border border-border px-2 py-1"
            >
              Xoá tất cả
            </button>
            <button
              type="button"
              onClick={() => datXacNhanXoaHet(false)}
              className="focus-brass cursor-pointer rounded px-2 py-1 text-muted-foreground"
            >
              Giữ lại
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => datXacNhanXoaHet(true)}
            className="focus-brass cursor-pointer text-[13px] text-muted-foreground underline-offset-2 hover:underline"
          >
            Xoá tất cả
          </button>
        ))}
    </section>
  );
}
