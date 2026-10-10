import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../../../types'

const NEAR_BOTTOM_PX = 120

/**
 * Chat scroll behaviour: keep the reader's place when older messages are prepended, follow new
 * messages while at the bottom (or when we sent them), otherwise offer a "New messages" jump.
 */
export function useScrollAnchoring(messages: ChatMessage[], myId: string | undefined) {
  const scrollerRef = useRef<HTMLDivElement>(null)
  const nearBottom = useRef(true)
  const prevHeight = useRef<number | null>(null)
  const lastCount = useRef(0)
  const [showJump, setShowJump] = useState(false)

  const scrollToBottom = useCallback((smooth = false) => {
    const el = scrollerRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
    setShowJump(false)
  }, [])

  useLayoutEffect(() => {
    const el = scrollerRef.current
    if (!el) return
    if (prevHeight.current !== null) {
      el.scrollTop += el.scrollHeight - prevHeight.current
      prevHeight.current = null
    } else if (messages.length > lastCount.current) {
      if (nearBottom.current || messages.at(-1)?.sender_id === myId) scrollToBottom()
      else setShowJump(true)
    }
    lastCount.current = messages.length
  }, [messages, myId, scrollToBottom])

  const onScroll = useCallback(() => {
    const el = scrollerRef.current
    if (!el) return
    nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
    if (nearBottom.current) setShowJump(false)
  }, [])

  /** Call right before loading older messages so the view stays anchored. */
  const rememberPosition = useCallback(() => {
    prevHeight.current = scrollerRef.current?.scrollHeight ?? null
  }, [])

  return { scrollerRef, onScroll, showJump, scrollToBottom, rememberPosition }
}
