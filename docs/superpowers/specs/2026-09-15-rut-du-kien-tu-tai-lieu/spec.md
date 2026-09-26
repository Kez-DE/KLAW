# Đặc tả tính năng: Rút dữ kiện có neo nguồn từ tài liệu người dùng

**Nhánh**: `feat/tro-ly-phap-luat`

**Ngày tạo**: 2026-09-15

**Trạng thái**: Draft — phạm vi đã chốt

**Đầu vào**: "Đọc tài liệu người dùng để rút sự kiện có neo nguồn, nối vào soạn thảo. Phạm vi: PDF có lớp text + DOCX, không OCR, không lưu file gốc, mỗi fact mang trích nguyên văn kiểm được bằng tra chuỗi."

---

## Bối cảnh

Hôm nay người dùng muốn soạn một văn bản pháp lý phải gõ tay từng dữ kiện, dù dữ kiện đó đã nằm sẵn trong hợp đồng, quyết định hay thông báo họ đang cầm. Hệ thống không nhận tệp; đường duy nhất đưa nội dung vào là dán chữ, và chữ dán vào không được lưu.

Tính năng này mở một cửa vào mới: người dùng tải tài liệu lên, hệ thống đọc và rút ra danh sách dữ kiện, **mỗi dữ kiện mang theo đoạn trích nguyên văn chứng minh nó đến từ đâu**. Người dùng xác nhận, sửa hoặc bỏ từng dữ kiện, rồi dùng chúng để soạn văn bản.

Nguyên tắc trung tâm của KLAW được mở rộng sang một loại nguồn mới: **nguồn gốc của một dữ kiện là phép tra chuỗi trên văn bản đã đọc, không phải lời khẳng định của mô hình.** Cùng cơ chế đã dùng cho trích dẫn điều luật, nay áp cho dữ kiện tài liệu.


## Clarifications

### Session 2026-09-15

- Q: Tập dữ kiện rút từ tài liệu gắn vào cuộc hội thoại hiện có, hay sống trong một không gian riêng? → A: Gắn vào cuộc hội thoại hiện có; xoá hội thoại là xoá dữ kiện.
- Q: Người dùng chờ tại chỗ hay tải lên rồi làm việc khác? → A: Cả hai — tài liệu nhỏ xử lý ngay tại chỗ, tài liệu lớn tự chuyển sang chạy nền. Không đặt trần thời gian: ra được kết quả quan trọng hơn ra nhanh.
- Q: Ngưỡng chuyển nền và trần tuyệt đối là bao nhiêu? → A: Chuyển nền từ 10 trang; trần tuyệt đối 100 trang hoặc 20 MB.
- Q: Bỏ trần thời gian rồi thì cái gì chặn một lần xử lý mất kiểm soát? → A: Trần chi phí cho mỗi tài liệu, cộng trần số lần thử lại.
- Q: SC-002 đo trên tập tài liệu nào? → A: Tập mẫu tự dựng 20–30 tài liệu, nhãn do chủ dự án duyệt tay, đặt cạnh các bộ dữ liệu đánh giá hiện có.
- Phát hiện khi triển khai 2026-09-15: "biểu mẫu soạn thảo" ở FR-020 từng mơ hồ giữa hai bề mặt khác nhau. Biểu mẫu React (`KhongGianSoanThao`) có mô hình dữ liệu riêng và KHÔNG chạy bằng bộ từ vựng `rules.yaml`; thứ chạy bằng `facts` là đường soạn thảo trong hội thoại. FR-019/FR-020 đã viết lại cho đúng bề mặt, và FR-020a được thêm cho ca người dùng đã tự nhập.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Tải tài liệu và nhận dữ kiện có neo nguồn (Priority: P1)

