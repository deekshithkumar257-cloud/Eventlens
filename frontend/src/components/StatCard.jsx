const TONES = {
  neutral: 'text-slate-50',
  rose: 'text-rose-300',
  amber: 'text-amber-300',
  cyan: 'text-cyan-300',
};

export default function StatCard({ label, value, hint, tone = 'neutral' }) {
  return (
    <div className="panel p-5">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`mt-2 text-3xl font-semibold tabular-nums ${TONES[tone]}`}>{value}</div>
      {hint && <div className="mt-1.5 text-xs leading-relaxed text-slate-500">{hint}</div>}
    </div>
  );
}
