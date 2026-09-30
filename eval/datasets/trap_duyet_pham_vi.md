# Owner review: the 15 trap "ngoài phạm vi" items under the Vietnamese-law scope

Decision record `docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md`, item 10
(owner, 2026-09-30): an item whose governing law is shown with full text now expects
"answer with correct citations"; genuinely out-of-scope items (foreign law, predicting
court outcomes, non-legal) keep `out_of_scope`. An agent applied the rule, and a review
round corrected the anchors. The owner has not read the result yet.

How to use this table: fill the last column with ✓ (the new label is right) or ✗, plus
a note if needed. The old labels are kept unchanged in `trap.truoc-pham-vi.yaml`.

Evidence, all read-only on the dev DB and the saved gateway JSON, 2026-09-30:

- "Shown" is the real rule, `hien_thi.hien_thi_luc(engine, as_of)`: 484 documents at
  as_of 2026-09-30, and the same 484 at 2026-09-28. The tl run saw 486, because
  101/2024/NĐ-CP and 102/2024/NĐ-CP were shown then. Both are hidden again today.
- "Full text" means more than one `provisions` row. A document shown without parsed
  text holds only its title row (decision 2026-09-28 item 16). One such document is
  168/2025/NĐ-CP.
- **An anchor is a stored provision whose text still gives the current answer.** When
  an article was rewritten, the anchor is the amending khoản, never the stored original
  or an intermediate version. This follows the golden-set rule
  (`golden_mapping_12-2022_283-2026.md`): the original article stays an anchor only
  when the amended text gives the same answer, as for lao-014/015 Điều 61. Nothing in
  the system swaps in current text for these articles. Decision 2026-09-28 item 18(a)
  runs only through `sua_doi_dieu_khoan` (`expand.py` `_SQL_NEO_SUA`). That table has
  47 rows for four documents (64/2025/QH15, Hiến pháp 2013, 45/2019/QH14, 52/2014/QH13
  Điều 123), and none of them covers these anchors.
- A hit also needs two things. The answer must not contain a `cam_nhac` phrase, which
  catches stated law that has since been amended (for example "cấp huyện" for the
  courts renamed by 85/2025/QH15). And no cited path may sit at or under a `cam_dan`
  prefix, which lists provisions that were repealed, with the repealing clause cited in
  `trap.yaml`.
- `tests/test_eval/test_trap_yaml.py` checks three things: each anchor resolves to
  exactly one `provisions` row, each `cam_dan` prefix matches at least one row, and the
  superseded paths below are not anchors.
- The re-score column applies three label sets to three recorded runs, with zero
  model calls: old, then the first relabel (commit e2554e3), then the current labels.
  It uses `eval.run_trap.dung` on the stored `result_type`, the cited paths, and the
  answer (`da_dan` and `tra_loi_dau` in `eval/results/kho-luat/*-trap.bo-sung.json`).
  `tra_loi_dau` is only the first 300 characters of the answer, so a `cam_nhac` phrase
  that appears later is missed here. A live run checks the full answer.
- Totals over the scored items: K11 8/13 → 7/13 → **1/8**, final 8/15 → 8/15 → **2/10**,
  tl 4/15 → 10/15 → **2/10**. The five `cho_duyet` items are not scored. The first
  relabel's tl figure of 10/15 counted answers that stated superseded law (oos-07 "Tòa án
  nhân dân cấp huyện") and answers that cited repealed provisions (oos-03 101/2024
  Điều 28, 30; oos-04 102/2024 Điều 106, 107). It also counted one answer that cited only
  superseded text (oos-11: 123/2015 Điều 2 khoản 1 and Điều 9 khoản 2).

