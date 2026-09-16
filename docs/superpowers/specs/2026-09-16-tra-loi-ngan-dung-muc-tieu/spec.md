# Đặc tả tính năng: Câu trả lời ngắn, đúng mục tiêu (GĐ0 + GĐ1)

**Feature Branch**: `feat/tro-ly-phap-luat`

**Created**: 2026-09-16

**Status**: Draft

**Input**: GĐ0+GĐ1 của `cai_thien.md` — baseline hợp lệ có metadata trên model
deepseek; chọn prompt hành văn giữa `assemble.v3/v4/v5`; kỷ luật độ dài 900 ký tự
cho `answer` và 160 cho `coverage_note`, cưỡng chế bằng phép kiểm 0 token; đuôi hỏi
thêm chỉ còn khi lượt vừa tạo giả định mới; sửa nhận diện lượt đầu dùng
`lich_su or tom_tat`; tách `make check` khỏi `format` và lane test khỏi
`integration`/`pending_review`.

## Bối cảnh

Người hỏi nhận được câu trả lời đúng luật nhưng đọc như một bản tra cứu: 10–21 trích
dẫn, 1.600–3.400 ký tự, ý lặp, và một câu hỏi bổ sung gắn vào gần như mọi lượt bất kể
dữ kiện đó có làm đổi kết luận hay không. Ba nguyên nhân đã xác định trong repo:

1. `assemble` nhận mọi luận điểm đã qua kiểm chứng, không lọc theo mục tiêu người hỏi.
2. Đuôi hỏi thêm chọn trong ba trường cố định (vai, loại hợp đồng, thời điểm), không
   biết trường đó có làm đổi kết luận không.
3. Nhận diện lượt đầu chỉ xét lịch sử hội thoại, nên một phiên đã có tóm tắt vẫn bị
   chào lại như người lạ.

Đợt này KHÔNG sửa khả năng tìm căn cứ. Nó sửa cách chọn và cách nói, và trước hết
dựng một mốc đo hợp lệ để biết bản sửa tốt hơn hay tệ hơn.

## Clarifications

### Phiên 2026-09-16

- Phạm vi: chỉ GĐ0 + GĐ1 của `cai_thien.md`. GĐ2–GĐ5 để đợt sau.
- Model ghim cho mọi lượt đo: `deepseek/deepseek-v4-flash-0731` cho vai chính và vai
  generate; `mistralai/mistral-small-3.2-24b-instruct` giữ vai judge (ràng buộc
  "verify khác họ với generate" trong `.env.local` vẫn đúng).
- Bộ đo: 77 câu vàng đã có (`eval/datasets/golden_qa.yaml`) + 57 bẫy + 20 câu mơ hồ.
  Bộ `chat_quality` 40 ca thuộc đợt sau, không chặn đợt này.
- So ba prompt `assemble.v3` / `v4` / `v5`, không chỉ v3 với v5: v4 đã tồn tại và đã
  có tầng "điều gì làm đổi kết luận".
- Giới hạn 900 ký tự áp cho `answer`; `coverage_note` có giới hạn riêng 160 ký tự;
  bảng không tính vào hai giới hạn này.
- Đuôi hỏi thêm không bị xoá hẳn: nó chỉ còn xuất hiện khi chính lượt đó vừa tạo một
  giả định mới, và phải hỏi đúng trường vừa giả định.

### Phiên 2026-09-16 — chốt theo uỷ quyền của chủ dự án

Ba điểm dưới đây chưa có trong mô tả ban đầu và được chốt bằng thẩm quyền có sẵn
trong repo; chủ dự án có thể phủ quyết bất kỳ điểm nào trước khi thi công.

- Q: "Lượt này vừa tạo một giả định mới" nhận biết bằng gì? → A: bằng đúng tín hiệu
  suy diễn mà lượt đó sinh ra. Bước suy diễn chỉ suy ra vai KHI hồ sơ còn trống vai,
  và nó đã ghi lại kết quả suy ra của chính lượt đó. Một giá trị suy diễn mang sang
  từ lượt trước KHÔNG tính là giả định mới, nên không mở lại câu hỏi.
