/**
 * Kiểm chạy được cho `catTheoTrichDan` — phần định vị câu trích trong nguyên
 * văn. Đây là logic duy nhất trong pha 5 có thể sai âm thầm: nó cắt chuỗi bằng
 * chỉ số, và một chỉ số lệch một ký tự sẽ tô sáng sai chỗ mà không ai nhận ra
 * cho tới khi có người đối chiếu tay.
 *
 * Chạy: `npm run kiem-trich-dan` (Node 22 đọc thẳng TypeScript, không cần
 * thêm thư viện nào).
 */
import assert from "node:assert/strict";
import {
  banGocKy,
  cachTrichHopLe,
  canCuPhapLy,
  catTheoTrichDan,
  chiSoDauCuaVanBan,
  chuoiSaoChep,
  cumDieuKhoan,
  dongBanHanh,
  dongThongTin,
  ghiChuHieuLuc,
  laCauChoNguoiDoc,
  lienKetChinhThuc,
  manhMoTa,
  trichDieuKhoan,
  vanBanHopLe,
} from "../src/lib/trich-dan.ts";
import { cauPhamViTimKiem, laVanBanBiAn, vanBanBiAn } from "../src/lib/klaw.ts";

// 1. Khớp thẳng: ba mảnh ghép lại phải bằng đúng nguyên văn.
{
  const noiDung = "Người lao động có quyền đơn phương chấm dứt hợp đồng lao động.";
  const lat = catTheoTrichDan(noiDung, "đơn phương chấm dứt hợp đồng lao động");
  assert.equal(lat.timThay, true);
  assert.equal(lat.trung, "đơn phương chấm dứt hợp đồng lao động");
  assert.equal(lat.truoc + lat.trung + lat.sau, noiDung.normalize("NFC"));
}

// 2. Khoảng trắng lệch: nguyên văn xuống dòng và có khoảng trắng kép, quote thì
//    một dòng. Phần cắt ra phải là NGUYÊN VĂN (giữ xuống dòng), không phải
//    chuỗi đã bị chuẩn hoá.
{
  const noiDung = "Thời giờ làm việc bình thường\nkhông  quá 08 giờ trong 01 ngày.";
  const lat = catTheoTrichDan(noiDung, "bình thường không quá 08 giờ");
  assert.equal(lat.timThay, true);
  assert.equal(lat.trung, "bình thường\nkhông  quá 08 giờ");
  assert.equal(lat.truoc + lat.trung + lat.sau, noiDung.normalize("NFC"));
}

// 3. Dấu tiếng Việt dạng tổ hợp (NFD) một bên, dựng sẵn (NFC) bên kia.
{
  const noiDung = "Hợp đồng lao động phải được giao kết bằng văn bản.".normalize("NFD");
  const lat = catTheoTrichDan(noiDung, "giao kết bằng văn bản".normalize("NFC"));
  assert.equal(lat.timThay, true);
  assert.equal(lat.trung.normalize("NFC"), "giao kết bằng văn bản");
}

// 4. Không tìm thấy: phải nói ra, và phải trả nguyên văn nguyên vẹn để nơi gọi
//    vẫn hiển thị được điều luật.
{
  const noiDung = "Người sử dụng lao động phải trả lương đúng hạn.";
  const lat = catTheoTrichDan(noiDung, "câu trích không có trong điều này");
  assert.equal(lat.timThay, false);
  assert.equal(lat.trung, "");
  assert.equal(lat.truoc, noiDung.normalize("NFC"));
}

// 5. Quote rỗng hoặc chỉ khoảng trắng KHÔNG phải một câu trích: không được tô
//    sáng ký tự đầu tiên rồi báo là đã định vị được.
for (const rong of ["", "   ", "\n\t"]) {
  const lat = catTheoTrichDan("Nguyên văn bất kỳ.", rong);
  assert.equal(lat.timThay, false, `quote ${JSON.stringify(rong)} phải không định vị được`);
}

// 6. Câu trích nằm ở đúng cuối nguyên văn — biên hay lệch một ký tự nhất.
{
  const noiDung = "Mức lương tối thiểu được điều chỉnh theo vùng.";
  const lat = catTheoTrichDan(noiDung, "theo vùng.");
  assert.equal(lat.timThay, true);
  assert.equal(lat.sau, "");
  assert.equal(lat.trung, "theo vùng.");
}

