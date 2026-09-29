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

| Wave | Work | Depends on |
|---|---|---|
| T1 | Research: official thể thức rules (NĐ 30/2020 Phụ lục I) and official sample forms per checklist type and per new contract type, from .gov.vn sources | – |
| T2 | Thể thức engine: config per document type, render in ban_thao + A4 preview + Word/PDF export, blanks clickable | T1 |
| T3 | Contract content: mandatory clauses with căn cứ for existing contract checklists; new contract checklists | T1 |
| F1 | Foundational laws: load Hiến pháp 2013 (+ amendments in force) and 64/2025/QH15 (+ 87/2025/QH15) deep, verified, linked, indexed | K11 final eval done |
| F2 | Routing: legal-system questions → tra cứu; kho questions → kho data by type; introduction only for KLAW questions | F1 |
| V | Reviews, e2e in the real app, eval re-run | T2, T3, F2 |

## Risks And Recovery

- Longer drafts overflow A4 pages → the export layout tests and a real-app check.
- A wrong sample-form claim becomes text users sign → only official sources, quoted.
- Routing changes shift eval numbers → eval re-run after F2; F1/F2 wait for the K11
  final eval so its numbers are not confounded.

## Progress

- [x] Decisions; decision record; this plan.
- [ ] T1 research.
- [ ] T2 thể thức engine.
- [ ] T3 contract content.
- [ ] F1 foundational laws.
- [ ] F2 routing.
- [ ] V reviews, e2e, eval.

## Validation

- pytest + kiem for render/export/blank filling; khuôn byte-identical test.
- Real-app check of three draft types and the legal-system question.
- Eval (golden/trap/mơ hồ) after F2, within the owner's ceiling.

## Result

Pending.
