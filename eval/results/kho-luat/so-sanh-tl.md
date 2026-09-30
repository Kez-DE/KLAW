# After-eval: tra-loi-tu-nhien integration vs K11 and final (golden 74, trap 57, mơ hồ 20)

Date 2026-09-30. Commit 9e8f452 (`integ/tra-loi-tu-nhien`: main d380a27 + N1 data, N2
meta, N3 analysis, N4 UI + integration fixes), detached worktree `wt-eval-tl`. Tables
below are generated with zero model calls from the result files beside this one.

## Conditions

| | value |
|---|---|
| models | router/generate `google/gemini-2.5-flash-lite`, judge `mistralai/mistral-small-3.2-24b-instruct`, embedding `voyageai/voyage-4-lite`, rerank `cohere/rerank-4-fast` (read back from `moi_truong`) |
| as_of / cache / memory | 2026-09-28 / `KLAW_CACHE_TTL_NGAY=0` / `KLAW_BO_NHO_NEN=false`; `answer_cache` 0 rows after |
| retrieval | BM25 off (`RETRIEVE_BM25_TOPK=0` in the process env), dense 20, RRF 60, final 10 |
| corpus | 1,825 documents · 113,758 provisions · 26,321 chunks · 12,465 references; **486 shown** at 2026-09-28 (final run: 108,713 provisions, 25,497 chunks, 484 shown). Fingerprint start = end: documents md5 `26deaa76…`, references `2c190276…`, provisions `5db5fed5…` |
| runs | each set once, no rerun; a set started only after a key read at or below 27.5 |
| cost (key usage, shared key: upper bound) | 24.151723 → 24.574213 golden (0.4225) → 24.706804 trap (0.1326) → 24.799186 mơ hồ (0.0924); **total 0.6475** |

Not isolated to this wave: the baseline (e68b659) is 85 main commits older than this
wave's base (d380a27). Between them the router's draft-type list (`danh_sach_loai`, an
input of the route prompt) grew from 29 to 51 types and the corpus grew (N1). The shared
dev DB also still holds the two N1 loai 23 edges 169188/169363 -> 178259 that commit
ba25aef says to replace with loai 21 (keep 101/2024 and 102/2024 hidden): both decrees
are shown in this run. No golden row cites them.

## Golden 74

| metric | K11 r1 | K11 r2 | final r1 | final (ref) | **tl** |
|---|---|---|---|---|---|
| ran / errors | 73 / 1 | 66 / 8 | 71 / 3 | 71 / 3 | 71 / 3 |
| trúng dẫn | 64.4% | 69.7% | 64.8% | 66.2% | 64.8% |
| trích dẫn đúng | 80.9% | 82.1% | 80.7% | 81.9% | 85.1% |
| answer | 82.2% | 81.8% | 80.3% | 85.9% | 83.1% |
| abstain | 8.2% | 7.6% | 9.9% | 4.2% | 11.3% |
| out_of_scope | 8.2% | 9.1% | 8.5% | 8.5% | 5.6% |
| độ dài tb | 708 | 712 | 716 | 731 | 739 |
| chi_phi (traces) | 0.2047 | 0.1656 | 0.1946 | 0.2138 | 0.1933 |
| hits | 47/73 | 46/66 | 46/71 | 47/71 | 46/71 |

runner: trung_dan 0.6479, trich_dan_dung 0.8511, latency_p95 120.998, do_dai_tb 739, so_loi 3, commit 9e8f452

### Golden questions where tl differs from final (ref) or final r1

| id | K11 r1 | K11 r2 | final r1 | final (ref) | **tl** |
|---|---|---|---|---|---|
| lao-002-0 | abstain / miss | answer / hit | answer / hit | abstain / miss | abstain / miss |
| lao-002-1 | answer / miss | answer / miss | error | answer / miss | answer / miss |
| lao-017-1 | abstain / miss | abstain / miss | abstain / miss | answer / hit | abstain / miss |
| lao-018-0 | answer / hit | abstain / miss | answer / hit | answer / miss | answer / hit |
| lao-020-0 | answer / miss | abstain / miss | error | answer / miss | answer / miss |
| lao-020-1 | out_of_scope / miss | out_of_scope / miss | out_of_scope / miss | out_of_scope / miss | error |
| lao-022-0 | answer / hit | answer / hit | answer / hit | answer / hit | abstain / miss |
| lao-023-0 | answer / hit | answer / hit | answer / hit | error | answer / hit |
| lao-023-1 | answer / hit | error | abstain / miss | answer / hit | error |
| lao-024-0 | answer / hit | answer / hit | error | error | answer / hit |
| lao-029-1 | answer / hit | abstain / miss | abstain / miss | answer / miss | abstain / miss |
| lao-030-0 | answer / hit | answer / hit | answer / hit | answer / hit | error |
| lao-033-0 | abstain / miss | error | abstain / miss | answer / hit | abstain / miss |
| lao-034-1 | soan_thao_hoi / miss | soan_thao_hoi / miss | soan_thao_hoi / miss | soan_thao_hoi / miss | answer / miss |
| lao-037-0 | answer / hit | answer / hit | answer / miss | answer / hit | answer / hit |
| lao-042-1 | error | error | answer / hit | error | answer / hit |
| lao-044-1 | out_of_scope / miss | out_of_scope / miss | out_of_scope / miss | out_of_scope / miss | abstain / miss |
| lao-hand-07 | answer / hit | answer / hit | abstain / miss | answer / hit | answer / hit |