// 7. Thẻ `doc:ID` mở điều khoản ĐẦU của văn bản đó theo `k` (Q5, spec §7.2).
{
  const cit = [
    { doc_id: "152668", k: 3 },
    { doc_id: "139264", k: 2 },
    { doc_id: "139264", k: 1 },
    { doc_id: "139264", k: null },
  ] as unknown as import("../src/lib/klaw.ts").Citation[];
  assert.equal(
    chiSoDauCuaVanBan(cit, "139264"),
    2,
    "k nhỏ nhất của văn bản, không phải vị trí đầu",
  );
  assert.equal(chiSoDauCuaVanBan(cit, "152668"), 0);
  assert.equal(chiSoDauCuaVanBan(cit, "000"), -1);
  // Không có k nào (payload cũ) → trích dẫn đầu tiên của văn bản.
  const cu = [
    { doc_id: "1" },
    { doc_id: "2" },
  ] as unknown as import("../src/lib/klaw.ts").Citation[];
  assert.equal(chiSoDauCuaVanBan(cu, "2"), 1);
}

// ── Trích dẫn đầy đủ (quyết định 2026-09-28) ─────────────────────────────────
type Citation = import("../src/lib/klaw.ts").Citation;

// 8. Link chỉ khi https VÀ đúng một trong hai cổng chính thống; nhãn theo host.
{
  assert.deepEqual(lienKetChinhThuc("https://vbpl.vn/van-ban/chi-tiet/139264"), {
    url: "https://vbpl.vn/van-ban/chi-tiet/139264",
    nhan: "CSDL quốc gia về pháp luật",
  });
  assert.deepEqual(lienKetChinhThuc("https://vanban.chinhphu.vn/?pageid=27160&docid=198540"), {
    url: "https://vanban.chinhphu.vn/?pageid=27160&docid=198540",
    nhan: "Cổng TTĐT Chính phủ",
  });
  for (const hong of [
    "http://vbpl.vn/van-ban/chi-tiet/1",
    "https://thuvienphapluat.vn/van-ban/x",
    "https://vbpl.vn.evil.example/van-ban/chi-tiet/1",
    "https://evil.example/?u=https://vbpl.vn/",
    "https://user@vbpl.vn/van-ban/chi-tiet/1",
    "https://vbpl.vn:8443/van-ban/chi-tiet/1",
    "https://constructor/",
    "javascript:alert(1)",
    "vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/139264",
    "",
    null,
    42,
  ]) {
    assert.equal(lienKetChinhThuc(hong), null, `${JSON.stringify(hong)} không được thành link`);
  }
}

// 9. Siêu dữ liệu văn bản: giá trị dị dạng bị bỏ, trường vắng là vắng; nguồn
//    đầu biết thì dùng, không thì lấy nguồn sau; tên rơi về `bo_luat` (payload cũ).
{
  const vb = vanBanHopLe(
    {
      so_ky_hieu: "90/2019/NĐ-CP",
      bo_luat: "Nghị định quy định mức lương tối thiểu",
      co_quan_ban_hanh: "  ",
      ngay_ban_hanh: "15/11/2019",
      lien_ket: "http://vbpl.vn/van-ban/chi-tiet/139094",
    },
    {
      co_quan_ban_hanh: "Chính phủ",
      ngay_ban_hanh: "2019-11-15",
      ngay_hieu_luc: "2020-01-01T00:00:00Z",
      lien_ket: "https://vbpl.vn/van-ban/chi-tiet/139094",
    },
  );
  assert.deepEqual(vb, {
    ten_van_ban: "Nghị định quy định mức lương tối thiểu",
    so_ky_hieu: "90/2019/NĐ-CP",
    co_quan_ban_hanh: "Chính phủ",
    ngay_ban_hanh: "2019-11-15",
    ngay_hieu_luc: null,
    lien_ket: {
      url: "https://vbpl.vn/van-ban/chi-tiet/139094",
      nhan: "CSDL quốc gia về pháp luật",
    },
  });
  assert.deepEqual(vanBanHopLe(null, "x", undefined), {
    ten_van_ban: null,
    so_ky_hieu: null,
    co_quan_ban_hanh: null,
    ngay_ban_hanh: null,
    ngay_hieu_luc: null,
    lien_ket: null,
  });
  assert.equal(
    cachTrichHopLe({ cach_trich: " Điều 3 Bộ luật Lao động " }),
    "Điều 3 Bộ luật Lao động",
  );
  assert.equal(cachTrichHopLe({ cach_trich: "" }), null);
  assert.equal(cachTrichHopLe({ cach_trich: 7 }), null);
  assert.equal(cachTrichHopLe({}), null);
}

