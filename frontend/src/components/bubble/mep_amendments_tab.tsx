/**
 * MEP Amendments Sub-tab Component
 *
 * Displays EP committee amendments for a legislative procedure.
 * Part of My EU Bubble > Amendments > MEP Amendments.
 *
 * Sections: Procedure selector, overview bar, filter row with group pills,
 * group activity bars, hotspot table, amendment cards, pagination.
 *
 * Created: February 2026
 */

import { useEffect, useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import Icon from '@mdi/react';
import {
  mdiAccountGroupOutline,
  mdiFileDocumentOutline,
  mdiChevronDown,
  mdiChevronUp,
  mdiMagnify,
  mdiClose,
  mdiStarOutline,
} from '@mdi/js';
import { useAuth } from '../../hooks/use_auth';
import {
  useMEPAmendments,
  EP_GROUP_COLOURS,
  DARK_TEXT_GROUPS,
} from '../../hooks/use_mep_amendments';
import { useCommitteeWork } from '../../hooks/use_committee_work';
import type { MEPAmendment, RapporteurInfo } from '../../services/mep_amendment_service';
import './mep_amendments_tab.css';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

interface PickerProcedure {
  procedure_ref: string;
  committees: string[];
  count: number;
  title: string | null;
}

// ============================================================================
// Word-level diff (highlights bold-italic additions, strikethrough deletions)
// ============================================================================

type DiffSegment = { text: string; type: 'equal' | 'add' | 'del' };

/**
 * Simple word-level diff using longest-common-subsequence.
 * Returns segments tagged as equal / add / del.
 */
function wordDiff(oldText: string, newText: string): DiffSegment[] {
  const oldWords = oldText.split(/(\s+)/);
  const newWords = newText.split(/(\s+)/);

  // LCS table (optimised for typical amendment lengths)
  const m = oldWords.length;
  const n = newWords.length;

  // For very long texts, skip diffing to avoid perf issues
  if (m * n > 500_000) return [{ text: newText, type: 'equal' }];

  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldWords[i - 1] === newWords[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to build diff
  const segments: DiffSegment[] = [];
  let i = m, j = n;
  const stack: DiffSegment[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldWords[i - 1] === newWords[j - 1]) {
      stack.push({ text: oldWords[i - 1], type: 'equal' });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      stack.push({ text: newWords[j - 1], type: 'add' });
      j--;
    } else {
      stack.push({ text: oldWords[i - 1], type: 'del' });
      i--;
    }
  }

  // Reverse and merge consecutive same-type segments
  for (let k = stack.length - 1; k >= 0; k--) {
    const seg = stack[k];
    if (segments.length > 0 && segments[segments.length - 1].type === seg.type) {
      segments[segments.length - 1].text += seg.text;
    } else {
      segments.push({ ...seg });
    }
  }

  return segments;
}

/** Render diff segments as React elements with EP-style formatting */
function DiffText({ original, proposed }: { original: string; proposed: string }) {
  if (!original || !proposed) return <>{proposed || original}</>;

  const segments = wordDiff(original, proposed);

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.type === 'add') {
          return <span key={i} className="mep-card__diff-added">{seg.text}</span>;
        }
        if (seg.type === 'del') {
          return <span key={i} className="mep-card__diff-deleted">{seg.text}</span>;
        }
        return <span key={i}>{seg.text}</span>;
      })}
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

/** Overview metric card */
const OverviewCard = ({ value, label }: { value: number; label: string }) => (
  <div className="mep-overview__card">
    <div className="mep-overview__value">{value}</div>
    <div className="mep-overview__label">{label}</div>
  </div>
);

