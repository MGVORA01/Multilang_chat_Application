import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { translationApi } from '../../translation/api'
import { languages } from '../../../test/fixtures'
import { Composer } from './Composer'

vi.mock('../../translation/api', () => ({
  translationApi: { preview: vi.fn() },
}))

// The real picker renders ~1,900 emoji; a stub keeps the test about our insert/open/close logic.
vi.mock('./EmojiPanel', () => ({
  default: ({ onSelect }: { onSelect: (e: string) => void }) => (
    <div>
      <button type="button" onClick={() => onSelect('😀')}>pick-grin</button>
      <button type="button" onClick={() => onSelect('👍🏽')}>pick-thumb</button>
    </div>
  ),
}))

const preview = vi.mocked(translationApi.preview)

function renderComposer(over: Partial<Parameters<typeof Composer>[0]> = {}) {
  const onSend = vi.fn()
  render(
    <Composer
      languages={languages}
      myLanguage="guj_Gujr"
      recipientName="Ravi"
      recipientLanguage="hin_Deva"
      onSend={onSend}
      onTyping={() => {}}
      {...over}
    />,
  )
  return { onSend }
}

beforeEach(() => {
  localStorage.clear()
  preview.mockReset().mockResolvedValue({
    translated_text: 'आप कैसे हैं?',
    source_language: 'guj_Gujr',
    target_language: 'hin_Deva',
    model_name: 'm',
    duration_ms: 1,
    cached: false,
  })
})

describe('Composer translation preview', () => {
  it('shows what the recipient will see after a pause in typing', async () => {
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), 'તમે કેમ છો?')
    expect(screen.getByRole('region', { name: 'Translation preview' })).toHaveTextContent('Ravi will see · Hindi')
    expect(await screen.findByText('आप कैसे हैं?', {}, { timeout: 2000 })).toBeInTheDocument()
    // debounced: one request for the whole word, with the auto-detected source language
    expect(preview).toHaveBeenCalledTimes(1)
    expect(preview).toHaveBeenCalledWith('તમે કેમ છો?', 'guj_Gujr', 'hin_Deva', expect.any(AbortSignal))
  })

  it('says no translation is needed when writing in the recipient language', async () => {
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), 'नमस्ते')
    expect(screen.getByText(/same language/i)).toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 800))
    expect(preview).not.toHaveBeenCalled()
  })

  it('can be switched off, and remembers the choice', async () => {
    renderComposer()
    const toggle = screen.getByRole('button', { name: 'Translation preview' })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await userEvent.type(screen.getByLabelText('Message'), 'Hello')
    expect(screen.queryByRole('region', { name: 'Translation preview' })).not.toBeInTheDocument()
    expect(localStorage.getItem('composer.preview')).toBe('off')
  })

  it('lets the user override the detected language for preview and sending', async () => {
    const { onSend } = renderComposer({ myLanguage: 'eng_Latn' })
    await userEvent.type(screen.getByLabelText('Message'), 'kem cho')
    await userEvent.selectOptions(screen.getByLabelText('Written in'), 'guj_Gujr')
    await waitFor(() => expect(preview).toHaveBeenLastCalledWith('kem cho', 'guj_Gujr', 'hin_Deva', expect.any(AbortSignal)), {
      timeout: 2000,
    })
    await userEvent.type(screen.getByLabelText('Message'), '{Enter}')
    expect(onSend).toHaveBeenCalledWith('kem cho', 'guj_Gujr')
  })

  it('auto-detect sends no explicit language', async () => {
    const { onSend } = renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), 'Hello{Enter}')
    expect(onSend).toHaveBeenCalledWith('Hello', null)
  })

  it('shows a friendly message if the preview fails', async () => {
    preview.mockRejectedValue(new Error('503'))
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), 'Hello')
    expect(await screen.findByText(/preview unavailable/i, {}, { timeout: 2000 })).toBeInTheDocument()
  })
})

describe('Composer emoji picker', () => {
  it('opens the picker and inserts emoji at the cursor, staying open for more', async () => {
    const { onSend } = renderComposer()
    const box = screen.getByLabelText('Message') as HTMLTextAreaElement
    await userEvent.type(box, 'Hi there')
    box.setSelectionRange(2, 2) // caret after "Hi"

    await userEvent.click(screen.getByRole('button', { name: 'Emoji' }))
    expect(screen.getByRole('dialog', { name: 'Emoji picker' })).toBeInTheDocument()
    await userEvent.click(await screen.findByText('pick-grin'))
    expect(box.value).toBe('Hi😀 there')
    await userEvent.click(screen.getByText('pick-thumb'))
    expect(screen.getByRole('dialog', { name: 'Emoji picker' })).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Emoji picker' })).not.toBeInTheDocument()
    await userEvent.type(box, '{Enter}')
    expect(onSend).toHaveBeenCalledWith(expect.stringContaining('😀'), null)
  })

  it('can send an emoji-only message (previewed as sent as-is)', async () => {
    const { onSend } = renderComposer()
    await userEvent.click(screen.getByRole('button', { name: 'Emoji' }))
    await userEvent.click(await screen.findByText('pick-thumb'))
    expect(screen.getByText(/emoji and numbers are sent as-is/i)).toBeInTheDocument()
    expect(preview).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))
    expect(onSend).toHaveBeenCalledWith('👍🏽', null)
  })
})
