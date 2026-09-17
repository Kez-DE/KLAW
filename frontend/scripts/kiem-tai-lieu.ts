/**
 * Kiểm chạy được cho phần trình bày dữ kiện rút từ tài liệu (spec 2026-09-15).
 *
 * Vì sao mấy hàm ngắn này đáng có kiểm riêng: chúng quyết định người dùng TIN
 * điều gì. Một giá trị người dùng tự sửa mà hiện kèm đoạn trích của giá trị cũ
 * là giao diện nói dối bằng cách trưng ra bằng chứng cho một điều nó không
 * chứng minh — và điều đó đi thẳng vào một văn bản pháp lý.
 *
 * Chạy: `npm run kiem-tai-lieu`.
 */
import assert from "node:assert/strict";
import {
  DINH_DANG_CHAP_NHAN,
  DUONG_DAN,
  NGUONG_TIN_CANH_BAO,
  TRAN_BYTE,
  canhBaoDoTin,
  canhBaoOcr,
  coNeo,
  dinhDangHopLe,
  loiTruocKhiGui,
  nhanNeo,
  nhanNguon,
  nhanVung,
  seDungOcr,
  theoTrang,
  trichHienThi,
  type DuKien,
} from "../src/lib/tai-lieu.ts";

const dk = (p: Partial<DuKien>): DuKien => ({
  id: "1",
  khoa: "luong_thang",
  nhan: "Lương tháng",
  gia_tri: "20000000",
  nguon: "tai_lieu",
  trich: "Mức lương: 20.000.000 đồng/tháng",
  trich_goc: null,
  trang: 1,
  chi_so_don_vi: 0,
  do_tin: null,
  ...p,
});

// 1. Bốn nguồn, bốn nhãn KHÁC NHAU. "Từ tài liệu" và "Máy đọc từ ảnh" đặc biệt
//    không được gộp: một cái là chữ thật, cái kia là máy đoán từ ảnh.
{
  const nhan = (["tai_lieu", "tai_lieu_ocr", "nguoi_dung_nhap", "nguoi_dung_sua"] as const).map(
    nhanNguon,
  );
  assert.equal(new Set(nhan).size, 4);
  for (const n of nhan) assert.ok(n.trim().length > 0);
}

// 1b. Dữ kiện OCR vẫn bấm xem được bằng chứng, và vẫn nhóm theo trang.
{
  const ocr = dk({ nguon: "tai_lieu_ocr", do_tin: 0.93 });
  assert.equal(coNeo(ocr), true);
  assert.equal(theoTrang([ocr])[0].trang, 1);
}

// 1c. Cảnh báo CHỈ khi độ tin thấp. Cảnh báo mọi dòng OCR sẽ làm người dùng bỏ
//     qua cảnh báo — đúng cách một lời nhắc tự vô hiệu hoá.
{
  assert.equal(canhBaoDoTin(dk({})), null, "chữ thật không cảnh báo");
  assert.equal(canhBaoDoTin(dk({ nguon: "tai_lieu_ocr", do_tin: 0.95 })), null);
  const canh = canhBaoDoTin(dk({ nguon: "tai_lieu_ocr", do_tin: 0.62 }));
  assert.ok(canh && canh.includes("đối chiếu"), "cảnh báo phải nói việc cần làm");
  assert.ok(NGUONG_TIN_CANH_BAO > 0 && NGUONG_TIN_CANH_BAO < 1);
}

// 1d. Biết trước tệp nào sẽ phải qua OCR, để báo cho người dùng TRƯỚC khi gửi.
assert.equal(seDungOcr("scan.png"), true);
assert.equal(seDungOcr("HOP-DONG.JPG"), true);
assert.equal(seDungOcr("hop-dong.pdf"), false);
assert.equal(seDungOcr("hop-dong.docx"), false);
assert.equal(seDungOcr("hop-dong.doc"), false);