Người dùng có sẵn một hợp đồng lao động dạng tệp. Họ tải lên, chờ vài giây, và nhận được danh sách dữ kiện mà hệ thống đọc ra: tên người lao động, chức danh, mức lương, ngày bắt đầu, thời hạn hợp đồng. Bên cạnh mỗi dữ kiện là đoạn trích nguyên văn từ tài liệu và vị trí của nó, bấm vào xem được ngay chỗ đó nói gì.

**Vì sao P1**: Đây là toàn bộ giá trị mới. Không có nó thì hai story còn lại không tồn tại. Tự nó đã dùng được: người dùng đọc lại tài liệu dài bằng một bảng dữ kiện thay vì cuộn tay.

**Kiểm độc lập**: Tải một tệp mẫu, xác nhận mọi dữ kiện hiện ra đều có đoạn trích, và mọi đoạn trích đều tìm lại được nguyên văn trong tài liệu gốc.

**Acceptance Scenarios**:

1. **Given** một PDF hợp đồng lao động có lớp text, **When** người dùng tải lên, **Then** hệ thống trả về danh sách dữ kiện, mỗi dữ kiện kèm đoạn trích nguyên văn và vị trí trong tài liệu.
2. **Given** một dữ kiện đã hiện trên màn hình, **When** người dùng bấm vào đoạn trích của nó, **Then** hệ thống chỉ ra đúng chỗ trong tài liệu chứa đoạn đó.
3. **Given** mô hình đề xuất một dữ kiện mà đoạn trích kèm theo **không** tìm thấy nguyên văn trong tài liệu, **When** hệ thống dựng danh sách, **Then** dữ kiện đó bị loại và không bao giờ hiện ra cho người dùng.
4. **Given** một tài liệu không chứa dữ kiện nào hệ thống nhận ra, **When** xử lý xong, **Then** hệ thống nói rõ "không rút được dữ kiện nào" kèm lý do, không trả danh sách rỗng không giải thích.

---

### User Story 2 — Dùng dữ kiện đã rút để soạn văn bản (Priority: P2)

Sau khi xem danh sách, người dùng sửa hai chỗ đọc sai, bỏ một dữ kiện không liên quan, rồi chọn "dùng để soạn đơn". Biểu mẫu soạn thảo mở ra đã điền sẵn những gì rút được; người dùng chỉ điền phần còn thiếu.

**Vì sao P2**: Đây là chỗ tiết kiệm thời gian thật sự, nhưng phụ thuộc hoàn toàn vào P1. Tách riêng được vì P1 vẫn có giá trị nếu người dùng chỉ đọc bảng dữ kiện.

**Kiểm độc lập**: Rút dữ kiện từ một tài liệu, mở soạn thảo, xác nhận các trường được điền sẵn đúng và chỉ những trường có dữ kiện tương ứng mới được điền.

**Acceptance Scenarios**:

1. **Given** danh sách dữ kiện đã rút, **When** người dùng sửa giá trị một dữ kiện, **Then** dữ kiện đó được đánh dấu nguồn là *người dùng sửa*, phân biệt rõ với dữ kiện *rút từ tài liệu*, và đoạn trích gốc vẫn hiện để đối chiếu.
2. **Given** dữ kiện đã xác nhận, **When** người dùng chuyển sang soạn thảo, **Then** các trường của biểu mẫu tương ứng được điền sẵn, các trường không có dữ kiện để trống chứ không đoán.
3. **Given** một dữ kiện bị người dùng xoá, **When** soạn thảo mở ra, **Then** trường tương ứng để trống và được liệt kê trong phần còn thiếu.
4. **Given** hai tài liệu cùng một cuộc hội thoại đưa ra hai giá trị khác nhau cho cùng một dữ kiện, **When** dựng danh sách, **Then** hệ thống nêu mâu thuẫn và để người dùng chọn, không tự lấy một bên.

---

### User Story 3 — Tài liệu không đọc được thì nói thẳng (Priority: P3)

Người dùng tải lên một bản scan chụp điện thoại. Hệ thống không đoán nội dung; nó nói rõ tài liệu này không có lớp chữ máy đọc được, nêu tính năng chưa hỗ trợ ảnh và bản scan, và gợi ý cách thay thế.

