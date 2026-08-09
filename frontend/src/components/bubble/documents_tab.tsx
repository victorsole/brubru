/**
 * Documents Tab Component
 *
 * Displays and manages user documents (amendments, analyses, strategies, notes,
 * uploaded files, AI-generated documents).
 *
 * Now also:
 *   - merges rows from the amendments table (Amendator drafts) so the tab is the
 *     single library for everything the user has built;
 *   - exposes first-class filters for the 5 generated document types;
 *   - lets users edit any document inline and download as DOCX/PDF;
 *   - shows a version-history modal driven by /api/documents/{id}/versions;
 *   - surfaces CELEX + alias context on cards;
 *   - extends the include_in_ai_context toggle to every document type;
 *   - opens the document-generator wizard when the URL carries
 *     ?openWizard=1&docType=...&topic=...;
 *   - links out to Amendator, Chat and EU Law Comply.
 */

import { useEffect, useState, useRef, useMemo } from 'react';
import { ExportButton } from '../shared/export_button';
import { chatReturnParams } from '../../utils/chat_return';
import { ListSkeleton } from '../shared/skeleton';
import { createPortal } from 'react-dom';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiRobotOutline,
  mdiFileUploadOutline,
  mdiFilePdfBox,
  mdiFileWordBox,
  mdiFileDocumentOutline,
  mdiBrain,
  mdiPencilOutline,
  mdiHistory,
  mdiDownload,
  mdiOpenInNew,
  mdiChatOutline,
  mdiClipboardCheckOutline,
  mdiContentCopy,
  mdiDotsHorizontal,
  mdiTrayArrowDown,
  mdiFileDocumentEditOutline,
  mdiClose,
} from '@mdi/js';
import { marked } from 'marked';
import { useBubble } from '../../hooks/use_bubble';
import type { UserDocument } from '../../hooks/use_bubble';
import { useAuth } from '../../hooks/use_auth';
import { DocumentGeneratorWizard } from './document_generator_wizard';
import { DocumentEditor } from './document_editor';
import { formatCelexLabel, aliasOnly } from './celex_alias';
import { MeubHeader } from './meub_header';
import { toast } from '../shared/feedback_host';
import './documents_tab.css';

/**
 * Detect documents that embed raw layout HTML (e.g. the letter and event poster,
 * which centre a logo). The markdown WYSIWYG editor can mangle raw HTML on round-trip,
 * so these fall back to source editing until the visual canvas (later phase) lands.
 */
