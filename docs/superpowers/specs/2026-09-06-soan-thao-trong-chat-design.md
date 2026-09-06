# Soạn thảo ngay trong chat và card câu trả lời — thiết kế

Ngày: 2026-09-06 · Trạng thái: đã duyệt qua brainstorming, chờ kế hoạch thi công
Tiếp nối: `docs/superpowers/specs/2026-09-06-soul-trich-dan-bam-duoc-design.md`
(sub-project 1; việc này là sub-project 2, bắt đầu SAU khi sub-project 1 qua
review tổng và dọn worktree).

## 1. Vấn đề, đo được

Gõ "bạn giúp tôi soạn thảo văn bản hợp đồng lao động nghỉ việc được ko" vào
`/dung-thu`, hôm nay nhận về `result_type = huong_dan_soan_thao` với một đoạn
cố định bảo người dùng "mở màn Soạn thảo, chọn loại văn bản rồi điền biểu mẫu".
Người dùng phải rời hội thoại, tự tìm đúng loại trong 28 mẫu, rồi điền lại từ
đầu. Câu trả lời cũng nằm trần trên nền trang, không trong card như các sản
phẩm chat quen dùng.

Thứ người dùng muốn: nói câu thường → trợ lý nói đúng loại văn bản và vì sao →
điền dữ kiện ngay tại chỗ → nhận văn bản hoàn chỉnh có căn cứ → tải .docx/.pdf,
tất cả không rời hội thoại.

Thứ KHÔNG làm: để mô hình tự viết văn bản trong chat (bản tham chiếu của người
dùng làm vậy, và nó bịa loại "Thỏa thuận chấm dứt HĐLĐ" rồi tự dẫn Điều 34, 46,
48). Bất biến của KLAW là mọi điều khoản neo vào căn cứ kiểm chứng được; kho
mẫu (`config/checklist_*.yaml`, mỗi mục một `can_cu` tra thẳng `provisions`) là
cách duy nhất giữ lời hứa đó.

## 2. Quyết định đã chốt (chủ dự án, 2026-09-06)

| # | Quyết định | Hệ quả |
|---|---|---|
| Q1 | Mức B: biểu mẫu + bản thảo ngay trong chat, không LLM viết điều khoản | Tái dùng biểu mẫu, xem trước, soát `/soat`, xuất file của `/soan-thao/$loaiVanBan`. |
| Q2 | Router LLM chọn 1 loại + tối đa 2 loại thay thế | Mở rộng schema node `route` (lượt LLM đã có). Loại ngoài kho → nói thẳng chưa có mẫu. |
| Q3 | Thêm mẫu "Thoả thuận chấm dứt hợp đồng lao động" (hai bên) | Một checklist YAML mới, `can_cu` tra DB thật; kho lên 29 loại. |
| Q4 | PA1: khung soạn thảo bên cạnh chat + card gợi ý | Tách thân màn soạn thảo thành component dùng chung; không thiết kế lại biểu mẫu cho bề rộng card. |
| Q5 | Mọi câu trả lời của trợ lý nằm trong card | Sửa một chỗ bọc ở `dung-thu.tsx`; áp cho mọi `result_type`. |

## 3. Hiện trạng liên quan (đã đọc, không suy đoán)

