import type { InputHTMLAttributes } from 'react'

/** Labelled text input with inline validation message (wired with aria-invalid/aria-describedby). */
export function TextField({
  id,
  label,
  error,
  className = '',
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { id: string; label: string; error?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-semibold text-slate-700">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`rounded-xl border bg-white px-4 py-3 text-sm shadow-sm transition focus:ring-4 focus:outline-none ${
          error ? 'border-red-300 focus:ring-red-100' : 'border-slate-200 focus:border-indigo-400 focus:ring-indigo-100'
        } ${className}`}
        {...props}
      />
      {error && (
        <p id={`${id}-error`} className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
