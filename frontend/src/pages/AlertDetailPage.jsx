import { Link, useParams } from 'react-router-dom';
import { api } from '../services/api';
import { formatUtc } from '../services/format';
import { useAsync } from '../services/useAsync';
import PriorityBadge from '../components/PriorityBadge';
import Timeline from '../components/Timeline';
import { EmptyState, ErrorState, LoadingState } from '../components/StatusMessage';

export default function AlertDetailPage() {
  const { alertId } = useParams();
  const alert = useAsync(() => api.getAlert(alertId), [alertId]);
  const timeline = useAsync(() => api.getTimeline(alertId), [alertId]);

  if (alert.loading && !alert.data) {
    return <LoadingState label="Loading alert…" />;
  }

  if (alert.error) {
    const notFound = alert.error.status === 404;
    return (
      <div className="space-y-4">
        <BackLink />
        {notFound ? (
          <EmptyState title="Alert not found">
            No alert with ID <span className="font-mono text-slate-200">{alertId}</span> exists in this database.
            Alert IDs change if the underlying events change.
          </EmptyState>
        ) : (
          <ErrorState title="Could not load this alert" error={alert.error} onRetry={alert.reload} />
        )}
      </div>
    );
  }

  const data = alert.data;
  return (
    <div className="space-y-6">
      <BackLink />

      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <PriorityBadge priority={data.priority} />
          <span className="text-xs font-medium text-slate-400">{data.rule_name}</span>
          <span className="font-mono text-xs text-slate-600">{data.alert_id}</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">{data.title}</h1>
        <p className="max-w-3xl text-sm leading-relaxed text-slate-300">{data.summary}</p>
      </header>

      <div role="note" className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-relaxed text-amber-100">
        <span className="font-semibold">Investigation lead, not proof.</span> This alert is a transparent rule match on synthetic logs.
        It does not establish that an attack occurred. A human reviewer must decide what it means.
      </div>

      <section aria-label="Alert facts" className="panel grid grid-cols-2 gap-4 p-5 text-sm md:grid-cols-4">
        <Fact label="Entity" value={`${data.entity_type === 'user' ? 'Account' : 'Source IP'}: ${data.entity_value}`} mono />
        <Fact label="First observed" value={formatUtc(data.first_seen)} mono />
        <Fact label="Last observed" value={formatUtc(data.last_seen)} mono />
        <Fact label="Supporting events" value={String(data.event_count)} />
        <Fact label="Affected account" value={data.affected_user || 'Not single-valued'} mono />
        <Fact label="Affected source IP" value={data.affected_source_ip || 'Not single-valued'} mono />
        <Fact label="Affected host" value={data.affected_host || '—'} mono />
        <Fact label="Rule" value={data.rule_name} />
      </section>

      <section aria-label="Explanation" className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ExplanationCard heading="What we observed" tone="cyan">{data.observed}</ExplanationCard>
        <ExplanationCard heading="What remains uncertain" tone="amber">{data.uncertain}</ExplanationCard>
        <ExplanationCard heading="Suggested next step" tone="emerald">{data.next_step}</ExplanationCard>
      </section>

      <section aria-label="Evidence factors" className="panel p-5">
        <h2 className="panel-title">Evidence factors</h2>
        <dl className="mt-4 grid grid-cols-1 gap-x-8 gap-y-3 md:grid-cols-2">
          {data.evidence_factors.map((factor) => (
            <div key={factor.factor} className="flex flex-col border-b border-slate-800/80 pb-2 sm:flex-row sm:justify-between sm:gap-4">
              <dt className="text-sm text-slate-400">{factor.factor}</dt>
              <dd className="text-sm text-slate-100 sm:text-right">{factor.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-label="Timeline" className="space-y-4">
        <div>
          <h2 className="panel-title">Chronological timeline</h2>
          <p className="text-xs text-slate-500">
            {data.supporting_event_ids.length} supporting event(s), oldest first. Each event shows why it is linked to this alert.
          </p>
        </div>
        {timeline.loading && !timeline.data && <LoadingState label="Loading timeline…" />}
        {timeline.error && <ErrorState title="Could not load the timeline" error={timeline.error} onRetry={timeline.reload} />}
        {timeline.data && timeline.data.items.length === 0 && (
          <EmptyState title="No supporting events are linked to this alert." />
        )}
        {timeline.data && timeline.data.items.length > 0 && <Timeline items={timeline.data.items} />}
      </section>
    </div>
  );
}

function BackLink() {
  return <Link to="/alerts" className="inline-flex text-sm font-medium text-cyan-300 hover:text-cyan-200">← Back to alerts</Link>;
}

function Fact({ label, value, mono = false }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-0.5 truncate text-slate-100 ${mono ? 'font-mono text-xs' : ''}`} title={value}>{value}</div>
    </div>
  );
}

function ExplanationCard({ heading, tone, children }) {
  const accents = {
    cyan: 'border-t-cyan-400',
    amber: 'border-t-amber-400',
    emerald: 'border-t-emerald-400',
  };
  return (
    <div className={`panel border-t-2 p-5 ${accents[tone]}`}>
      <h2 className="text-sm font-semibold text-slate-100">{heading}</h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-300">{children}</p>
    </div>
  );
}
