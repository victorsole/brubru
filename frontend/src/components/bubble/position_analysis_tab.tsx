// frontend/src/components/bubble/position_analysis_tab.tsx
//
// Position Analysis (MEUB Section 4 - Cross-analysis). For a legislative file, the
// state of play across the three institutions, who is moving it, who is lobbying it,
// and what to do about it. PI-aware (tracked + suggested-by-interests), with a
// lobbying overlay, predicted-vs-actual votes, an action bridge, and a clear
// separation of EVIDENCED facts from INFERRED predictions.
import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams, useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import {
  mdiScaleBalance, mdiRefresh, mdiTrendingUp, mdiAccountGroup, mdiBank,
  mdiFileDocumentOutline, mdiChevronRight, mdiContentSave, mdiCircleSmall,
  mdiHandshakeOutline, mdiOpenInNew, mdiCheckDecagram, mdiCrystalBall,
  mdiClipboardTextOutline, mdiPencilOutline, mdiCompareHorizontal, mdiStarOutline, mdiUpdate,
  mdiInformationOutline, mdiTargetAccount, mdiMessageTextOutline,
} from '@mdi/js';
import { positionService } from '../../services/position_service';
import type {
  PositionResponse, PositionListItem, PositionListResponse, UserPosition,
  AmendmentDrilldown, LobbyingResult, ActualVote, AlignmentResult, AlignmentOrg,
} from '../../services/position_service';
import './position_analysis_tab.css';

// EP political-group colours (canonical display names from the aggregator).
const GROUP_COLORS: Record<string, string> = {
  EPP: '#3399FF', 'S&D': '#E2001A', Renew: '#FFD43B', 'Greens/EFA': '#57B45F',
  ECR: '#2B5797', PfE: '#1F4E79', ESN: '#36454F', 'The Left': '#990000',
  NI: '#9aa0a6', Unattributed: '#cbd5e1',
};
const groupColor = (g: string) => GROUP_COLORS[g] || '#a78bfa';

const fmtDate = (iso: string | null | undefined): string => {
  if (!iso) return '';
  try { return new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return iso; }
};

