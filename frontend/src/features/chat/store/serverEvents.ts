/** Applies server WebSocket events to the chat store (one handler per event type). */
import type { StoreApi } from 'zustand'
import { TIMING } from '../../../constants'
import type { ChatMessage, Message, MessageTranslation, ServerEnvelope, ServerEventMap, UUID } from '../../../types'
import { conversationsApi } from '../../conversations/api'
import { mergeMessage, upsertTranslation, withStatus } from './messageMerge'
import type { Outbox } from './outbox'
import type { ChatState } from './types'

type SetState = StoreApi<ChatState>['setState']
type GetState = StoreApi<ChatState>['getState']

interface Ctx {
  set: SetState
  get: GetState
  outbox: Outbox
}

/** Merge a translation update into its message (and the conversation preview if it is the last message). */
export function applyTranslation(set: SetState, conversationId: UUID, tr: MessageTranslation): void {
  set((s) => {
    const list = s.messages[conversationId]
    const conv = s.conversations[conversationId]
    const patch = <M extends Message>(m: M): M =>
      m.id === tr.message_id ? { ...m, translations: upsertTranslation(m.translations, tr) } : m
    return {
      messages: list ? { ...s.messages, [conversationId]: list.map(patch) } : s.messages,
      conversations:
        conv?.last_message?.id === tr.message_id
          ? { ...s.conversations, [conversationId]: { ...conv, last_message: patch(conv.last_message) } }
          : s.conversations,
    }
  })
}

/** Rewrite one member across every conversation that contains them. */
function patchMember(ctx: Ctx, userId: UUID, patch: (m: ChatState['conversations'][string]['members'][number]) => typeof m) {
  ctx.set((s) => {
    const conversations = { ...s.conversations }
    for (const [id, c] of Object.entries(conversations)) {
      if (c.members.some((m) => m.id === userId)) {
        conversations[id] = { ...c, members: c.members.map((m) => (m.id === userId ? patch(m) : m)) }
      }
    }
    return { conversations }
  })
}

function onSessionReady(ctx: Ctx, payload: ServerEventMap['session.ready']): void {
  const online: Record<UUID, boolean> = {}
  for (const c of Object.values(ctx.get().conversations)) for (const m of c.members) online[m.id] = false
  for (const id of payload.online_user_ids) online[id] = true
  ctx.set({ online })
  void ctx.get().resync()
}

function onMessageCreated(ctx: Ctx, payload: ServerEventMap['message.created'], correlationId: string | null): void {
  const { message, duplicate } = payload
  if (correlationId) ctx.outbox.acknowledge(correlationId)
  const cid = message.conversation_id
  const me = ctx.get().me
  ctx.set((s) => {
    const conv = s.conversations[cid]
    const typing = { ...s.typing, [cid]: { ...s.typing[cid] } }
    delete typing[cid]![message.sender_id]
    const incoming = message.sender_id !== me
    const isActive = s.activeConversationId === cid && document.visibilityState !== 'hidden'
    const serverCopy: ChatMessage = { ...message, localState: undefined }
    return {
      messages: { ...s.messages, [cid]: mergeMessage(s.messages[cid], serverCopy) },
      typing,
      conversations: conv
        ? {
            ...s.conversations,
            [cid]: {
              ...conv,
              last_message: message,
              last_message_at: message.created_at,
              unread_count: incoming && !isActive && !duplicate ? conv.unread_count + 1 : conv.unread_count,
            },
          }
        : s.conversations,
    }
  })
  if (!ctx.get().conversations[cid]) {
    // First message of a conversation someone else started.
    void conversationsApi
      .get(cid)
      .then((c) => ctx.get().upsertConversation(c))
      .catch(() => undefined)
  }
  ctx.get().markRead(cid)
}

function onReceipt(
  ctx: Ctx,
  payload: ServerEventMap['message.delivered'] | ServerEventMap['message.read'],
  target: 'delivered' | 'read',
): void {
  const { conversation_id: cid, message_ids, user_id } = payload
  const ids = new Set(message_ids)
  const me = ctx.get().me
  ctx.set((s) => {
    const list = s.messages[cid]
    const conv = s.conversations[cid]
    return {
      messages: list ? { ...s.messages, [cid]: list.map((m) => withStatus(m, ids, target)) } : s.messages,
      conversations: conv
        ? {
            ...s.conversations,
            [cid]: {
              ...conv,
              last_message: conv.last_message ? withStatus(conv.last_message, ids, target) : null,
              unread_count: target === 'read' && user_id === me ? 0 : conv.unread_count,
            },
          }
        : s.conversations,
    }
  })
}

function onTyping(ctx: Ctx, payload: ServerEventMap['typing.started'], started: boolean): void {
  const { conversation_id: cid, user_id } = payload
  ctx.set((s) => {
    const entry = { ...s.typing[cid] }
    if (started) entry[user_id] = Date.now() + TIMING.typingIndicatorTtlMs
    else delete entry[user_id]
    return { typing: { ...s.typing, [cid]: entry } }
  })
}

function onConversationRemoved(ctx: Ctx, conversationId: UUID): void {
  ctx.set((s) => {
    const conversations = { ...s.conversations }
    const messages = { ...s.messages }
    const history = { ...s.history }
    delete conversations[conversationId]
    delete messages[conversationId]
    delete history[conversationId]
    return { conversations, messages, history }
  })
}

export function applyServerEvent(ctx: Ctx, event: ServerEnvelope): void {
  switch (event.type) {
    case 'session.ready':
      return onSessionReady(ctx, event.payload)
    case 'message.created':
      return onMessageCreated(ctx, event.payload, event.correlation_id)
    case 'message.translated':
      return applyTranslation(ctx.set, event.payload.conversation_id, event.payload)
    case 'message.delivered':
      return onReceipt(ctx, event.payload, 'delivered')
    case 'message.read':
      return onReceipt(ctx, event.payload, 'read')
    case 'typing.started':
      return onTyping(ctx, event.payload, true)
    case 'typing.stopped':
      return onTyping(ctx, event.payload, false)
    case 'presence.updated': {
      const { user_id, online, last_seen_at } = event.payload
      patchMember(ctx, user_id, (m) => ({ ...m, is_online: online, last_seen_at }))
      ctx.set((s) => ({ online: { ...s.online, [user_id]: online } }))
      return
    }
    case 'user.updated': {
      const { user } = event.payload
      patchMember(ctx, user.id, () => user)
      ctx.set((s) => ({ online: { ...s.online, [user.id]: user.is_online } }))
      return
    }
    case 'conversation.removed':
      return onConversationRemoved(ctx, event.payload.conversation_id)
    case 'error':
      if (event.correlation_id) ctx.outbox.reject(event.correlation_id)
      return
    case 'pong':
      return
  }
}
