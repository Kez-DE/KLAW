import type { Config, PayloadRequest } from 'payload'

/**
 * Derived rather than imported: the global `AfterErrorHook` type lives in
 * `payload/dist/config/types.d.ts` but the name `AfterErrorHook` re-exported from
 * `payload` is the *collection* one (aliased to `CollectionAfterErrorHook`), so
 * importing it by name would silently bind the wrong signature.
 */
type AfterErrorHook = NonNullable<NonNullable<Config['hooks']>['afterError']>[number]

/**
 * Title the admin's error toast shows above the real reason — for the bulk
 * operations only, see `wantsGenericTitle` below.
 *
 * Deliberately generic. The bulk components pass this as the toast title and the
 * per-document reasons as its description, so a title that repeated a reason
 * verbatim would print it twice in the same toast.
 */
export const ERROR_TITLE = 'Không thực hiện được'

/**
 * Which admin surfaces want a generic `message` on the body, and which are
 * actively broken by one.
 *
 * Two groups read a failed response, and they read it incompatibly.
 *
 * **Bulk operations NEED a top-level `message`.** They render it as the toast
 * title with the reasons underneath:
 * `toast.error(json.message, { description: json.errors.map(e => e.message).join('\n') })`
 * — `DeleteMany/index.js:171`, `PublishMany/DrawerContent.js:116`,
 * `UnpublishMany/DrawerContent.js:109`, `RestoreMany/index.js:143`,
 * `Hierarchy/MoveMany/index.js:188,200`. Without it the toast has no title.
 *
 * **The edit form is DESTROYED by one.** `forms/Form/index.js:384`:
 *
 *     if (json.message) { errorToast(json.message); return }
 *     if (Array.isArray(json.errors)) { … ADD_SERVER_ERRORS … }
 *
 * That `return` is unconditional, so a `message` on the body means the second
 * branch never runs: no field is marked, and `errors[].message` — the line that
 * says WHICH field and WHY — is never rendered. Measured 2026-08-18 against the
 * running dev server: clearing a required Link `Type` and pressing Save produced
 * a bare "Không thực hiện được" toast, zero `has-error` classes anywhere in the
 * DOM, while the response body carried
 * `"The following field is invalid: Main menu > Main Menu 1 > Link > Type"` the
 * whole time. That applied to EVERY validation error and every hook throw in the
 * whole panel, not just links.
 *
 * The two groups are told apart by `where`. Every bulk component builds its
 * request from `qs.stringify({ where })` — `DeleteMany/index.js:112-119`,
 * `PublishMany/DrawerContent.js:84-87`, `UnpublishMany/DrawerContent.js:77-80`,
 * `RestoreMany/index.js:100-108`, `Hierarchy/MoveMany/index.js:160-162` — while
 * a form submit is always addressed to one document (`PATCH /api/<coll>/<id>`,
 * `POST /api/<coll>`) and never carries one. Read from `req.query`, Payload's
 * qs-parsed params, not from `searchParams`: qs serialises a constraint as
 * `where[id][in][0]=…`, so no raw param is literally named `where`.
 *
 * Not keyed off the error's own shape, which was the first idea and is wrong: a
 * form save also fails with plain non-field errors (a hook throw such as
 * `guardThemeKeys` or `guardSectionInUse`, a 403), and those bodies carry no
 * field paths to detect. Suppressing the title only for field errors would have
 * left exactly the reasons that are hardest to guess still hidden.
 */
const wantsGenericTitle = (req: PayloadRequest | undefined): boolean =>
  Boolean(req?.query && typeof req.query === 'object' && 'where' in req.query)

/**
 * Puts back the two keys Payload's admin panel reads *before* it reads the error.
 *
 * Measured 2026-08-16 against the running dev server: an error that reaches
 * `routeError` serialises as `{"errors":[{"message":"…"}]}` — no `docs` key.
 * `@payloadcms/ui/dist/elements/DeleteMany/index.js:154` then evaluates
 *
 *     const deletedDocs = json?.docs.length || 0
 *
 * whose `?.` guards `json` but not `docs`, so `undefined.length` throws
 * TypeError. That lands in the same file's `catch`, whose only statement is
 * `toast.error(t('error:unknown'))` — the bare "An unknown error has occurred."
 * the operator sees. The reason was in the body the whole time; the panel
 * crashed three lines before it would have rendered it. The same unguarded
 * dereference is in `PublishMany/DrawerContent.js:108` and
 * `UnpublishMany/DrawerContent.js:101`, which is why `docs` goes on every body
 * rather than only the ones that also get a title.
 *
 * `withTitle` decides only whether `message` comes along — see
 * `wantsGenericTitle`. It is a required argument on purpose: neither value is
 * safe as a default, one blinds the edit form and the other untitles the bulk
 * toasts, so a caller has to say which surface it is answering.
 *
 * Returns `undefined` — meaning "leave this response alone" — in two cases:
 *
 * - **`docs` already present.** A hook that throws inside a bulk operation is
 *   caught per document (`payload/dist/collections/operations/delete.js:227`)
 *   and pushed onto `errors` beside a real `docs` array. That path never
 *   crashes and already prints the reason; rewriting it could only change what
 *   it prints.
 * - **No errors to show.** Without a message to surface there is nothing to fix,
 *   and synthesising an empty `docs` array onto some other body shape would be
 *   guessing at a contract we have not measured.
 *
 * This does not widen what the server discloses. `routeError` replaces the
 * message of any non-public error with "Something went wrong." *before* calling
 * `afterError`, so genuine 500s stay masked here exactly as they were.
 */
export const readableErrorResponse = (
  result: unknown,
  { withTitle }: { withTitle: boolean },
): Record<string, unknown> | undefined => {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return undefined

  const body = result as Record<string, unknown>
  if ('docs' in body) return undefined

  const { errors } = body
  if (!Array.isArray(errors) || errors.length === 0) return undefined

  return { ...body, docs: [], totalDocs: 0, ...(withTitle ? { message: ERROR_TITLE } : {}) }
}

/**
 * Global `afterError` hook. Registered once in `config.ts` rather than per
 * collection: the crash above is in shared admin code, so every collection
 * reaches it the same way, and a per-collection list would silently omit
 * whichever collection someone forgets to add next.
 */
export const exposeErrorReason: AfterErrorHook = ({ req, result }) => {
  const response = readableErrorResponse(result, { withTitle: wantsGenericTitle(req) })
  return response ? { response } : undefined
}
