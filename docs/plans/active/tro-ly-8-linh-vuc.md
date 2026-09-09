# Execution Plan: Trợ lý phủ 8 lĩnh vực, trả lời đúng dạng câu hỏi

Date: 2026-09-02

## Status

Active

## Outcome

Quan sát được qua giao diện thật, sau khi xong:

1. `bạn là ai` và `bạn làm được những gì` trả về **hai** câu trả lời khác nhau.
   Câu đầu mở bằng danh tính ("Tôi là KLAW — trợ lý AI về pháp luật Việt Nam"),
   câu sau là bài năng lực. Hôm nay hai câu trả về cùng một đoạn văn từng byte.
2. Câu hỏi về kho hoặc về năng lực, khi người dùng xin "dạng bảng", hiện ra một
   `<table>` thật trên màn hình — không phải văn xuôi gạch đầu dòng.
3. Bảng phạm vi khai **8 lĩnh vực** kèm nhãn độ sâu đọc từ DB, không viết cứng.
4. Câu hỏi về thuế, đất đai, hôn nhân gia đình, doanh nghiệp, đầu tư, SHTT
   được trả lời kèm trích dẫn bấm được — không còn nhận `out_of_scope`.
5. Mỗi câu trả lời đóng bằng "⚖️ Thông tin chỉ mang tính tham khảo, không thay
   thế tư vấn của luật sư."
6. Bộ golden 77 câu lao động có số liệu **trước và sau** khi mở kho, chênh lệch
   được ghi lại. Đây là điều kiện phải có, không phải mục phụ.
7. `bạn là ai` và `bạn là gì` trả về **hai** câu trả lời khác nhau. Câu thứ hai
   nói rõ KLAW không phải luật sư, không phải thẩm phán, không phải cơ quan nhà
   nước, và nói được điều một LLM thô không nói được: mỗi trích dẫn đã qua hai
   tầng kiểm.
8. `soạn hộ tôi văn bản nghỉ việc` dựng được biểu mẫu, và tải được `.docx`.
9. Bài năng lực khai đúng **27** loại văn bản soạn được, không phải 3, và con số
   đọc từ `config/checklist_*.yaml` chứ không viết cứng.

## Context

Đo được trên backend đang chạy 2026-09-02 (uvicorn :8000, `POST /api/v1/tra-cuu`):

- `bạn là ai` ≡ `bạn làm được những gì` → cùng `gioi_thieu.NANG_LUC`.
- `model của bạn là gì` **đã** đúng (3 model + vai) — commit `7ff7b6d` sửa rồi.
- Câu nối tiếp **đã** đúng: `cau_hoi_day_du` = "Đưa cho tôi bảng hiển thị 130
  văn bản pháp lý trong kho của KLAW để xem dễ hơn". Không còn lệch nhịp,
  không còn abstain oan.
- Nhưng `answer` của lượt đó vẫn là văn xuôi: ý "bảng" được nhận ở khâu diễn
  nghĩa rồi **bỏ qua** ở khâu dựng câu trả lời.

Authority phải sửa đồng bộ — ba bản sao của cùng một tuyên bố phạm vi:

- `prompts/route.v1.md:1` (dòng "Phạm vi hệ thống: 6 Bộ luật…") và bullet
  `ngoai_pham_vi` liệt kê đúng "(thuế, đất đai, hôn nhân gia đình, doanh nghiệp…)".
- `src/agents/nodes/gioi_thieu.py` hằng `NANG_LUC` ("Mình chưa phủ: thuế, …").
- `docs/bo-luat-agent.md` bảng dòng 3, ví dụ mẫu là "Thuế TNCN tính sao?".

Nạp kho mà không sửa ba chỗ này thì ta trả tiền embed Luật Thuế rồi router vẫn
từ chối câu hỏi về thuế. Đây là phụ thuộc cứng, không phải việc song song.

Nguồn dữ liệu — đường đã verify, KHÔNG dùng firecrawl:

- `data/raw/metadata.parquet` (15 MB, 171.556 văn bản, CC-BY-4.0) đã ở trên máy
  → tra `doc_id` tại local.
