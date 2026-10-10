/** Outgoing-message delivery over the socket: tracks unacknowledged sends and their timeouts. */
import { TIMING } from '../../../constants'
import { newId, type ChatSocket } from '../../../services/websocket'
import type { ChatMessage, ClientEventMap, ClientEventType, UUID } from '../../../types'

/** Minimal socket surface the store needs (lets tests inject a fake). */
export type SocketLike = Pick<ChatSocket, 'send'>

interface Pending {
  conversationId: UUID
  clientMessageId: string
  timer: ReturnType<typeof setTimeout>
}

export class Outbox {
  private socket: SocketLike | null = null
  private readonly pending = new Map<string, Pending>()
  private readonly onFailed: (conversationId: UUID, clientMessageId: string) => void

  constructor(onFailed: (conversationId: UUID, clientMessageId: string) => void) {
    this.onFailed = onFailed
  }

  bind(socket: SocketLike | null): void {
    this.socket = socket
  }

  /** Fire-and-forget events (read receipts, typing). Returns false while disconnected. */
  send<T extends ClientEventType>(type: T, payload: ClientEventMap[T]): boolean {
    return this.socket?.send(type, payload) ?? false
  }

  /** Send a chat message. If the socket is down it stays "sending" and is flushed on reconnect. */
  transmit(conversationId: UUID, msg: ChatMessage): void {
    if (!this.socket || !msg.client_message_id) return
    const correlationId = newId()
    const sent = this.socket.send(
      'message.send',
      {
        conversation_id: conversationId,
        text: msg.original_text,
        client_message_id: msg.client_message_id,
        ...(msg.requestedSourceLanguage ? { source_language: msg.requestedSourceLanguage } : {}),
      },
      correlationId,
    )
    if (!sent) return
    const clientMessageId = msg.client_message_id
    const timer = setTimeout(() => {
      this.pending.delete(correlationId)
      this.onFailed(conversationId, clientMessageId)
    }, TIMING.sendAckTimeoutMs)
    this.pending.set(correlationId, { conversationId, clientMessageId, timer })
  }

  /** Server acknowledged the send (`message.created` with our correlation id). */
  acknowledge(correlationId: string): void {
    const entry = this.pending.get(correlationId)
    if (entry) clearTimeout(entry.timer)
    this.pending.delete(correlationId)
  }

  /** Server rejected the send (`error` with our correlation id): mark it failed. */
  reject(correlationId: string): void {
    const entry = this.pending.get(correlationId)
    if (!entry) return
    clearTimeout(entry.timer)
    this.pending.delete(correlationId)
    this.onFailed(entry.conversationId, entry.clientMessageId)
  }

  reset(): void {
    this.pending.forEach((p) => clearTimeout(p.timer))
    this.pending.clear()
  }
}
