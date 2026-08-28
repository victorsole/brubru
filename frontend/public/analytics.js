/*
 * Brubru consent-gated analytics loader.
 *
 * ONE file for every Brubru surface: the React SPA, the static canon and API
 * pages, the deep-dives, and the Catalan legislation landing page. Nothing that
 * sets a cookie or records a session may load before the visitor accepts.
 *
 * Before this existed, the Contentsquare tag sat raw in <head> on every page and
 * fired on first paint, while the React cookie banner wrote localStorage that
 * nothing read. The banner was decorative. See .claude/skills/clarity/SKILL.md.
 *
 * Two modes:
 *   - React surfaces set window.__BRUBRU_CONSENT_UI__ = 'react' BEFORE loading
 *     this file, so the existing React banner owns the UI and this file only
 *     listens for its accept event.
 *   - Static pages leave that unset, so this file renders its own small banner.
 *
 * The Clarity project ID is public by design (it ships in the page). The API
 * token is NOT, and lives only in the shell env for MCP and Data Export.
 */
(function () {
  'use strict';

  var CONSENT_KEY = 'brubru_cookie_consent';
  var ACCEPT_EVENT = 'brubru-consent-accepted';
  var DECLINE_EVENT = 'brubru-consent-declined';

  var CONTENTSQUARE_TAG = 'https://t.contentsquare.net/uxa/f2e32d332b6a1.js';

  // Brubru's own Clarity project, created 28 Aug 2026. It briefly reused
  // Beresol's project (y8zjfhmyoa); that is superseded, and with it the caveat
  // that every read had to be filtered by URL host to stop the two sites
  // blending. Brubru's data now stands alone.
  // The ID is public by design: it ships in the page. The API token is not,
  // and lives only in the shell env.
  var CLARITY_PROJECT_ID = 'y9d0jw5ety';

  var loaded = false;

  function readConsent() {
    try {
      return window.localStorage.getItem(CONSENT_KEY);
    } catch (e) {
      // Private mode, or storage blocked. Treat as no consent given.
      return null;
    }
  }

  function writeConsent(value) {
    try {
      window.localStorage.setItem(CONSENT_KEY, value);
    } catch (e) {
      /* nothing we can do; the visitor simply gets asked again */
    }
  }

  function loadContentsquare() {
    var s = document.createElement('script');
    s.src = CONTENTSQUARE_TAG;
    s.defer = true;
    document.head.appendChild(s);
  }

  function loadClarity() {
    if (!CLARITY_PROJECT_ID) return;
    (function (c, l, a, r, i, t, y) {
      c[a] = c[a] || function () { (c[a].q = c[a].q || []).push(arguments); };
      t = l.createElement(r); t.async = 1;
      t.src = 'https://www.clarity.ms/tag/' + i;
      y = l.getElementsByTagName(r)[0];
      y.parentNode.insertBefore(t, y);
    })(window, document, 'clarity', 'script', CLARITY_PROJECT_ID);
    // Consent Mode belt and braces: we only get here post-acceptance, but say so
    // explicitly so Clarity releases cookies even if the project has Consent
    // Mode switched on.
    if (window.clarity) window.clarity('consent');
  }

  function loadTrackers() {
    if (loaded) return;
    loaded = true;
    loadContentsquare();
    loadClarity();
  }

  /* ---------- the built-in banner, for pages with no React ---------- */

  var COPY = {
    en: { text: 'We use cookies to understand how this site is used. Analytics only loads if you accept.',
          accept: 'Accept', decline: 'Decline', more: 'Cookie policy' },
    es: { text: 'Usamos cookies para entender como se usa este sitio. La analitica solo se carga si aceptas.',
          accept: 'Aceptar', decline: 'Rechazar', more: 'Politica de cookies' },
    ca: { text: "Fem servir galetes per entendre com s'utilitza aquest lloc. L'analitica nomes es carrega si hi acceptes.",
          accept: 'Accepta', decline: 'Rebutja', more: 'Politica de galetes' },
    fr: { text: 'Nous utilisons des cookies pour comprendre comment ce site est utilise. Les analyses ne se chargent que si vous acceptez.',
          accept: 'Accepter', decline: 'Refuser', more: 'Politique de cookies' },
    it: { text: 'Usiamo i cookie per capire come viene usato questo sito. Le analisi si caricano solo se accetti.',
          accept: 'Accetta', decline: 'Rifiuta', more: 'Politica sui cookie' },
    nl: { text: 'We gebruiken cookies om te begrijpen hoe deze site wordt gebruikt. Analyse laadt alleen als je accepteert.',
          accept: 'Accepteren', decline: 'Weigeren', more: 'Cookiebeleid' }
  };

  function copy() {
    var lang = (document.documentElement.getAttribute('lang') || 'en').slice(0, 2).toLowerCase();
    return COPY[lang] || COPY.en;
  }

  function renderBanner() {
    var c = copy();
    var bar = document.createElement('div');
    bar.setAttribute('role', 'dialog');
    bar.setAttribute('aria-live', 'polite');
    bar.setAttribute('aria-label', c.more);
    bar.style.cssText = [
      'position:fixed', 'left:0', 'right:0', 'bottom:0', 'z-index:99999',
      'background:#ffffff', 'border-top:1px solid #d1d5db',
      'box-shadow:0 -2px 12px rgba(0,0,0,0.08)',
      'padding:1rem 1.25rem', 'display:flex', 'flex-wrap:wrap',
      'align-items:center', 'gap:0.75rem', 'justify-content:center',
      "font-family:'Segoe UI',Roboto,-apple-system,sans-serif",
      'font-size:0.9rem', 'color:#1f2937'
    ].join(';');

    var msg = document.createElement('span');
    msg.textContent = c.text;
    msg.style.cssText = 'flex:1 1 280px;min-width:220px;line-height:1.5';

    var link = document.createElement('a');
    link.href = '/cookies';
    link.textContent = c.more;
    link.style.cssText = 'color:#003399;text-decoration:underline;white-space:nowrap';

    function button(label, primary) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = label;
      b.style.cssText = [
        'padding:0.5rem 1.1rem', 'border-radius:8px', 'cursor:pointer',
        'font-size:0.9rem', 'font-weight:600', 'white-space:nowrap',
        primary ? 'background:#003399' : 'background:#ffffff',
        primary ? 'color:#ffffff' : 'color:#374151',
        primary ? 'border:1px solid #003399' : 'border:1px solid #d1d5db'
      ].join(';');
      return b;
    }

    var accept = button(c.accept, true);
    var decline = button(c.decline, false);

    accept.addEventListener('click', function () {
      writeConsent('accepted');
      bar.remove();
      loadTrackers();
    });
    decline.addEventListener('click', function () {
      writeConsent('declined');
      bar.remove();
    });

    bar.appendChild(msg);
    bar.appendChild(link);
    bar.appendChild(decline);
    bar.appendChild(accept);
    document.body.appendChild(bar);
  }

  /* ---------- wiring ---------- */

  function start() {
    var consent = readConsent();

    if (consent === 'accepted') { loadTrackers(); return; }
    if (consent === 'declined') { return; }

    // No decision yet. React surfaces own their own banner; static pages get ours.
    if (window.__BRUBRU_CONSENT_UI__ !== 'react') {
      if (document.body) renderBanner();
      else document.addEventListener('DOMContentLoaded', renderBanner);
    }
  }

  // Either banner signals through the same events, so the loader is shared.
  window.addEventListener(ACCEPT_EVENT, loadTrackers);
  window.addEventListener(DECLINE_EVENT, function () { /* stay dormant */ });

  start();
})();
