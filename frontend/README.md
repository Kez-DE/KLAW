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
