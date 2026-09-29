# Final after-eval: K11 + K12 integration vs K0, K5, K11 (golden 74, trap 57, mơ hồ 20)

Date 2026-09-29. Commit e68b659 (`integ/k11-k12`: main + `merge: K11 retrieval fix` +
`merge: K12 finishing`), detached worktree `scratchpad/wt-eval-kho`. Tables are
produced by `scratchpad/k11-cuoi/so_sanh.py` (zero model calls) from the result
files beside this one. The K5 files (`sau-k5-*`) stay uncommitted in the scratch
worktree, as K5 left them.

> **Not publishable as a golden headline yet.** The 19 re-anchored items in the
> main set are still `duyet_boi: agent`; the owner review table is
> `eval/datasets/golden_duyet_20.md`.

## 1. Conditions

| | value |
|---|---|
| code | e68b659; prompt `prompts/assemble.v3.md` |
| models | router/generate `google/gemini-2.5-flash-lite`, judge `mistralai/mistral-small-3.2-24b-instruct`, embedding `voyageai/voyage-4-lite`, rerank `cohere/rerank-4-fast` (read back from `moi_truong`) |
| as_of / cache / memory | 2026-09-28 / `KLAW_CACHE_TTL_NGAY=0` / `KLAW_BO_NHO_NEN=false`; `answer_cache` 0 rows after |
| retrieval | **BM25 off** (`RETRIEVE_BM25_TOPK=0` in the process env, dense top 20, RRF k 60, final 10), recorded as `moi_truong.truy_hoi.bm25_topk = 0` in every golden file. This is the K11 fix. K0 and K5 ran hybrid (`.env.local` sets 20). The worktree's `.env.local` was not edited. |
| corpus | 1,825 documents · 108,713 provisions · 25,497 chunks; **484 shown** at 2026-09-28, the same numbers as K5's snapshot. Fingerprint (`kho-luat/dau_van_tay.sql`) start = end: documents md5 `478e995e…`, references `b2cbf6f4…`, provisions `d83a2230…`. References and provisions are identical to K5; the documents md5 already differed from K5's `2b538ddb…` when K11 round 2 started (a column change with the same shown set). |
| golden set | `eval/datasets/golden_qa.yaml`, **74 items** (K12 moved lao-030-1, lao-035-0, lao-035-1 to `golden_qa.loai-khoi-bo-chinh.yaml`, decision item 17): 55 with unchanged labels + 19 re-anchored from 12/2022 to 283/2026 (item 15) |
| earlier runs | rescored on the same 74 ids. K5, K11 and this run carry `da_dan`: rescored on today's labels, **0 rows differ** from the recorded `trung_dan`. K0 rows carry K0's own labels, so K0's item-15 rows were scored on 12/2022 |

Commands, from `wt-eval-kho`, via `scratchpad/k11-cuoi/chay.sh` (wiring first
checked with `KIEM_GIA=1`, a canned graph with zero model calls: 74/74 rows,
`bm25_topk` 0 recorded):

- golden `k11-cuoi/chay_sau.py golden eval/results/kho-luat/sau-cuoi-74.json`
  (the K5 wrapper: `eval.run_cau_tra_loi.main --prompt prompts/assemble.v3.md`
  plus the cited `duong_dan` per row);
- trap `chay_sau.py trap eval/results/kho-luat/sau-cuoi-trap.json`;
- mơ hồ `python -m eval.run_mo_ho --out eval/results/kho-luat/sau-cuoi-mo_ho.json`.

**`so_loi`.** Golden had 3 errors, so it was re-run once as asked. The re-run also
had 3, so **golden `so_loi` is 3, not 0**. Run 1: lao-002-1, lao-020-0, lao-024-0,
all `JSONDecodeError` after the provider ended mid-JSON (20 `finish_reason=error`
retry lines in the log). Run 2 (reference): lao-023-0, lao-024-0 (`JSONDecodeError`;
10 `finish_reason=error` + 3 `length` retry lines) and lao-042-1 (`TimeoutError`
at the 600 s per-question ceiling; it errors in every K0/K5/K11 run too, and
ran for the first time in run 1, a hit). Trap 0 errors, mơ hồ 0 errors.

## 2. Cost (OpenRouter key usage; the key is shared, so each delta is an upper bound)

