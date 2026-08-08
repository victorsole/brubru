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
  mdiChevronRight,
  mdiDragVertical,
  mdiOpenInNew,
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
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import { ProactiveOpener } from '../shared/proactive_opener';
import { LegislativeFileDetail } from './legislative_file_detail';
import { destinationName } from '../../utils/destination_label';
import './dashboard_cockpit.css';
import { uiDateLocale } from '../../i18n/config';

// Canonical EUR-Lex deep link for a CELEX that came from the database. Matches
// the pattern already used in parliamentary_questions_tab / consultation_detail.
const eurLexUrl = (celex: string) =>
  `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${encodeURIComponent(celex)}`;

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

// Where each tile drills to, named by the CANONICAL label of that
// destination rather than by a string of its own. These CTAs used to carry
// hand-written names that had drifted away from the navigation: the sidebar
// said "Legislative Train: state of play" while the tile said "Open
// Legislative Tracker", and "My Tracked Files" was offered as "Open My
// Files" — three names for one place, in all six languages. Composing the
// label from the tab's own key means there is one name per destination and
// the drift cannot come back.
const TILE_DESTINATION: Record<string, { key: string; fallback: string }> = {
  new_this_week: { key: 'bubble.tabs.legislativeTrain', fallback: 'Legislative Train' },
  tracked_files_moving: { key: 'bubble.tabs.myTrackedFiles', fallback: 'My Tracked Files' },
  positions_under_stress: { key: 'bubble.tabs.positionAnalysis', fallback: 'Position Analysis' },
  next_seven_days: { key: 'bubble.tabs.euCalendar', fallback: 'My EU Calendar' },
  compliance_signals: { key: 'bubble.feat.eulawcomply', fallback: 'EU Law Comply' },
  voice_opportunities: { key: 'bubble.tabs.consultations', fallback: 'EU Public Consultations' },
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
                {(() => {
                  const dest = TILE_DESTINATION[tileKey];
                  if (!dest) return t('proactive.open', 'Open');
                  return t('common.openNamed', {
                    name: destinationName(t(dest.key, dest.fallback)),
                    defaultValue: `Open ${destinationName(dest.fallback)}`,
                  });
                })()}
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

/**
 * One cockpit line.
 *
 * Every item that has a real destination becomes a real control: an in-app
 * button when the destination lives inside Brubru (the legislative file modal,
 * a sibling tab), an anchor when it lives outside (EUR-Lex, an institutional
 * source page). Items with no destination stay plain text — we never dress
 * something up as clickable when there is nowhere to go.
 *
 * The inner markup uses spans, not divs: the row body sits inside a <button>
 * or an <a>, both of which take phrasing content only. The classes carry an
 * explicit `display`, so the elements render exactly as before.
 */
const CockpitRow = ({
  href,
  onOpen,
  children,
}: {
  href?: string | null;
  onOpen?: () => void;
  children: React.ReactNode;
}) => {
  if (!href && !onOpen) {
    return <li className="dashboard-cockpit__item">{children}</li>;
  }
  const body = (
    <>
      <span className="dashboard-cockpit__item-body">{children}</span>
      <Icon
        path={href ? mdiOpenInNew : mdiChevronRight}
        size={href ? 0.6 : 0.75}
        className="dashboard-cockpit__item-go"
      />
    </>
  );
  return (
    <li className="dashboard-cockpit__item dashboard-cockpit__item--clickable">
      {href ? (
        <a
          className="dashboard-cockpit__item-hit"
          href={href}
          target="_blank"
          rel="noopener noreferrer"
        >
          {body}
        </a>
      ) : (
        <button type="button" className="dashboard-cockpit__item-hit" onClick={onOpen}>
          {body}
        </button>
      )}
    </li>
  );
};

const renderNewThisWeekItem = (item: NewThisWeekItem, openFile: (id: string) => void) => (
  <CockpitRow key={item.carriage_id} onOpen={() => openFile(item.carriage_id)}>
    <span className="dashboard-cockpit__item-title">{item.title}</span>
    <span className="dashboard-cockpit__item-meta">
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
    </span>
  </CockpitRow>
);

const renderTrackedFileMovingItem = (
  item: TrackedFileMovingItem,
  openFile: (id: string) => void,
) => (
  <CockpitRow
    key={`${item.carriage_id}-${item.changed_at ?? ''}`}
    onOpen={() => openFile(item.carriage_id)}
  >
    <span className="dashboard-cockpit__item-title">{item.title}</span>
    <span className="dashboard-cockpit__item-meta">
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
    </span>
  </CockpitRow>
);

const renderPositionStressItem = (
  item: PositionStressItem,
  openFile: (id: string) => void,
) => (
  <CockpitRow
    key={`${item.carriage_id}-${item.detected_at ?? ''}`}
    onOpen={() => openFile(item.carriage_id)}
  >
    <span className="dashboard-cockpit__item-title">{item.title}</span>
    <span className="dashboard-cockpit__item-meta">
      {item.procedure_ref && (
        <span className="dashboard-cockpit__item-pill">
          {item.procedure_ref}
        </span>
      )}
      <span className="dashboard-cockpit__item-detail">{item.detail}</span>
    </span>
  </CockpitRow>
);

const renderCalendarEventItem = (item: CalendarEventItem) => (
  <CockpitRow key={item.event_id} href={item.source_url}>
    <span className="dashboard-cockpit__item-title">{item.title}</span>
    <span className="dashboard-cockpit__item-meta">
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
    </span>
  </CockpitRow>
);

const renderComplianceItem = (item: ComplianceSignalItem) => (
  <CockpitRow key={item.eu_law_id} href={item.celex ? eurLexUrl(item.celex) : null}>
    <span className="dashboard-cockpit__item-title">{item.title}</span>
    <span className="dashboard-cockpit__item-meta">
      {/* No CELEX pill. It is a database identifier that means nothing to a
          reader, and the row itself already links to the act on EUR-Lex. */}
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
    </span>
  </CockpitRow>
);

const renderVoiceItem = (
  item: VoiceOpportunityItem,
  openConsultation: (id: string) => void,
) => (
  <CockpitRow
    key={item.consultation_id}
    onOpen={() => openConsultation(item.consultation_id)}
  >
    <span className="dashboard-cockpit__item-title">{item.title}</span>
    <span className="dashboard-cockpit__item-meta">
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
    </span>
  </CockpitRow>
);

export const DashboardCockpit = () => {
  const { t: i18nT } = useTranslation();
  const navigate = useNavigate();
  const { data, isLoading, error, fetchTiles } = useDashboard();
  const { isAuthenticated, user } = useAuth();
  const fetchFileDetail = useLegislativeTrains((s) => s.fetchFileDetail);

  // Opening a cockpit line is the same gesture as opening it from My Tracked
  // Files: the shared legislative-file modal, mounted once at the bottom of
  // this component. Consultations have their own modal, which lives in the
  // consultations tab, so we deep-link there and let it open on arrival.
  const openFile = (carriageId: string) => {
    void fetchFileDetail(carriageId);
  };
  const openConsultation = (consultationId: string) => {
    navigate(
      `/my-eu-bubble?tab=consultations&consultation=${encodeURIComponent(consultationId)}`,
    );
  };
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
        {/* The raw API detail is English-only; keep the visible message translated. */}
        <p>{i18nT('cockpit.error', 'We could not load the cockpit right now.')}</p>
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
        return t.new_this_week.items.map((i) => renderNewThisWeekItem(i, openFile));
      case 'tracked_files_moving':
        return t.tracked_files_moving.items.map((i) =>
          renderTrackedFileMovingItem(i, openFile),
        );
      case 'positions_under_stress':
        return t.positions_under_stress.items.map((i) =>
          renderPositionStressItem(i, openFile),
        );
      case 'next_seven_days':
        return t.next_seven_days.items.map(renderCalendarEventItem);
      case 'compliance_signals':
        return t.compliance_signals.items.map(renderComplianceItem);
      case 'voice_opportunities':
        return t.voice_opportunities.items.map((i) =>
          renderVoiceItem(i, openConsultation),
        );
      default:
        return null;
    }
  };

  return (
    <section className="dashboard-cockpit">
      {/* The briefing cards name specific files. This surface already mounts
          the file modal below, so they open in place rather than sending the
          user off to My Tracked Files. */}
      <ProactiveOpener surface="dashboard" onOpenFile={openFile} />

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

      {/* Shared legislative-file modal, opened by clicking any file line above.
          Reads `selectedFile` from the legislative-trains store and renders
          nothing when empty, so mounting it here is free. My Tracked Files and
          the Legislative Train mount their own; those tabs never render at the
          same time as Overview, so there is never a second copy on screen. */}
      <LegislativeFileDetail />
    </section>
  );
};
