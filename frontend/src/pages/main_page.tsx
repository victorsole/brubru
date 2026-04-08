// frontend/src/pages/main_page.tsx
import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/shared/sidebar';
import { ChatInterface } from '../components/chat/chat_interface';
import { DocumentUpload } from '../components/chat/document_upload';
import { useAuth } from '../hooks/use_auth';
import './main_page.css';

interface Conversation {
  id: string;
  title: string | null;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
}

const API_BASE_URL = import.meta.env?.VITE_API_URL || (window as any).REACT_APP_API_URL || 'http://localhost:8000';

/** Group conversations into Today / Yesterday / This Week / Older */
function groupConversations(conversations: Conversation[], t: (key: string) => string) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: { label: string; items: Conversation[] }[] = [];
  const buckets: Record<string, Conversation[]> = {
    today: [],
    yesterday: [],
    thisWeek: [],
    older: [],
  };

  for (const c of conversations) {
    const d = new Date(c.last_message_at || c.created_at);
    if (d >= today) buckets.today.push(c);
    else if (d >= yesterday) buckets.yesterday.push(c);
    else if (d >= weekAgo) buckets.thisWeek.push(c);
    else buckets.older.push(c);
  }

  if (buckets.today.length) groups.push({ label: t('main.today'), items: buckets.today });
  if (buckets.yesterday.length) groups.push({ label: t('main.yesterday'), items: buckets.yesterday });
  if (buckets.thisWeek.length) groups.push({ label: t('main.thisWeek'), items: buckets.thisWeek });
  if (buckets.older.length) groups.push({ label: t('main.older'), items: buckets.older });

  return groups;
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

interface MainPageProps {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
}

export const MainPage = ({ isSidebarOpen, setIsSidebarOpen }: MainPageProps) => {
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const state = location.state as { initialQuestion?: string; source?: string; findingId?: number } | null;
  const queryParam = searchParams.get('q');
  const [uploadedDocumentIds, setUploadedDocumentIds] = useState<string[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const handleDocumentUpload = (documentId: string) => {
    setUploadedDocumentIds((prev) => [...prev, documentId]);
  };

  const fetchConversations = useCallback(async () => {
    if (!isAuthenticated || !user?.id) return;
    setIsLoadingHistory(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/list?user_id=${user.id}&limit=30`);
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setConversations(data.conversations || []);
    } catch (err) {
      console.error('Failed to load chat history:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [isAuthenticated, user?.id]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleNewChat = () => {
    setActiveChatId(null);
    // Force ChatInterface to reset by toggling to a sentinel then null
    setActiveChatId(null);
  };

  const handleSelectConversation = (id: string) => {
    setActiveChatId(id);
  };

  const groups = groupConversations(conversations, t);

  return (
    <div className="main-page">
      <Sidebar isOpen={isSidebarOpen} onToggle={toggleSidebar}>
        <div className="main-page__sidebar-content">
          <div className="main-page__history">
            <h3 className="main-page__history-title">{t('main.chatHistory')}</h3>

            {isAuthenticated ? (
              <>
                <button
                  className="main-page__new-chat-btn"
                  onClick={handleNewChat}
                  type="button"
                >
                  <span className="mdi mdi-plus" />
                  {t('main.newChat')}
                </button>

                {isLoadingHistory ? (
                  <p className="main-page__history-placeholder">{t('common.loading')}</p>
                ) : conversations.length === 0 ? (
                  <p className="main-page__history-placeholder">{t('main.noConversations')}</p>
                ) : (
                  <div className="main-page__history-list">
                    {groups.map((group) => (
                      <div key={group.label} className="main-page__history-group">
                        <span className="main-page__history-group-label">{group.label}</span>
                        {group.items.map((conv) => (
                          <button
                            key={conv.id}
                            type="button"
                            className={`main-page__history-item ${activeChatId === conv.id ? 'main-page__history-item--active' : ''}`}
                            onClick={() => handleSelectConversation(conv.id)}
                            title={conv.title || t('main.newChat')}
                          >
                            <span className="main-page__history-item-title">
                              {conv.title
                                ? (conv.title.length > 50 ? conv.title.slice(0, 50) + '...' : conv.title)
                                : t('main.newChat')}
                            </span>
                            <span className="main-page__history-item-meta">
                              <span className="main-page__history-item-time">
                                {formatRelativeTime(conv.last_message_at || conv.created_at)}
                              </span>
                              <span className="main-page__history-item-count">
                                <span className="mdi mdi-message-outline" />
                                {conv.message_count}
                              </span>
                            </span>
                          </button>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <p className="main-page__history-placeholder">{t('main.signInHistory')}</p>
            )}
          </div>

          {/* Document Upload Section - only for authenticated users */}
          {isAuthenticated && (
            <div className="main-page__documents">
              <DocumentUpload onUpload={handleDocumentUpload} />
            </div>
          )}
        </div>
      </Sidebar>

      <main className={`main-page__main ${isSidebarOpen ? 'main-page__main--sidebar-open' : ''}`}>
        <ChatInterface
          initialQuestion={queryParam || state?.initialQuestion}
          documentIds={uploadedDocumentIds}
          activeChatId={activeChatId}
          onConversationUpdate={fetchConversations}
        />
      </main>
    </div>
  );
};
