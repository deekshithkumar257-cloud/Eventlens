import { useState } from 'react';

/** Shows the original log record. Rendered as text, never executed or interpreted as HTML. */
export default function RawEvent({ raw, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="text-xs font-medium text-cyan-300 hover:text-cyan-200"
      >
        {open ? 'Hide original raw event' : 'Show original raw event'}
      </button>
      {open && (
        <pre className="mt-2 max-h-64 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-300">
          {JSON.stringify(raw, null, 2)}
        </pre>
      )}
    </div>
  );
}
