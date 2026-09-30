# Design: every draft is a real .docx built from a khuôn mẫu (wave D1)

Date: 2026-09-29

## Status

Design, revised after review round 1 (10 findings; resolutions in §9). Nothing is
implemented yet. Waves D3 (khuôn mẫu data) and D4 (engine) code against §1–§8.
**Gate:** Open owner decision 3 (page cap) must be answered before D4c. D4a, D4b
and D3 may start now.

## Outcome

1. A chat request such as "soạn hợp đồng thuê tài sản giữa tôi Nguyễn Văn A và …"
   yields a draft whose pages are a real `.docx` rendered by LibreOffice:
   - A4 and margins per NĐ 30/2020 Phụ lục I.
   - Header: quốc hiệu, tiêu ngữ, số, địa danh và ngày, placed where the type's
     form puts them.
   - Tên loại and trích yếu.
   - Căn cứ from the kho, with full number and date.
   - Party blocks and numbered Điều, or the fixed sections of an official đơn.
   - A signature block in the form's column order.
   - Nơi nhận, when the type has one.

   Values the user did not give are "……" blanks.
2. That draft behaves exactly like a draft on an uploaded khuôn gốc:
   - The stage opens.
   - Blanks are clicked and filled on the page.
   - Every save is a version, and Lùi walks back.
   - The Word and PDF downloads are the same file as the pages.
3. Chat requests make a new version of the same draft. Examples: "sửa điều 3 …",
   "thêm điều về phạt vi phạm", "điền tên bên B là …". None of these ever reaches
   a page or a download: a ⟦n⟧ marker, a template token, a `[…]`, or a
   model-written `[Tên Bên A]`.
4. Every clause that has a căn cứ opens it from the stage, in the existing đối
   chiếu drawer. Every căn cứ line of the frame opens its document (§5, decision
   item 3).
5. Types: the 29 checklist types plus new types (decision item 8). Each comes from
   one registry file that records its source: an official form URL and SHA-256,
   or "built to Phụ lục I".

## Context

Authority:

- Decision `docs/decisions/2026-09-29-the-thuc-moi-ban-thao.md` items 1–8
  (Accepted; items 5–8 are this wave).
- Decision `2026-09-26-luu-khuon-goc-va-dien-tai-cho.md` and plan
  `docs/plans/completed/khuon-goc-dien-tai-cho.md`: the engine and its contracts.
- Decision `2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`: the căn cứ block,
  and the visibility rule in `src/services/hien_thi.py`.
- `CONTEXT.md`: khuôn mẫu, khuôn gốc, thể thức, bản thảo tổng quát, căn cứ, kho.
- The `_re_sau_route` docstring: the router verdict is the only authority on
  whether a turn drafts. Session state must not override it.

Research, all read in full (session scratchpad):

- T1, `tt/`:
  - `the-thuc.md`: NĐ 30 Điều 8 and the Phụ lục I rules, quoted from Công báo
    283+284.
  - `mau-hien-co.md`: the 29 checklists.
  - `hop-dong.md`: contract clauses, and the NĐ 96/2024 Phụ lục II layout.
  - `nen-tang.md` and `dinh-tuyen.md`: waves F1/F2.
- D2, `tt/mau-that/index.{md,json}`: the official files with SHA-256, their
  LibreOffice renders, and per-form layout notes.
- 2026-09-29, `pdftotext -layout` of the two official Mẫu 23-DS files:
  - toaan `goc/m23-ds_toaan-TAND279888.pdf`, SHA-256 `6881d9dd…`;
  - its `.doc` twin, rendered to `pdf/m23-ds_toaan-TAND279887.pdf`.

  Both give one party order: người khởi kiện → người bị kiện → người có quyền,
  lợi ích được bảo vệ → người có quyền lợi, nghĩa vụ liên quan. That is the order
  §7 uses.

What the engine already gives (read end to end, 2026-09-29):

- **Storage** keys on `viec_doc_tai_lieu.id`:
  - `khuon_goc` (036) holds the bytes.
  - `viec_doc_tai_lieu.don_vi` holds the reader's units with `dia_chi`,
    `cho_trong` and `doan_chu`.
  - `ban_thao.viec_id`/`phep_sua` (037) say which file and which ops a version
    is.
  - `ban_thao._SQL_KHUON`/`_SQL_KHUON_DAY` join the two. Every route goes
    through them: `/ban-thao/{id}/trang`, `/o-dien`, `/tai-xuong`, `/lui`,
    `/phien-ban/{n}`.
- **Versions** carry their own `(viec_id, phep_sua)`:
  - `_snap` stores both, `sua` writes the ket's pair, and `lui` restores the
    snapshot's pair.
  - `khuon_cua_phien_ban` reads the version's `viec_id`.

  So consecutive versions may sit on different files with no engine change.
- **Blank detector** (`doc_tai_lieu._cho_trong_doan`):

  | Kind | What it matches |
  |---|---|
  | `cham` | A maximal run that `RE_CHO_DIEN` (`…\|[._–—-]{3,}`) accepts. One `…` is enough. |
  | `tab` | The n-th `w:tab` of a paragraph, when the n-th stop declared DIRECTLY in its `w:pPr/w:tabs` has `w:leader="dot"`. |
  | `o` | An empty cell of a BORDERED body table, under a named column. |

  Units are body `w:p`, body-table `w:tc`, and header/footer paragraphs. A
  text-less paragraph is not a unit. Paragraphs that hold fields, text boxes or
  `mc:AlternateContent` carry no blanks (fail closed).
- **The value net** (`hieu_tai_lieu._RE_GIA_TRI`) turns every digit run or e-mail
  that is not in the turn's sources into `[…]`. The block net
  (`bo_nho._vuong_luoi_chan`) catches:
  - `Điều|Khoản|Điểm|Đ` followed by a number;
  - a document number;
  - a run of 9–12 digits, an `@`, or a phone number.

  `lam_sach_van_ban` drops a whole mục on a net hit.
- **Today's HTML draft path:**
  1. `hieu_tai_lieu` (`soan_tu_do`) writes `van_ban`.
  2. `lam_sach_van_ban` cleans it.
  3. `dung_ban_thao_tong_quat.ket_ban_thao` saves it.
  4. `ban_thao._render_markdown` renders it.
  5. `XemTruocA4` shows it, and `xuat-tep.ts` exports it from the browser.

  The stage already switches on `khuon !== null` (`SanKhauBanThao.tsx:844`). It
  hides the mục column, the căn cứ toggle and `DrawerSuaMuc` for such drafts,
  which is why §5 adds a căn cứ surface.
- **Căn cứ lines:** `graph_soan_thao.can_cu_van_ban` →
  `trich_dan.khoi_can_cu`/`dong_can_cu`. Only visible, in-force documents are
  listed, and NĐ 30 is excluded as a thể thức-only source. Checklist clauses
  carry `can_cu_provision_id` (`DraftClause`); `db_provisions` maps it to
  `document_id` (`ban_thao._duong_dan_index`).

## §1 Template format: blanks, page setup, fidelity to official forms

**No template file with markers.** A khuôn mẫu is a registry entry (§7) plus the
builder (§2). The builder writes the clauses straight into the document it
generates. No slot token exists in any stored or downloaded file, so there is
nothing to strip.

**Rebuild, including forms LibreOffice renders faithfully.** D2 §3 found faithful
LibreOffice renders for Mẫu 23-DS, NĐ 124 Mẫu 01, NĐ 145 Mẫu 01/PLV, NĐ 96
Phụ lục II and TT 5/2023 Phụ lục I. We still rebuild those forms rather than ship
the official file as a khuôn gốc, for three reasons:

1. The official files carry parts that are not the filed document (D2 §4.1): the
   annex caption with its rule, footnote callouts (1)…(16), and the guidance page.
2. Their blanks are literal dot runs. The khuôn gốc rules let only user-word
   `dien` ops touch them, so the model-written sections (yêu cầu, nội dung khiếu
   nại, Điều) would have no place.
3. The court's Mẫu 23-DS is set in Arial, but the MOJ copy of the same form and
   NĐ 30 use Times New Roman (D2 §4.8). That rendition choice is Open owner
   decision 7.

Fidelity is instead a tested contract:

- same labels, verbatim;
- same order;
- same alignment of Kính gửi, date line and signature column;
- page geometry within Phụ lục I.

`test_khuon_mau_registry.py` checks the recorded label lists (§7).
`test_khuon_mau_trang.py` and wave V check the page images against D2's official
PNGs. The upgrade path (ship `config/khuon_mau/<loai>.docx` as a khuôn gốc)
stays open only if wave V shows a rebuilt form cannot match its official PNG.

**Blanks, so the existing detector finds them unchanged:**