- Q: Giới hạn 160 ký tự áp cho toàn bộ phần nói giới hạn hay chỉ phần đuôi hỏi? →
  A: chỉ cho phần đuôi hỏi được gắn thêm sau một câu trả lời thành công. Phần nói
  giới hạn do nhánh từ chối hoặc phủ một phần sinh ra không bị đợt này đụng tới
  (xem FR-013).
- Q: "Ghi nhận" một câu vượt giới hạn nghĩa là ghi ở đâu? → A: vào dấu vết của chính
  lượt đó, cùng chỗ đang ghi model và phiên bản prompt, để lượt đo đọc được mà không
  cần thêm kho lưu nào.
- Q: 900 ký tự đếm trên cái gì? → A: trên đúng chuỗi văn xuôi mà hệ thống phát hành,
  tính cả phần đánh dấu của thẻ trích dẫn. Đó là thứ bộ đo đang đếm, nên ngưỡng và số
  đo nói cùng một ngôn ngữ.
- Q: Thế nào là một "gạch đầu dòng" khi đếm trần 4? → A: một dòng cấp một bắt đầu bằng
  dấu gạch nối và một khoảng trắng. Dòng lồng bên trong một gạch không đếm riêng.
- Q: Mốc so sánh là ứng viên nào? → A: ứng viên đang là mặc định của hệ thống, chạy
  trong cùng đợt đo với các ứng viên khác.
- Q: Trung bình độ dài tính trên tập nào? → A: chỉ trên các lượt trả lời thành công.
  Lượt từ chối vốn rất ngắn, gộp vào sẽ kéo trung bình xuống mà không cải thiện gì.
- Q: Đuôi hỏi tự nó vượt 160 ký tự thì sao? → A: bỏ hẳn đuôi đó. Một câu trả lời đã
  chắc không cần rào đón, và cắt một câu hỏi làm đôi thì tệ hơn là không hỏi.
- Q: Lượt vừa tạo giả định mới nhưng kết quả là từ chối hoặc phủ một phần thì sao? →
  A: giữ nguyên hành vi hỏi lại của hai nhánh đó, KHÔNG gắn thêm đuôi, để người dùng
  không nhận hai câu hỏi trong một lượt.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Nhận câu trả lời đọc được trong một hơi (Priority: P1)

Người lao động hỏi một câu về quyền của mình và nhận lại kết luận trước, điều kiện
quyết định sau, hết. Họ không phải lướt qua một danh sách điều luật để tìm câu trả lời.

**Why this priority**: Đây là lời than trực tiếp về sản phẩm. Câu trả lời đúng mà
không đọc nổi thì không giúp được ai.

**Independent Test**: Chạy 77 câu vàng, đo số ký tự `answer` và số gạch đầu dòng.
Đạt khi độ dài trung bình giảm ≥20% so với mốc và không câu nào vượt giới hạn.

**Acceptance Scenarios**:

1. **Given** một câu hỏi có 8 căn cứ đã qua kiểm chứng, **When** KLAW trả lời,
   **Then** `answer` không quá 900 ký tự và không quá 4 gạch đầu dòng.
2. **Given** một câu trả lời mà mô hình viết 6 gạch, **When** hệ thống phát hành,
   **Then** chỉ 4 gạch đầu tới người dùng và lượt đó bị đánh dấu trong nhật ký chạy.
3. **Given** một câu trả lời vẫn dài hơn giới hạn sau khi bỏ gạch thừa, **When** hệ
   thống phát hành, **Then** văn bản KHÔNG bị cắt giữa câu và lượt đó được ghi nhận
   để người bảo trì xem lại.

---

### User Story 2 — Không bị hỏi lại thứ không đổi được gì (Priority: P1)

