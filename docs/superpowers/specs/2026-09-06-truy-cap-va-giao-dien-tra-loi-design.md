# Truy cập bằng tài khoản và dọn giao diện trả lời — thiết kế

Ngày: 2026-09-06. Nhánh: `feat/tro-ly-phap-luat`. Trạng thái: đã duyệt cả năm phần.

## 1. Mục tiêu

Một người mở KLAW phải thấy đúng một cửa vào trợ lý, đăng nhập rồi mới hỏi,
thấy kho luật ngay khi vào trang Tra cứu, và đọc câu trả lời chỉ gồm luật còn
hiệu lực. Năm việc, cùng một tinh thần: bớt thứ thừa, giữ thứ đúng.

## 2. Bối cảnh tìm thấy trong mã

- `/chat` (mục nav "Trò chuyện") chỉ render màn chào `KlawChat` rồi đẩy câu
  hỏi sang `/dung-thu?q=`. Không phải lỗi điều hướng; là vỏ rỗng còn lại từ
  bản Lovable. Cửa vào thật là `/dung-thu` (mục nav "Trợ lý KLAW").
- Backend đã bắt đăng nhập: khi Supabase được cấu hình,
  `bao_ve.xac_thuc_nguoi_goi` trả 401 "Cần đăng nhập để dùng tính năng này"
  cho mọi lượt gọi AI không có token. Người mới được `ghi_nhan_nguoi_dung` gán
  gói `free` = 50 lượt/tháng theo `config/han_muc.yaml`. Khi Supabase CHƯA cấu
  hình (máy dev), backend cho ẩn danh và đếm theo IP.
- Frontend chưa chặn trang nào. Landing có nút "Dùng thử agent" và bốn link
  khác trỏ `/chat`; bảng giá ghi "Dùng thử miễn phí" cho hai gói trả phí chưa
  có thanh toán; JSON-LD ghi "Bản dùng thử miễn phí".
- `GET /tim-kiem` bắt buộc `q` (min 1 ký tự). Không có endpoint liệt kê văn
  bản, nên tick "Nghị định" (696) mà ô từ khoá rỗng thì trang trống.
- Trong card trả lời, danh sách "Trích dẫn — bấm để mở nguyên văn" là chỗ DUY
  NHẤT hiện nhãn hiệu lực và nhóm "Quy định cũ"; khung đối chiếu bên cạnh chưa
  có nhãn nào. Khối đỏ "Cảnh báo hiệu lực" vẽ `warnings[]` của backend; dòng
  gây nhiễu là "45/2019/QH14 hết hiệu lực một phần: bị 19/2023/QH15 sửa đổi…"
  xuất hiện ở gần như mọi câu trả lời về Bộ luật Lao động.

## 3. Quyết định của chủ sản phẩm

| # | Câu hỏi | Quyết định |
|---|---|---|
| 1 | Khối "Cảnh báo hiệu lực" | Bỏ hẳn. Người dùng chỉ cần luật còn hiệu lực; phần không còn hiệu lực không hiển thị. |
| 2 | Danh sách trích dẫn cuối card | Bỏ danh sách, chuyển nhãn hiệu lực sang khung đối chiếu; bỏ luôn nhóm "Quy định cũ" (theo quyết định 1); giữ một danh sách "Căn cứ" chỉ khi câu trả lời không có tag bấm được. |
| 3 | Truy cập | Chặn ở frontend, giữ URL `/dung-thu`. Nút vào trợ lý vẫn mở giao diện chat nhưng ô hỏi khoá cho đến khi đăng nhập. Tài khoản mới là gói Miễn phí 50 lượt/tháng. Bảng giá thêm thẻ Miễn phí, gói trả phí "Sắp ra mắt". Đổi URL sang `/tro-ly` để sau sub-project soạn thảo trong chat. |
| 4 | Tra cứu khi ô từ khoá rỗng | Luôn hiện danh sách văn bản, kể cả chưa tick bộ lọc. |
| 5 | Thứ tự | Gói này thi công TRƯỚC plan `2026-09-06-soan-thao-trong-chat.md`. |

