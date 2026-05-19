// frontend/src/pages/tenderator_page.tsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TenderDetail } from '../components/tenders/tender_detail';
import { BidChecklist } from '../components/tenders/bid_checklist';
import { TenderCalendar } from '../components/tenders/tender_calendar';
import { TenderProfileSetup } from '../components/tenders/tender_profile_setup';
import { TenderatorDashboard } from '../components/tenders/tenderator_dashboard';
import { useAuth } from '../hooks/use_auth';
import './tenderator_page.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Award criterion extracted from eForms XML
export interface AwardCriterion {
  type?: string;
  name?: string;
  description?: string;
  weight?: number;
}

export interface Tender {
  id: number;
  publication_number: string;
  title: string;
  buyer_name: string;
  buyer_country: string;
  estimated_value: number | null;
  currency: string;
  cpv_main: string;
  cpv_codes: string[];
  procedure_type: string;
  submission_deadline: string | null;
  publication_date: string;
  status: string;
  sme_suitability_score: number | null;
  description?: string;
  award_criteria?: AwardCriterion[] | Record<string, number>;  // Array (new) or object (legacy)
  award_criteria_type?: string;  // 'quality', 'price', 'cost', 'best-value'
  lots_count?: number;
  ted_url?: string;
}

export interface TenderMatch {
  id: number;
  tender_id: number;
  user_id: string;
  match_score: number;
  match_reasons: string[];
  match_details: Record<string, number> | null;
  is_viewed: boolean;
  is_saved: boolean;
  is_dismissed: boolean;
  is_applied: boolean;
  user_notes: string | null;
  user_rating: number | null;
  created_at: string;
  tender: Tender;
}

export interface TenderProfile {
  id: number;
  user_id: string;
  company_name: string;
  company_size: string;
  annual_turnover: number | null;
  employee_count: number | null;
  cpv_categories: string[];
  countries_of_interest: string[];
  keywords: string[];
  max_tender_value: number | null;
  min_tender_value: number | null;
  min_deadline_days: number;
  preferred_procedures: string[];
  notification_frequency: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserTenderStats {
  total_matches: number;
  saved_tenders: number;
  dismissed_tenders: number;
  applied_tenders: number;
  average_match_score: number | null;
  matches_this_week: number;
}

type ViewState = 'dashboard' | 'detail' | 'checklist' | 'calendar' | 'profile';

interface TenderatorPageProps {
  isSidebarOpen?: boolean;
  setIsSidebarOpen?: (open: boolean) => void;
}

export const TenderatorPage = ({ isSidebarOpen: _isSidebarOpen }: TenderatorPageProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [viewState, setViewState] = useState<ViewState>('dashboard');
  const [selectedTender, setSelectedTender] = useState<Tender | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<TenderMatch | null>(null);
  const [userProfile, setUserProfile] = useState<TenderProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasBlueAccess, setHasBlueAccess] = useState(true);

  // Fetch user profile and stats on mount
  useEffect(() => {
    if (token) {
      fetchUserData();
    }
  }, [token]);

