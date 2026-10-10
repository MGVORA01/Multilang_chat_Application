/**
 * localStorage that never throws (private mode, blocked storage). Use only for per-device
 * conveniences, never for data that must persist.
 */
export const safeStorage = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  },
  set(key: string, value: string): void {
    try {
      localStorage.setItem(key, value)
    } catch {
      /* preference just isn't remembered */
    }
  },
}
