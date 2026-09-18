# Execution Plan: Drafting without the checklist gate, and an account that remembers

Date: 2026-09-18

## Status

Active. Phases 15 and 16 are merged and pushed. Phase 14 and Phase 12 part A are
implemented, reviewed, fixed and merged locally. Phase 12 part B is implemented
on `feat/bo-nho-tai-khoan` and awaiting review.

## Outcome

Observable through the real API and UI once complete:

1. A drafting request that matches none of the 29 checklists is drafted anyway,
   with no label and no "Kho mẫu của tôi chưa có loại văn bản này" dead end.
2. A drafting request that matches one of the 29 is also drafted when the user
   does not use the form. The checklist is offered; it is never a gate on the
   chat path. It stays compulsory nowhere and available everywhere on
   `/soan-thao`.
3. A drafting request in a conversation that already owns a document is drafted
   from that document, instead of ending at "Lượt này tôi chưa soạn được mục nào."
4. KLAW speaks about Vietnamese law, not about "kho của tôi": an answer names the
   instrument ("Điều 47 Bộ luật Lao động 2019"), and the scope admission survives
   so the new wording never promises coverage the corpus does not hold.
5. A question whose retrieval returns nothing usable still gets a substantive
   general explanation, carrying no Điều/Khoản/Điểm citation at all — and a
   citation that cannot be verified is still rejected by the anchor check.
6. The account screen lists everything KLAW has remembered about the user, and
   every item can be deleted, one at a time or all at once.
7. A fact stated in one conversation is recalled in another conversation of the
   same account, and never poured into a document the user did not ask for it in.

## Context

The owner hit the drafting dead end four times, once while simply asking *"đây là
đơn gì"*, and asked for two things in the same sitting: stop treating the 29
checklists as the boundary of what KLAW can write, and stop calling the legal
corpus "kho của tôi" when what is being quoted is the statute itself. Separately
they asked to be remembered — "tôi muốn việc này được nhớ nhưng mà ko phải văn
bản mới mà khách yêu cầu khác là điền luôn mà chỉ cần nhớ thôi" — which is the
one rule Phase 12 exists to honour: remember, do not apply.

Work ran as numbered phases in throwaway worktrees, with one implementer and one
independent reviewer per phase. The briefs and per-phase reports live with those
worktrees under the session scratchpads, which do not survive a `/tmp` sweep; this
file is the part that has to outlive them.

## Scope

- Phase 14 — drafting freedom (R1–R6 of its brief): delete the refusal strings,
  route a drafting turn to the general drafting node, keep the checklist as an
  offer, sweep the "kho" wording, answer without citations when retrieval finds
  nothing.
- Phase 12 part A — the store: migration `034_bo_nho_tai_khoan`, the service, the
  list/delete API, and the "Điều KLAW đã nhớ về bạn" card.
- Phase 12 part B — extraction during a drafting turn, the "đã nhớ" line, recall
  into the prompt, and the proof that nothing is auto-filled. Not started; it
  waited for Phase 14 because both edit `hieu_tai_lieu.py`.
- Out of scope: removing the 29 checklists or the `/soan-thao` screen; changing
  what `audit_report.muc_kiem` means; loosening the anchor check; storing
  documents or transcripts in account memory.

## Decisions

- **D14-A — no "chưa kiểm pháp lý" badge on a chat-drafted document.** The owner
  accepted that a user can download a labour-law document without that
  distinction on screen. The record still carries the truth: `muc_kiem` keeps
  saying what actually ran, for both draft kinds. `nhanMucKiem` now takes `loai`
  and returns null only for `tong_quat`, so a hand-edited checklist draft still
  shows "Đã sửa tay — chưa kiểm pháp lý" and Phase 3's downgrade toast survives.
- **D14-B — the checklist is not a gate in chat.** Per-clause citations and
  `muc_kiem = kiem_phap_ly` come from the checklist path, so a chat draft will
  not have them. The 29 stay whole on `/soan-thao`.