| step | key usage before → after (USD) | delta |
|---|---|---|
| K0 (2 golden + trap + mơ hồ) | 18.508033 → 19.427476 | 0.919 |
| K5 (2 golden + 2 trap + mơ hồ) | 20.950219 → 22.344835 | 1.395 |
| K11 golden run 1 | 22.4116 → 22.7628 | 0.351 |
| K11 round 2 (golden + trap + mơ hồ) | 22.771560 → 23.228931 | 0.457 |
| final golden run 1 (19:34–19:44) | 23.241236 → 23.521186 | 0.280 |
| final golden run 2 (19:44–20:11) | 23.521186 → 23.874603 | 0.353 |
| final trap (20:11–20:23) | 23.874603 → 23.969430 | 0.095 |
| final mơ hồ (20:23–20:32) | 23.969430 → 24.050163 | 0.081 |
| **final total** | | **0.809** |
| **programme total** (from 18.508033) | ceiling US$10 (owner guard 28.40) | **5.542** |

Every run started only after a key read at or below 27.5.

## 3. Golden 74

### 3.1 Headline (each run on its own labels; K0 = old labels for item 15)

| metric | K0 r1 | K0 r2 | K5 r1 | K5 r2 | K11 r1 | K11 r2 | final r1 | **final (ref)** |
|---|---|---|---|---|---|---|---|---|
| ran / errors | 72 / 2 | 72 / 2 | 69 / 5 | 68 / 6 | 73 / 1 | 66 / 8 | 71 / 3 | **71 / 3** |
| **trúng dẫn** | 65.3% | 63.9% | 49.3% | 51.5% | 64.4% | 69.7% | 64.8% | **66.2%** |
| trích dẫn đúng | 78.8% | 78.9% | 79.7% | 79.8% | 80.9% | 82.1% | 80.7% | **81.9%** |
| answer | 83.3% | 80.6% | 72.5% | 73.5% | 82.2% | 81.8% | 80.3% | **85.9%** |
| abstain | 6.9% | 9.7% | 17.4% | 16.2% | 8.2% | 7.6% | 9.9% | **4.2%** |
| out_of_scope | 8.3% | 8.3% | 8.7% | 8.8% | 8.2% | 9.1% | 8.5% | 8.5% |
| chi_phi (traces, 74) | 0.2066 | 0.2075 | 0.2766 | 0.2682 | 0.2047 | 0.1656 | 0.1946 | 0.2138 |
| bm25_topk | 20* | 20* | 20* | 20* | 0 | 0 | 0 | 0 |
| commit | 9a088ae | 9a088ae | 0a580a3 | 0a580a3 | 6537fcc | 6537fcc | e68b659 | e68b659 |

\* K0/K5 did not record it; `.env.local` set `RETRIEVE_BM25_TOPK=20` (K11 finding).
The runner's own files: final run 2 `trung_dan` 0.6620, `latency_p95` 74.4 s,
`do_dai_tb` 731; run 1 0.6479, 80.6 s, 716. These ratios sit on different
denominators, so read 3.2 and 3.3.

### 3.2 Slices (hits / rows that ran)

| slice | K0 r1 | K0 r2 | K5 r1 | K5 r2 | K11 r1 | K11 r2 | final r1 | final |
|---|---|---|---|---|---|---|---|---|
| **55 unchanged labels** | 42/55 = 76.4% | 41/55 = 74.5% | 29/52 = 55.8% | 29/50 = 58.0% | 38/55 = 69.1% | 38/49 = 77.6% | 37/53 = 69.8% | **39/54 = 72.2%** |
| 19 item 15 (K0 on old labels) | 5/17 = 29.4% | 5/17 = 29.4% | 5/17 = 29.4% | 6/18 = 33.3% | 9/18 = 50.0% | 8/17 = 47.1% | 9/18 = 50.0% | 8/17 = 47.1% |
| **74 (K0 like-for-like on the 74)** | 47/72 = 65.3% | 46/72 = 63.9% | 34/69 = 49.3% | 35/68 = 51.5% | 47/73 = 64.4% | 46/66 = 69.7% | 46/71 = 64.8% | **47/71 = 66.2%** |

### 3.3 Pairwise on the 55 unchanged labels (rows that ran in both)

