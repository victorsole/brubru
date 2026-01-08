// Landing page for Brubru with pricing tiers
import { Link } from 'react-router-dom';
import { CarouselSection } from '../components/carousel/carousel_section';
import './landing_page.css';

export const LandingPage = () => {
  return (
    <div className="landing">
      {/* Hero Section */}
      <section className="landing__hero">
        <img
          className="landing__hero-image"
          src="/assets/eu_labyrinth.png"
          alt="EU Labyrinth"
        />
        <div className="landing__hero-overlay"></div>
        <div className="landing__hero-content">
          <img
            src="/assets/brubru_mainlogo.png"
            alt="Brubru Logo"
            className="landing__hero-logo"
          />
          <h1 className="landing__hero-title">
            Your AI-Powered EU Bubble Assistant
          </h1>
          <p className="landing__hero-subtitle">
            AI-powered tools for EU legislation research, amendment drafting,
            and policy advocacy.
          </p>
          <div className="landing__hero-cta">
            <Link to="/signup" className="btn btn--primary btn--large">
              Start Free Trial
            </Link>
            <Link to="/login" className="btn btn--secondary btn--large">
              Log In
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="landing__features">
        <h2>What You Can Do With Brubru</h2>
        <div className="landing__features-grid">
          <div className="landing__feature-card">
            <img src="/assets/brubru_myeububble.png" alt="Chat" />
            <h3>AI Policy Assistant</h3>
            <p>Chat with EU legislation, get instant answers about EU laws, procedures, officials, and much more</p>
          </div>
          <div className="landing__feature-card">
            <img src="/assets/brubru_amendator.png" alt="Amendator" />
            <h3>Brubru Amendator</h3>
            <p>Draft legislative amendments with AI assistance, export in multiple formats</p>
          </div>
          <div className="landing__feature-card">
            <img src="/assets/brubru_mainlogo.png" alt="Search" />
            <h3>Smart Search</h3>
            <p>Do not look for expensive consultants when Brubru can also do it and much cheaper</p>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="landing__pricing" id="pricing">
        <h2>Choose Your Plan</h2>
        <p className="landing__pricing-subtitle">Start free, upgrade when you need more</p>

        <div className="landing__pricing-grid">
          {/* White Tier */}
          <div className="landing__pricing-card">
            <div className="landing__pricing-badge">🤍 WHITE</div>
            <h3>Basic</h3>
            <div className="landing__pricing-price">
              <span className="landing__pricing-amount">€0</span>
              <span className="landing__pricing-period">/month</span>
            </div>
            <ul className="landing__pricing-features">
              <li>✓ Basic AI chat</li>
              <li>✓ Search EU legislation</li>
              <li>✓ View MEP profiles and Parliament data</li>
              <li>✓ 5 amendments/month</li>
              <li>✓ Save up to 5 searches</li>
              <li>✗ Watermark on exports</li>
              <li>✗ No PDF/Word downloads (XML/HTML only)</li>
            </ul>
            <Link to="/signup" className="btn btn--outline">
              Start Free
            </Link>
          </div>

          {/* Yellow Tier */}
          <div className="landing__pricing-card landing__pricing-card--featured">
            <div className="landing__pricing-badge landing__pricing-badge--popular">
              💛 YELLOW • MOST POPULAR
            </div>
            <h3>Professional</h3>
            <div className="landing__pricing-price">
              <span className="landing__pricing-amount">€79</span>
              <span className="landing__pricing-period">/month</span>
            </div>
            <p className="landing__pricing-savings">
              or €790/year (save €158)
            </p>
            <ul className="landing__pricing-features">
              <li>✓ Everything in White</li>
              <li>✓ Unlimited amendments</li>
              <li>✓ Advanced AI</li>
              <li>✓ Priority response time</li>
              <li>✓ No watermark</li>
              <li>✓ PDF/Word downloads</li>
              <li>✓ Save unlimited searches</li>
              <li>✓ Advanced search & filters</li>
              <li>✓ Custom RSS alerts</li>
              <li>✓ Email support (48h response)</li>
              <li>✓ API access (1,000 calls/month)</li>
            </ul>
            <Link to="/signup?tier=yellow" className="btn btn--primary">
              Start 14-Day Trial
            </Link>
          </div>

          {/* Blue Tier */}
          <div className="landing__pricing-card">
            <div className="landing__pricing-badge">💙 BLUE</div>
            <h3>Enterprise</h3>
            <div className="landing__pricing-price">
              <span className="landing__pricing-amount" style={{ fontSize: '1.5rem' }}>Custom pricing</span>
            </div>
            <p className="landing__pricing-note">5+ users - Contact us for a tailored quote</p>
            <ul className="landing__pricing-features">
              <li>✓ Everything in Yellow</li>
              <li>✓ Multi-user teams (5+)</li>
              <li><strong>✓ Domain specialisation</strong></li>
              <li>&nbsp;&nbsp;&nbsp;(agriculture, transport, etc.)</li>
              <li>✓ Custom knowledge base</li>
              <li>✓ Dedicated account manager</li>
              <li>✓ Priority support</li>
              <li>✓ Onboarding & training</li>
            </ul>
            <a href="mailto:helloberesol@gmail.com" className="btn btn--outline">
              Contact Us
            </a>
          </div>
        </div>
      </section>

      {/* Blue Tier Examples */}
      <section className="landing__examples">
        <h2>Blue Tier: Specialised Brubru</h2>
        <p>Custom-built for your industry</p>
        <div className="landing__examples-grid">
          <div className="landing__example-card">
            <h4>Agriculture & Food</h4>
            <p>Specialised in CAP, food safety, organic farming, and rural development</p>
            <div className="landing__example-client">
              <span></span>
              <a href="https://hellobo.eu" target="_blank" rel="noopener noreferrer">
                <img src="/assets/Bo_logo.png" alt="Bo" className="landing__client-logo" />
              </a>
            </div>
          </div>
          <div className="landing__example-card">
            <h4>Transport & Infrastructure</h4>
            <p>Focused on railway regulations, TEN-T, mobility, and logistics</p>
            <div className="landing__example-client">
              <span></span>
              <a href="https://ferrmed.com" target="_blank" rel="noopener noreferrer">
                <img src="/assets/ferrmed.jpeg" alt="Ferrmed" className="landing__client-logo" />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Carousel Section */}
      <CarouselSection />

      {/* CTA Section */}
      <section className="landing__cta">
        <h2>Ready?</h2>
        <p>Join EU policy professionals using Brubru to work smarter</p>
        <Link to="/signup" className="btn btn--primary btn--large">
          Create Free Account
        </Link>
      </section>

      {/* Footer */}
      <footer className="landing__footer">
        <div className="landing__footer-brand">
          <img
            src="/assets/beresol-logo.png"
            alt="Beresol"
            className="landing__footer-logo"
          />
          <p>© 2025 Beresol BV. All rights reserved.</p>
          <p className="landing__footer-tagline">Brubru is a product of Beresol.</p>
        </div>
        <div className="landing__footer-links">
          <a href="https://beresol.eu">About Us</a>
          <a href="/privacy">Privacy Policy</a>
          <a href="/terms">Terms of Service</a>
          <a href="/contact">Contact</a>
        </div>
      </footer>
    </div>
  );
};