- **D14-C (2026-09-18) — `soul.v2.md` and `soul.v3.md` carry a named exception
  for the general-explanation turn.** SOUL promise 1 forbids answering from the
  model's own knowledge and declares the stricter rule the winner; R6 asks for
  exactly that on one narrow turn. The owner chose a carve-out in the promise
  document over calling that turn with `co_soul=False`, so the promise still
  reads as one coherent rule and `assemble` stays in `CO_SOUL`. The prohibition
  the exception must not dent: a citation is never allowed without a real
  provision behind it.
- **D14-D (2026-09-18) — an explanation that trips the guard is dropped whole.**
  The turn has already been paid for and the user still sees the abstain. The
  owner chose the fail-closed direction over sentence-level redaction, which
  would have to cut Vietnamese sentences correctly and can read as evasive. The
  drop rate is to be measured, not assumed; the trace key is
  `assemble_giai_thich == "bi_loc"` and nothing counts it yet.
- **D14-E (2026-09-18) — the drafting trap measures the new behaviour.**
  `eval/run_trap.py` scored `soan_thao_loai` with `rt == "huong_dan_soan_thao"`,
  a result type no path produces after Phase 14, which would have scored 0/3
  forever. The scorer now accepts a real draft, and the login invite that an
  anonymous runner necessarily gets. The three `trap.yaml` items keep their
  questions and their `loai_chap_nhan` values.
- **D12-A — account memory is a separate table, not an extension of
  `ho_so_tai_khoan`.** That table is the Pro-only legal-situation profile whose
  guard *rejects* 9–12 digit strings and other identity traces; the owner's
  revised scope (remember họ tên and mã SV) inverts that rule, so extending it
  would mean punching a hole in a guard that is right for its own purpose.
- **D12-B — seeing and erasing personal data is not a plan perk.** The `da-nho`
  endpoints are behind `nguoi_dung_bat_buoc` but not Pro-gated.
- **D12-C (2026-09-18) — "the user asking in that turn" is a deterministic
  per-key test, not the model's judgement.** `hieu_tai_lieu.BO_NHO_KHOA` maps
  each key to the Vietnamese labels people type for it; a turn naming one
  ("điền họ và tên của tôi vào") makes that key's value a legal source for
  `_nguon_soan`, and every other remembered value goes into `cam`. The whole
  memory is still in the prompt as context, because the guarantee has to live
  in code — `lam_sach_van_ban` — not in a prompt instruction, and because a
  negative test that only proves "the model never saw it" proves nothing about
  the document. Recognising a request is biased toward "not asked": a missed
  fill is one field the user retypes, a wrong fill breaks the one rule.
- **D12-D (2026-09-18) — the existing value cleaner could not carry this
  alone.** `_RE_GIA_TRI` only sees digit-bearing strings and email addresses,
  so a remembered NAME sailed through it untouched; the `cam` pass is the
  narrow addition that closes exactly that hole, counted separately in
  `traces.dung_ban_thao_so_bo_nho_chan` so the rate is measured, not assumed.

## Progress

- [x] Phase 15 — smooth editing UI. Reviewed clean bar one MED (hover contrast,
      fixed in `21cff09`), merged as `8f64b45`, pushed.
- [x] Phase 16 — long documents split across replies, failure spend recorded.
      Reviewed, fix round `9220037` + `62ec459`, merged as `4a307e8`, pushed.
- [x] Phase 14 — implemented (`526e961`, `5b76bdf`, `0b3fd65`), reviewed
      FIX FIRST, fixed (`fa06eb9`, `4252829`), owner decisions D14-C/D/E applied
      (`4d0a274`, `919df0e`, and the SOUL/wording round).
- [x] Phase 12 part A — implemented (`96e8d72`, `128fd07`, `361e0e1`), reviewed
      clean bar one MED, fixed (`1350ae7`, `dfc038c`).
- [x] Phase 14 merge round — the merge exposed seven failures the phase gates
      never ran; fixed in `b965e77`, `7fdfe25`, `3373ebd`, `9862e01`. Final gate
      on `main`: 2772 passed, 5 standing failures, ruff clean, `npm run kiem`
      exit 0.
