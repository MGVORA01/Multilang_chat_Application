/** Messenger shell. Desktop: sidebar + chat side by side; mobile: one panel at a time. */
import { useParams } from 'react-router'
import { Icon } from '../components/ui'
import { ChatView } from '../features/chat'
import { ConversationList } from '../features/conversations'

/**
 * Desktop: sidebar + chat side by side. Mobile: list at "/", chat at "/c/:id" (one panel at a time).
 */
export function MessengerPage() {
  const { conversationId } = useParams()
  return (
    <div className="flex h-dvh overflow-hidden">
      <div className={`h-full w-full md:w-80 md:shrink-0 lg:w-96 ${conversationId ? 'hidden md:block' : 'block'}`}>
        <ConversationList activeId={conversationId} />
      </div>
      <div className={`h-full min-w-0 flex-1 ${conversationId ? 'block' : 'hidden md:block'}`}>
        {conversationId ? (
          <ChatView key={conversationId} conversationId={conversationId} />
        ) : (
          <div className="chat-wallpaper flex h-full items-center justify-center p-8">
            <div className="max-w-md text-center">
              <div className="bg-brand-gradient mx-auto mb-5 flex h-20 w-20 animate-float items-center justify-center rounded-3xl text-white shadow-xl shadow-indigo-500/30">
                <Icon.Globe className="h-10 w-10" />
              </div>
              <h2 className="text-2xl font-extrabold text-slate-900">
                Chat in <span className="text-brand-gradient">any Indian language</span>
              </h2>
              <p className="mt-2 text-slate-500">
                Write in your own language — everyone receives your message in theirs, translated instantly.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2 text-sm">
                {['ગુજરાતી', 'हिन्दी', 'English', 'தமிழ்', 'বাংলা', 'मराठी', 'తెలుగు', 'ಕನ್ನಡ'].map((l) => (
                  <span key={l} className="rounded-full bg-white/80 px-3 py-1 font-medium text-slate-600 shadow-sm ring-1 ring-slate-900/5">
                    {l}
                  </span>
                ))}
              </div>
              <p className="mt-6 text-xs text-slate-400">Pick a chat on the left, or search for someone to start.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
