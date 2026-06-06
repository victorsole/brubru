/**
 * Votes Tab — EP committee + plenary roll-call results.
 *
 * Two sub-tabs (Committee results | Plenary results), each a list of vote
 * cards: outcome donut + per-group breakdown bars + tally. PI lens shared with
 * the rest of MEUB ("My interests | All"). A card opens a detail modal with the
 * per-MEP roll-call and — when the dossier was voted at both levels — the
 * committee->plenary delta the EP itself never shows.
 *
 * Data: /api/ep-votes/{committee,plenary,detail/{id},procedure/{ref},my-committees,stats}
 */

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiGavel, mdiAccountGroup, mdiStar, mdiClose, mdiMagnify,
  mdiOpenInNew, mdiSwapHorizontal, mdiCheckCircle, mdiCloseCircle, mdiScaleBalance,
  mdiBankOutline, mdiInformationOutline, mdiImageFilterCenterFocus,
  mdiClipboardListOutline, mdiFilePdfBox, mdiAccountVoice, mdiCalendarOutline,
} from '@mdi/js';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './votes_tab.css';
import { FreshnessChip } from './freshness_chip';
import { LensToggle, TrackedBadge, type LensMode } from './lens_toggle';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

// EP political-group colours (kept close to the groups' own brand colours).
const GROUP_COLORS: Record<string, string> = {
  'PPE': '#3399ff', 'EPP': '#3399ff',
  'S&D': '#e2001a',
  'Renew': '#f6c026', 'RE': '#f6c026',
  'Verts/ALE': '#2e8b57', 'Greens/EFA': '#2e8b57',
  'ECR': '#1a5fb4',
  'PfE': '#15397f',
  'The Left': '#b5121b', 'GUE/NGL': '#b5121b',
  'ESN': '#6c3a86',
  'NI': '#8a8f98', 'NA': '#8a8f98',
};
const groupColor = (g: string) => GROUP_COLORS[g] || '#6b7280';

const CHOICE_COLORS = { '+': '#2e8b57', '-': '#c0392b', '0': '#9aa0a6' };

// EU27 in Council protocol order, with English names (EL = Greece).
const EU27_ORDER: [string, string][] = [
  ['BE', 'Belgium'], ['BG', 'Bulgaria'], ['CZ', 'Czechia'], ['DK', 'Denmark'],
  ['DE', 'Germany'], ['EE', 'Estonia'], ['IE', 'Ireland'], ['EL', 'Greece'],
  ['ES', 'Spain'], ['FR', 'France'], ['HR', 'Croatia'], ['IT', 'Italy'],
  ['CY', 'Cyprus'], ['LV', 'Latvia'], ['LT', 'Lithuania'], ['LU', 'Luxembourg'],
  ['HU', 'Hungary'], ['MT', 'Malta'], ['NL', 'Netherlands'], ['AT', 'Austria'],
  ['PL', 'Poland'], ['PT', 'Portugal'], ['RO', 'Romania'], ['SI', 'Slovenia'],
  ['SK', 'Slovakia'], ['FI', 'Finland'], ['SE', 'Sweden'],
];
const EU27_NAME: Record<string, string> = Object.fromEntries(EU27_ORDER);
const COUNCIL_VOTE_COLOR: Record<string, string> = {
  for: CHOICE_COLORS['+'], against: CHOICE_COLORS['-'], abstain: CHOICE_COLORS['0'],
};

type Level = 'committee' | 'plenary' | 'council' | 'voting_lists';

// A committee voting list (the amendment order paper behind a vote) - a document,
// not a roll-call result, so a distinct shape from Vote.
interface VotingList {
  reference: string | null;
  title: string | null;
  item_title: string | null;
  committee_code: string | null;
  committee_name: string | null;
  meeting_date: string | null;
  procedure_ref: string | null;
  rapporteurs: string[];
  pdf_url: string | null;
  source_url: string | null;
  languages: string[];
  matches_interests: boolean;
  matches_tracked: boolean;
}
interface VotingListResponse {
  items: VotingList[]; total: number; my_committees: string[]; pi_active: boolean;
  has_tracked_files?: boolean; files_active?: boolean;
}
// The voting-list PDF(s) attached to a roll-call vote where the dossier matches.
interface VoteVotingList {
  committee_code: string | null; meeting_date: string | null;
  item_title: string | null; title: string | null;
  pdf_url: string | null; source_url: string | null;
}

