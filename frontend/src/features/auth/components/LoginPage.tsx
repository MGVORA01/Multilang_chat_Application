import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { Button, ErrorBanner, Spinner, TextField } from '../../../components/ui'
import { ROUTES } from '../../../constants/routes'
import { errorMessage } from '../../../services/api/client'
import { useAuthStore } from '../store'
import { AuthLayout } from './AuthLayout'

export function LoginPage() {
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()
  const [form, setForm] = useState({ login: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!form.login.trim() || !form.password) {
      setError('Enter your username or email and password')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await login(form.login.trim(), form.password)
      navigate(ROUTES.home, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Login failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to continue your conversations.">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        {error && <ErrorBanner message={error} />}
        <TextField
          id="login"
          label="Username or email"
          autoComplete="username"
          value={form.login}
          onChange={(e) => setForm({ ...form, login: e.target.value })}
        />
        <TextField
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <Button type="submit" disabled={busy} className="mt-2 w-full py-3">
          {busy ? <Spinner label="Signing in…" /> : 'Sign in'}
        </Button>
        <p className="text-center text-sm text-slate-500">
          New here?{' '}
          <Link to={ROUTES.register} className="font-medium text-indigo-600 hover:underline">
            Create an account
          </Link>
        </p>
      </form>
    </AuthLayout>
  )
}
