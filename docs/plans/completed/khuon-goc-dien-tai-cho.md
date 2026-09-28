# Execution Plan: Show an uploaded document as uploaded, and fill it in place

Date: 2026-09-26

## Status

Completed 2026-09-27. Decisions settled with the owner on 2026-09-26 (Q1–Q20)
and refined by owner feedback on 2026-09-27; execution delegated to agents
without a further approval gate, by the owner's instruction: "tự động thực thi vs
agent và sửa đổi, thực thi plan với agent luôn, ko cần tôi duyệt". Nothing pushed
or deployed.

## Outcome

Observable in the real app once complete:

1. Uploading `BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx` and opening
   **Bản tải lên** shows two pages that match the file page for page.
2. A `.docx`, `.doc`, digital PDF or scanned PDF of up to 10 pages is accepted;
   an 11-page one is refused at upload with a message naming the 10-page limit,
   and that refusal does not count against the daily document quota.
3. Asking KLAW to fill the form produces a draft whose pages are the uploaded
   file with the blanks filled: everything KLAW did not touch keeps its position,
   font, borders and page breaks. Blanks KLAW had no value for keep their dots and
   are listed in the chat answer.
4. Any blank is filled on the page itself: clicking it opens it for typing, and
   Enter, Tab or leaving it saves that blank as a new version on the existing
   version bar (fill saves do not count toward the edit cap); the pages re-render
   after the last save, and **Lùi** walks back.
5. Downloads: the filled `.docx` (opens in Microsoft Word without a repair
   prompt) plus a PDF for docx/`.doc` inputs; the filled PDF for PDF inputs.
6. The whole document (≤10 pages) reaches the model; nothing is trimmed silently.
7. Drafts without a source, and documents uploaded before this change, still use
   the HTML A4 preview, which now flows across sheets and draws source images.

## Context

- Decision: `docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md` (partly
  supersedes 2026-09-16 and item 3 of 2026-09-18). Glossary: **khuôn gốc** in
  `CONTEXT.md`.
- Previous fidelity work: `docs/plans/active/trung-thuc-bieu-mau.md` (the reader
  ruler `eval/run_trung_thuc.py`, 99.84% by declaration).
- Grounding evidence (session scratchpad, not reproducible from the repo until
  ported into tests): an ElementTree round trip that keeps the root start tag
  verbatim is pixel-identical on all 8 owner forms; `soffice --convert-to pdf`
  is 0.8–2.0 s per document; `pdftoppm -r 110` is 0.1–0.5 s; a pypdf overlay
  renders Vietnamese diacritics correctly.
- Owner forms live in `~/giấy tờ thực tập/` and are never committed; tests gate on
  the folder existing (`tests/test_services/test_doc_tai_lieu_doc.py:37-38`).

### Root causes this plan removes (confirmed 2026-09-26)

| Symptom | Cause |
|---|---|
| Draft stuck on one sheet | `clauses_tu` drops `trang` and `anh` (`src/agents/nodes/dung_ban_thao_tong_quat.py:92-106`); overflow split only between sections, sheets `overflow-y-auto` (`XemTruocA4.tsx:835,870`) |
| "Renders like a table" | model rewrites every block; layout re-attached by verbatim text lookup; unmatched tables forced `vien: True` with a shaded header row (`hieu_tai_lieu.py:2128-2137`, `XemTruocA4.tsx:1030-1062`) |
| Wrong page count | pages = declared breaks only; Evaluation Form is 4 pages, read as 1 |
| Whole document not understood | `loc_don_vi` trims above 30,000 chars; per-document cost cap ≈25,000 chars |
| Source images missing | image URL is relative, lacks `/api/v1`, and is fetched without the Bearer header |
| Scanned PDF > 2 MB refused | global 2 MB body cap (`src/main.py:145`) under a UI that says 20 MB |

## Scope

In scope:

- Storage of khuôn gốc (migration `036`), true page count, 10-page cap.
- Reader: an OOXML locator and blank records per đơn vị văn bản; word boxes for
  digital PDF; OCR boxes for scanned PDF.
- Edit-operation engine for docx (lxml) and PDF (reportlab overlay merged with
  pypdf).
- Graph: edit operations instead of `van_ban` for a document with a khuôn gốc.
- API: page images, downloads, fill-field save, re-extract from the stored file.
- Frontend: page-image viewer, **Bản tải lên**, fill-field panel, downloads.
- HTML path fixes: `trang`/`anh` in `clauses_tu`, authed source images, sheet
  overflow split at block boundaries.
- Docker (`poppler-utils`, `tesseract-ocr`, `tesseract-ocr-vie`,
  `fonts-crosextra-carlito`, `fonts-crosextra-caladea`), CI apt step (owner
  authorised 2026-09-26, Q18), `lxml` and `reportlab` in `requirements.txt`.
- Ruler: page count and per-page image comparison, LibreOffice automatic and
  Microsoft Word through `osascript` on the owner's Mac.

Out of scope:

- The checklist drafting path (`gom_du_kien` → `dung_ban_thao`): named exception,
  it drafts KLAW's own form from facts.
- Hard-deleting `ban_thao` / `luot_hoi_thoai` on conversation delete (issue).
- Inserting or deleting paragraphs in a PDF.
- Image uploads (`.png`/`.jpg`…) as khuôn gốc; they keep today's OCR path.
- Pushing to `origin`, deploying to Railway.

## Contracts

Every phase codes against these; changing one is a plan edit first.

### Đơn vị văn bản additions (persisted in `viec_doc_tai_lieu.don_vi`)

Optional keys, present only when the source states them (`**({"k": v} if v
else {})`), each with an explicit key in `_hang_don_vi` and a tolerant reader:

- `dia_chi` (docx): `{"phan": "word/document.xml" | "word/header1.xml" | …,
  "chi_muc": [int, …]}` — element-child indices from the part's body (or
  `w:hdr`/`w:ftr` root) down to the unit's container (`w:p`, or `w:tc` for a
  cell). Pinned at read time; the applier never re-walks with newer code.
- `cho_trong`: list of blanks in reading order,
  `{"so": int, "kieu": "cham" | "tab", "doan": int, "dau": int, "cuoi": int,
  "nhan": str}` — `doan` is the paragraph index inside the unit (0 for a body
  paragraph), `dau`/`cuoi` are offsets into that paragraph's RAW concatenated
  `w:t` text (not the stripped `noi_dung`), `nhan` is the display label:
  `doc_tai_lieu.nhan_sach` of at most 60 chars of the text before the blank
  (long label → drop a trailing `(nếu có)`/`(ghi rõ …)` note, then if still
  long the tail after the last `,;:()`/sentence break, no trailing `:`,
  a letterless label → previous blank's label + ` (sau /)`, `""` when unknown;
  the same pure function runs again in `ban_thao.cho_trong_khuon`, so rows
  stored before it read clean too). A PDF line that is only dots takes the tail
  of the line above on the same page. `kieu: "tab"` is a `w:tab` whose stop has
  a dot leader.
  For PDF: `{"so", "kieu": "cham", "hop": [x0, y0, x1, y1], "co_chu": float,
  "nhan"}` in PDF points on the unit's `trang`, in poppler display space: origin
  at the top-left of the page's MEDIA box (not the CropBox), after `/Rotate`.
- `kieu: "o"` (G5, docx body tables only): an EMPTY cell (`doc_tai_lieu.o_rong`:
  no text after `strip`, a `w:p`, not a `w:vMerge` continuation, no drawing,
  picture, object, `mc:AlternateContent`, nested table, `w:sdt` or field) of a
  BORDERED table (`bang_vien`; a borderless table lays out a letterhead or a
  signature pair and is never a data table), with an address and no other
  blank, under a named column. Column name: the text of the LAST row above the
  first data row whose cell covering that grid column (`w:gridSpan` included)
  has a letter — row 0 is always a header, and a row with no empty named cell
  before the first data row ("(1) (2)", the lower tier of a two-tier header)
  is one too. `{"so": 0, "kieu": "o", "doan": 0, "dau": 0, "cuoi": 0, "nhan":
  "<column> (dòng n)"}`, n counted from the first data row; `nhan_sach` cleans
  the column and keeps " (dòng n)". The unit carries `doan_chu` (the raw empty
  paragraph texts). Measured on the 8 owner forms: BM.M05 24, BM.ĐT.18.05 13,
  BM.ĐT.18.11 5, phiếu đánh giá 5, the other four 0 (47 in all); chấm/tab
  counts unchanged (124).
