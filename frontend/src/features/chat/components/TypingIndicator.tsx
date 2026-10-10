import { Avatar } from '../../../components/ui'
import type { User } from '../../../types'
import { TypingDots } from './TypingDots'

/**
 * Snapchat-style strip above the message box: the other person's round photo (or initials),
 * "<name> is typing" and bouncing dots on the right.
 */
export function TypingIndicator({ user }: { user: User }) {
  return (
    <div
      data-testid="typing-indicator"
      aria-live="polite"
      className="mb-2 flex animate-peek-in items-center gap-2.5 px-1"
    >
      <span className="animate-ring-pulse rounded-full">
        <Avatar name={user.display_name} seed={user.id} src={user.profile_image_url} size="sm" />
      </span>
      <p className="min-w-0 truncate text-sm text-slate-600">
        <span className="font-semibold text-slate-800">{user.display_name}</span> is typing
      </p>
      <span className="ml-auto pr-2">
        <TypingDots tone="dark" />
      </span>
    </div>
  )
}
