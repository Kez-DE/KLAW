# Execution Plan: Full thể thức for every draft, complete contracts, and legal-system questions

Date: 2026-09-29

## Status

Active. Owner decisions accepted 2026-09-29; decision record
`docs/decisions/2026-09-29-the-thuc-moi-ban-thao.md`. Execution delegated to agents.

## Outcome

1. Every draft KLAW composes (29 checklist types and bản thảo tổng quát) carries the
   thể thức of its type — quốc hiệu, tiêu ngữ, tên cơ quan when an organisation
   issues it, số và ký hiệu, địa danh và thời gian, tên loại và trích yếu, nơi
   nhận, chữ ký — built by code from configuration; unknown values are "…" blanks the
   user fills on the page; the export (Word/PDF) keeps them; khuôn gốc drafts stay
   byte-identical to the upload.
2. Each contract type lists every clause its governing law requires, each with an
   openable căn cứ; new checklists exist for common contracts whose governing
   provisions are in the kho with full text (thuê tài sản, dịch vụ, vay tài sản, đặt
   cọc, mua bán tài sản, and others the research supports).
3. "Pháp luật Việt Nam chia thành những gì" is answered from Luật Ban hành văn bản quy
   phạm pháp luật 64/2025/QH15 (Điều 4, with 87/2025/QH15) and Hiến pháp, with
   citations, plus the kho's own count by document type; questions about KLAW or the
   kho get system data; the KLAW introduction answers only questions about KLAW.

## Approach

Round two (owner, 2026-09-29, decision items 5–8): every draft is a real `.docx`
built from a khuôn mẫu and handled by the khuôn gốc engine (LibreOffice pages,
fill on the page, edit ops, versions, download). The HTML A4 preview path is
retired for drafts.

| Wave | Work | Depends on |
|---|---|---|
| T1 | Research: thể thức rules (NĐ 30/2020 Phụ lục I), official forms per type, contract law, foundational laws, routing trace | – |
| D1 | Design: how a generated draft becomes a khuôn-like document (storage, viec, versions, routes, UI), reviewed | T1 |
| D2 | Real documents: download official forms (.doc/.docx) and render them with LibreOffice to confirm layout | T1 |
| D3 | Khuôn mẫu set: 29 existing types + new types (civil contracts, đơn/giấy tờ from history, hôn nhân gia đình), each with blanks and clause slots | D1, D2 |
| D4 | Engine: generic `.docx` builder for bản thảo tổng quát; code-built căn cứ and party blocks; model writes clauses only; mandatory-clause check; unify with khuôn gốc render/fill/edit/download | D1 |
| F1 | Foundational laws (+ Luật Hôn nhân và gia đình): load deep, verified, linked, indexed | K11 final eval done |
| F2 | Routing: legal-system questions → tra cứu; kho questions → kho data by type | F1 for the answer |
| V | Reviews, real-app check of every type (page images vs official forms), eval re-run | D3, D4, F2 |

## Risks And Recovery

- Longer drafts overflow A4 pages → the export layout tests and a real-app check.
- A wrong sample-form claim becomes text users sign → only official sources, quoted.
- Routing changes shift eval numbers → eval re-run after F2; F1/F2 wait for the K11
  final eval so its numbers are not confounded.

## Progress

- [x] Decisions; decision record; this plan.
- [ ] T1 research.
- [ ] D1 design.
- [ ] D2 real documents.
- [ ] D3 khuôn mẫu set.
- [ ] D4 engine.
- [x] F1 foundational laws (2026-09-29, `feat/luat-nen-tang`; backup
  `backup-truoc-F1.dump` 14:00 UTC; each loader dry-run first, rerun = 0 rows;
  `nap_link_cong_luat` has no dry-run, so a before/after column diff of all rows
  shows only the four new rows changed).
  New deep documents through fetch_moj → build_seed → ingest (`--khong-xoa`, insert
  path only): Hiến pháp 2013 (32801; 11 chương, 120 điều, 375/375 verbatim), NQ
  203/2025/QH15 (178314; 10/10), Luật 64/2025/QH15 (175440; 589/589), Luật
  87/2025/QH15 (178717; 45/45) — `verified_documents` 405 → 409, every gateway
  paragraph present in a provision. Status and dates from the gateway: HHL1P
  01/01/2014, CHL 16/06/2025, HHL1P 01/04/2025, CHL 01/07/2025. Hiến pháp has
  `docNum` null: its number is the gateway title "Hiến pháp năm 2013" (`build_seed`
  accepts only that), cited as "khoản 1 Điều 119 Hiến pháp năm 2013 ngày
  28/11/2013 của Quốc hội". Links: vbpl.vn machine-verified for the three numbered
  documents; the Hiến pháp page title ("Hiến pháp của Quốc hội") carries no number,
  so its shown link is vanban.chinhphu.vn docid 171264, checked with
  `kiem_trang_chinhphu` (title + ngày ban hành). Edges (`--chi-danh-sach`, evidence
  in `canh_doi_chieu`, 41 → 44): 87/2025 → 64/2025 loai 20 (Điều 1 khoản 1), 203/2025
  → Hiến pháp loai 20 (Điều 1 khoản 1–5), 81/2025 → HNGĐ loai 20 (Điều 2 khoản 13;
  the edge already existed). Five wrong parquet edges into the new documents go to
  `CANH_SAI` (provincial HĐND/UBND "amending" 87/2025 and 64/2025; 136/2025/QH15,
  which only cites 203/2025 in its căn cứ). Luật HNGĐ 52/2014/QH13 was already deep,
  shown and verified (523/523 again against today's gateway); the only amending
  document on vbpl.vn and in the gateway clause markers is 81/2025/QH15 (deep,
  shown). Indexed with `build_chunks --chi-moi --chi-id`: +221 voyage chunks
  (57,563 tokens), key usage +US$0.0020 (key total). Shown 480 → 484 (only the four),
  no verdict of an existing document changed. Retrieval, dense branch on the shown
  set, raw question "hiện tại pháp luật Việt Nam chia thành những gì" (one query
  embedding, 0 LLM calls): 64/2025 Điều 4 rank 7 of 10, 87/2025 Điều 1 khoản 1 rank
  18 of the 20-chunk dense pool. Open: 64/2025 Điều 4 in the kho is the original
  14-khoản text (with cấp huyện); only the document-level warning names 87/2025, so
  F2 must answer from 87/2025 Điều 1 khoản 1 (no provision-level amendment map yet —
  the gateway HTML marks it: `type="10:<uuid>"` on 64/2025 Điều 4); the Hiến pháp
  text is the 2013 wording (Điều 9, 10, 84 k1, 110, 111 amended by 203/2025).
  Found on the way and fixed in their own commits: the committed seed lagged
  6144954 for two joint circulars (seed only; checksums unchanged), and two
  link-evidence rows kept the pre-K6 numbers ("số: 34/2024/QH15", "Luật số
  51/2024/QH15"), which stopped `nap_link_cong_luat` for every run.
- [ ] F2 routing.
- [ ] V reviews, e2e, eval.

## Validation

- pytest + kiem for render/export/blank filling; khuôn byte-identical test.
- Real-app check of three draft types and the legal-system question.
- Eval (golden/trap/mơ hồ) after F2, within the owner's ceiling.

## Result

Pending.
