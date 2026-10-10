import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ConnectionStatus, ServerEnvelope } from '../../types'
import { ChatSocket } from './ChatSocket'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  readyState = 0
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: ((e: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close(code = 1000) {
    this.readyState = 3
    this.onclose?.({ code })
  }
  // test helpers
  open() {
    this.readyState = 1
    this.onopen?.()
  }
  emit(event: Partial<ServerEnvelope>) {
    this.onmessage?.({ data: JSON.stringify(event) })
  }
  drop(code = 1006) {
    this.readyState = 3
    this.onclose?.({ code })
  }
}

const flush = () => vi.advanceTimersByTimeAsync(0)

function setup(getTicket = vi.fn().mockResolvedValue('ticket-1')) {
  const statuses: ConnectionStatus[] = []
  const events: ServerEnvelope[] = []
  const onUnauthorized = vi.fn()
  const socket = new ChatSocket({
    getTicket,
    onEvent: (e) => events.push(e),
    onStatus: (s) => statuses.push(s),
    onUnauthorized,
    url: (t) => `ws://test/ws/chat?ticket=${t}`,
    WebSocketImpl: FakeWebSocket as unknown as typeof WebSocket,
    heartbeatMs: 1000,
    baseBackoffMs: 100,
    maxBackoffMs: 1000,
  })
  return { socket, statuses, events, getTicket, onUnauthorized }
}

describe('ChatSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
  })
  afterEach(() => vi.useRealTimers())

  it('connects with a fresh ticket and reports status', async () => {
    const { socket, statuses } = setup()
    socket.start()
    await flush()
    const ws = FakeWebSocket.instances[0]!
    expect(ws.url).toBe('ws://test/ws/chat?ticket=ticket-1')
    ws.open()
    expect(statuses).toEqual(['connecting', 'open'])
    socket.stop()
  })

  it('dispatches parsed server events and sends typed envelopes', async () => {
    const { socket, events } = setup()
    socket.start()
    await flush()
    const ws = FakeWebSocket.instances[0]!
    ws.open()
    ws.emit({ type: 'pong', id: '1', correlation_id: 'abc', payload: {}, ts: '' })
    expect(events[0]?.type).toBe('pong')
    expect(socket.send('typing.start', { conversation_id: 'c1' }, 'cid-1')).toBe(true)
    expect(JSON.parse(ws.sent[0]!)).toEqual({ type: 'typing.start', id: 'cid-1', payload: { conversation_id: 'c1' } })
    socket.stop()
  })

  it('returns false from send while disconnected', () => {
    const { socket } = setup()
    expect(socket.send('ping', {})).toBe(false)
  })

  it('reconnects with backoff and a new ticket after an unexpected close', async () => {
    const getTicket = vi.fn().mockResolvedValueOnce('t1').mockResolvedValueOnce('t2')
    const { socket, statuses } = setup(getTicket)
    socket.start()
    await flush()
    FakeWebSocket.instances[0]!.open()
    FakeWebSocket.instances[0]!.drop()
    expect(statuses.at(-1)).toBe('reconnecting')
    await vi.advanceTimersByTimeAsync(200)
    expect(getTicket).toHaveBeenCalledTimes(2)
    const ws2 = FakeWebSocket.instances[1]!
    expect(ws2.url).toContain('ticket=t2')
    ws2.open()
    expect(statuses.at(-1)).toBe('open')
    socket.stop()
  })

  it('does not reconnect after stop()', async () => {
    const { socket } = setup()
    socket.start()
    await flush()
    FakeWebSocket.instances[0]!.open()
    socket.stop()
    await vi.advanceTimersByTimeAsync(5000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('recycles a half-open connection when heartbeats stop', async () => {
    const { socket } = setup()
    socket.start()
    await flush()
    const ws = FakeWebSocket.instances[0]!
    ws.open()
    await vi.advanceTimersByTimeAsync(1000)
    expect(ws.sent.some((s) => JSON.parse(s).type === 'ping')).toBe(true)
    await vi.advanceTimersByTimeAsync(2500) // no messages received
    expect(ws.readyState).toBe(3)
    await vi.advanceTimersByTimeAsync(500)
    expect(FakeWebSocket.instances.length).toBeGreaterThan(1)
    socket.stop()
  })

  it('stops and reports unauthorized when the ticket request is rejected with 401', async () => {
    const getTicket = vi.fn().mockRejectedValue({ response: { status: 401 } })
    const { socket, statuses, onUnauthorized } = setup(getTicket)
    socket.start()
    await flush()
    expect(statuses.at(-1)).toBe('unauthorized')
    expect(onUnauthorized).toHaveBeenCalled()
    expect(FakeWebSocket.instances).toHaveLength(0)
  })
})