- API MOJ `vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{id}` → toàn văn,
  `effStatus`, `references[]`, `provisionTree`. Không auth, không anti-bot.
- `vbpl.vn`, `phapluat.gov.vn`: JS anti-bot 403. `thuvienphapluat.vn`:
  Cloudflare + site thương mại, tầng biên tập KHÔNG thuộc diện miễn bản quyền.
- Nguyên văn QPPL miễn bản quyền theo Luật SHTT Đ15.2 khoản 2 (đã đối chiếu cả
  ba luật sửa đổi 36/2009, 42/2019, 07/2022 — không luật nào chạm Điều 15).

Pipeline đã có: `scripts/fetch_moj.py` → `build_seed.py` → `ingest.py` →
`build_chunks.py`. Kho chỉ có 130 văn bản vì `DOC_IDS` ở `fetch_moj.py:9` là một
dict **21 id viết cứng**, không phải vì giới hạn kỹ thuật.

## Scope

In scope:

- Mở `DOC_IDS` sang 8 lĩnh vực, kèm phép canh id trước khi nạp.
- Sửa ba bản sao tuyên bố phạm vi + authority `docs/bo-luat-agent.md`.
- Tách dạng "là ai" khỏi dạng "làm được gì" trong `gioi_thieu.py`.
- Thêm `bang` vào response và một component bảng ở FE.
- Nhận diện ý "xin dạng bảng" bằng quy tắc 0 token.
- Đổi câu đóng.
- Đo eval trước/sau.

Out of scope:

- Markdown parser ở FE. Bảng đi bằng dữ liệu có kiểu, không bằng chuỗi markdown
  — không mở thêm bề mặt XSS, `van-xuoi.ts` không đụng tới.
- QT-1, QT-2, QT-3, QT-4 trong `docs/bo-luat-agent.md` (dự đoán kết quả, lách
  luật, tiêm lệnh, hỏi lại) — chưa cưỡng chế, và không thuộc việc này.
- Button mới ở FE: hỏi chủ dự án ở P5, chưa chốt nên chưa nằm trong scope.
- `data/content.parquet` (784 MB) và `legacy/` (3,5 GB): không tải. Toàn văn lấy
  từ API, tươi hơn và có `effStatus` tại thời điểm chạy.

## Approach

Bảy nhóm, thứ tự có ý nghĩa. P1 và P2 phải cùng vào MỘT thay đổi — nạp kho
mà chưa đồng bộ tuyên bố phạm vi thì router vẫn từ chối, xem Context.

**P0 — Đo mốc.** Chạy eval golden 77 câu trên kho hiện tại, ghi số vào plan này.
Không có mốc thì "có tụt không" là câu không trả lời được.

**P1 — Mở kho.** Thêm vào `DOC_IDS`: Đất đai `177815`, Nhà ở `169032`, KDBĐS
`169027`, HN&GĐ `36870`, Doanh nghiệp `142881`, Đầu tư `142867`, Thương mại
`26117`, SHTT `16748`, QL Thuế `136036`, Thuế TNCN `187045`, BHXH `175027`,
Tố tụng hành chính `96035`, Xử lý VPHC `27621`.

Mỗi id phải qua **hai** phép canh trước khi nạp, vì đây là lớp sai âm thầm đã
bắt được trong lúc khảo sát: tra `50/2005/QH11` theo số hiệu trả về một **Nghị
quyết**, không phải Luật SHTT — số hiệu trùng nhau giữa các loại văn bản. Nạp
theo id đó sẽ đưa sai văn bản vào kho dưới đúng cái tên, và không test nào đỏ.

- Canh 1: `loai_van_ban` và `title` từ `metadata.parquet` phải khớp văn bản định
  nạp. SHTT = `16748` khớp doc id đã dùng để đối chiếu Điều 15 — mốc độc lập.
- Canh 2: id phải là số. 15.370/171.556 id là UUID hoặc `vbpqta_*`; gateway
  `/doc/{id}` nhận id tuần tự, id phi số không lấy được toàn văn.

Rate-limit lịch sự: thấy HTTP 400 sau ~35 request liên tiếp, nghỉ giữa các lô.

