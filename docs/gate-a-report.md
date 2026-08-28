# Cổng A — Data Integrity Audit

Sinh bởi `python -m scripts.gate_a_audit` (2026-08-28, sau vòng sửa gốc parser,
sau ruling tách chữ đuôi thành cấp `phu_luc`, và sau ruling C1/H2/H3 tách chữ
đầu thành cấp `mo_dau`).

Phép kiểm ĐỘC LẬP VỚI PARSER: độ phủ token so với văn bản gốc đã strip tag,
cộng hai phép kiểm cấu trúc mà độ phủ dùng `set()` về bản chất không thấy.

**Phạm vi: cả 21 văn bản.** Bản trước chỉ đo 6 Bộ luật — và đó là lý do nó
không thấy gì. Đã đo lại: 6 Bộ luật chỉ mất 1.882 ký tự (0,13%), còn 15 văn bản
còn lại mất 111.239 (TT 09/2020: 64,4% tài liệu). Cổng soi đúng phần parser làm
tốt và bỏ qua đúng phần parser hỏng nặng.

| doc_id | so_ky_hieu | provisions | Điều | token gốc | token thiếu | độ phủ | rỗng | dãy số Điều |
|---|---|---|---|---|---|---|---|---|
| 95942 | 91/2015/QH13 | 2515 | 689 | 3129 | 2 | 99.94% | 0 | liên tục |
| 96122 | 100/2015/QH13 | 4802 | 426 | 3428 | 0 | 100.00% | 0 | liên tục |
| 96115 | 92/2015/QH13 | 2661 | 517 | 2821 | 0 | 100.00% | 0 | liên tục |
| 96172 | 101/2015/QH13 | 2890 | 510 | 2972 | 0 | 100.00% | 0 | liên tục |
| 139264 | 45/2019/QH14 | 1168 | 220 | 2320 | 2 | 99.91% | 0 | liên tục |
| 96117 | 95/2015/QH13 | 1704 | 341 | 2647 | 0 | 100.00% | 0 | liên tục |
| 152668 | 145/2020/NĐ-CP | 913 | 115 | 2752 | 0 | 100.00% | 0 | liên tục |
| 146696 | 10/2020/TT-BLĐTBXH | 106 | 12 | 726 | 0 | 100.00% | 0 | liên tục |
| 183939 | 293/2025/NĐ-CP | 30 | 5 | 356 | 0 | 100.00% | 0 | liên tục |
| 185561 | 337/2025/NĐ-CP | 194 | 30 | 846 | 0 | 100.00% | 0 | liên tục |
| 153913 | 12/2022/NĐ-CP | 973 | 64 | 1610 | 0 | 100.00% | 0 | liên tục |
| 152670 | 09/2020/TT-BLĐTBXH | 70 | 13 | 1895 | 0 | 100.00% | 0 | liên tục |
| 153297 | 18/2021/TT-BLĐTBXH | 46 | 10 | 605 | 8 | 98.68% | 0 | liên tục |
| 152734 | 135/2020/NĐ-CP | 36 | 9 | 369 | 0 | 100.00% | 0 | liên tục |
| 134611 | 29/2019/NĐ-CP | 183 | 29 | 1170 | 0 | 100.00% | 0 | liên tục |
| 70811 | 84/2015/QH13 | 667 | 93 | 1699 | 0 | 100.00% | 0 | liên tục |
| 168670 | 74/2024/NĐ-CP | 29 | 5 | 358 | 0 | 100.00% | 0 | liên tục |
| 139094 | 90/2019/NĐ-CP | 36 | 6 | 398 | 0 | 100.00% | 0 | liên tục |
| 132862 | 157/2018/NĐ-CP | 37 | 6 | 733 | 0 | 100.00% | 0 | liên tục |
| 126319 | 141/2017/NĐ-CP | 37 | 6 | 422 | 0 | 100.00% | 0 | liên tục |
| 92898 | 122/2015/NĐ-CP | 38 | 6 | 478 | 0 | 100.00% | 0 | liên tục |

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

## Cấp `phu_luc` — chữ đuôi tách theo VỊ TRÍ

