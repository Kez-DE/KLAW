# KLAW frontend

Vite + React + TypeScript + Tailwind. Builds to `../src/static`, served by the
FastAPI backend at `/` (see `src/main.py`). In dev, `/api` proxies to
`http://localhost:8000` (`vite.config.ts`).

## Scripts

- `npm run dev` — dev server with HMR
- `npm run build` — typecheck (`tsc -b`) + production build into `../src/static`
- `npm run typecheck` — typecheck only, no build
- `npm run lint` — oxlint (this template's default linter)
- `npm run preview` — preview a production build locally

## Structure

- `src/styles/tokens.css` — design tokens (colors, type, radius, elevation,
  motion, z-layers) as CSS custom properties, plus the Tailwind `@theme`
  wiring that exposes the color/font/radius/shadow/perspective/ease ones as
  utility classes. Source of truth: `../DESIGN.md`.
- `src/types.ts` — TypeScript types mirroring the API contract 1:1.
- `src/lib/api.ts` — typed fetch client for the backend endpoints, including
  the still-hypothetical `GET /api/v1/pham-vi` (no contract exists yet — see
  the doc comment on `layPhamVi`/`PhamViResponse`).
- `src/lib/useTieuDeTrang.ts` — sets `<title>`/meta description/`og:*` per
  route from one table in `App.tsx`, and does the SPA accessibility chores a
  browser gives you for free on a real page load: resets keyboard focus to
  the new page's `<h1>` and announces the route change via `aria-live`. Runs
  centrally off `useLocation()` so it covers every route, including the three
  screens this hook's own file may not touch.
- `src/App.tsx` — all seven routes + a catch-all 404. The three Read routes
  (`/huong-dan`, `/pham-vi`, `/mien-tru`) code-split with `React.lazy`; `/`
  and `/tra-cuu` load eagerly.
- `src/pages/*` — `TraCuu` is the built lookup screen. `HuongDan`, `PhamVi`,
  `MienTru`, `KhongTimThay` are built Read pages. `GioiThieu` is a
  deliberately minimal placeholder (an `<h1>` and a real question input into
  `/tra-cuu`) for another session to design fully. `SoanThao`/`Soat` are
  still empty placeholders pending their backend endpoints.
- `src/components/Nav.tsx` — the persistent "đổi khay phim" tab bar (the
  three Operate screens only).
- `src/components/Footer.tsx` — on every route: links to Giới thiệu / Hướng
  dẫn / Phạm vi dữ liệu / Miễn trừ trách nhiệm, plus a one-line description.
- `src/components/ErrorBoundary.tsx` — wraps the whole app in `App.tsx` so a
  render error shows a real message and a reload button instead of a blank
  page.

## Fonts — four roles, all self-hosted, Vietnamese coverage verified

Four roles per `KLAW-BUILD-SPEC` §5.2, wired as `--font-*` tokens in
`src/styles/tokens.css` and imported in `src/index.css`:

| Token | Role | Family | Weights loaded |
|---|---|---|---|
| `--font-tieu-de` | headings (`h1`, `h2`) | Playfair Display | 500, 600 |
| `--font-doc` | body & UI | Be Vietnam Pro | 400, 500, 600, 700 |
| `--font-phim` | statute text on the film surface | Source Serif 4 | 400, 700 |
| `--font-dia-chi` | document numbers / citation paths | JetBrains Mono | 400, 500 |

All four are self-hosted via `@fontsource`. **Not** `next/font` — this is Vite,
not Next.js — and not the Google Fonts CDN, because a slow-network user should
not depend on a third-party host. Each `@fontsource/<family>/<weight>.css`
declares every subset with its own `unicode-range`, so the browser downloads
only the subsets a page actually needs.

Only weights with a real consumer are imported. Playfair 700 is deliberately
skipped: no heading uses `font-bold`. Be Vietnam Pro 600 was **added** here —
`font-semibold` is used on six `h1`s but the 600 face was previously missing,
so the browser was synthesising it.

`h3` deliberately does **not** get Playfair: every `h3` in this codebase renders
at 13px (`text-[0.8125rem]`), which is the spec's `caption` role, not its
`h3 24px` role. A high-contrast display serif at 13px loses its hairlines and
crowds stacked Vietnamese diacritics. See the comment in `src/index.css` for why
the heading rule needs its apparently-redundant `h1.mat-doc, h2.mat-doc` branch.

### Mandatory glyph test (spec §5.2) — passed, no Noto substitution needed

Test string: `Ưu đãi thuế đối với doanh nghiệp — Điều 25, khoản 2, điểm ạ ẫ ộ ữ ỹ`

Verified two independent ways in a real browser (Chrome, via devtools), not by
assumption:

1. `document.fonts.check('500 16px "<family>"', <test string>)` returned true
   for all four families, and also for the stacked-diacritic set `ạẫộữỹếốớệ`
   on its own.
2. Canvas `measureText` of the hard-diacritic set in each family differs from
   the same string measured with a deliberately non-existent family (which
   forces the generic fallback) — confirming the glyphs really come from the
   intended font rather than silently from a fallback.

**No glyph fell back, so no family was replaced with `Noto Serif`/`Noto Sans`.**

One gotcha worth knowing before re-running this check: `document.fonts.check()`
returns **false** for a family whose `vietnamese` subset has not been downloaded
yet, because subsets load lazily and only when a glyph in their `unicode-range`
is actually painted. JetBrains Mono initially reported false on `/` for exactly
this reason — that route renders document numbers (`45/2019/QH14`) which are
pure ASCII, so its Vietnamese subset was never requested. Call
`await document.fonts.load('500 16px "JetBrains Mono"', <string>)` first, then
check. A false here is not by itself evidence of a missing glyph.

## Hero 3D (WebGL) — verified versions, and what keeps it honest

`/` mounts a WebGL scene ("the floating law archive") in the hero's 3D slot at
768px and up. Everything below was measured on a **production build** served by
`vite preview`, not on the dev server — a dev-server number for this page is
meaningless, because the unbundled module graph dominates it.

### Verified versions (KLAW-BUILD-SPEC §3.2)

| Package | Installed | Peer requirement | Result |
|---|---|---|---|
| `react` / `react-dom` | 19.2.8 (pinned exactly) | — | — |
| `@react-three/fiber` | 9.7.0 | `react` / `react-dom` `>=19 <19.3` | PASS |
| `@react-three/drei` | 10.7.8 | `react` `^19`, `@react-three/fiber` `^9.0.0` | PASS |
| `three` | 0.185.1 (single deduped copy) | `>=0.159` (drei) | PASS |

Installed with **no** `--force` and **no** `--legacy-peer-deps`; npm reported no
peer warnings and no vulnerabilities. `@types/three` arrives transitively via
drei — `three` itself ships no type declarations.

**`react` and `react-dom` are pinned to an exact `19.2.8`, not `^19.2.8`.** The
caret range admits 19.3, which R3F's peer range (`>=19 <19.3`) excludes, so a
routine `npm install` could have quietly broken the peer contract with no code
change. Removing one character per line closes that off. When you do want to
move React, bump R3F in the same commit and re-run the table above.

### The four performance constraints (§10.4), with evidence

1. **Below 768px, `three` is never downloaded.** `SlotBaChieu` decides before
   rendering, and `React.lazy` only invokes its import factory when the
   component actually renders. Verified at an emulated 390x844, dpr 3: total
   requests were the 3 entry scripts, one API call and the favicon; the
   Resource Timing API — the browser's own record of every fetch — contained
   **zero** entries matching `KhoLuat|three|drei|fiber`; `document.querySelectorAll('canvas').length`
   was **0**. The built `index.html` also carries no `modulepreload` for the
   chunk, and the main bundle contains zero `three` fingerprints.
   Mobile is not a degraded hero: it gets the full CSS microfilm machine with
   the same real statute.
2. **Rendering actually stops** when the hero leaves the viewport or the tab is
   hidden. §10.4 asks for an early return inside `useFrame`, but that does not
   stop anything — R3F still calls `gl.render()` and the GPU still draws. So
   `frameloop` is state-driven (`never` / `demand` / `always`) and the early
   return is only the second gate. Measured by counting real WebGL draw calls:
   4,213 draws/s visible -> **0** scrolled out -> 4,203 on return -> **0** with
   `document.hidden` -> 4,201 on return.
3. **`dpr={[1, 1.75]}`, `antialias: false`, `powerPreference`** as specified. At
   `devicePixelRatio` 2 the effective ratio measured **1.75** (canvas backing
   store 1396x696, 0.97 MP) — the clamp is doing its job.
4. **One geometry, three shared materials** for all 30 meshes (15 slates + 15
   brass frames, which reuse the same `BoxGeometry` at a different scale). The
   third material exists only because §10.2 requires hover to change
   `emissiveIntensity`, which on a shared material would light all fifteen
   frames at once. Steady state is 35 draw calls per frame.

### Measured numbers

| Metric | Unthrottled | CPU 4x + Fast 4G | Budget |
|---|---|---|---|
| First WebGL draw (hero interactive) | 423 ms | **831 ms** | < 2500 ms (§10.4) |
| LCP | — | 530 ms | — |
| CLS | — | 0.0263 | < 0.1 |
| Frame rate | 120 fps | 120 fps | 60 fps (§10.4) |

Frame rate is pinned to the display's 120Hz refresh in both columns, so 120 fps
is the ceiling being hit, not the scene's limit.

**CLS attributable to the hero slot is 0.** The 0.0263 comes entirely from web
font loading (`playfair-display`, `be-vietnam-pro`, `jetbrains-mono`) and
predates this work; every one of the 7 recorded shift sources lies outside
`.gt-khay`. The visible tray measured exactly 400px on all 148 samples across
the fallback-to-canvas swap. Note when re-measuring: React keeps a suspended
Suspense subtree mounted with `display: none`, so during the reveal there are
briefly **two** `.gt-khay` nodes — `querySelector('.gt-khay')` can grab the
hidden one and report height 0. Filter by `offsetParent !== null`.

Bundle: the async chunk is 1,060.81 kB raw / **297.47 kB gzip** (295,233 bytes
on the wire). Deep-importing individual drei modules instead of the package
root produced a byte-identical chunk, so that weight is `three` + troika +
R3F itself, not barrel-import waste. The main entry chunk is unchanged at
313.09 kB / 95.37 kB gzip.

**troika (drei `<Text>`) costs 41.99 kB gzip**, measured by a differential
build: 297.47 kB gzip with `<Text>`, 255.48 kB without (1,060.81 kB vs
945.26 kB raw). That is under the 60 kB line agreed for dropping it, so drei
`<Text>` stays and §10.1 is followed literally. Hand-rolling canvas-2D label
textures to save 42 kB would be a maintenance debt, not an optimisation — and
it is worth knowing the number rather than guessing, because the intuition
that troika is "most of the bundle" is wrong: `three` itself is.

Console on load: zero errors, one warning (`THREE.Clock` deprecation, emitted
from inside R3F).

### Where this deliberately departs from the spec

Each of these is also commented at the code, with the measurement that forced it.

- **`<Environment preset="city" />` -> `RoomEnvironment` + `PMREMGenerator`.**
  drei's presets fetch an HDR from a third-party CDN, which adds a network
  round-trip to the very metric §10.4 constrains and makes the hero depend on an
  outside host. `RoomEnvironment` ships inside `three`, gives brass the same
  thing to reflect, and costs 0 bytes. `environmentIntensity` stays 0.4.
- **`config={{ mass: 1, tension: 180 }}` -> `damping={0.3}`.** That prop no
  longer exists: drei 10 dropped react-spring for maath easing and takes a
  smoothTime in seconds. The original spring was near-critically damped
  (zeta ~= 0.97) and settled in ~0.3s, so this is a translation, not a guess.
- **`PresentationControls` gets `global`.** Each slate's `onPointerOver` calls
  `stopPropagation()` so only the nearest slate hovers; that also stopped the
  gesture from ever seeing a pointer (the cursor on the events element never
  changed). With `global`, drei binds DOM listeners to the canvas directly.
  Verified: `grab` at mount -> `grabbing` during drag -> `grab` on release.
- **The hover readout is a still plate in the tray, not an `<Html>` glued to the
  slate.** `.gt-khay` clips hard at 398px while the readout is 95-147px tall
  depending on the document name and effectivity label. Anchoring it to a
  moving object only moved where it got cut: 109px, then 52px, then 73px of
  overflow as offsets were tuned. Measured after the change: 64 hover samples
  across 11 distinct documents, **zero** overflow. The pointer-to-slate link is
  not lost, because §10.2 puts that feedback in the slate — which still lifts
  0.15 and lights its brass frame. The excerpt card stays an `<Html>` centred on
  the slate and clears the tray by 48px with the corpus's longest excerpt.
- **No GSAP / ScrollTrigger.** The whole requirement is a 0..1 number in a ref,
  read inside `useFrame`; a passive scroll listener does it in four lines.
  Adding ~70KB for that would contradict the budget §10.4 sets.
- **`<Text>` labels are the four ASCII document numbers.** troika renders from a
  single font file, and the self-hosted JetBrains Mono is subset: the `latin`
  file has digits and `/` but not `Đ` (U+0110), so any `NĐ-CP` or `BLĐTBXH`
  number would render as tofu on the slate face. Those numbers still appear in
  full in the readout, the card and the keyboard list, which are real DOM using
  the page's real fonts.
- **Document numbers come from the database, not from the spec.** §10.1 offers
  four examples; two of them (`36/2005/QH11`, `356/2025/NĐ-CP`) **do not exist**
  in the corpus, so they were replaced with `84/2015/QH13` and `92/2015/QH13`.
  Printing a fabricated document number on the hero of a product about
  verifiable citation would be the worst defect available. See the header of
  `src/components/hero3d/duLieuPhien.ts` for the full provenance, including why
  `hieuLuc` is the verdict from `src/services/effectivity.py` rather than
  `documents.tinh_trang` read straight off.

### Accessibility

A `<canvas>` cannot be tabbed to and exposes nothing to a screen reader, so all
fifteen slates would have been mouse-only (WCAG 2.1.1). A visually-hidden list
of buttons selects any slate; the focused button reveals itself with a brass
outline so focus stays visible (2.4.7); Escape closes the card. The readout and
card are real DOM reusing `DuongDan` and `BadgeHieuLuc`. Verified in the
accessibility tree: all 15 documents appear as expandable buttons carrying
document number, full Vietnamese name and real effectivity label.

`prefers-reduced-motion: reduce` mounts the scene and freezes it: measured
**0 draw calls in 2 seconds** while idle, with click still working (one click
produced exactly 35 draws — a single on-demand render — and opened the real
excerpt).

### Re-running the checks

The 768px gate is guarded by a self-check, because it is the one invariant whose
regression is completely silent — nothing throws, types stay green, desktop looks
identical, and mobile quietly starts downloading 297 kB. It asserts against the
**build output**, not the source, since "the 3D chunk cannot reach a phone" is a
property only the build can state:

```bash
npm run build && node scripts/kiem-cua-3d.ts
```

It checks that the eager graph (entry plus everything it `modulepreload`s, plus
the transitive closure of their *static* imports) contains no `three`/drei/troika
fingerprint; that the 3D chunk exists, does carry those fingerprints, and sits
outside that graph; that nothing static-imports it while something dynamic-imports
it; and that the width guard returns before `<KhoLuat>` is referenced, at the same
`48rem` the stylesheet uses.

It was verified by mutation — three deliberate breaks, each confirmed to turn it
red. The third one initially **escaped**, which is the whole reason the mutation
step exists: `includes('(min-width: 48rem)')` was matching the prose of the doc
comment above the constant rather than the constant itself, so moving the real
gate to 40rem stayed green. Assertions about source now strip comments first, and
the threshold is read out of the constant that `matchMedia` actually receives.

Manual browser checks, for what a script cannot assert:

```bash
npm run build && npx vite preview --port 4317
# 390px (device emulation, not window resize — Chrome floors real windows at 500px):
#   confirm zero requests matching KhoLuat|three|drei|fiber
# 1440px: confirm first WebGL draw < 2500ms, and that draw calls hit zero
#   when the hero scrolls away and when document.hidden
```

Note the prior art this overrides: `research-zoom-3d.md` §8 ruled Three.js out
of *every* screen, because its cost sits in a different weight class from the
"old phone, weak network" users KLAW serves as one of three primary groups. The
project owner chose to enable WebGL after that tradeoff was stated. The 768px
gate is what keeps that choice from becoming the defect the research predicted
— so if the gate is ever removed, the research's objection applies again in
full.

## SEO limitation (SPA)

This is a client-rendered single-page app: `index.html` ships an empty
`#root` and React renders everything after the JS bundle loads. A crawler
that doesn't execute JavaScript sees only the static `<head>` tags (title,
meta description, Open Graph, JSON-LD) — never the actual answer content,
since that's fetched and rendered at runtime per query.

That's an acceptable tradeoff for an authenticated-feel lookup tool where
individual query results aren't meant to be indexed pages anyway. If public,
indexable content pages are ever needed (e.g. a shareable permalink per
answer, or marketing/landing pages), that requires server rendering or
prerendering — neither is set up here. Options, not implemented:

- Static prerendering of specific known routes at build time (e.g.
  `vite-plugin-ssr`-style prerender, or a simple headless-browser snapshot
  step in CI) for content that doesn't change per request.
- A real SSR framework (Next.js/Remix-style) for the whole app — a much
  bigger change than this frontend's current architecture, and not
  something to reach for without a concrete need.

Do not build either speculatively; this note exists so the tradeoff is a
documented decision, not a surprise.

`public/sitemap.xml` lists all seven routes and `public/robots.txt` points to
it, so crawlers can at least discover every URL — but neither solves the
problem above. A sitemap only helps a crawler find a URL; it still needs to
execute JS to see anything past the empty `#root` once it's there. Both files
also use a placeholder `https://klaw.example.com` domain (no production
domain exists yet — Task 8 deploy is out of scope for this session); replace
it with the real domain at deploy time, same as the `url` field noted as
TODO in `index.html`'s JSON-LD.
