import { useEffect, useState } from 'react';
import { getKpiList, type DatabaseRecord, type KpiCategory } from '../api';

type Props = {
  category: KpiCategory | null;
  databaseType?: string | null;
  onClose: () => void;
  onEmailReport?: (category: KpiCategory, title: string) => void;
};

export default function KpiDetailDialog({ category, databaseType, onClose, onEmailReport }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [title, setTitle] = useState('');
  const [records, setRecords] = useState<DatabaseRecord[]>([]);

  useEffect(() => {
    if (!category) return;
    setLoading(true);
    setError('');
    getKpiList(category, databaseType || undefined)
      .then((res) => {
        setTitle(res.title);
        setRecords(res.records);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load list'))
      .finally(() => setLoading(false));
  }, [category, databaseType]);

  if (!category) return null;

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal-dialog modal-dialog-wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kpi-detail-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header-row">
          <h2 id="kpi-detail-title">{title || 'Database list'}</h2>
          <button type="button" className="btn btn-ghost modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {loading && <p className="modal-loading">Loading…</p>}
        {error && <div className="alert alert-error">{error}</div>}
        {!loading && !error && (
          <>
            <p className="modal-count">
              {records.length} database{records.length === 1 ? '' : 's'}
            </p>
            {records.length === 0 ? (
              <p className="chart-empty">No databases match this KPI.</p>
            ) : (
              <div className="kpi-list-wrap">
                <table className="kpi-list-table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Database</th>
                      <th>Assignee</th>
                      <th>Team</th>
                      <th>End Date</th>
                      <th>Status</th>
                      <th>Prod Mirror</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((r) => (
                      <tr key={r.id}>
                        <td>{r.database_type ?? '—'}</td>
                        <td>{r.database_name}</td>
                        <td>{r.assignee ?? '—'}</td>
                        <td>{r.team ?? '—'}</td>
                        <td>{r.end_date?.slice(0, 10) ?? '—'}</td>
                        <td>{r.status ?? '—'}</td>
                        <td>{r.prod_mirror ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
        <div className="modal-actions">
          {onEmailReport && category && !loading && !error && records.length > 0 && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onEmailReport(category, title || 'Database list')}
            >
              Email report
            </button>
          )}
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
