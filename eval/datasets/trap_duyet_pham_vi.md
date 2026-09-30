# Owner review: the 15 trap "ngoài phạm vi" items under the Vietnamese-law scope

Decision record `docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md`, item 10
(owner, 2026-09-30): an item whose governing law is shown with full text now expects
"answer with correct citations"; genuinely out-of-scope items (foreign law, predicting
court outcomes, non-legal) keep `out_of_scope`. An agent applied the rule. The owner has
not read the result yet.

How to use this table: fill the last column with ✓ (the new label is right) or ✗, plus
a note if needed. The old labels are kept unchanged in `trap.truoc-pham-vi.yaml`.

Evidence, all read-only on the dev DB, 2026-09-30:

- "Shown" is the real rule, `hien_thi.hien_thi_luc(engine, as_of)`: 484 documents at
  as_of 2026-09-30, and the same 484 at 2026-09-28. The tl run saw 486, because
  101/2024/NĐ-CP and 102/2024/NĐ-CP were shown then. Both are hidden again today.
- "Full text" means more than one `provisions` row. A document shown without parsed
  text holds only its title row (decision 2026-09-28 item 16). One such document is
  168/2025/NĐ-CP.
- Anchors follow the golden convention. An anchor is the governing article (prefix
  match covers its khoản and điểm), plus the amending khoản as an alternative. A
  repealed provision is never an anchor.
  `tests/test_eval/test_trap_yaml.py` checks that each anchor resolves to exactly one
  `provisions` row.
- The re-score column applies the new labels to three recorded runs, with zero model
  calls. It uses `eval.run_trap.dung` on the stored `result_type` plus the cited paths
  (`da_dan` in `eval/results/kho-luat/*-trap.bo-sung.json`). Cells read old label →
  new label. Totals: K11 8/13 → 7/13, final 8/15 → 8/15, tl 4/15 → 10/15.

