# Design

<!-- impeccable:design-schema 1 -->

## Thế giới thị giác: máy đọc vi phim

Một cỗ máy tra cứu lưu trữ. Bạn gõ câu hỏi, máy tìm trong kho, **tiến tới đúng khung
phim**, và rọi sáng nguyên văn điều luật lên mặt kính.

Ẩn dụ này được chọn vì nó mang đúng lời hứa của sản phẩm và không thể mang một lời hứa
khác: *đây là nguyên văn, và đây là chỗ nó đến từ.* Một trợ lý pháp lý nói trôi chảy mà
không chỉ được nguồn thì phản bội chính nó; một máy đọc vi phim **không thể** làm vậy —
nó chỉ biết chiếu lại thứ có thật trên phim.

Ba lớp, người dùng chọn đi sâu tới đâu:

| Lớp | Nội dung | Ai dùng nhiều nhất |
|---|---|---|
| **Mặt đọc** | Câu trả lời bằng tiếng Việt thường | người lao động |
| **Dải khung** | Các trích dẫn, mỗi cái một khung phim có nhãn hiệu lực | nhân sự |
| **Khung rọi sáng** | Nguyên văn điều luật, câu trích được đánh dấu | sinh viên luật |

Một câu trả lời, ba lớp — không phải ba giao diện.

## Bảng màu

Ground tối là mặt máy; ánh sáng là thứ rọi qua phim. Nền là **đen ngả nâu**, không
phải xám lạnh — máy đọc vi phim là thiết bị lưu trữ thập niên 70, phim đã ngả màu,
thư viện luật là gỗ và da. Xám xanh là màu của phần mềm, không phải của kho lưu trữ.

```
--nen          #12100D   mặt máy — đen ngả nâu
--nen-cao      #1C1813   khay, thanh công cụ
--vien         #2B2419   đường viền, cạnh khay
--phim         #F3EEE3   mặt phim được rọi — nền của văn bản luật
--muc          #1A1611   chữ trên phim
--muc-nhat     #6B6154   chú thích, nhãn phụ
--den-sang     #F0BC5A   ánh đèn máy: quầng sáng, tiêu điểm, con trỏ
--xanh-that    #4C9E78   còn hiệu lực
--do-thay      #E05A45   đã bị thay thế / hết hiệu lực
--vang-mo      #C9922F   một phần không xác định
--xam-cho      #938981   ABSTAIN, cần đối chiếu tay — TRUNG TÍNH
```

**`--xam-cho` là quyết định quan trọng nhất của bảng màu này.** `abstain` là hành vi
**đúng**, được tính điểm trong đánh giá. Nó không bao giờ được mang màu đỏ, không icon
cảnh báo, không rung. Một hệ thống thà nói "tôi không đủ căn cứ" còn hơn bịa một điều
luật — nếu giao diện tô đỏ câu đó, nó dạy người dùng rằng sự trung thực là thất bại.

Đỏ dành riêng cho **luật đã bị thay thế**. Đó mới là thứ khiến người dùng hành động sai.

**Nền nâu buộc phải chỉnh ba màu trạng thái, không chỉ đổi nền.** Nâu chính là
đỏ-cam đã khử bão hoà — nên một màu đỏ cảnh báo vừa phải sẽ chìm vào chính đồ đạc
xung quanh. `--do-thay` vì vậy được đẩy bão hoà và sáng hơn bản nền lạnh
(`#C4553D` → `#E05A45`), đủ tách khỏi nền. Cảnh báo quan trọng nhất của sản phẩm
không được phép trông như một phần của khung cảnh.

`--xam-cho` giờ là **chính màu nền đã khử bão hoà**, không phải xám xanh mượn từ
nơi khác. Điều đó đúng cả về khái niệm: `abstain` nghĩa là máy không có gì để nói,
nên nó mang màu của đồ đạc — và vì nó *là* đồ đạc, nó không thể bị đọc nhầm thành
cảnh báo.

`--den-sang` và `--vang-mo` cùng họ vàng và không tách nhau bằng màu. Chúng tách
nhau bằng **hình**: đèn máy luôn là **quầng sáng** (radial-gradient, mờ dần), còn
`--vang-mo` luôn là **đường viền đặc**. Nếu có lúc nào đèn máy bị dùng làm nền
đặc, quy tắc này gãy — đừng làm vậy.