Pairwise final (ref) vs tl on rows both ran: n=68, final 45, tl 43, delta -2
Pairwise final r1 vs tl: n=68, final r1 45, tl 45, delta +0

tl golden rows with 'kho' in the first 300 chars: none
tl golden rows citing 101/2024 or 102/2024: none
tl golden errors: [('lao-020-1', 'TruncatedOutputError: model google/gemini-2.5-flash-lite: JSON bị cắt giữa chừng (finish_reason=length) sau 2 lần thử — có vẻ CẤU TRÚC (schema + ngữ cảnh cần nhiều token hơn provider chịu phát), không thử thêm'), ('lao-023-1', 'JSONDecodeError: Unterminated string starting at: line 313 column 16 (char 32800)'), ('lao-030-0', 'TimeoutError: ')]

## Trap 57

| group | K11 | final | **tl** |
|---|---|---|---|
| dieu_khong_ton_tai | 20/20 | 20/20 | 20/20 |
| ngoai_pham_vi | 8/13 | 8/15 | 4/15 |
| van_ban_bi_thay | 5/10 | 5/10 | 5/10 |
| giong_va_the | 7/8 | 6/9 | 8/9 |
| soan_thao | 3/3 | 3/3 | 3/3 |
| **total** | 43/54 | 42/57 | 40/57 |
| errors | 3 | 0 | 0 |
| token_in_tong | 825,480 | 934,581 | 1,139,488 |

| id | group | K11 | final | **tl** |
|---|---|---|---|---|
| trap-oos-02 | ngoai_pham_vi | partial_coverage / SAI | partial_coverage / SAI | out_of_scope / ok |
| trap-oos-05 | ngoai_pham_vi | out_of_scope / ok | out_of_scope / ok | abstain / SAI |
| trap-oos-08 | ngoai_pham_vi | error | answer / SAI | abstain / SAI |
| trap-oos-10 | ngoai_pham_vi | out_of_scope / ok | out_of_scope / ok | abstain / SAI |
| trap-oos-11 | ngoai_pham_vi | out_of_scope / ok | out_of_scope / ok | answer / SAI |
| trap-oos-12 | ngoai_pham_vi | out_of_scope / ok | out_of_scope / ok | answer / SAI |
| trap-oos-13 | ngoai_pham_vi | out_of_scope / ok | out_of_scope / ok | answer / SAI |
| trap-soul-03 | giong_va_the | answer / ok | answer / SAI | answer / ok |
| trap-soul-09 | giong_va_the | answer / SAI | answer / SAI | gioi_thieu / ok |

tl trap rows with 'kho' in the first 300 chars: none

## Mơ hồ 20

| metric | K11 | final | **tl** |
|---|---|---|---|
| dung | 15 | 14 | 15 |
| so_cham | 20 | 20 | 19 |
| abstain_oan | 3 | 3 | 3 |
| so_loi | 0 | 0 | 1 |

| id | K11 | final | **tl** |
|---|---|---|---|
| mh-003 | soan_thao_hoi / SAI | soan_thao_hoi / SAI | abstain / SAI |
| mh-005 | answer / ok | answer / ok | error |
| mh-007 | answer / ok | soan_thao_hoi / SAI | answer / ok |
| mh-009 | abstain / SAI | abstain / SAI | answer / ok |

Analysis part (log lines `phần phân tích nói quá căn cứ`): golden 29 answers had
sentences dropped (26 `khong_dan_dieu`, 11 `phan_quyet`, 2 `dieu`, 1 each `moc`,
`khoan`, `diem`), 1 generation error; trap 1; mơ hồ 10. Golden latency p95 121.0 s
(final run 74.4 s).
