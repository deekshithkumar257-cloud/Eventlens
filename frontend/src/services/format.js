/** Display helpers. Timestamps are always shown in UTC to avoid local-time confusion. */

export function formatUtc(timestamp) {
  if (!timestamp) return '—';
  return `${timestamp.replace('T', ' ').replace(/Z$/, '')} UTC`;
}

export function formatCount(value) {
  return Number(value ?? 0).toLocaleString('en-US');
}

export const EVENT_TYPE_LABELS = {
  login_success: 'Successful login',
  login_failure: 'Failed login',
  network_connection: 'Network connection',
};

export function eventTypeLabel(type) {
  return EVENT_TYPE_LABELS[type] || type || 'Unknown';
}

export const RULE_OPTIONS = [
  { value: 'R1_REPEATED_FAILED_LOGINS', label: 'Repeated failed logins' },
  { value: 'R2_SUCCESS_AFTER_FAILURES', label: 'Successful login after failures' },
];

export const PRIORITY_STYLES = {
  High: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  Medium: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  Low: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
};

export function formatDestination(event) {
  const host = event.destination_host;
  const ip = event.destination_ip;
  const port = event.port != null ? `:${event.port}` : '';
  if (host && ip) return `${host} (${ip})${port}`;
  if (host || ip) return `${host || ip}${port}`;
  return '—';
}

export function orDash(value) {
  return value === null || value === undefined || value === '' ? '—' : value;
}
