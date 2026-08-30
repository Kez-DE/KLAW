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
- `src/lib/api.ts` — typed fetch client for all four backend endpoints.
- `src/pages/*` — one file per screen; each is currently an empty placeholder
  for another agent/session to build out.
- `src/components/Nav.tsx` — the persistent "đổi khay phim" tab bar.

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
