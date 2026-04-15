// frontend/src/pages/api_page.tsx
import { useTranslation } from 'react-i18next';
import './policy_pages.css';
import './api_page.css';

export const ApiPage = () => {
  const { t } = useTranslation();

  const endpoints = [
    { m: 'GET',  p: '/api/v1/laws',                                           k: 'laws' },
    { m: 'GET',  p: '/api/v1/procedures',                                     k: 'procedures' },
    { m: 'GET',  p: '/api/v1/consultations/by-initiative/{id}/feedback',      k: 'consultations' },
    { m: 'GET',  p: '/api/v1/commissioners/{name}/agenda',                    k: 'commissioners' },
    { m: 'GET',  p: '/api/v1/legal-text/{celex}/recital-article-map',         k: 'recitalMap' },
    { m: 'GET',  p: '/api/v1/legal-text/{celex}/defined-terms',               k: 'definedTerms' },
    { m: 'POST', p: '/api/v1/legal-text/resolve-references',                  k: 'resolveRefs' },
    { m: 'POST', p: '/api/v1/legal-text/resolve-aliases',                     k: 'resolveAliases' },
  ];

  const errorRows: Array<{ code: string; key: string }> = [
    { code: '200', key: 'ok' },
    { code: '401', key: 'unauthorized' },
    { code: '403', key: 'forbidden' },
    { code: '404', key: 'notFound' },
    { code: '422', key: 'invalidQuery' },
    { code: '429', key: 'rateLimited' },
    { code: '502', key: 'upstream' },
  ];

  return (
    <div className="policy-page api-page">
      <div className="policy-page__container">

        <div className="api-page__eyebrow">{t('api.eyebrow')}</div>
        <h1 className="policy-page__title">
          {t('api.titlePre')} <span className="api-page__accent">{t('api.titleAccent')}</span>.
        </h1>
        <p className="api-page__lede">{t('api.lede')}</p>

        <div className="api-page__cta-row">
          <a className="api-page__cta api-page__cta--primary" href="/api/docs">
            <span className="mdi mdi-book-open-variant" /> {t('api.cta.reference')}
          </a>
          <a className="api-page__cta api-page__cta--secondary" href="/subscription">
            <span className="mdi mdi-rocket-launch" /> {t('api.cta.trial')}
          </a>
          <a className="api-page__cta api-page__cta--secondary" href="mailto:hello@beresol.eu?subject=Brubru%20API%20access">
            <span className="mdi mdi-email" /> {t('api.cta.contact')}
          </a>
        </div>

        <section className="policy-page__section">
          <h2>{t('api.sections.whatYouGet')}</h2>
          <div className="api-page__grid">
            {endpoints.map((e) => (
              <div className="api-page__card" key={e.p}>
                <div className="api-page__card-head">
                  <span className={`api-page__method api-page__method--${e.m.toLowerCase()}`}>{e.m}</span>
                  <code>{e.p}</code>
                </div>
                <p>{t(`api.endpoints.${e.k}`)}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="policy-page__section">
          <h2>{t('api.sections.authentication')}</h2>
          <p>{t('api.auth.description')}</p>
          <pre className="api-page__pre"><code>{`curl -H "Authorization: Bearer brubru_live_..." \\
  "https://brubru.beresol.eu/api/v1/laws?policy_area=Transport&limit=10"`}</code></pre>
          <p className="api-page__note">{t('api.auth.note')}</p>
        </section>

        <section className="policy-page__section">
          <h2>{t('api.sections.envelope')}</h2>
          <p>{t('api.envelope.description')}</p>
          <pre className="api-page__pre"><code>{`{
  "total": 139,
  "returned": 20,
  "pages": 7,
  "page": 1,
  "limit": 20,
  "has_more": true,
  "next_page": 2,
  "remaining_pages": 6,
  "coverage_complete": true,
  "published_from": "2026-01-01",
  "published_to": "2026-01-31",
  "published_end": "2026-01-31",
  "detail_level": "Full",
  "data": [ ... ],
  "meta": {
    "source": "brubru.beresol.eu",
    "powered_by": "Brubru",
    "fetched_at": "2026-04-15T12:34:56Z"
  }
}`}</code></pre>
        </section>

        <section className="policy-page__section">
          <h2>{t('api.sections.pricing')}</h2>
          <div className="api-page__table-wrap">
            <table className="api-page__table">
              <thead>
                <tr>
                  <th>{t('api.pricing.plan')}</th>
                  <th>{t('api.pricing.monthly')}</th>
                  <th>{t('api.pricing.api')}</th>
                  <th>{t('api.pricing.rateLimit')}</th>
                  <th>{t('api.pricing.chatbot')}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{t('api.pricing.starter')}</td>
                  <td>&euro;39</td><td>&mdash;</td><td>&mdash;</td><td>{t('api.pricing.yes')}</td>
                </tr>
                <tr>
                  <td>{t('api.pricing.advocate')}</td>
                  <td>&euro;59</td><td>&mdash;</td><td>&mdash;</td><td>{t('api.pricing.yes')}</td>
                </tr>
                <tr>
                  <td><strong>{t('api.pricing.professional')}</strong></td>
                  <td><strong>&euro;99 ({t('api.pricing.annual', { price: '\u20AC67' })})</strong></td>
                  <td><strong>{t('api.pricing.included')}</strong></td>
                  <td><strong>{t('api.pricing.rate', { n: 60 })}</strong></td>
                  <td>{t('api.pricing.included')}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            {t('api.pricing.note')} <a href="mailto:hello@beresol.eu">{t('api.cta.contact')}</a>.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>{t('api.sections.errors')}</h2>
          <div className="api-page__table-wrap">
            <table className="api-page__table">
              <thead>
                <tr>
                  <th>{t('api.errors.code')}</th>
                  <th>{t('api.errors.meaning')}</th>
                </tr>
              </thead>
              <tbody>
                {errorRows.map((row) => (
                  <tr key={row.code}>
                    <td>{row.code}</td>
                    <td>{t(`api.errors.${row.key}`)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="api-page__note">{t('api.errors.envelopeNote')}</p>
        </section>

        <section className="policy-page__section">
          <h2>{t('api.sections.startBuilding')}</h2>
          <div className="api-page__cta-row">
            <a className="api-page__cta api-page__cta--primary" href="/api/docs">
              <span className="mdi mdi-book-open-variant" /> {t('api.cta.openRef')}
            </a>
            <a className="api-page__cta api-page__cta--secondary" href="/api/v1/ping">
              <span className="mdi mdi-heart-pulse" /> {t('api.cta.ping')}
            </a>
          </div>
        </section>

      </div>
    </div>
  );
};

export default ApiPage;
