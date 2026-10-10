import { initials } from '../../lib/format'

const AVATAR_GRADIENTS = [
  'from-indigo-500 to-violet-500',
  'from-sky-500 to-indigo-500',
  'from-emerald-500 to-teal-500',
  'from-amber-500 to-orange-500',
  'from-rose-500 to-pink-500',
  'from-fuchsia-500 to-purple-500',
  'from-cyan-500 to-blue-500',
  'from-lime-500 to-emerald-500',
]

/** Stable colour per person (by id, falling back to name). */
function gradientFor(seed: string): string {
  let h = 0
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) | 0
  return AVATAR_GRADIENTS[Math.abs(h) % AVATAR_GRADIENTS.length]!
}

export function Avatar({
  name,
  src,
  online,
  size = 'md',
  seed,
  muted = false,
}: {
  name: string
  src?: string | null
  online?: boolean
  size?: 'sm' | 'md' | 'lg' | 'xl'
  /** Usually the user id, so colours stay stable when names change. */
  seed?: string
  /** Greyed-out style (deleted accounts). */
  muted?: boolean
}) {
  const dim = {
    sm: 'h-8 w-8 text-xs',
    md: 'h-11 w-11 text-sm',
    lg: 'h-14 w-14 text-lg',
    xl: 'h-20 w-20 text-2xl',
  }[size]
  const dot = size === 'sm' ? 'h-2.5 w-2.5' : 'h-3.5 w-3.5'
  return (
    <span className={`relative inline-flex shrink-0 ${dim}`}>
      {src ? (
        // User-supplied URL: don't tell the image host which page/conversation is open.
        <img
          src={src}
          alt=""
          referrerPolicy="no-referrer"
          loading="lazy"
          className={`${dim} rounded-full object-cover ring-2 ring-white`}
        />
      ) : (
        <span
          aria-hidden
          className={`${dim} inline-flex items-center justify-center rounded-full bg-gradient-to-br font-bold text-white shadow-sm ring-2 ring-white ${
            muted ? 'from-slate-300 to-slate-400' : gradientFor(seed ?? name)
          }`}
        >
          {muted ? '?' : initials(name)}
        </span>
      )}
      {online !== undefined && (
        <span
          className={`absolute right-0 bottom-0 ${dot} rounded-full border-2 border-white ${
            online ? 'bg-emerald-500' : 'bg-slate-300'
          }`}
          aria-label={online ? 'online' : 'offline'}
          role="img"
        />
      )}
    </span>
  )
}