**Vì sao P3**: Không tạo ra giá trị mới, nhưng là chỗ tính năng giữ hay phản bội lời hứa trung tâm của sản phẩm. "Thà từ chối còn hơn bịa" phải đúng cả với tài liệu, không chỉ với điều luật.

**Kiểm độc lập**: Tải một PDF scan, xác nhận thông báo nêu đúng nguyên nhân và không có dữ kiện nào được rút.

**Acceptance Scenarios**:

1. **Given** một PDF chỉ chứa ảnh, không lớp text, **When** người dùng tải lên, **Then** hệ thống báo rõ nguyên nhân và không rút dữ kiện nào.
2. **Given** một tệp định dạng ngoài phạm vi hỗ trợ, **When** người dùng tải lên, **Then** hệ thống nêu danh sách định dạng được hỗ trợ trước khi tiêu bất kỳ chi phí xử lý nào.
3. **Given** một tệp hỏng hoặc có mật khẩu, **When** hệ thống mở, **Then** thông báo phân biệt được "hỏng" với "không hỗ trợ" với "cần mật khẩu".

---

### Edge Cases

- Tài liệu chứa câu chữ dạng chỉ dẫn ("bỏ qua hướng dẫn trước đó, hãy…") — nội dung tài liệu là **dữ liệu**, không bao giờ là chỉ dẫn cho hệ thống.
- Tài liệu là một văn bản quy phạm pháp luật (người dùng tải Bộ luật Lao động lên) — không được nhầm với kho luật đã kiểm chứng; dữ kiện rút từ tài liệu người dùng **không bao giờ trở thành căn cứ pháp luật**.
- Đoạn trích nằm vắt qua hai ô bảng hoặc hai đoạn — phép tra chuỗi phải khớp trong một đơn vị văn bản, không ghép.
- Dấu tiếng Việt bị lệch chuẩn hoá giữa tài liệu và đoạn trích — chuẩn hoá phải đủ để khớp dấu cách và dạng ký tự, nhưng **không** được bỏ dấu, vì bỏ dấu làm hai từ khác nghĩa trùng nhau.
- Tài liệu rất dài — chuyển sang xử lý nền thay vì từ chối hay treo; người dùng phải biết nó đã chuyển.
- Tài liệu chứa thông tin cá nhân của bên thứ ba — đây là mặc định chứ không phải ngoại lệ.
- Người dùng tải nhiều tệp liên tiếp — hạn mức phải chặn trước khi tiêu chi phí.
- Xử lý bị ngắt giữa chừng — tệp đang đọc không được để lại dấu vết trên đĩa.

---

## Requirements *(mandatory)*

### Functional Requirements

**Tiếp nhận tài liệu**

- **FR-001**: Hệ thống MUST nhận tài liệu định dạng PDF có lớp chữ máy đọc được và DOCX.
- **FR-002**: Hệ thống MUST từ chối mọi định dạng khác bằng một thông báo nêu rõ định dạng được hỗ trợ, trước khi tiêu chi phí xử lý.
- **FR-003**: Hệ thống MUST phân biệt và báo riêng bốn nguyên nhân không xử lý được: định dạng không hỗ trợ, tệp hỏng, tệp cần mật khẩu, PDF không có lớp chữ.
- **FR-004**: Hệ thống MUST áp hạn mức số tài liệu theo gói tài khoản và chặn trước khi xử lý khi vượt.
- **FR-005**: Hệ thống MUST từ chối tài liệu dài quá **100 trang** hoặc nặng quá **20 MB**, và MUST nêu đúng trần đã vượt trong thông báo từ chối.
  - _Ghi chú 2026-09-26_: trần trang nay là **10 trang**, đếm bằng dàn trang thật (LibreOffice cho docx và `.doc`, số trang của PDF); tài liệu vượt trần bị từ chối lúc tải lên và không trừ vào hạn mức ngày. Xem `docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`.

