import { useRef, useState } from 'react';
import { api } from '../services/api';
import { formatCount } from '../services/format';
import SampleLoadButton from '../components/SampleLoadButton';
import { ErrorState, InlineMessage } from '../components/StatusMessage';

const MAX_UPLOAD_MB = 5;
const MAX_RECORDS = 10000;

export default function UploadPage() {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [fileError, setFileError] = useState(null);

  function handleFileChange(event) {
    const selected = event.target.files?.[0] ?? null;
    setResult(null);
    setError(null);
    setFileError(null);
    setFile(null);
    if (!selected) return;
    const lower = selected.name.toLowerCase();
    if (!lower.endsWith('.csv') && !lower.endsWith('.json')) {
      setFileError('Unsupported file type. Choose a .csv or .json file.');
      return;
    }
    if (selected.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setFileError(`This file is larger than the ${MAX_UPLOAD_MB} MB limit.`);
      return;
    }
    if (selected.size === 0) {
      setFileError('This file is empty.');
      return;
    }
    setFile(selected);
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.uploadLogs(file));
    } catch (err) {
      setError(err);
    } finally {
      setUploading(false);
    }
  }

  function reset() {
    setFile(null);
    setResult(null);
    setError(null);
    setFileError(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">Upload Logs</h1>
        <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-400">
          Add synthetic CSV or JSON events. Each record is validated, normalized, stored in SQLite, and checked against the detection rules.
          Use synthetic data only.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_340px]">
        <section aria-label="Upload form" className="panel space-y-5 p-6">
          <form onSubmit={handleUpload} className="space-y-4">
            <label htmlFor="log-file" className="block text-sm font-medium text-slate-200">Log file</label>
            <input
              ref={inputRef}
              id="log-file"
              type="file"
              accept=".csv,.json,text/csv,application/json"
              onChange={handleFileChange}
              disabled={uploading}
              className="block w-full cursor-pointer rounded-lg border border-dashed border-slate-600 bg-slate-950/60 px-4 py-6 text-sm text-slate-400 file:mr-4 file:rounded-md file:border-0 file:bg-cyan-500/20 file:px-3 file:py-2 file:text-sm file:font-medium file:text-cyan-100 hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-60"
            />
            {file && (
              <p className="text-sm text-slate-300">
                Selected: <span className="font-mono text-slate-100">{file.name}</span>{' '}
                <span className="text-slate-500">({Math.max(1, Math.round(file.size / 1024))} KB)</span>
              </p>
            )}
            {fileError && <InlineMessage tone="warning">{fileError}</InlineMessage>}

            <div className="flex flex-wrap gap-3">
              <button type="submit" className="btn-primary" disabled={!file || uploading}>
                {uploading && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-cyan-200/40 border-t-cyan-200" aria-hidden="true" />}
                {uploading ? 'Validating and analyzing…' : 'Upload and analyze'}
              </button>
              <button type="button" className="btn-secondary" onClick={reset} disabled={uploading}>Clear</button>
            </div>
          </form>

          <div className="border-t border-slate-800 pt-5">
            <h2 className="text-sm font-semibold text-slate-100">Or load the synthetic sample</h2>
            <p className="mt-1 text-sm text-slate-400">
              Loads <span className="font-mono text-slate-300">data/sample_logs.json</span> on the server. Repeating it does not create duplicates.
            </p>
            <div className="mt-3">
              <SampleLoadButton variant="secondary" />
            </div>
          </div>

          {error && (
            <ErrorState
              title="The upload was not accepted"
              error={error}
            />
          )}

          {result && <ImportSummary result={result} />}
        </section>

        <aside className="space-y-4">
          <div className="panel space-y-3 p-5 text-sm leading-relaxed text-slate-300">
            <h2 className="panel-title">Accepted input</h2>
            <ul className="list-disc space-y-2 pl-5 text-slate-400">
              <li><span className="text-slate-200">CSV</span> with a header row. Required columns: <code className="font-mono text-xs text-slate-300">timestamp</code>, <code className="font-mono text-xs text-slate-300">event_type</code>.</li>
              <li><span className="text-slate-200">JSON</span> as an array of event objects, or an object with an <code className="font-mono text-xs text-slate-300">events</code> array.</li>
              <li>Event types: <code className="font-mono text-xs text-slate-300">login_success</code>, <code className="font-mono text-xs text-slate-300">login_failure</code>, <code className="font-mono text-xs text-slate-300">network_connection</code>.</li>
              <li>Timestamps: ISO-8601 (UTC assumed when no offset is given) or Unix seconds.</li>
              <li>Limits: {MAX_UPLOAD_MB} MB and {formatCount(MAX_RECORDS)} records per file.</li>
            </ul>
          </div>
          <div className="panel space-y-3 p-5 text-sm leading-relaxed text-slate-400">
            <h2 className="panel-title">How it is handled</h2>
            <ul className="list-disc space-y-2 pl-5">
              <li>Files are processed in memory. Uploaded content is not saved to disk.</li>
              <li>Malformed rows are skipped and listed with their row number; valid rows are still stored.</li>
              <li>Identical events are stored once, so re-uploading the same file adds nothing.</li>
              <li>Log text is treated as data only. It is never executed.</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}

function ImportSummary({ result }) {
  const stats = [
    ['Records in file', result.total_records],
    ['New events stored', result.inserted_events],
    ['Already stored (duplicates)', result.duplicate_events],
    ['Rows rejected', result.rejected_records],
    ['New alerts', result.new_alerts],
    ['Total alerts now', result.total_alerts],
  ];
  return (
    <div className="space-y-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-semibold text-emerald-200">
          Processed {result.file_name} ({result.source_format.toUpperCase()})
        </div>
        <div className="font-mono text-xs text-slate-500">{result.import_id}</div>
      </div>
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {stats.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2.5">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-slate-100">{formatCount(value)}</dd>
          </div>
        ))}
      </dl>
      {result.rejected_details.length > 0 && (
        <div>
          <div className="mb-2 text-sm font-medium text-amber-200">Rejected rows</div>
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="min-w-full divide-y divide-slate-800 text-sm">
              <thead className="bg-slate-900/80">
                <tr>
                  <th className="th">Row</th>
                  <th className="th">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {result.rejected_details.map((item) => (
                  <tr key={`${item.row}-${item.reason}`}>
                    <td className="td font-mono text-xs">{item.row}</td>
                    <td className="td">{item.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.rejected_records > result.rejected_details.length && (
            <p className="mt-2 text-xs text-slate-500">Showing the first {result.rejected_details.length} of {formatCount(result.rejected_records)} rejected rows.</p>
          )}
        </div>
      )}
      <p className="text-xs text-slate-500">
        Next: <a className="text-cyan-300 hover:underline" href="/alerts">review alerts</a> or <a className="text-cyan-300 hover:underline" href="/events">explore events</a>.
      </p>
    </div>
  );
}