| Where | Written as | Detector kind | Label the page shows |
|---|---|---|---|
| Whole-line field (catalog line "Họ và tên:", or an official line "Người khởi kiện:") | Label run, then one `w:tab`. The paragraph's own `w:pPr/w:tabs` declares a right stop at text width with `w:leader="dot"`. | `tab` | Text before the tab |
| Two fields on one line ("Số điện thoại: …(nếu có); số fax: …(nếu có)") | Two tabs to two direct stops (≈45 % and ≈90 % of text width), both with dot leaders; the static text between them stays verbatim | `tab` ×2 | Text before each tab |
| Inline parts: `Số: ……/HĐ-……`, `……, ngày …… tháng …… năm ……`, "tại ……", "Kính gửi: Toà án nhân dân ……", blanks inside clause text | "……" (two U+2026) in its own run, paragraph formatting | `cham` | Text before ("Số", "ngày", "tháng", "năm"; a leading place blank reads "Chỗ trống") |
| Signature name line (types whose form has one) | A paragraph "……" under the signer label | `cham` | "Chỗ trống" (value copied from the party's `ho_ten`, §2) |
| Data tables (phiếu đánh giá, danh mục), only for types that need one | Bordered table, header row with column names, empty body cells | `o` | "<column> (dòng n)" |

Rules the builder keeps, so the reader and the applier accept every blank:

- Never put a blank in a paragraph with a field, a text box or a drawing.
- A "." right after a "……" is preceded by U+2060 WORD JOINER (`khuon_mau.NOI`). The
  reader joins every `.`/`…` run into one blank ("……." — right for uploaded forms), so
  without it the sentence's period is lost on fill ("Theo đề nghị của …….", "Lưu: VT,
  ……." — both end with "." per Phụ lục I, Công báo 283+284 tr. 25, 30).
- Header and signature tables are borderless (`w:tblBorders` all `none`, no table
  style). They are never data tables and yield no `o` blanks.
- "……" is the ONLY blank the builder writes. Model text is normalised before the
  build (§6), so no other `…`, `...`, `___` or `---` run reaches a clause and
  becomes a stray `cham` blank.
- Unknown values are never filled: no date, place or number of KLAW's own
  (decision item 2).

**Page setup (Phụ lục I, quoted in `the-thuc.md` §3):**

- A4 portrait (`w:pgSz` 11906×16838).
- Margins: top 20 mm (1134), bottom 20 mm (1134), left 30 mm (1701), right 15 mm
  (851). Toaan's Mẫu 23-DS uses 20/20/30/20, which is inside the range; an entry
  may carry its form's margins.
- Times New Roman, which the server renders as the metric-compatible Liberation
  Serif.
- Page number centred in the top margin, size 14, not on page 1: `w:titlePg`, a
  default header with one `w:fldSimple w:instr="PAGE"`, and no first-page header.

One size set serves the whole document ("tăng, giảm phải thống nhất"), using the
upper bound of each range:

| Element | Size and style |
|---|---|
| Quốc hiệu | 13, bold, upper case |
| Tiêu ngữ | 14, bold. "Độc lập - Tự do - Hạnh phúc", with U+002D |
| Tên cơ quan | 13, bold |
| "Số:" | 13 |
| Địa danh và ngày | 14, italic |
| Tên loại | 14, bold, upper case |
| Trích yếu | 14, bold |
| Căn cứ | 14, italic. ";" ends each line, "." ends the last |
| Body | 14, justified, first-line indent 1.27 cm, 6 pt after, line spacing 1.15 |
| Quyền hạn/chức vụ ký | 14, bold, upper case |
| Họ tên ký | 14, bold |
| "Nơi nhận:" | 12, bold italic. Items 11 |

If D4 measures the quốc hiệu wrapping in its column, the whole set drops to the
lower bounds. Strings are the official ones, e.g. "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT
NAM" (Ò is U+00D2).

The rules under tiêu ngữ and tên cơ quan are empty paragraphs with a bottom
border, and an empty paragraph is not a unit. Their symmetric indents give the
text's length for tiêu ngữ (a fixed string), or one third of the cell for tên cơ
quan.

## §2 Builder

**Choice: the repo's `lxml` OOXML path, no python-docx.**

- `lxml` is already in `requirements.txt`, and `dien_khuon.py` already writes
  OOXML with it.
- The builder needs exactly the parts python-docx has no API for: table and
  paragraph borders, `w:titlePg`, `fldSimple`, and direct tab stops per
  paragraph. It would drop to raw XML anyway.
- python-docx's default template brings Calibri theme fonts and its own core
  properties to override.
- A new dependency would mean installing into the shared `.venv`.

The builder writes these parts, zipped by `zipfile` with fixed timestamps, so the
same spec gives the same bytes:

- `[Content_Types].xml` and `_rels/.rels`;
- `word/document.xml`;
- `word/styles.xml`, with `w:docDefaults` Times New Roman 14 / `vi-VN`;
- `word/settings.xml`, with `w:compatSetting compatibilityMode=15` so Word does
  not open it in compatibility mode;
- `word/header1.xml` and its rels.

**Signature:**

```python
dung_docx(spec) -> tuple[bytes, dict[tuple[str, tuple[int, ...]], list[tuple[str, str]]]]
```

It lives in `src/services/khuon_mau.py` and is pure: no DB, no model, no
LibreOffice. The map is `(part, chi_muc)` → the `(ben, truong)` of each field
blank of that unit, in reading order. That is exactly the reader's `dia_chi`, and
§3 turns it into `dien` ops.

**`spec`** is validated in §6:

```
{loai | None, bo_cuc, the_thuc, tieu_de, trich_yeu,
 can_cu: [{dong, doc_id}], ben: [...], than: [...],
 dieu: [{key, ten, doan: [str], can_cu}], ky: {...}, noi_nhan: [...] | None}
```

`the_thuc` and `than` are the §7 registry fields; tổng quát turns get a
`the_thuc` from the `bo_cuc` defaults.

**Three layouts, one set of pieces** (`bo_cuc` of the registry entry). The
positions that vary by form are `the_thuc` parameters, never hard-coded:

- `ngay`: `dau` (centred under tiêu ngữ), `cot_phai` (right column, same row as
  Số), `cuoi` (end, right, above the signer) or `khong`.
- `kinh_gui`: `{dong, can}`, the verbatim line with its slot, and `can` `giua`
  (centred) or `thut` (indented 30 mm).
- `ky.thu_tu`: column order.
- `dong_mau`: an optional form caption.

The three layouts:

- **`hanh_chinh`** (NĐ 30 sơ đồ, CB p.33). A borderless 2×2 header table, split
  38 % / 62 % (D2 §4.2):
  - Row 1: tên cơ quan chủ quản (optional, not bold), TÊN CƠ QUAN (bold) and a
    rule | quốc hiệu, tiêu ngữ and a rule.
  - Row 2: `Số: ……/<ký hiệu>-……` (+ "V/v …" for công văn) | `……, ngày …… tháng
    …… năm ……` when `ngay: cot_phai`.

  Then, in order:
  1. tên loại, trích yếu and a rule (not for công văn);
  2. "Kính gửi:", when `kinh_gui` is set;
  3. the căn cứ lines;
  4. "Theo đề nghị của …….", the last căn cứ line, and the "QUYẾT ĐỊNH:" line, for
     quyết định;
  5. the body, with "./." after its last paragraph (the Phụ lục III model layout,
     not a quoted rule); the paragraph before the signature block keeps with it
     (`keepNext` + `keepLines`), so a page never holds only Nơi nhận and signature;
  6. a borderless signature table: the "Nơi nhận:" list on the left | QUYỀN HẠN,
     CHỨC VỤ / (Chữ ký, dấu) / name blank on the right.

  Flags cover the Phụ lục III variants:
  - biên bản: no top date; THƯ KÝ | CHỦ TỌA; Nơi nhận below both blocks (D2 §4.4);
  - văn bản kèm theo: no Số and no date; "(Kèm theo Quyết định số …/QĐ-… ngày …
    tháng … năm … của …)"; no signature. It is its own section: new page, page
    numbers restart at 1, first page unnumbered (Phụ lục I, Phần I mục 7; Phần III
    mục 1.đ by analogy). Số, ký hiệu, ngày ban hành, thẩm quyền and trích yếu are
    `van_ban` fields, so one value fills the decision and the "(Kèm theo …)" line.
- **`don`** (Mẫu 23-DS, NĐ 124 Mẫu 01, Mẫu 01-VDS):
  - centred quốc hiệu and tiêu ngữ; no cơ quan and no Số;
  - the date line per `ngay`, then TÊN ĐƠN;
  - "Kính gửi: …" per `kinh_gui`;
  - the ordered `than` list: party blocks, fixed sections labelled in the form's
    own words, static lines;
  - the signature per `ky`, in the form's own wording.

  An official đơn has no "Điều n." numbering. The model's clauses fill the
  `than` sections by key (§6).
- **`hop_dong`** (NĐ 96/2024 Phụ lục II, `hop-dong.md` §4, D2 §4.9):
  1. centred quốc hiệu and tiêu ngữ;
  2. the date line centred ABOVE the title, when `ngay: dau`;
  3. TÊN HỢP ĐỒNG;
  4. `Số: ……/……`, centred;
  5. căn cứ;
  6. "Hôm nay, ngày …… tháng …… năm ……, tại ……, chúng tôi gồm:";
  7. party blocks "I. BÊN … (sau đây gọi là Bên A):" with their field lines;
  8. "Hai bên thống nhất ký kết … với các điều khoản sau:";
  9. the Điều list;
  10. the closing "Hợp đồng này được lập thành …… bản, …";
  11. a borderless two-column signature table in `ky.thu_tu` order: ĐẠI DIỆN
      BÊN A | ĐẠI DIỆN BÊN B, with "(Ký, ghi rõ họ tên)", or "…, chức vụ và
      đóng dấu" for organisations.

**Code builds the frame; the model writes only clauses (item 7).** Everything
except the clause text comes from code and data:

- quốc hiệu, tiêu ngữ, số, the date line;
- tên loại: registry `tieu_de`, or for tổng quát the model's title upper-cased;
- căn cứ;
- party labels and field lines;
- the fixed đơn sections;
- Điều numbering: an "Điều n." bold heading, then the model's `ten`, with any
  number the model wrote already stripped (§6);
- the closing and the signature.

Căn cứ comes from one function in every case:

- Registry types with a checklist call `graph_soan_thao.can_cu_van_ban` on
  `requirements(loai)`.
- Registry types without one list `can_cu: [duong_dan]` in the entry, and use the
  same function.
- Tổng quát turns may name `can_cu: [so_ky_hieu]`. Code resolves these against
  `documents`, through the same visibility and in-force filter (`khoi_can_cu`).
  Unresolved numbers print nothing.

`can_cu_van_ban` gains a sibling, `can_cu_van_ban_co_id`, which returns
`[{dong, doc_id}]` with the same filter and order. `can_cu_van_ban` becomes a
comprehension over it, so the stage can link each line (§5).

The signature name blank gets the party's `ho_ten` value when the user gave one.

## §3 Storage

**Reuse `viec_doc_tai_lieu` + `khuon_goc`, one additive column.** A built draft
is stored like an upload:

- One `viec_doc_tai_lieu` row:
  - `nguon = 'khuon_mau'`, `trang_thai 'xong'`, `ten_tep` "<Tên loại>.docx";
  - `loai` = the registry id, or NULL for tổng quát;
  - `don_vi` from running the existing reader `doc_tai_lieu.doc` on the built
    bytes;
  - `so_trang` from one LibreOffice render via `dung_trang.khuon_goc`.
- One `khuon_goc` row, `dinh_dang 'docx'`.
- `ban_thao.viec_id` pointing at it.

Every route, the applier, the probe, the page cap and the per-account render slot
work unchanged, because they only see a viec with a khuôn gốc.

Migration `041_viec_doc_nguon.sql`. On 2026-09-29, 041 was checked free on every
local branch and on every worktree:

```sql
ALTER TABLE viec_doc_tai_lieu ADD COLUMN IF NOT EXISTS nguon TEXT NOT NULL DEFAULT 'tai_len'
    CONSTRAINT ck_viec_doc_nguon CHECK (nguon IN ('tai_len', 'khuon_mau'));
```

- It is idempotent in the style of 040 (inline CHECK, `IF NOT EXISTS`).
- The constant default needs no table rewrite (Postgres 11+), and the CHECK
  validates a small table once.
- It is appended to `src/main.py::MIGRATIONS_KHOI_DONG`, and is applied only in
  the Integrate stage.

The column exists because three readers must not see a khuôn mẫu as a user's
tài liệu. Each gains `AND nguon = 'tai_len'`:

- `tai_lieu.tai_lieu_cua_hoi_thoai`: chat chips, `tai_lieu_phien`, and the router's
  `{tai_lieu_trong_phien}`;
- the document Q&A path;
- `tai_lieu.da_dung_hom_nay`: the daily document quota.

`ban_thao._SQL_KHUON`/`_SQL_KHUON_DAY` return `v.nguon`, so `khuon` gains
`"nguon"`. `BanThaoOut.khuon` is an untyped dict (`src/models/schemas.py:237`),
so there is no schema change.

Rejected:

- A sibling table keyed on `ban_thao`: every `_SQL_KHUON*`, `_VIEC_CUA_CHU`,
  snapshot, lookup and route would need a second branch.
- A column on `khuon_goc`: the listing and quota filters read
  `viec_doc_tai_lieu`.

**Three draft kinds, three lookups.** Kinds never share a lookup, so the retained
HTML path can never write over a khuôn mẫu draft (review finding 2):

| Kind | Live version's `viec_id` | Found by |
|---|---|---|
| HTML (legacy, image, pre-036) | NULL | `moi_nhat_cua_hoi_thoai(viec_id=None)` → `viec_id IS NULL`, unchanged |
| Khuôn gốc | The upload's viec (`nguon 'tai_len'`) | `moi_nhat_cua_hoi_thoai(viec_id=<upload>)`, unchanged |
| Khuôn mẫu | The newest built viec (`nguon 'khuon_mau'`); changes on every rebuild | New `ban_thao.moi_nhat_khuon_mau(sub, hoi_thoai_id)`, see below |

