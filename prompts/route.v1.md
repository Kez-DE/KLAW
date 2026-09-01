Phân loại ý định của câu hỏi sau. Phạm vi hệ thống: 6 Bộ luật của Việt Nam (Dân sự, Hình sự, Tố tụng dân sự, Tố tụng hình sự, Lao động, Hàng hải) và các văn bản hướng dẫn về lao động.

- `tra_cuu`: hỏi về nội dung pháp luật
- `soan_thao`: yêu cầu soạn hoặc soát một văn bản (hợp đồng lao động, nội quy lao động, quyết định kỷ luật)
- `gioi_thieu`: hỏi về CHÍNH TRỢ LÝ này — làm được gì, là ai, hoạt động ra sao, dữ liệu lấy từ đâu, có tin được không; hoặc chỉ chào hỏi
- `ngoai_pham_vi`: câu hỏi pháp luật nhưng rõ ràng không thuộc phạm vi (thuế, đất đai, hôn nhân gia đình, doanh nghiệp…)

Nếu không chắc, chọn `tra_cuu`.

Trả về JSON: {{"intent": "tra_cuu"}}

CÂU HỎI: {cau_hoi}
