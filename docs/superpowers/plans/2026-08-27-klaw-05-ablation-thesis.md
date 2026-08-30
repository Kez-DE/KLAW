# KLAW Plan 5/5 — Ablation · Cổng B · Khóa luận (tuần 9–12)

> **For agentic workers:** Plan này **KHÔNG theo TDD**. Tuần 9–12 là đo đạc, phản biện và viết — áp "viết test đỏ → implement" lên "viết chương 4" là diễn. Mỗi task có **tiêu chí chấp nhận** thay cho test. Dùng `superpowers:executing-plans` với checkpoint sau mỗi task; đừng dùng subagent-driven cho task viết luận văn.

**Goal:** Bảng kết quả chính hoàn chỉnh, đã qua phản biện đối kháng, và một khóa luận bảo vệ được.

**Spec:** `docs/superpowers/specs/2026-08-27-klaw-design.md` (mục 11, 16.3)
**Plan trước:** `2026-08-27-klaw-04-drafting-fe-deploy.md`

## Nguyên tắc chi phối plan này

1. **Tuần 9 là mốc "đủ để bảo vệ".** Tuần 10–12 chỉ viết. Nếu tuần 9 chưa có bảng kết quả thì cắt phạm vi, không cắt tuần viết.
2. **Không tinh chỉnh tham số trên tập báo cáo.** Task 1 tách tập dev trước khi làm bất cứ gì khác. Đây là lỗ hổng phương pháp mà Cổng B sẽ tấn công.
3. **Mỗi phản biện của Cổng B phải hoặc bị bác bằng dữ liệu, hoặc thành một dòng trong chương Giới hạn.** Không phản biện nào được bỏ qua im lặng.
4. **Số xấu vẫn báo cáo.** "Abstain sai 18%" là kết quả; che nó đi là chỗ mất điểm nặng nhất khi bị hỏi.

---

## Task 1: Tách tập dev · hoàn thiện bộ đánh giá

**Tiêu chí chấp nhận:**
- `eval/datasets/golden_qa.yaml` đủ **150 câu**: 90 Lao động + 60 cho 5 Bộ luật khác (12/bộ)
- `eval/datasets/dev.yaml` — **30 câu tách riêng**, KHÔNG nằm trong 150 câu báo cáo
- `eval/datasets/boundary.yaml` — **25 câu** thuộc tầng nông (BHXH, BHTN, công đoàn, ATVSLĐ chi tiết)
- `docs/golden-qa-process.md` cập nhật tỉ lệ loại cho cả 150 câu
- Test `tests/test_eval/test_golden_qa.py` vẫn xanh với 150 câu

**Việc:**
1. Chuyển 6 Bộ luật sang tầng sâu nếu chưa (`documents.depth`), đặt 6 luật liền kề thành `shallow` (spec 4.3)
2. `python -m scripts.gen_golden_candidates` cho từng Bộ luật còn lại → **người review** → 12 câu/bộ
3. Sinh riêng 30 câu `dev.yaml` **trước khi** chốt 150 câu, để không có câu nào dùng cả hai nơi
4. Viết tay 25 câu `boundary.yaml`, mỗi câu ghi `luat_ky_vong` (số hiệu luật mà `coverage_note` phải nêu đúng)

**Kiểm chồng lấn — chạy trước khi đi tiếp:**

```bash
python3 -c "
import yaml
g={i['cau_hoi'].strip() for i in yaml.safe_load(open('eval/datasets/golden_qa.yaml',encoding='utf-8'))['items']}
d={i['cau_hoi'].strip() for i in yaml.safe_load(open('eval/datasets/dev.yaml',encoding='utf-8'))['items']}
assert not (g & d), f'CHỒNG LẤN dev/test: {g & d}'
print(f'golden {len(g)} · dev {len(d)} · không chồng lấn')
"
```

**Commit:** `feat(eval): 150 golden questions across six codes, plus a held-out dev set`

---

## Task 2: Tinh chỉnh ngưỡng — CHỈ trên tập dev

**Tiêu chí chấp nhận:**
- `docs/threshold-tuning.md` ghi: giá trị đã thử, số đo **trên `dev.yaml`**, giá trị chốt, lý do
- `ABSTAIN_THRESHOLD` và `RRF_K` cuối cùng đến từ tập dev, **không** từ 150 câu báo cáo
- Có một câu trong tài liệu nói rõ điều đó — Cổng B sẽ hỏi

