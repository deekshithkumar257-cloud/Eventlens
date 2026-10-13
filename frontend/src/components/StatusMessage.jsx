export function LoadingState({ label = 'Loading…' }) {
  return (
    <div role="status" aria-live="polite" className="panel flex items-center gap-3 px-5 py-8 text-sm text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400" aria-hidden="true" />
      {label}
    </div>
  );
}

export function EmptyState({ title, children, action }) {
  return (
    <div className="panel flex flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <div className="text-base font-semibold text-slate-100">{title}</div>
      {children && <div className="max-w-xl text-sm leading-relaxed text-slate-400">{children}</div>}
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = 'Something went wrong' }) {
  const message = error?.message || 'Unexpected error.';
  return (
    <div role="alert" className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-5 py-4 text-sm text-rose-100">
      <div className="font-semibold text-rose-200">{title}</div>
      <p className="mt-1 leading-relaxed text-rose-100/90">{message}</p>
      {error?.details?.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-rose-100/80">
          {error.details.slice(0, 10).map((detail) => <li key={detail}>{detail}</li>)}
        </ul>
      )}
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-secondary mt-3 text-xs">
          Try again
        </button>
      )}
    </div>
  );
}

export function InlineMessage({ tone = 'info', children }) {
  const styles = {
    info: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100',
    success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100',
    warning: 'border-amber-500/30 bg-amber-500/10 text-amber-100',
  };
  return <div role="status" className={`rounded-lg border px-4 py-3 text-sm leading-relaxed ${styles[tone]}`}>{children}</div>;
}
