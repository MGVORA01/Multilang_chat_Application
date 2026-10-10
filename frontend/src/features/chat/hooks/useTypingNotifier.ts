import { useCallback, useEffect, useRef } from 'react'
import { TIMING } from '../../../constants'

/**
 * Turns keystrokes into throttled `typing.start` / `typing.stop` notifications:
 * start at most every few seconds, stop after a pause, on send, and on unmount.
 */
export function useTypingNotifier(notify: (started: boolean) => void) {
  const lastStart = useRef(0)
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const notifyRef = useRef(notify)

  useEffect(() => {
    notifyRef.current = notify
  }, [notify])

  const stop = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current)
    if (lastStart.current) notifyRef.current(false)
    lastStart.current = 0
  }, [])

  const onInput = useCallback(
    (value: string) => {
      if (!value.trim()) return stop()
      const now = Date.now()
      if (now - lastStart.current > TIMING.typingThrottleMs) {
        notifyRef.current(true)
        lastStart.current = now
      }
      if (idleTimer.current) clearTimeout(idleTimer.current)
      idleTimer.current = setTimeout(stop, TIMING.typingIdleMs)
    },
    [stop],
  )

  useEffect(() => stop, [stop])

  return { onInput, stop }
}