Người hỏi đã nói đủ dữ kiện thì nhận thẳng câu trả lời, không kèm một câu hỏi lấy lệ.
Khi KLAW phải đoán một dữ kiện để trả lời, nó nói ra mình đã đoán gì và hỏi đúng dữ
kiện đó.

**Why this priority**: Hành vi máy móc dễ nhận ra nhất, và nó làm hỏng ấn tượng về
một câu trả lời vốn đúng.

**Independent Test**: 20 câu mơ hồ + một tập ca có hồ sơ đầy đủ. Đạt khi câu đủ dữ
kiện không có đuôi hỏi, và câu có giả định mới hỏi đúng trường vừa giả định.

**Acceptance Scenarios**:

1. **Given** hồ sơ đã có vai, loại hợp đồng và thời điểm, **When** KLAW trả lời thành
   công, **Then** không có câu hỏi bổ sung nào được gắn thêm.
2. **Given** câu hỏi không nói vai và KLAW suy ra vai để trả lời, **When** KLAW trả
   lời, **Then** nó nêu giả định thành một dòng và hỏi lại đúng vai, không hỏi trường
   khác.
3. **Given** người dùng đã nói vai trong chính câu hỏi, **When** KLAW trả lời,
   **Then** nó không hỏi lại vai.

---

### User Story 3 — Cuộc trò chuyện không bắt đầu lại mỗi lượt (Priority: P2)

Người dùng quay lại một phiên đang dở và được trả lời tiếp, không bị chào như lần đầu.

**Why this priority**: Rẻ để sửa, hỏng thì thấy ngay, và nó phá cảm giác đang nói
chuyện với một người.

**Independent Test**: Một phiên có tóm tắt nhưng lịch sử rỗng. Đạt khi lời mở là lời
mở nối tiếp.

**Acceptance Scenarios**:

1. **Given** phiên đã có tóm tắt và lịch sử vừa bị rút gọn về rỗng, **When** người
   dùng hỏi tiếp, **Then** KLAW không chào lại.
2. **Given** một phiên hoàn toàn mới, **When** người dùng hỏi câu đầu tiên, **Then**
   KLAW chào đúng một lần.

---

### User Story 4 — Người bảo trì so được hai lượt đo (Priority: P2)

Người bảo trì mở một tệp kết quả cũ và biết ngay nó chạy trên model nào, kho văn bản
nào, ngày hiệu lực nào, cache bật hay tắt.

**Why this priority**: Không có nó thì mọi kết luận "bản mới tốt hơn" đều không kiểm
chứng được. Hai tệp kết quả cùng chạy `assemble.v3` đang lệch 30 điểm phần trăm mà
không tệp nào ghi model.

**Independent Test**: Chạy một lượt, mở tệp JSON, đọc được model từng vai, số hàng
corpus, ngày hiệu lực, trạng thái cache, độ trễ p95 và chi phí.

**Acceptance Scenarios**:

1. **Given** một lượt đo vừa chạy xong, **When** mở tệp kết quả, **Then** thấy đủ
   model từng vai, dấu vân tay corpus, ngày hiệu lực, trạng thái cache, p95 và chi phí.
2. **Given** kho dữ liệu không truy cập được lúc ghi metadata, **When** lượt đo kết
   thúc, **Then** lượt đo vẫn cho ra kết quả và phần corpus để trống thay vì hỏng.
3. **Given** tệp kết quả được lưu vào repo, **When** đọc toàn bộ nội dung, **Then**
   không có khoá API nào trong đó.

---

### User Story 5 — Lệnh kiểm tra không sửa file và không đốt tiền (Priority: P3)

Người đóng góp chạy một lệnh kiểm tra duy nhất và nhận kết quả đúng/sai, không bị
lệnh đó tự sửa mã đang viết dở, không bị nó gọi mô hình trả phí.

**Why this priority**: Rào cản hằng ngày, và một lệnh kiểm tra tự ghi file làm hỏng
chính diff đang được xem xét.

