import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { bob } from '../../../test/fixtures'
import { TypingIndicator } from './TypingIndicator'

describe('TypingIndicator', () => {
  it('shows a round avatar, "<name> is typing" and three bouncing dots', () => {
    render(<TypingIndicator user={bob} />)
    const indicator = screen.getByTestId('typing-indicator')
    expect(indicator).toHaveTextContent('Bob is typing')
    expect(indicator.querySelector('.rounded-full')).not.toBeNull()
    expect(indicator.querySelectorAll('.animate-dot-wave')).toHaveLength(3)
  })

  it('uses the profile photo, cropped round, when the user has one', () => {
    render(<TypingIndicator user={{ ...bob, profile_image_url: 'https://cdn.example/bob.png' }} />)
    const img = screen.getByTestId('typing-indicator').querySelector('img')!
    expect(img).toHaveAttribute('src', 'https://cdn.example/bob.png')
    expect(img).toHaveClass('rounded-full', 'object-cover')
  })
})
