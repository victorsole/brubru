// frontend/src/components/api_console/request_pane.tsx
// A form built from the route's declared parameters. Only the Send button makes a call: not loading the page,
// not typing, not pressing Enter.
import type { FormEvent, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ConsoleOperation, ConsoleParam, ConsolePricing } from '../../services/api_console';
import { buildRequestPath, hasSandbox, missingRequired, priceOf, sandboxServes } from '../../services/api_console';

interface Props {
  op: ConsoleOperation;
  values: Record<string, string>;
  pricing: ConsolePricing | null;
  sending: boolean;
  sandboxLeft: number | null;
  onChange: (name: string, value: string) => void;
  onSend: () => void;
}

// The spec's descriptions are short Markdown: bold headings, code, lists. Built as React nodes, never as raw HTML.
function inline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean).map((part, i) => {
    if (part.startsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    return part;
  });
}

function Description({ text }: { text: string }) {
  const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  return (
    <>
      {blocks.map((block, i) => {
        const lines = block.split('\n').map((l) => l.trim());
        const list = lines.filter((l) => l.startsWith('- '));
        if (list.length === lines.length) {
          return <ul key={i}>{list.map((l, j) => <li key={j}>{inline(l.slice(2))}</li>)}</ul>;
        }
        return <p key={i}>{lines.map((l, j) => <span key={j}>{j > 0 && <br />}{inline(l)}</span>)}</p>;
      })}
    </>
  );
}

const Field = ({ param, value, onChange }: { param: ConsoleParam; value: string; onChange: (v: string) => void }) => {
  const { t } = useTranslation();
  const id = `api-console-param-${param.name}`;
  const placeholder = param.defaultValue ? t('api.console.defaultValue', { value: param.defaultValue }) : undefined;
  let control: ReactNode;
  if (param.kind === 'enum' || param.kind === 'boolean') {
    const options = param.kind === 'boolean' ? ['true', 'false'] : param.options || [];
    control = (
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} required={param.required}>
        <option value="">{placeholder || t('api.console.any')}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  } else {
    const type = param.kind === 'integer' || param.kind === 'number' ? 'number' : param.kind === 'date' ? 'date' : 'text';
    control = (
      <input
        id={id}
        type={type}
        step={param.kind === 'number' ? 'any' : undefined}
        value={value}
        placeholder={placeholder || (param.kind === 'datetime' ? 'YYYY-MM-DDTHH:MM:SSZ' : undefined)}
        onChange={(e) => onChange(e.target.value)}
        required={param.required}
        autoComplete="off"
      />
    );
  }
  return (
    <div className="api-console__field">
      <label htmlFor={id}>
        <code>{param.name}</code>
        {param.required && <span className="api-console__required">{t('api.console.required')}</span>}
      </label>
      {control}
      {param.description && <p className="api-console__help">{param.description}</p>}
    </div>
  );
};

export const RequestPane = ({ op, values, pricing, sending, sandboxLeft, onChange, onSend }: Props) => {
  const { t, i18n } = useTranslation();
  const missing = missingRequired(op, values);
  const requestPath = buildRequestPath(op, values);
  // Priced on the route, so an empty path parameter does not hide that a route is heavy.
  const pathOnly = op.path.replace(/\{[^}]+\}/g, 'x');
  const served = sandboxServes(pathOnly, pricing);
  const price = priceOf(pathOnly, pricing);
  const priceText = price === null ? null : price.toLocaleString(i18n.language, { minimumFractionDigits: 3, maximumFractionDigits: 6 });
  const outOfCalls = sandboxLeft === 0;
  const canSend = hasSandbox() && served && missing.length === 0 && !sending && !outOfCalls;

  const refuseSubmit = (e: FormEvent) => e.preventDefault();

  return (
    <div className="api-console__pane api-console__pane--request">
      <div className="api-console__heading">
        <span className="api-console__method">GET</span>
        <code className="api-console__path">{op.path}</code>
      </div>
      {op.deprecated && <span className="api-console__badge">{t('api.console.deprecated')}</span>}
      {op.summary && <h3 className="api-console__summary">{op.summary}</h3>}
      {op.description && (
        <details className="api-console__about">
          <summary>{t('api.console.about')}</summary>
          <Description text={op.description} />
        </details>
      )}

      <form onSubmit={refuseSubmit} className="api-console__form">
        {op.params.length === 0 && <p className="api-console__note">{t('api.console.noParameters')}</p>}
        {op.params.map((param) => (
          <Field key={`${param.in}-${param.name}`} param={param} value={values[param.name] || ''} onChange={(v) => onChange(param.name, v)} />
        ))}
      </form>

      <div className="api-console__send">
        <div className="api-console__url"><code>{requestPath}</code></div>
        <button type="button" className="api-console__send-button" disabled={!canSend} onClick={onSend}>
          <span className={`mdi ${sending ? 'mdi-loading mdi-spin' : 'mdi-send'}`} aria-hidden="true" />
          {sending ? t('api.console.sending') : t('api.console.send')}
        </button>
        <div className="api-console__cost">
          {!hasSandbox() && <p>{t('api.console.sandboxUnavailable')}</p>}
          {hasSandbox() && !served && (
            <p>
              {priceText ? t('api.console.needsKeyPriced', { cost: priceText }) : t('api.console.needsKey')}{' '}
              <Link to="/api#your-keys">{t('api.console.getKey')}</Link>
            </p>
          )}
          {hasSandbox() && served && missing.length > 0 && <p>{t('api.console.fillRequired', { names: missing.join(', ') })}</p>}
          {hasSandbox() && served && missing.length === 0 && (
            <p>
              {t('api.console.freeHere')}{priceText ? ` ${t('api.console.ownKeyPrice', { cost: priceText })}` : ''}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