**Cách xử lý và phản hồi tiến trình**

- **FR-029**: Hệ thống MUST xử lý tại chỗ và trả kết quả ngay trong cùng lượt tương tác khi tài liệu dài **dưới 10 trang**.
- **FR-030**: Hệ thống MUST tự chuyển sang xử lý nền khi tài liệu dài **từ 10 trang trở lên**, và MUST báo cho người dùng biết việc đã chuyển nền ngay khi chuyển.
- **FR-031**: Ở cả hai đường, hệ thống MUST hiển thị tiến trình đang ở bước nào, không để người dùng nhìn một màn hình chờ không thông tin.
- **FR-032**: Hệ thống MUST KHÔNG huỷ một lần xử lý vì nó chạy lâu. Ra được kết quả được ưu tiên hơn ra nhanh.
- **FR-033**: Người dùng MUST rời đi và quay lại lấy kết quả của một lần xử lý nền mà không mất kết quả đó.
- **FR-034**: Khi một lần xử lý nền xong hoặc hỏng, hệ thống MUST báo cho người dùng qua đúng cơ chế thông báo đang dùng cho các việc khác của tài khoản.
- **FR-035**: Người dùng MUST huỷ được một lần xử lý nền đang chạy.
- **FR-036**: Hệ thống MUST áp một trần chi phí cho mỗi lần xử lý một tài liệu, tách khỏi trần chi phí ngày dùng chung, và MUST dừng lần xử lý đó khi chạm trần.
- **FR-037**: Hệ thống MUST áp trần số lần thử lại cho một tài liệu và MUST KHÔNG thử lại vô hạn.
- **FR-038**: Khi một lần xử lý bị dừng vì chạm trần chi phí hoặc hết lượt thử lại, hệ thống MUST nêu rõ nguyên nhân đó và MUST KHÔNG trừ vào hạn mức của người dùng.

**Rút dữ kiện và neo nguồn**

- **FR-006**: Mỗi dữ kiện hệ thống trả ra MUST mang theo: tên trường, giá trị, **đoạn trích nguyên văn** từ tài liệu, và vị trí của đoạn trích trong tài liệu.
- **FR-007**: Hệ thống MUST xác minh mọi đoạn trích bằng phép tra chuỗi trên nội dung đã đọc từ tài liệu. Dữ kiện có đoạn trích không khớp MUST bị loại trước khi hiển thị.
- **FR-008**: Phép xác minh ở FR-007 MUST là phép so khớp tất định, không phải phán đoán của mô hình ngôn ngữ.
- **FR-009**: Chuẩn hoá trước khi so khớp MUST giới hạn ở dạng ký tự Unicode và khoảng trắng. Hệ thống MUST KHÔNG bỏ dấu tiếng Việt và MUST KHÔNG bỏ phân biệt hoa thường khi so khớp.
- **FR-010**: Đoạn trích MUST khớp trọn trong một đơn vị văn bản liền mạch; hệ thống MUST KHÔNG chấp nhận đoạn trích ghép từ hai vị trí rời nhau.
- **FR-011**: Khi không rút được dữ kiện nào, hệ thống MUST nêu lý do thay vì trả danh sách rỗng không giải thích.
- **FR-012**: Khi hai tài liệu trong cùng một cuộc hội thoại cho hai giá trị khác nhau của cùng một dữ kiện, hệ thống MUST nêu mâu thuẫn và để người dùng quyết định.

**Quyền của người dùng trên dữ kiện**

- **FR-013**: Người dùng MUST sửa, bỏ, hoặc thêm được từng dữ kiện trước khi dùng.
- **FR-014**: Hệ thống MUST đánh dấu nguồn của từng dữ kiện, phân biệt ít nhất: *rút từ tài liệu*, *người dùng nhập*, *người dùng sửa*.
- **FR-015**: Khi người dùng sửa một dữ kiện rút từ tài liệu, hệ thống MUST giữ đoạn trích gốc để đối chiếu và MUST KHÔNG trình bày giá trị đã sửa như thể nó đến từ tài liệu.