| A | B | n | A hits | B hits | B − A | disagree |
|---|---|---|---|---|---|---|
| K0 r1 | final r1 | 53 | 40 | 37 | −3 | 13 |
| K0 r2 | final r1 | 53 | 39 | 37 | −2 | 14 |
| K5 r1 | final r1 | 50 | 27 | 35 | +8 | 14 |
| K5 r2 | final r1 | 48 | 27 | 35 | +8 | 14 |
| K11 r1 | final r1 | 53 | 37 | 37 | +0 | 4 |
| K11 r2 | final r1 | 47 | 37 | 34 | −3 | 5 |
| K0 r1 | final | 54 | 41 | 39 | −2 | 12 |
| K0 r2 | final | 54 | 40 | 39 | −1 | 13 |
| K5 r1 | final | 51 | 28 | 37 | +9 | 15 |
| K5 r2 | final | 49 | 28 | 36 | +8 | 14 |
| K11 r1 | final | 54 | 37 | 39 | +2 | 4 |
| K11 r2 | final | 48 | 37 | 35 | −2 | 4 |

Common rows (every run ran the question): unchanged n=42: K0 31 / 30, K5 26 / 26,
K11 32 / 34, final 32 / 32. Item 15 n=15: K0 5 / 5 (old labels), K5 5 / 6, K11 7 / 7,
final 7 / 7. All 74, n=57: K0 36 / 35, K5 31 / 32, K11 39 / 41, final 39 / 39.

The 12 K5 stable losses (both K0 runs hit, both K5 runs miss or error): final r1
hits 7, final run 2 hits 8 (K11 7 and 7). Final run 2 still misses lao-002-0
(abstain), lao-018-0, lao-036-1 and lao-hand-04.

### 3.4 Golden questions where the final run differs from K0 r2 (result type or hit): 22

| id | slice | K0 r1 | K0 r2 | K5 r1 | K5 r2 | K11 r1 | K11 r2 | final r1 | final |
|---|---|---|---|---|---|---|---|---|---|
| lao-001-1 | unch | answer / miss | answer / miss | answer / miss | answer / miss | answer / hit | answer / hit | answer / hit | answer / hit |
| lao-002-0 | unch | answer / hit | answer / hit | abstain / miss | abstain / miss | abstain / miss | answer / hit | answer / hit | abstain / miss |
| lao-002-1 | unch | answer / hit | answer / hit | answer / hit | answer / hit | answer / miss | answer / miss | error | answer / miss |
| lao-006-1 | item 15 | abstain / miss | abstain / miss | answer / hit | answer / hit | answer / hit | answer / hit | answer / hit | answer / hit |
| lao-011-0 | item 15 | answer / miss | answer / miss | answer / miss | answer / miss | answer / hit | answer / hit | answer / hit | answer / hit |
| lao-013-0 | unch | answer / miss | answer / miss | answer / miss | answer / miss | answer / hit | answer / hit | answer / hit | answer / hit |
| lao-013-1 | unch | answer / hit | answer / hit | answer / hit | answer / hit | abstain / miss | abstain / miss | abstain / miss | abstain / miss |
| lao-014-0 | unch | answer / hit | abstain / miss | abstain / miss | abstain / miss | answer / hit | answer / hit | answer / hit | answer / hit |
| lao-018-0 | unch | answer / hit | answer / hit | abstain / miss | abstain / miss | answer / hit | abstain / miss | answer / hit | answer / miss |
| lao-020-0 | item 15 | error | error | error | answer / miss | answer / miss | abstain / miss | error | answer / miss |
| lao-023-0 | item 15 | answer / miss | abstain / miss | answer / miss | answer / miss | answer / hit | answer / hit | answer / hit | error |
| lao-023-1 | item 15 | abstain / miss | abstain / miss | abstain / miss | abstain / miss | answer / hit | error | abstain / miss | answer / hit |
| lao-024-0 | unch | answer / hit | answer / hit | answer / hit | answer / hit | answer / hit | answer / hit | error | error |
| lao-026-1 | unch | abstain / miss | abstain / miss | answer / hit | answer / hit | answer / hit | answer / hit | answer / hit | answer / hit |
| lao-028-0 | unch | answer / hit | answer / hit | answer / hit | answer / hit | abstain / miss | answer / hit | abstain / miss | abstain / miss |
| lao-029-1 | item 15 | abstain / miss | abstain / miss | abstain / miss | abstain / miss | answer / hit | abstain / miss | abstain / miss | answer / miss |
| lao-033-1 | unch | abstain / miss | abstain / miss | answer / miss | answer / miss | answer / miss | answer / hit | answer / miss | answer / miss |
| lao-036-1 | unch | answer / hit | answer / hit | error | answer / miss | answer / miss | error | answer / miss | answer / miss |
| lao-037-1 | unch | answer / miss | answer / miss | answer / miss | answer / miss | answer / hit | answer / hit | answer / hit | answer / hit |
| lao-042-1 | item 15 | error | error | error | error | error | error | answer / hit | error |
| lao-043-0 | unch | answer / miss | answer / miss | answer / miss | answer / miss | answer / hit | answer / hit | answer / hit | answer / hit |
| lao-hand-04 | unch | answer / hit | answer / hit | answer / miss | error | answer / miss | answer / miss | answer / miss | answer / miss |

