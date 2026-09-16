# Execution Plan: Trợ lý suy luận và trả lời như một luật sư

Date: 2026-09-16

## Status

Active

## Outcome

Observable through the real API and UI once complete:

1. "bạn làm được gì, có những bộ luật gì, có những lĩnh vực pháp luật gì" returns
   three short blocks in the order asked; the code list and domain list come from
   the running corpus, not from a hard-coded template; no "Dựa trên" line is shown
   for that turn; the session profile does not gain a fake `vu_viec`.
2. A legal answer opens with the conclusion, lists at most four conditions or
   exceptions that change it, and closes with at most one question that names a
   decisive missing fact. Wording strength matches evidence: certain, conditional,
   or insufficient — computed deterministically, not by model confidence.
3. Every verified claim carries a role (`ket_luan` / `dieu_kien` / `ngoai_le` /
   `che_tai`); tier 2 rejects claims that are legally supported but off-goal.
4. Follow-up turns answer only the new part of the question; sessions with a
   summary are never greeted again.
5. Baseline and post-change measurements exist for the same commit family, model,
   and corpus with `so_loi = 0`; release gates in `cai_thien.md` §8 decide the
   default prompt, not taste.

## Context

- Owner decisions 2026-09-16 (grilling round, all recommendations accepted):
  keep the thesis contract (every legal statement anchored to a verified
  citation; the model is never a source of law); the "new reasoning" is the
  request frame, claim roles, relevance check, decisive-fact questions and a
  rewritten SOUL — not free recall. No control plane, evidence graph, risk gate,
  tool registry, multi-agent, or `/v2` API this round.
- Authority: `ex.md` (meta answers), `cai_thien.md` §3, §5, §6 GĐ0–GĐ4, §8, §11;
  `docs/superpowers/specs/2026-09-16-tra-loi-ngan-dung-muc-tieu/` (GĐ0+GĐ1, its
  code is in the working tree and green: 283 passed);
  `/Users/kenz_de/Downloads/FULL_PLAN.md` is reference only (§29, §30, §45, §52
  inform the answer shape and SOUL v3; §51 P0–P2 is the slice we take).
- Verified call graph: `route.v3` → `gioi_thieu` → `_RE_TAT` shortcut →
  `graph_tra_cuu.n_assemble` → `assemble` → `gioi_thieu.cau_gioi_thieu` →
  regex fall-through → `_NANG_LUC_MAU` (hard-coded scope). 0 LLM, SOUL not
  injected. `assemble._base` sets `ho_so_da_dung` to the whole profile for every
  result type; `DuaTren.tsx` returns null on an empty list. `bo_nho.cap_nhat_phien`
  runs after every turn without the turn's intent.
- Models pinned for measurement (owner, spec 2026-09-16): router + generate
  `deepseek/deepseek-v4-flash-0731`, judge `mistralai/mistral-small-3.2-24b-instruct`.
  `.env.local` currently points router/generate at `google/gemini-2.5-flash-lite`;
  measurements override per command via `OPENROUTER_MODEL_NAME` /
  `OPENROUTER_GENERATE_MODEL_NAME`, never by editing `.env.local`.

## Scope

In scope:

- Slice 0: commit the green GĐ1 work already in the tree (path-scoped).
- Slice 1: GĐ0 baseline — `assemble.v3/v4/v5` × 77 golden questions, 57 traps,
  20 ambiguous questions; cache off; cost ceiling US$6.
- Slice 2: `ex.md` — facet decomposition inside the meta branch, dynamic scope
  from `kho.py`, correct provenance, memory guard.
- Slice 3: GĐ2 — `khung_yeu_cau` produced by the existing `rewrite_query` turn.
- Slice 4: GĐ3 — claim `vai_tro`, tier-2 relevance, deterministic `muc_chac`,
  claim selection in `assemble`, additive `vai_tro` on citations.
- Slice 5: GĐ4 — decisive-fact questions, `cau_hoi_goc` + `cau_hoi_day_du` in the
  prose prompt, no repetition on follow-up turns.
- Slice 6: `prompts/soul.v3.md`, switchable, default flipped only after gates.
- Slice 7: re-measure, compare, decision record, report.

Out of scope:

- GĐ5 drafting conversation, the 40-case `chat_quality` set and its human review.
- `route.v4` with runtime-injected scope (follow-up).
- Any change to `abstain_threshold`, citation verification, effectivity rules,
  HTTP contract shape beyond additive optional fields, database schema.
- Owner's long-lived uncommitted files (`src/services/checklist.py`,
  `tests/test_services/test_moi_mau.py`, `docs/guide/*`, `scripts/*`, `.agents/`,
  `eval/datasets/golden_qa_candidates.yaml`, `CLAUDE.md`, screenshots) are never
  staged.

## Approach

Each slice: red test first, smallest diff, focused tests, lint, path-scoped
commit. Names follow repo convention (Vietnamese identifiers): `khia_canh`,
`khung_yeu_cau`, `vai_tro`, `muc_chac`. Glossary entries land in `CONTEXT.md` in
the slice that introduces the term.

Slice 2 design (ex.md):

- `kho.py`: `danh_sach_bo_luat(kho)` and `tom_tat_linh_vuc(kho)` built on
  `_van_ban_dang_dung`, `hien_van_ban`, `_nhan`, `_do_sau_linh_vuc`. One data
  source, one effectivity rule. No second SQL.
- `gioi_thieu.py`: `khia_canh(cau_hoi) -> list[str]` ordered by first match
  position; blocks `danh_tinh`, `ban_chat`, `nang_luc` (new, short, no scope
  list), `bo_luat`, `linh_vuc`, `soan_thao`, `nguon`, `model`; `gioi_han` =
  `CAU_GIOI_HAN` appended once when `bo_luat` or `linh_vuc` is present. Greeting
  prefix only on a first turn whose question starts with a greeting. Pure
  greeting / thanks unchanged. Unknown → `nang_luc`.
