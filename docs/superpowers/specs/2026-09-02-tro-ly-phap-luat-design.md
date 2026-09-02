# KLAW — từ công cụ tra văn bản thành trợ lý pháp luật

Ngày: 2026-09-02 · Trạng thái: đã duyệt, chờ thi công
Tiếp nối: `docs/superpowers/specs/2026-08-27-klaw-design.md` (thiết kế gốc)

## 1. Vấn đề, đo được

Người dùng hỏi *"Hiện tại có bao nhiêu bộ luật?"*. Chạy thật qua graph
(2026-09-02):

```
intent=tra_cuu  retrieved=10  deep=30  shallow=0  claims=0  insufficient=True
result_type : abstain
answer      : (rỗng)   coverage_note: None   nguon: []
```

Ba mươi điều khoản tầng sâu trong tay, **không một luận điểm nào**, và người hỏi
nhận về một màn hình trắng. Khi truy hồi có chạm tầng nông thì nhánh
`partial_coverage` chạy và dán ra một danh sách văn bản kèm câu
*"Hệ thống KHÔNG diễn giải trong trường hợp này — văn bản gốc được nêu đích danh
dưới đây để bạn tự đối chiếu."* Hai mặt của cùng một gốc bệnh.

### 1.1 Bốn khiếm khuyết tách bạch

**K1 — thiếu ý định cho câu hỏi về kho.** `prompts/route.v1.md` có bốn intent,
không cái nào hợp một câu hỏi *về kho dữ liệu*; prompt tự dặn "không chắc thì
chọn `tra_cuu`". Câu hỏi bị đẩy sang đường tra cứu *nội dung luật*, truy hồi tìm
chữ "bộ luật" và trúng những văn bản có chữ "Luật" trong tiêu đề.

Dữ liệu làm điều này gay hơn: `loai_van_ban = 'Bộ luật'` trả **12 dòng** — 6 bộ
hiện hành cộng 6 bản đã bị thay (BLLĐ 2012, BLHS 1999, BLDS 2005, BLTTDS 2004,
BLTTHS 2003, BLHH 2005). Đếm thô ra 12 là sai.

**K2 — bối cảnh đưa cho model quá mỏng.** `generate_claims.build_context`
(dòng 48–58) chỉ đưa `id`, `so_ky_hieu`, `duong_dan`, `tieu_de`, `noi_dung`.
Thiếu `loai_van_ban` nên model không phân biệt Bộ luật với Thông tư, không áp
được thứ bậc hiệu lực. Thiếu hiệu lực — dù `expand()` đã tính xong cho từng
dòng — nên model không có cách nào ưu tiên văn bản còn áp dụng. Đây là gốc của
lỗi lương tối thiểu đã gặp ở Plan 1.

**K3 — lối thoát quá rộng.** Quy tắc 4 của `prompts/generate_claims.v1.md`:
*"Nếu các điều luật cung cấp KHÔNG trả lời được câu hỏi, đặt
`insufficient_evidence: true` và `claims: []`. Đây là câu trả lời ĐÚNG, không
phải thất bại."* Một lối thoát rộng đặt ngay cạnh một nhiệm vụ khó. Model đi lối
đó, và không có vòng nào thử lại.

**K4 — giọng hệ thống và ngõ cụt.** `assemble.py:363` và
`frontend/src/components/klaw/TheKetQua.tsx:431` đều nói bằng giọng một hệ
thống tự thuật về giới hạn của mình. Mọi nhánh abstain/partial kết thúc bằng một
danh sách văn bản: không nhánh nào nói *cái đã biết*, không nhánh nào hỏi *dữ
kiện còn thiếu*.

### 1.2 Cái KHÔNG hỏng

`prompts/assemble.v1.md` **đã có** cấu trúc ba tầng (trả lời thẳng → theo trường
hợp → ranh giới), xưng "bạn", cấm tiên đoán kết quả. Nó không bao giờ chạy vì
không có luận điểm nào tới nơi. Sửa được sản lượng của `generate_claims` thì
phần lớn yêu cầu về hành văn tự có — **không viết lại `assemble.v1.md`**.

## 2. Nguyên tắc ràng buộc

