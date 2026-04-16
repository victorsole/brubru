// frontend/src/pages/api_page.tsx
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './policy_pages.css';
import './api_page.css';

export const ApiPage = () => {
  const { t } = useTranslation();
  const [activeSection, setActiveSection] = useState('endpoints');

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

  const navItems = [
    { id: 'endpoints',      label: t('api.sections.whatYouGet') },
    { id: 'quickstart',     label: t('api.sections.quickstart') },
    { id: 'authentication', label: t('api.sections.authentication') },
    { id: 'envelope',       label: t('api.sections.envelope') },
    { id: 'examples',       label: t('api.sections.examples') },
    { id: 'pricing',        label: t('api.sections.pricing') },
    { id: 'errors',         label: t('api.sections.errors') },
    { id: 'start-building', label: t('api.sections.startBuilding') },
  ];

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0 }
    );
    for (const item of navItems) {
      const el = document.getElementById(item.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="policy-page api-page">
      <div className="api-page__layout">

        {/* ---- Sticky sidebar ---- */}
        <aside className="api-page__sidebar">
          <div className="api-page__sidebar-inner">
            <h6 className="api-page__sidebar-title">{t('api.sidebar.onThisPage')}</h6>
            <nav>
              <ul className="api-page__sidebar-nav">
                {navItems.map((item) => (
                  <li key={item.id}>
                    <a
                      href={`#${item.id}`}
                      className={`api-page__sidebar-link${activeSection === item.id ? ' api-page__sidebar-link--active' : ''}`}
                    >
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </aside>

        {/* ---- Main content ---- */}
        <div className="api-page__main">

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

          {/* Endpoints */}
          <section className="policy-page__section" id="endpoints">
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

          {/* Quickstart */}
          <section className="policy-page__section" id="quickstart">
            <h2>{t('api.sections.quickstart')}</h2>
            <p>{t('api.quickstart.intro')}</p>
            <div className="api-page__steps">
              <div className="api-page__step">
                <span className="api-page__step-num">1</span>
                <div>
                  <strong>{t('api.quickstart.step1Title')}</strong>
                  <p>{t('api.quickstart.step1')}</p>
                </div>
              </div>
              <div className="api-page__step">
                <span className="api-page__step-num">2</span>
                <div>
                  <strong>{t('api.quickstart.step2Title')}</strong>
                  <pre className="api-page__pre"><code>{`curl -H "Authorization: Bearer brubru_live_..." \\
  "https://brubru.beresol.eu/api/v1/laws?q=artificial+intelligence&limit=5"`}</code></pre>
                </div>
              </div>
              <div className="api-page__step">
                <span className="api-page__step-num">3</span>
                <div>
                  <strong>{t('api.quickstart.step3Title')}</strong>
                  <p>{t('api.quickstart.step3')}</p>
                </div>
              </div>
            </div>
          </section>

          {/* Authentication */}
          <section className="policy-page__section" id="authentication">
            <h2>{t('api.sections.authentication')}</h2>
            <p>{t('api.auth.description')}</p>
            <pre className="api-page__pre"><code>{`curl -H "Authorization: Bearer brubru_live_..." \\
  "https://brubru.beresol.eu/api/v1/laws?policy_area=Transport&limit=10"`}</code></pre>
            <p className="api-page__note">{t('api.auth.note')}</p>
          </section>

          {/* Response envelope */}
          <section className="policy-page__section" id="envelope">
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

          {/* Code examples */}
          <section className="policy-page__section" id="examples">
            <h2>{t('api.sections.examples')}</h2>
            <p>{t('api.examples.intro')}</p>

            <h3>Python</h3>
            <pre className="api-page__pre"><code>{`import requests

API_KEY = "brubru_live_..."
BASE    = "https://brubru.beresol.eu/api/v1"

# Search laws by keyword
resp = requests.get(f"{BASE}/laws", params={"q": "artificial intelligence", "limit": 5},
                    headers={"Authorization": f"Bearer {API_KEY}"})
for law in resp.json()["data"]:
    print(f'{law["celex"]}  {law["title"][:80]}')`}</code></pre>

            <h3>JavaScript / Node.js</h3>
            <pre className="api-page__pre"><code>{`const API_KEY = "brubru_live_...";
const BASE    = "https://brubru.beresol.eu/api/v1";

const res = await fetch(\`\${BASE}/laws?q=artificial+intelligence&limit=5\`, {
  headers: { Authorization: \`Bearer \${API_KEY}\` },
});
const { data } = await res.json();
data.forEach(law => console.log(law.celex, law.title));`}</code></pre>

            <h3>{t('api.examples.mcpTitle')}</h3>
            <p>{t('api.examples.mcpDescription')}</p>
            <pre className="api-page__pre"><code>{`// MCP server configuration
{
  "mcpServers": {
    "brubru": {
      "type": "sse",
      "url": "https://brubru.beresol.eu/api/mcp",
      "headers": { "Authorization": "Bearer brubru_live_..." }
    }
  }
}`}</code></pre>
          </section>

          {/* Pricing */}
          <section className="policy-page__section" id="pricing">
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

          {/* Errors */}
          <section className="policy-page__section" id="errors">
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

          {/* Start building */}
          <section className="policy-page__section" id="start-building">
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
    </div>
  );
};

export default ApiPage;
