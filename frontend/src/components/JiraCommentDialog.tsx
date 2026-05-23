import { useEffect, useState, type FormEvent } from 'react';
import { addJiraCommentForRecord, getJiraStatus, type DatabaseRecord } from '../api';

type Props = {
  open: boolean;
  record: DatabaseRecord | null;
  onClose: () => void;
  onSent?: (message: string) => void;
};

export default function JiraCommentDialog({ open, record, onClose, onSent }: Props) {
  const [jiraKey, setJiraKey] = useState('');
  const [comment, setComment] = useState('');
  const [saveKey, setSaveKey] = useState(true);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [configured, setConfigured] = useState(false);
  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setChecking(true);
    setError('');
    getJiraStatus()
      .then((s) => {
        setConfigured(s.configured);
        setBaseUrl(s.base_url);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not check JIRA status'))
      .finally(() => setChecking(false));
  }, [open]);

  useEffect(() => {
    if (!open || !record) return;
    setJiraKey(record.jira_key ?? '');
    setComment('');
    setSaveKey(true);
  }, [open, record]);

  if (!open || !record) return null;

  const browseUrl =
    baseUrl && jiraKey.trim()
      ? `${baseUrl.replace(/\/$/, '')}/browse/${jiraKey.trim().toUpperCase()}`
      : null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!configured || !comment.trim()) return;
    setLoading(true);
    setError('');
    try {
      const result = await addJiraCommentForRecord(record.id, {
        comment: comment.trim(),
        jira_key: jiraKey.trim() || undefined,
        save_jira_key: saveKey,
      });
      onSent?.(result.message);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add JIRA comment');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" role="presentation" onClick={loading ? undefined : onClose}>
      <div
        className="modal-dialog modal-dialog-wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="jira-comment-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header-row">
          <h2 id="jira-comment-title">Add JIRA comment</h2>
          <button
            type="button"
            className="btn btn-ghost modal-close"
            onClick={onClose}
            disabled={loading}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <p className="modal-description">
          Database: <strong>{record.database_name}</strong>
        </p>

        {checking && <p className="modal-loading">Checking JIRA configuration…</p>}

        {!checking && !configured && (
          <div className="alert alert-error">
            JIRA is not configured. Set <code>JIRA_*</code> variables in <code>backend/.env</code> (see
            README).
          </div>
        )}

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="edit-form-grid">
            <label className="edit-form-field">
              <span>JIRA issue key</span>
              <input
                type="text"
                value={jiraKey}
                onChange={(e) => setJiraKey(e.target.value.toUpperCase())}
                placeholder="PROJ-123"
                required
                disabled={loading || !configured}
                pattern="[A-Za-z][A-Za-z0-9_]*-\d+"
                title="Format: PROJECT-123"
              />
            </label>
            {browseUrl && (
              <p className="edit-form-field-wide jira-browse-link">
                <a href={browseUrl} target="_blank" rel="noopener noreferrer">
                  Open {jiraKey.trim().toUpperCase()} in JIRA
                </a>
              </p>
            )}
            <label className="checkbox-label edit-form-field-wide">
              <input
                type="checkbox"
                checked={saveKey}
                onChange={(e) => setSaveKey(e.target.checked)}
                disabled={loading || !configured}
              />
              Save JIRA key on this database record
            </label>
            <label className="edit-form-field edit-form-field-wide">
              <span>Comment</span>
              <textarea
                rows={6}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Comment to post on the JIRA issue…"
                required
                disabled={loading || !configured}
              />
            </label>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading || !configured}>
              {loading ? 'Posting…' : 'Add comment to JIRA'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
