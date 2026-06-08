/**
 * App-level feedback primitives: non-blocking toasts + a promise-based confirm,
 * replacing jarring native alert()/window.confirm(). Event-based so any module
 * can call `toast(...)` / `await confirmDialog(...)` without context plumbing;
 * <FeedbackHost/> is mounted once and renders everything via a body portal.
 */

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import './feedback_host.css';

type ToastType = 'success' | 'error' | 'info';
let _id = 0;

/** Show a transient toast. */
export function toast(message: string, type: ToastType = 'info') {
  window.dispatchEvent(new CustomEvent('brubru-toast', { detail: { message, type } }));
}

interface ConfirmOpts {
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

/** Ask for confirmation; resolves true/false. Replaces window.confirm(). */
export function confirmDialog(message: string, opts: ConfirmOpts = {}): Promise<boolean> {
  return new Promise((resolve) => {
    window.dispatchEvent(new CustomEvent('brubru-confirm', { detail: { message, opts, resolve } }));
  });
}

interface ToastItem { id: number; message: string; type: ToastType; }
interface ConfirmState { message: string; opts: ConfirmOpts; resolve: (v: boolean) => void; }

export const FeedbackHost = () => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);

  useEffect(() => {
    const onToast = (e: Event) => {
      const { message, type } = (e as CustomEvent).detail;
      const id = ++_id;
      setToasts((t) => [...t, { id, message, type }]);
      window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
    };
    const onConfirm = (e: Event) => setConfirm((e as CustomEvent).detail);
    window.addEventListener('brubru-toast', onToast);
    window.addEventListener('brubru-confirm', onConfirm);
    return () => {
      window.removeEventListener('brubru-toast', onToast);
      window.removeEventListener('brubru-confirm', onConfirm);
    };
  }, []);

  const closeConfirm = (val: boolean) => { confirm?.resolve(val); setConfirm(null); };

  // Escape cancels the confirm.
  useEffect(() => {
    if (!confirm) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeConfirm(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [confirm]);

  return createPortal(
    <>
      <div className="toast-host" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.type}`} role="status">{t.message}</div>
        ))}
      </div>

      {confirm && (
        <div className="confirm-overlay" role="dialog" aria-modal="true" onClick={() => closeConfirm(false)}>
          <div className="confirm-box" onClick={(e) => e.stopPropagation()}>
            <p className="confirm-box__msg">{confirm.message}</p>
            <div className="confirm-box__actions">
              <button type="button" className="confirm-box__cancel" onClick={() => closeConfirm(false)}>
                {confirm.opts.cancelLabel || 'Cancel'}
              </button>
              <button
                type="button"
                className={`confirm-box__ok ${confirm.opts.danger ? 'confirm-box__ok--danger' : ''}`}
                onClick={() => closeConfirm(true)}
                autoFocus
              >
                {confirm.opts.confirmLabel || 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>,
    document.body,
  );
};
