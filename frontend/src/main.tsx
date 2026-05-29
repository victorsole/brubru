import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import './styles/globals.css'
import './styles/fonts.css'

const root = document.getElementById('root')!;
const app = (
  <StrictMode>
    <App />
  </StrictMode>
);

// Always createRoot, never hydrateRoot. The prerendered HTML (homepage and
// public routes) is for crawlers/SEO -- they read the served markup and do
// not need hydration. Hydrating it on the client mismatched on every load
// (i18n language detection, auth-conditional rendering, dynamic content) and
// threw React #418, which then aborted the deep-link effects on app routes.
// createRoot renders the real route fresh from the served HTML; SEO content
// is unchanged, and there is no hydration mismatch to throw.
createRoot(root).render(app);