**Independent Test**: Chạy lệnh kiểm tra trên cây làm việc bẩn. Đạt khi không tệp nào
bị thay đổi và không lượt gọi trả phí nào được thực hiện.

**Acceptance Scenarios**:

1. **Given** cây làm việc có mã chưa định dạng, **When** chạy lệnh kiểm tra,
   **Then** lệnh báo lỗi định dạng nhưng không sửa tệp nào.
2. **Given** máy không có kho dữ liệu chạy, **When** chạy lệnh kiểm tra mặc định,
   **Then** lệnh vẫn kết thúc được vì các test cần kho dữ liệu bị loại khỏi lane.

---

### Edge Cases

- Mô hình viết 5 gạch trở lên → bỏ gạch thừa, không viết lại bằng một lượt gọi mới.
- `answer` vẫn quá dài sau khi bỏ gạch → ghi nhận, không cắt giữa câu, vì cắt theo ký
  tự sẽ chặt đứt một thẻ trích dẫn và biến câu hợp lệ thành câu có thẻ hỏng.
- Lượt vừa suy ra một giả định nhưng hồ sơ đã có sẵn trường đó → không hỏi lại.
- Giả định được suy ra ở lượt 2 và người dùng im lặng về nó ở lượt 3 → lượt 3 không
  hỏi lại, vì nó không tạo ra giả định mới nào.
- Lượt không suy ra giả định nào và hồ sơ còn trống → vẫn không hỏi, vì thiếu dữ kiện
  đó không chứng minh được là làm đổi kết luận.
- Câu trả lời là từ chối (`abstain`) hoặc phủ một phần → đuôi hỏi vẫn được phép như
  hiện tại; đợt này không đụng hai nhánh đó.
- Kho dữ liệu rớt giữa một lượt đo → lượt đó không hợp lệ để so sánh; báo cáo phải nói
  rõ số câu lỗi chứ không tính tỉ lệ trên mẫu số nhỏ hơn.
- Cả ba prompt ứng viên đều trượt ít nhất một cổng → giữ nguyên prompt hiện hành và
  báo cáo, không đổi mặc định để "có tiến độ".

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Mỗi lượt đo chất lượng trả lời PHẢI ghi vào chính tệp kết quả: model
  từng vai, dấu vân tay kho văn bản, ngày hiệu lực áp dụng, trạng thái cache, độ trễ
  p95, chi phí thật và số câu lỗi.
- **FR-002**: Tệp kết quả PHẢI KHÔNG chứa khoá API hoặc bí mật nào.
- **FR-003**: Khi kho dữ liệu không đọc được lúc ghi metadata, lượt đo PHẢI vẫn hoàn
  tất và để trống phần dấu vân tay, KHÔNG được hỏng.
- **FR-004**: Mốc so sánh PHẢI gồm ba ứng viên hành văn hiện có, chạy cùng commit,
  cùng model, cùng kho văn bản, cache tắt, đủ 77/77 câu.
- **FR-005**: Một lượt đo có câu lỗi PHẢI KHÔNG được dùng để kết luận hơn kém.
- **FR-006**: Phần văn xuôi có căn cứ của câu trả lời PHẢI KHÔNG quá 900 ký tự.
- **FR-007**: Phần văn xuôi có căn cứ PHẢI KHÔNG quá 4 gạch đầu dòng; gạch thứ 5 trở
  đi bị loại trước khi phát hành.
- **FR-008**: Phần đuôi hỏi gắn sau một câu trả lời thành công PHẢI KHÔNG quá 160
  ký tự. Phần nói giới hạn của nhánh từ chối và nhánh phủ một phần không thuộc
  phạm vi giới hạn này.
- **FR-009**: Việc cưỡng chế hai giới hạn trên PHẢI KHÔNG dùng thêm một lượt gọi mô
  hình nào.
