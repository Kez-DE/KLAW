# Execution Plan: Natural answers — meta questions, situational questions, analysis

Date: 2026-09-30

## Status

Active. Owner decisions accepted 2026-09-30; decision record
`docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md`. Execution delegated to agents.

## Outcome

1. "bạn là ai / bạn làm được gì / bạn giúp tôi được chứ" get one natural answer,
   written by the model from a code-built fact sheet (scope by field with counts,
   draft types, features, limits); unsupported sentences are dropped; no duplicate
   blocks; no stale "labour-only" copy.
2. "tôi đang gặp sự cố tranh chấp nhà đất, cần nắm rõ những bộ luật gì…" is routed to
   tra cứu and answered from Luật Đất đai 2024 (Điều 235, 236…), BLDS, BLTTDS (and Luật
   Nhà ở 27/2023 once loaded), every rule cited and verified, plus a labelled "Phân
   tích cho tình huống của bạn" part; laws that cannot be cited are listed as "Nên đối
   chiếu thêm" — the word "kho" never appears in a legal answer.
3. The scope sentence ("Đây là phạm vi văn bản tôi đọc được…") appears only with
   answers about document counts; UI copy says "pháp luật Việt Nam".
4. Luật Nhà ở 27/2023/QH15 is deep, verified, linked, indexed; the land decrees
   needed for disputes are checked (depth, visibility, edges).
5. "Tôi hiểu câu hỏi của bạn là…" only when the rewrite materially changes the
   question and never for meta; route guard flags and facets are stored in traces.

## Approach

| Wave | Work |
|---|---|
| N1 | Data: Luật Nhà ở 27/2023 deep; land decrees (NĐ 100/2024, 101/2024, 102/2024, 151/2025) depth/visibility/edges; index |
| N2 | Routing + meta: guard fix, fact sheet, model meta answer with sheet check, echo rule, traces fields |
| N3 | Answer composition: analysis part, "Nên đối chiếu thêm", scope sentence only for counts, no "kho" in legal answers |
| N4 | UI copy: scope wording; answer card renders the analysis part |
| V | Reviews, real-app check, eval re-run within the owner's ceiling |

## Progress

- [x] Decisions; decision record; this plan.
- [ ] N1 data.
- [ ] N2 routing + meta.
- [ ] N3 answer composition.
- [ ] N4 UI copy.
- [ ] V reviews, real-app check, eval.

## Result

Pending.
