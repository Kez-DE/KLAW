Phân loại ý định của câu hỏi sau. Phạm vi hệ thống: 6 Bộ luật của Việt Nam (Dân sự, Hình sự, Tố tụng dân sự, Tố tụng hình sự, Lao động, Hàng hải) và các văn bản hướng dẫn về lao động.

- `tra_cuu`: hỏi về nội dung pháp luật
- `soan_thao`: yêu cầu soạn hoặc soát một văn bản (hợp đồng lao động, nội quy lao động, quyết định kỷ luật)
- `gioi_thieu`: hỏi về CHÍNH TRỢ LÝ này — làm được gì, là ai, hoạt động ra sao, dữ liệu lấy từ đâu, có tin được không; hoặc chỉ chào hỏi
- `hoi_ve_kho`: hỏi về CHÍNH KHO VĂN BẢN — kho có những văn bản nào, bao nhiêu văn bản hay bao nhiêu bộ luật, phủ tới đâu, có văn bản X hay số hiệu X không. Phân biệt với `tra_cuu`: `tra_cuu` hỏi luật QUY ĐỊNH GÌ, `hoi_ve_kho` hỏi kho CÓ GÌ. "Bộ luật Lao động quy định gì về thử việc" là `tra_cuu`; "kho có Bộ luật Lao động không" là `hoi_ve_kho`. Nêu số hiệu KHÔNG làm câu hỏi thành `hoi_ve_kho`: "nghị định 90/2019 quy định mức lương tối thiểu vùng hai là bao nhiêu" hỏi NỘI DUNG nên là `tra_cuu`, dù có cả số hiệu lẫn chữ "bao nhiêu"
- `ngoai_pham_vi`: câu hỏi pháp luật nhưng rõ ràng không thuộc phạm vi (thuế, đất đai, hôn nhân gia đình, doanh nghiệp…)

Nếu không chắc, chọn `tra_cuu`.

Trả về JSON: {{"intent": "tra_cuu"}}

CÂU HỎI: {cau_hoi}
