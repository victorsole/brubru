// frontend/src/pages/cookies_page.tsx
import { Link } from 'react-router-dom';
import './policy_pages.css';

export const CookiesPage = () => {
  return (
    <div className="policy-page">
      <div className="policy-page__container">
        <h1 className="policy-page__title">Cookie Policy</h1>

        <section className="policy-page__section">
          <p className="policy-page__intro">
            <strong>Effective Date:</strong> November 2025<br />
            <strong>Last Updated:</strong> November 2025
          </p>
          <p>
            This Cookie Policy explains how Brubru (operated by Beresol BV) uses cookies
            and similar tracking technologies when you visit https://brubru.beresol.eu.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>1. What Are Cookies?</h2>
          <p>
            Cookies are small text files stored on your device (computer, tablet, smartphone)
            when you visit a website. They help websites remember information about your visit,
            such as your preferences, login status, and browsing activity.
          </p>
          <p>
            Cookies can be:
          </p>
          <ul>
            <li><strong>Session cookies:</strong> Temporary, deleted when you close your browser</li>
            <li><strong>Persistent cookies:</strong> Remain on your device until expiration or manual deletion</li>
            <li><strong>First-party cookies:</strong> Set by Brubru directly</li>
            <li><strong>Third-party cookies:</strong> Set by external services (e.g., Google, Stripe)</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>2. Why We Use Cookies</h2>
          <p>We use cookies to:</p>
          <ul>
            <li><strong>Authentication:</strong> Keep you logged in across sessions</li>
            <li><strong>Preferences:</strong> Remember your language, theme, and settings</li>
            <li><strong>Security:</strong> Detect suspicious activity and prevent fraud</li>
            <li><strong>Analytics:</strong> Understand how you use Brubru to improve our service</li>
            <li><strong>Performance:</strong> Optimize page load times and API responses</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>3. Types of Cookies We Use</h2>

          <h3>3.1 Strictly Necessary Cookies</h3>
          <p>
            These cookies are essential for the website to function and cannot be disabled.
            Without them, you would not be able to use Brubru.
          </p>
          <table className="policy-page__table">
            <thead>
              <tr>
                <th>Cookie Name</th>
                <th>Purpose</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>supabase-auth-token</td>
                <td>Stores your authentication JWT token to keep you logged in</td>
                <td>Session (7 days default)</td>
              </tr>
              <tr>
                <td>csrf_token</td>
                <td>Prevents cross-site request forgery attacks</td>
                <td>Session</td>
              </tr>
              <tr>
                <td>session_id</td>
                <td>Identifies your session on our backend</td>
                <td>Session</td>
              </tr>
            </tbody>
          </table>
          <p className="policy-page__note">
            <strong>Legal Basis:</strong> Legitimate interest (essential for service provision)
          </p>

          <h3>3.2 Functional Cookies</h3>
          <p>
            These cookies enable enhanced functionality and personalization but are not strictly necessary.
          </p>
          <table className="policy-page__table">
            <thead>
              <tr>
                <th>Cookie Name</th>
                <th>Purpose</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>i18next_lng</td>
                <td>Remembers your language preference</td>
                <td>1 year</td>
              </tr>
              <tr>
                <td>theme_preference</td>
                <td>Stores your background and UI theme settings</td>
                <td>1 year</td>
              </tr>
              <tr>
                <td>sidebar_state</td>
                <td>Remembers whether the sidebar is open or closed</td>
                <td>30 days</td>
              </tr>
            </tbody>
          </table>
          <p className="policy-page__note">
            <strong>Legal Basis:</strong> Consent (you can disable these in browser settings)
          </p>

          <h3>3.3 Analytics Cookies (Optional)</h3>
          <p>
            We may use analytics cookies to understand how visitors use Brubru.
            This helps us improve our service and identify bugs.
          </p>
          <table className="policy-page__table">
            <thead>
              <tr>
                <th>Service</th>
                <th>Purpose</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Google Analytics (optional)</td>
                <td>Tracks page views, user flows, and feature usage</td>
                <td>Up to 2 years</td>
              </tr>
              <tr>
                <td>Sentry (optional)</td>
                <td>Error tracking and performance monitoring</td>
                <td>Session</td>
              </tr>
            </tbody>
          </table>
          <p className="policy-page__note">
            <strong>Legal Basis:</strong> Consent (opt-in required)
          </p>
          <p>
            <strong>Current Status:</strong> Analytics cookies are active, and they load only
            after you accept them. If you decline, or before you have chosen, no analytics
            script is loaded and no analytics cookie is set. You can change your mind by
            clearing this site's data in your browser, which makes the banner appear again.
          </p>
          <p>We use two analytics services, both consent-gated:</p>
          <ul>
            <li>
              <strong>Contentsquare (formerly Hotjar):</strong> product analytics and session
              replay. Records how pages are used: clicks, scrolling, navigation and errors.
              Form inputs are masked.
            </li>
            <li>
              <strong>Microsoft Clarity:</strong> behavioural analytics (heatmaps and session
              replay) and AI-visibility reporting, which tells us which AI assistants reach
              the site and which of our pages they cite. Data is processed by Microsoft under
              the Microsoft Privacy Statement, including international transfers under
              standard contractual clauses. Form inputs are masked by default.
            </li>
          </ul>
          <p>
            Neither service is used to identify you personally, and neither is loaded on any
            page until you have accepted analytics cookies.
          </p>

          <h3>3.4 Third-Party Cookies</h3>
          <p>
            When you use certain features, third-party services may set cookies:
          </p>
          <ul>
            <li>
              <strong>Google OAuth:</strong> When you sign in with Google, Google may set cookies
              for authentication (controlled by Google's privacy policy)
            </li>
            <li>
              <strong>LinkedIn OAuth:</strong> When you sign in with LinkedIn, LinkedIn may set cookies
              (controlled by LinkedIn's privacy policy)
            </li>
            <li>
              <strong>Stripe:</strong> When you manage your subscription, Stripe may set cookies
              for payment processing (controlled by Stripe's privacy policy)
            </li>
          </ul>
          <p>
            We do not control these third-party cookies. Please refer to the respective privacy
            policies of these services.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>4. Local Storage and Session Storage</h2>
          <p>
            In addition to cookies, we use browser storage mechanisms:
          </p>

          <h3>4.1 Local Storage</h3>
          <p>We store the following in localStorage:</p>
          <ul>
            <li><strong>JWT Token:</strong> Your authentication token (same as auth cookie)</li>
            <li><strong>User Preferences:</strong> Language, theme, sidebar state</li>
            <li><strong>Draft Content:</strong> Unsaved amendment drafts (auto-save feature)</li>
          </ul>
          <p>localStorage data persists until you clear your browser data or log out.</p>

          <h3>4.2 Session Storage</h3>
          <p>We use sessionStorage for:</p>
          <ul>
            <li><strong>Temporary Data:</strong> Current chat session, form inputs</li>
            <li><strong>Navigation State:</strong> Where you were before navigating away</li>
          </ul>
          <p>sessionStorage is cleared when you close the browser tab.</p>
        </section>

        <section className="policy-page__section">
          <h2>5. How to Control Cookies</h2>

          <h3>5.1 Browser Settings</h3>
          <p>
            You can control cookies through your browser settings. Most browsers allow you to:
          </p>
          <ul>
            <li>View and delete existing cookies</li>
            <li>Block all cookies</li>
            <li>Block third-party cookies only</li>
            <li>Clear cookies when you close the browser</li>
          </ul>
          <p>
            Instructions for popular browsers:
          </p>
          <ul>
            <li>
              <a href="https://support.google.com/chrome/answer/95647" target="_blank" rel="noopener noreferrer" className="policy-page__link">
                Google Chrome
              </a>
            </li>
            <li>
              <a href="https://support.mozilla.org/en-US/kb/cookies-information-websites-store-on-your-computer" target="_blank" rel="noopener noreferrer" className="policy-page__link">
                Mozilla Firefox
              </a>
            </li>
            <li>
              <a href="https://support.apple.com/en-gb/guide/safari/sfri11471/mac" target="_blank" rel="noopener noreferrer" className="policy-page__link">
                Apple Safari
              </a>
            </li>
            <li>
              <a href="https://support.microsoft.com/en-us/microsoft-edge/delete-cookies-in-microsoft-edge-63947406-40ac-c3b8-57b9-2a946a29ae09" target="_blank" rel="noopener noreferrer" className="policy-page__link">
                Microsoft Edge
              </a>
            </li>
          </ul>

          <h3>5.2 Impact of Blocking Cookies</h3>
          <p className="policy-page__note">
            <strong>Important:</strong> If you block strictly necessary cookies, Brubru will not function properly.
            You will not be able to log in or use authenticated features.
          </p>
          <p>
            Blocking functional cookies may result in:
          </p>
          <ul>
            <li>Loss of language and theme preferences on each visit</li>
            <li>Need to log in every time</li>
            <li>Degraded user experience</li>
          </ul>

          <h3>5.3 Opt-Out of Analytics (Future)</h3>
          <p>
            If we implement analytics cookies in the future, you will be able to opt out via:
          </p>
          <ul>
            <li>Cookie consent banner (dismiss or reject)</li>
            <li>Profile → Privacy Settings (toggle analytics)</li>
            <li>Browser "Do Not Track" setting (we will respect this)</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>6. Do Not Track Signals</h2>
          <p>
            Some browsers offer "Do Not Track" (DNT) settings. We currently do not use analytics
            cookies, so DNT has no effect. If we implement analytics in the future, we will
            respect DNT signals and disable tracking for users who enable it.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>7. Updates to This Cookie Policy</h2>
          <p>
            We may update this Cookie Policy to reflect changes in our use of cookies or
            applicable laws. We will notify you of material changes via:
          </p>
          <ul>
            <li>Email to your registered address</li>
            <li>Prominent notice on our website</li>
          </ul>
          <p>
            The "Last Updated" date at the top indicates when this policy was last revised.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>8. Contact Us</h2>
          <p>
            If you have questions about our use of cookies:
          </p>
          <p>
            <strong>Email:</strong> <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a><br />
            <strong>Subject:</strong> "Cookie Policy Inquiry"
          </p>
        </section>

        <div className="policy-page__footer">
          <p>Last Updated: November 2025</p>
          <p>
            <Link to="/about" className="policy-page__link">About</Link> ·
            <Link to="/privacy" className="policy-page__link">Privacy Policy</Link> ·
            <Link to="/terms" className="policy-page__link">Terms of Service</Link> ·
            <Link to="/subprocessors" className="policy-page__link">Subprocessors</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
