# KLAW — hỏi nối tiếp: giữ ngữ cảnh mà không nhượng bộ kiểm chứng

Ngày: 2026-09-02 · Trạng thái: đã duyệt, chờ thi công
Tiếp nối: `2026-09-02-tro-ly-phap-luat-design.md` mục 8 (Pha 4, đã hoãn tới đây)

## 1. Vấn đề, đo được trên UI thật

Bảng `traces`, chuỗi hội thoại thật của chủ dự án:

```
10:19  "tôi đang chuẩn bị nghỉ việc"   answer            21 claim   42,1s   ✅
10:19  "bạn làm được những gì"         gioi_thieu         0 claim    1,1s   ✅
10:20  "liệt kê bảng cho tôi"          partial_coverage   0 claim    8,5s   ❌
```

Lượt thứ ba trỏ về **cái bảng trong câu trả lời của lượt thứ nhất**. Hệ thống
không có lịch sử hội thoại nên xử lý nó như một câu độc lập, và trả về:

> Mình tìm được văn bản chi phối câu hỏi của bạn, nhưng chưa đọc được nội dung
> của nó… Câu hỏi của bạn nằm trong 120/2025/QH15 (LUẬT PHÒNG, CHỐNG MA TÚY);
> Không số (Luật Thương mại số Không số).

Rồi hỏi lại ba câu về hợp đồng lao động.

### 1.1 Bốn khiếm khuyết tách bạch

**K1 — không có lịch sử hội thoại.** `TraCuuRequest` chỉ có `query`. Gốc bệnh.

**K2 — câu không có nội dung pháp lý vẫn đi vào truy hồi.** `"liệt kê bảng cho
tôi"` khớp **nhiễu**: `120/2025/QH15` (Luật Phòng chống ma túy, `depth=shallow`)
và `8532` (Luật Thương mại, `depth=shallow`).

**K3 — dữ liệu xấu lọt ra mặt người dùng.** `documents` id `8532` có
`so_ky_hieu = 'Không số'` và `ten = 'Luật Thương mại số Không số'` — crawler
ghép `"Luật Thương mại" + " số " + so_ky_hieu`. Hệ thống trình bày `Không số`
như một **số hiệu văn bản**.

**K4 — câu hỏi lại sai chủ đề.** `hoi_lai` hỏi về hợp đồng lao động cho một câu
`"liệt kê bảng"`, vì nó không biết câu hỏi rỗng nội dung.

### 1.2 Cái KHÔNG hỏng

Lượt `"tôi đang chuẩn bị nghỉ việc"` cho **21 luận điểm qua cả hai tầng** trong
42 giây. Pipeline lõi đang tốt; thiếu là ngữ cảnh giữa các lượt.

Và **FE đã giữ hội thoại**: `frontend/src/routes/dung-thu.tsx:83` có
`luuTru: LuotDaXong[]` tích lũy từng lượt xong và render tất cả. Lịch sử đã nằm
sẵn ở client — nó chỉ không được gửi lên.

## 2. Nguyên tắc ràng buộc

> Lịch sử hội thoại chỉ dùng để **làm câu hỏi tự đứng được**. Nó **KHÔNG BAO GIỜ**
> chống đỡ một khẳng định. Câu hỏi sau khi giải nghĩa đi qua ĐỦ truy hồi → tầng 1
> → tầng 2 như một câu hỏi mới.

Hệ quả: một lịch sử bị bịa (client gửi gì cũng được) chỉ tạo ra một câu hỏi
khác, rồi câu đó vẫn phải chịu đủ hai tầng kiểm. **Không có đường nào lách
verifier**, nên client-gửi-lịch-sử là an toàn ở đây và không cần session phía
server.

Quyết định của chủ dự án 2026-09-02: câu nối tiếp **tạo lại câu hỏi đầy đủ rồi
tra lại**, không trả lời từ trích dẫn cũ. Mọi khẳng định kiểm chứng lại từ đầu.

## 3. Phần 1 — lịch sử lên dây và node giải nghĩa

**Hợp đồng API.** `TraCuuRequest` thêm `lich_su: list[LuotTruoc] = []`, tối đa
**3 lượt gần nhất**. `LuotTruoc`:

| trường | kiểu | vì sao cần |
|---|---|---|
| `cau_hoi` | `str` | chủ đề của lượt trước |
| `tra_loi` | `str` (cắt ≤ 400 ký tự) | `"liệt kê bảng"` cần biết câu trả lời trước CÓ bảng |
| `duong_dan` | `list[str]` | định danh chính xác điều khoản lượt trước đã dẫn |

Cả ba đã có trong `LuotDaXong` của FE. Cắt 400 ký tự vì prompt giải nghĩa chạy
mỗi lượt nối tiếp; toàn văn câu trả lời cũ làm nó phình mà không thêm tín hiệu.

**Node mới `giai_nghia`**, chạy **TRƯỚC `route`** và **chỉ khi `lich_su` khác
rỗng** — lượt đầu không tốn thêm một token nào. Chạy trên model route
(`google/gemini-2.5-flash-lite`, đo 1,56s).

Phải trước `route` vì routing dựa trên câu ĐÃ giải nghĩa: `"còn model nào khác"`
sau một lượt `gioi_thieu` là câu hỏi về trợ lý, không phải tra cứu.

**Đầu ra:** `{cau_hoi_day_du: str | null, ly_do: str}`. `null` nghĩa là không đủ
ngữ cảnh để giải — không được đoán bừa. Khi `null`, đi đường ngõ cụt đã có
(`_ngo_cut` + `hoi_lai`), tức nói cái đã biết rồi hỏi lại.

**Cấm:** node này KHÔNG được thêm nội dung pháp luật vào câu hỏi. Nó chỉ giải
đại từ và tham chiếu (`"cái bảng đó"`, `"tôi"`, `"còn nếu…"`). Prompt phải nói
rõ, và test phải chặn: câu đã giải nghĩa không được chứa số Điều hay số hiệu văn
bản mà câu gốc VÀ lịch sử đều không có.

## 4. Phần 2 — hiện câu đã giải nghĩa

`state["query"]` bị thay để chạy pipeline. Câu gốc phải giữ nguyên cho hiển thị
và cho `traces.query` — nếu `traces` ghi câu đã giải nghĩa thì chương đánh giá
đọc lại sẽ thấy những câu hỏi người dùng chưa từng gõ.

State thêm: `cau_hoi_goc: str` và `cau_hoi_day_du: str | None`.
`TraCuuResponse` thêm `cau_hoi_day_du: str | None`.

UI ghi một dòng trước câu trả lời: *"Mình hiểu câu hỏi của bạn là: …"* — chỉ khi
nó KHÁC câu gốc.

Vì sao bắt buộc: giải nghĩa sai là chế độ hỏng chắc chắn xảy ra. Không có dòng
này, người dùng nhận câu trả lời cho một câu **họ không hỏi** mà không có cách
nào biết, và cũng không có cách nào sửa.

## 5. Phần 3 — thôi khẳng định điều chưa chứng minh

`assemble._phu_mot_phan` hiện viết *"Mình tìm được **văn bản chi phối** câu hỏi
của bạn"*. Với một khớp nhiễu đó là **lời nói sai**: Luật Phòng chống ma túy
không chi phối `"liệt kê bảng cho tôi"`.

Sửa thành điều đúng được: mình tìm được mấy văn bản **khớp từ ngữ** trong câu
hỏi nhưng chưa có toàn văn.

**KHÔNG dựng bộ phân loại "câu hỏi có nội dung pháp lý hay không".** Đó lại là
một danh sách từ khoá pháp lý cần thẩm quyền domain — đúng thứ đã bị từ chối cho
bộ lọc `hoi_lai` (xem `2026-09-02-tro-ly-phap-luat-design.md`). Và điểm RRF
không tới được tầng này: `KLawState.retrieved` là `list[int]`,
`Retriever.provision_ids()` bỏ điểm.

Có Phần 1 rồi thì đường này là **lưới an toàn**, không còn là đường chính.

## 6. Phần 4 — không hiện `so_ky_hieu` dị dạng

Khi `so_ky_hieu` không chứa chữ số nào (`'Không số'`), nó không phải một số hiệu
— hiển thị `ten` thay vì trình bày `Không số` như một định danh.