// 2. Chỉ dữ kiện từ tài liệu và CÓ ĐỦ neo mới được coi là bấm xem được.
assert.equal(coNeo(dk({})), true);
assert.equal(coNeo(dk({ nguon: "nguoi_dung_nhap", trich: null })), false);
assert.equal(coNeo(dk({ trich: null })), false, "thiếu trích thì không có neo");
assert.equal(coNeo(dk({ trang: null })), false, "thiếu vị trí thì không có neo");

// 3. Dữ kiện ĐÃ SỬA hiện TRÍCH GỐC và được đánh dấu là gốc. Đây là dòng quan
//    trọng nhất file này: đoạn trích chứng minh giá trị CŨ.
{
  const daSua = dk({
    nguon: "nguoi_dung_sua",
    gia_tri: "25000000",
    trich: null,
    trich_goc: "Mức lương: 20.000.000 đồng/tháng",
  });
  const ra = trichHienThi(daSua);
  assert.ok(ra, "dữ kiện đã sửa vẫn phải có đường đối chiếu");
  assert.equal(ra.laGoc, true, "phải đánh dấu đây là trích của giá trị CŨ");
  assert.equal(ra.chu, "Mức lương: 20.000.000 đồng/tháng");
}

// 4. Dữ kiện người dùng tự nhập KHÔNG có trích, và không được bịa ra một cái.
assert.equal(trichHienThi(dk({ nguon: "nguoi_dung_nhap", trich: null })), null);

// 5. Dữ kiện từ tài liệu hiện trích của chính nó, không đánh dấu là gốc.
{
  const ra = trichHienThi(dk({}));
  assert.ok(ra);
  assert.equal(ra.laGoc, false);
}

// 6. Nhóm theo trang: đúng thứ tự tài liệu, dữ kiện không có trang xếp cuối.
{
  const nhom = theoTrang([
    dk({ id: "a", trang: 2 }),
    dk({ id: "b", nguon: "nguoi_dung_nhap", trich: null, trang: null }),
    dk({ id: "c", trang: 1 }),
  ]);
  assert.deepEqual(
    nhom.map((n) => n.trang),
    [1, 2, null],
  );
  assert.equal(nhom[0].items[0].id, "c");
}

// 7. Chặn định dạng trước khi tốn một byte băng thông. Ảnh và scan nằm ngoài
//    phạm vi lần này, nên câu từ chối phải nói thẳng điều đó.
assert.equal(dinhDangHopLe("hop-dong.pdf"), true);
assert.equal(dinhDangHopLe("HOP-DONG.DOCX"), true, "phần mở rộng viết hoa vẫn hợp lệ");
assert.equal(dinhDangHopLe("anh-chup.png"), true, "ảnh nay đọc được bằng OCR");
assert.equal(
  dinhDangHopLe("ghi-chu.doc"),
  true,
  ".doc đọc được từ Phase 13 (chuyển sang .docx ở backend)",
);
for (const d of [".pdf", ".docx", ".doc", ".png", ".jpg"])
  assert.ok(DINH_DANG_CHAP_NHAN.includes(d), `accept thiếu ${d}`);

// 8. Hai câu từ chối phân biệt được: sai định dạng và quá lớn là hai việc khác
//    nhau người dùng phải làm.
{
  const sai = loiTruocKhiGui("bang-tinh.xlsx", 10);
  const lon = loiTruocKhiGui("hd.pdf", TRAN_BYTE + 1);
  assert.ok(sai && lon && sai !== lon);
  assert.ok(lon.includes("20 MB"), "phải nêu đúng giới hạn bị vượt");
  assert.equal(loiTruocKhiGui("hd.pdf", TRAN_BYTE), null, "đúng bằng trần thì vẫn gửi được");
}

