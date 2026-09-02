# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vite + React + TypeScript + Tailwind, build vào `src/static/`, FastAPI mount tại `/`.
Quyết định sẵn trong `docs/superpowers/plans/2026-08-27-klaw-04-drafting-fe-deploy.md`
Task 7, không phải lựa chọn mở.

Backend đã tồn tại và chạy: FastAPI + LangGraph + Postgres 16 (pgvector), Python 3.11.

## Sản phẩm

KLAW tra cứu pháp luật Việt Nam và soạn thảo văn bản pháp lý lao động, với một ràng
buộc mà các trợ lý pháp lý khác không có: **mọi khẳng định phải neo vào một trích dẫn
kiểm chứng được, và việc kiểm chứng đó là phép tra bảng chứ không phải suy luận của
mô hình.**

Cơ chế: bảy phép kiểm ở ba tầng, tất cả **0 token**.

- **đầu vào** — câu hỏi dẫn một điều luật không tồn tại thì nói thẳng
- **trích dẫn** — điều luật có thật? nằm trong tập đã truy hồi? câu trích đúng nguyên văn? còn hiệu lực?
- **đầu ra** — mọi số điều nhắc trong câu trả lời phải nằm trong tập trích dẫn đã xác minh

Đây là khóa luận tốt nghiệp, nhưng bản FE này được xây như **sản phẩm dùng thật**.

## Người dùng

Ba nhóm, **không nhóm nào phụ**:

| Nhóm | Tình huống | Việc họ làm |
|---|---|---|
| Người lao động | Bị trừ lương, bị đuổi việc, thắc mắc quyền lợi | Hỏi bằng lời thường, cần câu trả lời hiểu được ngay, và cần biết nó dựa vào đâu |
| Nhân sự / HR doanh nghiệp vừa và nhỏ | Soạn hợp đồng, nội quy, quyết định kỷ luật | Tra cứu **và** soạn thảo; quan tâm tính hợp pháp và hiệu lực; làm trên máy tính |
| Sinh viên luật / người nghiên cứu | Tra cứu chính xác, đọc toàn văn | Cần dẫn chiếu chéo, hiệu lực theo thời điểm, mật độ thông tin cao |

Hệ quả thiết kế: **cùng một câu trả lời phải phục vụ được cả ba** — dễ hiểu ở lớp
trên, đầy đủ ở lớp dưới khi người dùng muốn đào sâu. Không phải ba giao diện khác nhau.

## Bốn trạng thái kết quả — ràng buộc trung tâm của giao diện

| Trạng thái | Nghĩa |
|---|---|
| `answer` | có căn cứ, đã qua cả hai tầng kiểm |
| `partial_coverage` | chỉ trúng tầng nông — nêu văn bản, **không** diễn giải. **Đã sống từ 2026-09-01** (xem dưới) |
| `abstain` | không đủ căn cứ |
| `out_of_scope` | ngoài phạm vi 6 Bộ luật + cụm Lao động |

**`abstain` là hành vi ĐÚNG, được tính điểm trong đánh giá — không phải lỗi.** Giao
diện phải thể hiện đúng như vậy: màu trung tính, giọng bình thường. Một hệ thống thà
nói "tôi không đủ căn cứ" còn hơn bịa một điều luật, và giao diện là nơi lời hứa đó
hiện ra hoặc bị phản bội.

## Hiệu lực — thông tin không được giấu

Corpus là **văn bản gốc**, không phải bản hợp nhất (mọi văn bản hợp nhất trên cổng
MOJ đều chỉ có PDF scan, không có toàn văn máy đọc được). Hệ thống bảo đảm **nguồn
gốc** và **đúng nguyên văn**, **không** bảo đảm **là bản hiện hành**.

Cơ sở dữ liệu quốc gia đánh **bốn** nghị định lương tối thiểu đã bị thay thế là "còn
hiệu lực"; KLAW phát hiện và sửa cả bốn.

**Cập nhật 2026-09-01 — giới hạn cấp điều khoản đã lùi một bước.** Trước đây tài
liệu này ghi "CSDL quốc gia không công bố dữ liệu cấp điều khoản" như một ranh
giới tuyệt đối. Đúng với API MOJ (`referenceProvisions` khác null: **0/272**),
nhưng **không** đúng với Công báo: `congbao.chinhphu.vn` phát hành văn bản hợp
nhất dạng `.docx` gốc, trong đó `<w:footnoteReference>` nằm trong chính đoạn văn
là khoản bị sửa — neo **cấu trúc**, không phải suy diễn ngữ nghĩa.

