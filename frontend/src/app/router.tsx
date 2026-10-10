import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { Spinner } from '../components/ui'
import { ROUTES } from '../constants/routes'
import { LoginPage, RegisterPage, useAuthStore } from '../features/auth'
import { useChatConnection } from '../features/chat'
import { SettingsPage } from '../features/profile'
import { MessengerPage } from '../pages/MessengerPage'

function RequireAuth({ children }: { children: ReactNode }) {
  const status = useAuthStore((s) => s.status)
  if (status === 'loading') {
    return (
      <div className="flex h-dvh items-center justify-center text-slate-400">
        <Spinner label="Loading…" />
      </div>
    )
  }
  return status === 'authenticated' ? children : <Navigate to={ROUTES.login} replace />
}

function GuestOnly({ children }: { children: ReactNode }) {
  const status = useAuthStore((s) => s.status)
  return status === 'authenticated' ? <Navigate to={ROUTES.home} replace /> : children
}

/** Route table + the realtime connection for the signed-in user. */
export function AppRoutes() {
  useChatConnection()
  return (
    <Routes>
      <Route path={ROUTES.login} element={<GuestOnly><LoginPage /></GuestOnly>} />
      <Route path={ROUTES.register} element={<GuestOnly><RegisterPage /></GuestOnly>} />
      <Route path={ROUTES.settings} element={<RequireAuth><SettingsPage /></RequireAuth>} />
      <Route path={ROUTES.conversationPattern} element={<RequireAuth><MessengerPage /></RequireAuth>} />
      <Route path={ROUTES.home} element={<RequireAuth><MessengerPage /></RequireAuth>} />
      <Route path="*" element={<Navigate to={ROUTES.home} replace />} />
    </Routes>
  )
}
