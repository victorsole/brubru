// frontend/src/pages/api_page.tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/use_auth';
import { ApiKeysPanel } from '../components/api/api_keys_panel';
import '../components/api/api_keys.css';
import './policy_pages.css';
import './api_page.css';

export const ApiPage = () => {
  const { t } = useTranslation();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const [activeSection, setActiveSection] = useState('your-keys');

  // Public landing surface — only GET endpoints are listed here, all from the
  // v2 (institution-based) API, which is the only public surface we document.
  // POST endpoints (resolve-*) are documented in /api/docs for partners; we
  // intentionally do not surface them on this page.
  const endpoints = [
    { m: 'GET',  p: '/api/v2/proprietary/brussels-lobbies',                          k: 'brusselsLobbies' },
    { m: 'GET',  p: '/api/v2/legislative/eur-lex/laws',                              k: 'laws' },
    { m: 'GET',  p: '/api/v2/legislative/oeil/procedures',                           k: 'procedures' },
    { m: 'GET',  p: '/api/v2/proprietary/catalan',                                   k: 'catalanTranslations' },
    { m: 'GET',  p: '/api/v2/commission/consultations/by-initiative/{id}/feedback',  k: 'consultations' },
    { m: 'GET',  p: '/api/v2/commission/commissioners/{name}/agenda',                k: 'commissioners' },
    { m: 'GET',  p: '/api/v2/predictions/{procedure_ref}/outcome',                   k: 'predictions' },
    { m: 'GET',  p: '/api/v2/proprietary/tender-docs/templates/{template_id}',       k: 'tenderDocs' },
    { m: 'GET',  p: '/api/v2/open-data/eurostat-series/{dataset_code}',              k: 'eurostatSeries' },
    { m: 'GET',  p: '/api/v2/eeas/news',                                             k: 'eeas' },
    { m: 'GET',  p: '/api/v2/legislative/eur-lex/laws/{celex}/recital-article-map',  k: 'recitalMap' },
    { m: 'GET',  p: '/api/v2/legislative/eur-lex/laws/{celex}/defined-terms',        k: 'definedTerms' },
    { m: 'GET',  p: '/api/v2/extract',                                               k: 'extract' },
    { m: 'GET',  p: '/api/v2/social/posts',                                          k: 'social' },
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
    { id: 'your-keys',      label: t('api.keys.title') },
    { id: 'endpoints',      label: t('api.sections.whatYouGet') },
    { id: 'quickstart',     label: t('api.sections.quickstart') },
    { id: 'authentication', label: t('api.sections.authentication') },
    { id: 'envelope',       label: t('api.sections.envelope') },
    { id: 'examples',       label: t('api.sections.examples') },
    { id: 'client-libraries', label: t('api.sections.clientLibraries') },
    { id: 'full-docs',      label: t('api.sections.fullDocs') },
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
            <Link to="/mcp" className="api-page__cta api-page__cta--secondary">
              <span className="mdi mdi-connection" /> {t('api.cta.mcp')}
            </Link>
            <a className="api-page__cta api-page__cta--secondary" href="/subscription">
              <span className="mdi mdi-rocket-launch" /> {t('api.cta.trial')}
            </a>
            <a className="api-page__cta api-page__cta--secondary" href="mailto:hello@beresol.eu?subject=Brubru%20API%20access">
              <span className="mdi mdi-email" /> {t('api.cta.contact')}
            </a>
          </div>

          {/* Your API keys (Phase A — 21 May 2026)
              Logged-in users see ApiKeysPanel; logged-out users see a sign-in CTA. */}
          {isAuthenticated ? (
            <ApiKeysPanel />
          ) : (
            <section className="api-keys-signin-cta" id="your-keys" style={{ margin: '3rem 0' }}>
              <span className="mdi mdi-key-outline api-keys-signin-cta__icon" aria-hidden="true" />
              <h2 className="api-keys-signin-cta__title">{t('api.keys.signedOut.title')}</h2>
              <p className="api-keys-signin-cta__body">{t('api.keys.signedOut.body')}</p>
              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
                <Link to="/login" className="api-keys-btn api-keys-btn--primary">
                  <span className="mdi mdi-login" aria-hidden="true" /> {t('api.keys.signedOut.cta')}
                </Link>
                <Link to="/signup" className="api-keys-btn api-keys-btn--secondary">
                  {t('api.keys.signedOut.signup')}
                </Link>
              </div>
            </section>
          )}

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
  "https://brubru.beresol.eu/api/v2/legislative/eur-lex/laws?q=victims+rights+directive&limit=5"`}</code></pre>
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
  "https://brubru.beresol.eu/api/v2/legislative/eur-lex/laws?policy_area=Trade&limit=10"`}</code></pre>
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
BASE    = "https://brubru.beresol.eu/api/v2"

# Search laws by keyword
resp = requests.get(f"{BASE}/legislative/eur-lex/laws",
                    params={"q": "victims rights directive", "limit": 5},
                    headers={"Authorization": f"Bearer {API_KEY}"})
for law in resp.json()["data"]:
    print(f'{law["celex"]}  {law["title"][:80]}')

# Or browse the moat: ranked Brussels-based lobby orgs with their own news
resp = requests.get(f"{BASE}/proprietary/brussels-lobbies",
                    params={"has_news": "true", "order": "recent", "limit": 10},
                    headers={"Authorization": f"Bearer {API_KEY}"})
for org in resp.json()["data"]:
    print(org["name"], "—", org["org_type"], "—", org["last_item_date"])`}</code></pre>

            <h3>JavaScript / Node.js</h3>
            <pre className="api-page__pre"><code>{`const API_KEY = "brubru_live_...";
const BASE    = "https://brubru.beresol.eu/api/v2";

const res = await fetch(\`\${BASE}/legislative/eur-lex/laws?q=victims+rights+directive&limit=5\`, {
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
      "url": "https://brubru-production.up.railway.app/api/mcp",
      "headers": { "Authorization": "Bearer brubru_live_..." }
    }
  }
}`}</code></pre>
          </section>

          {/* Client libraries (preview: official Python wrappers in development) */}
          <section className="policy-page__section" id="client-libraries">
            <h2>{t('api.sections.clientLibraries')}</h2>
            <p>{t('api.libraries.lede')}</p>
            <p className="api-page__note">
              {t('api.libraries.openSource')}{' '}
              <a href="https://github.com/Beresol-BV/brubru-EU-scraper-library">github.com/Beresol-BV/brubru-EU-scraper-library</a>
            </p>
            <pre className="api-page__pre"><code>{`pip install brubru
pip install "brubru-eurovoc[local]"   # [local] adds the classifier model`}</code></pre>

            <h3>
              <code>brubru</code>{' '}
              <span className="api-page__badge">{t('api.libraries.status')}</span>
            </h3>
            <p>{t('api.libraries.brubruDesc')}</p>
            <pre className="api-page__pre"><code>{`import brubru

bru = brubru.Client(api_key="brubru_live_...")

# Extract structured items from any EU URL, tagged with EuroVoc
items = bru.extract("https://cinea.ec.europa.eu/news_en", classify=True)

# Recent posts from a mapped entity (MEP, Commissioner, institution, journalist)
posts = bru.social.posts(entity_type="commissioner", platform="x")`}</code></pre>

            <h3>
              <code>eurovoc</code>{' '}
              <span className="api-page__badge">{t('api.libraries.status')}</span>
            </h3>
            <p>{t('api.libraries.eurovocDesc')}</p>
            <pre className="api-page__pre"><code>{`import eurovoc

eurovoc.classify("Markets in crypto-assets regulation")
# -> [{"descriptor": "financial instrument", "mt": "2426",
#      "domain": "24", "score": 0.88}, ...]

# or run it through the hosted classifier over the API
eurovoc.classify("...", backend="brubru", api_key="brubru_live_...")`}</code></pre>
          </section>

          {/* Full documentation CTA (replaces pricing section) */}
          <section className="policy-page__section" id="full-docs">
            <h2>{t('api.sections.fullDocs')}</h2>
            <p>{t('api.fullDocs.lede')}</p>
            <div className="api-page__cta-row">
              <a className="api-page__cta api-page__cta--primary" href="/api/docs/">
                <span className="mdi mdi-book-open-variant" /> {t('api.cta.openFullDocs')}
              </a>
              <a className="api-page__cta api-page__cta--secondary" href="mailto:hello@beresol.eu?subject=Brubru%20API%20access">
                <span className="mdi mdi-email" /> {t('api.cta.contact')}
              </a>
            </div>
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
              <a className="api-page__cta api-page__cta--secondary" href="/health">
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
