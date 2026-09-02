Soạn {loai_van_ban} theo pháp luật lao động Việt Nam, dựa trên các thông tin và điều luật dưới đây.

Với MỖI điều khoản bạn viết:
- `key`: mã mục nội dung bắt buộc mà nó đáp ứng (lấy từ danh sách DANH MỤC MỤC)
- `can_cu_provision_id`: provision_id của điều luật là căn cứ, lấy đúng từ ĐIỀU LUẬT
- `noi_dung`: nội dung điều khoản, viết bằng văn phong hợp đồng

Không thêm điều khoản trái pháp luật. Không tự đặt mức thấp hơn mức tối thiểu luật định.

Phần ĐIỀU LUẬT gộp theo văn bản: mỗi văn bản mở đầu bằng một dòng `VĂN BẢN so_ky_hieu=… loai_van_ban=…`, dưới đó là từng điều khoản kèm `provision_id`, `duong_dan` và `hieu_luc`. `hieu_luc` và `loai_van_ban` CHỈ để chọn nguồn khi hai điều khoản nói khác nhau — ưu tiên `con_hieu_luc`, rồi tới văn bản cấp cao hơn. Ngoài việc đó chúng không có tác dụng nào: `mot_phan_khong_xac_dinh` và `chua_xac_dinh` vẫn dùng làm căn cứ bình thường, và TUYỆT ĐỐI KHÔNG viết bất kỳ câu nào về hiệu lực vào `noi_dung` — không nói điều luật còn hay hết hiệu lực, bị thay thế hay bị sửa đổi. Một hợp đồng khẳng định căn cứ của nó "còn hiệu lực" là một khẳng định hệ thống chưa kiểm ở cấp điều khoản, và nó đứng trong văn bản người ta đem đi ký.

Trả về JSON: {{"clauses": [{{"key": "...", "ten": "...", "noi_dung": "...", "can_cu_provision_id": 0}}]}}

THÔNG TIN: {facts}
DANH MỤC MỤC: {muc}
ĐIỀU LUẬT: {context}
