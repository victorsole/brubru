// frontend/src/pages/amendator_page.tsx
import { useState } from 'react';
import Icon from '@mdi/react';
import { mdiContentSave } from '@mdi/js';
import { Sidebar } from '../components/shared/sidebar';
import type { LegislativeElement, CellAmendment } from '../components/amendator/two_column_layout';
import { TwoColumnLayout } from '../components/amendator/two_column_layout';
import { AmendmentSidebar } from '../components/amendator/amendment_sidebar';
import { AIAssistantSidebar } from '../components/amendator/ai_assistant_sidebar';
import type { AISuggestion } from '../components/amendator/ai_assistant_sidebar';
import type { LoadedDocument } from '../components/amendator/document_viewer';
import './amendator_page.css';

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

interface AmendatorPageProps {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
}

export const AmendatorPage = ({ isSidebarOpen, setIsSidebarOpen }: AmendatorPageProps) => {
  const [selectedAmendment, setSelectedAmendment] = useState<Amendment | null>(null);
  const [loadedDocument, setLoadedDocument] = useState<LoadedDocument | null>(null);
  const [isAISidebarOpen, setIsAISidebarOpen] = useState(() => {
    // Start closed on mobile to not cover content
    if (typeof window !== 'undefined') {
      return window.innerWidth > 767;
    }
    return true;
  });
  const [selectedElement, setSelectedElement] = useState<LegislativeElement | null>(null);
  const [elementIndex, setElementIndex] = useState<number | null>(null);
  const [cellAmendments, setCellAmendments] = useState<Map<number, CellAmendment>>(new Map());
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

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

  const toggleAISidebar = () => {
    setIsAISidebarOpen(!isAISidebarOpen);
  };

  const handleSelectAmendment = (amendment: Amendment) => {
    setSelectedAmendment(amendment);
  };

  const handleDocumentLoaded = (document: LoadedDocument) => {
    setLoadedDocument(document);
  };

  const handleElementSelected = (element: LegislativeElement, index: number) => {
    setSelectedElement(element);
    setElementIndex(index);
  };

  const handleAmendmentsChange = (amendments: Map<number, CellAmendment>) => {
    setCellAmendments(amendments);
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
      const response = await fetch('http://localhost:8000/api/amendments/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
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
    // Apply AI suggestion to the selected element
    if (elementIndex !== null) {
      // This will be passed down to TwoColumnLayout to update the amendment
      // For now, we'll just log it
      console.log('AI Suggestion accepted for element', elementIndex, suggestion);
      // TODO: Update the element text in TwoColumnLayout
    }
  };

  return (
    <div className="amendator-page">
      {/* Right Sidebar: Saved Amendments */}
      <Sidebar isOpen={isSidebarOpen} onToggle={toggleSidebar}>
        <AmendmentSidebar
          amendments={amendments}
          onSelectAmendment={handleSelectAmendment}
          selectedAmendmentId={selectedAmendment?.id}
          documentId={loadedDocument?.document_id}
        />
      </Sidebar>

      {/* Main Content Area */}
      <main className={`amendator-page__main ${isSidebarOpen ? 'amendator-page__main--sidebar-open' : ''} ${isAISidebarOpen ? 'amendator-page__main--ai-sidebar-open' : ''}`}>
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
          onAmendmentsChange={handleAmendmentsChange}
        />

        {/* Right Sidebar: AI Assistant */}
        <AIAssistantSidebar
          isOpen={isAISidebarOpen}
          onToggle={toggleAISidebar}
          selectedElement={selectedElement}
          onSuggestionAccepted={handleAISuggestionAccepted}
        />
      </main>
    </div>
  );
};
