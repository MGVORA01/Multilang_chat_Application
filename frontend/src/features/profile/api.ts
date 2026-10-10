import { api } from '../../services/api/client'
import type { CurrentUser } from '../../types'

export const profileApi = {
  update: (body: { display_name?: string; profile_image_url?: string | null }) =>
    api.patch<CurrentUser>('/users/me', body).then((r) => r.data),
  updateLanguage: (preferred_language: string) =>
    api.patch<CurrentUser>('/users/me/language', { preferred_language }).then((r) => r.data),
  /** Hard delete: removes the account and all its conversations. */
  deleteAccount: (password: string) => api.delete('/users/me', { data: { password } }),
}
