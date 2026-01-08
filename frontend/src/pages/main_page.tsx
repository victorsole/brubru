// frontend/src/pages/main_page.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { Sidebar } from '../components/shared/sidebar';
import { ChatInterface } from '../components/chat/chat_interface';
import { DocumentUpload } from '../components/chat/document_upload';
import './main_page.css';

interface MainPageProps {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
}

export const MainPage = ({ isSidebarOpen, setIsSidebarOpen }: MainPageProps) => {
  const { t } = useTranslation();
  const location = useLocation();
  const state = location.state as { initialQuestion?: string; source?: string; findingId?: number } | null;
  const [uploadedDocumentIds, setUploadedDocumentIds] = useState<string[]>([]);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const handleDocumentUpload = (documentId: string) => {
    setUploadedDocumentIds((prev) => [...prev, documentId]);
  };

  return (
    <div className="main-page">
      <Sidebar isOpen={isSidebarOpen} onToggle={toggleSidebar}>
        <div className="main-page__sidebar-content">
          {/* Chat History Section - Placeholder for now */}
          <div className="main-page__history">
            <h3 className="main-page__history-title">{t('main.chatHistory')}</h3>
            <p className="main-page__history-placeholder">
              {t('main.previousConversations')}
            </p>
          </div>

          {/* Document Upload Section */}
          <div className="main-page__documents">
            <DocumentUpload onUpload={handleDocumentUpload} />
          </div>
        </div>
      </Sidebar>

      <main className={`main-page__main ${isSidebarOpen ? 'main-page__main--sidebar-open' : ''}`}>
        <ChatInterface
          initialQuestion={state?.initialQuestion}
          documentIds={uploadedDocumentIds}
        />
      </main>
    </div>
  );
};