const STANCE_COLORS: Record<string, string> = {
  for: 'var(--pos-green)', against: 'var(--pos-red)', abstention: 'var(--pos-yellow)',
  split: 'var(--pos-gold)', unknown: 'var(--pos-neutral)', support: 'var(--pos-green)',
  oppose: 'var(--pos-red)', neutral: 'var(--pos-neutral)', undecided: 'var(--pos-neutral)',
};
const STANCE_LABEL: Record<string, string> = {
  for: 'FOR', against: 'AGAINST', abstention: 'ABSTENTION', split: 'SPLIT', unknown: 'UNKNOWN',
  support: 'SUPPORT', oppose: 'OPPOSE', neutral: 'NEUTRAL', undecided: 'UNDECIDED',
};
const USER_STANCE_OPTIONS = [
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

// A small tag marking whether a card is grounded in records or model inference.
function SourceTag({ kind }: { kind: 'evidenced' | 'predicted' }) {
  const { t } = useTranslation();
  return kind === 'evidenced'
    ? <span className="pos-srctag pos-srctag--ev"><Icon path={mdiCheckDecagram} size={0.55} /> {t('positionTab.evidenced', 'Evidenced')}</span>
    : <span className="pos-srctag pos-srctag--pr"><Icon path={mdiCrystalBall} size={0.55} /> {t('positionTab.predicted', 'Predicted')}</span>;
}

function StanceBadge({ stance }: { stance: string }) {
  const key = (stance || 'unknown').toLowerCase();
  const label = STANCE_LABEL[key] || key.toUpperCase();
  return <span className="pos-stance-badge" style={{ background: STANCE_COLORS[key] || STANCE_COLORS.unknown }}>{label}</span>;
}

function FileItem({ item, active, onClick }: { item: PositionListItem; active: boolean; onClick: () => void }) {
  const { t } = useTranslation();
  return (
    <button className={`pos-file-item ${active ? 'pos-file-item--active' : ''}`} onClick={onClick}>
      <div className="pos-file-item__title">{item.title || item.procedure_ref}</div>
      <div className="pos-file-item__meta">
        <span>{item.procedure_ref}</span>
        {item.lead_committee && <span className="pos-file-chip">{item.lead_committee}</span>}
        {item.is_recently_updated && <span className="pos-file-chip pos-file-chip--upd"><Icon path={mdiUpdate} size={0.5} /> {t('positionTab.updated', 'updated')}</span>}
        {item.user_stance && (
          <span className="pos-file-item__user-stance">
            <Icon path={mdiCircleSmall} size={0.6} />{t('positionTab.yourStance', { stance: item.user_stance.replace(/_/g, ' ') })}
          </span>
        )}
      </div>
    </button>
  );
}

// Article-by-article: most-contested articles as a list of stacked group bars.
// The bar shows the mix among ATTRIBUTED amendments; unattributed shown muted.
function AmendmentDrilldownTable({ drilldown }: { drilldown: AmendmentDrilldown | null }) {
  const { t } = useTranslation();
  if (!drilldown || drilldown.articles.length === 0) return <div className="pos-empty">{t('positionTab.noArticleData')}</div>;

  // Legend: groups that actually appear (attributed), ordered by total volume.
  const legend = useMemo(() => {
    const totals: Record<string, number> = {};
    drilldown.articles.forEach((a) => Object.entries(a.by_group).forEach(([g, n]) => {
      if (g !== 'Unattributed') totals[g] = (totals[g] || 0) + n;
    }));
    return Object.keys(totals).sort((a, b) => totals[b] - totals[a]);
  }, [drilldown]);
  const maxTotal = Math.max(1, ...drilldown.articles.map((a) => a.total));

  return (
    <div className="pos-card pos-card--amend">
      <div className="pos-card__header">
        <Icon path={mdiChevronRight} size={1} /><h3>{t('positionTab.mostContested', 'Most contested articles')}</h3>
        <SourceTag kind="evidenced" />
      </div>
      <p className="pos-amend-intro">{t('positionTab.amendIntro', 'Tabled amendments rolled up to the article they target. Bar shows the group mix among attributed amendments.')}</p>

      <ul className="pos-amend-list">
        {drilldown.articles.map((a) => {
          const groups = Object.entries(a.by_group)
            .filter(([g]) => g !== 'Unattributed')
            .sort((x, y) => y[1] - x[1]);
          const attr = a.attributed_total || 0;
          return (
            <li key={a.article} className="pos-amend-row">
              <div className="pos-amend-row__head">
                <span className="pos-amend-row__art">{a.article}</span>
                <span className="pos-amend-row__count">
                  <span className="pos-amend-row__total" style={{ /* width by contention */ }}>{a.total}</span>
                  {a.unattributed > 0 && <span className="pos-amend-row__unattr">({a.unattributed} {t('positionTab.unattributedShort', 'unattributed')})</span>}
                </span>
              </div>
              <div className="pos-amend-bar" style={{ width: `${Math.max(8, (a.total / maxTotal) * 100)}%` }} title={`${a.total} ${t('positionTab.amendments').toLowerCase()}`}>
                {attr > 0 ? groups.map(([g, n]) => (
                  <span key={g} className="pos-amend-seg" style={{ width: `${(n / attr) * 100}%`, background: groupColor(g) }} title={`${g}: ${n}`} />
                )) : <span className="pos-amend-seg pos-amend-seg--none" style={{ width: '100%' }} title={t('positionTab.noGroupAttribution', 'No group attribution') as string} />}
              </div>
            </li>
          );
        })}
      </ul>

      {legend.length > 0 && (
        <div className="pos-amend-legend">
          {legend.map((g) => <span key={g} className="pos-amend-legend__item"><span className="pos-dot" style={{ background: groupColor(g) }} />{g}</span>)}
        </div>
      )}
    </div>
  );
}

// Normalise actual group votes into a readable cell (handles {for,against,..} or a string).
function actualForGroup(gb: Record<string, any> | undefined, group: string): string | null {
  if (!gb) return null;
  const v = gb[group] ?? gb[group.toUpperCase()] ?? gb[group.replace('/', '')];
  if (v == null) return null;
  if (typeof v === 'string') return v.toUpperCase();
  if (typeof v === 'object') {
    const f = v.for ?? v.For ?? v.yes; const a = v.against ?? v.Against ?? v.no; const ab = v.abstention ?? v.abstentions;
    if (f != null || a != null) return `${f ?? 0}/${a ?? 0}/${ab ?? 0}`;
  }
  return String(v);
}

function GroupsCard({ parliament, actual }: { parliament: PositionResponse['parliament_position']; actual: ActualVote | null }) {
  const { t } = useTranslation();
  const hasActual = !!actual?.has_vote && actual.group_breakdown && Object.keys(actual.group_breakdown).length > 0;
  return (
    <div className="pos-card pos-card--parliament">
      <div className="pos-card__header">
        <Icon path={mdiAccountGroup} size={1} /><h3>{t('positionTab.parliament')}</h3><SourceTag kind="predicted" />
      </div>
      <div className="pos-card__meta">
        <div>{t('positionTab.rapporteur')} {parliament.rapporteur || t('positionTab.notYetAppointed')}</div>
        {parliament.rapporteur_group && <div>{t('positionTab.rapporteurGroup')} {parliament.rapporteur_group}</div>}
        {parliament.lead_committee && <div>{t('positionTab.leadCommittee')} {parliament.lead_committee}</div>}
        {parliament.plenary_adopted?.adopted && <div className="pos-badge pos-badge--green">{t('positionTab.plenaryAdopted', { date: parliament.plenary_adopted.date })}</div>}
      </div>
      <div className="pos-group-table-wrapper">
        <table className="pos-group-table">
          <thead>
            <tr>
              <th>{t('positionTab.group')}</th>
              <th>{t('positionTab.predictedStance', 'Predicted')}</th>
              {hasActual && <th>{t('positionTab.actual', 'Actual')}</th>}
              <th>{t('positionTab.cohesion')}</th>
              <th>{t('positionTab.amendments')}</th>
            </tr>
          </thead>
          <tbody>
            {parliament.groups.map((g) => (
              <tr key={g.group_code}>
                <td className="pos-group-table__group-name">{g.group_code}</td>
                <td><StanceBadge stance={g.stance} /></td>
                {hasActual && <td className="pos-group-table__actual">{actualForGroup(actual!.group_breakdown, g.group_code) || '-'}</td>}
                <td className="pos-group-table__cohesion">{(g.cohesion * 100).toFixed(0)}%</td>
                <td className="pos-group-table__count">{g.amendment_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {parliament.amendment_activity?.total > 0 && (
        <div className="pos-card__footer">
          <SourceTag kind="evidenced" /> {t('positionTab.totalAmendmentsTabled', { n: parliament.amendment_activity.total })}
        </div>
      )}
    </div>
  );
}

function CouncilCard({ council }: { council: PositionResponse['council_position'] }) {
  const { t } = useTranslation();
  const { summary, member_states } = council;
  const supporting = member_states.filter((m) => m.stance === 'support');
  const opposing = member_states.filter((m) => m.stance === 'oppose');
  const undecided = member_states.filter((m) => m.stance !== 'support' && m.stance !== 'oppose');
  return (
    <div className="pos-card pos-card--council">
      <div className="pos-card__header"><Icon path={mdiBank} size={1} /><h3>{t('positionTab.councilLabel')}</h3><SourceTag kind="predicted" /></div>
      <div className="pos-card__meta">
        <div>{t('positionTab.supportingOpposingUndecided', { s: summary.supporting_count ?? 0, o: summary.opposing_count ?? 0, u: summary.undecided_count ?? 0 })}</div>
        {council.general_approach_adopted && <div className="pos-badge pos-badge--green">{t('positionTab.generalApproach')}</div>}
      </div>
      <div className="pos-ms-grid">
        {[{ title: t('positionTab.blocSupporting'), list: supporting, color: 'var(--pos-green)' },
          { title: t('positionTab.blocOpposing'), list: opposing, color: 'var(--pos-red)' },
          { title: t('positionTab.blocUndecided'), list: undecided, color: 'var(--pos-neutral)' }].map((bloc) => (
          <div key={bloc.title} className="pos-ms-bloc" style={{ borderTopColor: bloc.color }}>
            <div className="pos-ms-bloc__title">{bloc.title} ({bloc.list.length})</div>
            <div className="pos-ms-bloc__chips">
              {bloc.list.length === 0 && <span className="pos-ms-bloc__empty">-</span>}
              {bloc.list.map((m) => {
                const confCls = m.confidence === 'high' ? 'pos-ms-chip--high' : m.confidence === 'low' ? 'pos-ms-chip--low' : 'pos-ms-chip--medium';
                return <span key={m.country_code} className={`pos-ms-chip ${confCls}`} title={t('positionTab.countryConfidence', { country: m.country_name, confidence: m.confidence })}>{m.country_code}</span>;
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CommissionCard({ commission, procedureRef }: { commission: PositionResponse['commission_position']; procedureRef: string }) {
  const { t } = useTranslation();
  return (
    <div className="pos-card pos-card--commission">
      <div className="pos-card__header"><Icon path={mdiFileDocumentOutline} size={1} /><h3>{t('positionTab.commissionProposal')}</h3><SourceTag kind="evidenced" /></div>
      <div className="pos-card__meta">
        <div><strong>{commission.title || t('positionTab.untitled')}</strong></div>
        <div>{t('positionTab.procedure')} {procedureRef}</div>
        {commission.com_references && commission.com_references.length > 0 && <div>{t('positionTab.comReferences')} {commission.com_references.join(', ')}</div>}
        {commission.proposal_date && <div>{t('positionTab.proposalDate')} {commission.proposal_date.slice(0, 10)}</div>}
      </div>
      {commission.description && <div className="pos-card__body">{commission.description}</div>}
      {commission.documents && commission.documents.length > 0 && (
        <ul className="pos-doc-list">
          {commission.documents.slice(0, 6).map((d, i) => (
            <li key={i}><a href={d.portal_url || '#'} target="_blank" rel="noopener">[{d.doc_type}] {d.reference}{d.title ? ` -- ${String(d.title).slice(0, 80)}` : ''}</a></li>
          ))}
        </ul>
      )}
    </div>
  );
}

// #2 Lobbying overlay: who met the rapporteur/shadows on this file.
// Who is lobbying this file, set against the file's OUTCOME. Engagement vs outcome -
// NOT causation; a true "did they get their ask" read needs the positions layer.
function LobbyingCard({ lobbying, onOpenLobby }: {
  lobbying: LobbyingResult | null;
  onOpenLobby: (org: string, trId: string | null) => void;
}) {
  const { t } = useTranslation();
  const outcome = lobbying?.outcome;
  const outcomeLabel = outcome
    ? (outcome.has_vote ? `${(outcome.vote_level || '').toUpperCase()} ${outcome.result}` : outcome.status || '')
    : '';
  const outcomeClass = outcome?.has_vote
    ? (/(adopt|approv)/i.test(outcome.result || '') ? 'is-adopted' : /(reject|withdraw)/i.test(outcome.result || '') ? 'is-rejected' : 'is-neutral')
    : 'is-neutral';
  return (
    <div className="pos-card pos-card--lobby">
      <div className="pos-card__header"><Icon path={mdiHandshakeOutline} size={1} /><h3>{t('positionTab.whoLobbied', 'Who is lobbying this file')}</h3><SourceTag kind="evidenced" /></div>
      {!lobbying || lobbying.total === 0 ? (
        <div className="pos-card__meta"><div>{t('positionTab.noLobby', 'No published rapporteur/shadow meetings on this file yet.')}</div></div>
      ) : (
        <>
          <div className="pos-lobby-outcome">
            <span className="pos-lobby-outcome__label">{t('positionTab.fileOutcome', 'File outcome')}</span>
            <span className={`pos-lobby-outcome__badge ${outcomeClass}`}>{outcomeLabel || t('positionTab.inProgress', 'In progress')}</span>
            {outcome?.vote_date && <span className="pos-lobby-outcome__date">{fmtDate(outcome.vote_date)}</span>}
          </div>
          <div className="pos-card__meta"><div>{t('positionTab.lobbyCount', { n: lobbying.total })}</div></div>
          <ul className="pos-lobby-list">
            {lobbying.organisations.slice(0, 10).map((o, i) => (
              <li key={i} className="pos-lobby-item">
                <button className="pos-lobby-org pos-lobby-org--btn" onClick={() => onOpenLobby(o.organisation, o.transparency_register_id)}
                  title={t('positionTab.openInLobby', 'Open footprint in Lobby Meetings') as string}>
                  {o.organisation}
                </button>
                {o.reached_rapporteur && <span className="pos-lobby-tag pos-lobby-tag--rapp">{t('positionTab.reachedRapporteur', 'Reached rapporteur')}</span>}
                {!o.reached_rapporteur && o.best_label && <span className="pos-lobby-tag">{o.best_label}</span>}
                {o.last_meeting && <span className="pos-lobby-when">{fmtDate(o.first_meeting) !== fmtDate(o.last_meeting) ? `${fmtDate(o.first_meeting)} - ${fmtDate(o.last_meeting)}` : fmtDate(o.last_meeting)}</span>}
                <span className="pos-lobby-n">{o.meetings}</span>
              </li>
            ))}
          </ul>
          <div className="pos-card__footer pos-foot-note">{t('positionTab.lobbyOutcomeNote', 'Engagement set against the outcome - not causation. A true read of whether each organisation got its ask needs its stated position (positions layer, coming).')}</div>
        </>
      )}
    </div>
  );
}

function UserPositionCard({ pos, onSave, onAction }: {
  pos: PositionResponse;
  onSave: (p: UserPosition) => Promise<void>;
  onAction: (kind: 'paper' | 'amend' | 'compare') => void;
}) {
  const { t } = useTranslation();
  const [stance, setStance] = useState(pos.user_position?.stance || 'undecided');
  const [notes, setNotes] = useState(pos.user_position?.notes || '');
  const [priorityArticles, setPriorityArticles] = useState((pos.user_position?.priority_articles || []).join(', '));
  const [evidence, setEvidence] = useState((pos.user_position?.evidence_urls || []).join(', '));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true); setSaved(false);
    try {
      await onSave({
        stance, notes,
        priority_articles: priorityArticles.split(',').map((s) => s.trim()).filter(Boolean),
        evidence_urls: evidence.split(',').map((s) => s.trim()).filter(Boolean),
      });
      setSaved(true);
    } finally { setSaving(false); }
  };

  const evidenceList = (pos.user_position?.evidence_urls || []).filter(Boolean);

  return (
    <div className="pos-card pos-card--user">
      <div className="pos-card__header"><Icon path={mdiScaleBalance} size={1} /><h3>{t('positionTab.yourPosition')}</h3></div>
      <div className="pos-user-form">
        <label>{t('positionTab.stanceLabel')}
          <select value={stance} onChange={(e) => setStance(e.target.value)}>
            {USER_STANCE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <label>{t('positionTab.notesLabel')}
          <textarea value={notes} rows={3} onChange={(e) => setNotes(e.target.value)} placeholder={t('positionTab.notesPlaceholder')} />
        </label>
        <label>{t('positionTab.priorityArticlesLabel')}
          <input value={priorityArticles} onChange={(e) => setPriorityArticles(e.target.value)} placeholder={t('positionTab.articlePlaceholder')} />
        </label>
        <label>{t('positionTab.evidenceLabel', 'Evidence links (comma-separated)')}
          <input value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="https://..." />
        </label>
        <button className="pos-btn" onClick={handleSave} disabled={saving}>
          <Icon path={mdiContentSave} size={0.9} />{saving ? t('positionTab.saving') : saved ? t('positionTab.saved') : t('positionTab.save')}
        </button>
        {evidenceList.length > 0 && (
          <ul className="pos-evidence-list">
            {evidenceList.map((u, i) => <li key={i}><a href={u} target="_blank" rel="noopener noreferrer"><Icon path={mdiOpenInNew} size={0.55} /> {u.replace(/^https?:\/\//, '').slice(0, 48)}</a></li>)}
          </ul>
        )}
        {pos.user_position?.last_updated && (
          <div className="pos-user-form__updated">{t('myFilesTab.cardLastUpdate')} {new Date(pos.user_position.last_updated).toLocaleString()}</div>
        )}
      </div>
      {/* #4 Action bridge: turn the position into a core action */}
      <div className="pos-actions">
        <button className="pos-action-btn" onClick={() => onAction('paper')}><Icon path={mdiClipboardTextOutline} size={0.8} /> {t('positionTab.genPaper', 'Generate position paper')}</button>
        <button className="pos-action-btn" onClick={() => onAction('amend')}><Icon path={mdiPencilOutline} size={0.8} /> {t('positionTab.draftAmendment', 'Draft amendment')}</button>
        <button className="pos-action-btn" onClick={() => onAction('compare')}><Icon path={mdiCompareHorizontal} size={0.8} /> {t('positionTab.openComparator', 'Open in Comparator')}</button>
      </div>
    </div>
  );
}

const STANCE_TONE: Record<string, string> = {
  support: 'is-support', oppose: 'is-oppose', amend: 'is-amend', mixed: 'is-mixed',
  pending: 'is-pending', unclear: 'is-pending',
};
const STANCE_TXT: Record<string, string> = {
  support: 'Supports', oppose: 'Opposes', amend: 'Wants amendments', mixed: 'Mixed',
  pending: 'Position filed', unclear: 'Position filed',
};

// Tier-1 Outcome Alignment: stated consultation positions of the orgs that lobbied this
// file, set against the file outcome. Org-anchored, sourced, hedged - no causation.
function OutcomeAlignment({ data, loading }: { data: AlignmentResult | null; loading: boolean }) {
  const { t } = useTranslation();
  if (loading) return <div className="pos-loading">{t('positionTab.loadingPosition')}</div>;
  if (!data) return <div className="pos-empty">{t('positionTab.alignNone', 'No lobbying data for this file yet.')}</div>;
  // No rapporteur/shadow lobbying meetings recorded for this file -> nothing to align.
  if (data.coverage.lobbying_orgs === 0) {
    return <div className="pos-empty">{t('positionTab.alignNoLobby', 'No rapporteur or shadow lobbying meetings are recorded for this file yet, so there are no positions to align.')}</div>;
  }

  const withPos = data.organisations.filter((o) => o.has_position);
  const without = data.organisations.filter((o) => !o.has_position);
  const outcome = data.outcome;
  const outcomeLabel = outcome ? (outcome.has_vote ? `${(outcome.vote_level || '').toUpperCase()} ${outcome.result}` : outcome.status || '') : '';
  const outcomeClass = outcome?.has_vote
    ? (/(adopt|approv)/i.test(outcome.result || '') ? 'is-adopted' : /(reject|withdraw)/i.test(outcome.result || '') ? 'is-rejected' : 'is-neutral')
    : 'is-neutral';

  return (
    <div className="pos-align">
      <div className="pos-align__head">
        <div className="pos-lobby-outcome">
          <span className="pos-lobby-outcome__label">{t('positionTab.fileOutcome', 'File outcome')}</span>
          <span className={`pos-lobby-outcome__badge ${outcomeClass}`}>{outcomeLabel || t('positionTab.inProgress', 'In progress')}</span>
        </div>
        <span className="pos-align__coverage">
          {t('positionTab.alignCoverage', { n: data.coverage.with_position, total: data.coverage.lobbying_orgs })}
        </span>
      </div>
      <p className="pos-foot-note">{t('positionTab.alignCaveat', 'Stated positions are what each organisation told the Commission in named EC consultations, matched by Transparency Register id. They are not necessarily on this exact dossier, and imply no causation.')}</p>

      {withPos.length === 0 ? (
        <div className="pos-empty">{t('positionTab.alignNoPositions', 'None of the organisations that lobbied this file have a captured EC consultation position yet.')}</div>
      ) : (
        <ul className="pos-align__list">
          {withPos.map((o: AlignmentOrg, i) => (
            <li key={i} className="pos-align__org">
              <div className="pos-align__org-head">
                <span className="pos-align__org-name">{o.organisation}</span>
                {o.reached_rapporteur && <span className="pos-lobby-tag pos-lobby-tag--rapp">{t('positionTab.reachedRapporteur', 'Reached rapporteur')}</span>}
                <span className="pos-lobby-n">{o.meetings}</span>
              </div>
              {o.positions.map((p, j) => (
                <div key={j} className="pos-align__pos">
                  <span className={`pos-align__stance ${STANCE_TONE[p.stance] || 'is-pending'}`}>
                    {t(`positionTab.stance_${p.stance}`, STANCE_TXT[p.stance] || 'Position filed')}
                  </span>
                  <div className="pos-align__pos-body">
                    {p.summary
                      ? <span className="pos-align__summary">{p.summary}</span>
                      : p.excerpt && <span className="pos-align__excerpt">{p.excerpt.slice(0, 200)}{p.excerpt.length > 200 ? '…' : ''}</span>}
                    <span className="pos-align__src">
                      <Icon path={mdiMessageTextOutline} size={0.55} />
                      {p.consultation_title || t('positionTab.consultation', 'EC consultation')}
                      {p.source_url && <a href={p.source_url} target="_blank" rel="noopener noreferrer"><Icon path={mdiOpenInNew} size={0.5} /></a>}
                    </span>
                  </div>
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}

      {without.length > 0 && (
        <details className="pos-align__without">
          <summary>{t('positionTab.alignNoCapture', { n: without.length })}</summary>
          <div className="pos-chips">{without.map((o, i) => <span key={i} className="lobby-chip is-muted">{o.organisation}</span>)}</div>
        </details>
      )}
    </div>
  );
}

export const PositionAnalysisTab: React.FC = () => {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [myInterests, setMyInterests] = useState(true);
  const [data, setData] = useState<PositionListResponse | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PositionResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [drilldown, setDrilldown] = useState<AmendmentDrilldown | null>(null);
  const [lobbying, setLobbying] = useState<LobbyingResult | null>(null);
  const [actual, setActual] = useState<ActualVote | null>(null);
  const [view, setView] = useState<'summary' | 'amendments'>('summary');
  const [topTab, setTopTab] = useState<'state' | 'alignment'>('state');
  const [alignment, setAlignment] = useState<AlignmentResult | null>(null);
  const [alignLoading, setAlignLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    positionService.list(myInterests, 40)
      .then((res) => {
        setData(res);
        // Deep-link preselect: ?ref=<procedure> (cross-link from Predictions). Else first.
        const ref = searchParams.get('ref');
        const all = [...res.tracked, ...res.suggested];
        const matched = ref ? all.find((f) => f.procedure_ref === ref)?.carriage_id : null;
        const first = matched || res.tracked[0]?.carriage_id || res.suggested[0]?.carriage_id || null;
        setSelectedId((cur) => matched || cur || first);
        if (ref) {
          setSearchParams((prev) => { const n = new URLSearchParams(prev); n.delete('ref'); return n; }, { replace: true });
        }
      })
      .catch((e: any) => setListError(e?.response?.data?.detail || e.message || 'Failed to load files'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myInterests]);

  useEffect(() => {
    if (!selectedId) return;
    setDetailLoading(true); setDetailError(null); setLobbying(null); setActual(null);
    positionService.get(selectedId)
      .then((d) => setDetail(d))
      .catch((e: any) => setDetailError(e?.response?.data?.detail || e.message || 'Failed to load position'))
      .finally(() => setDetailLoading(false));
    positionService.amendments(selectedId).then(setDrilldown).catch(() => setDrilldown(null));
    positionService.lobbying(selectedId).then(setLobbying).catch(() => setLobbying(null));
    positionService.actualVote(selectedId).then(setActual).catch(() => setActual(null));
    setAlignment(null);   // reset cross-file
  }, [selectedId]);

  // Load the Outcome-alignment data lazily when that tab is opened.
  useEffect(() => {
    if (topTab !== 'alignment' || !selectedId || alignment) return;
    setAlignLoading(true);
    positionService.alignment(selectedId)
      .then(setAlignment).catch(() => setAlignment(null))
      .finally(() => setAlignLoading(false));
  }, [topTab, selectedId, alignment]);

  const handleRefresh = async () => {
    if (!selectedId) return;
    setRefreshing(true);
    try { setDetail(await positionService.get(selectedId, true)); }
    catch (e: any) { setDetailError(e?.response?.data?.detail || e.message || 'Refresh failed'); }
    finally { setRefreshing(false); }
  };

  const handleSaveUserPosition = async (payload: UserPosition) => {
    if (!selectedId) return;
    const updated = await positionService.saveUserPosition(selectedId, payload);
    setDetail(updated);
    setData((prev) => prev ? {
      ...prev,
      tracked: prev.tracked.map((x) => x.carriage_id === selectedId ? { ...x, user_stance: payload.stance } : x),
    } : prev);
  };

  const handleAction = (kind: 'paper' | 'amend' | 'compare') => {
    const ref = detail?.procedure_ref || '';
    if (kind === 'amend') {
      navigate(`/amendator${ref ? `?procedure=${encodeURIComponent(ref)}` : ''}`);
    } else if (kind === 'compare') {
      setSearchParams({ tab: 'comparator', ...(ref ? { procedure: ref } : {}) });
    } else {
      setSearchParams({ tab: 'documents', ...(ref ? { generate: 'position_paper', procedure: ref } : {}) });
    }
  };

  // Open one organisation's full footprint in Lobby Meetings.
  const openLobby = (orgName: string, trId: string | null) => {
    setSearchParams({ tab: 'lobby_meetings', org: orgName, ...(trId ? { org_tr: trId } : {}) });
  };
  // Cross-link to the forecast (Predictions) for this file.
  const seeForecast = () => {
    if (detail?.procedure_ref) setSearchParams({ tab: 'predictions', ref: detail.procedure_ref });
  };

  const renderBucket = (items: PositionListItem[]) => (
    <ul className="pos-file-list">
      {items.map((item) => (
        <li key={item.carriage_id}>
          <FileItem item={item} active={item.carriage_id === selectedId} onClick={() => { setSelectedId(item.carriage_id); setView('summary'); setTopTab('state'); }} />
        </li>
      ))}
    </ul>
  );

  return (
    <div className="pos-tab">
      <aside className="pos-tab__sidebar">
        <header className="pos-tab__sidebar-header">
          <Icon path={mdiScaleBalance} size={1} />
          <div><h2>{t('positionTab.headerTitle')}</h2><p>{t('positionTab.headerSubtitle')}</p></div>
        </header>

        <div className="pos-toggle">
          <button className={myInterests ? 'is-active' : ''} onClick={() => setMyInterests(true)}>{t('positionTab.mine', 'My interests')}</button>
          <button className={!myInterests ? 'is-active' : ''} onClick={() => setMyInterests(false)}>{t('positionTab.all', 'All tracked')}</button>
        </div>

        {listError && <div className="pos-error">{listError}</div>}
        {data === null && <div className="pos-loading">{t('positionTab.loadingTracked')}</div>}

        {data && (
          <>
            <div className="pos-bucket-title"><Icon path={mdiStarOutline} size={0.7} /> {t('positionTab.tracked', 'Tracked')} ({data.tracked.length})</div>
            {data.tracked.length === 0
              ? <div className="pos-empty" dangerouslySetInnerHTML={{ __html: t('positionTab.emptyTracking') }} />
              : renderBucket(data.tracked)}

            {myInterests && data.suggested.length > 0 && (
              <>
                <div className="pos-bucket-title"><Icon path={mdiTrendingUp} size={0.7} /> {t('positionTab.suggested', 'Suggested for your interests')} ({data.suggested.length})</div>
                {renderBucket(data.suggested)}
              </>
            )}
          </>
        )}
      </aside>

      <section className="pos-tab__main">
        {selectedId === null && (
          <div className="pos-placeholder"><Icon path={mdiScaleBalance} size={3} /><h3>{t('positionTab.pickFile')}</h3><p>{t('positionTab.eachFileShows')}</p></div>
        )}
        {selectedId && detailLoading && <div className="pos-loading">{t('positionTab.loadingPosition')}</div>}
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
                  {detail.generated_at && <span className="pos-detail-header__timestamp">Snapshot: {new Date(detail.generated_at).toLocaleString()}</span>}
                </div>
              </div>
              <div className="pos-detail-header__actions">
                <button className="pos-btn pos-btn--ghost" onClick={seeForecast}>
                  <Icon path={mdiCrystalBall} size={0.9} /> {t('positionTab.seeForecast', 'See forecast')}
                </button>
                <button className="pos-btn pos-btn--ghost" onClick={handleRefresh} disabled={refreshing}>
                  <Icon path={mdiRefresh} size={0.9} />{refreshing ? t('positionTab.refreshing', 'Refreshing...') : t('positionTab.refresh', 'Refresh')}
                </button>
              </div>
            </header>

            {/* #3 Actual outcome banner */}
            {actual?.has_vote && (
              <div className="pos-actual-banner">
                <Icon path={mdiCheckDecagram} size={0.85} />
                <span>
                  {t('positionTab.actualOutcome', 'Actual outcome')}: <strong>{(actual.level || '').toUpperCase()} {actual.result}</strong>
                  {' '}{actual.votes_for}-{actual.votes_against}-{actual.votes_abstention}
                  {actual.vote_date ? ` (${new Date(actual.vote_date).toLocaleDateString()})` : ''}
                </span>
                {actual.source_url && <a href={actual.source_url} target="_blank" rel="noopener noreferrer"><Icon path={mdiOpenInNew} size={0.6} /></a>}
              </div>
            )}

            {/* Top-level tabs: State of play | Outcome alignment */}
            <nav className="pos-toptabs" role="tablist">
              <button role="tab" aria-selected={topTab === 'state'} className={topTab === 'state' ? 'is-active' : ''} onClick={() => setTopTab('state')}>
                <Icon path={mdiScaleBalance} size={0.75} /> {t('positionTab.tabStateOfPlay', 'State of play')}
              </button>
              <button role="tab" aria-selected={topTab === 'alignment'} className={topTab === 'alignment' ? 'is-active' : ''} onClick={() => setTopTab('alignment')}>
                <Icon path={mdiTargetAccount} size={0.75} /> {t('positionTab.tabOutcomeAlignment', 'Outcome alignment')}
              </button>
            </nav>

            {topTab === 'state' && (<>
            <nav className="pos-view-switch" role="tablist">
              <button className={`pos-view-switch__btn ${view === 'summary' ? 'pos-view-switch__btn--active' : ''}`} onClick={() => setView('summary')}><Icon path={mdiTrendingUp} size={0.9} /> {t('positionTab.summary', 'Summary')}</button>
              <button className={`pos-view-switch__btn ${view === 'amendments' ? 'pos-view-switch__btn--active' : ''}`} onClick={() => setView('amendments')}><Icon path={mdiChevronRight} size={0.9} /> {t('positionTab.articleByArticle', 'Article-by-article')}</button>
              <span className="pos-view-info" tabIndex={0} role="img"
                aria-label={t('positionTab.articleByArticleTip', 'Every tabled amendment rolled up to the article it targets, with the bar showing which political groups are driving changes - ranked by how contested each article is.') as string}>
                <Icon path={mdiInformationOutline} size={0.7} />
                <span className="pos-view-info__bubble" role="tooltip">
                  {t('positionTab.articleByArticleTip', 'Every tabled amendment rolled up to the article it targets, with the bar showing which political groups are driving changes - ranked by how contested each article is.')}
                </span>
              </span>
            </nav>

            {view === 'summary' && (
              <div className="pos-grid">
                {/* Evidenced first, then predicted (the #5 reframing) */}
                <CommissionCard commission={detail.commission_position} procedureRef={detail.procedure_ref} />
                <LobbyingCard lobbying={lobbying} onOpenLobby={openLobby} />
                <GroupsCard parliament={detail.parliament_position} actual={actual} />
                <CouncilCard council={detail.council_position} />
                <UserPositionCard pos={detail} onSave={handleSaveUserPosition} onAction={handleAction} />
              </div>
            )}
            {view === 'amendments' && <AmendmentDrilldownTable drilldown={drilldown} />}
            </>)}

            {topTab === 'alignment' && <OutcomeAlignment data={alignment} loading={alignLoading} />}
          </>
        )}
      </section>
    </div>
  );
};
