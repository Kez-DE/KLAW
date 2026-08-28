# Nhánh BM25: đo rồi mới chọn (H1, review cuối Plan 2)

> **CẢNH BÁO:** `golden_qa.yaml` (77 câu) toàn bộ đang `da_review: false` — chưa ai,
> kể cả chủ dự án, duyệt tay từng câu (Task 8). Mọi con số dưới đây là **CHỈ BÁO cho
> hướng phát triển**, KHÔNG phải kết quả công bố được trong khóa luận cho tới khi
> review xong.

Tái lập: `python -m scripts.sweep_bm25` (chỉ đọc Postgres, không gọi OpenRouter, $0).

## 1. Vì sao phải đo lại

Bảng ablation đầu tiên cho `bm25_only` Recall@5 = **0,1299**. Đọc con số đó thành
"BM25 yếu trên văn bản pháp luật Việt Nam" là một kết luận **sai về bản chất phương
pháp**. Nó thật ra đo: `to_tsvector('simple')` + nối OR + `ts_rank` **không chuẩn hoá
độ dài** thì yếu. Ba nguyên nhân, đo trực tiếp trên DB:

- `'simple'` không có stopword list tiếng Việt, nên `neu/em/thi/co/duoc/khong/a`…
  đều thành lexeme, và nối OR biến truy hồi thành xếp hạng gần như toàn bộ corpus.
- `ts_rank(tsv, q)` không truyền tham số normalization = mặc định `0` = **không chia
  cho độ dài tài liệu** → top-k toàn chunk dài, dù corpus trung bình chỉ **272 token**
  và **1.631/3.283 chunk ≤ 200 token**.

