// frontend/src/pages/my_eu_bubble_page.tsx
import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiViewDashboard, mdiFileDocument, mdiFileEdit, mdiTrain,
  mdiStarOutline, mdiCalendarCollapseHorizontal, mdiCrystalBall, mdiCreation,
  mdiCalendarMonth, mdiScaleBalance, mdiCompareHorizontal, mdiBookmarkMultipleOutline, mdiMicrophoneMessage,
  mdiCommentQuestionOutline, mdiHandshakeOutline, mdiAccountGroup, mdiAccountTieOutline,
  mdiMenu, mdiChevronDoubleLeft, mdiChevronDoubleRight, mdiClose, mdiGavel,
  mdiNewspaperVariantOutline, mdiNewspaperVariantMultipleOutline, mdiBookshelf, mdiFlaskOutline,
  mdiGraphOutline, mdiBullseyeArrow,
  mdiRobotOutline, mdiBriefcaseSearchOutline, mdiAccountCircleOutline, mdiApi,
} from '@mdi/js';
import { useAuth } from '../hooks/use_auth';
import { DashboardTab } from '../components/bubble/dashboard_tab';
import { MeubHeader } from '../components/bubble/meub_header';
import { MeubAskLauncher } from '../components/bubble/meub_ask_launcher';
import { FeedbackHost } from '../components/shared/feedback_host';
import { DocumentsTab } from '../components/bubble/documents_tab';
import { AmendmentsTab } from '../components/bubble/amendments_tab';
import { LegislativeTrackerTab } from '../components/bubble/legislative_tracker_tab';
import { MyTrackedFilesTab } from '../components/bubble/my_tracked_files_tab';
import { ECConsultationsTab } from '../components/bubble/ec_consultations_tab';
import { ConsultationsCTA } from '../components/bubble/consultations_cta';
import { PredictionsTab } from '../components/bubble/predictions_tab';
import { EUCalendarTab } from '../components/bubble/eu_calendar_tab';
import { EUCalendarCTA } from '../components/bubble/eu_calendar_cta';
import { PositionAnalysisTab } from '../components/bubble/position_analysis_tab';
import { DatabasesTab } from '../components/bubble/databases_tab';
import { ResearchEvidenceTab } from '../components/bubble/research_evidence_tab';
import { StakeholderMapTab } from '../components/bubble/stakeholder_map_tab';
import { StrategyDocsTab } from '../components/bubble/strategy_docs_tab';
import { TenderDocsMeubTab } from '../components/bubble/tender_docs_meub_tab';
import { ComparatorTab } from '../components/bubble/comparator_tab';
import { VotesTab } from '../components/bubble/votes_tab';
import { OJTab } from '../components/bubble/oj_tab';
import { NewsTab } from '../components/bubble/news_tab';
import { TranscriptsTab } from '../components/bubble/transcripts_tab';
import { ParliamentaryQuestionsTab } from '../components/bubble/parliamentary_questions_tab';
import { LobbyMeetingsTab } from '../components/bubble/lobby_meetings_tab';
import { CouncilWatchTab } from '../components/bubble/council_watch_tab';
import { MepWatchTab } from '../components/bubble/mep_watch_tab';
import { PlenaryAgendaTab } from '../components/bubble/plenary_agenda_tab';
import { PolicyPreferencesSelector } from '../components/profile/policy_preferences_selector';
import { FeedbackInvitation } from '../components/shared/feedback_invitation';
import './my_eu_bubble_page.css';

type TabType =
  | 'dashboard' | 'policy_interests' | 'documents'
  | 'my_files' | 'oj' | 'amendments' | 'comparator' | 'legislative' | 'votes'
  | 'eu_calendar' | 'consultations' | 'news' | 'transcripts' | 'parliamentary_questions' | 'lobby_meetings'
  | 'council_watch' | 'mep_watch' | 'plenary_agenda'
  | 'position_analysis' | 'predictions' | 'databases' | 'research_evidence' | 'stakeholder_mapping' | 'strategy_docs' | 'tender_docs';