/** EP group colour pill (toggleable) */
const GroupPill = ({
  group,
  active,
  onClick,
}: {
  group: string;
  active: boolean;
  onClick: () => void;
}) => {
  const isAll = group === 'All';
  const colour = isAll ? '#6b7280' : (EP_GROUP_COLOURS[group] || EP_GROUP_COLOURS.Unknown);
  const isDark = DARK_TEXT_GROUPS.has(group);

  return (
    <button
      className={`mep-filter__pill ${active ? 'mep-filter__pill--active' : ''}`}
      style={
        active
          ? { background: colour, color: isDark ? '#333' : '#fff', borderColor: colour }
          : undefined
      }
      onClick={onClick}
      aria-pressed={active}
    >
      {!isAll && <span className="mep-filter__pill-dot" style={{ background: colour }} />}
      {group}
    </button>
  );
};

/** Group activity horizontal bar */
const GroupBar = ({
  group,
  count,
  maxCount,
  rapporteur,
}: {
  group: string;
  count: number;
  maxCount: number;
  rapporteur?: RapporteurInfo | null;
}) => {
  // Use rapporteur's actual group colour if this is the "Rapporteur" row
  const isRapporteur = group === 'Rapporteur';
  const effectiveGroup = isRapporteur && rapporteur?.political_group
    ? rapporteur.political_group : group;
  const colour = EP_GROUP_COLOURS[effectiveGroup] || EP_GROUP_COLOURS.Unknown;
  const width = maxCount > 0 ? Math.max(5, (count / maxCount) * 100) : 0;
  const isDark = DARK_TEXT_GROUPS.has(effectiveGroup);
  const showInside = width > 15;

  // Show rapporteur name + group in bar label
  const label = isRapporteur && rapporteur?.name
    ? `Rapporteur: ${rapporteur.name}${rapporteur.political_group ? ` (${rapporteur.political_group})` : ''}`
    : group;

  return (
    <div className="mep-bars__row">
      <div className="mep-bars__label" title={label}>{label}</div>
      <div className="mep-bars__track">
        <div
          className="mep-bars__fill"
          style={{ width: `${width}%`, background: colour }}
        >
          {showInside && (
            <span
              className="mep-bars__count"
              style={isDark ? { color: '#333', textShadow: 'none' } : undefined}
            >
              {count}
            </span>
          )}
        </div>
      </div>
      {!showInside && <span className="mep-bars__count-outside">{count}</span>}
    </div>
  );
};

/** Hotspot row (most amended element) */
const HotspotRow = ({
  element,
  count,
  maxCount,
  onClick,
}: {
  element: string;
  count: number;
  maxCount: number;
  onClick: () => void;
}) => (
  <button className="mep-hotspots__row" onClick={onClick}>
    <div className="mep-hotspots__element">{element}</div>
    <div className="mep-hotspots__bar">
      <div
        className="mep-hotspots__bar-fill"
        style={{ width: `${(count / maxCount) * 100}%` }}
      />
    </div>
    <div className="mep-hotspots__count">{count}</div>
  </button>
);

