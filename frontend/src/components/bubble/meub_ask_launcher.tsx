/**
 * MEUB "Ask Brubru" launcher — a single persistent, context-aware entry point
 * into Chat from anywhere in My EU Bubble. One floating button pinned to the
 * bottom-right of the whole MEUB shell (not per-tab), so Chat is always one
 * click away when a user is lost — without printing a button on every surface.
 *
 * Opening it from a given tab pre-seeds the question with that context. "Ask"
 * navigates to /main with the query auto-fired, so the answer streams without
 * an extra click. Portaled to document.body so it escapes the AnimatedPage
 * (framer-motion) transform and pins to the viewport, not the page box.
 */

import { useEffect, useRef, useState } from 'react';
import { chatReturnParams } from '../../utils/chat_return';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiRobotOutline, mdiClose, mdiSend, mdiCreation } from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import './meub_ask_launcher.css';

interface MeubAskLauncherProps {
  /** Human label of the active tab, used to seed the question context. */
  tabLabel: string;
}

export const MeubAskLauncher = ({ tabLabel }: MeubAskLauncherProps) => {
  const routerLocation = useLocation();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const popRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus the input when the popover opens.
  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  // Close on Escape or outside click (deferred so the opening click doesn't close it).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onDown = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    const id = window.setTimeout(() => document.addEventListener('mousedown', onDown), 0);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
      window.clearTimeout(id);
    };
  }, [open]);

  if (!isAuthenticated) return null;

  const ask = (query: string) => {
    const text = (query || '').trim();
    if (!text) return;
    setOpen(false);
    const params = new URLSearchParams({ q: text, autofire: '1' });
    Object.entries(chatReturnParams(`${routerLocation.pathname}${routerLocation.search}`, tabLabel))
      .forEach(([k, v]) => params.set(k, v));
    navigate(`/chat?${params.toString()}`);
  };

  const suggestions = [
    t('bubble.ask.suggestTab', { tab: tabLabel, defaultValue: `What is ${tabLabel} and how do I use it?` }),
    t('bubble.ask.suggestPi', 'What is happening on my policy interests right now?'),
  ];

  return createPortal(
    <div className="meub-ask">
      {open && (
        <div
          className="meub-ask__pop"
          ref={popRef}
          role="dialog"
          aria-label={t('bubble.ask.title', 'Ask Brubru')}
        >
          <div className="meub-ask__pop-head">
            <Icon path={mdiRobotOutline} size={0.85} />
            <span className="meub-ask__pop-title">{t('bubble.ask.title', 'Ask Brubru')}</span>
            <button
              type="button"
              className="meub-ask__close"
              onClick={() => setOpen(false)}
              aria-label={t('common.close', 'Close')}
            >
              <Icon path={mdiClose} size={0.7} />
            </button>
          </div>

          <p className="meub-ask__context">
            {t('bubble.ask.context', {
              tab: tabLabel,
              defaultValue: `You're on ${tabLabel}. Ask me anything about it, or the EU.`,
            })}
          </p>

          <div className="meub-ask__suggestions">
            {suggestions.map((s, i) => (
              <button key={i} type="button" className="meub-ask__chip" onClick={() => ask(s)}>
                <Icon path={mdiCreation} size={0.5} />
                <span>{s}</span>
              </button>
            ))}
          </div>

          <form className="meub-ask__form" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
            <input
              ref={inputRef}
              className="meub-ask__input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t('bubble.ask.placeholder', 'Ask anything about the EU…') as string}
            />
            <button
              type="submit"
              className="meub-ask__send"
              aria-label={t('bubble.ask.send', 'Ask')}
              disabled={!q.trim()}
            >
              <Icon path={mdiSend} size={0.8} />
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className={`meub-ask__fab ${open ? 'is-open' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={t('bubble.ask.fab', 'Ask Brubru')}
      >
        <Icon path={open ? mdiClose : mdiRobotOutline} size={1} />
        <span className="meub-ask__fab-label">{t('bubble.ask.fab', 'Ask Brubru')}</span>
      </button>
    </div>,
    document.body,
  );
};
