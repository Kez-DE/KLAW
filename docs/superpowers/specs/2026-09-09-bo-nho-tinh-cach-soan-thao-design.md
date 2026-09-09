# Bộ nhớ hội thoại, tính cách trả lời, soạn thảo hội thoại và không gian làm việc — thiết kế

Ngày: 2026-09-09. Trạng thái: chờ chủ dự án duyệt trước khi viết plan.

Tài liệu này là authority cho năm việc chủ dự án yêu cầu trong phiên brainstorming ngày
09/09: đổi giá và hạn mức; agent nhớ trọn phiên (Pro nhớ xuyên phiên); agent suy luận
câu mơ hồ như ChatGPT và Claude; soạn thảo bằng hội thoại thay cho form tự điền; panel
điều khoản kéo dãn và bản thảo mở thành sân khấu với chatbot nổi. Nó sửa đổi và nối
tiếp ba tài liệu đang hiệu lực:

- `docs/superpowers/specs/2026-09-07-vo-ung-dung-va-tai-khoan-design.md` (hạn mức §4,
  bảng giá) — mục 5 dưới đây ghi đè các con số.
- `docs/superpowers/specs/2026-09-07-lich-su-hoi-thoai-design.md` (phiên do máy chủ
  sở hữu, §5.2) — mục 6 mở rộng phiên thành bộ nhớ ba lớp và hiện thực "bản thảo đã
  lưu" mà §10 của spec đó để lại cho gói 3.
- `docs/bo-luat-agent.md` (QT-1..QT-4) — mục 7 thêm QT-5 và sửa QT-4.

## 1. Mục tiêu (quan sát được trên giao diện thật)

1. Trong một phiên, ở lượt thứ 8 người hỏi nói "vậy tôi được bao nhiêu ngày báo trước"
   và KLAW trả lời theo đúng vai và loại hợp đồng đã nói ở lượt 1, không hỏi lại.
2. Tài khoản Pro mở phiên mới, hỏi "trợ cấp thôi việc của tôi tính sao", KLAW dùng dữ
   kiện đã biết từ phiên trước và ghi rõ "Dựa trên: bạn là người lao động · làm 3 năm".
   Người dùng xem, sửa, xoá từng dữ kiện trong Cá nhân hoá. Free không có bộ nhớ xuyên
   phiên và không thấy mục đó.
3. Câu "tôi sắp nghỉ việc, hãy đưa cho tôi luật để đảm bảo quyền lợi cho tôi, văn bản
   nghỉ việc" nhận câu trả lời ngay ở lượt đầu: một dòng giả định, quyền và nghĩa vụ
   có trích dẫn đã kiểm, phần đuôi hỏi đúng dữ kiện còn làm đổi kết quả, và một nút
   "Soạn đơn xin nghỉ việc". Không còn màn abstain kèm danh sách tám văn bản.
4. "So sánh trợ cấp thôi việc và trợ cấp mất việc" trả về một bảng thật, mỗi ô có
   trích dẫn bấm được.
5. "Tôi cần đơn xin nghỉ việc" → KLAW hỏi một lần các dữ kiện còn thiếu; người dùng
   trả lời tự nhiên; bản thảo hiện trên sân khấu toàn bề rộng, chat thu thành cửa sổ
   nổi; "đổi ngày nghỉ thành 15/10" sửa đúng mục 3 và tạo phiên bản 2; tải .docx/.pdf
   tại chỗ.
6. Panel điều khoản kéo dãn trái phải bằng chuột và bàn phím, nhớ độ rộng. Bấm "Sửa"
   một mục của bản thảo mở drawer bên phải xếp chồng; mục lồng mở drawer thứ hai; Esc
   đóng tấm trên cùng.
7. Bảng giá ghi Cá nhân ₫69.000 / 30 ngày; thanh đo Free ghi 100 lượt/ngày và 30
   lượt/phiên; Pro 500 lượt/ngày, không có trần lượt mỗi phiên.
8. Golden 77 câu lao động có số đo trước và sau; hai bộ đo mới (hội thoại nhiều lượt,
   câu mơ hồ) có số ban đầu ghi trong plan.

## 2. Hiện trạng đo được (2026-09-09, nhánh `feat/tro-ly-phap-luat`)

- Lịch sử vào agent bị cắt ở 3 lượt tại ba chỗ khớp nhau: `LUOT_LICH_SU = 3`
  (`src/services/hoi_thoai.py`), `lich_su: list[LuotTruoc] = Field(max_length=3)`
  (`src/models/schemas.py`), `TOI_DA_LUOT_LICH_SU = 3` (`frontend/src/lib/klaw.ts`).
  Khách chưa đăng nhập giữ 10 lượt trong `sessionStorage` (`frontend/src/lib/khach.ts`)
  nhưng cũng chỉ gửi 3.
- Lịch sử chỉ vào node `giai_nghia` (viết lại câu hỏi cho tự đứng được), không vào
  `rewrite`, `generate`, `assemble`, `hoi_lai`. Dữ kiện kể ở lượt 1 rơi khỏi cửa sổ từ
  lượt 5 nên `hoi_lai` hỏi lại từ đầu. Đây là lỗi "chỉ nhớ đến lượt 3" chủ dự án thấy.
- `config/han_muc.yaml`: free `hoi_dap_ngay 200`, `luot_moi_phien 20`; pro
  `hoi_dap_ngay 100000` với lá chắn `pro_hoi_dap_ngay 500`, `luot_moi_phien 50`. Giá
  `GIA_PRO = 199_000` (`frontend/src/lib/goi.ts`) và `monthly: 199_000`
  (`frontend/src/routes/bang-gia.tsx`).
- Graph tra cứu (`src/agents/graph_tra_cuu.py`): `giai_nghia → route → tien_de →
  rewrite → retrieve → expand → generate → tier1 → tier2 → assemble`; `hoi_lai` được
  `assemble` gọi khi không còn luận điểm nào qua kiểm; sáu chiều dữ kiện hằng số
  (`hoi_lai.CHIEU`) và bộ lọc cấm câu hỏi chứa quy tắc luật.
