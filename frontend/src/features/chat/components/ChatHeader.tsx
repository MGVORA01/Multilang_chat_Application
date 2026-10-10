import { Link } from 'react-router'
import { Avatar, Icon } from '../../../components/ui'
import { ROUTES } from '../../../constants/routes'
import { lastSeen } from '../../../lib/format'
import type { ConnectionStatus, Language, User } from '../../../types'
import { languageName } from '../../translation/languages'
import { ConnectionBadge } from './ConnectionBadge'
import { TypingDots } from './TypingDots'

interface Props {
  other: User | undefined
  online: boolean
  typing: boolean
  languages: Language[]
  connection: ConnectionStatus
}

/** Contact, presence/typing status, their reading language and connection state. */
export function ChatHeader({ other, online: otherOnline, typing, languages, connection }: Props) {
  return (
    <header className="z-10 flex items-center gap-3 border-b border-slate-200/70 bg-white/80 px-3 py-2.5 backdrop-blur-md sm:px-5">
      <Link
        to={ROUTES.home}
        className="-ml-1 rounded-full p-2 text-slate-600 hover:bg-slate-100 md:hidden"
        aria-label="Back to conversations"
      >
        <Icon.Back />
      </Link>
      {other && (
        <Avatar
          name={other.display_name}
          seed={other.id}
          src={other.profile_image_url}
          online={other.is_deleted ? undefined : otherOnline}
          muted={other.is_deleted}
        />
      )}
      <div className="min-w-0 flex-1">
        <h2 className="truncate text-[15px] font-bold text-slate-900">{other?.display_name ?? 'Conversation'}</h2>
        <p className="truncate text-xs text-slate-500">
          {other?.is_deleted ? (
            'account deleted'
          ) : typing ? (
            <span className="inline-flex items-center gap-1.5 font-semibold text-violet-600">
              typing <TypingDots size="sm" />
            </span>
          ) : otherOnline ? (
            <span className="font-medium text-emerald-600">online</span>
          ) : (
            lastSeen(other?.last_seen_at ?? null)
          )}
        </p>
      </div>
      {other && !other.is_deleted && (
        <span
          className="hidden items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-600 sm:inline-flex"
          title={`${other.display_name} reads messages in ${languageName(other.preferred_language, languages)}`}
        >
          <Icon.Globe className="h-3.5 w-3.5" />
          {languageName(other.preferred_language, languages)}
        </span>
      )}
      <ConnectionBadge status={connection} />
    </header>
  )
}
