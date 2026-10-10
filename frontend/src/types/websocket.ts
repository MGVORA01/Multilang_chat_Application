import type { ISODateString, Message, MessageTranslation, User, UUID } from './domain'

/** WebSocket protocol: client/server envelopes and per-event payloads (docs/websocket-protocol.md). */

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'offline' | 'unauthorized'

export interface WebSocketError {
  code: string
  message: string
  details?: unknown
}

export interface ClientEventMap {
  'message.send': {
    conversation_id: UUID
    text: string
    client_message_id: string
    source_language?: string
  }
  'message.read': { conversation_id: UUID; message_id: UUID }
  'typing.start': { conversation_id: UUID }
  'typing.stop': { conversation_id: UUID }
  ping: Record<string, never>
}

export interface ServerEventMap {
  'session.ready': { user_id: UUID; online_user_ids: UUID[]; heartbeat_seconds: number }
  'message.created': { message: Message; duplicate: boolean }
  'message.translated': MessageTranslation & { conversation_id: UUID }
  'message.delivered': { conversation_id: UUID; message_ids: UUID[]; user_id: UUID; delivered_at: ISODateString }
  'message.read': {
    conversation_id: UUID
    user_id: UUID
    message_ids: UUID[]
    up_to_message_id: UUID
    read_at: ISODateString
  }
  'typing.started': { conversation_id: UUID; user_id: UUID }
  'typing.stopped': { conversation_id: UUID; user_id: UUID }
  'presence.updated': { user_id: UUID; online: boolean; last_seen_at: ISODateString }
  'user.updated': { user: User }
  'conversation.removed': { conversation_id: UUID; reason: 'account_deleted' }
  error: WebSocketError
  pong: Record<string, never>
}

export type ClientEventType = keyof ClientEventMap
export type ServerEventType = keyof ServerEventMap

export interface ClientEnvelope<T extends ClientEventType = ClientEventType> {
  type: T
  id: string
  payload: ClientEventMap[T]
}

export type ServerEnvelope = {
  [K in ServerEventType]: {
    type: K
    id: string
    correlation_id: string | null
    payload: ServerEventMap[K]
    ts: ISODateString
  }
}[ServerEventType]

export type WebSocketEvent = ServerEnvelope
