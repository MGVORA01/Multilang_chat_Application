import type { Language } from '../../types'

/**
 * Built-in copy of the default enabled languages so pickers and labels show proper names even
 * before (or if) GET /api/v1/languages succeeds. The server list replaces it once loaded.
 */
export const DEFAULT_LANGUAGES: Language[] = [
  { code: 'eng_Latn', name: 'English', native_name: 'English' },
  { code: 'guj_Gujr', name: 'Gujarati', native_name: 'ગુજરાતી' },
  { code: 'hin_Deva', name: 'Hindi', native_name: 'हिन्दी' },
  { code: 'tam_Taml', name: 'Tamil', native_name: 'தமிழ்' },
  { code: 'ben_Beng', name: 'Bengali', native_name: 'বাংলা' },
  { code: 'mar_Deva', name: 'Marathi', native_name: 'मराठी' },
  { code: 'tel_Telu', name: 'Telugu', native_name: 'తెలుగు' },
  { code: 'kan_Knda', name: 'Kannada', native_name: 'ಕನ್ನಡ' },
  { code: 'mal_Mlym', name: 'Malayalam', native_name: 'മലയാളം' },
  { code: 'pan_Guru', name: 'Punjabi', native_name: 'ਪੰਜਾਬੀ' },
  { code: 'ory_Orya', name: 'Odia', native_name: 'ଓଡ଼ିଆ' },
  { code: 'asm_Beng', name: 'Assamese', native_name: 'অসমীয়া' },
]

const SCRIPT_RANGES: [number, number, string][] = [
  [0x0900, 0x097f, 'Deva'],
  [0x0980, 0x09ff, 'Beng'],
  [0x0a00, 0x0a7f, 'Guru'],
  [0x0a80, 0x0aff, 'Gujr'],
  [0x0b00, 0x0b7f, 'Orya'],
  [0x0b80, 0x0bff, 'Taml'],
  [0x0c00, 0x0c7f, 'Telu'],
  [0x0c80, 0x0cff, 'Knda'],
  [0x0d00, 0x0d7f, 'Mlym'],
]

/**
 * Client-side guess used only to label the optimistic copy of a message; the server performs the
 * authoritative detection (backend/app/core/script_detect.py) and its copy replaces this one.
 */
export function guessLanguage(text: string, preferred: string): string {
  const counts = new Map<string, number>()
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0
    const script = /[a-z]/i.test(ch) ? 'Latn' : SCRIPT_RANGES.find(([a, b]) => cp >= a && cp <= b)?.[2]
    if (script) counts.set(script, (counts.get(script) ?? 0) + 1)
  }
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
  if (!top || preferred.endsWith(`_${top}`)) return preferred
  const defaults: Record<string, string> = { Latn: 'eng_Latn', Deva: 'hin_Deva', Beng: 'ben_Beng' }
  return defaults[top] ?? DEFAULT_LANGUAGES.find((l) => l.code.endsWith(`_${top}`))?.code ?? preferred
}

/** True when the text contains letters in any script (emoji/numbers/punctuation alone need no translation). */
export function hasLetters(text: string): boolean {
  return /\p{L}/u.test(text)
}

/** English name for a language code, falling back to the built-in catalog, then the raw code. */
export function languageName(code: string, languages: Language[]): string {
  return (languages.find((l) => l.code === code) ?? DEFAULT_LANGUAGES.find((l) => l.code === code))?.name ?? code
}
