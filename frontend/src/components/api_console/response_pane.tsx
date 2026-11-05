// frontend/src/components/api_console/response_pane.tsx
// Step 3: what came back, as things a person recognises: the title, what matters about it, where to read it. The five
// datapoints every Brubru item carries are one fold away. Text from the API is only ever shown as text; a link opens
// only if it is http(s).
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ConsoleCatalogue, ConsoleOperation, ConsolePricing, ConsoleResponse } from '../../services/api_console';
import {
  formatEuro,
  curlSnippet, fieldErrorsOf, humanise, isDateRefusal, isItemRoute, isList, isOurAddress, itemOfRow, pageInfo, pythonSnippet, reasonOf, rowFacts, rowsOf, rowText, rowTitle,
  safeHttpUrl, sandboxServes, shortenedJson, totalIsEstimate, totalOf,
} from '../../services/api_console';
import { ConsoleTip } from './console_tip';

const ROWS_SHOWN = 25;
const SNIPPET_LENGTH = 260;
const SLOW_AFTER_SECONDS = 3;
const VERY_SLOW_AFTER_SECONDS = 25;
const POINTS = ['public_url', 'body_txt', 'body_html', 'document_date', 'creation_date', 'updated_date'];
// A filter a person chose, as opposed to how the page is laid out.
const NOT_A_FILTER = new Set(['limit', 'page', 'include_body', 'order']);

type Tab = 'rows' | 'json' | 'code';

const CopyButton = ({ text }: { text: string }) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <button type="button" className="api-console__copy" onClick={copy}>
      <span className={`mdi ${copied ? 'mdi-check' : 'mdi-content-copy'}`} aria-hidden="true" />
      {copied ? t('api.console.copied') : t('api.console.copy')}
    </button>
  );
};

