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

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  mdiChevronUp,
  mdiChevronDown,
  mdiDragVertical,
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
import { uiDateLocale } from '../../i18n/config';

const formatDate = (iso?: string | null) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(uiDateLocale(), {
      day: 'numeric',
      month: 'short',
    });
  } catch {
    return '';
  }
};

const formatStatus = (raw?: string | null) =>
  raw ? raw.replace(/_/g, ' ') : '';

// Friendly labels for the InstitutionEnum codes. Verbose multi-word codes get a
// readable name; anything else (agency acronyms like ECB/EMA/ENISA) stays as-is.
const INSTITUTION_LABELS: Record<string, string> = {
  EP: 'European Parliament',
  COUNCIL: 'Council of the EU',
  EUROPEAN_COUNCIL: 'European Council',
  COMMISSION: 'European Commission',
  THIRD_PARTY: 'External event',
};

const formatInstitution = (raw?: string | null): string => {
  if (!raw) return '';
  if (INSTITUTION_LABELS[raw]) return INSTITUTION_LABELS[raw];
  // Multi-word codes (e.g. EU_OSHA) → title case; lone acronyms stay uppercase.
  return raw.includes('_')
    ? raw
        .split('_')
        .map((w) => (w.length <= 4 ? w : w.charAt(0) + w.slice(1).toLowerCase()))
        .join(' ')
    : raw;
};

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
  new_this_week: 'Open Legislative Tracker',
  tracked_files_moving: 'Open My Files',
  positions_under_stress: 'Open Position Analysis',
  next_seven_days: 'Open My EU Calendar',
  compliance_signals: 'Open EU Law Comply',
  voice_opportunities: 'Open EC Consultations',
};

const TILE_KEYS = [
  'new_this_week',
  'tracked_files_moving',
  'positions_under_stress',
  'next_seven_days',
  'compliance_signals',
  'voice_opportunities',
] as const;
type TileKey = (typeof TILE_KEYS)[number];

const ORDER_STORAGE_KEY = 'meub_cockpit_order_v1';
const FOLD_STORAGE_KEY = 'meub_cockpit_folds_v1';

// Load the saved tile order, dropping unknown keys and appending any new tiles
// that did not exist when the order was last saved (forwards-compatible).
const loadOrder = (): TileKey[] => {
  try {
    const raw = localStorage.getItem(ORDER_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        const valid = parsed.filter((k): k is TileKey =>
          (TILE_KEYS as readonly string[]).includes(k),
        );
        const merged = [
          ...valid,
          ...TILE_KEYS.filter((k) => !valid.includes(k)),
        ];
        if (merged.length === TILE_KEYS.length) return merged;
      }
    }
  } catch {
    /* ignore corrupt storage */
  }
  return [...TILE_KEYS];
};

const loadFolds = (): Record<string, boolean> => {
  try {
    const raw = localStorage.getItem(FOLD_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        return parsed as Record<string, boolean>;
      }
    }
  } catch {
    /* ignore corrupt storage */
  }
  return {};
};

interface TileShellProps {
  tileKey: keyof typeof TILE_ICONS;
  total: number;
  emptyState: TileEmptyState | null;
  drillPath: string;
  chatPrompt: string | null;
  children: React.ReactNode;
  folded: boolean;
  onToggleFold: () => void;
  dragging: boolean;
  dropTarget: boolean;
  onDragStart: () => void;
  onDragEnter: () => void;
  onDragEnd: () => void;
  onDrop: () => void;
}