- Kho có sáu bộ luật; câu lao động kéo cả Tố tụng hình sự, Dân sự vào truy hồi (ảnh
  chủ dự án gửi). `documents.linh_vuc` đã có (migration 018) nhưng truy hồi chưa lọc.
- Soạn thảo trong chat (plan `docs/plans/completed/soan-thao-trong-chat.md`): router v2
  đoán loại văn bản, `assemble` trả `huong_dan_soan_thao` với câu "Bạn điền dữ kiện ở
  khung bên cạnh", frontend mở `KhongGianSoanThao` (1.804 dòng, wizard năm bước) trong
  cột phải `min-w-[640px]`, chat co còn `max-w-[420px]`. Lược đồ trường đã có:
  `FactFieldOut` sinh từ `rules.yaml` (`mo_ta_facts`), `MucMauOut` từ
  `config/checklist_<loai>.yaml` (30 loại).
- `TraCuuResponse.bang: list[Bang]` và `BangKetQua.tsx` đã có cho câu hỏi về kho; câu
  trả lời pháp luật chưa dùng bảng.
- Plan `docs/plans/active/tro-ly-8-linh-vuc.md` chưa làm mục nào; P4/P5 (bảng) và P6
  (câu đóng) trùng với mục 7 và được hấp thụ.

## 3. Quyết định của chủ sản phẩm (phiên 2026-09-09)

| # | Câu hỏi | Quyết định |
|---|---|---|
| 1 | Tách gói | Năm gói trong một spec, một plan năm giai đoạn theo thứ tự giá/hạn mức → bộ nhớ → tính cách → soạn thảo hội thoại → giao diện. |
| 2 | Bộ nhớ Pro xuyên phiên | Hồ sơ tình huống theo tài khoản: dữ kiện về chính người hỏi, chưng cất sau mỗi lượt, xem/sửa/xoá được, có "phiên không ghi nhớ". Không nạp thẳng tóm tắt các phiên cũ, không tra lại phiên cũ ở gói này. |
| 3 | Câu mơ hồ | Làm như ChatGPT và Claude: suy ra điều hiển nhiên, trả lời phần chắc, nêu giả định, chỉ hỏi khi dữ kiện làm đổi kết quả. Ràng buộc riêng của KLAW giữ nguyên: mọi khẳng định luật có trích dẫn đã kiểm. |
| 4 | Bố cục soạn thảo | Bản thảo là sân khấu toàn bề rộng; chatbot là cửa sổ nổi kéo thả, thu thành bong bóng; sửa từng mục bằng drawer xếp chồng kiểu Payload (mẫu ở `~/VF_TTS/vsf-cms-multiple-sites-backend`, Payload 4 canary dùng `DocumentDrawer` và `useEditDepth`). |
| 5 | Bảng so sánh | Bảng là dữ liệu có kiểu (`Bang`), không phải markdown trong `answer` — giữ quyết định 2026-09-02 của plan 8 lĩnh vực. |
| 6 | Nghiên cứu | Chủ dự án yêu cầu khảo sát thêm bằng firecrawl và tìm kiếm trước khi chốt; kết quả ở mục 4 và các chỗ ghi "(theo …)". |

## 4. Khảo sát: các trợ lý lớn làm thế nào, và KLAW lấy gì

Khảo sát ngày 09/09 bằng firecrawl (bốn lần đầu lỗi, sau chạy được), WebFetch và
WebSearch. Chỉ ghi điều đã đọc được từ nguồn gốc.

**Bộ nhớ.** ChatGPT có hai lớp: *saved memories* (người dùng bảo nhớ, xem và xoá được) và
*chat history* (tổng hợp liên tục từ các phiên cũ, rộng hơn những gì liệt kê được);
người dùng tắt từng lớp; *Temporary Chat* không đọc không ghi bộ nhớ; xoá một phiên
không xoá memory đã rút từ nó (help.openai.com/en/articles/8590148-memory-faq;
openai.com/index/memory-and-new-controls-for-chatgpt). Claude nhớ bằng **một bản tóm
tắt tổng hợp**, tách riêng theo dự án, xem và sửa trong Settings, có chat ẩn danh
(claude.com/blog/memory). Mem0 (lớp bộ nhớ mã nguồn mở) chốt ba nguyên tắc: lưu **dữ
kiện đã trích**, không lưu nguyên văn hội thoại; tra cứu bộ nhớ liên quan trước khi ghi
để gộp trùng; luôn lọc theo `user_id`/`run_id` để bộ nhớ hai người không lẫn; và
"tránh lưu bí mật, thông tin nhạy cảm chưa che" (docs.mem0.ai/core-concepts/how-it-works).
LangGraph tách **ngắn hạn** theo thread (state + checkpointer) và **dài hạn** trong
store theo namespace; `SummarizationMiddleware(model, trigger=("tokens", N),
keep=("messages", M))` tóm tắt phần cũ và giữ M tin nhắn gần nhất nguyên văn;
`trim_messages` chỉ cắt; ghi bộ nhớ ở hot path hoặc chạy nền
(docs.langchain.com/oss/python/langgraph/memory và …/langchain/short-term-memory).

KLAW lấy: ngắn hạn = K lượt nguyên văn + tóm tắt cuộn (đúng hình `keep` + summary);
dài hạn = **hồ sơ có khoá cố định** theo tài khoản, xem/sửa được (Claude), có công tắc
theo phiên và theo tài khoản (Temporary Chat); ghi **chạy nền** sau mỗi lượt; gộp
trùng theo khoá với quy tắc "mới đè cũ" và giữ nguồn (Mem0 khuyên có đường sửa/xoá
tường minh thay vì để hai bản mâu thuẫn sống chung). Điểm khác biệt của đề tài giữ
nguyên: bộ nhớ chỉ chứa **dữ kiện về người hỏi**, không chứa quy tắc luật, không dùng
để chống đỡ khẳng định nào; hai tầng kiểm trích dẫn không đổi.