- Blanks hang only on đơn vị văn bản. A paragraph with no text is not a unit, so
  a text-less dotted or dot-leader continuation line (the lines under
  "Comments (góp ý thêm):") has no blank: it keeps its dots, is never filled and
  is not listed as unfilled. Measured on Evaluation Form: 45 dot-leader tab
  paragraphs, 12 addressable (label + leader), 33 text-less continuation lines;
  the "best strength" and "weakness" questions have only continuation lines, so
  an answer there can come only from `chen_sau` after the label unit. Upgrade
  path, only on an owner request: an optional per-blank locator for following
  text-less sibling paragraphs.
- Fail closed, measured limits: a header/footer paragraph deeper than 16
  element levels or inside `mc:AlternateContent` has no `dia_chi`; a paragraph
  that contains or sits inside a text box / `mc:AlternateContent` has no
  `cho_trong`; a scanned page above 16 Mpx at 200 dpi (about 2× A3) has line
  boxes but no blanks.
- `hop` (PDF, scanned PDF): the unit's line box, same coordinates.
- `doan_chu` (docx): `[str, …]`, the RAW concatenated `w:t` text of every `w:p`
  in `container.iter(w:p)` order on the raw part (the string `cho_trong`'s
  `doan`/`dau`/`cuoi` index; empty paragraphs included), present only when the
  unit has `cho_trong` or more than one paragraph. The tolerant reader reads
  anything but a list of strings as absent. Rows stored before this key have no
  `doan_chu`: the prompt falls back to the `chỗ trống:` list and a `thay` with
  `doan` on a unit that has blanks is refused (`khong_co_doan`); on a
  blank-less container with several paragraphs the applier refuses it
  (`khong_co_dia_chi`) instead of writing into raw paragraph 0.
- `noi_dung`, `chi_so`, anchors and every existing counter stay byte-identical;
  each reader change ships the equivalence test pattern of
  `tests/test_services/test_doc_tai_lieu_trang.py:193-231`.

### Edit operations (`phep_sua`)

```json
{"loai": "dien", "don_vi": 12, "cho_trong": 0, "gia_tri": "Nguyễn Văn A"}
{"loai": "thay", "don_vi": 14, "noi_dung": "…"}
{"loai": "thay", "don_vi": 3, "doan": 0, "noi_dung": "…"}
{"loai": "chen_sau", "don_vi": 14, "noi_dung": "…"}
{"loai": "xoa", "don_vi": 15}
```

- `dien` replaces only the blank's characters (possibly spanning runs) with the
  value in the formatting of the blank's first run; a `tab` blank inserts a run
  before the `w:tab` so the leader shrinks as in Word. An `o` blank appends ONE
  run to the cell's first paragraph, its `w:rPr` a copy of that paragraph mark's
  `w:pPr/w:rPr` without revision marks (none: no `w:rPr`, the paragraph and
  table styles apply); the cell must still be `o_rong` on the stored bytes, else
  `cho_trong_da_doi`.
- `thay` keeps `w:pPr` and the first run's `w:rPr`; `chen_sau` clones them;
  `xoa` removes the paragraph (a cell keeps one empty `w:p`).
- `thay` with `doan` (docx only, one line; `doan` is the `container.iter(w:p)`
  index, the `¶n` of the prompt) replaces only that paragraph's text: it keeps
  THAT paragraph's `w:pPr`, bookmarks and text-less drawings (the rule under the
  BM.M05 letterhead is an `mc:AlternateContent` shape), and writes one run in
  its first text run's `w:rPr` where that run stood. The unit's other paragraphs
  and their blanks stay. Refused: a paragraph index the container lacks, or a
  stored paragraph count (`doan_chu`, absent = one) that differs from the
  container's `w:p` count (`khong_co_dia_chi`), a paragraph in or holding a text box, field, comment or
  note reference, or text inside a drawing (`khong_an_toan`), several lines
  (`khong_hop_le`). A second `thay` on the same paragraph, a whole-unit
  `thay`/`xoa` together with a paragraph `thay` on one unit, and a `dien` into a
  replaced paragraph are `xung_dot`. PDF refuses `doan` (`loai_khong_ho_tro`).
- Merge (`ban_thao.gop_phep_sua`): a paragraph `thay` keys on `(don_vi, doan)`;
  it and a whole-unit `thay`/`xoa` of the same unit displace each other (later
  wins); it removes only the `dien` of blanks in that paragraph (the blank →
  paragraph map, `ban_thao.doan_cua_cho`, comes from the stored units, or from
  the turn's `cho_trong[].doan`). `cho_trong_khuon` and `assemble` exclude only
  that paragraph's blanks. A chat turn's non-empty `dien` that the merge removes
  (its unit or paragraph is `thay`/`xoa`-ed) goes to `bo_qua` as `da_viet_lai`,
  never lost silently; a turn whose proposals all ended that way answers
  `KHONG_DOI_KHUON`, not the existing-draft card.
- PDF accepts `dien` and `thay` only; `thay` must fit the unit's box at ≥70% of
  its font size or the operation is refused.
- Prompt (khuôn gốc, docx): each unit's text shows every fillable blank IN PLACE
  as `⟦so⟧` (`⟦so=«giá trị»⟧` when the open draft filled it) and, for a unit
  with several paragraphs, `¶doan` before each non-empty paragraph. A unit whose
  positions cannot be proven (no `doan_chu`, paragraphs not joining to
  `noi_dung`, a blank no longer dots at its offsets) keeps the `chỗ trống:` list
  line; a marker is never placed by guess. A paragraph (or unit) the open draft
  `thay`-ed shows its current text and none of its blanks.
- The applier is pure: `(bytes, don_vi, phep_sua) -> (bytes, bao_cao)`; an
  invalid operation is skipped and reported, never guessed.
- `dien` values must pass the provenance check (`_co_trong_nguon` over
  `hieu_tai_lieu._nguon_nguoi`: the USER's text this conversation — `cau_hoi_goc`,
  `query`, `cau_hoi_day_du` —, hồ sơ except `suy_dien` entries, and memory values
  the user asked for this turn) and the memory rules (`_chan_bo_nho`). The
  document's own text, `quan_sat` quotes and the open draft's `document` are NOT
  sources for a new value (owner rule 2026-09-27, Decisions); an op identical to
  one of the open version's ops is not new and is skipped silently (the merge
  keeps it). `_vuong_luoi_chan`'s identifier rule does not apply to `dien`
  values — a phone number the user stated is a legitimate fill — but its
  Điều/Khoản rule still applies to `thay`/`chen_sau` text.
- Every `thay` (with or without `doan`, on any unit) and every `chen_sau`: every
  run of consecutive words it ADDS — relative to that paragraph's (or unit's)
  original text for `thay`, to nothing for `chen_sau` — case- and
  diacritic-insensitive word-SEQUENCE comparison (`difflib.SequenceMatcher`: a
  word of the replaced text repeated or moved elsewhere is added) — must pass
  `_co_trong_nguon` over the same source set as `dien`, whole run at a time, else
  `khong_nguon` (replaces the `co_cho_trong` refusal). Numbers and `Nhãn: giá
  trị` values the replaced text keeps in place are not new. `doan` belongs to `thay` only: a `xoa` or
  `chen_sau` carrying one is `sai_hinh_dang`.
- `khuon.yeu_cau` (strict, required): `tao_lai` (recreate THIS document as it is:
  every proposed op is discarded before validation; a create turn saves version
  1 with `phep_sua: []`, byte-identical download; on an existing draft that is
  already the upload it is the no-change case and returns that draft, on a filled
  one it saves a new version with `phep_sua: []`, not counted toward `TRAN_SUA`),
  `dien_sua` (fill or edit it; missing or
  unknown values read as this), `van_ban_khac` (a different document: nothing
  built). `khuon.khong_dat: [str]` (strict, required): values the user gave that
  the model could not place; kept only when a case- and diacritic-insensitive
  substring of the user's text and not inside a kept op; `assemble` lists them.
  The values of the turn's DROPPED ops (a `dien` value, each run a `thay`/
  `chen_sau` adds) go through the same filter first (G5), so a user's value
  whose op the checks dropped is always named ("Chưa đặt được: «…»"), also in
  the no-change and other refusal answers. `coverage_note` and every answer name
  a blank by its label, else "một thay đổi" — never a unit index ("đoạn 29").
- Date split (deterministic, docx rows with `doan_chu` only): a `dien` whose value
  is a full date (`d/m/yyyy`, `dd/mm/yyyy`, `-` or `.` separators) into blank k
  becomes three `dien` (day, month, year) when blanks k, k+1, k+2 of the same
  paragraph are separated only by `/`, or read `ngày … tháng … năm …` with k the
  `ngày` blank — unless the turn itself fills k+1 or k+2.