/** Single amendment card */
const AmendmentCard = ({
  amendment,
  rapporteur,
}: {
  amendment: MEPAmendment;
  rapporteur?: RapporteurInfo | null;
}) => {
  const { t } = useTranslation();
  const [showJustification, setShowJustification] = useState(false);
  const isRapporteur = amendment.political_group === 'Rapporteur';

  // For rapporteur amendments, use the rapporteur's group colour if available
  const displayGroup = isRapporteur && rapporteur?.political_group
    ? rapporteur.political_group
    : amendment.political_group;
  const colour = EP_GROUP_COLOURS[displayGroup || 'Unknown'] || EP_GROUP_COLOURS.Unknown;
  const isDark = DARK_TEXT_GROUPS.has(displayGroup || '');

  const typeBadgeClass = `mep-card__type-badge mep-card__type-badge--${amendment.amendment_type}`;

  // Rapporteur label: "Rapporteur -- Name (Group)" or fallback
  const rapporteurLabel = isRapporteur
    ? rapporteur?.name
      ? `Rapporteur: ${rapporteur.name}${rapporteur.political_group ? ` (${rapporteur.political_group})` : ''}`
      : 'Rapporteur (Draft Report)'
    : null;

  return (
    <div className="mep-card" style={{ borderLeftColor: colour }}>
      {/* Header */}
      <div className="mep-card__header">
        <div className="mep-card__header-left">
          <span className="mep-card__number">AM {amendment.amendment_number}</span>
          {amendment.political_group && (
            <span
              className={`mep-card__group-badge${isRapporteur ? ' mep-card__group-badge--rapporteur' : ''}`}
              style={{ background: colour, color: isDark ? '#333' : '#fff' }}
            >
              {rapporteurLabel || amendment.political_group}
            </span>
          )}
          <span className={typeBadgeClass}>{amendment.amendment_type}</span>
        </div>
      </div>

      {/* Meta */}
      <div className="mep-card__meta">
        {amendment.author_names.length > 0 ? (
          <div className="mep-card__authors">{amendment.author_names.join(', ')}</div>
        ) : isRapporteur && rapporteur?.name ? (
          <div className="mep-card__authors mep-card__authors--rapporteur">
            Draft report by {rapporteur.name}{rapporteur.political_group ? ` (${rapporteur.political_group})` : ''}
          </div>
        ) : isRapporteur ? (
          <div className="mep-card__authors mep-card__authors--rapporteur">
            {t('mepAmendmentsTab.committeeRapporteurProposal', 'Committee rapporteur proposal')}
          </div>
        ) : null}
        {amendment.on_behalf_of_group && amendment.political_group && !isRapporteur && (
          <div className="mep-card__on-behalf">
            on behalf of the {amendment.political_group} Group
          </div>
        )}
        <div className="mep-card__element">{amendment.element_reference}</div>
      </div>

      {/* Diff table */}
      <div className="mep-card__diff">
        <div className="mep-card__diff-col">
          <div className="mep-card__diff-header">{t('mepAmendmentsTab.textProposedByCommission')}</div>
          <div className="mep-card__diff-text">
            {amendment.amendment_type === 'addition' ? (
              <span className="mep-card__diff-new">(new)</span>
            ) : amendment.amendment_type === 'modification' ? (
              <DiffText original={amendment.proposed_text} proposed={amendment.original_text} />
            ) : (
              amendment.original_text
            )}
          </div>
        </div>
        <div className="mep-card__diff-col mep-card__diff-col--proposed">
          <div className="mep-card__diff-header">{t('mepAmendmentsTab.amendment')}</div>
          <div className="mep-card__diff-text">
            {amendment.amendment_type === 'suppression' ? (
              <span className="mep-card__diff-del">{amendment.original_text}</span>
            ) : amendment.amendment_type === 'modification' ? (
              <DiffText original={amendment.original_text} proposed={amendment.proposed_text} />
            ) : (
              amendment.proposed_text
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mep-card__footer">
        <span className="mep-card__lang">Or. {amendment.original_language}</span>
        {amendment.justification && (
          <button
            className="mep-card__expand"
            onClick={() => setShowJustification(!showJustification)}
          >
            <Icon
              path={showJustification ? mdiChevronUp : mdiChevronDown}
              size={0.65}
            />
            {t('mepAmendmentsTab.justification')}
          </button>
        )}
      </div>

      {/* Justification */}
      {amendment.justification && showJustification && (
        <div className="mep-card__justification">
          <div className="mep-card__justification-title">{t('mepAmendmentsTab.justification')}</div>
          <div className="mep-card__justification-text">
            {amendment.justification}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export const MEPAmendmentsTab = ({ initialProcedure }: { initialProcedure?: string } = {}) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const { committees, fetchCommittees } = useCommitteeWork();
  const {
    selectedProcedure,
    amendments,
    stats,
    total,
    filters,
    page,
    pageSize,
    loadingStatus,
    statsLoadingStatus,
    selectProcedure,
    setFilter,
    setPage,
    loadAmendments,
  } = useMEPAmendments();

  const [authorSearch, setAuthorSearch] = useState('');

  // PI-aligned picker state (mirrors the My Tracked Files cockpit pattern).
  const [pickerProcedures, setPickerProcedures] = useState<PickerProcedure[]>([]);
  const [myAmCommittees, setMyAmCommittees] = useState<string[]>([]);
  const [amMode, setAmMode] = useState<'mine' | 'all'>('all');
  const [amChips, setAmChips] = useState<string[]>([]);
  const [amSearch, setAmSearch] = useState('');
  const [addAmCommittee, setAddAmCommittee] = useState('');
  const [pickerLoaded, setPickerLoaded] = useState(false);
  const [showPicker, setShowPicker] = useState(true);

  // Load committee names + the PI-annotated procedure list on mount.
  useEffect(() => {
    fetchCommittees();
    (async () => {
      try {
        const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
        const res = await axios.get<{ procedures: PickerProcedure[]; my_committees: string[] }>(
          `${API_BASE}/mep-amendments/procedures-by-committee`,
          headers ? { headers } : undefined,
        );
        setPickerProcedures(res.data?.procedures || []);
        const mine = res.data?.my_committees || [];
        setMyAmCommittees(mine);
        if (mine.length > 0) { setAmChips(mine); setAmMode('mine'); }
      } catch {
        /* leave empty -> "all" mode */
      } finally {
        setPickerLoaded(true);
      }
    })();
  }, []);

  // Reload amendments when filters or page change
  useEffect(() => {
    if (selectedProcedure && token) {
      loadAmendments(token);
    }
  }, [filters, page]);

  // Debounced author search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (authorSearch.length >= 2) {
        setFilter('author', authorSearch);
      } else if (authorSearch.length === 0) {
        setFilter('author', undefined);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [authorSearch]);

  const handleSelectProcedure = useCallback(
    (ref: string) => { if (ref && token) { selectProcedure(ref, token); setShowPicker(false); } },
    [token, selectProcedure],
  );

  // Deep-link from My Tracked Files: preselect a procedure and collapse the picker.
  useEffect(() => {
    if (initialProcedure && token) {
      selectProcedure(initialProcedure, token);
      setShowPicker(false);
    }
  }, [initialProcedure, token]);

  const totalPages = Math.ceil(total / pageSize);

  const committeeNameOf = useCallback(
    (code: string) => committees.find((c) => c.code === code)?.name || code,
    [committees],
  );

  // Committees that actually have procedures-with-amendments (for the add dropdown).
  const availableAmCommittees = useMemo(() => {
    const set = new Set<string>();
    for (const p of pickerProcedures) for (const c of p.committees) if (c) set.add(c);
    return Array.from(set).sort();
  }, [pickerProcedures]);

  const toggleAmChip = (code: string) =>
    setAmChips((prev) => prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]);

  // Group procedures by primary committee, my-interest committees first.
  const amGroups = useMemo(() => {
    const q = amSearch.trim().toLowerCase();
    const active = new Set(amChips);
    const filtered = pickerProcedures.filter((p) => {
      const codes = p.committees.length ? p.committees : [''];
      if (amMode === 'mine' && myAmCommittees.length > 0
        && !codes.some((c) => myAmCommittees.includes(c))) return false;
      if (active.size > 0 && !codes.some((c) => active.has(c))) return false;
      if (q && !((p.title || '').toLowerCase().includes(q) || p.procedure_ref.toLowerCase().includes(q))) return false;
      return true;
    });
    const byCode = new Map<string, PickerProcedure[]>();
    for (const p of filtered) {
      const code = p.committees[0] || 'OTHER';
      const list = byCode.get(code) || [];
      list.push(p);
      byCode.set(code, list);
    }
    return Array.from(byCode.entries())
      .map(([code, items]) => ({
        code,
        name: code === 'OTHER' ? t('myFilesTab.committeeOther') : committeeNameOf(code),
        isMine: myAmCommittees.includes(code),
        items: items.sort((a, b) => b.count - a.count),
      }))
      .sort((a, b) => (Number(b.isMine) - Number(a.isMine))
        || (a.code === 'OTHER' ? 1 : b.code === 'OTHER' ? -1 : a.code.localeCompare(b.code)));
  }, [pickerProcedures, amMode, amChips, amSearch, myAmCommittees, committeeNameOf, t]);

  const amVisibleCount = amGroups.reduce((n, g) => n + g.items.length, 0);

  // Stats-derived data
  const maxGroupCount = stats?.by_group?.length
    ? Math.max(...stats.by_group.map((g) => g.count))
    : 1;
  const hotspots = stats?.by_element?.slice(0, 5) || [];
  const maxHotspotCount = hotspots.length ? hotspots[0].count : 1;
  const uniqueGroups = stats?.by_group?.length || 0;
  const uniqueAuthors = stats?.top_authors?.length || 0;
  const uniqueElements = stats?.by_element?.length || 0;

  return (
    <div className="mep-amendments-tab">
      {/* Selected-procedure bar (shown when a procedure is chosen and picker collapsed) */}
      {selectedProcedure && !showPicker && (
        <div className="mep-procedure__selected">
          <div className="mep-procedure__selected-main">
            <span className="mep-procedure__selected-label">{t('mepAmendmentsTab.legislativeFile')}</span>
            <strong>{pickerProcedures.find((p) => p.procedure_ref === selectedProcedure)?.title || selectedProcedure}</strong>
            <span className="mep-procedure__selected-ref">{selectedProcedure}</span>
          </div>
          <button type="button" className="mep-procedure__change" onClick={() => setShowPicker(true)}>
            {t('mepAmendmentsTab.changeFile')}
          </button>
          {stats && (
            <div className="mep-procedure__meta">
              <span>
                <Icon path={mdiAccountGroupOutline} size={0.65} />
                {stats.committees.length > 0 ? `Committee: ${stats.committees.join(', ')}` : 'Committee: --'}
              </span>
              {stats.rapporteur && (
                <span>
                  Rapporteur: {stats.rapporteur.name}
                  {stats.rapporteur.political_group ? ` (${stats.rapporteur.political_group})` : ''}
                </span>
              )}
              <span>
                <Icon path={mdiFileDocumentOutline} size={0.65} />
                {stats.total_documents} document{stats.total_documents !== 1 ? 's' : ''} parsed
              </span>
            </div>
          )}
        </div>
      )}

      {/* PI-aligned procedure picker (committee-grouped, mirrors My Tracked Files) */}
      {showPicker && (
        <div className="my-tracked-files-tab__committee-work">
          <div className="my-tracked-files-tab__committee-controls">
            {myAmCommittees.length > 0 && (
              <div className="my-tracked-files-tab__segmented" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={amMode === 'mine'}
                  className={`my-tracked-files-tab__segment ${amMode === 'mine' ? 'my-tracked-files-tab__segment--active' : ''}`}
                  onClick={() => { setAmMode('mine'); setAmChips(myAmCommittees); }}
                >
                  {t('myFilesTab.myInterests')} ({myAmCommittees.length})
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={amMode === 'all'}
                  className={`my-tracked-files-tab__segment ${amMode === 'all' ? 'my-tracked-files-tab__segment--active' : ''}`}
                  onClick={() => { setAmMode('all'); setAmChips([]); }}
                >
                  {t('myFilesTab.allCommitteesLabel')}
                </button>
              </div>
            )}
            <div className="my-tracked-files-tab__committee-chips">
              {amChips.map((code) => (
                <button
                  key={code}
                  type="button"
                  className="my-tracked-files-tab__chip my-tracked-files-tab__chip--active"
                  title={committeeNameOf(code)}
                  onClick={() => toggleAmChip(code)}
                >
                  {code}
                  <Icon path={mdiClose} size={0.55} />
                </button>
              ))}
              <select
                className="my-tracked-files-tab__chip-add"
                value={addAmCommittee}
                onChange={(e) => { if (e.target.value) { toggleAmChip(e.target.value); setAddAmCommittee(''); } }}
              >
                <option value="">{t('myFilesTab.addCommittee')}</option>
                {availableAmCommittees.filter((c) => !amChips.includes(c)).map((c) => (
                  <option key={c} value={c}>{c} - {committeeNameOf(c)}</option>
                ))}
              </select>
            </div>
            <div className="my-tracked-files-tab__committee-filters">
              <div className="my-tracked-files-tab__committee-search">
                <Icon path={mdiMagnify} size={0.8} />
                <input
                  type="text"
                  placeholder={t('mepAmendmentsTab.searchProcedures')}
                  value={amSearch}
                  onChange={(e) => setAmSearch(e.target.value)}
                />
              </div>
            </div>
          </div>

          {!pickerLoaded ? (
            <div className="mep-amendments-tab__loading">{t('mepAmendmentsTab.loadingAmendmentData')}</div>
          ) : amVisibleCount === 0 ? (
            <div className="mep-amendments-tab__empty">
              <Icon path={mdiAccountGroupOutline} size={2} />
              <h3>{t('mepAmendmentsTab.selectFileTitle')}</h3>
              <p>{amMode === 'mine' ? t('mepAmendmentsTab.noProceduresMine') : t('mepAmendmentsTab.selectFileBody')}</p>
            </div>
          ) : (
            <div className="my-tracked-files-tab__committee-groups">
              {amGroups.map((group) => (
                <div key={group.code} className="my-tracked-files-tab__committee-group">
                  <div className="my-tracked-files-tab__committee-group-title">
                    <span className="my-tracked-files-tab__committee-group-code">{group.code}</span>
                    <span className="my-tracked-files-tab__committee-group-name">{group.name}</span>
                    {group.isMine && (
                      <span className="my-tracked-files-tab__committee-group-mine" title={t('myFilesTab.matchesInterests')}>
                        <Icon path={mdiStarOutline} size={0.6} />
                        {t('myFilesTab.matchesInterests')}
                      </span>
                    )}
                    <span className="my-tracked-files-tab__committee-group-count">{group.items.length}</span>
                  </div>
                  <div className="mep-procedure__rows">
                    {group.items.map((p) => (
                      <button
                        key={p.procedure_ref}
                        type="button"
                        className={`mep-procedure__row ${selectedProcedure === p.procedure_ref ? 'mep-procedure__row--active' : ''}`}
                        onClick={() => handleSelectProcedure(p.procedure_ref)}
                      >
                        <span className="mep-procedure__row-title">{p.title || p.procedure_ref}</span>
                        <span className="mep-procedure__row-meta">
                          <span className="mep-procedure__row-ref">{p.procedure_ref}</span>
                          <span className="mep-procedure__row-count">{t('mepAmendmentsTab.amendmentsCount', { n: p.count })}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Loading state */}
      {loadingStatus === 'loading' && statsLoadingStatus === 'loading' && (
        <div className="mep-amendments-tab__loading">{t('mepAmendmentsTab.loadingAmendmentData')}</div>
      )}

      {/* Content (only shown when a procedure is selected and stats loaded) */}
      {stats && selectedProcedure && (
        <>
          {/* Overview Bar */}
          <div className="mep-overview">
            <OverviewCard value={stats.total_amendments} label={t('mepAmendmentsTab.ariaAmendments')} />
            <OverviewCard value={uniqueGroups} label={t('mepAmendmentsTab.ariaPoliticalGroups')} />
            <OverviewCard value={uniqueAuthors} label="MEPs" />
            <OverviewCard value={uniqueElements} label={t('mepAmendmentsTab.ariaElementsAmended')} />
          </div>

          {/* Filter Row */}
          <div className="mep-filter">
            <div className="mep-filter__group">
              <label className="mep-filter__label">{t('mepAmendmentsTab.politicalGroup')}</label>
              <div className="mep-filter__pills">
                <GroupPill
                  group="All"
                  active={!filters.group}
                  onClick={() => setFilter('group', undefined)}
                />
                {stats.by_group.map((g) => (
                  <GroupPill
                    key={g.political_group}
                    group={g.political_group}
                    active={filters.group === g.political_group}
                    onClick={() =>
                      setFilter('group', filters.group === g.political_group ? undefined : g.political_group)
                    }
                  />
                ))}
              </div>
            </div>
            <div className="mep-filter__group">
              <label className="mep-filter__label">{t('mepAmendmentsTab.element')}</label>
              <select
                className="mep-filter__select"
                value={filters.element_type || ''}
                onChange={(e) => setFilter('element_type', e.target.value || undefined)}
              >
                <option value="">{t('amendmentsTab.statusAll')}</option>
                <option value="article">{t('mepAmendmentsTab.article')}</option>
                <option value="recital">{t('mepAmendmentsTab.recital')}</option>
                <option value="annex">{t('mepAmendmentsTab.annexOption')}</option>
              </select>
            </div>
            <div className="mep-filter__group">
              <label className="mep-filter__label">{t('mepAmendmentsTab.type')}</label>
              <select
                className="mep-filter__select"
                value={filters.amendment_type || ''}
                onChange={(e) => setFilter('amendment_type', e.target.value || undefined)}
              >
                <option value="">{t('amendmentsTab.statusAll')}</option>
                <option value="modification">{t('amendator.modification')}</option>
                <option value="suppression">{t('amendator.suppression')}</option>
                <option value="addition">{t('amendator.addition')}</option>
              </select>
            </div>
            <div className="mep-filter__group">
              <label className="mep-filter__label">{t('mepAmendmentsTab.searchMep')}</label>
              <div className="mep-filter__search">
                <Icon path={mdiMagnify} size={0.65} />
                <input
                  type="text"
                  placeholder={t('mepAmendmentsTab.examplePlaceholder')}
                  value={authorSearch}
                  onChange={(e) => setAuthorSearch(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Analysis Grid: Group Bars + Hotspots */}
          <div className="mep-analysis">
            <div className="mep-bars">
              <div className="mep-bars__title">{t('mepAmendmentsTab.groupActivity')}</div>
              {stats.by_group.map((g) => (
                <GroupBar
                  key={g.political_group}
                  group={g.political_group}
                  count={g.count}
                  maxCount={maxGroupCount}
                  rapporteur={stats.rapporteur}
                />
              ))}
            </div>

            <div className="mep-hotspots">
              <div className="mep-hotspots__title">{t('mepAmendmentsTab.mostAmendedElements')}</div>
              {hotspots.map((h) => (
                <HotspotRow
                  key={h.element_reference}
                  element={h.element_reference}
                  count={h.count}
                  maxCount={maxHotspotCount}
                  onClick={() => {
                    setFilter('element_type', h.element_type);
                  }}
                />
              ))}
              {hotspots.length === 0 && (
                <div className="mep-hotspots__empty">{t('mepAmendmentsTab.noElementData')}</div>
              )}
            </div>
          </div>

          {/* Amendment Cards */}
          <div className="mep-cards__title">
            {t('mepAmendmentsTab.amendmentsShowing', { total, from: (page - 1) * pageSize + 1, to: Math.min(page * pageSize, total) })}
          </div>

          {loadingStatus === 'loading' ? (
            <div className="mep-amendments-tab__loading">{t('mepAmendmentsTab.loadingShort')}</div>
          ) : amendments.length === 0 ? (
            <div className="mep-amendments-tab__empty-list">
              {t('mepAmendmentsTab.noAmendmentsMatchFilters')}
            </div>
          ) : (
            amendments.map((a) => (
              <AmendmentCard key={a.id} amendment={a} rapporteur={stats?.rapporteur} />
            ))
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mep-pagination">
              {Array.from({ length: Math.min(totalPages, 9) }, (_, i) => i + 1).map(
                (p) => (
                  <button
                    key={p}
                    className={`mep-pagination__btn ${p === page ? 'mep-pagination__btn--active' : ''}`}
                    aria-current={p === page ? 'page' : undefined}
                    onClick={() => {
                      setPage(p);
                      if (token) loadAmendments(token);
                    }}
                  >
                    {p}
                  </button>
                )
              )}
              {totalPages > 9 && (
                <>
                  <span className="mep-pagination__info">...</span>
                  <button
                    className="mep-pagination__btn"
                    onClick={() => {
                      setPage(totalPages);
                      if (token) loadAmendments(token);
                    }}
                  >
                    {totalPages}
                  </button>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};