Chữ mồ côi **sau thẻ `prov-*` cuối cùng** (Phụ lục, khối chữ ký) là một bản ghi
`phu_luc` riêng cho mỗi văn bản, cấp KHÔNG trích dẫn được. Chữ mồ côi **xen giữa
hai thẻ `prov-*`** là tiếp nối thật và vẫn gắn vào provision đang mở.

Đã đo phân bố: `152668` 42.636 đuôi / 647 xen giữa, `152670` 25.316 / 560,
`134611` 21.296 / 653 — 97–98% ở đuôi. Ranh giới là thật, nhận diện bằng vị trí
chứ không bằng regex tiếng Việt.

18 / 21 văn bản có chữ đuôi (17 trước khi vá H2: Bộ luật Hình sự có đúng MỘT
`<p class="prov-content">` rỗng đứng SAU khối "Bộ luật này đã được Quốc hội …
thông qua", và thẻ rỗng đó — không mang chữ nên không mang thông tin vị trí —
đẩy mốc đo vượt qua khối đuôi, làm 132 ký tự đó sập lại vào provision đang mở).
Tác dụng lên neo trích dẫn:
`145/2020/NĐ-CP > Điều 115` từ **44.106 → 278** ký tự; neo dài nhất còn lại trong
toàn corpus là 2.561 ký tự (`45/2019/QH14 > Điều 219 > Khoản 1 > Điểm a`). Trước
đó có 3 neo vượt 20.000 ký tự, tức một câu trích lấy từ Phụ lục sẽ "kiểm chứng
thành công" trên một neo Điều. Giờ 0.

`phu_luc` vẫn tính vào độ phủ token (chữ vẫn trong corpus) nên `do_phu_min`
không tụt: **0.9868 trước và sau**.

## Cấp `mo_dau` — chữ đầu, ĐỐI XỨNG với `phu_luc`

