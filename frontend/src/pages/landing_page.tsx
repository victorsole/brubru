// Landing page for Brubru - Full rewrite from approved mockup
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { CarouselSection } from '../components/carousel/carousel_section';
import './landing_page.css';

// =====================================================
// DATA ARRAYS (outside component to avoid re-creation)
// =====================================================

const FEATURE_TRACKS = [
  { icon: 'mdi-chat-processing-outline', name: 'AI Policy Chat', desc: 'Ask questions about any EU law, procedure, or institution' },
  { icon: 'mdi-file-edit-outline', name: 'Amendment Drafting', desc: 'AI-assisted legislative amendments in Akoma Ntoso XML' },
  { icon: 'mdi-rss', name: 'RSS Feed Aggregation', desc: 'Monitor 15+ EU institutional sources in one place' },
  { icon: 'mdi-chart-timeline-variant', name: 'Legislative Predictions', desc: 'AI-powered outcome forecasts for EP and Council votes' },
  { icon: 'mdi-scale-balance', name: 'EU Law Comply', desc: 'Compliance gap analysis against EU legislation' },
  { icon: 'mdi-file-document-multiple', name: 'Document Generation', desc: 'Position papers, MEP briefings, talking points' },
  { icon: 'mdi-train', name: 'Legislative Train Tracker', desc: 'Follow 500+ legislative files through the EU process' },
  { icon: 'mdi-account-group', name: 'EP Committee Monitoring', desc: 'Track work in progress across all 26 EP committees' },
  { icon: 'mdi-bullhorn', name: 'Public Consultations', desc: 'Discover and participate in EC "Have Your Say" consultations' },
  { icon: 'mdi-earth', name: '23 EU Languages', desc: 'Full interface localisation across all official EU languages' },
];

const STORY_STEPS = [
  {
    step: '01',
    title: 'Ask a policy question',
    content: 'Type any EU policy question in natural language. Brubru\u2019s AI draws on a knowledge base of 50,000+ EU laws, EP committee reports, Commission proposals, EPRS briefings, and 11 Beresol open reports covering topics from AI Act implementation to CBAM compliance.',
  },
  {
    step: '02',
    title: 'Track what matters',
    content: 'Set up RSS feeds from the European Parliament, Council, Commission, EUR-Lex, and more. Track specific legislative files through the Legislative Train, monitor EP committee work, and get alerts on public consultations with upcoming deadlines.',
  },
  {
    step: '03',
    title: 'Draft amendments',
    content: 'Load any EU regulation or directive from EUR-Lex, select the article or recital you want to amend, and let the AI suggest changes. Export in Akoma Ntoso XML, PDF, or Word format following official EP formatting guidelines.',
  },
  {
    step: '04',
    title: 'Generate documents',
    content: 'Produce AI-powered position papers, MEP briefing notes, and talking points tailored to your policy area. Run compliance gap analysis with EU Law Comply to check how new legislation affects your organisation or sector.',
  },
];

const ABOUT_VALUES = [
  { icon: 'mdi-shield-check', title: 'GDPR Compliant', desc: 'EU-hosted infrastructure. Your data stays in Europe.' },
  { icon: 'mdi-translate', title: 'Multilingual', desc: 'AI understands and responds in all EU languages.' },
  { icon: 'mdi-brain', title: 'Multi-AI Engine', desc: 'Mistral, Claude, GPT-4, and Gemini for reliability.' },
  { icon: 'mdi-database', title: '50,000+ EU Laws', desc: 'Comprehensive knowledge base of EU legislation.' },
];

const CTA_TITLE = 'Ready to navigate the EU bubble with AI?';
const CTA_WORDS = CTA_TITLE.split(/\s+/);

// =====================================================
// COMPONENT
// =====================================================

