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
- [x] K0 baseline eval (2026-09-28, detached worktree at 9a088ae, pinned
  models gemini-2.5-flash-lite + mistral judge, `eval/results/kho-luat/truoc-*`;
  corpus 1,634 documents / 43,720 provisions / 14,770 chunks). Golden 77: 75/77
  ran (two structural `TruncatedOutputError` rows), trúng dẫn 64.0% / 62.7%
  (two runs), trích dẫn đúng 77.0% / 77.0%, answer 81.3% / 78.7%. Trap 57: 43.
  Mơ hồ 20: 17.
- [x] K1 missing documents and edges (2026-09-28, `feat/kho-du-lieu`, review
  round 1 fixed). Eval at 9a088ae, pinned models,
  `eval/results/kho-luat/sau-k1-*`: golden 77 trúng dẫn 64.0% / 62.7% (K0, two runs) → 56.8% with the 7 labelled superseded
  documents indexed → 61.3% with all 24 unindexed (75/77 ran, the same two
  structural `TruncatedOutputError` rows as K0; answer 78.7%, trích dẫn đúng
  77.0%, equal to K0 run 2). Trap 57: 43 → 45, none lost. Mơ hồ 20: 17 → 17.
- [x] K2 metadata, effectivity, links, cleanup, refresh script (2026-09-28,
  `feat/kho-du-lieu`; backups `backup-truoc-K2.dump` 12:06 and
  `backup-truoc-K2-lan2.dump` 15:55). 1,822 documents after merging two
  gateway-duplicate pairs (33/2005/NĐ-CP keeps 18451, 60/2020/QH14 keeps
  142846; `load_incoming_edges.BAN_TRUNG` stops a reload re-inserting them).
  Issuing body 78 → 1,822/1,822 and signer 77 → 1,816 (`nap_co_quan_tang_nong`,
  parquet). `scripts/lam_moi_hieu_luc.py` read 1,812/1,822 from the gateway
  (`hieu_luc_kiem_luc` set, migration 038): CHL 299 · HHL1P 299 · HHL 1,212 ·
  chua_hieu_luc 2 (gateway `CCHL`) · unknown 10 (gateway HTTP 400/500 on
  every retry; vbpl.vn serves its generic page for the same ids). Only deep
  status change: 12/2022/NĐ-CP CHL → HHL; deep verdicts unchanged. Machine-
  verified vbpl.vn links 0 → 1,812 (evidence `data/seed/link_vbpl_da_kiem.yaml`;
  the 10 failures are the unknown-status ids, none has a chinhphu docid): all
  598 in-force documents carry one. `verified_documents` 0 → 75 (every
  gateway-loaded deep document whose provisions are verbatim substrings;
  145/2020 and 135/2020 miss 4 khoản where a formula/table was moved to
  `hang_bang`). `linh_vuc_chuan` fixed for 64/2020, 15/2012, 43/2024.
  Open: two wrong MOJ edges into 127/2025/QH15 (from 143/2025/QH15 and
  231/2026/NĐ-CP) are in `CANH_SAI` but still in the DB — the delete needs the
  owner (the effectivity date guard skips them, so no verdict changes);
  3 in-force shallow rows store the number with a "số" prefix until K6
  re-ingests them from gateway `docNum`; 528 in-force documents still lack
  full text (K6; their full gateway responses are cached).
  Review fixes (2026-09-29, no DB write): evidence-backed overrides (decision
  item 12) go in `data/seed/hieu_luc_ghi_de.yaml` and win over the gateway on
  every load; a disagreeing gateway is reported, not written. Effectivity
  evidence is committed as `data/seed/hieu_luc_gateway.jsonl` (1,812 rows, built
  offline from the K2 cache) and `lam_moi_hieu_luc --tu-seed` reloads it with 0
  requests: the pre-K2-run-2 rows (1,744 unknown) + seed give the K2 state on
  all 1,822 rows (0 mismatches); on the live DB it changes 0 rows. An outage no
  longer hides documents: a generic page, 403, 429/5xx or transport error keeps
  the previous link and evidence, a source is skipped after 5 consecutive
  failures (K2 had at most 2), and a run that would lose >5 % of checked
  documents writes nothing.
