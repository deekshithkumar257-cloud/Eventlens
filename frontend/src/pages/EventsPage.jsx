import { Fragment, useState } from 'react';
import { api } from '../services/api';
import { eventTypeLabel, formatDestination, formatUtc, orDash } from '../services/format';
import { useAsync, useDebouncedValue } from '../services/useAsync';
import RawEvent from '../components/RawEvent';
import { EmptyState, ErrorState, LoadingState } from '../components/StatusMessage';

const PAGE_SIZE = 50;
const EVENT_TYPES = ['login_success', 'login_failure', 'network_connection'];
const SEVERITIES = ['info', 'low', 'medium', 'high', 'critical'];

export default function EventsPage() {
  const [search, setSearch] = useState('');
  const [eventType, setEventType] = useState('');
  const [severity, setSeverity] = useState('');
  const [page, setPage] = useState(0);
  const [expandedId, setExpandedId] = useState(null);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);

  const filterKey = `${debouncedSearch}|${eventType}|${severity}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (lastFilterKey !== filterKey) {
    setLastFilterKey(filterKey);
    setPage(0);
  }

  const events = useAsync(
    () => api.listEvents({
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      q: debouncedSearch || undefined,
      event_type: eventType || undefined,
      severity: severity || undefined,
    }),
    [debouncedSearch, eventType, severity, page],
  );

  const total = events.data?.total ?? 0;
  const firstItem = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const lastItem = Math.min(total, (page + 1) * PAGE_SIZE);
  const hasFilters = Boolean(search || eventType || severity);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">Event Explorer</h1>
        <p className="mt-1 text-sm text-slate-400">
          Normalized events from the database, newest first. Expand a row to see the original raw record.
        </p>
      </header>

      <section aria-label="Filters" className="panel grid grid-cols-1 gap-3 p-4 md:grid-cols-[1fr_200px_160px]">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Search</span>
          <input
            type="search"
            className="input"
            placeholder="User, IP address, host or event ID"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Event type</span>
          <select className="input" value={eventType} onChange={(e) => setEventType(e.target.value)}>
            <option value="">All types</option>
            {EVENT_TYPES.map((t) => <option key={t} value={t}>{eventTypeLabel(t)}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Severity</span>
          <select className="input" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="">All</option>
            {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        {hasFilters && (
          <div className="md:col-span-3">
            <button type="button" className="text-xs font-medium text-cyan-300 hover:text-cyan-200" onClick={() => { setSearch(''); setEventType(''); setSeverity(''); }}>
              Clear filters
            </button>
          </div>
        )}
      </section>

      {events.loading && !events.data && <LoadingState label="Loading events…" />}
      {events.error && <ErrorState title="Could not load events" error={events.error} onRetry={events.reload} />}

      {events.data && events.data.items.length === 0 && (
        <EmptyState title={hasFilters ? 'No events match these filters' : 'No events stored yet'}>
          {hasFilters ? 'Try different filters.' : 'Load the sample logs or upload a file to populate the explorer.'}
        </EmptyState>
      )}

      {events.data && events.data.items.length > 0 && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-400">
            <span>Showing {firstItem}–{lastItem} of {total} event{total === 1 ? '' : 's'}</span>
            <div className="flex items-center gap-2">
              <button type="button" className="btn-secondary px-3 py-1.5 text-xs" disabled={page === 0 || events.loading} onClick={() => setPage((p) => p - 1)}>Previous</button>
              <button type="button" className="btn-secondary px-3 py-1.5 text-xs" disabled={lastItem >= total || events.loading} onClick={() => setPage((p) => p + 1)}>Next</button>
            </div>
          </div>

          <div className="panel overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-800">
              <thead className="bg-slate-900/80">
                <tr>
                  <th className="th">Timestamp</th>
                  <th className="th">Event type</th>
                  <th className="th">User</th>
                  <th className="th">Source IP</th>
                  <th className="th">Source host</th>
                  <th className="th">Destination</th>
                  <th className="th">Protocol</th>
                  <th className="th">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {events.data.items.map((event) => {
                  const expanded = expandedId === event.event_id;
                  return (
                    <Fragment key={event.event_id}>
                      <tr
                        className="cursor-pointer transition hover:bg-slate-800/40"
                        onClick={() => setExpandedId(expanded ? null : event.event_id)}
                        aria-expanded={expanded}
                      >
                        <td className="td whitespace-nowrap font-mono text-xs">{formatUtc(event.timestamp)}</td>
                        <td className="td whitespace-nowrap">{eventTypeLabel(event.event_type)}</td>
                        <td className="td font-mono text-xs">{orDash(event.user)}</td>
                        <td className="td font-mono text-xs">{orDash(event.source_ip)}</td>
                        <td className="td font-mono text-xs">{orDash(event.source_host)}</td>
                        <td className="td font-mono text-xs">{formatDestination(event)}</td>
                        <td className="td text-xs">{orDash(event.protocol)}</td>
                        <td className="td text-xs">{event.severity}</td>
                      </tr>
                      {expanded && (
                        <tr className="bg-slate-950/60">
                          <td colSpan={8} className="px-4 py-3">
                            <div className="font-mono text-[11px] text-slate-500">Event ID: {event.event_id}</div>
                            <RawEvent raw={event.raw} defaultOpen />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
