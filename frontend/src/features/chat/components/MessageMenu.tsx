import { useEffect, useRef, useState } from 'react'
import { Icon } from '../../../components/ui'

export interface MenuItem {
  label: string
  onSelect: () => void
}

/** Hover chevron menu on a bubble (copy, show original…), with an optional info footer. */
export function MessageMenu({ items, info, align }: { items: MenuItem[]; info?: string; align: 'left' | 'right' }) {
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
    <div ref={ref} className="absolute top-1 right-1 z-10">
      <button
        type="button"
        aria-label="Message options"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={`flex h-6 w-6 items-center justify-center rounded-full transition focus:opacity-100 focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:outline-none ${
          open ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
        } bg-black/10 text-current backdrop-blur hover:bg-black/20`}
      >
        <Icon.Chevron className="h-4 w-4" />
      </button>
      {open && (
        <div
          role="menu"
          className={`absolute top-7 ${align === 'right' ? 'right-0' : 'left-0'} w-56 overflow-hidden rounded-xl border border-slate-100 bg-white py-1 text-sm text-slate-700 shadow-xl shadow-slate-900/10`}
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              onClick={() => {
                item.onSelect()
                setOpen(false)
              }}
              className="block w-full px-4 py-2 text-left hover:bg-indigo-50 focus:bg-indigo-50 focus:outline-none"
            >
              {item.label}
            </button>
          ))}
          {info && (
            <p className="mt-1 border-t border-slate-100 px-4 pt-2 pb-1.5 text-xs text-slate-400" data-testid="message-info">
              {info}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
