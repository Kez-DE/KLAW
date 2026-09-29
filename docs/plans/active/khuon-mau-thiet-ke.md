# Design: every draft is a real .docx built from a khuôn mẫu (wave D1)

Date: 2026-09-29

## Status

Design for review (wave D1 of `docs/plans/active/the-thuc-va-he-thong-phap-luat.md`).
Nothing implemented. Waves D3 (khuôn mẫu data) and D4 (engine) code against §1–§8.

## Outcome

1. A chat request such as "soạn hợp đồng thuê tài sản giữa tôi Nguyễn Văn A và …"
   yields a draft whose pages are a real `.docx` rendered by LibreOffice: A4 and
   margins per NĐ 30/2020 Phụ lục I, header (quốc hiệu, tiêu ngữ, số, địa danh và
   ngày), tên loại and trích yếu, căn cứ from the kho with full number and date,
   party blocks, numbered Điều, a two-column signature table, nơi nhận when the
   type has one. Values the user did not give are "…" blanks.
2. That draft behaves exactly like a draft on an uploaded khuôn gốc: the stage
   opens, blanks are clicked and filled on the page, every save is a version, Lùi
   walks back, Word and PDF downloads are the same file as the pages.
3. "sửa điều 3 …", "thêm điều về phạt vi phạm", "điền tên bên B là …" in chat
   make a new version of the same draft. No ⟦n⟧ marker, template token or `[…]`
   ever reaches a page or a download.
4. Types: the 29 checklist types plus new types (decision item 8), each from one
   registry file recording its source (official form URL, or "built to Phụ lục I").

## Context

Authority: decision `docs/decisions/2026-09-29-the-thuc-moi-ban-thao.md` items
1–8 (Accepted; items 5–8 are this wave), decision
`2026-09-26-luu-khuon-goc-va-dien-tai-cho.md` and plan
`docs/plans/completed/khuon-goc-dien-tai-cho.md` (the engine and its
contracts), decision `2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md` (căn cứ
block, visibility rule `src/services/hien_thi.py`), `CONTEXT.md` (khuôn mẫu,
khuôn gốc, thể thức, bản thảo tổng quát, căn cứ, kho).

T1 research (session scratchpad `tt/`, read in full): `the-thuc.md` (NĐ 30
Điều 8 and Phụ lục I rules quoted from Công báo 283+284), `mau-hien-co.md` (29
checklists; official forms: Mẫu 23-DS NQ 01/2017/NQ-HĐTP, Mẫu 01 NĐ 124/2020,
NĐ 30 Mẫu 1.2, 1.3/1.4, 1.5), `hop-dong.md` (contract clauses; NĐ 96/2024
Phụ lục II contract layout), `nen-tang.md` and `dinh-tuyen.md` (waves F1/F2,
not this design).

What the engine already gives (read end to end, 2026-09-29):

- Storage keys on `viec_doc_tai_lieu.id`: `khuon_goc` (036) holds the bytes,
  `viec_doc_tai_lieu.don_vi` holds the reader's units with `dia_chi`,
  `cho_trong`, `doan_chu`; `ban_thao.viec_id`/`phep_sua` (037) say which file and
  which ops a version is. `ban_thao._SQL_KHUON`/`_SQL_KHUON_DAY` join the two;
  every route (`/ban-thao/{id}/trang`, `/o-dien`, `/tai-xuong`, `/lui`,
  `/phien-ban/{n}`) goes through them.
- A version carries its own `(viec_id, phep_sua)`: `_snap` stores both, `sua`
  writes the ket's pair, `lui` restores the snapshot's pair, and
  `khuon_cua_phien_ban` reads the version's `viec_id`. So consecutive versions
  may sit on different files with no engine change.
- Blank detector (`doc_tai_lieu._cho_trong_doan`): `cham` = a maximal run of
  `.`/`…` that `RE_CHO_DIEN` accepts (one `…` is enough, or three dots); `tab` =
  the n-th `w:tab` of a paragraph when the n-th stop declared DIRECTLY in its
  `w:pPr/w:tabs` has `w:leader="dot"`; `o` = empty cell of a BORDERED body table
  under a named column. Units are body `w:p`, body-table `w:tc`, header/footer
  paragraphs; a text-less paragraph is not a unit; paragraphs holding fields,
  text boxes or `mc:AlternateContent` carry no blanks (fail closed).
- Today's HTML draft path: `hieu_tai_lieu` (`soan_tu_do`: `intent = soan_thao`
  and no tài liệu) writes `van_ban` → `lam_sach_van_ban` value net →
  `dung_ban_thao_tong_quat.ket_ban_thao` → `ban_thao._render_markdown` → the stage
  draws `XemTruocA4`, and `xuat-tep.ts` `xuatWord`/`xuatPDF` export from the
  browser. The stage already switches on `khuon !== null`
  (`SanKhauBanThao.tsx:844`): a draft with `khuon` gets `KhungTrangAnh`, on-page
  filling and server downloads with no further frontend work.