> Mọi đường trả lời phải kết thúc ở **một trong hai**: một phép **tra bảng xác
> định** (SQL trên `documents`/`provisions`, không thể sai), hoặc **claim đã qua
> đủ tier 1 + tier 2**. Không có loại thứ ba. "Model suy luận ra" không phải một
> đường trả lời.

Hệ quả bắt buộc: câu trả lời về kho **luôn xưng "trong kho của mình"**, không bao
giờ phát biểu thay cho nền pháp luật Việt Nam. "Việt Nam hiện có 6 Bộ luật" là
ảo giác đúng loại hệ thống này tồn tại để chặn — và là loại verifier **không bắt
được**, vì không có trích dẫn nào để kiểm.

## 3. Bẫy đồng bộ — chặn bằng test ngay từ đầu

Thêm một ý định mới đòi sửa **SÁU** chỗ (bản đầu của spec này ghi bốn — thiếu
hai, xem bên dưới):

1. `prompts/route.v1.md` — mô tả intent
2. `src/agents/nodes/route.py` — giá trị trong `Intent`
3. `src/agents/nodes/route.py` — giá trị trong `INTENT_SCHEMA`
4. `src/agents/graph_tra_cuu.py` — `_RE_TAT` nếu intent rẽ tắt
5. `src/agents/nodes/assemble.py` — nhánh dựng kết quả
6. `src/models/schemas.py` — `Literal` của `TraCuuResponse.result_type`

Thiếu chỗ 6 thì **traces ghi xanh còn HTTP trả 500**, vì traces được ghi trước
khi response được serialize. Đã sập hai lần.

Thiếu chỗ 3 thì tệ hơn và im lặng hơn: `INTENT_SCHEMA` đi vào
`llm.chat(json_schema=…)`, nên **JSON schema chặn model chọn ý định mới**, rồi
`route` nuốt giá trị lạ bằng mặc định `tra_cuu`. Cả tính năng thành mã chết —
không test nào đỏ, không log nào bật, không HTTP nào lỗi. Phát hiện 2026-09-02
trong lúc thi công Pha 1, sau khi brief giao việc chỉ liệt kê năm chỗ.

Hai test bắt buộc, cả hai SO HAI TẬP thay vì liệt kê tay — mọi lần lỗi này lọt
đều là vì một test đếm tên cụ thể:
- `test_response_model_biet_moi_gia_tri_cua_ResultType` — `ResultType` vs `Literal`
- `test_moi_Intent_deu_co_mat_trong_PROMPT_va_trong_JSON_SCHEMA` — `Intent` vs
  `INTENT_SCHEMA` vs prompt
- `test_moi_y_dinh_KHONG_PHAI_tra_cuu_deu_phai_re_tat` — `_RE_TAT` vs `set(Intent)`

FE không cần nhánh mới cho `hoi_ve_kho`: nó mang `answer` nên rơi đúng nhánh mặc
định của `TheKetQua.tsx`.

## 4. Pha 0 — chặn đường chạy

Đã xong trong phiên khảo sát 2026-09-02:

- `src/config.py`: `env_file=(".env", ".env.local")`. Trước đó chỉ đọc `.env`,
  file không tồn tại → mọi biến rơi về mặc định trong code, không một dòng lỗi.
- `src/config.py`: validator cho `as_of_date`, chuỗi rỗng → `None`. Trước đó
  `AS_OF_DATE=` — đúng cách dùng `.env.example` ghi — làm Settings nổ lúc khởi
  động.
- `eval/datasets/golden_qa.yaml`: `duyet_boi: agent` → `nguoi` trên cả 77, theo
  xác nhận của chủ dự án.

Còn lại:

**0a — `llm.chat` không thử lại khi content rỗng.** `_post_with_retry` chỉ bắt
`HTTPStatusError` và `TransportError`. HTTP 200 kèm content rỗng thì `raise`
thẳng. Đo được: `mistralai/mistral-nemo` trả rỗng 2/5 lần trên prompt `route` →
mỗi lần là một HTTP 500 ở node đầu tiên. Ở `rewrite_query` lỗi này bị **nuốt**
rồi fallback lặng lẽ.

