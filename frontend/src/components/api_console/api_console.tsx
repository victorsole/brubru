// frontend/src/components/api_console/api_console.tsx
// The API Console: catalogue, request, response. Used full screen at /api/try and as the panel on /api.
// The catalogue is free and loads when the console comes into view; a metered call only ever follows the Send button.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ConsoleCatalogue, ConsoleOperation, ConsolePricing, ConsoleResponse } from '../../services/api_console';
import { BUNDLE_ORDER, bodiesRequested, buildRequestPath, bundleCount, initialValues, loadCatalogue, loadPricing, sendRequest, startOfBundle } from '../../services/api_console';
import { CataloguePane } from './catalogue_pane';
import { RequestPane } from './request_pane';
import { ResponsePane } from './response_pane';
import './api_console.css';

// Where a visitor can start. Paths the live spec does not hold are left out rather than shown broken.
const STARTERS: Array<{ path: string; key: string }> = [
  { path: '/api/v2/news/all', key: 'startNews' },
  { path: '/api/v2/funding/opportunities', key: 'startFunding' },
  { path: '/api/v2/legislative/eur-lex/laws', key: 'startLaws' },
  { path: '/api/v2/legislative/oeil/procedures', key: 'startProcedures' },
];

interface Props {
  compact?: boolean;
  initialRoute?: string | null;
  initialBundle?: string | null;
}