Đã chạy thật trên `18/VBHN-VPQH` (Bộ luật Lao động): **4/4 điểm sửa giải được, 0
cần đối chiếu tay**, 3,67 giây, **0 token**. Ví dụ đo được: `Điều 139 > Khoản 1`
đi từ *"không xác định được"* thành *"bị sửa bởi khoản 1 Điều 29 của
113/2025/QH15 từ 01/7/2026"*. Khoản 2 kề bên **không** thừa hưởng nhãn — chỉ
khoản thật sự bị sửa mới mang nó.

**Giới hạn của chính cải tiến này, nói rõ:** chỉ áp dụng cho văn bản **có** bản
hợp nhất trên Công báo (~2.900 VBHN tồn tại, hiện mới nạp **một**). Và hệ thống
nay nói đúng rằng câu trả lời **không còn hiện hành** — nhưng vẫn **chưa nói được
câu trả lời hiện hành là gì**, vì `113/2025/QH15` và `124/2025/QH15` chưa nằm
trong corpus. Corpus vẫn là **văn bản gốc**; bản hợp nhất chỉ dùng để suy ra bản
đồ sửa đổi, không thay thế nguyên văn. Mỗi trích dẫn mang nhãn hiệu lực, và nhãn đó
phải **thấy được**, không nằm trong metadata.

| Nhãn | Ý nghĩa |
|---|---|
| `con_hieu_luc` | còn hiệu lực |
| `bi_thay_the` / `het_hieu_luc` | đã bị thay thế — kèm tên văn bản thay thế |
| `mot_phan_khong_xac_dinh` | bị sửa một phần; **chưa** xác định được điều này còn hiệu lực hay không |
| `bi_sua_doi` | bị sửa một phần, và **biết đích danh** điều khoản nào, bởi văn bản nào, từ ngày nào |
| `can_doi_chieu_tay` | cần người đối chiếu |

## Phạm vi corpus

21 văn bản, 19.135 điều khoản.

- **Sáu Bộ luật**: Dân sự (689 Điều), Tố tụng dân sự (517), Tố tụng hình sự (510), Hình sự (426), Hàng hải (341), Lao động (220)
- **Cụm Lao động** 15 văn bản dưới luật: nghị định hướng dẫn, xử phạt, an toàn vệ sinh lao động, tuổi nghỉ hưu, thời giờ làm việc, 6 nghị định lương tối thiểu

Chiều sâu **không đều**: Lao động có luật + nghị định + thông tư + chế tài; năm Bộ
luật còn lại chỉ có bản thân bộ luật. Giao diện không được ngụ ý mọi lĩnh vực được
phủ như nhau.

Không phủ: thuế, đất đai, hôn nhân gia đình, doanh nghiệp, đầu tư, sở hữu trí tuệ.

## Thuật ngữ

- Định danh văn bản bằng **`so_ky_hieu`** (`45/2019/QH14`), **không bao giờ** bằng tên.
  Tên chỉ để hiển thị cho người đọc (`Bộ Luật lao động số 45/2019/QH14`).
- **Đính chính 2026-08-31:** ràng buộc này trước đây được biện minh bằng câu
  "`doc_id 96117` có tên chỉ là 'Hàng hải'". **Câu đó SAI** — tên thật là
  `Bộ luật Hàng hải số 95/2015/QH13`. Ràng buộc vẫn giữ, nhưng lý do thật khác:
  54/57 văn bản nhúng cả `số <so_ky_hieu>` vào `ten`, và `ten` không nhất quán
  về hoa/thường (`Bộ Luật lao động`) lẫn có bản ALL-CAPS.
- **Và `so_ky_hieu` KHÔNG duy nhất trên toàn bảng**: `65/2006/QH11` thuộc hai
  văn bản (`Nghị quyết…` id 15074 và `Luật sư…` id 15076). Cả hai ở tầng
  metadata (0 điều khoản) nên trích dẫn an toàn — nhưng `/pham-vi` và `nguon`
  của `partial_coverage` CÓ chạm tầng nông, nên chúng phải khoá theo `doc_id`.

**Cập nhật 2026-09-01 — `partial_coverage` ĐÃ SỐNG.** 74 văn bản tầng nông nay
mỗi văn bản có một hàng `mo_dau` mang tên nó, và bộ chia chunk đánh chỉ mục hàng
đó — CHỈ cho tầng nông, vì tiền tố của 47 văn bản tầng sâu là letterhead lặp lại
(trung bình 467 ký tự) và 47 chunk gần trùng là nhiễu tệ nhất khi `ts_rank` không
có IDF.

