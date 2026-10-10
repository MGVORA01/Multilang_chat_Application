import type { Conversation } from '../../types'

/** Last-message preview: the reader's translation when available, otherwise the original. */
export function conversationPreview(c: Conversation, me: string | undefined, myLanguage: string): string {
  const m = c.last_message
  if (!m) return 'No messages yet'
  if (m.sender_id === me) return m.original_text
  const tr = m.translations.find((t) => t.target_language === myLanguage && t.status === 'completed')
  return tr?.translated_text || m.original_text
}
