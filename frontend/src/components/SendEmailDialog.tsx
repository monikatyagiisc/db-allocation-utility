import { useEffect, useState, type FormEvent } from 'react';
import {
  getEmailStatus,
  sendCustomEmail,
  sendExpiryDigestEmail,
  notifyRecordEmail,
  type KpiCategory,
} from '../api';

export type EmailMode =
  | { type: 'custom'; defaultTo?: string; defaultSubject?: string; defaultBody?: string }
  | { type: 'record'; recordId: number; defaultTo?: string; databaseName?: string }
  | { type: 'digest'; category: KpiCategory; databaseType?: string; title?: string };

type Props = {
  open: boolean;
  mode: EmailMode | null;
  onClose: () => void;
  onSent?: (message: string) => void;
};

export default function SendEmailDialog({ open, mode, onClose, onSent }: Props) {
  const [to, setTo] = useState('');
  const [cc, setCc] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [extraMessage, setExtraMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [configured, setConfigured] = useState(false);
  const [emailHint, setEmailHint] = useState<string | null>(null);
  const [provider, setProvider] = useState<string>('smtp');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setChecking(true);
    setError('');
    getEmailStatus()
      .then((s) => {
        setConfigured(s.configured);
        setEmailHint(s.hint);
        setProvider(s.provider);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not check email status'))
      .finally(() => setChecking(false));
  }, [open]);

  useEffect(() => {
    if (!open || !mode) return;
    if (mode.type === 'custom') {
      setTo(mode.defaultTo ?? '');
      setSubject(mode.defaultSubject ?? '');
      setBody(mode.defaultBody ?? '');
      setExtraMessage('');
    } else if (mode.type === 'record') {
      setTo(mode.defaultTo ?? '');
      setSubject(`DB allocation: ${mode.databaseName ?? 'database'}`);
      setBody('');
      setExtraMessage('');
    } else {
      setTo('');
      setCc('');
      setSubject('');
      setBody('');
      setExtraMessage('');
    }
  }, [open, mode]);

  if (!open || !mode) return null;

  const title =
    mode.type === 'record'
      ? 'Email assignee'
      : mode.type === 'digest'
        ? `Email report${mode.title ? `: ${mode.title}` : ''}`
        : 'Send email';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!configured) return;
    setLoading(true);
    setError('');
    const toList = to
      .split(/[,;]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const ccList = cc
      .split(/[,;]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      let result: { message: string };
      if (mode.type === 'custom') {
        result = await sendCustomEmail({
          to: toList,
          cc: ccList,
          subject,
          body: body || extraMessage,
        });
      } else if (mode.type === 'record') {
        result = await notifyRecordEmail(mode.recordId, {
          to: toList[0] || undefined,
          message: extraMessage || body || undefined,
        });
      } else {
        result = await sendExpiryDigestEmail({
          category: mode.category,
          database_type: mode.databaseType,
          to: toList,
          cc: ccList,
          message: extraMessage || undefined,
        });
      }
      onSent?.(result.message);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send email');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" role="presentation" onClick={loading ? undefined : onClose}>
      <div
        className="modal-dialog modal-dialog-wide send-email-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="send-email-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header-row">
          <h2 id="send-email-title">{title}</h2>
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

        {checking && <p className="modal-loading">Checking email configuration…</p>}

        {!checking && !configured && (
          <div className="alert alert-error">
            Email is not configured on the server. Add Microsoft Graph settings to{' '}
            <code>backend/.env</code> (see README → Email via Microsoft Outlook).
            {emailHint ? <p style={{ marginTop: '0.5rem', marginBottom: 0 }}>{emailHint}</p> : null}
          </div>
        )}

        {!checking && configured && (
          <p className="modal-description">
            Sends via Microsoft Outlook / Office 365
            {provider === 'graph' ? ' (Graph API)' : ' (SMTP)'}.
            {emailHint ? ` ${emailHint}` : ''}
          </p>
        )}

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="edit-form-grid">
            <label className="edit-form-field edit-form-field-wide">
              <span>
                To (comma-separated)
                {mode.type === 'record' && ' — leave blank to use assignee email if present'}
              </span>
              <input
                type="text"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder={
                  mode.type === 'record' ? 'assignee@company.com (optional)' : 'colleague@company.com'
                }
                required={mode.type !== 'record'}
                disabled={loading || !configured}
              />
            </label>
            {mode.type !== 'record' && (
              <label className="edit-form-field edit-form-field-wide">
                <span>CC (optional)</span>
                <input
                  type="text"
                  value={cc}
                  onChange={(e) => setCc(e.target.value)}
                  disabled={loading || !configured}
                />
              </label>
            )}
            {mode.type === 'custom' && (
              <>
                <label className="edit-form-field edit-form-field-wide">
                  <span>Subject</span>
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    required
                    disabled={loading || !configured}
                  />
                </label>
                <label className="edit-form-field edit-form-field-wide">
                  <span>Message</span>
                  <textarea
                    rows={8}
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    required
                    disabled={loading || !configured}
                  />
                </label>
              </>
            )}
            {(mode.type === 'record' || mode.type === 'digest') && (
              <label className="edit-form-field edit-form-field-wide">
                <span>Additional note (optional)</span>
                <textarea
                  rows={4}
                  value={extraMessage}
                  onChange={(e) => setExtraMessage(e.target.value)}
                  placeholder="Optional message included in the email"
                  disabled={loading || !configured}
                />
              </label>
            )}
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading || !configured}>
              {loading ? 'Sending…' : 'Send email'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
