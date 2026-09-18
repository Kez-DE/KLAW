# Execution Plan: Reproduce an uploaded form faithfully

Date: 2026-09-18

## Status

Active. Nine of ten measured categories are at 100% on the owner's own forms.
One gap remains, named and counted.

## Outcome

Observable by uploading a form and opening the draft:

1. A letterhead laid out as a borderless table renders as two columns with no
   table chrome, each column keeping the alignment the source declares.
2. A signature row keeps the blank height the source reserves for signing.
3. A real data table keeps its borders, per edge, at the declared weight.
4. Bold, italic, underline, size and font appear as the source declares them,
   inside table cells as well as in prose.
5. Paragraph spacing, indentation and tab stops survive, including the dotted
   leader that draws a form's fill-in line.
6. The page's own margins position the content, instead of the preview's padding.
7. A logo or stamp appears instead of vanishing.
8. The exported `.docx` and PDF agree with the screen, because all three read the
   same facts from the same DOM attributes.

## Context

The owner set the bar on 2026-09-18: "khi khách hàng đưa lên 1 mẫu văn bản phải
render được chuẩn, đầy đủ nội dung, vị trí … kể cả cấu trúc bảng, cấu trúc đặt
căn lề chính xác đến 99%". Measured that day, the reader took text, page, the
table grid and paragraph alignment, and nothing else — no borders, no character
formatting, no spacing, no page margins, no images.

`docs/decisions/2026-09-18-trung-thuc-bieu-mau-va-media.md` scopes the answer: a
richer read representation plus extracted media, never the original bytes and
never OOXML. That decision also states the ceiling plainly — without OOXML,
absolute positioning is reconstructed rather than copied, and a draft that passes
through the model is never as faithful as a cloned template.

## Approach

Every field took the same road, and each phase's report names the road it
followed: parser → persist/restore → block assembly → A4 preview → `.docx` and
PDF, with the DOM carrying the facts so the exporters cannot drift from the
screen. Two rules held throughout:

- `noi_dung` stays byte-identical. It is what the citation anchor, `normalize`
  and `lam_sach_van_ban` search, so every phase shipped an equivalence test:
  the same document read with and without the new element yields identical text,
  identical anchors, identical cleaner output and identical counters.
- Fail closed per element. One malformed value drops that element's detail rather
  than painting a guess.

## The ruler

`eval/run_trung_thuc.py` compares what the parser produces against what the
source XML declares, per category, with no model call and no network. It exists
because "99%" was unfalsifiable before it. Its own limits, stated so the number
is not read for more than it is worth:

- It scores the READER, not the three renderers. A category at 100% means KLAW
  read every declaration; that it draws them is proven by the `frontend/scripts/kiem-*`
  checks, each reverse-verified by breaking the code and watching the check fail.
- It counts only what a file DECLARES. An absent `w:jc` is "not declared", never
  "left-aligned", so silence cannot inflate a score.
- A category the representation cannot express scores 0 and says CHƯA CÀI rather
  than being quietly skipped.

## Progress

- [x] Borders and layout — a table the source leaves borderless renders as
      layout, with row height and per-cell alignment (`79f8914`, `7906a58`).
- [x] Character formatting — `w:rPr` as offset spans beside `noi_dung`, resolved
      through `w:rStyle`/`w:basedOn`, drawn in prose (`e7affaf`, `805067b`) and
      inside table cells (`4b2a1bc`, `c7f798e`). The cell round also fixed a real
      PDF defect: measuring and drawing a row used different code, so rows ran
      past the bottom margin.
- [x] Spacing, indentation and tab stops — including the dotted leader, drawn
      natively in `.docx` and by hand on screen and in the PDF (`bc640db`,
      `e4e5f84`, `661467f`).
- [x] Per-edge borders, page margins and the row-height rule (`38ae09f`,
      `22cc91a`, `480a574`). `exact` is deliberately drawn as a minimum: clipping
      the user's own text is worse than a row a few millimetres taller.
- [x] Images — extracted, stored per conversation under migration `035`,
      cascade-deleted, drawn in all three places (`1b3cb85`, `0ddf964`).
- [ ] Text boxes, lines and frames — 11 declarations, the one category still at
      0%. They have no `word/media/` part behind them; reading them means
      `wps:txbx` content and VML geometry, a different shape of work.

## Result

Measured on the owner's eight real forms, by declaration: 14.2% → 99.84%
(6811 of 6822). By category: nine of eleven at 100%, one at 0%.

The phase that closed images also corrected the ruler itself. The old `media`
category counted 8 declarations, but 11 of the shapes it saw were text boxes,
lines and frames with no image behind them, each double-counted because
`mc:AlternateContent` carries the same shape as both `w:drawing` and `w:pict`.
There are exactly two real images across the eight forms. Splitting the category
LOWERED the reported total — leaving it alone would have scored `media` 25% and
the total 92.5% — and named a gap that had been hiding inside a number.

## Limits, stated plainly

- Body images render at the end of the body, not at their true mid-document
  position: anchoring one needs a source block to attach to, and the model has
  already rewritten those blocks.
- Every image is centred; real horizontal placement lives in `wp:anchor`, which
  is absolute positioning and outside the 2026-09-18 decision.
- The on-screen tab leader starts where the cursor sits, which needs measuring
  rendered text; CSS alone cannot. The source margin now fixes where it STOPS.
- A multi-section document's second `w:sectPr` has nowhere to attach, so only the
  body-level page margins are read.
- Table-style borders replace a parent's edges rather than merging edge by edge
  as Word does; a child style that turns some edges off still reads as bordered.