// Council-specific breakdown shape (auto-read from the Council's image result sheet).
interface CouncilBreakdown {
  votes?: Record<string, 'for' | 'against' | 'abstain'>;
  qmv?: { member_states_pct?: number | null; population_pct?: number | null };
  confidence?: 'high' | 'medium' | 'low' | null;
  vision_model?: string | null;
  meeting_no?: string | null;
  config?: string | null;
}

interface GroupSplit { '+': number; '-': number; '0': number; }
interface Vote {
  id: string;
  level: Level;
  procedure_ref: string | null;
  carriage_id: string | null;
  report_ref: string | null;
  ta_reference: string | null;
  title: string | null;
  subject: string | null;
  committee_code: string | null;
  vote_date: string | null;
  sitting_date: string | null;
  item_number: string | null;
  result: string | null;
  votes_for: number | null;
  votes_against: number | null;
  votes_abstention: number | null;
  total_records: number;
  group_breakdown: Record<string, GroupSplit>;
  country_breakdown: CouncilBreakdown;
  source_url: string | null;
  matches_interests: boolean;
  matches_tracked?: boolean;
  has_delta: boolean;
  margin: number;
  contestedness: number;
}
interface ListResponse {
  items: Vote[]; total: number; my_committees: string[]; pi_active: boolean;
  has_tracked_files?: boolean; files_active?: boolean;
}
interface MepRecord { mep_name: string; political_group: string | null; country: string | null; vote_choice: '+' | '-' | '0'; is_intention: boolean; }
interface Delta {
  confirmed: boolean; committee_result: string; plenary_result: string;
  committee_margin: number; plenary_margin: number;
  committee_tally: number[]; plenary_tally: number[];
}

const authCfg = () => {
  const token = useAuth.getState().token;
  return token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
};

// ---- small presentational pieces -----------------------------------------

const Donut = ({ f, a, ab, size = 64 }: { f: number; a: number; ab: number; size?: number }) => {
  const total = f + a + ab || 1;
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  const segs = [
    { v: f, color: CHOICE_COLORS['+'] },
    { v: a, color: CHOICE_COLORS['-'] },
    { v: ab, color: CHOICE_COLORS['0'] },
  ];
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="votes-donut" aria-hidden="true">
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        {segs.map((s, i) => {
          const len = (s.v / total) * c;
          const el = (
            <circle key={i} cx={size / 2} cy={size / 2} r={r} fill="none"
              stroke={s.color} strokeWidth={9}
              strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset} />
          );
          offset += len;
          return el;
        })}
      </g>
    </svg>
  );
};

const GroupBars = ({ breakdown, compact = false }: { breakdown: Record<string, GroupSplit>; compact?: boolean }) => {
  const rows = Object.entries(breakdown)
    .map(([g, s]) => ({ g, ...s, total: (s['+'] || 0) + (s['-'] || 0) + (s['0'] || 0) }))
    .filter((r) => r.total > 0)
    .sort((x, y) => y.total - x.total);
  const max = Math.max(1, ...rows.map((r) => r.total));
  const shown = compact ? rows.slice(0, 5) : rows;
  return (
    <div className="votes-groupbars">
      {shown.map((r) => (
        <div className="votes-groupbar" key={r.g}>
          <span className="votes-groupbar__label" style={{ color: groupColor(r.g) }}>{r.g}</span>
          <span className="votes-groupbar__track" style={{ width: `${(r.total / max) * 100}%` }}>
            {(['+', '-', '0'] as const).map((ch) =>
              r[ch] > 0 ? (
                <span key={ch} className="votes-groupbar__seg"
                  style={{ flexGrow: r[ch], background: CHOICE_COLORS[ch] }} />
              ) : null,
            )}
          </span>
          <span className="votes-groupbar__nums">
            <b style={{ color: CHOICE_COLORS['+'] }}>{r['+']}</b>/
            <b style={{ color: CHOICE_COLORS['-'] }}>{r['-']}</b>/
            <b style={{ color: CHOICE_COLORS['0'] }}>{r['0']}</b>
          </span>
        </div>
      ))}
      {compact && rows.length > 5 && <div className="votes-groupbar__more">+{rows.length - 5}</div>}
    </div>
  );
};

