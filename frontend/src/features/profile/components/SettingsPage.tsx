import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { Avatar, Button, ErrorBanner, Icon, LanguageSelect, Spinner, TextField } from '../../../components/ui'
import { DEFAULT_LANGUAGE } from '../../../constants'
import { ROUTES } from '../../../constants/routes'
import { errorMessage } from '../../../services/api/client'
import { useAuthStore } from '../../auth/store'
import { useChatStore } from '../../chat/store/chatStore'
import { profileApi } from '../api'
import { DeleteAccountSection } from './DeleteAccountSection'

export function SettingsPage() {
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const languages = useChatStore((s) => s.languages)
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [imageUrl, setImageUrl] = useState(user?.profile_image_url ?? '')
  const [language, setLanguage] = useState(user?.preferred_language ?? DEFAULT_LANGUAGE)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  if (!user) return null

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (imageUrl.trim() && !imageUrl.trim().startsWith('https://')) {
      setError('Profile image URL must start with https://')
      return
    }
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      let updated = await profileApi.update({
        display_name: displayName.trim(),
        profile_image_url: imageUrl.trim() || null,
      })
      if (language !== user.preferred_language) updated = await profileApi.updateLanguage(language)
      setUser(updated)
      setSaved(true)
    } catch (err) {
      setError(errorMessage(err, 'Could not save settings'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="chat-wallpaper min-h-dvh p-4 sm:py-10">
      <div className="mx-auto max-w-lg rounded-3xl bg-white p-6 shadow-xl shadow-slate-900/5 ring-1 ring-slate-900/5 sm:p-8">
        <div className="mb-6 flex items-center gap-3">
          <Link to={ROUTES.home} className="rounded-full p-2 text-slate-600 hover:bg-slate-100" aria-label="Back to chats">
            <Icon.Back />
          </Link>
          <h1 className="text-2xl font-extrabold text-slate-900">Settings</h1>
        </div>
        <div className="mb-6 flex items-center gap-3">
          <Avatar name={displayName || user.display_name} seed={user.id} src={imageUrl || null} size="xl" />
          <div>
            <p className="font-medium">@{user.username}</p>
            <p className="text-sm text-slate-500">{user.email}</p>
          </div>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-4">
          {error && <ErrorBanner message={error} />}
          {saved && (
            <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              Settings saved.
            </p>
          )}
          <TextField id="display-name" label="Display name" value={displayName} maxLength={64} required onChange={(e) => setDisplayName(e.target.value)} />
          <TextField id="image-url" label="Profile image URL (optional)" type="url" value={imageUrl} placeholder="https://…" onChange={(e) => setImageUrl(e.target.value)} />
          <LanguageSelect id="settings-language" label="Preferred language" value={language} languages={languages} onChange={setLanguage} />
          <p className="-mt-2 text-xs text-slate-500">
            New messages will be translated into this language. Earlier messages keep their existing translation — use
            “Translate to …” on a message to translate it again.
          </p>
          <Button type="submit" disabled={busy}>{busy ? <Spinner label="Saving…" /> : 'Save changes'}</Button>
        </form>
        <DeleteAccountSection />
      </div>
    </main>
  )
}
