# Options Lab – Web UI

Next.js (App Router) + Tailwind for the **Options Lab** dashboard: overview stats, backtest list and detail (charts, trades), create backtest, settings (defaults for new backtests), and data & symbols view. See the [project README](../README.md) for full setup.

## Run

```bash
npm install && npm run dev
```

Open [http://localhost:3000](http://localhost:3000); the app redirects to the dashboard. The Python API must be running on port 8000. The UI uses the same host as the page for the API (e.g. `http://192.168.1.16:3000` → API at `http://192.168.1.16:8000`). Override with `NEXT_PUBLIC_API_URL` in `.env.local` if needed.

`npm run dev` uses **Webpack** (`next dev --webpack`) so PNGs under `public/user-manual/images/` load correctly; the default Turbopack dev server can 404 those URLs while still serving the manual’s HTML/CSS.

## Config

- **`next.config.ts`**: `allowedDevOrigins` – for cross-origin dev requests when opening the app from another device.
- **`.env.local`** (optional): `NEXT_PUBLIC_API_URL=http://localhost:8000`

## Checks

`npm run lint` and `npm run build`.