// ---- Council-specific pieces ----------------------------------------------

// 27-cell member-state strip, coloured by each country's vote.
const CountryStrip = ({ votes, compact = false }: { votes: Record<string, string>; compact?: boolean }) => (
  <div className={`votes-cstrip ${compact ? 'is-compact' : ''}`}>
    {EU27_ORDER.map(([code, name]) => {
      const v = votes[code];
      const color = v ? COUNCIL_VOTE_COLOR[v] : '#e5e7eb';
      const label = v ? `${name}: ${v}` : `${name}: no record`;
      return (
        <span key={code} className="votes-cstrip__cell" style={{ background: color }}
          title={label} aria-label={label}>
          {compact ? '' : code}
        </span>
      );
    })}
  </div>
);

// QMV gauges: member-states % (threshold 55%) and population % (threshold 65%).
const QmvBars = ({ qmv }: { qmv: CouncilBreakdown['qmv'] }) => {
  const { t } = useTranslation();
  if (!qmv || (qmv.member_states_pct == null && qmv.population_pct == null)) return null;
  const Row = ({ label, pct, threshold }: { label: string; pct: number | null | undefined; threshold: number }) => {
    if (pct == null) return null;
    const met = pct >= threshold;
    return (
      <div className="votes-qmv__row">
        <span className="votes-qmv__lbl">{label}</span>
        <span className="votes-qmv__track">
          <span className="votes-qmv__fill" style={{ width: `${Math.min(100, pct)}%`, background: met ? CHOICE_COLORS['+'] : '#d99100' }} />
          <span className="votes-qmv__thresh" style={{ left: `${threshold}%` }} title={`${t('votes.council.threshold', 'threshold')} ${threshold}%`} />
        </span>
        <span className="votes-qmv__val">{pct.toFixed(1)}%</span>
      </div>
    );
  };
  return (
    <div className="votes-qmv">
      <Row label={t('votes.council.memberStates', 'Member states') as string} pct={qmv.member_states_pct} threshold={55} />
      <Row label={t('votes.council.population', 'Population') as string} pct={qmv.population_pct} threshold={65} />
    </div>
  );
};

// Provenance: confidence flag + tooltip explaining the data is read from an image sheet.
const ProvenanceTag = ({ cb }: { cb: CouncilBreakdown }) => {
  const { t } = useTranslation();
  if (!cb || !cb.confidence) return null;
  const tip = t('votes.council.provenance',
    'The Council publishes per-country results only as an image. Brubru reads the arrows (green up = in favour, red down = against, yellow circle = abstention) automatically. Always verify against the source sheet.') as string;
  return (
    <span className={`votes-prov is-${cb.confidence}`} title={tip}>
      <Icon path={mdiImageFilterCenterFocus} size={0.55} />
      {t('votes.council.autoread', 'Auto-read')}
      <Icon path={mdiInformationOutline} size={0.5} />
    </span>
  );
};

const ResultPill = ({ result }: { result: string | null }) => {
  const adopted = result === 'adopted';
  return (
    <span className={`votes-pill ${adopted ? 'is-adopted' : 'is-rejected'}`}>
      <Icon path={adopted ? mdiCheckCircle : mdiCloseCircle} size={0.6} />
      {adopted ? 'Adopted' : 'Rejected'}
    </span>
  );
};

// ---- detail modal ---------------------------------------------------------

