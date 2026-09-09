import { useEffect, useState } from "react";
import { datGhiNho, layBoNho, suaBoNho, xoaBoNho, xoaHetBoNho } from "@/lib/api";
import type { BoNhoTaiKhoan } from "@/lib/klaw";

/** "KLAW nhớ về bạn" — chỉ Pro (spec 2026-09-09 §6.6). Bảy khoá, sửa tại chỗ, xoá từng dòng, xoá hết có xác nhận. */
export function TheBoNho() {
  const [bn, datBn] = useState<BoNhoTaiKhoan | null>(null);
  const [loi, datLoi] = useState<string | null>(null);
  const [sua, datSua] = useState<{ khoa: string; nhap: string; loi: string | null } | null>(null);
  const [xacNhanXoaHet, datXacNhanXoaHet] = useState(false);
  const nap = () => {
    void layBoNho().then((kq) =>
      kq.ok ? datBn(kq.data) : datLoi("Tôi chưa đọc được bộ nhớ của bạn."),
    );
  };
  useEffect(nap, []);
  if (loi !== null)
    return (
      <p role="status" className="mt-6 text-[13px] text-muted-foreground">
        {loi}
      </p>
    );
  if (bn === null) return null;
  const chay = (p: Promise<{ ok: boolean }>) => void p.then(nap);
  return (
    <section
      className="mt-6 space-y-3 rounded-xl border border-border bg-card p-4"
      aria-labelledby="bo-nho-tieu-de"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="bo-nho-tieu-de" className="font-display m-0 text-[16px] font-bold text-primary">
            KLAW nhớ về bạn
          </h2>
          <p className="m-0 mt-1 text-[13px] text-muted-foreground">
            Chỉ dữ kiện về hoàn cảnh của bạn để phiên sau không phải kể lại; không bao giờ lưu giấy
            tờ, số tài khoản, địa chỉ.
          </p>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            checked={bn.ghi_nho}
            onChange={(e) => chay(datGhiNho(e.target.checked))}
          />
          Ghi nhớ
        </label>
      </div>
      {bn.muc.length === 0 ? (
        <p className="m-0 text-[13px] text-muted-foreground">
          Chưa có gì. Hỏi vài câu về việc của bạn, KLAW sẽ ghi lại những dữ kiện bền.
        </p>
      ) : (
        <ul className="m-0 list-none divide-y divide-border p-0">
          {bn.muc.map((m) => (
            <li key={m.khoa} className="py-2 text-[14px]">
              <div className="flex items-center gap-2">
                <span className="w-36 shrink-0 text-muted-foreground">{m.nhan}</span>
                {sua?.khoa === m.khoa ? (
                  <input
                    autoFocus
                    value={sua.nhap}
                    maxLength={120}
                    aria-label={`Sửa ${m.nhan}`}
                    onChange={(e) => datSua({ khoa: m.khoa, nhap: e.target.value, loi: null })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && sua.nhap.trim()) {
                        const giaTri = sua.nhap.trim();
                        // Không dùng `chay()` ở đây: máy chủ có thể từ chối giá trị này
                        // bằng 422 (trông giống một điều luật hoặc số văn bản), và
                        // `error.message` là câu tiếng Việt hiển thị thẳng được — nuốt
                        // nó rồi tải lại như không có gì xảy ra là hỏng âm thầm.
                        void suaBoNho(m.khoa, giaTri).then((kq) => {
                          if (kq.ok) {
                            datBn(kq.data);
                            datSua(null);
                          } else datSua({ khoa: m.khoa, nhap: giaTri, loi: kq.error.message });
                        });
                      }
                      if (e.key === "Escape") datSua(null);
                    }}
                    className="focus-brass flex-1 rounded border border-border bg-background px-2 py-1"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => datSua({ khoa: m.khoa, nhap: m.gia_tri, loi: null })}
                    className="focus-brass flex-1 cursor-pointer rounded px-2 py-1 text-left text-foreground hover:bg-secondary"
                  >
                    {m.gia_tri}
                  </button>
                )}
                <button
                  type="button"
                  aria-label={`Xoá ${m.nhan}`}
                  onClick={() => chay(xoaBoNho(m.khoa))}
                  className="focus-brass cursor-pointer rounded px-2 py-1 text-[13px] text-muted-foreground hover:text-foreground"
                >
                  Xoá
                </button>
              </div>
              {sua?.khoa === m.khoa && sua.loi !== null && (
                <p role="alert" className="m-0 mt-1 text-[12px] text-destructive">
                  {sua.loi}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      {bn.muc.length > 0 &&
        (xacNhanXoaHet ? (
          <div className="flex items-center gap-2 text-[13px]">
            <span>Xoá toàn bộ những gì KLAW nhớ về bạn?</span>
            <button
              type="button"
              onClick={() => {
                chay(xoaHetBoNho());
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