**Việc:** quét `ABSTAIN_THRESHOLD ∈ {0.3, 0.4, 0.5, 0.6, 0.7}` và `RRF_K ∈ {20, 60, 100}` trên `dev.yaml`, chọn theo cân bằng giữa **abstain đúng** (trên `trap`) và **abstain sai** (trên `dev`).

**Ghi lại đánh đổi**, không chỉ giá trị thắng: ngưỡng cao thì ít bịa hơn nhưng từ chối oan nhiều hơn. Đó là một hình vẽ tốt cho khóa luận.

**Commit:** `docs(eval): threshold tuning on the held-out dev set only`

---

## Task 3: Bảng kết quả chính — 7 cấu hình

**Tiêu chí chấp nhận:** `eval/results/report.md` có bảng 7 dòng × 9 cột đầy đủ số, **không ô trống**.

| Cấu hình | Cách chạy |
|---|---|
| Lexical only (`tsvector`+`ts_rank`, KHÔNG phải BM25) | `eval/configs/lexical_only.yaml` |
| Dense only | `eval/configs/dense_only.yaml` |
| Hybrid RRF (**baseline**) | `eval/configs/hybrid.yaml` |
| + rewrite_query | `hybrid_rewrite.yaml` |
| + verify tầng 1 | `hybrid_rewrite_t1.yaml` (`verify_tier2_enabled: false`) |
| + verify tầng 2 (**KLAW**) | `full.yaml` |
| Hướng B: retrieve-then-cite | `retrieve_then_cite.yaml` |

**Cột:** `R@5` · `Citation P` · `Faithful` · `Abstain đúng` · **`Abstain sai`** · `Halluc.` · `p95 (s)` · `$/câu`

**Hướng B** cần một node mới `src/agents/nodes/retrieve_then_cite.py`: LLM #1 chỉ **chọn** provision_id + trích nguyên văn; LLM #2 viết câu trả lời từ các đoạn đã chọn. Đây là **baseline**, không phải tính năng — build tối giản.

**Kiểm tra tính nhất quán bắt buộc trước khi tin bảng:**

```bash
python3 -c "
import json, glob
for f in sorted(glob.glob('eval/results/*.json')):
    d=json.load(open(f))['summary']
    print(f\"{d['config_name']:<24} R@5={d['recall@5']:.3f} n={d['n_queries']}\")
"
```
Mọi dòng phải có **cùng `n_queries` = 150**. Khác nhau nghĩa là có cấu hình chạy trên tập khác — bảng vô giá trị.

**Chạy mỗi cấu hình 3 lần**, báo cáo trung bình ± độ lệch. `temperature=0` **không** đảm bảo xác định qua API (spec 8.1) — một lần chạy không được trình bày như số tuyệt đối.

**Commit:** `feat(eval): complete seven-configuration ablation table with run-to-run spread`

---

## Task 4: Ba bảng phụ

**Tiêu chí chấp nhận:** cả ba có số đầy đủ trong `eval/results/report.md`.

**4a. Bảng tính tổng quát (spec 11.4)** — cấu hình `full` trên 60 câu của 5 Bộ luật khác, một dòng mỗi bộ + dòng đối chứng Lao động 90 câu. Trả lời: *cơ chế verify có chỉ chạy được với Bộ luật Lao động?*

**4b. Bảng coverage boundary** — `full` trên `boundary.yaml` 25 câu. Đếm **riêng** hai kiểu sai: **bịa chi tiết** (nghiêm trọng) và **abstain oan** (an toàn nhưng mất thông tin).

**4c. Bảng chiều LLM** — giữ nguyên graph, đổi `OPENROUTER_GENERATE_MODEL_NAME` giữa ≥4 model (`mistral-nemo`, `qwen3-32b`, `gemini-2.5-flash-lite`, `gemini-2.5-flash`). Báo cáo **hallucination rate và citation precision dưới CÙNG một cơ chế verify** — đây là bảng trả lời trực tiếp câu hỏi trung tâm của đề tài: model nào bịa nhiều hơn khi bị kiểm như nhau.

**4d (nếu còn thời gian). Reranker** — bật `OPENROUTER_RERANK_ENABLED`, so `cohere/rerank-4-fast` vs `qwen/qwen3-reranker-8b` vs không rerank. **Kiểm giá thật trước khi chạy** — `pricing.prompt` trả 0 không phản ánh cách tính.

