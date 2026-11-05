// frontend/src/components/api_console/api_console.tsx
// The API Console: choose what you want, narrow it down, read the results. Used full screen at /api/try and as the panel
// on /api. The catalogue, the prices and the pick lists are free and load when the console comes into view; a metered call
// only ever follows something a person pressed, and the words beside it say that it uses a free call. Pressing a card is
// such a press: the first thing a person does should show results, not one more form to fill in.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ConsoleCatalogue, ConsoleOperation, ConsolePricing, ConsoleResponse, ConsoleTask, PickLists } from '../../services/api_console';
import {
  BUNDLE_ORDER, TASKS, bodiesRequested, buildRequestPath, cardCanSend, fieldErrorsOf, initialValues, loadCatalogue, loadPickLists, loadPricing, parentList,
  rememberCallsLeft, rememberedCallsLeft, sandboxServes, sendRequest, startOfBundle, taskOf,
} from '../../services/api_console';
import { CataloguePane } from './catalogue_pane';
import { ConsoleTip } from './console_tip';
import { HowItWorks } from './how_it_works';
import { RequestPane } from './request_pane';
import { ResponsePane } from './response_pane';
import './api_console.css';

// What "back" returns to, with nothing spent: the list a person opened an item from.
interface Snapshot {
  op: ConsoleOperation;
  values: Record<string, string>;
  response: ConsoleResponse | null;
  bodiesOn: boolean;
}

