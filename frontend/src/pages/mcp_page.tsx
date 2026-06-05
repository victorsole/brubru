// frontend/src/pages/mcp_page.tsx
//
// /mcp — public landing page for the Brubru MCP server. Sibling of /api.
//
// Sections:
//   - Hero (what MCP is + the install button)
//   - Quickstart (3-step recipe)
//   - Install blocks (Claude Desktop / Cursor / Cline / Continue / Claude Cowork / VS Code)
//   - ChatGPT custom-GPT walkthrough
//   - Gemini setup
//   - Tool catalogue
//   - Pricing reminder
//   - Links to /api (mint key) and /billing (top up)
//
// Backend endpoint: POST https://brubru.beresol.eu/api/mcp (JSON-RPC 2.0)

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/use_auth';
import '../components/api/api_keys.css';
import './policy_pages.css';
import './api_page.css';   // reuse the eyebrow / hero / sidebar layout
import './mcp_page.css';

const TOOLS = [
  { name: 'ask_brubru',            scope: 'read:knowledge', costEur: 0.005 },
  { name: 'search_eu_legislation', scope: 'read:laws',      costEur: 0.005 },
  { name: 'search_knowledge_guides', scope: 'read:knowledge', costEur: 0.005 },
  { name: 'get_procedure_status',  scope: 'read:procedures', costEur: 0.005 },
  { name: 'get_calendar_events',   scope: 'read:calendar',  costEur: 0.005 },
  { name: 'search_eprs',           scope: 'read:knowledge', costEur: 0.005 },
] as const;

// Production URL — used in the copy-paste blocks. Dev pointers stay
// implicit (devs run locally).
const PROD_URL = 'https://brubru.beresol.eu/api/mcp';

const CONFIG_JSON_CLAUDE = (key = 'brubru_live_YOUR_KEY') =>
  JSON.stringify(
    {
      mcpServers: {
        brubru: {
          url: PROD_URL,
          headers: { Authorization: `Bearer ${key}` },
        },
      },
    },
    null,
    2,
  );

const CONFIG_JSON_CURSOR = (key = 'brubru_live_YOUR_KEY') =>
  JSON.stringify(
    {
      mcpServers: {
        brubru: {
          url: PROD_URL,
          env: { AUTHORIZATION: `Bearer ${key}` },
        },
      },
    },
    null,
    2,
  );

const CURL_EXAMPLE = (key = 'brubru_live_YOUR_KEY') =>
  `curl -X POST ${PROD_URL} \\\n  -H "Authorization: Bearer ${key}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`;

function CopyableBlock({ value, label }: { value: string; label: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked — ignore */
    }
  };

  return (
    <div className="mcp-codeblock">
      <div className="mcp-codeblock__header">
        <span className="mcp-codeblock__label">{label}</span>
        <button
          type="button"
          className="mcp-codeblock__copy"
          onClick={handleCopy}
          aria-label="Copy"
        >
          <span className="mdi mdi-content-copy" aria-hidden="true" />
          {copied ? t('mcp.copyBtn.copied') : t('mcp.copyBtn.copy')}
        </button>
      </div>
      <pre className="mcp-codeblock__pre">
        <code>{value}</code>
      </pre>
    </div>
  );
}