  const fetchUserData = async () => {
    setIsLoading(true);
    try {
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      };

      // Fetch profile
      const profileRes = await fetch(`${API_URL}/api/tenders/profile/me`, { headers });
      if (profileRes.status === 403) {
        setHasBlueAccess(false);
        setIsLoading(false);
        return;
      }
      if (profileRes.ok) {
        const profileData = await profileRes.json();
        setUserProfile(profileData);
      } else if (profileRes.status === 404) {
        // No profile yet - show profile setup
        setUserProfile(null);
      }

      // Note: the dashboard cockpit fetches its own KPIs directly from
      // /api/tenders/dashboard-stats. We no longer need the page-level
      // statistics call here.
    } catch (err) {
      console.error('Error fetching user data:', err);
      setError(t('tenderator.errorLoad'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectTender = (tender: Tender, match?: TenderMatch) => {
    setSelectedTender(tender);
    setSelectedMatch(match || null);
    setViewState('detail');
  };

  const handleViewChecklist = (tender: Tender) => {
    setSelectedTender(tender);
    setViewState('checklist');
  };

  const handleBackToFeed = () => {
    setSelectedTender(null);
    setSelectedMatch(null);
    setViewState('dashboard');
  };

  const handleSaveMatch = async (matchId: number) => {
    try {
      const response = await fetch(`${API_URL}/api/tenders/matches/${matchId}/save`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        // Refresh stats
        fetchUserData();
      }
    } catch (err) {
      console.error('Error saving match:', err);
    }
  };

  const handleDismissMatch = async (matchId: number) => {
    try {
      const response = await fetch(`${API_URL}/api/tenders/matches/${matchId}/dismiss`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        handleBackToFeed();
        fetchUserData();
      }
    } catch (err) {
      console.error('Error dismissing match:', err);
    }
  };

  const handleAskChatbot = (tender: Tender, question?: string) => {
    const defaultQuestion = `I need help with tender "${tender.title}" (${tender.publication_number}).
    ${tender.description ? `Description: ${tender.description.substring(0, 500)}...` : ''}
    ${question || 'What should I know about this tender and how can I prepare a competitive bid?'}`;

    navigate('/main', {
      state: {
        initialQuestion: defaultQuestion,
        source: 'tenderator',
        tenderId: tender.id
      }
    });
  };

  const handleProfileCreated = (profile: TenderProfile) => {
    setUserProfile(profile);
    setViewState('dashboard');
    fetchUserData();
  };

  // Render Blue tier upgrade prompt
  if (!hasBlueAccess) {
    return (
      <div className="tenderator-page">
        <img
          className="tenderator-page__background-image"
          src="/assets/euro_money.jpg"
          alt="EU Tenders"
        />
        <div className="tenderator-page__background-overlay"></div>

        <div className="tenderator-page__container tenderator-page__upgrade-prompt">
          <div className="tenderator-page__header">
            <div className="tenderator-page__header-content">
              <img
                src="/assets/brubru_tenderator.png"
                alt="Tenderator"
                className="tenderator-page__mascot"
              />
              <div>
                <h1 className="tenderator-page__title">{t('tenderator.title')}</h1>
                <p className="tenderator-page__subtitle">{t('tenderator.subtitle')}</p>
              </div>
            </div>
          </div>

          <div className="tenderator-page__upgrade-card">
            <span className="mdi mdi-lock-outline tenderator-page__upgrade-icon"></span>
            <h2>{t('tenderator.upgradeTitle')}</h2>
            <p>{t('tenderator.upgradeBody')}</p>
            <ul>
              <li><span className="mdi mdi-check"></span> {t('tenderator.upgradeFeature1')}</li>
              <li><span className="mdi mdi-check"></span> {t('tenderator.upgradeFeature2')}</li>
              <li><span className="mdi mdi-check"></span> {t('tenderator.upgradeFeature3')}</li>
              <li><span className="mdi mdi-check"></span> {t('tenderator.upgradeFeature4')}</li>
              <li><span className="mdi mdi-check"></span> {t('tenderator.upgradeFeature5')}</li>
            </ul>
            <button
              className="tenderator-page__upgrade-button"
              onClick={() => navigate('/subscription')}
            >
              <span className="mdi mdi-arrow-up-circle"></span>
              {t('tenderator.upgradeButton')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="tenderator-page tenderator-page--dashboard">
      {/* Loading state */}
      {isLoading && (
        <div className="tenderator-page__loading">
          <span className="mdi mdi-loading mdi-spin"></span>
          {t('tenderator.loading')}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="tenderator-page__error">
          <span className="mdi mdi-alert-circle"></span>
          {error}
          <button onClick={() => { setError(null); fetchUserData(); }}>
            {t('tenderator.retry')}
          </button>
        </div>
      )}

      {!isLoading && !error && (
        <>
          {/* No profile yet: route the user straight to profile setup, the
              dashboard needs profile data to render the matched feed. */}
          {!userProfile && viewState !== 'profile' && (
            <div className="tenderator-page__setup-prompt">
              <span className="mdi mdi-account-question"></span>
              <h3>{t('tenderator.setupTitle')}</h3>
              <p>{t('tenderator.setupBody')}</p>
              <button onClick={() => setViewState('profile')}>
                <span className="mdi mdi-account-plus"></span>
                {t('tenderator.createProfile')}
              </button>
            </div>
          )}

          {/* Dashboard cockpit (default landing view) */}
          {viewState === 'dashboard' && userProfile && (
            <TenderatorDashboard
              userProfile={userProfile}
              onSelectTender={handleSelectTender}
              onViewChecklist={handleViewChecklist}
              onOpenProfile={() => setViewState('profile')}
              onOpenCalendar={() => setViewState('calendar')}
            />
          )}

          {/* Detail view */}
          {viewState === 'detail' && selectedTender && (
            <TenderDetail
              tender={selectedTender}
              match={selectedMatch}
              onBack={handleBackToFeed}
              onSave={selectedMatch ? () => handleSaveMatch(selectedMatch.id) : undefined}
              onDismiss={selectedMatch ? () => handleDismissMatch(selectedMatch.id) : undefined}
              onViewChecklist={() => handleViewChecklist(selectedTender)}
              onAskChatbot={(question) => handleAskChatbot(selectedTender, question)}
            />
          )}

          {/* Checklist view */}
          {viewState === 'checklist' && selectedTender && (
            <BidChecklist
              tender={selectedTender}
              onBack={handleBackToFeed}
              onAskChatbot={(question) => handleAskChatbot(selectedTender, question)}
            />
          )}

          {/* Calendar full-screen view (accessible via header icon) */}
          {viewState === 'calendar' && userProfile && (
            <div className="tenderator-page__modal-shell">
              <button
                type="button"
                className="tenderator-page__modal-back"
                onClick={handleBackToFeed}
              >
                <span className="mdi mdi-arrow-left"></span>
                Back to dashboard
              </button>
              <TenderCalendar
                onSelectTender={handleSelectTender}
                userProfile={userProfile}
              />
            </div>
          )}

          {/* Profile setup */}
          {viewState === 'profile' && (
            <div className="tenderator-page__modal-shell">
              {userProfile && (
                <button
                  type="button"
                  className="tenderator-page__modal-back"
                  onClick={handleBackToFeed}
                >
                  <span className="mdi mdi-arrow-left"></span>
                  Back to dashboard
                </button>
              )}
              <TenderProfileSetup
                existingProfile={userProfile}
                onProfileSaved={handleProfileCreated}
                onBack={userProfile ? handleBackToFeed : undefined}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
};
