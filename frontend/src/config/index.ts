/**
 * Environment-driven configuration. Vite exposes only VITE_* variables to the browser;
 * never put secrets here.
 */
export const config = {
  /** REST base path. Same-origin by default (the Vite dev server / nginx proxies it). */
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  /** WebSocket path on the current host. */
  wsPath: import.meta.env.VITE_WS_PATH ?? '/ws/chat',
  /** REST request timeout. */
  apiTimeoutMs: 20_000,
} as const
