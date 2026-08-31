# Design

<!-- impeccable:design-schema 1 -->

Tài liệu này **đi theo giao diện, không dẫn giao diện**. Hướng thiết kế của KLAW
đã đổi ba lần; bản này ghi lại hệ thống thị giác **có thật** trong
`frontend-moi/src/styles.css`, chứ không suy ra một thế giới thị giác thứ tư.
Mỗi con số dưới đây được **tính trong mã** (`oklch → Oklab → linear sRGB → Y →
WCAG 2.1`), không ước lượng bằng mắt.

Bản trước mô tả một sản phẩm nền tối, ẩn dụ "máy đọc vi phim", brass là accent
duy nhất, font tự host, cấm WebGL. Sản phẩm đó vẫn còn trong git (29 commit chạm
`frontend/`) và là **bản tham chiếu cho các bảo đảm** không được đánh mất. Nó
không còn là mô tả của giao diện đang chạy. Hai hệ thiết kế không trộn từng phần
được — hướng sáng, cơ chế chiều sâu và số màu trạng thái đều xung khắc — nên
phải chọn một, và bản port đã chọn `Klaw_FE`.

Cái được **mang sang** từ bản cũ không phải màu, mà là **kỷ luật**: bốn màu
trạng thái có `abstain` trung tính, và mọi cặp màu chữ/nền đều phải đo tỉ lệ
tương phản rồi ghi lại con số cạnh token.

---

## Thế giới thị giác: giấy ngà dưới ánh sáng lạnh

Nền là **ngà sáng** — mặt giấy. Mực là **sapphire lạnh**. Accent là **vàng
đồng** ấm. Chiều sâu đến từ **glass/blur + bóng đổ ba tầng**, không từ
`perspective`/`translateZ`.

Ẩn dụ vẫn phải mang đúng một lời hứa: *đây là nguyên văn, và đây là chỗ nó đến
từ.* Giấy làm việc đó theo cách khác máy đọc vi phim — không phải rọi sáng một
khung phim, mà là **đặt bản gốc lên bàn**. Ba lớp không đổi, người dùng chọn đi
sâu tới đâu:

| Lớp | Nội dung | Ai dùng nhiều nhất |
|---|---|---|
| **Câu trả lời** | Tiếng Việt thường, có trích dẫn | người lao động |
| **Trích dẫn** | Chip dẫn tới điều, khoản, điểm, kèm nhãn hiệu lực | nhân sự |
| **Toàn văn** | Nguyên văn văn bản, câu trích được đánh dấu | sinh viên luật |

Một câu trả lời, ba lớp — không phải ba giao diện.

---

## Bảng màu

Token nguồn ở `frontend-moi/src/styles.css`. Cột HEX và cột tỉ lệ do
`scripts/` tính từ chính chuỗi `oklch()` trong tệp đó, không chép tay.

### Nền, mực, khung

| Token | oklch | HEX | Vai |
|---|---|---|---|
| `--background` | `0.985 0.008 100` | `#FBFAF4` | nền trang, ngà sáng |
| `--card` / `--popover` | `1 0.002 100` | `#FFFFFE` | thẻ, lớp nổi |
| `--foreground` | `0.26 0.03 250` | `#192532` | chữ thân |
| `--primary` | `0.38 0.085 255` | `#20436E` | mực sapphire: tiêu đề, nút chính |
| `--secondary` | `0.955 0.018 250` | `#E7F1FC` | nền phụ lạnh |
| `--muted-foreground` | `0.52 0.032 255` | `#5D6A7C` | chú thích, nhãn phụ |
| `--border` | `0.915 0.014 250` | `#DCE4EC` | đường kẻ **trang trí** |
| `--input` | `0.658 0.014 250` | `#8B929A` | ranh giới **ô nhập** — 3,00:1 |
| `--accent` | `0.83 0.115 88` | `#E6C36B` | vàng đồng, nền đặc |
| `--accent-foreground` | `0.3 0.05 70` | `#3E290F` | chữ trên nền accent |
| `--ring` | `0.642 0.1 90` | `#A48A3E` | vòng tiêu điểm — 3,20:1 |
| `--destructive` | `0.58 0.2 27` | `#D73431` | lỗi hệ thống (không phải hiệu lực) |

