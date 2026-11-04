// frontend/src/components/api_console/console_tip.tsx
// A small explanation that opens on hover, on keyboard focus and on tap, because a phone has no hover. It is drawn on
// document.body: the console's panes scroll and the page is animated, either of which would clip or misplace it.
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

const GAP = 8;
const EDGE = 8;
const CLOSE_DELAY_MS = 120;

interface Props {
  // What a screen reader says for the button: "More about Search words".
  label: string;
  children: ReactNode;
  // Words instead of the round "i": a term on the page that can be explained where it stands.
  term?: ReactNode;
}

export const ConsoleTip = ({ label, children, term }: Props) => {
  const id = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | null>(null);
  const staysClosed = useRef(false);
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  const cancelClose = () => {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  const close = useCallback(() => {
    cancelClose();
    setOpen(false);
    setPinned(false);
    setPosition(null);
  }, []);

  const closeSoon = () => {
    cancelClose();
    closeTimer.current = window.setTimeout(() => {
      setOpen(false);
      setPosition(null);
    }, CLOSE_DELAY_MS);
  };

  useLayoutEffect(() => {
    if (!open || !buttonRef.current || !popRef.current) return;
    const anchor = buttonRef.current.getBoundingClientRect();
    const pop = popRef.current.getBoundingClientRect();
    const roomBelow = window.innerHeight - anchor.bottom;
    const top = roomBelow >= pop.height + GAP + EDGE || anchor.top < pop.height + GAP + EDGE
      ? anchor.bottom + GAP
      : anchor.top - pop.height - GAP;
    const left = Math.min(Math.max(EDGE, anchor.left + anchor.width / 2 - pop.width / 2), window.innerWidth - pop.width - EDGE);
    setPosition({ top: Math.max(EDGE, top), left });
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        // Focus returns only from inside the box. Taken from elsewhere, it would open the tip again on the same key.
        const fromInside = popRef.current?.contains(document.activeElement);
        close();
        if (fromInside) {
          staysClosed.current = true;
          buttonRef.current?.focus();
          staysClosed.current = false;
        }
      }
    };
    const onPointer = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!buttonRef.current?.contains(target) && !popRef.current?.contains(target)) close();
    };
    // A fixed box left behind by a scroll would point at nothing.
    const onScroll = (e: Event) => {
      if (!popRef.current?.contains(e.target as Node)) close();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointer);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointer);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', close);
    };
  }, [open, close]);

  useEffect(() => () => cancelClose(), []);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className={term ? 'api-console__term' : 'api-console__tip'}
        aria-label={term ? undefined : label}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={(e) => {
          // Inside a label or a summary, a tap must open the explanation and nothing else.
          e.preventDefault();
          e.stopPropagation();
          cancelClose();
          if (pinned) close();
          else {
            setOpen(true);
            setPinned(true);
          }
        }}
        onMouseEnter={() => { cancelClose(); setOpen(true); }}
        onMouseLeave={() => { if (!pinned) closeSoon(); }}
        onFocus={() => { if (!staysClosed.current) { cancelClose(); setOpen(true); } }}
        onBlur={() => { if (!pinned) closeSoon(); }}
      >
        {term || <span className="mdi mdi-information-outline" aria-hidden="true" />}
      </button>
      {open && createPortal(
        <div
          ref={popRef}
          id={id}
          role="tooltip"
          className="api-console-pop"
          style={position ? { top: position.top, left: position.left } : { top: 0, left: 0, visibility: 'hidden' }}
          onMouseEnter={cancelClose}
          onMouseLeave={() => { if (!pinned) closeSoon(); }}
        >
          {children}
        </div>,
        document.body,
      )}
    </>
  );
};
