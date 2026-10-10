import { Fragment, useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { errorMessage } from '../../../services/api/client'
import { EmptyState, ErrorBanner, Icon, Spinner } from '../../../components/ui'
import { useNow } from '../hooks/useNow'
import { useScrollAnchoring } from '../hooks/useScrollAnchoring'
import { formatDay, otherMember } from '../../../lib/format'
import { languageName } from '../../translation/languages'
import { useAuthStore } from '../../auth/store'
import { useChatStore } from '../store/chatStore'
import type { ChatMessage } from '../../../types'
import { ChatHeader } from './ChatHeader'
import { Composer } from './Composer'
import { MessageBubble } from './MessageBubble'

const EMPTY: ChatMessage[] = []

/** One conversation: header, history (with paging), translated bubbles and the composer. */
export function ChatView({ conversationId }: { conversationId: string }) {
  const me = useAuthStore((s) => s.user)
  const conversation = useChatStore((s) => s.conversations[conversationId])
  const conversationsLoaded = useChatStore((s) => s.conversationsLoaded)
  const messages = useChatStore((s) => s.messages[conversationId] ?? EMPTY)
  const history = useChatStore((s) => s.history[conversationId])
  const typing = useChatStore((s) => s.typing[conversationId])
  const online = useChatStore((s) => s.online)
  const connection = useChatStore((s) => s.connection)
  const languages = useChatStore((s) => s.languages)
  const { setActive, loadMessages, sendMessage, resendMessage, sendTyping, retryTranslation } = useChatStore.getState()
  const now = useNow(1000)

  const { scrollerRef, onScroll, showJump, scrollToBottom, rememberPosition } = useScrollAnchoring(messages, me?.id)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    setActive(conversationId)
    if (!useChatStore.getState().history[conversationId]?.loaded) void loadMessages(conversationId)
    return () => setActive(null)
  }, [conversationId, setActive, loadMessages])

  const loadOlder = async () => {
    rememberPosition()
    await loadMessages(conversationId, true)
  }

  const onRetryTranslation = useCallback(
    async (message: ChatMessage, target: string) => {
      setActionError(null)
      try {
        await retryTranslation(message, target)
      } catch (err) {
        setActionError(errorMessage(err, 'Could not retry translation'))
      }
    },
    [retryTranslation],
  )
  const onResend = useCallback(
    (m: ChatMessage) => m.client_message_id && resendMessage(conversationId, m.client_message_id),
    [conversationId, resendMessage],
  )

  if (!conversation) {
    return (
      <div className="chat-wallpaper h-full">
        {conversationsLoaded ? (
          <EmptyState title="Conversation not found" icon={<Icon.Chat className="h-8 w-8" />}>
            <Link to="/" className="font-semibold text-indigo-600 hover:underline">
              Back to conversations
            </Link>
          </EmptyState>
        ) : (
          <EmptyState title="Loading conversation…">
            <Spinner />
          </EmptyState>
        )}
      </div>
    )
  }

  const other = otherMember(conversation, me?.id ?? null)
  const otherOnline = other ? (online[other.id] ?? other.is_online) : false
  const typers = Object.entries(typing ?? {}).filter(([uid, exp]) => uid !== me?.id && exp > now)
  const viewerLanguage = me?.preferred_language ?? 'eng_Latn'

  return (
    <section className="chat-wallpaper flex h-full min-h-0 flex-col" aria-label={`Chat with ${other?.display_name ?? ''}`}>
      <ChatHeader
        other={other}
        online={otherOnline}
        typing={typers.length > 0}
        languages={languages}
        connection={connection}
      />

      <div ref={scrollerRef} onScroll={onScroll} className="scrollbar-thin relative min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-8">
        {history?.hasMore && (
          <div className="mb-3 flex justify-center">
            <button
              type="button"
              onClick={() => void loadOlder()}
              disabled={history.loading}
              className="rounded-full bg-white/90 px-4 py-1.5 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-900/5 hover:bg-white disabled:opacity-60"
            >
              {history.loading ? <Spinner label="Loading…" /> : 'Load older messages'}
            </button>
          </div>
        )}
        {history?.error && (
          <ErrorBanner message={history.error} onRetry={() => void loadMessages(conversationId, history.loaded)} />
        )}
        {!history?.loaded && !history?.error && (
          <div className="flex justify-center py-8 text-slate-400">
            <Spinner label="Loading messages…" />
          </div>
        )}
        {history?.loaded && messages.length === 0 && (
          <div className="mx-auto mt-10 max-w-sm rounded-3xl bg-white/90 p-6 text-center shadow-sm ring-1 ring-slate-900/5">
            <div className="bg-brand-gradient mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl text-white shadow-lg shadow-indigo-500/30">
              <Icon.Sparkle className="h-7 w-7" />
            </div>
            <p className="font-bold text-slate-900">Say hello to {other?.display_name} 👋</p>
            <p className="mt-1 text-sm text-slate-500">
              Write in {languageName(viewerLanguage, languages)}. They&apos;ll read it in{' '}
              {languageName(other?.preferred_language ?? '', languages)} — automatically.
            </p>
          </div>
        )}
        <ol className="flex flex-col" aria-live="polite" aria-relevant="additions">
          {messages.map((m, i) => {
            const prev = messages[i - 1]
            const newDay = !prev || formatDay(prev.created_at) !== formatDay(m.created_at)
            const firstInGroup = newDay || prev?.sender_id !== m.sender_id
            return (
              <Fragment key={m.client_message_id ?? m.id}>
                {newDay && (
                  <li className="sticky top-0 z-[1] my-3 text-center">
                    <span className="rounded-full bg-white/90 px-3 py-1 text-[11px] font-semibold tracking-wide text-slate-500 uppercase shadow-sm ring-1 ring-slate-900/5 backdrop-blur">
                      {formatDay(m.created_at)}
                    </span>
                  </li>
                )}
                <li className={firstInGroup ? 'mt-2.5' : 'mt-0.5'}>
                  <MessageBubble
                    message={m}
                    mine={m.sender_id === me?.id}
                    viewerLanguage={viewerLanguage}
                    languages={languages}
                    isFirstInGroup={firstInGroup}
                    onRetryTranslation={onRetryTranslation}
                    onResend={onResend}
                  />
                </li>
              </Fragment>
            )
          })}
        </ol>
      </div>

      {showJump && (
        <div className="relative">
          <button
            type="button"
            onClick={() => scrollToBottom(true)}
            className="bg-brand-gradient absolute -top-14 left-1/2 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-500/30"
          >
            <Icon.ArrowDown className="h-3.5 w-3.5" />
            New messages
          </button>
        </div>
      )}
      {actionError && (
        <div className="px-3 pb-1">
          <ErrorBanner message={actionError} />
        </div>
      )}
      {other?.is_deleted ? (
        <p role="status" className="border-t border-slate-200/70 bg-white/80 px-4 py-4 text-center text-sm text-slate-500 backdrop-blur">
          This account has been deleted. You can still read your conversation history.
        </p>
      ) : (
        <Composer
          languages={languages}
          myLanguage={viewerLanguage}
          recipientName={other?.display_name}
          recipientLanguage={other?.preferred_language}
          typingUser={typers.length > 0 ? other : undefined}
          disabledReason={
            connection === 'reconnecting' || connection === 'offline'
              ? 'Connection lost — messages will be sent automatically when it is back.'
              : null
          }
          onSend={(text, lang) => sendMessage(conversationId, text, lang, viewerLanguage)}
          onTyping={(started) => sendTyping(conversationId, started)}
        />
      )}
    </section>
  )
}