- Căn cứ lines exist: `graph_soan_thao.can_cu_van_ban` →
  `trich_dan.khoi_can_cu`/`dong_can_cu` ("Căn cứ Bộ luật Lao động số
  45/2019/QH14 ngày 20 tháng 11 năm 2019;"), visible and in-force documents only,
  NĐ 30 excluded as a thể thức-only source.

## §1 Template format: blanks, clause slots, page setup

**No template file with markers.** A khuôn mẫu is a registry entry (§7) plus the
builder (§2); the builder writes the model's clauses straight into the document
it generates. There is no slot token in any stored or downloaded file, so there
is nothing to strip. (Upgrade path, only if D2 shows the builder cannot match an
official form: ship that form as `config/khuon_mau/<loai>.docx` and treat it as a
khuôn gốc; any slot token it carries is removed before storage, with a test that
none survives.)

**Blanks, so the existing detector finds them unchanged:**

| Where | Written as | Detector kind | Label the page shows |
|---|---|---|---|
| Party field lines, whole-line fields ("Họ và tên:", "Địa chỉ:") | label run, then one `w:tab`; the paragraph's own `w:pPr/w:tabs` declares a right stop at text width with `w:leader="dot"` | `tab` | text before the tab ("Họ và tên") |
| Two fields on one line ("Ngày sinh: … Giới tính: …") | two tabs, two direct stops (≈55 % and 100 % of text width), both dot leaders; first label short enough to end before stop 0 | `tab` ×2 | "Ngày sinh", "Giới tính" |
| Inline parts: `Số: ……/HĐ-……`, `……, ngày …… tháng …… năm ……`, "tại ……", blanks inside clause text | "……" (two U+2026) in its own run, paragraph formatting | `cham` | text before ("Số", "ngày", "tháng", "năm"; a leading place blank reads "Chỗ trống") |
| Signature name line | a paragraph "……" under "(Ký, ghi rõ họ tên)" | `cham` | "Chỗ trống" (value copied from the party's `ho_ten`, §2) |
| Data tables (phiếu đánh giá, danh mục) — only types that need one | bordered table, header row with column names, empty body cells | `o` | "<column> (dòng n)" |

Rules the builder keeps so the reader and applier accept every blank: never put
a blank in a paragraph with a field, text box or drawing; header and signature
tables are borderless (`w:tblBorders` all `none`, no table style), so they are
never data tables and yield no `o` blanks; the value net's `[…]`
(`hieu_tai_lieu.CHO_TRONG`) is written as "……", never literally. Unknown values
are never filled: no date, place or number of KLAW's own (decision item 2).

**Page setup (Phụ lục I, quoted in `the-thuc.md` §3):** A4 portrait
(`w:pgSz` 11906×16838); margins top 20 mm (1134), bottom 20 mm (1134), left 30 mm
(1701), right 15 mm (851); Times New Roman (server renders Liberation Serif,
metric-compatible); page number centred in the top margin, size 14, not on page 1
(`w:titlePg`, default header with one `w:fldSimple w:instr="PAGE"`, no first-page
header). One size set for the whole document (the "tăng, giảm phải thống nhất"
rule), upper bound of each range: quốc hiệu 13 bold upper; tiêu ngữ 14 bold,
"Độc lập - Tự do - Hạnh phúc" with U+002D; tên cơ quan 13 bold; "Số:" 13;
địa danh và ngày 14 italic; tên loại 14 bold upper; trích yếu 14 bold; căn cứ 14
italic, ";" per line and "." on the last; body 14 justified, first-line indent
1.27 cm, 6 pt after, line spacing 1.15; quyền hạn/chức vụ ký 14 bold upper; họ
tên ký 14 bold; "Nơi nhận:" 12 bold italic, items 11. If D4 measures the quốc
hiệu wrapping in its column, the whole set drops to the lower bounds. Strings are
the official ones: "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" (Ò U+00D2). Rules under
tiêu ngữ and tên cơ quan: an empty paragraph with a bottom border, symmetric
indents giving the text's length (tiêu ngữ, a fixed string) or one third of the
cell (tên cơ quan); an empty paragraph is not a unit.

## §2 Builder

**Choice: the repo's `lxml` OOXML path, no python-docx.** Reasons: `lxml` is
already in `requirements.txt` and is what `dien_khuon.py` writes OOXML with; the
builder needs exactly the parts python-docx has no API for (table and paragraph
borders, `w:titlePg`, `fldSimple`, direct tab stops per paragraph), so it would
drop to raw XML anyway; python-docx's default template brings Calibri theme
fonts and its own core properties to override; a new dependency would also mean
installing into the shared `.venv`. The builder writes six parts
(`[Content_Types].xml`, `_rels/.rels`, `word/document.xml`, `word/styles.xml`
with `w:docDefaults` Times New Roman 14 / `vi-VN`, `word/settings.xml` with
`w:compatSetting compatibilityMode=15` so Word does not open it in compatibility
mode, `word/header1.xml` + its rels), zipped by `zipfile` with fixed timestamps:
the same spec gives the same bytes.

**Signature:** `dung_docx(spec) -> tuple[bytes, dict[tuple[str, tuple[int, ...]], list[tuple[str, str]]]]`
in `src/services/khuon_mau.py`, pure (no DB, no model, no LibreOffice). The map
is `(part, chi_muc)` → the `(ben, truong)` of each field blank of that unit in
reading order, i.e. exactly the reader's `dia_chi` (§3 turns it into `dien` ops).

**`spec`** (validated, §6): `{loai | None, bo_cuc, the_thuc, tieu_de, trich_yeu,
can_cu: [line], ben: [{khoa, vai, loai, truong: [key]}], dieu: [{key, ten,
doan: [str]}], ky: [...], noi_nhan: [...] | None}`.

**Three layouts, one set of pieces** (`bo_cuc` of the registry entry):

- `hanh_chinh` (NĐ 30 sơ đồ, CB p.33): borderless 2×2 header table, 40 % / 60 %
  of the 165 mm text width — row 1: tên cơ quan chủ quản (optional, not bold) +
  TÊN CƠ QUAN (bold) + rule | quốc hiệu + tiêu ngữ + rule; row 2: `Số: ……/<ký
  hiệu>-……` (+ "V/v …" for công văn) | `……, ngày …… tháng …… năm ……`. Then tên
  loại + trích yếu + rule (not for công văn); "Kính gửi:" only for công văn and
  upward tờ trình/báo cáo; căn cứ lines; "Theo đề nghị của ……" and the
  "QUYẾT ĐỊNH:" line for quyết định; body; "./." after the last body paragraph
  (Phụ lục III model layout, not a quoted rule); borderless signature table:
  "Nơi nhận:" list left | QUYỀN HẠN, CHỨC VỤ / (Chữ ký, dấu) / name blank right.
  Flags cover the Phụ lục III variants: biên bản (no top date, THƯ KÝ | CHỦ TỌA),
  văn bản kèm theo (no Số and date, "(Kèm theo Quyết định số …/QĐ-… ngày … tháng …
  năm … của …)", no signature).
- `don` (Mẫu 23-DS, NĐ 124 Mẫu 01): centred quốc hiệu + tiêu ngữ, no cơ quan and
  no Số; date line; TÊN ĐƠN; "Kính gửi: …"; person blocks; labelled sections in
  the form's own wording; attachments; signature right: NGƯỜI … / (Ký, ghi rõ họ
  tên hoặc điểm chỉ) / name blank.
- `hop_dong` (NĐ 96/2024 Phụ lục II, `hop-dong.md` §4): centred quốc hiệu +
  tiêu ngữ; date line centred ABOVE the title when the entry says so; TÊN HỢP
  ĐỒNG; `Số: ……/……` centred; căn cứ; "Hôm nay, ngày …… tháng …… năm ……, tại ……,
  chúng tôi gồm:"; party blocks "I. BÊN … (sau đây gọi là Bên A):" + field lines;
  "Hai bên thống nhất ký kết … với các điều khoản sau:"; Điều list; closing "Hợp
  đồng này được lập thành …… bản, …"; borderless two-column signature table
  (ĐẠI DIỆN BÊN A | ĐẠI DIỆN BÊN B, "(Ký, ghi rõ họ tên)", or "…, chức vụ và đóng
  dấu" for organisations).

**Code builds the frame, the model writes only clauses (item 7):** quốc hiệu,
tiêu ngữ, số, date line, tên loại (registry `tieu_de`; tổng quát: the model's
title upper-cased), căn cứ, party labels, Điều numbering ("Điều n." bold heading,
the model's `ten` after it, any number the model wrote stripped), closing and
signature come from code and data. Căn cứ: registry types with a checklist use
`graph_soan_thao.can_cu_van_ban` on `requirements(loai)`; registry types without
one list `can_cu: [duong_dan]` in the entry, same function; tổng quát turns may
name `can_cu: [so_ky_hieu]`, which code resolves against `documents` and passes
through the same visibility and in-force filter (`khoi_can_cu`); unresolved
numbers print nothing. The signature name blank gets the party's `ho_ten` value
when the user gave one.

## §3 Storage

**Reuse `viec_doc_tai_lieu` + `khuon_goc`, one additive column.** A built draft
is stored like an upload: one `viec_doc_tai_lieu` row (`nguon = 'khuon_mau'`,
`trang_thai 'xong'`, `ten_tep` "<Tên loại>.docx", `loai` = registry id or NULL,
`don_vi` from running the existing reader `doc_tai_lieu.doc` on the built bytes,
`so_trang` from one LibreOffice render via `dung_trang.khuon_goc`), one
`khuon_goc` row (`dinh_dang 'docx'`), and `ban_thao.viec_id` pointing at it. Every
route, the applier, the probe, the page cap and the per-account render slot work
unchanged because they only see a viec with a khuôn gốc.

Migration `041_viec_doc_nguon.sql` (041 is free on main and on every live
worktree, checked 2026-09-29):

```sql
ALTER TABLE viec_doc_tai_lieu ADD COLUMN IF NOT EXISTS nguon TEXT NOT NULL DEFAULT 'tai_len'
    CONSTRAINT ck_viec_doc_nguon CHECK (nguon IN ('tai_len', 'khuon_mau'));
```

Idempotent in the style of 040 (inline CHECK, `IF NOT EXISTS`); the constant
default needs no table rewrite (Postgres 11+), and the CHECK validates a small
table once. Appended to `src/main.py::MIGRATIONS_KHOI_DONG`. Applied only in the
Integrate stage.

The column exists because three readers must not see a khuôn mẫu as a user's
tài liệu: `tai_lieu.tai_lieu_cua_hoi_thoai` (chat chips, `tai_lieu_phien`, the
document Q&A path) and `tai_lieu.da_dung_hom_nay` (daily document quota) add
`AND nguon = 'tai_len'`; `ban_thao._SQL_KHUON`/`_SQL_KHUON_DAY` return `v.nguon`
so `khuon` gains `"nguon"` (`BanThaoOut.khuon` is an untyped dict,
`src/models/schemas.py:237`, no schema change).

Rejected: a sibling table keyed on `ban_thao` (every `_SQL_KHUON*`, `_VIEC_CUA_CHU`,
snapshot, lookup and route would need a second branch); a column on
`khuon_goc` (the listing and quota filters read `viec_doc_tai_lieu`).

**Which draft a chat edit targets.** `_SQL_MOI_NHAT` and `_SQL_MOI_NHAT_NHE`
compare the draft's UPLOAD key instead of its raw `viec_id`:
`(SELECT v.id FROM viec_doc_tai_lieu v WHERE v.id = ban_thao.viec_id AND v.nguon = 'tai_len') IS NOT DISTINCT FROM CAST(:viec_id AS uuid)`.
So `viec_id=None` finds HTML drafts and khuôn mẫu drafts (one kind: "not on an
upload"), and a khuôn gốc draft is still found by its upload. The light query
also returns `nguon` for the routing guard in §4.

**Content edits rebuild; fills are ops.** A chat edit that changes clause text
builds a NEW docx from the updated spec and stores a new viec; the new version
points at it. Fills carry over by `ban_thao.mang_phep_sang(don_vi_cu, don_vi_moi,
phep_cu)`: `difflib.SequenceMatcher` over the two unit-text lists; a `dien` on a
unit inside an `equal` block moves to the mapped index (same text ⇒ same blanks,
checked by count); a `dien` on a changed unit is dropped and named in the answer.
Frame units come before and after the Điều list with unchanged text, so party
fills always carry, even when the signature table shifts. Only `dien` ops exist
on khuôn mẫu versions (chat content edits are rebuilds, on-page saves are `dien`).
A turn that changes only values keeps the viec and merges ops with
`gop_phep_sua`. Old viecs stay for Lùi; at most `TRAN_SUA + 1` per draft, all
removed with the conversation (ponytail: bounded, add a sweep if measured).

`ban_thao` columns per khuôn mẫu version: `loai 'tong_quat'` (so every chat
lookup keeps working), `facts` = the frame spec without values (registry id,
`bo_cuc`, title, trích yếu, căn cứ lines, party roles), `clauses` = `[{key, ten,
doan, can_cu}]` (the source of truth a rebuild uses), `document` = Markdown
summary from one helper `ban_thao.tom_tat_khuon_mau(facts, clauses, khuon)`
(title, căn cứ, Điều list, filled values; reuses `_render_markdown` and
`tom_tat_khuon`), `audit` = mandatory-clause result (§6), `viec_id`/`phep_sua`.
`sua_o_dien` writes `tom_tat_khuon_mau` instead of `tom_tat_khuon` when
`nguon = 'khuon_mau'`, so the prompt base keeps the clauses. `ban_thao.sua` gains
an optional `doi` so a rebuilt version records "Điều đã đổi" instead of a
blank-by-blank diff across two files.

## §4 Turn flow

**Create — "soạn hợp đồng thuê tài sản …"**

1. `route` (existing router call) → `intent = soan_thao`,
   `soan_thao_goi_y.loai` = a registry id or none. The router's type enum becomes
   the registry ids (a superset of the checklist types, §7); that changes the
   router prompt, so it rides the eval re-run the plan already schedules.
2. `_re_sau_route` → `hieu_tai_lieu`. `graph_tra_cuu.n_hieu_tai_lieu` does the DB
   part before the pure node, like `_nap_tai_lieu`: registry entry, checklist
   `muc` with their provision text (`requirements(loai)` → `build_context`, as
   `draft_generate` does), căn cứ lines (`can_cu_van_ban`), the open draft.
3. `hieu_tai_lieu`, `soan_tu_do` branch (no tài liệu in the turn) and the
   conversation's newest tổng quát draft is not a legacy HTML one → prompt
   `prompts/hieu_tai_lieu.v3.md`, strict schema `schema_khuon_mau` (§6), ONE model
   call → `kiem_khuon_mau` → state `khuon_mau_tong_quat`. Turns WITH a khuôn gốc
   keep prompt v2 and ops; turns with a non-khuôn tài liệu (images, uploads before
   036) keep v1 and `van_ban` (named exception, §5).
4. `dung_ban_thao_tong_quat`, khuôn mẫu branch: `EP_SOAN_THAO` quota (create) →
   `khuon_mau.dung_docx(spec)` → `ban_thao.luu_khuon_mau` (reader, one
   LibreOffice render for the page count, viec + don_vi + khuon_goc; more than 10
   pages or `qua_tai` → no draft, quota not spent, plain answer) → field values
   become `dien` ops through the field map and are checked by the existing
   `hieu_tai_lieu.kiem_phep_sua` (user words only, `khong_khop_nhan`, date split)
   → `ban_thao.tao` → traces row, as the HTML path does today.
5. `assemble` (0 token) answers with the khuôn mẫu wording (§6) and returns
   `ban_thao` with `khuon.nguon = 'khuon_mau'`; the frontend opens the stage once
   (G7 Q2); `GET /ban-thao/{id}/trang` renders pages and `o` positions; clicking a
   blank saves through `PATCH /ban-thao/{id}/o-dien` (G3/G4).

**Edit — "sửa điều 3 …", "thêm điều …", "điền tên bên B là …"**

- Routing guard (G7 Q4 applied to khuôn mẫu, deterministic), in `route.py`
  right after the `ep_meta` override because `hieu_tai_lieu.soan_tu_do` reads
  `intent == soan_thao` (a conditional edge cannot change state): when the
  conversation's newest draft is a khuôn mẫu (`ban_thao_tong_quat_dang_mo.nguon`,
  from `ban_thao.ban_thao_tong_quat_dang_mo_nhe`, which `routes._chuan_bi_phien`
  already loads every turn), the turn attaches nothing, and the user's
  words carry a fill/edit verb (`hieu_tai_lieu.xin_dien_sua`, accent-aware) and
  are not a question, `intent` becomes `soan_thao` whatever the router said
  (trace `route_ep_soan_khuon_mau`). On such a turn `n_hieu_tai_lieu` does not
  pull the conversation's newest upload in, so an older uploaded file cannot
  capture the edit.
- The model returns `sua_dieu` (clause-level ops) and/or `gia_tri`.
  `dung_ban_thao_tong_quat` applies `sua_dieu` to the stored `clauses`
  (unchanged clauses stay verbatim by construction), rebuilds and carries fills
  when the list changed (§3), merges new `dien` ops, then `ban_thao.sua` under
  `TRAN_SUA` like any chat edit. Nothing changed → the existing draft is the
  turn's card (the khuôn `co_san` rule), no version.
- "cho tôi xem bản thảo" keeps G7 Q3: `moi_nhat_tren_khuon` already matches a
  khuôn mẫu draft (`viec_id IS NOT NULL`), zero model calls.
- Download, Lùi, version reads: unchanged routes. Download names drop " - đã
  điền" for khuôn mẫu (`routes_ban_thao._tai_ve_dau` gets `co_doi=False` when
  `nguon = 'khuon_mau'`).

## §5 Existing HTML drafts and XemTruocA4

- Rows already in `ban_thao` are not converted. `XemTruocA4` and `xuat-tep.ts`
  `xuatWord`/`xuatPDF` stay mounted for versions whose `khuon` is null only:
  legacy drafts and their old versions (Lùi), and drafts written from a tài liệu
  without khuôn gốc.
- A conversation whose newest tổng quát draft is a legacy HTML draft keeps the
  HTML schema for its edits (decided before the call from the light row), so an
  old draft is never half-converted.
- New drafts never render through `XemTruocA4`. No code is deleted this wave;
  removal waits until no path yields an HTML draft (the two exceptions below are
  owner decisions).
- Named exceptions that stay HTML: drafting from an image upload or an upload
  stored before migration 036 (their tables and images are not expressible in the
  builder), and the standalone form workspace (`KhongGianSoanThao`,
  `POST /soan-thao`), which is stateless and has no conversation for a viec
  (`viec_doc_tai_lieu.hoi_thoai_id` is NOT NULL).
- The legacy checklist-in-chat path (`gom_du_kien` → `n_dung_ban_thao`, and
  `ban_thao.dung_lai` behind `POST /ban-thao/{id}/dung`) is moved onto the same
  builder in D4c: the clauses from `draft_generate` become `dieu`, the frame
  comes from the registry, the căn cứ lines are already in state. Visible
  consequence: the per-mục "Sửa" drawer (`DrawerSuaMuc`) no longer shows on docx
  versions (the stage hides the mục column when `khuon !== null`); editing is by
  chat and on the page, as the owner asked.

## §6 Model contract

One strict JSON schema (`hieu_tai_lieu.schema_khuon_mau`), every field
required, `null` when unused:

```json
{
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

`tieu_de`, `bo_cuc`, `ben`, `can_cu` are read only for tổng quát (no registry
entry); a registry type takes them from data. `dieu` is the create shape,
`sua_dieu` the edit shape (`dieu` numbers are the current Điều numbers; `them_sau`
with 0 inserts first). Enums: `key` ∈ the checklist's `muc` keys (else read as
null), `truong` ∈ the field catalog, `ben` ∈ the entry's party keys.

Validation (`hieu_tai_lieu.kiem_khuon_mau`, pure, 0 token):

- Clause text: each paragraph through the existing HTML value net
  (`lam_sach_van_ban` over a `{muc:[{ten, khoi}]}` view): a value not in
  `_nguon_soan` (user words, hồ sơ, allowed memory, the open draft's `document`)
  becomes "……"; a clause still caught by `bo_nho._vuong_luoi_chan` (Điều/Khoản
  numbers, document numbers, identity traces) is dropped and counted. Control
  characters, `⟦`, `¶`, `{{` removed; caps: ≤ 30 Điều, ≤ 12 paragraphs per Điều,
  ≤ 2000 characters per paragraph; an empty result creates nothing
  (`KHONG_SOAN_DUOC`).
- Frame values: `gia_tri` becomes `dien` ops after the build and goes through
  `kiem_phep_sua` with `_nguon_nguoi` (user words and hồ sơ without `suy_dien`:
  the stricter khuôn rule, since party identities are exactly what owner rule B2
  protects). Dropped values feed `khong_dat`, filtered to the user's words, and
  are named ("Chưa đặt được: «…»").
- Mandatory clauses: `checklist.check_completeness` on the `dieu` keys, same
  `khong_bat_buoc` and `muc_do_thieu` as `draft_audit`. On create, each missing
  mandatory `muc` is inserted at its checklist position as "Điều n. <muc.ten>"
  with one "……" paragraph — the draft always has every clause the law requires,
  empty rather than invented. On edit, nothing is re-added; a missing clause is a
  finding. `audit_report` = `{dat, completeness, so_dieu_khoan, findings (with
  can_cu duong_dan), muc_kiem: "tong_quat"}`; each clause keeps its `can_cu` in
  `clauses` for the openable căn cứ of item 3.
- Answer (assemble, 0 token): "Bản thảo <tên> (N trang) đã sẵn sàng: mở bản thảo
  để xem, tải Word hoặc PDF." + "Còn trống: «…»" from `khuon.cho_trong` minus the
  version's `dien` + "Điều còn trống vì luật đòi: «…»" + dropped fills + the
  private-document note "Thể thức theo tập quán, tham khảo Phụ lục I Nghị định
  30/2020/NĐ-CP" for types NĐ 30 does not bind. It only names ops present in the
  saved version (owner: never claim a fill that did not happen).

## §7 Registry

```
config/khuon_mau/_truong.yaml     field catalog: key → label (ho_ten "Họ và tên", ngay_sinh,
                                  gioi_tinh, so_dinh_danh "Số định danh cá nhân", noi_cu_tru,
                                  dia_chi, dien_thoai, thu_dien_tu, ten_to_chuc,
                                  ma_so_doanh_nghiep, dia_chi_tru_so, nguoi_dai_dien, chuc_vu,
                                  so_tai_khoan, ngan_hang); an entry may override a label with
                                  the official form's exact words
config/khuon_mau/<loai>.yaml      one per type, `loai` = the checklist id when one exists
```

```yaml
loai: don_khoi_kien
ten: đơn khởi kiện
tieu_de: ĐƠN KHỞI KIỆN
bo_cuc: don
nguon:
  loai: mau_chinh_thuc            # mau_chinh_thuc | tuong_tu | tu_dung
  van_ban: "Nghị quyết 01/2017/NQ-HĐTP, Mẫu số 23-DS"
  url: https://www.toaan.gov.vn/webcenter/ShowProperty?nodeId=%2FUCMServer%2FTAND279888
  sha256: null                    # D2 fills it from the downloaded file
  ghi_chu: "Tên Toà án để trống: Toà án nhân dân khu vực thay Toà cấp huyện (NQ 01/2025 Đ7.1)."
the_thuc: {co_quan: false, so: null, dia_danh_ngay: dau, kinh_gui: "Toà án nhân dân ……",
           can_cu: false, noi_nhan: null, ket_thuc: null}
ben:
  - {khoa: nguoi_khoi_kien, vai: "Người khởi kiện", truong: [ho_ten, ngay_sinh, so_dinh_danh, dia_chi, dien_thoai, thu_dien_tu]}
  - {khoa: nguoi_bi_kien, vai: "Người bị kiện", truong: [ho_ten, dia_chi, dien_thoai, thu_dien_tu]}
muc_co_dinh:                      # fixed body sections in the form's own words; key ↔ checklist muc
  - {key: yeu_cau, nhan: "Yêu cầu Toà án giải quyết những vấn đề sau đây:"}
ky: [{vai: "NGƯỜI KHỞI KIỆN", ghi_chu: "(Ký, ghi rõ họ tên hoặc điểm chỉ)", ho_ten_tu: nguoi_khoi_kien}]
```

Official files are recorded (URL + sha256 + page) and not committed by default;
D2 commits one only if a test needs it, with its source in the entry (forms
annexed to legal normative documents: Luật SHTT Điều 15). Loader:
`khuon_mau.cac_loai()` / `khuon_mau.nap(loai)` (lru_cache, fail at load on an
unknown `bo_cuc`, field key or party key, like `load_checklist`).

Mapping (from `mau-hien-co.md`; `bo_cuc` / source):

| Types | bo_cuc | Source |
|---|---|---|
| don_khoi_kien | don | mau_chinh_thuc, Mẫu 23-DS NQ 01/2017 |
| don_khieu_nai | don | mau_chinh_thuc, Mẫu 01 NĐ 124/2020 |
| cong_van | hanh_chinh (công văn) | mau_chinh_thuc, NĐ 30 Mẫu 1.5 |
| quyet_dinh_bo_nhiem | hanh_chinh (quyết định) | mau_chinh_thuc, NĐ 30 Mẫu 1.2 |
| quy_che_noi_bo | hanh_chinh (kèm theo) | mau_chinh_thuc, NĐ 30 Mẫu 1.3 + kèm theo |
| ban_tu_khai, don_yeu_cau, don_xin_nghi_viec, van_ban_giai_trinh | don | tuong_tu Mẫu 23-DS / NĐ 124 Mẫu 01 (don_yeu_cau until D2 reads NQ 04/2018) |
| giay_uy_quyen | don, two signers (cá nhân); a `giay_uy_quyen_to_chuc` entry uses hanh_chinh Mẫu 1.4 | tuong_tu NĐ 124 Mẫu 02 / NĐ 30 Mẫu 1.4 |
| bien_ban_hop_hdqt | hanh_chinh (biên bản) | tuong_tu NĐ 30 Mẫu 1.9 |
| quyet_dinh_cham_dut_hdld, quyet_dinh_ky_luat | hanh_chinh (quyết định) | tuong_tu Mẫu 1.2 |
| quyet_dinh_hdqt | hanh_chinh (nghị quyết/quyết định) | tuong_tu Mẫu 1.1 |
| noi_quy, quy_che_dan_chu | hanh_chinh (kèm theo) | tuong_tu Mẫu 1.3 kèm theo |
| hdld, hop_dong_thu_viec | hop_dong | tuong_tu NĐ 145/2020 Mẫu 01/PLV |
| hop_dong_dich_vu, _gia_cong, _hop_tac, _mua_ban, _mua_ban_tai_san, _nguyen_tac, _thue_tai_san, _uy_quyen, _vay, thoa_thuan_bao_mat, thoa_thuan_cham_dut_hdld | hop_dong | tuong_tu NĐ 96/2024 Phụ lục II layout |

New types (D3; each new contract also gets `config/checklist_<loai>.yaml` with
the verified clauses of `hop-dong.md`): `hop_dong_dat_coc`,
`hop_dong_van_chuyen_tai_san`, `hop_dong_van_chuyen_hanh_khach`,
`hop_dong_tang_cho_tai_san`, `hop_dong_chuyen_nhuong_quyen_su_dung_dat`,
`hop_dong_dich_vu_bat_dong_san` (hop_dong, buildable now); đơn and giấy tờ from
history (`don_xin_tam_hoan_nvqs`, `don_xin_hoc_lai`, `ban_kiem_diem_ca_nhan`,
`bien_ban_hop`, `giay_tiep_nhan_thuc_tap`, `phieu_danh_gia_thuc_tap`,
`ke_hoach_thuc_tap`) as registry entries without a checklist unless a law lists
their contents. Blocked until F1 loads the law: `hop_dong_thue_nha_o`,
`hop_dong_mua_ban_nha_o` (Luật Nhà ở 27/2023 shallow), hôn nhân gia đình types
(Luật Hôn nhân và gia đình).

## §8 Tests and end-to-end proof

Focused, no DB, no paid model (fake LLMs), TDD order:

| File | Proves |
|---|---|
| `tests/test_services/test_khuon_mau.py` | page setup values; exact quốc hiệu/tiêu ngữ strings and runs; no `{{`, `⟦`, `¶`, `[…]` in any part; same spec → same bytes; `doc()` re-read: every party field is one `tab` blank with its label, the date line gives blanks labelled "ngày/tháng/năm", header and signature tables have `bang_vien` False and no `o`; the field map resolves every `(ben, truong)` to a blank; `ap_dung_docx` fills every blank with an empty `bo_qua`; Điều numbered 1..n, `ten` numbers stripped |
| `tests/test_services/test_khuon_mau_registry.py` | every `config/khuon_mau/*.yaml` loads; every checklist type has an entry; `nguon.url` host is official (`*.gov.vn`, `vbpl.vn`, `datafiles.chinhphu.vn`, `congbao.chinhphu.vn`) or `nguon.loai` is `tu_dung`/`tuong_tu` with a reason |
| `tests/test_agents/test_kiem_khuon_mau.py` | unsourced number in a clause → "……"; a clause citing "Điều 473" dropped; unknown `key` → null; missing mandatory `muc` inserted with "……" on create, finding only on edit; `gia_tri` not in the user's words dropped and named; `sua_dieu` keeps untouched clauses byte-identical |
| `tests/test_services/test_mang_phep_sang.py` | party fills carry across a rebuild that adds a Điều (signature shifts); a fill inside a rewritten paragraph is dropped and reported |
| `tests/test_agents/test_dung_ban_thao_khuon_mau.py` | create persists viec `nguon='khuon_mau'` + khuon_goc + v1 with `dien` ops (service calls monkeypatched); edit with `sua_dieu` → new viec, carried ops, `tang=1`; values-only edit → same viec; >10 pages or `qua_tai` → nothing saved, no traces row |
| `tests/test_agents/test_assemble_khuon_mau.py` | answer names only saved fills, lists "Còn trống", never "tệp bạn tải lên", never ⟦n⟧ |
| `tests/test_agents/test_route_khuon_mau.py` (never `test_route.py`) | the guard as a pure function of `route.py`, no LLM: verb + khuôn mẫu draft → `soan_thao`; a question stays Q&A; an attachment or an HTML/upload draft leaves the router's verdict; accent-aware |
| `tests/test_services/test_khuon_mau_trang.py` | gated on `soffice` like `test_dung_trang.py`, run sequentially: every registry type with a sample spec renders ≤ 10 pages, quốc hiệu on one line (`pdftotext -tsv`), page 1 without a number and page 2 with "2", `/trang` probe positions every party blank |
| `tests/test_services/test_migration_041.py` | `pytest.mark.integration`, Integrate stage only, run by explicit path: column, default, CHECK, idempotent re-run |
| `frontend/scripts/kiem-khuon-goc.ts` (run by `npm run kiem`) | `khuonHopLe` keeps `nguon`, defaults to `tai_len`; `phuDeKhuon` wording per `nguon` |

End-to-end proof:

1. Integrate stage, fake LLM, real DB, one API test run by explicit path
   (`tests/test_api/test_khuon_mau_luot.py`, integration): create turn →
   `khuon.nguon == 'khuon_mau'`; `GET /ban-thao/{id}/trang` → pages + positioned
   blanks; `PATCH /o-dien` → v2; chat edit with `sua_dieu` → v3 on a new viec with
   v2's fill still present; `POST /lui` → v2 and `GET /trang?phien_ban=2` → 200;
   `/tai-xuong?dang=docx` re-reads with `doc()` and has no marker; `dang=pdf`
   starts `%PDF`; the conversation's tài liệu list and the daily document count
   do not include the khuôn mẫu viec.
2. Wave V, owner's budget: hợp đồng thuê tài sản, đơn khởi kiện, công văn and one
   tổng quát type in the real app, page images side by side with the official
   forms (D2 renders), each Word download opened in Microsoft Word on the owner's
   Mac (no repair prompt, same page count); screenshots in `.tham-dinh-shots/`.

Commands: `KLAW_BO_NHO_NEN=false KLAW_SUPABASE_URL= .venv/bin/python -m pytest -q
<files>`; the CI lane of the wave brief; `ruff check src/ tests/ scripts/`;
`ruff format --check` on changed files; `npm run typecheck && npm run kiem`;
`prettier --check` on changed frontend files.

## Files to change

| Wave | File | Change |
|---|---|---|
| D3 | `config/khuon_mau/_truong.yaml`, `config/khuon_mau/<loai>.yaml` (29 + new) | registry data |
| D3 | `config/checklist_<new contract>.yaml` | new checklists (verified căn cứ) |
| D4a | `src/services/khuon_mau.py` (new) | registry loader + `dung_docx` builder |
| D4b | `migrations/041_viec_doc_nguon.sql` (new), `src/main.py` | column; `"041"` in `MIGRATIONS_KHOI_DONG` |
| D4b | `src/services/tai_lieu.py` | `tao_viec(nguon=…)`; `nguon = 'tai_len'` in `tai_lieu_cua_hoi_thoai`, `da_dung_hom_nay` |
| D4b | `src/services/ban_thao.py` | `nguon` in `_SQL_KHUON*`, `_khuon_tu` and the light row of `_SQL_MOI_NHAT_NHE`; upload key in `_SQL_MOI_NHAT*`; `luu_khuon_mau`; `mang_phep_sang`; `tom_tat_khuon_mau`; `sua(doi=…)`; `sua_o_dien` document for khuôn mẫu |
| D4b | `src/api/routes_ban_thao.py` | download name without " - đã điền" for khuôn mẫu |
| D4c | `prompts/hieu_tai_lieu.v3.md` (new) | khuôn mẫu drafting rules |
| D4c | `src/agents/nodes/hieu_tai_lieu.py` | `schema_khuon_mau`, `kiem_khuon_mau`, v3 selection in `soan_tu_do` |
| D4c | `src/agents/graph_tra_cuu.py` | DB prep for the v3 turn; "newest khuôn mẫu draft" rule in `n_hieu_tai_lieu` |
| D4c | `src/agents/nodes/route.py` | fill/edit guard after `ep_meta`; type enum from `khuon_mau.cac_loai()` (eval re-run) |
| D4c | `src/agents/nodes/dung_ban_thao_tong_quat.py` | khuôn mẫu create/edit branch |
| D4c | `src/agents/nodes/assemble.py` | branch on `khuon.nguon`; khuôn mẫu answer |
| D4c | `src/agents/graph_tra_cuu.py::n_dung_ban_thao`, `src/services/ban_thao.py::dung_lai` | checklist-in-chat path onto the builder |
| D4d | `frontend/src/lib/klaw.ts` | `KhuonBanThao.nguon`, `khuonHopLe` |
| D4d | `frontend/src/components/soan-thao/SanKhauBanThao.tsx` | "Rút gọn / Trang trọng hơn / Soát lại theo luật" also for khuôn mẫu; page label "Các trang của bản thảo — bấm vào chỗ trống để điền" |
| D4d | `frontend/src/lib/khuon-goc.ts` | `phuDeKhuon`: "Bản thảo · N trang · còn K chỗ trống" for khuôn mẫu |

No new Python or npm dependency.

## Risks And Recovery

- LibreOffice cost: one extra render per build or rebuild (≈1–2 s, one of the
  three shared slots); `qua_tai` answers plainly and saves nothing. Ponytail:
  reuse that render for the first `/trang` when measured slow.
- 10-page cap (`ck_khuon_goc_so_trang`) applies to generated drafts; a long nội
  quy may hit it and is refused with a message (owner decision below).
- Rebuild drops a fill inside a rewritten paragraph; the answer names it. Frame
  fills always carry.
- Liberation Serif vs Times New Roman: page counts vs Word measured in wave V.
- Router enum change shifts routing: eval re-run after F2, as planned.
- Recovery: each wave merges `--no-ff`; `git revert -m 1 <merge>`. Migration 041
  is additive; the column can stay if the code is reverted.

## Open Owner Decisions

1. Căn cứ wording: the 2026-09-28/29 decisions print the full number and date for
   every document ("Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm
   2015"); Phụ lục I cites a Luật or Pháp lệnh by name without its number
   (`the-thuc.md` §3, "Viện dẫn"). Default: keep the owner's decision.
2. Contract number line: `Số: ……/……` (NĐ 96 model, default) vs the decision's
   example `…/…/HĐTTS`; HĐLĐ with or without Số and date line (Mẫu 01/PLV has
   neither).
3. Raise the 10-page cap for generated drafts (a CHECK change, one migration).
4. Official wording kept verbatim where a form still says "Số CMND/Hộ
   chiếu/Thẻ căn cước công dân" (NĐ 124 Mẫu 01) or relabelled.
5. Move the standalone form workspace (`POST /soan-thao`, `KhongGianSoanThao`)
   onto the engine (it needs a conversation), and whether drafting from an image
   upload should also produce a docx.
6. On a conversation with an uploaded khuôn gốc, a request for a different
   document still answers `van_ban_khac`; building a khuôn mẫu there costs a
   second model call.

## Progress

- [x] D1 design written (this file).
- [ ] D1 review.
- [ ] D3 registry + new checklists.
- [ ] D4a builder, D4b storage, D4c graph, D4d frontend.
- [ ] Integrate: migration 041, integration tests by path, e2e API test.
- [ ] V: real-app check, Word check, eval re-run.
