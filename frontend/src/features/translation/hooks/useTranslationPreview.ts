import { useEffect, useState } from 'react'
import { PREVIEW_MAX_CHARS, TIMING } from '../../../constants'
import { translationApi } from '../api'
import { hasLetters } from '../languages'

export type PreviewState =
  | { status: 'idle' }
  | { status: 'same' } // already in the reader's language: nothing to translate
  | { status: 'universal' } // emoji / numbers only: sent as-is
  | { status: 'loading'; text?: string } // keeps the previous result visible while updating
  | { status: 'ready'; text: string }
  | { status: 'error' }

/** States that need no request, decided synchronously during render. */
function localState(enabled: boolean, text: string, src: string, tgt: string | undefined): PreviewState | null {
  if (!enabled || !text || !tgt || text.length > PREVIEW_MAX_CHARS) return { status: 'idle' }
  if (!hasLetters(text)) return { status: 'universal' }
  if (src === tgt) return { status: 'same' }
  return null
}

/**
 * Live "they'll see" translation of the composer draft. Debounced so it only runs when the user
 * pauses typing; stale requests are aborted so results never arrive out of order.
 */
export function useTranslationPreview(
  enabled: boolean,
  text: string,
  sourceLanguage: string,
  targetLanguage: string | undefined,
): PreviewState {
  const trimmed = text.trim()
  const local = localState(enabled, trimmed, sourceLanguage, targetLanguage)
  const key = `${sourceLanguage}|${targetLanguage}|${trimmed}`
  const [remote, setRemote] = useState<{ key: string; state: PreviewState } | null>(null)

  useEffect(() => {
    if (local || !targetLanguage) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      translationApi
        .preview(trimmed, sourceLanguage, targetLanguage, controller.signal)
        .then((res) => setRemote({ key, state: { status: 'ready', text: res.translated_text } }))
        .catch(() => {
          if (!controller.signal.aborted) setRemote({ key, state: { status: 'error' } })
        })
    }, TIMING.previewDebounceMs)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
    // `local` is derived from the same inputs as `key`; only a change in what to translate matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, local === null])

  if (local) return local
  if (remote?.key === key) return remote.state
  return { status: 'loading', text: remote?.state.status === 'ready' ? remote.state.text : undefined }
}
