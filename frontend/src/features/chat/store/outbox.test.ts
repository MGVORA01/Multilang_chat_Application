import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TIMING } from '../../../constants'
import { message } from '../../../test/fixtures'
import { Outbox } from './outbox'

describe('Outbox', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  const setup = (connected = true) => {
    const onFailed = vi.fn()
    const send = vi.fn().mockReturnValue(connected)
    const outbox = new Outbox(onFailed)
    outbox.bind({ send } as never)
    return { outbox, send, onFailed }
  }

  it('sends with a correlation id and clears the timeout on acknowledgement', () => {
    const { outbox, send, onFailed } = setup()
    outbox.transmit('c1', message({ client_message_id: 'cm1', requestedSourceLanguage: null }))
    const [, payload, correlationId] = send.mock.calls[0]!
    expect(payload).not.toHaveProperty('source_language') // auto-detect
    outbox.acknowledge(correlationId)
    vi.advanceTimersByTime(TIMING.sendAckTimeoutMs + 1)
    expect(onFailed).not.toHaveBeenCalled()
  })

  it('marks the message failed on rejection or ack timeout', () => {
    const { outbox, send, onFailed } = setup()
    outbox.transmit('c1', message({ client_message_id: 'a', requestedSourceLanguage: 'hin_Deva' }))
    expect(send.mock.calls[0]![1]).toMatchObject({ source_language: 'hin_Deva' })
    outbox.reject(send.mock.calls[0]![2])
    expect(onFailed).toHaveBeenCalledWith('c1', 'a')

    outbox.transmit('c1', message({ client_message_id: 'b' }))
    vi.advanceTimersByTime(TIMING.sendAckTimeoutMs + 1)
    expect(onFailed).toHaveBeenLastCalledWith('c1', 'b')
  })

  it('does not start a timeout when the socket is down (message stays queued)', () => {
    const { outbox, onFailed } = setup(false)
    outbox.transmit('c1', message({ client_message_id: 'q' }))
    vi.advanceTimersByTime(TIMING.sendAckTimeoutMs + 1)
    expect(onFailed).not.toHaveBeenCalled()
  })
})
