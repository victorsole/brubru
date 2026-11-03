// frontend/src/components/api_console/response_pane.tsx
// What came back: status, time, rows, and on each row the five datapoints every Brubru item carries.
// Text from the API is only ever shown as text; a link opens only if it is http(s).
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ConsoleResponse } from '../../services/api_console';
import { curlSnippet, isList, pythonSnippet, reasonOf, rowsOf, safeHttpUrl, shortenedJson, totalOf } from '../../services/api_console';

const ROWS_SHOWN = 5;

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

const RowCard = ({ row, bodiesRequested }: { row: Record<string, any>; bodiesRequested: boolean }) => {
  const { t, i18n } = useTranslation();
  const title = row.title || row.name || row.reference || row.celex || row.id;
  const url = safeHttpUrl(row.public_url);
  const empty = <span className="api-console__empty">{t('api.console.emptyValue')}</span>;
  const bodyValue = (value: unknown) => {
    if (typeof value === 'string' && value.length > 0) return t('api.console.characters', { count: value.length, formatted: value.length.toLocaleString(i18n.language) });
    return bodiesRequested ? empty : <span className="api-console__not-requested">{t('api.console.notRequested')}</span>;
  };
  const date = (value: unknown) => (typeof value === 'string' && value ? <code>{value}</code> : empty);
  return (
    <article className="api-console__row">
      {title ? <h4>{String(title).slice(0, 220)}</h4> : null}
      <dl>
        <div className="api-console__point">
          <dt><code>public_url</code></dt>
          <dd>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{url}</a> : empty}</dd>
        </div>
        <div className="api-console__point">
          <dt><code>body_txt</code> <code>body_html</code></dt>
          <dd>
            <span>{bodyValue(row.body_txt)}</span>{' / '}<span>{bodyValue(row.body_html)}</span>
            {typeof row.body_txt === 'string' && row.body_txt && (
              <p className="api-console__snippet">{row.body_txt.slice(0, 240)}{row.body_txt.length > 240 ? '...' : ''}</p>
            )}
          </dd>
        </div>
        <div className="api-console__point"><dt><code>document_date</code></dt><dd>{date(row.document_date)}</dd></div>
        <div className="api-console__point"><dt><code>creation_date</code></dt><dd>{date(row.creation_date)}</dd></div>
        <div className="api-console__point"><dt><code>updated_date</code></dt><dd>{date(row.updated_date)}</dd></div>
      </dl>
    </article>
  );
};

interface Props {
  response: ConsoleResponse | null;
  sending: boolean;
  failed: boolean;
  bodiesRequested: boolean;
}

export const ResponsePane = ({ response, sending, failed, bodiesRequested }: Props) => {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>('rows');

  const rows = useMemo(() => (response ? rowsOf(response.json) : []), [response]);
  const hasPoints = rows.some((r) => r && ('public_url' in r || 'updated_date' in r || 'document_date' in r));
  const ok = Boolean(response && response.status >= 200 && response.status < 300);
  const list = response ? isList(response.json) : false;
  const total = response ? totalOf(response.json) : null;
  const reason = response ? reasonOf(response.json) : { code: '', message: '' };

  useEffect(() => {
    if (response) setTab(ok && hasPoints ? 'rows' : ok ? 'json' : 'rows');
  }, [response, ok, hasPoints]);

  const capped = reason.code === 'sandbox_ip_capped' || reason.code === 'sandbox_global_capped';
  const needsKey = capped || reason.code.startsWith('sandbox_');
  const refusalText =
    reason.code === 'sandbox_ip_capped' ? t('api.console.capVisitor')
      : reason.code === 'sandbox_global_capped' ? t('api.console.capPool')
        : reason.message || t('api.console.failedStatus', { status: response?.status });

  return (
    <div className="api-console__pane api-console__pane--response" aria-live="polite">
      <h3 className="api-console__pane-title">{t('api.console.response')}</h3>

      {!response && !sending && !failed && <p className="api-console__note">{t('api.console.nothingSent')}</p>}
      {sending && <p className="api-console__note">{t('api.console.sending')}</p>}
      {failed && !sending && <p className="api-console__problem">{t('api.console.networkError')}</p>}

      {response && !sending && (
        <>
          <div className="api-console__facts">
            <span className={`api-console__status api-console__status--${ok ? 'ok' : 'bad'}`}>{response.status}</span>
            <span>{t('api.console.milliseconds', { ms: response.ms.toLocaleString(i18n.language) })}</span>
            {ok && total !== null && (
              <span>{t('api.console.rowsFound', { count: total, formatted: total.toLocaleString(i18n.language) })}</span>
            )}
            {response.sandboxLeft !== null && (
              <span>{t('api.console.callsLeft', { count: response.sandboxLeft })}</span>
            )}
          </div>

          {!ok && (
            <div className="api-console__problem">
              <p>{refusalText}</p>
              {reason.code && <p><code>{reason.code}</code></p>}
              {needsKey && <p><Link to="/api#your-keys">{t('api.console.getKey')}</Link></p>}
            </div>
          )}

          {ok && list && rows.length === 0 && <p className="api-console__note">{t('api.console.zeroRows')}</p>}

          <div className="api-console__tabs" role="tablist">
            {ok && hasPoints && (
              <button type="button" role="tab" aria-selected={tab === 'rows'} onClick={() => setTab('rows')}>{t('api.console.tabRows')}</button>
            )}
            <button type="button" role="tab" aria-selected={tab === 'json'} onClick={() => setTab('json')}>{t('api.console.tabJson')}</button>
            <button type="button" role="tab" aria-selected={tab === 'code'} onClick={() => setTab('code')}>{t('api.console.tabCode')}</button>
          </div>

          {tab === 'rows' && ok && hasPoints && (
            <div className="api-console__rows">
              <p className="api-console__note">{t('api.console.datapointsNote')}</p>
              {rows.slice(0, ROWS_SHOWN).map((row, i) => <RowCard key={i} row={row} bodiesRequested={bodiesRequested} />)}
              {rows.length > ROWS_SHOWN && <p className="api-console__note">{t('api.console.moreInJson', { shown: ROWS_SHOWN, count: rows.length })}</p>}
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
              <div className="api-console__code-head"><strong>curl</strong><CopyButton text={curlSnippet(response.url)} /></div>
              <pre>{curlSnippet(response.url)}</pre>
              <div className="api-console__code-head"><strong>Python</strong><CopyButton text={pythonSnippet(response.url)} /></div>
              <pre>{pythonSnippet(response.url)}</pre>
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
