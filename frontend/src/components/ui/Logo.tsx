import { Icon } from './Icon'

export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className="bg-brand-gradient inline-flex h-9 w-9 items-center justify-center rounded-xl text-white shadow-md shadow-indigo-500/30">
        <Icon.Chat className="h-5 w-5" />
      </span>
      <span className="text-lg font-extrabold tracking-tight text-slate-900">
        Bhasha<span className="text-brand-gradient">Chat</span>
      </span>
    </span>
  )
}
