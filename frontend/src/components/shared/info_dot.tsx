/**
 * Shared affordance primitives for MEUB.
 *
 * <InfoDot text="..."/>  — a small (i) icon with a hover/focus tooltip, for
 *                          explaining a control or metric.
 * <CodeChip code="LIBE"/> — renders an institutional code with a plain-language
 *                          tooltip pulled from the shared code glossary, so bare
 *                          committee / Council / procedure codes are never
 *                          cryptic. Falls back to a plain span when unknown.
 *
 * Both expose the text via a native `title` (always works, accessible) AND a
 * styled CSS popover on hover/focus.
 */

import Icon from '@mdi/react';
import { useTranslation } from 'react-i18next';
import { mdiInformationOutline } from '@mdi/js';
import { glossaryFor } from '../../utils/code_glossary';
import './info_dot.css';

interface InfoDotProps {
  text: string;
  size?: number;
  className?: string;
}

export const InfoDot = ({ text, size = 0.65, className }: InfoDotProps) => (
  <span
    className={`info-dot ${className || ''}`}
    tabIndex={0}
    role="note"
    aria-label={text}
    title={text}
  >
    <Icon path={mdiInformationOutline} size={size} />
    <span className="info-dot__pop" role="tooltip">{text}</span>
  </span>
);

interface CodeChipProps {
  code: string;
  /** Override the visible text (defaults to the code itself). */
  label?: string;
  className?: string;
}

export const CodeChip = ({ code, label, className }: CodeChipProps) => {
  const { t } = useTranslation();
  const fallback = glossaryFor(code);
  // Localised expansion if present (glossary.<CODE>); else the English fallback.
  const expansion = fallback
    ? t('glossary.' + code.trim().toUpperCase(), { defaultValue: fallback })
    : null;
  if (!expansion) {
    return <span className={`code-chip ${className || ''}`}>{label || code}</span>;
  }
  return (
    <span
      className={`code-chip code-chip--known ${className || ''}`}
      tabIndex={0}
      title={expansion}
    >
      {label || code}
      <span className="code-chip__pop" role="tooltip">{expansion}</span>
    </span>
  );
};
