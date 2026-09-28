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
- [ ] K1 missing documents and edges.
- [ ] K2 metadata, effectivity, links, cleanup, refresh script.
- [ ] K3 citation display.
- [ ] K4 "Căn cứ" in drafts.
- [ ] K5 after eval, credit.

## Decisions

- 2026-09-28: machine-verified links are shown (HTTP 200 + title carries the number
  + issue date matches), evidence stored; see the decision record.

## Validation

- Data: SQL fill rates before/after; gateway spot checks; effectivity tests.
- Retrieval/answers: golden before/after on pinned models (`so_loi = 0`).
- UI: typecheck + kiem; a real-app check of one labour answer's citation.

## Result

Pending.