### Giấy và mực đậm (dùng trong màn ứng dụng)

| Token | HEX | Vai |
|---|---|---|
| `--color-paper-50` | `#FCFBF5` | mặt đọc |
| `--color-paper-100` | `#F6F3E8` | dải thông báo, hover |
| `--color-paper-200` | `#EDE8DB` | nhấn |
| `--color-ink-950` | `#13243C` | chữ trên nền brass đặc |
| `--color-ink-900` | `#1F3655` | bong bóng người dùng |
| `--color-brass-600` | `#8D6300` | accent làm **chữ** — 5,35:1 trên `--card` |
| `--color-brass-500` | `#DAB157` | accent làm **nền/viền** |
| `--color-brass-400` | `#EBD5A0` | accent nhạt |

### Màu trạng thái hiệu lực

Bốn màu, **sáu nhãn**. Không phải mỗi nhãn một màu: xem "Bốn màu cho sáu nhãn"
bên dưới để biết vì sao màu thứ năm là bất khả thi về số đo, và cái gì gánh
phần phân biệt thay cho nó.

| Token | oklch | HEX | Trên `--card` | Nhãn KLAW được gán |
|---|---|---|---|---|
| `--color-status-active` | `0.432 0.098 160` | `#00603D` | 7,64:1 | `con_hieu_luc` |
| `--color-status-partial` | `0.295 0.063 78` | `#3E2800` | 13,97:1 | `mot_phan_khong_xac_dinh` · `bi_sua_doi` |
| `--color-status-expired` | `0.39 0.149 32` | `#821100` | 10,32:1 | `het_hieu_luc` · `bi_thay_the` |
| `--color-status-neutral` | `= --muted-foreground` | `#5D6A7C` | 5,49:1 | `can_doi_chieu_tay` · `abstain` |

---

## Kỷ luật tương phản — đo, không đoán

Đây là phần được mang từ bản cũ sang, và là phần quan trọng nhất của tài liệu
này. Quy tắc bản cũ đặt ra và bản này giữ nguyên:

> Nếu một cặp trượt AA thì **làm sáng hoặc tối chữ, tuyệt đối không hạ chuẩn.**

### Đã đạt

| Cặp | Tỉ lệ |
|---|---|
| `--foreground` trên `--background` | **14,87:1** |
| `--foreground` trên `--card` | **15,50:1** |
| `--primary` trên `--background` | **9,62:1** |
| `--primary` trên `--card` | **10,03:1** |
| `--muted-foreground` trên `--background` | **5,27:1** |
| `--muted-foreground` trên `--card` | **5,49:1** |
| `--muted-foreground` trên `--color-paper-100` | **4,94:1** |
| `--background` trên nút `--primary` đặc | **9,62:1** |
| `--accent-foreground` trên nút `--accent` đặc | **8,12:1** |
| `--color-ink-950` trên nút `--color-brass-500` đặc | **7,72:1** |
| `--destructive` trên `--background` | **4,54:1** |

### Đã sửa ở pha 5 — trước / sau

| Cặp | Trước | Sau | Ngưỡng |
|---|---|---|---|
| `--color-status-active` làm chữ trên `--card` | 4,05:1 | **7,64:1** | 4,5 |
| `--color-status-partial` làm chữ trên `--card` | 2,34:1 | **13,97:1** | 4,5 |
| `--color-status-expired` làm chữ trên `--card` | 3,93:1 | **10,32:1** | 4,5 |
| `--color-brass-600` làm chữ trên `--card` | 3,15:1 | **5,35:1** | 4,5 |
| `--color-brass-600` trên `--color-paper-100` | 2,83:1 | **4,81:1** | 4,5 |
| `--ring` trên `--background` | 2,56:1 | **3,20:1** | 3,0 |
| `--ring` trên `--color-paper-100` | 2,40:1 | **3,00:1** | 3,0 |
| `--input` trên `--background` | 1,23:1 | **3,00:1** | 3,0 |