// A visitor who asked for less motion gets the jump without the glide.
const glide = (): ScrollBehavior => (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');

// How long a card's answer is shown again without another call: going back to a card must not cost a free search, and
// after this the data may have moved.
const CARD_ANSWER_MS = 15 * 60 * 1000;

interface Props {
  compact?: boolean;
  initialRoute?: string | null;
  initialBundle?: string | null;
}

export const ApiConsole = ({ compact = false, initialRoute = null, initialBundle = null }: Props) => {
  const { t, i18n } = useTranslation();
  const rootRef = useRef<HTMLDivElement>(null);
  const requestRef = useRef<HTMLDivElement>(null);
  const responseRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const cardAnswers = useRef(new Map<string, { at: number; values: string; response: ConsoleResponse }>());
  const cardWaiting = useRef(false);
  const [wanted, setWanted] = useState(!compact);
  const [bundle, setBundle] = useState(BUNDLE_ORDER.includes(initialBundle || '') ? (initialBundle as string) : '');
  const [catalogue, setCatalogue] = useState<ConsoleCatalogue | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [pricing, setPricing] = useState<ConsolePricing | null>(null);
  const [lists, setLists] = useState<PickLists | null>(null);
  const [selected, setSelected] = useState<ConsoleOperation | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [response, setResponse] = useState<ConsoleResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState(false);
  const [cancelled, setCancelled] = useState(false);
  const [bodiesOn, setBodiesOn] = useState(true);
  const [sandboxLeft, setSandboxLeft] = useState<number | null>(() => rememberedCallsLeft());
  const [browsing, setBrowsing] = useState(Boolean(initialRoute && !taskOf(initialRoute)) || Boolean(initialBundle));
  const [howOpen, setHowOpen] = useState(false);
  const [history, setHistory] = useState<Snapshot[]>([]);

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

  const select = useCallback((op: ConsoleOperation, scroll = false, keepHistory = false) => {
    abortRef.current?.abort();
    setSelected(op);
    setValues(initialValues(op, new Date(), lists?.oj_days));
    setResponse(null);
    setFailed(false);
    setCancelled(false);
    setSending(false);
    if (!keepHistory) setHistory([]);
    // After a choice, the form must be in view: below the cards on a laptop, a long way down on a phone.
    if (scroll && requestRef.current && requestRef.current.getBoundingClientRect().top > window.innerHeight * 0.45) {
      requestRef.current.scrollIntoView({ behavior: glide(), block: 'start' });
    }
  }, [lists]);

  const load = useCallback(() => {
    setLoadFailed(false);
    loadCatalogue().then(setCatalogue).catch(() => setLoadFailed(true));
    loadPricing().then(setPricing).catch(() => setPricing(null));
    loadPickLists().then(setLists).catch(() => setLists(null));
  }, []);

  useEffect(() => {
    // Not while the page is being pre-rendered at build time: the static page keeps its empty state.
    if (wanted && !navigator.webdriver) load();
  }, [wanted, load]);

  useEffect(() => {
    if (!catalogue || selected) return;
    const first = catalogue.operations.find((op) => op.path === initialRoute)
      || (bundle ? startOfBundle(catalogue, bundle) : undefined)
      || catalogue.operations.find((op) => op.path === TASKS[0].path)
      || catalogue.operations[0];
    if (first) select(first);
  }, [catalogue, selected, initialRoute, bundle, select]);

  // The days the Journal came out can arrive after its form opened on a day worked out from the calendar.
  useEffect(() => {
    const lastIssue = lists?.oj_days?.[0];
    if (!lastIssue || !selected?.path.endsWith('/oj/daily') || response || sending) return;
    const fromCalendar = initialValues(selected).date;
    setValues((v) => (v.date === fromCalendar ? { ...v, date: lastIssue } : v));
  }, [lists, selected, response, sending]);

  // Choosing a bundle makes no call: it narrows the list, and moves off a route that is not in it.
  const chooseBundle = useCallback((next: string) => {
    setBundle(next);
    if (!catalogue || !next || selected?.bundles.includes(next)) return;
    const start = startOfBundle(catalogue, next);
    if (start) select(start);
  }, [catalogue, selected, select]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // The answer must be in view when it arrives, wherever the page was: below on a phone, above after a long form. Measured
  // on the next frame: a card changes the form above the results, and the old height would land the page in the wrong place.
  // `arrived` is the second look: while an answer is on its way the page is short and the scroll stops early (a phone landed
  // 130px low), so once a card's answer is in, the results go right up under the header.
  const showResults = useCallback((arrived = false) => {
    requestAnimationFrame(() => {
      const el = responseRef.current;
      if (!el) return;
      const top = el.getBoundingClientRect().top;
      const header = parseFloat(window.getComputedStyle(el).scrollMarginTop) || 0;
      const tooLow = arrived ? top > header + 30 : top > window.innerHeight * 0.45;
      if (tooLow || top < header - 20) el.scrollIntoView({ behavior: glide(), block: 'start' });
    });
  }, []);

  // Every call goes through here, with what it is about passed in: a row's "Open" asks for a route not yet in the state.
  const run = useCallback(async (op: ConsoleOperation, callValues: Record<string, string>): Promise<ConsoleResponse | null> => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSending(true);
    setFailed(false);
    setCancelled(false);
    setResponse(null);
    setBodiesOn(bodiesRequested(op, callValues));
    showResults();
    try {
      const result = await sendRequest(buildRequestPath(op, callValues), controller.signal);
      if (controller.signal.aborted) return null;
      setResponse(result);
      if (result.sandboxLeft !== null) {
        setSandboxLeft(result.sandboxLeft);
        rememberCallsLeft(result.sandboxLeft);
      }
      return result;
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setFailed(true);
      return null;
    } finally {
      if (!controller.signal.aborted) setSending(false);
    }
  }, [showResults]);

  // Pressing a card runs its example, so the first press shows real results. A card seen a moment ago shows them again with
  // no call. With no free search left, or on a route that needs a key, it opens the form, which says why.
  const chooseTask = useCallback((task: ConsoleTask) => {
    const op = catalogue?.operations.find((o) => o.path === task.path);
    if (!op) return;
    if (bundle && !op.bundles.includes(bundle)) setBundle('');
    const example = initialValues(op, new Date(), lists?.oj_days);
    const asked = JSON.stringify(example);
    const seen = cardAnswers.current.get(task.id);
    if (seen && seen.values === asked && Date.now() - seen.at < CARD_ANSWER_MS) {
      select(op);
      setResponse(seen.response);
      setBodiesOn(bodiesRequested(op, example));
      showResults();
      return;
    }
    if (!cardCanSend(op, example, pricing, sandboxLeft)) {
      select(op, true);
      return;
    }
    select(op);
    cardWaiting.current = true;
    run(op, example).then((result) => {
      if (result && result.status >= 200 && result.status < 300) cardAnswers.current.set(task.id, { at: Date.now(), values: asked, response: result });
    });
  }, [catalogue, bundle, lists, pricing, sandboxLeft, select, run, showResults]);

  // A card's answer is on the page: take the second look now that the rows have their height.
  useEffect(() => {
    if (!response || !cardWaiting.current) return;
    cardWaiting.current = false;
    showResults(true);
  }, [response, showResults]);

  const send = useCallback(() => {
    cardWaiting.current = false;
    if (selected && !sending) run(selected, values);
  }, [selected, values, sending, run]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setSending(false);
    setCancelled(true);
  }, []);

  const openItem = useCallback((target: { op: ConsoleOperation; values: Record<string, string> }) => {
    if (!selected) return;
    const snapshot: Snapshot = { op: selected, values, response, bodiesOn };
    const next = { ...initialValues(target.op), ...target.values };
    select(target.op, false, true);
    setHistory((h) => [...h, snapshot]);
    setValues(next);
    if (sandboxServes(target.op.path.replace(/\{[^}]+\}/g, 'x'), pricing)) run(target.op, next);
  }, [selected, values, response, bodiesOn, pricing, select, run]);

  const goBack = useCallback(() => {
    const last = history[history.length - 1];
    if (!last) return;
    abortRef.current?.abort();
    setSending(false);
    setFailed(false);
    setCancelled(false);
    setSelected(last.op);
    setValues(last.values);
    setResponse(last.response);
    setBodiesOn(last.bodiesOn);
    setHistory(history.slice(0, -1));
  }, [history]);

  const nextPage = useCallback(() => {
    if (!selected) return;
    const next = { ...values, page: String(Number(values.page || 1) + 1) };
    setValues(next);
    run(selected, next);
  }, [selected, values, run]);

  const removeFilter = useCallback((name: string) => {
    setValues((v) => {
      const next = { ...v };
      delete next[name];
      return next;
    });
  }, []);

  const clearForm = useCallback(() => {
    if (!selected) return;
    const next: Record<string, string> = {};
    // A clear form still asks for a small page without the full texts, and keeps the id of the item it is on.
    for (const p of selected.params) {
      if (p.name === 'limit') next.limit = '5';
      if (p.name === 'include_body' && !selected.path.includes('{')) next.include_body = 'false';
      if (p.in === 'path' && values[p.name]) next[p.name] = values[p.name];
    }
    setValues(next);
  }, [selected, values]);

  const goToList = useCallback((op: ConsoleOperation) => select(op, true), [select]);
  const refine = useCallback(() => requestRef.current?.scrollIntoView({ behavior: glide(), block: 'start' }), []);

  const starters = catalogue ? TASKS.filter((task) => catalogue.operations.some((op) => op.path === task.path)) : [];
  const allowance = pricing?.sandbox;
  const fieldErrors = response ? Object.fromEntries(fieldErrorsOf(response.json).map((e) => [e.field, e.message])) : {};
  const activeTask = selected ? taskOf(selected.path) ?? null : null;
  const listParent = catalogue && selected ? parentList(catalogue, selected) ?? null : null;
  const routeCount = catalogue ? catalogue.operations.length.toLocaleString(i18n.language) : '';

  return (
    <div ref={rootRef} className={`api-console${compact ? ' api-console--compact' : ''}`}>
      <div className="api-console__intro">
        <h2 className="api-console__step">
          <span className="api-console__step-number" aria-hidden="true">1</span>
          {t('api.console.stepChoose')}
        </h2>
        <div className="api-console__allowance">
          {allowance && (
            <span className="api-console__allowance-count">
              {sandboxLeft !== null
                ? t('api.console.callsLeft', { count: sandboxLeft })
                : t('api.console.allowance', { calls: allowance.calls_per_visitor_per_day })}
              <ConsoleTip label={t('api.console.freeCallTipLabel')}>
                <p>{t('api.console.allowanceTip', { calls: allowance.calls_per_visitor_per_day, rows: allowance.max_limit })}</p>
              </ConsoleTip>
            </span>
          )}
          <button type="button" className="api-console__how" onClick={() => setHowOpen(true)}>
            <span className="mdi mdi-help-circle-outline" aria-hidden="true" /> {t('api.console.how.open')}
          </button>
          {compact && (
            <Link className="api-console__full-link" to={bundle ? `/api/try?bundle=${bundle}` : '/api/try'}>
              <span className="mdi mdi-arrow-expand" aria-hidden="true" /> {t('api.console.openFull')}
            </Link>
          )}
        </div>
      </div>

      {starters.length > 0 && (
        <div className="api-console__tasks" role="group" aria-label={t('api.console.bundleCardsLabel')}>
          {starters.map((task) => (
            <button
              key={task.id}
              type="button"
              data-task={task.id}
              className={`api-console__task${activeTask?.id === task.id ? ' api-console__task--active' : ''}`}
              aria-pressed={activeTask?.id === task.id}
              onClick={() => chooseTask(task)}
            >
              <span className={`mdi ${task.icon}`} aria-hidden="true" />
              <span className="api-console__task-words">
                <strong>{t(`api.console.tasks.${task.id}.title`)}</strong>
                <span>{t(`api.console.tasks.${task.id}.desc`)}</span>
              </span>
            </button>
          ))}
        </div>
      )}
      {starters.length > 0 && <p className="api-console__note api-console__cards-note">{t('api.console.cardsNote')}</p>}

      {loadFailed && (
        <div className="api-console__problem">
          <p>{t('api.console.loadError')}</p>
          <button type="button" className="api-console__copy" onClick={load}>{t('api.console.retry')}</button>
        </div>
      )}
      {!catalogue && !loadFailed && <p className="api-console__note api-console__loading">{t('api.console.loading')}</p>}

      {catalogue && (
        <div className="api-console__browse">
          <button type="button" className="api-console__link-button" aria-expanded={browsing} onClick={() => setBrowsing(!browsing)}>
            <span className={`mdi ${browsing ? 'mdi-chevron-down' : 'mdi-chevron-right'}`} aria-hidden="true" />
            {t('api.console.browseAll', { count: routeCount })}
          </button>
          <ConsoleTip label={t('api.console.routeTipLabel')}><p>{t('api.console.routeTip')}</p></ConsoleTip>
        </div>
      )}

      {catalogue && selected && (
        <div className={`api-console__panes${browsing ? ' api-console__panes--browsing' : ''}`}>
          {browsing && (
            <CataloguePane catalogue={catalogue} selected={selected} onSelect={(op) => select(op, true)} bundle={bundle} onBundle={chooseBundle} />
          )}
          <div ref={requestRef} className="api-console__request-anchor">
            <RequestPane
              op={selected}
              task={activeTask}
              values={values}
              fieldErrors={fieldErrors}
              pricing={pricing}
              lists={lists}
              sending={sending}
              sandboxLeft={sandboxLeft}
              listParent={listParent}
              canGoBack={history.length > 0}
              onBack={goBack}
              onChange={(name, value) => setValues((v) => {
                const next = { ...v, [name]: value };
                const either = activeTask?.eitherOr;
                if (value && either?.includes(name)) either.filter((other) => other !== name).forEach((other) => delete next[other]);
                return next;
              })}
              onExample={(name, value) => setValues((v) => {
                const next = { ...v, [name]: value };
                const either = activeTask?.eitherOr;
                if (either?.includes(name)) either.filter((other) => other !== name).forEach((other) => delete next[other]);
                activeTask?.exampleClears?.[name]?.forEach((other) => delete next[other]);
                return next;
              })}
              onClear={clearForm}
              onSend={send}
              onGoToList={goToList}
            />
          </div>
          <div ref={responseRef} className="api-console__response-anchor">
            <ResponsePane
              catalogue={catalogue}
              op={selected}
              values={values}
              response={response}
              sending={sending}
              failed={failed}
              cancelled={cancelled}
              bodiesRequested={bodiesOn}
              callsAllowed={allowance?.calls_per_visitor_per_day ?? null}
              sandboxLeft={sandboxLeft}
              maxPage={allowance?.max_page ?? null}
              pricing={pricing}
              canGoBack={history.length > 0}
              onBack={goBack}
              onTryWord={(word) => {
                if (!selected) return;
                const next = { ...values, q: word };
                setValues(next);
                run(selected, next);
              }}
              listParent={listParent}
              onCancel={cancel}
              onOpen={openItem}
              onNextPage={nextPage}
              onRemoveFilter={removeFilter}
              onGoToList={goToList}
              onRefine={refine}
            />
          </div>
        </div>
      )}

      {howOpen && <HowItWorks pricing={pricing} onClose={() => setHowOpen(false)} />}
    </div>
  );
};