| id | Question | Old label | New label | Governing law shown with full text? | Anchors (any one is a hit) and bans | Re-score K11 / final / tl (old → first relabel → now) | Duyệt (✓/✗ + ghi chú) |
|---|---|---|---|---|---|---|---|
| trap-oos-01 | thu nhập bao nhiêu thì phải đóng thuế thu nhập cá nhân | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật Thuế TNCN 109/2025/QH15 (210 rows): Điều 10 gives the 15,5 million đồng/month personal deduction; Điều 9 gives the brackets. Điều 7 khoản 1 ("500 triệu") was rewritten by 09/2026/QH16 Điều 1 from 01/01/2026. | 109/2025 Điều 10, Điều 9; 09/2026/QH16 Điều 1 | SAI→SAI→SAI / SAI→SAI→SAI / SAI→SAI→SAI (abstain each time) | |
| trap-oos-02 | thuế giá trị gia tăng hiện nay là bao nhiêu phần trăm | ngoai_pham_vi / out_of_scope | ngoai_pham_vi / **cho_duyet** (not scored) | No. Luật Thuế GTGT 48/2024/QH15 is not in the kho. 13/2008/QH12 is hidden. Decree 181/2025/NĐ-CP is hidden, title row only. | — | SAI→SAI→— / SAI→SAI→— / ok→ok→— | |
| trap-oos-03 | mua bán nhà đất cần những giấy tờ gì | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật Đất đai 31/2024/QH15 (2640 rows): Điều 27 khoản 3 (notarisation), Điều 45 (conditions, certificate), Điều 133 (registration of change). Luật Nhà ở 27/2023/QH15 (1638 rows): Điều 160, 164. | 31/2024 Điều 27 khoản 3, Điều 45, Điều 133; 27/2023 Điều 160, Điều 164. `cam_dan`: the NĐ 151/2025 Điều 21 khoản 4 b, c list (101/2024 and 102/2024) | SAI→ok→ok / SAI→ok→ok / SAI→ok→**SAI** (tl cited 101/2024 Điều 28, 30) | |
| trap-oos-04 | tranh chấp ranh giới đất đai giữa hai hộ gia đình giải quyết ở đâu | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật Đất đai Điều 235 (mandatory conciliation at the commune People's Committee) and Điều 236 khoản 1, 2 (court or People's Committee). The stored Điều 236 khoản 3 điểm a and khoản 4 still say "Chủ tịch Ủy ban nhân dân cấp huyện". NĐ 151/2025 Điều 5 khoản 2 điểm g moved that competence to the commune chair. | 31/2024 Điều 235, Điều 236 khoản 1, khoản 2; 102/2024 Điều 105 (hidden now, see note 2). `cam_nhac` "cấp huyện"; `cam_dan` as oos-03 | SAI→ok→**SAI** / SAI→ok→**SAI** / SAI→ok→**SAI** (K11 and final say "Ủy ban nhân dân cấp huyện"; tl cited 102/2024 Điều 106, 107) | |
| trap-oos-05 | sổ đỏ và sổ hồng khác nhau thế nào | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật Đất đai Điều 3 khoản 21 (the certificate). Điều 256 khoản 3: certificates issued earlier keep their legal value. | 31/2024 Điều 3 khoản 21, Điều 256 khoản 3 | ok→SAI→SAI / ok→SAI→SAI / SAI→SAI→SAI | |
| trap-oos-06 | thủ tục ly hôn đơn phương cần chuẩn bị giấy tờ gì | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. BLTTDS 92/2015/QH13 Điều 189 (petition and attachments). Luật HNGĐ 52/2014/QH13 (525 rows): Điều 51, 56. | 92/2015 Điều 189; 52/2014 Điều 56, Điều 51. `cam_nhac` "cấp huyện" (85/2025 renamed the courts) | error / SAI→SAI→SAI / SAI→SAI→SAI | |
| trap-oos-07 | muốn ly hôn thuận tình thì nộp đơn ở đâu | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. BLTTDS Điều 29 khoản 2, Điều 39 khoản 2 điểm h, Điều 396. The stored Điều 35 still says "Tòa án nhân dân cấp huyện". 85/2025/QH15 Điều 1 khoản 2 rewrote it as "Tòa án nhân dân khu vực". | 92/2015 Điều 39 khoản 2 điểm h, Điều 29 khoản 2, Điều 396; 85/2025 Điều 1 khoản 2. `cam_nhac` "cấp huyện" | SAI→ok→**SAI** / SAI→ok→ok / SAI→ok→**SAI** (K11 and tl say "Tòa án nhân dân cấp huyện") | |
| trap-oos-08 | đăng ký kết hôn cần thủ tục gì | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Partly (note 1). NĐ 123/2015/NĐ-CP (245 rows) Điều 10 lists the papers. Its khoản 1 was repealed by 07/2025/NĐ-CP Điều 2 khoản 10. Luật HNGĐ Điều 8, 9 are shown. Luật Hộ tịch 60/2014/QH13 is not in the kho. | 123/2015 Điều 10; 52/2014 Điều 9, Điều 8; 18/2026/NĐ-CP Điều 13 khoản 1. `cam_dan`: 24/2013/NĐ-CP, 126/2014 Điều 19–50, 123/2015 Điều 10 khoản 1 (note 4) | error / SAI→ok→**SAI** (final cited 126/2014 Điều 25, 26, 49 and 24/2013) / SAI→SAI→SAI | |
| trap-oos-09 | cấp lại căn cước công dân bị mất cần làm gì | ngoai_pham_vi / out_of_scope | ngoai_pham_vi / **cho_duyet** (not scored) | No. Luật Căn cước 26/2023/QH15 and NĐ 70/2024/NĐ-CP are not in the kho. Only a fee circular (71/2025/TT-BTC) and a sanctions decree (282/2025/NĐ-CP) mention it. | — | ok→ok→— / ok→ok→— / ok→ok→— | |
| trap-oos-10 | đăng ký kinh doanh hộ cá thể cần thủ tục gì | ngoai_pham_vi / out_of_scope | ngoai_pham_vi / **cho_duyet** (not scored) | No. The governing decree 168/2025/NĐ-CP is shown, but it holds only its title row. 01/2021/NĐ-CP is hidden. Luật Doanh nghiệp 59/2020/QH14 Điều 217 khoản 4 only says the Government regulates household-business registration. | — | ok→ok→— / ok→ok→— / SAI→SAI→— (abstain) | |
| trap-oos-11 | đăng ký khai sinh cho con cần giấy tờ gì | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Partly (note 1). NĐ 123/2015 Điều 9 khoản 1 names the papers. The stored Điều 9 khoản 2 still asks for the marriage certificate; 07/2025/NĐ-CP Điều 2 khoản 5 removed that. The stored Điều 2 khoản 1 still names the CMND; 18/2026/NĐ-CP Điều 13 khoản 1 rewrote it. | 123/2015 Điều 9 khoản 1; 07/2025 Điều 2 khoản 5; 18/2026 Điều 13 khoản 1 | ok→SAI→SAI / ok→SAI→SAI / SAI→ok→**SAI** (tl cited only the superseded texts and kept the marriage-certificate requirement) | |
| trap-oos-12 | khám bảo hiểm y tế trái tuyến có được thanh toán không | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật BHYT 25/2008/QH12 (357 rows) Điều 22 was rewritten by 46/2014/QH13 Điều 1 khoản 15, then by 51/2024/QH15 Điều 1 khoản 17, which is the current text. | 51/2024 Điều 1 khoản 17 | ok→SAI→SAI / ok→SAI→SAI / SAI→ok→ok | |
| trap-oos-13 | trẻ dưới sáu tuổi được cấp thẻ bảo hiểm y tế miễn phí không | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Current Điều 12 is 51/2024 Điều 1 khoản 10: khoản 3 điểm h lists children under 6. Current Điều 16 khoản 3 điểm d (valid to 72 months) is still the 46/2014 Điều 1 khoản 10 text, because 51/2024 Điều 1 khoản 14 rewrote only điểm c. The stored 2008 Điều 12, Điều 16 khoản 3 and Điều 17 khoản 2 were replaced. | 51/2024 Điều 1 khoản 10; 46/2014 Điều 1 khoản 10 | ok→SAI→SAI / ok→SAI→SAI / SAI→ok→ok | |
| trap-oos-14 | thủ tục nhập học lớp một cần giấy tờ gì | ngoai_pham_vi / out_of_scope | ngoai_pham_vi / **cho_duyet** (not scored) | No. Luật Giáo dục 43/2019/QH14 is hidden, title row only. The primary-school charter (28/2020/TT-BGDĐT) is not in the kho. No shown provision mentions grade 1 enrollment. | — | ok→ok→— / ok→ok→— / ok→ok→— | |
| trap-oos-15 | miễn giảm học phí đại học áp dụng cho đối tượng nào | ngoai_pham_vi / out_of_scope | ngoai_pham_vi / **cho_duyet** (not scored) | No. The tuition decrees 81/2021, 97/2023 and 238/2025/NĐ-CP are not in the kho. Luật Giáo dục đại học 08/2012/QH13 is shown but does not list who is exempt. | — | ok→ok→— / ok→ok→— / ok→ok→— | |

