import { PRIORITY_STYLES } from '../services/format';

export default function PriorityBadge({ priority }) {
  const style = PRIORITY_STYLES[priority] || 'border-slate-600 bg-slate-800 text-slate-300';
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold ${style}`}>
      {priority} priority
    </span>
  );
}
