import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { useAsync } from '../services/useAsync';
import { eventTypeLabel, formatCount, formatUtc } from '../services/format';
import StatCard from '../components/StatCard';
import BreakdownBars from '../components/BreakdownBars';
import AlertTable from '../components/AlertTable';
import SampleLoadButton from '../components/SampleLoadButton';
import { EmptyState, ErrorState, LoadingState } from '../components/StatusMessage';

export default function DashboardPage() {
  const stats = useAsync(() => api.stats(), []);
  const alerts = useAsync(() => api.listAlerts({ limit: 5 }), []);

  function refresh() {
    stats.reload();
    alerts.reload();
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-50">Overview</h1>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-400">
            Synthetic security events, normalized and checked against transparent, rule-based detection.
            Every alert is a lead for human review, not a confirmed attack.
          </p>
        </div>
        {stats.data && stats.data.total_events > 0 && (
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={refresh} className="btn-secondary">Refresh</button>
            <Link to="/upload" className="btn-secondary">Upload logs</Link>
          </div>
        )}
      </header>

      {stats.loading && !stats.data && <LoadingState label="Loading dashboard statistics…" />}

      {stats.error && (
        <ErrorState
          title="Could not load dashboard statistics"
          error={stats.error}
          onRetry={refresh}
        />
      )}

      {stats.data && stats.data.total_events === 0 && (
        <EmptyState
          title="No events have been analyzed yet"
          action={<SampleLoadButton onLoaded={refresh} />}
        >
          Load the bundled synthetic sample logs to see normal activity and two suspicious patterns,
          or upload your own CSV or JSON file from the <Link to="/upload" className="text-cyan-300 hover:underline">Upload Logs</Link> page.
        </EmptyState>
      )}

      {stats.data && stats.data.total_events > 0 && (
        <>
          <section aria-label="Key metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Events analyzed" value={formatCount(stats.data.total_events)} hint="Normalized events stored in SQLite" />
            <StatCard label="Possible alerts" value={formatCount(stats.data.total_alerts)} tone="cyan" hint="Rule matches, each with supporting evidence" />
            <StatCard label="High-concern alerts" value={formatCount(stats.data.high_priority_alerts)} tone="rose" hint="High review priority: check these first" />
            <StatCard label="Medium-priority alerts" value={formatCount(stats.data.medium_priority_alerts)} tone="amber" hint="Worth reviewing, lower escalation" />
          </section>

          <section aria-label="Recent alerts" className="space-y-3">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h2 className="panel-title">Recent alerts</h2>
                <p className="text-xs text-slate-500">Highest review priority first. Last import: {formatUtc(stats.data.last_import_at)}</p>
              </div>
              <Link to="/alerts" className="text-sm font-medium text-cyan-300 hover:text-cyan-200">View all alerts →</Link>
            </div>
            {alerts.loading && !alerts.data && <LoadingState label="Loading alerts…" />}
            {alerts.error && <ErrorState title="Could not load alerts" error={alerts.error} onRetry={alerts.reload} />}
            {alerts.data && alerts.data.items.length === 0 && (
              <EmptyState title="No alerts were raised">
                The stored events did not match any detection rule. This can be normal for benign activity.
              </EmptyState>
            )}
            {alerts.data && alerts.data.items.length > 0 && <AlertTable alerts={alerts.data.items} />}
          </section>

          <section aria-label="Summaries" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <BreakdownBars
              title="Events by type"
              counts={stats.data.events_by_type}
              labelFor={eventTypeLabel}
              barClass="bg-cyan-400/70"
            />
            <BreakdownBars
              title="Events by severity"
              counts={stats.data.events_by_severity}
              barClass="bg-amber-400/70"
              emptyText="No severity values."
            />
          </section>
        </>
      )}
    </div>
  );
}
