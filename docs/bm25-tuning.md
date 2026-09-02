# Nhánh `lexical_only`: đo rồi mới chọn (H1, review cuối Plan 2)

> **CẢNH BÁO:** `golden_qa.yaml` (77 câu) toàn bộ đang `da_review: false` — chưa ai,
> kể cả chủ dự án, duyệt tay từng câu (Task 8). Mọi con số dưới đây là **CHỈ BÁO cho
> hướng phát triển**, KHÔNG phải kết quả công bố được trong khóa luận cho tới khi
> review xong.

Tái lập: `python -m scripts.sweep_bm25` (chỉ đọc Postgres, không gọi OpenRouter, $0).

## 1. Vì sao phải đo lại

Bảng ablation đầu tiên cho preset `bm25_only` (nay đổi tên thành `lexical_only`, xem §5)
Recall@5 = **0,1299**. Đọc con số đó thành
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

`lexical_only` Recall@5 **0,1299 → 0,3117** (×2,4). Nhánh từ vựng **vẫn** yếu hơn dense
(0,6494) một khoảng lớn, nhưng bây giờ đó là một phát biểu về BM25 trên tiếng Việt
chứ không phải về một baseline hỏng.

Nguyên nhân còn lại đã biết tên, **chưa** xử lý ở vòng này:

1. **Không tách từ tiếng Việt.** `'simple'` tách theo khoảng trắng nên "người lao
   động" thành ba lexeme độc lập; IDF của từng âm tiết gần như vô nghĩa. Global
   Constraint của Plan cho phép thêm `pyvi`/`underthesea` "nếu đo được Recall@k kém"
   — đã đo và kém, nhưng hai biến rẻ hơn ở trên phải được vắt kiệt trước. Đây là
   dòng ablation kế tiếp, không phải việc của vòng này.
2. **`ts_rank` không phải BM25** — xem §5.

## 5. Đặt tên: `lexical_only`, không phải `bm25_only`

Preset đã đổi tên `bm25_only` → **`lexical_only`** (`eval/configs/lexical_only.yaml`).

Nhánh này là **truy hồi từ vựng bằng `tsvector` + `ts_rank` của PostgreSQL** (config
`simple` + `unaccent`, truy vấn OR, chuẩn hoá độ dài `normalization=1`, lọc hư từ) —
**không phải BM25**: `ts_rank` không có tham số `k1`/`b` và không dùng IDF (chỉ trọng
số A–D theo `setweight`, mà dự án không set). Gọi nó là "baseline BM25" trong khóa
luận là một **lỗi sự kiện** người phản biện sẽ bắt.

Muốn có baseline BM25 đúng nghĩa thì phải cài `pg_search`/ParadeDB hoặc tự tính IDF —
đó là một dòng ablation riêng, chưa làm.

File kết quả cũ `eval/results/bm25_only-baai_bge-m3-77.json` **giữ nguyên tên**: nó là
hồ sơ của lần chạy đã xảy ra dưới tên cũ, không phải thứ để viết lại. Lần chạy sau
sinh `lexical_only-*`.

---

# Phụ lục — đo lại trên corpus 47 văn bản (2026-09-01)

Corpus mở từ **21 → 47 văn bản toàn văn** (19.138 → 36.710 điều khoản, 3.283 →
6.067 chunk mỗi model). Mọi số ở §1–§5 đo trên corpus 21 văn bản và **không còn
đúng**. Đo lại bằng đúng script cũ (`python -m scripts.sweep_bm25`, $0) và bằng
`_run_items` cho ba preset; **không ghi đè `eval/results/*.json`** — chúng là hồ
sơ của lần chạy đã xảy ra.

## A. Sweep hai biến, corpus 47 văn bản

| normalization | lọc hư từ | Recall@5 | MRR@5 | nDCG@5 | Recall@10 |
|---|---|---|---|---|---|
| 0 | không | 0,0260 | 0,0195 | 0,0212 | 0,0649 |
| 0 | có | 0,0779 | 0,0498 | 0,0553 | 0,1169 |
| **1** | **có** | **0,1818** | **0,1030** | **0,1209** | **0,2208** |
| 1 | không | 0,0974 | 0,0463 | 0,0581 | 0,1104 |
| 2 | có | 0,0130 | 0,0130 | 0,0130 | 0,0260 |
| 4 | có | 0,0779 | 0,0498 | 0,0553 | 0,1169 |
| 33 | có | 0,1818 | 0,1030 | 0,1209 | 0,2208 |