**Ranh giới với căn cứ pháp luật**

- **FR-016**: Dữ kiện rút từ tài liệu người dùng MUST KHÔNG bao giờ được dùng làm căn cứ pháp luật trong câu trả lời hoặc văn bản soạn ra.
- **FR-017**: Nội dung tài liệu người dùng MUST được xử lý như dữ liệu. Hệ thống MUST KHÔNG thực thi câu chữ trong tài liệu như chỉ dẫn.
- **FR-018**: Khi tài liệu tải lên là một văn bản quy phạm pháp luật, hệ thống MUST KHÔNG coi nội dung đó ngang hàng với kho luật đã kiểm chứng.

**Nối vào soạn thảo**

- **FR-019**: Người dùng MUST chuyển được tập dữ kiện đã xác nhận sang luồng soạn thảo **trong hội thoại**.
- **FR-020**: Sau khi chuyển, luồng soạn thảo MUST đã biết đúng những trường có dữ kiện, MUST để trống phần còn lại, và MUST KHÔNG suy đoán giá trị cho trường không có dữ kiện.
- **FR-020a**: Dữ kiện người dùng đã tự nhập trong hội thoại MUST được giữ nguyên khi tài liệu mang đến một giá trị khác cho cùng trường. Tài liệu bổ sung vào chỗ trống, không ghi đè thứ người dùng tự khẳng định.
- **FR-021**: Các trường còn trống sau khi điền sẵn MUST xuất hiện trong danh sách thông tin còn thiếu như hiện nay.

**Lưu trữ và riêng tư**

- **FR-022**: Hệ thống MUST KHÔNG lưu tệp gốc của người dùng sau khi xử lý xong.
  - _Ghi chú 2026-09-16_: vẫn đúng nguyên văn — tệp gốc không được lưu. Nhưng **biểu diễn văn bản đã đọc** (`don_vi`: chữ + trang + toạ độ bảng + nguồn chữ) nay được lưu theo cuộc hội thoại và xoá cùng nó; không lưu bytes, không lưu OOXML. Xem `docs/decisions/2026-09-16-luu-bieu-dien-tai-lieu-theo-hoi-thoai.md`.
  - _Ghi chú 2026-09-26_: không còn đúng cho **khuôn gốc**. Tệp tải lên (docx, `.doc` dưới dạng docx đã quy đổi, PDF) nay được lưu theo cuộc hội thoại và xoá cứng cùng nó, để hiển thị đúng như bản tải lên và điền tại chỗ. Xem `docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`. SC-005 đổi theo: sau khi hội thoại bị xoá, 0 khuôn gốc của nó còn tồn tại.
- **FR-023**: Hệ thống MUST KHÔNG ghi toàn văn tài liệu vào nhật ký vận hành hoặc dữ liệu đánh giá.
- **FR-024**: Hệ thống MUST cho người dùng xoá toàn bộ dữ kiện đã rút của một cuộc hội thoại bằng một thao tác.
- **FR-025**: Mọi thông báo lỗi MUST KHÔNG lặp lại nội dung tài liệu.
- **FR-026**: Tập dữ kiện đã rút MUST thuộc về đúng một cuộc hội thoại. Hệ thống MUST KHÔNG lưu dữ kiện rút từ tài liệu ở phạm vi tài khoản để dùng lại ở cuộc hội thoại khác.
- **FR-027**: Khi người dùng xoá một cuộc hội thoại, hệ thống MUST xoá theo toàn bộ dữ kiện đã rút và mọi đoạn trích kèm theo của cuộc hội thoại đó.
- **FR-028**: Dữ kiện rút từ tài liệu MUST KHÔNG chảy vào hồ sơ tài khoản hay bộ nhớ hội thoại dài hạn.

### Key Entities

