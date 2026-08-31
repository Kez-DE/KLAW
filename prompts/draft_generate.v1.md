Soạn {loai_van_ban} theo pháp luật lao động Việt Nam, dựa trên các thông tin và điều luật dưới đây.

Với MỖI điều khoản bạn viết:
- `key`: mã mục nội dung bắt buộc mà nó đáp ứng (lấy từ danh sách DANH MỤC MỤC)
- `can_cu_provision_id`: provision_id của điều luật là căn cứ, lấy đúng từ ĐIỀU LUẬT
- `noi_dung`: nội dung điều khoản, viết bằng văn phong hợp đồng

Không thêm điều khoản trái pháp luật. Không tự đặt mức thấp hơn mức tối thiểu luật định.

Trả về JSON: {{"clauses": [{{"key": "...", "ten": "...", "noi_dung": "...", "can_cu_provision_id": 0}}]}}

THÔNG TIN: {facts}
DANH MỤC MỤC: {muc}
ĐIỀU LUẬT: {context}
