// frontend/src/pages/my_eu_bubble_page.tsx
import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiViewDashboard, mdiFileDocument, mdiFileEdit, mdiChartLine, mdiTrain, mdiStarOutline, mdiCalendarCollapseHorizontal, mdiCrystalBall, mdiCreation, mdiCalendarMonth, mdiScaleBalance, mdiCompareHorizontal } from '@mdi/js';
import { useAuth } from '../hooks/use_auth';
import { DashboardTab } from '../components/bubble/dashboard_tab';
import { DocumentsTab } from '../components/bubble/documents_tab';
import { AmendmentsTab } from '../components/bubble/amendments_tab';
import { AnalyticsTab } from '../components/bubble/analytics_tab';
import { LegislativeTrackerTab } from '../components/bubble/legislative_tracker_tab';
import { MyTrackedFilesTab } from '../components/bubble/my_tracked_files_tab';
import { ECConsultationsTab } from '../components/bubble/ec_consultations_tab';
import { ConsultationsCTA } from '../components/bubble/consultations_cta';
import { PredictionsTab } from '../components/bubble/predictions_tab';
import { EUCalendarTab } from '../components/bubble/eu_calendar_tab';
import { EUCalendarCTA } from '../components/bubble/eu_calendar_cta';
import { PositionAnalysisTab } from '../components/bubble/position_analysis_tab';
import { ComparatorTab } from '../components/bubble/comparator_tab';
import { NewsSidebar } from '../components/bubble/news_sidebar';
import { FeedbackInvitation } from '../components/shared/feedback_invitation';
import { TalkToBrubruButton } from '../components/shared/talk_to_brubru_button';
import './my_eu_bubble_page.css';

type TabType = 'dashboard' | 'my_files' | 'position_analysis' | 'comparator' | 'eu_calendar' | 'predictions' | 'consultations' | 'documents' | 'amendments' | 'analytics' | 'legislative';

const VALID_TABS: TabType[] = [
  'dashboard', 'my_files', 'position_analysis', 'comparator', 'eu_calendar', 'predictions', 'consultations',
  'documents', 'amendments', 'analytics', 'legislative',
];

export const MyEUBubblePage = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [searchParams] = useSearchParams();

  const [activeTab, setActiveTab] = useState<TabType>(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && VALID_TABS.includes(tabParam as TabType)) {
      return tabParam as TabType;
    }
    return 'dashboard';
  });

  // Respond to URL param changes (e.g. from calendar deep-links)
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && VALID_TABS.includes(tabParam as TabType)) {
      setActiveTab(tabParam as TabType);
    }
  }, [searchParams]);

  // Tab-specific Chat hand-off prompts. Each one is a question Brubru is
  // already able to answer from the user's profile + tracked files; the
  // /main?q=...&autofire=1 navigation streams the answer immediately.
  const CHAT_HANDOFF_PROMPTS: Record<TabType, string> = {
    dashboard: "Brief me on what's new this week across my policy areas and tracked files, and what I should act on first.",
    my_files: 'Summarise the legislative files I track and what to watch this week.',
    position_analysis: 'Walk me through the positions on the files I track and which are likely to survive trilogue.',
    comparator: 'Compare the files I have selected — where do they overlap and where do they conflict?',
    eu_calendar: 'Summarise the EU institutional events in the next 7 days that touch my policy areas or tracked files.',
    predictions: 'Predict the outcome of the files I track and explain the key variables driving each prediction.',
    consultations: 'Which open EC public consultations close soon for my policy areas, and what is the strongest angle for my response?',
    documents: 'Help me draft a position paper on the file I am viewing — start with the key arguments and likely counter-positions.',
    amendments: 'Summarise the amendments tabled on my tracked files in the last week and tell me which articles are most affected.',
    legislative: 'Walk me through where my tracked legislative files sit in the pipeline and the next procedural milestones.',
    analytics: 'Which of my tracked files are gaining momentum and what does my Brubru usage tell me about my priorities?',
  };

  const tabs = [
    { id: 'dashboard' as TabType, label: t('bubble.dashboard'), icon: mdiViewDashboard },
    { id: 'my_files' as TabType, label: 'My Files', icon: mdiStarOutline },
    { id: 'position_analysis' as TabType, label: t('bubble.tabs.positionAnalysis', 'Position Analysis'), icon: mdiScaleBalance },
    { id: 'comparator' as TabType, label: 'Comparator', icon: mdiCompareHorizontal },
    { id: 'eu_calendar' as TabType, label: t('bubble.tabs.euCalendar', 'My EU Calendar'), icon: mdiCalendarMonth },
    { id: 'predictions' as TabType, label: t('bubble.tabs.predictions', 'Predictions'), icon: mdiCrystalBall, isPredictions: true },
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
      case 'position_analysis':
        return <PositionAnalysisTab />;
      case 'comparator':
        return <ComparatorTab />;
      case 'eu_calendar':
        // Show CTA for White tier users, full calendar for Yellow+ tiers
        if (!user || user.subscription_tier === 'white') {
          return <EUCalendarCTA />;
        }
        return <EUCalendarTab />;
      case 'predictions':
        return <PredictionsTab />;
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
      {/* SVG gradient definition for Predictions tab */}
      <svg width="0" height="0" style={{ position: 'absolute' }}>
        <defs>
          <linearGradient id="predictionGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style={{ stopColor: '#0693e3' }} />
            <stop offset="100%" style={{ stopColor: '#06b6d4' }} />
          </linearGradient>
        </defs>
      </svg>

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
          {/* Talk to Brubru — tab-specific Chat hand-off */}
          <div className="my-eu-bubble-page__chat-handoff">
            <TalkToBrubruButton prompt={CHAT_HANDOFF_PROMPTS[activeTab]} />
          </div>

          {/* Tab Navigation */}
          <nav className="my-eu-bubble-page__tabs">
            {tabs.map(tab => {
              const isActive = activeTab === tab.id;
              const isPredictionsTab = 'isPredictions' in tab && tab.isPredictions;

              return (
                <button
                  key={tab.id}
                  className={`my-eu-bubble-page__tab ${
                    isActive ? 'my-eu-bubble-page__tab--active' : ''
                  } ${isPredictionsTab ? 'my-eu-bubble-page__tab--predictions' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <span className={`my-eu-bubble-page__tab-icon ${isPredictionsTab && isActive ? 'my-eu-bubble-page__tab-icon--gradient' : ''}`}>
                    <Icon path={tab.icon} size={1} color={isPredictionsTab && isActive ? 'url(#predictionGradient)' : '#0693E3'} />
                  </span>
                  <span className={`my-eu-bubble-page__tab-label ${isPredictionsTab && isActive ? 'my-eu-bubble-page__tab-label--gradient' : ''}`}>
                    {isPredictionsTab && isActive && (
                      <Icon path={mdiCreation} size={0.6} className="my-eu-bubble-page__sparkle" />
                    )}
                    {tab.label}
                  </span>
                </button>
              );
            })}
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