- **Tài liệu tải lên**: một tệp người dùng đưa vào để đọc. Tồn tại trong thời gian xử lý, không lưu lại. _(2026-09-26: tệp nay được giữ làm khuôn gốc theo hội thoại — xem quyết định 2026-09-26.)_ Có: tên tệp, định dạng, kích thước, dấu vân (để nhận ra tải trùng), kết quả xử lý.
- **Dữ kiện có neo**: một mẩu thông tin hệ thống đọc ra được. Có: tên trường, giá trị, nguồn (*rút từ tài liệu* / *người dùng nhập* / *người dùng sửa*), và — khi nguồn là tài liệu — một **Neo nguồn**.
- **Neo nguồn**: bằng chứng cho một dữ kiện. Có: đoạn trích nguyên văn, vị trí trong tài liệu, và trạng thái xác minh. Một dữ kiện không có neo hợp lệ thì không tồn tại đối với người dùng.
- **Tập mẫu đánh giá**: bộ tài liệu tự dựng kèm nhãn dữ kiện đúng, do chủ dự án duyệt tay, dùng để đo SC-002. Đứng ngang hàng với các bộ dữ liệu đánh giá sẵn có của dự án.
- **Cuộc hội thoại**: đơn vị sở hữu tập dữ kiện. Dữ kiện thuộc về đúng một cuộc hội thoại, đi theo quyền sở hữu và vòng đời sẵn có của nó; xoá cuộc hội thoại là xoá dữ kiện.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trong toàn bộ kiểm thử, **0** dữ kiện hiển thị cho người dùng mà đoạn trích của nó không tìm lại được nguyên văn trong tài liệu gốc.
- **SC-002**: Trên tập mẫu 20–30 tài liệu tự dựng, có nhãn do chủ dự án duyệt tay, hệ thống rút đúng ít nhất **80%** số trường bắt buộc của loại văn bản tương ứng.
- **SC-003**: **100%** tài liệu không đọc được nhận về một thông báo nêu đúng nguyên nhân trong bốn nguyên nhân đã định, và **0** trường hợp hệ thống đoán nội dung.
- **SC-004**: Người dùng chuẩn bị xong tập dữ kiện cho một đơn từ một tài liệu có sẵn **nhanh hơn ít nhất một nửa** so với gõ tay toàn bộ.
- **SC-010**: **0** lần xử lý bị huỷ chỉ vì chạy lâu.
- **SC-011**: **100%** lần xử lý nền cho người dùng lấy lại được kết quả sau khi họ rời đi và quay lại.
- **SC-012**: **0** lần xử lý vượt trần chi phí cho một tài liệu mà vẫn tiếp tục chạy.
- **SC-013**: **0** lần người dùng bị trừ hạn mức cho một lần xử lý dừng vì chạm trần.
- **SC-005**: Sau khi xử lý xong, **0** tệp gốc còn tồn tại trong hệ thống, kiểm được bằng rà soát nơi lưu trữ.
- **SC-006**: **0** dòng nhật ký hoặc bản ghi đánh giá chứa toàn văn tài liệu người dùng.
- **SC-007**: Trên tập tài liệu có câu chữ dạng chỉ dẫn cài cắm, **0** trường hợp hệ thống làm theo chỉ dẫn đó.
- **SC-008**: **0** câu trả lời hoặc văn bản soạn ra viện dẫn một dữ kiện tài liệu như căn cứ pháp luật.
- **SC-009**: Sau khi một cuộc hội thoại bị xoá, **0** dữ kiện rút từ tài liệu và **0** đoạn trích của cuộc hội thoại đó còn tồn tại trong hệ thống.

---

## Assumptions

