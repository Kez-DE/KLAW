# KLAW — AI Agent tra cứu pháp luật & soạn thảo văn bản pháp lý

**Ngày:** 2026-08-27 · **Trạng thái:** Design đã chốt, chờ review · **Loại:** Khóa luận tốt nghiệp

---

## 1. Bối cảnh & mục tiêu

Hệ thống AI Agent hai module: (1) **tra cứu pháp luật** có dẫn nguồn kiểm chứng được, (2) **soạn thảo văn bản pháp lý** có căn cứ pháp lý và kiểm tra tính hợp pháp.

| Tham số | Giá trị |
|---|---|
| Bối cảnh | Đồ án/khóa luận tốt nghiệp, có hội đồng bảo vệ |
| Lĩnh vực pháp luật | **Luật Lao động** (chỉ một lĩnh vực) |
| Đóng góp chính | **Chống ảo giác bằng trích dẫn kiểm chứng được** |
| Thời lượng giả định | ~12 tuần (điều chỉnh nếu khác) |
| Hạ tầng | OpenRouter (LLM) · Railway (deploy, Docker) · Postgres |

### Tiêu chí thành công

1. Bảng ablation 7 cấu hình × 8 metric hoàn chỉnh (mục 11.3)
2. Hệ thống **từ chối** trả lời trên tập bẫy thay vì bịa
3. Mọi citation trong câu trả lời **tra ngược được** về `provision_id` có thật
4. Deploy live, hội đồng click citation ra được nguyên văn điều luật

### Ngoài phạm vi (out of scope)

Lĩnh vực pháp luật ngoài Lao động – Tiền lương · **benchmark ngoại vi ALQAC/Zalo** (license không khai báo) · **phủ sâu 6 luật ở tầng nông** (chỉ nêu ranh giới, không diễn giải) · tư vấn vụ việc cụ thể · xác thực người dùng · thanh toán · app di động · đa ngôn ngữ.

---

## 2. Pain points (xếp theo mức nguy hiểm)

| # | Pain point | Vì sao nguy hiểm |
|---|---|---|
| 1 | **Citation hallucination** | LLM viết "theo Điều 47 BLLĐ" khi điều đó nói chuyện khác, hoặc bịa số điều không tồn tại. Nghe thuyết phục hơn câu trả lời đúng. |
| 2 | **Citation đã chết** | Trả lời đúng từ điều luật **đã bị bãi bỏ**. Có dẫn nguồn đầy đủ, vẫn sai hoàn toàn. |
| 3 | **Vocabulary gap** | Người dân hỏi "công ty cho nghỉ không báo trước có được không", corpus viết "nghĩa vụ thông báo khi đơn phương chấm dứt HĐLĐ". |
| 4 | **Một câu hỏi cần nhiều điều luật** | "Thử việc bao lâu?" cần Đ24 + Đ25 + Đ26. Top-k trả 1 điều → trả lời thiếu mà vẫn tự tin. |
| 5 | **Dẫn chiếu chéo** | "theo quy định tại khoản 2 Điều 35 của Bộ luật này" — chunk độc lập không resolve được. |
| 6 | **Soạn thảo sinh điều khoản trái luật** | Thử việc 90 ngày cho vị trí thường; điều khoản phạt tiền NLĐ (bị cấm). Văn phong hoàn hảo, nội dung phạm luật. |
| 7 | **Không có bộ đánh giá sẵn cho Lao động** | Phải tự xây golden set — chỗ hội đồng soi kỹ nhất. |

---

## 3. Kiến trúc: Hướng A, với B và C là tài sản

- **Hướng A — Verifier-gated RAG** (verify 2 tầng): hệ thống chính, build kỹ.
- **Hướng B — Retrieve-then-Cite**: gán citation *trước* khi viết. Là **baseline trong bảng ablation**, chi phí thêm ~0 vì chỉ là A bỏ bớt node.
- **Hướng C — Agentic multi-tool**: chương "Hướng phát triển", prototype 1 tool nếu còn thời gian.

Lợi ích: **3 cấu hình để so sánh, chỉ phải xây kỹ 1 cái.**

### Luận điểm trung tâm

> **Tính hợp lệ của trích dẫn là bài toán tra bảng, không phải bài toán suy luận.**

Phần lớn hệ thống hiện nay nhờ LLM tự kiểm tra chính nó — sai về nguyên tắc. Verify tầng 1 bắt phần lớn ảo giác citation với **chi phí 0 token và độ chính xác 100% theo định nghĩa**.

---

## 4. Dữ liệu

### 4.1 Nguồn (đã xác minh 2026-08-27)

| Ưu tiên | Nguồn | Trạng thái |
|---|---|---|
| **1** | `th1nhng0/vietnamese-legal-documents` (HuggingFace, **CC-BY-4.0**, DOI 10.57967/hf/8598) — 171.556 metadata + 170.824 toàn văn + 1.033.255 cạnh quan hệ + kèm mã crawler | Nguồn chính. License rõ ràng — hiếm. |
| **2** | API MOJ `https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{id}` — JSON, không auth, không JS, không anti-bot | Refresh delta ~40 văn bản Lao động |
| ❌ | `nguyenlab/ALQAC`, `kiil-lab/vietnamese-law-corpus`, `another-symato/VMTEB-ALQAC-retrieval` | **NGOÀI SCOPE.** Có GOLD label nhưng **license không khai báo** → không được viện dẫn là dữ liệu mở trong khóa luận. Đánh giá dùng hoàn toàn tập tự xây |
| ❌ | `thuvienphapluat.vn` | **KHÔNG dùng.** `robots.txt`: `User-agent: ClaudeBot` / `Disallow: /`, `ai-train=no`, HTTP 403, reservation of rights theo EU Directive 2019/790 Art.4 |
| ❌ | `vbpl.vn` / `phapluat.gov.vn` frontend | JS anti-bot, 403. Dùng API gateway thay thế |

Chiến lược: **dataset CC-BY-4.0 làm nguồn chính** (bỏ hẳn 1–2 tuần crawl, bỏ việc enumerate 185k ID), **API MOJ chỉ refresh delta**, rate-limit lịch sự (quan sát HTTP 400 thoáng qua sau ~35 request liên tiếp).

### 4.2 Cơ sở pháp lý của việc sử dụng dữ liệu

**Luật Sở hữu trí tuệ 50/2005/QH11, Điều 15** (trích nguyên văn từ chính CSDL MOJ, `doc_id 16748`) — *Các đối tượng không thuộc phạm vi bảo hộ quyền tác giả*:

> 2. Văn bản quy phạm pháp luật, văn bản hành chính, văn bản khác thuộc lĩnh vực tư pháp và bản dịch chính thức của văn bản đó.

Đã kiểm chéo cả 3 luật sửa đổi (36/2009/QH12, 42/2019/QH14, 07/2022/QH15): **0 lần** chạm tới Điều 15.

**Chưa xác minh, ghi vào chương Giới hạn:** vbpl.vn không có `robots.txt` máy đọc được (đường dẫn trả về chính trang challenge) → không có chỉ thị "allow" tường minh để viện dẫn; ToS chưa đọc được. Điều luật bảo hộ phần *biên tập/sưu tập* của site thương mại: chưa tìm được số điều.

### 4.3 Corpus

`linh_vuc` **KHÔNG dùng để lọc được**: `"Chưa phân loại"` cho 113.772/171.556 dòng (**66%**), **kể cả chính Bộ luật Lao động**.

Corpus recall-oriented: **1.971 văn bản** (TW, loại Bộ luật/Luật/NĐ/TT/TTLT). Có nhiễu (Luật Báo chí, Luật Cư trú lọt vào) → không dùng trực tiếp.

#### Logic chọn corpus — 4 tầng, KHÔNG lọc theo `linh_vuc`

