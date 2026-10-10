import { beforeEach, describe, expect, it, vi } from 'vitest'
import { alice, conversation, message, translation } from '../../../test/fixtures'
import type { ServerEnvelope } from '../../../types'
import { bindSocket, useChatStore } from './chatStore'

vi.mock('../../conversations/api', () => ({
  conversationsApi: { list: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 }), get: vi.fn() },
}))
vi.mock('../api', () => ({
  messagesApi: { history: vi.fn().mockResolvedValue({ items: [], next_cursor: null, has_more: false }), retryTranslation: vi.fn() },
}))
vi.mock('../../translation/api', () => ({ translationApi: { languages: vi.fn().mockResolvedValue([]) } }))

function event<T extends ServerEnvelope['type']>(
  type: T,
  payload: Extract<ServerEnvelope, { type: T }>['payload'],
  correlation_id: string | null = null,
): ServerEnvelope {
  return { type, payload, correlation_id, id: 'e', ts: '' } as ServerEnvelope
}

const send = vi.fn()

beforeEach(() => {
  send.mockReset().mockReturnValue(true)
  bindSocket({ send } as never)
  useChatStore.getState().reset(alice.id)
  useChatStore.getState().upsertConversation(conversation({ last_message: null }))
})

describe('chatStore', () => {
  it('adds an optimistic message and replaces it with the server copy', () => {
    const store = useChatStore.getState()
    store.sendMessage('c1', 'hello', 'guj_Gujr')
    const [type, payload, correlationId] = send.mock.calls[0]!
    expect(type).toBe('message.send')
    expect(payload).toMatchObject({ conversation_id: 'c1', text: 'hello', source_language: 'guj_Gujr' })

    let list = useChatStore.getState().messages.c1!
    expect(list).toHaveLength(1)
    expect(list[0]!.localState).toBe('sending')

    const serverCopy = message({
      id: 'm-server',
      original_text: 'hello',
      client_message_id: payload.client_message_id,
      translations: [translation({ message_id: 'm-server', status: 'pending', translated_text: null })],
    })
    store.handleEvent(event('message.created', { message: serverCopy, duplicate: false }, correlationId))
    list = useChatStore.getState().messages.c1!
    expect(list).toHaveLength(1)
    expect(list[0]!.id).toBe('m-server')
    expect(list[0]!.localState).toBeUndefined()

    store.handleEvent(
      event('message.translated', { ...translation({ message_id: 'm-server' }), conversation_id: 'c1' }),
    )
    expect(useChatStore.getState().messages.c1![0]!.translations[0]!.status).toBe('completed')
  })

  it('marks a message failed on an error event and resends it with the same client id', () => {
    const store = useChatStore.getState()
    store.sendMessage('c1', 'oops', 'guj_Gujr')
    const [, payload, correlationId] = send.mock.calls[0]!
    store.handleEvent(event('error', { code: 'rate_limited', message: 'slow down' }, correlationId))
    expect(useChatStore.getState().messages.c1![0]!.localState).toBe('failed')

    store.resendMessage('c1', payload.client_message_id)
    expect(send).toHaveBeenCalledTimes(2)
    expect(send.mock.calls[1]![1].client_message_id).toBe(payload.client_message_id)
    expect(useChatStore.getState().messages.c1![0]!.localState).toBe('sending')
  })

  it('queues messages while disconnected and flushes them after reconnect', () => {
    send.mockReturnValue(false)
    const store = useChatStore.getState()
    store.sendMessage('c1', 'later', 'guj_Gujr')
    expect(useChatStore.getState().messages.c1![0]!.localState).toBe('sending')
    send.mockReturnValue(true)
    store.resendPending()
    expect(send).toHaveBeenLastCalledWith('message.send', expect.objectContaining({ text: 'later' }), expect.any(String))
  })

  it('counts unread incoming messages for inactive conversations', () => {
    const store = useChatStore.getState()
    store.handleEvent(
      event('message.created', { message: message({ id: 'm9', sender_id: 'u-bob' }), duplicate: false }),
    )
    const conv = useChatStore.getState().conversations.c1!
    expect(conv.unread_count).toBe(1)
    expect(conv.last_message?.id).toBe('m9')
  })

  it('upgrades delivery status but never downgrades it', () => {
    const store = useChatStore.getState()
    store.handleEvent(event('message.created', { message: message({ status: 'sent' }), duplicate: false }))
    store.handleEvent(
      event('message.read', {
        conversation_id: 'c1',
        user_id: 'u-bob',
        message_ids: ['m1'],
        up_to_message_id: 'm1',
        read_at: '',
      }),
    )
    store.handleEvent(
      event('message.delivered', { conversation_id: 'c1', user_id: 'u-bob', message_ids: ['m1'], delivered_at: '' }),
    )
    expect(useChatStore.getState().messages.c1![0]!.status).toBe('read')
  })

  it('tracks presence and typing', () => {
    const store = useChatStore.getState()
    store.handleEvent(event('presence.updated', { user_id: 'u-bob', online: false, last_seen_at: '2026-10-10T10:00:00Z' }))
    expect(useChatStore.getState().online['u-bob']).toBe(false)
    store.handleEvent(event('typing.started', { conversation_id: 'c1', user_id: 'u-bob' }))
    expect(useChatStore.getState().typing.c1!['u-bob']).toBeGreaterThan(Date.now())
    store.handleEvent(event('typing.stopped', { conversation_id: 'c1', user_id: 'u-bob' }))
    expect(useChatStore.getState().typing.c1!['u-bob']).toBeUndefined()
  })

  it('sends a read receipt for the latest incoming message of the active conversation', () => {
    const store = useChatStore.getState()
    store.handleEvent(
      event('message.created', { message: message({ id: 'm5', sender_id: 'u-bob' }), duplicate: false }),
    )
    store.setActive('c1')
    expect(send).toHaveBeenCalledWith('message.read', { conversation_id: 'c1', message_id: 'm5' })
  })
})

describe('source language', () => {
  it('omits source_language for auto-detect and labels the optimistic copy by script', () => {
    useChatStore.getState().sendMessage('c1', 'Hello this is meet.', null, 'hin_Deva')
    const [, payload] = send.mock.calls[0]!
    expect(payload).not.toHaveProperty('source_language')
    expect(useChatStore.getState().messages.c1![0]!.source_language).toBe('eng_Latn')
  })
})

describe('conversation.removed', () => {
  it('drops the conversation and its messages', () => {
    const store = useChatStore.getState()
    store.handleEvent(event('message.created', { message: message({ sender_id: 'u-bob' }), duplicate: false }))
    expect(useChatStore.getState().messages.c1).toHaveLength(1)
    store.handleEvent(event('conversation.removed', { conversation_id: 'c1', reason: 'account_deleted' }))
    expect(useChatStore.getState().conversations.c1).toBeUndefined()
    expect(useChatStore.getState().messages.c1).toBeUndefined()
  })
})