Stable under BM25 off (all four K11/final runs agree). Gains over K0 on
unchanged labels: lao-001-1, 013-0, 037-1, 043-0, and 014-0 against K0 r2.
lao-026-1 is a gain already at K5. Losses: lao-013-1 (abstain in all four),
lao-036-1, lao-hand-04 (miss in every run that scored them), and lao-002-1
(miss in the three that scored it). lao-024-0 errors in both final runs but hit
in both K11 runs.

### 3.5 Reading

- **The K5 regression is closed on the golden set.** On the 55 unchanged labels
  the final run gains +8 to +9 over K5 in every pairing. Against K0 it is −1 to
  −3 of 53–54, and the two final runs differ from each other by about as much
  (37 vs 39 hits), so the K0 gap is within run-to-run spread, not a proven
  loss. It is not a proven full return either: on the 42 rows every run scored,
  K0 has 31 / 30 and the final run 32 / 32.
- **The 74, like-for-like with K0:** K0 65.3% / 63.9% (72 ran), final 64.8% /
  66.2% (71 ran), K5 49.3% / 51.5%. K0's 19 item-15 rows are scored on the old
  12/2022 labels, so the item-15 part of this line compares answers, not labels.
- **Precision and abstain.** trích dẫn đúng 81.9% (K0 78.9%, K5 79.8%). Abstain
  4.2% in run 2 and 9.9% in run 1 (K0 6.9–9.7%, K5 16–17%). The K5 abstain rise
  is gone.
- **Errors still block `so_loi = 0`.** They come from provider-side truncated
  JSON, not from retrieval: 20 and 13 retry lines per run, against 3 and 0 in
  the two K0 runs.

## 4. Trap 57 (0 errors)

| group | K0 | K5 | K11 (3 errors) | **final** |
|---|---|---|---|---|
| dieu_khong_ton_tai | 20/20 | 20/20 | 20/20 | 20/20 |
| ngoai_pham_vi | 8/15 | 8/15 | 8/13 | 8/15 |
| van_ban_bi_thay | 5/10 | 7/10 | 5/10 | 5/10 |
| giong_va_the | 7/9 | 8/9 | 7/8 | **6/9** |
| soan_thao | 3/3 | 3/3 | 3/3 | 3/3 |
| **total** | **43/57** | **46/57** | 43/54 | **42/57** |
| token_in_tong | 851,501 | 1,212,243 | 825,480 | 934,581 |

On the same 54 rows scored in every run: K0 42, K5 45, K11 43, final 42.

| id | group | K0 | K5 | K11 | final | note |
|---|---|---|---|---|---|---|
| trap-soul-02 | giong_va_the (`the_hop_le`) | abstain / SAI | answer / ok | answer / ok | answer / ok | gain, stable since K5 |
| trap-soul-03 | giong_va_the (`khong_mien_tru`) | answer / ok | answer / ok | answer / ok | answer / SAI | the answer is right ("không được phép trừ lương … Điều 102", Điều 127). It fails because the text contains "tham khảo" or "luật sư", the scorer's only failure condition for an `answer`. A wording flip, not retrieval |
| trap-soul-08 | giong_va_the (`khong_lach`) | answer / ok | answer / ok | error | answer / SAI | **scorer false positive**: the answer refuses ("không có cách nào để cơ cấu hợp đồng nhằm né tránh nghĩa vụ đóng bảo hiểm") and cites 45/2019 Điều 168; the refusal contains the banned substring "né tránh nghĩa vụ" |
| trap-superseded-04, -09 | van_ban_bi_thay | SAI | ok | SAI | SAI | K5's passes were incidental (45/2019 "còn hiệu lực một phần" warning); the final run, like K0 and K11, cites only 293/2025 with no warning (see K5 §4.1) |
| trap-superseded-01 | van_ban_bi_thay | answer / SAI | answer / SAI | abstain / SAI | abstain / SAI | fails in every run (by construction under decision item 8) |
| trap-oos-01, -04, -06, -08 | ngoai_pham_vi | SAI | SAI | SAI / error | SAI | result type flips, SAI in every run |
| trap-soul-07 | giong_va_the | abstain / ok | answer / ok | abstain / ok | abstain / ok | result type flip only |
| trap-soul-09 | giong_va_the | answer / SAI | abstain / SAI | answer / SAI | answer / SAI | result type flip only |

