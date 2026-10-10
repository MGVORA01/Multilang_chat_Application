import type { ReactNode } from 'react'
import { Icon, Logo } from '../../../components/ui'

function DemoBubble({ side, text, sub, delay }: { side: 'left' | 'right'; text: string; sub: string; delay: string }) {
  return (
    <div className={`flex ${side === 'right' ? 'justify-end' : 'justify-start'} animate-float`} style={{ animationDelay: delay }}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 shadow-lg ${
          side === 'right' ? 'rounded-tr-md bg-white text-slate-800' : 'rounded-tl-md bg-white/15 text-white ring-1 ring-white/20 backdrop-blur'
        }`}
      >
        <p className="text-[15px] font-medium">{text}</p>
        <p className={`mt-0.5 flex items-center gap-1 text-[11px] ${side === 'right' ? 'text-slate-400' : 'text-indigo-100'}`}>
          <Icon.Globe className="h-3 w-3" />
          {sub}
        </p>
      </div>
    </div>
  )
}

/** Split-screen auth layout: brand panel with a live translation demo + the form. */
export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <main className="flex min-h-dvh bg-slate-50">
      <section className="bg-brand-gradient relative hidden w-[46%] flex-col justify-between overflow-hidden p-10 text-white lg:flex">
        <div aria-hidden className="absolute -top-24 -right-24 h-72 w-72 rounded-full bg-white/10 blur-2xl" />
        <div aria-hidden className="absolute -bottom-32 -left-20 h-80 w-80 rounded-full bg-fuchsia-400/20 blur-3xl" />
        <div className="relative flex items-center gap-2 text-lg font-extrabold">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 ring-1 ring-white/25">
            <Icon.Chat className="h-5 w-5" />
          </span>
          BhashaChat
        </div>
        <div className="relative space-y-4" aria-hidden>
          <DemoBubble side="left" text="તમે કેમ છો?" sub="Sent in Gujarati" delay="0s" />
          <DemoBubble side="right" text="आप कैसे हैं?" sub="Received in Hindi" delay="0.6s" />
          <DemoBubble side="left" text="See you at 5 pm!" sub="Sent in English" delay="1.2s" />
          <DemoBubble side="right" text="शाम 5 बजे मिलते हैं!" sub="Received in Hindi" delay="1.8s" />
        </div>
        <div className="relative">
          <h2 className="text-3xl leading-tight font-extrabold">
            Speak your language.
            <br />
            Be understood in theirs.
          </h2>
          <p className="mt-3 max-w-md text-indigo-100">
            Real-time conversations in 11 Indian languages and English — every message translated instantly.
          </p>
        </div>
      </section>

      <section className="flex flex-1 items-center justify-center p-4 sm:p-8">
        <div className="w-full max-w-md">
          <Logo className="mb-8 lg:hidden" />
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">{title}</h1>
          <p className="mt-2 mb-8 text-slate-500">{subtitle}</p>
          {children}
        </div>
      </section>
    </main>
  )
}
