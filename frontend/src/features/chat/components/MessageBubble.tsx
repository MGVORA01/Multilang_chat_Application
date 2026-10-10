import { memo, useState } from 'react'
import { Icon, Spinner } from '../../../components/ui'
import { DeliveryTicks } from './DeliveryTicks'
import { MessageMenu, type MenuItem } from './MessageMenu'
import { formatTime } from '../../../lib/format'
import { hasLetters, languageName } from '../../translation/languages'
import type { ChatMessage, Language, MessageTranslation } from '../../../types'

interface Props {
  message: ChatMessage
  mine: boolean
  viewerLanguage: string
  languages: Language[]
  /** First bubble of a run of consecutive messages from the same sender (gets the tail). */
  isFirstInGroup?: boolean
  onRetryTranslation: (message: ChatMessage, targetLanguage: string) => Promise<void>
  onResend: (message: ChatMessage) => void
}

async function copy(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/**
 * Received: the translation into the viewer's language is shown by default; the 🌐 button toggles
 * the original. Sent: just the text you wrote. Copy actions and language details live in the menu.
 */
export const MessageBubble = memo(function MessageBubble({
  message,
  mine,
  viewerLanguage,
  languages,
  isFirstInGroup = true,
  onRetryTranslation,
  onResend,
}: Props) {
  const [showOriginal, setShowOriginal] = useState(false)
  const [showSentTranslation, setShowSentTranslation] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const needsTranslation = !mine && message.source_language !== viewerLanguage && hasLetters(message.original_text)
  const translation: MessageTranslation | undefined = mine
    ? message.translations[0]
    : message.translations.find((t) => t.target_language === viewerLanguage)
  // Never present an empty string as a successful translation.
  const translated =
    translation?.status === 'completed' && translation.translated_text?.trim() ? translation.translated_text : null
  const translationFailed = translation?.status === 'failed' || (translation?.status === 'completed' && !translated)

  const showingTranslation = !mine && needsTranslation && !!translated && !showOriginal
  const text = showingTranslation ? translated : message.original_text
  const shownLanguage = showingTranslation ? viewerLanguage : message.source_language
  const lang = (code: string) => languageName(code, languages)

  const retry = async (target: string) => {
    setRetrying(true)
    try {
      await onRetryTranslation(message, target)
    } finally {
      setRetrying(false)
    }
  }

  const doCopy = async (value: string) => {
    if (await copy(value)) {
      setToast('Copied')
      setTimeout(() => setToast(null), 1200)
    }
  }

  const items: MenuItem[] = [{ label: 'Copy', onSelect: () => void doCopy(text) }]
  if (showingTranslation) items.push({ label: 'Copy original', onSelect: () => void doCopy(message.original_text) })
  if (!mine && needsTranslation && translated && showOriginal)
    items.push({ label: 'Copy translation', onSelect: () => void doCopy(translated) })
  if (!mine && translated && needsTranslation)
    items.push({ label: showOriginal ? 'Show translation' : 'Show original', onSelect: () => setShowOriginal((v) => !v) })
  if (mine && translation)
    items.push({
      label: showSentTranslation ? 'Hide translation' : `See ${lang(translation.target_language)} translation`,
      onSelect: () => setShowSentTranslation((v) => !v),
    })

  let info: string | undefined
  if (mine) {
    info = translation
      ? `Written in ${lang(message.source_language)} · delivered in ${lang(translation.target_language)}`
      : `Written in ${lang(message.source_language)}`
  } else if (needsTranslation) {
    info = `${lang(message.source_language)} → ${lang(viewerLanguage)}`
  } else {
    info = `Written in ${lang(message.source_language)}`
  }

  const tail = isFirstInGroup ? (mine ? 'rounded-tr-md' : 'rounded-tl-md') : ''

  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'} animate-message-in`}>
      <article
        aria-label={mine ? 'Your message' : 'Received message'}
        className={`group relative max-w-[85%] rounded-2xl px-3.5 pt-2 pb-1.5 sm:max-w-[65%] ${tail} ${
          mine
            ? 'bg-brand-gradient text-white shadow-md shadow-indigo-500/20'
            : 'bg-white text-slate-800 shadow-sm shadow-slate-900/5 ring-1 ring-slate-900/5'
        } ${message.localState === 'failed' ? 'ring-2 ring-red-400' : ''}`}
      >
        <MessageMenu items={items} info={info} align={mine ? 'right' : 'left'} />

        <p className="pr-5 text-[15px] leading-relaxed break-words whitespace-pre-wrap" lang={shownLanguage.slice(0, 3)}>
          {text}
        </p>

        {mine && showSentTranslation && translation && (
          <p className="mt-1.5 rounded-xl bg-white/15 px-2.5 py-1.5 text-sm whitespace-pre-wrap text-indigo-50">
            {translated ?? (translation.status === 'pending' ? 'Translating…' : 'Translation unavailable')}
          </p>
        )}

        {/* Recipient-side translation states (compact) */}
        {!mine && needsTranslation && translation?.status === 'pending' && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-indigo-500">
            <Spinner className="h-3 w-3" />
            Translating…
          </p>
        )}
        {!mine && needsTranslation && translationFailed && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-amber-600" title={translation?.error_message ?? undefined}>
            <Icon.Alert className="h-3.5 w-3.5" />
            Translation unavailable
            <button
              type="button"
              disabled={retrying}
              onClick={() => void retry(viewerLanguage)}
              className="ml-1 inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-700 hover:bg-amber-100 disabled:opacity-50"
            >
              <Icon.Refresh className="h-3 w-3" />
              {retrying ? 'Retrying…' : 'Retry'}
            </button>
          </p>
        )}
        {!mine && needsTranslation && !translation && (
          <button
            type="button"
            disabled={retrying}
            onClick={() => void retry(viewerLanguage)}
            aria-label={`Translate to ${lang(viewerLanguage)}`}
            className="mt-1 inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-600 hover:bg-indigo-100 disabled:opacity-50"
          >
            <Icon.Globe className="h-3 w-3" />
            {retrying ? 'Translating…' : 'Translate'}
          </button>
        )}

        <footer
          className={`mt-0.5 flex items-center justify-end gap-1.5 text-[11px] ${mine ? 'text-indigo-100' : 'text-slate-400'}`}
        >
          {toast && <span className="font-medium">{toast}</span>}
          {!mine && needsTranslation && translated && (
            <button
              type="button"
              onClick={() => setShowOriginal((v) => !v)}
              aria-pressed={showOriginal}
              aria-label={showOriginal ? 'Show translation' : 'Show original'}
              title={showOriginal ? `Showing original (${lang(message.source_language)})` : `Translated from ${lang(message.source_language)}`}
              className={`rounded-full p-0.5 transition hover:text-indigo-600 ${showOriginal ? 'text-indigo-600' : ''}`}
            >
              <Icon.Globe className="h-3.5 w-3.5" />
            </button>
          )}
          <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
          {mine && <DeliveryTicks message={message} />}
        </footer>

        {mine && message.localState === 'failed' && (
          <div className="mt-1 flex items-center justify-end gap-2 text-xs">
            <span className="text-red-100">Not sent</span>
            <button
              type="button"
              className="rounded-full bg-white/20 px-2 py-0.5 font-semibold text-white hover:bg-white/30"
              onClick={() => onResend(message)}
            >
              Resend
            </button>
          </div>
        )}
      </article>
    </div>
  )
})