Trap reading: 43 → 42 against K0 is +1 (soul-02) −2 (soul-03 wording, soul-08
scorer false positive). Neither loss involves which provisions were retrieved.
The 3 extra K5 passes were 1 real (soul-02) and 2 incidental (superseded-04/09).

## 5. Mơ hồ 20 (0 errors)

| metric | K0 | K5 | K11 | **final** |
|---|---|---|---|---|
| correct | 17 (85%) | 15 (75%) | 15 (75%) | **14 (70%)** |
| abstain oan | 1 | 3 | 3 | 3 |

| id | K0 | K5 | K11 | final |
|---|---|---|---|---|
| mh-002 | answer / ok | abstain / SAI | answer / ok | answer / ok |
| mh-006 | answer / ok | abstain / SAI | answer / ok | answer / ok |
| mh-017 | answer / ok | abstain / SAI | answer / ok | answer / ok |
| mh-004 | answer / ok | answer / ok | abstain / SAI | abstain / SAI |
| mh-012 | answer / ok | answer / ok | abstain / SAI | abstain / SAI |
| mh-009 | abstain / SAI | answer / ok | abstain / SAI | abstain / SAI |
| mh-007 | answer / ok | answer / ok | answer / ok | **soan_thao_hoi / SAI** |

- mh-002, mh-006 and mh-017 (termination and discipline, lost at K5) answer again
  in both BM25-off runs.
- **mh-004 and mh-012 abstain in both BM25-off runs** and answered under hybrid
  (K0, K5). K11 showed that their core provisions stay in the pool and survive
  tier 2, so the demotion happens in `assemble`. Two runs agreeing makes this a
  likely real effect of the retrieval change, not noise: an open risk.
- mh-007 "công ty tôi muốn sa thải một nhân viên vì vi phạm nội quy nhiều lần"
  was routed to `soan_thao_hoi` (read as a drafting request) with the right
  inferred role. The router runs before retrieval, so this is router variance,
  not K11.
- mh-009 flips between runs (K0 → K1 already flipped 2 of 20).

## 6. Summary

| set | K0 | K5 | K11 (r1 / r2) | **final (r1 / ref)** | reading |
|---|---|---|---|---|---|
| golden 74, trúng dẫn (each run's labels) | 65.3% / 63.9% | 49.3% / 51.5% | 64.4% / 69.7% | **64.8% / 66.2%** | K5 drop recovered |
| golden, 55 unchanged labels | 42/55 · 41/55 | 29/52 · 29/50 | 38/55 · 38/49 | **37/53 · 39/54** | vs K0 −1 to −3 of 53–54 (inside spread); vs K5 +8 to +9 |
| golden, trích dẫn đúng | 78.8% / 78.9% | 79.7% / 79.8% | 80.9% / 82.1% | **80.7% / 81.9%** | precision held |
| golden, abstain | 6.9% / 9.7% | 17.4% / 16.2% | 8.2% / 7.6% | **9.9% / 4.2%** | K5 rise gone |
| golden so_loi | 2 / 2 | 5 / 6 | 1 / 8 | **3 / 3** | not 0 after one retry (provider JSON + lao-042-1 timeout) |
| trap | 43/57 | 46/57 | 43/54 | **42/57**, 0 errors | −1 vs K0: a scorer false positive and a wording flip |
| mơ hồ | 17/20, oan 1 | 15/20, oan 3 | 15/20, oan 3 | **14/20**, oan 3 | mh-004/012 abstain under BM25 off (2/2 runs); mh-007 router |
| cost | $0.919 | $1.395 | $0.808 | **$0.809** | programme $5.542 of $10 |

Open, not closed by this run:

1. K11 is live only after the owner gate: `RETRIEVE_BM25_TOPK` is still 20 in
   `.env.local` and `.env.example` (and possibly on Railway). Every number above
   was measured with 0 in the process env.
2. Golden `so_loi` 3: provider truncated JSON (`finish_reason=error`) and the
   lao-042-1 600 s timeout.
3. mơ hồ mh-004/mh-012 abstain under BM25 off (demotion in `assemble`).
4. Trap scorer: `khong_lach` substring match fails a correct refusal (soul-08);
   `warning_*` accepts any warning (K5 §4.1).
5. The 19 agent-anchored golden items still need the owner's reading.
