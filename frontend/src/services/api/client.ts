import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import { config } from '../../config'
import type { ApiErrorBody, AuthResponse } from '../../types'

/**
 * Axios instance for the REST API.
 * - Access token lives in memory only (set via setAccessToken).
 * - Refresh token is an httpOnly cookie; on a 401 we refresh once and replay the request.
 */
export const api = axios.create({ baseURL: config.apiBaseUrl, withCredentials: true, timeout: config.apiTimeoutMs })

let accessToken: string | null = null
let refreshPromise: Promise<AuthResponse> | null = null
let onSessionRefreshed: ((data: AuthResponse) => void) | null = null
let onSessionExpired: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

export function configureSessionHandlers(handlers: {
  refreshed: (data: AuthResponse) => void
  expired: () => void
}): void {
  onSessionRefreshed = handlers.refreshed
  onSessionExpired = handlers.expired
}

/** Single-flight refresh: concurrent 401s share one /auth/refresh call. */
export function refreshSession(): Promise<AuthResponse> {
  refreshPromise ??= axios
    .post<AuthResponse>(`${config.apiBaseUrl}/auth/refresh`, null, { withCredentials: true })
    .then((res) => {
      setAccessToken(res.data.access_token)
      onSessionRefreshed?.(res.data)
      return res.data
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.set('Authorization', `Bearer ${accessToken}`)
  return config
})

const NO_RETRY = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']

api.interceptors.response.use(undefined, async (error: AxiosError<ApiErrorBody>) => {
  const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined
  if (
    error.response?.status === 401 &&
    original &&
    !original._retried &&
    !NO_RETRY.some((p) => original.url?.endsWith(p))
  ) {
    original._retried = true
    try {
      await refreshSession()
      return api(original)
    } catch {
      onSessionExpired?.()
    }
  }
  return Promise.reject(error)
})

/** Human-readable message from an API error (consistent backend error shape). */
export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError<ApiErrorBody>(err)) {
    if (!err.response) return 'Cannot reach the server. Check your connection.'
    const body = err.response.data?.error
    if (body?.code === 'validation_error' && Array.isArray(body.details)) {
      const first = body.details[0] as { loc?: unknown[]; msg?: string } | undefined
      const field = first?.loc?.at(-1)
      if (first?.msg) return field ? `${String(field)}: ${first.msg.replace(/^Value error, /, '')}` : first.msg
    }
    return body?.message ?? fallback
  }
  return fallback
}

export function errorCode(err: unknown): string | undefined {
  return axios.isAxiosError<ApiErrorBody>(err) ? err.response?.data?.error?.code : undefined
}
