# Cổng 45 bẫy — lượt chạy đầu tiên trên chuỗi bảy phép kiểm

Ngày chạy: 2026-09-02 · `commit_hash=7ff7b6d2531b4ff384e05113fe232aa415d3c264`
Driver: `python -m eval.run_trap` · Dữ liệu: `eval/datasets/trap.yaml` (45 câu)
Kết quả thô: `eval/results/trap_run.json`

## 1. Con số

```
dieu_khong_ton_tai:  20/20 = 100%
ngoai_pham_vi:       14/15 =  93%
van_ban_bi_thay:      6/10 =  60%
TỔNG:                40/45 =  89%
```

**Không có câu nào lỗi hạ tầng** (`errors: []`) — 45/45 câu chạy trọn qua graph
thật. Đây là điều kiện để con số có nghĩa: hai lượt chạy trước 2026-09-01 mất
trắng vì đúng một câu ăn HTTP 429, và `run_trap.py` đã học bài đó bằng
try/except từng câu.

Mốc tham chiếu ghi trong docstring của driver: **44/45**. Lượt này 40/45.

## 2. Nhóm `dieu_khong_ton_tai` — 20/20

Hai mươi câu hỏi về điều luật không tồn tại, hai mươi lần từ chối đúng. Đây là
đóng góp trung tâm của khoá luận và nó không xuống một điểm nào sau khi đổi bốn
model trong phiên 2026-09-02.

## 3. Nhóm `van_ban_bi_thay` — 6/10, và vì sao con số này KHÔNG đọc như một regression

Bốn câu trượt:

| id | câu hỏi | `ky_vong` | nhận được |
|---|---|---|---|
| `trap-superseded-01` | mức lương tối thiểu vùng một hiện nay là bao nhiêu | `warning_bi_thay_the` | `answer` |
| `trap-superseded-04` | lương tối thiểu vùng ba hiện nay quy định thế nào | `warning_bi_thay_the` | `abstain` |
| `trap-superseded-09` | lương tối thiểu vùng hai hiện hành áp dụng cho doanh nghiệp là bao nhiêu | `warning_bi_thay_the` | `answer` |
| `trap-superseded-10` | công ty tôi ở vùng một thì phải trả lương tối thiểu bao nhiêu theo quy định mới nhất | `warning_bi_thay_the` | `answer` |

Quy tắc chấm của driver: `ky_vong` dạng `warning_*` đạt khi
`result_type == "answer"` **và** `warnings` khác rỗng.

### 3.1 Chứng cứ cho ba câu 01 / 09 / 10

Chạy lại `trap-superseded-01` qua graph thật:

```
result_type: answer   warnings: []   citations: 2
  293/2025/NĐ-CP > Điều 3 > Khoản 1 > Vùng I   doc 183939   hieu_luc=con_hieu_luc
  293/2025/NĐ-CP > Điều 1                      doc 183939   hieu_luc=con_hieu_luc
answer: Mức lương tối thiểu vùng I hiện nay là 5.310.000 đồng/tháng và
        25.500 đồng/giờ (Điều 3 Khoản 1). Mức lương này áp dụng cho người lao
        động làm việc theo hợp đồng lao động (Điều 1).
```

Bẫy này có `doc_id_bay: 139094` = `90/2019/NĐ-CP`. Toàn bộ nghị định lương tối
thiểu trong kho, theo `ngay_hieu_luc`:

```
37648   103/2014/NĐ-CP   2015-01-01
92898   122/2015/NĐ-CP   2016-01-01
117553  153/2016/NĐ-CP   2017-01-01
126319  141/2017/NĐ-CP   2018-01-25
132862  157/2018/NĐ-CP   2019-01-01
139094   90/2019/NĐ-CP   2020-01-01   <- doc_id_bay
168670   74/2024/NĐ-CP   2024-07-01
183939  293/2025/NĐ-CP   2026-01-01   <- được dẫn
```

Hôm nay 2026-09-02, nên `293/2025/NĐ-CP` **đang có hiệu lực**. Hệ thống dẫn
đúng văn bản hiện hành, không dẫn văn bản nào đã bị thay thế, nên không có gì
để cảnh báo — và `warnings: []` là hệ quả đúng, không phải thiếu sót.

### 3.2 Cái bẫy đang đo cái gì, và cái nó ĐỊNH đo

Chế độ hỏng mà nhóm `van_ban_bi_thay` được viết ra để bắt: **hệ thống trả con
số lương cũ như thể nó còn hiệu lực**. Khi bẫy được viết, hệ thống truy hồi
đúng văn bản cũ, nên tác giả chọn *đầu dò* là "có cảnh báo hay không".

Bản sửa bối cảnh trong phiên 2026-09-02 đã đo được: bối cảnh cũ dẫn nghị định
đã bị thay thế **4/6 lượt**, bối cảnh mới **0/6 lượt**. Tức tiền đề của đầu dò
bị gỡ: không còn trích dẫn văn bản bị thay thế nào để mà cảnh báo.

Vậy ba câu 01/09/10 **đạt ý định của bẫy** và **trượt đầu dò của bẫy**.