| id | Question | Old label | New label | Governing law shown with full text? | Anchors (any one is a hit) | Re-score K11 / final / tl | Duyệt (✓/✗ + ghi chú) |
|---|---|---|---|---|---|---|---|
| trap-oos-01 | thu nhập bao nhiêu thì phải đóng thuế thu nhập cá nhân | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật Thuế TNCN 109/2025/QH15 (210 rows): Điều 10 gives the 15,5 million đồng/month personal deduction; Điều 9 gives the brackets. | 109/2025 Điều 10, Điều 9, Điều 7 khoản 1; 09/2026/QH16 Điều 1 | SAI→SAI / SAI→SAI / SAI→SAI (abstain each time) | |
| trap-oos-02 | thuế giá trị gia tăng hiện nay là bao nhiêu phần trăm | ngoai_pham_vi / out_of_scope | unchanged, **pending owner** | No. Luật Thuế GTGT 48/2024/QH15 is not in the kho. 13/2008/QH12 is hidden. Decree 181/2025/NĐ-CP is hidden, title row only. | — | SAI / SAI / ok | |
| trap-oos-03 | mua bán nhà đất cần những giấy tờ gì | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật Đất đai 31/2024/QH15 (2640 rows): Điều 27 khoản 3 (notarisation), Điều 45 (conditions, certificate), Điều 133 (registration of change). Luật Nhà ở 27/2023/QH15 (1638 rows): Điều 160, 164. | 31/2024 Điều 27 khoản 3, Điều 45, Điều 133; 27/2023 Điều 160, Điều 164 | SAI→ok / SAI→ok / SAI→ok | |
| trap-oos-04 | tranh chấp ranh giới đất đai giữa hai hộ gia đình giải quyết ở đâu | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật Đất đai Điều 235 (mandatory conciliation at the commune People's Committee) and Điều 236 (competence). | 31/2024 Điều 235, Điều 236; 102/2024 Điều 105 (hidden now, see note 2) | SAI→ok / SAI→ok / SAI→ok (tl hit only via 102/2024 Điều 105) | |
| trap-oos-05 | sổ đỏ và sổ hồng khác nhau thế nào | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật Đất đai Điều 3 khoản 21 (the certificate). Điều 256 khoản 3: certificates issued earlier keep their legal value. | 31/2024 Điều 3 khoản 21, Điều 256 khoản 3 | ok→SAI / ok→SAI / SAI→SAI | |
| trap-oos-06 | thủ tục ly hôn đơn phương cần chuẩn bị giấy tờ gì | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. BLTTDS 92/2015/QH13 Điều 189 (petition and attachments). Luật HNGĐ 52/2014/QH13 (525 rows): Điều 51, 56. | 92/2015 Điều 189; 52/2014 Điều 56, Điều 51 | error / SAI→SAI / SAI→SAI | |
| trap-oos-07 | muốn ly hôn thuận tình thì nộp đơn ở đâu | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. BLTTDS Điều 29 khoản 2, Điều 39 khoản 2 điểm h, Điều 396. Điều 35 was rewritten by 85/2025/QH15 Điều 1 khoản 2 ("Tòa án nhân dân khu vực"). | 92/2015 Điều 39 khoản 2 điểm h, Điều 35, Điều 29 khoản 2, Điều 396; 85/2025 Điều 1 khoản 2 | SAI→ok / SAI→ok / SAI→ok | |
| trap-oos-08 | đăng ký kết hôn cần thủ tục gì | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Partly (note 1). NĐ 123/2015/NĐ-CP (245 rows) Điều 10 lists the papers. Luật HNGĐ Điều 8, 9 are shown. Luật Hộ tịch 60/2014/QH13 is not in the kho. | 123/2015 Điều 10, Điều 2 khoản 1; 52/2014 Điều 9, Điều 8; 18/2026/NĐ-CP Điều 13 khoản 1 | error / SAI→ok / SAI→SAI | |
| trap-oos-09 | cấp lại căn cước công dân bị mất cần làm gì | ngoai_pham_vi / out_of_scope | unchanged, **pending owner** | No. Luật Căn cước 26/2023/QH15 and NĐ 70/2024/NĐ-CP are not in the kho. Only a fee circular (71/2025/TT-BTC) and a sanctions decree (282/2025/NĐ-CP) mention it. | — | ok / ok / ok | |
| trap-oos-10 | đăng ký kinh doanh hộ cá thể cần thủ tục gì | ngoai_pham_vi / out_of_scope | unchanged, **pending owner** | No. The governing decree 168/2025/NĐ-CP is shown, but it holds only its title row. 01/2021/NĐ-CP is hidden. Luật Doanh nghiệp 59/2020/QH14 Điều 217 khoản 4 only says the Government regulates household-business registration. | — | ok / ok / SAI (abstain) | |
| trap-oos-11 | đăng ký khai sinh cho con cần giấy tờ gì | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Partly (note 1). NĐ 123/2015 Điều 9 lists the papers. Điều 9 khoản 2 was amended by 07/2025/NĐ-CP Điều 2 khoản 5. Điều 2 khoản 1 was amended by 18/2026/NĐ-CP Điều 13 khoản 1. | 123/2015 Điều 9, Điều 2 khoản 1; 07/2025 Điều 2 khoản 5; 18/2026 Điều 13 khoản 1 | ok→SAI / ok→SAI / SAI→ok | |
| trap-oos-12 | khám bảo hiểm y tế trái tuyến có được thanh toán không | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật BHYT 25/2008/QH12 (357 rows) Điều 22. It was rewritten by 46/2014/QH13 Điều 1 khoản 15, then by 51/2024/QH15 Điều 1 khoản 17 (the current text). | 51/2024 Điều 1 khoản 17; 25/2008 Điều 22; 46/2014 Điều 1 khoản 15 | ok→SAI / ok→SAI / SAI→ok | |
| trap-oos-13 | trẻ dưới sáu tuổi được cấp thẻ bảo hiểm y tế miễn phí không | ngoai_pham_vi / out_of_scope | trong_pham_vi / tra_loi_dan_dung | Yes. Luật BHYT: Điều 12 (children under 6 are a state-paid group, current text 51/2024 Điều 1 khoản 10), Điều 16 khoản 3, Điều 17 khoản 2. | 51/2024 Điều 1 khoản 10; 25/2008 Điều 12, Điều 16 khoản 3, Điều 17 khoản 2; 46/2014 Điều 1 khoản 6, khoản 10 | ok→SAI / ok→SAI / SAI→ok | |
| trap-oos-14 | thủ tục nhập học lớp một cần giấy tờ gì | ngoai_pham_vi / out_of_scope | unchanged, **pending owner** | No. Luật Giáo dục 43/2019/QH14 is hidden, title row only. The primary-school charter (28/2020/TT-BGDĐT) is not in the kho. No shown provision mentions grade 1 enrollment. | — | ok / ok / ok | |
| trap-oos-15 | miễn giảm học phí đại học áp dụng cho đối tượng nào | ngoai_pham_vi / out_of_scope | unchanged, **pending owner** | No. The tuition decrees 81/2021, 97/2023 and 238/2025/NĐ-CP are not in the kho. Luật Giáo dục đại học 08/2012/QH13 is shown but does not list who is exempt. | — | ok / ok / ok | |

## Open for the owner

1. **Five Vietnamese-law items whose law is not shown with full text** (oos-02, 09, 10,
   14, 15). The owner's rule has two cases: the governing law is shown with full text,
   or the item is genuinely out of scope (foreign law, predicting court outcomes,
   non-legal). None of the 15 items is genuinely out of scope. These five are
   questions of Vietnamese law that the kho cannot support, so the rule does not
   decide them. They keep `out_of_scope` until the owner chooses one option:
   (a) keep `out_of_scope`. This matches today's router: `prompts/route.v5.md` still
   scopes by field and names giáo dục as `ngoai_pham_vi`.
   (b) expect `abstain`. `CONTEXT.md` defines abstain as the refusal when no live căn cứ
   supports an answer.
   (c) accept either refusal.
   The agent recommends (c). The risk this group measures is answering without law,
   and both refusals avoid it. Choosing between them is the router-scope decision,
   which is separate.
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
   The decree is hidden today because of the CANH_SAI hold (commit ba25aef), so the
   anchor counts only after decision A un-hides it. Luật Đất đai Điều 235 and 236 keep
   oos-04 answerable without it.
3. Evidence for decision A: the tl run's answers cited 101/2024 Điều 28 and 30 (oos-03)
   and 102/2024 Điều 106 and 107 (oos-04). NĐ 151/2025 Điều 21 khoản 4 b and c repeals
   all four (gateway JSON 178259). None of them is an anchor. oos-03 still scores as a
   hit in tl because the same answer also cited Luật Nhà ở Điều 160.
4. Adjacent, not changed (outside this group): trap-soul-06 `van_ban_ngoai_kho` fails
   any answer that names 126/2014. But 126/2014/NĐ-CP (document 47412) is now shown with
   352 rows, so the check penalises a correct citation of a shown decree. 01/2016 is
   still absent.
5. Data risk for oos-02: 57/2005/QH11 is shown (HHL1P, 11 rows). It amends the 2003 VAT
   law and carries a 2005 list of goods at the 5% rate (Điều 2 khoản 2). The system could
   cite that stale rate. This is for the effectivity data stage, not the labels.

## Documents behind the verdicts

| Document | id | tinh_trang | Shown 2026-09-30 | provisions rows |
|---|---|---|---|---|
| 109/2025/QH15 Luật Thuế TNCN | 187045 | HHL1P | yes | 210 |
| 09/2026/QH16 (sửa TNCN, GTGT, TNDN, TTĐB) | 6dbee1e0-… | CHL | yes | 9 |
| 31/2024/QH15 Luật Đất đai | 177815 | HHL1P | yes | 2640 |
| 27/2023/QH15 Luật Nhà ở | 169032 | HHL1P | yes | 1638 |
| 101/2024/NĐ-CP | 169188 | HHL1P | **no** | 947 |
| 102/2024/NĐ-CP | 169363 | HHL1P | **no** | 1440 |
| 92/2015/QH13 BLTTDS | 96115 | HHL1P | yes | 2661 |
| 85/2025/QH15 (sửa BLTTDS) | 179420 | HHL1P | yes | 98 |
| 52/2014/QH13 Luật HNGĐ | 36870 | CHL | yes | 525 |
| 123/2015/NĐ-CP (hộ tịch) | 92897 | HHL1P | yes | 245 |
| 07/2025/NĐ-CP | 174485 | HHL1P | yes | 48 |
| 18/2026/NĐ-CP | 187582 | HHL1P | yes | 159 |
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