- **FR-010**: Hệ thống PHẢI KHÔNG cắt văn bản giữa câu để đạt giới hạn; vượt giới hạn
  sau khi loại gạch thừa thì ghi vào dấu vết của lượt đó, cùng nơi đang ghi model và
  phiên bản prompt.
- **FR-011**: Câu trả lời thành công PHẢI chỉ kèm câu hỏi bổ sung khi chính lượt đó
  vừa tạo một giả định mới, và câu hỏi đó PHẢI hỏi đúng trường vừa giả định. Một giá
  trị suy diễn mang sang từ lượt trước KHÔNG mở lại câu hỏi.
- **FR-012**: Hệ thống PHẢI KHÔNG hỏi lại một trường đã có trong hồ sơ hoặc đã được
  người dùng nói rõ trong câu hỏi.
- **FR-013**: Nhánh từ chối và nhánh phủ một phần PHẢI giữ nguyên hành vi hỏi lại
  hiện tại.
- **FR-014**: Nhận diện lượt đầu PHẢI xét cả lịch sử hội thoại lẫn tóm tắt phiên;
  phiên đã có tóm tắt KHÔNG được chào lại.
- **FR-015**: Lệnh kiểm tra mặc định PHẢI KHÔNG ghi đè tệp nguồn.
- **FR-016**: Lane test mặc định PHẢI loại các test cần kho dữ liệu và các test chờ
  người duyệt, và PHẢI khớp với lane mà tích hợp liên tục đang chạy.
- **FR-017**: Việc đổi prompt hành văn mặc định PHẢI lùi lại được bằng một biến môi
  trường, không cần sửa mã.
- **FR-018**: Mọi quy tắc trên PHẢI có một nơi cưỡng chế chạy được kèm bằng chứng cả
  chiều đạt lẫn chiều vi phạm.
- **FR-019**: Giới hạn độ dài PHẢI đếm trên đúng chuỗi được phát hành, kể cả phần đánh
  dấu thẻ trích dẫn; bảng kết quả không tính vào giới hạn này.
- **FR-020**: Trần 4 gạch PHẢI đếm theo dòng cấp một; dòng lồng bên trong một gạch
  không đếm riêng.
- **FR-021**: Khi phần đuôi hỏi tự nó vượt giới hạn 160 ký tự, hệ thống PHẢI bỏ hẳn
  đuôi đó thay vì cắt ngắn.
- **FR-022**: Khi một lượt vừa tạo giả định mới nhưng kết quả là từ chối hoặc phủ một
  phần, hệ thống PHẢI KHÔNG gắn thêm đuôi hỏi; nhánh đó giữ đúng hành vi hiện tại.
- **FR-023**: Lane test mặc định PHẢI loại hai nhóm riêng biệt: test cần kho dữ liệu
  đang chạy, và test chờ người duyệt thủ công. Các script đo gọi mô hình trả phí nằm
  hoàn toàn ngoài lane test, không phải bị loại khỏi nó.

### Key Entities

- **Lượt đo**: một lần chạy bộ câu hỏi trên một cấu hình xác định; mang metadata,
  từng hàng kết quả và các tỉ lệ tổng hợp.
- **Câu trả lời**: gồm phần văn xuôi có căn cứ, phần nói giới hạn, bảng (nếu có) và
  danh sách trích dẫn.
- **Giả định**: cách hiểu của KLAW về một dữ kiện người dùng chưa nói; có nguồn riêng,
  luôn hiện, luôn sửa được, không bao giờ là căn cứ.
- **Đuôi hỏi thêm**: đúng một câu hỏi nối tiếp sau một câu trả lời thành công.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Độ dài trung bình phần văn xuôi có căn cứ, tính TRÊN CÁC LƯỢT TRẢ LỜI
  THÀNH CÔNG, giảm ít nhất 20% so với ứng viên đang mặc định trong cùng đợt đo.