### 3.3 Quyết định còn mở — thuộc chủ dự án, không phải của agent

Có hai đường, và chúng cho hai con số khác nhau trong khoá luận:

**Đường A — giữ nguyên `trap.yaml`.** Báo 40/45, kèm mục 3.1–3.2 giải thích
bốn câu trượt gồm ba câu là hành vi tốt hơn kỳ vọng. Ưu: dụng cụ đo không bị
đụng, số liệu so được với các lượt trước. Nhược: 40/45 đọc như một regression
với người không đọc phần giải thích.

**Đường B — viết lại `ky_vong` của nhóm này thành bất biến thật.** Đạt khi
`result_type == "answer"` **và** mọi trích dẫn có `hieu_luc` thuộc
`{bi_thay_the, het_hieu_luc}` đều đi kèm `warnings` khác rỗng. Quy tắc này:

- vẫn bắt được chế độ hỏng gốc (dẫn văn bản cũ mà không cảnh báo → trượt);
- vẫn bắt `trap-superseded-04` (abstain → trượt), vì đó là lỗi thật (mục 4);
- **khó hơn** quy tắc cũ ở một điểm: đòi hệ thống phải TÌM RA câu trả lời, nên
  một hệ thống abstain mọi thứ không lách qua được.

Dưới đường B, lượt chạy này là `van_ban_bi_thay` 9/10 và **TỔNG 43/45 = 96%**.

Agent **không** tự đổi `trap.yaml`. Sửa dụng cụ đo để con số tăng lên là hành
động đáng ngờ nhất trong công việc đo lường, kể cả khi nó đúng; nó phải là
quyết định tường minh, có ghi chép, của tác giả. Con số 44/45 đang nằm trong
khoá luận là một khẳng định học thuật, và đổi nó là việc của chủ dự án.

## 4. `trap-superseded-04` — lỗi THẬT, đã vào vòng sửa

```
run 1: rt=abstain cits=0 shallow=2 expanded=119 claims=0
run 2: rt=abstain cits=0 shallow=2 expanded=119 claims=0
run 3: rt=abstain cits=0 shallow=2 expanded=119 claims=0
```

Xác định, 3/3. Truy hồi **không** hỏng: 119 provision được mở rộng. Hỏng ở
`claims=0` — sinh luận điểm không cho ra luận điểm nào sống sót.

Câu trả lời CÓ trong kho, xác nhận bằng SQL trực tiếp:

```
293/2025/NĐ-CP > Điều 3 > Khoản 1 > Vùng III     (cap = 'hang_bang')
```

Vùng I và vùng II trả lời được; chỉ vùng ba trượt. Đây là **abstain sai** —
người hỏi một câu hợp lệ, có câu trả lời neo được trong kho, và nhận về màn
hình trắng. An toàn (từ chối chứ không bịa) nhưng là khiếm khuyết chất lượng.

Giả thuyết đang kiểm: tầng 1 khớp chuỗi **nguyên văn**; người viết "vùng ba",
văn bản viết "Vùng III". Nếu model sinh luận điểm phát biểu "Vùng 3" hoặc
"vùng ba" thì tầng 1 không tìm được neo và loại luận điểm. Nếu đúng vậy thì
đó là bảo đảm chống ảo giác đang làm đúng việc của nó, và **bản sửa không được
nằm ở tầng 1**.

## 5. `trap-oos-12` — nhãn khác, hành vi cùng loại

`khám bảo hiểm y tế trái tuyến có được thanh toán không` → nhận `abstain`, kỳ
vọng `out_of_scope`. Cả hai đều là từ chối trả lời; khác nhau ở lời nói với
người dùng: `out_of_scope` nói "không thuộc phạm vi của mình", `abstain` nói
"chưa đủ căn cứ". Với một câu hỏi bảo hiểm y tế thì `out_of_scope` đúng hơn.
Mức độ: thấp — không có nguy cơ ảo giác, chỉ là câu nói chưa đúng nhất.

## 6. Nhiễu quan sát được, không tính vào cột sai

`rewrite_query` nhận JSON bị cắt **2/45 lượt** (≈4%):

```
rewrite_query: lỗi khi gọi LLM (JSONDecodeError: Unterminated string starting
at: line 4 column 5 (char 55)) — bỏ qua, fallback về query gốc, không bịa biến thể
```

Suy giảm an toàn (rơi về query gốc) nhưng mất mở rộng truy vấn trong im lặng.
Đang xem cùng mục 4.

## 7. Kho, đã kiểm — không có vấn đề toàn vẹn

`information_schema` liệt kê mỗi cột của `chunks` hai lần vì có **hai** bảng
tên `chunks`: `public.chunks` và `corpus_cu.chunks` (kho cũ, để so sánh, dựng
từ `eval/corpus_cu.sql`). `search_path` là `"$user", public` nên truy vấn ứng
dụng chỉ thấy `public`.

`public.chunks` có 12.508 dòng = **6.254 chunk × 2 model embedding**
(`voyageai/voyage-4-lite` hiện dùng, `baai/bge-m3` trước đó), cả hai `dim=1024`.
`retrieval.py` lọc theo `embedding_model`, nên không có đếm trùng.
