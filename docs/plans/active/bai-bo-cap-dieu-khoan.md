# Execution Plan: Provision-level repeal, consistent field filter, un-hide 101/102/2024

Date: 2026-09-30

## Status

Active. Owner decision (A) 2026-09-30, recorded as item 9 of
`docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md`. Branch
`feat/bai-bo-cap-dieu`; integration and the paid eval run in the Integrate stage.

## Outcome

1. Every article/khoản/điểm that another document repealed by name, where the repealing
   sentence reads as a full provision list, is recorded with the repealing provision, a
   verbatim quote and the official URL; from its repeal date it and its sub-provisions are
   never retrieved, expanded into căn cứ, cited (nor matched as a quote under a live parent)
   or found by search, and the document page
   shows its number, title and "Đã bị bãi bỏ bởi … từ …" with a link.
2. The retrieval hard field filter reads `nganh_luat` and keeps unclassified documents, so
   showing 102/2024 cannot drop Luật Đất đai 31/2024/QH15 Điều 235/236.
3. NĐ 101/2024 (169188) and 102/2024 (169363) are shown again (verified partial-repeal
   edges to 151/2025/NĐ-CP), with their repealed articles hidden.

## Approach

- Table `bai_bo_dieu_khoan` (migration 043), sibling of `sua_doi_dieu_khoan` so no
  amendment reader mistakes a repeal for an amendment.
- Candidates: loai 23 edges out of, and loai 20 edges into, a shown deep document (an amending
  document also repeals: 49/2026, 226/2025 → 101/102/2024), plus `CAP_THEM`/`DOI_CHIEU_TAY`.
  `DOI_CHIEU_TAY`: sentences the parser deliberately skips, verified by hand, re-checked
  verbatim against the gateway text on every seed run (`kiem_boi: doi-chieu-tay`).
- `scripts/trich_bai_bo.py`: deterministic parser over gateway full text → seed
  `data/seed/bai_bo_dieu_khoan.yaml`; `scripts/nap_bai_bo_dieu_khoan.py` loads it
  (dry-run default, `--ghi`), keyed by (document id, `duong_dan`).
- `effectivity.bai_bo_tai` / `dieu_khoan_bai_bo` judge the repeal date;
  `hien_thi.dieu_khoan_an` feeds `:bai_bo` to retrieval, expand, both search endpoints,
  eval retrieval and the answer-cache fingerprint; `hien_thi.bai_bo_tren_trang` renders the
  document page; `test_hien_thi_bat_bien` enforces the rule on every provision read.
- Edges: `CANH_SAI` drops the parquet "thay thế" edges, `CANH_DOI_CHIEU_NGUYEN_VAN` adds
  loai 23; evidence in `data/seed/canh_doi_chieu.yaml`.

## Risks And Recovery

- Main's code does not read `bai_bo_dieu_khoan`: until this branch reaches the running
  dev server, the shared dev DB shows 101/102/2024 without hiding their repealed articles.
  Re-hide: `.claude/worktrees/_scratch/du-lieu-n1/giu_an_101_102.py --ghi` (edges only).
- Full rollback: `pg_restore --clean` from
  `.claude/worktrees/_scratch/backup-truoc-bai-bo-20260930.dump`.
- An `ingest` that rewrites provision ids cascades the repeal rows away: `ingest` now re-syncs
  the table from the seed after `resolve_all` (fails loudly if a seed row no longer resolves).
- Field filter (ADR 9(c)) now filters every question: BLDS 91/2015 Điều 248 drops from the
  land question; cross-field căn cứ (BLDS/BLTTDS) can drop. Zero-cost golden proxy loses 0/18
  gold. Recommended: do not merge before the paid Integrate eval (golden + trap + land question
  with real rewrite variants); fallback `KLAW_LINH_VUC_LOC=false`.
- Ranking-only leak (ADR 9(e)): 93 chunk anchors (98 chunks) still embed repealed descendant
  text; fix = re-chunk + re-embed those anchors (small paid embed, owner approval). Code ready on
  `feat/bai-bo-bo-sung` (`scripts/nhung_lai_bai_bo.py`); the paid `--ghi` must run AFTER the seed is
  loaded (it refuses otherwise). Rollback: restore the `chunks` backup taken just before.
- Seed reproducibility: `trich_bai_bo` needs five `--tho` folders to regenerate the committed seed,
  two of them under an ephemeral `/private/tmp/…/scratchpad/kho-cache/` session dir (exact list in
  `_scratch/bai-bo-bs/dry-run.txt`); if they vanish, a regeneration fails on `DOI_CHIEU_TAY` or drops
  rows. Copy them to a durable folder before the next regeneration.
- Not recorded: 6 pairs whose repealing text is PDF-only or 400 at the gateway (ADR 9(b)
  list), and every sentence the parser cannot read in full.
- Soạn thảo checklist provisions are not filtered by `:bai_bo` (0 repealed on 2026-09-30,
  `MIEN_BAI_BO` note); filter in `chi_van_ban_hien` once one is.

## Progress