// 10. Dòng ban hành: đủ phần, dd/mm/yyyy; thiếu phần nào thì bỏ đúng phần đó.
{
  const du = {
    ten_van_ban: null,
    so_ky_hieu: null,
    co_quan_ban_hanh: "Chính phủ",
    ngay_ban_hanh: "2019-11-15",
    ngay_hieu_luc: "2020-01-01",
    lien_ket: null,
  };
  assert.equal(dongBanHanh(du), "Do Chính phủ ban hành ngày 15/11/2019 · hiệu lực từ 01/01/2020");
  assert.equal(
    dongBanHanh({ ...du, ngay_hieu_luc: null }),
    "Do Chính phủ ban hành ngày 15/11/2019",
  );
  assert.equal(
    dongBanHanh({ ...du, ngay_ban_hanh: null }),
    "Do Chính phủ ban hành · hiệu lực từ 01/01/2020",
  );
  assert.equal(
    dongBanHanh({ ...du, co_quan_ban_hanh: null }),
    "Ban hành ngày 15/11/2019 · hiệu lực từ 01/01/2020",
  );
  assert.equal(
    dongBanHanh({ ...du, co_quan_ban_hanh: null, ngay_ban_hanh: null }),
    "Hiệu lực từ 01/01/2020",
  );
  assert.equal(
    dongBanHanh({ ...du, co_quan_ban_hanh: null, ngay_ban_hanh: null, ngay_hieu_luc: null }),
    null,
  );
}

// 11. Cụm điều khoản theo lối văn bản luật, và chuỗi sao chép.
{
  assert.equal(cumDieuKhoan("45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a"), "điểm a khoản 1 Điều 21");
  assert.equal(cumDieuKhoan("90/2019/NĐ-CP > Điều 3 > Khoản 1".normalize("NFD")), "khoản 1 Điều 3");
  // Hàng bảng không phải đơn vị trích dẫn: dẫn tới khoản chứa nó.
  assert.equal(cumDieuKhoan("293/2025/NĐ-CP > Điều 3 > Khoản 1 > Vùng I"), "khoản 1 Điều 3");
  assert.equal(cumDieuKhoan("145/2020/NĐ-CP > Phụ lục"), "Phụ lục");
  assert.equal(cumDieuKhoan("45/2019/QH14"), "");
  assert.equal(
    trichDieuKhoan(
      "90/2019/NĐ-CP > Điều 3 > Khoản 1",
      "Nghị định số 90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ",
    ),
    "khoản 1 Điều 3 Nghị định số 90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ",
  );
  assert.equal(trichDieuKhoan("90/2019/NĐ-CP > Điều 3", "90/2019/NĐ-CP"), "Điều 3 90/2019/NĐ-CP");
  assert.equal(trichDieuKhoan("45/2019/QH14", "45/2019/QH14"), "45/2019/QH14");
  const cau = "khoản 1 Điều 3 Nghị định số 90/2019/NĐ-CP ngày 15/11/2019 của Chính phủ";
  assert.equal(
    chuoiSaoChep(cau, lienKetChinhThuc("https://vbpl.vn/van-ban/chi-tiet/139094")),
    `${cau} — https://vbpl.vn/van-ban/chi-tiet/139094`,
  );
  assert.equal(chuoiSaoChep(cau, null), cau);
}

