# Trả lời tự nhiên: câu hỏi về KLAW, câu hỏi tình huống và phần phân tích

Date: 2026-09-30

## Status

Accepted (chủ dự án chốt các phương án đề xuất, 2026-09-30). Thay quy tắc "câu hỏi meta
trả bằng quy tắc cố định, không dùng model" (CONTEXT.md, docstring `gioi_thieu.py`).

## Context

Chủ dự án, 2026-09-30: "tại sao agent ko thể suy luận được điều tôi muốn … KLAW lại trả
lời kiểu bot". Đo trên app thật cùng ngày (traces 88117154…, 8eb13b06…, 6203bc9d…,
2cfaa33a…):

- "tôi đang gặp sự cố tranh chấp nhà đất, cần nắm rõ những bộ luật gì để ko bị mất
  quyền lợi" bị ép vào nhánh giới thiệu (`gioi_thieu.py` nhánh `những … bộ luật … gì`
  không cần gọi bạn/KLAW/kho) và nhận danh sách 6 Bộ luật, không tra luật — dù Luật
  Đất đai 31/2024/QH15 (Điều 235 hòa giải, Điều 236 thẩm quyền) có đủ toàn văn.
- "bạn là ai / bạn làm được gì" ghép hai đoạn cố định trùng nội dung, còn ghi "chỉ lao
  động"; "bạn giúp tôi được chứ" nhận đoạn năng lực chung kèm dòng "Tôi hiểu câu hỏi
  của bạn là…".
- Luật Nhà ở 27/2023/QH15 mới có tên, chưa có điều; NĐ 101/2024, 102/2024 đang ẩn.

## Decision

1. **Câu hỏi về KLAW do model viết tự nhiên, chỉ từ bảng dữ kiện**: code dựng bảng từ
   dữ liệu hệ thống (vai trò, phạm vi theo lĩnh vực và số văn bản, các loại văn bản
   soạn được, tính năng, giới hạn, tên model); model trả lời đúng câu được hỏi, một
   khối, không lặp; câu nào bảng không đỡ thì bị bỏ.
2. **Câu có tình huống hỏi "cần nắm luật gì" là câu hỏi pháp luật**: đi tra cứu; nhánh
   giới thiệu chỉ nhận câu gọi thẳng bạn/KLAW/kho, và bị phủ quyết khi câu kể tình
   huống của người hỏi hoặc mang nội dung pháp lý.
3. **Luật có trích dẫn + phần "Phân tích cho tình huống của bạn"**: mọi câu nêu quy định
   vẫn phải có trích dẫn và qua hai tầng kiểm; model viết thêm một phần phân tích ghi
   rõ, áp các quy định đã trích vào tình huống, gợi ý bước làm; phần này không nêu quy
   định nào ngoài phần đã trích, không phải tư vấn pháp lý.
4. **Không nhắc "kho" trong câu trả lời pháp lý**: văn bản cần nhưng chưa trích được
   nguyên văn được ghi ở cuối: "Nên đối chiếu thêm: <văn bản> (chưa trích dẫn được
   nguyên văn)", kèm liên kết nguồn khi có.
5. **Câu giới hạn phạm vi** ("Đây là phạm vi văn bản tôi đọc được…") chỉ đi kèm câu trả
   lời về số liệu văn bản; miễn trừ "không thay thế tư vấn của luật sư" giữ nguyên.
6. **Phạm vi tự giới thiệu**: trợ lý pháp luật Việt Nam, sâu nhất ở lao động, kèm số
   liệu thật; tiêu đề và các chỗ còn ghi "chỉ lao động" được sửa cho khớp.
7. **Nạp sâu Luật Nhà ở 27/2023/QH15** và kiểm các văn bản đất đai (Luật Đất đai
   2024 và nghị định hướng dẫn giải quyết tranh chấp) có toàn văn, hiện đúng.
8. Dòng "Tôi hiểu câu hỏi của bạn là…" chỉ hiện khi câu viết lại đổi nghĩa đáng kể,
   không bao giờ với câu hỏi về KLAW; cờ định tuyến và khía cạnh được ghi vào traces.
9. **Điều khoản bị bãi bỏ được ghi có bằng chứng và bị ẩn** (chủ dự án chốt 2026-09-30).
   (a) Mỗi điều, khoản, điểm bị một văn bản khác bãi bỏ đích danh được ghi kèm điều khoản
   đi bãi bỏ, câu trích nguyên văn và nguồn chính thống (bảng `bai_bo_dieu_khoan`,
   migration 043; seed `data/seed/bai_bo_dieu_khoan.yaml`, đọc bằng
   `scripts/trich_bai_bo.py` từ toàn văn gateway Bộ Tư pháp). Từ ngày bãi bỏ, điều khoản
   đó cùng mọi khoản, điểm con bị ẩn khỏi truy hồi, căn cứ, trích dẫn và tìm kiếm; trên
   thân trang văn bản nó còn số hiệu, tiêu đề và câu "Đã bị bãi bỏ bởi … từ …" kèm liên
   kết văn bản đi bãi bỏ; phần còn lại của văn bản vẫn hiện. `effectivity` là nơi phán
   điều khoản đã tới ngày bãi bỏ chưa. (b) Áp cho 101/2024/NĐ-CP và 102/2024/NĐ-CP theo
   151/2025/NĐ-CP Điều 21 khoản 4 điểm b, c, và cho mọi văn bản toàn văn đang hiện có cạnh
   "hết hiệu lực 1 phần" mà câu bãi bỏ đọc trọn được thành danh sách điều khoản; câu giới
   hạn nội dung ("các nội dung quy định về …"), bãi bỏ cụm từ, phụ lục, mẫu, câu có "trừ
   …", hay câu nêu số điều khoản của bản đã sửa đổi thì không ghi (đợt đầu: 56/128 cặp,
   61 câu, 187 điều khoản). (c) Bộ lọc cứng lĩnh vực của truy hồi đọc `nganh_luat` — nhãn
   xếp cho cả kho bằng một bộ từ khoá — thay nhãn nguồn `linh_vuc` (102/2024 mang "Đất
   đai", Luật Đất đai 31/2024/QH15 để trống); mã lĩnh vực của bước viết lại truy vấn được
   xếp vào ngành bằng cùng bộ từ khoá, và điều khoản của văn bản chưa xếp ngành được giữ.
   (d) Sau (a)–(c), 101/2024 và 102/2024 được hiện: cạnh "hết hiệu lực 1 phần" đã đối
   chiếu nguyên văn thay cạnh "thay thế" sai, bỏ lệnh giữ ẩn của commit ba25aef.

## Alternatives Considered

1. Giữ đoạn cố định, viết lại cho hay. Loại: vẫn máy móc, không đáp đúng từng câu.
2. Model trả lời tự do, không bắt buộc kiểm. Loại: phá cam kết trích dẫn kiểm chứng được.
3. Liệt kê văn bản kho theo lĩnh vực cho câu tình huống. Loại: không trả lời điều người
   hỏi cần.

## Consequences

- Câu hỏi về KLAW tốn một lượt model; phải có phép kiểm câu so với bảng dữ kiện.
- Câu trả lời pháp lý dài hơn vì có phần phân tích; bộ đo cần chạy lại.
- Plan: `docs/plans/active/tra-loi-tu-nhien.md`.