export const LandingPage = () => {
  const [openStory, setOpenStory] = useState<number | null>(null);
  const [ctaVisible, setCtaVisible] = useState(false);
  const ctaSectionRef = useRef<HTMLElement>(null);

  // Effect 1: IntersectionObserver for .fade-up elements
  useEffect(() => {
    const elements = document.querySelectorAll('.landing .fade-up');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
    );
    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  // Effect 2: IntersectionObserver for CTA section
  useEffect(() => {
    const section = ctaSectionRef.current;
    if (!section) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setCtaVisible(true);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.3 }
    );
    observer.observe(section);
    return () => observer.disconnect();
  }, []);

  // Effect 3: Add/remove scroll-snap class on <html>
  useEffect(() => {
    document.documentElement.classList.add('landing-scroll-snap');
    return () => {
      document.documentElement.classList.remove('landing-scroll-snap');
    };
  }, []);

  const handleStoryClick = useCallback((index: number) => {
    setOpenStory((prev) => (prev === index ? null : index));
  }, []);

  return (
    <div className="landing">
      {/* ========== NAVIGATION ========== */}
      <nav className="nav-top">
        <Link to="/">
          <img src="/assets/brubru_mainlogo.png" alt="Brubru" className="nav-top__logo" />
        </Link>
        <div className="nav-top__links">
          <a href="#features" className="nav-link">
            <span className="nav-link-text">Features</span>
            <span className="nav-link-text nav-link-text--hover">Features</span>
          </a>
          <a href="#pricing" className="nav-link">
            <span className="nav-link-text">Pricing</span>
            <span className="nav-link-text nav-link-text--hover">Pricing</span>
          </a>
          <a href="#about" className="nav-link">
            <span className="nav-link-text">About</span>
            <span className="nav-link-text nav-link-text--hover">About</span>
          </a>
          <Link to="/login" className="nav-link">
            <span className="nav-link-text">Log In</span>
            <span className="nav-link-text nav-link-text--hover">Log In</span>
          </Link>
          <Link to="/signup" className="nav-cta">Start Free</Link>
        </div>
      </nav>

      <main>
        {/* ========== 1. HERO ========== */}
        <section className="section section--hero">
          <div className="hero">
            <video className="hero__video" autoPlay muted loop playsInline>
              <source src="/assets/jubelpark.mp4" type="video/mp4" />
            </video>
            <div className="hero__overlay" />
            <div className="hero__content">
              <img src="/assets/brubru_mainlogo.png" alt="Brubru Logo" className="hero__logo" />
              <h1 className="hero__title">Your AI-Powered EU Bubble Assistant</h1>
              <p className="hero__subtitle">
                Analyse legislation. Draft amendments. Navigate EU institutions.
              </p>
              <div className="hero__cta">
                <Link to="/signup" className="btn btn--white btn--large">Start Free Trial</Link>
                <Link to="/login" className="btn btn--outline-white btn--large">Log In</Link>
              </div>
            </div>
          </div>
        </section>

        {/* ========== 2. INTRO ========== */}
        <section className="section intro-section">
          <div className="intro fade-up">
            <p className="intro__eyebrow">What is Brubru</p>
            <h2 className="intro__heading">
              <strong>Brubru</strong> is an AI-powered strategic advocacy assistant for EU policy professionals.
              It combines conversational AI with legislative tools to help users analyse policies,
              draft amendments, and navigate EU institutional processes.
            </h2>
            <p className="intro__text">
              Built by <em><a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">Beresol</a></em>, a Brussels-based public affairs technology company,
              Brubru serves lobbyists, trade associations, law firms, and NGOs working in the EU bubble.
            </p>
          </div>
        </section>

        {/* ========== 3. VIDEO ========== */}
        <section className="section video-section">
          <div className="video-container">
            <video autoPlay muted loop playsInline>
              <source src="/assets/eu_flag.mp4" type="video/mp4" />
            </video>
            <div className="video-overlay">
              <p className="video-overlay__text">
                The EU produces <strong>50,000+ legislative acts</strong>. Brubru helps you find what matters.
              </p>
            </div>
          </div>
        </section>

        {/* ========== 4. PRODUCT (Features Tracklist) ========== */}
        <section className="section product-section" id="features">
          <div className="product">
            <div className="product__tracks fade-up">
              {FEATURE_TRACKS.map((track) => (
                <div key={track.name} className="product__track">
                  <span className={`product__track-icon mdi ${track.icon}`} />
                  <span>
                    <span className="product__track-name">{track.name}</span>
                    {' \u2014'}{track.desc}
                  </span>
                </div>
              ))}
            </div>
            <div className="product__info fade-up">
              <p className="product__eyebrow">Platform</p>
              <h2 className="product__title">10 Tools.<br />One Platform.</h2>
              <p className="product__subtitle">Everything EU professionals need</p>
              <p className="product__description">
                Brubru replaces expensive consultants and fragmented tools with a single AI-powered platform
                that covers the full EU advocacy workflow {'\u2014'}from research to amendment drafting to compliance checking.
              </p>
            </div>
          </div>
        </section>

        {/* ========== 5. STORY (How It Works) ========== */}
        <section className="story-section">
          <div className="story">
            <div className="story__header">
              <p className="story__eyebrow">How Brubru Works</p>
              <h2 className="story__title fade-up">From research question to policy action in minutes, not weeks</h2>
            </div>
            <p className="story__intro fade-up">
              Brubru{'\u2019'}s AI understands EU institutional processes, legislative procedures,
              and policy context. Here{'\u2019'}s how professionals use it every day.
            </p>
            <div className="story__timeline">
              {STORY_STEPS.map((item, i) => (
                <div
                  key={item.step}
                  className={`story__item fade-up${openStory === i ? ' open' : ''}`}
                  onClick={() => handleStoryClick(i)}
                >
                  <h3 className="story__step">{item.step}</h3>
                  <h4 className="story__step-title">{item.title}</h4>
                  <p className="story__content">{item.content}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ========== 6. PRICING ========== */}
        <section className="pricing-section" id="pricing">
          <p className="pricing__eyebrow">Pricing</p>
          <h2 className="pricing__title fade-up"><strong>Choose Your Plan</strong></h2>
          <p className="pricing__subtitle fade-up">Start free, upgrade when you need more</p>

          <div className="pricing__grid">
            {/* White */}
            <div className="pricing__card fade-up">
              <div className="pricing__badge pricing__badge--white">
                <span className="mdi mdi-heart-outline" /> WHITE
              </div>
              <h3>Basic</h3>
              <div className="pricing__price">
                <span className="pricing__amount">&euro;0</span>
                <span className="pricing__period">/month</span>
              </div>
              <ul className="pricing__features">
                <li><span className="mdi mdi-check" /> Basic AI chat</li>
                <li><span className="mdi mdi-check" /> Search EU legislation</li>
                <li><span className="mdi mdi-check" /> View MEP profiles</li>
                <li><span className="mdi mdi-check" /> 5 amendments/month</li>
                <li><span className="mdi mdi-close" /> Watermark on exports</li>
              </ul>
              <Link to="/signup" className="btn btn--outline" style={{ width: '100%' }}>Start Free</Link>
            </div>

            {/* Yellow */}
            <div className="pricing__card pricing__card--featured fade-up">
              <div className="pricing__badge pricing__badge--yellow">
                <span className="mdi mdi-heart" /> YELLOW {'\u2014'}MOST POPULAR
              </div>
              <h3>Professional</h3>
              <div className="pricing__price">
                <span className="pricing__amount">&euro;79</span>
                <span className="pricing__period">/month</span>
              </div>
              <p className="pricing__savings">or &euro;790/year (save &euro;158)</p>
              <ul className="pricing__features">
                <li><span className="mdi mdi-check" /> Everything in White</li>
                <li><span className="mdi mdi-check" /> Unlimited amendments</li>
                <li><span className="mdi mdi-check" /> Advanced AI + predictions</li>
                <li><span className="mdi mdi-check" /> PDF/Word downloads</li>
                <li><span className="mdi mdi-check" /> Custom RSS alerts</li>
                <li><span className="mdi mdi-check" /> API access (1,000 calls/month)</li>
              </ul>
              <Link to="/signup?tier=yellow" className="btn btn--primary" style={{ width: '100%' }}>Start 14-Day Trial</Link>
            </div>

            {/* Blue */}
            <div className="pricing__card fade-up">
              <div className="pricing__badge pricing__badge--blue">
                <span className="mdi mdi-heart" /> BLUE
              </div>
              <h3>Enterprise</h3>
              <div className="pricing__price">
                <span className="pricing__amount" style={{ fontSize: '1.5rem' }}>Custom pricing</span>
              </div>
              <p className="pricing__note">5+ users {'\u2014'}Contact us for a tailored quote</p>
              <ul className="pricing__features">
                <li><span className="mdi mdi-check" /> Everything in Yellow</li>
                <li><span className="mdi mdi-check" /> Multi-user teams (5+)</li>
                <li><span className="mdi mdi-check" /> Domain specialisation</li>
                <li><span className="mdi mdi-check" /> Custom knowledge base</li>
                <li><span className="mdi mdi-check" /> Dedicated account manager</li>
              </ul>
              <a href="mailto:hello@beresol.eu" className="btn btn--outline" style={{ width: '100%' }}>Contact Us</a>
            </div>
          </div>
        </section>

        {/* ========== 7. CLIENTS ========== */}
        <section className="clients-section">
          <div className="clients">
            <p className="clients__eyebrow">Blue Tier</p>
            <h2 className="clients__title fade-up">Specialised Brubru</h2>
            <p className="clients__subtitle fade-up">Custom-built for your industry</p>
            <div className="clients__cta fade-up">
              <a href="mailto:hello@beresol.eu?subject=Brubru%20-%20I%20need%20help!" className="btn--rainbow">Contact Us</a>
            </div>
            <div className="clients__grid" style={{ marginTop: 'var(--spacing-2xl)' }}>
              <div className="clients__card fade-up">
                <h4>Agriculture & Food</h4>
                <p>Specialised in CAP, food safety, organic farming, and rural development</p>
                <a href="https://hellobo.eu" target="_blank" rel="noopener noreferrer">
                  <img src="/assets/Bo_logo.png" alt="Bo" className="clients__logo" />
                </a>
              </div>
              <div className="clients__card fade-up">
                <h4>Transport & Infrastructure</h4>
                <p>Focused on railway regulations, TEN-T, mobility, and logistics</p>
                <a href="https://ferrmed.com" target="_blank" rel="noopener noreferrer">
                  <img src="/assets/ferrmed.jpeg" alt="Ferrmed" className="clients__logo" />
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ========== 8. CAROUSEL ========== */}
        <div className="carousel-wrapper">
          <CarouselSection />
        </div>

        {/* ========== 9. ABOUT ========== */}
        <section className="about-section" id="about">
          <div className="about">
            <div className="fade-up">
              <p className="about__eyebrow">About Brubru</p>
              <h2 className="about__title">Built in <strong>Brussels</strong>, for the <strong>EU bubble</strong></h2>
              <p className="about__text">
                Brubru is developed by <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">Beresol</a>,
                a Brussels-based public affairs technology company. We combine deep understanding of EU institutional
                processes with cutting-edge AI to create tools that actually work for policy professionals.
              </p>
              <p className="about__text">
                Our mission is to democratise access to EU policy intelligence. Whether you{'\u2019'}re a lobbyist tracking
                legislative files, an NGO drafting amendments, or a trade association monitoring consultations {'\u2014'}
                Brubru gives you the same analytical power as the largest firms in town.
              </p>
              <div className="about__values">
                {ABOUT_VALUES.map((value) => (
                  <div key={value.title} className="about__value">
                    <div className={`about__value-icon mdi ${value.icon}`} />
                    <h4>{value.title}</h4>
                    <p>{value.desc}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="about__team fade-up">
              <img src="/assets/victor.JPG" alt="Victor Sole Ferioli, Founder" className="about__team-photo" />
              <h3 className="about__team-name">
                <a href="https://linkedin.com/in/victor-sole" target="_blank" rel="noopener noreferrer">Victor Sol&eacute; Ferioli</a>
              </h3>
              <p className="about__team-role">
                Founder & CEO, <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">Beresol</a>
              </p>
              <p className="about__team-bio">
                Brussels-based public affairs professional and technologist. Victor founded{' '}
                <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">Beresol</a> to bridge the gap
                between EU policy expertise and modern AI technology, making institutional knowledge
                accessible to everyone in the EU bubble.
              </p>
            </div>
          </div>
        </section>

        {/* ========== 10. CTA ========== */}
        <section
          ref={ctaSectionRef}
          className={`section section--end cta-section${ctaVisible ? ' cta--visible' : ''}`}
        >
          <div>
            <h2 className="cta__title">
              {CTA_WORDS.map((word, i) => (
                <span
                  key={i}
                  className="cta__word"
                  style={{ animationDelay: `${0.8 + i * 0.1}s` }}
                >
                  {word}
                </span>
              )).reduce<React.ReactNode[]>((acc, el, i) => (i === 0 ? [el] : [...acc, ' ', el]), [])}
            </h2>
            <p className="cta__text">Join EU policy professionals using Brubru to work smarter</p>
            <Link to="/signup" className="btn--rainbow btn--rainbow-outline">Create Free Account</Link>
          </div>
        </section>
      </main>

      {/* ========== FOOTER ========== */}
      <footer className="footer">
        <div className="footer__inner">
          <div className="footer__brand">
            <img src="/assets/beresol-logo.png" alt="Beresol" className="footer__logo" />
            <span className="footer__copy">
              &copy; 2026 <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">Beresol</a> BV. Brubru is a product of <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">Beresol</a>.
            </span>
          </div>
          <div className="footer__links">
            <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">About Us</a>
            <Link to="/privacy">Privacy</Link>
            <Link to="/terms">Terms</Link>
            <Link to="/cookies">Cookies</Link>
            <Link to="/contact">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  );
};
