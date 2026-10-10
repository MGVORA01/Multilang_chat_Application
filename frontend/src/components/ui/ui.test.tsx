import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ConnectionBadge } from '../../features/chat/components/ConnectionBadge'
import { LanguageSelect } from './LanguageSelect'

describe('ConnectionBadge', () => {
  it.each([
    ['open', 'Connected'],
    ['reconnecting', 'Reconnecting…'],
    ['offline', 'Offline'],
  ] as const)('%s → %s', (status, text) => {
    render(<ConnectionBadge status={status} />)
    expect(screen.getByRole('status')).toHaveTextContent(text)
  })
})

describe('LanguageSelect', () => {
  it('shows proper language names even when the server list has not loaded', async () => {
    render(<LanguageSelect id="l" label="Preferred language" value="eng_Latn" languages={[]} onChange={() => {}} />)
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(12)
    expect(options.map((o) => o.textContent)).toContain('Gujarati — ગુજરાતી')
  })
})

describe('Avatar', () => {
  it('loads user-supplied images without sending a referrer', async () => {
    const { Avatar } = await import('./Avatar')
    const { container } = render(<Avatar name="A" src="https://cdn.example/a.png" />)
    expect(container.querySelector('img')).toHaveAttribute('referrerpolicy', 'no-referrer')
  })
})