Nền badge pha 10% chính màu chữ là mặt **tệ nhất** một nhãn phải đứng lên, nên
nó được đo riêng: active **6,28:1** · partial **11,41:1** · expired **8,45:1** ·
neutral **4,55:1** — cả bốn vẫn qua 4,5.

### Còn để nguyên, có lý do

| Cặp | Tỉ lệ | Vì sao không sửa |
|---|---|---|
| `--color-brass-500` làm chữ trên `--background` | 1,93:1 | nó **không phải** màu chữ; chỉ nền/viền. Sửa nó là hợp thức hoá một cách dùng sai |
| `--border` trên `--background` | 1,23:1 | đường kẻ **trang trí**. WCAG 1.4.11 chỉ đòi 3:1 khi đường viền là cách DUY NHẤT nhận ra một control — nên `--input` tách ra và được sửa, còn đường kẻ thẻ giữ nguyên |

### Tách độ sáng — chỗ hỏng nặng nhất, đã đóng

Bản cũ coi **1,07:1** giữa `--do-thay` và `--xam-cho` là một khiếm khuyết và đã
sửa lên 1,44:1. Bảng màu `Klaw_FE` tệ hơn hẳn ở đúng cặp nguy hiểm nhất, và pha
5 sửa nó:

| Cặp | Trước | Sau |
|---|---|---|
| `status-active` vs `status-expired` | **1,03:1** | **1,35:1** |
| `status-active` vs `status-neutral` | 1,35:1 | 1,39:1 |
| `status-expired` vs `status-neutral` | 1,40:1 | 1,88:1 |
| `status-partial` vs `status-expired` | 1,68:1 | 1,35:1 |
| `status-active` vs `status-partial` | 1,73:1 | 1,83:1 |
| `status-partial` vs `status-neutral` | — | 2,54:1 |

**1,03:1 nghĩa là trong ảnh xám, "còn hiệu lực" và "hết hiệu lực" trông y hệt
nhau** — hai trạng thái đối lập nhất trong sản phẩm. Với người mù màu
deuteranopia, xanh 160° và đỏ 32° đều ngả vàng nâu, nên hue cũng không cứu được.

### Cách tìm ra bộ số

Ràng buộc kép: mỗi màu ≥ 4,5:1 làm chữ trên `--card`, `--background`,
`--color-paper-50`, `--color-paper-100` **và** trên nền badge pha 10% chính nó;
đồng thời hai màu bất kỳ tách nhau ≥ 1,35:1. Ép cả ba xuống đúng 4,5:1 thì chúng
bằng nhau về độ sáng (1,00:1) — sửa xong AA lại làm hỏng tách xám.

Bộ đang chạy giữ nguyên hue, chỉ hạ `L`, và hạ `C` xuống **đúng biên sRGB**.
Điểm cuối đó không có trong bản đề xuất pha 0 và là một sửa lỗi thật: ba trong
bốn giá trị đề xuất nằm **ngoài gam sRGB**, nên trình duyệt tự ánh xạ gam theo
CSS Color 4 (giảm chroma, **giữ** L) trong khi script đo lại kẹp từng kênh —
hai phép khác nhau, tức con số trong tài liệu sẽ không phải con số trên màn
hình. Hạ `C` vào trong gam làm hai phép trùng nhau.

### Bốn màu cho sáu nhãn — vì sao không phải sáu