const Datapoints = ({ row, bodiesRequested }: { row: Record<string, any>; bodiesRequested: boolean }) => {
  const { t, i18n } = useTranslation();
  const empty = <span className="api-console__empty">{t('api.console.emptyValue')}</span>;
  const url = safeHttpUrl(row.public_url);
  const value = (name: string) => {
    const raw = row[name];
    if (name === 'public_url') return url ? <a href={url} target="_blank" rel="noopener noreferrer">{url}</a> : empty;
    if (name === 'body_txt' || name === 'body_html') {
      if (typeof raw === 'string' && raw.length > 0) return t('api.console.characters', { count: raw.length, formatted: raw.length.toLocaleString(i18n.language) });
      return bodiesRequested ? empty : <span className="api-console__not-requested">{t('api.console.notRequested')}</span>;
    }
    return typeof raw === 'string' && raw ? <code>{raw}</code> : empty;
  };
  return (
    <details className="api-console__points">
      <summary>
        {t('api.console.datapointsTitle')}
        <ConsoleTip label={t('api.console.datapointsTipLabel')}><p>{t('api.console.datapointsNote')}</p></ConsoleTip>
      </summary>
      <dl>
        {POINTS.map((name) => (
          <div className="api-console__point" key={name}>
            <dt>
              <code>{name}</code>
              <ConsoleTip label={t('api.console.moreAbout', { name })}><p>{t(`api.console.points.${name}`)}</p></ConsoleTip>
            </dt>
            <dd>{value(name)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
};

interface RowProps {
  row: Record<string, any>;
  bodiesRequested: boolean;
  single: boolean;
  catalogue: ConsoleCatalogue;
  op: ConsoleOperation;
  noCallsLeft: boolean;
  ownKey: boolean;
  pricing: ConsolePricing | null;
  onOpen: (target: { op: ConsoleOperation; values: Record<string, string> }) => void;
}

const RowCard = ({ row, bodiesRequested, single, catalogue, op, noCallsLeft, ownKey, pricing, onOpen }: RowProps) => {
  const { t, i18n } = useTranslation();
  const title = rowTitle(row);
  const url = isOurAddress(row.public_url) ? null : safeHttpUrl(row.public_url);
  const facts = rowFacts(row);
  const words = rowText(row);
  // Many a summary opens with the title again: say it once.
  const text = title && words.toLowerCase().startsWith(title.toLowerCase()) ? words.slice(title.length).replace(/^[\s:;,.-]+/, '') : words;
  const fullText = typeof row.body_txt === 'string' ? row.body_txt : '';
  const target = single ? null : itemOfRow(catalogue, row, op);
  // A row whose full item is not in the free trial opens on the form that says so, without a call.
  const targetFree = target ? ownKey || sandboxServes(target.op.path.replace(/\{[^}]+\}/g, 'x'), pricing) : true;

  const factWords = (value: string | boolean | number, key?: string) => {
    // A policy area's code: finance-economy.
    if (key === 'families' && typeof value === 'string') return (value.charAt(0).toUpperCase() + value.slice(1)).replace(/-/g, ' ');
    if (value === true) return t('api.console.yes');
    if (value === false) return t('api.console.no');
    if (typeof value === 'number') return value.toLocaleString(i18n.language);
    // A moment as a day people read; the Raw data tab keeps the exact value.
    if (/^\d{4}-\d{2}-\d{2}([T ]|$)/.test(value)) {
      const moment = new Date(value);
      // British English: 18 Nov 2026.
      const locale = i18n.language.startsWith('en') ? 'en-GB' : i18n.language;
      if (!Number.isNaN(moment.getTime())) return moment.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
    }
    // MEMBER and COMMISSION read as words; ENVI and BEL stay codes.
    const shown = /^[A-Z_]{5,}$/.test(value) ? value.charAt(0) + value.slice(1).toLowerCase().replace(/_/g, ' ') : value;
    return t(`api.console.options.${value}`, { defaultValue: shown, nsSeparator: false, keySeparator: '.' });
  };

  return (
    <article className="api-console__row">
      {title ? <h4>{title.length > 260 ? `${title.slice(0, 260)}...` : title}</h4> : null}
      {facts.length > 0 && (
        <dl className="api-console__facts-list">
          {facts.map(({ key, value }) => (
            <div key={key}>
              <dt>{t(`api.console.fields.${key}.label`, { defaultValue: humanise(key) })}</dt>
              <dd>{factWords(value, key)}</dd>
            </div>
          ))}
        </dl>
      )}
      {!single && text && <p className="api-console__snippet">{text.slice(0, SNIPPET_LENGTH)}{text.length > SNIPPET_LENGTH ? '...' : ''}</p>}
      {single && url && (
        <div className="api-console__row-actions">
          <a href={url} target="_blank" rel="noopener noreferrer" className="api-console__row-link">
            <span className="mdi mdi-open-in-new" aria-hidden="true" /> {t('api.console.officialPage')}
          </a>
        </div>
      )}
      {single && fullText && (
        <details className="api-console__full-text" open>
          <summary>{t('api.console.fullTextTitle', { formatted: fullText.length.toLocaleString(i18n.language) })}</summary>
          <div className="api-console__full-text-body">{fullText.slice(0, 20000)}{fullText.length > 20000 ? '...' : ''}</div>
        </details>
      )}
      {single && !fullText && text && <p className="api-console__snippet">{text}</p>}
      <div className="api-console__row-actions">
        {target && (
          <button type="button" className="api-console__row-open" disabled={noCallsLeft && targetFree} onClick={() => onOpen(target)}>
            <span className="mdi mdi-open-in-app" aria-hidden="true" /> {ownKey ? t('api.console.ownKey.openItem') : targetFree ? t('api.console.openItem') : t('api.console.openItemKey')}
          </button>
        )}
        {url && !single && (
          <a href={url} target="_blank" rel="noopener noreferrer" className="api-console__row-link">
            <span className="mdi mdi-open-in-new" aria-hidden="true" /> {t('api.console.officialPage')}
          </a>
        )}
      </div>
      {('public_url' in row || 'updated_date' in row || 'document_date' in row || 'body_txt' in row) && <Datapoints row={row} bodiesRequested={bodiesRequested} />}
    </article>
  );
};

interface Props {
  catalogue: ConsoleCatalogue;
  op: ConsoleOperation;
  values: Record<string, string>;
  response: ConsoleResponse | null;
  sending: boolean;
  failed: boolean;
  cancelled: boolean;
  bodiesRequested: boolean;
  callsAllowed: number | null;
  ownKey: boolean;
  sandboxLeft: number | null;
  maxPage: number | null;
  pricing: ConsolePricing | null;
  listParent: ConsoleOperation | null;
  canGoBack: boolean;
  onBack: () => void;
  onTryWord: (word: string) => void;
  onCancel: () => void;
  onOpen: (target: { op: ConsoleOperation; values: Record<string, string> }) => void;
  onNextPage: () => void;
  onRemoveFilter: (name: string) => void;
  onGoToList: (op: ConsoleOperation) => void;
  onRefine: () => void;
  onStopKey: () => void;
}

export const ResponsePane = ({
  catalogue, op, values, response, sending, failed, cancelled, bodiesRequested, callsAllowed, ownKey, sandboxLeft, maxPage, pricing, listParent, canGoBack, onBack, onTryWord,
  onCancel, onOpen, onNextPage, onRemoveFilter, onGoToList, onRefine, onStopKey,
}: Props) => {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>('rows');
  const [elapsed, setElapsed] = useState(0);

  const rows = useMemo(() => (response ? rowsOf(response.json) : []), [response]);
  const ok = Boolean(response && response.status >= 200 && response.status < 300);
  const list = response ? isList(response.json) : false;
  const total = response ? totalOf(response.json) : null;
  const reason = response ? reasonOf(response.json) : { code: '', message: '' };
  const fieldErrors = response ? fieldErrorsOf(response.json) : [];
  const paging = response ? pageInfo(response.json, values) : null;
  const shownRows = rows.length > 0;

  useEffect(() => {
    // Nothing matched: the box above says what to do, and the raw data stays one click away.
    if (response) setTab(ok && !shownRows && !list ? 'json' : 'rows');
  }, [response, ok, shownRows, list]);

  useEffect(() => {
    if (!sending) {
      setElapsed(0);
      return undefined;
    }
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 500);
    return () => window.clearInterval(timer);
  }, [sending]);

  const capped = reason.code === 'sandbox_ip_capped' || reason.code === 'sandbox_global_capped';
  const noBalance = reason.code === 'insufficient_balance' || response?.status === 402;
  const needsKey = !ownKey && (capped || reason.code.startsWith('sandbox_') || response?.status === 401 || response?.status === 403);
  const status = response?.status ?? 0;
  const refusalText = () => {
    if (ownKey && status === 401) return t('api.console.ownKey.rejected');
    if (ownKey && noBalance) return t('api.console.ownKey.noBalance');
    if (reason.code === 'sandbox_ip_capped') return t('api.console.capVisitor');
    if (reason.code === 'sandbox_global_capped') return t('api.console.capPool');
    if (status === 404) return reason.message || t('api.console.notFound');
    if (status === 429) return t('api.console.tooManyCalls');
    if (status === 502 || status === 503) return reason.message || t('api.console.serverFault');
    if (status >= 500) return t('api.console.serverFault');
    if (fieldErrors.length > 0) return t('api.console.checkFields');
    return reason.message || t('api.console.failedStatus', { status });
  };
  const activeFilters = Object.entries(values).filter(([name, value]) => value && !NOT_A_FILTER.has(name) && op.params.some((p) => p.name === name && p.in === 'query'));
  const noCallsLeft = sandboxLeft === 0;
  // Two words that never meet may each find plenty.
  const words = (values.q || '').split(/\s+/).filter((w) => w.length > 2).slice(0, 5);
  const servedHere = ownKey || sandboxServes(op.path.replace(/\{[^}]+\}/g, 'x'), pricing);

  const statusWords = () => {
    if (ok) return t('api.console.statusOk');
    if (status === 404) return t('api.console.statusNotFound');
    if (status >= 500) return t('api.console.statusServer');
    return t('api.console.statusRefused');
  };

  return (
    <div className="api-console__pane api-console__pane--response" aria-live="polite">
      <h2 className="api-console__step">
        <span className="api-console__step-number" aria-hidden="true">3</span>
        {t('api.console.stepResults')}
      </h2>

      {!response && !sending && !failed && !cancelled && (
        <div className="api-console__idle">
          <span className="mdi mdi-text-search" aria-hidden="true" />
          {noCallsLeft ? <p>{t('api.console.capVisitor')}</p> : servedHere ? (
            <>
              <p>{ownKey ? t('api.console.ownKey.idle') : isItemRoute(op) ? t('api.console.idleItem') : t('api.console.idleList')}</p>
              {!ownKey && <p className="api-console__idle-small">{t('api.console.idleCost', { calls: callsAllowed ?? 10 })}</p>}
            </>
          ) : <p>{t('api.console.idleNeedsKey')}</p>}
        </div>
      )}
      {cancelled && !sending && !response && <p className="api-console__note">{t('api.console.cancelled')}</p>}
      {sending && (
        <div className="api-console__waiting">
          <p><span className="mdi mdi-loading mdi-spin" aria-hidden="true" /> {isItemRoute(op) ? t('api.console.opening', { seconds: elapsed }) : t('api.console.waiting', { seconds: elapsed })}</p>
          {elapsed >= SLOW_AFTER_SECONDS && elapsed < VERY_SLOW_AFTER_SECONDS && <p className="api-console__note">{t('api.console.slowNote')}</p>}
          {elapsed >= VERY_SLOW_AFTER_SECONDS && <p className="api-console__note">{t('api.console.verySlowNote')}</p>}
          <button type="button" className="api-console__link-button" onClick={onCancel}>{t('api.console.cancel')}</button>
          <ConsoleTip label={t('api.console.cancelTipLabel')}><p>{t('api.console.cancelTip')}</p></ConsoleTip>
        </div>
      )}
      {failed && !sending && <p className="api-console__problem">{t('api.console.networkError')}</p>}

      {canGoBack && !sending && (
        <button type="button" className="api-console__link-button api-console__results-back" onClick={onBack}>
          <span className="mdi mdi-arrow-left" aria-hidden="true" /> {t('api.console.backToResults')}
        </button>
      )}

      {response && !sending && (
        <>
          <div className="api-console__facts">
            <span className={`api-console__status api-console__status--${ok ? 'ok' : 'bad'}`} data-status={status}>
              {statusWords()}
              <ConsoleTip label={t('api.console.statusTipLabel')}><p>{t('api.console.statusTip', { status })}</p></ConsoleTip>
            </span>
            {ok && total !== null && (
              <span className="api-console__total">
                {paging && totalIsEstimate(response.json, rows.length, paging.page, paging.limit)
                  ? t('api.console.rowsAtLeast', { formatted: ((paging.page - 1) * paging.limit + rows.length).toLocaleString(i18n.language) })
                  : t('api.console.rowsFound', { count: total, formatted: total.toLocaleString(i18n.language) })}
              </span>
            )}
            <span>{t('api.console.seconds', { value: (response.ms / 1000).toLocaleString(i18n.language, { maximumFractionDigits: 1 }) })}</span>
            {!ownKey && (sandboxLeft ?? response.sandboxLeft) !== null && <span>{t('api.console.callsLeft', { count: sandboxLeft ?? response.sandboxLeft })}</span>}
            {ownKey && response.costEur !== null && <span data-own-key-cost>{t('api.console.ownKey.cost', { cost: formatEuro(response.costEur, i18n.language) })}</span>}
            {ownKey && response.balanceEur !== null && <span data-own-key-balance>{t('api.console.ownKey.balance', { balance: formatEuro(response.balanceEur, i18n.language) })}</span>}
          </div>
          {!isItemRoute(op) && (
            <button type="button" className="api-console__link-button api-console__refine" onClick={onRefine}>
              <span className="mdi mdi-tune-variant" aria-hidden="true" /> {t('api.console.refine')}
            </button>
          )}

          {!ok && (
            <div className="api-console__problem">
              <p>{refusalText()}</p>
              {fieldErrors.length > 0 && (
                <ul className="api-console__field-errors">
                  {fieldErrors.map((error, i) => (
                    <li key={i}>
                      <strong>{t(`api.console.fields.${error.field}.label`, { defaultValue: humanise(error.field) })}:</strong> {isDateRefusal(error.message) ? t('api.console.hintMoment') : error.message}
                    </li>
                  ))}
                </ul>
              )}
              {reason.code && !capped && fieldErrors.length === 0 && !(ownKey && (status === 401 || noBalance)) && <p><code>{reason.code}</code></p>}
              {ownKey && status === 401 && (
                <p><button type="button" className="api-console__link-button" onClick={onStopKey}>{t('api.console.ownKey.stop')}</button></p>
              )}
              {needsKey && (
                <p>
                  <Link to="/api#your-keys">{t('api.console.getKey')}</Link>{' · '}
                  <a href="mailto:hello@beresol.eu?subject=Brubru%20API%20pricing">{t('api.console.askPricing')}</a>
                </p>
              )}
              {ownKey && noBalance && <p><Link to="/api/billing">{t('api.console.ownKey.topUp')}</Link>{' · '}<a href="mailto:hello@beresol.eu?subject=Brubru%20API%20pricing">{t('api.console.askPricing')}</a></p>}
              {status === 404 && listParent && (
                <button type="button" className="api-console__link-button" onClick={() => onGoToList(listParent)}>
                  <span className="mdi mdi-format-list-bulleted" aria-hidden="true" /> {t('api.console.goToList')}
                </button>
              )}
            </div>
          )}

          {ok && list && rows.length === 0 && (
            <div className="api-console__zero">
              <p><strong>{t('api.console.zeroTitle')}</strong></p>
              <p>{activeFilters.length > 0 ? t('api.console.zeroWithFilters') : t('api.console.zeroNoFilters')}</p>
              {activeFilters.length > 0 && (
                <div className="api-console__filter-chips">
                  {activeFilters.map(([name, value]) => (
                    <button key={name} type="button" className="api-console__filter-chip" onClick={() => onRemoveFilter(name)}>
                      {t(`api.console.fields.${name}.label`, { defaultValue: humanise(name) })}: {value}
                      <span className="mdi mdi-close" aria-label={t('api.console.removeFilter')} />
                    </button>
                  ))}
                </div>
              )}
              {!i18n.language.startsWith('en') && <p className="api-console__note">{t('api.console.mostlyEnglish')}</p>}
              {words.length > 1 && (
                <div className="api-console__examples">
                  <span>{t('api.console.tryOneWord')}</span>
                  {words.map((word) => (
                    <button key={word} type="button" className="api-console__example" disabled={noCallsLeft} onClick={() => onTryWord(word)}>{word}</button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="api-console__tabs" role="tablist">
            {ok && shownRows && (
              <button type="button" role="tab" aria-selected={tab === 'rows'} onClick={() => setTab('rows')}>{t('api.console.tabRows')}</button>
            )}
            <button type="button" role="tab" aria-selected={tab === 'json'} onClick={() => setTab('json')}>{t('api.console.tabJson')}</button>
            <button type="button" role="tab" aria-selected={tab === 'code'} onClick={() => setTab('code')}>{t('api.console.tabCode')}</button>
          </div>

          {tab === 'rows' && ok && shownRows && (
            <div className="api-console__rows">
              {rows.slice(0, ROWS_SHOWN).map((row, i) => (
                <RowCard
                  key={i}
                  row={row}
                  bodiesRequested={bodiesRequested}
                  single={!list}
                  catalogue={catalogue}
                  op={op}
                  noCallsLeft={noCallsLeft}
                  ownKey={ownKey}
                  pricing={pricing}
                  onOpen={onOpen}
                />
              ))}
              {rows.length > ROWS_SHOWN && <p className="api-console__note">{t('api.console.moreInJson', { shown: ROWS_SHOWN, count: rows.length })}</p>}
              {list && paging?.hasMore && op.params.some((p) => p.name === 'page') && (
                <div className="api-console__next">
                  {maxPage !== null && paging.page >= maxPage
                    ? <p className="api-console__note">{t('api.console.lastFreePage')} <Link to="/api#your-keys">{t('api.console.getKey')}</Link></p>
                    : (
                      <button type="button" className="api-console__copy" disabled={noCallsLeft} onClick={onNextPage}>
                        <span className="mdi mdi-arrow-right" aria-hidden="true" /> {t('api.console.nextPage')}
                      </button>
                    )}
                </div>
              )}
            </div>
          )}

          {tab === 'json' && (
            <div className="api-console__code">
              <div className="api-console__code-head">
                <span className="api-console__note">{t('api.console.shortened')}</span>
                <CopyButton text={response.text} />
              </div>
              <pre>{shortenedJson(response.json, response.text)}</pre>
            </div>
          )}

          {tab === 'code' && (
            <div className="api-console__code">
              <p className="api-console__note">{t('api.console.codeNote')}</p>
              <p className="api-console__note">{t('api.console.notAProgrammer')} <Link to="/mcp">{t('api.console.connectAssistant')}</Link></p>
              <div className="api-console__code-head"><strong>curl</strong><CopyButton text={curlSnippet(response.url)} /></div>
              <pre>{curlSnippet(response.url)}</pre>
              <div className="api-console__code-head"><strong>Python</strong><CopyButton text={pythonSnippet(response.url)} /></div>
              <pre>{pythonSnippet(response.url)}</pre>
              <p className="api-console__note">
                <Link to="/api#your-keys">{t('api.console.getKey')}</Link>{' · '}
                <a href="mailto:hello@beresol.eu?subject=Brubru%20API%20pricing">{t('api.console.askPricing')}</a>
              </p>
            </div>
          )}

          {response.requestId && (
            <p className="api-console__request-id">{t('api.console.requestId')} <code>{response.requestId}</code></p>
          )}
        </>
      )}
    </div>
  );
};
