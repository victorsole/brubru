// frontend/src/pages/amendator_page.tsx
import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiContentSave, mdiFileEditOutline, mdiRobotOutline, mdiCompassOutline } from '@mdi/js';
import { Sidebar } from '../components/shared/sidebar';
import type { LegislativeElement, CellAmendment, PendingAIAmendment } from '../components/amendator/two_column_layout';
import { TwoColumnLayout } from '../components/amendator/two_column_layout';
import { AmendmentSidebar } from '../components/amendator/amendment_sidebar';
import { AIAssistantPanel } from '../components/amendator/ai_assistant_sidebar';
import { RecitalsPanel } from '../components/amendator/recitals_panel';
import type { AISuggestion } from '../components/amendator/ai_assistant_sidebar';
import type { LoadedDocument } from '../components/amendator/document_viewer';
import { LegislativeContextBanner } from '../components/amendator/legislative_context_banner';
import { useAuth } from '../hooks/use_auth';
import { formatCelexLabel } from '../components/bubble/celex_alias';
import './amendator_page.css';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;

// Amendment Types (based on European Parliament specification)
export type AmendmentType = 'modification' | 'suppression' | 'addition';
export type AmendmentStatus = 'candidate' | 'tabled' | 'withdrawn';
export type StructureLevel = 'recital' | 'article' | 'article-title' | 'point' | 'paragraph' | 'subparagraph';

// Text change tracking for bold italic formatting
export interface TextChange {
  start: number;
  end: number;
  oldText: string;
  newText: string;
}

export interface Amendment {
  id: string;

  // Amendment Type System
  type: AmendmentType; // modification, suppression, or addition
  structureLevel: StructureLevel; // which part of the document

  // Position reference (e.g., "Recital 15", "Article 3, point 2, paragraph (a)")
  position: string;

  // Text content
  originalText: string;
  proposedText: string;

  // Formatting
  changedWords?: TextChange[]; // For bold italic highlighting
  isCompleteSupression?: boolean; // Shows "Suppressed text" in italic
  isNewAddition?: boolean; // Shows "No original text" in italic

  // Metadata
  status: AmendmentStatus;
  createdAt: Date;
  updatedAt?: Date;

  // Optional fields
  justification?: string; // Why this amendment is needed
  author?: string; // Who drafted it
  group?: string; // Committee or political group
}

type SidebarTab = 'amendments' | 'ai' | 'recitals';

interface AmendatorPageProps {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
}

