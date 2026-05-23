import { useEffect, type FormEvent } from 'react';
import { DATABASE_FIELDS } from '../databaseFields';
import type { DatabaseRecord } from '../api';

type Props = {
  open: boolean;
  databaseName: string;
  draft: Partial<DatabaseRecord>;
  saving?: boolean;
  onChange: (draft: Partial<DatabaseRecord>) => void;
  onSave: () => void;
  onCancel: () => void;
};

function fieldValue(draft: Partial<DatabaseRecord>, key: keyof DatabaseRecord): string {
  const v = draft[key];
  if (v === null || v === undefined) return '';
  return String(v);
}

export default function EditDatabaseDialog({
  open,
  databaseName,
  draft,
  saving = false,
  onChange,
  onSave,
  onCancel,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !saving) onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, saving, onCancel]);

  if (!open) return null;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!saving) onSave();
  };

  return (
    <div className="modal-overlay" role="presentation" onClick={saving ? undefined : onCancel}>
      <div
        className="modal-dialog modal-dialog-wide edit-database-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-database-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header-row">
          <h2 id="edit-database-title">Edit record</h2>
          <button
            type="button"
            className="btn btn-ghost modal-close"
            onClick={onCancel}
            disabled={saving}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <p className="modal-description edit-database-subtitle">
          <strong>{databaseName}</strong>
          {draft.database_type ? ` · ${draft.database_type}` : null}
        </p>
        <form onSubmit={handleSubmit}>
          <div className="edit-form-grid">
            {DATABASE_FIELDS.map(({ key, label, type, wide, headerTitle }) => (
              <label
                key={key}
                className={`edit-form-field${wide ? ' edit-form-field-wide' : ''}`}
                title={headerTitle}
              >
                <span>{label}</span>
                {type === 'number' ? (
                  <input
                    type="number"
                    value={fieldValue(draft, key)}
                    onChange={(e) =>
                      onChange({
                        ...draft,
                        [key]: e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                    disabled={saving}
                  />
                ) : type === 'date' ? (
                  <input
                    type="date"
                    value={fieldValue(draft, key).slice(0, 10)}
                    onChange={(e) =>
                      onChange({ ...draft, [key]: e.target.value || null })
                    }
                    disabled={saving}
                  />
                ) : wide ? (
                  <textarea
                    rows={4}
                    value={fieldValue(draft, key)}
                    onChange={(e) =>
                      onChange({ ...draft, [key]: e.target.value || null })
                    }
                    disabled={saving}
                  />
                ) : (
                  <input
                    type="text"
                    value={fieldValue(draft, key)}
                    onChange={(e) =>
                      onChange({ ...draft, [key]: e.target.value || null })
                    }
                    disabled={saving}
                  />
                )}
              </label>
            ))}
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
