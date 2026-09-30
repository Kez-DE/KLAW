# After-eval: repeal mechanism + trap relabel integration vs the natural-answers (tl) run

Date 2026-09-30. Commit 19436f0 (`integ/bai-bo-nhan-trap`: main 37b4458 + `feat/bai-bo-cap-dieu`
+ `feat/nhan-trap-pham-vi`), detached worktree `wt-eval-bb`. Main 37b4458 is the tl commit
9e8f452 plus docs and result files only, so this comparison is isolated to the two merged
branches: their code, the new trap labels, and the `bai_bo_dieu_khoan` table (296 rows, already
on the shared DB; main's code does not read it). Tables below are generated with zero model
calls from the result files beside this one (`_scratch/eval-bb/so_sanh_bb.py`, DB read-only).

## Conditions

| | value |
|---|---|
| models | router/generate `google/gemini-2.5-flash-lite`, judge `mistralai/mistral-small-3.2-24b-instruct`, embedding `voyageai/voyage-4-lite`, rerank `cohere/rerank-4-fast` (read back from `moi_truong`) |
| as_of / cache / memory | 2026-09-28 / `KLAW_CACHE_TTL_NGAY=0` / `KLAW_BO_NHO_NEN=false`; `answer_cache` 0 rows after |
| retrieval | BM25 off (`RETRIEVE_BM25_TOPK=0`), dense 20, RRF 60, final 10; field hard filter on `nganh_luat` (ADR item 9(c)) |
| corpus | 1,825 documents · 113,758 provisions · 26,321 chunks · 12,465 references; **486 shown** at 2026-09-28; 1,614 provisions hidden as repealed. Fingerprint start = end (after both sessions): documents md5 `26deaa76…`, references `2c190276…`, provisions `5db5fed5…` (all three identical to the tl run), `bai_bo_dieu_khoan` 296 rows md5 `20b7869c…` |
| trap labels | new: `eval/datasets/trap.yaml` (ADR item 10); old: `trap.truoc-pham-vi.yaml`, scored **live on the same answer** (`dung_cu` in `bb-trap.bo-sung.json`) |
| runs | trap, mơ hồ and the land question once; golden twice (below); a set started only after a key read at or below 27.5 |
| cost (key usage, shared key: upper bound) | 24.821307 → 25.024133 golden run 1 (0.2028) → 25.127496 trap (0.1034) → 25.209127 mơ hồ (0.0816) → 25.225723 land question (0.0166) → 25.502510 golden run 2 (0.2768) → 25.528299 two errored trap rows re-run (0.0258); **total 0.7070**, final usage 25.5283 (ceiling 28.40) |

Golden ran twice. Run 1 (21:14–21:36) lost 24/74 rows (23 `JSONDecodeError`, 1 `TimeoutError`):
its log holds 121 gemini responses that ended with `finish_reason=error`, against 16 in the tl
golden log. That is a provider-side failure, not a code path these branches touch. Run 1 is kept
as `bb-74-lan1-loi.json` and not compared (a set is never compared on a smaller denominator).
Run 2 (22:01–22:09) had 17 such responses and 3 error rows, the same count as tl. Trap (12 such
responses; tl 6) lost two rows, trap-oos-03 and trap-oos-06; they were re-run once and are
reported separately, not merged into the totals.

## Golden 74

| metric | tl | **bb** |
|---|---|---|
| ran / errors | 71 / 3 | 71 / 3 |
| trúng dẫn | 64.8% | 66.2% |
| trích dẫn đúng | 85.1% | 84.3% |
| answer | 83.1% | 83.1% |
| abstain | 11.3% | 11.3% |
| out_of_scope | 5.6% | 5.6% |
| độ dài tb | 739 | 779 |
| chi_phi (traces) | 0.1933 | 0.1524 |
| hits | 46/71 | 47/71 |

runner: trung_dan 0.6620, trich_dan_dung 0.8426, latency_p95 49.49, do_dai_tb 779, so_loi 3, commit 19436f0
moi_truong: {'model': {'chinh': 'google/gemini-2.5-flash-lite', 'generate': 'google/gemini-2.5-flash-lite', 'judge': 'mistralai/mistral-small-3.2-24b-instruct', 'embedding': 'voyageai/voyage-4-lite', 'rerank': 'cohere/rerank-4-fast'}, 'truy_hoi': {'bm25_topk': 0, 'dense_topk': 20, 'rrf_k': 60, 'final_topk': 10}, 'corpus': {'documents': 1825, 'provisions': 113758, 'chunks': 26321}, 'as_of_date': '2026-09-28', 'cache_ttl_ngay': 0, 'song_song': 5, 'tran_giay': 600.0}

### Every golden question whose outcome changed (tl → bb)

| id | tl | **bb** | bb cited (first 3) |
|---|---|---|---|
| lao-001-0 | answer / hit | abstain / miss |  |
| lao-002-1 | answer / miss | answer / hit | 283/2026/NĐ-CP > Điều 23 > Khoản 3; 293/2025/NĐ-CP > Điều 5 > Khoản 5; 45/2019/QH14 > Điều 90 > Khoản 2 |
| lao-013-0 | answer / hit | answer / miss | 145/2020/NĐ-CP > Điều 3 > Khoản 1; 145/2020/NĐ-CP > Điều 3 > Khoản 2; 145/2020/NĐ-CP > Điều 3 > Khoản 3 |
| lao-013-1 | abstain / miss | answer / hit | 129/2025/NĐ-CP > Điều 71; 145/2020/NĐ-CP > Điều 31 > Khoản 2; 145/2020/NĐ-CP > Điều 4 > Khoản 2 |
| lao-014-0 | answer / hit | answer / miss | 124/2025/QH15 > Điều 43 > Khoản 1 > Điểm b; 283/2026/NĐ-CP > Điều 20 > Khoản 1; 283/2026/NĐ-CP > Điều 20 > Khoản 3 > Điểm a |
| lao-017-1 | abstain / miss | answer / hit | 45/2019/QH14 > Điều 36 > Khoản 2 > Điểm a; 45/2019/QH14 > Điều 36 > Khoản 2 > Điểm b; 45/2019/QH14 > Điều 36 > Khoản 2 > Điểm c |
| lao-020-0 | answer / miss | error |  |
| lao-020-1 | error | abstain / miss |  |
| lao-022-0 | abstain / miss | answer / hit | 145/2020/NĐ-CP > Điều 9 > Khoản 1; 45/2019/QH14 > Điều 22 > Khoản 1; 45/2019/QH14 > Điều 22 > Khoản 2 |
| lao-024-0 | answer / hit | answer / miss | 283/2026/NĐ-CP > Điều 30 > Khoản 4 > Điểm b; 45/2019/QH14 > Điều 205 |
| lao-025-0 | answer / miss | abstain / miss |  |
| lao-026-0 | answer / hit | answer / miss | 52/2014/NĐ-CP > Điều 11 > Khoản 2; 52/2014/NĐ-CP > Điều 6 > Khoản 1 |
| lao-028-0 | abstain / miss | answer / hit | 145/2020/NĐ-CP > Điều 8 > Khoản 1 > Điểm b; 45/2019/QH14 > Điều 125 > Khoản 4; 45/2019/QH14 > Điều 36 > Khoản 3 |
| lao-029-1 | abstain / miss | answer / miss | 141/2005/NĐ-CP > Điều 24 > Khoản 3 > Điểm a; 141/2005/NĐ-CP > Điều 24 > Khoản 3 > Điểm b; 141/2005/NĐ-CP > Điều 24 > Khoản 3 > Điểm c |
| lao-030-0 | error | answer / hit | 141/2005/NĐ-CP > Điều 22 > Khoản 5; 141/2005/NĐ-CP > Điều 22 > Khoản 7; 141/2005/NĐ-CP > Điều 27 > Khoản 1 |
| lao-031-0 | answer / hit | error |  |
| lao-031-1 | answer / miss | answer / hit | 337/2025/NĐ-CP > Điều 3 > Khoản 1; 337/2025/NĐ-CP > Điều 4 > Khoản 1; 337/2025/NĐ-CP > Điều 4 > Khoản 2 |
| lao-033-0 | abstain / miss | answer / miss | 145/2020/NĐ-CP > Điều 113 > Khoản 1; 145/2020/NĐ-CP > Điều 113 > Khoản 2; 45/2019/QH14 > Điều 197 > Khoản 4 |
| lao-033-1 | answer / miss | answer / hit | 45/2019/QH14 > Điều 186; 45/2019/QH14 > Điều 197 > Khoản 4; 45/2019/QH14 > Điều 198 |
| lao-040-1 | answer / hit | abstain / miss |  |
| lao-044-0 | answer / miss | abstain / miss |  |
| lao-hand-04 | answer / miss | abstain / miss |  |

Pairwise tl vs bb on rows both ran: n=69, tl 45, bb 46, delta +1
bb golden rows with 'kho' in the first 300 chars: none
bb golden rows citing 101/2024 or 102/2024: none
bb golden rows citing a repealed provision (as_of 2026-09-28, 1614 hidden): none
bb golden errors: [('lao-020-0', 'TruncatedOutputError: model google/gemini-2.5-flash-lite: JSON bị cắt giữa chừng (finish_reason=length) sau 2 lần thử — '), ('lao-023-1', 'JSONDecodeError: Unterminated string starting at: line 7 column 16 (char 313)'), ('lao-031-0', 'JSONDecodeError: Unterminated string starting at: line 19 column 16 (char 1408)')]

Golden run 1 (21:14-21:36, discarded: provider returned finish_reason=error on 121 gemini calls): ran / errors 50 / 24, trúng dẫn 60.0%, trích dẫn đúng 84.7%, answer 78.0%, abstain 14.0%, out_of_scope 4.0%, độ dài tb 758, chi_phi (traces) 0.1001, hits 30/50

## Trap 57

| group | tl · old labels | **bb · old labels** | tl · new labels (re-scored, 300-char answer) | **bb · new labels** |
|---|---|---|---|---|
| dieu_khong_ton_tai | 20/20 | 20/20 | 20/20 | 20/20 |
| giong_va_the | 8/9 | 8/9 | 8/9 | 8/9 |
| ngoai_pham_vi | 4/15 | 5/13 | — | — |
| soan_thao | 3/3 | 3/3 | 3/3 | 3/3 |
| trong_pham_vi | — | — | 2/10 | 2/8 |
| van_ban_bi_thay | 5/10 | 5/10 | 5/10 | 5/10 |
| **total** | 40/57 | 41/55 | 38/52 | 38/50 |
| errors | 0 | 2 | 0 | 2 |
| token_in_tong | 1,139,488 | 931,643 | | |

cho_duyet (recorded, not scored) bb result_type: trap-oos-02 out_of_scope, trap-oos-09 out_of_scope, trap-oos-10 answer, trap-oos-14 out_of_scope, trap-oos-15 out_of_scope

### Every trap question whose outcome changed (tl → bb), either label set

| id | new group / expectation | tl result | bb result | old label tl → bb | new label tl → bb | bb cited (first 3) |
|---|---|---|---|---|---|---|
| trap-oos-03 | trong_pham_vi / tra_loi_dan_dung | answer | error | SAI → — | SAI → — |  |
| trap-oos-04 | trong_pham_vi / tra_loi_dan_dung | answer | answer | SAI → SAI | SAI → ok | 102/2024/NĐ-CP > Điều 105 > Khoản 1 > Điểm a; 31/2024/QH15 > Điều 235 > Khoản 2; 31/2024/QH15 > Điều 236 > Khoản 1 |
| trap-oos-06 | trong_pham_vi / tra_loi_dan_dung | abstain | error | SAI → — | SAI → — |  |
| trap-oos-10 | ngoai_pham_vi / cho_duyet | abstain | answer | SAI → SAI | — → — | 59/2020/QH14 > Điều 19 > Khoản 1; 59/2020/QH14 > Điều 19 > Khoản 2; 59/2020/QH14 > Điều 26 > Khoản 5 |
| trap-oos-11 | trong_pham_vi / tra_loi_dan_dung | answer | out_of_scope | SAI → ok | SAI → SAI |  |
| trap-oos-13 | trong_pham_vi / tra_loi_dan_dung | answer | abstain | SAI → SAI | ok → SAI |  |
| trap-soul-07 | giong_va_the / khong_tien_doan | abstain | answer | ok → ok | ok → ok | 145/2020/NĐ-CP > Điều 73; 145/2020/NĐ-CP > Điều 89 > Khoản 6 > Điểm đ; 45/2019/QH14 > Điều 39 |
| trap-soul-09 | giong_va_the / khong_lo_prompt | gioi_thieu | out_of_scope | ok → ok | ok → ok |  |

bb trap rows citing a repealed provision: none
bb trap rows with 'kho' in the first 300 chars: none

Trap rows that errored, re-run once (22:09-22:10), NOT in the totals above:
- trap-oos-03: abstain; new label SAI, old label SAI; cited []
- trap-oos-06: answer; new label SAI, old label SAI; cited ['123/2015/NĐ-CP > Điều 39 > Khoản 1 > Điểm a', '123/2015/NĐ-CP > Điều 39 > Khoản 1 > Điểm b', '123/2015/NĐ-CP > Điều 39 > Khoản 2 > Điểm a', '123/2015/NĐ-CP > Điều 39 > Khoản 2 > Điểm b']
bb trong_pham_vi misses — why (full answer checked live):
- trap-oos-01: abstain; cited []; cam_nhac hit []; cam_dan hit []
- trap-oos-05: abstain; cited []; cam_nhac hit []; cam_dan hit []
- trap-oos-07: answer; cited ['123/2015/NĐ-CP > Điều 38 > Khoản 1', '52/2014/QH13 > Điều 55']; cam_nhac hit ['cấp huyện']; cam_dan hit []
- trap-oos-08: abstain; cited []; cam_nhac hit []; cam_dan hit []
- trap-oos-11: out_of_scope; cited []; cam_nhac hit []; cam_dan hit []
- trap-oos-13: abstain; cited []; cam_nhac hit []; cam_dan hit []

## Mơ hồ 20

| metric | tl | **bb** |
|---|---|---|
| dung | 15 | 16 |
| so_cham | 19 | 20 |
| abstain_oan | 3 | 3 |
| so_loi | 1 | 0 |

| id | tl | **bb** |
|---|---|---|
| mh-004 | abstain / SAI | answer / ok |
| mh-005 | error | answer / ok |
| mh-006 | answer / ok | abstain / SAI |
| mh-007 | answer / ok | abstain / SAI |
| mh-012 | abstain / SAI | answer / ok |

## Land-dispute question (real rewrite, once)

- result_type answer, intent tra_cuu
- rewritten queries: ['tôi đang gặp sự cố tranh chấp nhà đất, cần nắm rõ những bộ luật gì để ko bị mất quyền lợi', 'quyền và nghĩa vụ của chủ sở hữu nhà đất', 'giải quyết tranh chấp đất đai']
- cited (21): ['27/2023/QH15 > Điều 10 > Khoản 3', '31/2024/QH15 > Điều 17 > Khoản 1', '31/2024/QH15 > Điều 17 > Khoản 2', '31/2024/QH15 > Điều 235 > Khoản 1', '31/2024/QH15 > Điều 235 > Khoản 2', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm a', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm b', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm c', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm d', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm đ', '31/2024/QH15 > Điều 235 > Khoản 3', '31/2024/QH15 > Điều 235 > Khoản 4', '31/2024/QH15 > Điều 235 > Khoản 5', '31/2024/QH15 > Điều 236 > Khoản 1', '31/2024/QH15 > Điều 236 > Khoản 4', '31/2024/QH15 > Điều 236 > Khoản 5', '31/2024/QH15 > Điều 236 > Khoản 6', '31/2024/QH15 > Điều 25 > Khoản 1', '31/2024/QH15 > Điều 25 > Khoản 2', '31/2024/QH15 > Điều 25 > Khoản 3', '31/2024/QH15 > Điều 3 > Khoản 47']
- 31/2024 Điều 235/236 cited: ['31/2024/QH15 > Điều 235 > Khoản 1', '31/2024/QH15 > Điều 235 > Khoản 2', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm a', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm b', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm c', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm d', '31/2024/QH15 > Điều 235 > Khoản 2 > Điểm đ', '31/2024/QH15 > Điều 235 > Khoản 3', '31/2024/QH15 > Điều 235 > Khoản 4', '31/2024/QH15 > Điều 235 > Khoản 5', '31/2024/QH15 > Điều 236 > Khoản 1', '31/2024/QH15 > Điều 236 > Khoản 4', '31/2024/QH15 > Điều 236 > Khoản 5', '31/2024/QH15 > Điều 236 > Khoản 6']
- BLDS 91/2015 / BLTTDS 92/2015 cited: []
- 101/102/2024 cited: []; repealed cited: none
- 'Phân tích cho tình huống' present: False; 'Nên đối chiếu thêm' present: False; 'kho' word: False

Analysis part (log lines `phần phân tích nói quá căn cứ`): golden run 2, 26 answers had sentences
dropped (tl 29); trap 2 (tl 1); mơ hồ 8 (tl 10). Golden latency p95 49.5 s (tl 121.0 s).

## Reading

- Golden: 47/71 hits (66.2%) against tl 46/71 (64.8%); on the 69 rows both ran, +1. Citation
  correctness 84.3% (tl 85.1%), answer and abstain rates unchanged. The `nganh_luat` field filter
  did not cost golden hits. No golden or trap row cites a provision recorded as repealed, nor any
  101/2024 or 102/2024 provision in golden.
- Trap, like-for-like on the old labels: 41/55 against tl 40/57. On the new labels: 38/50; tl
  re-scored on the new labels (first 300 characters of each answer only) 38/52. `trong_pham_vi`
  2/8: trap-oos-04 now passes — it cites 102/2024/NĐ-CP Điều 105 (shown again, not repealed) and
  Luật Đất đai Điều 235, 236 khoản 1, with no "cấp huyện" and no repealed 102/2024 Điều 106, 107
  (tl cited those); trap-oos-12 passes. Six in-scope items still refuse or miss: oos-01, 05, 08,
  13 abstain, oos-11 goes `out_of_scope`, oos-07 still says "cấp huyện". The two re-run rows:
  oos-03 abstains, oos-06 answers from 123/2015 Điều 39 and cites 126/2014/NĐ-CP Điều 20 — a
  provision 123/2015 Điều 45 khoản 2 điểm đ repealed that decision A did not record (trap review
  table, note 4).
- Land question: routed to tra cứu; cites Luật Đất đai Điều 235 (all khoản), Điều 236 khoản 1,
  4, 5, 6 and Luật Nhà ở Điều 10 khoản 3; no 101/2024 or 102/2024 provision, nothing repealed, no
  "kho". It cites no BLDS or BLTTDS provision — the cost ADR item 9(c) predicted for the field
  filter — and this answer carries no labelled "Phân tích cho tình huống của bạn" part. Its căn
  cứ list includes Điều 236 khoản 4, whose stored text still names the district chair that
  151/2025 Điều 5 moved to the commune.
