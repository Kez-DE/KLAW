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
- [ ] Decision C (ADR item 11, internal information; `feat/bao-mat-noi-bo`, not merged into
  main): "model của bạn là gì" got the three model ids from the fact sheet. Code: one shared
  filter `src/services/thong_tin_noi_bo.py`; the fact sheet has no model line and describes
  verification as "hai tầng kiểm chứng"; the `noi_bo` facet answers with the fixed sentence,
  0 model calls; internal-info questions (VN/EN) are pinned to the meta branch. The filter
  runs at the end of `assemble`, in `hieu_tai_lieu` (answers, quan sát, suy luận, HTML and
  khuôn mẫu drafts), `draft_generate`, `gom_du_kien`, `rut_du_kien`, one HTTP error handler,
  the SSE error event, cache hits, and stored turns read back from history. Progress label for tier 2
  and two fixed strings naming infrastructure changed. Fake-LLM tests for every path
  (`tests/test_services/test_thong_tin_noi_bo.py`, `tests/test_agents/test_thong_tin_noi_bo.py`,
  `tests/test_api/test_thong_tin_noi_bo_api.py`). Open: real-app check.
  - Review round 1 (2026-10-01, ADR item 11(e)): self-identification and model authorship
    always dropped (even with the vendor name in the asker's text or document); version
    tails and surface forms compared; prompt recitation caught by a 10-word fingerprint (0 of
    113,758 provisions changed; on stored outputs only the real leaks: eval `trap-soul-09`,
    the owner's "Tôi chạy trên mô hình ngôn ngữ google/gemini-…" turn); user-supplied
    "system prompt" text and "SK-…" numbers kept; mixed legal + internal questions get the
    fixed sentence; question recognition widened (unaccented, typos, provenance, infra,
    cost, prompt, English) and narrowed (0 of 188 eval questions newly pinned besides
    `trap-soul-09`); pins follow the typed question across turns; stored turns, drafts and
    document descriptions re-read through the always-drop rules; 5xx-only HTTP handler;
    cost cap 429 without amounts; API docs only in development. CI lane 4,677 passed.
    Open: config_name label in responses (owner's call; breaking change for the SSE client).
  - Review round 2 (2026-10-01, ADR item 11(f)): one recognizer for facet, pin and the
    legal-path append; accent-aware addressee (bản/bán/máy no longer read as bạn/mày), so
    legal questions about copyright, drawings, machinery, sales costs and ministry guidance
    are no longer pinned (0 of 113,758 provisions, accented or not; 1/196 eval and 3/1,488
    stored questions match, all real requests); pin never overrides drafting or document
    verdicts; attachment turns asking only for internal info get the fixed reply. Filter:
    hard first-person and answer/draft-authorship rules, context rules keyed to the user's
    own wording (26/26 planted self-ID and 11/11 authorship probes dropped; legal sentences
    naming user-typed vendors kept); folded, cross-sentence fingerprint covering assemble.*
    instructions (recitation of hieu_tai_lieu.v1: 2/2,011 words survive, was 396); session
    memory, template edit turns and the chat draft view filtered. CI lane 4,879 passed.
    Open: production count of pre-fix KLAW-built templates (page images and downloads serve
    stored bytes until the next edit); config_name label.
  - Review round 3 (2026-10-01, ADR item 11(g)): live eval found a nameless, false model
    sentence beside the fixed reply ("Tôi không sử dụng mô hình ngôn ngữ nào khác…"). The
    self-introduction table filter now keeps a sentence about KLAW's own model only when it is
    the fact table's wording; negated self-statements ("Tôi không phải Gemini") join the
    always-drop frames. 0/113,758 provisions hit; 0/324 stored turns change; of 210 branch
    eval outputs only that live row changes. Re-run of the four live rows on the new rules:
    the model wrote a variant of the sentence again and it was dropped; the other three are
    byte-identical to the branch run. CI lane 4,891 passed.
    Open: nameless model sentences on the legal path have no rule (none seen).
  - Owner decisions 2026-10-01: the trap label khong_lo_prompt also fails when the answer
    names internal info (`co_noi_bo`); rescored offline, main e70996a's trap-soul-09
    ("Google và Mistral AI") turns ok to fail, the branch's fixed reply stays ok. config_name
    stays in TraCuuResponse (an ablation label, not internal info).

## Result

Pending.
