/** Domain types mirroring the backend response schemas (backend/app/features/<feature>/schemas.py). */

export type UUID = string
export type ISODateString = string

export interface Language {
  code: string
  name: string
  native_name: string
}

export interface User {
  id: UUID
  username: string
  display_name: string
  preferred_language: string
  profile_image_url: string | null
  last_seen_at: ISODateString | null
  is_online: boolean
  /** Account was deleted: shown as "Deleted user", can't receive messages. */
  is_deleted: boolean
}

export interface CurrentUser extends User {
  email: string
  created_at: ISODateString
  is_active: boolean
}

export type ConversationMember = User

export type TranslationStatus = 'pending' | 'completed' | 'failed'
export type DeliveryStatus = 'sent' | 'delivered' | 'read'
/** Client-only states for messages not yet acknowledged by the server. */
export type LocalSendState = 'sending' | 'failed'

export interface MessageTranslation {
  id: UUID
  message_id: UUID
  target_language: string
  translated_text: string | null
  model_name: string | null
  status: TranslationStatus
  error_message: string | null
  translated_at: ISODateString | null
}

export interface Message {
  id: UUID
  conversation_id: UUID
  sender_id: UUID
  client_message_id: string | null
  original_text: string
  source_language: string
  created_at: ISODateString
  translations: MessageTranslation[]
  status: DeliveryStatus
}

export interface ChatMessage extends Message {
  localState?: LocalSendState
  /** Language the user explicitly chose in the composer; undefined/null = let the server detect. */
  requestedSourceLanguage?: string | null
}

export interface Conversation {
  id: UUID
  conversation_type: 'direct' | 'group'
  title: string | null
  created_at: ISODateString
  last_message_at: ISODateString | null
  members: ConversationMember[]
  last_message: Message | null
  unread_count: number
}
