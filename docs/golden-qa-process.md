# Quy trình xây golden_qa (đợt 1 — Lao động)

Spec 11.1: LLM sinh câu hỏi từ một Điều cụ thể (ground truth biết trước) →
người review, loại câu lộ đáp án hoặc lệch nội dung → viết lại giọng dân
sinh. Đây là báo cáo tỉ lệ loại theo yêu cầu.

Nguồn ứng viên: `chunks JOIN provisions` trên toàn bộ cụm Lao động (16 văn
bản, 768 chunk khả dụng), KHÔNG chỉ Bộ luật Lao động — sửa so với bản nháp
đầu của brief vốn chỉ đọc 1 văn bản và lọc theo độ dài `provisions.noi_dung`
ở cấp Điều (loại nhầm đúng các Điều quan trọng nhất vì nội dung thật nằm ở
Khoản con — xem docstring `scripts/gen_golden_candidates.py`).

- Ứng viên LLM sinh: 88 (từ 44 Điều/Khoản × 2 câu, seed 7; 1 lần gọi model bị
  cắt JSON giữa chừng nên bỏ qua, không tính vào 88)
- Người loại: 19 (tỉ lệ loại 19/88 ≈ 21.6%)
- Người sửa ground truth (mở rộng `provision_ids` cho khớp đầy đủ hơn, không
  đổi câu hỏi): 1
- Người viết thêm câu tay (phủ đúng 4 pain point đã đo trong brief + phủ
  thêm 3 văn bản mà random sample không trúng): 8
- Còn lại trong `golden_qa.yaml`: 77 — TẤT CẢ `da_review: false`, `nguon:
  llm-gen`. Agent không có quyền tự duyệt; chủ dự án duyệt tay là bước tiếp
  theo (xem "Việc cần làm tiếp" bên dưới).

## Lý do loại thường gặp (đọc tay từng câu, đối chiếu với `chunks.noi_dung_embed` thật)

1. **Nhầm chủ thể loại tranh chấp**: câu hỏi về tranh chấp lương CÁ NHÂN
   nhưng LLM neo vào Điều 192 (thủ tục tranh chấp lao động TẬP THỂ về
   quyền) — cùng loại lỗi "nhầm phía chủ thể" mà bộ eval này muốn phát hiện,
   nhưng lần này lỗi nằm ở người/LLM sinh câu hỏi, không phải ở hệ thống
   truy hồi. (`lao-012-0/1`)
2. **Điều quá chung** (Phạm vi điều chỉnh / Đối tượng áp dụng / Trách nhiệm
   thi hành): các Điều mở đầu hoặc kết thúc văn bản chỉ nêu phạm vi hoặc ai
   thi hành, không có nội dung cụ thể để thật sự trả lời câu hỏi tình huống
   mà LLM tự dựng ra. (`lao-003`, `lao-021`, `lao-027`)
3. **Lệch điều khoản trong cùng chủ đề**: câu hỏi đúng chủ đề nhưng câu trả
   lời thật nằm ở một Điều khác trong cùng văn bản (vd điều kiện đình công
   hợp pháp là Điều 199, không phải Điều 201 — thủ tục lấy ý kiến).
   (`lao-025-1`)
4. **Nội dung không khớp** khi đối chiếu lại toàn văn (vd câu hỏi về quyền
   lợi khi hoãn/ngừng đình công lệch với đúng nội dung Điều 112 đã đọc kỹ).
   (`lao-008`)
5. **Hợp lệ nhưng quá hẹp/hành chính liên bộ**, ít giá trị test pain point
   dân sinh (vd "Bộ Tài chính chịu trách nhiệm kinh phí gì cho nền tảng
   HĐLĐ điện tử") — giữ lại sẽ pha loãng bộ eval bằng câu không ai thật sự
   hỏi. (`lao-007`, `lao-016`, `lao-019`, `lao-038`)

## Câu tay thêm vào (8 câu, để bảo đảm bộ eval CHỨA ĐƯỢC pain point đã đo, không chỉ tự khen)

Ground truth mọi câu đã kiểm bằng `provisions`/`chunks` thật (không bịa),
xem `tests/test_eval/test_golden_qa.py::test_moi_provision_id_ton_tai_trong_DB_va_duong_dan_khop`.

| Câu hỏi | Ground truth | Vì sao thêm |
|---|---|---|
| "Một ngày mình phải làm việc bao nhiêu tiếng thì đúng luật?" | Điều 105 | Brief đo: hệ thống không trả Điều 105 trong top 3 |
| "Tôi muốn nghỉ việc thì phải báo cho công ty biết trước bao nhiêu ngày?" | Điều 35 (NLĐ) | Brief đo: hệ thống trả nhầm Điều 36 (NSDLĐ) hạng 1 |
| "Đi làm thêm giờ thì có được trả thêm tiền không..." | Điều 107 + Điều 98 | Ví dụ giọng dân sinh trong brief; multi-provision |
| "Bị công ty cho nghỉ việc mà không có lý do gì thì phải kiện ai..." | Điều 41 + Điều 187 | Ví dụ giọng dân sinh trong brief; multi-provision |
| "Lương tối thiểu vùng bây giờ là bao nhiêu một tháng?" | Điều 91 (BLLĐ) + NĐ 293/2025 Điều 3 | Ví dụ multi-provision nêu rõ trong yêu cầu |
| "Tôi bị tai nạn khi đang làm việc, công ty có phải lo..." | Luật ATVSLĐ 84/2015 Điều 38 | Random sample không trúng văn bản này |
| "Bây giờ bao nhiêu tuổi thì được nghỉ hưu?" | Điều 169 (BLLĐ) + NĐ 135/2020 Điều 4 | Random sample không trúng NĐ 135/2020 |
| "Công ty bắt làm thêm giờ liên tục, một tháng tối đa..." | TT 18/2021/TT-BLĐTBXH Điều 6 | Random sample không trúng văn bản này |

## Việc cần làm tiếp (chủ dự án — KHÔNG phải agent)

Toàn bộ 77 item đang `da_review: false`. Đọc từng câu trong
`eval/datasets/golden_qa.yaml`, đối chiếu với `duong_dan`, quyết định giữ/sửa/
loại, rồi đặt `da_review: true` cho item đã duyệt. File
`eval/datasets/golden_qa_candidates.yaml` (88 câu nguyên bản trước khi lọc)
vẫn giữ lại trong git để đối chiếu ngược nếu cần.

Test `test_moi_item_da_qua_review_cua_nguoi` cố ý đỏ cho tới khi việc này
xong — chạy `pytest tests/test_eval/test_golden_qa.py -v` (không filter) để
tự kiểm sau khi duyệt.
