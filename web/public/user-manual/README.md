# OptionsLab user manual (static HTML)

Files live under `web/public/user-manual/` and are served by Next.js at **`/user-manual/`** (e.g. `http://localhost:3000/user-manual/index.html` when `npm run dev` is running).

Internal links and images use **root-absolute** paths (`/user-manual/...`) so styles, scripts, PNGs, and chapter links work from the running app (relative `images/` and `docs.html` break when the URL omits a trailing segment or `index.html`).

This manual is aimed at **operators and developers running the stack** (clone, configure `.env`, API + web). The **Documentation** chapter consolidates the Markdown guides from the repository **`docs/`** folder.

## UI screenshots

PNG screenshots are in **`public/user-manual/images/`** and requested as **`/user-manual/images/*.png`**. The dev server uses **Webpack** (`npm run dev` runs `next dev --webpack`) because **Turbopack** can return 404 for some static files under `public/` while CSS/HTML/JS from the same folder still load. Regenerate after UI changes:

```bash
# From repo root: API on :8000, web on :3000
PYTHONPATH=. uvicorn api.main:app --host 127.0.0.1 --port 8000 &
cd web && npm run dev &
cd web && node scripts/capture-manual-ui.mjs
```

Requires the `playwright` devDependency in `web/` (`npm install` in `web/`). The capture script uses **`colorScheme: 'dark'`** so screenshots match the dark UI (headless Chrome defaults to light `prefers-color-scheme`).

| File | Contents |
|------|----------|
| `index.html` | Home + chapter cards |
| `getting-started.html` | Install, env, registration, demo data |
| `dashboard.html` | Dashboard pages |
| `concepts.html` | Theory and metrics |
| `workflows.html` | Guided workflows |
| `docs.html` | Full reference from repo `docs/` (data, auth, forecasting, strategy, research, risk, volatility, macro, frameworks, TSF architecture, AWS deployment) |
| `reference.html` | API tables + glossary |
| `images/*.png` | UI screenshots (`/user-manual/images/…`) |