Đo trên một truy vấn `golden_qa` thật (`lao-001-0`: *"Nếu sếp em cứ chửi bới, xúc
phạm em trước mặt mọi người thì có được không ạ?"*), chunk `baai/bge-m3` sau khi sửa C1:

| Truy vấn / rank | Số chunk khớp | Top-10 token trung bình |
|---|---|---|
| gốc, `normalization=0` (cấu hình cũ) | 3.236/3.283 = **98,6%** | **791** (496–1.056) |
| đã lọc hư từ, `normalization=0` | 2.803/3.283 = 85,4% | 781 (338–1.171) |
| đã lọc hư từ, `normalization=1` (cấu hình mới) | 2.803/3.283 = 85,4% | **568** (109–1.056) |

Hai biến chữa hai chuyện khác nhau: lọc hư từ thu **tập ứng viên** (98,6% → 85,4%
corpus), normalization thu **thiên lệch độ dài** trong xếp hạng (791 → 568 token,
và chunk ngắn nhất lọt top-10 đi từ 496 xuống 109 token). Đúng như bảng sweep cho
thấy: hai biến cộng dồn chứ không thay thế nhau.

Vì `hybrid` fuse nhánh này vào, kết luận "hybrid thua dense" cũng thừa hưởng nguyên
nhân đó. Việc sweep `rrf_k` không cứu được là bằng chứng **củng cố**: tham số trộn
không sửa nổi một danh sách xếp theo độ dài.

## 2. Bảng sweep — hai biến độc lập

`normalization` là bitmask của `ts_rank`; `lọc hư từ` bỏ hư từ tiếng Việt khỏi **truy
vấn** (corpus không đụng tới). Đo trên chunk **đã sửa C1**, model `baai/bge-m3`,
`retrieve_bm25_topk=20`, `retrieve_final_topk=10`, 77 câu.

| normalization | lọc hư từ | Recall@5 | MRR@5 | nDCG@5 | Recall@10 |
|---|---|---|---|---|---|
| 0 | không | 0.1299 | 0.0801 | 0.0929 | 0.1558 |
| 0 | có | 0.1883 | 0.1299 | 0.1448 | 0.2468 |
| **1** | **có** | **0.3117** | **0.2245** | **0.2455** | **0.4156** |
| 1 | không | 0.2143 | 0.1351 | 0.1541 | 0.3312 |
| 2 | không | 0.013 | 0.0032 | 0.0056 | 0.013 |
| 2 | có | 0.026 | 0.0162 | 0.0186 | 0.039 |
| 4 | không | 0.1299 | 0.0801 | 0.0929 | 0.1558 |
| 4 | có | 0.1883 | 0.1299 | 0.1448 | 0.2468 |
| 33 | không | 0.2143 | 0.1351 | 0.1541 | 0.3312 |
| 33 | có | 0.3117 | 0.2245 | 0.2455 | 0.4156 |

Hai biến **cộng dồn** chứ không thay thế nhau: lọc hư từ cho +45%…+60% tương đối ở
**mọi** mức normalization, và normalization=1 cho +65% ở cả hai trạng thái lọc.

## 3. Đọc bảng

- **`normalization = 1`** (chia `1 + log(độ dài)`) là mức tốt nhất. Chọn giá trị này.
- **`2` (chia thẳng độ dài) sụp hẳn xuống 0,013** — tệ hơn cả không chuẩn hoá. Phạt
  độ dài tuyến tính là quá tay với corpus mà một Điều dài hợp lệ có thể dài gấp 5 lần
  một Điều ngắn; chuẩn hoá logarit mới đúng hình dạng dữ liệu. Đây là lý do phải đo
  chứ không lấy đại một giá trị "có chuẩn hoá".
- **`4` cho ĐÚNG con số của `0`.** Bit 4 (mean harmonic distance giữa các extent) chỉ
  có ý nghĩa với `ts_rank_cd` (cover density); `ts_rank` bỏ qua nó. Không phải trùng
  hợp — là no-op.
- **`33` (= `1|32`) cho ĐÚNG con số của `1`.** Bit 32 chia điểm cho `rank + 1`: một
  biến đổi đơn điệu, đổi **thang điểm** chứ không đổi **thứ tự**, nên top-k không
  thể khác. Bit 32 chỉ hữu ích khi cần ngưỡng điểm tuyệt đối. Lấy `1` vì nó nói đúng
  điều đang làm.
- **Lọc hư từ** cho +50% tương đối ở mọi mức. Danh sách 40 từ, tự viết, so khớp sau
  khi bỏ dấu (giống `unaccent()`). Cố ý **bỏ qua** những hư từ mà bản không dấu đụng
  độ với từ nội dung pháp lý — `tai` ← tại / **tài sản**, `trong` ← trong / **trọng
  tài**, `ban` ← bạn / **văn bản**, `can` ← cần / **căn cứ**, `the` ← thế / **có
  thể**, `hoi` ← hỏi / **hội đồng**, `dang` ← đang / **đăng ký**, `boi` ← bởi / **chửi
  bới**. Lọc nhầm chúng là mất từ khoá thật.

Cấu hình chọn: `bm25_rank_normalization = 1`, `bm25_strip_stopwords = true`
(`src/config.py`). Preset nào cần khác thì ghi đè trong `eval/configs/*.yaml`; giá
trị thật đi vào từng file kết quả nên mỗi hàng ablation tự mô tả được.

## 4. Kết luận còn đứng được sau khi sửa

`bm25_only` Recall@5 **0,1299 → 0,3117** (×2,4). Nhánh BM25 **vẫn** yếu hơn dense
(0,6494) một khoảng lớn, nhưng bây giờ đó là một phát biểu về BM25 trên tiếng Việt
chứ không phải về một baseline hỏng.

Nguyên nhân còn lại đã biết tên, **chưa** xử lý ở vòng này:

1. **Không tách từ tiếng Việt.** `'simple'` tách theo khoảng trắng nên "người lao
   động" thành ba lexeme độc lập; IDF của từng âm tiết gần như vô nghĩa. Global
   Constraint của Plan cho phép thêm `pyvi`/`underthesea` "nếu đo được Recall@k kém"
   — đã đo và kém, nhưng hai biến rẻ hơn ở trên phải được vắt kiệt trước. Đây là
   dòng ablation kế tiếp, không phải việc của vòng này.
2. **`ts_rank` không phải BM25.** Nó không có thành phần `k1`/`b` của BM25, không
   dùng IDF thật (chỉ trọng số A–D). Gọi nhánh này là "BM25" trong khóa luận là
   **không chính xác** — nên gọi là "truy hồi từ vựng bằng `tsvector`/`ts_rank`", và
   nếu cần một baseline BM25 đúng nghĩa thì phải cài `pg_search`/`ParadeDB` hoặc tự
   tính IDF. Tên preset `bm25_only` giữ nguyên để không phá liên kết với các file
   kết quả đã có, nhưng chú thích này phải đi kèm bảng.
