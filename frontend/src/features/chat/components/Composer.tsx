import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Icon } from '../../../components/ui'
import { MAX_MESSAGE_LENGTH, STORAGE_KEYS } from '../../../constants'
import { safeStorage } from '../../../lib/storage'
import { EmojiButton } from './EmojiButton'
import { TranslationPreviewBar } from './TranslationPreviewBar'
import { TypingIndicator } from './TypingIndicator'
import { useTranslationPreview } from '../../translation/hooks/useTranslationPreview'
import { DEFAULT_LANGUAGES, guessLanguage } from '../../translation/languages'
import { useTypingNotifier } from '../hooks/useTypingNotifier'
import type { Language, User } from '../../../types'

interface Props {
  languages: Language[]
  /** Sender's preferred language: the fallback when the script is ambiguous. */
  myLanguage: string
  /** The person who will read the message. */
  recipientName?: string
  recipientLanguage?: string
  /** The other person while they are typing (shows the Snapchat-style strip). */
  typingUser?: User
  disabledReason?: string | null
  /** sourceLanguage null = auto-detect on the server */
  onSend: (text: string, sourceLanguage: string | null) => void
  onTyping: (started: boolean) => void
}

const readPreviewPref = (): boolean => safeStorage.get(STORAGE_KEYS.translationPreview) !== 'off'

/** Message input: emoji picker, live translation preview, Enter to send, typing notifications. */
export function Composer({
  languages,
  myLanguage,
  recipientName,
  recipientLanguage,
  typingUser,
  onSend,
  onTyping,
  disabledReason,
}: Props) {
  const [text, setText] = useState('')
  const [sourceOverride, setSourceOverride] = useState('') // '' = auto-detect
  const [previewOn, setPreviewOn] = useState(readPreviewPref)
  const ref = useRef<HTMLTextAreaElement>(null)
  const typing = useTypingNotifier(onTyping)

  // ChatView is keyed by conversation, so this mounts once per conversation.
  useEffect(() => {
    ref.current?.focus()
  }, [])

  const trimmed = text.trim()
  const detected = sourceOverride || guessLanguage(trimmed, myLanguage)
  const preview = useTranslationPreview(previewOn, trimmed, detected, recipientLanguage)
  const langs = languages.length ? languages : DEFAULT_LANGUAGES

  const handleChange = (value: string) => {
    setText(value)
    typing.onInput(value)
  }

  const tooLong = trimmed.length > MAX_MESSAGE_LENGTH
  const canSend = trimmed.length > 0 && !tooLong

  const submit = () => {
    if (!canSend) return
    onSend(trimmed, sourceOverride || null)
    setText('')
    typing.stop()
    ref.current?.focus()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  /** Insert at the caret (replacing any selection), then put the caret after the emoji. */
  const insertEmoji = (emoji: string) => {
    const el = ref.current
    const start = el?.selectionStart ?? text.length
    const end = el?.selectionEnd ?? text.length
    handleChange(text.slice(0, start) + emoji + text.slice(end))
    requestAnimationFrame(() => {
      if (!el) return
      el.focus()
      el.setSelectionRange(start + emoji.length, start + emoji.length)
    })
  }

  const togglePreview = () => {
    setPreviewOn((on) => {
      safeStorage.set(STORAGE_KEYS.translationPreview, on ? 'off' : 'on')
      return !on
    })
  }

  const showBar = previewOn && trimmed.length > 0 && !!recipientLanguage

  return (
    <form
      className="border-t border-slate-200/70 bg-white/85 px-3 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur sm:px-5"
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      {typingUser && <TypingIndicator user={typingUser} />}

      {disabledReason && (
        <p className="mb-2 flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-700">
          <Icon.Alert className="h-3.5 w-3.5" />
          {disabledReason}
        </p>
      )}

      {showBar && (
        <TranslationPreviewBar
          preview={preview}
          recipientName={recipientName}
          recipientLanguage={recipientLanguage!}
          detectedLanguage={detected}
          sourceOverride={sourceOverride}
          onSourceOverride={setSourceOverride}
          languages={langs}
        />
      )}

      <div className="flex items-end gap-2.5">
        <div className="flex min-w-0 flex-1 items-end gap-1.5 rounded-[1.5rem] border border-slate-200 bg-white px-[5px] py-[5px] shadow-sm transition-[border-color,box-shadow] focus-within:border-indigo-400 focus-within:shadow-[0_0_0_3px_rgb(99_102_241/0.12)]">
          <EmojiButton onSelect={insertEmoji} />
          <label htmlFor="composer" className="sr-only">
            Message
          </label>
          <textarea
            id="composer"
            ref={ref}
            rows={1}
            value={text}
            placeholder="Type a message"
            onChange={(e) => handleChange(e.target.value)}
            onKeyDown={onKeyDown}
            aria-invalid={tooLong || undefined}
            className="scrollbar-thin block max-h-40 min-h-9 min-w-0 flex-1 resize-none border-0 bg-transparent px-1 py-1.5 text-[15px] leading-6 text-slate-800 [field-sizing:content] placeholder:text-slate-400 focus:ring-0 focus:outline-none"
          />
          <button
            type="button"
            onClick={togglePreview}
            aria-label="Translation preview"
            aria-pressed={previewOn}
            title={previewOn ? 'Translation preview on — click to hide' : 'Show what they will see before sending'}
            className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition ${
              previewOn ? 'text-indigo-600 hover:bg-indigo-50' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600'
            }`}
          >
            {previewOn ? <Icon.Eye className="h-5 w-5" /> : <Icon.EyeOff className="h-5 w-5" />}
          </button>
          {trimmed.length > MAX_MESSAGE_LENGTH * 0.8 && (
            <span
              className={`inline-flex h-9 shrink-0 items-center text-xs tabular-nums ${tooLong ? 'font-semibold text-red-600' : 'text-slate-400'}`}
              aria-live="polite"
            >
              {trimmed.length}/{MAX_MESSAGE_LENGTH}
            </span>
          )}
        </div>
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          className="bg-brand-gradient inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-white shadow-md shadow-indigo-500/30 transition hover:scale-105 hover:brightness-110 focus-visible:ring-4 focus-visible:ring-indigo-200 focus-visible:outline-none active:scale-95 disabled:scale-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:bg-none disabled:text-slate-400 disabled:shadow-none"
        >
          <Icon.Send className="h-5 w-5 translate-x-px" />
        </button>
      </div>
    </form>
  )
}