**Câu mơ hồ.** OpenAI Model Spec (bản 2026-08-18): "If the user's intent is unclear, the
assistant should provide a robust answer or a safe guess if it can, stating assumptions
and asking clarifying questions as appropriate" và "assume users have goals and
preferences similar to an average, reasonable human being, avoiding unnecessary or
trivial clarifying questions" (model-spec.openai.com/2026-08-18.html). Hiến pháp của
Claude: "always try to identify the most plausible interpretation", "ask for
clarification in cases of genuine ambiguity", và liệt kê "asks clarifying questions
more than necessary" là lỗi cần tránh (anthropic.com/constitution). KLAW lấy nguyên
ba ý này thành QT-5 (mục 7.1), cộng ràng buộc riêng: giả định phải hiện ra thành chữ
và sửa được một chạm.

**Thu thập dữ kiện bằng hội thoại.** Tutorial "information gathering" của LangGraph
chạy hai pha: pha gom hỏi cho tới khi model **gọi một structured output** đủ trường
(`PromptInstructions`), pha sau mới sinh; điều kiện chuyển pha là chính lời gọi có cấu
trúc đó, không phải cờ riêng (langchain-ai/langgraph, examples/chatbots/
information-gather-prompting). KLAW dùng đúng khuôn: `gom_du_kien` trả JSON theo lược
đồ trường của loại văn bản kèm `du: bool`; `du = true` là tín hiệu dựng bản thảo.