- Plausibility (model output only): a `dien` into a blank whose label is a short
  number label (`Số`, `Số:`, `No.`) or ends with `ngày`/`tháng`/`năm` takes a
  value with a digit, else `khong_khop_nhan`; so does an `o` blank whose column
  starts with `Mã`, `Số`, `STT` or `TT` (G5), and a `thay` (any `doan`) or
  `chen_sau` on that cell's unit, whose added words go into the same column
  (G5 review). No other label heuristic.
- Prompt: an `o` blank shows as `⟦0⟧` inside its cell unit plus a `chỗ trống:`
  line with its label (`[A-30] (tr. 2, bảng 2 hàng 2 cột 4) ⟦0⟧` /
  `chỗ trống: 0 «Họ và tên (dòng 1)»`); the rules say a list table is filled
  row by row, each value in the column that names it.

### Storage

- `khuon_goc`: `viec_id uuid PRIMARY KEY REFERENCES viec_doc_tai_lieu(id) ON
  DELETE CASCADE`, `dinh_dang text CHECK IN ('docx','pdf')`, `noi_dung bytea`,
  `so_byte int CHECK (so_byte = octet_length(noi_dung) AND so_byte <= 20 MB)`,
  `so_trang int CHECK (so_trang BETWEEN 1 AND 10)`, `kho jsonb` (per-page
  `[w_pt, h_pt]`), `tao_luc timestamptz`. Owner reads JOIN `viec_doc_tai_lieu`.
- `ban_thao` gains `viec_id uuid NULL REFERENCES viec_doc_tai_lieu(id) ON DELETE
  SET NULL` and `phep_sua jsonb NULL` (migration `037`); version snapshots in
  `phien_ban_truoc` carry `viec_id` and `phep_sua` (HTML snapshots keep their
  old shape). A version IS its full op list on its viec: `sua` writes the ket's
  pair, `lui` restores the snapshot's pair, and every write stores `viec_id`
  only when that viec still exists and belongs to the draft's owner (else NULL,
  an HTML version). Rendered PDFs and PNGs are not stored; they are rebuilt on
  demand (ponytail: add a cache table when a measured render is too slow).

### API (all under `/api/v1`, `nguoi_dung_bat_buoc`, another owner = 404)

- `POST /tai-lieu` — unchanged shape; `TaiLieuOut` gains `co_khuon_goc: bool`. A
  refused upload (page cap, format, broken file, converter busy) leaves no
  conversation it opened itself; the page-cap 422 names the file and its real
  page count (`«<tên tệp>» có N trang, vượt giới hạn 10 trang.`).
- `GET /tai-lieu/{viec_id}/trang` — the khuôn gốc as uploaded:
  `{"kho": [[w, h], …], "trang": ["<base64 png>", …], "o": [...]}`, one request
  for every page. `o` (added 2026-09-27, owner feedback "để người dùng trực
  tiếp thao tác trên" the page): `[{"don_vi", "so", "trang": int | null,
  "hop": [x0, y0, x1, y1] | null, "nhan", "gia_tri": str | null}]`, exactly the
  `khuon.cho_trong` set of the pristine file (or of the version, below), in
  reading order; `trang` is a 0-based index into `trang`, `hop` is in points
  from the top-left of that page (the space of `kho`; pixel scale = PNG width /
  `kho[i][0]`) and covers the blank's dots, or its value once filled;
  `gia_tri` is trimmed. PDF: the reader's stored blank box on the unit's page.
  DOCX: measured on the rendered page with a probe copy (Decisions, G1); an `o`
  blank's box is its whole cell, from a probe-only cell shading (Decisions, G5).
  `trang`/`hop` are null only when the position was not measured. Old clients
  ignore `o`.
  A render takes one of the three LibreOffice slots (503 `qua_tai`) and holds at
  most 12 Mpx for the whole document; `kho` is always in (0, 14400] pt. One
  render per account at a time: a second concurrent `/trang` from the same
  account is the same 503 `qua_tai`, so the viewer fetches once.
- `POST /tai-lieu/{viec_id}/doc-lai` `{"loai"}` — re-extract by type from the
  stored khuôn gốc (no re-upload, no new viec, no quota hit). At most
  `so_lan_thu` (FR-037, 3) paid re-extracts per document, then 429; `tong_quat`
  calls no model and is free. The cost estimate (422) and the daily cost cap run
  before the claim, so a refusal leaves the viec as it was.
- `GET /ban-thao/{id}/trang?phien_ban=N` — the filled version, same shape
  (with `o` for that version's op list); the apply, the probe and the render
  are one slot of the same per-account guard (a held slot is 503 `qua_tai`
  before the applier runs). No `phien_ban` (live
  version): `private, no-store`; with `phien_ban`: `private, max-age=3600`
  (version numbers are never reissued). 404: not found/foreign, unknown version,
  HTML version, khuôn gốc deleted. Render errors map like `/tai-lieu/…/trang`
  (503 `qua_tai`/`khong_co_cong_cu`, 422 `tep_hong`).
- `GET /ban-thao/{id}/tai-xuong?dang=docx|pdf&phien_ban=N` — attachment bytes.
  `dang` required. docx khuôn: `docx` = the filled khuôn gốc, `pdf` = its
  LibreOffice render; every branch, applier included, holds the same
  per-account slot; PDF khuôn: `pdf` only, `docx` =
  422. `Content-Disposition: attachment; filename="<ASCII stem> - da dien.<dang>";
  filename*=UTF-8''<stem> - đã điền.<dang>` (stem of `ten_tep`, so a `.doc`
  downloads as `.docx`) for a version with changes; a version whose merged op
  list is empty downloads as the upload itself, `<stem>.<dang>`; `nosniff`,
  `private, no-store`.
- `PATCH /ban-thao/{id}/o-dien` `{"phien_ban", "gia_tri": [{"don_vi",
  "cho_trong", "gia_tri"}]}` (1–500 items, value ≤ 500 chars, `""` clears) →
  `BanThaoOut`. One new version per save, NOT counted in `TRAN_SUA` (`so_lan_sua`
  unchanged; history still keeps the last `TRAN_SUA` snapshots), `audit.sua_tay`;
  a save that changes nothing returns the draft without a version. Every
  refusal is 422 with a Vietnamese string `detail` (stale `phien_ban`, not a
  khuôn draft, unknown blank, multi-line value, an op the applier skips) — the
  `PATCH …/muc` convention, not 409. No render.
- `BanThaoOut` and `BanThaoPhienBanChiTietOut` gain `khuon: {"viec_id",
  "dinh_dang", "so_trang", "cho_trong": [{"don_vi", "so", "kieu", "nhan",
  "gia_tri" | null}]} | null` (default null). `cho_trong` lists only blanks the
  applier can reach (docx: unit has `dia_chi`; PDF: blank has `hop`) and not on
  a unit the version `thay`/`xoa`-ed or in a paragraph it `thay`-ed by `doan`.
- `POST /tai-lieu/{viec_id}/ban-thao` (no body) → `BanThaoOut` with `khuon` —
  opens the fill panel when no model turn filled anything. Explicit user action:
  no model call, no quota row. 200 with the newest draft of this account whose
  live version is on that viec, else 201 with version 1, `phep_sua: []`,
  `document` = `# <ten_tep stem>`. 404 for a foreign/unknown viec or one with no
  khuôn gốc; 401 without login. Concurrent opens serialize on the viec row.
- `GET /tai-lieu/{viec_id}/ban-thao` (G7) → `BanThaoOut` with `khuon`: the newest
  draft of this account whose live version is on that viec. Read-only: no model
  call, no quota, creates nothing. 404 when there is none, for a foreign or
  unknown viec, or an id that is not a UUID.
- Binary responses: `nosniff`, `Cache-Control: private`. Logs carry ids and
  counts only.

## Approach

Phases run in throwaway worktrees under the session scratchpad, one implementer
and one independent reviewer each, then a fix round, then a `--no-ff` merge into
local `main` (`merge: <summary>`). Nothing is pushed. Waves:

| Wave | Phase | Tree | Depends on |
|---|---|---|---|
| A | P1a `clauses_tu` carries `trang`, `anh` | backend node | – |
| A | P1b HTML preview: authed images + overflow split at blocks | frontend | – |
| A | P1c Tooling: Docker, CI apt, requirements, 20 MB upload path, cost cap 0.10, refusal not counted | infra + config | – |
| B | P2a Khuôn gốc storage, true page count, 10-page cap, page routes, re-extract, copy/docstrings | upload/storage | P1c |
| B | P2b Reader: `dia_chi`, `cho_trong` (docx); `hop`, `cho_trong` (PDF word boxes, OCR boxes) | reader | P1c |
| C | P3a docx applier (lxml) | new service | P2b |
| C | P3b PDF / scanned PDF applier (reportlab + pypdf) | new service | P2b |
| D | P4 Graph: ops schema + prompt, validation, `ban_thao` columns, fill save, downloads, memory exclusion, no silent trim | graph + ban_thao | P2a, P3a, P3b |
| E | P5 Frontend: viewer, Bản tải lên, fill panel, downloads, re-extract call | frontend | P4 |
| F | P6 Ruler + Word check + end-to-end capture in the real app | eval + e2e | P5 |