Đỏ `#E05A45` và xanh `#4C9E78` với người mù màu deuteranopia đều ngả vàng nâu.
Đó là lý do nhãn hiệu lực **không bao giờ chỉ có màu**: `con_hieu_luc` là chấm
không chữ, `bi_thay_the` là viền **kèm tên văn bản thay thế**. Hình và chữ mang
nghĩa; màu chỉ nhắc lại.

Độ tương phản đã **tính**, không phải ước: `--muc` trên `--phim` 15,6:1 ·
`--phim` trên `--nen` 16,4:1 · `--muc-nhat` trên `--phim` 5,2:1 · `--xam-cho`
trên `--nen-cao` 5,2:1 · `--xanh-that` 5,4:1 · `--do-thay` 4,8:1 · `--vang-mo`
6,4:1 · `--den-sang` 10,1:1. Tất cả đạt AA cho chữ thường.

Một kết quả đo đáng nêu ra thay vì giấu đi: `--do-thay` và `--xam-cho` **gần như
cùng độ sáng** (1,07:1 giữa hai màu). Trong ảnh xám, "đã bị thay thế" và "không
đủ căn cứ" trông như nhau — mà đó lại là hai trạng thái đối lập nhất trong sản
phẩm. Không chỉnh số này, vì chỉnh thì hoặc đỏ nhạt đi thành hồng cá hồi và mất
sức nặng cảnh báo, hoặc xám tụt xuống dưới ngưỡng AA. Thay vào đó bất biến ở trên
được nâng thành ràng buộc cứng: **không trạng thái nào được truyền đạt chỉ bằng
màu.** `bi_thay_the` luôn kèm câu nêu đích danh văn bản thay thế; `abstain` luôn
kèm câu "Không tìm thấy căn cứ pháp lý cho câu hỏi này." Người đọc phân biệt được
bằng chữ, kể cả khi màu nói dối họ.

## Chữ và bố cục

- **Mặt đọc**: sans humanist đọc tốt tiếng Việt có dấu, thân 17px trên di động và 18px
  trên desktop, dòng 1.7. Dấu tiếng Việt cần chiều cao dòng rộng hơn tiếng Anh.
- **Trên phim**: serif, vì nguồn là văn bản in. Chữ trên phim **không bao giờ** đổi màu
  theo trạng thái — phim là phim; trạng thái sống ở nhãn và ở viền khung.
- **Số hiệu, đường dẫn trích dẫn**: mono, vì `45/2019/QH14 > Điều 127 > Khoản 2` là một
  **địa chỉ**, không phải văn xuôi. Người dùng cần quét và so từng ký tự.
- Bề rộng đọc tối đa **68 ký tự** ở mặt đọc; dải khung không giới hạn ngang.

## Cấu trúc và điều hướng

Ba màn hình, một máy:

- **Tra cứu** — ô hỏi ở giữa khi trống, trượt lên đầu khi có kết quả
- **Soạn thảo** — nhập thông tin, máy sinh văn bản, mỗi điều khoản mang căn cứ riêng
- **Soát** — dán văn bản có sẵn, máy trả danh sách phát hiện, mỗi cái neo vào một khung

Chuyển giữa ba màn hình là **đổi khay phim**, không phải tải lại trang.

## Trạng thái — bốn kết quả, bốn cách hiển thị

| `result_type` | Giao diện |
|---|---|
| `answer` | mặt đọc có văn bản; dải khung bên dưới; badge hiệu lực trên từng khung |
| `partial_coverage` | mặt đọc **để trống có chủ đích** — không diễn giải. Chỉ nêu văn bản tìm thấy + đường dẫn tới nguyên văn |
| `abstain` | *"Không tìm thấy căn cứ pháp lý cho câu hỏi này."* + gợi ý diễn đạt lại. Nền `--xam-cho`, chữ bình thường, **không icon lỗi** |
| `out_of_scope` | nêu rõ phạm vi: 6 Bộ luật + cụm Lao động; liệt kê cái **không** phủ (thuế, đất đai, hôn nhân gia đình) |

Badge hiệu lực trên mỗi khung, **luôn thấy được**, không nằm trong tooltip:

| Nhãn | Hiển thị |
|---|---|
| `con_hieu_luc` | chấm `--xanh-that`, không chữ |
| `bi_thay_the` / `het_hieu_luc` | viền `--do-thay` + câu nêu **đích danh** văn bản thay thế |
| `mot_phan_khong_xac_dinh` | viền `--vang-mo` + *"CSDL quốc gia không công bố dữ liệu cấp điều khoản"* |
| `can_doi_chieu_tay` | chấm `--xam-cho` + *"cần đối chiếu tay"* |