Superseded paths that are no longer anchors, each with its replacement:

| Stored path (outdated text) | What changed | Current text anchored instead |
|---|---|---|
| 109/2025/QH15 Điều 7 khoản 1 | "500 triệu" → threshold set by the Government, from 01/01/2026 | 09/2026/QH16 Điều 1 |
| 92/2015/QH13 Điều 35 | "Tòa án nhân dân cấp huyện" → "Tòa án nhân dân khu vực" | 85/2025/QH15 Điều 1 khoản 2 |
| 31/2024/QH15 Điều 236 (whole article) | khoản 3 điểm a, khoản 4: district chair → commune chair (NĐ 151/2025 Điều 5 khoản 2 điểm g; 151/2025 holds only its title row in the kho) | 31/2024 Điều 236 khoản 1, khoản 2 |
| 123/2015/NĐ-CP Điều 2 khoản 1 | CMND list rewritten | 18/2026/NĐ-CP Điều 13 khoản 1 |
| 123/2015/NĐ-CP Điều 9 (whole), Điều 9 khoản 2 | marriage certificate no longer required | 123/2015 Điều 9 khoản 1; 07/2025/NĐ-CP Điều 2 khoản 5 |
| 25/2008/QH12 Điều 22; 46/2014/QH13 Điều 1 khoản 15 | rewritten by 46/2014, then by 51/2024 | 51/2024/QH15 Điều 1 khoản 17 |
| 25/2008/QH12 Điều 12; 46/2014/QH13 Điều 1 khoản 6 | rewritten by 46/2014, then by 51/2024 | 51/2024/QH15 Điều 1 khoản 10 |
| 25/2008/QH12 Điều 16 khoản 3 | rewritten by 46/2014; 51/2024 rewrote điểm c again, so the stored "điểm c" now names a different rule | 46/2014/QH13 Điều 1 khoản 10 |
| 25/2008/QH12 Điều 17 khoản 2 | the children's dossier rule was removed by 46/2014 Điều 1 khoản 11; 51/2024 Điều 1 khoản 15 is the current Điều 17 | — (no current text answers the question) |

