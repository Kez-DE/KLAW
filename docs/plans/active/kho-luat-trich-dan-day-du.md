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
| K5 | Eval AFTER; record the difference; data-source page credit | K2 |

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
- [ ] K1 missing documents and edges. Branch `feat/kho-du-lieu`; review round 1
  fixed. Eval at 9a088ae, pinned models, `eval/results/kho-luat/`: golden 77
  trúng dẫn 64.0% / 62.7% (K0, two runs) → 56.8% with the 7 labelled superseded
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
- [ ] K3 citation display.
- [ ] K4 "Căn cứ" in drafts.
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
  (8,517 chunk/provision id pairs). **Owner decision pending:** a text-verified
  edge class that bypasses `cung_chu_de` (an effectivity invariant change); K7's
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

## Validation

- Data: SQL fill rates before/after; gateway spot checks; effectivity tests.
- Retrieval/answers: golden before/after on pinned models (`so_loi = 0`).
- UI: typecheck + kiem; a real-app check of one labour answer's citation.

## Result

Pending.
