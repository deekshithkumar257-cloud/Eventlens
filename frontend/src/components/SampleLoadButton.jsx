import { useState } from 'react';
import { api } from '../services/api';
import { formatCount } from '../services/format';
import { InlineMessage } from './StatusMessage';

/** Loads the bundled synthetic sample dataset via the backend. Safe to click repeatedly. */
export default function SampleLoadButton({ onLoaded, variant = 'primary' }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleClick() {
    setBusy(true);
    setError(null);
    try {
      const data = await api.loadSample();
      setResult(data);
      onLoaded?.(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <button type="button" onClick={handleClick} disabled={busy} className={variant === 'primary' ? 'btn-primary' : 'btn-secondary'}>
        {busy && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-cyan-200/40 border-t-cyan-200" aria-hidden="true" />}
        {busy ? 'Loading sample logs…' : 'Load sample logs'}
      </button>
      {result && (
        <InlineMessage tone="success">
          Sample processed: {formatCount(result.inserted_events)} new events stored,{' '}
          {formatCount(result.duplicate_events)} already present, {formatCount(result.new_alerts)} new alerts
          ({formatCount(result.total_alerts)} total).
        </InlineMessage>
      )}
      {error && <InlineMessage tone="warning">Could not load sample logs: {error}</InlineMessage>}
    </div>
  );
}