- `graph_tra_cuu.n_assemble`: for `gioi_thieu` and `hoi_ve_kho`, compute facets
  once; kho-only → existing `tra_loi_ve_kho` / table path; assistant-only → no DB;
  mixed → `nap_kho` once and compose. `assemble()` signature unchanged.
- `assemble._base`: `ho_so_da_dung=[]` for `gioi_thieu`, `hoi_ve_kho`,
  `out_of_scope`. Drafting branches keep it (`gom_du_kien` reads `ho_so`).
- `bo_nho.cap_nhat_phien(..., result_type)`: meta turns update `tom_tat`, skip
  `gop_ho_so`. Both API routes pass `payload["result_type"]`.

Slices 3–5 design (cai_thien GĐ2–GĐ4): see the Decisions section as they are
made; the invariants are: no new LLM call on the normal success path; JSON
failure falls back to the previous behaviour; `khung_yeu_cau` never carries
article numbers, document numbers, legal thresholds or PII (`hoi_lai.bi_loai`,
`bo_nho._vuong_luoi_chan`); a value stated by the user beats a model inference;
`result_type` enum unchanged.

## Risks And Recovery

- Baseline on deepseek hung once for 1 h 53 min (SSL read). Mitigated by the
  per-question 600 s ceiling and parallelism 5 already in `run_cau_tra_loi`.
  Recovery: a run with `so_loi > 0` is discarded and rerun; never compare on a
  smaller denominator.
- Facet regexes misfire on real phrasing. Recovery: unknown → capability block,
  same safe default as today; every facet has a test with a real sentence.
- Tier-2 relevance rejects too much and raises abstain. Gate SC-003/SC-004 in
  `cai_thien.md` §8 blocks the default flip; rollback is the prompt path
  (`KLAW_ASSEMBLE_PROMPT`, `verify_tier2` prompt version) — old prompts are never
  edited.
- Schema changes with `strict: True` break older prompts. Schema is chosen by
  template content (pattern already used in `rewrite_query.py`).
- Rollback per slice: each slice is one or two commits; `git revert` of the
  slice restores behaviour; no migration involved.

## Progress

- [ ] Slice 0 — commit GĐ1 (eval metadata + parallel runner; shape cap + tail;
      Makefile lanes; spec docs).
- [ ] Slice 1 — baseline v3/v4/v5 ×77, trap 57, mo_ho 20 on deepseek, cache off.
- [ ] Slice 2a — `kho.py` pure list/summary functions + tests.
- [ ] Slice 2b — `gioi_thieu.py` facets + composer + tests (contract changes to
      three existing tests per `ex.md`).
- [ ] Slice 2c — `graph_tra_cuu.n_assemble` wiring, one `nap_kho`.
- [ ] Slice 2d — provenance (`_base`) + memory guard + both routes + tests.
- [ ] Slice 2e — `CONTEXT.md` glossary; regression run.
- [ ] Slice 3 — `khung_yeu_cau` (rewrite_query.v3) + state + fallback tests.
- [ ] Slice 4 — claim `vai_tro`, tier-2 `relevant`/`overstated`, `muc_chac`,
      selection rules, additive citation field.
- [ ] Slice 5 — decisive-fact questions, `cau_hoi_goc` in prompt, no-repeat tests.
- [ ] Slice 6 — `soul.v3.md`, `KLAW_SOUL_PROMPT` switch.
- [ ] Slice 7 — re-measure, gates, decision record, move plan to completed.

## Decisions

- 2026-09-16: Meta branch stays 0-LLM; "not fixed" means composed from live data
  per facet, not model-generated (owner, Q1/Q2).
- 2026-09-16: `route.v3` scope text left unchanged this round (owner, Q7).
- 2026-09-16: Kho-only questions keep the existing `hoi_ve_kho` text path; the
  short code/domain blocks appear only in composite answers (ex.md §3.3).
- 2026-09-16: `muc_chac` is computed in code from claim roles and missing decisive
  facts, then fed to the prose prompt; no new `result_type` (owner, Q6).
- 2026-09-16: SOUL v3 keeps the three promises, professional boundaries and
  injection rules; drops the long voice/method sections (owner, Q3).

## Validation

- Focused proof (per slice):
  `KLAW_SUPABASE_URL= .venv/bin/python -m pytest -q -m "not integration and not pending_review" <slice test files>`
- Regression lane (whole default lane, same as CI):
  `KLAW_SUPABASE_URL= .venv/bin/python -m pytest -q -m "not integration and not pending_review" --deselect tests/test_services/test_moi_mau.py`
- Lint on touched files: `.venv/bin/ruff check <files>` and
  `.venv/bin/ruff format --check <files>` (never `make format`).
- Measurement (paid, owner-authorised, ceiling US$6):
  `OPENROUTER_MODEL_NAME=deepseek/deepseek-v4-flash-0731 OPENROUTER_GENERATE_MODEL_NAME=deepseek/deepseek-v4-flash-0731 KLAW_CACHE_TTL_NGAY=0 .venv/bin/python -m eval.run_cau_tra_loi --prompt prompts/assemble.v3.md --json eval/results/deepseek/v3-77.json`
  (same for v4, v5, later v6), `python -m eval.run_trap --out …`,
  `python -m eval.run_mo_ho --out …`, then
  `python -m eval.run_cau_tra_loi --bang eval/results/deepseek/*.json`.
- Gates before flipping any default: `cai_thien.md` §8.

## Result

Pending.
