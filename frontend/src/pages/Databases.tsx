import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  clearAllDatabases,
  deleteDatabase,
  exportExcel,
  importExcel,
  getJiraStatus,
  listDatabases,
  updateDatabase,
  type DatabaseRecord,
  type DatabaseSortField,
  type ExpiryFilter,
  type SortOrder,
} from '../api';
import ConfirmDeleteDialog from '../components/ConfirmDeleteDialog';
import EditDatabaseDialog from '../components/EditDatabaseDialog';
import JiraCommentDialog from '../components/JiraCommentDialog';
import SendEmailDialog, { type EmailMode } from '../components/SendEmailDialog';
import { DATABASE_FIELDS } from '../databaseFields';
import { useAuth } from '../AuthContext';
import type { KpiCategory } from '../api';

function guessAssigneeEmail(assignee: string | null | undefined): string | undefined {
  if (!assignee) return undefined;
  const t = assignee.trim();
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t)) return t;
  const angle = t.match(/<([^>]+@[^>]+)>/);
  if (angle) return angle[1];
  return undefined;
}

type PendingDelete =
  | { type: 'record'; id: number; name: string }
  | { type: 'clear-all' }
  | null;

const DEFAULT_SORT: DatabaseSortField = 'serial_number';
const DEFAULT_SORT_ORDER: SortOrder = 'asc';

const FIELDS = DATABASE_FIELDS;

