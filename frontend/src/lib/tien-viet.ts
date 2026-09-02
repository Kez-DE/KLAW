const CHU_SO = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"];

const cs = (i: number) => CHU_SO[i] as string;

function docBaChuSo(n: number, dayDu: boolean): string {
  const tram = Math.floor(n / 100);
  const chuc = Math.floor((n % 100) / 10);
  const donVi = n % 10;
  const out: string[] = [];

  if (tram > 0) {
    out.push(cs(tram), "trăm");
    if (chuc === 0 && donVi > 0) out.push("linh");
  } else if (dayDu) {
    out.push("không", "trăm");
    if (chuc === 0 && donVi > 0) out.push("linh");
  }

  if (chuc > 1) {
    out.push(cs(chuc), "mươi");
    if (donVi === 1) out.push("mốt");
    else if (donVi === 5) out.push("lăm");
    else if (donVi > 0) out.push(cs(donVi));
  } else if (chuc === 1) {
    out.push("mười");
    if (donVi === 5) out.push("lăm");
    else if (donVi > 0) out.push(cs(donVi));
  } else if (donVi > 0) {
    out.push(cs(donVi));
  }

  return out.join(" ");
}

/** Đọc số thành chữ tiếng Việt, ví dụ 500000000 → "Năm trăm triệu đồng chẵn". */
export function docSoThanhChu(so: number, hauTo = "đồng chẵn"): string {
  if (!Number.isFinite(so) || so <= 0) return "";
  const n = Math.floor(so);
  const nhom: number[] = [];
  let con = n;
  while (con > 0) {
    nhom.unshift(con % 1000);
    con = Math.floor(con / 1000);
  }
  const donViNhom = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"];
  const phan: string[] = [];
  nhom.forEach((giaTri, i) => {
    const bac = nhom.length - 1 - i;
    if (giaTri === 0) return;
    phan.push(docBaChuSo(giaTri, i !== 0), donViNhom[bac] as string);
  });
  const chu = phan.join(" ").replace(/\s+/g, " ").trim();
  const hoa = chu.charAt(0).toUpperCase() + chu.slice(1);
  return `${hoa} ${hauTo}`.trim();
}

/** Định dạng 1000000 → "1.000.000 ₫" */
export function dinhDangTien(so: number | ""): string {
  if (so === "" || !Number.isFinite(Number(so))) return "";
  return `${Number(so).toLocaleString("vi-VN")} ₫`;
}

export function chiSo(chuoi: string): number | "" {
  const s = chuoi.replace(/[^\d]/g, "");
  return s === "" ? "" : Number(s);
}