- `route.py`: `INTENT_SCHEMA` strict với `intent ∈ {tra_cuu, soan_thao, ngoai_pham_vi, gioi_thieu, hoi_ve_kho}`; `prompts/route.v1.md`; Settings chưa có khoá chọn prompt cho route.
- `graph_tra_cuu._RE_TAT` đưa `soan_thao` thẳng tới `assemble`; `assemble` trả `_base(state, ResultType.huong_dan_soan_thao, answer=HUONG_DAN_SOAN_THAO)`.
- `graph_soan_thao.cac_loai()` suy tập loại từ `config/checklist_*.yaml` trên đĩa (28 file); `load_checklist_cached(loai).ten` là tên đọc được; `GET /mau/{loai}` trả `facts` + `cau_truc`.
- FE: `/soan-thao/$loaiVanBan` là một route 1.400 dòng; component `KhongGianSoanThao()` đọc `Route.useParams()` và bọc `<AppShell active="/soan-thao">` ở hai chỗ (trạng thái tải và màn chính); biểu mẫu nhiều bước (`Draft {A, B, nd, dk}`), bản xem trước dựng bằng `dungKhung(cauTruc)`, soát qua `POST /soat` (`SoatBanThao`), xuất `.docx/.pdf` từ DOM (`xuatWord`, `xuatPDF` trong `lib/xuat-ban.ts`). FE KHÔNG gọi `POST /soan-thao`.
- `lib/mau-van-ban.ts`: `MAU` (28 slug) và `LOAI_BACKEND: slug → {loai, phamVi}`; `hdld` ánh xạ từ HAI slug (xác định / không xác định thời hạn); `quyet_dinh_ky_luat` là loại backend duy nhất chưa có slug FE.
- `TheKetQua.tsx` chưa có nhánh riêng cho `huong_dan_soan_thao` (rơi vào nhánh văn xuôi mặc định). `dung-thu.tsx::Luot` render phần trả lời trong `<div className="mt-4">` trần; khung phải hiện chỉ có `KhungDoiChieu`, bật theo `useHaiCot()` (≥ 68rem), dưới ngưỡng phủ màn hình.
- Test giọng `tests/test_agents/test_giong_tra_loi.py` quét mã `TheKetQua.tsx` và hằng số của `assemble`/`gioi_thieu`/`hoi_lai`: cấm "hệ thống", "không diễn giải", "chưa đủ căn cứ", "truy hồi", "database", "để bạn tự đối chiếu", "máy chủ trả về".

## 4. Backend

### 4.1 Router — chọn loại văn bản trong cùng lượt gọi

`prompts/route.v2.md`: như v1, thêm chỉ dẫn "khi `soan_thao`, chọn `loai_van_ban`
trong danh sách dưới, nêu `ly_do` một câu, và tối đa hai `thay_the`; không chắc
loại thì `khong_ro`". Danh sách 29 dòng `mã — tên đọc được` được node dựng lúc
gọi từ `cac_loai()` + `load_checklist_cached(loai).ten`, KHÔNG viết tay trong
prompt (thêm checklist là tự có trong danh sách); template mang placeholder
`{danh_sach_loai}`.

Schema strict (mọi khoá `required`, cùng lý do `QUERIES_V2_SCHEMA`):

```python
INTENT_V2_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["intent", "loai_van_ban", "thay_the", "ly_do"],
    "properties": {
        "intent": {"type": "string", "enum": [...5 intent như v1...]},
        "loai_van_ban": {"type": "string", "enum": [*sorted(cac_loai()), "khong_ro"]},
        "thay_the": {"type": "array", "items": {"type": "string", "enum": [*sorted(cac_loai())]}, "maxItems": 2},
        "ly_do": {"type": "string"},
    },
}
```

Chọn template theo nội dung (`"loai_van_ban" in mau`) như `rewrite_query`; khoá
`Settings.route_prompt` mặc định `prompts/route.v1.md`, đổi sang v2 sau khi bẫy
xanh. Với v1 node hành xử y như hôm nay (`soan_thao_goi_y` không được đặt).

Node ghi vào state: `intent` như cũ; khi `intent == soan_thao` và template v2:
`soan_thao_goi_y = {"loai": <mã hoặc None>, "ly_do": ..., "thay_the": [...]}`.
Node route KHÔNG tiêm SOUL (giữ nguyên quyết định sub-project 1).

### 4.2 Assemble — nhánh `soan_thao`, vẫn 0 token

Kiểm 0 token: `loai` phải thuộc `cac_loai()`, `thay_the` lọc còn phần tử thuộc
`cac_loai()` và khác `loai`. Dựng:

