import { useState } from 'react';
import { api } from '../services/api';
import { RULE_OPTIONS } from '../services/format';
import { useAsync, useDebouncedValue } from '../services/useAsync';
import AlertTable from '../components/AlertTable';
import { EmptyState, ErrorState, LoadingState } from '../components/StatusMessage';

const PAGE_SIZE = 25;

export default function AlertsPage() {
  const [search, setSearch] = useState('');
  const [priority, setPriority] = useState('');
  const [ruleId, setRuleId] = useState('');
  const [page, setPage] = useState(0);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);

  // Reset to the first page whenever a filter changes.
  const filterKey = `${debouncedSearch}|${priority}|${ruleId}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (lastFilterKey !== filterKey) {
    setLastFilterKey(filterKey);
    setPage(0);
  }

  const alerts = useAsync(
    () => api.listAlerts({
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      q: debouncedSearch || undefined,
      priority: priority || undefined,
      rule_id: ruleId || undefined,
    }),
    [debouncedSearch, priority, ruleId, page],
  );

  const hasFilters = Boolean(search || priority || ruleId);
  const total = alerts.data?.total ?? 0;
  const firstItem = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const lastItem = Math.min(total, (page + 1) * PAGE_SIZE);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">Alerts</h1>
        <p className="mt-1 text-sm text-slate-400">
          Rule matches with supporting evidence. Open an alert to see what was observed, what remains uncertain, and the next step.
        </p>
      </header>

      <section aria-label="Filters" className="panel grid grid-cols-1 gap-3 p-4 md:grid-cols-[1fr_180px_260px]">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Search</span>
          <input
            type="search"
            className="input"
            placeholder="Account, IP address, rule or alert ID"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Review priority</span>
          <select className="input" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="">All priorities</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-400">Rule</span>
          <select className="input" value={ruleId} onChange={(e) => setRuleId(e.target.value)}>
            <option value="">All rules</option>
            {RULE_OPTIONS.map((rule) => <option key={rule.value} value={rule.value}>{rule.label}</option>)}
          </select>
        </label>
        {hasFilters && (
          <div className="md:col-span-3">
            <button
              type="button"
              className="text-xs font-medium text-cyan-300 hover:text-cyan-200"
              onClick={() => { setSearch(''); setPriority(''); setRuleId(''); }}
            >
              Clear filters
            </button>
          </div>
        )}
      </section>

      {alerts.loading && !alerts.data && <LoadingState label="Loading alerts…" />}
      {alerts.error && <ErrorState title="Could not load alerts" error={alerts.error} onRetry={alerts.reload} />}

      {alerts.data && alerts.data.items.length === 0 && (
        <EmptyState title={hasFilters ? 'No alerts match these filters' : 'No alerts yet'}>
          {hasFilters
            ? 'Try a different search term or clear the filters.'
            : 'Load the sample logs or upload a CSV/JSON file to generate alerts.'}
        </EmptyState>
      )}

      {alerts.data && alerts.data.items.length > 0 && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-400">
            <span>Showing {firstItem}–{lastItem} of {total} alert{total === 1 ? '' : 's'}</span>
            <div className="flex items-center gap-2">
              <button type="button" className="btn-secondary px-3 py-1.5 text-xs" disabled={page === 0 || alerts.loading} onClick={() => setPage((p) => p - 1)}>
                Previous
              </button>
              <button type="button" className="btn-secondary px-3 py-1.5 text-xs" disabled={lastItem >= total || alerts.loading} onClick={() => setPage((p) => p + 1)}>
                Next
              </button>
            </div>
          </div>
          <AlertTable alerts={alerts.data.items} />
        </div>
      )}
    </div>
  );
}
