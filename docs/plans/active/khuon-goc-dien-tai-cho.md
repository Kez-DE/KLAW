# Execution Plan: Show an uploaded document as uploaded, and fill it in place

Date: 2026-09-26

## Status

Active. Decisions settled with the owner on 2026-09-26 (Q1–Q20 of that session);
execution delegated to agents without a further approval gate, by the owner's
instruction: "tự động thực thi vs agent và sửa đổi, thực thi plan với agent luôn,
ko cần tôi duyệt".

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
4. The fill-field panel beside the pages edits any blank; saving re-renders the
   pages as a new version on the existing version bar, and **Lùi** walks back.
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
  `w:t` text (not the stripped `noi_dung`), `nhan` is at most 60 chars of the
  label before the blank. `kieu: "tab"` is a `w:tab` whose stop has a dot leader.
  For PDF: `{"so", "kieu": "cham", "hop": [x0, y0, x1, y1], "co_chu": float,
  "nhan"}` in PDF points on the unit's `trang`, in poppler display space: origin
  at the top-left of the page's MEDIA box (not the CropBox), after `/Rotate`.
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
- `noi_dung`, `chi_so`, anchors and every existing counter stay byte-identical;
  each reader change ships the equivalence test pattern of
  `tests/test_services/test_doc_tai_lieu_trang.py:193-231`.

### Edit operations (`phep_sua`)

```json
{"loai": "dien", "don_vi": 12, "cho_trong": 0, "gia_tri": "Nguyễn Văn A"}
{"loai": "thay", "don_vi": 14, "noi_dung": "…"}
{"loai": "chen_sau", "don_vi": 14, "noi_dung": "…"}
{"loai": "xoa", "don_vi": 15}
```

- `dien` replaces only the blank's characters (possibly spanning runs) with the
  value in the formatting of the blank's first run; a `tab` blank inserts a run
  before the `w:tab` so the leader shrinks as in Word.
- `thay` keeps `w:pPr` and the first run's `w:rPr`; `chen_sau` clones them;
  `xoa` removes the paragraph (a cell keeps one empty `w:p`).
- PDF accepts `dien` and `thay` only; `thay` must fit the unit's box at ≥70% of
  its font size or the operation is refused.
- The applier is pure: `(bytes, don_vi, phep_sua) -> (bytes, bao_cao)`; an
  invalid operation is skipped and reported, never guessed.
- `dien` values must pass the provenance check (`_co_trong_nguon`: the user's
  text this conversation, hồ sơ, or the document) and the memory rules
  (`_chan_bo_nho`). `_vuong_luoi_chan`'s identifier rule does not apply to `dien`
  values — a phone number the user stated is a legitimate fill — but its
  Điều/Khoản rule still applies to `thay`/`chen_sau` text.

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

- `POST /tai-lieu` — unchanged shape; `TaiLieuOut` gains `co_khuon_goc: bool`.
- `GET /tai-lieu/{viec_id}/trang` — the khuôn gốc as uploaded:
  `{"kho": [[w, h], …], "trang": ["<base64 png>", …]}`, one request for every page.
  A render takes one of the three LibreOffice slots (503 `qua_tai`) and holds at
  most 12 Mpx for the whole document; `kho` is always in (0, 14400] pt. One
  render per account at a time: a second concurrent `/trang` from the same
  account is the same 503 `qua_tai`, so the viewer fetches once.
- `POST /tai-lieu/{viec_id}/doc-lai` `{"loai"}` — re-extract by type from the
  stored khuôn gốc (no re-upload, no new viec, no quota hit). At most
  `so_lan_thu` (FR-037, 3) paid re-extracts per document, then 429; `tong_quat`
  calls no model and is free. The cost estimate (422) and the daily cost cap run
  before the claim, so a refusal leaves the viec as it was.
- `GET /ban-thao/{id}/trang?phien_ban=N` — the filled version, same shape; the
  apply and the render are one slot of the same per-account guard (a held slot
  is 503 `qua_tai` before the applier runs). No `phien_ban` (live
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
  downloads as `.docx`); `nosniff`, `private, no-store`.
