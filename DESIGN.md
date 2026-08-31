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

Ground tối là mặt máy; ánh sáng là thứ rọi qua phim. Nền là **ink-navy**, accent là
**brass** — giá trị lấy từ `KLAW-BUILD-SPEC` §5.1, do chủ dự án chốt.

Bản trước của mục này chọn **đen ngả nâu** và lập luận rằng "xám xanh là màu của
phần mềm, không phải của kho lưu trữ". Lập luận đó không sai, nó chỉ bị **thay
thế bằng một quyết định của chủ dự án** — ghi lại ở đây thay vì xoá, vì người đọc
sau này cần biết bảng màu đã đổi có chủ đích chứ không phải trôi dạt. Ẩn dụ giữ
nguyên, chỉ đổi vật liệu: cỗ máy giờ là **thép và kính** thay vì gỗ và da. Phần
quan trọng của ẩn dụ chưa bao giờ nằm ở nhiệt độ màu — nó nằm ở chỗ *ánh sáng
rọi qua phim*, và brass làm việc đó tốt như amber.

**Tên biến là hợp đồng FE**, không đổi theo bảng màu. Chỉ giá trị đổi.

```
--nen          #060D1A   ink-950 · mặt máy
--nen-cao      #0A1628   ink-900 · khay, thanh công cụ, thẻ
--vien         #14294A   ink-700 · đường viền, cạnh khay
--phim         #FAF9F6   paper-50 · mặt phim được rọi — nền của văn bản luật
--muc          #12203A   text-light · chữ trên phim
--muc-nhat     #A3AFC2   text-dark-muted · chú thích, nhãn phụ — LUÔN trên nền tối
--den-sang     #C8A45C   brass-500 · ánh đèn máy: quầng sáng, tiêu điểm, con trỏ
--xanh-that    #358F68   còn hiệu lực
--do-thay      #CA5F54   đã bị thay thế / hết hiệu lực
--vang-mo      #B4842B   một phần không xác định
--xam-cho      #949CA8   ABSTAIN, cần đối chiếu tay — TRUNG TÍNH
```

Ba bậc ink lấy đúng ba vai mà spec §5.3 đặt tên: nền trang · khay/thẻ · đường
viền. `--nen` là ink-950 chứ không phải ink-900 vì đó là cách gán duy nhất cho cả
ba token rơi đúng vai, và vì nó để `--nen-cao` ở ink-900 — ground sáng hơn, tức
ràng buộc tương phản chặt hơn — được nhiều khoảng dư nhất cho bốn màu trạng thái.

**`--xam-cho` vẫn là quyết định quan trọng nhất của bảng màu này.** `abstain` là
hành vi **đúng**, được tính điểm trong đánh giá. Nó không bao giờ được mang màu
đỏ, không icon cảnh báo, không rung. Một hệ thống thà nói "tôi không đủ căn cứ"
còn hơn bịa một điều luật — nếu giao diện tô đỏ câu đó, nó dạy người dùng rằng sự
trung thực là thất bại. Vì vậy `--xam-cho` **không phải** một token `status-*` nào
của spec: nó là hue của chính ground (217°) khử bão hoà xuống 10%, tức vẫn đúng
lý lẽ cũ — *`abstain` nghĩa là máy không có gì để nói, nên nó mang màu của đồ đạc;
và vì nó **là** đồ đạc, nó không thể bị đọc nhầm thành cảnh báo.*

Đỏ dành riêng cho **luật đã bị thay thế**. Đó mới là thứ khiến người dùng hành động sai.

**Nền navy đổi cách phải chỉnh ba màu trạng thái.** Trên nền nâu, vấn đề là *hue*:
nâu chính là đỏ-cam khử bão hoà, nên đỏ cảnh báo chìm vào đồ đạc và `--do-thay`
phải được đẩy bão hoà. Trên nền navy, hue tách miễn phí — đỏ ở 6° không thể lẫn
vào ground ở 217°. Vấn đề chuyển thành *độ sáng*: đo ra thì ba màu `status-*` của
spec **trượt AA** trên nền ink khi dùng làm màu chữ (đỏ 2,61:1 · xanh 3,63:1 ·
xanh dương 2,64:1). Trong sản phẩm này chúng **là màu chữ** (`ResultCard`,
`BadgeHieuLuc`), không chỉ là chấm 6px như spec §8 giả định. Nên cả ba được nâng
độ sáng — giữ nguyên hue và saturation — theo đúng chỉ dẫn của chính spec §5.1:
*"nếu fail thì làm sáng/tối chữ, tuyệt đối không hạ chuẩn."* `--vang-mo` giữ
nguyên giá trị spec vì nó đã đạt 5,42:1.

`--den-sang` và `--vang-mo` cùng họ vàng và không tách nhau bằng màu. Chúng tách
nhau bằng **hình**: đèn máy luôn là **quầng sáng** (radial-gradient, mờ dần), còn
`--vang-mo` luôn là **đường viền đặc**.

> Ngoại lệ duy nhất, có từ trước và giờ được ghi ra thay vì để ngầm: nút hành động
> chính và liên kết "bỏ qua tới nội dung" dùng brass làm **nền đặc** với chữ
> `--muc` (đo 6,9:1). Spec §8 (`BrassButton variant="solid"`) chủ động yêu cầu
> đúng như vậy. Ngoài hai chỗ đó, đừng lấy `--den-sang` làm nền đặc.

