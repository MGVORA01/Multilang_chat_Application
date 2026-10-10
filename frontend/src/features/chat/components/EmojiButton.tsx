import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Icon, Spinner } from '../../../components/ui'

const EmojiPanel = lazy(() => import('./EmojiPanel'))

/** 😊 button that opens the emoji picker above the composer. Stays open for picking several. */
export function EmojiButton({ onSelect }: { onSelect: (emoji: string) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        aria-label="Emoji"
        aria-haspopup="dialog"
        aria-expanded={open}
        title="Emoji"
        onClick={() => setOpen((v) => !v)}
        className={`inline-flex h-9 w-9 items-center justify-center rounded-full transition ${
          open ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-500/30' : 'text-slate-500 hover:bg-indigo-50 hover:text-indigo-600'
        }`}
      >
        <Icon.Smile className="h-[22px] w-[22px]" />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Emoji picker"
          className="absolute bottom-full left-0 z-30 mb-3 w-[min(22rem,calc(100vw-1.5rem))] animate-message-in overflow-hidden rounded-2xl shadow-2xl shadow-slate-900/15 ring-1 ring-slate-900/5"
        >
          <Suspense
            fallback={
              <div className="flex h-[380px] items-center justify-center bg-white text-slate-400">
                <Spinner label="Loading emoji…" />
              </div>
            }
          >
            <EmojiPanel onSelect={onSelect} />
          </Suspense>
        </div>
      )}
    </div>
  )
}