**0b — backoff cho 429 quá ngắn.** `_RETRYABLE_STATUS` có 429 nhưng
`retry_backoff_base = 0.2` với `max_retries = 3` cạn cả bốn lần thử trong 1,4
giây. Quan sát được một 429 xuyên thủng khi chạy hai câu hỏi liên tiếp. Honor
header `Retry-After` khi có; không có thì dùng backoff riêng, dài hơn, cho 429.

**0c — `eval/run.py`** tính `golden_qa_da_review` từ `duyet_boi` trong YAML thay
vì hardcode `False` (dòng 246) và hardcode câu cảnh báo (dòng 305). Cập nhật ba
tài liệu mang cảnh báo cũ: `docs/bm25-tuning.md`,
`docs/embedding-comparison.md`, `docs/duyet-golden-qa.md`.

Không đụng nội dung câu trả lời → **không chạy cổng đo**.

## 5. Pha 1 — ý định `hoi_ve_kho`

Câu hỏi *về kho* tách khỏi đường tra cứu *nội dung luật*.

**Nhận diện:** intent mới trong `route.v1.md` — "hỏi kho này có những văn bản
nào, bao nhiêu, phủ tới đâu, có văn bản X không". Rẽ tắt ngay sau `route` qua
`_RE_TAT`: không truy hồi, không sinh luận điểm, không hai tầng kiểm.

**Trả lời:** một hàm thuần SQL trong `src/services/` — không LLM cho phần số
liệu. Ba dạng truy vấn:

- đếm/liệt kê theo `loai_van_ban`, **lọc bản đã bị thay** để "Bộ luật" ra 6 chứ
  không phải 12

  Lọc bằng `effectivity.danh_gia_theo_id(engine, doc_id, as_of)` — cùng cơ chế
  cạnh đồ thị mà `expand()` dùng — rồi **loại verdict `het_hieu_luc` và
  `bi_thay_the`**. Đây là một quy tắc, không phải danh sách cứng sáu doc_id.

  KHÔNG lọc bằng `documents.tinh_trang`: sáu bản cũ đều mang `chua_xac_dinh`,
  còn năm trong sáu bản hiện hành mang `HHL1P` — cột đó không tách được hai
  nhóm. KHÔNG lọc bằng `documents.depth`: `deep`/`shallow` nói mức đã nạp, không
  nói hiệu lực; ở kho hiện tại nó trùng khớp một cách tình cờ và sẽ sai ngay khi
  nạp sâu một văn bản đã hết hiệu lực.

  Đo được 2026-09-02: ba bản cũ (BLLĐ 2012, BLDS 2005, BLHS 1999) ra
  `het_hieu_luc` với `tin_cay: cao`; ba bản hiện hành ra `con_hieu_luc` hoặc
  `mot_phan_khong_xac_dinh`. Năm trong sáu bộ hiện hành đang bị sửa đổi một
  phần — câu trả lời phải nói ra điều đó, không được trình bày chúng như nguyên
  vẹn.
- phủ theo lĩnh vực, dùng `documents.depth` (`deep` / `shallow` / `metadata`) để
  nói đúng mức phủ
- có/không một văn bản cụ thể, tra theo `so_ky_hieu`

**Khung lời bắt buộc:** mở bằng "Trong kho của mình…", đóng bằng một câu nói rõ
đây là phạm vi kho chứ không phải toàn bộ văn bản pháp luật Việt Nam. Câu đóng
này là **hằng số trong mã**, không do model sinh — model không được phép quên nó.

**Test:** câu hỏi "có bao nhiêu Bộ luật" phải ra `6`, và chuỗi trả về phải chứa
cụm giới hạn phạm vi. Có cổng đo.

## 6. Pha 2 — giọng và ngõ cụt

Thuần lời, không đổi logic, **không chạy cổng đo**.

**Cấm xuất hiện trong bất kỳ chuỗi nào người dùng đọc:** "hệ thống", "không diễn
giải", "chưa đủ căn cứ", "truy hồi", "database", "để bạn tự đối chiếu". Bắt bằng
một test quét chuỗi trên cả `assemble.py` và các nhánh của `TheKetQua.tsx`, để
lời cũ không bò về sau này.

**Mỗi abstain và partial phải có hai nửa:** nửa đầu nói *cái đã biết* (nguyên tắc
chung rút được từ nguồn đang có, hoặc tên văn bản chi phối); nửa sau hỏi *đúng
dữ kiện còn thiếu* để đi tiếp. Ngõ cụt hiện nay — một danh sách văn bản và hết —
bị loại.

