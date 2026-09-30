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
- [x] N1 data (`feat/tra-loi-du-lieu`). Code merged. **DB not in the committed state**:
  the shared dev DB still holds the two N1 loai 23 edges 169188/169363 -> 178259 that
  ba25aef says to replace with the parquet loai 21 edges (keep 101/2024, 102/2024
  hidden). Both decrees are shown (486 shown at 2026-09-28) and their repealed articles
  are retrievable: dense replay of the land question (saved query vector, 0 cost) ranks
  101/2024 Điều 30 k12 #4 and 102/2024 Điều 108 #3, #5, #8. Script and backups:
  `.claude/worktrees/_scratch/du-lieu-n1/giu_an_101_102.py`,
  `backup-truoc-giu-an-101-102-20260930.dump`. Needs an authorised run.
  Superseded by decision A (ADR item 9, `feat/bai-bo-cap-dieu`): the verified loai 23 edges are
  now the committed state and both decrees are shown with their repealed provisions hidden.
- [x] N2 routing + meta (`feat/tra-loi-meta`). Migration 042: the three `traces`
  columns exist on the shared DB (checked in `information_schema`); a re-apply from the
  integration stage was refused by the permission layer, backup taken first
  (`_scratch/klaw-truoc-042-20260930-163309.dump`).
- [x] N3 answer composition (`feat/tra-loi-phan-tich`).
- [x] N4 UI copy (`feat/tra-loi-giao-dien`).
- [ ] V reviews, real-app check, eval. Integration `integ/tra-loi-tu-nhien` (not merged
  into main):
  - Conflicts: `gioi_thieu.py` kept the model-written meta rewrite; the lease note kept
    "chưa đối chiếu với Luật Nhà ở…" (the law is deep now, so "chưa trích dẫn được
    nguyên văn" would be false); UI kept the analysis/check-further superset.
  - Integration fixes: scope sentence only on count answers on the meta path too
    (number lookups no longer carry it); the `["kho"]` facet collapse moved from
    `assemble` into `gioi_thieu.khia_canh_luot_kho`; FE/BE key parity made strict.
  - CI lane on 9e8f452: 4323 passed, 1 failed (known worktree-only
    `test_data_raw_VAN_bi_gitignore`);
    ruff clean on changed files, no new format debt; frontend typecheck, `kiem`,
    prettier pass.
  - Replay with fake LLMs (0 paid): land question routed to tra_cuu whatever the
    router says (`route_ep_luat` true on a gioi_thieu verdict), answer with citations
    and an analysis part, invented Điều dropped; "bạn làm được những gì, bạn là ai" and
    "Bạn là ai và bạn làm được những gì" give one model block, facets
    danh_tinh+nang_luc, invented "luật sư AI" sentence dropped; "bạn giúp tôi được chứ"
    no echo line; "pháp luật việt nam chia thành những gì" to tra_cuu; "trong KLAW có
    bao nhiêu bộ luật" hoi_ve_kho with the scope sentence. No "kho" in legal answers.
  - Eval (`eval/results/kho-luat/so-sanh-tl.md`, US$0.6475): golden 71/74 ran,
    trúng dẫn 64.8% (final 66.2% / 64.8%), trích dẫn đúng 85.1% (81.9%), abstain
    11.3% (4.2% / 9.9%); trap 40/57 (42/57), `ngoai_pham_vi` 4/15 (8/15); mơ hồ 15/19
    scored (14/20). Not isolated to this wave (85 main commits since the baseline).
- [ ] Decisions A and B (ADR items 9, 10). Integration `integ/bai-bo-nhan-trap` (main 37b4458 +
  `feat/bai-bo-cap-dieu` + `feat/nhan-trap-pham-vi`, merge 19436f0; not merged into main):
  - Conflict: only the ADR, both items kept (9 repeal, 10 trap labels). Semantic check (DB
    read-only): every trap anchor resolves and none is hidden; the oos-03/04 `cam_dan` lists
    (NĐ 151/2025 repeals) resolve to 0 citable provisions; 102/2024 Điều 105 counts again.
    Stale "hidden" remarks corrected in `trap.yaml` and `trap_duyet_pham_vi.md`.
  - Migration 043 is already on the shared DB (table, PK, FKs, CHECKs match; 296 rows); nothing
    to apply. Document page body checked in-process (0 cost): 101/2024 Điều 9 khoản 5, 11 and
    Điều 30, 102/2024 Điều 54 khoản 1, 5 and Điều 106 show "bãi bỏ bởi Nghị định số
    151/2025/NĐ-CP Điều 21 khoản 4 điểm b/c từ 2025-07-01" with a link; the rest shows.
  - CI lane on 19436f0: 4407 passed, 1 failed (known worktree-only
    `test_data_raw_VAN_bi_gitignore`); pure `test_run_trap.py` + `test_trap_yaml.py` 18 passed;
    read-only integration `test_trap_yaml` anchor test and `test_verify_tier1.py -m integration`
    (10) pass; ruff clean, no new format debt; frontend `npm run kiem` and prettier pass.
  - Eval (`eval/results/kho-luat/so-sanh-bb.md`, US$0.7070, final key usage 25.5283): golden
    run 1 lost 24/74 rows to provider `finish_reason=error` and is not compared; run 2 71/74 ran,
    trúng dẫn 66.2% (tl 64.8%, pairwise +1 on 69), trích dẫn đúng 84.3% (85.1%), abstain 11.3%
    (11.3%); trap old labels 41/55 (tl 40/57), new labels 38/50 (tl re-scored 38/52),
    `trong_pham_vi` 2/8 (oos-04 now passes via 102/2024 Điều 105); mơ hồ 16/20 (15/19); land
    question cites Luật Đất đai Điều 235, 236 and Luật Nhà ở, no BLDS/BLTTDS, no analysis part.
    No row cites a provision recorded as repealed.
  - Open: owner labels for the five `cho_duyet` items; 126/2014 Điều 19–50 and most of 24/2013
    still citable (repeals not recorded; the oos-06 re-run cited 126/2014 Điều 20); the field
    filter drops BLDS/BLTTDS from the land answer (keep, widen or `KLAW_LINH_VUC_LOC=false`);
    real-app check on a running server after merge.

## Result

Pending.
