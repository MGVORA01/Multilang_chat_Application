import { api } from '../../services/api/client'
import type { AuthResponse, CurrentUser } from '../../types'

export interface RegisterInput {
  username: string
  email: string
  password: string
  display_name: string
  preferred_language: string
}

export const authApi = {
  register: (body: RegisterInput) => api.post<AuthResponse>('/auth/register', body).then((r) => r.data),
  login: (login: string, password: string) =>
    api.post<AuthResponse>('/auth/login', { login, password }).then((r) => r.data),
  logout: () => api.post('/auth/logout'),
  me: () => api.get<CurrentUser>('/auth/me').then((r) => r.data),
  /** Single-use ticket for opening the WebSocket (keeps JWTs out of URLs). */
  wsTicket: () => api.post<{ ticket: string; expires_in: number }>('/auth/ws-ticket').then((r) => r.data),
}
