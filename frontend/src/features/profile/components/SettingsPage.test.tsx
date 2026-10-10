import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../../auth/store'
import { alice } from '../../../test/fixtures'
import { SettingsPage } from './SettingsPage'

vi.mock('../api', () => ({ profileApi: {} }))
vi.mock('../../auth/api', () => ({ authApi: {} }))
vi.mock('../../translation/api', () => ({ translationApi: { languages: vi.fn().mockResolvedValue([]) } }))

function renderSettings() {
  render(
    <MemoryRouter initialEntries={['/settings']}>
      <Routes>
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/login" element={<p>login page</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('delete account', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { ...alice, email: 'a@example.com', created_at: '', is_active: true },
      status: 'authenticated',
    })
  })

  it('requires opening the confirmation and entering the password', async () => {
    const deleteAccount = vi.fn()
    useAuthStore.setState({ deleteAccount })
    renderSettings()
    expect(screen.queryByLabelText(/confirm with your password/i)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /delete my account/i }))
    await userEvent.click(screen.getByRole('button', { name: /permanently delete account/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(/enter your password/i)
    expect(deleteAccount).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByLabelText(/confirm with your password/i)).not.toBeInTheDocument()
  })

  it('shows the server error for a wrong password and stays on the page', async () => {
    const deleteAccount = vi.fn().mockRejectedValue(new Error('403'))
    useAuthStore.setState({ deleteAccount })
    renderSettings()
    await userEvent.click(screen.getByRole('button', { name: /delete my account/i }))
    await userEvent.type(screen.getByLabelText(/confirm with your password/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /permanently delete account/i }))
    expect(deleteAccount).toHaveBeenCalledWith('wrong')
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('login page')).not.toBeInTheDocument()
  })

  it('deletes and redirects to login', async () => {
    const deleteAccount = vi.fn().mockResolvedValue(undefined)
    useAuthStore.setState({ deleteAccount })
    renderSettings()
    await userEvent.click(screen.getByRole('button', { name: /delete my account/i }))
    await userEvent.type(screen.getByLabelText(/confirm with your password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /permanently delete account/i }))
    expect(await screen.findByText('login page')).toBeInTheDocument()
  })
})