- [x] K1 + K2 integrated with main (K3/K4/K7) on 2026-09-29, `integ/kho-day-du`
  (merge 5a8482d; only the plan conflicted). K7's rule and K2's `CCHL` →
  `chua_hieu_luc` both hold: the two `chua_hieu_luc` rows (04/2026/QH16,
  05/2026/QH16) are shown. Shared DB, read-only, as of 2026-09-29: **480 of
  1,822 shown** (CHL 250, HHL1P 228, chua_hieu_luc 2; 435 of them shallow —
  K6); of the 600 candidates by MOJ status every one has a verified link, 120
  are hidden by the KLAW verdict (`can_doi_chieu_tay` 72, `bi_thay_the` 43,
  `chua_xac_dinh` 5). CI lane 2,891 passed (1 known worktree-only failure);
  the six K7/effectivity/kho/route integration files + `test_lien_quan` 264/265:
  `test_kho_that_so_hieu_trung_thi_neu_het_hai_van_ban` fails on main's code
  too — data, not the merge: 128/2025/NĐ-CP (HHL1P, linked) is hidden because
  an MOJ replacement edge from 03/2026/NĐ-CP (a different title) makes it
  `can_doi_chieu_tay`, the same class as open risk (b) under K7.
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
  `integ/hien-thi-con-hieu-luc`, on main at 5ec9acf). `services/hien_thi` is the
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
- 2026-09-28 (K1): 17 of the 24 new documents are repealed verbatim by a kho
  document (145/2020/NĐ-CP Điều 114 k2, 29/2019/NĐ-CP Điều 28 k2, 09/2020/TT-BLĐTBXH
  Điều 13 k2), but `effectivity` labels them `can_doi_chieu_tay`: the repeal edge
  joins two different titles, so the `cung_chu_de` guard downgrades it, and
  assemble filters only `bi_thay_the`/`het_hieu_luc` from prose. The other 7 are
  labelled correctly, but with them indexed golden 77 fell to 56.8% trúng dẫn
  (K0: 62.7% / 64.0%); 28/2020/NĐ-CP was in the hybrid top 10 of 7 of the 13
  changed questions. All 24 are superseded, so all 24 stay out of the retrieval
  index (`scripts/build_chunks.KHONG_DANH_CHI_MUC`, decision item 8); provisions
  and edges stay for tier 1 and replacement chains. This overrides "indexed" in
  outcome 4 for superseded documents. The voyage index is again the pre-K1 set
  (8,517 chunk/provision id pairs). Owner decision (item 12, 2026-09-28): a
  text-verified edge is not downgraded by `cung_chu_de` — not implemented yet; K7's
  visibility rule supersedes the list. Pre-existing documents with the same defect
  are NOT in the list: 29/2019/NĐ-CP (repealed by 145/2020 Điều 114 k2 điểm c, 58
  chunks, rank 2 for "cho thuê lại lao động"), 135/2020/NĐ-CP, 31/2024/QH15.
- 2026-09-28 (K1): the gateway `/doc/{id}` now returns `references: null` for every
  document (33/33 fresh fetches, including 161263 and 152668, whose 2026-09-02
  cache held 8 and 31); `/doc/154245/related` returned HTTP 500 six times. The 24
  new documents therefore have 0 document-level MOJ relations. `build_seed` warns
  per document; K2 treats gateway references as unavailable, not empty, and keeps
  the cached and parquet relations.
- 2026-09-28 (K1, for K2): MOJ `effFrom` of 38/2019/QH14 is 2019-07-01, but its
  Điều 151 khoản 1 says 01/7/2020; the reason text for 78/2006/QH11 carries the
  MOJ date.
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
