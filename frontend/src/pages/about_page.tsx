// frontend/src/pages/about_page.tsx
import { Link } from 'react-router-dom';
import './policy_pages.css';

export const AboutPage = () => {
  return (
    <div className="policy-page">
      <div className="policy-page__container">
        <h1 className="policy-page__title">About Brubru</h1>

        <section className="policy-page__section">
          <h2>Your AI Companion for Navigating the EU Bubble</h2>
          <p>
            Brubru is an AI-powered strategic advocacy assistant designed specifically for EU policy professionals,
            lobbyists, and organisations working within the Brussels institutional ecosystem. We combine cutting-edge
            conversational AI with specialized legislative tools to help you analyse policies, strategise advocacy
            campaigns, draft amendments, and navigate EU institutional processes with confidence.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>What We Offer</h2>

          <div className="policy-page__feature">
            <h3>Brubru Chat</h3>
            <p>
              Our AI-powered conversational interface provides real-time analysis of EU policy matters.
              Brubru's chat injects contextual information
              from EU institutional sources.
            </p>
          </div>

          <div className="policy-page__feature">
            <h3>Amendator</h3>
            <p>
              A professional legislative amendment authoring tool to draft, edit, and manage amendments to EU legislative texts with precision.
              Export your work in multiple formats including XML, HTML, PDF, and Word.
            </p>
          </div>

          <div className="policy-page__feature">
            <h3>My EU Bubble</h3>
            <p>
              Stay informed with personalised news feed aggregation from 15+ EU institutional sources.
              Subscribe to European Parliament committees, Commission DGs, European legislative procedures,
              research, and more: all in one place.
            </p>
          </div>

          <div className="policy-page__feature">
            <h3>EU Law Comply</h3>
            <p>
              Automated compliance checking for EU laws. Upload your organisational documents
              and receive a comprehensive gap analysis against relevant EU law clusters. Get actionable
              recommendations and export detailed compliance reports.
            </p>
          </div>

          <div className="policy-page__feature">
            <h3>Legislative Tracking</h3>
            <p>
              Monitor EU legislative procedures in real-time. Track the European Legislative Train Schedule,
              procedural dossiers, and EU parliamentary activities. Never miss a critical deadline or procedural update.
            </p>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>Who We Serve</h2>
          <p>Brubru is designed for:</p>
          <ul>
            <li>EU Policy Professionals and Lobbyists</li>
            <li>Advocacy Organizations and NGOs</li>
            <li>Think Tanks and Research Institutes</li>
            <li>Government Agencies and Public Affairs Teams</li>
            <li>Corporations with Brussels Offices</li>
            <li>Law Firms Specializing in EU Law</li>
            <li>Academic Researchers in EU Studies</li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>Subscription Plans</h2>

          <div className="policy-page__tier">
            <h3>Starter (from &euro;39/month)</h3>
            <p>AI Chat and My EU Bubble dashboard with RSS aggregation and legislative tracking. Perfect for getting started with EU policy monitoring.</p>
          </div>

          <div className="policy-page__tier">
            <h3>Advocate (from &euro;59/month)</h3>
            <p>
              Full advocacy toolkit. Everything in Starter plus Amendator with unlimited amendments,
              AI-powered amendment suggestions, and PDF/Word exports without watermark.
            </p>
          </div>

          <div className="policy-page__tier">
            <h3>Professional (from &euro;99/month)</h3>
            <p>
              Complete platform access. Everything in Advocate plus EU Law Comply, Tenderator,
              Council vote predictions, dedicated support, and API access.
            </p>
          </div>

          <div className="policy-page__tier">
            <h3>EP Plan (&euro;49/month)</h3>
            <p>
              Tailored for accredited parliamentary assistants and MEPs. Includes Chat, Bubble, and Amendator
              with EP-specific AI context and committee monitoring.
            </p>
          </div>

          <p className="policy-page__cta">
            <Link to="/subscription" className="policy-page__link">View Detailed Pricing →</Link>
          </p>
        </section>

        <section className="policy-page__section">
          <h2>About Beresol BV</h2>
          <p>
            Brubru is developed and maintained by <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer" className="policy-page__link">Beresol BV</a>,
            a technology company specializing in AI-powered solutions for policy and advocacy professionals.
            Founded by Victor Solé Ferioli, Beresol combines deep expertise in EU institutional processes
            with cutting-edge artificial intelligence to create tools that empower policy professionals.
          </p>
          <p>
            The Brubru trademark is registered with the European Union Intellectual Property Office (EUIPO)
            and belongs exclusively to Beresol BV.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>Contact Us</h2>
          <p>
            We would love to hear from you. Whether you have questions about our services, need technical support,
            or want to discuss custom enterprise solutions, please do not hesitate to reach out.
          </p>
          <ul>
            <li><strong>Email:</strong> <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a></li>
            <li><strong>Website:</strong> <a href="https://brubru.beresol.eu" target="_blank" rel="noopener noreferrer" className="policy-page__link">brubru.beresol.eu</a></li>
            <li><strong>Company Website:</strong> <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer" className="policy-page__link">beresol.eu</a></li>
          </ul>
        </section>

        <section className="policy-page__section">
          <h2>Open Source & Transparency</h2>
          <p>
            We believe in transparency. While Brubru's core platform is proprietary, we actively contribute
            to open-source projects and maintain public documentation of our technical architecture,
            data sources, and AI model usage.
          </p>
          <p>
            For technical documentation, API specifications, and developer resources, please visit our
            GitHub repository or contact us for access to our technical documentation.
          </p>
        </section>

        <div className="policy-page__footer">
          <p>Last Updated: November 2025</p>
          <p>
            <Link to="/privacy" className="policy-page__link">Privacy Policy</Link> ·
            <Link to="/terms" className="policy-page__link">Terms of Service</Link> ·
            <Link to="/cookies" className="policy-page__link">Cookies</Link> ·
            <Link to="/subprocessors" className="policy-page__link">Subprocessors</Link>
          </p>
        </div>
      </div>
    </div>
  );
};
