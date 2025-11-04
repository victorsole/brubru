// frontend/src/components/amendator/two_column_layout.tsx
import { DocumentViewer } from './document_viewer';
import { AmendmentEditor } from './amendment_editor';
import type { Amendment } from '../../pages/amendator_page';
import './two_column_layout.css';

interface TwoColumnLayoutProps {
  selectedAmendment: Amendment | null;
  onSaveAmendment: (amendment: Amendment) => void;
  onCancelEdit: () => void;
}

export const TwoColumnLayout = ({
  selectedAmendment,
  onSaveAmendment,
  onCancelEdit,
}: TwoColumnLayoutProps) => {
  return (
    <div className="two-column-layout">
      {/* Left Column: Original Legislative Text */}
      <div className="two-column-layout__column two-column-layout__column--left">
        <div className="two-column-layout__header">
          <h2 className="two-column-layout__title">Original Text</h2>
        </div>
        <DocumentViewer selectedText={selectedAmendment?.originalText} />
      </div>

      {/* Right Column: Proposed Amendment */}
      <div className="two-column-layout__column two-column-layout__column--right">
        <div className="two-column-layout__header">
          <h2 className="two-column-layout__title">Proposed Amendment</h2>
        </div>
        <AmendmentEditor
          amendment={selectedAmendment}
          onSave={onSaveAmendment}
          onCancel={onCancelEdit}
        />
      </div>
    </div>
  );
};