**P2 — Đồng bộ phạm vi.** Sửa `route.v1.md`, `NANG_LUC`, `bo-luat-agent.md`
dòng 3 trong cùng một thay đổi. Danh sách lĩnh vực trong `NANG_LUC` nên đọc từ
DB thay vì viết cứng nếu làm được rẻ; không thì để một hằng duy nhất.

**P3 — Tách dạng "là ai".** `gioi_thieu.py`: thêm `DANH_TINH` + `_RE_LA_AI`,
đặt **sau** `_RE_MODEL`/`_RE_NGUON` (dạng hẹp trước dạng rộng, đúng thứ tự
docstring đang mô tả). `NANG_LUC` vẫn là mặc định an toàn cho câu không khớp
dạng nào. `DANH_TINH` vẫn phải nêu ranh giới — nói được mình làm gì mà không
nói được mình KHÔNG làm gì thì là quảng cáo.

Hai test khóa hành vi cũ, sửa **có chủ đích**, ghi lý do trong test:

- `test_dang_LA_roi_ve_bai_nang_luc_chu_khong_roi_vao_im_lang:164` — khẳng định
  `bạn là ai` == `NANG_LUC`. Đổi: `bạn là ai` → `DANH_TINH`; giữ `""` và
  `bạn hoạt động ra sao` → `NANG_LUC` để mặc định an toàn còn được canh.
- `test_gioi_thieu_tra_loi_thay_vi_tu_choi:39` — dùng `bạn là ai` rồi đòi
  `"thuế" in ans`. Đổi câu hỏi sang dạng năng lực, và thêm test mới:
  `DANH_TINH != NANG_LUC`, `len(DANH_TINH) < len(NANG_LUC)`.
- `DANG` dict trong test thêm khoá `danh_tinh` để
  `test_moi_dang_cau_hoi_cho_MOT_cau_tra_loi_RIENG` phủ dạng mới.

**P4 — Bảng là dữ liệu.** Thêm `bang: Bang | None` vào `TraCuuResponse`
(`{tieu_de, cot: list[str], dong: list[list[str]]}`). `kho.py` dựng bảng từ
chính query đang dùng cho `_tom_tat`, không thêm truy vấn thứ hai. FE thêm
component `<Bang>` bọc trong `overflow-x: auto`.

**P5 — Ý "xin dạng bảng".** Quy tắc 0 token trong `kho.py`, cùng lối
`moi_so_hieu_trong` đang dùng: `bảng|liệt kê|dạng cột|dạng bảng|xem dễ|table`
→ trả `bang` kèm một câu văn xuôi dẫn vào, thay vì bài văn xuôi đầy đủ. Chạy
trên `cau_hoi_day_du` khi có, vì đó là câu đã tự đứng được.

**P6 — Câu đóng + button.** Câu đóng: "⚖️ Thông tin chỉ mang tính tham khảo,
không thay thế tư vấn của luật sư." Button: hỏi chủ dự án trước khi làm.

## Risks And Recovery

- **Mở kho làm tụt precision trên lao động.** Golden 77 câu đều là lao động;
  thêm 13 văn bản lớn làm nhiễu BM25 và dense. Giảm thiểu: P0 đo mốc trước,
  đo lại sau P1, ghi delta vào plan. Nếu tụt quá ngưỡng chấp nhận được thì
  `sweep_bm25.py`/`sweep_fusion.py` đã có sẵn để chỉnh lại trọng số.
- **Mâu thuẫn với phạm vi đề tài đã chốt.** Quyết định 2026-08-27 là "chỉ lao
  động, ~20–40 văn bản", để bảo vệ trước hội đồng. Việc này đổi câu chuyện sang
  "rộng". Chủ dự án đã yêu cầu hai lần và đã được nêu rủi ro. Ghi vào
  `docs/decisions/` để hội đồng thấy đây là lựa chọn có chủ đích, không phải
  phạm vi trôi.
- **Nạp sai văn bản dưới đúng cái tên.** Đã bắt được một lần trong lúc khảo sát
  (`50/2005/QH11` → Nghị quyết). Giảm thiểu: hai phép canh ở P1, và in
  `title` ra để đọc trước khi nạp.