export const McpPage = () => {
  const { t } = useTranslation();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const [activeSection, setActiveSection] = useState('what');

  const navItems = [
    { id: 'what',        label: t('mcp.nav.what') },
    { id: 'quickstart',  label: t('mcp.nav.quickstart') },
    { id: 'claude',      label: t('mcp.nav.claude') },
    { id: 'cursor',      label: t('mcp.nav.cursor') },
    { id: 'cline',       label: t('mcp.nav.cline') },
    { id: 'continue',    label: t('mcp.nav.continue') },
    { id: 'vscode',      label: t('mcp.nav.vscode') },
    { id: 'chatgpt',     label: t('mcp.nav.chatgpt') },
    { id: 'gemini',      label: t('mcp.nav.gemini') },
    { id: 'tools',       label: t('mcp.nav.tools') },
    { id: 'pricing',     label: t('mcp.nav.pricing') },
  ];

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActiveSection(entry.target.id);
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0 },
    );
    for (const item of navItems) {
      const el = document.getElementById(item.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="policy-page api-page mcp-page">
      <div className="api-page__layout">
        {/* ---- Sticky sidebar ---- */}
        <aside className="api-page__sidebar">
          <div className="api-page__sidebar-inner">
            <h6 className="api-page__sidebar-title">{t('mcp.sidebar.onThisPage')}</h6>
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
          <div className="api-page__eyebrow">{t('mcp.eyebrow')}</div>
          <h1 className="policy-page__title">
            {t('mcp.titlePre')} <span className="api-page__accent">{t('mcp.titleAccent')}</span>.
          </h1>
          <p className="api-page__lede">{t('mcp.lede')}</p>

          <div className="api-page__cta-row">
            {isAuthenticated ? (
              <>
                <Link to="/api" className="api-page__cta api-page__cta--primary">
                  <span className="mdi mdi-key-plus" aria-hidden="true" /> {t('mcp.cta.mintKey')}
                </Link>
                <Link to="/billing" className="api-page__cta api-page__cta--secondary">
                  <span className="mdi mdi-wallet-outline" aria-hidden="true" /> {t('mcp.cta.topUp')}
                </Link>
              </>
            ) : (
              <Link to="/login" className="api-page__cta api-page__cta--primary">
                <span className="mdi mdi-login" aria-hidden="true" /> {t('mcp.cta.signIn')}
              </Link>
            )}
            <a className="api-page__cta api-page__cta--secondary" href="https://modelcontextprotocol.io/" target="_blank" rel="noreferrer">
              <span className="mdi mdi-open-in-new" aria-hidden="true" /> {t('mcp.cta.protocolSpec')}
            </a>
          </div>

          {/* ===== What is MCP ===== */}
          <section className="policy-page__section" id="what">
            <h2>{t('mcp.what.title')}</h2>
            <p>{t('mcp.what.body1')}</p>
            <p>{t('mcp.what.body2')}</p>
          </section>

          {/* ===== Quickstart ===== */}
          <section className="policy-page__section" id="quickstart">
            <h2>{t('mcp.quickstart.title')}</h2>
            <div className="api-page__steps">
              <div className="api-page__step">
                <span className="api-page__step-num">1</span>
                <div>
                  <strong>{t('mcp.quickstart.step1Title')}</strong>
                  <p>{t('mcp.quickstart.step1')} <Link to="/api">brubru.beresol.eu/api</Link>.</p>
                </div>
              </div>
              <div className="api-page__step">
                <span className="api-page__step-num">2</span>
                <div>
                  <strong>{t('mcp.quickstart.step2Title')}</strong>
                  <p>{t('mcp.quickstart.step2')} <Link to="/billing">brubru.beresol.eu/billing</Link>. {t('mcp.quickstart.step2b')}</p>
                </div>
              </div>
              <div className="api-page__step">
                <span className="api-page__step-num">3</span>
                <div>
                  <strong>{t('mcp.quickstart.step3Title')}</strong>
                  <p>{t('mcp.quickstart.step3')}</p>
                </div>
              </div>
            </div>
            <CopyableBlock value={CURL_EXAMPLE()} label={t('mcp.quickstart.curlLabel') as string} />
          </section>

          {/* ===== Claude Desktop ===== */}
          <section className="policy-page__section" id="claude">
            <h2>{t('mcp.claude.title')}</h2>
            <p>{t('mcp.claude.body')}</p>
            <ol className="mcp-list">
              <li>{t('mcp.claude.s1')}</li>
              <li>{t('mcp.claude.s2')}</li>
              <li>{t('mcp.claude.s3')}</li>
              <li>{t('mcp.claude.s4')}</li>
            </ol>
            <CopyableBlock value={CONFIG_JSON_CLAUDE()} label="claude_desktop_config.json" />
          </section>

          {/* ===== Cursor ===== */}
          <section className="policy-page__section" id="cursor">
            <h2>{t('mcp.cursor.title')}</h2>
            <p>{t('mcp.cursor.body')}</p>
            <ol className="mcp-list">
              <li>{t('mcp.cursor.s1')}</li>
              <li>{t('mcp.cursor.s2')}</li>
              <li>{t('mcp.cursor.s3')}</li>
            </ol>
            <CopyableBlock value={CONFIG_JSON_CURSOR()} label=".cursor/mcp.json" />
          </section>

          {/* ===== Cline ===== */}
          <section className="policy-page__section" id="cline">
            <h2>{t('mcp.cline.title')}</h2>
            <p>{t('mcp.cline.body')}</p>
            <ol className="mcp-list">
              <li>{t('mcp.cline.s1')}</li>
              <li>{t('mcp.cline.s2')}</li>
              <li>{t('mcp.cline.s3')}</li>
            </ol>
            <CopyableBlock value={CONFIG_JSON_CLAUDE()} label="cline_mcp_settings.json" />
          </section>

          {/* ===== Continue ===== */}
          <section className="policy-page__section" id="continue">
            <h2>{t('mcp.continue.title')}</h2>
            <p>{t('mcp.continue.body')}</p>
            <ol className="mcp-list">
              <li>{t('mcp.continue.s1')}</li>
              <li>{t('mcp.continue.s2')}</li>
            </ol>
            <CopyableBlock value={CONFIG_JSON_CLAUDE()} label="~/.continue/config.json" />
          </section>

          {/* ===== VS Code ===== */}
          <section className="policy-page__section" id="vscode">
            <h2>{t('mcp.vscode.title')}</h2>
            <p>{t('mcp.vscode.body')}</p>
            <ol className="mcp-list">
              <li>{t('mcp.vscode.s1')}</li>
              <li>{t('mcp.vscode.s2')}</li>
              <li>{t('mcp.vscode.s3')}</li>
            </ol>
            <CopyableBlock value={CONFIG_JSON_CLAUDE()} label=".vscode/mcp.json" />
          </section>

          {/* ===== ChatGPT ===== */}
          <section className="policy-page__section" id="chatgpt">
            <h2>{t('mcp.chatgpt.title')}</h2>
            <p>{t('mcp.chatgpt.body')}</p>
            <p>{t('mcp.chatgpt.bodyMoaning')}</p>
            <ol className="mcp-list">
              <li>{t('mcp.chatgpt.s1')}</li>
              <li>{t('mcp.chatgpt.s2')}</li>
              <li>{t('mcp.chatgpt.s3')}</li>
              <li>{t('mcp.chatgpt.s4')}</li>
            </ol>
            <CopyableBlock
              value={`${PROD_URL}\n(use Bearer auth in the action's Authentication settings)`}
              label={t('mcp.chatgpt.actionUrl') as string}
            />
          </section>

          {/* ===== Gemini ===== */}
          <section className="policy-page__section" id="gemini">
            <h2>{t('mcp.gemini.title')}</h2>
            <p>{t('mcp.gemini.body')}</p>
            <p>{t('mcp.gemini.bodySecondary')}</p>
          </section>

          {/* ===== Tool catalogue ===== */}
          <section className="policy-page__section" id="tools">
            <h2>{t('mcp.tools.title')}</h2>
            <p>{t('mcp.tools.lede')}</p>
            <div className="mcp-tools-grid">
              {TOOLS.map((tool) => (
                <article key={tool.name} className="mcp-tool-card">
                  <code className="mcp-tool-card__name">{tool.name}</code>
                  <p className="mcp-tool-card__desc">{t(`mcp.tools.descs.${tool.name}`)}</p>
                  <div className="mcp-tool-card__meta">
                    <span className="mcp-tool-card__scope">
                      <span className="mdi mdi-lock-outline" aria-hidden="true" /> {tool.scope}
                    </span>
                    <span className="mcp-tool-card__cost">€{tool.costEur.toFixed(3)}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>

          {/* ===== Pricing reminder ===== */}
          <section className="policy-page__section" id="pricing">
            <h2>{t('mcp.pricing.title')}</h2>
            <p>{t('mcp.pricing.body')}</p>
            <ul className="mcp-bullets">
              <li>{t('mcp.pricing.b1')}</li>
              <li>{t('mcp.pricing.b2')}</li>
              <li>{t('mcp.pricing.b3')}</li>
              <li>{t('mcp.pricing.b4')}</li>
            </ul>
            <div className="api-page__cta-row" style={{ marginTop: '1.5rem' }}>
              <Link to="/api" className="api-page__cta api-page__cta--primary">
                <span className="mdi mdi-key-plus" aria-hidden="true" /> {t('mcp.cta.mintKey')}
              </Link>
              <Link to="/billing" className="api-page__cta api-page__cta--secondary">
                <span className="mdi mdi-wallet-outline" aria-hidden="true" /> {t('mcp.cta.topUp')}
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default McpPage;
