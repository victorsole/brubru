// frontend/src/components/shared/legal_text.tsx
//
// Renders a paragraph (or set of paragraphs) of EU legal text with:
//   - clickable cross-references to EUR-Lex ("Article 7 of Regulation (EU) 2024/1234")
//   - clickable acronym links (GDPR, DSA, AI Act, ...)
//   - statutory definitions wrapped with a native `title` tooltip
//
// The annotation is performed server-side via POST /api/legislation/annotate-text
// and memoised client-side. While the fetch is in flight we render the raw text
// so there is zero layout shift.

import type * as React from 'react';
import { useAnnotatedTexts } from '../../hooks/use_legal_intelligence';
import './legal_text.css';

interface LegalTextProps {
  /** Raw paragraph text to render. Pass a single string. */
  text: string;
  /** CELEX of the law this paragraph belongs to. Required for defined-term wrapping. */
  celex?: string;
  /** Optional HTML element to render as. Defaults to <p>. */
  as?: 'p' | 'div' | 'span';
  /** Extra className to merge with the component's default. */
  className?: string;
}

export const LegalText = ({ text, celex, as = 'p', className }: LegalTextProps) => {
  const { data } = useAnnotatedTexts(celex, [text]);
  const html = data?.[0];
  const mergedClassName = ['legal-text', className].filter(Boolean).join(' ');

  // While loading or if annotation failed, render raw text so layout is stable.
  if (!html) {
    const Tag = as;
    return <Tag className={mergedClassName}>{text}</Tag>;
  }

  // After annotation, render the HTML. The annotator only ever inserts <a> and
  // <span> tags with our own CSS classes -- no scripts, no event handlers.
  if (as === 'p') {
    return <p className={mergedClassName} dangerouslySetInnerHTML={{ __html: html }} />;
  }
  if (as === 'span') {
    return <span className={mergedClassName} dangerouslySetInnerHTML={{ __html: html }} />;
  }
  return <div className={mergedClassName} dangerouslySetInnerHTML={{ __html: html }} />;
};

/**
 * Batched variant: annotate many paragraphs in one network call, then render
 * them with a caller-provided renderer. Useful when a page has 50+ paragraphs.
 */
interface LegalTextListProps {
  texts: string[];
  celex?: string;
  render: (html: string, raw: string, index: number) => React.ReactNode;
}

export const LegalTextList = ({ texts, celex, render }: LegalTextListProps) => {
  const { data } = useAnnotatedTexts(celex, texts);
  const htmls = data ?? texts;
  return (
    <>
      {texts.map((raw, i) => render(htmls[i] ?? raw, raw, i))}
    </>
  );
};
