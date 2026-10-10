# Frontend — Bhasha Chat

React 19 + TypeScript (strict) + Vite + Tailwind CSS. Structure, data flows and conventions are in
[`../docs/architecture.md`](../docs/architecture.md); full setup in [`../docs/setup.md`](../docs/setup.md).

```bash
npm install
cp .env.example .env      # optional: VITE_BACKEND_URL (default http://localhost:8000)
npm run dev               # http://localhost:5173 (proxies /api and /ws to the backend)

npm test                  # Vitest
npm run typecheck && npm run lint && npm run build
```
