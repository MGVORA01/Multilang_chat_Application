/** Application-wide constants shared by several features. Feature-local values stay in their feature. */

/** Must match backend MAX_MESSAGE_LENGTH. */
export const MAX_MESSAGE_LENGTH = 2000

export const DEFAULT_LANGUAGE = 'eng_Latn'

export const TIMING = {
  /** Remote typing indicator disappears after this long without a refresh. */
  typingIndicatorTtlMs: 6_000,
  /** Throttle for our own `typing.start` events. */
  typingThrottleMs: 3_000,
  /** Send `typing.stop` after this long without keystrokes. */
  typingIdleMs: 4_000,
  /** Mark an unacknowledged send as failed after this long. */
  sendAckTimeoutMs: 15_000,
  /** WebSocket ping interval; the server idle-timeout is 60 s. */
  heartbeatMs: 25_000,
  reconnectBaseMs: 1_000,
  reconnectMaxMs: 30_000,
  /** Wait for a pause in typing before requesting a translation preview. */
  previewDebounceMs: 700,
} as const

export const PREVIEW_MAX_CHARS = 600
export const HISTORY_PAGE_SIZE = 30

/** WebSocket close codes sent by the backend (see docs/websocket-protocol.md). */
export const WS_CLOSE = {
  unauthorized: 4401,
  originNotAllowed: 4403,
  idleTimeout: 4408,
  accountDeleted: 4410,
  heartbeatTimeout: 4000,
} as const

export const STORAGE_KEYS = {
  translationPreview: 'composer.preview',
} as const
