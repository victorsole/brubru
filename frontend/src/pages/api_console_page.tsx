// frontend/src/pages/api_console_page.tsx
// /api/console: the full-screen API Console. /api keeps the pitch, the keys and the docs, and shows the same console as a panel.
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ApiConsole } from '../components/api_console/api_console';
import './policy_pages.css';
import './api_page.css';

export const ApiConsolePage = () => {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  return (
    <div className="api-console-page">
      <div className="api-console-page__head">
        <div>
          <div className="api-page__eyebrow">{t('api.eyebrow')}</div>
          <h1 className="policy-page__title">{t('api.console.title')}</h1>
          <p className="api-console-page__lede">{t('api.console.lede')}</p>
        </div>
        <div className="api-console-page__links">
          <Link to="/api"><span className="mdi mdi-arrow-left" aria-hidden="true" /> {t('api.console.backToApi')}</Link>
          <a href="/api/docs"><span className="mdi mdi-book-open-variant" aria-hidden="true" /> {t('api.cta.reference')}</a>
        </div>
      </div>
      <ApiConsole initialRoute={params.get('route')} initialBundle={params.get('bundle')} />
    </div>
  );
};