```python
soan_thao_goi_y = {
    "loai": "don_xin_nghi_viec",            # None khi khong_ro hoặc loại lạ
    "ten": "Đơn xin nghỉ việc",             # load_checklist_cached(loai).ten
    "ly_do": "...",                          # câu của router, cắt còn 300 ký tự
    "thay_the": [{"loai": "thoa_thuan_cham_dut_hdld", "ten": "Thoả thuận chấm dứt hợp đồng lao động"}],
    "ho_tro": True,                          # False khi loai None
}
```

`answer` mới, xưng "tôi" (Q1 sub-project 1), hai biến thể:

- Có loại: *"Tôi hiểu bạn cần &lt;ten&gt;: &lt;ly_do&gt;. Bạn điền dữ kiện ở khung bên
  cạnh, tôi dựng bản thảo kèm căn cứ cho từng mục, soát lại theo luật trong kho,
  rồi bạn tải .docx hoặc .pdf ngay tại đây."*
- Không loại: *"Kho mẫu của tôi chưa có loại văn bản này. Gần nhất là &lt;tên các
  thay_the&gt; — bạn chọn một loại để tôi mở biểu mẫu."* (không có `thay_the` thì
  câu thứ hai đổi thành mời mô tả rõ hơn văn bản cần soạn).

Khi state không có `soan_thao_goi_y` (route v1), `answer` giữ nguyên
`HUONG_DAN_SOAN_THAO` hôm nay nhưng đổi cụm "mở màn Soạn thảo" thành "bấm Chọn
loại văn bản bên dưới" và `soan_thao_goi_y = None`; FE vẫn hiện nút mở khung với
lưới chọn mẫu. Hằng số mới không chứa cụm bị cấm của test giọng.

### 4.3 Hợp đồng dữ liệu (additive)

```python
class LoaiGoiYOut(BaseModel):
    loai: str
    ten: str

class SoanThaoGoiYOut(BaseModel):
    loai: str | None
    ten: str | None
    ly_do: str
    thay_the: list[LoaiGoiYOut] = []
    ho_tro: bool

class TraCuuResponse(BaseModel):
    ...
    soan_thao: SoanThaoGoiYOut | None = None
```

`KLawState.soan_thao_goi_y: dict | None` (bắt buộc khai — test canh),
`_payload_cache["soan_thao"] = st.get("soan_thao_goi_y")`,
`tra_cuu_response(... soan_thao=payload.get("soan_thao"))`. Cache cũ không có
khoá → `None`.

### 4.4 Mẫu mới — Thoả thuận chấm dứt hợp đồng lao động

`config/checklist_thoa_thuan_cham_dut_hdld.yaml`, `loai: thoa_thuan_cham_dut_hdld`,
`la_hop_dong: true` (hai bên ký). Mục dự kiến, mỗi mục một `can_cu` tra
`provisions.duong_dan` trước khi ghi (chạy đúng phép canh `rong_than` mà
`checklist_don_xin_nghi_viec.yaml` mô tả):

| key | nội dung | căn cứ dự kiến (phải tra DB) |
|---|---|---|
| cac_ben | NSDLĐ và NLĐ | khung hợp đồng chung (BLDS 91/2015/QH13 Điều 385) hoặc mục riêng của checklist |
| hop_dong_cham_dut | số, ngày ký HĐLĐ đang chấm dứt | 45/2019/QH14 > Điều 34 > Khoản 3 |
| ngay_cham_dut | ngày chấm dứt, ngày làm việc cuối | 45/2019/QH14 > Điều 34 > Khoản 3 |
| thanh_toan_14_ngay | hạn thanh toán các khoản song phương | 45/2019/QH14 > Điều 48 > Khoản 1 |
| tro_cap_thoi_viec | điều kiện, mức | 45/2019/QH14 > Điều 46 > Khoản 1 |
| hoan_tra_giay_to | trả bản chính giấy tờ | 45/2019/QH14 > Điều 48 > Khoản 3 > Điểm a |
| bhxh | chốt và trả sổ | điểm phù hợp của Điều 48 Khoản 3 sau khi tra |

