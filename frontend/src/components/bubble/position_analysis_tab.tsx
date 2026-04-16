// frontend/src/components/bubble/position_analysis_tab.tsx
import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import Icon from '@mdi/react';
import {
  mdiScaleBalance,
  mdiRefresh,
  mdiTrendingUp,
  mdiAccountGroup,
  mdiBank,
  mdiFileDocumentOutline,
  mdiChevronRight,
  mdiContentSave,
  mdiCircleSmall,
} from '@mdi/js';
import { positionService } from '../../services/position_service';
import type {
  PositionResponse,
  TrackedPositionListItem,
  UserPosition,
  AmendmentDrilldown,
} from '../../services/position_service';
import './position_analysis_tab.css';

const STANCE_COLORS: Record<string, string> = {
  for: 'var(--pos-green)',
  against: 'var(--pos-red)',
  abstention: 'var(--pos-yellow)',
  split: 'var(--pos-gold)',
  unknown: 'var(--pos-neutral)',
  support: 'var(--pos-green)',
  oppose: 'var(--pos-red)',
  neutral: 'var(--pos-neutral)',
  undecided: 'var(--pos-neutral)',
};

const STANCE_LABEL: Record<string, string> = {
  for: 'FOR',
  against: 'AGAINST',
  abstention: 'ABSTENTION',
  split: 'SPLIT',
  unknown: 'UNKNOWN',
  support: 'SUPPORT',
  oppose: 'OPPOSE',
  neutral: 'NEUTRAL',
  undecided: 'UNDECIDED',
};

const USER_STANCE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'support', label: 'Support' },
  { value: 'support_with_amendments', label: 'Support with amendments' },
  { value: 'oppose', label: 'Oppose' },
  { value: 'neutral', label: 'Neutral' },
  { value: 'undecided', label: 'Undecided' },
];

function ConfidencePill({ level }: { level: string }) {
  const cls = level === 'high' ? 'pos-pill--high' : level === 'low' ? 'pos-pill--low' : 'pos-pill--medium';
  return <span className={`pos-pill ${cls}`}>{level} confidence</span>;
}

function StanceBadge({ stance }: { stance: string }) {
  const key = (stance || 'unknown').toLowerCase();
  const label = STANCE_LABEL[key] || key.toUpperCase();
  const color = STANCE_COLORS[key] || STANCE_COLORS.unknown;
  return (
    <span className="pos-stance-badge" style={{ background: color }}>
      {label}
    </span>
  );
}

function PositionFileListItem({
  item,
  active,
  onClick,
}: {
  item: TrackedPositionListItem;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`pos-file-item ${active ? 'pos-file-item--active' : ''}`} onClick={onClick}>
      <div className="pos-file-item__title">{item.title || item.procedure_ref}</div>
      <div className="pos-file-item__meta">
        <span>{item.procedure_ref}</span>
        <span> -- {item.parliament_summary.amendments} amendments</span>
        {item.user_stance && (
          <span className="pos-file-item__user-stance">
            <Icon path={mdiCircleSmall} size={0.6} />
            Your stance: {item.user_stance.replace(/_/g, ' ')}
          </span>
        )}
      </div>
    </button>
  );
}