- [x] Phase 12 part B — implemented. Extraction is a deterministic 0-token
      read of the user's own sentence (`hieu_tai_lieu.rut_bo_nho`), so no
      drafting turn gains a model call; `graph_tra_cuu._ghi_bo_nho` writes it
      and keeps the labels `ghi` reported as `"moi"`/`"doi"`, which
      `assemble.DA_NHO` says in that turn's answer. Recall reaches the model as
      a prompt block (`_khoi_bo_nho`), the same way `# Bản thảo đang có` does,
      and `lam_sach_van_ban(cam=…)` replaces any remembered value the turn did
      not ask for with `[…]` before it can become a clause.

- [x] Phase 12 part B review round — reviewed FIX FIRST on three HIGH findings,
      each reproduced before and after the fix (`5452a92`, `139d7b5`,
      `3e336d2`), merged as `45bd024`. What it caught: a remembered value
      reached the document through `truong[]`, bypassing the block and landing
      in `du_kien_tai_lieu` as well; the block itself deleted ordinary
      Vietnamese prose, so a remembered `nganh = "Luật"` turned "tuân thủ Bộ
      luật Lao động" into "Bộ […] Lao động" and a `xung_ho` of "em" gutted every
      sentence opening with it; and both the extractor and the "did the user
      ask" gate read `cau_hoi_day_du`, the model's own restatement, so a third
      party's name from earlier in the conversation overwrote the account's own
      and unlocked autofill. Two more: a pasted form stored every label line as
      a fact about the account, and a failed memory write logged the value
      through SQLAlchemy's `[parameters: …]`.
- [ ] Phase 12 follow-ups, deliberately not blocking the merge: the memory block
      is built for every `hieu_tai_lieu` turn including pure reading ones, whose
      output never passes the block pass, so a summary answer can name the
      remembered person unprompted; `_bo_qua_cache` does not list account memory
      as a state input (latent — unreachable while drafting results are never
      cached, a cross-account leak the day one is); and one-word labels (`lop`,
      `nganh`, `van_phong`) count as "asked" from any sentence containing them.

## Risks And Recovery

- **The one guarantee this work must not weaken** is that a citation is
  verifiable. Phase 14's review caught the real instance: the explanation path
  had built a second, weaker copy of a guard the same file already imported, so
  "Bộ luật Lao động 2019 quy định thời gian thử việc tối đa 60 ngày." reached the
  reader unchecked. The fix reuses `bi_loai` + `kho.moi_so_hieu_trong` on the
  normalised string. The repo rule it restores is recorded at
  `giai_nghia.dinh_danh_bia`: each family reuses the detector that already
  exists rather than building a second copy of the same rule.
- **Routing is the other recurring risk.** An earlier session widened
  "conversation owns a document → route to `hieu_tai_lieu`" into every turn and
  broke retrieval and citations for the whole conversation; it had to be rolled
  back. Any change to `graph_tra_cuu` is reviewed against that incident.
- **Account memory is personal data**, including a student identifier. Deletion
  is a real row delete, ownership is filtered in SQL on every statement, and a
  delete of someone else's id answers 404 rather than 403 so it leaks nothing.

## What the merge caught that the phase gates did not

Phase 14 passed 871 non-integration tests and still broke seven that only run with
a database. Two were stale assertions from the R5 wording sweep
(`test_kho.py`, integration-marked, so the implementer's `-m "not integration"`
lane never saw them). The other five pointed at something larger:

**Chat drafting was neither gated nor metered.** Phase 14 made
`dung_ban_thao_tong_quat` the default chat drafting path, and that node never
called `bao_ve.kiem_han_muc` and never wrote the `/api/v1/soan-thao` traces row
that `bao_ve.dem_luot` counts — both of which the checklist path does
(`graph_tra_cuu.py:427-431`, `:438-450`). From that commit until the fix, the
draft quota existed only on the `/soan-thao` screen and the legacy checklist
path, and an out-of-quota user got `CHUA_SOAN_DUOC` ("Chưa soạn được lúc này.")
instead of being told about the quota. Fixed by putting the general path through
the same gate, with an edit deliberately exempt (its ceiling is `TRAN_SUA`).

