import { Link } from 'react-router'
import { Avatar, Icon } from '../../../components/ui'
import { ROUTES } from '../../../constants/routes'
import { formatListTime, otherMember } from '../../../lib/format'
import { TypingDots } from '../../chat/components/TypingDots'
import type { Conversation, CurrentUser, UUID } from '../../../types'
import { conversationPreview } from '../preview'

interface Props {
  conversation: Conversation
  me: CurrentUser
  active: boolean
  isTyping: boolean
  online: Record<UUID, boolean>
}

export function ConversationListItem({ conversation: c, me, active, isTyping, online }: Props) {
  const other = otherMember(c, me.id)
  const lastMine = c.last_message?.sender_id === me.id
  return (
    <Link
      to={ROUTES.conversation(c.id)}
      aria-current={active ? 'page' : undefined}
      className={`flex items-center gap-3 rounded-2xl px-3 py-2.5 transition focus-visible:outline-none ${
        active ? 'bg-indigo-50 ring-1 ring-indigo-100' : 'hover:bg-slate-50 focus-visible:bg-slate-50'
      }`}
    >
      <Avatar
        name={other?.display_name ?? '?'}
        seed={other?.id}
        src={other?.profile_image_url}
        muted={other?.is_deleted}
        online={other && !other.is_deleted ? (online[other.id] ?? other.is_online) : undefined}
      />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className={`truncate font-semibold ${other?.is_deleted ? 'text-slate-400' : 'text-slate-900'}`}>
            {other?.display_name}
          </span>
          <span className={`shrink-0 text-xs ${c.unread_count ? 'font-semibold text-indigo-600' : 'text-slate-400'}`}>
            {formatListTime(c.last_message_at)}
          </span>
        </span>
        <span className="mt-0.5 flex items-center justify-between gap-2">
          <span
            className={`flex min-w-0 items-center gap-1 truncate text-sm ${
              isTyping ? 'font-medium text-indigo-600' : c.unread_count ? 'font-medium text-slate-700' : 'text-slate-500'
            }`}
          >
            {!isTyping && lastMine && c.last_message && (
              <Icon.DoubleCheck
                className={`h-3.5 w-4 shrink-0 ${c.last_message.status === 'read' ? 'text-sky-500' : 'text-slate-400'}`}
              />
            )}
            {isTyping ? (
              <span className="inline-flex items-center gap-1.5 font-semibold text-violet-600">
                typing <TypingDots size="sm" />
              </span>
            ) : (
              <span className="truncate">{conversationPreview(c, me.id, me.preferred_language)}</span>
            )}
          </span>
          {c.unread_count > 0 && (
            <span
              className="bg-brand-gradient inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full px-1.5 text-[11px] font-bold text-white shadow-sm"
              aria-label={`${c.unread_count} unread`}
            >
              {c.unread_count}
            </span>
          )}
        </span>
      </span>
    </Link>
  )
}