Ghi nhận rủi ro đã được chủ sản phẩm chấp nhận ở quyết định 1: người cố hỏi
về một văn bản đã bị thay thế (backend vẫn cho vào văn xuôi khi câu hỏi nêu
đích danh số ký hiệu, xem `assemble._neo_vao_van_ban`) sẽ chỉ thấy trạng thái
"Đã bị thay thế" khi mở khung đối chiếu, không còn dòng đỏ trong card.

## 4. Phần 1 — Gộp "Trò chuyện" vào "Trợ lý KLAW"

### 4.1 Hành vi

- `/dung-thu` khi chưa có lượt nào hiện màn chào giống Image 6: biểu tượng cân
  trên nền `bg-gradient-ink`, tiêu đề "Xin chào, tôi là KLAW", đoạn "Tôi tra
  cứu quy định pháp luật lao động Việt Nam theo điều, khoản, điểm và soạn thảo
  văn bản pháp lý. Mỗi câu trả lời nêu rõ văn bản và điều khoản để bạn tự kiểm
  chứng.", bốn thẻ gợi ý có icon và tiêu đề (Tra cứu quy định / Soạn hợp đồng /
  Nghĩa vụ của người sử dụng lao động / Soạn đơn) với đúng bốn câu mẫu hiện có
  trong `KlawChat.SUGGESTIONS`, dòng "Chọn một gợi ý để điền vào ô soạn bên
  dưới."
- Bấm thẻ CHỈ điền câu vào ô soạn và đưa tiêu điểm vào đó, không gửi. Hành vi
  hiện tại của `/dung-thu` (gửi ngay) bỏ.
- Placeholder ô soạn: "Hỏi về quy định pháp luật hoặc yêu cầu soạn văn bản…".
  Dưới ô soạn đúng một dòng miễn trừ: "KLAW cung cấp thông tin tham khảo,
  không thay thế tư vấn của luật sư. Vui lòng kiểm chứng với văn bản quy phạm
  pháp luật đang có hiệu lực." (nếu dòng tương đương đã có thì giữ một, không
  hai).
- Mục nav "Trò chuyện" biến mất ở vỏ ứng dụng (`AppShell.NAV`) và ở nav trang
  giới thiệu (`AppNav`, mục `/chat` đổi thành `/dung-thu` nhãn "Trợ lý KLAW").
- `/chat` chỉ còn là chuyển hướng 3xx sang `/dung-thu`, mang theo `?q` nếu có.
  Link đã chia sẻ không 404; không còn giao diện riêng.

### 4.2 Thay đổi file

| File | Việc |
|---|---|
| `frontend/src/components/klaw/ManChao.tsx` (mới) | Màn chào tách từ `KlawChat`: props `{ onChonGoiY: (cau: string) => void }`. Không header, không ô nhập (hai thứ đó của `/dung-thu`). |
| `frontend/src/routes/dung-thu.tsx` | Nhánh `chuaHoiGiCa` render `<ManChao>`; bỏ `GOI_Y`; đổi placeholder; dòng miễn trừ. |
| `frontend/src/routes/chat.tsx` | `beforeLoad` ném `redirect({ to: "/dung-thu", search })`, không `component`. |
| `frontend/src/components/KlawChat.tsx` | Xoá. |
| `frontend/src/components/app/AppShell.tsx` | Bỏ mục `/chat`; bỏ import `MessagesSquare` nếu không còn dùng. |
| `frontend/src/components/AppNav.tsx` | `/chat` → `/dung-thu`, nhãn "Trợ lý KLAW". |
| `frontend/src/routes/index.tsx` | Năm link `/chat` → `/dung-thu`. Nhãn: "Dùng thử agent" → "Mở trợ lý KLAW"; "Bắt đầu trò chuyện" → "Hỏi KLAW"; "Trò chuyện với KLAW" → "Mở trợ lý KLAW"; "Hỏi KLAW một câu" và "Mở trợ lý" giữ. |
| `frontend/src/routes/huong-dan.tsx` | Link "Thử ngay với KLAW" → `/dung-thu`, nhãn "Mở trợ lý KLAW". |
| `frontend/src/routeTree.gen.ts` | Tự sinh lại. |

### 4.3 Kiểm