// 12. Ghi chú hiệu lực: `canh_bao` của CHÍNH trích dẫn khi máy chủ gửi (hiệu
//     lực tính theo điều khoản — hai trích dẫn cùng văn bản khác nhãn được);
//     payload cũ thì câu `warnings[]` của ĐÚNG văn bản, không của văn bản trùng
//     tiền tố số hiệu.
{
  const canhBao = [
    "12/2022/NĐ-CP đã hết hiệu lực: hết hiệu lực từ 2026-09-10",
    "90/2019/NĐ-CP đã bị thay thế: bị 38/2022/NĐ-CP thay thế từ 2022-07-01",
  ];
  assert.equal(ghiChuHieuLuc(canhBao, { so_ky_hieu: "90/2019/NĐ-CP" }), canhBao[1]);
  assert.equal(ghiChuHieuLuc(canhBao, { so_ky_hieu: "2/2022/NĐ-CP" }), undefined);
  assert.equal(ghiChuHieuLuc(canhBao, { so_ky_hieu: "45/2019/QH14" }), undefined);
  // Điều khác của cùng văn bản, còn hiệu lực: máy chủ nói `null`, không mượn
  // câu cảnh báo của điều đã bị thay thế.
  assert.equal(ghiChuHieuLuc(canhBao, { so_ky_hieu: "90/2019/NĐ-CP", canh_bao: null }), undefined);
  assert.equal(
    ghiChuHieuLuc(canhBao, { so_ky_hieu: "12/2022/NĐ-CP", canh_bao: canhBao[0] }),
    canhBao[0],
  );
}

// 13. "Căn cứ pháp lý": thứ tự thẻ trong văn xuôi (rồi ô bảng), mỗi điều khoản
//     một dòng, bỏ nhóm hết hiệu lực/bị thay thế; không thẻ nào → lưới an toàn.
{
  const c = (doc_id: string, duong_dan: string, k: number | null, hieu_luc: string | null) =>
    ({ doc_id, duong_dan, k, hieu_luc, khop_tai_id: k ?? 0 }) as unknown as Citation;
  const citations = [
    c("1", "45/2019/QH14 > Điều 21", 1, "con_hieu_luc"),
    c("1", "45/2019/QH14 > Điều 36 > Khoản 1", 2, "con_hieu_luc"),
    c("2", "90/2019/NĐ-CP > Điều 3", 3, "bi_thay_the"),
    c("1", "45/2019/QH14 > Điều 21", 4, "con_hieu_luc"),
    c("3", "12/2022/NĐ-CP > Điều 7", null, "con_hieu_luc"),
    c("4", "293/2025/NĐ-CP > Điều 3", 5, "con_hieu_luc"),
  ];
  const ds = canCuPhapLy({
    answer:
      "Theo [Điều 36](cite:2), rồi [Điều 21](cite:1), [lại](cite:4), [cũ](cite:3), [x](cite:99).",
    citations,
    bang: [
      { tieu_de: "So sánh", cot: ["Mức"], dong: [["[Điều 3](cite:5)"], ["[Điều 36](cite:2)"]] },
    ],
  });
  assert.deepEqual(
    ds.map((m) => m.chiSoGoc),
    [1, 0, 5],
    "thứ tự thẻ; trùng điều khoản gộp; nhóm 4 bỏ; thẻ lạc bỏ; ô bảng sau văn xuôi",
  );
  assert.deepEqual(
    canCuPhapLy({ answer: "Không có thẻ nào.", citations, bang: [] }).map((m) => m.chiSoGoc),
    [0, 1, 4, 5],
    "không thẻ: cùng tập còn hiệu lực của `KhoiCanCu`, vẫn gộp trùng",
  );
  assert.deepEqual(canCuPhapLy({ answer: null, citations: [], bang: [] }), []);
}

// 14. Câu cho người đọc (quyết định 2026-09-28, mục 10): dòng chẩn đoán nội bộ
//     không bao giờ tới mặt người đọc — kể cả `canh_bao` của lượt đã lưu trước
//     khi máy chủ viết lại lời, vốn mang nguyên `ly_do` của `effectivity.py`.
{
  for (const cau of [
    "tình trạng MOJ = 'chua_xac_dinh' không nằm trong bảng mã đã biết",
    "Đánh giá tại ngày 28/09/2026 · độ tin cậy: thấp",
    "45/2019/QH14 hết hiệu lực một phần: CSDL quốc gia không công bố dữ liệu cấp điều khoản nên không xác định được điều này còn hiệu lực hay không",
    "90/2019/NĐ-CP đã bị thay thế: đồ thị xác nhận: bị 38/2022/NĐ-CP thay thế",
    "không có tín hiệu chấm dứt nào; theo tình trạng CHL",
    "Chưa xác định",
    "   ",
  ]) {
    assert.equal(laCauChoNguoiDoc(cau), false, cau);
  }
  for (const cau of [
    "Đã được sửa đổi, bổ sung bởi Luật số 12/2022/QH15.",
    "Có hiệu lực từ ngày 01/01/2026.",
    "Văn bản này không còn hiệu lực nên không có trong phạm vi tra cứu.",
  ]) {
    assert.equal(laCauChoNguoiDoc(cau), true, cau);
  }
  // `ghiChuHieuLuc` đi qua cùng cửa: câu chẩn đoán bị bỏ, nhãn vẫn đứng đó.
  const chanDoan = "45/2019/QH14 hết hiệu lực một phần: không xác định được điều này";
  assert.equal(ghiChuHieuLuc([], { so_ky_hieu: "45/2019/QH14", canh_bao: chanDoan }), undefined);
  assert.equal(ghiChuHieuLuc([chanDoan], { so_ky_hieu: "45/2019/QH14" }), undefined);
}

