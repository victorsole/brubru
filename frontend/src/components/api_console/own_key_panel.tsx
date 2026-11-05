// frontend/src/components/api_console/own_key_panel.tsx
// Using your own API key here instead of the free trial. The key is typed once and goes only to the Brubru API: it stays out
// of the address, the code examples and anything the page records. Pressing "Use this key" makes no call, so a key is only
// ever checked by a search the person chose to make.
import { useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { keyLooksWhole } from '../../services/api_console';

interface Props {
  onUse: (key: string, remember: boolean) => void;
  onCancel: () => void;
}

export const OwnKeyPanel = ({ onUse, onCancel }: Props) => {
  const { t } = useTranslation();
  const [typed, setTyped] = useState('');
  const [remember, setRemember] = useState(false);
  const [problem, setProblem] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const key = typed.trim();
    if (!keyLooksWhole(key)) {
      setProblem(true);
      return;
    }
    onUse(key, remember);
  };

  return (
    <form className="api-console__own-key" onSubmit={submit} autoComplete="off">
      <label htmlFor="api-console-own-key" className="api-console__field-label">{t('api.console.ownKey.label')}</label>
      <div className="api-console__own-key-row">
        <input
          id="api-console-own-key"
          type="password"
          value={typed}
          placeholder={t('api.console.ownKey.placeholder')}
          autoComplete="off"
          spellCheck={false}
          data-clarity-mask="true"
          aria-invalid={problem}
          aria-describedby={problem ? 'api-console-own-key-problem' : undefined}
          // Focus goes here when the panel opens, as it was asked for.
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus
          onChange={(e) => {
            setTyped(e.target.value);
            setProblem(false);
          }}
        />
        <button type="submit" className="api-console__copy">{t('api.console.ownKey.use')}</button>
        <button type="button" className="api-console__link-button" onClick={onCancel}>{t('api.console.ownKey.cancel')}</button>
      </div>
      {problem && <p id="api-console-own-key-problem" className="api-console__field-error">{t('api.console.ownKey.tooShort')}</p>}
      <label className="api-console__own-key-remember">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
        {' '}{t('api.console.ownKey.remember')}
      </label>
      <p className="api-console__note">{t('api.console.ownKey.note')}</p>
      <p className="api-console__note">
        {t('api.console.ownKey.noKey')}{' '}
        <Link to="/api#your-keys">{t('api.console.getKey')}</Link>{' · '}
        <a href="mailto:hello@beresol.eu?subject=Brubru%20API%20pricing">{t('api.console.askPricing')}</a>
      </p>
    </form>
  );
};