`npm run typecheck`, `npm run lint`, `npm run build`. Chrome thật: vào
`/dung-thu` thấy màn chào, bấm thẻ thì ô soạn có chữ và tiêu điểm; vào
`/chat?q=abc` thì URL đổi thành `/dung-thu?q=abc`; nav không còn "Trò chuyện".

## 5. Phần 2 — Đăng nhập mới hỏi được

### 5.1 Hành vi

- `/dung-thu` dùng `useAuth()` (đã có: `session`, `loading`, `chuaCauHinh`).
  Định nghĩa `canDangNhap = !chuaCauHinh && !loading && user === null`.
  - `loading`: chỗ ô soạn là một khung trống cùng chiều cao, không nhấp nháy.
  - `canDangNhap`: chỗ ô soạn là thẻ `TheDangNhap`: "Đăng nhập để hỏi KLAW.
    Tài khoản mới dùng gói Miễn phí." + nút "Đăng nhập" (→ `/dang-nhap`,
    `search: { next: "/dung-thu" }`) + nút "Tạo tài khoản" (→ `/dang-ky`, cùng
    `next`). Bấm thẻ gợi ý khi đang khoá thì đi tới `/dang-nhap?next=/dung-thu`
    (không có ô để điền).
  - `chuaCauHinh` (Supabase không có biến môi trường): không khoá gì, khớp
    backend đang cho ẩn danh. Đây là đường máy dev chạy.
  - Con số "50 lượt" KHÔNG viết cứng trong thẻ khoá: nguồn số là
    `config/han_muc.yaml`, và `HanMucThang` đã hiện nó sau đăng nhập. Viết cứng
    là lặp lại lỗi `TrialMeter` "còn N/20 lượt" mà mã đã gỡ.
- `/dang-nhap` và `/dang-ky` nhận `next` qua `validateSearch`; danh sách trắng
  đúng hai giá trị `"/dung-thu"` và `"/soan-thao"` (`lib/quay-lai.ts`); giá trị
  khác bị bỏ — không kiểm tiền tố, để `navigate({ to })` vẫn được kiểm kiểu. Sau khi thành công điều hướng tới `next`, mặc
  định `/dung-thu` như hiện nay. Câu "Đang mở phiên dùng thử…" đổi thành "Đang
  mở trợ lý KLAW…" ở cả hai trang.
- Lỗi 401/403 từ API: `lib/api.ts` đổi thông điệp "Máy chủ KLAW từ chối yêu
  cầu vì thiếu quyền truy cập." thành "Bạn cần đăng nhập để dùng tính năng
  này."; `BaoLoi` khi `kind === "unauthorized"` hiện thêm link "Đăng nhập".
  Đây là đường của màn Soạn thảo (POST `/soan-thao` đi qua cùng cổng) — màn đó
  KHÔNG bị khoá ở gói này để không đụng file mà plan soạn-thảo-trong-chat sắp
  tách.
- Landing và metadata: xem bảng 4.2 cho nhãn nút; `__root.tsx` JSON-LD
  `offers.description` "Bản dùng thử miễn phí" → "Gói Miễn phí".
- Bảng giá `/bang-gia`:
  - Thêm thẻ đầu tiên `mien-phi`: tên "Miễn phí", tagline "Cho người mới bắt
    đầu", giá 0 (hiện "0đ" cả tháng và năm), tính năng: "Tra cứu không giới
    hạn", "50 lượt hỏi AI/tháng", "Xuất Word, PDF"; nút "Tạo tài khoản" →
    `/dang-ky`.
  - Gói "Cá nhân": "50 lượt hỏi AI/tháng" → "500 lượt hỏi AI/tháng" (khớp gói
    `pro` trong `han_muc.yaml`; 50 trùng gói Miễn phí là mâu thuẫn).
  - Gói "Cá nhân" và "Doanh nghiệp": nút "Sắp ra mắt", `disabled` +
    `aria-disabled`, không link. Gói "Tổ chức lớn" giữ "Liên hệ báo giá".
  - Thẻ Miễn phí hiện chữ "Miễn phí" thay giá "0 ₫" và dòng phụ "Không cần thẻ
    thanh toán". Bảng so sánh thêm cột Miễn phí (bốn cột). Hai câu hỏi thường
    gặp "Có đăng ký được ngay không?" và "Hạn mức lượt hỏi tính thế nào?" viết
    lại: có tài khoản Miễn phí ngay; 50 lượt/tháng đếm ở máy chủ, soạn bản thảo
    cũng tính một lượt; gói trả phí chưa mở.
  - `HanMucThang` đã có ở trang này, giữ nguyên.
  - Con số "50"/"500" trong danh sách tính năng là chữ tiếp thị của trang giá,
    cùng loại với "5 người dùng"; khác với thẻ khoá ở `/dung-thu`, nó không tự
    nhận là số đo của tài khoản, nên viết cứng ở đây chấp nhận được.