// 15. `mo_ta`: câu thường dưới nhãn, tên văn bản trong câu thành mảnh bấm được
//     theo ĐÚNG thứ tự `van_ban_lien_quan`; không câu (hoặc câu chẩn đoán) thì
//     không có gì; văn bản câu không nêu tên thì không dựng link.
{
  const noiBo = { doc_id: "99", so_ky_hieu: "12/2022/QH15", ten_van_ban: null, lien_ket: null };
  const ngoai = {
    doc_id: null,
    so_ky_hieu: "145/2020/NĐ-CP",
    ten_van_ban: "Nghị định hướng dẫn",
    lien_ket: "https://vbpl.vn/van-ban/chi-tiet/145",
  };
  const cau = "Đã được sửa đổi, bổ sung bởi Luật số 12/2022/QH15 và Nghị định số 145/2020/NĐ-CP.";
  assert.deepEqual(manhMoTa({ mo_ta: cau, van_ban_lien_quan: [noiBo, ngoai] }), [
    "Đã được sửa đổi, bổ sung bởi Luật số ",
    { chu: "12/2022/QH15", vanBan: noiBo },
    " và Nghị định số ",
    { chu: "145/2020/NĐ-CP", vanBan: ngoai },
    ".",
  ]);
  const khongNeu = { ...ngoai, so_ky_hieu: "1/2000/NĐ-CP", ten_van_ban: null };
  assert.deepEqual(
    manhMoTa({ mo_ta: "Có hiệu lực từ ngày 01/01/2026.", van_ban_lien_quan: [khongNeu] }),
    ["Có hiệu lực từ ngày 01/01/2026."],
  );
  assert.deepEqual(manhMoTa({ mo_ta: cau }), [cau], "payload chưa có `van_ban_lien_quan`");
  assert.equal(manhMoTa({ mo_ta: null, van_ban_lien_quan: [noiBo] }), null);
  assert.equal(manhMoTa({ verdict: "con_hieu_luc", tin_cay: "thap", ly_do: "x" }), null);
  assert.equal(manhMoTa({ mo_ta: "độ tin cậy: thấp" }), null);
  // Phần tử dị dạng bị loại, không làm hỏng cả câu.
  assert.deepEqual(manhMoTa({ mo_ta: cau, van_ban_lien_quan: [{ doc_id: 7 }, "x", noiBo] }), [
    "Đã được sửa đổi, bổ sung bởi Luật số ",
    { chu: "12/2022/QH15", vanBan: noiBo },
    " và Nghị định số 145/2020/NĐ-CP.",
  ]);
}

// 16. "Thông tin văn bản" (trang văn bản): trường vắng thì BỎ dòng — không
//     "Không rõ", không "Chưa có"; ngày dd/mm/yyyy; ngày dị dạng cũng bỏ.
{
  assert.deepEqual(
    dongThongTin({
      so_ky_hieu: "45/2019/QH14",
      loai_van_ban: "Bộ luật",
      co_quan_ban_hanh: "Quốc hội",
      nguoi_ky: null,
      chuc_danh_nguoi_ky: null,
      ngay_ban_hanh: "2019-11-20",
      ngay_hieu_luc: "2021-01-01",
      ngay_het_hieu_luc: null,
    }),
    [
      ["Số hiệu", "45/2019/QH14"],
      ["Loại văn bản", "Bộ luật"],
      ["Cơ quan ban hành", "Quốc hội"],
      ["Ngày ban hành", "20/11/2019"],
      ["Ngày có hiệu lực", "01/01/2021"],
    ],
  );
  assert.deepEqual(
    dongThongTin({ so_ky_hieu: "1/2000/NĐ-CP", ngay_ban_hanh: "20/11/2019", nguoi_ky: " " }),
    [["Số hiệu", "1/2000/NĐ-CP"]],
  );
}