const VALID_TABS: TabType[] = [
  'dashboard', 'policy_interests', 'documents',
  'my_files', 'oj', 'amendments', 'comparator', 'legislative', 'votes',
  'eu_calendar', 'news', 'transcripts', 'council_watch', 'mep_watch', 'plenary_agenda',
  'parliamentary_questions', 'consultations', 'lobby_meetings',
  'position_analysis', 'predictions', 'databases', 'research_evidence', 'stakeholder_mapping', 'strategy_docs', 'tender_docs',
];

// Defensive aliases: the canonical tab id, the component filename, and the name
// used in the Chat system prompt / nav label do not always match (e.g. the tab
// id is `legislative` but the file is legislative_tracker_tab and the prompt
// says "Legislative Tracker"). If any cross-link emits one of those alternative
// spellings, resolve it to the canonical id instead of falling back to the
// dashboard. Canonical ids are unchanged, so every existing link keeps working.
const TAB_ALIASES: Record<string, TabType> = {
  legislative_tracker: 'legislative',
  legislative_train: 'legislative',
  legislative_trains: 'legislative',
  ec_consultations: 'consultations',
  ec_public_consultations: 'consultations',
  stakeholder_map: 'stakeholder_mapping',
  stakeholder: 'stakeholder_mapping',
  tracked_files: 'my_files',
  my_tracked_files: 'my_files',
  overview: 'dashboard',
  my_oj: 'oj',
};

/** Resolve a raw `?tab=` value to a canonical TabType, or null if unknown. */
const resolveTab = (raw: string | null): TabType | null => {
  if (!raw) return null;
  if (VALID_TABS.includes(raw as TabType)) return raw as TabType;
  return TAB_ALIASES[raw] ?? null;
};

// Per-tab metadata: label key + icon. `dashboard` keeps its id but is now
// labelled "Overview"; `legislative` keeps its id but is now "Legislative Train".
const TAB_META: Record<TabType, { labelKey: string; fallback: string; icon: string; isPredictions?: boolean }> = {
  dashboard:         { labelKey: 'bubble.tabs.overview',          fallback: 'Overview',                 icon: mdiViewDashboard },
  policy_interests:  { labelKey: 'bubble.tabs.policyInterests',   fallback: 'Policy Interests',         icon: mdiBookmarkMultipleOutline },
  documents:         { labelKey: 'bubble.tabs.myDocuments',       fallback: 'My Documents',             icon: mdiFileDocument },
  my_files:          { labelKey: 'bubble.tabs.myTrackedFiles',    fallback: 'My Tracked Files',         icon: mdiStarOutline },
  oj:                { labelKey: 'bubble.tabs.oj',                 fallback: 'My OJ',                    icon: mdiNewspaperVariantOutline },
  amendments:        { labelKey: 'bubble.amendments',             fallback: 'Amendments',               icon: mdiFileEdit },
  comparator:        { labelKey: 'bubble.tabs.comparator',        fallback: 'Comparator',               icon: mdiCompareHorizontal },
  legislative:       { labelKey: 'bubble.tabs.legislativeTrain',  fallback: 'Legislative Train',        icon: mdiTrain },
  votes:             { labelKey: 'bubble.tabs.votes',             fallback: 'Votes',                    icon: mdiGavel },
  eu_calendar:       { labelKey: 'bubble.tabs.euCalendar',        fallback: 'My EU Calendar',           icon: mdiCalendarMonth },
  consultations:     { labelKey: 'bubble.tabs.consultations',     fallback: 'EU Public Consultations',  icon: mdiCalendarCollapseHorizontal },
  news:              { labelKey: 'bubble.tabs.news',              fallback: 'News',                     icon: mdiNewspaperVariantMultipleOutline },
  transcripts:       { labelKey: 'bubble.tabs.transcripts',       fallback: 'Transcripts',              icon: mdiMicrophoneMessage },
  parliamentary_questions: { labelKey: 'bubble.tabs.parliamentaryQuestions', fallback: 'Parliamentary Questions', icon: mdiCommentQuestionOutline },
  lobby_meetings:    { labelKey: 'bubble.tabs.lobbyMeetings',     fallback: 'Lobby Meetings',           icon: mdiHandshakeOutline },
  council_watch:     { labelKey: 'bubble.tabs.councilWatch',      fallback: 'Council Watch',            icon: mdiAccountGroup },
  mep_watch:         { labelKey: 'bubble.tabs.mepWatch',          fallback: 'MEP Watch',                icon: mdiAccountTieOutline },
  plenary_agenda:    { labelKey: 'bubble.tabs.plenaryAgenda',     fallback: 'Plenary Order of Business', icon: mdiGavel },
  position_analysis: { labelKey: 'bubble.tabs.positionAnalysis',  fallback: 'Position Analysis',        icon: mdiScaleBalance },
  predictions:       { labelKey: 'bubble.tabs.predictions',       fallback: 'Predictions',              icon: mdiCrystalBall, isPredictions: true },
  databases:         { labelKey: 'bubble.databases',              fallback: 'Brubru Databases',         icon: mdiBookshelf },
  research_evidence: { labelKey: 'bubble.research_evidence',      fallback: 'Research & Evidence',      icon: mdiFlaskOutline },
  stakeholder_mapping: { labelKey: 'bubble.stakeholder_mapping',  fallback: 'Stakeholder Mapping',      icon: mdiGraphOutline },
  strategy_docs:     { labelKey: 'bubble.strategy_docs',          fallback: 'Strategy Docs',            icon: mdiBullseyeArrow },
  tender_docs:       { labelKey: 'bubble.tender_docs',            fallback: 'Tender Docs',              icon: mdiBriefcaseSearchOutline },
};

