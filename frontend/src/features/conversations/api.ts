import { api } from '../../services/api/client'
import type { Conversation, Page, User } from '../../types'

export const conversationsApi = {
  list: () => api.get<Page<Conversation>>('/conversations', { params: { limit: 100 } }).then((r) => r.data),
  get: (id: string) => api.get<Conversation>(`/conversations/${id}`).then((r) => r.data),
  /** Returns the existing direct conversation if there already is one. */
  openDirect: (participant_id: string) =>
    api.post<Conversation>('/conversations', { participant_id }).then((r) => r.data),
}

export const peopleApi = {
  search: (q: string, limit = 20) => api.get<Page<User>>('/users', { params: { q, limit } }).then((r) => r.data),
}
