import type { FactField } from '../../types';

/**
 * Form nhập fact — DỰNG TỪ `GET /api/v1/mau/{loai}`, không hardcode một trường
 * nào. Danh sách trường sinh từ `can_facts` của các rule trong
 * `config/rules.yaml`; chép cứng nó vào JSX sẽ trôi lệch khỏi YAML ngay lần
 * sửa rule đầu tiên, và không ai phát hiện ra cho tới khi một rule im lặng
 * không được kiểm.
 *
 * Giá trị giữ dưới dạng CHUỖI cho mọi kiểu; đổi kiểu một lần lúc gửi
 * (`pages/SoanThao.tsx`). Ô trống nghĩa là fact VẮNG MẶT — một input hợp lệ:
 * rule engine trả "không kiểm được: thiếu …" thay vì đoán bừa.
 */

interface FormFactsProps {
  facts: FactField[];
  giaTri: Record<string, string>;
  onDoi: (key: string, giaTri: string) => void;
  voHieu: boolean;
}

const O_NHAP =
  'block w-full rounded-vua border p-2 text-[0.9375rem] text-phim placeholder:text-muc-nhat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:opacity-50';

const KIEU_O_NHAP = {
  background: 'var(--nen-cao)',
  borderColor: 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)',
  minHeight: 'var(--vung-cham-toi-thieu)',
};

export function FormFacts({ facts, giaTri, onDoi, voHieu }: FormFactsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {facts.map((truong) => {
        const id = `fact-${truong.key}`;
        const giaTriHienTai = giaTri[truong.key] ?? '';

        if (truong.kieu === 'bool') {
          return (
            <div key={truong.key} className="sm:col-span-2">
              <label
                htmlFor={id}
                className="flex min-h-[var(--vung-cham-toi-thieu)] cursor-pointer items-center gap-3 text-[0.9375rem] leading-6 text-phim"
              >
                <input
                  id={id}
                  type="checkbox"
                  disabled={voHieu}
                  checked={giaTriHienTai === 'true'}
                  onChange={(su) => onDoi(truong.key, su.target.checked ? 'true' : 'false')}
                  className="size-5 shrink-0 accent-[var(--den-sang)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
                />
                {truong.nhan}
              </label>
            </div>
          );
        }

        return (
          <div key={truong.key}>
            <label htmlFor={id} className="mb-1 block text-[0.875rem] leading-6 text-phim">
              {truong.nhan}
              {truong.bat_buoc && (
                <span className="ms-1 text-[0.75rem] text-muc-nhat">(bắt buộc)</span>
              )}
            </label>
            {truong.lua_chon !== null ? (
              <select
                id={id}
                disabled={voHieu}
                aria-required={truong.bat_buoc}
                value={giaTriHienTai}
                onChange={(su) => onDoi(truong.key, su.target.value)}
                className={O_NHAP}
                style={KIEU_O_NHAP}
              >
                <option value="">— chưa chọn —</option>
                {truong.lua_chon.map((lua) => (
                  <option key={lua} value={lua}>
                    {lua}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={id}
                // `kieu` là chuỗi từ YAML: kiểu lạ rơi về ô chữ thay vì làm sập form.
                type={truong.kieu === 'int' ? 'number' : 'text'}
                inputMode={truong.kieu === 'int' ? 'numeric' : undefined}
                step={truong.kieu === 'int' ? 1 : undefined}
                disabled={voHieu}
                aria-required={truong.bat_buoc}
                value={giaTriHienTai}
                onChange={(su) => onDoi(truong.key, su.target.value)}
                className={O_NHAP}
                style={KIEU_O_NHAP}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
