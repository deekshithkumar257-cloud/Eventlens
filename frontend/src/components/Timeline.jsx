import { eventTypeLabel, formatDestination, formatUtc, orDash } from '../services/format';
import RawEvent from './RawEvent';

const ROLE_LABELS = {
  failed_login: 'Failed attempt',
  successful_login: 'Successful login',
};

/** Vertical chronological timeline built with plain React and CSS. */
export default function Timeline({ items }) {
  return (
    <ol className="relative ml-3 border-l border-slate-700">
      {items.map((item, index) => {
        const { event } = item;
        const isSuccess = item.role === 'successful_login';
        return (
          <li key={`${event.event_id}-${index}`} className="relative pb-7 pl-7 last:pb-0">
            <span
              aria-hidden="true"
              className={`absolute -left-[7px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-slate-950 ${
                isSuccess ? 'bg-amber-400' : 'bg-rose-400'
              }`}
            />
            <div className="panel p-4">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-xs font-mono text-slate-400">#{item.position}</span>
                <time className="font-mono text-xs text-slate-300" dateTime={event.timestamp}>{formatUtc(event.timestamp)}</time>
                <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs font-medium text-slate-200">
                  {eventTypeLabel(event.event_type)}
                </span>
                <span className="rounded-md border border-slate-700 px-2 py-0.5 text-xs text-slate-400">
                  {ROLE_LABELS[item.role] || item.role}
                </span>
              </div>

              <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                <Field label="User" value={orDash(event.user)} mono />
                <Field label="Source IP" value={orDash(event.source_ip)} mono />
                <Field label="Source host" value={orDash(event.source_host)} mono />
                <Field label="Destination" value={formatDestination(event)} mono />
                <Field label="Protocol" value={orDash(event.protocol)} />
                <Field label="Severity" value={event.severity} />
              </dl>

              <p className="mt-3 rounded-lg bg-slate-950/60 px-3 py-2 text-xs leading-relaxed text-slate-300">
                <span className="font-semibold text-slate-200">Why this event is linked: </span>
                {item.reason}
              </p>

              <RawEvent raw={event.raw} />
              <div className="mt-1 font-mono text-[11px] text-slate-600">{event.event_id}</div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Field({ label, value, mono = false }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={`truncate text-slate-200 ${mono ? 'font-mono text-xs' : ''}`} title={String(value)}>{value}</dd>
    </div>
  );
}