// The 4-section information architecture (doc 03). Section titles render as
// small-caps group headers in the folding left sidebar.
const SECTIONS: { id: string; titleKey: string; titleFallback: string; withName?: boolean; items: TabType[] }[] = [
  { id: 'corner',        titleKey: 'bubble.sections.corner',        titleFallback: 'Start here',                             items: ['dashboard', 'policy_interests', 'documents', 'news'] },
  { id: 'legislative',   titleKey: 'bubble.sections.legislative',   titleFallback: 'Legislative Monitoring',                 items: ['my_files', 'oj', 'amendments', 'comparator', 'legislative', 'votes'] },
  { id: 'institutional', titleKey: 'bubble.sections.institutional', titleFallback: 'Institutional Monitoring',               items: ['eu_calendar', 'transcripts', 'council_watch', 'mep_watch', 'plenary_agenda', 'parliamentary_questions', 'consultations', 'lobby_meetings'] },
  { id: 'strategy',      titleKey: 'bubble.sections.strategy',      titleFallback: 'Analysis & Strategy',                    items: ['position_analysis', 'predictions', 'databases', 'research_evidence', 'stakeholder_mapping', 'strategy_docs', 'tender_docs'] },
];

// Section 5: links OUT to the other Brubru products (navigate, not internal tabs).
const OTHER_FEATURES: { key: string; labelKey: string; fallback: string; icon: string; route: string }[] = [
  { key: 'amendator',   labelKey: 'bubble.feat.amendator',   fallback: 'Amendator',     icon: mdiFileEdit,               route: '/amendator' },
  { key: 'chat',        labelKey: 'bubble.feat.chat',        fallback: 'Chat',          icon: mdiRobotOutline,           route: '/chat' },
  { key: 'eulawcomply', labelKey: 'bubble.feat.eulawcomply', fallback: 'EU Law Comply', icon: mdiScaleBalance,           route: '/eulawcomply' },
  { key: 'tenderator',  labelKey: 'bubble.feat.tenderator',  fallback: 'Tenderator',    icon: mdiBriefcaseSearchOutline, route: '/tenderator' },
  { key: 'api',         labelKey: 'bubble.feat.api',         fallback: 'API',           icon: mdiApi,                    route: '/api' },
  { key: 'profile',     labelKey: 'bubble.feat.profile',     fallback: 'Profile',       icon: mdiAccountCircleOutline,   route: '/profile' },
];