export const ApiConsole = ({ compact = false, initialRoute = null, initialBundle = null }: Props) => {
  const { t } = useTranslation();
  const rootRef = useRef<HTMLDivElement>(null);
  const requestRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [wanted, setWanted] = useState(!compact);
  const [bundle, setBundle] = useState(BUNDLE_ORDER.includes(initialBundle || '') ? (initialBundle as string) : '');
  const [catalogue, setCatalogue] = useState<ConsoleCatalogue | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [pricing, setPricing] = useState<ConsolePricing | null>(null);
  const [selected, setSelected] = useState<ConsoleOperation | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [response, setResponse] = useState<ConsoleResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState(false);
  const [bodiesOn, setBodiesOn] = useState(true);
  const [sandboxLeft, setSandboxLeft] = useState<number | null>(null);

  // The panel on /api waits until it is near the screen, so the page does not pay for the whole spec up front.
  useEffect(() => {
    if (wanted || !rootRef.current || typeof IntersectionObserver === 'undefined') {
      if (typeof IntersectionObserver === 'undefined') setWanted(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) setWanted(true);
    }, { rootMargin: '400px' });
    observer.observe(rootRef.current);
    return () => observer.disconnect();
  }, [wanted]);

  const select = useCallback((op: ConsoleOperation, scroll = false) => {
    abortRef.current?.abort();
    setSelected(op);
    setValues(initialValues(op));
    setResponse(null);
    setFailed(false);
    setSending(false);
    if (scroll && window.matchMedia('(max-width: 767px)').matches) {
      requestRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  const load = useCallback(() => {
    setLoadFailed(false);
    loadCatalogue().then(setCatalogue).catch(() => setLoadFailed(true));
    loadPricing().then(setPricing).catch(() => setPricing(null));
  }, []);

  useEffect(() => {
    // Not while the page is being pre-rendered at build time: the static page keeps its empty state.
    if (wanted && !navigator.webdriver) load();
  }, [wanted, load]);

  useEffect(() => {
    if (!catalogue || selected) return;
    const first = catalogue.operations.find((op) => op.path === initialRoute)
      || (bundle ? startOfBundle(catalogue, bundle) : undefined)
      || catalogue.operations.find((op) => op.path === STARTERS[0].path)
      || catalogue.operations[0];
    if (first) select(first);
  }, [catalogue, selected, initialRoute, bundle, select]);

  // Choosing a bundle makes no call: it narrows the list, and moves off a route that is not in it.
  const chooseBundle = useCallback((next: string) => {
    setBundle(next);
    if (!catalogue || !next || selected?.bundles.includes(next)) return;
    const start = startOfBundle(catalogue, next);
    if (start) select(start);
  }, [catalogue, selected, select]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const send = useCallback(async () => {
    if (!selected || sending) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setSending(true);
    setFailed(false);
    setResponse(null);
    setBodiesOn(bodiesRequested(selected, values));
    try {
      const result = await sendRequest(buildRequestPath(selected, values), controller.signal);
      setResponse(result);
      if (result.sandboxLeft !== null) setSandboxLeft(result.sandboxLeft);
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setFailed(true);
    } finally {
      if (!controller.signal.aborted) setSending(false);
    }
  }, [selected, values, sending]);

  const starters = catalogue ? STARTERS.filter((s) => catalogue.operations.some((op) => op.path === s.path)) : [];
  const allowance = pricing?.sandbox;

  return (
    <div ref={rootRef} className={`api-console${compact ? ' api-console--compact' : ''}`}>
      {compact && (
        <div className="api-console__bundles" role="group" aria-label={t('api.console.bundleCardsLabel')}>
          {BUNDLE_ORDER.map((id) => {
            const count = catalogue ? bundleCount(catalogue, id) : 0;
            return (
              <button
                key={id}
                type="button"
                className={`api-console__bundle${bundle === id ? ' api-console__bundle--active' : ''}`}
                aria-pressed={bundle === id}
                onClick={() => chooseBundle(bundle === id ? '' : id)}
              >
                <strong>{t(`api.bundles.${id}.name`)}</strong>
                <span>{t(`api.bundles.${id}.desc`)}</span>
                {count > 0 && <small>{t('api.console.resultCount', { count })}</small>}
              </button>
            );
          })}
        </div>
      )}

      <div className="api-console__bar">
        <div className="api-console__starters">
          {!compact && starters.length > 0 && <span className="api-console__starters-label">{t('api.console.start')}</span>}
          {!compact && starters.map((s) => (
            <button
              key={s.path}
              type="button"
              className={`api-console__starter${selected?.path === s.path ? ' api-console__starter--active' : ''}`}
              onClick={() => {
                const op = catalogue?.operations.find((o) => o.path === s.path);
                if (op) {
                  if (bundle && !op.bundles.includes(bundle)) setBundle('');
                  select(op, true);
                }
              }}
            >
              {t(`api.console.${s.key}`)}
            </button>
          ))}
        </div>
        <div className="api-console__allowance">
          {allowance && (
            <span>
              {sandboxLeft !== null
                ? t('api.console.callsLeft', { count: sandboxLeft })
                : t('api.console.allowance', { calls: allowance.calls_per_visitor_per_day, rows: allowance.max_limit })}
            </span>
          )}
          {compact && (
            <Link className="api-console__full-link" to={bundle ? `/api/try?bundle=${bundle}` : '/api/try'}>
              <span className="mdi mdi-arrow-expand" aria-hidden="true" /> {t('api.console.openFull')}
            </Link>
          )}
        </div>
      </div>

      {loadFailed && (
        <div className="api-console__problem">
          <p>{t('api.console.loadError')}</p>
          <button type="button" className="api-console__copy" onClick={load}>{t('api.console.retry')}</button>
        </div>
      )}
      {!catalogue && !loadFailed && <p className="api-console__note api-console__loading">{t('api.console.loading')}</p>}

      {catalogue && selected && (
        <div className="api-console__panes">
          <CataloguePane catalogue={catalogue} selected={selected} onSelect={(op) => select(op, true)} bundle={bundle} onBundle={chooseBundle} />
          <div ref={requestRef} className="api-console__request-anchor">
            <RequestPane
              op={selected}
              values={values}
              pricing={pricing}
              sending={sending}
              sandboxLeft={sandboxLeft}
              onChange={(name, value) => setValues((v) => ({ ...v, [name]: value }))}
              onSend={send}
            />
          </div>
          <ResponsePane response={response} sending={sending} failed={failed} bodiesRequested={bodiesOn} />
        </div>
      )}
    </div>
  );
};