**Quy tắc, không phải chuỗi cứng:** nếu `ten` kết thúc bằng `" số " + so_ky_hieu`
thì cắt hậu tố đó đi. Đó chính là cách crawler dựng `ten`, nên quy tắc này đúng
cho mọi văn bản có `so_ky_hieu` dị dạng, kể cả những cái chưa xuất hiện. Viết
cứng `" số Không số"` sẽ bỏ sót dòng thứ hai xuất hiện với một dạng khác.

Kiểm bằng chữ số, KHÔNG bằng danh sách giá trị xấu: `any(c.isdigit() for c in
so_ky_hieu)`. Mọi số hiệu văn bản pháp luật Việt Nam đều có chữ số (năm ban
hành), nên phép kiểm này không loại oan một số hiệu thật nào.

Áp ở mọi chỗ hiển thị `so_ky_hieu` cho người đọc: `assemble` (`coverage_note`,
`nguon`), `kho.py`. KHÔNG đụng `so_ky_hieu` trong DB hay trong `duong_dan` —
đó là khoá dữ liệu, sửa nó là sửa neo trích dẫn.

## 7. File chạm

**Backend:** `src/models/schemas.py` (`LuotTruoc`, `TraCuuRequest.lich_su`,
`TraCuuResponse.cau_hoi_day_du`) · `src/agents/state.py` (`lich_su`,
`cau_hoi_goc`, `cau_hoi_day_du`) · `src/agents/nodes/giai_nghia.py` (MỚI) ·
`prompts/giai_nghia.v1.md` (MỚI) · `src/agents/graph_tra_cuu.py` (node đầu vào
mới) · `src/api/routes.py` (truyền `lich_su`, trả `cau_hoi_day_du`) ·
`src/agents/nodes/assemble.py` (Phần 3, Phần 4)

**Frontend:** `frontend/src/lib/klaw.ts` (kiểu) · `frontend/src/lib/api.ts` (gửi
`lich_su`) · `frontend/src/routes/dung-thu.tsx` (dựng `lich_su` từ `luuTru`) ·
`frontend/src/components/klaw/TheKetQua.tsx` (hiện câu đã giải nghĩa)

## 8. Ngoài phạm vi

- Không đụng `abstain_threshold` hay bất kỳ điều kiện quyết định `result_type`
- Không đụng tầng 1, tầng 2, `prompts/assemble.v1.md`
- Không session phía server (mục 2 giải thích vì sao không cần)
- Không thêm `result_type` mới — bảy điểm đồng bộ đã sập bốn lần, và pha này
  không cần loại mới
- Không dựng bộ phân loại nội dung pháp lý (mục 5)

## 9. Chi phí

**Một lượt LLM thêm cho mỗi lượt hỏi NỐI TIẾP**, không phải mỗi lượt. Trên
`gemini-2.5-flash-lite` là ~1,5s và ~$0,00005. Lượt đầu của mỗi hội thoại không
tốn gì thêm.

## 10. Kiểm chứng

Test bắt buộc:

- `"liệt kê bảng cho tôi"` + lịch sử về nghỉ việc → câu đã giải nghĩa chứa
  "báo trước" hoặc "nghỉ việc", KHÔNG còn rỗng nội dung
- lịch sử rỗng + câu rỗng nội dung → `cau_hoi_day_du is None`, đi đường ngõ cụt
- câu đã giải nghĩa KHÔNG chứa số Điều/số hiệu vắng mặt ở cả câu gốc và lịch sử
- `traces.query` ghi câu GỐC, không ghi câu đã giải nghĩa
- lượt đầu (lịch sử rỗng) KHÔNG gọi `giai_nghia` — đếm lượt gọi LLM, đừng `raise`
  (bài học Pha 2: `hoi_lai` bắt `Exception` nên nuốt `AssertionError` của fake và
  làm chết ba lưới canh)
- `so_ky_hieu = 'Không số'` không xuất hiện trong chuỗi người dùng đọc

Cổng đo: `eval/run_trap.py` sau khi thi công — pha này đụng node ĐẦU VÀO của
graph, nên mọi nhóm bẫy đều nằm dưới nó.