const SIDEBAR_COLLAPSED_KEY = 'meub_sidebar_collapsed';

export const MyEUBubblePage = () => {
  const { t } = useTranslation();
  const { user, updateProfile } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<TabType>(() => {
    return resolveTab(searchParams.get('tab')) ?? 'dashboard';
  });

  // Folding sidebar (desktop) + drawer (mobile)
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1'; } catch { return false; }
  });
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
  };

  // Policy Interests state (mirrors the profile page wiring so both surfaces
  // read/write the same users.policy_interests field).
  const [policyInterests, setPolicyInterests] = useState<string[]>([]);

  useEffect(() => {
    if (user?.policy_interests) {
      try {
        const interests = typeof user.policy_interests === 'string'
          ? JSON.parse(user.policy_interests)
          : user.policy_interests;
        setPolicyInterests(Array.isArray(interests) ? interests : []);
      } catch {
        setPolicyInterests([]);
      }
    } else {
      setPolicyInterests([]);
    }
  }, [user]);

  const handlePolicyUpdate = async (policies: string[]) => {
    setPolicyInterests(policies);
    try {
      await updateProfile({ policy_interests: JSON.stringify(policies) });
    } catch (err) {
      console.error('Failed to update policy interests', err);
    }
  };

  // Respond to URL param changes (e.g. from calendar deep-links)
  useEffect(() => {
    const resolved = resolveTab(searchParams.get('tab'));
    if (resolved) {
      setActiveTab(resolved);
    }
  }, [searchParams]);

  const selectTab = (id: TabType) => {
    setActiveTab(id);
    setMobileNavOpen(false);
  };

  const firstName = (user?.full_name || '').trim().split(/\s+/)[0] || t('common.there', 'there');
  const initials = (user?.full_name || '?')
    .split(/\s+/).filter(Boolean).slice(0, 2).map(p => p[0]?.toUpperCase() || '').join('') || '?';

  const tabLabel = (id: TabType) => t(TAB_META[id].labelKey, TAB_META[id].fallback);
  const sectionTitle = (s: typeof SECTIONS[number]) =>
    s.withName ? t(s.titleKey, { name: firstName, defaultValue: s.titleFallback.replace('{{name}}', firstName) })
               : t(s.titleKey, s.titleFallback);

  const renderTabContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardTab />;
      case 'policy_interests':
        return (
          <div className="my-eu-bubble-page__policy-pane">
            <MeubHeader
              icon={mdiBookmarkMultipleOutline}
              title={t('bubble.tabs.policyInterests', 'Policy Interests')}
              subtitle={t('bubble.policyInterestsIntro', "These are the European Commission's own policy areas. Choose the ones that matter to you and Brubru pre-selects the legislative and non-legislative files currently being worked on under them, above all at the European Parliament, so they flow into your feed, calendar and alerts. You can always fine-tune the list later by adding or removing individual files in My Tracked Files.")}
            />
            <PolicyPreferencesSelector selectedPolicies={policyInterests} onUpdate={handlePolicyUpdate} />
          </div>
        );
      case 'my_files':
        return <MyTrackedFilesTab />;
      case 'oj':
        return <OJTab />;
      case 'amendments':
        return <AmendmentsTab />;
      case 'comparator':
        return <ComparatorTab />;
      case 'legislative':
        return <LegislativeTrackerTab />;
      case 'votes':
        return <VotesTab />;
      case 'eu_calendar':
        // Show CTA for White tier users, full calendar for Yellow+ tiers
        if (!user || user.subscription_tier === 'white') {
          return <EUCalendarCTA />;
        }
        return <EUCalendarTab />;
      case 'consultations':
        // Show CTA for White tier users, full tab for Yellow+ tiers
        if (!user || user.subscription_tier === 'white') {
          return <ConsultationsCTA />;
        }
        return <ECConsultationsTab />;
      case 'news':
        return <NewsTab />;
      case 'transcripts':
        return <TranscriptsTab />;
      case 'parliamentary_questions':
        return <ParliamentaryQuestionsTab />;
      case 'lobby_meetings':
        return <LobbyMeetingsTab />;
      case 'council_watch':
        return <CouncilWatchTab />;
      case 'mep_watch':
        return <MepWatchTab />;
      case 'plenary_agenda':
        return <PlenaryAgendaTab />;
      case 'position_analysis':
        return <PositionAnalysisTab />;
      case 'predictions':
        return <PredictionsTab />;
      case 'documents':
        return <DocumentsTab />;
      case 'databases':
        return <DatabasesTab />;
      case 'research_evidence':
        return <ResearchEvidenceTab />;
      case 'stakeholder_mapping':
        return <StakeholderMapTab />;
      case 'strategy_docs':
        return <StrategyDocsTab />;
      case 'tender_docs':
        return <TenderDocsMeubTab />;
      default:
        return <DashboardTab />;
    }
  };

  // Get background image URL if user has selected one
  const backgroundImage = user?.background_preference && user.background_preference !== 'default'
    ? `/assets/backgrounds/${user.background_preference}`
    : null;

  const renderNavItem = (id: TabType) => {
    const meta = TAB_META[id];
    const isActive = activeTab === id;
    const isPred = !!meta.isPredictions;
    return (
      <button
        key={id}
        type="button"
        className={[
          'my-eu-bubble-nav__item',
          isActive ? 'my-eu-bubble-nav__item--active' : '',
          isPred ? 'my-eu-bubble-nav__item--predictions' : '',
        ].join(' ').trim()}
        onClick={() => selectTab(id)}
        aria-current={isActive ? 'page' : undefined}
        title={collapsed ? tabLabel(id) : undefined}
      >
        <span className="my-eu-bubble-nav__item-icon">
          <Icon
            path={meta.icon}
            size={0.9}
            color={isPred && isActive ? 'url(#predictionGradient)' : (isActive ? '#0693E3' : '#5b6b7a')}
          />
        </span>
        <span className={`my-eu-bubble-nav__item-label ${isPred && isActive ? 'my-eu-bubble-nav__item-label--gradient' : ''}`}>
          {isPred && isActive && <Icon path={mdiCreation} size={0.55} className="my-eu-bubble-nav__sparkle" />}
          {tabLabel(id)}
        </span>
      </button>
    );
  };

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
          src="/assets/brubru_mainlogo.png"
          alt={t('bubble.title')}
          className="my-eu-bubble-page__icon"
        />
        <div className="my-eu-bubble-page__header-text">
          <h1>{t('bubble.title')}</h1>
          <p className="my-eu-bubble-page__subtitle">
            {t('bubble.subtitle')}
          </p>
        </div>
        {/* Mobile-only: open the navigation drawer */}
        <button
          type="button"
          className="my-eu-bubble-page__mobile-menu"
          onClick={() => setMobileNavOpen(true)}
          aria-label={t('bubble.sidebar.menu', 'Menu')}
        >
          <Icon path={mdiMenu} size={1.1} />
          <span>{tabLabel(activeTab)}</span>
        </button>
      </div>

      <div className={`my-eu-bubble-page__layout ${collapsed ? 'my-eu-bubble-page__layout--collapsed' : ''}`}>
        {/* Folding left sidebar (module navigation) */}
        {mobileNavOpen && (
          <div className="my-eu-bubble-nav__scrim" onClick={() => setMobileNavOpen(false)} aria-hidden="true" />
        )}
        <aside className={`my-eu-bubble-nav ${collapsed ? 'my-eu-bubble-nav--collapsed' : ''} ${mobileNavOpen ? 'my-eu-bubble-nav--open' : ''}`}>
          <div className="my-eu-bubble-nav__head">
            <div className="my-eu-bubble-nav__avatar" aria-hidden="true">{initials}</div>
            {!collapsed && (
              <div className="my-eu-bubble-nav__who">
                <span className="my-eu-bubble-nav__name">{user?.full_name || firstName}</span>
                {user?.role_title && <span className="my-eu-bubble-nav__role">{user.role_title}</span>}
              </div>
            )}
            {/* Mobile-only close */}
            <button
              type="button"
              className="my-eu-bubble-nav__close"
              onClick={() => setMobileNavOpen(false)}
              aria-label={t('common.close', 'Close')}
            >
              <Icon path={mdiClose} size={1} />
            </button>
          </div>

          <nav className="my-eu-bubble-nav__sections">
            {SECTIONS.map(section => (
              <div className="my-eu-bubble-nav__section" key={section.id}>
                {!collapsed && (
                  <p className="my-eu-bubble-nav__section-title">{sectionTitle(section)}</p>
                )}
                {collapsed && <div className="my-eu-bubble-nav__section-rule" aria-hidden="true" />}
                {section.items.map(renderNavItem)}
              </div>
            ))}

            {/* Section 5: links out to the other Brubru products */}
            <div className="my-eu-bubble-nav__section" key="other">
              {!collapsed && (
                <p className="my-eu-bubble-nav__section-title">{t('bubble.sections.other', 'Other Brubru Features')}</p>
              )}
              {collapsed && <div className="my-eu-bubble-nav__section-rule" aria-hidden="true" />}
              {OTHER_FEATURES.map(feature => (
                <button
                  key={feature.key}
                  type="button"
                  className="my-eu-bubble-nav__item"
                  onClick={() => { setMobileNavOpen(false); navigate(feature.route); }}
                  title={collapsed ? t(feature.labelKey, feature.fallback) : undefined}
                >
                  <span className="my-eu-bubble-nav__item-icon">
                    <Icon path={feature.icon} size={0.9} color="#5b6b7a" />
                  </span>
                  <span className="my-eu-bubble-nav__item-label">{t(feature.labelKey, feature.fallback)}</span>
                </button>
              ))}
            </div>
          </nav>

          {/* Desktop collapse toggle */}
          <button
            type="button"
            className="my-eu-bubble-nav__toggle"
            onClick={toggleCollapsed}
            aria-label={collapsed ? t('bubble.sidebar.expand', 'Expand sidebar') : t('bubble.sidebar.collapse', 'Collapse sidebar')}
            title={collapsed ? t('bubble.sidebar.expand', 'Expand sidebar') : t('bubble.sidebar.collapse', 'Collapse sidebar')}
          >
            <Icon path={collapsed ? mdiChevronDoubleRight : mdiChevronDoubleLeft} size={0.9} />
            {!collapsed && <span>{t('bubble.sidebar.collapse', 'Collapse sidebar')}</span>}
          </button>
        </aside>

        {/* Workspace. Every tab gets the full content width. The scraped-items
            feed ("Latest Updates") now lives INSIDE Overview, beside the cockpit,
            instead of as a global right rail. */}
        <div className="my-eu-bubble-page__main">
          <div className="my-eu-bubble-page__content">
            {renderTabContent()}
          </div>
        </div>
      </div>

      {/* Feedback Section */}
      <FeedbackInvitation
        featureName={t('bubble.feedbackTitle')}
        featureDescription={t('bubble.feedbackDescription')}
        variant="card"
      />

      {/* Persistent, context-aware Chat entry point — one launcher for the whole shell. */}
      <MeubAskLauncher tabLabel={tabLabel(activeTab)} />

      {/* App-level toasts + confirm dialog (replaces native alert/confirm). */}
      <FeedbackHost />
    </div>
  );
};
