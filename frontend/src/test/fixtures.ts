import type { ChatMessage, Conversation, Language, MessageTranslation, User } from '../types'

export const languages: Language[] = [
  { code: 'eng_Latn', name: 'English', native_name: 'English' },
  { code: 'guj_Gujr', name: 'Gujarati', native_name: 'ગુજરાતી' },
  { code: 'hin_Deva', name: 'Hindi', native_name: 'हिन्दी' },
]

export const alice: User = {
  id: 'u-alice',
  username: 'alice',
  display_name: 'Alice',
  preferred_language: 'guj_Gujr',
  profile_image_url: null,
  last_seen_at: null,
  is_online: true,
  is_deleted: false,
}

export const bob: User = { ...alice, id: 'u-bob', username: 'bob', display_name: 'Bob', preferred_language: 'hin_Deva' }

export function translation(over: Partial<MessageTranslation> = {}): MessageTranslation {
  return {
    id: 't1',
    message_id: 'm1',
    target_language: 'hin_Deva',
    translated_text: 'आप कैसे हैं?',
    model_name: 'ai4bharat/indictrans2-indic-indic-dist-320M',
    status: 'completed',
    error_message: null,
    translated_at: '2026-10-10T10:00:01Z',
    ...over,
  }
}

export function message(over: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'm1',
    conversation_id: 'c1',
    sender_id: alice.id,
    client_message_id: 'cm1',
    original_text: 'તમે કેમ છો?',
    source_language: 'guj_Gujr',
    created_at: '2026-10-10T10:00:00Z',
    translations: [translation()],
    status: 'delivered',
    ...over,
  }
}

export function conversation(over: Partial<Conversation> = {}): Conversation {
  return {
    id: 'c1',
    conversation_type: 'direct',
    title: null,
    created_at: '2026-10-10T09:00:00Z',
    last_message_at: '2026-10-10T10:00:00Z',
    members: [alice, bob],
    last_message: message(),
    unread_count: 0,
    ...over,
  }
}
