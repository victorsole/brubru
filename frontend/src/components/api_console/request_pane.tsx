// frontend/src/components/api_console/request_pane.tsx
// Step 2: the form, in plain words, with what most people need first and the rest folded away. Typing makes no call:
// a call follows the button or the Enter key, and the words beside the button say what it uses.
import { useMemo, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { ConsoleOperation, ConsoleParam, ConsolePricing, ConsoleTask, PickLists } from '../../services/api_console';
import {
  ROUTE_EXAMPLES, buildRequestPath, choicesOf, codeForTyped, dateRangeProblem, fieldHint, groupFields, hasSandbox, humanise, isItemRoute,
  missingRequired, recentWorkingDays, sandboxLimitProblem, sandboxServes, whatItDoes,
} from '../../services/api_console';
import { ConsoleTip } from './console_tip';

// Real values people can try on any route that asks for one of these.
const GENERIC_EXAMPLES: Record<string, string[]> = {
  celex: ['32016R0679', '32024R1689'],
  procedure_ref: ['2021/0106(COD)'],
  reference: ['2021/0106(COD)'],
  procedure: ['2021/0106(COD)'],
  procedure_reference: ['2021/0106(COD)'],
};

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

interface FieldProps {
  param: ConsoleParam;
  value: string;
  examples: string[];
  fixedOptions?: string[];
  lists: PickLists | null;
  showHelp: boolean;
  error?: string;
  onChange: (v: string) => void;
  onExample: (v: string) => void;
}

const Field = ({ param, value, examples, fixedOptions, lists, showHelp, error, onChange, onExample }: FieldProps) => {
  const { t, i18n } = useTranslation();
  const id = `api-console-param-${param.name}`;
  const label = t(`api.console.fields.${param.name}.label`, { defaultValue: humanise(param.name) });
  const plainHelp = t(`api.console.fields.${param.name}.help`, { defaultValue: '' });
  const placeholderText = t(`api.console.fields.${param.name}.placeholder`, { defaultValue: '' });
  const choices = choicesOf(param, lists, i18n.language);
  const options = fixedOptions || param.options;
  const [typing, setTyping] = useState(false);
  // Only once the person has finished: "Spain" is on its way to becoming ES, and that is what the help above says to do.
  const hint = typing ? null : fieldHint(param, value);

  const optionLabel = (option: string) => {
    const note = param.optionNotes?.[option];
    const named = t(`api.console.options.${option}`, { defaultValue: '' });
    if (named) return named;
    return note && !/^default/i.test(note) ? `${humanise(option)}: ${note}` : humanise(option);
  };

  // What an empty field means, in the words of the option it falls back to.
  const emptyLabel = () => {
    if (param.kind === 'boolean' && param.defaultValue) {
      return t('api.console.defaultChoice', { value: param.defaultValue === 'true' ? t('api.console.yes') : t('api.console.no') });
    }
    if (param.defaultValue) return t('api.console.defaultChoice', { value: optionLabel(param.defaultValue) });
    return t('api.console.any');
  };

  let control: ReactNode;
  if (param.name === 'include_body' && param.kind === 'boolean') {
    control = (
      <label className="api-console__check" htmlFor={id}>
        {/* Empty means the route's own default, which for most routes is to bring the text. */}
        <input id={id} type="checkbox" checked={value === 'true' || (value === '' && param.defaultValue !== 'false')} onChange={(e) => onChange(e.target.checked ? 'true' : 'false')} />
        <span>{t('api.console.includeBodyChoice')}</span>
      </label>
    );
  } else if (param.kind === 'boolean') {
    control = (
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} required={param.required}>
        <option value="">{emptyLabel()}</option>
        <option value="true">{t('api.console.yes')}</option>
        <option value="false">{t('api.console.no')}</option>
      </select>
    );
  } else if (options && !param.openList) {
    control = (
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} required={param.required}>
        <option value="">{emptyLabel()}</option>
        {options.map((o) => <option key={o} value={o}>{optionLabel(o)}</option>)}
      </select>
    );
  } else if (choices && (param.source === 'bodies' || param.source === 'families')) {
    // One at a time here; the API also takes several, separated by commas, and the tip says so.
    control = (
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t('api.console.any')}</option>
        {!choices.some((c) => c.value === value) && value && <option value={value}>{value}</option>}
        {choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
      </select>
    );
  } else {
    const type = param.kind === 'integer' || param.kind === 'number' ? 'number' : param.kind === 'date' ? 'date' : 'text';
    const listId = choices || param.openList ? `${id}-list` : undefined;
    const placeholder = placeholderText
      || (param.defaultValue ? t('api.console.defaultChoice', { value: param.defaultValue }) : undefined)
      || (param.kind === 'datetime' ? '2026-11-01' : undefined);
    control = (
      <>
        <input
          id={id}
          type={type}
          list={listId}
          step={param.kind === 'number' ? 'any' : undefined}
          min={param.kind === 'integer' ? 0 : undefined}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setTyping(true)}
          // "Belgium" becomes BE as the person leaves the field, so they see what will be sent.
          onBlur={() => {
            setTyping(false);
            if (!choices || !value) return;
            const code = codeForTyped(value, choices);
            if (code !== value) onChange(code);
          }}
          required={param.required}
          aria-invalid={error ? true : undefined}
          autoComplete="off"
        />
        {listId && (
          <datalist id={listId}>
            {(choices || (param.options || []).map((o) => ({ value: o, label: optionLabel(o) }))).map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </datalist>
        )}
      </>
    );
  }

  // Short controls sit side by side, so the form fits on a laptop without a scroll of its own.
  const shortList = Boolean(options && !param.openList && options.length <= 8);
  const half = (['date', 'datetime', 'boolean', 'integer', 'number'].includes(param.kind) || shortList) && param.name !== 'include_body' && !param.required;

  return (
    <div className={`api-console__field${half ? ' api-console__field--half' : ''}${error ? ' api-console__field--error' : ''}`} data-field={param.name}>
      <div className="api-console__field-head">
        {param.name === 'include_body' && param.kind === 'boolean'
          ? <span className="api-console__field-label">{label}</span>
          : <label htmlFor={id} className="api-console__field-label">{label}</label>}
        {param.required && <span className="api-console__required">{t('api.console.required')}</span>}
        <ConsoleTip label={t('api.console.moreAbout', { name: label })}>
          {plainHelp && <p>{plainHelp}</p>}
          {param.description && <p className="api-console-pop__source">{param.description}</p>}
          {!plainHelp && !param.description && <p>{t('api.console.noFieldHelp')}</p>}
          {(param.source === 'bodies' || param.source === 'families') && <p>{t('api.console.severalInCode')}</p>}
          <p className="api-console-pop__name">{t('api.console.nameInAddress')} <code>{param.name}</code></p>
        </ConsoleTip>
      </div>
      {control}
      {showHelp && !half && examples.length === 0 && plainHelp && <p className="api-console__help">{plainHelp}</p>}
      {examples.length > 0 && (
        <div className="api-console__examples">
          <span>{t('api.console.tryExample')}</span>
          {examples.map((example) => (
            <button key={example} type="button" className="api-console__example" aria-pressed={value === example} onClick={() => onExample(example)}>
              {example}
            </button>
          ))}
        </div>
      )}
      {hint && <p className="api-console__hint"><span className="mdi mdi-alert-circle-outline" aria-hidden="true" /> {t(`api.console.${hint}`)}</p>}
      {error && !hint && <p className="api-console__field-error">{error}</p>}
    </div>
  );
};

