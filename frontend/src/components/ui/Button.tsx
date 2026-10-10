import type { ButtonHTMLAttributes } from 'react'

export type ButtonVariant = 'primary' | 'ghost' | 'danger' | 'destructive' | 'soft'

export function Button({
  children,
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  const styles = {
    primary:
      'bg-brand-gradient text-white shadow-md shadow-indigo-500/25 hover:brightness-110 disabled:opacity-50 disabled:shadow-none',
    soft: 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 disabled:opacity-50',
    ghost: 'text-slate-700 hover:bg-slate-100 disabled:text-slate-400',
    danger: 'text-red-600 hover:bg-red-50',
    destructive: 'bg-red-600 text-white shadow-md shadow-red-500/25 hover:bg-red-700 disabled:opacity-50 disabled:shadow-none',
  }[variant]
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:outline-none active:scale-[0.98] disabled:cursor-not-allowed ${styles} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