- **Recovery.** `ingest.py` idempotent qua `documents.checksum`; seed vào git.
  Lùi lại = `git checkout` `data/seed/` rồi chạy lại `ingest.py`. Kho hiện tại
  nằm trong git nên không có đường mất dữ liệu.
- **Đổi câu đóng làm đỏ test giọng.** `test_giong_tra_loi.py` và
  `test_re_tat_som.py` canh giọng hệ thống; câu đóng mới có emoji ⚖️ có thể
  vi phạm. Đọc hai file đó trước khi sửa.

## Progress

- [ ] P0 · Đo mốc eval golden 77 câu, ghi số vào mục Validation.
- [ ] P1 · Mở `DOC_IDS` + hai phép canh id + chạy fetch/seed/ingest/chunks.
- [ ] P2 · Đồng bộ ba bản sao tuyên bố phạm vi + authority.
- [ ] P3 · Tách `DANH_TINH` khỏi `NANG_LUC`, sửa hai test có chủ đích.
- [ ] P4 · `bang` trong response + component `<Bang>` ở FE.
- [ ] P5 · Nhận diện ý "xin dạng bảng", 0 token.
- [ ] P6 · Câu đóng; hỏi chủ dự án về button.
- [ ] T6 · checklist `don_xin_nghi_viec` + `LoaiVanBan` + test can_cu tồn tại.
- [ ] Đo lại eval, ghi delta, kết luận có tụt hay không.

## Decisions

- 2026-09-02: Bảng phạm vi khai **8 lĩnh vực kèm nhãn độ sâu đọc từ DB**, không
  khai hẹp theo phần có toàn văn, cũng không copy y nguyên bảng bản Lovable.
  Chủ dự án chọn. Lý do giữ nhãn độ sâu: khai một lĩnh vực không có trong kho
  mà không nói độ sâu thì người hỏi vào đó nhận abstain ngay sau khi vừa được hứa.
- 2026-09-02: Câu đóng dùng **y nguyên câu bản Lovable**. Chủ dự án chọn sau khi
  đã được nêu rằng câu đó nói chung cho cả trích dẫn đã kiểm và trích dẫn bịa,
  nên người đọc không phân biệt được KLAW khác chỗ nào.
- 2026-09-02: **Không dùng firecrawl.** Không phải vì công cụ dở mà vì nguồn:
  hai cổng chính thức chặn bot, nguồn thương mại còn lại có tầng biên tập không
  miễn trừ bản quyền, và pipeline API MOJ đã verify nằm sẵn trong repo. Xem Context.
- 2026-09-02: Bảng đi bằng **dữ liệu có kiểu**, không bằng markdown trong
  `answer`. Đúng nguyên tắc "tra bảng xác định" của đề tài, và tránh nhúng một
  markdown parser vào đường render.

- 2026-09-02: `bạn là ai` (hỏi VAI) và `bạn là gì` (hỏi BẢN CHẤT) là HAI dạng
  riêng. Chủ dự án nêu đích danh hai câu này. Quy tắc tách: `là ai`/`tên gì` →
  `DANH_TINH`; `là gì`/`là cái gì`/`có phải luật sư không` → `BAN_CHAT`.
- 2026-09-02: "Đơn xin nghỉ việc" thêm bằng MỘT checklist YAML, không phải một
  đường soạn thảo mới. `config/` đã có 27 checklist cùng khuôn, và ba nút "Tải
  Word (.docx)" / "Tải PDF" / "Sao chép toàn văn" đã chạy ở
  `frontend/src/routes/soan-thao.$loaiVanBan.tsx:1036-1049` qua
  `frontend/src/lib/xuat-ban.ts` (`docx@9.7.1` + `jspdf@4.2.1` đã cài). Nên câu
  trả lời cho "tải được ko" là: KLAW ĐÃ làm được — thiếu loại văn bản, không
  thiếu nút.
- 2026-09-02: `NANG_LUC` đang khai KLAW ÍT hơn thực tế (3 loại văn bản, thực tế
  27). Sửa cùng chiều với việc sửa tuyên bố phạm vi, và đếm từ `config/` lúc
  chạy — cùng lý do `_model()` tra tên model từ config thay vì viết cứng.