### 5.2 Thay đổi file

`frontend/src/routes/dung-thu.tsx`, `frontend/src/components/klaw/TheDangNhap.tsx`
(mới), `frontend/src/routes/dang-nhap.tsx`, `frontend/src/routes/dang-ky.tsx`,
`frontend/src/lib/api.ts`, `frontend/src/components/klaw/BaoLoi.tsx`,
`frontend/src/routes/__root.tsx`, `frontend/src/routes/bang-gia.tsx`,
`frontend/src/lib/quay-lai.ts` (mới), `frontend/scripts/kiem-quay-lai.ts` (mới),
`frontend/package.json`.
Backend: không đổi.

### 5.3 Kiểm

`npm run kiem` (đủ chuỗi). Test giọng `tests/test_agents/test_giong_tra_loi.py`
(chỉ quét `TheKetQua.tsx`; `TheDangNhap` không dùng cụm bị cấm dù không bị
quét). Chrome thật: đăng xuất → `/dung-thu` hiện màn chào + thẻ khoá; bấm
"Đăng nhập" → về `/dung-thu` sau khi vào; đăng nhập rồi hỏi một câu; `/bang-gia`
có thẻ Miễn phí và hai nút "Sắp ra mắt" không bấm được.

## 6. Phần 3 — Tra cứu luôn có danh sách văn bản

### 6.1 Hợp đồng API (mới, đọc, không cổng AI)

`GET /van-ban` trong `src/api/routes_van_ban.py`.

Tham số: `loai: list[str] | None`, `co_quan: list[str] | None`, `tu_nam`,
`den_nam` (1900–2100, `tu_nam > den_nam` → 422 như `/tim-kiem`),
`sap_xep: Literal["moi_nhat", "con_hieu_luc_truoc"] = "moi_nhat"`,
`limit` (1–50, mặc định 20), `offset ≥ 0`, `as_of_date`. Giá trị `loai`/`co_quan`
không có trong kho → 422 qua `_kiem_gia_tri_loc` (dùng chung với `/tim-kiem`).

Chỉ trả văn bản `depth <> 'metadata'` — cùng tập "1626 văn bản có toàn văn" mà
trang đang nói; văn bản chỉ có thông tin không mở được nguyên văn nên không
liệt kê ở đây.

```python
class VanBanTomTat(BaseModel):
    doc_id: str
    so_ky_hieu: str
    bo_luat: str                 # documents.ten
    loai_van_ban: str
    co_quan_ban_hanh: str | None
    ngay_ban_hanh: date | None
    hieu_luc: HieuLucOut         # phán quyết cấp văn bản, từ danh_gia_toan_bo

class DanhSachVanBanResponse(BaseModel):
    tong: int                    # của toàn tập khớp bộ lọc, không phải của trang
    limit: int
    offset: int
    sap_xep: str
    ket_qua: list[VanBanTomTat]
```

Sắp xếp: `moi_nhat` = `ngay_ban_hanh DESC NULLS LAST, so_ky_hieu`;
`con_hieu_luc_truoc` = cùng thứ tự nhóm hiệu lực mà `/tim-kiem` dùng
(`array_position` theo danh sách doc_id đã xếp từ `danh_gia_toan_bo`), chốt đuôi
`so_ky_hieu`. Không bao giờ trả `documents.tinh_trang` thô — cùng lý do với
`/tim-kiem`.

### 6.2 Hành vi frontend (`routes/tra-cuu.index.tsx`)

