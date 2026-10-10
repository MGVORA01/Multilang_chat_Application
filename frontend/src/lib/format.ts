/** Display formatting helpers (dates, names). */

import type { Conversation, User, UUID } from '../types'

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function formatDay(iso: string): string {
  const d = new Date(iso)
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (d.toDateString() === today.toDateString()) return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatListTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toDateString() === new Date().toDateString()
    ? formatTime(iso)
    : d.toLocaleDateString([], { day: 'numeric', month: 'short' })
}

export function lastSeen(iso: string | null): string {
  if (!iso) return 'offline'
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (mins < 1) return 'last seen just now'
  if (mins < 60) return `last seen ${mins} min ago`
  return `last seen ${formatDay(iso).toLowerCase()} at ${formatTime(iso)}`
}

export function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => [...p][0]?.toUpperCase() ?? '')
      .join('') || '?'
  )
}

export function otherMember(conversation: Conversation, me: UUID | null): User | undefined {
  return conversation.members.find((m) => m.id !== me) ?? conversation.members[0]
}