export const AmendatorPage = ({ isSidebarOpen, setIsSidebarOpen }: AmendatorPageProps) => {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedAmendment, setSelectedAmendment] = useState<Amendment | null>(null);
  const [loadedDocument, setLoadedDocument] = useState<LoadedDocument | null>(null);
  const [activeTab, setActiveTab] = useState<SidebarTab>('amendments');
  const [selectedElement, setSelectedElement] = useState<LegislativeElement | null>(null);
  const [elementIndex, setElementIndex] = useState<number | null>(null);
  const [cellAmendments, setCellAmendments] = useState<Map<number, CellAmendment>>(new Map());
  const [pendingAmendments, setPendingAmendments] = useState<PendingAIAmendment[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // Filter out false article-title rows that the EUR-Lex / COM parser
  // sometimes emits for cross-references like "Article 22 of Directive
  // (EU) 2017/1132". These create the illusion that the document jumps
  // from Article 2 to Article 22 because they appear before the real
  // Article 3 row. Heuristic: an article_title is a continuation
  // reference if its text starts with a lower-case word, with "of " /
  // "and " / "to " / "from ", with punctuation, or is empty / a single
  // character. Such rows are merged into the previous element's text so
  // the document keeps reading naturally.
  const sanitiseElements = (raw: any[]): any[] => {
    if (!Array.isArray(raw)) return [];
    const looksLikeCrossRef = (text: string): boolean => {
      const t = (text || '').trim();
      if (!t || t.length <= 2) return true;
      if (/^[;,.)\]–—]/.test(t)) return true;
      const first = t.split(/\s+/)[0];
      // Single lowercase preposition or starting lowercase letter => continuation
      if (/^(of|and|to|from|in|on|by|the|or|as|for|with|at|that|which)\b/i.test(t)) return true;
      if (first && /^[a-z]/.test(first)) return true;
      return false;
    };
    const out: any[] = [];
    for (const el of raw) {
      const isFakeTitle = el && el.type === 'article_title' && looksLikeCrossRef(el.text);
      if (isFakeTitle && out.length > 0) {
        const prev = out[out.length - 1];
        const fragment = `${el.number ? el.number + ' ' : ''}${(el.text || '').trim()}`.trim();
        if (fragment) {
          prev.text = `${prev.text || ''} ${fragment}`.replace(/\s+/g, ' ').trim();
        }
        continue;
      }
      out.push({ ...el });
    }
    return out;
  };

  // Deep-link: auto-load document from ?celex= and (optionally) hydrate the
  // user's saved amendments so "Open in Amendator" from My EU Bubble lands
  // on the editor with the chosen amendment restored on screen.
  const [pendingFocusAmendmentId, setPendingFocusAmendmentId] = useState<string | null>(null);
  const [pendingFocusCelex, setPendingFocusCelex] = useState<string | null>(null);
  const [deepLinkStatus, setDeepLinkStatus] = useState<
    | { kind: 'idle' }
    | { kind: 'loading'; celex: string }
    | { kind: 'error'; celex: string; reason: string }
    | { kind: 'hydrating'; celex: string }
    | { kind: 'done' }
  >({ kind: 'idle' });

  useEffect(() => {
    const celex = searchParams.get('celex');
    if (!celex || loadedDocument) return;

    // Capture deferred params BEFORE we clear the URL.
    const amendmentId = searchParams.get('amendmentId');
    setDeepLinkStatus({ kind: 'loading', celex });

    const loadFromCelex = async () => {
      try {
        const eurlexUrl = `https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:${celex}`;
        console.debug('[Amendator] Fetching CELEX', celex);
        const response = await fetch(`${API_BASE}/documents/fetch-eurlex`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: eurlexUrl, format: 'html', language: 'EN' }),
        });
        if (!response.ok) {
          const body = await response.text().catch(() => '');
          console.error('[Amendator] fetch-eurlex failed', response.status, body);
          setDeepLinkStatus({
            kind: 'error',
            celex,
            reason: `EUR-Lex returned HTTP ${response.status}. The law could not be auto-loaded.`,
          });
          return;
        }
        const doc = await response.json();
        if (!doc?.structure?.legislative_structure?.elements?.length) {
          setDeepLinkStatus({
            kind: 'error',
            celex,
            reason:
              'EUR-Lex returned the document but its legislative structure could not be parsed. ' +
              'This sometimes happens when EUR-Lex serves a WAF challenge page.',
          });
          return;
        }
        // Strip out false article-title rows before storing the doc so both
        // the editor and the amendment-hydration pass operate on a clean
        // element list.
        const cleanedElements = sanitiseElements(doc.structure.legislative_structure.elements);
        const cleanedDoc = {
          document_id: doc.document_id,
          filename: doc.filename,
          text: doc.text,
          metadata: doc.metadata,
          structure: {
            ...doc.structure,
            legislative_structure: {
              ...doc.structure.legislative_structure,
              elements: cleanedElements,
            },
          },
        };
        console.debug(
          '[Amendator] Element sanitisation:',
          doc.structure.legislative_structure.elements.length,
          '->',
          cleanedElements.length,
        );
        setLoadedDocument(cleanedDoc);
        // Queue the saved-amendments hydration; the next effect handles it
        // once loadedDocument is populated.
        setPendingFocusCelex(celex);
        if (amendmentId) setPendingFocusAmendmentId(amendmentId);
        setDeepLinkStatus({ kind: 'hydrating', celex });
      } catch (err) {
        console.error('[Amendator] Failed to auto-load CELEX document:', err);
        setDeepLinkStatus({
          kind: 'error',
          celex,
          reason: err instanceof Error ? err.message : 'Network error while loading the law.',
        });
      } finally {
        // Clear the params so they don't re-trigger
        setSearchParams({}, { replace: true });
      }
    };

    loadFromCelex();
  }, [searchParams, loadedDocument, setSearchParams]);

  // Hydrate the user's saved amendments from /api/amendments?celex=... so a
  // round-trip from the Documents tab restores the editor exactly where the
  // user left it. Runs once after the legislative document is in place.
  useEffect(() => {
    if (!loadedDocument || !pendingFocusCelex) return;
    const celex = pendingFocusCelex;
    const focusId = pendingFocusAmendmentId;
    setPendingFocusCelex(null);
    setPendingFocusAmendmentId(null);

    const token = useAuth.getState().token;
    if (!token) return;

    (async () => {
      try {
        const res = await fetch(
          `${API_BASE}/amendments?celex=${encodeURIComponent(celex)}&page_size=200`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!res.ok) {
          console.warn('[Amendator] /api/amendments returned', res.status);
          setDeepLinkStatus({ kind: 'done' });
          return;
        }
        const data = await res.json();
        const rows: any[] = Array.isArray(data) ? data : data.amendments || [];
        console.debug('[Amendator] Hydrating', rows.length, 'saved amendments for', celex);
        if (rows.length === 0) {
          setDeepLinkStatus({ kind: 'done' });
          return;
        }

        // Resolve each saved amendment to a fresh index in the current parse.
        // element_index in the DB was computed against an old parse that may
        // no longer match this one (recital/article counts drift, parser
        // fixes, sanitisation strips false article-titles), so we fall back
        // through a chain of progressively looser matchers.
        const parsedElements: any[] =
          loadedDocument.structure?.legislative_structure?.elements || [];

        const normalise = (s: string) =>
          (s || '')
            .toLowerCase()
            .replace(/[(),.]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();

        // Pull the article / paragraph / point / subparagraph / recital
        // identifiers out of a position string like "Article 5, paragraph 2"
        // or "Article 7(1)(a)" or "Recital 15".
        const parsePosition = (pt: string) => {
          const out: {
            articleNum?: string;
            paragraphNum?: string;
            pointNum?: string;
            subparagraphNum?: string;
            recitalNum?: string;
          } = {};
          const text = pt || '';
          const articleMatch = /Article\s+(\d+[a-z]?)/i.exec(text);
          if (articleMatch) out.articleNum = articleMatch[1].toLowerCase();
          const recitalMatch = /Recital\s+(\d+[a-z]?)/i.exec(text);
          if (recitalMatch) out.recitalNum = recitalMatch[1].toLowerCase();
          const paragraphMatch = /paragraph\s+(\d+[a-z]?)/i.exec(text);
          if (paragraphMatch) out.paragraphNum = paragraphMatch[1].toLowerCase();
          const pointMatch = /point\s+\(?([a-z0-9]+)\)?/i.exec(text);
          if (pointMatch) out.pointNum = pointMatch[1].toLowerCase();
          const subMatch = /subparagraph\s+\(?([a-z0-9]+)\)?/i.exec(text);
          if (subMatch) out.subparagraphNum = subMatch[1].toLowerCase();
          // Bare "Article 5(2)" / "Article 5(2)(a)" parenthesised form
          const parenMatch = /Article\s+\d+[a-z]?\s*\(([a-z0-9]+)\)(?:\s*\(([a-z0-9]+)\))?/i.exec(text);
          if (parenMatch && !out.paragraphNum) out.paragraphNum = parenMatch[1].toLowerCase();
          if (parenMatch && parenMatch[2] && !out.pointNum) out.pointNum = parenMatch[2].toLowerCase();
          return out;
        };

        const buildPositionStrings = (el: any): string[] => {
          const tps: string[] = [];
          if (!el) return tps;
          const articleNum = el.article_number || (el.type?.startsWith('article') ? el.number : '');
          const elNum = el.number || '';
          const paraNum = el.paragraph_number || '';
          if (el.type === 'recital' && elNum) tps.push(`recital ${elNum}`);
          if (el.type === 'article_title' && elNum) tps.push(`article ${elNum}`);
          if (el.type === 'article_intro' && articleNum) tps.push(`article ${articleNum}`);
          if (el.type === 'paragraph' && articleNum && elNum) {
            tps.push(`article ${articleNum} paragraph ${elNum}`);
            tps.push(`article ${articleNum} ${elNum}`);
            tps.push(`article ${articleNum}  ${elNum}`); // tolerate "Article 5, 2"
          }
          if (el.type === 'subparagraph' && articleNum && paraNum && elNum)
            tps.push(`article ${articleNum} paragraph ${paraNum} subparagraph ${elNum}`);
          if (articleNum && elNum) tps.push(`${articleNum} ${elNum}`);
          return tps.map(normalise);
        };

        const indexByPosition = new Map<string, number>();
        // Fast direct lookups by structural keys.
        const indexByTypeArtNum = new Map<string, number>(); // "paragraph:5:2" -> i
        const indexByTypeArt = new Map<string, number[]>(); // "paragraph:5"   -> [i, ...]
        parsedElements.forEach((el, i) => {
          for (const candidate of buildPositionStrings(el)) {
            if (!indexByPosition.has(candidate)) indexByPosition.set(candidate, i);
          }
          if (!el) return;
          const articleNum = el.article_number || (el.type?.startsWith('article') ? el.number : '');
          const elNum = el.number != null ? String(el.number).toLowerCase() : '';
          if (el.type && articleNum && elNum) {
            const k = `${el.type}:${String(articleNum).toLowerCase()}:${elNum}`;
            if (!indexByTypeArtNum.has(k)) indexByTypeArtNum.set(k, i);
          }
          if (el.type && articleNum) {
            const k = `${el.type}:${String(articleNum).toLowerCase()}`;
            if (!indexByTypeArt.has(k)) indexByTypeArt.set(k, []);
            indexByTypeArt.get(k)!.push(i);
          }
        });

        const resolveIndex = (a: any): { index: number | null; via: string } => {
          // 1) Trust element_index when its element looks right.
          if (typeof a.element_index === 'number' && a.element_index < parsedElements.length) {
            const el = parsedElements[a.element_index];
            if (el && el.type === a.element_type) {
              const elNum = String(el.number ?? '');
              if (!a.element_number || elNum === String(a.element_number)) {
                return { index: a.element_index, via: 'element_index' };
              }
            }
          }

          // 2) Exact position-string match.
          const target = normalise(a.position_text || '');
          if (target && indexByPosition.has(target)) {
            return { index: indexByPosition.get(target)!, via: 'position_text' };
          }

          // 3) Direct type:article:elementNumber lookup. This is the most
          //    reliable channel: a saved "Article 5, paragraph 2" amendment
          //    has type='paragraph', element_number='2', and we parse '5'
          //    out of position_text.
          const parsed = parsePosition(a.position_text || '');
          const inferredArticle =
            String(parsed.articleNum || a.article_number || '').toLowerCase();
          const inferredNumber = String(
            a.element_number ||
              parsed.paragraphNum ||
              parsed.pointNum ||
              parsed.recitalNum ||
              parsed.subparagraphNum ||
              '',
          ).toLowerCase();

          if (a.element_type && inferredArticle && inferredNumber) {
            const key = `${a.element_type}:${inferredArticle}:${inferredNumber}`;
            if (indexByTypeArtNum.has(key)) {
              return { index: indexByTypeArtNum.get(key)!, via: `type+art+num (${key})` };
            }
          }

          // 4) Cross-type fallback: maybe the saved row said 'paragraph' but
          //    the new parse buckets it as 'subparagraph' (or vice versa).
          if (inferredArticle && inferredNumber) {
            for (const candidateType of ['paragraph', 'subparagraph', 'point', 'article_title']) {
              const key = `${candidateType}:${inferredArticle}:${inferredNumber}`;
              if (indexByTypeArtNum.has(key)) {
                return { index: indexByTypeArtNum.get(key)!, via: `cross-type (${key})` };
              }
            }
          }

          // 5) Last resort: any element of the right type+article. Caller
          //    decides whether to accept the first one.
          if (a.element_type && inferredArticle) {
            const arr = indexByTypeArt.get(`${a.element_type}:${inferredArticle}`);
            if (arr && arr.length > 0) {
              return { index: arr[0], via: `type+art-only (${a.element_type}:${inferredArticle})` };
            }
          }

          return { index: null, via: 'unresolved' };
        };

        const next = new Map<number, CellAmendment>();
        let focusIndex: number | null = null;
        let resolved = 0;
        let unresolved = 0;
        for (const a of rows) {
          const { index: idx, via } = resolveIndex(a);
          if (idx === null) {
            unresolved += 1;
            console.warn(
              `[Amendator] Could not place saved amendment in current parse: position="${a.position_text}" type=${a.element_type} number=${a.element_number} oldIndex=${a.element_index}`,
            );
            continue;
          }
          resolved += 1;
          console.debug(
            `[Amendator] Placed "${a.position_text}" at element_index=${idx} via ${via}`,
          );
          const cell: CellAmendment = {
            elementIndex: idx,
            elementType: a.element_type || 'paragraph',
            elementNumber: a.element_number || '',
            amendmentType: (a.amendment_type || 'modification') as
              | 'modification'
              | 'suppression'
              | 'addition',
            originalText: a.original_text || '',
            proposedText: a.proposed_text || '',
            position: a.position_text || '',
            insertAfter: typeof a.insert_after === 'number' ? a.insert_after : undefined,
          };
          next.set(idx, cell);
          if (focusId && a.id === focusId) focusIndex = idx;
        }
        console.debug(
          '[Amendator] Hydration result:',
          resolved,
          'placed,',
          unresolved,
          'unresolved',
        );
        if (next.size === 0) {
          setDeepLinkStatus({ kind: 'done' });
          return;
        }
        setCellAmendments(next);
        setDeepLinkStatus({ kind: 'done' });

        // Best-effort focus on the requested amendment.
        if (focusIndex !== null) {
          setTimeout(() => {
            const sel = document.querySelector(`[data-element-index="${focusIndex}"]`);
            if (sel && 'scrollIntoView' in sel) {
              (sel as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' });
              sel.classList.add('two-column-layout__row--focus');
              setTimeout(() => sel.classList.remove('two-column-layout__row--focus'), 2500);
            }
          }, 400);
        }
      } catch (err) {
        console.warn('[Amendator] Failed to hydrate saved amendments:', err);
        setDeepLinkStatus({ kind: 'done' });
      }
    })();
  }, [loadedDocument, pendingFocusCelex, pendingFocusAmendmentId]);

  // Convert cellAmendments to Amendment format for sidebar display
  const amendments: Amendment[] = Array.from(cellAmendments.entries()).map(([index, cellAmendment]) => ({
    id: `${index}`, // Use index as temporary ID
    type: cellAmendment.amendmentType,
    structureLevel: cellAmendment.elementType as StructureLevel,
    position: cellAmendment.position,
    originalText: cellAmendment.originalText,
    proposedText: cellAmendment.proposedText,
    status: 'candidate' as AmendmentStatus,
    createdAt: new Date(),
    isCompleteSupression: cellAmendment.amendmentType === 'suppression',
    isNewAddition: cellAmendment.amendmentType === 'addition',
  }));

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const handleSelectAmendment = (amendment: Amendment) => {
    setSelectedAmendment(amendment);
  };

  const handleDeleteAmendment = (amendment: Amendment) => {
    const key = parseFloat(amendment.id);
    const newAmendments = new Map(cellAmendments);
    newAmendments.delete(key);
    setCellAmendments(newAmendments);
    if (selectedAmendment?.id === amendment.id) {
      setSelectedAmendment(null);
    }
  };

  const handleDocumentLoaded = (document: LoadedDocument) => {
    // Apply the same false-article-title scrub used by the deep-link path so
    // every ingress point (EUR-Lex URL input, file upload, tracked files,
    // deep-link) hands the editor a clean element list.
    const structure = document.structure;
    const raw = structure?.legislative_structure?.elements;
    if (structure && Array.isArray(raw) && raw.length > 0) {
      const cleaned = sanitiseElements(raw);
      if (cleaned.length !== raw.length) {
        console.debug('[Amendator] Element sanitisation:', raw.length, '->', cleaned.length);
      }
      setLoadedDocument({
        ...document,
        structure: {
          ...structure,
          legislative_structure: {
            ...structure.legislative_structure,
            elements: cleaned,
          },
        },
      });
      return;
    }
    setLoadedDocument(document);
  };

  const handleElementSelected = (element: LegislativeElement, index: number) => {
    setSelectedElement(element);
    setElementIndex(index);
    // Auto-switch to AI tab when an element is selected
    setActiveTab('ai');
  };


  const handleSaveAmendments = async () => {
    if (!loadedDocument || cellAmendments.size === 0) {
      setSaveMessage(t('amendator.noToSave'));
      setTimeout(() => setSaveMessage(null), 3000);
      return;
    }

    setIsSaving(true);
    setSaveMessage(null);

    try {
      // Convert Map to array
      const amendmentsArray = Array.from(cellAmendments.values());

      // Call batch API endpoint
      const token = useAuth.getState().token;
      const response = await fetch(`${API_BASE}/amendments/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
        body: JSON.stringify({
          document_id: loadedDocument.document_id,
          document_filename: loadedDocument.filename,
          amendments: amendmentsArray.map(amendment => ({
            document_id: loadedDocument.document_id,
            document_filename: loadedDocument.filename,
            element_index: amendment.elementIndex,
            element_type: amendment.elementType,
            element_number: amendment.elementNumber,
            position_text: amendment.position,
            amendment_type: amendment.amendmentType,
            original_text: amendment.originalText,
            proposed_text: amendment.proposedText,
            insert_after: amendment.insertAfter,
            justification: amendment.justification || '',
            group_label: '',
            author: '',
            amendment_number: '',
            status: 'draft',
          })),
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to save amendments');
      }

      const savedAmendments = await response.json();
      setSaveMessage(t('amendator.saveSuccess', { count: savedAmendments.length }));
      setTimeout(() => setSaveMessage(null), 5000);

    } catch (error) {
      console.error('Error saving amendments:', error);
      setSaveMessage(t('amendator.saveError'));
      setTimeout(() => setSaveMessage(null), 5000);
    } finally {
      setIsSaving(false);
    }
  };

  const handleAISuggestionAccepted = (suggestion: AISuggestion) => {
    const pending: PendingAIAmendment = {
      // Prefer the index the suggestion was generated against; fall back to the
      // current selection only if the suggestion carries none. This avoids
      // mis-placing when the user reselects a different row before accepting.
      elementIndex: suggestion.element_index ?? (elementIndex ?? undefined),
      elementPosition: suggestion.element_position,
      amendmentType: suggestion.amendment_type,
      proposedText: suggestion.proposed_text,
      justification: suggestion.justification,
    };
    setPendingAmendments([pending]);
    // Switch to amendments tab to show the result
    setActiveTab('amendments');
  };

  const handleBatchSuggestionsAccepted = (suggestions: AISuggestion[]) => {
    const pending: PendingAIAmendment[] = suggestions.map(s => ({
      elementIndex: s.element_index ?? undefined,
      elementPosition: s.element_position,
      amendmentType: s.amendment_type,
      proposedText: s.proposed_text,
      justification: s.justification,
    }));
    setPendingAmendments(pending);
    setActiveTab('amendments');
  };

  const handlePendingAmendmentsProcessed = () => {
    setPendingAmendments([]);
  };

  // Determine mascot state based on context
  const getMascotSrc = () => {
    if (amendments.length > 0) return '/assets/brubru_amendator.png';
    return '/assets/brubru_amendator_nochips.png';
  };

  const getMascotClass = () => {
    if (amendments.length > 0) return 'bounce wiggle';
    return 'breathe';
  };

  return (
    <div className="amendator-page">
      {/* Unified Left Sidebar */}
      <Sidebar isOpen={isSidebarOpen} onToggle={toggleSidebar} width={360}>
        <div className="amendator-sidebar">
          {/* Mascot */}
          <div className="amendator-sidebar__mascot">
            <img
              src={getMascotSrc()}
              alt="Brubru Amendator"
              className={`amendator-sidebar__mascot-image ${getMascotClass()}`}
            />
          </div>

          {/* Legislative Context Banner - shows tracking info when document is loaded */}
          {loadedDocument && (
            <LegislativeContextBanner
              documentId={loadedDocument.document_id}
              celex={loadedDocument.metadata?.celex}
            />
          )}

          {/* Tab Switcher */}
          <div className="amendator-sidebar__tabs">
            <button
              className={`amendator-sidebar__tab ${activeTab === 'amendments' ? 'amendator-sidebar__tab--active' : ''}`}
              onClick={() => setActiveTab('amendments')}
            >
              <Icon path={mdiFileEditOutline} size={0.8} />
              <span className="amendator-sidebar__tab-label">{t('amendator.amendments')}</span>
              {amendments.length > 0 && (
                <span className="amendator-sidebar__tab-badge">{amendments.length}</span>
              )}
            </button>
            <button
              className={`amendator-sidebar__tab ${activeTab === 'ai' ? 'amendator-sidebar__tab--active' : ''}`}
              onClick={() => setActiveTab('ai')}
            >
              <Icon path={mdiRobotOutline} size={0.8} />
              <span className="amendator-sidebar__tab-label">{t('amendator.ai')}</span>
            </button>
            <button
              className={`amendator-sidebar__tab ${activeTab === 'recitals' ? 'amendator-sidebar__tab--active' : ''}`}
              onClick={() => setActiveTab('recitals')}
              title={t('amendator.recitalsTitle')}
            >
              <Icon path={mdiCompassOutline} size={0.8} />
              <span className="amendator-sidebar__tab-label">{t('amendator.recitals')}</span>
            </button>
          </div>

          {/* Tab Content - both panels stay mounted to preserve state */}
          <div className="amendator-sidebar__content">
            <div style={{ display: activeTab === 'amendments' ? 'contents' : 'none' }}>
              <AmendmentSidebar
                amendments={amendments}
                onSelectAmendment={handleSelectAmendment}
                onDeleteAmendment={handleDeleteAmendment}
                selectedAmendmentId={selectedAmendment?.id}
                documentId={loadedDocument?.document_id}
              />
            </div>
            <div style={{ display: activeTab === 'ai' ? 'contents' : 'none' }}>
              <AIAssistantPanel
                selectedElement={selectedElement}
                selectedElementIndex={elementIndex}
                loadedDocument={loadedDocument}
                onSuggestionAccepted={handleAISuggestionAccepted}
                onBatchSuggestionsAccepted={handleBatchSuggestionsAccepted}
              />
            </div>
            <div style={{ display: activeTab === 'recitals' ? 'contents' : 'none' }}>
              <RecitalsPanel
                selectedElement={selectedElement}
                celex={loadedDocument?.metadata?.celex}
              />
            </div>
          </div>
        </div>
      </Sidebar>

      {/* Main Content Area */}
      <main className={`amendator-page__main ${isSidebarOpen ? 'amendator-page__main--sidebar-open' : ''}`}>
        {/* Deep-link status: centred overlay while fetching, small error pill on failure. */}
        {(deepLinkStatus.kind === 'loading' || deepLinkStatus.kind === 'hydrating') && (
          <div className="amendator-page__loading-overlay" role="status" aria-live="polite">
            <div className="amendator-page__loading-card">
              <div className="amendator-page__loading-spinner" />
              <div className="amendator-page__loading-title">
                {deepLinkStatus.kind === 'loading'
                  ? 'Loading legislative text…'
                  : 'Restoring your amendments…'}
              </div>
              <div className="amendator-page__loading-sub">
                {formatCelexLabel(deepLinkStatus.celex)}
              </div>
              <div className="amendator-page__loading-celex">{deepLinkStatus.celex}</div>
            </div>
          </div>
        )}
        {deepLinkStatus.kind === 'error' && (
          <div className="amendator-page__deeplink amendator-page__deeplink--error" role="alert">
            <span>Couldn't auto-open {deepLinkStatus.celex}: {deepLinkStatus.reason}</span>
            <button
              className="amendator-page__deeplink-dismiss"
              onClick={() => setDeepLinkStatus({ kind: 'idle' })}
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        )}

        {/* Save Amendments Bar */}
        {loadedDocument && cellAmendments.size > 0 && (
          <div className="amendator-page__save-bar">
            <div className="amendator-page__save-info">
              <span className="amendator-page__amendment-count">
                {t('amendator.amendmentsPending', { count: cellAmendments.size })}
              </span>
              {saveMessage && (
                <span className={`amendator-page__save-message ${(saveMessage === t('amendator.saveError') || saveMessage === t('amendator.noToSave')) ? 'amendator-page__save-message--error' : 'amendator-page__save-message--success'}`}>
                  {saveMessage}
                </span>
              )}
            </div>
            <button
              className="button button-primary amendator-page__save-button"
              onClick={handleSaveAmendments}
              disabled={isSaving}
            >
              <Icon path={mdiContentSave} size={0.8} />
              {isSaving ? t('amendator.saving') : t('amendator.saveAmendments')}
            </button>
          </div>
        )}

        {/* Two-Column Amendment Table */}
        <TwoColumnLayout
          loadedDocument={loadedDocument}
          onDocumentLoaded={handleDocumentLoaded}
          onElementSelected={handleElementSelected}
          amendments={cellAmendments}
          setAmendments={setCellAmendments}
          pendingAmendments={pendingAmendments}
          onPendingAmendmentsProcessed={handlePendingAmendmentsProcessed}
        />
      </main>
    </div>
  );
};