**Tài liệu là sân khấu, chat bên cạnh.** OpenAI Canvas: cửa sổ riêng bên cạnh chat;
người dùng **chọn vùng** để chỉ đạo sửa có đích, không chọn thì model viết lại cả bài;
có nút lùi phiên bản và "Show changes"; menu phím tắt (Suggest edits, Adjust length,
Add final polish) (openai.com/index/introducing-canvas). Teardown Claude Artifacts:
thẻ bàn giao trong luồng chat trước khi mở pane ("card is a handoff, not the
workspace"), pane chia đôi để chat và sản phẩm cùng hiện, **chế độ toàn bề rộng che
mất chat** là chi phí phải bù, và "mobile likely needs a full-screen artifact mode";
đừng mở pane cho câu trả lời vừa một đoạn (aiuxplayground.com/teardowns/claude/
artifacts). KLAW lấy: thẻ "Bản thảo đã sẵn sàng" trong chat trước khi chuyển sân khấu;
chat nổi để bù việc sân khấu che chat (quyết định #4); sửa có đích theo mục khi người
dùng chọn mục, viết lại cả bản khi lệnh nói chung; lịch sử phiên bản có tô khác biệt;
ba phím tắt cho văn bản pháp lý; mobile toàn màn có tab.

**Kéo dãn có tiếp cận.** W3C APG Window Splitter: `role="separator"` có tiêu điểm,
`aria-valuenow/min/max` theo kích cỡ pane chính, `aria-orientation`, nhãn bằng
`aria-label`; phím ← → di chuyển, **Enter** thu gọn pane chính hoặc khôi phục, Home/End
về nhỏ nhất/lớn nhất, F6 xoay vòng giữa các pane (w3.org/WAI/ARIA/apg/patterns/
windowsplitter). KLAW làm đúng bảng phím này cho panel điều khoản và cho vách ngăn
danh sách mục / xem trước trong sân khấu.

## 5. Gói 1 — Giá và hạn mức

Chỉ đổi dữ liệu và copy; không đổi cơ chế đếm (`traces`, múi giờ, quy ước 0 và ≥ 100000).

| Khoá | Cũ | Mới |
|---|---|---|
| `goi.free.hoi_dap_ngay` | 200 | **100** |
| `goi.free.luot_moi_phien` | 20 | **30** |
| `goi.pro.hoi_dap_ngay` | 100000 | **500** |
| `goi.pro.luot_moi_phien` | 50 | **100000** (không giới hạn) |
| `la_chan.pro_hoi_dap_ngay` | 500 | **bỏ khoá** (đã là hạn mức thật; `bao_ve` không đọc nữa) |
| `la_chan.free_hoi_dap_thang` | 2000 | **3000** (100 × 30, để trần tháng không đứng dưới hạn mức ngày) |
| `la_chan.ip_ngay` | 1500 | 1500 (giữ, vẫn = 3 × 500) |
| `GIA_PRO` / `monthly` | 199.000 | **69.000** |

Tệp: `config/han_muc.yaml`; `src/services/bao_ve.py` (gỡ nhánh đọc `pro_hoi_dap_ngay`,
sửa `NHAN_MUC` nếu có nhãn "không giới hạn" cho pro); `frontend/src/lib/goi.ts`
(`GIA_PRO`, hai mảng `danhSach`: "100 lượt hỏi đáp mỗi ngày", "30 lượt mỗi phiên";
"500 lượt hỏi đáp mỗi ngày", "Không giới hạn lượt mỗi phiên", "Trí nhớ hoàn cảnh xuyên
phiên" bỏ chữ "(sắp có)" khi gói 2 xong, bỏ dấu sao); `frontend/src/routes/bang-gia.tsx`
(`monthly`, câu "₫69.000 / 30 ngày"); thẻ hết hạn Pro trên `/dung-thu` ("Gia hạn 30
ngày để tiếp tục hỏi 500 lượt mỗi ngày và soạn 20 bản thảo"). Spec 2026-09-07 nhận
thêm mục "Sửa 2026-09-09" trỏ về đây.

Hành vi khi chạm trần lượt/phiên (Free 30): giữ `LOI_PHIEN_DAY` và nút "Mở phiên mới"
hiện có. Pro không có thông điệp trần phiên; độ dài phiên được kiểm soát bằng cửa sổ
bộ nhớ ở mục 6, không bằng trần.

Kiểm: `tests/test_api/test_han_muc_yaml.py`, `test_han_muc_ngay.py`, `test_han_muc_dua.py`
cập nhật số; `frontend/scripts/kiem-han-muc.ts` 5/5; ảnh chụp `/bang-gia` và thanh đo.

## 6. Gói 2 — Bộ nhớ phiên và bộ nhớ tài khoản

### 6.1 Ba lớp của một phiên

Mọi tài khoản đăng nhập (Free và Pro):

1. **Lượt gần nhất nguyên văn**: `K = 6` lượt cuối, mỗi lượt `{cau_hoi, tra_loi[:1200],
   duong_dan[:50]}` (nới `TRA_LOI_TOI_DA` 2000 → 1200 để 6 lượt vẫn gọn).
2. **Tóm tắt cuộn** `hoi_thoai.tom_tat` (≤ 1.200 ký tự) cho các lượt cũ hơn K, kèm
   `hoi_thoai.tom_tat_den_thu_tu`. Tóm tắt luôn viết lại toàn bộ (không nối chuỗi).
3. **Hồ sơ tình huống** `hoi_thoai.ho_so` JSONB, khoá cố định, giá trị ≤ 120 ký tự,
   kèm nguồn:

```json
{
  "chu_the":       {"gia_tri": "người lao động", "nguon": "suy_dien"},
  "loai_hop_dong": {"gia_tri": "không xác định thời hạn", "nguon": "nguoi_noi"},
  "tham_nien":     {"gia_tri": "3 năm", "nguon": "tai_khoan"},
  "vung_luong": {}, "thoi_diem": {}, "van_ban_da_co": {},
  "vu_viec":       {"gia_tri": "sắp nghỉ việc, muốn biết quyền lợi và soạn đơn", "nguon": "nguoi_noi"}
}
```

Sáu khoá đầu trùng đúng `hoi_lai.CHIEU`; `vu_viec` là một câu về việc đang theo.
`nguon`: `suy_dien` (giả định do mục 7 tạo, giao diện ghi là giả định), `nguoi_noi`
(người dùng nói), `tai_khoan` (kế thừa từ bộ nhớ tài khoản). Người dùng sửa thì nguồn
thành `nguoi_noi` và đè mọi nguồn khác.

### 6.2 Cập nhật chạy nền

Sau `hoi_thoai.ghi_luot` thành công, `routes.py` xếp một `BackgroundTasks` gọi
`src/services/bo_nho.py::cap_nhat_phien(hoi_thoai_id)`:

- Đọc `tom_tat` cũ, các lượt từ `tom_tat_den_thu_tu + 1` tới `thu_tu_moi - K`, `ho_so`
  cũ và lượt vừa ghi.
- Một lời gọi LLM (cùng model và cấu hình `giai_nghia` đang dùng, JSON schema strict)
  trả `{tom_tat, ho_so}`. Prompt mới `prompts/bo_nho.v1.md` được tiêm `soul`, dặn rõ:
  chỉ dữ kiện **bền** về hoàn cảnh (không lấy câu tạm thời kiểu "hôm nay tôi bận",
  theo bài học Mem0 về hiểu sai câu nhất thời thành dữ kiện lâu dài); không định danh
  cá nhân; không quy tắc luật.
- Lưới chặn 0 token trước khi ghi: giá trị chứa số Điều/Khoản/số hiệu văn bản (regex
  dùng lại của `hoi_lai`), hoặc chuỗi 9–12 chữ số liên tiếp (giấy tờ, tài khoản), hoặc
  dạng email/số điện thoại, thì bỏ và giữ giá trị cũ.
- Lỗi LLM hay DB: ghi log, giữ nguyên bản cũ; câu trả lời của lượt không phụ thuộc.
- Chi phí: ~1,5k token vào, ~300 ra, model rẻ; ghi `traces` với `endpoint =
  '/api/v1/bo-nho'` (không tính hạn mức: `han_muc.yaml` chỉ đếm `/tra-cuu` và
  `/soan-thao`).
- Công tắc vận hành `KLAW_BO_NHO_NEN` (mặc định bật); tắt thì agent chỉ có K lượt.

### 6.3 Bộ nhớ đi vào agent ở đâu

`routes._gan_phien` nạp ba lớp vào state: `lich_su` (K lượt), `tom_tat`, `ho_so`.

- `giai_nghia`: thêm `tom_tat` vào khối ngữ cảnh; `dinh_danh_bia` đối chiếu với đúng
  khối đã đưa vào prompt (như nay).
- `rewrite`: nhận `ho_so` để truy vấn mang đúng vai và loại hợp đồng.
- `generate` và `assemble`: nhận khối **"Tình huống của người hỏi"** dựng từ `ho_so`
  (gạch đầu dòng, đánh dấu giả định) qua placeholder mới `{tinh_huong}`. Khối này là
  DỮ LIỆU theo mục "An toàn và bí mật" của `soul`; luận điểm vẫn phải trích điều khoản
  trong `{context}` và qua `tier1`/`tier2` không đổi.
- `hoi_lai`: bỏ chiều đã có giá trị trong `ho_so` (bất kể nguồn).

`KLawState` thêm `tom_tat: str | None`, `ho_so: dict`, `ho_so_da_dung: list[str]`.

### 6.4 Bộ nhớ tài khoản (chỉ Pro)

Bảng mới `ho_so_tai_khoan(user_sub UUID REFERENCES users ON DELETE CASCADE, khoa TEXT,
gia_tri TEXT, nguon_hoi_thoai_id UUID, cap_nhat_luc TIMESTAMPTZ, PRIMARY KEY
(user_sub, khoa))`, cùng bộ khoá với `ho_so`. Cột `users.ghi_nho BOOLEAN NOT NULL
DEFAULT true`, `hoi_thoai.khong_ghi_nho BOOLEAN NOT NULL DEFAULT false`.

- Tạo phiên mới của tài khoản có gói hiệu lực `pro` và `users.ghi_nho = true`: nạp
  `ho_so_tai_khoan` vào `hoi_thoai.ho_so` với `nguon = tai_khoan`.
- Sau mỗi `cap_nhat_phien` của phiên Pro không đánh `khong_ghi_nho`: gộp `ho_so` vào
  `ho_so_tai_khoan` theo khoá, mới đè cũ, giữ `nguon_hoi_thoai_id` và `cap_nhat_luc`.
  Không giữ hai giá trị mâu thuẫn cho một khoá; người dùng thấy giá trị hiện hành và
  sửa/xoá tường minh (khuyến nghị của Mem0).
- Gói hết hạn về Free: dừng đọc và ghi, **không xoá** (nâng lại thì có ngay); xoá tài
  khoản thì cascade.
- Free: không đọc, không ghi bảng này; giao diện không hiện mục bộ nhớ.

API (`src/api/routes_tai_khoan.py`, xác thực bắt buộc; Free trả 403 với thông điệp
nâng cấp):

- `GET /api/v1/tai-khoan/bo-nho` → `{ghi_nho, muc: [{khoa, nhan, gia_tri,
  cap_nhat_luc, nguon_hoi_thoai_id}]}`.
- `PATCH /api/v1/tai-khoan/bo-nho/{khoa}` body `{gia_tri}` (≤ 120 ký tự, qua lưới chặn).
- `DELETE /api/v1/tai-khoan/bo-nho/{khoa}`; `DELETE /api/v1/tai-khoan/bo-nho` (xoá hết).
- `PATCH /api/v1/tai-khoan/bo-nho/cai-dat` body `{ghi_nho: bool}`.
- `PATCH /api/v1/hoi-thoai/{id}` nhận thêm `khong_ghi_nho: bool` (mọi gói).
- `PATCH /api/v1/hoi-thoai/{id}/ho-so` body `{khoa, gia_tri | null}` sửa hồ sơ phiên từ
  dòng "Dựa trên" (mọi gói; `null` = xoá khoá).

### 6.5 Khách chưa đăng nhập

Không có phiên máy chủ nên không có tóm tắt hay hồ sơ. Client gửi tối đa **10** lượt
(`max_length=10`, `TOI_DA_LUOT_LICH_SU = 10`, khớp `khach.ts` đang giữ 10). Khách chỉ
có 10 lượt/24 giờ nên 10 lượt nguyên văn là đủ và có trần rõ.

### 6.6 Giao diện

- `TraCuuResponse.ho_so_da_dung: list[HoSoDaDungOut] = []` với `{khoa, nhan, gia_tri,
  gia_dinh: bool}`. `TheKetQua` hiện dòng nhỏ "Dựa trên: bạn là người lao động · hợp
  đồng không xác định thời hạn" (giả định in nghiêng kèm chữ "tôi đoán"), nút "Sửa" mở
  popover gọi `PATCH /hoi-thoai/{id}/ho-so`.
- Cá nhân hoá (`routes/tai-khoan.ca-nhan-hoa.tsx`) thêm thẻ "KLAW nhớ về bạn" (chỉ
  Pro): công tắc chung, bảng khoá/giá trị sửa tại chỗ, xoá từng dòng, "Xoá tất cả" có
  xác nhận, dòng giải thích "Chỉ dữ kiện về hoàn cảnh của bạn; không bao giờ lưu giấy
  tờ, số tài khoản, địa chỉ".
- Menu "…" của phiên thêm "Không ghi nhớ phiên này" (cả hai gói), giống Temporary Chat.

### 6.7 Kiểm

- Đơn vị: cửa sổ K và mốc `tom_tat_den_thu_tu`; gộp hồ sơ theo khoá và nguồn; lưới
  chặn loại số Điều, chuỗi 9–12 chữ số, email, số điện thoại; `hoi_lai` bỏ chiều đã có.
- API: Free 403 ở mọi endpoint bộ nhớ tài khoản và không có dòng nào được ghi; Pro ghi
  và đọc; `khong_ghi_nho` chặn cả tóm tắt và gộp; xoá tài khoản cascade; hai tài khoản
  không đọc được bộ nhớ của nhau.
- Graph: fixture phiên 8 lượt; lượt 8 hỏi "tôi được báo trước bao nhiêu ngày" phải ra
  luận điểm Điều 35 khớp loại hợp đồng đã nói ở lượt 1 và `hoi_lai` không hỏi
  `chu_the`/`loai_hop_dong`.
- Eval mới `eval/datasets/hoi_thoai_nhieu_luot.yaml`: 10 hội thoại × 5–8 lượt, mỗi lượt
  cuối có tập dữ kiện phải được dùng; chỉ số "tỷ lệ lượt dùng đúng dữ kiện đã nói".
  Golden 77 chạy lại trước/sau, không được tụt.

## 7. Gói 3 — Tính cách trả lời

### 7.1 Authority: QT-5 và sửa QT-4 trong `docs/bo-luat-agent.md`

**QT-5 — Suy ra điều hiển nhiên, nêu giả định, hỏi chỉ khi đổi kết quả.** Khi câu hỏi
tự nó cho biết dữ kiện (ngôi thứ nhất + "nghỉ việc/bị sa thải/bị trừ lương" ⇒ người
lao động; "nhân viên của tôi/công ty tôi" ⇒ người sử dụng lao động), agent mặc định theo
cách hiểu đó, ghi rõ giả định một dòng, trả lời phần chắc, và chỉ hỏi thêm ở cuối những
dữ kiện làm đổi kết quả. Hỏi lại **trước** khi trả lời chỉ khi hai cách hiểu dẫn tới hai
câu trả lời trái nhau. Cơ sở: Model Spec của OpenAI ("robust answer or a safe guess …
stating assumptions", "avoiding unnecessary or trivial clarifying questions") và Hiến
pháp của Claude ("most plausible interpretation", "clarification in cases of genuine
ambiguity"). QT-4 sửa thành: "Thiếu dữ kiện quyết định kết quả thì trả lời theo nhánh
phổ biến nhất có nêu giả định, rồi hỏi đúng dữ kiện đó" — nay đã có trạng thái hội
thoại để lượt sau dùng câu trả lời.

### 7.2 `prompts/soul.v2.md`

Đổi ba câu, giữ mọi thứ khác:

- "Thiếu dữ kiện thì nói rõ kết quả phụ thuộc dữ kiện nào ... thay vì chọn bừa một
  nhánh" → "Thiếu dữ kiện thì chọn nhánh hiển nhiên hoặc phổ biến nhất, nói rõ bạn
  đang giả định gì, trả lời phần chắc, rồi nêu kết quả còn phụ thuộc dữ kiện nào."
- Thêm vào GIỌNG: "Trả lời trước, giải thích sau: ba câu đầu phải là câu trả lời. Khi
  người hỏi xin so sánh, đối chiếu hay liệt kê theo tiêu chí, trả về bảng theo hợp
  đồng đầu ra của bước đó."
- HỢP ĐỒNG ĐẦU RA: "không bảng" → "bảng chỉ đi bằng trường `bang` có kiểu, không vẽ
  bảng bằng ký tự".

### 7.3 Suy diễn 0 token và vị trí mới của `hoi_lai`

- Node mới `suy_dien` (thuần Python, sau `giai_nghia`/lượt đầu, trước `route`): từ
  `cau_hoi_day_du` và `ho_so`, điền `chu_the` khi trống bằng bảng mẫu ngôi thứ
  nhất/thứ ba (regex có test bảng), `nguon = suy_dien`. Không gọi LLM.
- `assemble` khi **có** luận điểm qua kiểm: mở bằng dòng giả định (nếu có khoá
  `suy_dien` được dùng), rồi nội dung, rồi đuôi "Để chính xác hơn" với tối đa **hai**
  câu hỏi từ `hoi_lai` cho chiều còn trống. `hoi_lai` chỉ thay câu trả lời (abstain kèm
  câu hỏi) khi không còn luận điểm nào.
- Kết quả `abstain` không liệt kê danh sách văn bản "khớp từ ngữ" nữa; thay bằng một
  câu "Tôi chưa tìm được điều khoản trả lời chắc" và tối đa hai câu hỏi.

### 7.4 Router v3 và truy hồi khoanh vùng

`prompts/route.v3.md` + `schema_v3`: thêm `linh_vuc` (enum đọc từ `SELECT DISTINCT
linh_vuc FROM documents` lúc gọi, cộng `khong_ro`), `dang_tra_loi: van_xuoi | bang`,
và `y_dinh_phu: soan_thao | null` với `loai_van_ban` như v2. `retrieve` lọc
`documents.linh_vuc = :linh_vuc` khi router trả một lĩnh vực; `khong_ro` giữ toàn kho;
lọc ra dưới 3 kết quả thì tự mở lại toàn kho (trace `retrieve_mo_rong = true`). Khi
`y_dinh_phu = soan_thao` và loại có checklist, `TraCuuResponse.soan_thao` được điền
cùng câu trả lời để `TheKetQua` gắn nút "Soạn {ten}" mở luồng ở mục 8.

### 7.5 Bảng từ luận điểm

Khi `dang_tra_loi = bang` (quy tắc 0 token của plan 8 lĩnh vực chạy trên
`cau_hoi_day_du`, router chỉ xác nhận): `generate` sinh luận điểm kèm `hang:
{doi_tuong, tieu_chi}` tuỳ chọn; `assemble` dựng `Bang{tieu_de, cot, dong}` từ các luận
điểm **đã qua tier1/tier2**, mỗi ô kèm mã trích dẫn, và một đoạn dẫn ngắn. Hấp thụ
P4/P5 của plan 8 lĩnh vực (dùng lại `BangKetQua.tsx`, cuộn ngang trong thẻ). Plan đó
ghi "P4/P5/P6 chuyển sang gói 4" trong Decisions.

### 7.6 `prompts/assemble.v3.md`

Trả lời trước trong tối đa ba câu; gạch đầu dòng sau; không lặp lại câu hỏi; không câu
đóng miễn trừ (giao diện đã có). Câu đóng "⚖️ …" của plan 8 lĩnh vực **không** thêm vào
`answer` (mâu thuẫn `soul` "không viết lời miễn trừ").

### 7.7 Kiểm và đo

- Test bảng mẫu `suy_dien` (≥ 20 câu, cả trường hợp không được suy: "công ty tôi có
  được sa thải nhân viên…" ⇒ người sử dụng lao động).
- `test_giong_tra_loi.py`, `test_re_tat_som.py` sửa có chủ đích theo soul v2.
- Eval mới `eval/datasets/mo_ho.yaml`: 20 câu mơ hồ có chủ đích; kỳ vọng `result_type
  ∈ {answer, partial_coverage}` và `ho_so_da_dung` chứa khoá suy diễn đúng; tỷ lệ
  abstain oan là chỉ số chính; tỷ lệ gán sai vai là chỉ số phụ.
- Golden 77 trước/sau; precision trích dẫn không được tụt.

## 8. Gói 4 — Soạn thảo hội thoại

### 8.1 Trạng thái soạn thảo sống trong phiên

`hoi_thoai.soan_thao JSONB`: `{loai, facts: {khoa: gia_tri}, ban_thao_id, so_lan_sua}`.
Mỗi lượt là một lần chạy graph mới nên trạng thái phải nằm ở phiên, không ở RAM.

### 8.2 Luồng

1. `route` v3 trả `soan_thao` + `loai_van_ban` hoặc `y_dinh_phu`. Với
   `soan_thao_dang_mo` trong phiên, router nhận thêm ngữ cảnh "đang soạn {ten}" để
   phân biệt **trả lời dữ kiện**, **sửa bản thảo** và **hỏi luật** giữa chừng (`tra_cuu`
   vẫn đi đường tra cứu, không phá phiên soạn).
2. Node mới `gom_du_kien` (LLM, JSON strict, schema dựng lúc gọi từ `FactFieldOut`:
   khoá cố định, `lua_chon` thành enum, cộng `du: bool`): trích dữ kiện từ câu hiện
   tại + `ho_so` phiên + bộ nhớ tài khoản; gộp vào `soan_thao.facts`; `du` chỉ được
   `true` khi mọi trường bắt buộc có giá trị (kiểm lại bằng Python, không tin model).
3. Chưa đủ: `assemble` trả `result_type = soan_thao_hoi`, `soan_thao_hoi: {loai, ten,
   da_co, con_thieu: [FactFieldOut], chip: {khoa: [gia_tri…]}}`; `answer` hỏi **một
   lần** tối đa sáu trường, có ví dụ; giao diện hiện chip cho trường có `lua_chon`.
   Người dùng nói "cứ soạn" → trường thiếu để `[…]` và audit báo thiếu.
4. Đủ: node `dung_ban_thao` gọi `graph_soan_thao` với `facts` (đúng pipeline
   `/soan-thao`: draft → clauses → audit), ghi `ban_thao`, trả `result_type =
   ban_thao`, `ban_thao: {id, loai, ten, phien_ban, document, clauses, audit_report,
   facts, doi_so_voi_truoc: [khoa_muc]}`. Chat hiện **thẻ bàn giao** "Bản thảo đã sẵn
   sàng · Mở" (theo teardown Artifacts) rồi giao diện chuyển sân khấu.
5. Sửa bằng lời: `gom_du_kien` với `ban_thao_id` có sẵn → khoá đổi → `dung_ban_thao`
   dựng lại, `phien_ban + 1`, `doi_so_voi_truoc` liệt kê mục đổi để giao diện tô.
   Lệnh nói chung ("trang trọng hơn") → viết lại cả bản; lệnh khi người dùng đang chọn
   một mục trong sân khấu → chỉ mục đó (khuôn Canvas "chọn vùng thì sửa có đích").
   Trần `so_lan_sua = 10` mỗi bản; vượt thì mời mở bản mới.

### 8.3 Dữ liệu

Bảng mới `ban_thao(id UUID PK, user_sub UUID REFERENCES users ON DELETE CASCADE,
hoi_thoai_id UUID REFERENCES hoi_thoai ON DELETE SET NULL, loai TEXT, facts JSONB,
document TEXT, clauses JSONB, audit JSONB, phien_ban INT, phien_ban_truoc JSONB,
tao_luc, cap_nhat_luc)`, index `(user_sub, cap_nhat_luc DESC)`. `phien_ban_truoc` giữ
tối đa 10 bản trước `{phien_ban, document, facts}` để lùi phiên bản. Đây là "bản thảo
đã lưu" của spec lịch sử hội thoại §10. `GET /api/v1/ban-thao`, `GET /api/v1/ban-thao/
{id}`, `POST /api/v1/ban-thao/{id}/lui` (về phiên bản trước), `DELETE` mềm — dùng cho
mục "Bản thảo" trong Gần đây.

### 8.4 Hạn mức

Lần `dung_ban_thao` đầu của một `ban_thao_id` ghi trace `endpoint = '/api/v1/soan-thao'`
(được `han_muc.yaml` đếm); lần sửa ghi `endpoint = '/api/v1/soan-thao/sua'` (không đếm).
Hết hạn mức soạn thảo: `soan_thao_hoi` vẫn hỏi được dữ kiện nhưng `dung_ban_thao` trả
429 nói thật với mốc mở lại.

### 8.5 Kiểm

- Đơn vị: schema `gom_du_kien` dựng đúng từ `FactFieldOut` cho cả 30 loại; `du` bị
  Python phủ quyết khi thiếu trường bắt buộc; gộp và `con_thieu`; trần sửa.
- API/graph: "tôi cần đơn xin nghỉ việc" → hỏi → trả lời tự nhiên → `ban_thao` có
  `document` chứa ngày đã nói; "đổi ngày nghỉ thành 15/10" → `phien_ban = 2`,
  `doi_so_voi_truoc = ["ngay_du_kien_nghi"]`; câu hỏi luật xen giữa không xoá
  `soan_thao` của phiên; `lui` trả về phiên bản 1.
- Free hết 3 bản thảo/ngày → 429 đúng thông điệp; đếm không tăng khi sửa.

## 9. Gói 5 — Không gian làm việc

Không thêm thư viện; kéo thả và kéo dãn bằng pointer events; token thiết kế từ
`DESIGN.md` của frontend.

### 9.1 Tay kéo dùng chung — `TayKeo`

Một component theo W3C Window Splitter: `role="separator"`, `aria-orientation=
"vertical"`, `aria-label`, `aria-controls` trỏ pane chính, `aria-valuenow/min/max` theo
phần trăm; ← → chỉnh 24 px, Shift+mũi tên 96 px, **Enter** thu gọn pane chính về nhỏ
nhất hoặc khôi phục, Home/End về biên; pointer capture khi kéo; mọi giá trị đi qua một
hàm kẹp duy nhất rồi ghi cả `flex-basis` và `aria-valuenow` cùng lúc. Dùng cho 9.2 và 9.3.

### 9.2 Panel điều khoản kéo dãn — `KhungDoiChieu`

`TayKeo` ở mép trái panel. Biên: 320 px đến 60% bề rộng; chat không xuống dưới 480 px;
mặc định 420 px; lưu `localStorage["klaw.doi-chieu.rong"]`. Dưới 68rem giữ tấm trượt
toàn màn như nay.

### 9.3 Sân khấu bản thảo — `SanKhauBanThao`

Khi lượt trả về `ban_thao` và người dùng bấm thẻ bàn giao (hoặc mở lại từ Gần đây):
`/dung-thu` chuyển bố cục toàn bề rộng gồm thanh tiêu đề (tên văn bản, chọn phiên bản
với "Hiện thay đổi", Tải Word/PDF, Đóng), cột trái danh sách mục (`MucMauOut`, trạng
thái đủ/thiếu, nút "Sửa"), `TayKeo` ở giữa, cột phải xem trước A4 cập nhật sống (tách
từ `KhongGianSoanThao` thành `XemTruocA4` và `xuatTep`). Ba phím tắt cho văn bản pháp
lý ở thanh công cụ: "Rút gọn", "Trang trọng hơn", "Soát lại theo luật" (chạy audit
hiện có). Bấm chọn một mục trong xem trước đánh dấu mục đó là đích cho lệnh sửa tiếp
theo trong chat. Đóng sân khấu về lại chat; bản thảo vẫn ở Gần đây.

### 9.4 Cửa sổ trợ lý nổi — `CuaSoTroLy`

Chat thu thành cửa sổ 380 × 520 px ở góc phải dưới: kéo thanh tiêu đề để di chuyển,
kéo góc để đổi cỡ (tối thiểu 320 × 400), nút thu thành bong bóng 56 px có chấm số lượt
chưa đọc, nút "Về hai cột" trả chat ra toàn màn cạnh sân khấu. Vị trí và cỡ lưu
`localStorage["klaw.cua-so-tro-ly"]`, kẹp trong viewport khi resize. Stream và hạn mức
y như chat thường; tin "Đã sửa Mục 3 ✓ · phiên bản 2" hiện trong cửa sổ.

### 9.5 Drawer xếp chồng — `NganXepDrawer`

Bấm "Sửa" một mục mở drawer bên phải (480 px, nền mờ, khoá tiêu điểm, đóng bằng
Esc/nút/bấm nền, trả tiêu điểm về nút mở). Nội dung: các trường `FactFieldOut` liên
quan mục đó, căn cứ của mục (`can_cu`, bấm mở điều khoản trong cùng drawer), Huỷ/Lưu.
Lưu gọi `dung_ban_thao` với facts mới (cùng đường sửa bằng lời, tính vào trần sửa). Mục
có danh sách con mở drawer thứ hai chồng lên, lệch 24 px, breadcrumb "Mục 10 › Khoản
2"; Esc đóng tấm trên cùng; tối đa ba tầng (`useEditDepth` của Payload là mẫu). Trên
điện thoại drawer thành tấm trượt toàn màn.

### 9.6 Màn hẹp

Dưới 68rem: sân khấu toàn màn với thanh tab dưới cùng "Bản thảo | Trợ lý"; không có cửa
sổ nổi; tab Trợ lý là chat toàn màn; drawer thành tấm trượt toàn màn.

### 9.7 Kiểm

- Đơn vị (vitest): hàm kẹp của `TayKeo` và đồng bộ `aria-valuenow`; reducer kẹp vị
  trí/cỡ cửa sổ; ngăn xếp drawer (mở/đóng/Esc/tầng tối đa/trả tiêu điểm).
- Ảnh chụp Chrome ở 1440 và 390: panel kéo dãn (chuột và bàn phím), sân khấu + cửa sổ
  nổi + drawer hai tầng, chọn phiên bản có tô thay đổi, tab mobile.

## 10. Thứ tự, phụ thuộc và tiêu chí xong

| Gói | Phụ thuộc | Xong khi |
|---|---|---|
| 1 Giá/hạn mức | — | Test hạn mức xanh với số mới; `/bang-gia` và thanh đo hiện số mới; spec 2026-09-07 có mục sửa. |
| 2 Bộ nhớ | 1 (trần phiên Pro bỏ) | Migration 023; test graph 8 lượt xanh; endpoint bộ nhớ có test gating; Cá nhân hoá hiện thẻ cho Pro; eval nhiều lượt có số ban đầu. |
| 3 Tính cách | 2 (`ho_so`) | QT-5 ghi; soul v2, route v3, assemble v3; câu "tôi sắp nghỉ việc" ra answer kèm giả định trên giao diện thật; golden 77 không tụt; eval mơ hồ có số. |
| 4 Soạn thảo hội thoại | 2, 3 | Migration 024; hội thoại end-to-end dựng, sửa và lùi phiên bản đơn xin nghỉ việc; hạn mức đếm đúng. |
| 5 Không gian làm việc | 4 (`ban_thao`) | Ảnh chụp bốn trạng thái; test reducer; đi hết drawer bằng bàn phím. |

Mỗi gói là một loạt commit tự đứng được; plan sẽ chia nhỏ theo TDD.

## 11. Rủi ro và cách lùi

- **Chi phí**: thêm một lời gọi nền rẻ mỗi lượt (ước 15–25% chi phí lượt). Lùi:
  `KLAW_BO_NHO_NEN=0`.
- **Sai giả định**: `suy_dien` gán sai vai. Giảm: dòng giả định luôn hiện và sửa được
  một chạm; eval mơ hồ đo tỷ lệ gán sai; bảng mẫu chỉ bắt ngôi thứ nhất rõ ràng.
- **Bộ nhớ chứa quy tắc luật hoặc dữ liệu định danh**: lưới chặn 0 token trước khi
  ghi, test âm cho từng mẫu; giá trị ≤ 120 ký tự; prompt chỉ lấy dữ kiện bền.
- **Rò bộ nhớ giữa tài khoản hoặc từ Pro sang Free**: mọi truy vấn lọc `user_sub`;
  test API khẳng định Free không có dòng nào; cascade khi xoá tài khoản.
- **Câu chuyện đồ án**: từ "hỏi lại" sang "giả định có kiểm soát" — ghi vào
  `docs/decisions/` với hai bộ eval mới làm bằng chứng, trích Model Spec và Hiến pháp
  Claude làm cơ sở so sánh.
- **Kích cỡ `KhongGianSoanThao`** (1.804 dòng): chỉ tách phần render/xuất, không viết
  lại wizard; route `/soan-thao/$loai` giữ nguyên hành vi.
- **Lùi toàn bộ**: mọi cột mới có mặc định, `TraCuuResponse` chỉ thêm trường mặc định
  rỗng, payload cache cũ vẫn tuần tự hoá; frontend đọc trường mới theo kiểu tuỳ chọn.

## 12. Ngoài phạm vi gói này

- Tra lại nội dung phiên cũ theo ngữ nghĩa (embedding lịch sử) — quyết định #2.
- Nhiều worker uvicorn: tác vụ nền và `_TRUC_TUYEN` vẫn theo tiến trình.
- Thanh toán thật cho gói 69.000đ; vẫn là yêu cầu nâng gói do admin duyệt.
- Mở kho sang 8 lĩnh vực (P1/P2) và bảng cho câu hỏi về kho (P4 phần kho): plan đó
  tiếp tục riêng, chỉ P4 phần trả lời/P5/P6 chuyển sang đây.
- Markdown trong `answer`, thư viện kéo thả, trình soạn thảo rich-text trong drawer,
  gợi ý sửa dạng "track changes" trong xem trước.

## 13. Câu hỏi đã chốt (để không hỏi lại)

- K = 6 lượt nguyên văn, tóm tắt ≤ 1.200 ký tự, hồ sơ 7 khoá × ≤ 120 ký tự; đổi bằng
  hằng số trong `bo_nho.py`, không phải YAML (tham số kỹ thuật, không phải chính sách gói).
- Bộ nhớ tài khoản tối đa 7 khoá (không phải danh sách tự do) — đơn giản, xem/sửa
  được, khớp `hoi_lai.CHIEU`.
- Sửa bản thảo tính trần 10 lần/bản và giữ 10 phiên bản trước; không tính hạn mức ngày.
- Cửa sổ nổi chỉ ở màn ≥ 68rem; màn hẹp dùng tab.
- Câu đóng "⚖️ …" không đưa vào `answer`.
- Thẻ bàn giao trong chat luôn đi trước khi chuyển sân khấu; không tự bật sân khấu cho
  câu trả lời tra cứu.
