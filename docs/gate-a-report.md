# Cổng A — Data Integrity Audit

Sinh bởi `python -m scripts.gate_a_audit` (2026-08-27, sau vòng sửa gốc parser).

Phép kiểm ĐỘC LẬP VỚI PARSER: độ phủ token so với văn bản gốc đã strip tag,
cộng hai phép kiểm cấu trúc mà độ phủ dùng `set()` về bản chất không thấy.

**Phạm vi: cả 21 văn bản.** Bản trước chỉ đo 6 Bộ luật — và đó là lý do nó
không thấy gì. Đã đo lại: 6 Bộ luật chỉ mất 1.882 ký tự (0,13%), còn 15 văn bản
còn lại mất 111.239 (TT 09/2020: 64,4% tài liệu). Cổng soi đúng phần parser làm
tốt và bỏ qua đúng phần parser hỏng nặng.

| doc_id | so_ky_hieu | provisions | Điều | token gốc | token thiếu | độ phủ | rỗng | dãy số Điều |
|---|---|---|---|---|---|---|---|---|
| 95942 | 91/2015/QH13 | 2514 | 689 | 3129 | 2 | 99.94% | 0 | liên tục |
| 96122 | 100/2015/QH13 | 4801 | 426 | 3428 | 0 | 100.00% | 0 | liên tục |
| 96115 | 92/2015/QH13 | 2659 | 517 | 2821 | 0 | 100.00% | 0 | liên tục |
| 96172 | 101/2015/QH13 | 2890 | 510 | 2972 | 0 | 100.00% | 0 | liên tục |
| 139264 | 45/2019/QH14 | 1166 | 220 | 2320 | 2 | 99.91% | 0 | liên tục |
| 96117 | 95/2015/QH13 | 1702 | 341 | 2647 | 0 | 100.00% | 0 | liên tục |
| 152668 | 145/2020/NĐ-CP | 911 | 115 | 2752 | 0 | 100.00% | 0 | liên tục |
| 146696 | 10/2020/TT-BLĐTBXH | 104 | 12 | 726 | 0 | 100.00% | 0 | liên tục |
| 183939 | 293/2025/NĐ-CP | 28 | 5 | 356 | 0 | 100.00% | 0 | liên tục |
| 185561 | 337/2025/NĐ-CP | 193 | 30 | 846 | 0 | 100.00% | 0 | liên tục |
| 153913 | 12/2022/NĐ-CP | 972 | 64 | 1610 | 0 | 100.00% | 0 | liên tục |
| 152670 | 09/2020/TT-BLĐTBXH | 68 | 13 | 1895 | 0 | 100.00% | 0 | liên tục |
| 153297 | 18/2021/TT-BLĐTBXH | 44 | 10 | 605 | 8 | 98.68% | 0 | liên tục |
| 152734 | 135/2020/NĐ-CP | 34 | 9 | 369 | 0 | 100.00% | 0 | liên tục |
| 134611 | 29/2019/NĐ-CP | 181 | 29 | 1170 | 0 | 100.00% | 0 | liên tục |
| 70811 | 84/2015/QH13 | 665 | 93 | 1699 | 0 | 100.00% | 0 | liên tục |
| 168670 | 74/2024/NĐ-CP | 27 | 5 | 358 | 0 | 100.00% | 0 | liên tục |
| 139094 | 90/2019/NĐ-CP | 35 | 6 | 398 | 0 | 100.00% | 0 | liên tục |
| 132862 | 157/2018/NĐ-CP | 35 | 6 | 733 | 0 | 100.00% | 0 | liên tục |
| 126319 | 141/2017/NĐ-CP | 35 | 6 | 422 | 0 | 100.00% | 0 | liên tục |
| 92898 | 122/2015/NĐ-CP | 36 | 6 | 478 | 0 | 100.00% | 0 | liên tục |

- Văn bản đã đo: **21** / 21
- Độ phủ thấp nhất: **98.68%** (ngưỡng 98%) — ĐẠT
- `noi_dung` rỗng ở cấp trích dẫn được: **0** (ngưỡng 0) — ĐẠT
- Dãy số Điều hỏng: **0** văn bản (ngưỡng 0) — ĐẠT
- Neo trích dẫn (`duong_dan` cấp dieu/khoan/diem) trùng: **0** — ĐẠT
- **Kết quả: PASS**

## Trùng ở cấp container — chấp nhận có chủ đích

- `145/2020/NĐ-CP > Chương XI` xuất hiện 2 lần

NĐ 145/2020 thật sự đánh số hai Chương cùng là "Chương XI". Neo trích dẫn phải
là thứ CÓ TRONG văn bản nguồn, nên cổng KHÔNG bịa "XII" để né trùng; cấp
container chỉ WARN, cấp trích dẫn được thì RAISE.

## Phần dưới 100% còn lại của độ phủ KHÔNG phải mất chữ

Ba văn bản chưa đạt 100% và cả ba là chênh lệch TÁCH TỪ, không phải mất chữ:

- `95942` thiếu `[',', ';']`, `139264` thiếu `['.', '“']` — token chỉ có dấu câu.
- `153297` thiếu `['(T', ')]', 'L', 'N', '[T', 'n', 'p', 't']` — mảnh của công
  thức `T<sub>Q</sub> = [T<sub>N</sub> - (T<sub>t</sub> + T<sub>p</sub>)]`.

`get_text(" ")` của Cổng A chèn khoảng trắng ở MỌI biên thẻ kể cả thẻ inline
(`T Q = [T N …]`), phía parser thì dán liền (`TQ = [TN …]`). Hàm này CỐ Ý không
được chỉnh cho khớp parser: cổng phải giữ tính độc lập, kể cả khi giá là vài
token dấu câu. Phép bảo toàn ký tự tuyệt đối (0 ký tự lệch, không ngưỡng) là
việc của `prov_parser.parse_anomalies()`, chạy trong `build_seed`.

## Lỗ của chính phép đo này

- Đối xứng NFC hai phía ⇒ Cổng A **vĩnh viễn không thấy** lệch NFC/NFD giữa văn
  bản lưu và truy vấn người dùng. Vì thế NFC được áp ở TẦNG LƯU trong parser,
  không chỉ ở tầng so sánh.
- `<table>` bị decompose ở CẢ HAI phía ⇒ nội dung bảng ra ngoài phạm vi đo
  (thuộc Plan 2). `parse_anomalies()` cảnh báo khi có thẻ `prov-*` trong bảng và
  CHẶN build nếu đó là cấp trích dẫn được (BLHS hiện có 9 ca cấp container:
  "Phần thứ hai"/"Mục 3" lặp ở đầu trang Công báo tiếp theo).
- Độ phủ dùng `set()` ⇒ không thấy trùng lặp và không thấy thứ tự. Đó là lý do
  có C1 (dãy số Điều) và C2 (neo trích dẫn duy nhất).

Chẩn đoán đầy đủ, cơ chế và các lỗ của phép đo bản cũ:
`.superpowers/sdd/2026-08-27-klaw-01-data-layer/task-10-report.md`
