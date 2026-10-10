import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { Button, ErrorBanner, Spinner, TextField } from '../../../components/ui'
import { ROUTES } from '../../../constants/routes'
import { errorMessage } from '../../../services/api/client'
import { useAuthStore } from '../../auth/store'

/** Password-confirmed, irreversible account deletion. */
export function DeleteAccountSection() {
  const deleteAccount = useAuthStore((s) => s.deleteAccount)
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!password) {
      setError('Enter your password to confirm')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await deleteAccount(password)
      navigate(ROUTES.login, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Could not delete account'))
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="danger-zone" className="mt-8 rounded-2xl border border-red-100 bg-red-50/40 p-5">
      <h2 id="danger-zone" className="font-semibold text-red-700">Delete account</h2>
      <p className="mt-1 text-sm text-slate-600">
        Your account and all of your chats are permanently erased — including the messages in those chats, for both
        you and the people you talked to. This cannot be undone.
      </p>
      {!open ? (
        <Button variant="danger" className="mt-3 border border-red-300" onClick={() => setOpen(true)}>
          Delete my account…
        </Button>
      ) : (
        <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
          {error && <ErrorBanner message={error} />}
          <TextField id="delete-password" label="Confirm with your password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <div className="flex gap-2">
            <Button type="submit" variant="destructive" disabled={busy}>
              {busy ? <Spinner label="Deleting…" /> : 'Permanently delete account'}
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => { setOpen(false); setPassword(''); setError(null) }}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </section>
  )
}