// 9. Đường dẫn KHÔNG lặp `/api/v1`. `apiGoc()` đã chứa nó; lặp lại cho
//    `/api/v1/api/v1/...` và một 404 mà MỌI test phía máy chủ đều không thấy,
//    vì chúng gọi thẳng FastAPI chứ không đi qua client này. Đây là lớp lỗi đã
//    thật sự xảy ra một lần, không phải lo xa.
{
  const duong = [
    DUONG_DAN.taiLen(),
    DUONG_DAN.chiTiet("v1"),
    DUONG_DAN.donVi("v1"),
    DUONG_DAN.huy("v1"),
    DUONG_DAN.duKien("d1"),
    DUONG_DAN.theoHoiThoai("h1"),
    DUONG_DAN.sangSoanThao("h1", "hdld", true),
  ];
  for (const d of duong) {
    assert.ok(d.startsWith("/tai-lieu"), `đường dẫn phải bắt đầu bằng /tai-lieu: ${d}`);
    assert.ok(!d.includes("/api/"), `đường dẫn KHÔNG được chứa /api: ${d}`);
  }
  assert.ok(DUONG_DAN.sangSoanThao("h1", "hdld", true).includes("&ghi=true"));
  assert.ok(!DUONG_DAN.sangSoanThao("h1", "hdld", false).includes("ghi=true"));
  // Tham số phải được mã hoá: một id lạ không được phá cấu trúc URL.
  assert.ok(DUONG_DAN.chiTiet("a/b").includes("a%2Fb"));
}

// 10. Nhãn neo tài liệu phải ĐỊNH VỊ ĐƯỢC BẰNG MẮT trên tờ giấy: người dùng
//     bấm chip để mở, rồi vẫn phải tìm lại chỗ đó trên bản gốc. "đơn vị #28"
//     không tìm được bao giờ; "tr. 1 · bảng 1, h5 c2" tìm được trong ba giây.
{
  assert.equal(
    nhanNeo({ trang: 1, chi_so_don_vi: 28, vung: "than", bang: null }),
    "tr. 1 · đoạn 28",
  );
  assert.equal(
    nhanNeo({ trang: 1, chi_so_don_vi: 12, vung: "than", bang: [1, 5, 2] }),
    "tr. 1 · bảng 1, h5 c2",
  );
  // Đầu/chân trang lặp ở MỌI trang, nên số trang ở đó chỉ sai chỗ.
  assert.equal(
    nhanNeo({ trang: 3, chi_so_don_vi: 2, vung: "chan_trang", bang: null }),
    "chân trang · đoạn 2",
  );
  assert.equal(
    nhanNeo({ trang: 1, chi_so_don_vi: 0, vung: "dau_trang", bang: null }),
    "đầu trang · đoạn 0",
  );
  // Thiếu trang vẫn phải ra một nhãn đọc được, không ra "tr. null".
  const khongTrang = nhanNeo({ trang: null, chi_so_don_vi: 4 });
  assert.ok(!khongTrang.includes("null"), khongTrang);
  assert.ok(khongTrang.includes("đoạn 4"));
  // Vùng lạ (backend thêm sau) rơi về chính mã của nó, không làm sập nhãn.
  assert.ok(nhanVung("phu_luc").length > 0);
  assert.equal(nhanVung("chan_trang"), "chân trang");
}

// 11. Một ngưỡng, một câu chữ cho CẢ dữ kiện lẫn neo tài liệu. Hai màn hình nói
//     hai điều khác nhau về cùng một mức tin cậy là cách người dùng mất lòng tin.
{
  assert.equal(canhBaoOcr(false, 0.1), null, "chữ đọc thẳng không có gì để cảnh báo");
  assert.equal(canhBaoOcr(true, 0.9), null);
  assert.equal(canhBaoOcr(true, 0.5), canhBaoDoTin(dk({ nguon: "tai_lieu_ocr", do_tin: 0.5 })));
  assert.ok(canhBaoOcr(true, null), "OCR không kèm độ tin thì cứ cảnh báo");
}

console.log("kiem-tai-lieu: OK");
