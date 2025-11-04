// frontend/src/pages/amendator_page.tsx
import { useState } from 'react';
import { Sidebar } from '../components/shared/sidebar';
import { TwoColumnLayout } from '../components/amendator/two_column_layout';
import { AmendmentGrid } from '../components/amendator/amendment_grid';
import './amendator_page.css';

export interface Amendment {
  id: string;
  position: string;
  status: 'candidate' | 'tabled' | 'withdrawn';
  originalText: string;
  proposedText: string;
  createdAt: Date;
}

export const AmendatorPage = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [selectedAmendment, setSelectedAmendment] = useState<Amendment | null>(null);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const handleSelectAmendment = (amendment: Amendment) => {
    setSelectedAmendment(amendment);
  };

  const handleSaveAmendment = (amendment: Amendment) => {
    if (amendments.find(a => a.id === amendment.id)) {
      // Update existing
      setAmendments(prev => prev.map(a => a.id === amendment.id ? amendment : a));
    } else {
      // Add new
      setAmendments(prev => [...prev, amendment]);
    }
    setSelectedAmendment(null);
  };

  return (
    <div className="amendator-page">
      <Sidebar isOpen={isSidebarOpen} onToggle={toggleSidebar}>
        <AmendmentGrid
          amendments={amendments}
          onSelectAmendment={handleSelectAmendment}
          selectedAmendmentId={selectedAmendment?.id}
        />
      </Sidebar>

      <main className={`amendator-page__main ${isSidebarOpen ? 'amendator-page__main--sidebar-open' : ''}`}>
        <TwoColumnLayout
          selectedAmendment={selectedAmendment}
          onSaveAmendment={handleSaveAmendment}
          onCancelEdit={() => setSelectedAmendment(null)}
        />
      </main>
    </div>
  );
};