Xếp hạng giữa các cấu hình **không đổi**: `1` vẫn tốt nhất, `2` vẫn sụp, `4` vẫn
là no-op của `0`, `33` vẫn trùng `1`. Kết luận §3 đứng vững. Cái đổi là **mức**.

## B. Ba preset, trước và sau khi mở corpus

| preset | Recall@5 (21 vb) | Recall@5 (47 vb) | Δ tương đối |
|---|---|---|---|
| `lexical_only` | 0,3117 | **0,1818** | **−42 %** |
| `dense_only` | 0,6494 | **0,5974** | −8 % |
| `hybrid` | 0,5455 | **0,4740** | −13 % |

Tập golden vẫn là 77 câu **chỉ về lao động**; corpus thì nay trải 7 lĩnh vực
khác. Đó chính là phép thử: thêm nhiễu ngoài lĩnh vực, nhánh nào chịu được?

**Nhánh từ vựng chịu kém nhất, và nó đang KÉO hybrid xuống dưới dense thuần**
(0,474 < 0,597). Điều này đã đúng ở corpus 21 văn bản (0,5455 < 0,6494) nhưng
khoảng cách rộng ra. Đây là số liệu cho một quyết định cấu hình — dùng hybrid
hay dense thuần — **không tự đổi** ở đây: nó là hành vi quan sát được của sản
phẩm và cần người quyết.

## C. Nghị định hết hiệu lực xếp TRÊN nghị định hiện hành — chẩn đoán

Đo trên truy vấn `"lương tối thiểu vùng"` (`normalization=1`, đã lọc hư từ):

| # | ts_rank | token | `tinh_trang` MOJ | neo |
|---|---|---|---|---|
| 1 | 0,012916 | 85 | HHL1P | `145/2020/NĐ-CP > Điều 49` |
| 2 | 0,012090 | 217 | **CHL** | `157/2018/NĐ-CP > Điều 3` |
| 3 | 0,012090 | 217 | **CHL** | `141/2017/NĐ-CP > Điều 3` |
| 4 | 0,012090 | 217 | **CHL** | `90/2019/NĐ-CP > Điều 3` |
| 5 | 0,011781 | 162 | **CHL** | `122/2015/NĐ-CP > Điều 3` |
| … | | | | |
| 10 | 0,011294 | **484** | CHL | `293/2025/NĐ-CP > Điều 3` ← **văn bản hiện hành** |

Ba điều đọc được thẳng từ bảng này:

1. **`documents.tinh_trang` KHÔNG phân biệt được gì cả.** Cả bốn nghị định đã
   chết lẫn nghị định hiện hành đều mang `CHL`. Đây chính là lỗi MOJ mà Mức 2
   của `effectivity.py` sinh ra để chữa. Xếp hạng theo `tinh_trang` sẽ **không
   đổi một dòng nào** của bảng trên.
2. **Bốn nghị định đã chết cho ĐIỂM BẰNG NHAU tới 6 chữ số** (0,012090 ×3). Chúng
   là bản sao gần đúng của nhau về mặt văn bản. `ts_rank` **không có IDF** (§5)
   nên không có cơ chế nào phạt một cụm từ xuất hiện trong năm văn bản giống nhau.
3. **`293/2025` bị phạt vì CHỨA câu trả lời.** Nó dài 484 token thay vì 217 đúng
   bởi bản vá `parse_tables` đã đưa BẢNG LƯƠNG vào `noi_dung`. Chuẩn hoá
   `1+log(len)` chỉ bù được một phần: log(484)/log(217) ≈ 1,15.

## D. Quyết định: KHÔNG trộn tín hiệu hiệu lực vào điểm truy hồi

Bốn lý do, theo thứ tự sức nặng:

1. **Nó sẽ không chữa được ca này.** Tín hiệu hiệu lực rẻ duy nhất có ở tầng truy
   hồi là `documents.tinh_trang`, và §C.1 đo được rằng nó bằng `CHL` cho cả năm
   văn bản. Phán quyết ĐÚNG phải đi qua `effectivity.danh_gia` — cần cạnh đồ thị
   và suy luận cho từng văn bản, tức chạy tầng hiệu lực bên trong vòng xếp hạng.
2. **Corpus CỐ Ý chứa văn bản đã chết làm BẪY.** Sáu nghị định lương tối thiểu
   cũ và hai văn bản đợt C có ích *vì* đã chết: chúng đo được Mức 1/Mức 2 có
   cảnh báo đúng không. Hạ hạng chúng ở tầng truy hồi là giấu bẫy đi và làm cho
   chính phép đo đó không thực hiện được.
3. **Hai tầng dính nhau thì không gỡ ra được nữa.** Truy hồi trả lời "điều khoản
   nào NÓI VỀ chuyện này"; tầng hiệu lực trả lời "điều khoản đó CÒN ĐÚNG không".
   Trộn lại thì một câu trả lời tồi không còn chỉ ra được nó tồi ở đâu, và bảng
   ablation của khoá luận mất khả năng quy trách nhiệm.
4. **Nguyên nhân đo được nằm ở hàm xếp hạng, không ở hiệu lực.** Không IDF, không
   tách từ tiếng Việt (§4). Chỗ sửa đúng là một ranker từ vựng thật
   (`pg_search`/ParadeDB, hoặc IDF tự tính) — dòng ablation đã có tên ở §4, chưa
   làm.

**Cái đang giữ cho hệ thống không nói sai** là tầng dưới, và nó đang chạy: mọi
provision đi qua `expand` đều mang `effectivity`, bốn nghị định trên ra
`bi_thay_the`/`het_hieu_luc`, và `assemble` sinh cảnh báo. Thứ hạng thô sai
hướng là một vấn đề về CHẤT LƯỢNG XẾP HẠNG, không phải một lỗ hổng về tính đúng.

## E. `"vùng 1"` (số Ả Rập) trượt `"Vùng I"` (số La Mã) — ghi lại, KHÔNG sửa

Đo được:

```
to_tsvector('simple', unaccent('Vùng I …'))  →  'i':2 'vung':1
plainto_tsquery('simple', unaccent('vùng 1')) →  'vung' & '1'   (mã đổi & thành |)
```

Lexeme `1` không bao giờ khớp `i`, nên truy vấn thoái hoá về đúng một từ `vung`
và **mất toàn bộ khả năng phân biệt Vùng I với Vùng IV**. Trong corpus: 3 điều
khoản viết `Vùng <La Mã>`, **0** viết `Vùng <Ả Rập>`.

Vì sao **không** sửa ở vòng này:

- **Không mất câu trả lời.** Đo cả bốn dạng truy vấn (`vùng 1`, `vùng I`, có/không
  "mức"): `293/2025/NĐ-CP > Điều 3 > Khoản 1` — chunk chứa bảng lương —
  **luôn nằm trong context** sau `expand`, vì truy hồi bắt ở cấp Điều rồi bước
  cha→con kéo Khoản xuống. Cái đổi chỉ là THỨ HẠNG THÔ.
- **Chữa nó là đặc cách cho 6/6.067 chunk.** `tsv @@ 'vung <-> i'` khớp đúng 6
  chunk. Còn thêm lexeme `i` trần vào truy vấn OR thì đụng **220/6.067 chunk**
  (3,6 %) — "Chương I", "Mục I", "Phụ lục I" — tức đổi một lỗi hẹp lấy một nguồn
  nhiễu rộng, trên nhánh đang có Recall@5 = 0,18.
- **Đúng chỗ của nó là bộ phân tích, không phải truy vấn.** Gấp số La Mã ↔ Ả Rập
  phải áp cho **cả hai phía** (corpus và truy vấn) mới nhất quán, và đó là việc
  của lần thay ranker từ vựng ở §4 — cùng chỗ với tách từ tiếng Việt.

Xếp cùng danh sách với "không tách từ" và "`ts_rank` không có IDF": biết tên, đo
được, chưa xử lý — không phải quên.