export default function Databases() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const typeFilter = searchParams.get('type') || undefined;
  const expiryFromUrl = searchParams.get('expiry') as ExpiryFilter | null;
  const initialExpiry: ExpiryFilter =
    expiryFromUrl === 'expiring_this_month' || expiryFromUrl === 'expiring_next_month'
      ? expiryFromUrl
      : '';
  const [records, setRecords] = useState<DatabaseRecord[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<DatabaseRecord>>({});
  const [saving, setSaving] = useState(false);
  const [replaceOnImport, setReplaceOnImport] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);
  const [sortBy, setSortBy] = useState<DatabaseSortField>(DEFAULT_SORT);
  const [sortOrder, setSortOrder] = useState<SortOrder>(DEFAULT_SORT_ORDER);
  const [expiryFilter, setExpiryFilter] = useState<ExpiryFilter>(initialExpiry);
  const [emailMode, setEmailMode] = useState<EmailMode | null>(null);
  const [jiraRecord, setJiraRecord] = useState<DatabaseRecord | null>(null);
  const [jiraBaseUrl, setJiraBaseUrl] = useState<string | null>(null);

  const monthName = new Date().toLocaleString('default', { month: 'long', year: 'numeric' });
  const nextMonthDate = new Date();
  nextMonthDate.setMonth(nextMonthDate.getMonth() + 1);
  const nextMonthName = nextMonthDate.toLocaleString('default', {
    month: 'long',
    year: 'numeric',
  });

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const data = await listDatabases(
        search || undefined,
        sortBy,
        sortOrder,
        typeFilter,
        expiryFilter || undefined,
      );
      setRecords(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [user, search, sortBy, sortOrder, typeFilter, expiryFilter]);

  const toggleColumnSort = (field: DatabaseSortField) => {
    if (sortBy === field) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const sortIndicator = (field: DatabaseSortField) => {
    if (sortBy !== field) return ' ↕';
    return sortOrder === 'asc' ? ' ↑' : ' ↓';
  };

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!user) return;
    getJiraStatus()
      .then((s) => setJiraBaseUrl(s.base_url))
      .catch(() => setJiraBaseUrl(null));
  }, [user]);

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    setMessage('');
    try {
      const result = await importExcel(file, replaceOnImport);
      setMessage(result.message);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    }
    e.target.value = '';
  };

  const handleExport = async () => {
    setError('');
    try {
      await exportExcel();
      setMessage('Export downloaded.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  const startEdit = (record: DatabaseRecord) => {
    setEditingId(record.id);
    setDraft({ ...record });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraft({});
  };

  const saveEdit = async () => {
    if (editingId === null || saving) return;
    setError('');
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      for (const { key, type } of FIELDS) {
        const raw = draft[key];
        if (raw === undefined) continue;
        if (type === 'number') {
          payload[key] = raw === '' || raw === null ? null : Number(raw);
        } else {
          payload[key] = raw === '' ? null : raw;
        }
      }
      await updateDatabase(editingId, payload);
      setMessage('Record updated.');
      cancelEdit();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const editingRecord = editingId !== null ? records.find((r) => r.id === editingId) : null;

  const requestDeleteRecord = (id: number, name: string) => {
    setPendingDelete({ type: 'record', id, name });
  };

  const requestClearAll = () => {
    setPendingDelete({ type: 'clear-all' });
  };

  const cancelPendingDelete = () => setPendingDelete(null);

  const executePendingDelete = async () => {
    if (!pendingDelete) return;
    setError('');
    setMessage('');
    try {
      if (pendingDelete.type === 'record') {
        await deleteDatabase(pendingDelete.id);
        setMessage(`Record "${pendingDelete.name}" deleted.`);
        if (editingId === pendingDelete.id) cancelEdit();
      } else {
        const result = await clearAllDatabases();
        setMessage(result.message);
        cancelEdit();
      }
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : pendingDelete.type === 'record'
            ? 'Delete failed'
            : 'Failed to clear all data',
      );
    }
  };

  if (!user) {
    return (
      <div className="page">
        <p>Please log in to manage database records.</p>
      </div>
    );
  }

  const deleteDialog =
    pendingDelete?.type === 'record' ? (
      <ConfirmDeleteDialog
        open
        title="Delete database record"
        description={`Permanently delete "${pendingDelete.name}"? This cannot be undone.`}
        confirmLabel="Delete record"
        onConfirm={executePendingDelete}
        onCancel={cancelPendingDelete}
      />
    ) : pendingDelete?.type === 'clear-all' ? (
      <ConfirmDeleteDialog
        open
        title="Clear all data"
        description="Permanently delete ALL database allocation records from the database. This cannot be undone."
        confirmLabel="Clear all"
        onConfirm={executePendingDelete}
        onCancel={cancelPendingDelete}
      />
    ) : null;

  return (
    <div className="page databases-page">
      {deleteDialog}
      <EditDatabaseDialog
        open={editingId !== null}
        databaseName={String(draft.database_name ?? editingRecord?.database_name ?? 'Record')}
        draft={draft}
        saving={saving}
        onChange={setDraft}
        onSave={saveEdit}
        onCancel={cancelEdit}
      />
      <SendEmailDialog
        open={emailMode !== null}
        mode={emailMode}
        onClose={() => setEmailMode(null)}
        onSent={(msg) => setMessage(msg)}
      />
      <JiraCommentDialog
        open={jiraRecord !== null}
        record={jiraRecord}
        onClose={() => setJiraRecord(null)}
        onSent={(msg) => {
          setMessage(msg);
          load();
        }}
      />
      <div className="page-header">
        <h1>Database records{typeFilter ? ` — ${typeFilter}` : ''}</h1>
        <div className="toolbar">
          <div className="toolbar-filters">
            <input
              type="search"
              placeholder="Search database, assignee, team…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="search-input"
            />
            <label className="sort-control">
              Expiration
              <select
                value={expiryFilter}
                onChange={(e) => {
                  const value = e.target.value as ExpiryFilter;
                  setExpiryFilter(value);
                  if (value && sortBy !== 'end_date') {
                    setSortBy('end_date');
                    setSortOrder('asc');
                  }
                }}
              >
                <option value="">All end dates</option>
                <option value="expiring_this_month">Expiring in {monthName}</option>
                <option value="expiring_next_month">Expiring in {nextMonthName}</option>
              </select>
            </label>
            <label className="sort-control">
              Sort by
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as DatabaseSortField)}
              >
                {FIELDS.map((f) => (
                  <option key={f.key} value={f.key}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="sort-control">
              Order
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as SortOrder)}
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </label>
            <label className="checkbox-label toolbar-checkbox">
              <input
                type="checkbox"
                checked={replaceOnImport}
                onChange={(e) => setReplaceOnImport(e.target.checked)}
              />
              Replace all on import
            </label>
          </div>
          <div className="toolbar-actions">
            {expiryFilter && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() =>
                  setEmailMode({
                    type: 'digest',
                    category: expiryFilter as KpiCategory,
                    databaseType: typeFilter,
                    title: `Expiring — ${expiryFilter === 'expiring_this_month' ? monthName : nextMonthName}`,
                  })
                }
                title="Email the filtered expiry list via Outlook"
              >
                Email expiry list
              </button>
            )}
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setEmailMode({ type: 'custom' })}
              title="Send a custom email via Outlook"
            >
              Send email
            </button>
            <label className="btn btn-secondary file-btn">
              Upload Excel
              <input type="file" accept=".xlsx,.xlsm" hidden onChange={handleImport} />
            </label>
            <button type="button" className="btn btn-primary" onClick={handleExport}>
              Export Excel
            </button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={requestClearAll}
              disabled={loading}
              title="Permanently delete all database records"
            >
              Clear all data
            </button>
          </div>
        </div>
      </div>

      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <p>Loading…</p>
      ) : records.length === 0 ? (
        <p className="empty">No records yet. Upload an Excel file to get started.</p>
      ) : (
        <>
          <p className="table-hint">
            Click <strong>Edit</strong> or double-click a row to open the edit dialog. Click a column header to sort. Scroll horizontally for all columns; long comments scroll inside the Comments cell.
          </p>
          <div className="table-wrap">
          <table className="data-table">
            <colgroup>
              <col className="col-actions" />
              {FIELDS.map((f) => (
                <col key={f.key} className={`col-${f.key}`} />
              ))}
            </colgroup>
            <thead>
              <tr className="data-table-header-row">
                <th className="actions-col" scope="col">
                  Actions
                </th>
                {FIELDS.map((f) => (
                  <th
                    key={f.key}
                    scope="col"
                    className={`col-${f.key}${f.wide ? ' col-comments' : ''}`}
                  >
                    <button
                      type="button"
                      className={`sort-header${sortBy === f.key ? ' sort-header-active' : ''}`}
                      onClick={() => toggleColumnSort(f.key)}
                      title={f.headerTitle ?? `Sort by ${f.label}`}
                    >
                      {f.label}
                      <span className="sort-indicator">{sortIndicator(f.key)}</span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr
                  key={record.id}
                  className={editingId === record.id ? 'row-editing' : ''}
                  onDoubleClick={() => startEdit(record)}
                  title="Double-click to edit"
                >
                  <td
                    className="actions-cell actions-col"
                    onDoubleClick={(e) => e.stopPropagation()}
                  >
                    <div className="actions-buttons">
                      <button
                          type="button"
                          className="btn btn-sm btn-primary"
                          onClick={() => startEdit(record)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-secondary"
                          onClick={() => setJiraRecord(record)}
                          title="Add a comment to the linked JIRA issue"
                        >
                          JIRA
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-secondary"
                          onClick={() =>
                            setEmailMode({
                              type: 'record',
                              recordId: record.id,
                              defaultTo: guessAssigneeEmail(record.assignee),
                              databaseName: record.database_name,
                            })
                          }
                          title="Email assignee via Outlook"
                        >
                          Email
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          onClick={() => requestDeleteRecord(record.id, record.database_name)}
                        >
                          Delete
                        </button>
                    </div>
                  </td>
                  {FIELDS.map(({ key, wide }) => (
                    <td
                      key={key}
                      className={wide ? 'col-comments' : `col-${key}`}
                      title={!wide && record[key] ? String(record[key]) : undefined}
                    >
                      {key === 'jira_key' ? (
                          record.jira_key ? (
                            jiraBaseUrl ? (
                              <a
                                href={`${jiraBaseUrl}/browse/${record.jira_key}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="jira-key-link"
                              >
                                {record.jira_key}
                              </a>
                            ) : (
                              record.jira_key
                            )
                          ) : (
                            '—'
                          )
                        ) : key === 'start_date' || key === 'end_date' ? (
                          record[key]?.slice(0, 10) ?? '—'
                        ) : wide ? (
                        <div className="cell-comments-scroll">
                          {String(record[key] ?? '—')}
                        </div>
                      ) : (
                        <span className="cell-ellipsis">{String(record[key] ?? '—')}</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  );
}
