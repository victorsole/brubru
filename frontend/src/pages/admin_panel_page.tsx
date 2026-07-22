// frontend/src/pages/admin_panel_page.tsx
import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/use_auth';
import { useNavigate } from 'react-router-dom';
import { AdminDashboard } from '../components/admin/admin_dashboard';
import { UserManagement } from '../components/admin/user_management';
import { FeedManagement } from '../components/admin/feed_management';
import { FeedbackManagement } from '../components/admin/feedback_management';
import { SystemMonitoring } from '../components/admin/system_monitoring';
import { ChatExamplesManagement } from '../components/admin/chat_examples_management';
import { EUComplyManagementEnhanced } from '../components/admin/eu_comply_management_enhanced';
import { AmendmentsManagement } from '../components/admin/amendments_management';
import { DocumentsManagement } from '../components/admin/documents_management';
import { SubscriptionsManagement } from '../components/admin/subscriptions_management';
import { NotificationsCenter } from '../components/admin/notifications_center';
import { EUBubbleAdmin } from '../components/admin/eu_bubble_admin';
import { LegislativeTracking } from '../components/admin/legislative_tracking';
import { ChatAnalytics } from '../components/admin/chat_analytics';
import { BillingManagement } from '../components/admin/billing_management';
import { OutreachManagement } from '../components/admin/outreach_management';
import { TenderatorManagement } from '../components/admin/tenderator_management';
import './admin_panel_page.css';

type AdminTab =
  | 'dashboard'
  | 'users'
  | 'feeds'
  | 'feedback'
  | 'monitoring'
  | 'chat_examples'
  | 'eu_comply'
  | 'amendments'
  | 'documents'
  | 'subscriptions'
  | 'billing'
  | 'outreach'
  | 'tenderator'
  | 'notifications'
  | 'eu_bubble'
  | 'legislative_tracking'
  | 'chat_analytics';

export const AdminPanelPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<AdminTab>('dashboard');

  // Check if user is admin, redirect if not
  useEffect(() => {
    if (user && user.role !== 'admin') {
      // Redirect non-admin users to home page
      navigate('/');
    }
  }, [user, navigate]);

  // Show loading or return null while checking auth
  if (!user) {
    return (
      <div className="admin-panel">
        <div className="admin-panel__loading">Loading...</div>
      </div>
    );
  }

  // Only render admin panel if user is admin
  if (user.role !== 'admin') {
    return null;
  }

  return (
    <div className="admin-panel">
      <div className="admin-panel__header">
        <h1>Admin Panel</h1>
        <p className="admin-panel__subtitle">
          Comprehensive system management and analytics
        </p>
      </div>

      {/* Navigation Tabs */}
      <nav className="admin-panel__nav">
        <button
          className={`admin-panel__nav-item ${activeTab === 'dashboard' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          <span className="admin-panel__nav-icon mdi mdi-view-dashboard"></span>
          Dashboard
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'users' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <span className="admin-panel__nav-icon mdi mdi-account-group"></span>
          Users
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'subscriptions' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('subscriptions')}
        >
          <span className="admin-panel__nav-icon mdi mdi-cash-multiple"></span>
          Subscriptions
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'billing' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('billing')}
        >
          <span className="admin-panel__nav-icon mdi mdi-credit-card-outline"></span>
          Billing &amp; API
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'outreach' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('outreach')}
        >
          <span className="admin-panel__nav-icon mdi mdi-email-fast"></span>
          Outreach
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'tenderator' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('tenderator')}
        >
          <span className="admin-panel__nav-icon mdi mdi-file-certificate"></span>
          Tenderator
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'amendments' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('amendments')}
        >
          <span className="admin-panel__nav-icon mdi mdi-file-edit"></span>
          Amendments
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'documents' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          <span className="admin-panel__nav-icon mdi mdi-file-cabinet"></span>
          Documents
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'feeds' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('feeds')}
        >
          <span className="admin-panel__nav-icon mdi mdi-rss"></span>
          Feeds
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'eu_bubble' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('eu_bubble')}
        >
          <span className="admin-panel__nav-icon mdi mdi-earth"></span>
          EU Bubble
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'legislative_tracking' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('legislative_tracking')}
        >
          <span className="admin-panel__nav-icon mdi mdi-train"></span>
          Legislation
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'notifications' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('notifications')}
        >
          <span className="admin-panel__nav-icon mdi mdi-bell-ring"></span>
          Notifications
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'chat_analytics' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('chat_analytics')}
        >
          <span className="admin-panel__nav-icon mdi mdi-chart-line"></span>
          Chat Analytics
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'feedback' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('feedback')}
        >
          <span className="admin-panel__nav-icon mdi mdi-comment-text"></span>
          Feedback
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'monitoring' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('monitoring')}
        >
          <span className="admin-panel__nav-icon mdi mdi-monitor-eye"></span>
          Monitoring
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'chat_examples' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('chat_examples')}
        >
          <span className="admin-panel__nav-icon mdi mdi-lightbulb"></span>
          Chat Examples
        </button>
        <button
          className={`admin-panel__nav-item ${activeTab === 'eu_comply' ? 'admin-panel__nav-item--active' : ''}`}
          onClick={() => setActiveTab('eu_comply')}
        >
          <span className="admin-panel__nav-icon mdi mdi-scale-balance"></span>
          EU Law Comply
        </button>
      </nav>

      {/* Content Area */}
      <div className="admin-panel__content">
        {activeTab === 'dashboard' && <AdminDashboard />}
        {activeTab === 'users' && <UserManagement />}
        {activeTab === 'subscriptions' && <SubscriptionsManagement />}
        {activeTab === 'billing' && <BillingManagement />}
        {activeTab === 'outreach' && <OutreachManagement />}
        {activeTab === 'tenderator' && <TenderatorManagement />}
        {activeTab === 'amendments' && <AmendmentsManagement />}
        {activeTab === 'documents' && <DocumentsManagement />}
        {activeTab === 'feeds' && <FeedManagement />}
        {activeTab === 'eu_bubble' && <EUBubbleAdmin />}
        {activeTab === 'legislative_tracking' && <LegislativeTracking />}
        {activeTab === 'notifications' && <NotificationsCenter />}
        {activeTab === 'chat_analytics' && <ChatAnalytics />}
        {activeTab === 'feedback' && <FeedbackManagement />}
        {activeTab === 'monitoring' && <SystemMonitoring />}
        {activeTab === 'chat_examples' && <ChatExamplesManagement />}
        {activeTab === 'eu_comply' && <EUComplyManagementEnhanced />}
      </div>
    </div>
  );
};
