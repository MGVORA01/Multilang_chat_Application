export const ROUTES = {
  home: '/',
  login: '/login',
  register: '/register',
  settings: '/settings',
  conversation: (id: string) => `/c/${id}`,
  conversationPattern: '/c/:conversationId',
} as const
