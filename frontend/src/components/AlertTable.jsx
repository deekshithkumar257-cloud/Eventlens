import { Link } from 'react-router-dom';
import PriorityBadge from './PriorityBadge';
import { formatUtc } from '../services/format';

export default function AlertTable({ alerts }) {
  return (
    <div className="panel overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-800">
        <thead className="bg-slate-900/80">
          <tr>
            <th className="th">Priority</th>
            <th className="th">Alert</th>
            <th className="th">Entity</th>
            <th className="th">Last seen</th>
            <th className="th text-right">Events</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80">
          {alerts.map((alert) => (
            <tr key={alert.alert_id} className="transition hover:bg-slate-800/40">
              <td className="td"><PriorityBadge priority={alert.priority} /></td>
              <td className="td min-w-64">
                <Link to={`/alerts/${alert.alert_id}`} className="font-medium text-slate-100 hover:text-cyan-300">
                  {alert.title}
                </Link>
                <div className="mt-0.5 text-xs text-slate-500">{alert.rule_name} · {alert.alert_id}</div>
              </td>
              <td className="td font-mono text-xs">
                {alert.entity_type === 'user' ? 'Account' : 'Source IP'}: {alert.entity_value}
              </td>
              <td className="td whitespace-nowrap text-xs">{formatUtc(alert.last_seen)}</td>
              <td className="td text-right tabular-nums">{alert.event_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
