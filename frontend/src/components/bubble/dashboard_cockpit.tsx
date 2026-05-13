/**
 * Dashboard cockpit — the six-tile front door of My EU Bubble.
 *
 * One backend call (/api/dashboard/tiles). Each tile renders either real
 * items from the DB or an honest empty state with one concrete CTA. Never
 * shows mock content.
 *
 * Drill-down navigates into the existing My EU Bubble sub-tab; the
 * "Talk to Brubru" handoff opens Chat with a pre-loaded prompt.
 */

import { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import {
  mdiCreation,
  mdiSwapHorizontalBold,
  mdiScaleUnbalanced,
  mdiCalendarClock,
  mdiShieldCheckOutline,
  mdiBullhornOutline,
  mdiArrowRight,
  mdiMessageOutline,
  mdiAccountCircleOutline,
} from '@mdi/js';

import {
  useDashboard,
  type CalendarEventItem,
  type ComplianceSignalItem,
  type NewThisWeekItem,
  type PositionStressItem,
  type TileEmptyState,
  type TrackedFileMovingItem,
  type VoiceOpportunityItem,
} from '../../hooks/use_dashboard';
import { useAuth } from '../../hooks/use_auth';
import { ProactiveOpener } from '../shared/proactive_opener';
import './dashboard_cockpit.css';

const formatDate = (iso?: string | null) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
    });
  } catch {
    return '';
  }
};

const formatStatus = (raw?: string | null) =>
  raw ? raw.replace(/_/g, ' ') : '';

const TILE_ICONS: Record<string, string> = {
  new_this_week: mdiCreation,
  tracked_files_moving: mdiSwapHorizontalBold,
  positions_under_stress: mdiScaleUnbalanced,
  next_seven_days: mdiCalendarClock,
  compliance_signals: mdiShieldCheckOutline,
  voice_opportunities: mdiBullhornOutline,
};

const TILE_LABELS: Record<string, string> = {
  new_this_week: 'New this week for you',
  tracked_files_moving: 'Your tracked files moving',
  positions_under_stress: 'Positions under stress',
  next_seven_days: 'Next 7 days',
  compliance_signals: 'Compliance signals',
  voice_opportunities: 'Voice opportunities',
};

const TILE_OPEN_LABELS: Record<string, string> = {
  new_this_week: 'Open My Files',
  tracked_files_moving: 'Open My Files',
  positions_under_stress: 'Open Position Analysis',
  next_seven_days: 'Open My EU Calendar',
  compliance_signals: 'Open EU Law Comply',
  voice_opportunities: 'Open EC Consultations',
};

interface TileShellProps {
  tileKey: keyof typeof TILE_ICONS;
  total: number;
  emptyState: TileEmptyState | null;
  drillPath: string;
  chatPrompt: string | null;
  children: React.ReactNode;
}

const TileShell = ({
  tileKey,
  total,
  emptyState,
  drillPath,
  chatPrompt,
  children,
}: TileShellProps) => {
  const navigate = useNavigate();

  const onDrill = () => navigate(drillPath);
  const onChat = () => {
    if (!chatPrompt) return;
    navigate(`/main?q=${encodeURIComponent(chatPrompt)}&autofire=1`);
  };
  const onCta = () => {
    if (emptyState) navigate(emptyState.cta_path);
  };

  return (
    <article className="dashboard-cockpit__tile">
      <header
        className="dashboard-cockpit__tile-header"
        onClick={onDrill}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onDrill();
        }}
      >
        <span className="dashboard-cockpit__tile-icon">
          <Icon path={TILE_ICONS[tileKey]} size={1} color="#0693E3" />
        </span>
        <h3 className="dashboard-cockpit__tile-title">
          {TILE_LABELS[tileKey]}
        </h3>
        {!emptyState && total > 0 && (
          <span className="dashboard-cockpit__tile-count">{total}</span>
        )}
      </header>

      <div className="dashboard-cockpit__tile-body">
        {emptyState ? (
          <div className="dashboard-cockpit__empty">
            <p className="dashboard-cockpit__empty-message">
              {emptyState.message}
            </p>
            <button
              className="dashboard-cockpit__empty-cta"
              type="button"
              onClick={onCta}
            >
              {emptyState.cta_label}
              <Icon path={mdiArrowRight} size={0.7} />
            </button>
          </div>
        ) : (
          children
        )}
      </div>

      {!emptyState && (
        <footer className="dashboard-cockpit__tile-footer">
          <button
            type="button"
            className="dashboard-cockpit__tile-action"
            onClick={onDrill}
          >
            {TILE_OPEN_LABELS[tileKey] || 'Open'}
            <Icon path={mdiArrowRight} size={0.7} />
          </button>
          {chatPrompt && (
            <button
              type="button"
              className="dashboard-cockpit__tile-action dashboard-cockpit__tile-action--chat"
              onClick={onChat}
            >
              <Icon path={mdiMessageOutline} size={0.7} />
              Talk to Brubru about this
            </button>
          )}
        </footer>
      )}
    </article>
  );
};