- Khi `q.trim() === ""`: gọi `/van-ban` với `loai`, `co_quan`, `tu_nam`,
  `den_nam`, `sap_xep`, `limit=20`, `offset=(trang-1)*20`. Câu "Nhập từ khoá để
  bắt đầu." bỏ.
- Dòng tổng: "1626 văn bản" khi không lọc; "696 văn bản · Nghị định" khi có
  chip (nối các chip đang bật bằng " · ").
- Mỗi dòng: số ký hiệu (font mono), tên, dòng phụ "loại · cơ quan · năm" (bỏ
  phần trống), `BadgeHieuLuc hieuLuc={hieu_luc.verdict}`; cả dòng là
  `<Link to="/tra-cuu/$docId">`.
- Chip sắp xếp: "Liên quan nhất" không hiện khi không có từ khoá; nếu URL đang
  mang `sap_xep=lien_quan` mà `q` rỗng thì coi là `moi_nhat`. Có từ khoá: hành
  vi cũ giữ nguyên.
- Phân trang dùng `trang` sẵn có; đổi bộ lọc thì `trang` về đầu (như hiện nay).
- Lỗi mạng/422: không nuốt thành danh sách rỗng, hiện `BaoLoi` như nhánh tìm
  kiếm đang làm.

### 6.3 Thay đổi file

`src/api/routes_van_ban.py`, `src/models/schemas.py`,
`tests/test_api/test_danh_sach_van_ban.py` (mới, cùng cách dựng fixture với
`test_tim_kiem.py`), `frontend/src/lib/klaw.ts` (kiểu `VanBanTomTat`,
`DanhSachVanBan`, predicate `laDanhSachVanBan`), `frontend/src/routes/tra-cuu.index.tsx`.

### 6.4 Kiểm

pytest cho endpoint: mặc định 20 dòng `moi_nhat`; lọc `loai=["Nghị định"]`
đúng `tong`; `tu_nam > den_nam` → 422; `loai` lạ → 422; `limit=51` → 422;
`hieu_luc` không bao giờ là `tinh_trang`. FE: typecheck/lint/build; Chrome
thật: vào `/tra-cuu` có danh sách, tick "Nghị định" → dòng tổng đổi và danh
sách thu hẹp, bấm một dòng → `/tra-cuu/$docId`.

## 7. Phần 4 — Card trả lời chỉ dẫn luật còn hiệu lực

### 7.1 Hành vi

- Bỏ khối "Cảnh báo hiệu lực" ở MỌI nhánh kết quả (`answer`, `bang`,
  `partial_coverage`, `abstain`, `out_of_scope`). `warnings` vẫn nằm trong
  response và traces; giao diện không vẽ.
- Bỏ danh sách "Trích dẫn — bấm để mở nguyên văn và tự đối chiếu" và nhóm "Quy
  định cũ". Căn cứ có `hieu_luc ∈ {het_hieu_luc, bi_thay_the}` (nhóm 4 theo
  `nhomHieuLuc`) không hiển thị ở bất kỳ đâu trong card.
- Chốt an toàn: khi `catManh(answer)` không sinh mảnh `cite`/`doc` nào VÀ còn
  ít nhất một căn cứ ngoài nhóm 4, hiện khối "Căn cứ": các dòng bấm được (số ký
  hiệu, đường dẫn, câu trích) mở khung đối chiếu; sắp theo `xepTrichDan`. Có tag
  bấm được thì khối này không hiện. Bằng chứng vì thế không bao giờ mất đường
  mở, kể cả khi mô hình quên gắn tag.
- Khung đối chiếu hiện nhãn hiệu lực: `BadgeHieuLuc` ngay dưới số ký hiệu
  trong header, khi người mở truyền `hieuLuc`. Đây là chỗ duy nhất còn nói
  trạng thái hiệu lực trong luồng hỏi–đáp.
- `KhoiLienKet` (link cổng luật) giữ nguyên.

### 7.2 Thay đổi file