`moi_nhat_khuon_mau` runs `_SQL_MOI_NHAT_KHUON_MAU`: the `_SQL_MOI_NHAT` columns,
`loai = 'tong_quat'`, and
`EXISTS (SELECT 1 FROM viec_doc_tai_lieu v WHERE v.id = ban_thao.viec_id AND v.user_sub = ban_thao.user_sub AND v.nguon = 'khuon_mau')`.

The predicates of `_SQL_MOI_NHAT` and `_SQL_MOI_NHAT_NHE` do not change.
`_SQL_MOI_NHAT_NHE` gains a `LEFT JOIN viec_doc_tai_lieu v ON v.id =
ban_thao.viec_id` that returns two columns: `v.nguon` and `v.loai AS loai_khuon`.
That lets `routes._chuan_bi_phien`'s every-turn light row tell the three kinds
apart with no extra query.

`_SQL_MOI_NHAT_KHUON` (the view shortcut, and `GET /tai-lieu/{id}/ban-thao`)
drops its `loai = :loai` filter. "Cho tôi xem bản thảo" then also finds checklist
drafts that sit on a khuôn mẫu. Uploads only ever carry tổng quát drafts, so the
per-upload route is unaffected.

**Content edits rebuild; fills are ops.**

- **Rebuild.** A chat edit that changes clause text builds a NEW docx from the
  updated spec and stores a new viec. The new version points at it.
- **Carrying fills** is done by `ban_thao.mang_phep_sang(don_vi_cu, don_vi_moi,
  phep_cu)`:
  - It runs `difflib.SequenceMatcher` over the two lists of `(clause, text)`
    pairs. The builder tags every clause paragraph with its clause
    (`khuon_mau.dung_docx_thuoc`: checklist key or name, plus occurrence), and
    the version stores the tags in `audit.khung.thuoc`. Frame units carry no
    tag. Without the tag, identical "……" bodies were interchangeable and every
    heading renumbered on an insert, so fills moved to other clauses (code
    review 2026-09-29, finding 2).
  - A `dien` on a unit inside an `equal` block moves to the mapped index (same
    text ⇒ same blanks, checked by count).
  - A `dien` on a changed unit is dropped, and named in the answer.

  Frame units come before and after the Điều list, with unchanged text, so party
  fills always carry, even when the signature table shifts.
- **Only `dien` ops** exist on khuôn mẫu versions: chat content edits are
  rebuilds, and on-page saves are `dien`.
- **Values only.** A turn that changes only values keeps the viec and merges ops
  with `gop_phep_sua`; new ops win on the same blank.
- **Old viecs** stay for Lùi. There are at most `TRAN_SUA + 1` per draft, and all
  are removed with the conversation (ponytail: bounded, add a sweep if measured).

**`ban_thao` columns per khuôn mẫu version** (tổng quát and checklist rows alike):

| Column | Contents |
|---|---|
| `loai` | `'tong_quat'` for chat drafts; the checklist id for checklist drafts (below) |
| `facts` | Unchanged semantics: the checklist's user facts, or `{}` for tổng quát. The frontend types it `Record<string, string>`. |
| `clauses` | `[{key, ten, doan, can_cu}]`, where `can_cu` is `{duong_dan, doc_id, khop_tai_id} \| null`. It is resolved at build time from `db_provisions` (`_duong_dan_index`; `can_cu_provision_id` for checklist clauses; the checklist `muc.can_cu` for v3 clauses with a `key`). This is the source of truth a rebuild uses, and the căn cứ the stage opens. |
| `audit` | The mandatory-clause result (§6) plus `khung`: `{loai, bo_cuc, tieu_de, trich_yeu, ben: [{khoa, vai, loai}], can_cu: [{dong, doc_id}]}`. `khung` is the frame spec without values. It lives in `audit`, not `facts`, so the frontend's `facts` type holds. |
| `document` | A Markdown summary from one helper, `ban_thao.tom_tat_khuon_mau(khung, clauses, khuon)`: title, căn cứ, Điều list, filled values. It reuses `_render_markdown` and `tom_tat_khuon`, and it is what the v3 prompt and the value source read. |
| `viec_id`/`phep_sua` | As for khuôn gốc |

- `sua_o_dien` writes `tom_tat_khuon_mau` instead of `tom_tat_khuon` when
  `nguon = 'khuon_mau'`. It keeps `audit.muc_kiem` and `audit.khung` and adds
  `sua_tay`, where today's code forces `muc_kiem = tong_quat`.
- `ban_thao.sua` gains an optional `doi`, so a rebuilt version records "Điều đã
  đổi" instead of a blank-by-blank diff across two files.

**Checklist drafts (the `gom_du_kien` path) also become docx.** Review finding 5
asked for this to be fully specified:

- **`loai` stays the checklist id.** `graph_soan_thao`, `dung_lai`,
  `draft_audit`, `/mau/{loai}` and `DrawerSuaMuc` all key on it. `dung_lai` still
  refuses `tong_quat`.
- **One shared helper**,
  `ban_thao.dat_khuon_mau(sub, hoi_thoai_id, loai, facts, ket, cu=None) -> ket`,
  runs after `tu_state_soan_thao(st)` in both places:
  - `n_dung_ban_thao` (create);
  - `ban_thao.dung_lai`, which serves both the chat facts edit through
    `gom_du_kien` and `POST /ban-thao/{id}/dung`.

  It does five things:
  1. Builds the spec: the registry frame of `loai`; the `ket` clauses as `dieu`
     (`noi_dung` split on blank lines into `doan`, `can_cu` from
     `can_cu_provision_id`); `can_cu_van_ban_co_id` for the frame.
  2. Calls `luu_khuon_mau`, which writes a new viec, `don_vi` and `khuon_goc`.
  3. Derives `dien` ops from `facts`, through the entry's `truong_tu_facts` map
     (fact key → `(ben, truong)`).
  4. Carries the previous version's fills, when `cu` is given.
  5. Returns `ket` with `viec_id`, `phep_sua`, `document = tom_tat_khuon_mau(…)`
     and `audit_report.khung`.

  `tao`/`sua` then store them as today.
- **Fill precedence on a checklist rebuild.** For each mapped field blank:
  - its fact changed in this turn → the op comes from the new fact;
  - otherwise → the carried op, if any (an on-page fill is newer than an old fact);
  - otherwise → the op from the fact.
- **The conversation.** `dung_lai` takes `hoi_thoai_id` from `cu["hoi_thoai_id"]`.
  When that is NULL (drafts not made in a conversation), the version stays HTML:
  the named exception of §5, since `viec_doc_tai_lieu.hoi_thoai_id` is NOT NULL.
- **Lookups.** Checklist drafts are edited by id through `soan_thao_dang_mo` →
  `gom_du_kien` → `dung_lai`, so the `loai = 'tong_quat'` lookups need not see
  them. The view shortcut finds them, because `_SQL_MOI_NHAT_KHUON` drops its
  `loai` filter. Ponytail: a checklist draft whose session was closed is not a
  target for tổng quát chat edits; route by id if that case is measured.

## §4 Turn flow

**Routing (review finding 1): the router decides; there is no route-level
guard.**

- `route()` keeps its verdict in every case. The deterministic override proposed
  in round 1 is dropped: it matched verbs alone, it captured legal questions
  phrased as imperatives, and it contradicted `_re_sau_route`.
- What changes is what the router sees. `_dang_soan(sd, bt)` takes the checklist
  session `sd` (unchanged line) and, when there is no checklist session, the
  light row `bt` (`ban_thao_tong_quat_dang_mo`). When `bt.nguon == 'khuon_mau'`
  it returns
  `"<registry ten, or 'văn bản tự soạn' when loai_khuon is NULL> (bản thảo Word đang mở, N điều)"`,
  where N comes from `audit.so_dieu_khoan`.
- The line is built from repo data only. It never carries the model-written title
  or any user text: QT-3, the same rule `{dang_soan}` follows today.
- `route.v4.md` already says: when ĐANG SOẠN is not "(không)", a fact answer or a
  request to edit the draft is `soan_thao`, and only a real LEGAL question is
  `tra_cuu`.
- `prompts/route.v5.md` = v4 plus two example lines:
  - "Giải thích quy định về …" and "Nêu điều kiện để …" are `tra_cuu`, even while
    a draft is open.
  - "thêm điều về phạt vi phạm", "bỏ điều 5" and "tên bên B là …" are
    `soan_thao`.

  `config.route_prompt` moves to v5, so v4 stays reproducible for old results.
  The type enum becomes the registry ids (a superset of the checklists).
  `assemble._goi_y_soan_thao` and `gom_du_kien` keep checking `cac_loai()`, so a
  registry-only id reaches only `n_hieu_tai_lieu`.
- Both prompt changes ride the eval re-run the plan already schedules, plus the
  routing set of §8 (wave V).

**Which draft a no-attachment soạn turn works on.** When `intent == soan_thao`,
the turn attaches nothing, and the light row's `nguon == 'khuon_mau'`,
`n_hieu_tai_lieu` does not pull `tai_lieu_phien[:1]`. The khuôn mẫu is then the
turn's draft, and an older upload cannot capture the edit.

This decision uses data plus the router verdict, never verbs. If the router
instead says `tai_lieu`, the user is asking about an upload, and the existing
G7 path (`_quyet_khuon`: verb plus passing op or soạn reading) applies unchanged.

**Create or edit, no attachment** ("soạn hợp đồng thuê tài sản …", "sửa điều 3 …",
"thêm điều …", "điền tên bên B là …"):

1. `route` → `intent = soan_thao`, with `soan_thao_goi_y.loai` = a registry id or
   none.
2. `_re_sau_route` → `hieu_tai_lieu`, or `gom_du_kien` when a checklist session
   is open (unchanged).
3. `graph_tra_cuu.n_hieu_tai_lieu` does the DB part before the pure node, like
   `_nap_tai_lieu`. It loads:
   - the registry entry;
   - the checklist `muc` with their provision text (`requirements(loai)` →
     `build_context`, as `draft_generate` does), and `db_provisions` for
     `can_cu`;
   - the căn cứ lines (`can_cu_van_ban_co_id`);
   - the base.

   The base is the newest tổng quát draft (the light row). If it is khuôn mẫu,
   the base is editable, and `document` = its `tom_tat_khuon_mau`, with the
   current Điều numbers. If it is HTML, it is shown as "# Bản thảo cũ (chỉ để
   tham khảo)".
4. `hieu_tai_lieu`, `soan_tu_do` branch (no tài liệu in the turn, attached or
   pulled): prompt `prompts/hieu_tai_lieu.v3.md` on EVERY such turn (review
   finding 6), strict schema `schema_khuon_mau(sua=<base is khuôn mẫu>)` (§6),
   ONE model call → `kiem_khuon_mau` → state `khuon_mau_tong_quat`.
   - The model says `muc_tieu`: `ban_moi` (a new document) or `sua_ban_dang_co`.
   - With no base, or a legacy HTML base, the schema's enum is `ban_moi` only
     and `sua_dieu` is `null`-only. The turn therefore creates a new khuôn mẫu
     draft, with the legacy text as context and as a clause value source
     (`_nguon_soan` already includes it).
   - The legacy draft stays untouched. Nothing is converted half-way, and every
     new draft is a docx (decision item 5).
   - Frame values on that turn still follow `_nguon_nguoi` (§6). A party value
     that lived only in the legacy text is listed under "Còn trống" and is
     click-filled.
