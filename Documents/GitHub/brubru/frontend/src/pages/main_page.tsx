// frontend/src/pages/main_page.tsx
import { useState } from 'react';
import { Sidebar } from '../components/shared/sidebar';
import { ChatInterface } from '../components/chat/chat_interface';
import { DocumentUpload } from '../components/chat/document_upload';
import './main_page.css';

export const MainPage = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  return (
    <div className="main-page">
      <Sidebar isOpen={isSidebarOpen} onToggle={toggleSidebar}>
        <div className="main-page__sidebar-content">
          {/* Chat History Section - Placeholder for now */}
          <div className="main-page__history">
            <h3 className="main-page__history-title">Chat History</h3>
            <p className="main-page__history-placeholder">
              Previous conversations will appear here
            </p>
          </div>

          {/* Document Upload Section */}
          <div className="main-page__documents">
            <DocumentUpload />
          </div>
        </div>
      </Sidebar>

      <main className={`main-page__main ${isSidebarOpen ? 'main-page__main--sidebar-open' : ''}`}>
        <ChatInterface />
      </main>
    </div>
  );
};
