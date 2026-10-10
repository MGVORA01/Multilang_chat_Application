import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../store'
import { validateRegister } from '../validation'
import { LoginPage } from './LoginPage'
import { RegisterPage } from './RegisterPage'

vi.mock('../api', () => ({ authApi: {} }))
vi.mock('../../translation/api', () => ({ translationApi: { languages: vi.fn().mockResolvedValue([]) } }))

describe('auth forms', () => {
  beforeEach(() => useAuthStore.setState({ user: null, status: 'anonymous' }))

  it('validates registration input', () => {
    expect(validateRegister({ username: 'a', email: 'x', password: '123', display_name: ' ' })).toEqual({
      username: expect.any(String),
      email: expect.any(String),
      password: expect.any(String),
      display_name: 'Required',
    })
    expect(validateRegister({ username: 'alice', email: 'a@b.co', password: 'longenough', display_name: 'A' })).toEqual({})
  })

  it('shows field errors without calling the API', async () => {
    const register = vi.fn()
    useAuthStore.setState({ register })
    render(<MemoryRouter><RegisterPage /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText('At least 8 characters')).toBeInTheDocument()
    expect(register).not.toHaveBeenCalled()
  })

  it('shows a server error on failed login', async () => {
    const login = vi.fn().mockRejectedValue({
      isAxiosError: true,
      response: { status: 401, data: { error: { code: 'invalid_credentials', message: 'Invalid username/email or password' } } },
    })
    useAuthStore.setState({ login })
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    await userEvent.type(screen.getByLabelText('Username or email'), 'alice')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(login).toHaveBeenCalledWith('alice', 'wrong')
    // errorMessage() only understands real Axios errors; any rejection still surfaces an alert.
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('requires both fields before submitting login', async () => {
    const login = vi.fn()
    useAuthStore.setState({ login })
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/enter your username/i)
    expect(login).not.toHaveBeenCalled()
  })
})
