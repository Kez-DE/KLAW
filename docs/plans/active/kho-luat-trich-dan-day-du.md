# Execution Plan: A complete corpus with full, linked citations

Date: 2026-09-28

## Status

Active. Owner decisions Q1–Q6 accepted 2026-09-28 ("chốt các phương án đề xuất
của bạn, thực thi đi"); execution delegated to agents. Decision record:
`docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`.

## Outcome

Observable once complete:

1. Every document in the kho carries issuing body, issue date, effective date and
   a refreshed effectivity status taken from the Bộ Tư pháp database; every
   document whose vbpl.vn page passes the machine check carries a working link
   `https://vbpl.vn/van-ban/chi-tiet/{id}` with its evidence.
2. A citation in a chat answer shows the provision, the document's full name,
   type and number, issuing body, issue date, effective date, KLAW's effectivity
   label (naming the replacing/amending document when there is one) and the
   official link — in the đối chiếu frame and in a "Căn cứ pháp lý" list at the
   end of the answer. 'Sao chép trích dẫn' copies the same sentence in the form the
   statutes themselves use ('khoản 1 Điều 3 Nghị định số 90/2019/NĐ-CP ngày
   15/11/2019 của Chính phủ') plus the link.
3. The document page `/tra-cuu/{doc_id}` shows the official link and dd/mm/yyyy dates.
4. Documents the kho points to but lacks (replacing, amending, guiding documents
   within the 8 fields — starting with 38/2022/NĐ-CP) are loaded with full text,
   indexed and citable; wrong relation edges are removed (19/2023 → BLLĐ) and the
   BLLĐ amendment chain is complete.
5. Checklist/HTML drafts export a "Căn cứ" block built from verified in-force
   documents; khuôn-gốc drafts stay byte-identical to the upload.
6. `scripts/lam_moi_hieu_luc.py` (manual) refreshes effectivity and links from the
   Bộ Tư pháp database; the data-source page credits the HuggingFace dataset.
7. The golden 77 + trap 57 + mơ hồ 20 set is measured before and after, on the
   pinned models, and the difference is recorded.
8. Owner rules added 2026-09-28 (decision items 8–10): only documents that are in
   force (or partly in force), of known status and with a verified official link
   are shown anywhere; expired ones stay hidden in the DB; every shown document
   has full text; an official signed PDF with a page-1 preview is shown when one
   exists; no diagnostic lines ('tình trạng MOJ…', 'độ tin cậy') anywhere.

## Context

Read-only audit 2026-09-28 (scratchpad evidence): 1,634 documents (54 deep with
text verified 8,609/8,609 provisions against the gateway; 1,572 shallow title-only;
8 metadata-only). co_quan/nguoi_ky/tinh_trang missing on 1,580 rows while
`data/raw/metadata.parquet` has them; link_vbpl 0/1,634; stale effectivity
(12/2022/NĐ-CP now HHL at the gateway); wrong edge 19/2023 → 45/2019; 90/2019 is
replaced by 38/2022 (MOJ 154245, absent); CitationOut carries no issuing body,
dates or link; KhungDoiChieu drops metadata the API already returns; warnings[]
never shown; drafts export no "Căn cứ". vbpl.vn serves bots again; the old
`vbpq-toanvan.aspx?ItemID=` pattern redirects to the home page, so
`data/seed/link_vbpl_suy_ra.yaml` must not be loaded as is.

## Approach

| Wave | Work | Depends on |
|---|---|---|
| K0 | Eval baseline BEFORE any data change (detached worktree, pinned models) | – |
| K1 | Load missing documents (38/2022 + reference-graph targets) deep; fix edges; index | K0 |
| K2 | Metadata + effectivity refresh from the gateway for all rows; machine-verified vbpl.vn links; cleanup; refresh script | K1 |
| K3 | Citation display (backend fields + frontend frame, list, copy, document page) | G7 merged |
| K4 | "Căn cứ" block in checklist/HTML drafts | K3 |
| K6 | Full text for every shown document; official PDFs + previews | K2 |
| K7 | Visibility rule in listing/search/filters/doc page/retrieval; hide diagnostics; PDF/link rows | K3, K6 |
| K5 | Eval AFTER; record the difference; data-source page credit | K6 |

Rules: data writes go through additive migrations and the `nap_*` UPDATE path —
never re-ingest an existing document (ingest DELETE cascades provisions); new
documents enter through the existing fetch → build_seed → ingest path. Gateway
at ≤1 request/1.5 s with backoff on HTTP 400. No text from commercial sites.

## Risks And Recovery

- Re-indexing changes retrieval → the before/after eval is the guard.
- Machine link checks can pass a page that later changes → the refresh script.
- A wrong new edge could flip an effectivity verdict → K1/K2 reviewers re-run the
  effectivity tests and spot-check the labour chain against gateway text.
- Recovery: every data change is scripted and idempotent; migrations additive;
  a pg_dump of the shared DB is taken before K1 writes.

## Progress

- [x] Decisions Q1–Q6; decision record; this plan.
- [ ] K0 baseline eval.
- [ ] K1 missing documents and edges.
- [ ] K2 metadata, effectivity, links, cleanup, refresh script.
- [x] K3 citation display (2026-09-28, `integ/trich-dan-day-du`). Backend
  `services/trich_dan.truong_trich_dan` adds `ten_van_ban`, `loai_van_ban`,
  `co_quan_ban_hanh`, `ngay_ban_hanh`, `ngay_hieu_luc`, `lien_ket`, `cach_trich`
  to citations, `nguon`, `documents[]` and `GET /van-ban/{id}`, plus
  `citations[].canh_bao`. Frontend reads the same names: frame header, "Căn cứ
  pháp lý" list, copy sentence, document page link and dates. The frame's
  effectivity note now reads `canh_bao` (per provision) and falls back to
  matching `warnings[]` only for turns cached before the field. Every field is
  NULL-safe: while `link_vbpl` is empty no link shows. Remaining: the plan's
  real-app check of one labour answer, once K2 has filled links; `/tim-kiem`
  rows don't carry `cach_trich`/`lien_ket` yet (the frontend falls back).
- [x] K4 "Căn cứ" in drafts (2026-09-28, same branch). Checklist drafts get
  the block in `document` and as `can_cu_van_ban`; `XemTruocA4` draws it under
  the title as plain paragraphs, so the `.docx`/PDF export (read from the
  sheet) carries it. General and khuôn-gốc drafts get `[]`. Remaining: open a
  labour draft in the real app and check the downloaded file.
- [ ] K6 full text for every shown document, PDFs.
- [x] K7 visibility rule and diagnostics hidden (2026-09-28,
  `integ/hien-thi-con-hieu-luc`, not yet on main). `services/hien_thi` is the
  one definition: shown = MOJ `tinh_trang` CHL/HHL1P AND KLAW verdict alive
  (`VERDICT_HIEN`) AND `trich_dan.lien_ket` passes. Lists, bộ lọc counts,
  tìm kiếm, phạm vi, liên quan, retrieval/expand, drafting sources and the
  answer-cache key use it; `test_hien_thi_bat_bien` guards every user read.
  A hidden document answers 404 `{ma: "khong_hien_thi", thong_diep,
  thay_the}` on the document routes; a question naming one gets
  `van_ban_khong_hien_thi` (plain sentence + replacing documents with links)
  and a `warnings[]` line. Readers never see `ly_do`/`tin_cay`/MOJ codes:
  `HieuLucOut.mo_ta` + `van_ban_lien_quan`, `canh_bao` in reader wording;
  frontend badge reads "Còn hiệu lực một phần", draws nothing for
  `chua_xac_dinh`/`can_doi_chieu_tay`, and `kiem-khong-chan-doan` scans
  components/routes. Integration closed two contract gaps: the answer card
  renders `van_ban_khong_hien_thi` with the 404 page's `DanhSachThayThe`
  (the backend no longer copies the sentence into `coverage_note`, so it
  shows once), and a provision's reader warning (`ghiChu`) still shows when
  its label draws nothing. Templates whose checklist root basis is hidden
  stop before the paid call: plain chat reply, 422 sentence as the rebuild
  toast. Snapshot of the shared DB, read-only, 2026-09-28 09:01 UTC, while
  K2 was still writing: 1,822 documents, 10 with a verified link, **8
  shown** (the six codes, 145/2020/NĐ-CP, 293/2025/NĐ-CP); 8/29 templates
  blocked (root basis in 30/2020/NĐ-CP ×4, 10/2020/TT-BLĐTBXH, 59/2020/QH14,
  15/2012/QH13, 02/2011/QH13). Golden: 26/77 questions have every expected
  provision in a hidden document (22 on 12/2022/NĐ-CP, now `het_hieu_luc`;
  2 on 337/2025/NĐ-CP, 1 on 84/2015/QH13, 1 on 18/2021/TT-BLĐTBXH — no link
  yet), 1 more partly (135/2020/NĐ-CP). Remaining and open risks: (a) K5
  must re-baseline and the 12/2022 golden items need re-anchoring to its
  replacement — golden unchanged here; (b) owner decision: 135/2020/NĐ-CP is
  HHL1P with a verified link but hidden because KLAW's verdict is
  `can_doi_chieu_tay` — item 8 names MOJ status and link, the verdict
  condition is the backend's reading; (c) deploy the frontend with or before
  the backend, or the hidden-document notice is invisible in between; (d)
  every data refresh changes the shown set and so invalidates the answer
  cache (by design); (e) `GET /mau/{loai}` still names a hidden basis — the
  frame then shows the 404 notice; (f) PDF rows wait for K6; (g) no real-app
  browser check yet.
- [ ] K5 after eval, credit.

## Decisions

- 2026-09-28: machine-verified links are shown (HTTP 200 + title carries the number
  + issue date matches), evidence stored; see the decision record.
- 2026-09-28 (owner): decision items 11–15 — CCHL shown; effectivity names the
  replacement for date-expired documents, follows the chain to a live document and
  exempts text-verified edges from the topic guard; Công báo as fallback full-text
  source; K8 expansion (283/2026, 158/2025, 129/2025, 66.18/2026/NQ-CP, 148/2025);
  golden labels on 12/2022 re-anchored to 283/2026 after verbatim mapping. Research
  evidence: scratchpad `k8/ke-hoach-nap.{json,md}`. The owner grants DB write
  permission for the K8/K6 data work (the permission classifier blocked DELETEs).

## Validation

- Data: SQL fill rates before/after; gateway spot checks; effectivity tests.
- Retrieval/answers: golden before/after on pinned models (`so_loi = 0`).
- UI: typecheck + kiem; a real-app check of one labour answer's citation.

## Result

Pending.