- `PATCH /ban-thao/{id}/o-dien` `{"phien_ban", "gia_tri": [{"don_vi",
  "cho_trong", "gia_tri"}]}` (1–500 items, value ≤ 500 chars, `""` clears) →
  `BanThaoOut`. One new version per save, counted in `TRAN_SUA`, `audit.sua_tay`;
  a save that changes nothing returns the draft without a version. Every
  refusal is 422 with a Vietnamese string `detail` (stale `phien_ban`, edit cap,
  not a khuôn draft, unknown blank, multi-line value, an op the applier skips) —
  the `PATCH …/muc` convention, not 409. No render.
- `BanThaoOut` and `BanThaoPhienBanChiTietOut` gain `khuon: {"viec_id",
  "dinh_dang", "so_trang", "cho_trong": [{"don_vi", "so", "kieu", "nhan",
  "gia_tri" | null}]} | null` (default null). `cho_trong` lists only blanks the
  applier can reach (docx: unit has `dia_chi`; PDF: blank has `hop`) and not on
  a unit the version `thay`/`xoa`-ed.
- `POST /tai-lieu/{viec_id}/ban-thao` (no body) → `BanThaoOut` with `khuon` —
  opens the fill panel when no model turn filled anything. Explicit user action:
  no model call, no quota row. 200 with the newest draft of this account whose
  live version is on that viec, else 201 with version 1, `phep_sua: []`,
  `document` = `# <ten_tep stem>`. 404 for a foreign/unknown viec or one with no
  khuôn gốc; 401 without login. Concurrent opens serialize on the viec row.
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
- **Edit cap.** `TRAN_SUA = 10` is shared by chat edits and panel saves; the panel
  saves every changed field in one version. A draft opened by `POST
  /tai-lieu/{viec_id}/ban-thao` costs no first-build quota, so later chat fills on
  it are edit turns under `TRAN_SUA`, not `EP_SOAN_THAO` (one draft per viec, and
  each viec already spent `tai_lieu_ngay`).
- Recovery: each phase is one merge commit on `main`; `git revert -m 1 <merge>`
  undoes it. Migration `036` is additive (new table, nullable columns).

## Progress

- [x] Decisions Q1–Q20 settled; decision record, glossary term, spec notes.
- [x] Wave A — P1a, P1b, P1c (merges `9e4474c`, `8dcc8a9`, `ea86a9b`; CI lane 2163 passed on main).
- [x] Wave B — P2b (`a8fd793`), P2a (`3d3871d`, after a merge-up and a replacement privacy review that found and fixed unbounded re-extracts, a reversed-MediaBox render bypass, uncounted kept files, and LibreOffice fetching linked images).
- [x] Wave C — P3a docx applier (`d2ee30a`), P3b PDF overlay applier (`570c805`); CI lane 2381 passed on main.
- [x] P2c — `.doc` importer egress closed with a dead loopback proxy (`fix/soffice-chan-mang`).
- [x] Wave D — P4a storage/routes, P4b graph edit operations, P2c .doc egress barrier, integrated on `integ/wave-d` and merged (`d32a50b`); CI lane 2437 passed on main.
- [ ] Wave E — P5.
- [ ] Wave F — P6.
- [x] Issue opened for the soft-delete gap (#3).

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
- 2026-09-27 (P4b review): on a document with a khuôn gốc, a chat turn that asks
  for a different document ("dựa vào hợp đồng này soạn đơn xin nghỉ việc") gets
  no edit-draft of the upload: decision item 3 leaves "a different document" to
  the checklist, so a create turn that ends with no valid operation saves nothing,
  writes no `EP_SOAN_THAO` trace, and points to **Chọn loại văn bản**. Agent
  default under the owner's standing delegation, open for the owner to reverse
  (the reverse keeps an empty draft so the fill panel opens before any value is
  stated). Blanks are filled only by `dien`: `thay` on a unit with a fillable
  blank is refused (`co_cho_trong`), each `Nhãn: giá trị` value in `thay`/
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

Pending.
