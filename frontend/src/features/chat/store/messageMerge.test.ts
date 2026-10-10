import { describe, expect, it } from 'vitest'
import { message, translation } from '../../../test/fixtures'
import { mergeMessage, mergeTranslations, upsertTranslation, withStatus } from './messageMerge'

describe('messageMerge', () => {
  it('replaces an optimistic copy with the server copy (matched by client_message_id) and keeps order', () => {
    const optimistic = message({ id: 'local:x', client_message_id: 'x', created_at: '2026-10-10T10:00:05Z', translations: [] })
    const older = message({ id: 'm0', client_message_id: 'a', created_at: '2026-10-10T09:00:00Z' })
    const server = message({ id: 'm9', client_message_id: 'x', created_at: '2026-10-10T10:00:04Z', translations: [] })
    const list = mergeMessage(mergeMessage([], optimistic), older)
    const merged = mergeMessage(list, server)
    expect(merged.map((m) => m.id)).toEqual(['m0', 'm9'])
  })

  it('never lets a stale pending snapshot overwrite a settled translation', () => {
    const done = translation({ status: 'completed' })
    const stale = translation({ status: 'pending', translated_text: null })
    expect(mergeTranslations([done], [stale])).toEqual([done])
    expect(mergeTranslations([stale], [done])).toEqual([done])
  })

  it('upserts one translation per target language and strips extra event fields', () => {
    const event = { ...translation({ status: 'failed', translated_text: null }), conversation_id: 'c1' }
    const result = upsertTranslation([translation()], event)
    expect(result).toHaveLength(1)
    expect(result[0]).not.toHaveProperty('conversation_id')
    expect(result[0]!.status).toBe('failed')
  })

  it('upgrades delivery status but never downgrades it', () => {
    const ids = new Set(['m1'])
    expect(withStatus(message({ status: 'sent' }), ids, 'read').status).toBe('read')
    expect(withStatus(message({ status: 'read' }), ids, 'delivered').status).toBe('read')
    expect(withStatus(message({ id: 'other', status: 'sent' }), ids, 'read').status).toBe('sent')
  })
})
