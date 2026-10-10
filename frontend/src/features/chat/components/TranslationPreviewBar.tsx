import { Icon, Spinner } from '../../../components/ui'
import type { Language } from '../../../types'
import type { PreviewState } from '../../translation/hooks/useTranslationPreview'
import { languageName } from '../../translation/languages'

interface Props {
  preview: PreviewState
  recipientName?: string
  recipientLanguage: string
  detectedLanguage: string
  /** '' = auto-detect */
  sourceOverride: string
  onSourceOverride: (code: string) => void
  languages: Language[]
}

/** "Ravi will see · Hindi: …" — live translation of the draft, plus the rare manual source-language override. */
export function TranslationPreviewBar({
  preview,
  recipientName,
  recipientLanguage,
  detectedLanguage,
  sourceOverride,
  onSourceOverride,
  languages,
}: Props) {
  const name = (code: string) => languageName(code, languages)
  return (
    <section
      aria-label="Translation preview"
      aria-live="polite"
      className="mb-2 animate-message-in rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50 to-violet-50 px-4 py-2.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[11px] font-semibold tracking-wide text-indigo-500 uppercase">
        <span className="flex items-center gap-1.5">
          <Icon.Globe className="h-3.5 w-3.5" />
          {recipientName ? `${recipientName} will see` : 'They will see'} · {name(recipientLanguage)}
        </span>
        <label className="flex items-center gap-1 font-medium tracking-normal text-slate-500 normal-case">
          Written in
          <select
            aria-label="Written in"
            value={sourceOverride}
            onChange={(e) => onSourceOverride(e.target.value)}
            className="cursor-pointer rounded-md bg-transparent py-0 pr-1 font-semibold text-slate-700 [field-sizing:content] hover:text-indigo-600 focus:ring-2 focus:ring-indigo-300 focus:outline-none"
          >
            <option value="">Auto ({name(detectedLanguage)})</option>
            {languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name} — {l.native_name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="mt-1 min-h-6 text-[15px] leading-6 text-slate-800" lang={recipientLanguage.slice(0, 3)}>
        {preview.status === 'same' && (
          <span className="text-sm text-slate-500">Same language — they&apos;ll read exactly what you wrote.</span>
        )}
        {preview.status === 'universal' && (
          <span className="text-sm text-slate-500">Emoji and numbers are sent as-is — no translation needed.</span>
        )}
        {preview.status === 'ready' && preview.text}
        {preview.status === 'loading' &&
          (preview.text ? (
            <span className="opacity-50">{preview.text}</span>
          ) : (
            <span className="inline-flex items-center gap-2 text-sm text-indigo-500">
              <Spinner className="h-3 w-3" /> Translating preview…
            </span>
          ))}
        {preview.status === 'error' && (
          <span className="text-sm text-amber-700">Preview unavailable — your message will still be translated.</span>
        )}
        {preview.status === 'idle' && <span className="text-sm text-slate-500">Message too long to preview.</span>}
      </p>
    </section>
  )
}
