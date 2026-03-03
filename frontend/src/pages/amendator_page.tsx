// frontend/src/pages/amendator_page.tsx
import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import Icon from '@mdi/react';
import { mdiContentSave, mdiFileEditOutline, mdiRobotOutline } from '@mdi/js';
import { Sidebar } from '../components/shared/sidebar';
import type { LegislativeElement, CellAmendment, PendingAIAmendment } from '../components/amendator/two_column_layout';
import { TwoColumnLayout } from '../components/amendator/two_column_layout';
import { AmendmentSidebar } from '../components/amendator/amendment_sidebar';
import { AIAssistantPanel } from '../components/amendator/ai_assistant_sidebar';
import type { AISuggestion } from '../components/amendator/ai_assistant_sidebar';
import type { LoadedDocument } from '../components/amendator/document_viewer';
import { LegislativeContextBanner } from '../components/amendator/legislative_context_banner';
import { useAuth } from '../hooks/use_auth';
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

type SidebarTab = 'amendments' | 'ai';

interface AmendatorPageProps {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
}

export const AmendatorPage = ({ isSidebarOpen, setIsSidebarOpen }: AmendatorPageProps) => {
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

  // Deep-link: auto-load document from ?celex= query param
  useEffect(() => {
    const celex = searchParams.get('celex');
    if (!celex || loadedDocument) return;

    const loadFromCelex = async () => {
      try {
        const eurlexUrl = `https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:${celex}`;
        const response = await fetch(`${API_BASE}/documents/fetch-eurlex`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: eurlexUrl, format: 'html', language: 'EN' }),
        });
        if (response.ok) {
          const doc = await response.json();
          setLoadedDocument({
            document_id: doc.document_id,
            filename: doc.filename,
            text: doc.text,
            metadata: doc.metadata,
            structure: doc.structure,
          });
        }
      } catch (err) {
        console.error('Failed to auto-load CELEX document:', err);
      }
      // Clear the celex param so it doesn't re-trigger
      setSearchParams({}, { replace: true });
    };

    loadFromCelex();
  }, [searchParams, loadedDocument, setSearchParams]);

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
      setSaveMessage('No amendments to save');
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
            justification: '',
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
      setSaveMessage(`Successfully saved ${savedAmendments.length} amendments!`);
      setTimeout(() => setSaveMessage(null), 5000);

    } catch (error) {
      console.error('Error saving amendments:', error);
      setSaveMessage('Error saving amendments. Please try again.');
      setTimeout(() => setSaveMessage(null), 5000);
    } finally {
      setIsSaving(false);
    }
  };

  const handleAISuggestionAccepted = (suggestion: AISuggestion) => {
    const pending: PendingAIAmendment = {
      elementIndex: elementIndex ?? undefined,
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
              <span className="amendator-sidebar__tab-label">Amendments</span>
              {amendments.length > 0 && (
                <span className="amendator-sidebar__tab-badge">{amendments.length}</span>
              )}
            </button>
            <button
              className={`amendator-sidebar__tab ${activeTab === 'ai' ? 'amendator-sidebar__tab--active' : ''}`}
              onClick={() => setActiveTab('ai')}
            >
              <Icon path={mdiRobotOutline} size={0.8} />
              <span className="amendator-sidebar__tab-label">AI Assistant</span>
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
                loadedDocument={loadedDocument}
                onSuggestionAccepted={handleAISuggestionAccepted}
                onBatchSuggestionsAccepted={handleBatchSuggestionsAccepted}
              />
            </div>
          </div>
        </div>
      </Sidebar>

      {/* Main Content Area */}
      <main className={`amendator-page__main ${isSidebarOpen ? 'amendator-page__main--sidebar-open' : ''}`}>
        {/* Save Amendments Bar */}
        {loadedDocument && cellAmendments.size > 0 && (
          <div className="amendator-page__save-bar">
            <div className="amendator-page__save-info">
              <span className="amendator-page__amendment-count">
                {cellAmendments.size} amendment{cellAmendments.size !== 1 ? 's' : ''} pending
              </span>
              {saveMessage && (
                <span className={`amendator-page__save-message ${saveMessage.includes('Error') ? 'amendator-page__save-message--error' : 'amendator-page__save-message--success'}`}>
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
              {isSaving ? 'Saving...' : 'Save Amendments'}
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