- **SC-002**: 0/77 câu vượt 900 ký tự phần văn xuôi có căn cứ; 0/77 câu quá 4 gạch.
- **SC-003**: Tỉ lệ dẫn đúng điều luật người duyệt ghi giảm không quá 1 câu trên 77
  so với ứng viên đang mặc định, đo trong cùng đợt.
- **SC-004**: Độ chính xác trích dẫn giảm không quá 1 điểm phần trăm so với ứng viên
  đang mặc định, đo trong cùng đợt.
- **SC-005**: Số lỗi bẫy an toàn không tăng so với mốc trên đủ 57 bẫy.
- **SC-006**: Trên 20 câu mơ hồ, 100% câu có giả định mới đều hỏi lại đúng trường vừa
  giả định, và 0 câu có hồ sơ đầy đủ bị gắn câu hỏi bổ sung.
- **SC-007**: 0 lượt chào lại trong các phiên đã có tóm tắt.
- **SC-008**: Mọi lượt đo dùng để kết luận đều hoàn tất đủ mẫu, số câu lỗi bằng 0.
- **SC-009**: Chi phí trung bình mỗi câu không tăng quá 10% và độ trễ p95 không tăng
  quá 15% so với ứng viên đang mặc định, đo trên cùng máy trong cùng đợt.
- **SC-010**: Lệnh kiểm tra mặc định chạy trên cây làm việc bẩn không làm thay đổi
  một tệp nào.

## Assumptions

- Mốc đo và bản sửa đều chạy trên `deepseek/deepseek-v4-flash-0731` (vai chính và vai
  generate) với vai judge giữ nguyên; kết luận của đợt này chỉ có hiệu lực cho cấu
  hình đó.
- 77 câu vàng hiện có đủ đại diện để đo độ dài và độ trúng dẫn trong đợt này; bộ ca
  hội thoại chuyên biệt thuộc đợt sau.
- Kho văn bản không đổi trong suốt đợt đo (1.634 văn bản, 43.720 điều khoản, 14.770
  đoạn).
- Cache trả lời tắt trong mọi lượt đo; bật lại ở vận hành bình thường.
- Ngân sách gọi mô hình cho đợt này ở mức vài đô la; nếu bị khoá, phần đo dừng và mọi
  kết luận về prompt được đánh dấu "chưa đo" thay vì suy đoán.

## Ràng buộc kế thừa từ tài liệu đã chấp nhận

- Hiến pháp dự án: mọi khẳng định pháp lý neo vào trích dẫn kiểm chứng được; thà từ
  chối còn hơn bịa; mọi quy tắc phải có nơi cưỡng chế; giả định không bao giờ là căn
  cứ; chỉ tuyên bố hoàn thành khi có bằng chứng chạy được.
- Quyết định 2026-09-09 "giả định có kiểm soát": thiếu dữ kiện thì trả lời nhánh phổ
  biến nhất, nêu giả định thành một dòng, rồi hỏi đúng dữ kiện đó. Đợt này thu hẹp
  phạm vi câu hỏi cuối chứ KHÔNG bỏ hành vi đó.
- Bảy phép kiểm 0 token hiện có và hai tầng kiểm chứng giữ nguyên; đợt này chỉ thêm
  phép kiểm hình dạng, không bỏ phép nào.
- Prompt mới luôn là tệp phiên bản mới; không sửa đè phiên bản đang chạy.

## Ngoài phạm vi

- Khung yêu cầu có cấu trúc cho mục tiêu người hỏi (GĐ2).
- Phân loại vai trò luận điểm và chấm độ liên quan theo mục tiêu (GĐ3).
- Hỏi lại theo dữ kiện quyết định lấy từ khung yêu cầu (GĐ4).
- Làm mượt luồng soạn thảo (GĐ5).
- Bộ 40 ca chất lượng hội thoại và quy trình người duyệt của nó.
- Đổi ngưỡng từ chối, đổi model để che lỗi prompt, mở rộng kho văn bản.
- Đổi hợp đồng HTTP hoặc lược đồ cơ sở dữ liệu.