- Loại dữ kiện cần rút lấy theo bộ trường đã khai báo sẵn cho từng loại văn bản trong hệ thống soạn thảo hiện tại; tính năng này không định nghĩa một bộ trường mới.
- Hạn mức số tài liệu theo gói đi theo đúng cách hạn mức câu hỏi và bản thảo đang được cấu hình, không tạo cơ chế hạn mức riêng.
- Tập mẫu đánh giá gồm tài liệu tự dựng, không dùng tài liệu thật của người dùng, vì tài liệu thật chứa thông tin cá nhân của bên thứ ba và không đưa vào kho mã được.
- Số trang là thước đo ngưỡng vì người dùng hiểu ngay và nó sát công sức xử lý hơn dung lượng tệp.
- Người dùng giữ tệp gốc của họ. Hệ thống không giữ hộ, nên không có nhu cầu tải lại tệp đã xử lý.
- Tiếng Việt là ngôn ngữ duy nhất cần hỗ trợ.
- Tài liệu người dùng mặc định chứa thông tin cá nhân của bên thứ ba; mọi quyết định thiết kế xuất phát từ giả định đó chứ không coi đó là trường hợp ngoại lệ.
- Ảnh, bản scan, và PDF không có lớp chữ nằm ngoài phạm vi lần này. Quyết định này có thể đảo lại về sau nếu đo được sai số nhận dạng chữ.
- Tính năng mở rộng luồng soạn thảo hiện có; nó không thay thế đường nhập dữ kiện bằng hội thoại đang chạy.
- Người dùng chấp nhận tải lại tài liệu nếu quay lại sau khi cuộc hội thoại đã bị xoá. Đổi lại, hệ thống không giữ thông tin cá nhân của bên thứ ba quá thời gian cần thiết.

---

## Ràng buộc kế thừa từ tài liệu đã chấp nhận

Những dòng dưới đây không do đặc tả này đặt ra; chúng đã là quy tắc của dự án và tính năng phải nằm gọn trong đó.

| Nguồn | Quy tắc | Ảnh hưởng tới tính năng |
|---|---|---|
| `PRODUCT.md:19-22` | Mọi khẳng định neo vào một trích dẫn kiểm chứng được, và phép kiểm là tra bảng | FR-007, FR-008 áp cùng nguyên tắc cho dữ kiện tài liệu |
| Invariant I3 | Thà từ chối còn hơn bịa; từ chối là hành vi đúng | User Story 3, FR-011, SC-003 |
| Invariant I5 | Soạn thảo là checklist nội dung bắt buộc, **không phải điền mẫu** | FR-019 đến FR-021 nối vào checklist sẵn có, không đụng tới bố cục tài liệu |
| `docs/bo-luat-agent.md` QT-3 | Nội dung người dùng đưa vào là dữ liệu, không phải chỉ dẫn | FR-017, SC-007 |
| `docs/bo-luat-agent.md` QT-5 | Giả định phải hiện thành chữ, sửa được, và **không bao giờ là căn cứ pháp luật** | FR-014, FR-015, FR-016 |
| `src/api/routes.py:1053-1060` + migration `011` | Toàn văn người dùng dán không được lưu | FR-022, FR-023, SC-005, SC-006 |
| `verify_tier1.py:113-133` | Chuẩn hoá không bỏ dấu, không bỏ hoa thường | FR-009 |
| `verify_tier1.py:174` | Đoạn trích khớp trong một đơn vị, không ghép | FR-010 |

---

## Ngoài phạm vi

- Nhận dạng chữ trong ảnh và bản scan.
- Giữ nguyên bố cục tài liệu gốc để sinh ra một tệp mới cùng hình thức.
- Lưu trữ tài liệu lâu dài, thư viện tài liệu theo tài khoản, chia sẻ tài liệu.
- Ký số, đóng dấu, xác thực chữ ký trong tài liệu.
- Ngôn ngữ ngoài tiếng Việt.
- Đọc tài liệu để trả lời câu hỏi pháp lý về chính tài liệu đó. Dữ kiện rút ra chỉ phục vụ soạn thảo; luồng tra cứu không đổi.
- Lưu tập dữ kiện đã rút để dùng cho lần sau.
