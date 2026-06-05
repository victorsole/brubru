/**
 * MEUB Overview — the front door of My EU Bubble.
 *
 * Three parts: (1) a Chat-style personalised greeting (+ policy hooks) from
 * /api/personalization/greeting; (2) the monitoring cockpit (DashboardCockpit,
 * /api/dashboard/tiles) that synthesises the user's whole MEUB with deep-links;
 * (3) an "Explore" navigator that jumps to every MEUB filter. No "Latest Updates".
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Icon from '@mdi/react';
import {
  mdiBookmarkMultipleOutline, mdiFileDocument, mdiStarOutline, mdiNewspaperVariantOutline,
  mdiFileEdit, mdiCompareHorizontal, mdiTrain, mdiGavel, mdiCalendarMonth,
  mdiNewspaperVariantMultipleOutline, mdiMicrophoneMessage, mdiAccountGroup, mdiAccountTieOutline,
  mdiCommentQuestionOutline, mdiCalendarCollapseHorizontal, mdiHandshakeOutline, mdiScaleBalance,
  mdiCrystalBall, mdiBookshelf, mdiFlaskOutline, mdiGraphOutline, mdiBullseyeArrow,
  mdiArrowRight, mdiCreation, mdiInformationOutline,
} from '@mdi/js';
import { useAuth } from '../../hooks/use_auth';
import { DashboardCockpit } from './dashboard_cockpit';
import './dashboard_tab.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface PolicyHook { label: string; spoken?: string; suggested_query?: string; source?: string }
interface DigestItem { title: string; date?: string | null; ref?: string | null; url?: string | null }
interface DigestSection { key: string; label: string; drill: string; items: DigestItem[] }

interface NavItem { tab: string; labelKey: string; fallback: string; icon: string }
const NAV_GROUPS: { titleKey: string; fallback: string; descKey: string; descFallback: string; items: NavItem[] }[] = [
  { titleKey: 'bubble.overview.corner', fallback: 'Start here',
    descKey: 'bubble.overview.desc_corner', descFallback: 'Your starting point: set your policy interests, manage your own documents and read the news that matters to you.', items: [
    { tab: 'policy_interests', labelKey: 'bubble.tabs.policyInterests', fallback: 'Policy Interests', icon: mdiBookmarkMultipleOutline },
    { tab: 'documents', labelKey: 'bubble.tabs.myDocuments', fallback: 'My Documents', icon: mdiFileDocument },
    { tab: 'news', labelKey: 'bubble.tabs.news', fallback: 'News', icon: mdiNewspaperVariantMultipleOutline },
  ] },
  { titleKey: 'bubble.sections.legislative', fallback: 'Legislative Monitoring',
    descKey: 'bubble.overview.desc_legislative', descFallback: 'Track legislative files and their paperwork.', items: [
    { tab: 'my_files', labelKey: 'bubble.tabs.myTrackedFiles', fallback: 'My Tracked Files', icon: mdiStarOutline },
    { tab: 'oj', labelKey: 'bubble.tabs.oj', fallback: 'My OJ', icon: mdiNewspaperVariantOutline },
    { tab: 'amendments', labelKey: 'bubble.amendments', fallback: 'Amendments', icon: mdiFileEdit },
    { tab: 'comparator', labelKey: 'bubble.tabs.comparator', fallback: 'Comparator', icon: mdiCompareHorizontal },
    { tab: 'legislative', labelKey: 'bubble.tabs.legislativeTrain', fallback: 'Legislative Train', icon: mdiTrain },
    { tab: 'votes', labelKey: 'bubble.tabs.votes', fallback: 'Votes', icon: mdiGavel },
  ] },
  { titleKey: 'bubble.sections.institutional', fallback: 'Institutional Monitoring',
    descKey: 'bubble.overview.desc_institutional', descFallback: 'Follow the EU institutions.', items: [
    { tab: 'eu_calendar', labelKey: 'bubble.tabs.euCalendar', fallback: 'My EU Calendar', icon: mdiCalendarMonth },
    { tab: 'transcripts', labelKey: 'bubble.tabs.transcripts', fallback: 'Transcripts', icon: mdiMicrophoneMessage },
    { tab: 'council_watch', labelKey: 'bubble.tabs.councilWatch', fallback: 'Council Watch', icon: mdiAccountGroup },
    { tab: 'mep_watch', labelKey: 'bubble.tabs.mepWatch', fallback: 'MEP Watch', icon: mdiAccountTieOutline },
    { tab: 'plenary_agenda', labelKey: 'bubble.tabs.plenaryAgenda', fallback: 'Plenary Order of Business', icon: mdiGavel },
    { tab: 'parliamentary_questions', labelKey: 'bubble.tabs.parliamentaryQuestions', fallback: 'Parliamentary Questions', icon: mdiCommentQuestionOutline },
    { tab: 'consultations', labelKey: 'bubble.tabs.consultations', fallback: 'EC Public Consultations', icon: mdiCalendarCollapseHorizontal },
    { tab: 'lobby_meetings', labelKey: 'bubble.tabs.lobbyMeetings', fallback: 'Lobby Meetings', icon: mdiHandshakeOutline },
  ] },
  { titleKey: 'bubble.sections.strategy', fallback: 'Analysis & Strategy',
    descKey: 'bubble.overview.desc_strategy', descFallback: 'Analyse and act.', items: [
    { tab: 'position_analysis', labelKey: 'bubble.tabs.positionAnalysis', fallback: 'Position Analysis', icon: mdiScaleBalance },
    { tab: 'predictions', labelKey: 'bubble.tabs.predictions', fallback: 'Predictions', icon: mdiCrystalBall },
    { tab: 'databases', labelKey: 'bubble.databases', fallback: 'Brubru Databases', icon: mdiBookshelf },
    { tab: 'research_evidence', labelKey: 'bubble.research_evidence', fallback: 'Research & Evidence', icon: mdiFlaskOutline },
    { tab: 'stakeholder_mapping', labelKey: 'bubble.stakeholder_mapping', fallback: 'Stakeholder Mapping', icon: mdiGraphOutline },
    { tab: 'strategy_docs', labelKey: 'bubble.strategy_docs', fallback: 'Strategy Docs', icon: mdiBullseyeArrow },
  ] },
];

export const DashboardTab = () => {
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [greeting, setGreeting] = useState<string | null>(null);
  const [hooks, setHooks] = useState<PolicyHook[]>([]);
  const [digest, setDigest] = useState<DigestSection[]>([]);

  useEffect(() => {
    if (!token) return;
    axios.get(`${API_BASE_URL}/api/personalization/greeting`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { setGreeting(r.data?.message || null); setHooks(r.data?.policy_hooks || []); })
      .catch(() => { /* fall back to the time-of-day greeting below */ });
  }, [token]);

  // Phase-4 linking digest: what touched your tracked files / areas across surfaces.
  useEffect(() => {
    if (!token) return;
    axios.get(`${API_BASE_URL}/api/dashboard/digest`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => setDigest(r.data?.sections || []))
      .catch(() => { /* section just won't render */ });
  }, [token]);

  const firstName = (user?.full_name || '').trim().split(/\s+/)[0] || t('common.there', 'there');
  const fallbackGreeting = () => {
    const h = new Date().getHours();
    const part = h < 12 ? t('bubble.overview.morning', 'Good morning') : h < 18 ? t('bubble.overview.afternoon', 'Good afternoon') : t('bubble.overview.evening', 'Good evening');
    return `${part}, ${firstName}.`;
  };

  const openHook = (hook: PolicyHook) => {
    const q = hook.suggested_query || hook.label;
    navigate(`/main?q=${encodeURIComponent(q)}`);
  };

  return (
    <div className="ov">
      {/* 1. Greeting (Chat-style) */}
      <section className="ov-greeting">
        <p className="ov-greeting__text">{greeting || fallbackGreeting()}</p>
        {hooks.length > 0 && (
          <div className="ov-hooks">
            {hooks.map((hook, i) => (
              <button key={`${hook.source}-${i}`} className="ov-hook" onClick={() => openHook(hook)}>
                <Icon path={mdiCreation} size={0.6} /> {hook.label}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* 2. Synthesis — the monitoring cockpit (deep-links to every filter) */}
      <DashboardCockpit />

      {/* 2b. What touched your workspace — the Phase-4 cross-feature linking digest */}
      {digest.length > 0 && (
        <section className="ov-digest">
          <h3 className="ov-digest__title">
            <Icon path={mdiCreation} size={0.7} /> {t('bubble.overview.workspace', 'What touched your workspace')}
          </h3>
          <div className="ov-digest__grid">
            {digest.map((s) => (
              <div key={s.key} className="ov-digest__card">
                <button className="ov-digest__head" onClick={() => navigate(s.drill)}>
                  <span>{s.label}</span><Icon path={mdiArrowRight} size={0.6} />
                </button>
                <ul className="ov-digest__items">
                  {s.items.slice(0, 4).map((it, i) => (
                    <li key={i}>
                      {it.url
                        ? <a href={it.url} target="_blank" rel="noopener noreferrer">{it.title}</a>
                        : it.title}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 3. Explore — jump to any filter */}
      <section className="ov-explore">
        <h3 className="ov-explore__title">{t('bubble.overview.explore', 'Explore My EU Bubble')}</h3>
        {NAV_GROUPS.map((g) => (
          <div key={g.titleKey} className="ov-navgroup">
            <h4 className="ov-navgroup__title">
              {t(g.titleKey, { defaultValue: g.fallback, name: firstName })}
              <span className="ov-tip" tabIndex={0} aria-label={t(g.descKey, g.descFallback)}>
                <Icon path={mdiInformationOutline} size={0.6} />
                <span className="ov-tip__pop">{t(g.descKey, g.descFallback)}</span>
              </span>
            </h4>
            <div className="ov-navgrid">
              {g.items.map((it) => (
                <button key={it.tab} className="ov-navcard" onClick={() => navigate(`/my-eu-bubble?tab=${it.tab}`)}>
                  <Icon path={it.icon} size={0.95} className="ov-navcard__icon" />
                  <span className="ov-navcard__label">{t(it.labelKey, it.fallback)}</span>
                  <Icon path={mdiArrowRight} size={0.6} className="ov-navcard__go" />
                </button>
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
};
