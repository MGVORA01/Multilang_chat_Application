import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { languages, message, translation } from '../../../test/fixtures'
import { MessageBubble } from './MessageBubble'

function renderBubble(props: Partial<Parameters<typeof MessageBubble>[0]> = {}) {
  const onRetryTranslation = vi.fn().mockResolvedValue(undefined)
  const onResend = vi.fn()
  render(
    <MessageBubble
      message={message()}
      mine={false}
      viewerLanguage="hin_Deva"
      languages={languages}
      onRetryTranslation={onRetryTranslation}
      onResend={onResend}
      {...props}
    />,
  )
  return { onRetryTranslation, onResend }
}

describe('MessageBubble (recipient)', () => {
  it('shows the translation by default and toggles to the original with the globe button', async () => {
    renderBubble()
    expect(screen.getByText('आप कैसे हैं?')).toBeInTheDocument()
    // No visible language words in the bubble
    const bubble = screen.getByRole('article')
    expect(bubble).not.toHaveTextContent(/gujarati|hindi/i)

    await userEvent.click(screen.getByRole('button', { name: 'Show original' }))
    expect(screen.getByText('તમે કેમ છો?')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Show translation' }))
    expect(screen.getByText('आप कैसे हैं?')).toBeInTheDocument()
  })

  it('keeps language details in the message menu', async () => {
    renderBubble()
    await userEvent.click(screen.getByRole('button', { name: 'Message options' }))
    expect(screen.getByTestId('message-info')).toHaveTextContent('Gujarati → Hindi')
    expect(screen.getByTestId('message-info')).not.toHaveTextContent(/IndicTrans2/)
    await userEvent.click(screen.getByRole('menuitem', { name: 'Show original' }))
    expect(screen.getByText('તમે કેમ છો?')).toBeInTheDocument()
  })

  it('shows a loading indicator while translation is pending', () => {
    renderBubble({ message: message({ translations: [translation({ status: 'pending', translated_text: null })] }) })
    expect(screen.getByText('તમે કેમ છો?')).toBeInTheDocument()
    expect(screen.getByText(/translating…/i)).toBeInTheDocument()
  })

  it('shows the original with an unavailable notice and a retry button when translation fails', async () => {
    const { onRetryTranslation } = renderBubble({
      message: message({
        translations: [translation({ status: 'failed', translated_text: null, error_message: 'timeout' })],
      }),
    })
    expect(screen.getByText('તમે કેમ છો?')).toBeInTheDocument()
    expect(screen.getByText(/translation unavailable/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetryTranslation).toHaveBeenCalledWith(expect.objectContaining({ id: 'm1' }), 'hin_Deva')
  })

  it('never presents an empty translation as success', () => {
    renderBubble({ message: message({ translations: [translation({ translated_text: '   ' })] }) })
    expect(screen.getByText('તમે કેમ છો?')).toBeInTheDocument()
    expect(screen.getByText(/translation unavailable/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /copy translation/i })).not.toBeInTheDocument()
  })

  it('offers to translate when no translation exists for the viewer language', async () => {
    const { onRetryTranslation } = renderBubble({ message: message({ translations: [] }), viewerLanguage: 'eng_Latn' })
    await userEvent.click(screen.getByRole('button', { name: /translate to english/i }))
    expect(onRetryTranslation).toHaveBeenCalledWith(expect.anything(), 'eng_Latn')
  })

  it('does not show translation controls when the message is already in the viewer language', () => {
    renderBubble({ message: message({ translations: [] }), viewerLanguage: 'guj_Gujr' })
    expect(screen.queryByRole('button', { name: /translate/i })).not.toBeInTheDocument()
  })

  it('copies the shown text and the original from the menu', async () => {
    const user = userEvent.setup()
    const writeText = vi.spyOn(navigator.clipboard, 'writeText')
    renderBubble()
    await user.click(screen.getByRole('button', { name: 'Message options' }))
    await user.click(screen.getByRole('menuitem', { name: 'Copy' }))
    expect(writeText).toHaveBeenLastCalledWith('आप कैसे हैं?')
    await user.click(screen.getByRole('button', { name: 'Message options' }))
    await user.click(screen.getByRole('menuitem', { name: 'Copy original' }))
    expect(writeText).toHaveBeenLastCalledWith('તમે કેમ છો?')
  })
})

describe('MessageBubble (sender)', () => {
  it('shows only the text, time and ticks — no translation/language labels', async () => {
    renderBubble({ mine: true, viewerLanguage: 'guj_Gujr', message: message({ status: 'read' }) })
    expect(screen.getByText('તમે કેમ છો?')).toBeInTheDocument()
    expect(screen.getByLabelText('read')).toBeInTheDocument()
    const bubble = screen.getByRole('article')
    expect(bubble).not.toHaveTextContent(/translated|gujarati|hindi/i)
    expect(screen.queryByText('आप कैसे हैं?')).not.toBeInTheDocument()

    // Still reachable from the menu
    await userEvent.click(screen.getByRole('button', { name: 'Message options' }))
    await userEvent.click(screen.getByRole('menuitem', { name: /see hindi translation/i }))
    expect(screen.getByText('आप कैसे हैं?')).toBeInTheDocument()
  })

  it('lets the user resend a failed message', async () => {
    const { onResend } = renderBubble({ mine: true, message: message({ localState: 'failed' }) })
    expect(screen.getByText('Not sent')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Resend' }))
    expect(onResend).toHaveBeenCalled()
  })
})

describe('MessageBubble (emoji only)', () => {
  it('shows no translate controls for emoji-only messages', () => {
    renderBubble({ message: message({ original_text: '👍🏽🎉', translations: [] }), viewerLanguage: 'hin_Deva' })
    expect(screen.getByText('👍🏽🎉')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /translate/i })).not.toBeInTheDocument()
  })
})