// 17. 404 `khong_hien_thi`: `detail` được mang qua `goi` nguyên vẹn; guard lấy
//     ra câu và danh sách thay thế, bỏ phần tử dị dạng; 404 thường → null.
{
  const detail = {
    ma: "khong_hien_thi",
    thong_diep: "Văn bản này không còn hiệu lực nên không có trong phạm vi tra cứu.",
    thay_the: [
      { doc_id: "154245", so_ky_hieu: "38/2022/NĐ-CP", ten_van_ban: "Nghị định", lien_ket: null },
      { doc_id: null, so_ky_hieu: "" },
      { doc_id: null, so_ky_hieu: "1/2000/NĐ-CP", ten_van_ban: null, lien_ket: null },
    ],
  };
  const biAn = vanBanBiAn({ kind: "not_found", message: "", status: 404, detail: { detail } });
  assert.deepEqual(biAn, {
    ma: "khong_hien_thi",
    thong_diep: detail.thong_diep,
    thay_the: [detail.thay_the[0], detail.thay_the[2]],
  });
  assert.equal(laVanBanBiAn(biAn), true, "dữ liệu notFound kiểm lại được ở trang");
  assert.equal(
    vanBanBiAn({ kind: "not_found", message: "", detail: { detail: "Not Found" } }),
    null,
  );
  assert.equal(vanBanBiAn({ kind: "server_error", message: "", detail: { detail } }), null);
  assert.equal(laVanBanBiAn(null), false);
}

// 18. "Bản gốc có chữ ký (PDF)" (quyết định 2026-09-28, mục 9): chỉ một tệp PDF
//     https trên datafiles.chinhphu.vn; ảnh xem trước chỉ đi cùng link đó; vắng
//     hoặc dị dạng → `null`, trang không vẽ gì.
{
  const pdf = "https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/12/145.signed.pdf";
  assert.deepEqual(banGocKy({ link_pdf_ban_ky: pdf, co_anh_xem_truoc: true }), {
    url: pdf,
    coAnh: true,
  });
  assert.deepEqual(banGocKy({ link_pdf_ban_ky: pdf }), { url: pdf, coAnh: false });
  assert.deepEqual(banGocKy({ link_pdf_ban_ky: pdf, co_anh_xem_truoc: "true" }), {
    url: pdf,
    coAnh: false,
  });
  for (const sai of [
    undefined,
    null,
    7,
    "",
    "http://datafiles.chinhphu.vn/cpp/145.signed.pdf",
    "https://datafiles.chinhphu.vn.evil.example/145.pdf",
    "https://user@datafiles.chinhphu.vn/cpp/145.pdf",
    "https://datafiles.chinhphu.vn:8443/cpp/145.pdf",
    "https://datafiles.chinhphu.vn/cpp/1/Logo/quoc-huy.png",
    "https://vanban.chinhphu.vn/?pageid=27160&docid=198540",
    "javascript:alert(1)//.pdf",
  ]) {
    assert.equal(banGocKy({ link_pdf_ban_ky: sai, co_anh_xem_truoc: true }), null, String(sai));
  }
  assert.equal(banGocKy(null), null);
}

// 19. Câu dưới ô tìm kiếm (quyết định 2026-09-28, mục 16): văn bản chưa có toàn
//     văn vẫn được hiện, nên tổng và phần có toàn văn là HAI con số của máy chủ;
//     máy chủ cũ chưa gửi phần kia thì chỉ nói tổng, không bao giờ "N có toàn văn".
{
  assert.equal(
    cauPhamViTimKiem({ tong_van_ban: 481, so_co_toan_van: 372 }),
    "Ô này tìm trong 481 văn bản, trong đó 372 văn bản có toàn văn và tìm được tới từng điều, " +
      "khoản, điểm; 109 văn bản còn lại KLAW chưa có toàn văn nên chỉ tìm được theo tên.",
  );
  assert.equal(
    cauPhamViTimKiem({ tong_van_ban: 12, so_co_toan_van: 12 }),
    "Ô này tìm trong 12 văn bản, văn bản nào cũng có toàn văn.",
  );
  assert.equal(cauPhamViTimKiem({ tong_van_ban: 484 }), "Ô này tìm trong 484 văn bản.");
}

console.info("kiem-trich-dan: 19/19 đạt");
