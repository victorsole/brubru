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
            <div className="landing__pricing-badge"><span className="mdi mdi-heart-outline"></span> WHITE</div>
            <h3>Basic</h3>
            <div className="landing__pricing-price">
              <span className="landing__pricing-amount">€0</span>
              <span className="landing__pricing-period">/month</span>
            </div>
            <ul className="landing__pricing-features">
              <li><span className="mdi mdi-check"></span> Basic AI chat</li>
              <li><span className="mdi mdi-check"></span> Search EU legislation</li>
              <li><span className="mdi mdi-check"></span> View MEP profiles and Parliament data</li>
              <li><span className="mdi mdi-check"></span> 5 amendments/month</li>
              <li><span className="mdi mdi-check"></span> Save up to 5 searches</li>
              <li><span className="mdi mdi-close"></span> Watermark on exports</li>
              <li><span className="mdi mdi-close"></span> No PDF/Word downloads (XML/HTML only)</li>
            </ul>
            <Link to="/signup" className="btn btn--outline">
              Start Free
            </Link>
          </div>

          {/* Yellow Tier */}
          <div className="landing__pricing-card landing__pricing-card--featured">
            <div className="landing__pricing-badge landing__pricing-badge--popular">
              <span className="mdi mdi-heart landing__pricing-badge-icon--yellow"></span> YELLOW • MOST POPULAR
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
              <li><span className="mdi mdi-check"></span> Everything in White</li>
              <li><span className="mdi mdi-check"></span> Unlimited amendments</li>
              <li><span className="mdi mdi-check"></span> Advanced AI</li>
              <li><span className="mdi mdi-check"></span> Priority response time</li>
              <li><span className="mdi mdi-check"></span> No watermark</li>
              <li><span className="mdi mdi-check"></span> PDF/Word downloads</li>
              <li><span className="mdi mdi-check"></span> Save unlimited searches</li>
              <li><span className="mdi mdi-check"></span> Advanced search & filters</li>
              <li><span className="mdi mdi-check"></span> Custom RSS alerts</li>
              <li><span className="mdi mdi-check"></span> Email support (48h response)</li>
              <li><span className="mdi mdi-check"></span> API access (1,000 calls/month)</li>
            </ul>
            <Link to="/signup?tier=yellow" className="btn btn--primary">
              Start 14-Day Trial
            </Link>
          </div>

          {/* Blue Tier */}
          <div className="landing__pricing-card">
            <div className="landing__pricing-badge"><span className="mdi mdi-heart landing__pricing-badge-icon--blue"></span> BLUE</div>
            <h3>Enterprise</h3>
            <div className="landing__pricing-price">
              <span className="landing__pricing-amount" style={{ fontSize: '1.5rem' }}>Custom pricing</span>
            </div>
            <p className="landing__pricing-note">5+ users - Contact us for a tailored quote</p>
            <ul className="landing__pricing-features">
              <li><span className="mdi mdi-check"></span> Everything in Yellow</li>
              <li><span className="mdi mdi-check"></span> Multi-user teams (5+)</li>
              <li><strong><span className="mdi mdi-check"></span> Domain specialisation</strong></li>
              <li>&nbsp;&nbsp;&nbsp;(agriculture, transport, etc.)</li>
              <li><span className="mdi mdi-check"></span> Custom knowledge base</li>
              <li><span className="mdi mdi-check"></span> Dedicated account manager</li>
              <li><span className="mdi mdi-check"></span> Priority support</li>
              <li><span className="mdi mdi-check"></span> Onboarding & training</li>
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