## Chuyển động — giải thích quan hệ, không trang trí

Bốn chuyển động, mỗi cái một việc:

1. **Tiến tới khung** — bấm một trích dẫn, khung trượt vào tiêu điểm và sáng lên. Đây là
   động tác trung tâm: nó *là* click-to-verify. `transform` + `opacity`, chạy trên
   compositor.
2. **Rọi tiêu điểm** — câu trích sáng dần trong nguyên văn, để mắt tìm được nó trong một
   Điều dài.
3. **Trạng thái chờ** — tra cứu mất **10–60 giây**. Không spinner. Máy đếm qua các bước
   **có thật** trong đồ thị: *đang tìm → đang mở rộng → đang kiểm chứng → đang dựng câu
   trả lời*. Người dùng thấy hệ thống đang làm gì, không phải một vòng tròn quay.
   Trên ngưỡng 10 giây, một chỉ báo không xác định đọc như **treo máy**: phải có tên
   bước đang chạy, tiến trình xác định, và **nút huỷ**. Hoãn 300–500ms trước khi hiện
   chỉ báo để câu trả lời nhanh không làm loé rồi tắt. Luôn có timeout dẫn tới lỗi thật
   kèm nút thử lại — không treo im lặng.
4. **Đổi khay** — chuyển giữa ba màn hình, trượt ngang có chiều sâu.

Chiều sâu 3D dùng `perspective` + `translateZ` ở dải khung, **không WebGL** — thư viện 3D
nặng sẽ giết trải nghiệm trên điện thoại đời cũ, mà người lao động là một trong ba nhóm
người dùng chính.

`prefers-reduced-motion`: thay dịch chuyển bằng đổi opacity, **giữ nguyên** phản hồi
trạng thái. Tắt hết không được — người dùng vẫn phải biết bước nào đang chạy trong 60
giây đó.

## Responsive

- **Di động**: một cột. Mặt đọc trước, dải khung cuộn ngang bên dưới, khung rọi sáng mở
  toàn màn hình. Vùng chạm tối thiểu 44px.
- **Máy tính**: hai cột — mặt đọc trái, khung rọi sáng phải, dải khung dưới mặt đọc. Đọc
  câu trả lời và nguyên văn **cùng lúc**, không chuyển qua lại.
- Điểm gãy theo **nội dung**, không theo tên thiết bị: cột đôi khi đủ chỗ cho 68 ký tự
  **và** một khung phim đọc được cạnh nhau.

## Ràng buộc không được vi phạm

- Định danh văn bản bằng `so_ky_hieu`, **không bao giờ** bằng tên
- Cảnh báo hiệu lực **không được** giấu vào tooltip hay metadata
- `abstain` **không bao giờ** mang màu lỗi
- `GET /van-ban/{id}` lazy — không tải cả cây 689 Điều
- Chữ trên phim là nguyên văn từ CSDL: **không** rút gọn, **không** sửa chính tả

---

## Mã nhãn — KLAW

Một **khung phim đang được rọi sáng**. Hình vuông bo góc là khung; hai khía răng
cưa ở cạnh trái và phải là lỗ kéo phim; một vòng tròn ánh sáng ấm (`--den-sang`)
lệch tâm bên trong là chỗ đèn máy rọi qua.

Ràng buộc: ở 16px (favicon) chỉ còn **khung + chấm sáng** vẫn phải nhận ra được.
Nếu phải nhìn kỹ mới thấy răng cưa thì răng cưa bị bỏ ở kích thước đó, không thu
nhỏ tiếp.

Chữ hiệu: `KLAW` bằng font địa chỉ (mono), giãn chữ nhẹ. Đặt cạnh mã nhãn, không
lồng vào trong. Dưới nó, khi có chỗ: *Tra cứu pháp luật có trích dẫn kiểm chứng
được* — đây là lời hứa của sản phẩm, không phải khẩu hiệu quảng cáo.

**Không** dùng: búa thẩm phán, cán cân công lý, bộ não, người máy, tia lửa AI.
Chúng nói "pháp luật" và "AI" một cách chung chung, không nói được điều duy nhất
KLAW làm khác.

## Bộ biểu tượng