const renderNewThisWeekItem = (item: NewThisWeekItem) => (
  <li key={item.carriage_id} className="dashboard-cockpit__item">
    <div className="dashboard-cockpit__item-title">{item.title}</div>
    <div className="dashboard-cockpit__item-meta">
      {item.procedure_ref && (
        <span className="dashboard-cockpit__item-pill">
          {item.procedure_ref}
        </span>
      )}
      {item.current_status && (
        <span className="dashboard-cockpit__item-pill dashboard-cockpit__item-pill--status">
          {formatStatus(item.current_status)}
        </span>
      )}
      {item.matched_interests.slice(0, 2).map((tag) => (
        <span
          key={tag}
          className="dashboard-cockpit__item-pill dashboard-cockpit__item-pill--interest"
        >
          {tag}
        </span>
      ))}
    </div>
  </li>
);

const renderTrackedFileMovingItem = (item: TrackedFileMovingItem) => (
  <li key={`${item.carriage_id}-${item.changed_at ?? ''}`} className="dashboard-cockpit__item">
    <div className="dashboard-cockpit__item-title">{item.title}</div>
    <div className="dashboard-cockpit__item-meta">
      {item.procedure_ref && (
        <span className="dashboard-cockpit__item-pill">
          {item.procedure_ref}
        </span>
      )}
      <span className="dashboard-cockpit__item-transition">
        {item.old_status ? formatStatus(item.old_status) : 'previous'}
        {' → '}
        <strong>{formatStatus(item.new_status)}</strong>
      </span>
      {item.changed_at && (
        <span className="dashboard-cockpit__item-when">
          {formatDate(item.changed_at)}
        </span>
      )}
    </div>
  </li>
);

const renderPositionStressItem = (item: PositionStressItem) => (
  <li key={`${item.carriage_id}-${item.detected_at ?? ''}`} className="dashboard-cockpit__item">
    <div className="dashboard-cockpit__item-title">{item.title}</div>
    <div className="dashboard-cockpit__item-meta">
      {item.procedure_ref && (
        <span className="dashboard-cockpit__item-pill">
          {item.procedure_ref}
        </span>
      )}
      <span className="dashboard-cockpit__item-detail">{item.detail}</span>
    </div>
  </li>
);

const renderCalendarEventItem = (item: CalendarEventItem) => (
  <li key={item.event_id} className="dashboard-cockpit__item">
    <div className="dashboard-cockpit__item-title">{item.title}</div>
    <div className="dashboard-cockpit__item-meta">
      <span className="dashboard-cockpit__item-pill">
        {formatDate(item.start_date)}
        {item.end_date && item.end_date !== item.start_date
          ? ` – ${formatDate(item.end_date)}`
          : ''}
      </span>
      {item.institution && (
        <span className="dashboard-cockpit__item-pill dashboard-cockpit__item-pill--institution">
          {item.institution}
        </span>
      )}
      {item.event_type && (
        <span className="dashboard-cockpit__item-pill">
          {formatStatus(item.event_type)}
        </span>
      )}
    </div>
  </li>
);

const renderComplianceItem = (item: ComplianceSignalItem) => (
  <li key={item.eu_law_id} className="dashboard-cockpit__item">
    <div className="dashboard-cockpit__item-title">{item.title}</div>
    <div className="dashboard-cockpit__item-meta">
      {item.celex && (
        <span className="dashboard-cockpit__item-pill">{item.celex}</span>
      )}
      {item.policy_area && (
        <span className="dashboard-cockpit__item-pill dashboard-cockpit__item-pill--interest">
          {item.policy_area}
        </span>
      )}
      {item.adopted_on && (
        <span className="dashboard-cockpit__item-when">
          adopted {formatDate(item.adopted_on)}
        </span>
      )}
    </div>
  </li>
);

const renderVoiceItem = (item: VoiceOpportunityItem) => (
  <li key={item.consultation_id} className="dashboard-cockpit__item">
    <div className="dashboard-cockpit__item-title">{item.title}</div>
    <div className="dashboard-cockpit__item-meta">
      {item.initiative_id && (
        <span className="dashboard-cockpit__item-pill">
          {item.initiative_id}
        </span>
      )}
      {item.end_date && (
        <span className="dashboard-cockpit__item-pill dashboard-cockpit__item-pill--deadline">
          closes {formatDate(item.end_date)}
          {typeof item.days_until_deadline === 'number'
            ? ` · ${item.days_until_deadline}d left`
            : ''}
        </span>
      )}
    </div>
  </li>
);

