import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../features/auth/store'
import { bindSocket, useChatStore } from '../features/chat/store/chatStore'
import { alice, bob, conversation, languages, message, translation } from '../test/fixtures'
import { MessengerPage } from './MessengerPage'

vi.mock('../features/auth/api', () => ({
  authApi: { login: vi.fn(), register: vi.fn(), logout: vi.fn(), wsTicket: vi.fn() },
}))
vi.mock('../features/conversations/api', () => ({
  conversationsApi: { list: vi.fn(), get: vi.fn(), openDirect: vi.fn() },
  peopleApi: { search: vi.fn() },
}))
vi.mock('../features/chat/api', () => ({
  messagesApi: {
    history: vi.fn().mockResolvedValue({ items: [], next_cursor: null, has_more: false }),
    retryTranslation: vi.fn(),
  },
}))
vi.mock('../features/translation/api', () => ({
  translationApi: { languages: vi.fn().mockResolvedValue([]), preview: vi.fn().mockResolvedValue({ translated_text: 'preview' }) },
}))

const me = { ...alice, email: 'a@example.com', created_at: '', is_active: true }

function renderMessenger(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<MessengerPage />} />
        <Route path="/c/:conversationId" element={<MessengerPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('messenger', () => {
  beforeEach(() => {
    bindSocket({ send: vi.fn().mockReturnValue(true) } as never)
    useAuthStore.setState({ user: me, status: 'authenticated' })
    const store = useChatStore.getState()
    store.reset(me.id)
    useChatStore.setState({ languages, conversationsLoaded: true, connection: 'open' })
    store.upsertConversation(
      conversation({
        unread_count: 2,
        last_message: message({
          sender_id: 'u-bob',
          original_text: 'मैं ठीक हूँ',
          source_language: 'hin_Deva',
          translations: [translation({ target_language: 'guj_Gujr', translated_text: 'હું ઠીક છું' })],
        }),
      }),
    )
  })

  it('lists conversations with translated preview and unread badge', () => {
    renderMessenger('/')
    expect(screen.getByText('Bob')).toBeInTheDocument()
    expect(screen.getByText('હું ઠીક છું')).toBeInTheDocument()
    expect(screen.getByLabelText('2 unread')).toBeInTheDocument()
  })

  it('shows only the list on mobile at "/" and only the chat on mobile when a conversation is open', async () => {
    const { container, unmount } = renderMessenger('/')
    const [listPane, chatPane] = Array.from(container.firstElementChild!.children)
    expect(listPane).toHaveClass('block')
    expect(chatPane).toHaveClass('hidden', 'md:block')
    unmount()

    const second = renderMessenger('/c/c1')
    const [list2, chat2] = Array.from(second.container.firstElementChild!.children)
    expect(list2).toHaveClass('hidden', 'md:block')
    expect(chat2).toHaveClass('block')
    expect(await screen.findByRole('link', { name: /back to conversations/i })).toBeInTheDocument()
  })

  it('renders history and sends a message from the composer', async () => {
    const send = vi.fn().mockReturnValue(true)
    bindSocket({ send } as never)
    useChatStore.setState({
      messages: { c1: [message({ id: 'm2', sender_id: 'u-bob', original_text: 'नमस्ते', source_language: 'hin_Deva', translations: [translation({ message_id: 'm2', target_language: 'guj_Gujr', translated_text: 'નમસ્તે' })] })] },
      history: { c1: { loaded: true, loading: false, hasMore: false, cursor: null, error: null } },
    })
    renderMessenger('/c/c1')
    expect(await screen.findByText('નમસ્તે')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Message'), 'કેમ છો?{Enter}')
    await waitFor(() =>
      expect(send).toHaveBeenCalledWith(
        'message.send',
        expect.objectContaining({ conversation_id: 'c1', text: 'કેમ છો?' }),
        expect.any(String),
      ),
    )
    // Auto-detect is the default: no source_language is sent; the server detects it.
    expect(send.mock.calls[0]![1]).not.toHaveProperty('source_language')
    expect(screen.getByText('કેમ છો?')).toBeInTheDocument()
    expect(screen.getByLabelText('sending')).toBeInTheDocument()
  })

  it('shows a reconnect notice in the composer when the connection drops', () => {
    useChatStore.setState({ connection: 'reconnecting', history: { c1: { loaded: true, loading: false, hasMore: false, cursor: null, error: null } } })
    renderMessenger('/c/c1')
    expect(screen.getByText(/connection lost/i)).toBeInTheDocument()
    expect(screen.getAllByText('Reconnecting…').length).toBeGreaterThan(0)
  })
})

describe('deleted contact', () => {
  beforeEach(() => {
    bindSocket({ send: vi.fn().mockReturnValue(true) } as never)
    useAuthStore.setState({ user: me, status: 'authenticated' })
    useChatStore.getState().reset(me.id)
    useChatStore.setState({
      languages,
      conversationsLoaded: true,
      connection: 'open',
      history: { c1: { loaded: true, loading: false, hasMore: false, cursor: null, error: null } },
    })
    useChatStore.getState().upsertConversation(conversation())
  })

  it('updates live and replaces the composer with a notice', async () => {
    renderMessenger('/c/c1')
    expect(screen.getByLabelText('Message')).toBeInTheDocument()
    act(() => {
      useChatStore.getState().handleEvent({
        type: 'user.updated',
        id: 'e',
        correlation_id: null,
        ts: '',
        payload: { user: { ...bob, display_name: 'Deleted user', is_deleted: true, is_online: false } },
      })
    })
    expect(screen.getAllByText('Deleted user').length).toBeGreaterThan(0)
    expect(screen.queryByLabelText('Message')).not.toBeInTheDocument()
    expect(screen.getByText(/this account has been deleted/i)).toBeInTheDocument()
  })
})

describe('sidebar logout', () => {
  it('has a labelled Log out button at the bottom of the sidebar', async () => {
    const logout = vi.fn().mockResolvedValue(undefined)
    useAuthStore.setState({ user: me, status: 'authenticated', logout })
    useChatStore.getState().reset(me.id)
    useChatStore.setState({ languages, conversationsLoaded: true })
    renderMessenger('/')
    const button = screen.getByRole('button', { name: 'Log out' })
    expect(button.closest('footer')).not.toBeNull()
    await userEvent.click(button)
    expect(logout).toHaveBeenCalled()
  })
})
