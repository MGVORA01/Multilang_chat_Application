import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { Button, ErrorBanner, LanguageSelect, Spinner, TextField } from '../../../components/ui'
import { DEFAULT_LANGUAGE } from '../../../constants'
import { ROUTES } from '../../../constants/routes'
import { errorMessage } from '../../../services/api/client'
import { useChatStore } from '../../chat/store/chatStore'
import { useAuthStore } from '../store'
import { validateRegister, type RegisterErrors } from '../validation'
import { AuthLayout } from './AuthLayout'

export function RegisterPage() {
  const register = useAuthStore((s) => s.register)
  const languages = useChatStore((s) => s.languages)
  const loadLanguages = useChatStore((s) => s.loadLanguages)
  const navigate = useNavigate()
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    display_name: '',
    preferred_language: DEFAULT_LANGUAGE,
  })
  const [errors, setErrors] = useState<RegisterErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void loadLanguages()
  }, [loadLanguages])

  const update = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value })

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const v = validateRegister(form)
    setErrors(v)
    if (Object.keys(v).length) return
    setBusy(true)
    setError(null)
    try {
      await register({ ...form, display_name: form.display_name.trim() })
      navigate(ROUTES.home, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Registration failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="Pick the language you want to read messages in.">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        {error && <ErrorBanner message={error} />}
        <TextField id="display_name" label="Display name" value={form.display_name} onChange={update('display_name')} error={errors.display_name} autoComplete="name" />
        <TextField id="username" label="Username" value={form.username} onChange={update('username')} error={errors.username} autoComplete="username" />
        <TextField id="email" label="Email" type="email" value={form.email} onChange={update('email')} error={errors.email} autoComplete="email" />
        <TextField id="new-password" label="Password" type="password" value={form.password} onChange={update('password')} error={errors.password} autoComplete="new-password" />
        <LanguageSelect
          id="preferred_language"
          label="Preferred language"
          value={form.preferred_language}
          languages={languages}
          onChange={(code) => setForm({ ...form, preferred_language: code })}
        />
        <Button type="submit" disabled={busy} className="mt-2 w-full py-3">
          {busy ? <Spinner label="Creating account…" /> : 'Create account'}
        </Button>
        <p className="text-center text-sm text-slate-500">
          Already have an account?{' '}
          <Link to={ROUTES.login} className="font-medium text-indigo-600 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  )
}
