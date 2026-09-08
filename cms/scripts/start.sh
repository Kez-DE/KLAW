#!/usr/bin/env bash
#
# Production entrypoint: apply migrations, PROVE they applied, then serve.
#
# WHY THIS EXISTS
#
# `start` used to be `payload migrate && next start`. On 2026-08-17 that shipped
# a schema mismatch to production: `payload migrate` exited 0 having applied
# nothing, so `next start` came up serving a config whose `productSpecGrid`
# block referenced columns that did not exist. Every read at `depth >= 1`
# returned 500 —
#
#   error: column sc__blocks_productSpecGrid_items_specs.icon_id does not exist
#
# — which is the entire frontend content path, because config.ts sets
# `defaultDepth: 3`. `payload migrate:status` on the running container still
# listed the migration as `No`. Roughly two minutes of downtime, ended by
# running `npx payload migrate` by hand over `railway ssh`.
#
# Same failure mode `scripts/run-migration.sh` documents for `payload run`:
# the CLI's dynamic `import('payload')` never resolves, the event loop drains,
# the process exits 0 having done nothing. Silent success. `&&` cannot catch it
# because the exit status is a lie — the only honest signal is an external
# observation of the database.
#
# WHAT THIS DOES
#
# Runs the migration, then reads `migrate:status` back and refuses to start the
# server unless every migration file is recorded as applied. A no-op run leaves
# rows at `No` and is retried; a second failure exits non-zero so the deploy
# goes red instead of serving broken reads.
#
# Fail-closed on purpose: if `migrate:status` prints no table at all — the CLI
# no-opping on the verification step this time — that counts as a failure, not
# as "nothing pending". Never infer success from absent output.

set -uo pipefail

# `pnpm start` would put this on PATH for us, but then the script only works
# when invoked exactly that way — and a `payload: command not found` here reads
# as "migrations unreadable", i.e. it fails the deploy for the wrong reason.
# Setting it ourselves makes `bash scripts/start.sh` behave identically.
cd "$(dirname "$0")/.." || exit 1
PATH="$PWD/node_modules/.bin:$PATH"
export PATH

# Fail closed: `payload.config.ts` builds `origins` from these two variables; if
# production has neither, `origins` is `[]` and `csrf: []` makes Payload accept the
# session cookie from any Origin. Refuse to boot rather than serve that silently.
if [ "${NODE_ENV:-}" = production ] && [ -z "${PAYLOAD_PUBLIC_SERVER_URL:-}" ] && [ -z "${RAILWAY_PUBLIC_DOMAIN:-}" ]; then
  echo "[start] FATAL: production thiếu cả PAYLOAD_PUBLIC_SERVER_URL và RAILWAY_PUBLIC_DOMAIN — allowlist CSRF sẽ rỗng, chấp nhận mọi Origin." >&2
  exit 1
fi

readonly MAX_ATTEMPTS=2

# Table rows are `│ <name> │ <batch> │ Yes|No │`. Match only lines carrying a
# migration filename (`YYYYMMDD_HHMMSS_`) so the WARN line "No email adapter
# provided" — which also contains " No " — cannot be miscounted as a pending
# migration.
readonly NAME_SHAPE='[0-9]{8}_[0-9]{6}_'

strip_ansi() { sed -E $'s/\x1b\\[[0-9;]*[A-Za-z]//g'; }

# Echoes the pending count, or "unreadable" when the status table never appeared.
pending_count() {
  local out
  out="$(payload migrate:status 2>&1 | strip_ansi)"

  # ` Ran ` is the status table's own column header. No header means the CLI
  # produced no table, so we know nothing — say so rather than report zero.
  if ! printf '%s\n' "$out" | grep -q ' Ran '; then
    echo unreadable
    return
  fi

  printf '%s\n' "$out" | grep -E "$NAME_SHAPE" | grep -c ' No '
}

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  echo "[start] applying migrations (attempt ${attempt}/${MAX_ATTEMPTS})"
  payload migrate

  pending="$(pending_count)"
  echo "[start] pending migrations after attempt ${attempt}: ${pending}"

  if [ "$pending" = "0" ]; then
    echo "[start] migrations verified, starting server"
    exec next start -p "${PORT:-3001}"
  fi
done

echo "[start] FATAL: migrations did not apply after ${MAX_ATTEMPTS} attempts (pending: ${pending})." >&2
echo "[start] Refusing to start: serving the new config on the old schema returns 500 on every depth>=1 read." >&2
echo "[start] Inspect with: railway ssh --service klaw-cms 'cd /app && payload migrate:status'" >&2
exit 1
