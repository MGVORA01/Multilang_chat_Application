import type { ReactNode } from 'react'

export function EmptyState({ title, icon, children }: { title: string; icon?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center text-slate-500">
      {icon && (
        <div className="mb-1 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-500">
          {icon}
        </div>
      )}
      <p className="text-base font-semibold text-slate-800">{title}</p>
      {children}
    </div>
  )
}
