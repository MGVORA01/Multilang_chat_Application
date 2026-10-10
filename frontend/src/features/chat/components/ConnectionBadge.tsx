import type { ConnectionStatus } from '../../../types'

const LABELS: Record<ConnectionStatus, { text: string; dot: string }> = {
  idle: { text: 'Not connected', dot: 'bg-slate-300' },
  connecting: { text: 'Connecting…', dot: 'bg-amber-400 animate-pulse' },
  open: { text: 'Connected', dot: 'bg-emerald-500' },
  reconnecting: { text: 'Reconnecting…', dot: 'bg-amber-400 animate-pulse' },
  offline: { text: 'Offline', dot: 'bg-red-500' },
  unauthorized: { text: 'Signed out', dot: 'bg-red-500' },
}

export function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  const { text, dot } = LABELS[status]
  return (
    <span
      role="status"
      aria-live="polite"
      title={text}
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${
        status === 'open' ? 'text-slate-400' : 'bg-amber-50 text-amber-700'
      }`}
    >
      <span aria-hidden className={`h-2 w-2 rounded-full ${dot}`} />
      <span className={status === 'open' ? 'sr-only lg:not-sr-only' : ''}>{text}</span>
    </span>
  )
}