| Tầng | Tiêu chí chọn | Số VB | Nguồn tiêu chí |
|---|---|---|---|
| **1 — Bắt buộc** | Mọi văn bản mà **rule (mục 7.3) hoặc checklist (mục 7.2) trích dẫn** | 4 | suy ra từ chính spec |
| **2 — Cần** | Cạnh `references` trỏ tới BLLĐ (`139264`) với `referenceType ∈ {8 Hướng dẫn áp dụng, 9 Quy định chi tiết, hướng dẫn thi hành}` | ~6 | **truy vấn dữ liệu**, do cơ quan ban hành tự khai |
| **3 — Tập bẫy** | Chuỗi supersession của nghị định lương tối thiểu, **kể cả đã hết hiệu lực toàn bộ** | ~5 | mục 11.1 |
| **4 — Loại vòng 1** | BHXH · Việc làm/BHTN · NLĐ nước ngoài · NLĐ VN đi nước ngoài · Công đoàn · TT chuyên sâu ATVSLĐ | — | lĩnh vực liền kề nhưng riêng |

Tầng 2 dùng **truy vấn cạnh quan hệ thay cho lọc tay** — tiêu chí do cơ quan ban hành khai báo, không do tác giả phán đoán. Đây là lựa chọn có thể tái lập và bảo vệ được trước hội đồng.

**⚠ Tầng 3 BẮT BUỘC ingest văn bản đã HẾT HIỆU LỰC TOÀN BỘ.** Lọc corpus theo *"chỉ Còn hiệu lực hoặc HHL một phần"* sẽ **loại bỏ chính tập bẫy**: nếu NĐ 74/2024 (`168670`) không có trong index thì retrieval không bao giờ trả về nó, và cơ chế hiệu lực 3 mức (mục 5.2) **không có gì để đo**. Đúng cách là ingest hết, rồi để cơ chế hiệu lực làm việc của nó — đó mới là bài toán thật.