Nếu một đường dẫn không tồn tại hoặc rỗng thân trong DB thì bỏ mục đó hoặc hạ
xuống cấp Khoản/Điểm có thân — không bịa. Kèm: `LoaiVanBan` Literal thêm giá
trị; FE `MAU` thêm `thoa-thuan-cham-dut-hop-dong-lao-dong` (nhóm `lao-dong`,
`canCu: [BLLD]`) và `LOAI_BACKEND` ánh xạ `phamVi: "noi_dung"`; `kiem-khung.ts`
đếm `MAU.length` 28 → 29. `tests/test_services/test_moi_mau.py` tự phủ file mới.

## 5. Frontend

### 5.1 Card cho mọi câu trả lời (Q5)

`dung-thu.tsx::Luot`: đổi `<div className="mt-4">{children}</div>` thành
`<div className="mt-4 rounded-xl border border-border bg-card p-5 shadow-soft">`.
Token `--card` và `shadow-soft` đã có trong `styles.css`/DESIGN.md với tương phản
đo sẵn; `TrangThaiCho`, `BaoLoi`, `TheKetQua` đều nằm trong card. Không đổi
`TheKetQua` cho việc này.

### 5.2 Nhánh `huong_dan_soan_thao` — `TheGoiYSoanThao`

Trong `TheKetQua.tsx`, trước nhánh mặc định:

- Văn xuôi `answer` qua `KhoiVanXuoi` như các nhánh khác.
- Nếu `ketQua.soan_thao?.ho_tro`: dòng tên loại đậm, nút chính **"Soạn ngay tại
  đây"** gọi `onSoanThao(slug)`; dưới là chip cho từng `thay_the` (cùng callback).
- Nếu không hỗ trợ hoặc `soan_thao == null`: chỉ chip `thay_the` (nếu có) và một
  nút "Chọn loại văn bản" gọi `onSoanThao(null)` (khung hiện lưới chọn mẫu).
- Ánh xạ: `slugCuaLoai(loai: string): string[]` đảo từ `LOAI_BACKEND` trong
  `lib/mau-van-ban.ts`; `hdld` trả hai slug → hai chip "HĐLĐ xác định thời hạn"
  / "HĐLĐ không xác định thời hạn"; loại không có slug (`quyet_dinh_ky_luat`) →
  rơi về nút "Chọn loại văn bản".
- `TheKetQua` nhận prop mới `onSoanThao?: (slug: string | null) => void`.
- Chuỗi hiển thị xưng "tôi", không cụm bị cấm.

### 5.3 Khung soạn thảo bên phải trong `/dung-thu`

Trạng thái khung phải: `khungPhai: {kieu:"doi_chieu"} | {kieu:"soan_thao"; slug: string | null} | null`
thay cho việc chỉ dựa vào `doiChieu.dang`. Mở khung soạn thảo thì đóng đối
chiếu và ngược lại (một khung một lúc). `inert` trên cột hội thoại và fallback
phủ màn hình dưới 68rem giữ đúng cơ chế hiện có. Khi `kieu === "soan_thao"`,
khung lấy `flex-1 min-w-[640px]` và cột hội thoại co về `max-w-[420px]` vì màn
soạn thảo có hai pane (biểu mẫu + A4 xem trước ở zoom 0,72); dưới 68rem là lớp
phủ toàn màn như `KhungDoiChieu`. Nút đóng ở góc khung.

### 5.4 Tách `KhongGianSoanThao` thành component dùng chung

`frontend/src/components/soan-thao/KhongGianSoanThao.tsx` (di chuyển thân từ
route, không đổi logic): chữ ký
`KhongGianSoanThao({ loaiVanBan, trongKhung = false, onDong }: { loaiVanBan: string | null; trongKhung?: boolean; onDong?: () => void })`.
`trongKhung` bỏ hai lớp `<AppShell>` (thay bằng `<div>`), ẩn liên kết "về
/soan-thao", thêm nút đóng gọi `onDong`. `loaiVanBan === null` (chỉ xảy ra trong
khung chat) render lưới chọn mẫu từ `MAU` nhóm theo `NHOM`; bấm chọn thì đặt
slug và vào biểu mẫu. Route `soan-thao.$loaiVanBan.tsx` còn lại `head`,
`validateSearch` và `component: () => <KhongGianSoanThao loaiVanBan={Route.useParams().loaiVanBan} />`.
Các hàm con (`BenForm`, `DiaChi`, `DieuKhoanRow`, `A4`, `tongTyLe`, `demTrong`…)
đi theo vào file component.