interface Props {
  op: ConsoleOperation;
  task: ConsoleTask | null;
  values: Record<string, string>;
  fieldErrors: Record<string, string>;
  pricing: ConsolePricing | null;
  lists: PickLists | null;
  sending: boolean;
  sandboxLeft: number | null;
  listParent: ConsoleOperation | null;
  canGoBack: boolean;
  onBack: () => void;
  onChange: (name: string, value: string) => void;
  onExample: (name: string, value: string) => void;
  onClear: () => void;
  onSend: () => void;
  onGoToList: (op: ConsoleOperation) => void;
}

export const RequestPane = ({
  op, task, values, fieldErrors, pricing, lists, sending, sandboxLeft, listParent, canGoBack, onBack, onChange, onExample, onClear, onSend, onGoToList,
}: Props) => {
  const { t } = useTranslation();
  const groups = useMemo(() => groupFields(op), [op]);
  const missing = missingRequired(op, values);
  const missingLabels = missing.map((name) => t(`api.console.fields.${name}.label`, { defaultValue: humanise(name) }));
  const requestPath = buildRequestPath(op, values);
  // Priced on the route, so an empty path parameter does not hide that a route is heavy.
  const pathOnly = op.path.replace(/\{[^}]+\}/g, 'x');
  const served = sandboxServes(pathOnly, pricing);
  const outOfCalls = sandboxLeft === 0;
  const limitProblem = sandboxLimitProblem(values, pricing);
  const rangeProblem = dateRangeProblem(values);
  const canSend = hasSandbox() && served && missing.length === 0 && !sending && !outOfCalls && !limitProblem && !rangeProblem;
  const item = isItemRoute(op);
  const moreCount = groups.more.length + groups.developer.length;
  const movedOpen = [...groups.more, ...groups.developer].some((p) => Boolean(values[p.name]) && !['limit', 'include_body'].includes(p.name));
  const developerOpen = groups.developer.some((p) => Boolean(values[p.name]));
  const taskWords = task ? t(`api.console.tasks.${task.id}.title`) : '';

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (canSend) onSend();
  };

  const field = (param: ConsoleParam, showHelp: boolean) => {
    const dates = param.name === 'date' && op.path.endsWith('/oj/daily') ? recentWorkingDays(4) : [];
    const examples = ROUTE_EXAMPLES[op.path]?.[param.name] || task?.examples?.[param.name] || (dates.length ? dates : GENERIC_EXAMPLES[param.name]) || [];
    return (
      <Field
        key={`${param.in}-${param.name}`}
        param={param}
        value={values[param.name] || ''}
        examples={examples}
        fixedOptions={task?.options?.[param.name]}
        lists={lists}
        showHelp={showHelp}
        error={fieldErrors[param.name]}
        onChange={(v) => onChange(param.name, v)}
        onExample={(v) => onExample(param.name, v)}
      />
    );
  };

  return (
    <div className="api-console__pane api-console__pane--request">
      <h2 className="api-console__step">
        <span className="api-console__step-number" aria-hidden="true">2</span>
        {item ? t('api.console.stepItem') : t('api.console.stepNarrow')}
      </h2>
      {canGoBack && (
        <button type="button" className="api-console__link-button" onClick={onBack}>
          <span className="mdi mdi-arrow-left" aria-hidden="true" /> {t('api.console.backToResults')}
        </button>
      )}
      <h3 className="api-console__summary">{taskWords || op.summary || op.path}</h3>
      {task && <p className="api-console__task-desc">{t(`api.console.tasks.${task.id}.desc`)}</p>}
      {!task && whatItDoes(op) && <p className="api-console__task-desc">{whatItDoes(op)}</p>}
      {op.deprecated && <span className="api-console__badge">{t('api.console.deprecated')}</span>}

      {item && !canGoBack && (
        <div className="api-console__item-help">
          <p>{t('api.console.itemNeedsId')}</p>
          {listParent && (
            <button type="button" className="api-console__link-button" onClick={() => onGoToList(listParent)}>
              <span className="mdi mdi-format-list-bulleted" aria-hidden="true" /> {t('api.console.goToList')}
            </button>
          )}
        </div>
      )}

      <form onSubmit={submit} className="api-console__form">
        {op.params.length === 0 && <p className="api-console__note">{t('api.console.noParameters')}</p>}
        {op.params.length > 0 && !item && missing.length === 0 && groups.main.every((p) => !p.required) && (
          <p className="api-console__note">{t('api.console.allOptional')}</p>
        )}
        <div className="api-console__fields">{groups.main.map((param) => field(param, true))}</div>
        {moreCount > 0 && (
          <details className="api-console__more" open={movedOpen || undefined}>
            <summary>{t('api.console.moreFilters', { count: moreCount })}</summary>
            <div className="api-console__fields">{groups.more.map((param) => field(param, false))}</div>
            {groups.developer.length > 0 && (
              <details className="api-console__more api-console__more--developer" open={developerOpen || undefined}>
                <summary>
                  {t('api.console.developerFilters', { count: groups.developer.length })}
                  <ConsoleTip label={t('api.console.developerFiltersTipLabel')}><p>{t('api.console.developerFiltersTip')}</p></ConsoleTip>
                </summary>
                <div className="api-console__fields">{groups.developer.map((param) => field(param, false))}</div>
              </details>
            )}
          </details>
        )}

        <div className="api-console__send">
          <div className="api-console__send-row">
            <button type="submit" className="api-console__send-button" disabled={!canSend}>
              <span className={`mdi ${sending ? 'mdi-loading mdi-spin' : item ? 'mdi-open-in-app' : 'mdi-magnify'}`} aria-hidden="true" />
              {sending ? t('api.console.sending') : item ? t('api.console.sendItem') : t('api.console.send')}
            </button>
            <button type="button" className="api-console__link-button" onClick={onClear}>{t('api.console.clear')}</button>
          </div>
          <div className="api-console__cost">
            {!hasSandbox() && <p>{t('api.console.sandboxUnavailable')}</p>}
            {hasSandbox() && !served && (
              <p className="api-console__needs-key">
                {t('api.console.needsKey')}{' '}
                <Link to="/api#your-keys">{t('api.console.getKey')}</Link>{' '}
                <a href="mailto:hello@beresol.eu?subject=Brubru%20API%20pricing">{t('api.console.askPricing')}</a>
              </p>
            )}
            {hasSandbox() && served && outOfCalls && (
              <p className="api-console__needs-key">{t('api.console.capVisitor')} <Link to="/api#your-keys">{t('api.console.getKey')}</Link>{' · '}<a href="mailto:hello@beresol.eu?subject=Brubru%20API%20pricing">{t('api.console.askPricing')}</a></p>
            )}
            {hasSandbox() && served && !outOfCalls && missing.length > 0 && <p>{t('api.console.fillRequired', { names: missingLabels.join(', ') })}</p>}
            {hasSandbox() && served && !outOfCalls && limitProblem && <p className="api-console__needs-key">{t(`api.console.tooMany.${limitProblem.name}`, { top: limitProblem.top })}</p>}
            {hasSandbox() && served && !outOfCalls && rangeProblem && <p className="api-console__needs-key">{t('api.console.datesReversed')}</p>}
            {hasSandbox() && served && !outOfCalls && missing.length === 0 && !limitProblem && !rangeProblem && (
              <p>
                {t('api.console.usesOneCall')}{' '}
                <ConsoleTip label={t('api.console.freeCallTipLabel')}>
                  <p>{t('api.console.freeHere')}</p>
                </ConsoleTip>
              </p>
            )}
          </div>
        </div>
      </form>

      <details className="api-console__about">
        <summary>{t('api.console.about')}</summary>
        <div className="api-console__address">
          <span className="api-console__method">GET</span>
          <code className="api-console__path" data-route-path={op.path}>{op.path}</code>
        </div>
        <p className="api-console__address-note">{t('api.console.addressNote')}</p>
        <div className="api-console__url"><code>{requestPath}</code></div>
        {op.description && <Description text={op.description} />}
      </details>
    </div>
  );
};