Đánh chỉ mục chưa đủ. Đo được: "Nghị định 95/2026 quy định gì?" truy hồi 18 nguồn
— 16 tầng sâu KHÔNG liên quan và 2 tầng nông ĐÚNG — nên điều kiện cũ
`not deep and shallow` bỏ qua, rồi 16 nguồn kia sinh 0 luận điểm và người hỏi
nhận `abstain` trơ trong khi hệ thống đang cầm tên nghị định. Điều kiện nay kích
thêm khi **không luận điểm nào sống sót nhưng có nguồn tầng nông**; nó chỉ NÂNG
CẤP một `abstain`, không bao giờ chen chỗ câu trả lời thật.

Lời hứa "nêu văn bản, KHÔNG diễn giải" do SCHEMA giữ, không cần code:
`ux_provisions_neo_trich_dan` và `provisions_noi_dung_citable_check` chỉ phủ
`dieu`/`khoan`/`diem`, nên hàng `mo_dau` không bao giờ thành trích dẫn nguyên văn.

Giữ lại chẩn đoán cũ vì nó vẫn đúng về nguyên nhân:

**Đính chính 2026-08-31 — `partial_coverage` khi đó là nhánh KHÔNG kích hoạt được.**
Tôi đã nhiều lần nói "36 văn bản metadata chính là thứ sinh ra `partial_coverage`".
**Sai.** Chuỗi kiểm: `expand.py:123-126` chỉ giữ `depth` là `deep` hoặc `shallow`
và loại `metadata`; DB có `deep: 21`, `metadata: 36`, **`shallow: 0`**; và 36 văn
bản metadata có **0 provision** nên truy hồi không bao giờ chạm tới. Điều kiện
`assemble.py:260` `if not deep and shallow:` vì thế không bao giờ đúng.

Nhánh này **được giữ lại** — nó đúng về hành vi, tốn 0 token, và sẽ kích hoạt
ngay khi corpus có một văn bản `depth='shallow'`: đúng trường hợp một văn bản có
metadata mà MOJ không công bố toàn văn máy đọc được. Việc mở rộng corpus có thể
làm nó sống. Nhưng tới lúc đó, **đừng mô tả nó như một nhánh đang chạy**.
  Khoá duy nhất tuyệt đối là `doc_id`; `so_ky_hieu` là định danh CHO NGƯỜI ĐỌC.
- `duong_dan` là chuỗi trích dẫn chính tắc: `45/2019/QH14 > Điều 127 > Khoản 2`
- Một trích dẫn mang **hai** id: `provision_id` (điều luật mô hình dẫn) và
  `khop_tai_id` (dòng câu trích thật sự khớp). Chúng khác nhau ở **73,6%** số Điều,
  vì phần lớn Điều chỉ có tiêu đề còn nội dung nằm ở Khoản con.

## Ngôn ngữ

Chỉ tiếng Việt. Nhãn, thông báo, SEO đều tiếng Việt.

## Ràng buộc kỹ thuật đã cố định

- `GET /van-ban/{id}` **phải lazy** — Bộ luật Dân sự có 689 Điều, không tải cả cây
- Endpoint đã có: `POST /api/v1/tra-cuu`; Task 5 thêm `/soan-thao` và `/soat`
- `self_audit=true` phân biệt "soát output của chính mình" với "soát văn bản người
  dùng đưa vào" — cần cho số liệu đánh giá

## Quyết định còn mở — chịu tải cao

Chủ dự án muốn sản phẩm **chịu được lượng truy cập cao**. Hiện chưa khả thi, và FE
không giải quyết được:

- một request tra cứu gọi LLM tối đa **5 lần**, mất **10–60 giây**, tốn **~$0,0065**
- **không có rate limit, không có trần chi phí** — rà soát bảo mật đã nêu là cổng bắt
  buộc trước khi mở ra ngoài
- chưa có cache câu trả lời

Cần trước khi mở công khai: cache theo câu hỏi đã chuẩn hoá, rate limit theo IP, trần
chi phí ngày, và hàng đợi cho request dài. Đó là việc backend, **không nằm trong phạm
vi Task 7**.

FE phần của nó: tài sản tĩnh cache được, tải nhanh trên mạng yếu, và trạng thái chờ
trung thực cho một thao tác mất 10–60 giây.

## Khả năng tiếp cận

Người dùng gồm người lao động dùng điện thoại đời cũ, mạng yếu. Chưa có cam kết chuẩn
WCAG cụ thể; mặc định làm đúng nền tảng (tương phản đủ, bàn phím dùng được, đánh dấu
ngữ nghĩa) thay vì tuyên bố một mức tuân thủ chưa kiểm chứng.
