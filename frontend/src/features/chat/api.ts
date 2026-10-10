import { HISTORY_PAGE_SIZE } from '../../constants'
import { api } from '../../services/api/client'
import type { CursorPage, Message, MessageTranslation } from '../../types'

export const messagesApi = {
  /** Oldest-first page of messages older than `before` (null = latest page). */
  history: (conversationId: string, before?: string | null, limit = HISTORY_PAGE_SIZE) =>
    api
      .get<CursorPage<Message>>(`/conversations/${conversationId}/messages`, {
        params: { limit, before: before ?? undefined },
      })
      .then((r) => r.data),
  retryTranslation: (messageId: string, target_language?: string) =>
    api
      .post<MessageTranslation>(`/messages/${messageId}/translations/retry`, { target_language })
      .then((r) => r.data),
}
