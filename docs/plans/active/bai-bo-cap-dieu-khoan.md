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
   never retrieved, expanded into căn cứ, cited or found by search, and the document page
   shows its number, title and "Đã bị bãi bỏ bởi … từ …" with a link.
2. The retrieval hard field filter reads `nganh_luat` and keeps unclassified documents, so
   showing 102/2024 cannot drop Luật Đất đai 31/2024/QH15 Điều 235/236.
3. NĐ 101/2024 (169188) and 102/2024 (169363) are shown again (verified partial-repeal
   edges to 151/2025/NĐ-CP), with their repealed articles hidden.

## Approach

- Table `bai_bo_dieu_khoan` (migration 043), sibling of `sua_doi_dieu_khoan` so no
  amendment reader mistakes a repeal for an amendment.
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
- An `ingest` that rewrites provision ids cascades the repeal rows away: rerun
  `python -m scripts.nap_bai_bo_dieu_khoan --ghi` (runbook note in `docs/deploy.md`).

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
- [ ] Integrate: merge, paid eval, real-app check of a 101/102 document page.

## Validation

- Focused proof: `tests/test_scripts/test_trich_bai_bo.py`,
  `tests/test_scripts/test_nap_bai_bo_dieu_khoan.py`,
  `tests/test_services/test_bai_bo_dieu_khoan.py`,
  `tests/test_services/test_retrieval_linh_vuc.py`,
  `tests/test_services/test_hien_thi_bat_bien.py`,
  `tests/test_scripts/test_incoming_edges.py` (pure part).
- Integration: `tests/test_services/test_migration_043.py` (explicit path).
- Repository-required checks: CI lane, ruff, frontend `npm run kiem`.