## Open for the owner

1. **Five Vietnamese-law items whose law is not shown with full text** (oos-02, 09, 10,
   14, 15). The owner's rule has two cases: the governing law is shown with full text,
   or the item is genuinely out of scope (foreign law, predicting court outcomes,
   non-legal). None of the 15 items is genuinely out of scope. These five are
   questions of Vietnamese law that the kho cannot support, so the rule does not
   decide them. They are marked `cho_duyet`. `eval/run_trap.py` still runs them and
   records the `result_type`, but it does not score them or add them to any total. That
   holds until the owner chooses one option:
   (a) keep `out_of_scope`. This matches today's router: `prompts/route.v5.md` still
   scopes by field and names giáo dục as `ngoai_pham_vi`.
   (b) expect `abstain`. `CONTEXT.md` defines abstain as the refusal when no live căn cứ
   supports an answer.
   (c) accept either refusal.
   (d) expect `partial_coverage`. This is closest to items 4 and 6 of the same decision
   record: the scope is Vietnamese law, and a needed text that cannot be cited ends
   with "Nên đối chiếu thêm".
   The first relabel kept `out_of_scope` for these five, which scored a run that follows
   items 4 and 6 as wrong on all five. Choosing among these options is the router-scope
   decision, which is separate.
2. **oos-10 differs from the example in the brief.** The brief named hộ kinh doanh as
   covered. The DB shows only the title of 168/2025/NĐ-CP. The item flips to
   `trong_pham_vi` once the parser loads that decree in depth (decision 2026-09-28 item 16).

## Notes

1. oos-08 and oos-11 are relabeled on implementing-decree coverage. The owner's own
   example named khai sinh. However, 123/2015/NĐ-CP Điều 9 and Điều 10 point back to
   Luật Hộ tịch Điều 16 and 18 for the core paper list, and that law is not in the kho.
   Mark ✗ if the statute itself is required.
2. 102/2024/NĐ-CP Điều 105 (conciliation procedure) is not on the repeal list in
   NĐ 151/2025/NĐ-CP Điều 21 khoản 4 điểm c. That list does include Điều 106 and 107.
   NĐ 226/2025/NĐ-CP Điều 4 and Điều 7 khoản 4 amend 102/2024 but do not touch
   Điều 105 (checked in the saved MOJ copy, `_scratch/du-lieu-n1/raw/moj/181906.json`).
   NĐ 49/2026/NĐ-CP also has an edge to 102/2024, but its text is not available, so it
   is unchecked. The decree is hidden today because of the CANH_SAI hold (commit
   ba25aef), so the anchor counts only after decision A un-hides it. Luật Đất đai
   Điều 235 and Điều 236 khoản 1, 2 keep oos-04 answerable without it.
3. The `cam_dan` list for oos-03 and oos-04 is the full NĐ 151/2025 Điều 21 khoản 4 b, c
   list: 101/2024 Điều 9 khoản 5, 11, Điều 19 khoản 1, Điều 20 khoản 3, Điều 21, 22,
   28–49, 60; 102/2024 Điều 14 khoản 1, Điều 54 khoản 1, 5, Điều 94 khoản 2 điểm c and
   khoản 3 điểm a, Điều 99 khoản 4, 6, Điều 100 khoản 3, Điều 101 khoản 6 điểm b,
   Điều 20, 21, 23, 44, 45, 48, 49, 51–53, 60, 64, 66, 68, 73, 106, 107. The forms
   (Mẫu số) are not provisions. The prefix match runs one way: citing Điều 9 as a whole
   is not citing its repealed khoản 5. If decision A breaks and these provisions reach
   citations again, this trap group fails.