function AmendmentDrilldownTable({ drilldown }: { drilldown: AmendmentDrilldown | null }) {
  if (!drilldown || drilldown.articles.length === 0) {
    return <div className="pos-empty">No article-level amendment data available.</div>;
  }
  const allGroups = useMemo(() => {
    const s = new Set<string>();
    drilldown.articles.forEach((a) => Object.keys(a.by_group).forEach((g) => s.add(g)));
    return Array.from(s).sort();
  }, [drilldown]);

  return (
    <div className="pos-article-table-wrapper">
      <table className="pos-article-table">
        <thead>
          <tr>
            <th>Article</th>
            {allGroups.map((g) => (
              <th key={g}>{g}</th>
            ))}
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {drilldown.articles.map((a) => (
            <tr key={a.article}>
              <td className="pos-article-cell">{a.article}</td>
              {allGroups.map((g) => (
                <td key={g} className="pos-article-count">
                  {a.by_group[g] || ''}
                </td>
              ))}
              <td className="pos-article-total">{a.total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GroupsCard({ parliament }: { parliament: PositionResponse['parliament_position'] }) {
  return (
    <div className="pos-card pos-card--parliament">
      <div className="pos-card__header">
        <Icon path={mdiAccountGroup} size={1} />
        <h3>Parliament</h3>
      </div>
      <div className="pos-card__meta">
        <div>Rapporteur: {parliament.rapporteur || '(not yet appointed)'}</div>
        {parliament.rapporteur_group && <div>Rapporteur's group: {parliament.rapporteur_group}</div>}
        {parliament.lead_committee && <div>Lead committee: {parliament.lead_committee}</div>}
        {parliament.plenary_adopted?.adopted && (
          <div className="pos-badge pos-badge--green">Plenary adopted {parliament.plenary_adopted.date}</div>
        )}
      </div>
      <div className="pos-group-table-wrapper">
        <table className="pos-group-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Stance</th>
              <th>Cohesion</th>
              <th>Amendments</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {parliament.groups.map((g) => (
              <tr key={g.group_code}>
                <td className="pos-group-table__group-name">{g.group_code}</td>
                <td><StanceBadge stance={g.stance} /></td>
                <td className="pos-group-table__cohesion">{(g.cohesion * 100).toFixed(0)}%</td>
                <td className="pos-group-table__count">{g.amendment_count}</td>
                <td className="pos-group-table__confidence">{g.confidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {parliament.amendment_activity?.total > 0 && (
        <div className="pos-card__footer">Total amendments tabled: {parliament.amendment_activity.total}</div>
      )}
    </div>
  );
}

function CouncilCard({ council }: { council: PositionResponse['council_position'] }) {
  const { summary, member_states } = council;
  const supporting = member_states.filter((m) => m.stance === 'support');
  const opposing = member_states.filter((m) => m.stance === 'oppose');
  const undecided = member_states.filter((m) => m.stance !== 'support' && m.stance !== 'oppose');
  return (
    <div className="pos-card pos-card--council">
      <div className="pos-card__header">
        <Icon path={mdiBank} size={1} />
        <h3>Council</h3>
      </div>
      <div className="pos-card__meta">
        <div>
          Supporting {summary.supporting_count ?? 0} | Opposing {summary.opposing_count ?? 0} | Undecided {summary.undecided_count ?? 0}
        </div>
        {council.general_approach_adopted && (
          <div className="pos-badge pos-badge--green">General approach adopted</div>
        )}
      </div>
      <div className="pos-ms-grid">
        {[{ title: 'Supporting', list: supporting, color: 'var(--pos-green)' },
          { title: 'Opposing', list: opposing, color: 'var(--pos-red)' },
          { title: 'Undecided', list: undecided, color: 'var(--pos-neutral)' }].map((bloc) => (
          <div key={bloc.title} className="pos-ms-bloc" style={{ borderTopColor: bloc.color }}>
            <div className="pos-ms-bloc__title">{bloc.title} ({bloc.list.length})</div>
            <div className="pos-ms-bloc__chips">
              {bloc.list.length === 0 && <span className="pos-ms-bloc__empty">—</span>}
              {bloc.list.map((m) => {
                const confCls = m.confidence === 'high' ? 'pos-ms-chip--high' : m.confidence === 'low' ? 'pos-ms-chip--low' : 'pos-ms-chip--medium';
                return (
                  <span key={m.country_code} className={`pos-ms-chip ${confCls}`} title={`${m.country_name} (${m.confidence} confidence)`}>
                    {m.country_code}
                  </span>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CommissionCard({ commission, procedureRef }: { commission: PositionResponse['commission_position']; procedureRef: string }) {
  return (
    <div className="pos-card pos-card--commission">
      <div className="pos-card__header">
        <Icon path={mdiFileDocumentOutline} size={1} />
        <h3>Commission proposal</h3>
      </div>
      <div className="pos-card__meta">
        <div><strong>{commission.title || '(untitled)'}</strong></div>
        <div>Procedure: {procedureRef}</div>
        {commission.com_references && commission.com_references.length > 0 && (
          <div>COM references: {commission.com_references.join(', ')}</div>
        )}
        {commission.proposal_date && <div>Proposal date: {commission.proposal_date.slice(0, 10)}</div>}
      </div>
      {commission.description && (
        <div className="pos-card__body">{commission.description}</div>
      )}
      {commission.documents && commission.documents.length > 0 && (
        <ul className="pos-doc-list">
          {commission.documents.slice(0, 6).map((d, i) => (
            <li key={i}>
              <a href={d.portal_url || '#'} target="_blank" rel="noopener">
                [{d.doc_type}] {d.reference} {d.title ? ` -- ${String(d.title).slice(0, 80)}` : ''}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function UserPositionCard({
  pos,
  onSave,
}: {
  pos: PositionResponse;
  onSave: (p: UserPosition) => Promise<void>;
}) {
  const [stance, setStance] = useState(pos.user_position?.stance || 'undecided');
  const [notes, setNotes] = useState(pos.user_position?.notes || '');
  const [priorityArticles, setPriorityArticles] = useState(
    (pos.user_position?.priority_articles || []).join(', '),
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await onSave({
        stance,
        notes,
        priority_articles: priorityArticles
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="pos-card pos-card--user">
      <div className="pos-card__header">
        <Icon path={mdiScaleBalance} size={1} />
        <h3>Your position</h3>
      </div>
      <div className="pos-user-form">
        <label>
          Stance
          <select value={stance} onChange={(e) => setStance(e.target.value)}>
            {USER_STANCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label>
          Notes
          <textarea
            value={notes}
            rows={3}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="What is your organisation's line on this file?"
          />
        </label>
        <label>
          Priority articles (comma-separated)
          <input
            value={priorityArticles}
            onChange={(e) => setPriorityArticles(e.target.value)}
            placeholder="Article 4, Article 27a, Recital 9"
          />
        </label>
        <button className="pos-btn" onClick={handleSave} disabled={saving}>
          <Icon path={mdiContentSave} size={0.9} />
          {saving ? 'Saving...' : saved ? 'Saved' : 'Save position'}
        </button>
        {pos.user_position?.last_updated && (
          <div className="pos-user-form__updated">
            Last updated {new Date(pos.user_position.last_updated).toLocaleString()}
          </div>
        )}
      </div>
    </div>
  );
}

export const PositionAnalysisTab: React.FC = () => {
  const [list, setList] = useState<TrackedPositionListItem[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PositionResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<AmendmentDrilldown | null>(null);
  const [view, setView] = useState<'summary' | 'amendments'>('summary');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    positionService
      .list(100)
      .then((rows) => {
        setList(rows);
        if (rows.length > 0 && !selectedId) setSelectedId(rows[0].carriage_id);
      })
      .catch((e: any) => setListError(e?.response?.data?.detail || e.message || 'Failed to load tracked files'));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setDetailLoading(true);
    setDetailError(null);
    positionService
      .get(selectedId)
      .then((d) => setDetail(d))
      .catch((e: any) => setDetailError(e?.response?.data?.detail || e.message || 'Failed to load position'))
      .finally(() => setDetailLoading(false));
    positionService
      .amendments(selectedId)
      .then((d) => setDrilldown(d))
      .catch(() => setDrilldown(null));
  }, [selectedId]);

  const handleRefresh = async () => {
    if (!selectedId) return;
    setRefreshing(true);
    try {
      const d = await positionService.get(selectedId, true);
      setDetail(d);
    } catch (e: any) {
      setDetailError(e?.response?.data?.detail || e.message || 'Refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  const handleSaveUserPosition = async (payload: UserPosition) => {
    if (!selectedId) return;
    const updated = await positionService.saveUserPosition(selectedId, payload);
    setDetail(updated);
    setList((prev) =>
      (prev || []).map((x) =>
        x.carriage_id === selectedId ? { ...x, user_stance: payload.stance } : x,
      ),
    );
  };

  return (
    <div className="pos-tab">
      <aside className="pos-tab__sidebar">
        <header className="pos-tab__sidebar-header">
          <Icon path={mdiScaleBalance} size={1} />
          <div>
            <h2>Position Analysis</h2>
            <p>Commission / Parliament / Council stances on your tracked files.</p>
          </div>
        </header>
        {listError && <div className="pos-error">{listError}</div>}
        {list === null && <div className="pos-loading">Loading tracked files...</div>}
        {list && list.length === 0 && (
          <div className="pos-empty">
            You aren't tracking any legislative files yet. Go to <strong>My Files</strong> to start.
          </div>
        )}
        {list && list.length > 0 && (
          <ul className="pos-file-list">
            {list.map((item) => (
              <li key={item.carriage_id}>
                <PositionFileListItem
                  item={item}
                  active={item.carriage_id === selectedId}
                  onClick={() => { setSelectedId(item.carriage_id); setView('summary'); }}
                />
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section className="pos-tab__main">
        {selectedId === null && (
          <div className="pos-placeholder">
            <Icon path={mdiScaleBalance} size={3} />
            <h3>Pick a file to see positions</h3>
            <p>Each file shows Commission proposal, Parliament stance by group, Council stance by Member State, and your own position.</p>
          </div>
        )}

        {selectedId && detailLoading && <div className="pos-loading">Loading position analysis...</div>}
        {selectedId && detailError && <div className="pos-error">{detailError}</div>}

        {detail && !detailLoading && (
          <>
            <header className="pos-detail-header">
              <div>
                <div className="pos-detail-header__title">{detail.title || detail.procedure_ref}</div>
                <div className="pos-detail-header__meta">
                  <span>{detail.procedure_ref}</span>
                  <ConfidencePill level={detail.confidence} />
                  <span className="pos-pill pos-pill--completeness">{detail.data_completeness} data</span>
                  {detail.generated_at && (
                    <span className="pos-detail-header__timestamp">
                      Snapshot: {new Date(detail.generated_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
              <div className="pos-detail-header__actions">
                <button className="pos-btn pos-btn--ghost" onClick={handleRefresh} disabled={refreshing}>
                  <Icon path={mdiRefresh} size={0.9} />
                  {refreshing ? 'Refreshing...' : 'Refresh'}
                </button>
              </div>
            </header>

            <nav className="pos-view-switch" role="tablist">
              <button
                className={`pos-view-switch__btn ${view === 'summary' ? 'pos-view-switch__btn--active' : ''}`}
                onClick={() => setView('summary')}
              >
                <Icon path={mdiTrendingUp} size={0.9} /> Summary
              </button>
              <button
                className={`pos-view-switch__btn ${view === 'amendments' ? 'pos-view-switch__btn--active' : ''}`}
                onClick={() => setView('amendments')}
              >
                <Icon path={mdiChevronRight} size={0.9} /> Article-by-article
              </button>
            </nav>

            {view === 'summary' && (
              <div className="pos-grid">
                <CommissionCard commission={detail.commission_position} procedureRef={detail.procedure_ref} />
                <GroupsCard parliament={detail.parliament_position} />
                <CouncilCard council={detail.council_position} />
                <UserPositionCard pos={detail} onSave={handleSaveUserPosition} />
              </div>
            )}
            {view === 'amendments' && <AmendmentDrilldownTable drilldown={drilldown} />}
          </>
        )}
      </section>
    </div>
  );
};
