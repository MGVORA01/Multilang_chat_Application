import { config } from '../../config'
import { TIMING, WS_CLOSE } from '../../constants'
import type { ClientEventMap, ClientEventType, ConnectionStatus, ServerEnvelope } from '../../types'

export interface ChatSocketOptions {
  /** Obtain a fresh single-use ticket (POST /auth/ws-ticket). Rejects if the session is gone. */
  getTicket: () => Promise<string>
  onEvent: (event: ServerEnvelope) => void
  onStatus: (status: ConnectionStatus) => void
  /** Called when the ticket cannot be obtained because the user is logged out. */
  onUnauthorized?: () => void
  url?: (ticket: string) => string
  WebSocketImpl?: typeof WebSocket
  heartbeatMs?: number
  baseBackoffMs?: number
  maxBackoffMs?: number
}

function defaultUrl(ticket: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${config.wsPath}?ticket=${encodeURIComponent(ticket)}`
}

export function newId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

/**
 * Typed, self-healing WebSocket client.
 * - Fetches a fresh ticket for every (re)connect; JWTs never go in the URL.
 * - Exponential backoff with jitter; reconnects immediately when the browser comes back online.
 * - Heartbeat: sends `ping`; if nothing is received for 2 intervals the socket is recycled.
 */
export class ChatSocket {
  private ws: WebSocket | null = null
  private stopped = true
  private attempt = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private lastMessageAt = 0
  private status: ConnectionStatus = 'idle'
  private readonly opts: Required<Omit<ChatSocketOptions, 'onUnauthorized'>> & Pick<ChatSocketOptions, 'onUnauthorized'>

  constructor(options: ChatSocketOptions) {
    this.opts = {
      url: defaultUrl,
      WebSocketImpl: globalThis.WebSocket,
      heartbeatMs: TIMING.heartbeatMs,
      baseBackoffMs: TIMING.reconnectBaseMs,
      maxBackoffMs: TIMING.reconnectMaxMs,
      ...options,
    }
  }

  get connectionStatus(): ConnectionStatus {
    return this.status
  }

  start(): void {
    if (!this.stopped) return
    this.stopped = false
    window.addEventListener('online', this.handleOnline)
    window.addEventListener('offline', this.handleOffline)
    void this.connect()
  }

  stop(): void {
    this.stopped = true
    window.removeEventListener('online', this.handleOnline)
    window.removeEventListener('offline', this.handleOffline)
    this.clearTimers()
    const ws = this.ws
    this.ws = null
    if (ws && ws.readyState <= 1) ws.close(1000, 'client stop')
    this.setStatus('idle')
  }

  /** Returns false when the socket is not open (caller keeps the message queued). */
  send<T extends ClientEventType>(type: T, payload: ClientEventMap[T], id: string = newId()): boolean {
    if (!this.ws || this.ws.readyState !== 1) return false
    this.ws.send(JSON.stringify({ type, id, payload }))
    return true
  }

  private async connect(): Promise<void> {
    if (this.stopped) return
    this.setStatus(this.attempt === 0 ? 'connecting' : 'reconnecting')
    let ticket: string
    try {
      ticket = await this.opts.getTicket()
    } catch (err) {
      if (this.stopped) return
      const status = (err as { response?: { status?: number } }).response?.status
      if (status === 401) {
        this.setStatus('unauthorized')
        this.opts.onUnauthorized?.()
        return
      }
      this.scheduleReconnect()
      return
    }
    if (this.stopped) return

    const ws = new this.opts.WebSocketImpl(this.opts.url(ticket))
    this.ws = ws
    ws.onopen = () => {
      if (this.ws !== ws) return
      this.attempt = 0
      this.lastMessageAt = Date.now()
      this.setStatus('open')
      this.startHeartbeat()
    }
    ws.onmessage = (msg: MessageEvent<string>) => {
      if (this.ws !== ws) return
      this.lastMessageAt = Date.now()
      let event: ServerEnvelope
      try {
        event = JSON.parse(msg.data) as ServerEnvelope
      } catch {
        return
      }
      this.opts.onEvent(event)
    }
    ws.onclose = (ev: CloseEvent) => {
      if (this.ws !== ws) return
      this.ws = null
      this.clearTimers()
      if (this.stopped) return
      // 4401: ticket rejected. A new ticket is fetched on reconnect (refreshing the session if needed).
      if (ev.code === WS_CLOSE.unauthorized) this.attempt = Math.max(this.attempt, 1)
      this.scheduleReconnect()
    }
    ws.onerror = () => {
      // onclose follows; nothing to do here.
    }
  }

  private scheduleReconnect(): void {
    if (this.stopped) return
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      this.setStatus('offline')
      return // handleOnline will reconnect
    }
    this.setStatus('reconnecting')
    const exp = Math.min(this.opts.maxBackoffMs, this.opts.baseBackoffMs * 2 ** this.attempt)
    const delay = exp / 2 + Math.random() * (exp / 2)
    this.attempt += 1
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      void this.connect()
    }, delay)
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (!this.ws) return
      if (Date.now() - this.lastMessageAt > this.opts.heartbeatMs * 2) {
        // Half-open connection: recycle it.
        this.ws.close(WS_CLOSE.heartbeatTimeout, 'heartbeat timeout')
        return
      }
      this.send('ping', {})
    }, this.opts.heartbeatMs)
  }

  private clearTimers(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer)
    this.reconnectTimer = null
    this.heartbeatTimer = null
  }

  private setStatus(status: ConnectionStatus): void {
    if (status === this.status) return
    this.status = status
    this.opts.onStatus(status)
  }

  private readonly handleOnline = (): void => {
    if (this.stopped || this.ws) return
    this.clearTimers()
    this.attempt = 0
    void this.connect()
  }

  private readonly handleOffline = (): void => {
    if (this.stopped) return
    this.setStatus('offline')
    this.ws?.close(WS_CLOSE.heartbeatTimeout, 'browser offline')
  }
}