function hasRawHtmlBlock(content?: string | null): boolean {
  if (!content) return false;
  return /<(img|div|section|figure|iframe|style)\b/i.test(content);
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Strip markdown syntax for plain-text card excerpts */
function stripMarkdown(text: string): string {
  return text
    .replace(/```[\w]*\n?/g, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/^--\s*/gm, '— ')
    .replace(/^#+\s*/gm, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/^[-*]\s+/gm, '')
    .trim();
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileTypeIcon(contentType?: string): string {
  if (contentType === 'application/pdf') return mdiFilePdfBox;
  if (contentType?.includes('word') || contentType?.includes('docx')) return mdiFileWordBox;
  return mdiFileDocumentOutline;
}

/** Resolve the visible kind (filter category) for a document. */
function resolveKind(doc: UserDocument): string {
  if (doc.document_type === 'amendment_carriage') return 'amendment';
  // Tender Docs kinds (added 16 Jun 2026 with Tender Docs v1)
  if (doc.tags?.includes('tender_application_short')) return 'tender_application_short';
  if (doc.tags?.includes('tender_application_full')) return 'tender_application_full';
  if (doc.tags?.includes('tender_pitch_deck')) return 'tender_pitch_deck';
  if (doc.tags?.includes('tender_video_script')) return 'tender_video_script';
  if (doc.tags?.includes('tender_implementation_plan')) return 'tender_implementation_plan';
  if (doc.tags?.includes('tender_financial_plan')) return 'tender_financial_plan';
  if (doc.tags?.includes('tender_lump_sum_budget')) return 'tender_lump_sum_budget';
  if (doc.tags?.includes('tender_fto_analysis')) return 'tender_fto_analysis';
  if (doc.tags?.includes('tender_letters_of_intent')) return 'tender_letters_of_intent';
  if (doc.tags?.includes('tender_consortium_agreement')) return 'tender_consortium_agreement';
  if (doc.tags?.includes('tender_ownership_control')) return 'tender_ownership_control';
  if (doc.tags?.includes('tender_clinical_studies_annex')) return 'tender_clinical_studies_annex';
  if (doc.tags?.includes('tender_ethics_self_assessment')) return 'tender_ethics_self_assessment';
  if (doc.tags?.includes('tender_org_profile_consent')) return 'tender_org_profile_consent';
  if (doc.tags?.includes('tender_budget_table')) return 'tender_budget_table';
  if (doc.tags?.includes('tender_budget_narrative')) return 'tender_budget_narrative';
  if (doc.tags?.includes('tender_eligibility_dossier')) return 'tender_eligibility_dossier';
  if (doc.tags?.includes('position_paper')) return 'position_paper';
  if (doc.tags?.includes('mep_briefing')) return 'mep_briefing';
  if (doc.tags?.includes('talking_points')) return 'talking_points';
  if (doc.tags?.includes('resolution')) return 'resolution';
  if (doc.tags?.includes('petition')) return 'petition';
  if (doc.tags?.includes('ep_question')) return 'ep_question';
  if (doc.tags?.includes('eu_email')) return 'eu_email';
  if (doc.tags?.includes('one_pager')) return 'one_pager';
  if (doc.tags?.includes('press_release')) return 'press_release';
  if (doc.tags?.includes('stakeholder_map')) return 'stakeholder_map';
  if (doc.tags?.includes('impact_assessment')) return 'impact_assessment';
  if (doc.tags?.includes('presentation')) return 'presentation';
  if (doc.tags?.includes('event_poster')) return 'event_poster';
  if (doc.tags?.includes('consultation_response')) return 'consultation_response';
  return doc.document_type;
}

/** Funding-doc kinds (drives the "Funding & Tenders" filter group). */
const FUNDING_DOC_KINDS = new Set([
  'tender_application_short',
  'tender_application_full',
  'tender_pitch_deck',
  'tender_video_script',
  'tender_implementation_plan',
  'tender_financial_plan',
  'tender_lump_sum_budget',
  'tender_fto_analysis',
  'tender_letters_of_intent',
  'tender_consortium_agreement',
  'tender_ownership_control',
  'tender_clinical_studies_annex',
  'tender_ethics_self_assessment',
  'tender_org_profile_consent',
  'tender_budget_table',
  'tender_budget_narrative',
  'tender_eligibility_dossier',
]);

const KIND_LABELS: Record<string, string> = {
  uploaded: 'Uploaded',
  amendment: 'Amendment',
  analysis: 'Analysis',
  strategy: 'Strategy',
  note: 'Note',
  position_paper: 'Position paper',
  mep_briefing: 'MEP briefing',
  talking_points: 'Talking points',
  resolution: 'EP resolution',
  petition: 'EP petition',
  ep_question: 'EP question',
  eu_email: 'EU email',
  one_pager: 'One-pager',
  press_release: 'Press release',
  stakeholder_map: 'Stakeholder map',
  impact_assessment: 'Impact assessment',
  presentation: 'Presentation',
  event_poster: 'Event poster',
  consultation_response: 'Consultation response',
  // Tender Docs (16 Jun 2026)
  tender_application_short: 'Tender — Part B (short)',
  tender_application_full: 'Tender — Part B (full)',
  tender_pitch_deck: 'Tender — pitch deck',
  tender_video_script: 'Tender — video script',
  tender_implementation_plan: 'Tender — implementation plan',
  tender_financial_plan: 'Tender — financial plan',
  tender_lump_sum_budget: 'Tender — lump-sum budget',
  tender_fto_analysis: 'Tender — FTO analysis',
  tender_letters_of_intent: 'Tender — letters of intent',
  tender_consortium_agreement: 'Tender — consortium agreement',
  tender_ownership_control: 'Tender — ownership control',
  tender_clinical_studies_annex: 'Tender — clinical studies annex',
  tender_ethics_self_assessment: 'Tender — ethics self-assessment',
  tender_org_profile_consent: 'Tender — NCP consent',
  tender_budget_table: 'Tender — budget table',
  tender_budget_narrative: 'Tender — budget narrative',
  tender_eligibility_dossier: 'Tender — eligibility dossier (ESPD)',
};

export const DocumentsTab = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    documents,
    isLoadingDocuments,
    fetchDocuments,
    createDocument,
    updateDocument,
    deleteDocument,
    selectDocument,
  } = useBubble();

  const { user, token } = useAuth();
  const userTier = user?.subscription_tier || 'white';
  const canUseResolution = userTier === 'yellow' || userTier === 'blue';

  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showGeneratorWizard, setShowGeneratorWizard] = useState(false);
  const [presetGenerator, setPresetGenerator] = useState<{ docType?: string; topic?: string } | null>(null);
  const [viewingDocument, setViewingDocument] = useState<UserDocument | null>(null);
  const [editingDocument, setEditingDocument] = useState<UserDocument | null>(null);
  const [versionsFor, setVersionsFor] = useState<UserDocument | null>(null);
  const [versionList, setVersionList] = useState<Array<{ id: string; version: number; title: string; updated_at: string; created_at: string; word_count?: number }>>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  // Full-screen WYSIWYG editor target (Phase 1). Null = closed.
  const [fullEditDoc, setFullEditDoc] = useState<UserDocument | null>(null);

  // Carriage-amendments (merged from /api/amendments)
  const [carriageAmendments, setCarriageAmendments] = useState<UserDocument[]>([]);

  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadDragging, setUploadDragging] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Deep-link to a specific filter: /my-eu-bubble?tab=documents&type=funding
  // Used by the MEUB Tender Docs cross-link strip.
  useEffect(() => {
    const typeParam = searchParams.get('type');
    if (typeParam) {
      setFilterType(typeParam);
      const next = new URLSearchParams(searchParams);
      next.delete('type');
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Open the wizard if the URL says so (chat -> /my-eu-bubble?tab=documents&openWizard=1&docType=...)
  useEffect(() => {
    if (searchParams.get('openWizard') === '1') {
      const docType = searchParams.get('docType') || undefined;
      const topic = searchParams.get('topic') || undefined;
      setPresetGenerator({ docType, topic });
      setShowGeneratorWizard(true);

      // Strip the params so refresh doesn't re-open it
      const next = new URLSearchParams(searchParams);
      next.delete('openWizard');
      next.delete('docType');
      next.delete('topic');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Auto-open a freshly-drafted document when the chat hands us
  // /my-eu-bubble?tab=documents&docId=<uuid>. Fetches that specific row,
  // pops the View modal, then strips the param.
  useEffect(() => {
    const docId = searchParams.get('docId');
    if (!docId || !token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/documents/${docId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          console.warn('[Documents] Could not load drafted document:', res.status);
          return;
        }
        const doc = await res.json();
        if (cancelled) return;
        selectDocument(doc);
        setViewingDocument(doc);
        // Make sure the new doc is also in the list so subsequent navigation works.
        fetchDocuments({ search: searchQuery || undefined });
      } catch (err) {
        console.warn('[Documents] Failed to fetch drafted document:', err);
      } finally {
        const next = new URLSearchParams(searchParams);
        next.delete('docId');
        setSearchParams(next, { replace: true });
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, token]);

  useEffect(() => {
    fetchDocuments({ search: searchQuery || undefined });
  }, [searchQuery]);

  // Fetch carriage-amendments in parallel so the tab is the single library.
  useEffect(() => {
    let cancelled = false;
    const loadCarriage = async () => {
      if (!token) {
        setCarriageAmendments([]);
        return;
      }
      try {
        const res = await fetch(`${API_BASE_URL}/api/amendments?limit=100`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        const rows = Array.isArray(data) ? data : data.amendments || [];
        const extractCelex = (docId?: string | null): string | undefined => {
          if (!docId) return undefined;
          // amendments.document_id stores raw CELEX or "eurlex-<CELEX>"; both
          // should produce the same deep-link target.
          return docId.startsWith('eurlex-') ? docId.slice('eurlex-'.length) : docId;
        };
        const extractArticle = (positionText?: string | null): string | undefined => {
          if (!positionText) return undefined;
          const m = /Article\s+(\d+[a-z]?)/i.exec(positionText);
          return m ? m[1] : undefined;
        };
        const mapped: UserDocument[] = rows.map((a: any) => ({
          id: `amendment-${a.id}`,
          document_type: 'amendment_carriage',
          title: a.title || a.position_text || `Amendment ${a.amendment_number || ''}`.trim() || 'Amendment',
          content: a.justification || a.amended_text || a.original_text || '',
          celex_number: extractCelex(a.document_id),
          procedure_reference: a.procedure_reference || undefined,
          carriage_id: a.carriage_id || undefined,
          amendment_type: a.amendment_type,
          amendment_status: a.status || a.amendment_status,
          article_number: extractArticle(a.position_text),
          created_at: a.created_at,
          updated_at: a.updated_at || a.created_at,
          word_count: a.amended_text ? a.amended_text.split(/\s+/).length : 0,
          tags: ['amendator'],
        }));
        if (!cancelled) setCarriageAmendments(mapped);
      } catch (err) {
        console.warn('Failed to fetch carriage amendments:', err);
      }
    };
    loadCarriage();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const [createType, setCreateType] = useState('note');
  const RESOLUTION_TEMPLATE = t('documentsTab.resolutionTemplate');
  const PETITION_TEMPLATE = t('documentsTab.petitionTemplate');

  const handleCreateDocument = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);

    const selectedType = formData.get('type') as string;
    const isResolution = selectedType === 'resolution';

    const userTags = (formData.get('tags') as string)?.split(',').map((s) => s.trim()).filter(Boolean) || [];

    const document = {
      document_type: (isResolution ? 'note' : selectedType) as 'amendment' | 'analysis' | 'strategy' | 'note',
      title: formData.get('title') as string,
      content: formData.get('content') as string,
      policy_areas: (formData.get('policy_areas') as string)?.split(',').map((s) => s.trim()).filter(Boolean) || [],
      tags: isResolution ? ['resolution', ...userTags] : userTags,
    };

    try {
      const form = e.currentTarget;
      await createDocument(document);
      form.reset();
      setCreateType('note');
      setShowCreateModal(false);
    } catch (error) {
      console.error('Failed to create document:', error);
    }
  };

  const handleDelete = async (id: string, title: string) => {
    if (id.startsWith('amendment-')) {
      // Delete carriage amendment
      const realId = id.replace(/^amendment-/, '');
      if (!confirm(t('documentsTab.confirmDelete', { title }))) return;
      try {
        const res = await fetch(`${API_BASE_URL}/api/amendments/${realId}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          setCarriageAmendments((prev) => prev.filter((d) => d.id !== id));
        }
      } catch (err) {
        console.error('Failed to delete amendment:', err);
      }
      return;
    }
    if (confirm(t('documentsTab.confirmDelete', { title }))) {
      await deleteDocument(id);
    }
  };

  const handleToggleAIContext = async (doc: UserDocument) => {
    if (doc.document_type === 'amendment_carriage') {
      return;
    }
    try {
      await updateDocument(doc.id, { include_in_ai_context: !doc.include_in_ai_context });
    } catch (error) {
      console.error('Failed to toggle AI context:', error);
    }
  };

  const handleDownloadPptx = async (doc: UserDocument) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/documents/${doc.id}/export-pptx`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      triggerBlobDownload(await res.blob(), `${doc.title}.pptx`);
    } catch (err) {
      console.error('PPTX download failed:', err);
      toast(t('documentsTab.pptxFailed', 'PPTX download failed. Please try again.'), 'error');
    }
  };

  const handleDownload = async (doc: UserDocument, fmt: 'docx' | 'pdf') => {
    if (doc.document_type === 'amendment_carriage') {
      // No saved doc; render from in-memory content
      try {
        const res = await fetch(`${API_BASE_URL}/api/generate/export`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            document_title: doc.title,
            document_content: doc.content || '',
            export_format: fmt,
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        triggerBlobDownload(await res.blob(), `${doc.title}.${fmt}`);
      } catch (err) {
        console.error('Download failed:', err);
        toast(t('documentsTab.downloadFailed', 'Download failed. Please try again.'), 'error');
      }
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/documents/${doc.id}/export?format=${fmt}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      triggerBlobDownload(await res.blob(), `${doc.title}.${fmt}`);
    } catch (err) {
      console.error('Download failed:', err);
      toast(t('documentsTab.downloadFailed', 'Download failed. Please try again.'), 'error');
    }
  };

  const triggerBlobDownload = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = filename;
    window.document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  };

  const openEdit = (doc: UserDocument) => {
    if (doc.document_type === 'uploaded' || doc.document_type === 'amendment_carriage') {
      // Uploaded files are not editable from here; carriage amendments live in Amendator.
      return;
    }
    const isSlideDoc = doc.tags?.includes('presentation') || doc.tags?.includes('event_poster');
    if (isSlideDoc || hasRawHtmlBlock(doc.content)) {
      // Slide docs (presentation, poster) are PowerPoint, not Word: they edit their
      // source text here and export to PPTX. Raw-HTML layout docs also keep source editing.
      setEditingDocument(doc);
      setEditTitle(doc.title);
      setEditContent(doc.content || '');
      return;
    }
    // Default: full-screen WYSIWYG (Word-like) editor.
    setFullEditDoc(doc);
  };

  /** Persist edits coming from the full-screen WYSIWYG editor (mirrors saveEdit). */
  const saveFromEditor = async (title: string, markdown: string, asNewVersion: boolean) => {
    if (!fullEditDoc) return;
    if (asNewVersion) {
      const res = await fetch(`${API_BASE_URL}/api/documents/${fullEditDoc.id}/version`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const newDoc = await res.json();
      await updateDocument(newDoc.id, { title, content: markdown });
    } else {
      await updateDocument(fullEditDoc.id, { title, content: markdown });
    }
    fetchDocuments({ search: searchQuery || undefined });
  };

  const saveEdit = async (asNewVersion: boolean) => {
    if (!editingDocument) return;
    setSavingEdit(true);
    try {
      if (asNewVersion) {
        // POST /version creates a copy with version+1; then PATCH the new copy with the edited content.
        const res = await fetch(`${API_BASE_URL}/api/documents/${editingDocument.id}/version`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const newDoc = await res.json();
        await updateDocument(newDoc.id, { title: editTitle, content: editContent });
      } else {
        await updateDocument(editingDocument.id, { title: editTitle, content: editContent });
      }
      setEditingDocument(null);
      fetchDocuments({ search: searchQuery || undefined });
    } catch (err) {
      console.error('Failed to save edit:', err);
      toast(t('documentsTab.saveFailed', 'Save failed. Please try again.'), 'error');
    } finally {
      setSavingEdit(false);
    }
  };

  const openVersions = async (doc: UserDocument) => {
    setVersionsFor(doc);
    setVersionList([]);
    setVersionsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/documents/${doc.id}/versions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setVersionList(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.warn('Failed to fetch versions:', err);
    } finally {
      setVersionsLoading(false);
    }
  };

  // CELEX shape: optional sector digit + 4-digit year + 1-2 type letters + 4 digits
  // (handles 32016R0679 / 52022PC0123 / 12012E47 etc.)
  const CELEX_RE = /^[0-9]?[0-9]{4}[A-Z]{1,2}[0-9]{2,4}[A-Z0-9-]*$/;

  const openInAmendator = (doc: UserDocument) => {
    const celex = doc.celex_number;
    const isCarriage = doc.document_type === 'amendment_carriage';
    const realId = isCarriage ? doc.id.replace(/^amendment-/, '') : '';

    if (!celex) {
      if (isCarriage) {
        toast(t('documentsTab.reuploadNote', 'This amendment was saved on an uploaded document, not an EUR-Lex law. Re-upload the source file in the Amendator to continue editing it.'), 'error');
        return;
      }
      navigate('/amendator');
      return;
    }
    if (!CELEX_RE.test(celex.toUpperCase())) {
      if (isCarriage) {
        toast(t('documentsTab.celexNote', { celex, defaultValue: 'Cannot auto-open this amendment in the Amendator: the source identifier "{{celex}}" is not an EUR-Lex CELEX number. The amendment is safe in My EU Bubble.' }), 'error');
        return;
      }
    }
    const params = new URLSearchParams({ celex });
    if (doc.article_number) params.set('article', doc.article_number);
    if (isCarriage && realId) params.set('amendmentId', realId);
    console.debug('[Documents] Open in Amendator', { celex, amendmentId: realId, article: doc.article_number });
    navigate(`/amendator?${params.toString()}`);
  };

  const useInChat = (doc: UserDocument) => {
    // Make sure the doc is fed into chat context, then drop the user into chat
    // with a prefilled "use this document" hint.
    if (doc.document_type !== 'amendment_carriage' && doc.document_type !== 'uploaded' && !doc.include_in_ai_context) {
      updateDocument(doc.id, { include_in_ai_context: true });
    }
    const params = new URLSearchParams(
      chatReturnParams('/my-eu-bubble?tab=documents', t('bubble.tabs.documents', 'My Documents')),
    );
    navigate(`/chat?${params.toString()}`, {
      state: {
        initialQuestion: `Use my document "${doc.title}" to answer the next question.`,
        source: 'documents_tab',
      },
    });
  };

  const sendToComply = (doc: UserDocument) => {
    const params = new URLSearchParams();
    if (doc.celex_number) params.set('celex', doc.celex_number);
    params.set('doc', doc.id);
    navigate(`/eulawcomply?${params.toString()}`);
  };

  const handleUploadFile = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      for (const file of fileArray) {
        if (file.size > 10 * 1024 * 1024) {
          setUploadError(t('documentsTab.exceedsLimit', { name: file.name }));
          continue;
        }
        const formData = new FormData();
        formData.append('file', file);
        const tk = useAuth.getState().token;
        const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
          method: 'POST',
          headers: { ...(tk ? { Authorization: `Bearer ${tk}` } : {}) },
          body: formData,
        });
        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: t('documentsTab.uploadFailed') }));
          setUploadError(err.detail || t('documentsTab.failedUpload', { name: file.name }));
          continue;
        }
        setUploadSuccess(t('documentsTab.uploadSuccess', { name: file.name }));
      }
      fetchDocuments({ search: searchQuery || undefined });
      setTimeout(() => {
        setShowUploadModal(false);
        setUploadSuccess(null);
      }, 1500);
    } catch (error) {
      console.error('Upload failed:', error);
      setUploadError(t('documentsTab.failedUploadGeneric'));
    } finally {
      setIsUploading(false);
    }
  };

  const handleUploadDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setUploadDragging(false);
    if (e.dataTransfer.files.length > 0) {
      handleUploadFile(e.dataTransfer.files);
    }
  };

  /** Merged + filtered + searched view. */
  const filteredDocuments = useMemo(() => {
    const merged: UserDocument[] = [...documents, ...carriageAmendments];
    const filtered = merged.filter((doc) => {
      const kind = resolveKind(doc);
      if (filterType !== 'all') {
        if (filterType === 'amendment') {
          if (kind !== 'amendment') return false;
        } else if (filterType === 'generated') {
          if (
            ![
              'position_paper',
              'mep_briefing',
              'talking_points',
              'resolution',
              'ep_question',
              'eu_email',
              'one_pager',
              'press_release',
              'stakeholder_map',
              'impact_assessment',
              'presentation',
              'event_poster',
              'consultation_response',
            ].includes(kind)
          ) {
            return false;
          }
        } else if (filterType === 'funding') {
          // "Funding & Tenders" umbrella — surfaces every Tender Docs kind
          if (!FUNDING_DOC_KINDS.has(kind)) return false;
        } else if (kind !== filterType) {
          return false;
        }
      }
      if (searchQuery && !doc.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
    filtered.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));
    return filtered;
  }, [documents, carriageAmendments, filterType, searchQuery]);

  return (
    <div className="documents-tab">
      {/* Header + memory-layer explainer */}
      <MeubHeader
        icon={mdiBrain}
        accent="#0d9488"
        title={t('documentsTab.title')}
        subtitle={t('documentsTab.subtitle')}
        aside={
          <div className="documents-tab__header-actions">
            <button className="documents-tab__upload-btn" onClick={() => setShowUploadModal(true)}>
              <Icon path={mdiFileUploadOutline} size={0.9} />
              {t('documentsTab.upload')}
            </button>
            <button
              className="documents-tab__generate-btn"
              onClick={() => {
                setPresetGenerator(null);
                setShowGeneratorWizard(true);
              }}
            >
              <Icon path={mdiRobotOutline} size={0.9} />
              {t('documentsTab.generateWithAi')}
            </button>
            <button className="documents-tab__create-btn" onClick={() => setShowCreateModal(true)}>
              {t('documentsTab.createDocument')}
            </button>
          </div>
        }
      />

      {/* memory-layer explainer */}
      <div className="documents-tab__intro">
        <p className="documents-tab__intro-body">{t('documentsTab.intro')}</p>

        <ul className="documents-tab__intro-points">
          <li>
            <Icon path={mdiTrayArrowDown} size={0.85} />
            <div>
              <strong>{t('documentsTab.point1Title')}</strong>
              <span>{t('documentsTab.point1Body')}</span>
            </div>
          </li>
          <li>
            <Icon path={mdiFileDocumentEditOutline} size={0.85} />
            <div>
              <strong>{t('documentsTab.point2Title')}</strong>
              <span>{t('documentsTab.point2Body')}</span>
            </div>
          </li>
        </ul>
      </div>

      {/* Filters */}
      <div className="documents-tab__filters">
        <ExportButton
          path="/api/documents"
          params={{ search: searchQuery || undefined }}
          limit={200}
        />
        <div className="documents-tab__filter-group">
          <label>{t('documentsTab.type')}</label>
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
            <option value="all">{t('documentsTab.all')}</option>
            <optgroup label={t('docType.grpUploaded') as string}>
              <option value="uploaded">{t('documentsTab.uploadedDocs')}</option>
              <option value="note">{t('documentsTab.notes')}</option>
              <option value="analysis">{t('documentsTab.analyses')}</option>
              <option value="strategy">{t('documentsTab.strategies')}</option>
              <option value="amendment">{t('docType.amendmentAll')}</option>
            </optgroup>
            <optgroup label={t('docType.grpAi') as string}>
              <option value="generated">{t('docType.generatedAll')}</option>
              <option value="position_paper">{t('docType.position_paper')}</option>
              <option value="mep_briefing">{t('docType.mep_briefing')}</option>
              <option value="talking_points">{t('docType.talking_points')}</option>
              <option value="resolution">{t('docType.resolution')}</option>
              <option value="petition">{t('docType.petition')}</option>
              <option value="ep_question">{t('docType.ep_question')}</option>
              <option value="eu_email">{t('docType.eu_email')}</option>
              <option value="one_pager">{t('docType.one_pager')}</option>
              <option value="press_release">{t('docType.press_release')}</option>
              <option value="stakeholder_map">{t('docType.stakeholder_map')}</option>
              <option value="impact_assessment">{t('docType.impact_assessment')}</option>
              <option value="presentation">{t('docType.presentation')}</option>
              <option value="event_poster">{t('docType.event_poster')}</option>
              <option value="consultation_response">{t('docType.consultation_response')}</option>
            </optgroup>
            <optgroup label={t('documentsTab.grpFundingTenders') as string}>
              <option value="funding">{t('documentsTab.kindAllTenderDocs')}</option>
              <option value="tender_application_short">{t('documentsTab.kindTenderApplicationShort')}</option>
              <option value="tender_application_full">{t('documentsTab.kindTenderApplicationFull')}</option>
              <option value="tender_pitch_deck">{t('documentsTab.kindTenderPitchDeck')}</option>
              <option value="tender_video_script">{t('documentsTab.kindTenderVideoScript')}</option>
              <option value="tender_implementation_plan">{t('documentsTab.kindTenderImplementationPlan')}</option>
              <option value="tender_financial_plan">{t('documentsTab.kindTenderFinancialPlan')}</option>
              <option value="tender_lump_sum_budget">{t('documentsTab.kindTenderLumpSumBudget')}</option>
              <option value="tender_fto_analysis">{t('documentsTab.kindTenderFtoAnalysis')}</option>
              <option value="tender_letters_of_intent">{t('documentsTab.kindTenderLettersOfIntent')}</option>
              <option value="tender_consortium_agreement">{t('documentsTab.kindTenderConsortiumAgreement')}</option>
              <option value="tender_ownership_control">{t('documentsTab.kindTenderOwnershipControl')}</option>
              <option value="tender_clinical_studies_annex">{t('documentsTab.kindTenderClinicalStudiesAnnex')}</option>
              <option value="tender_ethics_self_assessment">{t('documentsTab.kindTenderEthicsSelfAssessment')}</option>
              <option value="tender_org_profile_consent">{t('documentsTab.kindTenderOrgProfileConsent')}</option>
              <option value="tender_budget_table">{t('documentsTab.kindTenderBudgetTable')}</option>
              <option value="tender_budget_narrative">{t('documentsTab.kindTenderBudgetNarrative')}</option>
              <option value="tender_eligibility_dossier">{t('documentsTab.kindTenderEligibilityDossier')}</option>
            </optgroup>
          </select>
        </div>

        <div className="documents-tab__filter-group documents-tab__filter-group--search">
          <input
            type="text"
            placeholder={t('documentsTab.search')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Document Grid */}
      <div className="documents-tab__content">
        {isLoadingDocuments ? (
          <div className="documents-tab__loading"><ListSkeleton count={5} /></div>
        ) : filteredDocuments.length === 0 ? (
          <div className="documents-tab__empty">
            <p>{t('documentsTab.noDocs')}</p>
            <button onClick={() => setShowCreateModal(true)}>{t('documentsTab.createFirstDoc')}</button>
          </div>
        ) : (
          <div className="documents-tab__grid">
            {filteredDocuments.map((doc) => {
              const kind = resolveKind(doc);
              const isCarriage = doc.document_type === 'amendment_carriage';
              const isUploaded = doc.document_type === 'uploaded';
              const isSlide =
                doc.tags?.includes('presentation') || doc.tags?.includes('event_poster');
              const celexLabel = doc.celex_number ? formatCelexLabel(doc.celex_number) : '';
              const alias = doc.celex_number ? aliasOnly(doc.celex_number) : undefined;
              return (
                <div key={doc.id} className="documents-tab__card" data-type={kind}>
                  {/* Type Badge — type on the left, version pill + AI toggle on the right */}
                  <div className="documents-tab__card-badge">
                    <span className="documents-tab__card-badge-label">
                      {isUploaded ? (
                        <span className="documents-tab__card-badge--uploaded">
                          <Icon path={getFileTypeIcon(doc.file_content_type)} size={0.6} />
                          {t('documentsTab.uploadedBadge')}
                        </span>
                      ) : isCarriage ? (
                        <>{t('docType.amendatorDraft', 'Amendator draft')}</>
                      ) : (
                        t('docType.' + kind, KIND_LABELS[kind] || kind)
                      )}
                    </span>
                    <span className="documents-tab__card-badge-right">
                      {doc.version && doc.version > 1 && (
                        <span className="documents-tab__version-pill" title={t('documentsTab.versionPillTitle', 'Document version') as string}>
                          v{doc.version}
                        </span>
                      )}
                      {!isCarriage && (
                        <button
                          className={`documents-tab__card-ai ${
                            doc.include_in_ai_context ? 'documents-tab__card-ai--active' : ''
                          }`}
                          onClick={() => handleToggleAIContext(doc)}
                          title={
                            doc.include_in_ai_context
                              ? 'Included in chat context — click to remove'
                              : 'Feed this document into chat'
                          }
                        >
                          <Icon path={mdiBrain} size={0.65} />
                        </button>
                      )}
                    </span>
                  </div>

                  {/* Content */}
                  <div className="documents-tab__card-content">
                    <h3 className="documents-tab__card-title">{doc.title}</h3>

                    {celexLabel && (
                      <div className="documents-tab__card-celex" title={doc.celex_number}>
                        <Icon path={mdiClipboardCheckOutline} size={0.55} />
                        <span>{celexLabel}</span>
                        {alias && <span className="documents-tab__alias-chip">{alias}</span>}
                      </div>
                    )}

                    {isUploaded && doc.original_filename && (
                      <div className="documents-tab__file-meta">
                        <span className="documents-tab__file-name">{doc.original_filename}</span>
                        {doc.file_size_bytes && (
                          <span className="documents-tab__file-size">{formatFileSize(doc.file_size_bytes)}</span>
                        )}
                      </div>
                    )}

                    {doc.content && (
                      <p className="documents-tab__card-excerpt">
                        {stripMarkdown(doc.content).slice(0, 150)}...
                      </p>
                    )}

                    <div className="documents-tab__card-meta">
                      <span>{new Date(doc.updated_at).toLocaleDateString()}</span>
                      <span>•</span>
                      <span>
                        {doc.word_count || 0} {t('documentsTab.wordsLabel')}
                      </span>
                    </div>

                    {doc.policy_areas && doc.policy_areas.length > 0 && (
                      <div className="documents-tab__card-tags">
                        {doc.policy_areas.slice(0, 3).map((area, idx) => (
                          <span key={idx} className="documents-tab__tag">
                            {area}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions: one primary CTA + overflow menu */}
                  <div className="documents-tab__card-actions">
                    <button
                      className="documents-tab__action-btn documents-tab__action-btn--primary"
                      onClick={() => {
                        if (isCarriage) {
                          openInAmendator(doc);
                        } else {
                          selectDocument(doc);
                          setViewingDocument(doc);
                        }
                      }}
                    >
                      {isCarriage ? t('documentsTab.openInAmendator') : t('documentsTab.viewBtn')}
                    </button>

                    <div className="documents-tab__menu-wrap">
                      <button
                        className="documents-tab__action-btn documents-tab__action-btn--icon"
                        data-doc-menu-trigger={doc.id}
                        onClick={() => setOpenMenuId(openMenuId === doc.id ? null : doc.id)}
                        title={t('documentsTab.moreActions') as string}
                        aria-label={t('documentsTab.moreActions') as string}
                        aria-haspopup="menu"
                        aria-expanded={openMenuId === doc.id}
                      >
                        <Icon path={mdiDotsHorizontal} size={0.9} />
                      </button>
                      {openMenuId === doc.id &&
                        createPortal(
                          <>
                            <div
                              className="documents-tab__menu-backdrop"
                              onClick={() => setOpenMenuId(null)}
                            />
                            <div
                              className="documents-tab__menu"
                              role="menu"
                              ref={(node) => {
                                if (!node) return;
                                // Position the portal-mounted menu relative to the trigger
                                const trigger = (document.querySelector(
                                  `[data-doc-menu-trigger="${doc.id}"]`,
                                ) as HTMLElement) || null;
                                const fallback = node.parentElement?.querySelector(
                                  '.documents-tab__menu-wrap .documents-tab__action-btn--icon',
                                ) as HTMLElement | null;
                                const anchor = trigger || fallback;
                                if (anchor) {
                                  const r = anchor.getBoundingClientRect();
                                  const menuW = 230;
                                  node.style.top = `${r.bottom + 4}px`;
                                  node.style.left = `${Math.min(r.right - menuW, window.innerWidth - menuW - 8)}px`;
                                }
                              }}
                            >
                              {!isCarriage && !isUploaded && (
                                <button
                                  role="menuitem"
                                  onClick={() => {
                                    setOpenMenuId(null);
                                    openEdit(doc);
                                  }}
                                >
                                  <Icon path={mdiPencilOutline} size={0.7} />
                                  {isSlide ? t('documentsTab.editSlideText') : t('documentsTab.edit')}
                                </button>
                              )}
                              {!isCarriage && (
                                <button
                                  role="menuitem"
                                  onClick={() => {
                                    setOpenMenuId(null);
                                    openVersions(doc);
                                  }}
                                >
                                  <Icon path={mdiHistory} size={0.7} />
                                  {t('documentsTab.versionHistory')}
                                </button>
                              )}
                              <button
                                role="menuitem"
                                onClick={() => {
                                  setOpenMenuId(null);
                                  handleDownload(doc, 'docx');
                                }}
                              >
                                <Icon path={mdiDownload} size={0.7} />
                                {t('documentsTab.downloadDocx')}
                              </button>
                              <button
                                role="menuitem"
                                onClick={() => {
                                  setOpenMenuId(null);
                                  handleDownload(doc, 'pdf');
                                }}
                              >
                                <Icon path={mdiFilePdfBox} size={0.7} />
                                {t('documentsTab.downloadPdf')}
                              </button>
                              {isSlide && (
                                <button
                                  role="menuitem"
                                  onClick={() => {
                                    setOpenMenuId(null);
                                    handleDownloadPptx(doc);
                                  }}
                                >
                                  <Icon path={mdiDownload} size={0.7} />
                                  {t('documentsTab.downloadPptx')}
                                </button>
                              )}
                              {doc.celex_number && !isCarriage && (
                                <button
                                  role="menuitem"
                                  onClick={() => {
                                    setOpenMenuId(null);
                                    openInAmendator(doc);
                                  }}
                                >
                                  <Icon path={mdiOpenInNew} size={0.7} />
                                  {t('documentsTab.openInAmendator')}
                                </button>
                              )}
                              <button
                                role="menuitem"
                                onClick={() => {
                                  setOpenMenuId(null);
                                  useInChat(doc);
                                }}
                              >
                                <Icon path={mdiChatOutline} size={0.7} />
                                {t('documentsTab.useInChat')}
                              </button>
                              <button
                                role="menuitem"
                                onClick={() => {
                                  setOpenMenuId(null);
                                  sendToComply(doc);
                                }}
                              >
                                <Icon path={mdiClipboardCheckOutline} size={0.7} />
                                {t('documentsTab.sendToComply')}
                              </button>
                              <div className="documents-tab__menu-sep" />
                              <button
                                role="menuitem"
                                className="documents-tab__menu-item--danger"
                                onClick={() => {
                                  setOpenMenuId(null);
                                  handleDelete(doc.id, doc.title);
                                }}
                              >
                                {t('documentsTab.deleteBtn')}
                              </button>
                            </div>
                          </>,
                          document.body,
                        )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUploadModal &&
        createPortal(
          <div
            className="documents-tab__modal-overlay"
            onClick={() => {
              setShowUploadModal(false);
              setUploadError(null);
              setUploadSuccess(null);
            }}
          >
            <div
              className="documents-tab__modal documents-tab__upload-modal"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="documents-tab__modal-header">
                <h3>{t('documentsTab.uploadModalTitle')}</h3>
                <button
                  onClick={() => {
                    setShowUploadModal(false);
                    setUploadError(null);
                    setUploadSuccess(null);
                  }}
                  aria-label={t('documentsTab.close')}
                >
                  <Icon path={mdiClose} size={0.85} />
                </button>
              </div>

              <div
                className={`documents-tab__dropzone ${uploadDragging ? 'documents-tab__dropzone--dragging' : ''} ${
                  isUploading ? 'documents-tab__dropzone--uploading' : ''
                }`}
                onDragEnter={(e) => {
                  e.preventDefault();
                  setUploadDragging(true);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setUploadDragging(true);
                }}
                onDragLeave={() => setUploadDragging(false)}
                onDrop={handleUploadDrop}
                onClick={() => !isUploading && fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc"
                  style={{ display: 'none' }}
                  onChange={(e) => e.target.files && handleUploadFile(e.target.files)}
                />
                {isUploading ? (
                  <div className="documents-tab__dropzone-content">
                    <div className="documents-tab__upload-spinner" />
                    <p>{t('documentsTab.uploading')}</p>
                  </div>
                ) : (
                  <div className="documents-tab__dropzone-content">
                    <Icon path={mdiFileUploadOutline} size={2} />
                    <p>{t('documentsTab.dropFiles')}</p>
                    <span className="documents-tab__dropzone-formats">{t('documentsTab.fileTypes')}</span>
                  </div>
                )}
              </div>

              {uploadSuccess && (
                <div className="documents-tab__upload-feedback documents-tab__upload-feedback--success">
                  {uploadSuccess}
                </div>
              )}
              {uploadError && (
                <div className="documents-tab__upload-feedback documents-tab__upload-feedback--error">
                  {uploadError}
                </div>
              )}

              <p className="documents-tab__upload-note">{t('documentsTab.uploadNote')}</p>
            </div>
          </div>,
          document.body,
        )}

      {/* Create Modal */}
      {showCreateModal &&
        createPortal(
          <div
            className="documents-tab__modal-overlay"
            onClick={() => {
              setShowCreateModal(false);
              setCreateType('note');
            }}
          >
            <div className="documents-tab__modal" onClick={(e) => e.stopPropagation()}>
              <div className="documents-tab__modal-header">
                <h3>{t('documentsTab.createModalTitle')}</h3>
                <button
                  onClick={() => {
                    setShowCreateModal(false);
                    setCreateType('note');
                  }}
                  aria-label={t('documentsTab.close')}
                >
                  <Icon path={mdiClose} size={0.85} />
                </button>
              </div>

              <form onSubmit={handleCreateDocument}>
                <div className="documents-tab__form-group">
                  <label>{t('documentsTab.docTypeLabel')}</label>
                  <select
                    name="type"
                    required
                    value={createType}
                    onChange={(e) => setCreateType(e.target.value)}
                  >
                    <option value="note">{t('documentsTab.optionNote')}</option>
                    <option value="amendment">{t('documentsTab.optionAmendment')}</option>
                    <option value="analysis">{t('documentsTab.optionAnalysis')}</option>
                    <option value="strategy">{t('documentsTab.optionStrategy')}</option>
                    {canUseResolution && (
                      <option value="resolution">{t('documentsTab.optionEpResolution')}</option>
                    )}
                    {canUseResolution && (
                      <option value="petition">{t('documentsTab.optionEpPetition')}</option>
                    )}
                  </select>
                </div>

                <div className="documents-tab__form-group">
                  <label>{t('documentsTab.titleLabel')}</label>
                  <input
                    type="text"
                    name="title"
                    required
                    placeholder={
                      createType === 'resolution'
                        ? t('documentsTab.titlePlaceholderResolution')
                        : t('documentsTab.titlePlaceholder')
                    }
                  />
                </div>

                <div className="documents-tab__form-group">
                  <label>
                    {createType === 'resolution'
                      ? t('documentsTab.resolutionTextLabel')
                      : t('documentsTab.contentLabel')}
                  </label>
                  <textarea
                    name="content"
                    rows={createType === 'resolution' || createType === 'petition' ? 12 : 6}
                    placeholder={
                      createType === 'resolution'
                        ? t('documentsTab.resolutionTextPlaceholder')
                        : t('documentsTab.contentPlaceholder')
                    }
                    defaultValue={createType === 'resolution' ? RESOLUTION_TEMPLATE : createType === 'petition' ? PETITION_TEMPLATE : ''}
                    key={createType}
                  />
                </div>

                <div className="documents-tab__form-group">
                  <label>{t('documentsTab.policyAreasLabel')}</label>
                  <input
                    type="text"
                    name="policy_areas"
                    placeholder={t('documentsTab.policyAreasPlaceholder')}
                  />
                </div>

                <div className="documents-tab__form-group">
                  <label>{t('documentsTab.tagsLabel')}</label>
                  <input type="text" name="tags" placeholder={t('documentsTab.tagsPlaceholder')} />
                </div>

                <div className="documents-tab__modal-actions">
                  <button
                    type="button"
                    className="documents-tab__modal-btn documents-tab__modal-btn--secondary"
                    onClick={() => {
                      setShowCreateModal(false);
                      setCreateType('note');
                    }}
                  >
                    {t('documentsTab.cancelBtn')}
                  </button>
                  <button
                    type="submit"
                    className="documents-tab__modal-btn documents-tab__modal-btn--primary"
                  >
                    {t('documentsTab.createBtn')}
                  </button>
                </div>
              </form>
            </div>
          </div>,
          document.body,
        )}

      {/* View Modal */}
      {viewingDocument &&
        createPortal(
          <div className="documents-tab__modal-overlay" onClick={() => setViewingDocument(null)}>
            <div className="documents-tab__view-modal" onClick={(e) => e.stopPropagation()}>
              <div className="documents-tab__modal-header">
                <div>
                  <span className="documents-tab__view-badge" data-type={viewingDocument.document_type}>
                    {t('docType.' + resolveKind(viewingDocument), KIND_LABELS[resolveKind(viewingDocument)] || viewingDocument.document_type)}
                  </span>
                  <h3>{viewingDocument.title}</h3>
                </div>
                <button onClick={() => setViewingDocument(null)} aria-label={t('documentsTab.close')}>
                  <Icon path={mdiClose} size={0.85} />
                </button>
              </div>

              <div className="documents-tab__view-meta">
                <span>{new Date(viewingDocument.updated_at).toLocaleDateString()}</span>
                <span>•</span>
                <span>
                  {viewingDocument.word_count || 0} {t('documentsTab.wordsLabel')}
                </span>
                {viewingDocument.celex_number && (
                  <>
                    <span>•</span>
                    <span>{formatCelexLabel(viewingDocument.celex_number)}</span>
                  </>
                )}
                {viewingDocument.document_type === 'uploaded' && viewingDocument.original_filename && (
                  <>
                    <span>•</span>
                    <span>{viewingDocument.original_filename}</span>
                    {viewingDocument.file_size_bytes && (
                      <span>({formatFileSize(viewingDocument.file_size_bytes)})</span>
                    )}
                  </>
                )}
                {viewingDocument.policy_areas && viewingDocument.policy_areas.length > 0 && (
                  <>
                    <span>•</span>
                    {viewingDocument.policy_areas.map((area, idx) => (
                      <span key={idx} className="documents-tab__tag">
                        {area}
                      </span>
                    ))}
                  </>
                )}
              </div>

              <div className="documents-tab__view-content">
                {viewingDocument.content ? (
                  <div
                    className="markdown-content"
                    dangerouslySetInnerHTML={{
                      __html: marked.parse(
                        viewingDocument.content.replace(/^```[\w]*\n?/, '').replace(/\n?```\s*$/, ''),
                      ) as string,
                    }}
                  />
                ) : (
                  <p className="documents-tab__view-empty">{t('documentsTab.noContent')}</p>
                )}
              </div>

              <div className="documents-tab__view-footer">
                <div className="documents-tab__view-footer-left">
                  <button
                    className="documents-tab__link-btn"
                    onClick={() => navigator.clipboard.writeText(viewingDocument.content || '')}
                  >
                    <Icon path={mdiContentCopy} size={0.65} />
                    {t('documentsTab.copyBtn')}
                  </button>
                  <span className="documents-tab__view-footer-sep">·</span>
                  <span className="documents-tab__view-footer-label">{t('documentsTab.downloadLabel')}</span>
                  <button
                    className="documents-tab__link-btn"
                    onClick={() => handleDownload(viewingDocument, 'docx')}
                  >
                    DOCX
                  </button>
                  <button
                    className="documents-tab__link-btn"
                    onClick={() => handleDownload(viewingDocument, 'pdf')}
                  >
                    PDF
                  </button>
                </div>
                {viewingDocument.document_type !== 'uploaded' && (
                  <button
                    className="documents-tab__modal-btn documents-tab__modal-btn--primary"
                    onClick={() => {
                      const d = viewingDocument;
                      setViewingDocument(null);
                      openEdit(d);
                    }}
                  >
                    <Icon path={mdiPencilOutline} size={0.7} />
                    {t('documentsTab.editBtn')}
                  </button>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )}

      {/* Edit Modal */}
      {editingDocument &&
        createPortal(
          <div className="documents-tab__modal-overlay" onClick={() => setEditingDocument(null)}>
            <div className="documents-tab__view-modal" onClick={(e) => e.stopPropagation()}>
              <div className="documents-tab__modal-header">
                <h3>{t('documentsTab.editDocModalTitle')}</h3>
                <button onClick={() => setEditingDocument(null)} aria-label={t('documentsTab.close')}>
                  <Icon path={mdiClose} size={0.85} />
                </button>
              </div>

              <div className="documents-tab__form-group">
                <label>{t('documentsTab.editTitleLabel', 'Title')}</label>
                <input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
              </div>

              <div className="documents-tab__form-group">
                <label>{t('documentsTab.contentLabel')}</label>
                <textarea
                  rows={18}
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  style={{ fontSize: '0.95rem', lineHeight: 1.6 }}
                />
              </div>

              <div className="documents-tab__modal-actions">
                <button
                  className="documents-tab__modal-btn documents-tab__modal-btn--secondary"
                  onClick={() => setEditingDocument(null)}
                  disabled={savingEdit}
                >
                  {t('documentsTab.cancelBtn')}
                </button>
                <button
                  className="documents-tab__modal-btn documents-tab__modal-btn--secondary"
                  onClick={() => saveEdit(true)}
                  disabled={savingEdit}
                  title={t('documentsTab.saveAsNewVersionTooltip') as string}
                >
                  {t('documentsTab.saveAsNewVersion')}
                </button>
                <button
                  className="documents-tab__modal-btn documents-tab__modal-btn--primary"
                  onClick={() => saveEdit(false)}
                  disabled={savingEdit}
                >
                  {savingEdit ? t('documentsTab.saving') : t('documentsTab.saveBtn')}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}

      {/* Versions Modal */}
      {versionsFor &&
        createPortal(
          <div className="documents-tab__modal-overlay" onClick={() => setVersionsFor(null)}>
            <div className="documents-tab__view-modal" onClick={(e) => e.stopPropagation()}>
              <div className="documents-tab__modal-header">
                <h3>{t('documentsTab.versionHistoryTitle', { title: versionsFor.title })}</h3>
                <button onClick={() => setVersionsFor(null)} aria-label={t('documentsTab.close')}>
                  <Icon path={mdiClose} size={0.85} />
                </button>
              </div>

              <div className="documents-tab__view-content">
                {versionsLoading ? (
                  <p>{t('documentsTab.loadingVersions')}</p>
                ) : versionList.length === 0 ? (
                  <p className="documents-tab__view-empty">
                    {t('documentsTab.noVersionsYet')}
                  </p>
                ) : (
                  <ul className="documents-tab__version-list">
                    {versionList.map((v) => (
                      <li key={v.id} className="documents-tab__version-row">
                        <div>
                          <strong>v{v.version}</strong> — {v.title}
                          <div className="documents-tab__version-meta">
                            {new Date(v.updated_at || v.created_at).toLocaleString()} ·{' '}
                            {v.word_count || 0} {t('documentsTab.wordsLabel')}
                          </div>
                        </div>
                        <button
                          className="documents-tab__action-btn"
                          onClick={async () => {
                            // Open this version in the View modal
                            try {
                              const res = await fetch(`${API_BASE_URL}/api/documents/${v.id}`, {
                                headers: { Authorization: `Bearer ${token}` },
                              });
                              if (res.ok) {
                                const full = await res.json();
                                setVersionsFor(null);
                                setViewingDocument(full);
                              }
                            } catch (err) {
                              console.error('Failed to load version:', err);
                            }
                          }}
                        >
                          Open
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )}

      {/* Full-screen WYSIWYG editor (Phase 1) */}
      {fullEditDoc && (
        <DocumentEditor
          key={fullEditDoc.id}
          doc={fullEditDoc}
          onClose={() => setFullEditDoc(null)}
          onSave={saveFromEditor}
        />
      )}

      {/* Document Generator Wizard */}
      <DocumentGeneratorWizard
        isOpen={showGeneratorWizard}
        onClose={() => {
          setShowGeneratorWizard(false);
          setPresetGenerator(null);
        }}
        onDocumentGenerated={() => {
          fetchDocuments({ search: searchQuery || undefined });
        }}
        presetDocType={presetGenerator?.docType}
        presetTopic={presetGenerator?.topic}
      />
    </div>
  );
};