Two ceilings stated rather than fixed: an out-of-quota user still spends one
model call in `hieu_tai_lieu` before the refusal, because gating earlier would
need a database read inside the pure routing function; and a general-path *edit*
writes no `/api/v1/soan-thao/sua` trace where the checklist path's
`ban_thao.dung_lai` does, so the two paths do not report edits symmetrically.

The seam the gates missed was that no test measured the meter — every Phase 14
test checked `result_type`, `ban_thao_ket`, `muc_kiem`, strings and the anchor
check. Three tests at the node now do, and they were verified to fail without
the fix.

## Validation

Backend lanes, run with Postgres up (`docker compose up -d db`):

- `KLAW_SUPABASE_URL= .venv/bin/python -m pytest tests/test_agents -q -m "not integration"`
- `KLAW_SUPABASE_URL= .venv/bin/python -m pytest tests/test_agents -q -m integration --ignore=tests/test_agents/test_route.py --ignore=tests/test_agents/test_verify_tier2.py`
- `.venv/bin/python -m ruff check src/ tests/`
- Frontend: `cd frontend && npm run kiem`

**The brief's original gate command was wrong and it cost real money.** It said
`pytest tests/test_agents -q` with no marker, and listed the paid files as
`tests/test_api/test_route.py` and `test_verify_tier2.py` — paths that do not
exist. The real files are `tests/test_agents/test_route.py` and
`tests/test_agents/test_verify_tier2.py`, which that unmarked command collects
and which call OpenRouter for real. One implementer ran it once before spotting
the contradiction. Always pass `-m "not integration"`, or ignore those two paths
explicitly. A third file spends money and is named by neither list:
`tests/test_scripts/test_build_chunks.py::test_run_that_tren_toan_corpus_TON_TIEN`
re-embeds the whole corpus through OpenRouter at roughly US$0.009 a run, so the
full suite needs `-k "not TON_TIEN"` as well.

Known failures that are not this work, measured on `main` with the database up:
`test_tra_cuu_phien`, `test_effectivity`, `test_migration_024` (the standing
baseline), `test_download_data::test_data_raw_VAN_bi_gitignore` (a worktree
symlink artifact — `git check-ignore` refuses a path beyond a symlink), and
`test_bat_bien_dinh_danh::test_tang_sau_moi_so_ky_hieu_la_duy_nhat`, which is a
**data** failure: the local corpus holds 14 groups of documents sharing a
`so_ky_hieu`, so two different provisions would render the same citation address.
That last one deserves its own work item — it is the invariant this product sells.

## Phase 12 part B — the contract, so it survives the scratchpad

Part A shipped the store and touched nothing under `src/agents/` or `prompts/`.
Part B is exactly that part. The call surface it builds on:

```python
ghi(sub, loai, khoa, gia_tri, nguon_hoi_thoai_id=None) -> "moi" | "doi" | "giu"
liet_ke(sub) -> list[dict]   # {id, loai, khoa, nhan, gia_tri, nguon_hoi_thoai_id, cap_nhat_luc}
```

`loai` is `"ca_nhan"` or `"thoi_quen"`; `khoa` matches `^[a-z][a-z0-9_]{0,39}$`;
`gia_tri` is non-empty and at most 200 characters; anything else raises
`ValueError`. The status comes from the write itself (`INSERT … ON CONFLICT …
WHERE gia_tri IS DISTINCT FROM EXCLUDED.gia_tri RETURNING (xmax = 0)`), so a
restatement of the same value returns `"giu"` and refreshes neither
`nguon_hoi_thoai_id` nor `cap_nhat_luc`.

1. Extract from work that already happens — the drafting turn already parses the
   user's instruction. No paid model call may be added to every drafting turn; if
   one turns out to be unavoidable, stop and report the measured cost per turn
   first.
2. Say it in the turn, in one short line, only when `ghi` returns `"moi"` or
   `"doi"`. Announcing on `"giu"` tells the user "đã nhớ" every time they repeat
   their own name.
3. Recall reaches the model's context, never `clauses`, `facts`, or a rendered
   block by any path that does not run through the user asking in that turn.
4. The deliverable is the negative: a fresh document generated with memory
   populated and a turn that does not ask for those details contains none of the
   remembered values. Assert on the values themselves, not on a flag claiming
   they were withheld.
