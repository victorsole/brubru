import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { hydrateRoot } from 'react-dom/client'
import { App } from './App'
import './styles/globals.css'
import './styles/fonts.css'

const root = document.getElementById('root')!;
const app = (
  <StrictMode>
    <App />
  </StrictMode>
);

if (root.innerHTML.trim().length > 0) {
  hydrateRoot(root, app);
} else {
  createRoot(root).render(app);
}
