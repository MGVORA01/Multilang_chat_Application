/** Chat state: conversations, messages, presence and typing. Event handling lives in serverEvents.ts. */
import { create } from 'zustand'
import { DEFAULT_LANGUAGE } from '../../../constants'
import { newId } from '../../../services/websocket'
import type { ChatMessage, Conversation, UUID } from '../../../types'
import { conversationsApi } from '../../conversations/api'
import { translationApi } from '../../translation/api'
import { DEFAULT_LANGUAGES, guessLanguage } from '../../translation/languages'
import { messagesApi } from '../api'
import { mergeMessage } from './messageMerge'
import { Outbox, type SocketLike } from './outbox'
import { applyServerEvent, applyTranslation } from './serverEvents'
import type { ChatState, HistoryState } from './types'

const LANGUAGE_LOAD_ATTEMPTS = 5

const outbox = new Outbox((conversationId, clientMessageId) =>
  useChatStore.setState((s) => ({
    messages: {
      ...s.messages,
      [conversationId]: (s.messages[conversationId] ?? []).map((m) =>
        m.client_message_id === clientMessageId && m.localState === 'sending' ? { ...m, localState: 'failed' } : m,
      ),
    },
  })),
)
/** Last message id we sent a read receipt for, per conversation (avoids duplicate receipts). */
const readSent = new Map<UUID, UUID>()

/** Connect the store to a live socket (null on logout). */
export function bindSocket(socket: SocketLike | null): void {
  outbox.bind(socket)
}

const EMPTY_HISTORY: HistoryState = { loaded: false, loading: false, hasMore: false, cursor: null, error: null }

export const useChatStore = create<ChatState>()((set, get) => ({
  me: null,
  connection: 'idle',
  languages: DEFAULT_LANGUAGES,
  languagesLoaded: false,
  conversations: {},
  conversationsLoaded: false,
  conversationsError: null,
  messages: {},
  history: {},
  typing: {},
  online: {},
  activeConversationId: null,

  reset: (me) => {
    outbox.reset()
    readSent.clear()
    set({
      me,
      conversations: {},
      conversationsLoaded: false,
      conversationsError: null,
      messages: {},
      history: {},
      typing: {},
      online: {},
      activeConversationId: null,
    })
  },

  setConnection: (connection) => set({ connection }),

  setActive: (id) => {
    set({ activeConversationId: id })
    if (id) get().markRead(id)
  },

  loadLanguages: async () => {
    if (get().languagesLoaded) return
    for (let attempt = 0; attempt < LANGUAGE_LOAD_ATTEMPTS; attempt++) {
      try {
        const languages = await translationApi.languages()
        if (languages.length) set({ languages, languagesLoaded: true })
        return
      } catch {
        // Backend may still be starting; the built-in list stays in place meanwhile.
        await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)))
      }
    }
  },

  loadConversations: async () => {
    try {
      const page = await conversationsApi.list()
      const conversations: Record<UUID, Conversation> = {}
      const online = { ...get().online }
      for (const c of page.items) {
        conversations[c.id] = c
        for (const m of c.members) online[m.id] = m.is_online
      }
      set({ conversations, conversationsLoaded: true, conversationsError: null, online })
    } catch {
      set({ conversationsLoaded: true, conversationsError: 'Could not load conversations' })
    }
  },

  upsertConversation: (c) => {
    set((s) => ({
      conversations: { ...s.conversations, [c.id]: c },
      online: { ...s.online, ...Object.fromEntries(c.members.map((m) => [m.id, m.is_online])) },
    }))
  },

  loadMessages: async (conversationId, older = false) => {
    const h = get().history[conversationId]
    if (h?.loading || (older && !h?.hasMore)) return
    const setHistory = (patch: Partial<HistoryState>): void =>
      set((s) => ({
        history: { ...s.history, [conversationId]: { ...EMPTY_HISTORY, ...s.history[conversationId], ...patch } },
      }))
    setHistory({ loading: true, error: null })
    try {
      const page = await messagesApi.history(conversationId, older ? h?.cursor : null)
      set((s) => {
        let list = s.messages[conversationId] ?? []
        for (const m of page.items) list = mergeMessage(list, m)
        return { messages: { ...s.messages, [conversationId]: list } }
      })
      const patch: Partial<HistoryState> = { loading: false, loaded: true }
      // Only move the cursor when paging backwards or on the first load.
      if (older || !h?.loaded) Object.assign(patch, { cursor: page.next_cursor, hasMore: page.has_more })
      setHistory(patch)
      get().markRead(conversationId)
    } catch {
      setHistory({ loading: false, error: 'Could not load messages' })
    }
  },

  sendMessage: (conversationId, text, sourceLanguage, fallbackLanguage = DEFAULT_LANGUAGE) => {
    const me = get().me
    if (!me) return
    const clientMessageId = newId()
    const optimistic: ChatMessage = {
      id: `local:${clientMessageId}`,
      conversation_id: conversationId,
      sender_id: me,
      client_message_id: clientMessageId,
      original_text: text,
      source_language: sourceLanguage ?? guessLanguage(text, fallbackLanguage),
      requestedSourceLanguage: sourceLanguage,
      created_at: new Date().toISOString(),
      translations: [],
      status: 'sent',
      localState: 'sending',
    }
    set((s) => ({ messages: { ...s.messages, [conversationId]: mergeMessage(s.messages[conversationId], optimistic) } }))
    outbox.transmit(conversationId, optimistic)
  },

  resendMessage: (conversationId, clientMessageId) => {
    const msg = get().messages[conversationId]?.find((m) => m.client_message_id === clientMessageId)
    if (!msg) return
    set((s) => ({
      messages: {
        ...s.messages,
        [conversationId]: mergeMessage(s.messages[conversationId], { ...msg, localState: 'sending' }),
      },
    }))
    outbox.transmit(conversationId, msg)
  },

  resendPending: () => {
    for (const [cid, list] of Object.entries(get().messages)) {
      for (const m of list) if (m.localState === 'sending') outbox.transmit(cid, m)
    }
  },

  markRead: (conversationId) => {
    const { me, messages, activeConversationId } = get()
    if (activeConversationId !== conversationId || typeof document === 'undefined') return
    if (document.visibilityState === 'hidden') return
    const lastIncoming = [...(messages[conversationId] ?? [])].reverse().find((m) => m.sender_id !== me && !m.localState)
    if (!lastIncoming || lastIncoming.status === 'read' || readSent.get(conversationId) === lastIncoming.id) return
    if (outbox.send('message.read', { conversation_id: conversationId, message_id: lastIncoming.id })) {
      readSent.set(conversationId, lastIncoming.id)
    }
  },

  sendTyping: (conversationId, started) => {
    outbox.send(started ? 'typing.start' : 'typing.stop', { conversation_id: conversationId })
  },

  retryTranslation: async (message, targetLanguage) => {
    const tr = await messagesApi.retryTranslation(message.id, targetLanguage)
    applyTranslation(set, message.conversation_id, tr)
  },

  handleEvent: (event) => applyServerEvent({ set, get, outbox }, event),

  resync: async () => {
    // After (re)connecting: catch up on anything missed while disconnected, then flush the outbox.
    await get().loadConversations()
    const active = get().activeConversationId
    if (active && get().history[active]?.loaded) await get().loadMessages(active)
    get().resendPending()
  },
}))

/** Conversations newest-activity first. */
export function sortedConversations(conversations: Record<UUID, Conversation>): Conversation[] {
  return Object.values(conversations).sort((a, b) =>
    (b.last_message_at ?? b.created_at).localeCompare(a.last_message_at ?? a.created_at),
  )
}