- 2026-09-02: KHÔNG chạy song song hai implementer trên cùng branch (tranh index
  git). Nếu cần song song thật thì dùng `git worktree`. Chọn tuần tự + gộp task,
  vì phần lớn việc mới là tái dùng thứ đã có.
- 2026-09-09: P4 (phần bảng trong câu trả lời pháp luật), P5 (ý "xin dạng bảng")
  và P6 (câu đóng) chuyển sang spec `2026-09-09-bo-nho-tinh-cach-soan-thao` mục 7;
  câu đóng "⚖️ …" KHÔNG đưa vào `answer` (mâu thuẫn `soul` "không viết lời miễn
  trừ"). Plan này còn P0–P3 (mở kho, đồng bộ phạm vi, tách DANH_TINH) và phần bảng
  cho câu hỏi về kho.

## Đối chiếu bản tham chiếu — hai lỗi đã tìm được

Bản Lovable (`~/Downloads/luật`, agent là một lệnh gọi LLM thô qua
`src/lib/ai-gateway.server.ts`, không có kho, không có verifier) được chủ dự án
nêu làm mẫu. Hình thức thì tốt và đã lấy làm mẫu. Nội dung thì đã tra DB và thấy
hai lỗi, cả hai đều thuộc lớp mà tầng kiểm của KLAW tồn tại để chặn:

1. Nó viết "Trưởng phòng … thử việc tối đa 60 ngày theo Khoản 2 Điều 25".
   Khoản 2 nguyên văn là "công việc có chức danh nghề nghiệp cần trình độ chuyên
   môn, kỹ thuật từ cao đẳng trở lên" — 60 ngày phụ thuộc TRÌNH ĐỘ công việc đòi
   hỏi, không phụ thuộc chức danh. Công việc chỉ cần trung cấp rơi vào Khoản 3,
   30 ngày. Nó làm phẳng một điều kiện thành một khẳng định.
2. Nghiêm trọng hơn: mẫu đơn nghỉ việc của nó chỉ nói "phải báo trước 45/30/3
   ngày, không thì bồi thường theo Điều 40", và KHÔNG hề nhắc Điều 35 Khoản 2 —
   bảy trường hợp NLĐ được nghỉ NGAY không cần báo trước, gồm bị nợ lương hoặc
   trả lương không đúng hạn (điểm b), bị ngược đãi/đánh đập/nhục mạ/cưỡng bức
   lao động (điểm c), bị quấy rối tình dục (điểm d), lao động nữ mang thai phải
   nghỉ theo Đ138.1 (điểm đ). Một người đang bị quấy rối đọc mẫu đó sẽ tưởng
   mình phải ở lại 45 ngày. Nó cũng bỏ Điểm d Khoản 1 (ngành nghề đặc thù thì
   thời hạn theo quy định của Chính phủ), tức ba con số kia không phổ quát.

Kết luận đưa vào thiết kế: lấy HÌNH THỨC của bản tham chiếu, kiểm chứng NỘI DUNG.
Mọi `can_cu` trong T6 đã tự tra `provisions` chứ không chép từ bản tham chiếu.

## Validation

- Focused proof: `pytest tests/test_agents/test_gioi_thieu.py` xanh với dạng mới;
  test mới canh `DANH_TINH != NANG_LUC` và canh độ dài; test canh mỗi id trong
  `DOC_IDS` khớp `title`+`loai_van_ban` trong parquet và có id dạng số.
- Integration / end-to-end proof: `POST /api/v1/tra-cuu` trên instance thật cho
  6 câu: `bạn là ai`, `bạn làm được những gì`, `bạn có bao nhiêu văn bản pháp lý`,
  `cho tôi dạng bảng` (kèm `lich_su`), một câu về thuế, một câu về đất đai.
  Kèm ảnh màn hình bảng hiện ra trên FE.
- Repository-required checks: `make check` (ruff + format + pytest),
  `cd frontend && npm run kiem`.
- Eval: golden 77 câu, số trước và sau P1, ghi delta.

## Result

Chưa xong.
