import type { CurrentUser } from './domain'

/** REST envelopes shared by every feature API. */

export interface AuthResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: CurrentUser
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface CursorPage<T> {
  items: T[]
  next_cursor: string | null
  has_more: boolean
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown }
}
