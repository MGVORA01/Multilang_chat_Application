export function Spinner({ className = 'h-4 w-4', label }: { className?: string; label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2">
      <span
        aria-hidden
        className={`${className} inline-block animate-spin rounded-full border-2 border-current border-r-transparent`}
      />
      {label && <span>{label}</span>}
      {!label && <span className="sr-only">Loading</span>}
    </span>
  )
}