Chỗ sửa: `assemble.py:363` (`coverage_note` của `_phu_mot_phan`), nhánh abstain
trơ ở `assemble.py:385/392/412`, và `TheKetQua.tsx:431` + nhánh `abstain` dòng
324.

## 7. Pha 3 — bối cảnh dày hơn và vòng cứu

Pha rủi ro nhất. **Có cổng đo.**

**3a — `build_context` dày hơn.** Thêm `loai_van_ban` và verdict hiệu lực vào
mỗi khối; gộp các điều khoản cùng một văn bản dưới một đầu mục thay vì dàn phẳng
ngăn bằng `---`. Hiệu lực lấy lại từ `state["expanded"]` — `expand()` đã tính,
**không tính lại** (tính lại với `canh_di_vao` rỗng sẽ luôn ra `con_hieu_luc`,
đúng lỗi mà `graph_tra_cuu.py:136` đang chặn).

**3b — siết lối thoát.** Sửa quy tắc 4 của `generate_claims.v1.md`: trước khi
được đặt `insufficient_evidence: true`, model phải soi qua nguyên tắc chung,
ngoại lệ, và chế tài trong tập đang có. Giữ nguyên tinh thần "thiếu căn cứ là
câu trả lời đúng" — chỉ dựng một ngưỡng cửa trước lối thoát đó.

**3c — vòng cứu: KHÔNG DỰNG.** Quyết định 2026-09-02, có lý do đo được.

Kế hoạch ban đầu: khi `claims == 0` mà `expanded` khác rỗng, chạy
`generate_claims` một lần nữa với khung khác.

Nó bị bỏ vì **không còn ca nào tái hiện `claims == 0` với nguồn dùng được**. Ca
duy nhất từng cho `claims=0` là "Hiện tại có bao nhiêu bộ luật?" — và Pha 1 đã
lấy câu đó ra khỏi đường này hoàn toàn (nó đi `hoi_ve_kho`, tra bảng, không qua
`generate_claims`). Ba câu đo của Pha 3 đều đã ra `answer` với 5–9 claims TRƯỚC
khi sửa; không câu nào tái hiện chỗ nghẽn.

Dựng 3c khi đó là thêm MỘT LƯỢT LLM trên MỌI đường abstain để giải một vấn đề
không có ca tái hiện. Nếu sau này cổng đo cho ra một câu `claims == 0` mà
`expanded` khác rỗng, dựng lại — kèm ca đó làm test.

Không đụng `abstain_threshold` (giữ 0.5) và không đụng `assemble.v1.md`.

### 7.1 Số đo của 3a — thí nghiệm cô lập, 2026-09-02

Tập điều khoản **CỐ ĐỊNH** (không truy hồi, không route, không tier2), nên chênh
lệch duy nhất giữa hai nhánh là bố cục bối cảnh: Điều 3 + Điều 4 của ba nghị định
lương tối thiểu chồng nhau — `90/2019/NĐ-CP` (đã bị thay), `74/2024/NĐ-CP`,
`293/2025/NĐ-CP` — sau `expand` là 51 điều khoản. Câu hỏi: "lương tối thiểu vùng
I là bao nhiêu". Một lượt LLM mỗi nhánh mỗi lần, n=6 mỗi nhánh, đo đủ 12/12.

| | kéo nghị định ĐÃ BỊ THAY vào claims | claims TB | token_in TB |
|---|---|---|---|
| bối cảnh CŨ | **4/6** | 5,2 | 6.351 |
| bối cảnh MỚI | **0/6** | 3,5 | 6.033 |

`insufficient_evidence` là `False` ở **cả 12 lượt** — nhãn hiệu lực trong bối cảnh
KHÔNG làm model ngờ vực nguồn rồi abstain nhiều hơn (rủi ro chính của 3a, vì
verdict áp đảo trên corpus là `mot_phan_khong_xac_dinh` chứ không `con_hieu_luc`).

Đây là lần đầu lỗi lương tối thiểu của Plan 1 có một TỈ LỆ: 67% số lượt, không
phải một ca biên.

