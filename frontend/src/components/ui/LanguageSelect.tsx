import { DEFAULT_LANGUAGES } from '../../features/translation/languages'
import type { Language } from '../../types'

export function LanguageSelect({
  id,
  value,
  onChange,
  languages,
  label,
  compact = false,
  disabled,
}: {
  id: string
  value: string
  onChange: (code: string) => void
  languages: Language[]
  label: string
  compact?: boolean
  disabled?: boolean
}) {
  return (
    <div className={compact ? 'inline-flex items-center gap-1' : 'flex flex-col gap-1'}>
      <label htmlFor={id} className={compact ? 'text-xs text-slate-500' : 'text-sm font-semibold text-slate-700'}>
        {label}
      </label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className={
          compact
            ? 'rounded-md border-0 bg-transparent py-0.5 pr-6 text-xs text-slate-700 focus:ring-2 focus:ring-indigo-500'
            : 'rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 focus:outline-none'
        }
      >
        {(languages.length ? languages : DEFAULT_LANGUAGES).map((l) => (
          <option key={l.code} value={l.code}>
            {l.name} — {l.native_name}
          </option>
        ))}
      </select>
    </div>
  )
}
