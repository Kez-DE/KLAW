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
- [ ] F1 foundational laws.
- [ ] F2 routing.
- [ ] V reviews, e2e, eval.

## Validation

- pytest + kiem for render/export/blank filling; khuôn byte-identical test.
- Real-app check of three draft types and the legal-system question.
- Eval (golden/trap/mơ hồ) after F2, within the owner's ceiling.

## Result

Pending.
