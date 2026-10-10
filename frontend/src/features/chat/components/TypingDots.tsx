const COLORFUL = ['bg-indigo-500', 'bg-violet-500', 'bg-fuchsia-500']
const DARK = ['bg-slate-800', 'bg-slate-800', 'bg-slate-800']

/** Three bouncing dots (used in the typing strip, header and chat list). */
export function TypingDots({ size = 'md', tone = 'color' }: { size?: 'sm' | 'md'; tone?: 'color' | 'dark' }) {
  const dot = size === 'sm' ? 'h-1 w-1' : 'h-2 w-2'
  const colors = tone === 'dark' ? DARK : COLORFUL
  return (
    <span aria-hidden className={`inline-flex items-center ${size === 'sm' ? 'gap-0.5' : 'gap-1'}`}>
      {colors.map((color, i) => (
        <span
          key={i}
          className={`${dot} animate-dot-wave rounded-full ${color}`}
          style={{ animationDelay: `${i * 160}ms` }}
        />
      ))}
    </span>
  )
}
