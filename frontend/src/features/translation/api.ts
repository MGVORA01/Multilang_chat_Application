import { api } from '../../services/api/client'
import type { Language } from '../../types'

export interface TranslatePreview {
  translated_text: string
  source_language: string
  target_language: string
  model_name: string
  duration_ms: number
  cached: boolean
}

export const translationApi = {
  /** Ad-hoc translation used by the composer's live preview (results are cached server-side). */
  preview: (text: string, source_language: string, target_language: string, signal?: AbortSignal) =>
    api
      .post<TranslatePreview>('/translations', { text, source_language, target_language }, { signal })
      .then((r) => r.data),
  languages: () => api.get<Language[]>('/languages').then((r) => r.data),
}