Each phase report states outcome, changed files, validation run with output, and
open risks, and follows the TDD order: failing test first, then code.

## Risks And Recovery

- **Word rejects a filled docx while LibreOffice renders it.** LibreOffice is
  tolerant of broken markup-compatibility declarations; only Word proves the file.
  P3a keeps the root start tag verbatim and P6 opens every filled form in Word.
- **Locator drift.** `dia_chi` is pinned at read time; old rows without it fall
  back to the HTML path, never to a re-walk.
- **Blank shapes vary.** Dots share a `w:t` with the label, span 2–3 runs, or are
  tab leaders; several blanks share a paragraph. The contract addresses a blank by
  unit + index + raw offsets, measured on all 8 forms in P2b.
- **Fonts.** Production has Liberation/Carlito/Caladea, the Mac has Times New
  Roman; page counts can differ between the two. The ruler reports both.
- **LibreOffice load.** Every upload and save costs one of 3 slots shared with
  `.doc` conversion; overload returns the existing `qua_tai` 503.
- **LibreOffice network egress.** Every docx upload and every `GET /trang` of a
  docx runs LibreOffice, whose sandbox does not block the network (decision
  Tradeoffs). Measured 2026-09-27 on LibreOffice 26.2.4 (dev Mac) and 25.2.3 (the
  Dockerfile's base + `libreoffice-writer`): an external linked image (`r:link`)
  is fetched (SSRF), and a `file://` one embeds a server file into the rendered
  PDF. Every soffice run now gets a profile seeded with
  `BlockUntrustedRefererLinks`, which stops both on both versions. The `.doc`
  importer fetched regardless (on main since Phase 13; raw loopback listener:
  `OPTIONS`+`HEAD`+`GET` for `http://`, one TLS handshake for `https://`, none
  for `ftp://`). P2c closed it: the same profile sets a manual proxy to the dead
  loopback port `127.0.0.1:9` and the subprocess env carries `*_proxy` to the
  same port; each layer alone gives zero connections on both versions, and
  `DisableActiveContent` does nothing for this path. Still open: these are
  application-level barriers, not network isolation; a LibreOffice path that
  opens sockets while ignoring proxy settings (none measured) would escape, and
  nothing in the container may listen on `127.0.0.1:9`. OS-level isolation for
  the converter stays the owner's call.
- **Rate limit.** 10 requests / 60 s per IP; page images come in one request.
- **Panel-save dry run.** `PATCH …/o-dien` runs the applier (≤ 1 s, 10-page
  docx) outside the per-account render slot on purpose: that slot refuses at
  once, and a save must not 503 while the preview renders. The draft's row lock
  serializes saves of one draft; one account saving many drafts from many IPs
  still dry-runs in parallel. Add a waiting per-account slot when measured.
- **Scanned PDFs.** Tesseract emits no words for long dotted leaders; blanks are
  located by label-relative placement and pixel runs, and the accuracy is measured,
  not promised.
- **Edit cap.** `TRAN_SUA = 10` caps chat edits (each calls a model); fill saves
  (`PATCH …/o-dien`) call no model and do not count (owner rule, fix/g4-backend
  B6), nor does a `tao_lai` reset to the upload (it edits nothing with a model;
  counting it would lock a capped draft out of the exact upload), so a 30-blank
  form saved blank by blank never dead-ends; every save is
  still one version under the optimistic lock, and history keeps the last
  `TRAN_SUA` snapshots, so **Lùi** reaches at most that far back. A draft opened by `POST
  /tai-lieu/{viec_id}/ban-thao` costs no first-build quota, so later chat fills on
  it are edit turns under `TRAN_SUA`, not `EP_SOAN_THAO` (one draft per viec, and
  each viec already spent `tai_lieu_ngay`). A chat create turn spends one
  `EP_SOAN_THAO` even when it fills nothing (owner 2026-09-27): its version 1 is
  the upload unchanged, so a user who only wants the file back pays one
  first-build, the same as any drafting turn.
- Recovery: each phase is one merge commit on `main`; `git revert -m 1 <merge>`
  undoes it. Migration `036` is additive (new table, nullable columns).

## Progress

- [x] Decisions Q1–Q20 settled; decision record, glossary term, spec notes.
- [x] Wave A — P1a, P1b, P1c (merges `9e4474c`, `8dcc8a9`, `ea86a9b`; CI lane 2163 passed on main).
- [x] Wave B — P2b (`a8fd793`), P2a (`3d3871d`, after a merge-up and a replacement privacy review that found and fixed unbounded re-extracts, a reversed-MediaBox render bypass, uncounted kept files, and LibreOffice fetching linked images).
- [x] Wave C — P3a docx applier (`d2ee30a`), P3b PDF overlay applier (`570c805`); CI lane 2381 passed on main.
- [x] P2c — `.doc` importer egress closed with a dead loopback proxy (`fix/soffice-chan-mang`).
- [x] Wave D — P4a storage/routes, P4b graph edit operations, P2c .doc egress barrier, integrated on `integ/wave-d` and merged (`d32a50b`); CI lane 2437 passed on main.
- [x] Wave E — P5 frontend: page viewer, Bản tải lên, downloads, re-extract without re-upload (`98028af`).
- [x] Wave F — P6 ruler `eval/run_khuon_goc.py` (`de4de72`), copy/touch-target polish (`f911bd6`), owner reversal: a drafting request always drafts (`a1ed1e7`), end-to-end runs in the owner's app (four rounds, defects fed into waves G–G6).
- [x] Wave G — fill on the page: paragraph `thay` by `doan` and label checks
  (`dbbd151`), G1 blank positions on rendered pages (`191872f`), G3 on-page
  filling (`4982040`), label/probe integration fixes, G4 owner-rule fixes
  backend (`5a63e0d`) and frontend (`78dd14a`), integrated on `integ/wave-g`;
  CI lane 2583 passed (only the worktree-only `test_data_raw_VAN_bi_gitignore`
  failure); ruler unchanged on every LibreOffice measure.
- [x] Issue opened for the soft-delete gap (#3).
- [x] G5 backend — empty list-table cells as `o` blanks, dropped user values
  always named, no unit index in answers; the column digit rule also covers a
  `thay`/`chen_sau` on an `o` cell (`fix/g5-backend`, merged `1cb43e7`).
- [x] G5 frontend — the draft stage closes on conversation change, the chat
  scrolls past the composer, the sidebar's Bản thảo list follows the live
  version (`fix/g5-frontend`, merged `5ecded2`).
- [x] Wave G5 integrated on `integ/wave-g5` without conflicts: khuôn test
  files 783 passed; CI lane 2613 passed (only the worktree-only
  `test_data_raw_VAN_bi_gitignore` failure); ruler LibreOffice measures
  byte-identical, `o` 47/47 applied and read back, page count kept 4/4.
- [x] Wave G merged to main (`740c147`), G5 (`9445f54`), G6 send held while a file uploads, with a visible cancel (`5981b44`); ruler re-recorded with Microsoft Word (`cea07b5`).

## Decisions

- 2026-09-26: Label **Bản tải lên**, not "bản gốc", which already means the
  statute's original text in the UI and is on the glossary's avoid list.
- 2026-09-26: `lxml` over ElementTree for writing OOXML: `ET.register_namespace`
  is process-global and raises on `ns\d+` prefixes, unsafe in a threadpool.
- 2026-09-26: `reportlab` for the PDF overlay instead of a hand-built Type0 font:
  the prototype works but embeds the whole TTF and puts glyph-width code in KLAW.
- 2026-09-26: Renders are rebuilt on demand, not stored, until measured slow.
- 2026-09-26: Upload body limit 20 MB for `POST /tai-lieu` only; every other route
  keeps 2 MB.
- 2026-09-26 (P2b review): text-less continuation leader lines keep their dots
  and carry no blank — the existing contract made explicit, not a new key; PDF
  coordinates are media-box space (poppler measured, CropBox ignored). The
  reader's new walks are linear in the part and render one scanned page at a
  time under a pixel cap.
- 2026-09-27 (P2a review): `doc-lai` spends FR-037's retry cap (`so_lan_thu: 3`,
  the value it had before it was dropped for lack of a stored file); a `tong_quat`
  re-extract calls no model and is free. `chi_phi_usd` accumulates per viec. A
  viec that keeps a khuôn gốc always counts against `tai_lieu_ngay`; an upload the
  cost estimate will refuse stores no file, so FR-038 still exempts it. Page
  renders: `kho` validated to (0, 14400] pt (ISO 32000-1 Annex C), 12 Mpx per
  document, `pdftoppm` crops at 2400 px and takes a LibreOffice slot; one
  render per account at a time (the rate limit before `/trang` is per IP, so
  one account on several IPs could otherwise hold all three slots).
- 2026-09-27 (P2a egress): the review's residual-risk finding measured real —
  a docx `r:link` image made LibreOffice fetch the URL (SSRF) or embed a
  `file://` server file into the render. Every soffice run gets a profile seeded
  with `BlockUntrustedRefererLinks`; the `.doc` importer's blind GET stays open
  and is the owner's call (isolation or drop `.doc`).
- 2026-09-27 (P2c): the `.doc` importer's fetch goes through LibreOffice's proxy
  (a live loopback proxy receives `GET http://…/anh.png`), so every soffice run
  now points `org.openoffice.Inet/Settings` (`ooInetProxyType=2`, HTTP/HTTPS/FTP
  name and port, empty `ooInetNoProxy`) and the `*_proxy` env vars at the dead
  port `127.0.0.1:9`. Both layers kept: each alone is enough on 26.2.4 (Mac) and
  25.2.3 (Dockerfile base, aarch64 and amd64); one is LibreOffice's own setting,
  the other the env it honours when the profile sets no proxy. The `.doc` egress
  test is a normal test now. `.doc` stays accepted; network isolation remains an
  optional further layer.
- 2026-09-27 (P4a): one merge for chat edits and panel saves,
  `ban_thao.gop_phep_sua(cu, moi)` — `dien` by `(don_vi, cho_trong)` latest
  wins and `""` clears; `thay`/`xoa` share one key per `don_vi`; `chen_sau`
  deduplicated in order; changed ops keep their position. `ap_phep_sua`
  re-deduplicates before every applier call (PDF is first-wins). A panel save
  dry-runs the applier on the pristine khuôn gốc and refuses when any op lands in
  `bo_qua`. The reader strips `nhan`, so `chuan_hoa_dien` gives every `tab`
  value one leading space.
- 2026-09-27 (P4b review; the empty-create rule is superseded by the owner
  decision of 2026-09-27 below): on a document with a khuôn gốc, a chat turn that asks
  for a different document ("dựa vào hợp đồng này soạn đơn xin nghỉ việc") gets
  no edit-draft of the upload: decision item 3 leaves "a different document" to
  the checklist, so a create turn that ends with no valid operation saves nothing,
  writes no `EP_SOAN_THAO` trace, and points to **Chọn loại văn bản**. Agent
  default under the owner's standing delegation, open for the owner to reverse
  (the reverse keeps an empty draft so the fill panel opens before any value is
  stated). Blanks are filled only by `dien`: `thay` on a unit with a fillable
  blank is refused (`co_cho_trong`; superseded 2026-09-27 by the provenance rule,
  see the fix/dien-dung-o decision below), each `Nhãn: giá trị` value in `thay`/
  `chen_sau` passes the `dien` provenance check, and Điều/Khoản numbers compare
  as whole tokens.
- 2026-09-27 (wave D integration): `gop_phep_sua` is defined once (P4a's body);
  a `thay`/`xoa` on a unit removes every `dien` on that unit, before or after it,
  so the applier, `cho_trong_khuon` and `assemble` agree on what is filled. The
  create-vs-edit target is the newest draft of the conversation whose live
  version has the turn's `viec_id` (`None` = HTML draft), so alternating kinds
  never edit, or overwrite, the other kind. The prompt's "Bản thảo đang có" base
  and `= «value»` hints use the same key: `graph_tra_cuu._nap_ban_thao_dang_mo`
  re-reads the light row by the turn's `viec_id` (first khuôn document of the
  turn, else `None`) when the per-turn read is the other kind, so an HTML turn
  never rebuilds from a form summary and a khuôn-only conversation never shows
  an HTML turn a base it cannot edit. `ban_thao_ket` reports the stored
  row's `viec_id`/`phep_sua`, not the ket's. Because a zero-op create turn saves
  nothing (P4b review), `POST /tai-lieu/{viec_id}/ban-thao` opens the fill panel
  with an empty version 1.
- 2026-09-27 (owner): a drafting request on a khuôn document always creates
  version 1 (possibly the upload unchanged); only an explicit different-document
  request points to the checklist; supersedes the P4b review default. The owner's
  words: "tôi ko muốn điền mà là tạo lại, soạn thảo lại cái file ấy để tôi lưu
  về, hoặc là sau đó tôi cần agent sửa thì tôi mới bảo nó điền tiếp". The strict
  schema carries `khuon.yeu_cau` (`van_ban_nay` | `van_ban_khac`, required);
  missing or unknown reads as `van_ban_nay`. `van_ban_nay` with an empty op list
  goes through `ban_thao.tao`, the `EP_SOAN_THAO` quota check and the traces row
  like any create; its download is byte-identical to the stored khuôn gốc (both
  appliers return the input for an empty list) and its pages are the Bản tải lên
  pages. `van_ban_khac` creates nothing, edits no existing draft, touches no
  quota and says the request is for a different document, pointing to **Chọn
  loại văn bản**. An edit turn that changes nothing still answers
  `KHONG_DOI_KHUON`, reworded to point at the existing draft (open, download
  Word or PDF, fill by saying the value or in the panel) instead of demanding
  values: the owner's sentence repeated, or said after **Điền biểu mẫu**, lands
  there. `POST /tai-lieu/{viec_id}/ban-thao` stays: it opens the
  fill panel without a chat turn and without quota.
- 2026-09-27 (fix/dien-dung-o, from the owner's real run with
  gemini-2.5-flash-lite on BM.M05, "Điền giúp tôi biểu mẫu này: tên cơ quan tiếp
  nhận là Công ty TNHH Luật Việt, số 12/2026, …"): the model wrote the company
  into the `Số` blank and "12/2026" into the `/` blank of the letterhead cell,
  leaving "Cơ quan/Đơn vị tiếp nhận: ……" empty. Causes: the prompt listed blanks
  apart from their sentence (`chỗ trống: 0 «Số» | 1 «/»`), and the uppercase
  placeholder "TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN" — a fill target in Vietnamese forms
  — could not be replaced (`co_cho_trong`), while a whole-cell `thay` would
  restyle every paragraph with the first run's format. Changes: the reader
  persists `doan_chu`; the prompt places `⟦n⟧` and `¶n` in the text (list-line
  fallback when unproven); `thay` gains `doan` (the plan's original contract
  allowed paragraph-level replace); the provenance rule on added words replaces
  `co_cho_trong`; `khong_khop_nhan` catches a real value in a number/date-part
  blank, because the provenance rule cannot. The prompt is what steers the model
  to the right blanks; on the observed wrong output the narrow label rule drops
  only the company in `Số`, and its `/` value ("12/2026": digits, grounded) still
  lands. Traces count `khuon_yeu_cau_khac` and `khuon_so_phep_bo_yeu_cau_khac`.
- 2026-09-27 (fix/dien-dung-o, refines the owner's no-change rule above): an
  edit turn with `yeu_cau = van_ban_nay` whose merged ops equal the current ones
  and that proposed nothing (no dropped op, including a `dien` the merge removed
  as `da_viet_lai`) returns the EXISTING draft as the
  turn's `ban_thao` (chat card, no version, no quota, no traces row), answering
  "Bản thảo trên tệp bạn tải lên đã có sẵn (phiên bản N): …". `KHONG_DOI_KHUON`
  remains only for turns whose proposed changes were all dropped and names the
  kinds of problem (never values). User-facing copy says "bấm vào chỗ trống trên
  trang" instead of the side-panel "dùng các ô điền bên cạnh trang" (on-page
  filling, `feat/sua-tren-trang`); the khuôn answer's "sửa từng ô hoặc tải về ở
  bên cạnh" follows for the same reason.
- 2026-09-27 (fix/dien-dung-o review, agent default under the standing
  delegation, open for the owner; supersedes the narrower default of the same
  day): the added-words provenance rule applies to EVERY `thay`. Measured on the
  real BM.M05: `thay(1, doan=null, "BỘ GIÁO DỤC VÀ ĐÀO TẠO")` on the one-paragraph
  "TÊN CHỦ QUẢN…" cell was kept while the byte-identical `doan: 0` was dropped,
  and multi-paragraph blank-less cells (the letterhead's own shape) left the same
  hole; `goc.isupper()` does not catch "… (nếu có)". Cost: a sentence the model
  rewrites in words nobody typed (and that are not in the document or hồ sơ) is
  dropped as `khong_nguon`; the prompt says so. `chen_sau` keeps the looser
  check (digits/email and `Nhãn: giá trị`) — the prompt sends placeholders to
  `thay`. Reverse only with an owner decision that accepts model-worded
  rewrites on the user's own form.
- 2026-09-27 (G1, blank positions): `dien_khuon.danh_dau_docx` builds a PROBE
  copy — each reachable blank's characters split into their own runs (same
  `w:rPr`) and wrapped in a `w:hyperlink` to `https://klaw.invalid/o/{don_vi}/{so}`;
  the applier fills the probe exactly as the clean copy (split runs keep the
  raw string, so `[dau:cuoi]` holds, and a value lands inside its link).
  LibreOffice exports each link as a `/Link` `/Rect`. Measured on the 8 owner
  forms (LibreOffice 26.2.4): splitting runs alone is pixel-identical, but ANY
  marker boundary (hyperlink, bookmark, colour) can move LibreOffice's line
  break — a marker portion with no break inside that overflows the line wraps
  at its own boundary (BM.M05 "Khoa .……" wraps one line differently and every
  later line of page 1 shifts) — and shifts glyphs by ≤ 1 px elsewhere (6/7
  forms with blanks are not pixel-identical). So pages are always rendered
  from the CLEAN copy; the probe is converted in the same soffice process (two
  files take 1.4–1.7 s, as one does), and positions are transferred by
  character: the non-space `pdftotext -tsv` streams of probe and clean are
  identical on all 8 forms before and after filling, so the chars under a
  probe `/Link` are found on the clean page (word kept intact → exact offset;
  word split differently → evenly divided width) and the box is their part on
  the first clean line. Streams that differ → no positions (logged). Result:
  247/248 blanks positioned (124 unfilled + 124 filled); the miss is the single
  "…" ending the right-aligned "… năm 20…" of BM.ĐT.18.03 while empty
  (LibreOffice emits no annotation for it; a trailing tab or ZWSP makes one but
  changes the layout). 38 blanks span several rects (split across runs or
  lines); the first clean line is used. A blank in a header shows on its first
  page only. `GET …/trang` median +0.10 s (1.66 → 1.76 s over the 8 forms, max
  +0.29 s on the 4-page Evaluation Form). A failed paired run falls back to the
  clean render alone (page returned, no positions).
- 2026-09-27 (G1, labels): the empty labels behind "Ô 9.0"/"Ô 11.0" come from
  the PDF export of BM.M05 (`bm-m05.pdf`, 30 blanks — the owner's "0/30 ô"): a
  dots-only line under its label had no words before it. A `.doc` converted by
  LibreOffice reads the same labels as the `.docx`.
- 2026-09-27 (on-page filling, G3 review): the owner dropped the fill panel
  ("tình trạng ô này thì ko cần thiết, có thể để người dùng trực tiếp thao tác
  trên" the page), so blanks are edited on the page image. Values typed there
  stay unsaved (the map lifted to `dung-thu.tsx`, shown over the blank with a
  dashed outline), and one toolbar **Lưu** sends every changed blank in one
  `PATCH …/o-dien`, i.e. one version: the Risks "Edit cap" rule. Saving per
  blank spends one of `TRAN_SUA` = 10 per field and dead-ends a 30-blank form.
  Agent default within that rule, open for the owner to reverse: exempting fill
  saves from the cap (`sua_o_dien` skips `kiem_tran_sua`, writes `tang: 0`,
  keeps the `[-TRAN_SUA:]` trim) would allow an instant save per blank.
- 2026-09-27 (wave G integration, `integ/wave-g`): `cho_trong_khuon` keeps
  both rules — a blank of a paragraph replaced by `thay` with `doan` is not
  listed, and every listed label goes through `nhan_sach` — so the probe
  (`ban_do`) marks exactly the blanks still on the page. Measured on BM.M05
  with LibreOffice 26.2.4: 32/32 blanks positioned untouched, 32/32 after
  `thay` of the letterhead's name paragraph plus fills, 30/30 after `thay` of
  its "Số …./…." paragraph. The node reads labels through
  `doc_tai_lieu.nhan_sach_don_vi` (the reader's own threading, now one helper),
  so rows stored before `nhan_sach` reach the prompt, the chat's "Còn trống"
  and `khong_khop_nhan` with the names the page shows.
- 2026-09-27 (owner rule, fix/g4-backend): "nếu người dùng yêu cầu sửa thì hãy
  sửa, còn nếu bảo soạn thảo văn bản ra thì phải đúng 100%". Observed in the
  owner's app the same day: "soạn thảo văn bản này cho tôi" on BM.M05 produced a
  draft with «Trường Đại học Phenikaa» — words PRINTED in unit 9 — in that
  sentence's «Khoa» blank; the provenance check let it through because the
  document was one of its sources. Changes (supersede the `yeu_cau` values and the
  looser `chen_sau` check of the decisions above; the no-change edit answer is
  unchanged):
  - B1: `yeu_cau` is `tao_lai | dien_sua | van_ban_khac`. `tao_lai` discards every
    proposed op before validation (traces count `khuon_tao_lai`,
    `khuon_so_phep_bo_tao_lai`): a create turn saves version 1, `phep_sua: []`,
    byte-identical download, answer "Tôi đã dựng lại văn bản đúng như tệp bạn tải
    lên (N trang) …"; on an existing draft see the review entry below (reset to
    the upload). Missing/unknown (including the old `van_ban_nay`) reads as
    `dien_sua`: B2 keeps every ADDED word to the user's text; deletions are not
    covered (see the review entry).
  - B2: a `dien` value and every word a `thay`/`chen_sau` adds must come from the
    user (`_nguon_nguoi`: `cau_hoi_goc`/`query`/`cau_hoi_day_du`, hồ sơ minus
    `suy_dien`, memory asked for this turn). The document's text, `quan_sat`
    quotes and the open draft's `document` are no longer sources; a `thay` still
    keeps the words and numbers of the text it replaces. A re-proposed op
    identical to the open version's is skipped silently, so a repeated value from
    an earlier turn is neither refused nor re-applied. Cost: a model-worded label
    ("Người liên hệ:") in a `chen_sau` is now dropped unless the user said it.
  - B3: `khuon.khong_dat` (values the user gave that the model could not place),
    filtered to substrings of the user's text; `assemble` lists them ("Chưa đặt
    được: «…» — hãy nói rõ chỗ cần điền hoặc bấm vào chỗ trống trên trang.") and
    takes their length out of the 320-character "Còn trống" budget, so the longest
    answer stays under 900 characters. Empty list-table cells (BM.M05 page 2) are
    filled by `thay` on the cell unit; the prompt says so.
  - B4: a full date into the first blank of a `… / … / …` triple, or into the
    `ngày` blank of `ngày … tháng … năm …`, is split into three `dien` in the node
    (not left to the model), unless the turn fills the other two itself.
  - B5: a refused upload (page cap, format, broken file, converter busy) into a
    conversation the upload opened itself hard-deletes that conversation
    (`hoi_thoai.xoa_cung_phien_mo_ho`, own and turn-less only); its viec row goes
    with it by the migration-026 cascade, so that refusal stops counting toward
    `tai_lieu_ngay` — the same as deleting the conversation already does. Agent
    default: the viec row cannot outlive its conversation (`hoi_thoai_id NOT
    NULL … ON DELETE CASCADE`), and keeping a soft-deleted row would leave a
    `hoi_thoai` row behind. Uploads into an existing conversation keep today's
    `hong` row. The page-cap 422 names the file and the real page count.
  - B6: fill saves no longer count toward `TRAN_SUA` (the G3 review's option,
    now taken): `sua_o_dien` skips `kiem_tran_sua` and writes `tang: 0`, still one
    version per save under the optimistic lock, history trimmed to the last
    `TRAN_SUA` snapshots. Chat edits still count.
  - B7: a version whose merged op list is empty downloads under the upload's own
    name (`<stem>.<dang>`); only versions with changes get " - đã điền".
  - B8: the backend's unlabeled-blank name is "Chỗ trống" (`ban_thao.ten_cho_trong`),
    with " (n)" in reading order only when two unlabeled blanks would read the same;
    "Ô x.y" is gone from saved documents, history diffs and save refusals.
- 2026-09-27 (fix/g4-backend review): two holes in B1/B2, measured with a fake
  LLM on the real BM.M05 unit 9 ("… Trường Đại học Phenikaa, thuộc Khoa ……").
  - B2 compared the words a `thay` adds as a SET, so repeating or moving printed
    words of the same paragraph read as "not added":
    `thay(9, doan 0, "<same prefix> thuộc Khoa Trường Đại học Phenikaa")` on
    "soạn thảo văn bản này cho tôi" was kept with `yeu_cau` missing or
    `dien_sua` (also `doan` null, "thuộc Khoa Phenikaa", and the move variant).
    Now `_them_khong_nguon` diffs word sequences (`difflib.SequenceMatcher`,
    `autojunk=False`); every inserted or replacing run needs a user source. The
    placeholder and empty list-cell fills still pass: their run is the user's
    value.
  - B1 `tao_lai` on an existing FILLED draft returned it unchanged (`co_san`), so a
    conversation carrying the pre-fix bad fill stayed wrong when the user asked
    again. Agent default under the standing delegation (the reviewer's option A),
    open for the owner to reverse: `tao_lai` on a filled draft saves one new
    version with `phep_sua: []` (`ban_thao.sua(tang=0)`: not counted toward
    `TRAN_SUA`, not blocked by it); the answer is "Tôi đã dựng lại văn bản đúng
    như tệp bạn tải lên …" plus "Giá trị đã điền trước đó vẫn ở phiên bản trước:
    bấm Lùi để lấy lại." A draft that already is the upload keeps the no-change
    answer. The reverse (option B) keeps `co_san` and says how many values the
    draft still holds. Cost: "xuất file này" on a filled draft, classified
    `tao_lai`, now yields the empty version first; one Lùi restores it.
  - Not closed: a `thay` or `xoa` that only DELETES printed text (e.g. the
    "thuộc Khoa ……" clause) adds no value, so B2 does not see it; with `yeu_cau`
    misclassified as `dien_sua` on a drafting request it still lands. Only the
    classifier guards that case; widening B2 to deletions needs an owner
    decision, because "bỏ dòng …" is a legitimate edit.
- 2026-09-27 (owner rules, wave G close-out): the day's owner rules as they now
  stand together. (1) Blanks are filled on the page, not in a side panel
  ("có thể để người dùng trực tiếp thao tác trên" the page). (2) "Soạn thảo văn
  bản ra thì phải đúng 100%": `tao_lai` returns the upload exactly; "yêu cầu sửa
  thì hãy sửa": `dien_sua` fills and edits with values from the user only (B1,
  B2). (3) Fill saves are outside `TRAN_SUA` (B6), so fix/g4-frontend saves each
  blank as its own version — Enter, Tab/Shift+Tab or leaving the blank saves,
  Esc drops the unsaved text, saves queue so each sends the version the previous
  one created, and the batch **Lưu** of the G3 review is gone (supersedes that
  entry's one-save-per-batch default). Pages re-render once, 1.2 s after the
  last save; renders and downloads run one at a time per tab, matching the
  server's one render per account. Known ceiling: history keeps the last
  `TRAN_SUA` snapshots, so after more than 10 blank saves **Lùi** cannot reach
  the first ones. Still open for the owner: the deletion-only `thay`/`xoa` gap
  and the `tao_lai`-on-a-filled-draft default (option A), both above. Both g4
  branches merged into `integ/wave-g` without conflicts.
- 2026-09-27 (G5, from the owner's real run with gemini-2.5-flash-lite on BM.M05,
  "Điền giúp tôi biểu mẫu này: tên cơ quan tiếp nhận là Công ty TNHH Luật Việt, số
  12/2026, sinh viên Nguyễn Văn Ánh, ngành Luật kinh tế, thời gian từ 01/10/2026
  đến 31/12/2026."): every value landed except «Nguyễn Văn Ánh», silently dropped
  — the page-2 list table's empty cells had no blank, the model's op went to unit
  29 («Mã sinh viên/ học viên», wrong column), `khong_dat` stayed empty and the
  note said "đoạn 29". Changes (supersede B3's "filled by `thay` on the cell
  unit"; a whole-cell `thay` is still accepted, under the same column digit
  check as `dien`): empty cells of a bordered table
  under a named column are `o` blanks (Contracts); the applier appends one run
  in the paragraph mark's format; a `Mã`/`Số`/`STT`/`TT` column needs a digit;
  dropped ops' user values feed `khong_dat`; answers name blanks, never units.
  Probe: an empty cell has no character to wrap in a link, and ANY run put in
  the empty paragraph — NBSP, ZWSP, WJ, hidden text, with or without a link or
  `w:rPr` — shortens the row under LibreOffice 26.2.4 (the line below the BM.M05
  table rises 1.4 pt after four rows; with `w:ptab` the cell wraps). A cell
  SHADING changes no word box (0 of 207 on BM.M05) and LibreOffice exports it as
  `r g b rg` + `re` + `f*`, so the probe shades each `o` cell `#01` + unit (hex)
  and `dung_trang._nen_o` reads the rectangles; the box is used as is only when
  every probe word above the cell's bottom sits within 1 pt of the clean page
  (a link wrapping differently above would move the cell: "chưa định vị").
  Measured on the 8 forms: 47/47 `o` positioned empty and 47/47 filled; chấm/tab
  unchanged at 123/124 empty and 124/124 filled; `eval.run_khuon_goc` numbers for
  chấm/tab byte-identical, `o` measured apart (47/47 applied, page count kept on
  4/4 forms, 47/47 read back in the right unit); `eval.run_trung_thuc` unchanged.
  Open: LibreOffice 25.2.3 (the Dockerfile's) not measured for the shading path —
  a build that draws cell fills otherwise leaves `o` blanks unpositioned, never
  misplaced; column names come from position (rows above the first data row),
  not formatting — every measured table has one header row. Agent defaults under
  the standing delegation, open for the owner: `TT` counts as a number column;
  a dropped op's value is listed only when it is a substring of the user's text.
- 2026-09-27 (wave G5 integration, `integ/wave-g5`): the owner-forms API test
  `test_bieu_mau_THAT_ra_dung_so_trang_dan_that` still expected BM.M05's pre-G5
  32 blanks on `GET …/trang`; the reader now gives 32 chấm + 24 `o` (the
  Contracts' count), so it expects 56, and its per-blank check (a page and a box
  inside it, a label, no value) now covers the 24 `o` cells too. Ruler
  (`eval.run_khuon_goc` without `--word`) against `eval/results/khuon_goc.json`:
  every LibreOffice measure is byte-identical — pages, round trip 8/8, chấm/tab
  fill 124/124 with the page count kept on 6/7 (BM.ĐT.18.05 still grows to 2
  pages, as before), pdf_so, pdf_scan, the 11-page refusal. The `o` blanks change
  no chấm/tab count because the ruler measures them apart (`o_bang`: BM.M05 24,
  BM.ĐT.18.05 13, BM.ĐT.18.11 5, phiếu đánh giá 5; applied 47/47, page count
  kept 4/4, read back 47/47). The Word fields are empty only because the run had
  no `--word`: Word is not re-measured for G5, and the committed result file is
  kept. The sidebar's Bản thảo list patches the drafts `api.ts` announces
  instead of re-fetching, because a GET per blank save would spend the per-IP
  rate bucket.
- 2026-09-28 (owner, G7 Q1–Q4). Source: the owner's real conversation a99dfda8…
  on BM.ĐT.18.11, with an empty draft opened by **Điền biểu mẫu**. Three turns,
  'soạn thảo lại văn bản này cho tôi', 'Điền họ và tên … mã số …' and 'cho tôi
  xem văn bản mới sau khi điền', each answered `tai_lieu`/`hoi` with no draft,
  and the model's "Tôi đã điền … ⟦0⟧" reached the user. Cause: the router called
  every follow-up turn `tai_lieu`, and the drafting veto
  (`_muc_dich_soan_da_xac_nhan`) downgraded each one to `hoi`. The owner rules
  above still stand: a recreate request yields exactly the upload, values come
  only from the user, and blanks are filled on the page.
  - Q1: the document line on a `tai_lieu` chat card is a button. It opens the
    newest draft of that file (`GET /tai-lieu/{viec_id}/ban-thao`, Contracts),
    or focuses it when it is already open. A 404 opens **Bản tải lên**. A file
    known to have no khuôn gốc (`co_khuon_goc: false`, from one `GET
    /tai-lieu/{id}` per unknown file per conversation load) opens its read facts
    instead. When the user clicks twice before the first GET returns, only the
    later click opens. This works the same on live and saved turns.
  - Q2: a live chat result that carries a khuôn draft (a fill, edit, recreate
    or view turn) opens the draft stage once; in the narrow layout that is the
    draft tab. The chat keeps the answer and the card. Saved history never opens
    the stage. HTML drafts do not open it either.
  - Q3: a request to VIEW the filled draft returns the conversation's newest
    khuôn draft as a `ban_thao` result, before the graph runs: zero model calls,
    no new version, no quota, traced like a cache hit. It is matched by a closed
    pattern over the whole sentence ("cho tôi xem văn bản mới sau khi điền", "mở
    bản đã điền", "bản đã điền đâu"); "cho tôi xem biểu mẫu này nói gì" is still
    a question. It applies only when the conversation's newest draft is a khuôn
    draft and the turn attaches no new file. A newer HTML draft takes the normal
    path.
  - Q4: on a document with a khuôn gốc, deterministic evidence decides whether a
    turn drafts, not the router's `intent` (`hieu_tai_lieu._quyet_khuon`). The
    evidence is a verb in the user's own words plus the ops that passed
    `kiem_phep_sua`. The verb match is accent-aware: an unaccented match counts
    only when the user typed it unaccented, so "điện thoại" is not "điền".
    - It is a fill turn when a fill/edit verb comes with a validated op, or with
      a model or router reading of drafting, or when `dien_sua` has at least one
      validated op.
    - A recreate verb makes it `tao_lai`, except in a question nobody read as
      drafting ("Văn bản này do ai soạn thảo?"), because recreating wipes the
      fills. "xuất bản" alone is not a recreate verb.
    - A model `van_ban_khac` stands. Real questions stay Q&A. Documents without
      a khuôn gốc, and HTML drafts, keep the router veto.
  - Honest answers:
    - A fill request that applies nothing never creates version 1. It gets a
      fixed answer, `CHUA_DIEN_KHUON`, that says why nothing was filled, plus
      "Chưa đặt được: «…»".
    - A model claim of a change ("Tôi đã sửa …") never reaches the user on a
      Q&A path (`CHUA_THAY_DOI`).
    - Several khuôn forms and no named target: nothing is applied, and the
      answer asks which form (`CHUA_RO_KHUON`).
    - `⟦n⟧`/`¶n` markers are stripped from every model text field, and the
      prompt forbids writing them.
  - Name: a khuôn draft's `ten` is the uploaded file's stem, through one helper
    (`ban_thao.ten_ban_thao`), on the chat card, `BanThaoOut` and the sidebar
    list. HTML drafts keep "Bản thảo tổng quát".
- 2026-09-28 (wave G7 integration, `integ/wave-g7`): `fix/g7-backend` and
  `fix/g7-frontend` merged without conflicts. Checked against the backend's
  final routes and fields:
  - `banThaoCuaTaiLieu` GETs the path the backend serves and validates the
    response as `BanThaoOut` (`laBanThao`); 404 maps to **Bản tải lên**.
  - A view result's `ban_thao` comes from `_ket_state` and carries `khuon`, so
    `banThaoTuMo` opens the stage.
  - The new SSE step `xem_ban_thao` gets its label from the server.
  - Every row that reaches `_out` carries `ten_tep`.

  Two G7 hunks (`assemble.xem_ban_thao_khuon`'s return and the view branch's
  `_ghi_traces_nhe` call) were laid out as `ruff format` wants. The other format
  drift in the changed files predates G7, and its size equals `main`'s.

## Validation

- Focused proof: per-phase pytest files run by path; `frontend` `npm run kiem`
  and `npm run typecheck`; `ruff check src/ tests/`; `ruff format --check` on
  changed files only (never `make format`).
- Integration: `docker compose up -d db`, then the integration lane for the files
  each phase touches (cascade, ownership, migration re-run).
- End-to-end: upload BM.M05 and Evaluation Form in the real app, open Bản tải lên,
  ask KLAW to fill, save one field in the panel, download both files; screenshots
  in `.tham-dinh-shots/` (owner's untracked folder).
- Ruler: page count equal to LibreOffice and to Word on all 8 forms; unchanged
  pages pixel-identical after a fill; every filled docx opens in Word.
- Egress (P6): run the three `*lien_ket*` / `*tep_may_chu*` tests of
  `tests/test_services/test_dung_trang.py` inside the production image. All
  three must pass (the `.doc` one since P2c); a failure there means that
  LibreOffice build fetches linked content again.
- Repository-required checks: CI lane
  `KLAW_SUPABASE_URL= python -m pytest -q -m 'not integration and not pending_review' --deselect tests/test_services/test_moi_mau.py`.

## Result

Verified outcome on local `main` (`5981b44`), 2026-09-27:

- Ruler (`eval/results/khuon_goc.json`, Word on, 8 owner forms): LibreOffice page
  count equals Word 8/8; empty-op round trip byte-identical 8/8 and
  pixel-identical 8/8; dot/tab blanks 124/124 applied and read back, Word opens
  7/7 filled files and keeps their page count 7/7; empty list-table cells 47/47
  applied and read back; the 11-page file is counted 11 and refused, the 10-page
  file accepted.
- Real app, owner's browser (four chunked runs, ~12 model calls in total):
  'soạn thảo văn bản này cho tôi' on BM.M05 answers in chat and yields version 1
  whose Word download is sha256-identical to the upload (PDF upload: PDF download
  byte-identical); repeating it creates no version. 'Điền giúp tôi …' places the
  company on 'Cơ quan/Đơn vị tiếp nhận', 'Số 12/2026' in the letterhead, the
  major, both page-1 dates and 'Nguyễn Văn Ánh' in 'Họ và tên (dòng 1)'; no
  printed form text is copied into a blank. On-page filling: click, type, Enter
  saves a version, Tab saves and moves, Esc sends nothing, Lùi walks back,
  `so_lan_sua` unchanged. No document panel or fill side panel; the attachment
  is a chip with a menu. Phiên mới and a sidebar switch close the stage. The
  11-page refusal names the file and its count and leaves no conversation.
- Test lanes on main: CI lane 2615 passed; khuôn files 783 passed; frontend
  `npm run typecheck` and `npm run kiem` pass.

Limits, stated plainly:

- 'Bản tải lên' and page images are LibreOffice renders: page counts match Word,
  but line positions differ (ink IoU vs Word mean 0.37, min 0.08 on Evaluation
  Form p3). The downloaded `.docx` is the user's own file, filled.
- PDF inputs: blanks found 93/124 (digital) and 112/124 with 26 extras (scan);
  about half of long values are refused as `khong_vua`; the overlay covers but
  does not remove the original text layer.
- Evaluation Form's 33 text-less dot-leader continuation lines are not fillable
  (contract, upgrade path recorded).
- Production image measured 2026-09-28 (local build of main, linux/arm64,
  LibreOffice 25.2.3, `--network none`): 8/8 forms give the true page count,
  every blank positioned except the known BM.ĐT.18.03 '… năm 20…', `o` cells
  filled and positioned, the four egress tests pass. Render 0.4–2.0 s per
  document. Peak memory per render ≈ 236 MB soffice.bin + 85 MB oosplash + 23 MB
  pdftoppm; with 3 shared slots plan for ≥ 2 GB RAM (0.5 GB will not hold one
  render next to the app). LibreOffice 25.2 lays BM.M05 page 1 out closer to
  Word than the Mac's 26.2 (ink IoU vs Word 0.28 vs 0.17; page 2 0.61 vs 0.55).
  Railway builds linux/amd64 from a fresh base — re-check `soffice --version`
  on the deployed service.
- History keeps the last 10 snapshots, so Lùi cannot reach the earliest of many
  on-page saves.

Follow-up (owner decisions left open, each recorded above as an agent default):
`tao_lai` on a filled draft saves a reset version; 'TT' counts as a number column;
a dropped value is named only when it appears in the user's words; a refused
broken file in a fresh chat no longer counts toward the daily quota; a
`thay`/`xoa` that only deletes printed text is not provenance-checked when a
request is misclassified as `dien_sua`. Also: soft-deleted drafts and turns
(issue #3); document spend does not reach `traces`, so the shared daily cost cap
does not see it — add a per-account cap before opening the app to many users.

G7 on `integ/wave-g7` (2026-09-28), fake LLMs only, zero model calls: khuôn test
files 778 passed (the new `test_khuon_luot_noi_tiep.py` included); CI lane 2697
passed, 1 skipped (the `tai_lieu_tong_quat` sample set is not built), and its one
failure is the worktree-only `test_data_raw_VAN_bi_gitignore`; `ruff check` passes;
frontend `npm run typecheck` and `npm run kiem` pass. Q1–Q4 have not been
re-run in the owner's app.