**Commit:** `feat(eval): generality, coverage-boundary and cross-vendor LLM tables`

---

## Task 5: ⭐ Cổng B — Adversarial Eval Verification (CHẶN)

**Tiêu chí chấp nhận:**
- `docs/gate-b-adversarial.md` có **mọi** phản biện, và với mỗi cái: **bị bác bằng dữ liệu** hoặc **đã thành một dòng trong chương Giới hạn**
- Không phản biện nào ở trạng thái "chưa xử lý"
- File này **đi vào phụ lục khóa luận**

**Cách chạy: 5 agent song song, mỗi agent một góc tấn công.** Prompt của mỗi agent phải mở bằng: *"Mặc định của bạn là kết quả này KHÔNG đáng tin. Nhiệm vụ của bạn là tìm cách bác bỏ nó bằng dữ liệu trong repo."*

| Agent | Góc | Phải trả lời bằng dữ liệu |
|---|---|---|
| 1 | **Leakage** | `golden_qa` có sinh từ chính đoạn text retrieval trả về? Tính tỉ lệ trùng từ vựng query↔document. Có câu nào copy thuật ngữ pháp lý? Đối chiếu `docs/golden-qa-process.md` với `git log` của `golden_qa.yaml` |
| 2 | **Tuning trên test** | Đọc `docs/threshold-tuning.md`: ngưỡng có thật sự chỉ chỉnh trên `dev.yaml`? Kiểm chồng lấn dev/test bằng script. Có tham số nào chỉnh sau khi xem số của 150 câu? |
| 3 | **Baseline bị làm yếu** | Diff `eval/configs/hybrid.yaml` vs `full.yaml`: baseline có cùng retrieval, prompt, model, temperature? Baseline có bị bỏ `rewrite_query` để KLAW trông tốt hơn? |
| 4 | **Cherry-pick** | Đối chiếu `traces.config_name` trong DB với các dòng trong `report.md`. Có cấu hình nào đã chạy mà không báo cáo? Có lần chạy nào bị loại? |
| 5 | **Ý nghĩa thống kê** | 150 câu, chênh 2% có nghĩa gì? Có khoảng tin cậy? Ba lần chạy lệch bao nhiêu? Kết luận nào nằm trong khoảng nhiễu? |

Agent 4 chạy được truy vấn này:

```sql
SELECT config_name, count(*) AS so_query, min(ts), max(ts)
FROM traces GROUP BY config_name ORDER BY min(ts);
```

**Mẫu ghi kết quả:**

```markdown
## Phản biện #N — <tiêu đề>

**Cáo buộc:** …
**Bằng chứng agent đưa ra:** …
**Xử lý:** [ĐÃ BÁC — kèm dữ liệu] hoặc [CHẤP NHẬN — đã thành mục X.Y chương Giới hạn]
```

**Không pass thì không viết chương kết quả.** Viết một chương dựa trên bảng số chưa qua phản biện là làm việc hai lần.

**Commit:** `docs(gate-b): adversarial verification of the results table, every objection resolved`

---

## Task 6: Biểu đồ

**Tiêu chí chấp nhận:** ≥4 hình trong `docs/figures/`, mỗi hình đọc được khi in đen trắng và trên máy chiếu kém.

Dùng skill **`dataviz`**. Bốn hình đáng vẽ:
1. **Ablation 7 cấu hình** — nhóm cột: Citation P và Halluc. cạnh nhau, thấy ngay tầng 1 làm gì
2. **Đánh đổi abstain** — abstain đúng vs abstain sai theo `ABSTAIN_THRESHOLD` (từ Task 2)
3. **Tính tổng quát** — Citation P theo từng Bộ luật, có đường đối chứng Lao động
4. **Chiều LLM** — hallucination rate theo model, cùng cơ chế verify

Hình 1 là hình sẽ xuất hiện trong slide. Hình 2 là hình chứng minh bạn hiểu đánh đổi của chính mình.

**Commit:** `docs(figures): four charts for the results chapter`

---

## Task 7: Viết khóa luận

**Tiêu chí chấp nhận:** bản nháp đủ chương, mỗi khẳng định số liệu **truy được** về một file trong `eval/results/`.

**Quy trình:** `ars-outline` → viết → `ars-full` → **`ars-reviewer` vòng 2 (kết quả)** → sửa → **vòng 3 (bản đầy đủ)** → `ars-citation-check`.

**Ánh xạ chương ↔ artifact đã có:**