const DetailModal = ({ vote, onClose }: { vote: Vote; onClose: () => void }) => {
  const { t } = useTranslation();
  const [records, setRecords] = useState<MepRecord[]>([]);
  const [delta, setDelta] = useState<Delta | null>(null);
  const [votingLists, setVotingLists] = useState<VoteVotingList[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const d = await axios.get(`${API_BASE}/ep-votes/detail/${vote.id}`, authCfg());
        setRecords(d.data?.records || []);
        setVotingLists(d.data?.voting_lists || []);
        if (vote.has_delta && vote.procedure_ref) {
          try {
            const p = await axios.get(
              `${API_BASE}/ep-votes/procedure/${encodeURIComponent(vote.procedure_ref)}`, authCfg());
            setDelta(p.data?.delta || null);
          } catch { /* delta optional */ }
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [vote.id]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return records;
    return records.filter((r) =>
      r.mep_name.toLowerCase().includes(needle) ||
      (r.political_group || '').toLowerCase().includes(needle));
  }, [records, q]);

  const byChoice = (ch: '+' | '-' | '0') => filtered.filter((r) => r.vote_choice === ch);

  const isCouncil = vote.level === 'council';
  const cb = vote.country_breakdown || {};
  const levelLabel = isCouncil
    ? t('votes.council.tab', 'Council')
    : vote.level === 'committee' ? t('votes.committee', 'Committee') : t('votes.plenary', 'Plenary');
  const levelIcon = isCouncil ? mdiBankOutline : vote.level === 'committee' ? mdiAccountGroup : mdiGavel;

  return createPortal(
    <div className="votes-modal__overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="votes-modal" onClick={(e) => e.stopPropagation()}>
        <button className="votes-modal__close" onClick={onClose} aria-label={t('common.close', 'Close')}>
          <Icon path={mdiClose} size={1} />
        </button>

        <div className="votes-modal__head">
          <div className="votes-modal__tags">
            <span className={`votes-leveltag is-${vote.level}`}>
              <Icon path={levelIcon} size={0.6} />
              {levelLabel}
            </span>
            {vote.committee_code && <span className="votes-chip">{vote.committee_code}</span>}
            {vote.report_ref && <span className="votes-chip is-muted">{vote.report_ref}</span>}
            {isCouncil && cb.meeting_no && (
              <span className="votes-chip is-muted">{t('votes.council.meeting', 'Meeting')} {cb.meeting_no}</span>
            )}
          </div>
          <h2>{vote.title}</h2>
          <p className="votes-modal__sub">{vote.subject} · {vote.vote_date}</p>
        </div>

        <div className="votes-modal__outcome">
          <Donut f={vote.votes_for || 0} a={vote.votes_against || 0} ab={vote.votes_abstention || 0} size={88} />
          <div className="votes-tallybig">
            <ResultPill result={vote.result} />
            <div className="votes-tallybig__row">
              <span style={{ color: CHOICE_COLORS['+'] }}>{vote.votes_for} {t('votes.for', 'for')}</span>
              <span style={{ color: CHOICE_COLORS['-'] }}>{vote.votes_against} {t('votes.against', 'against')}</span>
              <span style={{ color: CHOICE_COLORS['0'] }}>{vote.votes_abstention} {t('votes.abstention', 'abstentions')}</span>
            </div>
          </div>
        </div>

        {isCouncil && (
          <div className="votes-council-detail">
            {cb.confidence && (
              <p className="votes-council-detail__prov" title={t('votes.council.provenance',
                'The Council publishes per-country results only as an image. Brubru reads the arrows (green up = in favour, red down = against, yellow circle = abstention) automatically. Always verify against the source sheet.') as string}>
                <Icon path={mdiImageFilterCenterFocus} size={0.7} />
                {t('votes.council.provShort', 'Per-country results auto-read from the Council’s official image result sheet — qualified-majority vote.')}
                {vote.source_url && (
                  <a href={vote.source_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                    {t('votes.council.verify', 'Verify source')} <Icon path={mdiOpenInNew} size={0.55} />
                  </a>
                )}
              </p>
            )}
            <QmvBars qmv={cb.qmv} />
            <CountryStrip votes={cb.votes || {}} />
          </div>
        )}

        {delta && (
          <div className="votes-delta">
            <h3><Icon path={mdiSwapHorizontal} size={0.8} /> {t('votes.delta.title', 'Committee → Plenary')}</h3>
            <div className="votes-delta__grid">
              <div>
                <span className="votes-delta__cap">{t('votes.committee', 'Committee')}</span>
                <b>{delta.committee_tally[0]}/{delta.committee_tally[1]}/{delta.committee_tally[2]}</b>
                <span className={`votes-delta__res is-${delta.committee_result}`}>{delta.committee_result}</span>
              </div>
              <Icon path={mdiSwapHorizontal} size={1} className="votes-delta__arrow" />
              <div>
                <span className="votes-delta__cap">{t('votes.plenary', 'Plenary')}</span>
                <b>{delta.plenary_tally[0]}/{delta.plenary_tally[1]}/{delta.plenary_tally[2]}</b>
                <span className={`votes-delta__res is-${delta.plenary_result}`}>{delta.plenary_result}</span>
              </div>
            </div>
            <p className="votes-delta__verdict">
              {delta.confirmed
                ? t('votes.delta.confirmed', 'Plenary confirmed the committee.')
                : t('votes.delta.diverged', 'Plenary diverged from the committee.')}
            </p>
          </div>
        )}

        {votingLists.length > 0 && (
          <div className="votes-modal__section votes-votinglist-attach">
            <h3><Icon path={mdiClipboardListOutline} size={0.8} /> {t('votes.votingList.attachTitle', 'Voting list')}</h3>
            <p className="votes-muted votes-votinglist-attach__note">
              {t('votes.votingList.attachNote', 'The order paper this vote ran from - which amendments, in what order, with the compromises.')}
            </p>
            <ul className="votes-votinglist-attach__list">
              {votingLists.map((vl, i) => (
                <li key={i}>
                  <a href={vl.pdf_url || vl.source_url || undefined} target="_blank" rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}>
                    <Icon path={mdiFilePdfBox} size={0.75} />
                    {vl.committee_code} {vl.meeting_date ? `· ${vl.meeting_date}` : ''}
                    <Icon path={mdiOpenInNew} size={0.55} />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {!isCouncil && (
          <div className="votes-modal__section">
            <h3><Icon path={mdiAccountGroup} size={0.8} /> {t('votes.byGroup', 'By political group')}</h3>
            <GroupBars breakdown={vote.group_breakdown} />
          </div>
        )}

        <div className="votes-modal__section">
          <div className="votes-modal__rcvhead">
            <h3>
              {isCouncil ? t('votes.council.byState', 'By member state') : t('votes.rollCall', 'Roll-call')}{' '}
              <span className="votes-muted">({records.length})</span>
            </h3>
            <div className="votes-search">
              <Icon path={mdiMagnify} size={0.8} />
              <input value={q} onChange={(e) => setQ(e.target.value)}
                placeholder={(isCouncil ? t('votes.council.searchState', 'Search member state') : t('votes.searchMep', 'Search MEP or group')) as string} />
            </div>
          </div>
          {loading ? <p className="votes-muted">{t('common.loading', 'Loading…')}</p> : records.length === 0 ? (
            <p className="votes-muted">{t('votes.council.noBreakdown', 'Council act adopted — no per-member-state breakdown published for this item.')}</p>
          ) : (
            <div className="votes-rcv">
              {(['+', '-', '0'] as const).map((ch) => (
                <div className="votes-rcv__col" key={ch}>
                  <div className="votes-rcv__colhead" style={{ color: CHOICE_COLORS[ch] }}>
                    {ch === '+' ? t('votes.for', 'For') : ch === '-' ? t('votes.against', 'Against') : t('votes.abstention', 'Abstentions')}
                    <span>{byChoice(ch).length}</span>
                  </div>
                  <ul>
                    {byChoice(ch).map((r, i) => (
                      <li key={i}>
                        <span className="votes-rcv__dot" style={{ background: isCouncil ? CHOICE_COLORS[ch] : groupColor(r.political_group || 'NI') }} />
                        {isCouncil ? (r.mep_name || EU27_NAME[r.country || ''] || r.country) : r.mep_name}
                        <span className="votes-rcv__grp">{isCouncil ? r.country : r.political_group}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
};

// ---- vote card ------------------------------------------------------------

const VoteCard = ({ vote, onOpen }: { vote: Vote; onOpen: (v: Vote) => void }) => {
  const { t } = useTranslation();
  const isCouncil = vote.level === 'council';
  const cb = vote.country_breakdown || {};
  const hasBreakdown = !isCouncil || Object.keys(cb.votes || {}).length > 0;
  const total = (vote.votes_for || 0) + (vote.votes_against || 0) + (vote.votes_abstention || 0);
  return (
    <article className={`votes-card ${vote.matches_interests ? 'is-pi' : ''}`} onClick={() => onOpen(vote)}>
      <div className="votes-card__top">
        <div className="votes-card__tags">
          {vote.committee_code && <span className="votes-chip">{vote.committee_code}</span>}
          {isCouncil && <ProvenanceTag cb={cb} />}
          {vote.has_delta && (
            <span className="votes-chip is-delta"
              title={t('votes.deltaTip', 'This dossier was voted at both committee and plenary stage. Open the card to see how the plenary changed the committee result — a comparison the Parliament itself does not publish.') as string}>
              <Icon path={mdiScaleBalance} size={0.55} /> {t('votes.deltaBadge', 'Delta')}
            </span>
          )}
          {vote.matches_tracked && <TrackedBadge />}
          {vote.matches_interests && (
            <span className="votes-chip is-pi" title={t('votes.matches', 'Matches your interests') as string}>
              <Icon path={mdiStar} size={0.55} /> {t('votes.mine', 'My interests')}
            </span>
          )}
        </div>
        <span className="votes-card__date">{vote.vote_date}</span>
      </div>

      <h3 className="votes-card__title">{vote.title}</h3>
      {vote.subject && <p className="votes-card__subject">{vote.subject}</p>}

      {isCouncil && !hasBreakdown ? (
        <div className="votes-card__nodata">
          <Icon path={mdiBankOutline} size={0.9} />
          <p>{t('votes.council.noBreakdown', 'Council act adopted — no per-member-state breakdown published for this item.')}</p>
        </div>
      ) : (
        <div className="votes-card__body">
          <div className="votes-card__outcome">
            <Donut f={vote.votes_for || 0} a={vote.votes_against || 0} ab={vote.votes_abstention || 0} />
            <div className="votes-card__tally">
              <ResultPill result={vote.result} />
              <div className="votes-card__nums">
                <span style={{ color: CHOICE_COLORS['+'] }}>{vote.votes_for}</span>
                <span style={{ color: CHOICE_COLORS['-'] }}>{vote.votes_against}</span>
                <span style={{ color: CHOICE_COLORS['0'] }}>{vote.votes_abstention}</span>
              </div>
              <span className="votes-muted">{total} {isCouncil ? t('votes.council.states', 'states') : t('votes.cast', 'cast')}</span>
            </div>
          </div>
          {isCouncil ? (
            <div className="votes-card__council">
              <CountryStrip votes={cb.votes || {}} compact />
              <QmvBars qmv={cb.qmv} />
            </div>
          ) : (
            <GroupBars breakdown={vote.group_breakdown} compact />
          )}
        </div>
      )}

      <div className="votes-card__foot">
        {vote.carriage_id && (
          <a className="votes-link" href={`/my-eu-bubble?tab=my_files&file=${vote.carriage_id}`}
            onClick={(e) => e.stopPropagation()}>
            <Icon path={mdiOpenInNew} size={0.6} /> {t('votes.openDossier', 'Open dossier')}
          </a>
        )}
        {vote.source_url && (
          <a className="votes-link is-muted" href={vote.source_url} target="_blank" rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            title={t('votes.sourceTip', 'Open the official published voting record on the EU institution’s own website') as string}>
            <Icon path={mdiOpenInNew} size={0.6} />{' '}
            {isCouncil
              ? t('votes.sourceCouncil', 'Council result sheet')
              : t('votes.sourceEp', 'EP official record')}
          </a>
        )}
      </div>
    </article>
  );
};

// A committee voting list - a document card (no tally), with a prominent PDF link.
const VotingListCard = ({ vl }: { vl: VotingList }) => {
  const { t } = useTranslation();
  const href = vl.pdf_url || vl.source_url || undefined;
  const label = vl.item_title || vl.title || vl.reference || vl.committee_name || '';
  return (
    <article className={`votes-card votes-vlcard ${vl.matches_interests ? 'is-pi' : ''}`}>
      <div className="votes-card__top">
        <div className="votes-card__tags">
          {vl.committee_code && <span className="votes-chip">{vl.committee_code}</span>}
          {vl.matches_tracked && <TrackedBadge />}
          {vl.matches_interests && (
            <span className="votes-chip is-pi" title={t('votes.matches', 'Matches your interests') as string}>
              <Icon path={mdiStar} size={0.55} /> {t('votes.mine', 'My interests')}
            </span>
          )}
        </div>
        {vl.meeting_date && (
          <span className="votes-card__date"><Icon path={mdiCalendarOutline} size={0.6} /> {vl.meeting_date}</span>
        )}
      </div>

      <h3 className="votes-card__title">{label}</h3>
      <div className="votes-vlcard__meta">
        {vl.procedure_ref && <span className="votes-chip is-muted">{vl.procedure_ref}</span>}
        {vl.rapporteurs.length > 0 && (
          <span className="votes-vlcard__rapp"><Icon path={mdiAccountVoice} size={0.6} /> {vl.rapporteurs.join(', ')}</span>
        )}
      </div>

      <div className="votes-card__foot">
        {href && (
          <a className="votes-link votes-vlcard__pdf" href={href} target="_blank" rel="noopener noreferrer">
            <Icon path={mdiFilePdfBox} size={0.7} /> {t('votes.votingList.openPdf', 'Open voting list (PDF)')}
            <Icon path={mdiOpenInNew} size={0.55} />
          </a>
        )}
        {vl.procedure_ref && (
          <a className="votes-link is-muted"
            href={`/my-eu-bubble?tab=my_files&procedure=${encodeURIComponent(vl.procedure_ref)}`}>
            <Icon path={mdiOpenInNew} size={0.6} /> {t('votes.openDossier', 'Open dossier')}
          </a>
        )}
      </div>
    </article>
  );
};

// ---- main tab -------------------------------------------------------------

export const VotesTab = () => {
  const { t } = useTranslation();
  const [level, setLevel] = useState<Level>('committee');
  const [mode, setMode] = useState<LensMode>('all');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'date' | 'margin' | 'dissent'>('date');
  const [data, setData] = useState<ListResponse | null>(null);
  const [vlData, setVlData] = useState<VotingListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<Vote | null>(null);
  const [stats, setStats] = useState<{ committee: number; plenary: number; council: number; voting_lists: number; with_delta: number } | null>(null);

  const isVL = level === 'voting_lists';

  useEffect(() => {
    axios.get(`${API_BASE}/ep-votes/stats`).then((r) => setStats(r.data)).catch(() => { });
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (mode === 'pi') params.set('my_interests', 'true');
    if (mode === 'files') params.set('my_files', 'true');
    if (search.trim()) params.set('search', search.trim());
    if (isVL) {
      axios.get<VotingListResponse>(`${API_BASE}/ep-votes/voting-lists?${params.toString()}`, authCfg())
        .then((r) => setVlData(r.data))
        .catch(() => setVlData({ items: [], total: 0, my_committees: [], pi_active: false }))
        .finally(() => setLoading(false));
    } else {
      params.set('sort_by', sortBy);
      axios.get<ListResponse>(`${API_BASE}/ep-votes/${level}?${params.toString()}`, authCfg())
        .then((r) => setData(r.data))
        .catch(() => setData({ items: [], total: 0, my_committees: [], pi_active: false }))
        .finally(() => setLoading(false));
    }
  }, [level, mode, search, sortBy, isVL]);

  const items = data?.items || [];
  const vlItems = vlData?.items || [];
  const active = isVL ? vlData : data;
  const hasPi = (active?.my_committees || []).length > 0;

  return (
    <div className="votes-tab">
      <header className="votes-tab__head">
        <div>
          <h1><Icon path={mdiGavel} size={1.1} /> {t('votes.title', 'Votes')}</h1>
          <p>{t('votes.intro', 'How the Parliament voted on the dossiers in your interests: committee and plenary, ordered the way the EP does not.')}</p>
          <FreshnessChip sourceKey={['votes_ep', 'votes_council']} />
        </div>
        {stats && (
          <div className="votes-tab__stats">
            <span><b>{stats.committee}</b> {t('votes.committeeVotes', 'committee')}</span>
            <span><b>{stats.plenary}</b> {t('votes.plenaryVotes', 'plenary')}</span>
            <span><b>{stats.council}</b> {t('votes.councilVotes', 'council')}</span>
            <span><b>{stats.voting_lists}</b> {t('votes.votingListsCount', 'voting lists')}</span>
            <span><b>{stats.with_delta}</b> {t('votes.withDelta', 'with delta')}</span>
          </div>
        )}
      </header>

      <div className="votes-tab__tabs" role="tablist">
        <button role="tab" aria-selected={level === 'committee'}
          className={level === 'committee' ? 'is-active' : ''} onClick={() => setLevel('committee')}>
          <Icon path={mdiAccountGroup} size={0.8} /> {t('votes.committeeResults', 'Committee results')}
        </button>
        <button role="tab" aria-selected={level === 'plenary'}
          className={level === 'plenary' ? 'is-active' : ''} onClick={() => setLevel('plenary')}>
          <Icon path={mdiGavel} size={0.8} /> {t('votes.plenaryResults', 'Plenary results')}
        </button>
        <button role="tab" aria-selected={level === 'council'}
          className={level === 'council' ? 'is-active' : ''} onClick={() => setLevel('council')}>
          <Icon path={mdiBankOutline} size={0.8} /> {t('votes.councilResults', 'Council results')}
        </button>
        <button role="tab" aria-selected={level === 'voting_lists'}
          className={level === 'voting_lists' ? 'is-active' : ''} onClick={() => setLevel('voting_lists')}>
          <Icon path={mdiClipboardListOutline} size={0.8} /> {t('votes.votingListsTab', 'Voting lists')}
        </button>
      </div>

      <div className="votes-tab__controls">
        <LensToggle mode={mode} onChange={setMode} hasPi={hasPi} hasFiles={!!active?.has_tracked_files} />
        <div className="votes-search">
          <Icon path={mdiMagnify} size={0.8} />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={t('votes.searchDossier', 'Search a dossier') as string} />
        </div>
        {!isVL && (
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)} className="votes-sort">
            <option value="date">{t('votes.sortDate', 'Most recent')}</option>
            <option value="margin">{t('votes.sortMargin', 'Closest margin')}</option>
            <option value="dissent">{t('votes.sortDissent', 'Most contested')}</option>
          </select>
        )}
      </div>

      {isVL && (
        <p className="votes-tab__pinote votes-tab__vlnote">
          {t('votes.votingList.tabNote', 'The committee order papers behind the votes - which amendments get voted, in what order, with the compromises. Mostly forward-looking.')}
        </p>
      )}

      {mode === 'pi' && active && (active.my_committees.length > 0) && (
        <p className="votes-tab__pinote">
          {t('votes.piNote', 'Showing your Policy-Interest committees:')} {active.my_committees.join(', ')}
        </p>
      )}

      {loading ? (
        <p className="votes-muted votes-tab__empty">{t('common.loading', 'Loading…')}</p>
      ) : isVL ? (
        vlItems.length === 0 ? (
          <div className="votes-tab__empty">
            <Icon path={mdiClipboardListOutline} size={2} />
            <p>{mode === 'pi'
              ? t('votes.votingList.emptyPi', 'No voting lists yet for your interest committees.')
              : mode === 'files'
              ? t('votes.votingList.emptyFiles', 'No voting lists on the files you track.')
              : t('votes.votingList.empty', 'No committee voting lists recorded yet.')}</p>
          </div>
        ) : (
          <div className="votes-grid">
            {vlItems.map((vl, i) => <VotingListCard key={vl.reference || `${vl.procedure_ref}-${i}`} vl={vl} />)}
          </div>
        )
      ) : items.length === 0 ? (
        <div className="votes-tab__empty">
          <Icon path={mdiGavel} size={2} />
          <p>{mode === 'pi'
            ? t('votes.emptyPi', 'No votes yet for your interest committees at this level.')
            : mode === 'files'
            ? t('votes.emptyFiles', 'No votes on the files you track at this level.')
            : t('votes.empty', 'No votes recorded yet at this level.')}</p>
        </div>
      ) : (
        <div className="votes-grid">
          {items.map((v) => <VoteCard key={v.id} vote={v} onOpen={setOpen} />)}
        </div>
      )}

      {open && <DetailModal vote={open} onClose={() => setOpen(null)} />}
    </div>
  );
};
