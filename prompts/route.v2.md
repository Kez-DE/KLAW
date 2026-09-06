Phân loại ý định của câu hỏi sau. Phạm vi hệ thống: 6 Bộ luật của Việt Nam (Dân sự, Hình sự, Tố tụng dân sự, Tố tụng hình sự, Lao động, Hàng hải) và các văn bản hướng dẫn về lao động, cộng luật gốc của Đất đai, Kinh doanh bất động sản, Hôn nhân gia đình, Doanh nghiệp/Đầu tư/Thương mại, Sở hữu trí tuệ, Thuế, Tố tụng hành chính, Xử lý vi phạm hành chính (kho mở rộng 2026-09-02, T1 — các lĩnh vực này hiện chỉ có luật gốc, chưa có nghị định/thông tư hướng dẫn).

- `tra_cuu`: hỏi về nội dung pháp luật
- `soan_thao`: yêu cầu soạn hoặc soát một văn bản (hợp đồng lao động, nội quy lao động, quyết định kỷ luật)
- `gioi_thieu`: hỏi về CHÍNH TRỢ LÝ này — làm được gì, là ai, hoạt động ra sao, dữ liệu lấy từ đâu, có tin được không; hoặc chỉ chào hỏi
- `hoi_ve_kho`: hỏi về CHÍNH KHO VĂN BẢN — kho có những văn bản nào, bao nhiêu văn bản hay bao nhiêu bộ luật, phủ tới đâu, có văn bản X hay số hiệu X không. Phân biệt với `tra_cuu`: `tra_cuu` hỏi luật QUY ĐỊNH GÌ, `hoi_ve_kho` hỏi kho CÓ GÌ. "Bộ luật Lao động quy định gì về thử việc" là `tra_cuu`; "kho có Bộ luật Lao động không" là `hoi_ve_kho`. Nêu số hiệu KHÔNG làm câu hỏi thành `hoi_ve_kho`: "nghị định 90/2019 quy định mức lương tối thiểu vùng hai là bao nhiêu" hỏi NỘI DUNG nên là `tra_cuu`, dù có cả số hiệu lẫn chữ "bao nhiêu"
- `ngoai_pham_vi`: câu hỏi pháp luật nhưng rõ ràng không thuộc phạm vi (giáo dục, môi trường, xây dựng, ngân hàng…)

Nếu không chắc, chọn `tra_cuu`.

Khi ý định là `soan_thao`, chọn thêm `loai_van_ban` — mã của loại văn bản người
hỏi cần, lấy ĐÚNG một mã trong danh sách dưới (mỗi dòng: mã — tên). Nêu `ly_do`
một câu ngắn bằng lời thường, nói vì sao loại đó khớp với điều họ mô tả (ai lập,
gửi cho ai, mục đích), không dẫn số Điều. `ly_do` nói với chính người hỏi, gọi
họ là "bạn", một câu, không mở đầu bằng "Người dùng" hay "Yêu cầu". Nếu hai
hoặc ba loại cùng hợp, đặt loại
hợp nhất vào `loai_van_ban` và tối đa hai loại còn lại vào `thay_the`. Không chắc
loại nào thì `loai_van_ban` là `khong_ro` và `thay_the` là các loại gần nhất.
Với mọi ý định khác `soan_thao`: `loai_van_ban` là `khong_ro`, `thay_the` rỗng,
`ly_do` rỗng.

Ví dụ: "hợp đồng nghỉ việc" do người lao động tự viết → `don_xin_nghi_viec`,
thay thế `thoa_thuan_cham_dut_hdld`; "hai bên thoả thuận nghỉ" →
`thoa_thuan_cham_dut_hdld`; "công ty ra quyết định cho nghỉ" →
`quyet_dinh_cham_dut_hdld`.

DANH SÁCH LOẠI VĂN BẢN:
{danh_sach_loai}

Trả về JSON: {{"intent": "soan_thao", "loai_van_ban": "don_xin_nghi_viec", "thay_the": ["thoa_thuan_cham_dut_hdld"], "ly_do": "bạn là người lao động muốn tự chấm dứt hợp đồng, nên đơn xin nghỉ việc là loại khớp nhất"}}

CÂU HỎI: {cau_hoi}