**Tầng 4 — loại, và lý do phải ghi vào chương Phạm vi:** BHXH bị loại vì là lĩnh vực riêng *và* Luật BHXH 41/2024 có lỗi trạng thái (mục 5.1); checklist HĐLĐ chỉ cần biết "phải có điều khoản BHXH" (mục 7.2 #9), không cần chi tiết mức đóng. TT 5/2023/TT-BNV (`160212`) giữ **metadata** để tham chiếu trong khóa luận (có mẫu HĐLĐ nhưng cho cơ quan hành chính/ĐVSNCL, và bị 401), **không ingest nội dung**.

#### Hai tầng ĐỘ SÂU — phủ rộng mà không vỡ scope

Lĩnh vực "Lao động – Tiền lương" theo phân loại chính thức gồm 7–8 luật cấp Quốc hội. Phủ sâu cả 7 là gần toàn bộ 1.971 văn bản → không khả thi trong 12 tuần. Phủ hẹp rồi im lặng với câu hỏi BHXH → trông như thiếu sót. Giải pháp: **hai tầng độ sâu**.

| Tầng | Nội dung | Cách ingest | Dùng để |
|---|---|---|---|
| **SÂU** (`depth='deep'`) | Cụm BLLĐ ~15 văn bản (tầng 1–3 ở trên) | chunk tới Điều/Khoản, retrieval + verifier đầy đủ | trả lời có citation kiểm chứng |
| **NÔNG** (`depth='shallow'`) | 6 luật gốc còn lại, **chỉ thân luật**, không NĐ/TT | chunk ở mức Điều, không expand reference | **xác định ranh giới phủ** |

**Tầng NÔNG — 6 luật, `doc_id` đã fetch live 2026-08-27:**

| Luật | `doc_id` | `effFrom` | `effStatus` theo MOJ |
|---|---|---|---|
| Luật Việc làm 74/2025/QH15 | 179273 | 2026-01-01 | Còn hiệu lực |
| Luật Công đoàn 50/2024/QH15 | 172553 | 2025-07-01 | Hết hiệu lực một phần |
| Luật BHXH 41/2024/QH15 | 175027 | 2025-07-01 | ⚠ **"Hết hiệu lực toàn bộ"** — nghi lỗi MOJ, xem 5.2 |
| Luật NLĐ VN đi làm việc ở nước ngoài 69/2020/QH14 | 146643 | **2022-01-01** | Còn hiệu lực |
| Luật 97/2025/QH15 (SĐBS Luật Công đoàn…) | 179407 | 2025-07-01 | Còn hiệu lực |
| Luật Giáo dục nghề nghiệp 74/2014/QH13 | *chưa tra* | — | — |

Luật ATVSLĐ 84/2015/QH13 (`70811`) nằm ở **tầng SÂU** (đã ở tầng 2), không phải tầng nông.

**Quy mô ước tính:** tầng sâu ~15 văn bản → 1.500–2.500 điều → ~2.000–4.000 chunk; tầng nông +6 luật → +~600–900 điều. Tổng vector ~4–8 MB. Retrieval nhanh, eval rẻ.

**Vòng 1 — 15 văn bản lõi, `tinh_trang` đã fetch live từng cái:**

| so_hieu | Loại | Tên | Hiệu lực | Tình trạng | `doc_id` |
|---|---|---|---|---|---|
| 45/2019/QH14 | Bộ luật | **Bộ luật Lao động** | 2021-01-01 | HHL một phần | **139264** |
| 145/2020/NĐ-CP | NĐ | **QĐ chi tiết & HD thi hành BLLĐ** | 2021-02-01 | HHL một phần | **152668** |
| 10/2020/TT-BLĐTBXH | TT | **Nội dung HĐLĐ** | 2021-01-01 | Còn hiệu lực | **146696** |
| 293/2025/NĐ-CP | NĐ | **Mức lương tối thiểu** | 2026-01-01 | Còn hiệu lực | **183939** |
| 337/2025/NĐ-CP | NĐ | Hợp đồng lao động điện tử | 2026-01-01 | Còn hiệu lực | 185561 |
| 12/2022/NĐ-CP | NĐ | Xử phạt VPHC lao động, BHXH | 2022-01-17 | ⚠ **effTo 2026-09-10** | 153913 |
| 09/2020/TT-BLĐTBXH | TT | QĐ chi tiết một số điều BLLĐ | 2021-03-15 | HHL một phần | 152670 |
| 18/2021/TT-BLĐTBXH | TT | Thời giờ làm việc, nghỉ ngơi | 2022-02-01 | Còn hiệu lực | 153297 |
| 135/2020/NĐ-CP | NĐ | Tuổi nghỉ hưu | 2021-01-01 | HHL một phần | 152734 |
| 29/2019/NĐ-CP | NĐ | Cho thuê lại lao động (K3 Đ54 BLLĐ) | 2019-05-05 | Còn hiệu lực | 134611 |
| 84/2015/QH13 | Luật | An toàn, vệ sinh lao động | 2016-07-01 | HHL một phần | 70811 |
| 74/2025/QH15 | Luật | Việc làm | 2026-01-01 | Còn hiệu lực | 179273 |
| 219/2025/NĐ-CP | NĐ | NLĐ nước ngoài làm việc tại VN | 2025-08-07 | Còn hiệu lực | 180273 |
| 152/2020/NĐ-CP | NĐ | NLĐ nước ngoài (bản trước) | 2021-02-15 | HHL một phần | 152669 |
| 5/2023/TT-BNV | TT | Mẫu HĐ dịch vụ & **mẫu HĐLĐ** (CQHC/ĐVSNCL) | 2023-06-20 | Còn hiệu lực | 160212 |

Vòng 2 mở rộng từ danh sách 40 văn bản đã verify + lọc tay từ 1.971.

### 4.4 Schema

```sql
documents
  id, so_hieu, loai_van_ban, ten, co_quan_ban_hanh,
  depth,               -- 'deep' | 'shallow'  (xem 4.3 Hai tầng độ sâu)
  ngay_ban_hanh, ngay_hieu_luc, ngay_het_hieu_luc,
  tinh_trang,          -- CHL | HHL | HHL1P | chua_hieu_luc
  moj_doc_id, nguon_url, checksum, crawled_at

provisions             -- CÂY: Phần > Chương > Mục > Điều > Khoản > Điểm
  id, document_id, parent_id,
  cap,                 -- chuong | muc | dieu | khoan | diem
  so_hieu_cap,         -- "25" | "2" | "a"
  tieu_de, noi_dung,   -- nguyên văn của riêng cấp này
  duong_dan,           -- "45/2019/QH14 > Điều 25 > Khoản 2"  ← citation canonical
  source_node_id,      -- id từ HTML: NULLABLE, KHÔNG UNIQUE (xem 4.5)
  thu_tu               -- thứ tự xuất hiện, để dựng lại văn bản

references
  from_provision_id, to_provision_id, loai, raw_text
  -- loai theo 15 mã MOJ: 1 Bãi bỏ · 3 Căn cứ · 4 Dẫn chiếu
  --                      10 Sửa đổi bổ sung · 12 Thay thế · ...

chunks
  id, provision_id, noi_dung_embed,
  embedding vector, embedding_model, embedding_dim,   -- nhiều bộ song song cho ablation
  tsv tsvector, token_count

verified_provisions    -- đối chiếu tay cho các ĐIỀU quan trọng (xem 5.2)
  provision_id, verified_at, verified_by, nguon_doi_chieu, ket_luan

verified_documents     -- đối chiếu tay hiệu lực của các LUẬT GỐC (xem 5.2 guard)
  document_id, verified_at, verified_by, nguon_doi_chieu,
  ket_luan_hieu_luc, ghi_chu_lech_voi_moj

traces                 -- dữ liệu cho chương đánh giá
  id, ts, endpoint, query, config_name,
  retrieved_ids[], claims_raw, claims_after_tier1, claims_after_tier2,
  abstained, latency_ms, token_in, token_out, cost_usd
```

**Ba quyết định then chốt:**

1. **Citation neo vào `provisions.id`, KHÔNG vào `chunks.id`.** `chunks` sẽ bị DROP/CREATE nhiều lần khi ablation chunking; nếu neo vào chunk thì mọi số liệu eval cũ thành rác.
2. **`duong_dan` là citation string canonical.** Verifier tầng 1 so khớp đúng cột này. Không để LLM tự format citation.
3. **`chunks` mang `embedding_model`** → nhiều bộ embedding song song, chính là thứ ablation cần. Re-embed 10k chunk = vài phút + vài xu → chọn model **không phải lock-in**.

### 4.5 Parser — đọc class `prov-*`, KHÔNG regex tiếng Việt

`provisionTree` = **`null` trên 40/40** văn bản đã kiểm → field chết, bỏ qua.

Nhưng `documentContent.content` **đã được đánh dấu cấu trúc sẵn**:

```html
<p id="…" class="MsoNormal prov-article">Điều 21. Nội dung hợp đồng lao động</p>
<p id="…" class="MsoNormal prov-clause" >1. Hợp đồng lao động phải có những nội dung…</p>
<p id="…" class="MsoNormal prov-item"   >a) Tên, địa chỉ của người sử dụng lao động…</p>
<p        class="MsoNormal prov-content">Tiền lương của người lao động trong thời gian thử việc…</p>
```

Ánh xạ: `prov-chapter`→chuong · `prov-section`→muc · `prov-article`→dieu · `prov-clause`→khoan · `prov-item`→diem · `prov-content`→thân văn.

**Kiểm chứng trên BLLĐ (`139264`):** 220 node `prov-article`, **220/220** khớp `^Điều \d+\.`, liên tục Điều 1 → Điều 220 — đúng số điều thật.

#### Bốn cạm bẫy BẮT BUỘC xử lý

| # | Bẫy | Cách xử |
|---|---|---|
| 1 | **HTML phẳng** — mọi `<p>` là anh em trong `div.WordSection1`, cấp bậc chỉ nằm ở tên class | Duyệt tuần tự + **stack** đẩy/pop theo cấp. Không có DOM nesting để dựa. |
| 2 | **`prov-content` KHÔNG có `id`** — 157/1332 thẻ chỉ có `(class, style)` | **Gắn vào node đang ở đỉnh stack, KHÔNG tạo node mới.** Parser đòi `id` sẽ **mất trắng nội dung Điều 26 (tiền lương thử việc)** và câu dẫn Điều 25. |
| 3 | **`<br>` dính chữ** | Thay `<br>` bằng `' '` **trước** khi strip tag. Nếu không: `"Chương IIVIỆC LÀM…"` |
| 4 | **Bảng bị bẹp** — `<td>` hạ cấp thành `prov-content` rời | **Parse `<table>` bằng đường riêng**, giữ hàng/cột, lưu dạng markdown vào `noi_dung`. Bảng lương NĐ 293/2025 vỡ thành 15 mảnh nếu đi đường `prov-*`. |

Thêm: `id` HTML **không phải khóa chính đáng tin** (quan sát 1 node xuất hiện 2 lần) → lưu vào `source_node_id` nullable, non-unique; PK là id của ta.

**Acceptance test bắt buộc sau parse:** số node `cap='dieu'` phải khớp số Điều cuối cùng của văn bản (BLLĐ = 220). Fail → dừng ingest.

**Chưa xác minh:** class `prov-*` mới kiểm kỹ trên 3 văn bản (BLLĐ, TT 10/2020, NĐ 293/2025). 37 văn bản còn lại chỉ xác nhận content không rỗng. → **Chạy kiểm phủ trước khi tin parser cho toàn corpus.**

### 4.6 Dẫn chiếu chéo & tìm kiếm tiếng Việt

- **Dẫn chiếu:** ở ingest, regex bắt `(khoản \d+ )?Điều \d+( của ... này)?` → resolve thành `provision_id` → ghi `references`. Khi retrieve, expand **1 hop**, không lặp sâu.
- **Full-text:** PostgreSQL **không có** config `vietnamese`. Bắt đầu bằng `unaccent` + config `simple`. Tách từ (`pyvi`/`underthesea`) là tối ưu hóa sớm — chỉ thêm nếu đo được Recall@k kém, và khi đó nó thành thêm một dòng ablation.

### 4.7 Embedding

**Production gọi API/model nhẹ, KHÔNG self-host model lớn.** Railway Free = 0.5 GB RAM, RAM tính **$10/GB/tháng**; bge-m3 / AITeamVN nặng 2.27 GB weights → container ~3 GB ≈ **$30/tháng**, và image ~4.5 GB **vượt cap 4 GB** của Free/Trial.

| Model | params | Deploy size | VN-MTEB retrieval | Ghi chú |
|---|---|---|---|---|
| `AITeamVN/Vietnamese_Embedding` | 568M (chỉ F32) | 2.27 GB (ONNX cũng 2.27 GB, **không có bản int8**) | 34.18 | Legal Zalo Acc@1 **0.727** vs bge-m3 0.568 — **nguồn: model card, một chiều** |
| `BAAI/bge-m3` | 568M | 2.27 GB | 39.84 | tốt nhất nhóm ≤1B |
| `Alibaba-NLP/gte-multilingual-base` | 305M | 0.61 GB | 38.38 | Avg cao hơn bge-m3 |
| **`intfloat/multilingual-e5-small`** | 118M | **0.12 GB int8 ONNX ship sẵn** | **34.12** | Vừa Railway Free. Chênh AITeamVN **0.06 điểm** cho **19× nhỏ hơn** |

#### Key đã có trong `.env` (kiểm 2026-08-27)

`OPENAI_API_KEY` · `COHERE_API_KEY` · `LANGCHAIN_API_KEY` + `LANGCHAIN_TRACING_V2`

**Kế hoạch (đã sửa sau khi biết có sẵn key):**
- **Tuần 1–3: OpenAI `text-embedding-3-small`** — key có sẵn, zero setup, **không giới hạn call**. Chi phí cả khóa luận: corpus ~4.000 chunk × ~400 token = 1,6M token → **$0.032**; cộng eval queries ≈ **$0.05 tổng**. Quan trọng hơn tiền: **xóa câu hỏi RAM Railway khỏi tuần 1–3** — không phải dựng ONNX runtime, không phải lo cap 0.5 GB.
- **Tuần 4:** eval offline trên `golden_qa` Lao động, **chạy trên laptop**. `e5-small int8` từ điểm khởi đầu chuyển thành **một dòng trong bảng** — dòng đo phương án "hạ tầng $0".
- **Sau tuần 4:** chốt theo số đo, không theo phán đoán.

#### Bảng so sánh embedding tuần 4 — ứng viên đã chốt

| Model | Nguồn | Dim | ctx | Chi phí | Ghi chú |
|---|---|---|---|---|---|
| **OpenAI `text-embedding-3-small`** | API (key có sẵn) | 1536 (truncate được) | 8192 | $0.02/1M | **mặc định tuần 1–3** |
| `Cohere embed-v4.0` | API (key có sẵn, **trial**) | 1536 | 8192 | xem ghi chú trial | smoke test Vietnamese: **Recall@1 4/4** |
| `AITeamVN/Vietnamese_Embedding` | local | 1024 | 2048 | $0 offline | Legal Zalo Acc@1 0.727 |
| `BAAI/bge-m3` | local | 1024 | 8192 | $0 offline | VN-MTEB retrieval 39.84 |
| `Alibaba-NLP/gte-multilingual-base` | local | 768 | 8192 | $0 offline | VN-MTEB Avg 65.22 |
| `intfloat/multilingual-e5-small` int8 | local | 384 | 512 | $0, **vừa Railway Free** | đo phương án hạ tầng $0 |

**Cohere embed — smoke test đã chạy, và giới hạn đã đo.** Với 4 điều luật BLLĐ thật (Đ17 K1, Đ25 K4, Đ26, Đ127 K2) và 4 câu hỏi giọng dân sinh: **Recall@1 = 4/4**, dù docs Cohere không nêu tên tiếng Việt. **Nhưng đây là smoke test, KHÔNG phải eval** — 4 văn bản chủ đề tách biệt, biên điểm mỏng (câu 1 hơn 0.011, câu 4 hơn 0.041). Với 3.000 chunk chứa nhiều điều cùng nói về lương/thử việc, biên đó sẽ sập. Không được trích 4/4 như kết quả trong khóa luận.

Giới hạn trial key (đọc từ response header): `x-endpoint-monthly-call-limit: 1000`, `x-trial-endpoint-call-limit: 100`/phút. Batch 96 text/call thì ingest 4.000 chunk ≈ 42 call — vừa. Nhưng docs Cohere ghi trial key *"not permitted to be used for production or commercial purposes"* ⇒ **không dùng cho URL live**, chỉ dùng đo trong tuần 4.

`embed-multilingual-v3.0` ctx chỉ **512 token** → truncate chunk cấp Điều. Nếu dùng Cohere thì phải là `embed-v4.0` (ctx 8192).

#### Reranker — ứng viên đã chốt

Rerank gọi **1 lần/query** với top-20 candidate ⇒ số call rất thấp ⇒ giới hạn 1.000 call/tháng của Cohere trial **không cắn** ở workload này.

| Model | ctx | Nguồn |
|---|---|---|
| **`Cohere rerank-v4.0-fast`** / `rerank-v4.0-pro` | **32.768** | key có sẵn (trial, đủ cho eval) |
| `Cohere rerank-multilingual-v3.0` | 4.096 | dự phòng |
| `BAAI/bge-reranker-v2-m3` | 8.192 | local, $0 |
| `jina-reranker-v3` | 134.144 | $0.05/1M, **0/29 model Jina nhắc tiếng Việt** |

Cả bốn đều **chưa có số tiếng Việt công bố** → phải tự đo, và đó là thêm một dòng ablation.

#### Observability

`LANGCHAIN_API_KEY` + `LANGCHAIN_TRACING_V2` đã có ⇒ LangSmith cho latency/token/cost **theo từng node** miễn phí. Dùng nó thay cho phần lớn việc tự log; bảng `traces` chỉ cần giữ những gì eval harness đọc trực tiếp (`claims_after_tier1/2`, `abstained`, `config_name`).

Ràng buộc cứng: **corpus và query phải cùng model** (cùng vector space).

Bảng tuần 4 là đóng góp phụ: **VN-MTEB không test API thương mại nào**, model card AITeamVN không so với e5-small → số liệu chưa ai công bố.

---

## 5. Hiệu lực văn bản (pain point #2)

### 5.1 Vấn đề đã xác minh

1. **Dữ liệu bãi bỏ cấp điều khoản KHÔNG công khai.** `hasClauseRelation: true` trên 32/40 văn bản, nhưng `/clause-relation*` → 404, `/api/qtdc/public/clause-relation/{id}` → **401**, `references[].referenceProvisions` **luôn null**, `relationships.parquet` cũng chỉ cấp văn bản.
2. **Chính CSDL quốc gia có lỗi trạng thái.** NĐ 90/2019, 157/2018, 141/2017, 122/2015 — bốn nghị định lương tối thiểu **đã bị thay** — vẫn mang `effStatus = "Còn hiệu lực"`. Parquet khớp API 40/40 ⇒ lỗi ở phía MOJ.
3. Luật BHXH 41/2024 bị đánh *"Hết hiệu lực toàn bộ"* vì Luật Việc làm 74/2025 ghi quan hệ "Thay thế" — gần như chắc chắn **lỗi dữ liệu**, không nên tin máy móc.

### 5.2 Cơ chế suy luận hiệu lực 3 mức

```
Mức 1  doc.ngay_het_hieu_luc <= as_of_date
       → HET_HIEU_LUC, tin cậy CAO

Mức 2  tồn tại cạnh Thay thế/Bãi bỏ trỏ tới doc,
       và văn bản thay đã có hiệu lực tại as_of_date
       → BI_THAY_THE, tin cậy CAO        ← bắt được lỗi effStatus của MOJ

Mức 3  doc.tinh_trang == HHL1P
       → CO_PHAN_BI_BAI_BO_KHONG_XAC_DINH, tin cậy THẤP
         (CSDL không công bố dữ liệu cấp điều khoản)

Mặc định → CON_HIEU_LUC, tin cậy TRUNG BÌNH
```

**Mức 2 là đóng góp:** nó bắt đúng bốn nghị định mà `effStatus` bỏ sót.

**⚠ Nhưng Mức 2 KẾ THỪA lỗi của đồ thị — phải có guard.** Đồ thị MOJ chỉ biểu diễn quan hệ **cấp văn bản**; khi một luật chỉ thay thế *một phần* luật khác, quan hệ bị ép thành "Thay thế" toàn bộ. Ca đã xác minh:

```
Luật Việc làm 74/2025/QH15  ──THAY THẾ (type 12)──►  41/2024/QH15 Luật Bảo hiểm xã hội
```

⇒ MOJ suy ra Luật BHXH 41/2024 `effTo = 2026-01-01`, `effStatus = "Hết hiệu lực toàn bộ"`. Gần như chắc chắn sai: một Luật Việc làm không thể thay thế toàn bộ một Luật BHXH; thực tế 74/2025 chỉ thay phần **bảo hiểm thất nghiệp**. Mức 2 áp vào ca này sẽ **xác nhận lỗi**, không bắt được.

**Guard bắt buộc — kiểm tính hợp lý của cạnh "Thay thế" trước khi tin:**

| Điều kiện | Kết luận |
|---|---|
| Văn bản thay và văn bản bị thay **cùng `loai_van_ban`** và tiêu đề chia sẻ chủ ngữ chính (vd "Luật Việc làm" thay "Luật Việc làm") | Mức 2, tin cậy **CAO** |
| Khác chủ đề (vd "Luật Việc làm" thay "Luật Bảo hiểm xã hội") | **CẦN_ĐỐI_CHIẾU_TAY**, tin cậy **THẤP** — không tự động kết luận hết hiệu lực |

**Bảng `verified_documents`** (song song với `verified_provisions`): các **luật gốc cấp Quốc hội** trong corpus được đối chiếu tay một lần, ghi `verified_at` + `nguon_doi_chieu` + `ket_luan`. Tập này nhỏ và hữu hạn (≤10 văn bản) nên đây là task đóng, không phải vấn đề mở.

**Đóng góp và giới hạn nói cùng lúc:** cơ chế 3 mức cải thiện `effStatus`, nhưng **kế thừa lỗi phân loại của đồ thị nguồn**. Cách chặn là guard hợp lý + đối chiếu tay tập luật gốc — và phải công bố rõ giới hạn này, không được trình bày cơ chế như đã giải quyết trọn vẹn.

**Hai chiều lỗi đã xác minh trên chính CSDL quốc gia** (dùng làm bằng chứng ở chương kết quả):

| Ca | `doc_id` | MOJ nói | Thực tế | Chiều lỗi | Cơ chế nào cần |
|---|---|---|---|---|---|
| NĐ 90/2019 lương tối thiểu | 139094 | Còn hiệu lực | đã bị thay | **false negative** | Mức 2 bắt được |
| Luật BHXH 41/2024 | 175027 | Hết hiệu lực toàn bộ (`effTo 2026-01-01`) | chỉ mất phần BHTN | **false positive** | **guard + đối chiếu tay** |

**Mức 3 áp cho chính BLLĐ** (HHL1P do Luật BHXH 41/2024). Xử lý:
- Cảnh báo hiển thị **một lần ở tầng UI**, không lặp trên từng citation (tránh nhiễu vô dụng)
- Bảng `verified_provisions`: **đối chiếu tay ~10 điều quan trọng nhất** (Đ17, Đ21, Đ25, Đ26, Đ127 + các điều xuất hiện nhiều trong golden set) với văn bản hợp nhất. Điều đã verify → tin cậy CAO. Đây là task hữu hạn, không phải vấn đề mở.

**Chưa xác minh:** điều nào của BLLĐ thực sự bị bãi bỏ. Grep nội dung Luật BHXH 41/2024 tìm câu bãi bỏ dẫn chiếu "Bộ luật Lao động" → **không khớp câu nào**. Đây là rủi ro chính xác cao nhất còn tồn đọng.

---

## 6. Retrieval & Verifier (Hướng A)

```
query, as_of_date
  → route            tra_cuu | soan_thao | ngoai_pham_vi(→từ chối, END)
  → rewrite_query    dân sinh → ngôn ngữ pháp lý + 2–3 query phụ   [ablate được]
  → retrieve_hybrid  BM25 top20 ⊕ dense top20 → RRF → top10
  → expand           Khoản→Điều (parent-doc) · references 1-hop · lọc as_of_date
                     TÁCH 2 nhánh: expanded_deep[]  vs  hits_shallow[]
                     deep rỗng & shallow có → PARTIAL_COVERAGE (bỏ qua LLM, 0 token)
  → generate_claims  structured: [{text, provision_id, quote}] | insufficient_evidence
  → VERIFY TẦNG 1    thuần Python, 0 token
  → VERIFY TẦNG 2    LLM judge, chỉ claim qua tầng 1, batch 1 call
  → assemble         đủ căn cứ → trả lời + citation ; không → ABSTAIN
```

### 6.1 Verify tầng 1 — bốn phép kiểm, không dùng LLM

| Kiểm tra | Bắt lỗi gì | Hành động |
|---|---|---|
| `provision_id` tồn tại trong DB? | LLM bịa số điều không có thật | **DROP** |
| `provision_id` có trong tập `expanded`? | LLM lôi điều luật từ tham số của nó, không từ context | **DROP** |
| `quote` là substring của `provisions.noi_dung` (sau normalize dấu/khoảng trắng)? | LLM "trích dẫn" nhưng viết lại nội dung | **DROP** |
| Điều còn hiệu lực tại `as_of_date`? (mục 5.2) | Pain point #2 | **WARN** |

### 6.2 Bốn loại kết quả

| Kết quả | Khi nào | Chi phí |
|---|---|---|
| `ANSWER` | có claim qua verify từ **tầng sâu** | đầy đủ |
| `PARTIAL_COVERAGE` | `expanded_deep` rỗng, `hits_shallow` có kết quả | **0 token LLM** — nhánh xác định |
| `ABSTAIN` | không tìm thấy căn cứ ở **cả hai** tầng | tiết kiệm |
| `OUT_OF_SCOPE` | `route` xác định ngoài lĩnh vực lao động | rẻ nhất |

**`PARTIAL_COVERAGE` là nhánh xác định (deterministic), KHÔNG gọi LLM.** Trả về: tên luật + Điều liên quan từ tầng nông + tuyên bố ranh giới. Ví dụ:

> Câu hỏi thuộc **Luật Việc làm 74/2025/QH15, Điều X**. KLAW phủ sâu Bộ luật Lao động và các văn bản hướng dẫn; **chưa phủ nghị định/thông tư hướng dẫn Luật Việc làm** nên không diễn giải chi tiết được. Xem văn bản gốc: [link]

Tốt hơn `ABSTAIN` (có thông tin định hướng), và vô cùng tốt hơn việc bịa. Nó cũng khiến quyết định "ngoài phạm vi" của node `route` dựa trên **dữ liệu** thay vì danh sách hardcode.

### 6.3 Abstain

`ABSTAIN` khi **bất kỳ** điều nào sau đây đúng:

1. LLM tự trả `insufficient_evidence: true` ở bước `generate_claims`
2. 0 claim qua verify tầng 1
3. Tỉ lệ claim verified / tổng claim < ngưỡng (khởi đầu **0.5**, tinh chỉnh bằng eval)

**`ABSTAIN` là hành vi đúng, được tính điểm, không phải lỗi.**

---

## 7. Module soạn thảo

**Không có mẫu HĐLĐ chính thức hiện hành** cho khu vực doanh nghiệp: TT 21/2003/TT-BLĐTBXH "Mẫu số 1" đã **hết hiệu lực toàn bộ**; TT 10/2020/TT-BLĐTBXH (còn hiệu lực) chỉ quy định **nội dung** (toàn văn 0 lần "Mẫu số"). TT 5/2023/TT-BNV có mẫu HĐLĐ nhưng cho **cơ quan hành chính/ĐVSNCL**, và nằm trong PDF khoá 401.

⇒ Module soạn thảo **không phải template-filling** mà là **checklist nội dung bắt buộc + validator điều khoản trái luật**. Việc sinh HĐLĐ hợp pháp đòi hỏi suy luận từ luật thật — đó là bài toán đáng nghiên cứu.

### 7.1 Đối xứng với module tra cứu

| | Tra cứu | Soạn thảo |
|---|---|---|
| LLM sinh | `{claim, provision_id, quote}` | `{điều_khoản, căn_cứ_provision_id, đáp_ứng_mục_nào}` |
| Verify tầng 1 | citation tồn tại? trích nguyên văn? | completeness · legality · citation |
| Metric | citation precision, hallucination rate | completeness, legality violation rate |

**Bước citation dùng lại nguyên verifier tầng 1 của mục 6.1.**

### 7.2 Checklist nội dung bắt buộc — BLLĐ Đ21.1 × TT 10/2020 Đ3

| # | Nội dung bắt buộc | Căn cứ | Chi tiết |
|---|---|---|---|
| 1 | Tên, địa chỉ NSDLĐ và họ tên, chức danh người giao kết bên NSDLĐ | Đ21.1.a | TT10 Đ3.1.a–c |
| 2 | Họ tên, ngày sinh, giới tính, nơi cư trú, số CCCD/CMND/hộ chiếu của người giao kết bên NLĐ | Đ21.1.b | TT10 Đ3.2.a–c |
| 3 | Công việc và địa điểm làm việc | Đ21.1.c | TT10 Đ3.3.a–b |
| 4 | Thời hạn của hợp đồng lao động | Đ21.1.d | TT10 Đ3.4 |
| 5 | Mức lương theo công việc/chức danh, hình thức trả lương, thời hạn trả lương, phụ cấp và các khoản bổ sung khác | Đ21.1.đ | TT10 Đ3.5.a–đ |
| 6 | Chế độ nâng bậc, nâng lương | Đ21.1.e | TT10 Đ3.6 |
| 7 | Thời giờ làm việc, thời giờ nghỉ ngơi | Đ21.1.g | TT10 Đ3.7 |
| 8 | Trang bị bảo hộ lao động cho NLĐ | Đ21.1.h | TT10 Đ3.8 |
| 9 | Bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp | Đ21.1.i | TT10 Đ3.9 |
| 10 | Đào tạo, bồi dưỡng, nâng cao trình độ, kỹ năng nghề | Đ21.1.k | TT10 Đ3.10 |

**Ba ngoại lệ phải code, nếu bỏ qua sẽ báo sai:**

- **Đ21.3** — nông/lâm/ngư/diêm nghiệp *"tùy theo loại công việc mà hai bên có thể giảm một số nội dung chủ yếu"* + phải thỏa thuận phương thức xử lý khi chịu ảnh hưởng thiên tai, hỏa hoạn, thời tiết. **Hành vi cụ thể:** khi `nganh ∈ {nông, lâm, ngư, diêm nghiệp}`, mục thiếu báo `ĐƯỢC_PHÉP_GIẢM` (không tính vi phạm completeness) thay vì `THIẾU`; **và thêm một mục bắt buộc riêng**: thỏa thuận phương thức xử lý khi chịu ảnh hưởng thiên tai/hỏa hoạn/thời tiết. Denominator của completeness đổi theo ngành, không cố định 10.
- **Đ21.2** — điều khoản bí mật KD/công nghệ là **quyền** thỏa thuận (phải bằng văn bản), **không** bắt buộc ⇒ đừng báo thiếu
- **TT10 Đ3.5.c** — phúc lợi khác (thưởng Đ104, ăn giữa ca, xăng xe, điện thoại, nhà ở, giữ trẻ…) phải *"ghi thành mục riêng trong hợp đồng lao động"* ⇒ quy tắc **định dạng**, không chỉ nội dung

### 7.3 Rule engine — rules là DATA (YAML/DB), không phải code

Căn cứ dưới đây **đã fetch và trích nguyên văn từ API MOJ**, không lấy từ trí nhớ.

```yaml
- id: thu_viec_toi_da
  can_cu: "45/2019/QH14 > Điều 25"          # doc_id 139264
  nguyen_van: |
    Thời gian thử việc do hai bên thỏa thuận căn cứ vào tính chất và mức độ
    phức tạp của công việc nhưng chỉ được thử việc một lần đối với một công việc
    và bảo đảm điều kiện sau đây:
    K1. Không quá 180 ngày — công việc của người quản lý doanh nghiệp
    K2. Không quá 60 ngày  — chức danh cần trình độ chuyên môn, kỹ thuật từ cao đẳng trở lên
    K3. Không quá 30 ngày  — trung cấp, công nhân kỹ thuật, nhân viên nghiệp vụ
    K4. Không quá 06 ngày làm việc — công việc khác
  kiem: thoi_gian_thu_viec_ngay <= gioi_han_theo_chuc_danh

- id: luong_thu_viec_toi_thieu
  can_cu: "45/2019/QH14 > Điều 26"
  nguyen_van: "…ít nhất phải bằng 85% mức lương của công việc đó."
  kiem: luong_thu_viec >= 0.85 * luong_chinh_thuc

- id: luong_toi_thieu_vung
  can_cu: "293/2025/NĐ-CP > Điều 3 > Khoản 1"   # doc_id 183939, hiệu lực 2026-01-01
  bang:  { I: 5310000, II: 4730000, III: 4140000, IV: 3700000 }      # đ/tháng
  gio:   { I: 25500,   II: 22700,   III: 20000,   IV: 17800 }        # đ/giờ
  kiem: luong_thang >= bang[vung]
  # ⚠ vung PHẢI là input người dùng — xem ghi chú dưới

- id: cam_phat_tien_nld
  can_cu: "45/2019/QH14 > Điều 127 > Khoản 2"
  nguyen_van: "Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động."
  kiem: not co_dieu_khoan_phat_tien

- id: cam_giu_giay_to_dat_coc
  can_cu: "45/2019/QH14 > Điều 17 > Khoản 1, Khoản 2"
  nguyen_van: |
    K1. Giữ bản chính giấy tờ tùy thân, văn bằng, chứng chỉ của người lao động.
    K2. Yêu cầu người lao động phải thực hiện biện pháp bảo đảm bằng tiền
        hoặc tài sản khác cho việc thực hiện hợp đồng lao động.
  kiem: not (co_dieu_khoan_giu_giay_to or co_dieu_khoan_dat_coc)
```

**⚠ Giới hạn cứng của rule `luong_toi_thieu_vung`:** NĐ 293/2025 Đ3.2 ghi danh mục địa bàn vùng I–IV nằm ở **Phụ lục kèm theo**, và Phụ lục đó **KHÔNG có trong `documentContent.content`** (content chỉ 16.805 ký tự; 0 lần "Quận", 0 "Huyện"). Mọi đường tải file (`file/{uuid}`, `related-file/{uuid}`, `download/{uuid}`) đều **401**. ⇒ **Không tự suy được vùng từ địa chỉ. `vung` là input bắt buộc của người dùng.**

Lợi ích của rules-là-data: xác minh căn cứ thành task **nhập dữ liệu có checklist**; mỗi rule unit-test độc lập; khóa luận báo cáo được *"N rule, M đã đối chiếu nguồn gốc"*.

### 7.4 Metric

| Metric | Cách đo | Test set |
|---|---|---|
| Completeness | % nội dung bắt buộc được cover | 20 bộ fact hợp lệ |
| Legality detection | % lỗi cài sẵn bị bắt | **~30 HĐ cố tình cài lỗi**, mỗi rule 2–3 case |
| False positive | % HĐ hợp lệ bị báo sai | 20 HĐ hợp lệ |

Ground truth chắc chắn vì lỗi do ta tự cài → **không cần chuyên gia**. Nếu xin được luật sư/giảng viên review 10–15 văn bản theo rubric thì thêm một mục, nhưng không phụ thuộc.

Xuất file: `python-docx`. Bỏ: LaTeX, headless LibreOffice.

---

## 8. Backend & API

```
POST /api/v1/tra-cuu     {query, as_of_date?}     → {answer, citations[], warnings[], abstained, trace_id}
POST /api/v1/soan-thao   {loai_van_ban, facts{}}  → {document, clauses[], validation_report, trace_id}
GET  /api/v1/van-ban/{id}                         → provision tree
POST /api/v1/feedback    {trace_id, verdict}      → ghi bảng traces
GET  /health
```

**Không SSE token streaming ở MVP.** Verifier chạy *sau* generate → stream sẽ hiện text rồi rút lại, tệ hơn không stream. Thay bằng progress event thô. Thêm khi latency đo thực > 8s.

### 8.1 LLM qua OpenRouter

`src/services/llm.py` đã có `ChatOpenAI`; thêm `base_url="https://openrouter.ai/api/v1"`.

| Vai | Yêu cầu |
|---|---|
| `route`, `rewrite_query` | nhanh, rẻ, structured output |
| `generate_claims` | chất lượng cao, structured output ổn định |
| `verify_tier2` | judge, output ngắn, batch nhiều claim/call |

**Đã xác minh 2026-08-27: OpenRouter KHÔNG có embedding.** Quét `openrouter.ai/api/v1/models` — 417 model, **0 embedding, 0 reranker**. OpenRouter chỉ có chat/completion.

#### Contract config — BA provider, không gộp được về một key

| Tầng | Provider | Biến | Base URL |
|---|---|---|---|
| LLM (route, rewrite, generate_claims, verify_tier2) | OpenRouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| Embedding | OpenAI trực tiếp | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| Reranker *(tùy chọn)* | Cohere | `COHERE_API_KEY` | `https://api.cohere.com` |

```dotenv
# --- LLM: qua OpenRouter ---
OPENROUTER_API_KEY=          # CHƯA CÓ trong .env — lấy ở openrouter.ai/keys, set spend limit ngay
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_ROUTER=            # rẻ nhất, cần structured output
LLM_MODEL_GENERATE=          # mạnh, structured output ổn định
LLM_MODEL_JUDGE=             # trung, output ngắn, batch được

# --- Embedding: KHÔNG qua OpenRouter ---
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

# --- Reranker: tùy chọn, provider riêng ---
RERANK_PROVIDER=cohere       # cohere | local | none
RERANK_MODEL=rerank-v4.0-fast
```

Cả ba dùng chung SDK OpenAI-compatible, chỉ khác `base_url` → code không phức tạp thêm.

**Hai biến trong `.env` hiện tại lệch spec, phải sửa:** `DATABASE_URL` đang trỏ SQLite (spec dùng Postgres — mục 8.2); `CHROMA_PERSIST_DIR` không còn dùng (spec dùng pgvector hoặc numpy, không Chroma).

**Ablation chiều LLM (gần như miễn phí khi đã có OpenRouter):** giữ nguyên graph, đổi `LLM_MODEL_GENERATE` giữa Claude / Gemini / GPT / DeepSeek / Qwen → báo cáo hallucination rate và citation precision của từng model **dưới cùng một cơ chế verify**. Với đề tài về chống ảo giác, bảng "model nào bịa nhiều hơn khi bị kiểm chứng như nhau" là kết quả có giá trị và chi phí thêm chỉ là tiền token.

Set spend limit OpenRouter ngày đầu. Log `token_in/token_out/cost_usd` vào `traces`.

### 8.2 Database: Railway Postgres

| | Railway PG | Supabase free |
|---|---|---|
| Cùng project với BE | ✅ private network | ❌ qua internet |
| pgvector | cần bật extension *(verify)* | ✅ sẵn |
| **Pause khi idle** | ✅ không pause | ⚠ pause sau ~1 tuần *(verify)* |
| Auth/Storage | ❌ | ✅ (KLAW không dùng) |

Quyết định theo **pause khi idle**: bảo vệ vào ngày cố định, DB ngủ = chết demo.

**Rủi ro pgvector ≈ 0:** 10.000 chunk × 384–1024 dim × 4 byte = **15–40 MB** (e5-small 384 dim → 15 MB); brute-force cosine bằng numpy < 10ms. Postgres vẫn cần cho `provisions` (verifier) và BM25 (`tsvector`), nhưng vector store **không phải quyết định lớn** — không bật được pgvector thì numpy in-process là fallback hợp lệ, không phải xuống cấp.

---

## 9. Frontend

**React (Vite) build static, FastAPI `StaticFiles` mount.** Một service Railway, một domain, **không CORS**, không lệch env FE/BE.

Hai màn hình:
- `/` — chat tra cứu; citation **click được → mở nguyên văn điều luật**; badge `✓ đã kiểm chứng` · `⚠ hết hiệu lực một phần` · `✗ không tìm thấy căn cứ`
- `/soan-thao` — form nhập fact (gồm **`vung` bắt buộc**) → preview → **báo cáo kiểm tra** (thiếu mục nào, điều khoản nào trái luật) → tải `.docx`

Bỏ ở MVP: auth, tài khoản, lịch sử chat phía client. Giữ `trace_id` + bảng `traces` server-side (**bắt buộc** — dữ liệu cho chương đánh giá).

---

## 10. Deploy & DevOps

**Railway: 1 project, 2 service** — `klaw-api` (Dockerfile) + `klaw-db` (Postgres), private networking qua variable reference.

Dockerfile hiện có đã đủ; thêm một stage nếu build FE:
```
node:20-slim → npm ci && npm run build → dist/
python builder → pip install --user
python runtime → COPY --from=node dist/ ./static/  +  app.mount("/", StaticFiles(...))
```

**Migration: SQL thuần**, `migrations/001_init.sql`, `CREATE TABLE IF NOT EXISTS`, runner ~15 dòng. Bỏ Alembic. `chunks` sẽ DROP/CREATE nhiều lần khi ablation — đó là thí nghiệm, không phải migration.

**Ingest là job rời**, `scripts/ingest.py`, chạy local hoặc Railway one-off. Idempotent qua `documents.checksum`. **KHÔNG chạy trong API container.**

**CI** (`.github/workflows/ci.yml` đã có ruff + pytest) — thêm **eval smoke**: chạy 20 câu golden, **fail build nếu Recall@5 tụt dưới ngưỡng**.

---

## 11. Đánh giá

### 11.1 Bốn tập dữ liệu

| Tập | Cỡ | Cách xây | Đo |
|---|---|---|---|
| `golden_qa` | 100–150 | tự viết từ corpus, ghi rõ `provision_id` đúng | Recall@k, MRR, nDCG, citation P/R |
| `trap` | 40–50 | điều luật không tồn tại · ngoài lĩnh vực · **văn bản đã bị thay thế ở cấp văn bản** (xem dưới) | abstention accuracy, hallucination rate |
| `draft_facts` | 20 hợp lệ + 30 cài lỗi | tự tạo, mỗi rule 2–3 case | completeness, legality detection, FP |
| `boundary` | ~25 | câu hỏi chi tiết về BHXH · BHTN · công đoàn · NLĐ đi nước ngoài — thuộc **tầng nông** | **coverage-boundary accuracy** |

**Tập `trap` — nhóm "văn bản đã bị thay thế" phải ở CẤP VĂN BẢN, không phải cấp điều khoản.**
Lý do: mục 5.1 đã xác định dữ liệu bãi bỏ cấp điều khoản **không công khai** — nên không thể dựng ground truth đáng tin ở cấp điều. Hai ca cụ thể, đã verify live:

| Ca bẫy | `doc_id` | Trạng thái thật | Hành vi đúng của hệ thống | Cơ chế nào bắt được |
|---|---|---|---|---|
| NĐ 74/2024/NĐ-CP — lương tối thiểu vùng | 168670 | **Hết hiệu lực toàn bộ** | cảnh báo hoặc từ chối, không trích như luật hiện hành | Mức 1 (`effTo`) |
| NĐ 90/2019/NĐ-CP — lương tối thiểu vùng | 139094 | **đã bị thay, nhưng MOJ vẫn đánh "Còn hiệu lực"** | cảnh báo bị thay thế | **chỉ Mức 2** — Mức 1 và `effStatus` đều trượt |

Ca thứ hai là **test case then chốt của cả đề tài**: nó chứng minh cơ chế Mức 2 (đồ thị thay thế) bắt được lỗi mà chính cơ sở dữ liệu quốc gia bỏ sót. Baseline không có cơ chế này sẽ trả lời sai với vẻ hoàn toàn tự tin, kèm citation hợp lệ. Bổ sung thêm ca từ NĐ 157/2018, 141/2017, 122/2015 (cùng lỗi trạng thái).

**Quy trình xây `golden_qa` — phải viết vào khóa luận:**
1. LLM sinh câu hỏi **từ một điều luật cụ thể** → ground truth biết trước
2. **Người review, loại câu lộ đáp án** → **báo cáo tỉ lệ loại**
3. **Viết lại theo giọng dân sinh**, cấm copy thuật ngữ pháp lý

Bước 3 bắt buộc: câu hỏi dùng đúng từ trong luật làm retrieval quá dễ và **pain point #3 không được test**.

### 11.2 Metric riêng của đề tài

```
Citation precision = (citation qua verify tầng 1) / (tổng citation LLM đưa ra)
```
Deterministic, không cần LLM judge. Không có tầng 1 thì không tính được nó.

```
Coverage-boundary accuracy = (số câu tầng nông trả PARTIAL_COVERAGE với ĐÚNG tên luật)
                             / (tổng câu trong tập `boundary`)
```
Hai kiểu sai phải đếm riêng: **bịa chi tiết** (nghiêm trọng) và **abstain oan** (mất thông tin nhưng an toàn).

### 11.3 Bảng kết quả chính

| Cấu hình | R@5 | Cit.P | Faithful | Abstain đúng | **Abstain sai** | Halluc. | p95 | $/câu |
|---|---|---|---|---|---|---|---|---|
| BM25 only | | | | | | | | |
| Dense only | | | | | | | | |
| Hybrid RRF (**baseline**) | | | | | | | | |
| + rewrite_query | | | | | | | | |
| + verify tầng 1 | | | | | | | | |
| + verify tầng 2 (**KLAW**) | | | | | | | | |
| Hướng B: retrieve-then-cite | | | | | | | | |

Cột **"Abstain sai"** cố ý có mặt: từ chối quá nhiều là failure mode thật và là **giá phải trả** của cơ chế. Báo cáo trung thực làm khóa luận mạnh hơn.

Chạy: `python -m eval.run --config configs/full.yaml` → `eval/results/`.

---

## 12. Lộ trình 12 tuần

| Tuần | Việc | Deliverable **kiểm được** |
|---|---|---|
| **0** (3–4 ngày) | Phase 0 (mục 13) | `docs/phase0-findings.md` — mỗi dòng có URL hoặc "không xác minh được" |
| 1–2 | Ingest + schema + parser `prov-*` | `count(*) WHERE cap='dieu'` = **220** cho BLLĐ |
| 3 | Retrieval BM25+dense+RRF, 50 câu golden đầu | Recall@5 có số baseline |
| 4 | `golden_qa` đủ + `trap` 40 + eval harness + **bảng so sánh 5 embedding** | `eval/results/` có bảng đầu |
| 5–6 | Graph tra cứu + verifier 2 tầng + hiệu lực 3 mức | 3 dòng đầu bảng ablation |
| 7 | Soạn thảo + rule engine + test cài lỗi | 3 metric soạn thảo có số |
| 8 | FE + deploy Railway | URL live, click citation ra nguyên văn |
| **9** | Ablation đủ 7 cấu hình + Hướng B | **bảng kết quả chính hoàn chỉnh** ← mốc đủ bảo vệ |
| 10–11 | Viết khóa luận | nháp đủ chương |
| 12 | Slide + **demo dự phòng offline** (video + bản local có dữ liệu) | buổi bảo vệ không phụ thuộc mạng |

**Thứ tự cắt nếu trượt deadline** (quyết trước): Hướng C prototype → reranker → word segmentation → ablation chiều LLM → soạn thảo còn 1 loại văn bản.

---

## 13. Phase 0 — việc phải xác minh trước khi code

| # | Việc | Vì sao |
|---|---|---|
| 1 | Railway Postgres bật được `pgvector` + `unaccent`? | Quyết định vector store (fallback: numpy) |
| 2 | Mở `aistudio.google.com/rate-limit` đọc RPM/RPD thật của Gemini embedding | Docs Google **không còn publish** bảng này; phải đăng nhập xem |
| 3 | Railway auto-detect Dockerfile, hay cần `railway.json`? | Cấu hình deploy |
| 4 | Kiểm phủ class `prov-*` trên toàn corpus (mới verify 3/40 văn bản) | Parser có tin được không |
| 5 | Truy vấn `references` trỏ tới BLLĐ `139264` với `referenceType ∈ {8, 9}` → chốt tầng 2 của corpus | Thay việc lọc tay 1.971 dòng bằng tiêu chí do cơ quan ban hành khai báo (`linh_vuc` sai 66%) |
| 6 | Đối chiếu tay ~10 điều quan trọng với văn bản hợp nhất → `verified_provisions` | Dữ liệu bãi bỏ cấp điều khoản không public |
| 7 | Thử quantize int8 `AITeamVN/Vietnamese_Embedding` bằng `optimum`, đo chất lượng tụt | Họ **không ship** bản int8, khác e5-small |
| 8 | Đo RAM thật bằng `docker stats` cho model embedding đã chọn | Overhead runtime chưa ai công bố |
| 9 | Tra `doc_id` của NĐ 157/2018, 141/2017, 122/2015 (lương tối thiểu cũ) | Bổ sung ca bẫy Mức 2 (mục 11.1) |
| 10 | Đối chiếu tay hiệu lực của **các luật gốc cấp Quốc hội** trong corpus → `verified_documents`. Ưu tiên Luật BHXH 41/2024 (`175027`) | Mức 2 kế thừa lỗi phân loại cạnh của MOJ (mục 5.2 guard) |
| 11 | Tra `doc_id` Luật Giáo dục nghề nghiệp 74/2014/QH13 | Hoàn tất tầng nông (mục 4.3) |

---

## 14. Rủi ro

| Rủi ro | XS | Tác động | Phòng ngừa |
|---|---|---|---|
| Class `prov-*` không phủ đều toàn corpus | TB | +1 tuần | Phase 0 #4; fallback regex `^Điều \d+\.` (đã verify 220/220 trên BLLĐ) |
| Không xác định được điều nào của BLLĐ bị bãi bỏ | **Cao** | **Cao** | `verified_provisions` đối chiếu tay ~10 điều; cảnh báo phạm vi ở UI; ghi rõ vào chương Giới hạn |
| `effStatus` của MOJ sai | **Đã xảy ra** | TB | Cơ chế 3 mức (5.2) — mức 2 bắt được |
| Railway không bật pgvector | TB | **Thấp** | numpy in-process, 15–40 MB |
| Corpus lọc ra nhiễu | TB | TB | Phase 0 #5 lọc tay |
| `golden_qa` bị nghi vì LLM tự sinh | **Cao** | **Cao** | Quy trình 3 bước (11.1) + báo cáo tỉ lệ loại |
| NĐ 12/2022 hết hiệu lực **2026-09-10** | Chắc chắn | Thấp | Theo dõi văn bản thay; đừng hardcode mức phạt |
| Hết ngân sách API | Thấp | TB | Spend limit + cache + log cost |
| Trượt deadline | TB | Cao | Tuần 9 là mốc đủ bảo vệ; 10–12 chỉ viết |

---

## 15. Đạo đức & giới hạn

1. **KLAW không phải dịch vụ tư vấn pháp luật.** Disclaimer thường trực; không kết luận về vụ việc cụ thể; luôn chỉ về văn bản gốc.
2. **Nguồn dữ liệu:** chỉ dùng nội dung VBQPPL — không thuộc phạm vi bảo hộ quyền tác giả theo **Điều 15 khoản 2 Luật SHTT 50/2005/QH11**. Dataset chính có license **CC-BY-4.0** (ghi công đầy đủ).
3. **Không crawl `thuvienphapluat.vn`** — `robots.txt` có `ClaudeBot: Disallow: /`, `ai-train=no`, và reservation of rights theo EU Directive 2019/790 Art.4. Không vượt bot-detection ở bất kỳ site nào.
4. **Giới hạn đã biết, công bố rõ:** không có dữ liệu bãi bỏ cấp điều khoản · vbpl.vn không có robots.txt máy đọc được nên không có "allow" tường minh · phụ lục/biểu mẫu bị 401 · không suy được vùng lương tối thiểu từ địa chỉ · chỉ phủ một lĩnh vực.

---

## 16. Phụ lục — nguồn đã xác minh (2026-08-27)

| Fact | Nguồn |
|---|---|
| API MOJ hoạt động, không auth | `vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{id}` |
| BLLĐ `doc_id` = 139264, 220 điều, `effStatus` HHL1P | API MOJ, fetch live |
| `provisionTree` null 40/40 | API MOJ, 40 văn bản |
| Class `prov-*`, 220/220 khớp `^Điều \d+\.` | `documentContent.content` của 139264 |
| `prov-content` không có id: 157/1332 thẻ | đo trên 139264 |
| Điều 15 Luật SHTT — VBQPPL không bảo hộ quyền tác giả | API MOJ `doc_id 16748`, kiểm chéo 3 luật sửa đổi |
| Dataset CC-BY-4.0, 171.556 docs, 1.033.255 cạnh | HuggingFace `th1nhng0/vietnamese-legal-documents`, DOI 10.57967/hf/8598 |
| `linh_vuc` = "Chưa phân loại" 113.772/171.556 | metadata.parquet |
| OpenRouter: 0 embedding / 0 reranker / 417 model | `openrouter.ai/api/v1/models` |
| Jina embedding $0.02–0.05/1M; 0/29 model nhắc tiếng Việt | `api.jina.ai/v1/models` |
| VN-MTEB: bge-m3 39.84 · gte-mb 38.38 · AITeamVN 34.18 · e5-small 34.12 · MiniLM-L12 14.14 | arXiv 2507.21500, Findings of EACL 2026, Table 3 |
| e5-small có `model_qint8_avx512_vnni.onnx` 0.12 GB; AITeamVN không có bản int8 | HuggingFace API `?blobs=true` |
| Railway: Free 0.5 GB RAM / image 4 GB; RAM $10/GB/tháng | `docs.railway.com/pricing` |
| TVPL `robots.txt`: `ClaudeBot: Disallow: /` | `thuvienphapluat.vn/robots.txt`, HTTP 403 trang chủ |
| 5 rule + checklist 10 mục | API MOJ `doc_id` 139264, 146696, 183939 — trích nguyên văn |

### Chưa xác minh

Điều nào của BLLĐ bị bãi bỏ · danh mục địa bàn vùng I–IV (Phụ lục 401) · mẫu HĐLĐ Phụ lục II TT 5/2023/TT-BNV (PDF 401) · trạng thái "HHL toàn bộ" của Luật BHXH 41/2024 (nghi lỗi MOJ) · chuỗi supersession đầy đủ của nghị định lương tối thiểu · độ chính xác 1.971 dòng corpus · class `prov-*` trên 37/40 văn bản còn lại · overhead RAM runtime · rate limit gateway MOJ · Gemini embedding free tier RPM/RPD.
