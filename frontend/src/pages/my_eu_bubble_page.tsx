// frontend/src/pages/my_eu_bubble_page.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiViewDashboard, mdiFileDocument, mdiFileEdit, mdiChartLine, mdiTrain, mdiStarOutline, mdiCalendarCollapseHorizontal } from '@mdi/js';
import { useAuth } from '../hooks/use_auth';
import { DashboardTab } from '../components/bubble/dashboard_tab';
import { DocumentsTab } from '../components/bubble/documents_tab';
import { AmendmentsTab } from '../components/bubble/amendments_tab';
import { AnalyticsTab } from '../components/bubble/analytics_tab';
import { LegislativeTrackerTab } from '../components/bubble/legislative_tracker_tab';
import { MyTrackedFilesTab } from '../components/bubble/my_tracked_files_tab';
import { ECConsultationsTab } from '../components/bubble/ec_consultations_tab';
import { ConsultationsCTA } from '../components/bubble/consultations_cta';
import { NewsSidebar } from '../components/bubble/news_sidebar';
import { FeedbackInvitation } from '../components/shared/feedback_invitation';
import './my_eu_bubble_page.css';

type TabType = 'dashboard' | 'my_files' | 'consultations' | 'documents' | 'amendments' | 'analytics' | 'legislative';

export const MyEUBubblePage = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');

  const tabs = [
    { id: 'dashboard' as TabType, label: t('bubble.dashboard'), icon: mdiViewDashboard },
    { id: 'my_files' as TabType, label: 'My Files', icon: mdiStarOutline },
    { id: 'consultations' as TabType, label: t('bubble.tabs.consultations', 'EC Consultations'), icon: mdiCalendarCollapseHorizontal },
    { id: 'documents' as TabType, label: t('bubble.documents'), icon: mdiFileDocument },
    { id: 'amendments' as TabType, label: t('bubble.amendments'), icon: mdiFileEdit },
    { id: 'legislative' as TabType, label: 'Legislative Tracker', icon: mdiTrain },
    { id: 'analytics' as TabType, label: t('bubble.analytics'), icon: mdiChartLine },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardTab />;
      case 'my_files':
        return <MyTrackedFilesTab />;
      case 'consultations':
        // Show CTA for White tier users, full tab for Yellow+ tiers
        if (!user || user.subscription_tier === 'white') {
          return <ConsultationsCTA />;
        }
        return <ECConsultationsTab />;
      case 'documents':
        return <DocumentsTab />;
      case 'amendments':
        return <AmendmentsTab />;
      case 'legislative':
        return <LegislativeTrackerTab />;
      case 'analytics':
        return <AnalyticsTab />;
      default:
        return <DashboardTab />;
    }
  };

  // Get background image URL if user has selected one
  const backgroundImage = user?.background_preference && user.background_preference !== 'default'
    ? `/assets/backgrounds/${user.background_preference}`
    : null;

  return (
    <div
      className="my-eu-bubble-page"
      style={backgroundImage ? {
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed'
      } : undefined}
    >
      <div className="my-eu-bubble-page__header">
        <img
          src="/assets/brubru_myeububble.png"
          alt={t('bubble.title')}
          className="my-eu-bubble-page__icon"
        />
        <div className="my-eu-bubble-page__header-text">
          <h1>{t('bubble.title')}</h1>
          <p className="my-eu-bubble-page__subtitle">
            {t('bubble.subtitle')}
          </p>
        </div>
      </div>

      <div className="my-eu-bubble-page__layout">
        {/* Main Content Area */}
        <div className="my-eu-bubble-page__main">
          {/* Tab Navigation */}
          <nav className="my-eu-bubble-page__tabs">
            {tabs.map(tab => (
              <button
                key={tab.id}
                className={`my-eu-bubble-page__tab ${
                  activeTab === tab.id ? 'my-eu-bubble-page__tab--active' : ''
                }`}
                onClick={() => setActiveTab(tab.id)}
              >
                <span className="my-eu-bubble-page__tab-icon">
                  <Icon path={tab.icon} size={1} color="#0693E3" />
                </span>
                <span className="my-eu-bubble-page__tab-label">{tab.label}</span>
              </button>
            ))}
          </nav>

          {/* Tab Content */}
          <div className="my-eu-bubble-page__content">
            {renderTabContent()}
          </div>
        </div>

        {/* News Sidebar */}
        <aside className="my-eu-bubble-page__sidebar">
          <NewsSidebar />
        </aside>
      </div>

      {/* Feedback Section */}
      <FeedbackInvitation
        featureName="My EU Bubble"
        featureDescription="Help us improve My EU Bubble by sharing your thoughts, suggestions, or reporting any issues. Your feedback helps us create better tools for the EU policy community."
        variant="card"
      />
    </div>
  );
};
