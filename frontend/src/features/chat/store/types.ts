import type { ChatMessage, ConnectionStatus, Conversation, Language, Message, ServerEnvelope, UUID } from '../../../types'

export interface HistoryState {
  loaded: boolean
  loading: boolean
  hasMore: boolean
  cursor: string | null
  error: string | null
}

export interface ChatState {
  me: UUID | null
  connection: ConnectionStatus
  languages: Language[]
  languagesLoaded: boolean
  conversations: Record<UUID, Conversation>
  conversationsLoaded: boolean
  conversationsError: string | null
  messages: Record<UUID, ChatMessage[]>
  history: Record<UUID, HistoryState>
  /** conversationId -> userId -> expiry (ms epoch) */
  typing: Record<UUID, Record<UUID, number>>
  online: Record<UUID, boolean>
  activeConversationId: UUID | null

  reset: (me: UUID | null) => void
  setConnection: (status: ConnectionStatus) => void
  setActive: (id: UUID | null) => void
  loadLanguages: () => Promise<void>
  loadConversations: () => Promise<void>
  upsertConversation: (c: Conversation) => void
  loadMessages: (conversationId: UUID, older?: boolean) => Promise<void>
  /** sourceLanguage null = auto-detect on the server; fallbackLanguage labels the optimistic copy. */
  sendMessage: (conversationId: UUID, text: string, sourceLanguage: string | null, fallbackLanguage?: string) => void
  resendMessage: (conversationId: UUID, clientMessageId: string) => void
  resendPending: () => void
  markRead: (conversationId: UUID) => void
  sendTyping: (conversationId: UUID, started: boolean) => void
  retryTranslation: (message: Message, targetLanguage?: string) => Promise<void>
  handleEvent: (event: ServerEnvelope) => void
  resync: () => Promise<void>
}
