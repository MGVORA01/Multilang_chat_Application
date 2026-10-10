import { useEffect } from 'react'
import { authApi } from '../../auth/api'
import { ChatSocket } from '../../../services/websocket'
import { useAuthStore } from '../../auth/store'
import { bindSocket, useChatStore } from '../store/chatStore'

/** Owns the WebSocket for the logged-in user and wires it to the chat store. */
export function useChatConnection(): void {
  const userId = useAuthStore((s) => s.user?.id ?? null)

  useEffect(() => {
    if (!userId) return
    const store = useChatStore.getState()
    store.reset(userId)
    void store.loadLanguages()
    void store.loadConversations()

    const socket = new ChatSocket({
      getTicket: async () => (await authApi.wsTicket()).ticket,
      onEvent: (event) => useChatStore.getState().handleEvent(event),
      onStatus: (status) => useChatStore.getState().setConnection(status),
      onUnauthorized: () => void useAuthStore.getState().logout(),
    })
    bindSocket(socket)
    socket.start()

    const onVisible = (): void => {
      const { activeConversationId, markRead } = useChatStore.getState()
      if (activeConversationId) markRead(activeConversationId)
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      document.removeEventListener('visibilitychange', onVisible)
      bindSocket(null)
      socket.stop()
    }
  }, [userId])
}