5. `dung_ban_thao_tong_quat`, khuôn mẫu branch:
   - **`ban_moi`:**
     1. `EP_SOAN_THAO` quota.
     2. `khuon_mau.dung_docx(spec)`.
     3. `ban_thao.luu_khuon_mau`: the reader, one LibreOffice render for the page
        count, then viec + `don_vi` + `khuon_goc`.
     4. Field values become `dien` ops through the field map, checked by the
        existing `hieu_tai_lieu.kiem_phep_sua` (user words only,
        `khong_khop_nhan`, date split).
     5. `ban_thao.tao`, then a traces row, as the HTML path does today.
   - **`sua_ban_dang_co`:** the base is re-read with `moi_nhat_khuon_mau`, under
     `TRAN_SUA` like any chat edit.
     - `dieu` non-null → replace all clauses.
     - `sua_dieu` → clause ops on the stored `clauses`; unchanged clauses stay
       verbatim by construction.
     - Either way → rebuild and carry fills (§3), merge the `gia_tri` ops, then
       `ban_thao.sua(doi=…)`.
     - Only `gia_tri` → same viec, `gop_phep_sua`.
     - Nothing changed → the existing draft is the turn's card (the khuôn
       `co_san` rule) and no version is made. The answer names what was not
       applied (`khong_dat`), or asks which Điều ("Tôi chưa xác định được điều
       cần sửa — hãy nêu số hoặc tên điều.").

     No verb regex is involved.
   - **Page cap:** `luu_khuon_mau` measures pages. The §6 length budget keeps a
     draft under the cap. An overflow despite the budget, or `qua_tai`, saves
     nothing, spends no quota, and gets a plain answer naming the longest Điều.
     It is the last resort, not the expected path (review finding 9;
     Open decision 3 is the gate).
6. `assemble` (0 token) answers with the khuôn mẫu wording (§6) and returns
   `ban_thao` with `khuon.nguon = 'khuon_mau'`. Then:
   - the frontend opens the stage once (G7 Q2);
   - `GET /ban-thao/{id}/trang` renders pages and `o` positions;
   - clicking a blank saves through `PATCH /ban-thao/{id}/o-dien` (G3/G4).

**A turn that attaches an image or a pre-036 upload** (review finding 2):

- It stays on the v1/`van_ban` path (named exception, §5).
- `_nap_ban_thao_dang_mo` reads the light row. When its `nguon == 'khuon_mau'`
  and the turn carries tài liệu, none of them with a khuôn gốc, it sets
  `ban_thao_tong_quat_dang_mo = None` and `khuon_mau_dang_mo = <light row>`. The
  v1 path therefore gets no base at all: neither the khuôn mẫu, which the HTML
  lookup cannot return anyway, nor an older HTML draft. (A turn with no tài liệu
  keeps the light row as its v3 base, step 3 above; a khuôn gốc turn keeps
  today's per-upload reload.)
- In `dung_ban_thao_tong_quat`'s HTML branch, suppose all three hold:
  - `khuon_mau_dang_mo` is set;
  - the model's reading is soạn;
  - the user's own words (`cau_hoi_goc or query`) ask to fill or edit
    (`xin_dien_sua`).

  This is the G7 pairing of verb plus model reading. The branch saves nothing,
  spends no quota, and answers `KHONG_DIEN_TU_ANH`:

  > Bản thảo «<tên>» là tệp Word; giá trị trong ảnh chưa được điền thẳng vào đó.
  > Hãy gõ giá trị trong chat (ví dụ «họ tên bên B là …») hoặc bấm vào chỗ trống
  > trên trang để điền.

- Any other soạn reading creates a new HTML draft from the image, as today.
- The khuôn mẫu draft's live version is never touched. This is consistent with
  khuôn gốc, whose value source (`_nguon_nguoi`) excludes document text too.
  Accepting image text as a value source is Open owner decision 8.

**Checklist session turns:** `gom_du_kien` → `n_dung_ban_thao` or `dung_lai`, and
`ban_thao.dat_khuon_mau` builds the docx (§3).

**Other requests:**

- "Cho tôi xem bản thảo" keeps G7 Q3: `moi_nhat_tren_khuon` (no `loai` filter now)
  matches every draft on a khuôn, with zero model calls.
- Download, Lùi and version reads use unchanged routes. Download names drop
  " - đã điền" for khuôn mẫu: `routes_ban_thao._tai_ve_dau` gets `co_doi=False`
  when `nguon = 'khuon_mau'`.

## §5 Existing HTML drafts, the căn cứ surface, XemTruocA4

**Legacy HTML drafts:**

- Rows already in `ban_thao` are not converted.
- `XemTruocA4` and `xuat-tep.ts` `xuatWord`/`xuatPDF` stay mounted only for
  versions whose `khuon` is null. Those are:
  - legacy drafts and their old versions (Lùi);
  - drafts written from an image or a pre-036 upload;
  - checklist drafts outside a conversation.
- A chat soạn turn over a legacy HTML draft creates a new khuôn mẫu draft (§4
  step 4). The legacy draft is never edited in place by chat and never
  half-converted.
- The stage shortcuts "Rút gọn / Trang trọng hơn / Soát lại theo luật" are chat
  turns, so on a legacy draft they also yield a new khuôn mẫu draft.
- No code is deleted this wave. Removal waits until no path yields an HTML draft.

**Named exceptions that stay HTML (owner decision 5):**

- Drafting from an image upload, or from an upload stored before migration 036.
  Their tables and images cannot be expressed in the builder.
- The standalone form workspace (`KhongGianSoanThao`, `POST /soan-thao`). It is
  stateless and has no conversation for a viec (`viec_doc_tai_lieu.hoi_thoai_id`
  is NOT NULL).

**The căn cứ surface for docx drafts** (review finding 3, decision item 3,
plan Outcome 2):

- **Server.** `_voi_khuon` adds `khuon.can_cu` for khuôn mẫu rows. The list comes
  from one pure helper, `ban_thao.can_cu_khuon_mau(audit, clauses)`:

  ```
  [{nhan, doc_id, khop_tai_id | null, dieu | null}]
  ```

  - Frame lines come from `audit.khung.can_cu`: `nhan` is the line, and
    `khop_tai_id` is null.
  - Clause căn cứ come from `clauses[i].can_cu`:
    `nhan = "Điều <i+1>. <ten> — <duong_dan>"`, `khop_tai_id` = the provision id,
    and `dieu` = i+1.

  Both come from visible documents (§2 filters). The đối chiếu endpoint enforces
  visibility again on open.
- **Stage.** When `khuon.nguon === "khuon_mau"` and the list is not empty, the
  page toolbar shows a "Căn cứ (N)" button. It opens the existing `NganXepDrawer`
  with a tier `can-cu-ds` that lists the items:
  - An item with `khopTaiId` calls the existing
    `doiChieuCanCu.mo({docId, khopTaiId, duongDan: nhan})`, which opens tier two
    (`NoiDungCanCu`, nguyên văn plus hiệu lực badge). This is exactly what the
    mục drawer does today, but for every clause, not only those with an audit
    finding.
  - A frame line (a document) is a link to `/tra-cuu/{docId}`.
- **Chat.** The chat answer names the căn cứ documents in one line (§6).
- `DrawerSuaMuc` no longer shows on docx versions: the stage hides the mục column
  when `khuon !== null`. Editing is by chat and on the page, as the owner asked.
  `POST /ban-thao/{id}/dung` keeps working and rebuilds a docx (§3).

## §6 Model contract

One strict JSON schema, `hieu_tai_lieu.schema_khuon_mau(sua: bool)`. Every field
is required, with `null` when unused:

```json
{
  "muc_tieu": "ban_moi" | "sua_ban_dang_co",
  "tieu_de": "HỢP ĐỒNG …" | null,          "trich_yeu": "Về việc …" | null,
  "bo_cuc": "hop_dong" | "hanh_chinh" | "don" | null,
  "ben": [{"khoa": "ben_a", "vai": "Bên cho thuê", "loai": "ca_nhan" | "to_chuc"}] | null,
  "can_cu": ["91/2015/QH13"] | null,
  "gia_tri": [{"ben": "ben_a", "truong": "ho_ten", "gia_tri": "Nguyễn Văn A"}],
  "dieu": [{"key": "gia_thue" | null, "ten": "Giá thuê", "doan": ["…"]}] | null,
  "sua_dieu": [{"thao_tac": "thay" | "them_sau" | "xoa", "dieu": 3,
                "key": "…" | null, "ten": "…" | null, "doan": ["…"] | null}] | null,
  "khong_dat": ["…"]
}
```

- With `sua=False` (no base, or a legacy HTML base), the `muc_tieu` enum is
  `["ban_moi"]` and `sua_dieu` is `{"type": "null"}`.
- `tieu_de`, `bo_cuc`, `ben` and `can_cu` are read only for tổng quát (no registry
  entry). A registry type takes them from data.
- `dieu` is the full clause list: the create shape, or a replace-all edit.
  `sua_dieu` is the clause-op edit. Its `dieu` numbers are the current Điều
  numbers shown in the base, and `them_sau` with 0 inserts first.
- For a `don` layout, `dieu[*].key` must name a `than` section of the entry. An
  entry without a matching key is dropped and reported; the form fixes the
  positions.
- Enums: `key` ∈ the checklist's `muc` keys and the entry's section keys (else it
  is read as null); `truong` ∈ the field catalog; `ben` ∈ the entry's party keys.

**Prompt v3 rules the checks below enforce:**

- No article or document number anywhere in clause text; the căn cứ come from
  code.
- No numeric reference to another Điều: write "Điều về giá thuê" or "khoản trên".
  "khoản 2 Điều này" (a reference to the same Điều) is allowed.
- No party identity in clause text: names, CCCD, phone, e-mail and account
  numbers go in `gia_tri` only.
- An unknown value is written as "……", never as `[…]`, `[Tên …]` or `<…>`.
- The length budget: at most 25 Điều, 8 paragraphs per Điều, 1,200 characters per
  paragraph, and **`NGAN_SACH_KY_TU` characters in total** (see below).

**Validation** (`hieu_tai_lieu.kiem_khuon_mau`, pure, 0 token) runs in this order:

1. **Heading numbers.** Strip any leading number from `ten`:
   `^\s*(?:điều|ĐIỀU)\s*\d+\s*[.:–-]?\s*` and `^\s*\d+\s*[.)]\s*`, so "Điều 3.
   Giá thuê" becomes "Giá thuê". Also drop a first paragraph that only repeats the
   heading. This runs BEFORE the nets (review finding 4).
2. **Intra-document references.**
   - "Điều n (của|tại)? <tên loại of this draft, or Hợp đồng|văn bản|Quy
     chế|Nội quy|Quyết định|Thỏa thuận> này" is rewritten deterministically to
     "Điều về <ten of clause n, lower-cased first letter>", when n is in range.
     The rewrite is name-based, so it survives renumbering on a later rebuild.
   - "(khoản|điểm) <n>(, <m>)* (của )?Điều này" is a protected span. Both nets
     skip it (it is replaced by a neutral same-length string for the check, then
     restored).
   - An out-of-range n is left alone, so step 5 catches it.
3. **Placeholders.**
   - `\[[^\]\n]{0,80}\]`, `<[^>\n]{0,80}>` and `\{[^}\n]{0,80}\}` (a literal
     `[…]` included) become "……", counted as `cho_mo_hinh`. The value net's own
     `[…]` output in step 5 is written as "……" too.
   - Control characters, `⟦` and `¶` are removed.
4. **Stray blanks** (review finding 8).
   - Two or more U+2026, four or more dots, or three or more underscores → "……",
     an intended blank.
   - A single `…`, or exactly `...` → removed. At the end of a paragraph it
     becomes ".".
   - Three or more of `-–—` → removed.

   After this step, the only `RE_CHO_DIEN` matches in clause text are "……".
5. **Nets, per paragraph.** Each paragraph goes through the existing value net
   (`lam_sach_van_ban`, given each paragraph as its own mục, so its whole-mục drop
   acts on one paragraph). A value not in `_nguon_soan` becomes "……": user words,
   hồ sơ, allowed memory, the base's `document`. Then the paragraph goes through
   `bo_nho._vuong_luoi_chan`:
   - a paragraph it still catches (an external article number, a document number,
     an identity trace) is dropped, and named in the answer ("Bỏ 1 đoạn ở Điều 5
     vì dẫn số điều luật không kiểm được");
   - a Điều is dropped only when no paragraph remains;
   - `ten` is checked the same way.
6. **Caps and budget.**
   - Over the per-Điều caps → trailing paragraphs are cut and named.
   - Over `NGAN_SACH_KY_TU` → non-mandatory Điều are dropped from the end until
     the total fits, and named ("Chưa đưa vào vì quá dài: …"). Mandatory Điều are
     never cut.
   - An empty result creates nothing (`KHONG_SOAN_DUOC`).
7. **Mandatory clauses.** `checklist.check_completeness` runs on the `dieu` keys,
   with the same `khong_bat_buoc` and `muc_do_thieu` as `draft_audit`. The shared
   helper `khuon_mau.them_dieu_bat_buoc(dieu, loai)` also serves the checklist
   path.
   - On create, each missing mandatory `muc` is inserted at its checklist position
     as "Điều n. <muc.ten>", with one "……" paragraph. The draft always has every
     clause the law requires, empty rather than invented.
   - On edit, nothing is re-added; a missing clause is a finding.

   The result is `audit_report = {dat, completeness, so_dieu_khoan, findings (with
   can_cu duong_dan, doc_id, khop_tai_id), muc_kiem: "tong_quat" | <loai>,
   khung}`.
8. **Frame values.** `gia_tri` becomes `dien` ops after the build, and goes
   through `kiem_phep_sua` with `_nguon_nguoi`: user words and hồ sơ without
   `suy_dien`. This is the stricter khuôn rule, since party identities are exactly
   what owner rule B2 protects. Dropped values feed `khong_dat`, filtered to the
   user's words, and are named ("Chưa đặt được: «…»").

**`NGAN_SACH_KY_TU`** is measured, not guessed. D4a renders one maximal spec per
`bo_cuc`: the frame, 25 Điều, and filler text up to the budget. It pins the
largest budget that stays at 9 pages or fewer, leaving one page of headroom for
Liberation Serif vs Times New Roman.

The starting estimate is 16,000 characters. On a 165 × 257 mm text area at 14 pt
and 1.15 spacing, that is about 2,500 characters a page, with one page of frame.
The prompt states the budget in characters and in pages.

**Answer** (assemble, 0 token). It names only ops present in the saved version
(owner: never claim a fill that did not happen):

- "Bản thảo <tên> (N trang) đã sẵn sàng: mở bản thảo để xem, tải Word hoặc PDF."
- "Căn cứ: <document names from `audit.khung.can_cu`>. Bấm «Căn cứ» trên trang để
  xem nguyên văn."
- "Còn trống: «…»", from `khuon.cho_trong` minus the version's `dien`.
- "Điều còn trống vì luật đòi: «…»".
- The dropped paragraphs, cut Điều and dropped fills.
- For types NĐ 30 does not bind, the private-document note "Thể thức theo tập
  quán, tham khảo Phụ lục I Nghị định 30/2020/NĐ-CP".

## §7 Registry

```
config/khuon_mau/_truong.yaml     field catalog: key → label
config/khuon_mau/<loai>.yaml      one file per type; `loai` = the checklist id when one exists
```

The field catalog holds these keys, with labels such as ho_ten "Họ và tên" and
so_dinh_danh "Số định danh cá nhân": ho_ten, ngay_sinh, gioi_tinh, so_dinh_danh,
noi_cu_tru, dia_chi, dien_thoai, fax, thu_dien_tu, ten_to_chuc,
ma_so_doanh_nghiep, dia_chi_tru_so, nguoi_dai_dien, chuc_vu, so_tai_khoan,
ngan_hang, toa_an, co_quan_nhan.

**Rule for `nguon.loai: mau_chinh_thuc`** (review finding 7). The entry
reproduces the official form's content. Every static string is transcribed
verbatim from the official file, in the form's order:

- the party role lines and field lines;
- the section labels;
- the Kính gửi text;
- the signer label and its note, or its absence.

The official file is the one named in `nguon`, with its SHA-256 from D2
`index.json`. Transcription removes only three things: dot runs (they become
slots), footnote callouts "(n)", and the Công báo frame (D2 §4.1).

Lines are templates, and `{truong}` slots become the §1 blanks. A slot at the end
of a line becomes a `tab` leader; a slot mid-line becomes a `cham` "……". No `{`
reaches any part (builder test).

`tuong_tu` and `tu_dung` entries use catalog field lines, with an optional
`nhan` override per field.

**Party type** (hợp đồng review, 2026-09-29). A party whose type the law does not
fix is `loai: tuy`, with `mac_dinh` (`ca_nhan` | `to_chuc`) and two blocks
`ca_nhan:` / `to_chuc:` holding its `dong` or `truong`/`nhan`. Its signer slot
carries the same two blocks for `vai`/`ghi_chu`/`ho_ten_tu`.
`khuon_mau.chon_ben(entry, ben)` merges the chosen block. It is called in
`spec_tu`, so every build path resolves. The model names the type in `ben[].loai`
(prompt v3 rule 2, "Khoá bên" marks the party). Failing that, `_ben_registry`
takes, in order, the stored type, then the type implied by the fields `gia_tri`
assigns, then `mac_dinh`. An edit that changes a party's type rebuilds the file,
and carried fills on that party are dropped and reported. Fixed parties remain
where the law fixes them: the passenger carrier (Luật Đường bộ Đ56.10), the
real-estate service provider (Luật KDBĐS Đ9.5), and the employee.

**Optional-only căn cứ.** `graph_soan_thao.can_cu_khung` tags a frame line
`tuy_chon` when only the checklist's `khong_bat_buoc` part cites that document.
`khuon_mau.can_cu_hien` prints the line only while a Điều cites that document,
and it re-punctuates the block. It is applied in the docx build, the document
summary, the page's căn cứ list and the chat answer. Today this affects one type:
Luật Đường bộ in `hop_dong_van_chuyen_tai_san`, cited only by the optional
Giấy vận tải item. Prompt v3 marks optional items "TUỲ CHỌN".

Example, transcribed from `goc/m23-ds_toaan-TAND279888.pdf` (SHA-256 `6881d9dd…`),
page 1, `pdftotext -layout`, 2026-09-29. The source's own wording is kept verbatim,
including "chứng kèm theo" and the missing colon after the second "Địa chỉ"; see
Open decision 4.

```yaml
loai: don_khoi_kien
ten: đơn khởi kiện
tieu_de: ĐƠN KHỞI KIỆN
bo_cuc: don
nguon:
  loai: mau_chinh_thuc            # mau_chinh_thuc | tuong_tu | tu_dung
  van_ban: "Nghị quyết 01/2017/NQ-HĐTP, Mẫu số 23-DS"
  url: https://www.toaan.gov.vn/webcenter/ShowProperty?nodeId=%2FUCMServer%2FTAND279888
  tep_d2: goc/m23-ds_toaan-TAND279888.pdf
  sha256: 6881d9dda626033de033c120d790a3ef064c301b089ec3b754219cf5228a8a0a
  trang: 1
  ghi_chu: "Tên Toà án để trống: Toà án nhân dân khu vực thay Toà cấp huyện (NQ 01/2025 Đ7.1)."
the_thuc:
  dong_mau: null                  # D2 §4.1: annex caption stripped (Open decision 7)
  co_quan: false
  so: null
  ngay: dau                       # centred directly under tiêu ngữ, no gap (D2 §4.5)
  kinh_gui: {dong: "Kính gửi: Toà án nhân dân {toa_an}", can: thut}   # ≈30 mm (D2 layout note)
  can_cu: false
  noi_nhan: null
  ket_thuc: null
ben:
  - khoa: nguoi_khoi_kien
    dong: ["Người khởi kiện: {ho_ten}", "Địa chỉ: {dia_chi}",
           "Số điện thoại: {dien_thoai}(nếu có); số fax: {fax}(nếu có)",
           "Địa chỉ thư điện tử: {thu_dien_tu} (nếu có)"]
  - khoa: nguoi_bi_kien
    dong: ["Người bị kiện: {ho_ten}", "Địa chỉ {dia_chi}",
           "Số điện thoại: {dien_thoai}(nếu có); số fax: {fax}(nếu có)",
           "Địa chỉ thư điện tử: {thu_dien_tu} (nếu có)"]
  - khoa: nguoi_duoc_bao_ve
    dong: ["Người có quyền, lợi ích được bảo vệ (nếu có) {ho_ten}", "Địa chỉ: {dia_chi}",
           "Số điện thoại: {dien_thoai}(nếu có); số fax: {fax}(nếu có)",
           "Địa chỉ thư điện tử : {thu_dien_tu}(nếu có)"]
  - khoa: nguoi_lien_quan
    dong: ["Người có quyền lợi, nghĩa vụ liên quan (nếu có) {ho_ten}", "Địa chỉ: {dia_chi}",
           "Số điện thoại: {dien_thoai}(nếu có); số fax: {fax}(nếu có)",
           "Địa chỉ thư điện tử: {thu_dien_tu} (nếu có)"]
  - khoa: nguoi_lam_chung
    dong: ["Người làm chứng (nếu có) {ho_ten}", "Địa chỉ: {dia_chi}",
           "Số điện thoại: {dien_thoai}(nếu có); số fax: {fax}(nếu có)",
           "Địa chỉ thư điện tử: {thu_dien_tu} (nếu có)."]
than:                             # the form's order; key ↔ checklist muc
  - {ben: nguoi_khoi_kien}
  - {ben: nguoi_bi_kien}
  - {ben: nguoi_duoc_bao_ve}
  - {ben: nguoi_lien_quan}
  - {muc: yeu_cau, nhan: "Yêu cầu Tòa án giải quyết những vấn đề sau đây:"}
  - {ben: nguoi_lam_chung}
  - {muc: tai_lieu_kem_theo, nhan: "Danh mục tài liệu, chứng kèm theo đơn khởi kiện gồm có:", danh_sach: 2}
  - {muc: thong_tin_khac, nhan: "(Các thông tin khác mà người khởi kiện xét thấy cần thiết cho việc giải quyết vụ án)"}
ky:
  thu_tu: [nguoi_khoi_kien]       # one signer, right half (D2 §4.7, centre ≈146 mm)
  o: [{khoa: nguoi_khoi_kien, vai: "Người khởi kiện", in_hoa: false, ghi_chu: null, ho_ten_tu: null}]
truong_tu_facts: {}               # checklist fact key → [ben, truong], when the checklist collects facts
```

A few rules the entry relies on:

- A `muc` section with no model text keeps one "……" line. `danh_sach: n` gives
  "1 ……" … "n ……".
- `ho_ten_tu: null` means no name line, because the form has none. An entry whose
  form prints one names the party.
- Official files are recorded by URL, SHA-256 and page, and are not committed by
  default. D3 commits one only if a test needs it, with its source in the entry.
  Forms annexed to legal normative documents are not protected (Luật SHTT
  Điều 15).
- The loader, `khuon_mau.cac_loai()` / `khuon_mau.nap(loai)`, is `lru_cache`d.
  Like `load_checklist`, it fails at load on an unknown `bo_cuc`, field key,
  party key or `than` key, or on a `mau_chinh_thuc` entry without `tep_d2` and
  `sha256`.

**Recorded labels.** D3 writes
`tests/test_services/du_lieu/nhan_mau_chinh_thuc.yaml`. For each `mau_chinh_thuc`
entry it holds `tep_d2` and `sha256`, the exact `pdftotext -layout -f P -l P`
command, and the ordered static strings, with dot runs and "(n)" callouts removed
and whitespace collapsed. The registry test builds each entry's static-string
sequence (slots removed) and asserts it is equal.

Mapping, from `mau-hien-co.md` and D2. Each row gives `bo_cuc` and the source:

| Types | bo_cuc | Source |
|---|---|---|
| don_khoi_kien | don (`ngay: dau`, `kinh_gui: thut`) | mau_chinh_thuc, Mẫu 23-DS NQ 01/2017 (toaan TAND279887/8) |
| don_khieu_nai | don (`ngay: dau`, `kinh_gui: giua`; NGƯỜI KHIẾU NẠI / (Chữ ký hoặc điểm chỉ) / Họ và tên) | mau_chinh_thuc, Mẫu 01 NĐ 124/2020 (Công báo 1015+1016) |
| don_yeu_cau | don (`ngay: cuoi`, "(V/v: ……)" line, `kinh_gui: giua`, NGƯỜI YÊU CẦU) | mau_chinh_thuc, Mẫu 01-VDS NQ 04/2018 (layout authority: the VanBanGoc scan, D2) |
| cong_van | hanh_chinh (công văn, `ngay: cot_phai`) | mau_chinh_thuc, NĐ 30 Mẫu 1.5 (rebuilt: the Công báo .doc renders with wrong bold, D2 §3) |
| quyet_dinh_bo_nhiem | hanh_chinh (quyết định) | mau_chinh_thuc, NĐ 30 Mẫu 1.2 |
| quy_che_noi_bo | hanh_chinh (kèm theo) | mau_chinh_thuc, NĐ 30 Mẫu 1.3 + kèm theo |
| ban_tu_khai, don_xin_nghi_viec, van_ban_giai_trinh | don | tuong_tu NĐ 124 Mẫu 01 |
| giay_uy_quyen | don, two signers (NGƯỜI ĐƯỢC ỦY QUYỀN left, NGƯỜI ỦY QUYỀN right, per the form); a `giay_uy_quyen_to_chuc` entry uses hanh_chinh Mẫu 1.4 | tuong_tu NĐ 124 Mẫu 02 / NĐ 30 Mẫu 1.4 |
| bien_ban_hop_hdqt | hanh_chinh (biên bản) | tuong_tu NĐ 30 Mẫu 1.9 |
| quyet_dinh_cham_dut_hdld, quyet_dinh_ky_luat | hanh_chinh (quyết định) | tuong_tu Mẫu 1.2 |
| quyet_dinh_hdqt | hanh_chinh (nghị quyết/quyết định) | tuong_tu Mẫu 1.1 |
| noi_quy, quy_che_dan_chu | hanh_chinh (kèm theo) | tuong_tu Mẫu 1.3 kèm theo |
| hdld, hop_dong_thu_viec | hop_dong (`ngay: khong`, per Mẫu 01/PLV; Open decision 2) | tuong_tu NĐ 145/2020 Mẫu 01/PLV; TT 5/2023 Phụ lục II as a second reference |
| hop_dong_dich_vu | hop_dong | tuong_tu NĐ 96/2024 Phụ lục II layout; TT 5/2023 Phụ lục I |
| hop_dong_gia_cong, _hop_tac, _mua_ban, _mua_ban_tai_san, _nguyen_tac, _thue_tai_san, _uy_quyen, _vay, thoa_thuan_bao_mat, thoa_thuan_cham_dut_hdld | hop_dong | tuong_tu NĐ 96/2024 Phụ lục II layout |

- `ky.thu_tu` for a `tuong_tu` contract defaults to Bên A left. That is every
  commercial sample D2 viewed; the State forms vary (D2 §4.6).
- An entry that follows one State form takes that form's order.

**New types (D3).**

- Each new contract also gets `config/checklist_<loai>.yaml`, with the verified
  clauses of `hop-dong.md`.
- Contracts, `hop_dong`, buildable now: `hop_dong_dat_coc`,
  `hop_dong_van_chuyen_tai_san`, `hop_dong_van_chuyen_hanh_khach`,
  `hop_dong_tang_cho_tai_san`, `hop_dong_chuyen_nhuong_quyen_su_dung_dat`,
  `hop_dong_dich_vu_bat_dong_san`.
- Đơn and giấy tờ from history: `don_xin_tam_hoan_nvqs`, `don_xin_hoc_lai`,
  `ban_kiem_diem_ca_nhan`, `bien_ban_hop`, `giay_tiep_nhan_thuc_tap`,
  `phieu_danh_gia_thuc_tap`, `ke_hoach_thuc_tap`. These are registry entries
  without a checklist, unless a law lists their contents.
- Blocked until F1 loads the law:
  - `hop_dong_thue_nha_o` and `hop_dong_mua_ban_nha_o` (Luật Nhà ở 27/2023 is
    shallow). Interim since 2026-09-30: `hop_dong_thue_nha_o` exists with the
    BLDS thuê tài sản clauses under its own title, and a create turn states
    that the kho lacks the full text of Luật Nhà ở (`luat_rieng`, checked
    against the kho each turn). Its Luật Nhà ở clauses still wait for F1;
  - the hôn nhân gia đình types (Luật Hôn nhân và gia đình). Among them is
    thuận tình ly hôn, which files on Mẫu 01-VDS: NQ 04/2018 has no dedicated
    form (D2 §1).

## §8 Tests and end-to-end proof

Focused tests, with no DB and no paid model (fake LLMs), in TDD order:

| File | Proves |
|---|---|
| `tests/test_services/test_khuon_mau.py` | See [below](#what-test_khuon_maupy-proves). |
| `tests/test_services/test_khuon_mau_registry.py` | Every `config/khuon_mau/*.yaml` loads, and every checklist type has an entry. `nguon.url` is official (`*.gov.vn`, `vbpl.vn`, `datafiles.chinhphu.vn`, `congbao.chinhphu.vn`), or `nguon.loai` is `tu_dung`/`tuong_tu` with a reason. **Every `mau_chinh_thuc` entry's static strings equal `du_lieu/nhan_mau_chinh_thuc.yaml` in order**, and its `sha256` equals the recorded one. |
| `tests/test_agents/test_kiem_khuon_mau.py` | See [below](#what-test_kiem_khuon_maupy-proves). |
| `tests/test_services/test_mang_phep_sang.py` | Party fills carry across a rebuild that adds a Điều and shifts the signature. A fill inside a rewritten paragraph is dropped and reported. Checklist precedence: a changed fact beats a carried fill; an unchanged fact loses to a carried on-page fill. |
| `tests/test_agents/test_dung_ban_thao_khuon_mau.py` | See [below](#what-test_dung_ban_thao_khuon_maupy-proves). |
| `tests/test_agents/test_dung_ban_thao_checklist_docx.py` | `n_dung_ban_thao` create → the version sits on a viec with `nguon='khuon_mau'`. A facts edit through `gom_du_kien` → `dung_lai` → a new version on a NEW viec, never `viec_id` NULL, with fills carried. `moi_nhat_tren_khuon` (no `loai` filter) finds the checklist docx draft. `cu.hoi_thoai_id` NULL → HTML, unchanged. |
| `tests/test_agents/test_assemble_khuon_mau.py` | The answer names only saved fills. It lists "Còn trống" and the căn cứ documents. It never says "tệp bạn tải lên", and never shows ⟦n⟧. |
| `tests/test_agents/test_route_khuon_mau.py` (never `test_route.py`) | See [below](#what-test_route_khuon_maupy-proves). |
| `tests/test_services/test_khuon_mau_trang.py` | Gated on `soffice` like `test_dung_trang.py`, run sequentially. Every registry type with a sample spec renders at 10 pages or fewer. The maximal spec per `bo_cuc` at `NGAN_SACH_KY_TU` renders at 9 pages or fewer. The quốc hiệu sits on one line (`pdftotext -tsv`). Page 1 has no number and page 2 has "2". The `/trang` probe positions every party blank. |
| `tests/test_services/test_migration_041.py` | `pytest.mark.integration`, Integrate stage only, run by explicit path. Checks the column, the default, the CHECK, and an idempotent re-run. DDL only, no rows. |
| `frontend/scripts/kiem-khuon-goc.ts` (run by `npm run kiem`) | `khuonHopLe` keeps `nguon` and defaults it to `tai_len`. It keeps well-formed `can_cu` items and drops malformed ones (`docId` not a string, `khopTaiId` neither an integer nor null). `phuDeKhuon` wording follows `nguon`. |

### What `test_khuon_mau.py` proves

- The page setup values.
- The exact quốc hiệu and tiêu ngữ strings and runs.
- No `{`, `{{`, `⟦`, `¶`, `[` or `<` placeholder in any part.
- The same spec gives the same bytes.
- On `doc()` re-read:
  - every party field is one `tab` blank with its label;
  - the date line gives blanks labelled "ngày", "tháng", "năm";
  - header and signature tables have `bang_vien` False and no `o`.
- Every `cham` blank in clause text corresponds to a "……" in the spec, so no stray
  blank exists.
- `ngay` in `dau`/`cot_phai`/`cuoi`/`khong` puts the date where the form does, and
  `kinh_gui: thut` indents 30 mm.
- The field map resolves every `(ben, truong)` to a blank.
- `ap_dung_docx` fills every blank with an empty `bo_qua`.
- Điều are numbered 1..n.

### What `test_kiem_khuon_mau.py` proves

- "Điều 3. Giá thuê" → `ten` "Giá thuê", and the clause is kept.
- "theo quy định tại khoản 2 Điều này" keeps the paragraph, and its "2" is not
  blanked.
- "nghĩa vụ tại Điều 4 Hợp đồng này" → "nghĩa vụ tại Điều về <ten of 4>".
- "theo Điều 473 Bộ luật Dân sự" drops only that paragraph, and names it.
- `[Tên Bên A]`, `[Thông tin về Bên A…]`, `[số tiền]`, `<…>` → "……".
- "điện, nước, internet…" → "điện, nước, internet.". "………" → "……".
- An unsourced number → "……".
- Unknown `key` → null.
- A missing mandatory `muc` is inserted with "……" on create, and is only a finding
  on edit.
- A total over budget drops non-mandatory Điều from the end and names them;
  mandatory Điều are kept.
- `gia_tri` not in the user's words is dropped and named.
- `sua_dieu` keeps untouched clauses byte-identical.
- `sua=False` schema: `sua_dieu` null-only, `muc_tieu` `ban_moi` only.

### What `test_dung_ban_thao_khuon_mau.py` proves

- Create persists a viec with `nguon='khuon_mau'`, a khuon_goc, and v1 with
  `dien` ops (service calls monkeypatched).
- `clauses[*].can_cu` carries `doc_id`/`khop_tai_id`.
- An edit with `sua_dieu` → a new viec, carried ops, `tang=1`.
- A values-only edit → the same viec.
- A legacy HTML base → a NEW draft, and the legacy row is unchanged.
- An overflow or `qua_tai` → nothing saved and no traces row.
- **Image-attach turn with a khuôn mẫu draft open and "điền thông tin theo ảnh
  này vào hợp đồng"** → `KHONG_DIEN_TU_ANH`, no new row, no version. The khuôn
  mẫu's live version is still on its viec (review finding 2).

### What `test_route_khuon_mau.py` proves

- `_dang_soan` for a khuôn mẫu light row → the registry name and N điều.
- Tổng quát → "văn bản tự soạn", never the model's title.
- HTML or upload light row → "(không)".
- A checklist session keeps its line.
- `route()` with a fake LLM that records the prompt: the ĐANG SOẠN line carries
  the draft.
- The returned `intent` equals the fake LLM's verdict (`tra_cuu` stays `tra_cuu`,
  `soan_thao` stays `soan_thao`) whatever the draft: no override exists.
- `n_hieu_tai_lieu` does not pull the newest upload only when
  `intent == soan_thao`, nothing is attached, and the light row is khuôn mẫu.
- `_nap_ban_thao_dang_mo`: a turn with no tài liệu keeps the khuôn mẫu light
  row as its base; an image turn gets base `None` and `khuon_mau_dang_mo`; a
  khuôn gốc turn reloads by its upload, as today.

**Routing behaviour** is a model judgment, so it is measured, not unit-tested:
`eval/datasets/route_ban_thao_mo.yaml` plus a runner of about 40 lines,
`eval/run_route_ban_thao.py`, which calls `route()` with an open khuôn mẫu light
row. It runs in wave V, on the owner's budget: about 12 router calls on the pinned
router model.

- Negatives, expected `tra_cuu`:
  - "Giải thích quy định về sửa chữa tài sản thuê theo Bộ luật Dân sự."
  - "Cho tôi biết quy định khi bên thuê thay đổi mục đích sử dụng tài sản."
  - "Nêu điều kiện để sửa đổi hợp đồng lao động."
  - "Tôi muốn hỏi về thủ tục cập nhật thông tin đăng ký doanh nghiệp."
- Positives, expected `soan_thao`:
  - "thêm điều về phạt vi phạm"
  - "bỏ điều 5"
  - "viết lại điều 2 ngắn hơn"
  - "rút gọn điều 4"
  - "tên bên B là Trần Văn C"
  - "sửa điều 3 thành …"
  - "điền tên bên B là …"

Acceptance is 4/4 negatives and at least 6/7 positives. A miss is a v5 prompt fix
before merge, never a code override.

**End-to-end proof:**

1. **Integrate stage.** Fake LLM, one API test run by explicit path
   (`tests/test_api/test_khuon_mau_luot.py`, integration). The steps:
   1. A create turn → `khuon.nguon == 'khuon_mau'`, and `khuon.can_cu` is not
      empty for a checklist type.
   2. `GET /ban-thao/{id}/trang` → pages and positioned blanks.
   3. `PATCH /o-dien` → v2.
   4. A chat edit with `sua_dieu` → v3 on a new viec, with v2's fill still
      present.
   5. `POST /lui` → v2, and `GET /trang?phien_ban=2` → 200.
   6. `/tai-xuong?dang=docx` re-reads with `doc()` and has no marker; `dang=pdf`
      starts with `%PDF`.
   7. The conversation's tài liệu list and the daily document count do not include
      the khuôn mẫu viec.

   **Precondition** (review finding 10): this test writes rows (users, hoi_thoai,
   viec, khuon_goc, ban_thao). It runs only after the orchestrator confirms the
   parallel retrieval eval has finished, and it cleans up its rows the way the
   `hai_nguoi` fixture of `tests/test_api/test_ban_thao_khuon_api.py` does. Until
   then the Integrate checklist marks it "pending: DB busy". Running it earlier
   against a disposable database is allowed only if the orchestrator provides one;
   this wave creates none.
2. **Wave V**, on the owner's budget, in the real app: hợp đồng thuê tài sản, đơn
   khởi kiện, công văn and one tổng quát type.
   - Page images side by side with the official forms (D2 PNGs `png/m23-goc`,
     `png/nd124-cb`, `png/nd30-cb`).
   - Each Word download opened in Microsoft Word on the owner's Mac: no repair
     prompt, same page count.
   - The "Căn cứ" panel opens nguyên văn.
   - Screenshots go in `.tham-dinh-shots/`.
   - Then the routing set above.

**Commands:**

- `KLAW_BO_NHO_NEN=false KLAW_SUPABASE_URL= .venv/bin/python -m pytest -q <files>`
- the CI lane of the wave brief
- `ruff check src/ tests/ scripts/`
- `ruff format --check` on changed files
- `npm run typecheck && npm run kiem`
- `prettier --check` on changed frontend files

## Files to change

| Wave | File | Change |
|---|---|---|
| D3 | `config/khuon_mau/_truong.yaml`, `config/khuon_mau/<loai>.yaml` (29 + new) | Registry data; `mau_chinh_thuc` lines verbatim |
| D3 | `tests/test_services/du_lieu/nhan_mau_chinh_thuc.yaml` (new) | Recorded official label lists with file and SHA-256 |
| D3 | `config/checklist_<new contract>.yaml` | New checklists (verified căn cứ) |
| D4a | `src/services/khuon_mau.py` (new) | Registry loader, `dung_docx`, `them_dieu_bat_buoc`, `NGAN_SACH_KY_TU` (measured) |
| D4a | `src/agents/graph_soan_thao.py` | `can_cu_van_ban_co_id`; `can_cu_van_ban` becomes a comprehension over it |
| D4b | `migrations/041_viec_doc_nguon.sql` (new), `src/main.py` | The column; `"041"` in `MIGRATIONS_KHOI_DONG` |
| D4b | `src/services/tai_lieu.py` | `tao_viec(nguon=…)`; `nguon = 'tai_len'` in `tai_lieu_cua_hoi_thoai` and `da_dung_hom_nay` |
| D4b | `src/services/ban_thao.py` | See [below](#d4b-changes-to-ban_thaopy). |
| D4b | `src/api/routes_ban_thao.py` | Download name without " - đã điền" for khuôn mẫu |
| D4c | `prompts/hieu_tai_lieu.v3.md` (new) | Khuôn mẫu drafting rules and length budget (§6) |
| D4c | `prompts/route.v5.md` (new), `src/config.py` | v4 plus two example lines; `route_prompt` default v5 |
| D4c | `src/agents/nodes/route.py` | `_dang_soan(sd, bt)` with the khuôn mẫu line; type enum from `khuon_mau.cac_loai()`. **No override.** |
| D4c | `src/agents/nodes/hieu_tai_lieu.py` | `schema_khuon_mau(sua)`, `kiem_khuon_mau`, v3 on every `soan_tu_do` turn |
| D4c | `src/agents/graph_tra_cuu.py` | DB prep for the v3 turn; the no-pull rule in `n_hieu_tai_lieu`; `khuon_mau_dang_mo` in `_nap_ban_thao_dang_mo`; `n_dung_ban_thao` via `dat_khuon_mau` |
| D4c | `src/agents/nodes/dung_ban_thao_tong_quat.py` | Khuôn mẫu create/edit branch; `KHONG_DIEN_TU_ANH` |
| D4c | `src/agents/nodes/assemble.py` | Branch on `khuon.nguon`; khuôn mẫu answer with căn cứ line |
| D4d | `frontend/src/lib/klaw.ts` | `KhuonBanThao.nguon` and `can_cu`; `khuonHopLe` |
| D4d | `frontend/src/components/soan-thao/SanKhauBanThao.tsx` | See [below](#d4d-changes-to-sankhaubanthaotsx). |
| D4d | `frontend/src/lib/khuon-goc.ts` | `phuDeKhuon`: "Bản thảo · N trang · còn K chỗ trống" for khuôn mẫu |
| V | `eval/datasets/route_ban_thao_mo.yaml`, `eval/run_route_ban_thao.py` (new) | Routing set with an open khuôn mẫu draft |

### D4b changes to `ban_thao.py`

- `nguon` in `_SQL_KHUON*` and `_khuon_tu`.
- A `LEFT JOIN` in `_SQL_MOI_NHAT_NHE` that returns `nguon` and `loai_khuon`.
- `_SQL_MOI_NHAT_KHUON_MAU` and `moi_nhat_khuon_mau`.
- The `loai` filter dropped from `_SQL_MOI_NHAT_KHUON`.
- New helpers: `luu_khuon_mau`, `dat_khuon_mau`, `mang_phep_sang`,
  `tom_tat_khuon_mau`, `can_cu_khuon_mau`.
- `khuon.can_cu` in `_voi_khuon`.
- `sua(doi=…)`.
- `sua_o_dien` keeps `muc_kiem`/`khung` for khuôn mẫu.
- `dung_lai` via `dat_khuon_mau`.

### D4d changes to `SanKhauBanThao.tsx`

- A "Căn cứ (N)" toolbar button and a `can-cu-ds` drawer tier that reuses
  `doiChieuCanCu` and `NoiDungCanCu`; frame lines link to `/tra-cuu/{docId}`.
- "Rút gọn / Trang trọng hơn / Soát lại theo luật" also for khuôn mẫu.
- The page label "Các trang của bản thảo — bấm vào chỗ trống để điền".

No new Python or npm dependency.

## Risks And Recovery

- **LibreOffice cost.** One extra render per build or rebuild: about 1–2 s, in one
  of the three shared slots. `qua_tai` answers plainly and saves nothing.
  Ponytail: reuse that render for the first `/trang` when it is measured slow.
- **Page cap.** The budget (§6) keeps drafts at 9 pages or fewer. Long nội quy and
  quy chế may need more than the budget allows: Open decision 3 is a gate before
  D4c.
- **Rebuilds** drop a fill inside a rewritten paragraph, and the answer names it.
  Frame fills always carry.
- **Router.** Without an override, a router miss on an edit ("điền tên bên B …"
  routed `tra_cuu`) gives a legal answer instead of an edit. It is measured by the
  routing set, and fixed in the prompt.
- **Fonts.** Liberation Serif vs Times New Roman page counts are measured in
  wave V; the budget keeps one page of headroom.
- **Eval.** The router enum and v5 prompt shift routing, so the eval re-runs after
  F2, as planned.
- **Recovery.** Each wave merges `--no-ff`, reverted with `git revert -m 1
  <merge>`. Migration 041 is additive, and the column can stay if the code is
  reverted.

## Open Owner Decisions

Defaults apply unless the owner decides otherwise. Only decision 3 blocks.

1. **Căn cứ wording.** The 2026-09-28/29 decisions print the full number and date
   for every document ("Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11
   năm 2015"). Phụ lục I cites a Luật or Pháp lệnh by name, without its number
   (`the-thuc.md` §3, "Viện dẫn"). Default: keep the owner's decision.
2. **Contract number line.** `Số: ……/……` (the NĐ 96 model, default) vs the
   decision's example `…/…/HĐTTS`. And HĐLĐ with or without Số and date line:
   Mẫu 01/PLV has neither, so the default is neither.
3. **GATE before D4c: the page cap for generated drafts.** Today
   `ck_khuon_goc_so_trang BETWEEN 1 AND 10`, and `_PX_TAI_LIEU_TOI_DA` covers
   about 10 A4 pages at 110 dpi; beyond that, dpi drops uniformly.
   - (a) Keep 10, and let the §6 budget shorten long types.
   - (b) Recommended for nội quy / quy chế: raise it to 20 for `nguon='khuon_mau'`
     only. That takes one migration changing the CHECK to
     `CHECK (so_trang BETWEEN 1 AND 20)`; code keeps `TRAN_TRANG = 10` for
     uploads, and `_PX_TAI_LIEU_TOI_DA` is raised together, or `/trang`
     paginates.
4. **Verbatim vs relabelled official wording.** Examples: "Số CMND/Hộ chiếu/Thẻ
   căn cước công dân" (NĐ 124 Mẫu 01, superseded by "số định danh cá nhân");
   "chứng kèm theo" and "Địa chỉ" without a colon (the toaan Mẫu 23-DS file).
   Default: verbatim.
5. **The standalone form workspace.** Move `POST /soan-thao` and
   `KhongGianSoanThao` onto the engine (it needs a conversation)? And should
   drafting from an image upload also produce a docx?
6. **A different document on a conversation with an uploaded khuôn gốc.** Such a
   request still answers `van_ban_khac`; building a khuôn mẫu there costs a second
   model call.
7. **Rendition of official forms.** Times New Roman (default; the MOJ copy of
   Mẫu 23-DS and NĐ 30) or Arial (the toaan file)? And keep the annex caption
   "Mẫu số 23-DS (Ban hành kèm theo …)" (`dong_mau`)? Default: omit it, per
   D2 §4.1.
8. **Image text as a value source** for filling a khuôn gốc or khuôn mẫu. The
   default is no, like `_nguon_nguoi` today; the turn answers
   `KHONG_DIEN_TU_ANH`.

## §9 Review resolution (round 1, 2026-09-29)

| # | Finding | Resolution |
|---|---|---|
| 1 | high: the route guard overrode the router on verbs alone | Guard removed. The router decides. `{dang_soan}` shows the open khuôn mẫu draft (repo data only), and v5 adds legal-imperative examples. The no-pull rule uses the router verdict plus data. Tests: no-override and prompt capture; the eval set holds the reviewer's four negatives and the design's positives (§4, §8). |
| 2 | high: the HTML path could overwrite a khuôn mẫu draft | Three kinds, three lookups. The `_SQL_MOI_NHAT*` predicates are unchanged, so HTML means `viec_id IS NULL` only, and there is a new `moi_nhat_khuon_mau`. An image or pre-036 turn gets no base when a khuôn mẫu is open, and a fill/edit request answers `KHONG_DIEN_TU_ANH`. The requested test is added (§3, §4, §8). |
| 3 | high: no openable căn cứ on docx drafts | `clauses[].can_cu` carries `doc_id`/`khop_tai_id`, resolved at build. `audit.khung.can_cu` holds the frame lines with `doc_id`. The server adds `khuon.can_cu`. The stage gets a "Căn cứ (N)" drawer that reuses the đối chiếu tier, and the chat answer names the documents. A kiem test is added (§3, §5, §8). |
| 4 | medium: the block net hollowed contracts | Order is heading strip → intra-document references (name-based rewrite, protected "khoản n Điều này") → nets per paragraph, not per clause. The prompt forbids numeric cross-references. Tests for both cases (§6). |
| 5 | medium: the checklist path was underspecified | `loai` stays the checklist id. The shared `dat_khuon_mau` serves `n_dung_ban_thao` and `dung_lai` (new viec, carried fills, fact/fill precedence). The view shortcut drops its `loai` filter. `hoi_thoai_id` NULL stays HTML. Tests are added (§3, §8). |
| 6 | medium: an old HTML draft kept creates HTML | v3 runs on every soạn turn without a tài liệu. A legacy HTML base is context only, the schema allows only `ban_moi`, and the turn creates a docx draft (§4, §5, §6). |
| 7 | medium: the registry example did not reproduce Mẫu 23-DS | A verbatim-transcription rule, plus a recorded label fixture and test. The example is re-transcribed from the official PDF. Its party order follows the file (khởi kiện, bị kiện, được bảo vệ, liên quan), which differs from the review's list. `ngay`, `kinh_gui`, `dong_mau` and `ky.thu_tu` are now parameters. `don_yeu_cau` maps to Mẫu 01-VDS. Rebuild vs ship is decided explicitly: rebuild (§1, §7). |
| 8 | medium: model placeholders and stray ellipses | Deterministic placeholder → "……", and stray `…`/`...`/`---` normalisation. Builder and kiem tests assert no `[` and no unintended blank (§1, §6, §8). |
| 9 | medium: a >10-page refusal after a paid call | A measured `NGAN_SACH_KY_TU` and tighter caps in the prompt and in kiem, with non-mandatory Điều trimmed and named. Refusal is the last resort. Open decision 3 is a gate before D4c, with a recommendation (§4, §6, Open decisions). |
| 10 | medium: the e2e test writes to the shared DB | The test is gated until the parallel eval finishes, as a stated Integrate precondition with cleanup. No disposable DB is created by this wave (§8). |

## §10 Code review resolution (implementation, 2026-09-29)

| # | Finding | Resolution |
|---|---|---|
| 1 | high: a request for another type while a khuôn mẫu is open was built in the open draft's frame | `_nap_khuon_mau`: when the router names a type other than the open one, the turn is a create on the router's type, and the open draft is reference only. For a tự soạn draft, only a registry type counts as "other", because the router has no code to name a tự soạn draft again. Tests: three routing cases, same-type edit, and an end-to-end đơn khởi kiện over an open draft. |
| 2 | high: carried fills landed in the wrong Điều after an insert or delete | Carry-over by `(clause, text)` (§3). Tests: insert first, delete first, frame fills after the Điều list, and a node-level insert after on-page fills. |
| 3 | high: a paid checklist call went unrecorded when the docx failed | `n_dung_ban_thao` and `dung_lai` write the traces row with the generate cost and `result_type 'loi'`, so the daily cost cap sees it and no quota is spent. `dung_lai` also counts the attempt against `TRAN_SUA` (`tinh_lan_sua_hong`). Nothing is saved, as in §4. No HTML fallback: owner decision 5. |
| 4 | medium: tieu_de, trich_yeu and vai bypassed both nets | The same two nets as a paragraph. The block net drops the field (defaults "Văn bản", none, "Bên A") and names it; the value net leaves "……". |
| 5 | medium: checklist docx duplicated the party sections as Điều | `dat_khuon_mau` drops clauses keyed by `khoa_khung(entry)`. |
| 6 | medium: the answer claimed carried or on-page fills as this turn's | `da_dien` counts only this turn's new or changed ops. The sentence is omitted on `co_san` or when nothing is new. The checklist path states the version total "Đã điền X/Y chỗ trống." with no provenance. |
| 7 | medium: a tự soạn hành chính draft dropped the signer's name | `bo_cuc hanh_chinh` uses the fixed `co_quan`/`nguoi_ky` parties, and the prompt names them. Rejected `gia_tri` go to `khong_dat`. |

## §11 Review resolution (hợp đồng group, 2026-09-29)

| # | Finding | Resolution |
|---|---|---|
| 1 | medium: `trach_nhiem_vi_pham` was mandatory on BLDS Đ398.2.e, a "có thể có" provision | Moved to `khong_bat_buoc` in the nine checklists that added it, with the same Đ398.2 rationale as `tranh_chap`. A ratchet test keeps Đ398.2.e/g optional in every contract checklist except `hop_dong_nguyen_tac`, which is built on Đ398.2 by design. |
| 2 | medium: every vận chuyển tài sản contract printed "Căn cứ Luật Đường bộ" | Option (b): the optional-only căn cứ rule (§7). The line appears only when a Giấy vận tải Điều is drafted. |
| 3 | medium: parties fixed as individual or organisation | `loai: tuy` (§7) on every contract party the law does not fix, including the employer in the four labour entries (BLLĐ Đ3.2). Tests build and fill every entry under default, all-individual, all-organisation and mixed choices. |

## Progress

- [x] D1 design written.
- [x] D1 review round 1 (10 findings), resolved in this revision (§9).
- [ ] D1 review round 2.
- [ ] Owner: decision 3 (gate before D4c); defaults stand for 1, 2 and 4–8
      unless the owner says otherwise.
- [ ] D3 registry, recorded labels, new checklists. Started on `feat/khuon-mau`: the
      field catalog and three reference entries (`hdld` after NĐ 145 Mẫu 01/PLV,
      `don_khoi_kien` Mẫu 23-DS, `cong_van` NĐ 30 Mẫu 1.5) with their recorded labels.
      The other 26 checklist types and the new types remain; `test_moi_checklist_co_khuon_mau`
      is a strict xfail until they land.
- [x] D4a builder and budget measurement (`src/services/khuon_mau.py`). Measured
      2026-09-29 on LibreOffice 26.2: the maximal spec gives 8 pages per `bo_cuc` at
      16,000 and 18,000 characters, 10 at 20,000; `NGAN_SACH_KY_TU` stays 16,000.
      The tiêu ngữ rule is 171.2 pt, measured with `pdftotext -bbox`.
- [x] D4b storage: migration 041 written, not applied; `tai_lieu.tao_viec_khuon_mau`
      writes viec + `khuon_goc` in one transaction; `ban_thao` lookups, carry-over,
      `dat_khuon_mau`, `khuon.nguon`/`can_cu`, the download name.
- [x] D4c graph: prompt v3, `schema_khuon_mau`/`kiem_khuon_mau`, `_nap_khuon_mau`,
      the no-pull rule, `KHONG_DIEN_TU_ANH`, the create/edit branch, the answer,
      `_dang_soan` and `route.v5` as the default. Open decision 3 defaulted to (a):
      the 10-page cap stays; an overflow saves nothing and names the longest Điều.
      Implementation note: the v3 path runs when `graph_tra_cuu` has prepared
      `khuon_mau_ngu_canh`, which it does on every signed-in no-document drafting
      turn. A direct call to the node without it keeps the old `van_ban` path; old
      unit tests rely on that.
- [x] Code review of D4a–D4c (7 findings), resolved (§10).
- [ ] D4d frontend.
- [ ] Integrate: migration 041, integration tests by path; the e2e API test after
      the eval finishes.
- [ ] V: real-app check, Word check, routing set, eval re-run.