Màu thứ năm là **bất khả thi về số đo**, không phải lười. Trên `--card`, ngưỡng
4,5:1 chặn độ sáng tối đa ở `Y+0,05 = 0,2333`; đen tuyệt đối cho `0,05`. Toàn bộ
dải khả dụng vì thế chỉ rộng **4,67:1**. Năm màu tách nhau ≥ 1,35 cần
`1,35⁴ = 3,32` — vừa lọt, nhưng buộc màu tối nhất xuống ~**14,9:1**, tức đậm
ngang `--foreground` (15,5:1). Một "màu trạng thái" trông y hệt chữ thân thì
không còn là tín hiệu.

Nên bốn màu, và **hình + chữ** gánh phần còn lại: hai nhãn dùng chung `expired`
khác nhau ở chữ (*"Đã bị thay thế"* nêu đích danh văn bản thay thế, *"Hết hiệu
lực"* thì không); hai nhãn dùng chung `partial` khác nhau ở chữ và ở **độ tin
cậy nói ra** (*"Đã bị sửa đổi"* biết đích danh điều khoản và ngày; *"Một phần
không xác định"* nói thẳng là không biết).

Cái giá đã đo và ghi ra: `status-partial` cách `--foreground` chỉ **1,11:1** —
trong ảnh xám nó gần như là chữ thân. Đó là hệ quả bắt buộc của việc kéo một
hue vàng 78° lên 4,5:1. Nhãn `partial` vì thế **luôn** có viền và chữ, không bao
giờ chỉ một chấm màu.

**Bất biến không được nới, kể cả khi số đo tốt lên: không trạng thái nào được
truyền đạt chỉ bằng màu.** Hình và chữ mang nghĩa; màu chỉ nhắc lại.

---

## Hai ràng buộc cứng — phải sửa ở pha sau

### 1. `abstain` phải trung tính

`abstain` là hành vi **đúng**, được tính điểm trong đánh giá. Nó không bao giờ
được mang màu cảnh báo, không icon lỗi, không rung.

`Klaw_FE` vi phạm: `dung-thu.tsx:248-269` tô nhánh "không đủ căn cứ" bằng
`--color-status-partial` (cam) kèm icon `TriangleAlert`. Khối đó đã bị xoá ở pha
0 cùng các câu trả lời đóng hộp, nên **vi phạm hiện không còn trong mã** — nhưng
hệ thiết kế vẫn **chưa có token trung tính** để dựng lại cho đúng.
`--color-status-neutral` ở bảng trên là chỗ dành sẵn cho nó.

Nếu giao diện tô đỏ hoặc cam câu "tôi không đủ căn cứ", nó dạy người dùng rằng
sự trung thực là thất bại. Đỏ chỉ dành cho **luật đã bị thay thế** — thứ duy
nhất khiến người dùng hành động sai.

### 2. `mot_phan_khong_xac_dinh` bị dịch mất nghĩa

`van-ban.ts` và `VanBanUI.tsx` gọi nhãn này là **"Hết hiệu lực một phần"** — bỏ
mất chữ **"không xác định"**, tức bỏ mất lời thú nhận giới hạn. Hai câu nói hai
chuyện khác nhau:

- *"Hết hiệu lực một phần"* — hệ thống **biết** phần nào hết hiệu lực.
- *"Bị sửa một phần, chưa xác định được điều này còn hiệu lực hay không"* — hệ
  thống **không biết**, và nói ra.

Chỉ câu thứ hai là đúng với dữ liệu. Nhãn phải mang cả mệnh đề đó, không rút gọn
cho vừa chip.

### 3. Ba màu cho năm nhãn

`PRODUCT.md` định nghĩa năm nhãn hiệu lực; `Klaw_FE` có ba màu trạng thái, bản
cũ có bốn. Chưa có chỗ hiện cho `bi_thay_the` (khác `het_hieu_luc` ở chỗ **phải
nêu đích danh văn bản thay thế**), `bi_sua_doi` (biết đích danh điều khoản, văn
bản và ngày), và `can_doi_chieu_tay`. Cộng thêm `abstain` cần màu trung tính.

Cách bản cũ giải bài này và nên giữ: **`switch` trên chuỗi, nhãn lạ rơi xuống
`default` an toàn**, kèm `nhanDayDu` cho trình đọc màn hình — chứ không phải một
`Record<>` ném lỗi khi backend thêm nhãn thứ sáu.

---

## Chữ

Bốn họ, nạp qua **Google Fonts CDN**, `display=swap`, hai trọng lượng mỗi họ:

| Token | Họ | Dùng cho |
|---|---|---|
| `--font-display` | Playfair Display 600/700 | tiêu đề |
| `--font-sans` | Be Vietnam Pro 400/600 | giao diện |
| `--font-doc` | Source Serif 4 400/600 | nguyên văn văn bản luật |
| *(lớp `.font-jetbrains`)* | JetBrains Mono 400 | số hiệu văn bản |

Bản cũ **tự host** qua `@fontsource`. Bản này phụ thuộc `fonts.googleapis.com` +
`fonts.gstatic.com` — một phụ thuộc bên thứ ba trên đường tải trang chính, và
một đường rò referrer. Đây là **khác biệt đã biết**, không phải sơ suất; đổi lại
thì cần thêm bước build. Ghi ở đây để quyết định sau, không để trôi.

Số hiệu văn bản (`45/2019/QH14`) luôn dùng chữ đơn cách. Nó là **định danh**,
không phải văn xuôi.

---

## Hình khối, chiều sâu, chuyển động

- **Bo góc**: `--radius: 0.75rem`, sáu bậc từ `sm` (`-4px`) tới `3xl` (`+12px`).
- **Bóng đổ ba tầng**: `--shadow-soft` (nhấc nhẹ) · `--shadow-elegant` (lớp
  nổi) · `--shadow-gold` (nhấn accent) · `--shadow-depth` (viền + đổ, dùng qua
  `@utility surface-depth`).
- **Bốn gradient**: `--gradient-parchment` · `--gradient-ink` · `--gradient-gold`
  · `--gradient-aurora`.
- **13 `@utility`** gói các tổ hợp trên lại: `bg-gradient-*`, `text-gradient-gold`,
  `shadow-*`, `surface-depth`, `lift-hover`, `focus-brass`, `text-on-dark-muted`.
- **19 `@keyframes`**. Chiều sâu là **glass/blur + shadow**, không `perspective`.
  WebGL **được dùng** (three + R3F + drei ở hero và nền màn đăng nhập). Ràng buộc
  "cấm WebGL" ở bản DESIGN.md trước đã bị chính KLAW-p4 phá trước khi có bản port
  này; ràng buộc đó được gỡ ở đây thay vì giả vờ nó còn hiệu lực.

### `prefers-reduced-motion` — giảm chuyển động, không gỡ phản hồi trạng thái

`styles.css` giữ luật quét `*` làm lưới an toàn (animation mới thêm sau vẫn bị
bắt), rồi **mở đúng hai ngoại lệ** bằng selector hạng lớp — hạng lớp thắng `*`
nên không phải sửa luật gốc:

- `.thinking-dot` chuyển sang keyframe **chỉ đổi opacity**, bỏ `translateY(-3px)`,
  chậm còn 1,4s, giữ `animation-delay` của `nth-child` để ba chấm vẫn nhấp so le.
- `.brass-caret` vốn đã chỉ đổi opacity ở 1Hz, dưới xa ngưỡng 3Hz gây co giật;
  giữ, chậm còn 1,2s.

Lý do là một con số của sản phẩm: **một lượt trả lời mất 10–60 giây.** Tắt sạch
animation trong khoảng đó để người bật `prefers-reduced-motion` ngồi nhìn màn
hình đứng im, không biết hệ thống còn sống hay đã treo. Đó không phải giảm
chuyển động, đó là **gỡ phản hồi trạng thái**.

Hai lớp này hiện **chưa có nơi gọi** trong JSX — giao diện phát token đi cùng
các câu trả lời đóng hộp đã bị xoá. Hợp đồng CSS được giữ có chủ đích: pha nối
backend cần đúng một trạng thái chờ cho lượt 10–60 giây, và đây là thứ nó phải
dùng lại.

Trên ngưỡng 10 giây, một chỉ báo không xác định đọc như treo máy: phải có **tên
bước đang chạy**, tiến trình xác định, và **nút huỷ**. Hoãn 300–500ms trước khi
hiện chỉ báo để câu trả lời nhanh không loé rồi tắt. Luôn có timeout dẫn tới lỗi
thật kèm nút thử lại — không treo im lặng.
`Klaw_FE` có **0 `AbortController`** trong toàn bộ `src/`: không nút huỷ, không
timeout, không bước. Nợ đã biết.

---

## Responsive

Đã kiểm bằng trình duyệt thật ở **390px** và **1440px** trên cả 11 màn hình:
`document.scrollWidth === clientWidth` ở mọi trang, không trang nào tràn ngang.

- **390px**: một cột. Dải lọc thu thành nút "Bộ lọc (n)" mở sheet; điều hướng
  xuống thanh dưới; màn soạn thảo tách thành hai tab *Nhập thông tin* / *Xem
  trước*. Vùng chạm tối thiểu 44px.
- **1440px**: hai đến ba cột. Đọc câu trả lời và nguyên văn **cùng lúc**, không
  chuyển qua lại.
- Điểm gãy theo **nội dung**, không theo tên thiết bị.

---

## Ràng buộc không được vi phạm

- Định danh văn bản bằng `so_ky_hieu` **cho người đọc**; khoá duy nhất tuyệt đối
  là `doc_id`. **Không bao giờ** định danh bằng tên. 54/57 văn bản nhúng cả
  `số <so_ky_hieu>` vào `ten`, `ten` không nhất quán hoa/thường; và
  `65/2006/QH11` thuộc **hai** văn bản khác nhau.
- **Không bao giờ render `documents.tinh_trang` thô.** Cột đó gắn "Còn hiệu lực"
  cho đúng bốn nghị định lương tối thiểu đã bị thay thế — những văn bản KLAW bắt
  được là sai. Mọi trạng thái đi qua `effectivity.py`.
- Cảnh báo hiệu lực **không được** giấu vào tooltip hay metadata.
- `abstain` **không bao giờ** mang màu lỗi.
- Không trạng thái nào được truyền đạt **chỉ bằng màu**.
- Chữ nguyên văn từ CSDL: **không** rút gọn, **không** sửa chính tả.
- Giao diện **không được ngụ ý mọi lĩnh vực được phủ như nhau**: cụm Lao động có
  luật + nghị định + thông tư + chế tài; năm bộ luật còn lại chỉ có bản thân bộ
  luật.
- Số phạm vi corpus (số văn bản, số điều khoản, số lĩnh vực) lấy từ API ở
  `/pham-vi`, **không viết cứng** trong giao diện.

---

## Nợ thiết kế đã biết, xếp theo mức

| Mức | Việc |
|---|---|
| Cao | Bốn màu trạng thái không đạt AA làm chữ; `status-active` vs `status-expired` tách 1,03:1 |
| Cao | Chưa có token trung tính cho `abstain` và `can_doi_chieu_tay` |
| Cao | `mot_phan_khong_xac_dinh` bị dịch thành "Hết hiệu lực một phần" |
| Cao | `--ring` 2,56:1, dưới ngưỡng 3:1 của WCAG 1.4.11 cho vòng tiêu điểm |
| Trung bình | `--color-brass-600` làm chữ 3,15:1 và đang dùng làm chữ khắp nơi |
| Trung bình | `--input` dùng chung `--border` 1,23:1 — ranh giới ô nhập cần 3:1 |
| Trung bình | Font qua CDN bên thứ ba thay vì tự host |
| Trung bình | 0 `AbortController`: không nút huỷ, không timeout cho lượt 10–60 giây |
| Thấp | Hero không có ô hỏi thật, chỉ hai nút CTA |
| Thấp | `/dang-nhap` và `/dang-ky` không có `h1` |
