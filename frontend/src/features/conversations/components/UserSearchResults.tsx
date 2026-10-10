import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { Avatar, EmptyState, ErrorBanner, Icon, Spinner } from '../../../components/ui'
import { ROUTES } from '../../../constants/routes'
import { errorMessage } from '../../../services/api/client'
import type { User } from '../../../types'
import { useChatStore } from '../../chat/store/chatStore'
import { languageName } from '../../translation/languages'
import { conversationsApi, peopleApi } from '../api'

const SEARCH_DEBOUNCE_MS = 300

/** People search (debounced); picking someone opens or creates the direct conversation. */
export function UserSearchResults({ query, onStarted }: { query: string; onStarted: () => void }) {
  const navigate = useNavigate()
  const upsert = useChatStore((s) => s.upsertConversation)
  const languages = useChatStore((s) => s.languages)
  // Results are tagged with their query, so a new query shows "Searching…" without resetting state in the effect.
  const [found, setFound] = useState<{ query: string; users?: User[]; error?: string } | null>(null)
  const [starting, setStarting] = useState<string | null>(null)
  const [startError, setStartError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const t = setTimeout(() => {
      peopleApi
        .search(query)
        .then((page) => !cancelled && setFound({ query, users: page.items }))
        .catch((err) => !cancelled && setFound({ query, error: errorMessage(err, 'Search failed') }))
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [query])

  const current = found?.query === query ? found : null
  const results = current?.users ?? null
  const error = startError ?? current?.error ?? null

  const start = async (user: User) => {
    setStarting(user.id)
    try {
      const conversation = await conversationsApi.openDirect(user.id)
      upsert(conversation)
      onStarted()
      navigate(ROUTES.conversation(conversation.id))
    } catch (err) {
      setStartError(errorMessage(err, 'Could not start conversation'))
    } finally {
      setStarting(null)
    }
  }

  if (error) return <div className="p-3"><ErrorBanner message={error} /></div>
  if (!results) return <div className="flex justify-center p-6 text-slate-400"><Spinner label="Searching…" /></div>
  if (!results.length)
    return (
      <EmptyState title="No users found" icon={<Icon.Search className="h-7 w-7" />}>
        <p className="text-sm">Try a different name or username.</p>
      </EmptyState>
    )
  return (
    <div className="px-2 py-1">
      <p className="px-3 pt-2 pb-1 text-[11px] font-bold tracking-wider text-slate-400 uppercase">People</p>
      <ul aria-label="Search results">
        {results.map((u) => (
          <li key={u.id}>
            <button
              type="button"
              onClick={() => void start(u)}
              disabled={starting !== null}
              className="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition hover:bg-slate-100 focus-visible:bg-slate-100 focus-visible:outline-none"
            >
              <Avatar name={u.display_name} seed={u.id} src={u.profile_image_url} online={u.is_online} />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold text-slate-900">{u.display_name}</span>
                <span className="block truncate text-xs text-slate-500">
                  @{u.username} · reads {languageName(u.preferred_language, languages)}
                </span>
              </span>
              {starting === u.id ? (
                <Spinner />
              ) : (
                <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-600">Message</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
