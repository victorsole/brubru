// frontend/src/pages/subprocessors_page.tsx
import { Link } from 'react-router-dom';
import './policy_pages.css';

export const SubprocessorsPage = () => {
  return (
    <div className="policy-page">
      <div className="policy-page__container">
        <h1 className="policy-page__title">Subprocessors</h1>

        <section className="policy-page__section">
          <p className="policy-page__intro">
            <strong>Last Updated:</strong> November 2025
          </p>
          <p>
            Beresol BV ("we," "us," "our") uses third-party service providers ("subprocessors")
            to help us deliver Brubru. These subprocessors may process personal data on our behalf
            in accordance with our <Link to="/privacy" className="policy-page__link">Privacy Policy</Link>.
          </p>
          <p>
            This page lists all subprocessors we currently use, their purpose, and data location.
            We maintain Data Processing Agreements (DPAs) with all subprocessors to ensure GDPR compliance.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>1. Infrastructure & Hosting</h2>

          <div className="policy-page__subprocessor">
            <h3>Supabase, Inc.</h3>
            <ul>
              <li><strong>Purpose:</strong> Database hosting, authentication, file storage</li>
              <li><strong>Data Processed:</strong> User account data, chat history, amendments, uploaded documents, authentication tokens</li>
              <li><strong>Data Location:</strong> European Union (primary), United States (backup)</li>
              <li><strong>Website:</strong> <a href="https://supabase.com" target="_blank" rel="noopener noreferrer" className="policy-page__link">supabase.com</a></li>
              <li><strong>DPA:</strong> Standard Contractual Clauses (SCCs) in place</li>
              <li><strong>Privacy Policy:</strong> <a href="https://supabase.com/privacy" target="_blank" rel="noopener noreferrer" className="policy-page__link">supabase.com/privacy</a></li>
            </ul>
          </div>

          <div className="policy-page__subprocessor">
            <h3>IONOS SE</h3>
            <ul>
              <li><strong>Purpose:</strong> Backend application hosting (Docker containers, Nginx)</li>
              <li><strong>Data Processed:</strong> Application logs, temporary processing data, cached content</li>
              <li><strong>Data Location:</strong> European Union (France, Germany)</li>
              <li><strong>Website:</strong> <a href="https://www.ionos.fr" target="_blank" rel="noopener noreferrer" className="policy-page__link">ionos.fr</a></li>
              <li><strong>DPA:</strong> Standard DPA under GDPR</li>
              <li><strong>Privacy Policy:</strong> <a href="https://www.ionos.fr/terms-gtc/privacy-policy/" target="_blank" rel="noopener noreferrer" className="policy-page__link">ionos.fr/privacy-policy</a></li>
            </ul>
          </div>

          <div className="policy-page__subprocessor">
            <h3>Vercel Inc.</h3>
            <ul>
              <li><strong>Purpose:</strong> Frontend hosting, CDN, static asset delivery</li>
              <li><strong>Data Processed:</strong> IP addresses, browser data, page requests (minimal personal data)</li>
              <li><strong>Data Location:</strong> Global (CDN edge locations), primary US</li>
              <li><strong>Website:</strong> <a href="https://vercel.com" target="_blank" rel="noopener noreferrer" className="policy-page__link">vercel.com</a></li>
              <li><strong>DPA:</strong> SCCs available upon request</li>
              <li><strong>Privacy Policy:</strong> <a href="https://vercel.com/legal/privacy-policy" target="_blank" rel="noopener noreferrer" className="policy-page__link">vercel.com/legal/privacy-policy</a></li>
            </ul>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>2. AI & Machine Learning Services</h2>

          <div className="policy-page__subprocessor">
            <h3>Anthropic PBC</h3>
            <ul>
              <li><strong>Purpose:</strong> AI chat responses using Claude models (Sonnet 4, Opus 4)</li>
              <li><strong>Data Processed:</strong> Chat messages, user prompts, context from uploaded documents</li>
              <li><strong>Data Location:</strong> United States</li>
              <li><strong>Data Retention:</strong> Prompts and outputs are not used to train Anthropic's models (per our enterprise agreement)</li>
              <li><strong>Website:</strong> <a href="https://www.anthropic.com" target="_blank" rel="noopener noreferrer" className="policy-page__link">anthropic.com</a></li>
              <li><strong>DPA:</strong> Enterprise DPA with SCCs</li>
              <li><strong>Privacy Policy:</strong> <a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noopener noreferrer" className="policy-page__link">anthropic.com/legal/privacy</a></li>
            </ul>
          </div>

          <div className="policy-page__subprocessor">
            <h3>OpenAI, L.L.C.</h3>
            <ul>
              <li><strong>Purpose:</strong> Backup AI service (GPT-4, GPT-3.5-turbo) when Claude is unavailable</li>
              <li><strong>Data Processed:</strong> Chat messages, user prompts</li>
              <li><strong>Data Location:</strong> United States</li>
              <li><strong>Data Retention:</strong> 30 days (OpenAI's policy for API users)</li>
              <li><strong>Website:</strong> <a href="https://openai.com" target="_blank" rel="noopener noreferrer" className="policy-page__link">openai.com</a></li>
              <li><strong>DPA:</strong> OpenAI's Business Terms with SCCs</li>
              <li><strong>Privacy Policy:</strong> <a href="https://openai.com/policies/privacy-policy" target="_blank" rel="noopener noreferrer" className="policy-page__link">openai.com/policies/privacy-policy</a></li>
            </ul>
          </div>

          <div className="policy-page__subprocessor">
            <h3>Hugging Face, Inc.</h3>
            <ul>
              <li><strong>Purpose:</strong> Specialized legal AI models (Saul-7B), multilingual embeddings (BAAI/bge-m3)</li>
              <li><strong>Data Processed:</strong> Text for embedding generation, legal document analysis</li>
              <li><strong>Data Location:</strong> United States, European Union (varies by model)</li>
              <li><strong>Website:</strong> <a href="https://huggingface.co" target="_blank" rel="noopener noreferrer" className="policy-page__link">huggingface.co</a></li>
              <li><strong>DPA:</strong> Inference API DPA</li>
              <li><strong>Privacy Policy:</strong> <a href="https://huggingface.co/privacy" target="_blank" rel="noopener noreferrer" className="policy-page__link">huggingface.co/privacy</a></li>
            </ul>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>3. Payment Processing</h2>

          <div className="policy-page__subprocessor">
            <h3>Stripe, Inc.</h3>
            <ul>
              <li><strong>Purpose:</strong> Subscription billing, payment processing, invoicing</li>
              <li><strong>Data Processed:</strong> Email, billing address, payment method (credit card), transaction history</li>
              <li><strong>Data Location:</strong> United States, European Union</li>
              <li><strong>Note:</strong> We do not store credit card numbers; Stripe handles all payment data securely</li>
              <li><strong>Website:</strong> <a href="https://stripe.com" target="_blank" rel="noopener noreferrer" className="policy-page__link">stripe.com</a></li>
              <li><strong>DPA:</strong> Stripe Data Processing Agreement</li>
              <li><strong>Privacy Policy:</strong> <a href="https://stripe.com/privacy" target="_blank" rel="noopener noreferrer" className="policy-page__link">stripe.com/privacy</a></li>
            </ul>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>4. Authentication Services</h2>

          <div className="policy-page__subprocessor">
            <h3>Google LLC (OAuth)</h3>
            <ul>
              <li><strong>Purpose:</strong> Social login via Google OAuth</li>
              <li><strong>Data Processed:</strong> Email, name, profile picture (if you choose to sign in with Google)</li>
              <li><strong>Data Location:</strong> United States</li>
              <li><strong>Website:</strong> <a href="https://google.com" target="_blank" rel="noopener noreferrer" className="policy-page__link">google.com</a></li>
              <li><strong>Privacy Policy:</strong> <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" className="policy-page__link">policies.google.com/privacy</a></li>
            </ul>
          </div>

          <div className="policy-page__subprocessor">
            <h3>LinkedIn Corporation (OAuth)</h3>
            <ul>
              <li><strong>Purpose:</strong> Professional social login via LinkedIn OAuth</li>
              <li><strong>Data Processed:</strong> Email, name, profile information (if you choose to sign in with LinkedIn)</li>
              <li><strong>Data Location:</strong> United States</li>
              <li><strong>Website:</strong> <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer" className="policy-page__link">linkedin.com</a></li>
              <li><strong>Privacy Policy:</strong> <a href="https://www.linkedin.com/legal/privacy-policy" target="_blank" rel="noopener noreferrer" className="policy-page__link">linkedin.com/legal/privacy-policy</a></li>
            </ul>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>5. Optional Services (If Enabled)</h2>

          <div className="policy-page__subprocessor">
            <h3>Google Cloud Platform (Translation API)</h3>
            <ul>
              <li><strong>Purpose:</strong> Optional translation of chat messages and content to EU languages</li>
              <li><strong>Data Processed:</strong> Text to be translated</li>
              <li><strong>Data Location:</strong> European Union (when using EU endpoints), United States</li>
              <li><strong>Status:</strong> Optional, not currently active</li>
              <li><strong>Website:</strong> <a href="https://cloud.google.com" target="_blank" rel="noopener noreferrer" className="policy-page__link">cloud.google.com</a></li>
              <li><strong>Privacy Policy:</strong> <a href="https://cloud.google.com/terms/cloud-privacy-notice" target="_blank" rel="noopener noreferrer" className="policy-page__link">cloud.google.com/privacy</a></li>
            </ul>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>6. Monitoring & Error Tracking (Future)</h2>
          <p className="policy-page__note">
            The following services may be implemented in the future. We will update this page
            and notify users before activating them.
          </p>

          <div className="policy-page__subprocessor">
            <h3>Sentry (Not Currently Active)</h3>
            <ul>
              <li><strong>Purpose:</strong> Error tracking and performance monitoring</li>
              <li><strong>Data Processed:</strong> Error logs, stack traces, browser metadata</li>
              <li><strong>Data Location:</strong> United States</li>
              <li><strong>Status:</strong> Not currently active</li>
            </ul>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>7. Data Transfer Safeguards</h2>
          <p>
            When personal data is transferred to subprocessors outside the European Economic Area (EEA),
            we ensure adequate protection through:
          </p>
          <ul>
            <li>
              <strong>Standard Contractual Clauses (SCCs):</strong> EU-approved model contracts
              for data transfers to third countries
            </li>
            <li>
              <strong>Data Processing Agreements (DPAs):</strong> Binding agreements with all subprocessors
              that specify data protection requirements
            </li>
            <li>
              <strong>Privacy Shield (Legacy):</strong> Some processors were certified under Privacy Shield
              before it was invalidated; they now use SCCs
            </li>
            <li>
              <strong>Adequacy Decisions:</strong> Transfers to countries deemed adequate by the European Commission
            </li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>8. Changes to This List</h2>
          <p>
            We may add, remove, or replace subprocessors as our business needs change.
            Material changes to this list will be communicated via:
          </p>
          <ul>
            <li>Email notification (for changes affecting data security or location)</li>
            <li>Update to this page (check "Last Updated" date)</li>
          </ul>
          <p>
            If you object to a new subprocessor, you may terminate your subscription in accordance
            with our <Link to="/terms" className="policy-page__link">Terms of Service</Link>.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>9. Your Rights</h2>
          <p>
            Your rights under GDPR apply to data processed by our subprocessors.
            For information about your rights (access, rectification, erasure, etc.),
            see our <Link to="/privacy" className="policy-page__link">Privacy Policy</Link>.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>10. Contact Us</h2>
          <p>
            If you have questions about our subprocessors or data processing practices:
          </p>
          <p>
            <strong>Email:</strong> <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a><br />
            <strong>Subject:</strong> "Subprocessor Inquiry"
          </p>
        </section>

        <div className="policy-page__footer">
          <p>Last Updated: November 2025</p>
          <p>
            <Link to="/about" className="policy-page__link">About</Link> ·
            <Link to="/privacy" className="policy-page__link">Privacy Policy</Link> ·
            <Link to="/terms" className="policy-page__link">Terms of Service</Link> ·
            <Link to="/cookies" className="policy-page__link">Cookies</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
