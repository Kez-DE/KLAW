# KLAW

Vietnamese labor-law assistant. Every legal statement it shows is anchored to a
citation the backend resolved from stored statute text, and the anchoring is
checkable without asking a model.

## Language

### Answer surface

**answer**:
The prose KLAW asserts as law. Everything in it is backed by a verified claim and
carries a valid `doc`/`cite` tag. Hard limit 900 characters, at most 4 bullets.
_Avoid_: response, reply, output

**coverage_note**:
The part that states a limit of the answer — a dead end, a partial coverage, or the
single follow-up question. Not law, carries no citation. Hard limit 160 characters.
_Avoid_: note, footer, disclaimer

**đuôi hỏi thêm**:
The one follow-up question appended after a successful answer. Legitimate only when
the missing fact would change the conclusion.
_Avoid_: câu hỏi cuối, tail question, prompt for more

**miễn trừ**:
The fixed advisory-only notice. Written by the backend, never by the model.
_Avoid_: disclaimer, cảnh báo

### Reasoning

**claim**:
One legal statement bound to a `provision_id` and a verbatim quote. It is a
candidate until both verification tiers pass.
_Avoid_: luận điểm, statement, fact

**căn cứ**:
Statute text a claim is bound to. Only stored provisions qualify; a model's memory
never does.
_Avoid_: nguồn, source, evidence

**giả định**:
KLAW's reading of a fact the user did not state, always visible, always correctable,
never usable as căn cứ. Source `suy_dien`.
_Avoid_: assumption as fact, inferred fact, dữ kiện

**dữ kiện**:
A fact the user stated, or one carried in `ho_so`. Source `nguoi_noi`. Beats a
giả định with the same name.
_Avoid_: input, detail, thông tin

**dữ kiện quyết định**:
A missing dữ kiện whose value would change the conclusion. The only kind KLAW is
allowed to ask for.
_Avoid_: missing info, required field

**hồ sơ (`ho_so`)**:
The case facts carried across turns of one conversation, each with its source.
_Avoid_: profile, session state, context

**khung yêu cầu (`khung_yeu_cau`)**:
KLAW's structured reading of one question: the outcome the asker needs, the legal
question behind it, and the decisive facts still missing. A reading, never căn cứ.
_Avoid_: request frame, plan, intent object

**vai trò luận điểm (`vai_tro`)**:
What a verified claim does for the answer: `ket_luan` answers the question,
`dieu_kien` must hold for it, `ngoai_le` can reverse it, `che_tai` states the
consequence of breaching it.
_Avoid_: claim type, category, tag

**mức chắc (`muc_chac`)**:
How strongly an answer may be worded, derived from the claim roles and the
missing decisive facts: `chac` or `co_dieu_kien`. When no answer is issued the
outcome itself (abstain, partial_coverage) says "chưa đủ". Never a model
confidence score.
_Avoid_: confidence, certainty score, risk level

**hồ sơ đã dùng (`ho_so_da_dung`)**:
The subset of hồ sơ that actually shaped this turn's answer. Empty when the turn
did not read hồ sơ at all.
_Avoid_: profile shown, context used

**vụ việc (`vu_viec`)**:
The durable legal matter or drafting goal the asker is pursuing, kept in hồ sơ.
A question about KLAW itself or about the corpus is never a vụ việc.
_Avoid_: topic, session subject, case (in the litigation sense)


### Meta answers

**câu hỏi meta**:
A question about KLAW itself or about the corpus rather than about the law. It is
answered from system data by deterministic rules, never by a model.
_Avoid_: small talk, chit-chat, greeting

**khía cạnh (`khia_canh`)**:
One thing a câu hỏi meta asks for: identity, nature, capabilities, codes,
domains, corpus, drafting, sources, models. One question may carry several,
answered in the order asked.
_Avoid_: facet, intent, sub-question

**kho**:
The set of legal documents KLAW has loaded for this thesis, with each document's
effectivity verdict. Never "the law of Vietnam".
_Avoid_: corpus, database, knowledge base

### Outcomes

**abstain**:
The refusal issued when no live căn cứ supports an answer. A correct outcome, scored
as such.
_Avoid_: failure, no answer, fallback

**out_of_scope**:
The refusal issued when the question is outside the covered fields of law.
_Avoid_: rejected, unsupported

**partial_coverage**:
The outcome when căn cứ exists but does not interpret far enough to conclude.
_Avoid_: partial answer, incomplete
