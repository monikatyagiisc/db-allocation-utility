import { useEffect, useState, type FormEvent } from 'react';

const CONFIRM_WORD = 'DELETE';

type ConfirmDeleteDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmDeleteDialog({
  open,
  title,
  description,
  confirmLabel = 'Delete',
  onConfirm,
  onCancel,
}: ConfirmDeleteDialogProps) {
  const [input, setInput] = useState('');

  useEffect(() => {
    if (open) setInput('');
  }, [open]);

  if (!open) return null;

  const canConfirm = input === CONFIRM_WORD;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (canConfirm) onConfirm();
  };

  return (
    <div className="modal-overlay" role="presentation" onClick={onCancel}>
      <div
        className="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-delete-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-delete-title">{title}</h2>
        <p className="modal-description">{description}</p>
        <p className="modal-instruction">
          Type <strong>{CONFIRM_WORD}</strong> below to confirm:
        </p>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            className="modal-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={CONFIRM_WORD}
            autoFocus
            autoComplete="off"
            spellCheck={false}
          />
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn btn-danger" disabled={!canConfirm}>
              {confirmLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