## 6. Kiểm chứng

- `tests/test_agents/test_route.py`: template v2 → parse `loai_van_ban`/`thay_the`/`ly_do`; template v1 → không đặt `soan_thao_goi_y`; enum dựng từ `cac_loai()` (thêm checklist là enum tự dài thêm).
- `tests/test_agents/test_assemble.py`: `soan_thao_goi_y` dựng đúng, loại lạ → `ho_tro=False`, `thay_the` lọc; hằng số mới qua test giọng.
- `tests/test_api/test_tra_cuu.py`: FakeGraph trả `soan_thao_goi_y` → HTTP có `soan_thao`; payload cache cũ → `None`.
- `tests/test_services/test_moi_mau.py` (có sẵn) phủ checklist mới; test integration `can_cu` tồn tại.
- FE: `kiem-khung` 29; `scripts/kiem-goi-y-soan-thao.ts` cho `slugCuaLoai` (hdld → 2 slug, loại lạ → []); typecheck/lint; `npm run build` để chắc route sau tách vẫn dựng.
- Bẫy (`eval/datasets/trap.yaml`, nhóm `soan_thao`): "soạn cho tôi hợp đồng nghỉ việc" → `huong_dan_soan_thao` và `soan_thao.loai ∈ {thoa_thuan_cham_dut_hdld, don_xin_nghi_viec}`; "soạn hợp đồng lao động 12 tháng cho nhân viên kinh doanh" → `hdld`; "viết cho tôi bản kiểm điểm" → `ho_tro=False` hoặc loại hợp lý (đo, không ép). `run_trap.dung()` thêm `ky_vong: soan_thao_loai` với trường `loai_chap_nhan: [...]`.
- Kiểm bằng mắt trên `/dung-thu`: card bao mọi trả lời; hỏi câu ví dụ → card gợi ý → bấm "Soạn ngay tại đây" → khung bên mở biểu mẫu → điền → soát → tải .docx.

## 7. Thi công

Bước 0 trên nhánh: hợp đồng dữ liệu (§4.3), `Settings.route_prompt`, checklist
mới + `LoaiVanBan` + `MAU`/`LOAI_BACKEND`. Bước 1 hai worktree song song: BE
(§4.1, §4.2, bẫy) và FE (§5). Bước 2 gộp, chạy bẫy nhóm `soan_thao` với
`ROUTE_PROMPT=prompts/route.v2.md`, đổi mặc định nếu xanh, chụp màn hình, đóng
plan bền. Không chạy `make check`/`make format` (quy ước từ sub-project 1);
`ruff format --check` chỉ trên dòng mới.

## 8. Rủi ro

| Rủi ro | Dấu hiệu | Cách lùi |
|---|---|---|
| Router chọn sai loại | bẫy `soan_thao` đỏ | giữ `route_prompt` v1; card vẫn có nút "Chọn loại văn bản" |
| Tách component làm vỡ route `/soan-thao` | `npm run build` hoặc typecheck đỏ; `kiem-khung` đỏ | revert commit tách; route cũ giữ nguyên hành vi |
| Khung soạn thảo quá chật cạnh chat | biểu mẫu tràn ở 1088–1280px | co cột chat thêm hoặc phủ toàn màn dưới 80rem |
| `can_cu` mẫu mới không tồn tại | `test_moi_mau` integration đỏ | hạ cấp Khoản/Điểm có thân hoặc bỏ mục |

## 9. Ngoài phạm vi

- Trích dữ kiện từ câu chat tự do (mức C) — vòng sau, cần xác nhận từng dữ kiện.
- Biểu mẫu nằm trọn trong card (PA2) — nâng cấp sau khi component đã tách.
- Lưu hội thoại theo tài khoản (sub-project 3), mở kho HN&GĐ (sub-project 4).
