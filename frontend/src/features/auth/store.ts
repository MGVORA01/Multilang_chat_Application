import { create } from 'zustand'
import { configureSessionHandlers, refreshSession, setAccessToken } from '../../services/api/client'
import { profileApi } from '../profile/api'
import { authApi, type RegisterInput } from './api'
import type { AuthResponse, CurrentUser } from '../../types'

type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

interface AuthState {
  user: CurrentUser | null
  status: AuthStatus
  /** Restore a session from the httpOnly refresh cookie on page load. */
  bootstrap: () => Promise<void>
  login: (login: string, password: string) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => Promise<void>
  /** Permanently delete the account (requires the password), then sign out locally. */
  deleteAccount: (password: string) => Promise<void>
  setUser: (user: CurrentUser) => void
}

export const useAuthStore = create<AuthState>()((set) => {
  const apply = (data: AuthResponse): void => {
    setAccessToken(data.access_token)
    set({ user: data.user, status: 'authenticated' })
  }
  const clear = (): void => {
    setAccessToken(null)
    set({ user: null, status: 'anonymous' })
  }
  configureSessionHandlers({ refreshed: apply, expired: clear })

  return {
    user: null,
    status: 'loading',
    bootstrap: async () => {
      try {
        apply(await refreshSession())
      } catch {
        clear()
      }
    },
    login: async (login, password) => apply(await authApi.login(login, password)),
    register: async (input) => apply(await authApi.register(input)),
    logout: async () => {
      try {
        await authApi.logout()
      } finally {
        clear()
      }
    },
    deleteAccount: async (password) => {
      await profileApi.deleteAccount(password)
      clear()
    },
    setUser: (user) => set({ user }),
  }
})