- [x] Parser, seed (56/128 pairs, 61 sentences, 187 provisions), loader, migration.
- [x] Effectivity, visibility, retrieval, expand, search, document page, cache, frontend.
- [x] Field filter on `nganh_luat`; 101/102 edges; ADR item 9; CONTEXT term.
- [x] Data stage on the dev DB 2026-09-30: backup `_scratch/backup-truoc-bai-bo-20260930.dump`;
  `load_incoming_edges --chi-danh-sach` dry-run then `--ghi` (deleted the two loai 21
  edges, backup `_scratch/bai-bo/canh-xoa/`; added two loai 23; canh_doi_chieu 46 rows);
  `nap_bai_bo_dieu_khoan` dry-run then `--ghi` twice (187 rows, idempotent). Shown set
  484 → 486; 1,224 provisions hidden (187 named + descendants).
- [x] Zero-cost proof (saved query vector, real `Retriever` + field filter + `expand`, land-
  dispute question): 0 repealed provisions at every step; 31/2024 Điều 236 rank 1, kept
  by the filter (9 of 10 kept, no fail-open); Điều 235 is dense rank 12 (below top 10 for
  the raw query, not filtered out). Main's code on the same DB: 101/2024 Điều 30 khoản 12
  (repealed) at rank 4 and the raw-label filter keeps only 4 provisions of 102/2024,
  dropping Điều 236.
- [x] Review round 2026-09-30 (6 findings): candidates from loai 20 too, `DOI_CHIEU_TAY`
  (49/2026 Điều 16 khoản 3 điểm d; 226/2025 Điều 7 khoản 3, 4 điểm c), same-day repeal
  allowed (BLHS Điều 292), 6 more gateway texts fetched (5 PDF-only, 1 HTTP 400). Seed 86/363
  pairs, 94 sentences, 296 provisions. Data stage: backup
  `_scratch/backup-truoc-bai-bo-loai20-20260930.dump`; loader dry-run (187 → 296) then `--ghi`
  twice (idempotent); 1,614 provisions hidden, shown set 486. Tier-1 tree excludes repealed
  descendants (`nap_provisions(..., bai_bo)`, `_db_provisions` requires it); invariant test
  requires a `MIEN_BAI_BO` reason for every provisions/chunks reader; soft bonus compares
  `nganh_luat`; `ingest` re-syncs the table. Proof re-run: 0 repealed at every step, 31/2024
  Điều 236 rank 1 and kept.
- [x] Supplement 2026-09-30 (`feat/bai-bo-bo-sung`, owner-approved): `DOI_CHIEU_TAY` +2 sentences —
  123/2015/NĐ-CP Điều 45 khoản 2 điểm đ ("Từ Mục 1 đến Mục 6 Chương III gồm các điều từ Điều 19 đến
  Điều 50 và Điểm a Khoản 1 Điều 63" of 126/2014/NĐ-CP; the request said điểm d, the text says đ) and
  126/2014 Điều 65 khoản 2 (24/2013/NĐ-CP repealed "trừ các quy định về …": the exceptions are the
  titles of Điều 3, 5, 44, which 123/2015 điểm d repealed later, so all 42 others are recorded). The
  "trừ" exception names content, not provisions, so no parser rule generalises (other "whole law …,
  trừ …" targets are shallow). Seed 96 sentences, 371 provisions (hidden 1,614 → 2,037). Scan of all
  363 pairs: no other skipped range/"trừ" sentence in a shown deep document; five verifiable
  other-shape sentences listed for the owner, not recorded (`_scratch/bai-bo-bs/dry-run.txt`). Loader
  now reports `them`/`bot`. READ ONLY preview on the dev DB: +75, −0. Not loaded: the loader's own
  dry-run was blocked for the agent (writes then rolls back); controller runs backup, dry-run, `--ghi`.
- [x] Chunk text (ADR 9(e)): `build_chunks(…, an)` drops repealed descendants from live anchors and
  keeps anchors (split decision on the full text; hidden anchors unchanged); `build_chunks.run`
  passes `dieu_khoan_an`, so a later `--chi-moi` cannot restore the text. `scripts/nhung_lai_bai_bo.py`
  re-embeds only the changed chunks, UPDATE in place, refuses if the table differs from the seed.
  Offline dry-run (`_scratch/bai-bo-bs/re-embed-dry-run.txt`): 94 voyage-4-lite chunks (93 today +
  126/2014 Điều 63), ~42.5k tokens, ~US$0.0008 (ceiling US$0.004). Paid `--ghi` not run.
- [ ] Integrate: merge, paid eval, real-app check of a 101/102 document page. Merged and
  measured on `integ/bai-bo-nhan-trap` (19436f0, not in main): results and open items in
  `docs/plans/active/tra-loi-tu-nhien.md` and `eval/results/kho-luat/so-sanh-bb.md`; the
  document page body was checked in-process only (no running server).

## Validation

- Focused proof: `tests/test_scripts/test_trich_bai_bo.py`,
  `tests/test_scripts/test_nap_bai_bo_dieu_khoan.py`,
  `tests/test_services/test_bai_bo_dieu_khoan.py`,
  `tests/test_services/test_retrieval_linh_vuc.py`,
  `tests/test_services/test_hien_thi_bat_bien.py`,
  `tests/test_scripts/test_incoming_edges.py` (pure part), `tests/test_services/test_chunker.py`,
  `tests/test_scripts/test_nhung_lai_bai_bo.py`, `tests/test_scripts/test_build_chunks.py` (pure part).
- Integration: `tests/test_services/test_migration_043.py` (explicit path);
  `tests/test_agents/test_verify_tier1.py -m integration` (repealed-quote case).
- Repository-required checks: CI lane, ruff, frontend `npm run kiem`.