Chữ mồ côi **trước thẻ `prov-*` đầu tiên** (tiêu ngữ "CHÍNH PHỦ / CỘNG HÒA XÃ
HỘI CHỦ NGHĨA VIỆT NAM", số hiệu, tên văn bản, chuỗi "Căn cứ …", câu ban hành)
trước đây ghép vào `noi_dung` của provision đầu tiên. 13/21 văn bản mở đầu bằng
`prov-part`/`prov-chapter` nên row đó là cấp container — vô hại. **8/21 văn bản
mở đầu TRỰC TIẾP bằng "Điều 1"**, và ở đó row đầu là cấp TRÍCH DẪN ĐƯỢC: một câu
trích lấy từ TÊN VĂN BẢN hoặc từ chuỗi "Căn cứ …" sẽ khớp nguyên văn trong
`noi_dung` của Điều 1 và được tầng 1 trả về "đã kiểm chứng".

Giờ nó là MỘT bản ghi `mo_dau` cho mỗi văn bản (21/21 văn bản đều có chữ đầu),
cấp TÀI LIỆU, `parent_id` NULL, `so_hieu_cap` rỗng, `duong_dan = "<so_ky_hieu> >
Mở đầu"`, KHÔNG trích dẫn được và KHÔNG đánh số thứ tự.

`len(Điều 1.noi_dung)` của 8 văn bản đó, trước → sau:

| so_ky_hieu | Điều 1 trước | Điều 1 sau | Mở đầu |
|---|---|---|---|
| 293/2025/NĐ-CP | 695 | 166 | 528 |
| 18/2021/TT-BLĐTBXH | 1056 | 231 | 824 |
| 135/2020/NĐ-CP | 569 | 106 | 462 |
| 74/2024/NĐ-CP | 807 | 166 | 640 |
| 90/2019/NĐ-CP | 627 | 173 | 453 |
| 157/2018/NĐ-CP | 613 | 173 | 439 |
| 141/2017/NĐ-CP | 741 | 173 | 567 |
| 122/2015/NĐ-CP | 1191 | 312 | 878 |

Cũng như `phu_luc`, chữ chỉ ĐỔI CHỖ nên `do_phu_min` không tụt: **0.9868 trước
và sau**. Bất biến còn thiếu mà cả ba cổng đều mù (bảo toàn ký tự nói "không
mất", độ phủ dùng `set()` nên chữ chỉ cần "có mặt") giờ có test: `noi_dung` của
một provision cấp trích dẫn được phải MỞ ĐẦU bằng nhãn của chính nó —
`tests/test_scripts/test_seed_committed.py::
test_noi_dung_cap_trich_dan_duoc_MO_DAU_bang_nhan_cua_chinh_no`.

## Gộp mảnh Khoản/Điểm không có số hiệu (H3)

4 mảnh trong corpus từng thành neo trích dẫn KHÔNG CÓ SỐ (`"… > Điều 33 > Khoản"`
— không phải một dẫn chiếu pháp luật Việt Nam), và tệ hơn: provision cha bị CẮT
CỤT, nên một trích dẫn ĐÚNG vào khoản đó THẤT BẠI ở tầng 1 (false-negative trên
đúng phép kiểm số 3). Đã đối chiếu HTML thô cả 4: mỗi thẻ đứng ngay sau một thẻ
CÙNG CẤP có số và mở đầu giữa câu, không dấu hiệu số hiệu nào.

Với Khoản/Điểm, SỐ HỌC LÀ NHÃN, nên "không parse được số" chính là dấu hiệu
"không mở đầu bằng nhãn" mà cấp có nhãn đang dùng — cùng một luật. 4 mảnh giờ
nằm trong `noi_dung` của sibling cùng cấp liền trước:

| mảnh | về đúng |
|---|---|
| BLDS Điều 33 ("Trường hợp người được thử nghiệm …") | `91/2015/QH13 > Điều 33 > Khoản 3` |
| BLTTHS Điều 33 ("Nếu phát hiện hành vi trái pháp luật …") | `101/2015/QH13 > Điều 33 > Khoản 2` |
| BLTTHS Điều 123 ("Trường hợp bị can, bị cáo vì lý do bất khả kháng …") | `101/2015/QH13 > Điều 123 > Khoản 5` |
| BLHS Điều 3 ("Khoan hồng đối với người tự thú …") | `100/2015/QH13 > Điều 3 > Khoản 1 > Điểm d` |

`khoan`/`diem` có `so_hieu_cap` rỗng: **4 → 0**. Số mảnh đã gộp được WARN lúc
build (WARN chứ không RAISE: 0 là con số hiện tại của corpus, không phải bất
biến — MOJ tách thêm một đoạn thì gộp vẫn là hành vi ĐÚNG).

## Bất biến đã đẩy xuống DB (migration `004`)

Hai bất biến nền tảng trước đây chỉ tồn tại lúc BUILD (`_kiem_bat_bien`) và trên
FILE ĐÃ COMMIT (`test_seed_committed.py`), không cái nào trên đường INGEST:

```
ux_provisions_neo_trich_dan  UNIQUE (duong_dan) WHERE cap IN ('dieu','khoan','diem')
provisions_noi_dung_citable_check  CHECK (cap NOT IN (...) OR btrim(noi_dung) <> '')
```

`005` thêm ràng buộc thứ ba, dạng ĐỒNG NHẤT (đúng cho cả cấp sẽ thêm về sau,
không chỉ cấp đang có bug):

```
provisions_so_hieu_cap_check  CHECK (cap IN ('mo_dau','phu_luc') OR btrim(so_hieu_cap) <> '')
```

Partial index vì cấp container có ngoại lệ đã chấp nhận (hai "Chương XI" của
NĐ 145/2020). Đã xác minh chạy cả 6 migration HAI LẦN trên bảng có đủ 19.135 dòng.

`scripts/ingest.py` giờ ĐỌC `checksums.json`: `_kiem_toan_ven()` chạy MỘT LẦN
trước vòng lặp document (và trước `run_migrations()`), băm lại từng file seed và
raise nếu lệch hoặc nếu thiếu mục. Trước đó `checksums.json` là artefact CHỈ-GHI,
nên kênh "sửa `provisions.jsonl` mà không chạm `documents.jsonl` → ingest trả
0/0/0, không phân biệt được với re-run lành" còn nguyên.

`mo_dau` có `thu_tu = -1` (không phải index cuối): `local_id` vẫn ở cuối để
`parent_local_id` không phải dịch, nhưng chữ mở đầu nằm ở ĐẦU văn bản.

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
