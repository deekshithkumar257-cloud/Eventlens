import { NavLink } from 'react-router-dom';
import { useAsync } from '../services/useAsync';
import { api } from '../services/api';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', end: true, icon: GridIcon },
  { to: '/alerts', label: 'Alerts', icon: BellIcon },
  { to: '/events', label: 'Event Explorer', icon: ListIcon },
  { to: '/upload', label: 'Upload Logs', icon: UploadIcon },
];

export default function Layout({ children }) {
  const health = useAsync(() => api.health(), []);
  const apiOnline = health.status === 'success' && health.data?.status === 'ok';
  const apiChecking = health.loading && !health.data;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-slate-800 bg-slate-900/80 md:sticky md:top-0 md:h-screen md:w-60 md:shrink-0 md:border-b-0 md:border-r">
        <div className="flex items-center justify-between gap-3 px-4 py-4 md:flex-col md:items-stretch md:gap-6 md:px-5 md:py-6">
          <div className="flex items-center gap-3">
            <LogoMark />
            <div>
              <div className="text-base font-semibold tracking-tight text-slate-50">EventLens</div>
              <div className="hidden text-xs text-slate-500 md:block">Evidence first, score second</div>
            </div>
          </div>
          <ApiStatus
            online={apiOnline}
            checking={apiChecking}
            onRetry={health.reload}
          />
        </div>

        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible md:px-3 md:pb-0">
          {NAV_ITEMS.map(({ to, label, end, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-200 ring-1 ring-cyan-500/30'
                    : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-100'
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden px-5 pb-5 pt-8 text-xs leading-relaxed text-slate-500 md:absolute md:bottom-0 md:block">
          Synthetic data only. Alerts are investigation leads that need human review.
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-7xl">{children}</div>
      </main>
    </div>
  );
}

function ApiStatus({ online, checking, onRetry }) {
  if (checking) {
    return <span className="text-xs text-slate-500">Checking API…</span>;
  }
  if (online) {
    return (
      <span className="inline-flex items-center gap-2 text-xs text-emerald-300" title="Backend API is responding">
        <span className="h-2 w-2 rounded-full bg-emerald-400" /> API online
      </span>
    );
  }
  return (
    <button type="button" onClick={onRetry} className="inline-flex items-center gap-2 text-xs text-rose-300 hover:text-rose-200" title="Backend is not responding. Click to check again.">
      <span className="h-2 w-2 rounded-full bg-rose-400" /> API offline · retry
    </button>
  );
}

function LogoMark() {
  return (
    <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-500/40 bg-cyan-500/10">
      <svg viewBox="0 0 24 24" className="h-5 w-5 text-cyan-300" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="M15.5 15.5 21 21" />
      </svg>
    </div>
  );
}

function iconProps(className) {
  return { className, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': 'true' };
}
function GridIcon({ className }) {
  return <svg {...iconProps(className)}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>;
}
function BellIcon({ className }) {
  return <svg {...iconProps(className)}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></svg>;
}
function ListIcon({ className }) {
  return <svg {...iconProps(className)}><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3 6h.01M3 12h.01M3 18h.01" /></svg>;
}
function UploadIcon({ className }) {
  return <svg {...iconProps(className)}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m17 8-5-5-5 5" /><path d="M12 3v12" /></svg>;
}