4. oos-08 `cam_dan`. 24/2013/NĐ-CP lost effect in two steps: 126/2014 Điều 65 khoản 2
   repealed it except for listed rules, and 123/2015 Điều 45 khoản 2 điểm d repealed the
   rest from 01/01/2016. 126/2014 Điều 19–50 were repealed by 123/2015 Điều 45 khoản 2
   điểm đ. 123/2015 Điều 10 khoản 1 was repealed by 07/2025 Điều 2 khoản 10. 24/2013
   (273 rows) and 126/2014 are both shown today. That is a data-stage defect for
   decision A, not a label issue.
5. Adjacent, not changed (outside this group): trap-soul-06 `van_ban_ngoai_kho` fails
   any answer that names 126/2014. But 126/2014/NĐ-CP (document 47412) is now shown with
   352 rows, so the check penalises a correct citation of a shown decree. 01/2016 is
   still absent.
6. Data risk for oos-02: 57/2005/QH11 is shown (HHL1P, 11 rows). It amends the 2003 VAT
   law and carries a 2005 list of goods at the 5% rate (Điều 2 khoản 2). The system could
   cite that stale rate. This is for the effectivity data stage, not the labels.
7. Amending laws named in 147/2025/QH15 Điều 2 (58/2024, 84/2025, 93/2025, 95/2025/QH15)
   and Nghị quyết 254/2025/QH15 are not in the kho. The Luật Đất đai anchors are checked
   against every amending text the kho holds, but not against these.

## Documents behind the verdicts

| Document | id | tinh_trang | Shown 2026-09-30 | provisions rows |
|---|---|---|---|---|
| 109/2025/QH15 Luật Thuế TNCN | 187045 | HHL1P | yes | 210 |
| 09/2026/QH16 (sửa TNCN, GTGT, TNDN, TTĐB) | 6dbee1e0-… | CHL | yes | 9 |
| 31/2024/QH15 Luật Đất đai | 177815 | HHL1P | yes | 2640 |
| 27/2023/QH15 Luật Nhà ở | 169032 | HHL1P | yes | 1638 |
| 101/2024/NĐ-CP | 169188 | HHL1P | **no** | 947 |
| 102/2024/NĐ-CP | 169363 | HHL1P | **no** | 1440 |
| 151/2025/NĐ-CP (phân định thẩm quyền đất đai) | 178259 | HHL1P | yes | **1** (title only; text from the gateway JSON) |
| 226/2025/NĐ-CP (sửa các nghị định đất đai) | 181906 | HHL1P | yes | **1** (title only; text from the saved MOJ JSON) |
| 92/2015/QH13 BLTTDS | 96115 | HHL1P | yes | 2661 |
| 85/2025/QH15 (sửa BLTTDS) | 179420 | HHL1P | yes | 98 |
| 52/2014/QH13 Luật HNGĐ | 36870 | CHL | yes | 525 |
| 123/2015/NĐ-CP (hộ tịch) | 92897 | HHL1P | yes | 245 |
| 07/2025/NĐ-CP | 174485 | HHL1P | yes | 48 |
| 18/2026/NĐ-CP | 187582 | HHL1P | yes | 159 |
| 24/2013/NĐ-CP | 30386 | HHL1P | yes | 273 |
| 25/2008/QH12 Luật BHYT | 12326 | HHL1P | yes | 357 |
| 46/2014/QH13 | 36793 | HHL1P | yes | 34 |
| 51/2024/QH15 | 172923 | CHL | yes | 64 |
| 168/2025/NĐ-CP (đăng ký doanh nghiệp) | 179096 | HHL1P | yes | **1** (title only) |
| 43/2019/QH14 Luật Giáo dục | 136042 | CHL | **no** | 1 |
| 13/2008/QH12 Luật Thuế GTGT | 12806 | HHL | **no** | 1 |
| 181/2025/NĐ-CP (GTGT) | 187347 | HHL1P | **no** | 1 |
| 57/2005/QH11 (sửa Luật Thuế GTGT 2003) | 17065 | HHL1P | yes | 11 |
| 126/2014/NĐ-CP (HNGĐ) | 47412 | HHL1P | yes | 352 |
| 48/2024/QH15, 60/2014/QH13, 26/2023/QH15, 70/2024/NĐ-CP, 28/2020/TT-BGDĐT, 81/2021/NĐ-CP, 97/2023/NĐ-CP, 238/2025/NĐ-CP | — | not in the kho | — | — |