const TileShell = ({
  tileKey,
  total,
  emptyState,
  drillPath,
  chatPrompt,
  children,
  folded,
  onToggleFold,
  dragging,
  dropTarget,
  onDragStart,
  onDragEnter,
  onDragEnd,
  onDrop,
}: TileShellProps) => {
  const { t } = useTranslation();
  const tChat = t('talkToBrubru');
  const navigate = useNavigate();

  const onDrill = () => navigate(drillPath);
  const onChat = () => {
    if (!chatPrompt) return;
    navigate(`/chat?q=${encodeURIComponent(chatPrompt)}&autofire=1`);
  };
  const onCta = () => {
    if (emptyState) navigate(emptyState.cta_path);
  };

  const className =
    'dashboard-cockpit__tile' +
    (folded ? ' dashboard-cockpit__tile--folded' : '') +
    (dragging ? ' dashboard-cockpit__tile--dragging' : '') +
    (dropTarget ? ' dashboard-cockpit__tile--drop' : '');

  return (
    <article
      className={className}
      draggable
      onDragStart={onDragStart}
      onDragEnter={onDragEnter}
      onDragOver={(e) => e.preventDefault()}
      onDragEnd={onDragEnd}
      onDrop={(e) => {
        e.preventDefault();
        onDrop();
      }}
    >
      <header className="dashboard-cockpit__tile-header">
        <span
          className="dashboard-cockpit__tile-grip"
          title={t('dashboard.dragToReorder', 'Drag to reorder')}
          aria-hidden="true"
        >
          <Icon path={mdiDragVertical} size={0.8} color="#c2cdda" />
        </span>
        <span className="dashboard-cockpit__tile-icon">
          <Icon path={TILE_ICONS[tileKey]} size={1} color="#0693E3" />
        </span>
        <h3 className="dashboard-cockpit__tile-title">
          {t('cockpit.tile.' + tileKey, TILE_LABELS[tileKey])}
        </h3>
        {!emptyState && total > 0 && (
          <span className="dashboard-cockpit__tile-count">{total}</span>
        )}
        <button
          type="button"
          className="dashboard-cockpit__tile-fold"
          onClick={onToggleFold}
          aria-expanded={!folded}
          aria-label={
            folded
              ? t('dashboard.expandTile', 'Expand')
              : t('dashboard.collapseTile', 'Collapse')
          }
        >
          <Icon path={folded ? mdiChevronDown : mdiChevronUp} size={0.9} color="#7a8aa0" />
        </button>
      </header>

      {!folded && (
        <>
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
                {t('cockpit.tileOpen.' + tileKey, TILE_OPEN_LABELS[tileKey] || 'Open')}
                <Icon path={mdiArrowRight} size={0.7} />
              </button>
              {chatPrompt && (
                <button
                  type="button"
                  className="dashboard-cockpit__tile-action dashboard-cockpit__tile-action--chat"
                  onClick={onChat}
                >
                  <Icon path={mdiMessageOutline} size={0.7} />
                  {tChat}
                </button>
              )}
            </footer>
          )}
        </>
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
        {item.old_status ? (
          <>
            {formatStatus(item.old_status)}
            {' → '}
            <strong>{formatStatus(item.new_status)}</strong>
          </>
        ) : (
          <strong>{formatStatus(item.new_status)}</strong>
        )}
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
          {formatInstitution(item.institution)}
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
  const { t: i18nT } = useTranslation();
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

  // Per-user-browser cockpit layout: tile order + folded state, both persisted.
  const [order, setOrder] = useState<TileKey[]>(loadOrder);
  const [folds, setFolds] = useState<Record<string, boolean>>(loadFolds);
  const dragKey = useRef<TileKey | null>(null);
  const [draggingKey, setDraggingKey] = useState<TileKey | null>(null);
  const [overKey, setOverKey] = useState<TileKey | null>(null);

  const toggleFold = (key: TileKey) => {
    setFolds((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem(FOLD_STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const handleDragStart = (key: TileKey) => {
    dragKey.current = key;
    setDraggingKey(key);
  };
  const handleDragEnter = (key: TileKey) => {
    if (dragKey.current && dragKey.current !== key) setOverKey(key);
  };
  const handleDrop = (key: TileKey) => {
    const from = dragKey.current;
    setOverKey(null);
    if (!from || from === key) return;
    setOrder((prev) => {
      const arr = prev.filter((x) => x !== from);
      const idx = arr.indexOf(key);
      arr.splice(idx < 0 ? arr.length : idx, 0, from);
      try {
        localStorage.setItem(ORDER_STORAGE_KEY, JSON.stringify(arr));
      } catch {
        /* ignore */
      }
      return arr;
    });
  };
  const handleDragEnd = () => {
    dragKey.current = null;
    setDraggingKey(null);
    setOverKey(null);
  };

  if (!isAuthenticated) {
    return null;
  }

  if (isLoading && !data) {
    return (
      <section className="dashboard-cockpit dashboard-cockpit--loading">
        <p>{i18nT('dashboard.loadingCockpit')}</p>
      </section>
    );
  }

  if (error && !data) {
    return (
      <section className="dashboard-cockpit dashboard-cockpit--error">
        <p>{i18nT('cockpit.error', 'We could not load the cockpit right now.')} {error}</p>
      </section>
    );
  }

  if (!data) {
    return null;
  }

  const t = data.tiles;

  const renderItems = (key: TileKey) => {
    switch (key) {
      case 'new_this_week':
        return t.new_this_week.items.map(renderNewThisWeekItem);
      case 'tracked_files_moving':
        return t.tracked_files_moving.items.map(renderTrackedFileMovingItem);
      case 'positions_under_stress':
        return t.positions_under_stress.items.map(renderPositionStressItem);
      case 'next_seven_days':
        return t.next_seven_days.items.map(renderCalendarEventItem);
      case 'compliance_signals':
        return t.compliance_signals.items.map(renderComplianceItem);
      case 'voice_opportunities':
        return t.voice_opportunities.items.map(renderVoiceItem);
      default:
        return null;
    }
  };

  return (
    <section className="dashboard-cockpit">
      <ProactiveOpener surface="dashboard" />

      {completeness && completeness.score < 1 && (
        <div className="dashboard-cockpit__banner">
          <Icon path={mdiAccountCircleOutline} size={0.9} color="#0693E3" />
          <div className="dashboard-cockpit__banner-text">
            <strong>{i18nT('cockpit.profileComplete', { pct: completenessPct, defaultValue: 'Your profile is {{pct}}% complete.' })}</strong>{' '}
            {i18nT('cockpit.profileFinish', 'Finish it and Brubru will personalise these tiles for you.')}
          </div>
          <button
            type="button"
            className="dashboard-cockpit__banner-cta"
            onClick={() => navigate('/profile')}
          >
            {i18nT('cockpit.completeProfile', 'Complete profile')}
          </button>
        </div>
      )}

      <div className="dashboard-cockpit__grid">
        {order.map((key) => {
          const tile = t[key];
          if (!tile) return null;
          return (
            <TileShell
              key={key}
              tileKey={key}
              total={tile.total}
              emptyState={tile.empty_state}
              drillPath={tile.drill_down_path}
              chatPrompt={tile.chat_handoff_prompt}
              folded={!!folds[key]}
              onToggleFold={() => toggleFold(key)}
              dragging={draggingKey === key}
              dropTarget={overKey === key}
              onDragStart={() => handleDragStart(key)}
              onDragEnter={() => handleDragEnter(key)}
              onDragEnd={handleDragEnd}
              onDrop={() => handleDrop(key)}
            >
              <ul className="dashboard-cockpit__items">{renderItems(key)}</ul>
            </TileShell>
          );
        })}
      </div>
    </section>
  );
};