export const DashboardCockpit = () => {
  const navigate = useNavigate();
  const { data, isLoading, error, fetchTiles } = useDashboard();
  const { isAuthenticated, user } = useAuth();
  const profileSignature = `${user?.policy_interests ?? ''}|${(user?.sectors || []).join(',')}|${user?.country ?? ''}|${user?.organization ?? ''}|${user?.role_title ?? ''}`;

  useEffect(() => {
    if (isAuthenticated) {
      void fetchTiles();
    }
    // Refetch when the user edits any personalisation signal — keeps the
    // cockpit honest after a save on the /profile page.
  }, [isAuthenticated, profileSignature, fetchTiles]);

  const completeness = data?.profile_completeness;
  const completenessPct = useMemo(
    () => (completeness ? Math.round(completeness.score * 100) : 0),
    [completeness],
  );

  if (!isAuthenticated) {
    return null;
  }

  if (isLoading && !data) {
    return (
      <section className="dashboard-cockpit dashboard-cockpit--loading">
        <p>Loading your cockpit...</p>
      </section>
    );
  }

  if (error && !data) {
    return (
      <section className="dashboard-cockpit dashboard-cockpit--error">
        <p>We could not load the cockpit right now. {error}</p>
      </section>
    );
  }

  if (!data) {
    return null;
  }

  const t = data.tiles;

  return (
    <section className="dashboard-cockpit">
      <ProactiveOpener surface="dashboard" />

      {completeness && completeness.score < 1 && (
        <div className="dashboard-cockpit__banner">
          <Icon path={mdiAccountCircleOutline} size={0.9} color="#0693E3" />
          <div className="dashboard-cockpit__banner-text">
            <strong>Your profile is {completenessPct}% complete.</strong>{' '}
            Finish it and Brubru will personalise these tiles for you.
          </div>
          <button
            type="button"
            className="dashboard-cockpit__banner-cta"
            onClick={() => navigate('/profile')}
          >
            Complete profile
          </button>
        </div>
      )}

      <div className="dashboard-cockpit__grid">
        <TileShell
          tileKey="new_this_week"
          total={t.new_this_week.total}
          emptyState={t.new_this_week.empty_state}
          drillPath={t.new_this_week.drill_down_path}
          chatPrompt={t.new_this_week.chat_handoff_prompt}
        >
          <ul className="dashboard-cockpit__items">
            {t.new_this_week.items.map(renderNewThisWeekItem)}
          </ul>
        </TileShell>

        <TileShell
          tileKey="tracked_files_moving"
          total={t.tracked_files_moving.total}
          emptyState={t.tracked_files_moving.empty_state}
          drillPath={t.tracked_files_moving.drill_down_path}
          chatPrompt={t.tracked_files_moving.chat_handoff_prompt}
        >
          <ul className="dashboard-cockpit__items">
            {t.tracked_files_moving.items.map(renderTrackedFileMovingItem)}
          </ul>
        </TileShell>

        <TileShell
          tileKey="positions_under_stress"
          total={t.positions_under_stress.total}
          emptyState={t.positions_under_stress.empty_state}
          drillPath={t.positions_under_stress.drill_down_path}
          chatPrompt={t.positions_under_stress.chat_handoff_prompt}
        >
          <ul className="dashboard-cockpit__items">
            {t.positions_under_stress.items.map(renderPositionStressItem)}
          </ul>
        </TileShell>

        <TileShell
          tileKey="next_seven_days"
          total={t.next_seven_days.total}
          emptyState={t.next_seven_days.empty_state}
          drillPath={t.next_seven_days.drill_down_path}
          chatPrompt={t.next_seven_days.chat_handoff_prompt}
        >
          <ul className="dashboard-cockpit__items">
            {t.next_seven_days.items.map(renderCalendarEventItem)}
          </ul>
        </TileShell>

        <TileShell
          tileKey="compliance_signals"
          total={t.compliance_signals.total}
          emptyState={t.compliance_signals.empty_state}
          drillPath={t.compliance_signals.drill_down_path}
          chatPrompt={t.compliance_signals.chat_handoff_prompt}
        >
          <ul className="dashboard-cockpit__items">
            {t.compliance_signals.items.map(renderComplianceItem)}
          </ul>
        </TileShell>

        <TileShell
          tileKey="voice_opportunities"
          total={t.voice_opportunities.total}
          emptyState={t.voice_opportunities.empty_state}
          drillPath={t.voice_opportunities.drill_down_path}
          chatPrompt={t.voice_opportunities.chat_handoff_prompt}
        >
          <ul className="dashboard-cockpit__items">
            {t.voice_opportunities.items.map(renderVoiceItem)}
          </ul>
        </TileShell>
      </div>
    </section>
  );
};
