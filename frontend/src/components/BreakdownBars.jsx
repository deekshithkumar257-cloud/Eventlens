import { formatCount } from '../services/format';

/** Horizontal bars for a count breakdown (e.g. events by type). Values come from the API. */
export default function BreakdownBars({ title, counts, labelFor = (k) => k, barClass = 'bg-cyan-400/70', emptyText = 'No data yet.' }) {
  const entries = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  return (
    <div className="panel p-5">
      <div className="panel-title">{title}</div>
      {entries.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">{emptyText}</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {entries.map(([key, value]) => {
            const percent = total ? Math.round((value / total) * 100) : 0;
            return (
              <li key={key}>
                <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                  <span className="text-slate-300">{labelFor(key)}</span>
                  <span className="tabular-nums text-slate-400">
                    {formatCount(value)} <span className="text-slate-600">· {percent}%</span>
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-800" role="presentation">
                  <div className={`h-full rounded-full ${barClass}`} style={{ width: `${percent}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
