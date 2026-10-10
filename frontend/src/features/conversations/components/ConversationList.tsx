import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Avatar, EmptyState, ErrorBanner, Icon, Logo } from '../../../components/ui'
import { ROUTES } from '../../../constants/routes'
import { useAuthStore } from '../../auth/store'
import { sortedConversations, useChatStore } from '../../chat/store/chatStore'
import { languageName } from '../../translation/languages'
import { ConversationListItem } from './ConversationListItem'
import { UserSearchResults } from './UserSearchResults'

/** Sidebar: brand header, profile card, people search, conversation list and logout. */
export function ConversationList({ activeId }: { activeId?: string }) {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const conversationsMap = useChatStore((s) => s.conversations)
  const loaded = useChatStore((s) => s.conversationsLoaded)
  const error = useChatStore((s) => s.conversationsError)
  const online = useChatStore((s) => s.online)
  const typing = useChatStore((s) => s.typing)
  const languages = useChatStore((s) => s.languages)
  const loadConversations = useChatStore((s) => s.loadConversations)
  const [query, setQuery] = useState('')
  const conversations = useMemo(() => sortedConversations(conversationsMap), [conversationsMap])

  if (!user) return null

  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-slate-200/70 bg-white" aria-label="Conversations">
      <header className="flex items-center justify-between px-4 pt-4 pb-2">
        <Logo />
        <Link to={ROUTES.settings} className="rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-800" aria-label="Settings">
          <Icon.Settings />
        </Link>
      </header>

      <Link
        to={ROUTES.settings}
        className="mx-3 mt-1 flex items-center gap-3 rounded-2xl bg-gradient-to-br from-indigo-50 to-violet-50 px-3 py-2.5 ring-1 ring-indigo-100 transition hover:ring-indigo-200"
      >
        <Avatar name={user.display_name} seed={user.id} src={user.profile_image_url} size="sm" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-bold text-slate-900">{user.display_name}</span>
          <span className="flex items-center gap-1 truncate text-xs text-indigo-600">
            <Icon.Globe className="h-3 w-3" />
            Reading in {languageName(user.preferred_language, languages)}
          </span>
        </span>
      </Link>

      <div className="px-3 pt-3 pb-2">
        <label htmlFor="user-search" className="sr-only">
          Search people
        </label>
        <div className="relative">
          <Icon.Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            id="user-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search people to chat with…"
            className="w-full rounded-xl border border-transparent bg-slate-100 py-2.5 pr-3 pl-9 text-sm transition placeholder:text-slate-400 focus:border-indigo-200 focus:bg-white focus:ring-4 focus:ring-indigo-50 focus:outline-none"
          />
        </div>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
        {query.trim() ? (
          <UserSearchResults query={query.trim()} onStarted={() => setQuery('')} />
        ) : error ? (
          <div className="p-3">
            <ErrorBanner message={error} onRetry={() => void loadConversations()} />
          </div>
        ) : !loaded ? (
          <ul className="space-y-1 px-2 py-1" aria-label="Loading conversations">
            {[0, 1, 2, 3].map((i) => (
              <li key={i} className="flex animate-pulse items-center gap-3 rounded-2xl px-3 py-3">
                <span className="h-11 w-11 rounded-full bg-slate-200" />
                <span className="flex-1 space-y-2">
                  <span className="block h-3 w-1/2 rounded bg-slate-200" />
                  <span className="block h-3 w-3/4 rounded bg-slate-100" />
                </span>
              </li>
            ))}
          </ul>
        ) : conversations.length === 0 ? (
          <EmptyState title="No conversations yet" icon={<Icon.Chat className="h-8 w-8" />}>
            <p className="max-w-[16rem] text-sm">Search for someone above and start chatting in your own language.</p>
          </EmptyState>
        ) : (
          <div className="px-2 pb-2">
            <p className="px-3 pt-1 pb-1 text-[11px] font-bold tracking-wider text-slate-400 uppercase">Chats</p>
            <ul className="space-y-0.5">
              {conversations.map((c) => (
                <li key={c.id}>
                  <ConversationListItem
                    conversation={c}
                    me={user}
                    active={c.id === activeId}
                    online={online}
                    isTyping={Object.entries(typing[c.id] ?? {}).some(([uid, exp]) => uid !== user.id && exp > Date.now())}
                  />
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <footer className="border-t border-slate-100 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <button
          type="button"
          onClick={() => void logout()}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 focus-visible:ring-2 focus-visible:ring-red-300 focus-visible:outline-none"
        >
          <Icon.Logout className="h-4 w-4" />
          Log out
        </button>
      </footer>
    </aside>
  )
}