Nét (stroke) đồng nhất 1.5px ở 24px, đầu nét vuông — cùng họ với khung phim, chứ
không phải biểu tượng bo tròn mềm. Vẽ tay bằng SVG inline, **không thư viện icon**
(người lao động dùng mạng yếu; một bộ icon đầy đủ tốn nhiều hơn số icon thật dùng).

Biểu tượng mang **nghĩa trạng thái** không bao giờ đứng một mình: `abstain` không
có biểu tượng cảnh báo, và mọi nhãn hiệu lực đều kèm chữ hoặc màu, không chỉ hình
— người mù màu phải đọc được trạng thái.

## Màn hình giới thiệu — mode Persuade

Đây là **bề mặt duy nhất** ở mode Persuade. Ba màn hình công cụ vẫn là Operate;
đừng mang phong cách trang giới thiệu vào chúng.

Người vào lần đầu chưa biết KLAW khác gì ChatGPT. Trang này trả lời đúng một câu
hỏi đó, rồi để họ gõ câu hỏi thật ngay tại chỗ — ô hỏi ở hero **là** ô hỏi thật,
không phải nút dẫn sang trang khác. Gõ xong chuyển sang `/tra-cuu` mang theo câu
hỏi.

Thứ tự nội dung, theo đúng thứ tự người ta cần biết:

1. **Hero** — cỗ máy trong không gian 3D, ô hỏi thật, một câu nói KLAW làm gì
2. **Vì sao khác** — trích dẫn bấm được, kiểm bằng tra bảng chứ không phải suy luận
3. **Bốn kết quả** — nêu thẳng rằng *"không tìm thấy căn cứ"* là câu trả lời hợp lệ
4. **Phạm vi thật** — 6 Bộ luật + cụm Lao động; **nói rõ cái không phủ**
5. **Giới hạn** — corpus là văn bản gốc, không phải bản hợp nhất

Mục 4 và 5 nằm trên trang giới thiệu **có chủ đích**. Một trang Persuade giấu giới
hạn xuống footer là trang bán hàng; trang này bán được vì nó nói ra giới hạn.

## Trợ lý — người vận hành máy, không phải bong bóng chat biết tuốt

Sự hiện diện của AI trong giao diện là **người vận hành cỗ máy**: biết trong kho
có gì, đưa được đúng khay phim, và nói thẳng khi thứ bạn hỏi không có trong kho.

- Hình thái: ô đèn của máy — một vòng sáng `--den-sang` thở nhẹ khi rảnh, sáng ổn
  định khi đang chạy. **Không** mặt người, **không** nhân vật hoạt hình.
- Câu mở: *"Bạn cần tra điều gì?"* — kèm **câu hỏi mẫu có thật**, chạy được, lấy
  từ phạm vi corpus thật. Không phải câu bịa cho đẹp.
- Nó **nêu giới hạn trước khi bị hỏi**: khi câu hỏi chạm lĩnh vực không phủ, nói
  ngay thay vì để người dùng chờ 60 giây rồi nhận `out_of_scope`.
- Không bao giờ tự sinh nội dung pháp lý ngoài kết quả đã qua kiểm chứng. Nó dẫn
  đường trong máy, không trả lời thay máy.
- Thu gọn được, và trạng thái thu gọn được nhớ. Không bao giờ tự bật lại.

## Tương tác chuột

Chuột chỉ làm **một** việc: điều khiển ánh sáng của máy.

- Con trỏ di trên dải khung → tâm quầng sáng đi theo (`--x`/`--y` cập nhật bằng
  `pointermove`, đọc trong `radial-gradient`). Chỉ `opacity` và vị trí gradient.
- Hero nghiêng nhẹ theo con trỏ — biên độ **tối đa 6°**, và tắt hẳn dưới 1024px
  (màn cảm ứng không có con trỏ; đọc `@media (hover: hover) and (pointer: fine)`).
- Cuộn trang giới thiệu → các mặt phẳng `translateZ` khác nhau trôi lệch nhau,
  bằng `animation-timeline: scroll()`. **Không** JS nghe scroll.
- Mọi thứ chuột làm được, bàn phím cũng phải làm được. Không có tính năng nào chỉ
  tồn tại khi có con trỏ.
- `pointermove` phải throttle theo `requestAnimationFrame`. Một handler chạy mỗi
  sự kiện chuột là cách chắc chắn nhất để giết 60fps trên máy yếu.
