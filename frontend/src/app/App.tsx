import { useEffect } from 'react'
import { BrowserRouter } from 'react-router'
import { useAuthStore } from '../features/auth'
import { AppRoutes } from './router'

/** Restores the session from the refresh cookie, then renders the routes. */
export default function App() {
  const bootstrap = useAuthStore((s) => s.bootstrap)
  useEffect(() => {
    void bootstrap()
  }, [bootstrap])
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