**Đánh đổi phải ghi ra:** claims TB tụt 5,2 → 3,5. Phần lớn là vì bối cảnh cũ
sinh thêm claims TỪ CHÍNH các nghị định đã chết. Nhưng so riêng các lượt cũ sạch
(4 claims) với lượt mới (3,5), vẫn có mức giảm thật ~0,5. Đổi nửa luận điểm lấy
việc không dẫn văn bản hết hiệu lực là đổi đúng — một luận điểm dựa trên nghị
định đã bị thay tệ hơn không có luận điểm nào — nhưng nó là đánh đổi, không phải
cải thiện thuần.

**Chi phí token phụ thuộc TẬP, không phải một con số:** −5,0% trên tập nghị định
này (phần gộp dòng `tieu_de` trùng khít `noi_dung` lấn phần thêm trường), +7,5%
trên một tập 76 điều khoản của Bộ luật Lao động. Đại khái hoà.

n=6 là chỉ báo mạnh, KHÔNG phải một kiểm định thống kê.

## 8. Pha 4 — hỏi nối tiếp

Sau khi 1–3 đã đo xong. `TraCuuRequest` hiện chỉ có `query`; thêm lịch sử đụng
hợp đồng API, FE, state của graph và khoá cache.

Ràng buộc không được nhượng bộ: **claim của lượt sau phải kiểm chứng trên điều
khoản truy hồi cho chính lượt đó.** Ngữ cảnh cũ được dùng để *hiểu câu hỏi*
(giải "tôi", "chuyện đó"), không bao giờ để *chống đỡ một khẳng định*. Thiếu ranh
giới này thì một lượt sau thừa hưởng căn cứ chưa kiểm của lượt trước — đúng lỗ
hổng cả hệ thống tồn tại để bịt.

Thiết kế chi tiết pha này viết sau khi 1–3 xong.

## 9. Cổng đo

Chạy `eval/run.py` (77 golden) + `eval/run_trap.py` sau **Pha 1** và **Pha 3**.
Bỏ qua sau Pha 0 và Pha 2 (không đổi nội dung câu trả lời).

Mốc so sánh: kết quả trước khi bắt đầu, chụp một lần ở đầu Pha 1.

## 9b. Món nợ phát hiện trong lúc thi công (2026-09-02)

**`/pham-vi` đang báo sai cho người dùng.** `src/api/routes.py:563` (`_pham_vi`)
phân tầng theo SỐ ĐIỀU KHOẢN THẬT, và ruling ở đó viết rõ lý do. Ruling ấy nay
lạc hậu: migration `016_tang_nong.sql` chèn cho MỖI văn bản `shallow` đúng một
hàng `mo_dau`, nên `so_dieu_khoan > 0` không còn tách được hai tầng. Kết quả:
trang xếp **125** văn bản vào tầng "có toàn văn" khi thật ra chỉ **49** —
phóng đại độ phủ 2,5 lần, và đó là con số đưa cho khách xem. Cần task riêng.

**`ly_do` của effectivity không tất định giữa hai đường.** Với văn bản bị NHIỀU
văn bản khác sửa, `danh_gia_theo_id` và `danh_gia_toan_bo` nêu tên một văn bản
sửa KHÁC nhau trong cùng tập — cùng verdict, cả hai câu đều đúng sự thật, nhưng
cùng một văn bản hiện hai lý do khác nhau tuỳ người dùng đi qua màn nào
(`routes_tim_kiem.py` vốn dùng đường gộp, `expand`/`tier1` dùng đường từng-cái).
Đo được 5/130 văn bản 2026-09-02. Có TỪ TRƯỚC đợt này. Hướng sửa: nêu văn bản
sửa MỚI NHẤT, tất định — nhưng đụng `effectivity.py` nên cần task riêng.

**`65/2006/QH11` trùng hai dòng trong `documents`.** Lỗi dữ liệu, phát hiện khi
dựng phép khớp số hiệu. Ngoài phạm vi.

## 10. Ngoài phạm vi đợt này

- Không đổi `abstain_threshold`
- Không viết lại `prompts/assemble.v1.md`
- Không đụng đường soạn thảo văn bản (25 mẫu) và `huong_dan_soan_thao`
- Không dựng lại chunks / đổi model nhúng