| Chương | Nguồn |
|---|---|
| Mở đầu · Đặt vấn đề | spec mục 1, 2 (7 pain point) |
| Tổng quan | spec mục 16.5 (framework 6 tầng), nghiên cứu embedding, VN-MTEB |
| **Phương pháp** | spec mục 4b (không train, và **tại sao**), 5.2 (hiệu lực 3 mức + guard), 6 (verifier 2 tầng), **7b.2 (judge khác họ — self-preference bias)** |
| Dữ liệu | spec mục 4 · `docs/gate-a-report.md` · `docs/golden-qa-process.md` |
| **Kết quả** | `eval/results/report.md` · `docs/embedding-comparison.md` · `docs/prompt-iterations.md` · `docs/figures/` |
| **Thảo luận** | **3 lỗi dữ liệu MOJ đã xác minh** (title `"Hàng hải"`; `nganh` null 5/6; **5/6 Bộ luật HHL một phần = 83% không tra được điều nào đã chết**) · hai chiều lỗi hiệu lực (NĐ 90/2019 false negative, Luật BHXH 41/2024 false positive) |
| **Giới hạn** | `docs/gate-b-adversarial.md` · danh sách "Chưa xác minh" ở phụ lục spec · `temperature=0` không đảm bảo xác định |
| Kết luận · Hướng phát triển | Hướng C (agentic multi-tool), fine-tune embedding pháp lý, mở soạn thảo sang lĩnh vực khác |
| Phụ lục | `docs/gate-b-adversarial.md` toàn văn · `prompts/*.md` · `config/rules.yaml` |

**Ba điểm phải viết rõ, đừng để hội đồng phải hỏi:**

1. **Không train model, và tại sao đó là lựa chọn** (spec 4b.1). Ảo giác citation là vấn đề **grounding**, không phải **kiến thức** — fine-tune không giải được. Luật sửa đổi liên tục nên trọng số lỗi thời ngay.
2. **`ABSTAIN` là hành vi đúng**, và **abstain sai là giá phải trả** — báo cáo cả hai con số.
3. **Cơ chế Mức 2 kế thừa lỗi của đồ thị nguồn** và cách chặn (guard + `verified_documents`). Nói giới hạn trước khi bị hỏi thì đó là sự cẩn trọng; nói sau thì đó là chỗ hở.

**Commit:** `docs(thesis): full draft with every number traceable to a results file`

---

## Task 8: Slide và demo dự phòng

**Tiêu chí chấp nhận:** buổi bảo vệ **không phụ thuộc mạng**.

1. **Slide** — hình 1 và 2 từ Task 6 là hai slide trung tâm. Một slide cho bảng bẫy: *"baseline bịa, KLAW từ chối"*.
2. **Video demo 3–4 phút** — quay 4 `result_type`, và quay cảnh **click citation ra nguyên văn điều luật** (đó là lúc thuyết phục nhất).
3. **Bản chạy local có dữ liệu sẵn** — `docker compose up`, DB đã ingest, và một **file JSON cache** các câu demo để không cần gọi API nếu mạng chết.
4. **Audit FE** — `impeccable` + `Accessibility Auditor` một lượt: contrast trên máy chiếu kém, `abstain` có trông như hành vi đúng không.

**Tự hỏi trước ba câu hội đồng chắc chắn hỏi:**
- *"Em train model gì?"* → không train, và đây là lý do (Task 7 điểm 1)
- *"Sao chỉ 6 Bộ luật?"* → tra cứu 6 Bộ luật là tập trọn vẹn kiểm chứng được; soạn thảo hẹp hơn vì mỗi lĩnh vực cần bộ rule xác minh tay
- *"Hệ thống từ chối nhiều thế thì dùng làm gì?"* → đưa bảng đánh đổi abstain (hình 2), và tỉ lệ bịa của baseline

**Commit:** `docs(defense): slides, recorded demo and an offline fallback`

---

## Thứ tự cắt nếu trượt deadline

Quyết trước để khỏi phải quyết lúc hoảng: **Task 4d (reranker) → Task 4c (chiều LLM) → giảm số lần chạy lại từ 3 xuống 2 → giảm `boundary` từ 25 xuống 15 câu.**

**Không bao giờ cắt:** Cổng B (Task 5) · cột "Abstain sai" · mục Giới hạn. Ba thứ đó là chỗ khóa luận thể hiện sự trung thực học thuật, và là chỗ được chấm cao nhất.