| File | Việc |
|---|---|
| `frontend/src/components/klaw/TheKetQua.tsx` | Xoá `KhoiCanhBao`, `DanhSachTrichDan` và mọi chỗ gọi; thêm `KhoiCanCu`; bỏ import `ghiChuHieuLuc`. Prop `warnings` không còn dùng để render — giữ trong kiểu nếu còn nơi khác đọc, bỏ nếu không. |
| `frontend/src/lib/trich-dan.ts` | Bỏ `ghiChuHieuLuc` (chỉ danh sách cũ dùng). Giữ `xepTrichDan`, `nhomHieuLuc`. |
| `frontend/scripts/kiem-xep-trich-dan.ts` | Bỏ các assert của `ghiChuHieuLuc`; giữ phần thứ tự. |
| `frontend/src/hooks/use-doi-chieu.ts` | `MoDoiChieu.hieuLuc?: string \| null`, đưa xuống trạng thái để `KhungDoiChieu` nhận. |
| `frontend/src/components/klaw/KhungDoiChieu.tsx` | Prop `hieuLuc?: string \| null`; render `BadgeHieuLuc` trong header khi có. Ghi chú thay cho câu "KHÔNG BAO GIỜ giấu vào tooltip": trạng thái hiệu lực nay nằm ở nhãn này. |
| `frontend/src/routes/dung-thu.tsx` | `chonTrichDan` và đường `doc:` (mở tại căn cứ đầu) truyền `hieuLuc: trichDan.hieu_luc`. |
| (không có script render cho `KhungDoiChieu`) | Nhãn trong header kiểm bằng typecheck và Chrome thật ở Phần 5; `kiem-khung.ts` là kiểm của khung soạn thảo, không liên quan. |

Backend: không đổi. `docs/bo-luat-agent.md` không có quy tắc nào về khối cảnh
báo; chính sách mới ghi tại spec này.

### 7.3 Kiểm

`npm run kiem`; test giọng (không thêm cụm bị cấm; "Căn cứ" là chữ trung
tính). Chrome thật: một câu trả lời về thử việc — không còn khối đỏ, không còn
danh sách cuối card; bấm "Khoản 1 Điều 25" trong văn xuôi → khung mở, header
có nhãn hiệu lực; một câu trả lời `partial_coverage` cũng không có khối đỏ.

## 8. Phần 5 — Thứ tự, không gian làm việc, kiểm chứng chung

- Thi công trên `feat/tro-ly-phap-luat` tại checkout chính (một luồng, tuần
  tự; backend chỉ một endpoint nên không cần worktree song song). Thứ tự: Phần
  3 backend → Phần 4 → Phần 1 → Phần 2 → Phần 3 frontend, để hai file nặng
  (`TheKetQua.tsx`, `dung-thu.tsx`) mỗi file chỉ bị một chuỗi sửa liên tiếp.
- Sau gói này mới chạy plan `docs/superpowers/plans/2026-09-06-soan-thao-trong-chat.md`.
  Các mốc plan đó neo vào vẫn còn: `Luot` bọc `{children}` trong
  `<div className="mt-4">`, nhánh `if (loai === "partial_coverage")` trong
  `NoiDungKetQua`, state `dangMo` trong `dung-thu.tsx`.
- Kiểm chung cuối: `make lint`; `python -m pytest -q --ignore=tests/test_infra
  --ignore=tests/test_services/test_effectivity.py` (hai fail đã biết:
  `test_tang_sau_moi_so_ky_hieu_la_duy_nhat`,
  `test_chi_nhung_canh_ngay_mau_thuan_DA_BIET_moi_duoc_bo`); `cd frontend && npm
  run kiem`; kiểm bằng Chrome thật ba màn và chụp vào `.tham-dinh-shots/`.
- Không chạy `make check` / `make format` (ghi đè cây). Không stage file bẩn có
  từ trước phiên.

## 9. Ngoài phạm vi

- Thanh toán, nâng gói, giao diện quản lý gói: chưa làm; bảng giá chỉ nói "Sắp
  ra mắt".
- Đổi URL `/dung-thu` → `/tro-ly`: sau sub-project soạn thảo trong chat.
- Khoá màn Soạn thảo trước khi bấm "Dựng bản thảo": để sau khi
  `KhongGianSoanThao` được tách (plan soạn-thảo-trong-chat, Task 7).
- Liệt kê văn bản tầng chỉ-có-thông-tin (metadata) trong Tra cứu.
- Thay đổi backend `warnings`/`citations`: không; eval và traces vẫn cần đủ.