Đỏ và xanh với người mù màu deuteranopia đều ngả vàng nâu. Đó là lý do nhãn hiệu
lực **không bao giờ chỉ có màu**: `con_hieu_luc` là chấm không chữ, `bi_thay_the`
là viền **kèm tên văn bản thay thế**. Hình và chữ mang nghĩa; màu chỉ nhắc lại.

Độ tương phản đã **tính**, không phải ước — và đã đo lại trên trình duyệt thật
bằng `getComputedStyle`, không chỉ tính trên giấy. Toàn bộ 18 cặp bắt buộc đạt AA
cho chữ thường; bảng đầy đủ ở
`.superpowers/sdd/2026-08-27-klaw-04-drafting-fe-deploy/palette-brass-report.md`:

`--muc` trên `--phim` 15,4:1 · `--phim` trên `--nen` 18,5:1 · `--muc-nhat` trên
`--nen` 8,8:1 và trên `--nen-cao` 8,2:1 · `--xam-cho` trên `--nen` 7,0:1 và trên
`--nen-cao` 6,5:1 · `--den-sang` trên `--nen-cao` 7,7:1 (vòng tiêu điểm) ·
`--vang-mo` 5,42:1 · `--do-thay` 4,56:1 · `--xanh-that` 4,56:1.

Kết quả đo cũ đáng cập nhật thay vì giấu đi: `--do-thay` và `--xam-cho` từng
**gần như cùng độ sáng** (1,07:1) — trong ảnh xám, "đã bị thay thế" và "không đủ
căn cứ" trông như nhau, mà đó lại là hai trạng thái đối lập nhất trong sản phẩm.
Bảng ink-navy **cải thiện** con số này lên **1,44:1**, và hai màu giờ còn tách
nhau bằng cả họ màu (navy trung tính so với salmon ấm) — đo được trên trình duyệt
thật, xác nhận bằng mắt ở 390px. Dù vậy bất biến vẫn **không** được nới:
**không trạng thái nào được truyền đạt chỉ bằng màu.** `bi_thay_the` luôn kèm câu
nêu đích danh văn bản thay thế; `abstain` luôn kèm câu "Không tìm thấy căn cứ
pháp lý cho câu hỏi này." Người đọc phân biệt được bằng chữ, kể cả khi màu nói dối
họ. Một con số đo tốt hơn là lý do để bớt lo, không phải lý do để bỏ ràng buộc.

Cuối cùng, một cạm bẫy đã gặp thật: `@theme` của Tailwind v4 **chỉ phát ra biến
nào có utility dùng tới**, nên `var(--shadow-brass)` từng lặng lẽ không vẽ gì.
Khối `@theme` trong `tokens.css` vì vậy phải là `@theme static` — một file token
tồn tại để công bố bảng màu thì không được tuỳ hứng biến mất.

## Chữ và bố cục

Bốn vai, theo `KLAW-BUILD-SPEC` §5.2. Tất cả self-host qua `@fontsource`, đều có
subset `vietnamese` đã kiểm bằng công cụ trên trình duyệt thật — chi tiết phép
kiểm và cạm bẫy khi kiểm lại nằm ở `frontend/README.md`.

- **Tiêu đề** (`--font-tieu-de`, Playfair Display 500/600): chỉ `h1` và `h2`.
  **Cố ý không dùng cho `h3`** — mọi `h3` trong dự án render ở 13px, tức chúng là
  **nhãn** (vai `caption` của spec), không phải vai `h3 24px`. Một serif tương
  phản cao ở 13px mất hết nét mảnh và bó chặt dấu tiếng Việt xếp tầng.
- **Mặt đọc** (`--font-doc`, Be Vietnam Pro): sans humanist đọc tốt tiếng Việt có
  dấu, thân 17px trên di động và 18px trên desktop, dòng 1.7. Dấu tiếng Việt cần
  chiều cao dòng rộng hơn tiếng Anh — **giữ nguyên hai con số này**, không hạ về
  `body 16px` của spec.
- **Trên phim** (`--font-phim`, Source Serif 4): serif, vì nguồn là văn bản in.
  Chữ trên phim **không bao giờ** đổi màu theo trạng thái — phim là phim; trạng
  thái sống ở nhãn và ở viền khung. Quy tắc này thắng cả quy tắc tiêu đề: một
  `h3`/`h4` nằm trên phim vẫn là Source Serif 4.
- **Số hiệu, đường dẫn trích dẫn** (`--font-dia-chi`, JetBrains Mono): mono, vì
  `45/2019/QH14 > Điều 127 > Khoản 2` là một **địa chỉ**, không phải văn xuôi.
  Người dùng cần quét và so từng ký tự.
- Bề rộng đọc tối đa **68 ký tự** ở mặt đọc; dải khung không giới hạn ngang.
- Thang chữ của spec §5.2 (hero 72 → caption 13) và thang bo góc §5.3
  (6·10·16·24) đã có trong `@theme`. Thang chữ hiện là **đích để quy về dần** —
  các trang vẫn dùng giá trị tuỳ ý; thêm token không đổi hiển thị hiện tại.

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
