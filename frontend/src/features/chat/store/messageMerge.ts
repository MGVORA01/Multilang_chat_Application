/** Pure helpers for merging server data into the local message lists (no store access). */
import type { ChatMessage, DeliveryStatus, Message, MessageTranslation } from '../../../types'

const STATUS_RANK: Record<DeliveryStatus, number> = { sent: 0, delivered: 1, read: 2 }

export function sortMessages(list: ChatMessage[]): ChatMessage[] {
  return list.sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id))
}

/** Insert or replace a message; optimistic copies are matched by (sender, client_message_id). */
export function mergeMessage(list: ChatMessage[] | undefined, msg: ChatMessage): ChatMessage[] {
  const next = [...(list ?? [])]
  const idx = next.findIndex(
    (m) =>
      m.id === msg.id ||
      (msg.client_message_id != null && m.client_message_id === msg.client_message_id && m.sender_id === msg.sender_id),
  )
  if (idx >= 0) {
    // Keep translations that arrived before this copy of the message.
    next[idx] = { ...msg, translations: mergeTranslations(next[idx]!.translations, msg.translations) }
  } else {
    next.push(msg)
  }
  return sortMessages(next)
}

/** One translation per target language; a settled result is never replaced by a stale "pending" snapshot. */
export function mergeTranslations(a: MessageTranslation[], b: MessageTranslation[]): MessageTranslation[] {
  const byLang = new Map<string, MessageTranslation>()
  for (const t of [...a, ...b]) {
    const existing = byLang.get(t.target_language)
    if (existing && existing.status !== 'pending' && t.status === 'pending') continue
    byLang.set(t.target_language, t)
  }
  return [...byLang.values()]
}

/** Replace the translation for `tr.target_language` with the latest server state. */
export function upsertTranslation(list: MessageTranslation[], tr: MessageTranslation): MessageTranslation[] {
  const clean: MessageTranslation = {
    id: tr.id,
    message_id: tr.message_id,
    target_language: tr.target_language,
    translated_text: tr.translated_text,
    model_name: tr.model_name,
    status: tr.status,
    error_message: tr.error_message,
    translated_at: tr.translated_at,
  }
  return [...list.filter((t) => t.target_language !== clean.target_language), clean]
}

/** Upgrade delivery status (sent -> delivered -> read); never downgrade. */
export function withStatus<M extends Message>(message: M, ids: Set<string>, target: DeliveryStatus): M {
  return ids.has(message.id) && STATUS_RANK[target] > STATUS_RANK[message.status] ? { ...message, status: target } : message
}
