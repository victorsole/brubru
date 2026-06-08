// Landing page for Brubru - Full rewrite from approved mockup
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SUPPORTED_LANGUAGES, LANGUAGE_NAMES } from '../i18n/config';
import type { SupportedLanguage } from '../i18n/config';
import { CarouselSection } from '../components/carousel/carousel_section';
import Icon from '@mdi/react';
import { mdiInstagram } from '@mdi/js';
import './landing_page.css';

// =====================================================
// DATA ARRAYS (outside component to avoid re-creation)
// Only non-translatable data: icons, step numbers, keys
// =====================================================

const FEATURE_TRACKS = [
  { icon: 'mdi-chat-processing-outline', nameKey: 'aiChat', descKey: 'aiChatDesc' },
  { icon: 'mdi-file-edit-outline', nameKey: 'amendments', descKey: 'amendmentsDesc' },
  { icon: 'mdi-rss', nameKey: 'rss', descKey: 'rssDesc' },
  { icon: 'mdi-chart-timeline-variant', nameKey: 'predictions', descKey: 'predictionsDesc' },
  { icon: 'mdi-scale-balance', nameKey: 'comply', descKey: 'complyDesc' },
  { icon: 'mdi-file-document-multiple', nameKey: 'docGen', descKey: 'docGenDesc' },
  { icon: 'mdi-train', nameKey: 'legTrain', descKey: 'legTrainDesc' },
  { icon: 'mdi-account-group', nameKey: 'committees', descKey: 'committeesDesc' },
  { icon: 'mdi-bullhorn', nameKey: 'consultations', descKey: 'consultationsDesc' },
  { icon: 'mdi-earth', nameKey: 'languages', descKey: 'languagesDesc' },
];

const STORY_STEPS = [
  { step: '01', titleKey: 'step1Title', contentKey: 'step1Content' },
  { step: '02', titleKey: 'step2Title', contentKey: 'step2Content' },
  { step: '03', titleKey: 'step3Title', contentKey: 'step3Content' },
  { step: '04', titleKey: 'step4Title', contentKey: 'step4Content' },
];

// Brubru clients shown in the right-to-left carousel on the landing page.
// Logos live under frontend/public/clients/ (gitignored — see clients/README.md).
// Quotes are translated into the six Brubru languages (EN, ES, CA, FR, IT, NL)
// and picked at render time based on the active i18n language.
type ClientQuotes = { en: string; es: string; ca: string; fr: string; it: string; nl: string };
type BrubruClient = { id: string; name: string; url: string; logo: string; quotes: ClientQuotes };

const BRUBRU_CLIENTS: BrubruClient[] = [
  {
    id: 'bo',
    name: 'Bo',
    url: 'https://hellobo.eu',
    logo: '/clients/bo.png',
    quotes: {
      en: 'Thanks to Brubru, we could power our platform with all the European laws related to agri-food and geographical indications. Truly a game-changer!',
      es: '¡Gracias a Brubru, hemos podido potenciar nuestra plataforma con todas las leyes europeas relativas a la agroalimentación y a las indicaciones geográficas. Un auténtico cambio de juego!',
      ca: 'Gràcies a Brubru, hem pogut potenciar la nostra plataforma amb totes les lleis europees relatives a l\'agroalimentació i a les indicacions geogràfiques. Un autèntic canvi de joc!',
      fr: 'Grâce à Brubru, nous avons pu alimenter notre plateforme avec toutes les lois européennes relatives à l\'agroalimentaire et aux indications géographiques. Une véritable révolution !',
      it: 'Grazie a Brubru, abbiamo potuto potenziare la nostra piattaforma con tutte le leggi europee in materia di agroalimentare e indicazioni geografiche. Davvero rivoluzionario!',
      nl: 'Dankzij Brubru konden we ons platform voeden met alle Europese wetten over agrovoeding en geografische aanduidingen. Echt een game-changer!',
    },
  },
  {
    id: 'ferrmed',
    name: 'Ferrmed',
    url: 'https://www.ferrmed.com/',
    logo: '/clients/ferrmed.jpeg',
    quotes: {
      en: 'Brubru helps us advocate for the efficient development of the Mediterranean Corridor by assisting our work with document-generation of many types, following up on EU laws on transport and infrastructure, or contact the right EU stakeholder.',
      es: 'Brubru nos ayuda a defender el desarrollo eficiente del Corredor Mediterráneo asistiéndonos en la generación de muchos tipos de documentos, el seguimiento de las leyes europeas sobre transporte e infraestructura y el contacto con el actor adecuado en la UE.',
      ca: 'Brubru ens ajuda a defensar el desenvolupament eficient del Corredor Mediterrani assistint-nos en la generació de molts tipus de documents, en el seguiment de les lleis europees sobre transport i infraestructura i en el contacte amb l\'actor adequat de la UE.',
      fr: 'Brubru nous aide à défendre le développement efficace du Corridor Méditerranéen en nous accompagnant dans la rédaction de nombreux types de documents, le suivi des lois européennes sur les transports et les infrastructures et le contact avec le bon interlocuteur.',
      it: 'Brubru ci aiuta a promuovere lo sviluppo efficiente del Corridoio Mediterraneo assistendoci nella generazione di documenti di vario tipo, nel monitoraggio delle leggi UE su trasporti e infrastrutture e nel contatto con l\'interlocutore giusto.',
      nl: 'Brubru helpt ons pleiten voor een efficiënte ontwikkeling van de Mediterrane Corridor door ons werk te ondersteunen met documentgeneratie van allerlei aard, het opvolgen van EU-wetgeving over transport en infrastructuur en het contact met de juiste EU-stakeholder.',
    },
  },
  {
    id: 'movimentgaudi',
    name: 'Moviment Gaudí',
    url: 'https://movimentgaudi.cat/en/',
    logo: '/clients/movimentgaudi.png',
    quotes: {
      en: 'Brubru is very helpful to know how we can access cultural and educational EU funds and grants. We could not work without it!',
      es: 'Brubru nos resulta muy útil para saber cómo acceder a fondos y subvenciones europeas de cultura y educación. ¡No podríamos trabajar sin él!',
      ca: 'Brubru ens resulta molt útil per saber com accedir a fons i subvencions europees de cultura i educació. No podríem treballar sense ell!',
      fr: 'Brubru nous est très utile pour savoir comment accéder aux fonds et subventions européens en matière de culture et d\'éducation. Nous ne pourrions pas travailler sans lui !',
      it: 'Brubru è molto utile per capire come accedere ai fondi e alle sovvenzioni UE in ambito culturale ed educativo. Non potremmo lavorare senza!',
      nl: 'Brubru helpt ons enorm om te weten hoe we toegang krijgen tot Europese fondsen en subsidies voor cultuur en onderwijs. We zouden niet zonder kunnen!',
    },
  },
  {
    id: 'tas',
    name: 'TAS Europrojects',
    url: 'https://www.taseuro.com/',
    logo: '/clients/tas.png',
    quotes: {
      en: "Brubru's Tenderator helps us follow up on EU funds and tenders of any type. Brubru's Chat is a daily staple for us.",
      es: 'El Tenderator de Brubru nos ayuda a hacer seguimiento de fondos y licitaciones europeas de cualquier tipo. El Chat de Brubru es una herramienta diaria para nosotros.',
      ca: 'El Tenderator de Brubru ens ajuda a fer el seguiment de fons i licitacions europees de qualsevol tipus. El Chat de Brubru és una eina diària per a nosaltres.',
      fr: 'Le Tenderator de Brubru nous aide à suivre les fonds et les marchés publics européens de tout type. Le Chat de Brubru est un outil quotidien pour nous.',
      it: "Il Tenderator di Brubru ci aiuta a monitorare fondi e gare d'appalto UE di ogni tipo. La Chat di Brubru è uno strumento quotidiano per noi.",
      nl: 'De Tenderator van Brubru helpt ons om EU-fondsen en aanbestedingen van elk type op te volgen. De Chat van Brubru is voor ons een dagelijks hulpmiddel.',
    },
  },
  {
    id: 'govclipping',
    name: 'GovClipping',
    url: 'https://www.govclipping.com',
    logo: '/clients/govclipping.png',
    quotes: {
      en: "With Brubru's API we can provide our clients with updated data.",
      es: 'Con la API de Brubru podemos ofrecer a nuestros clientes datos actualizados.',
      ca: "Amb l'API de Brubru podem oferir als nostres clients dades actualitzades.",
      fr: "Grâce à l'API de Brubru, nous pouvons fournir à nos clients des données actualisées.",
      it: "Con l'API di Brubru possiamo fornire ai nostri clienti dati aggiornati.",
      nl: 'Met de API van Brubru kunnen we onze klanten van actuele gegevens voorzien.',
    },
  },
];

const ABOUT_VALUES = [
  { icon: 'mdi-shield-check', titleKey: 'gdprTitle', descKey: 'gdprDesc' },
  { icon: 'mdi-translate', titleKey: 'multilingualTitle', descKey: 'multilingualDesc' },
  { icon: 'mdi-brain', titleKey: 'multiAiTitle', descKey: 'multiAiDesc' },
  { icon: 'mdi-database', titleKey: 'lawsTitle', descKey: 'lawsDesc' },
];

// =====================================================
// COMPONENT
// =====================================================

export const LandingPage = () => {
  const { t, i18n } = useTranslation();
  const [openStory, setOpenStory] = useState<number | null>(null);
  const [ctaVisible, setCtaVisible] = useState(false);
  const ctaSectionRef = useRef<HTMLElement>(null);

  const ctaWords = t('landing.cta.title').split(/\s+/);

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
            <span className="nav-link-text">{t('landing.nav.features')}</span>
            <span className="nav-link-text nav-link-text--hover">{t('landing.nav.features')}</span>
          </a>
          <a href="#pricing" className="nav-link">
            <span className="nav-link-text">{t('landing.nav.pricing')}</span>
            <span className="nav-link-text nav-link-text--hover">{t('landing.nav.pricing')}</span>
          </a>
          <a href="#about" className="nav-link">
            <span className="nav-link-text">{t('landing.nav.about')}</span>
            <span className="nav-link-text nav-link-text--hover">{t('landing.nav.about')}</span>
          </a>
          <Link to="/login" className="nav-link">
            <span className="nav-link-text">{t('landing.nav.logIn')}</span>
            <span className="nav-link-text nav-link-text--hover">{t('landing.nav.logIn')}</span>
          </Link>
          <select
            className="nav-top__lang"
            value={i18n.language || 'en'}
            onChange={(e) => i18n.changeLanguage(e.target.value as SupportedLanguage)}
            aria-label={t('common.selectLanguage')}
          >
            {SUPPORTED_LANGUAGES.map((lang) => (
              <option key={lang} value={lang}>{LANGUAGE_NAMES[lang]}</option>
            ))}
          </select>
          <Link to="/main" className="nav-cta">{t('landing.nav.startFree')}</Link>
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
              <h1 className="hero__title">{t('landing.hero.title')}</h1>
              <p className="hero__subtitle">{t('landing.hero.subtitle')}</p>
              <div className="hero__cta">
                <Link to="/main" className="btn btn--white btn--large">{t('landing.hero.startTrial')}</Link>
                <Link to="/login" className="btn btn--outline-white btn--large">{t('landing.hero.logIn')}</Link>
              </div>
            </div>
          </div>
        </section>

        {/* ========== 2. INTRO ========== */}
        <section className="section intro-section">
          <div className="intro fade-up">
            <p className="intro__eyebrow">{t('landing.intro.eyebrow')}</p>
            <h2
              className="intro__heading"
              dangerouslySetInnerHTML={{ __html: t('landing.intro.heading') }}
            />
            <p
              className="intro__text"
              dangerouslySetInnerHTML={{ __html: t('landing.intro.text') }}
            />
          </div>
        </section>

        {/* ========== 3. VIDEO ========== */}
        <section className="section video-section">
          <div className="video-container">
            <video autoPlay muted loop playsInline>
              <source src="/assets/eu_flag.mp4" type="video/mp4" />
            </video>
            <div className="video-overlay">
              <p
                className="video-overlay__text"
                dangerouslySetInnerHTML={{ __html: t('landing.video.text') }}
              />
            </div>
          </div>
        </section>

        {/* ========== 4. PRODUCT (Features Tracklist) ========== */}
        <section className="section product-section" id="features">
          <div className="product">
            <div className="product__tracks fade-up">
              {FEATURE_TRACKS.map((track) => (
                <div key={track.nameKey} className="product__track">
                  <span className={`product__track-icon mdi ${track.icon}`} />
                  <span>
                    <span className="product__track-name">{t(`landing.features.${track.nameKey}`)}</span>
                    {' \u2014'}{t(`landing.features.${track.descKey}`)}
                  </span>
                </div>
              ))}
            </div>
            <div className="product__info fade-up">
              <p className="product__eyebrow">{t('landing.product.eyebrow')}</p>
              <h2
                className="product__title"
                dangerouslySetInnerHTML={{ __html: t('landing.product.title') }}
              />
              <p className="product__subtitle">{t('landing.product.subtitle')}</p>
              <p className="product__description">{t('landing.product.description')}</p>
            </div>
          </div>
        </section>

        {/* ========== 5. STORY (How It Works) ========== */}
        <section className="story-section">
          <div className="story">
            <div className="story__header">
              <p className="story__eyebrow">{t('landing.story.eyebrow')}</p>
              <h2 className="story__title fade-up">{t('landing.story.title')}</h2>
            </div>
            <p className="story__intro fade-up">{t('landing.story.intro')}</p>
            <div className="story__timeline">
              {STORY_STEPS.map((item, i) => (
                <div
                  key={item.step}
                  className={`story__item fade-up${openStory === i ? ' open' : ''}`}
                  onClick={() => handleStoryClick(i)}
                >
                  <h3 className="story__step">{item.step}</h3>
                  <h4 className="story__step-title">{t(`landing.story.${item.titleKey}`)}</h4>
                  <p className="story__content">{t(`landing.story.${item.contentKey}`)}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ========== 6. PRICING ========== */}
        <section className="pricing-section" id="pricing">
          <p className="pricing__eyebrow">{t('landing.pricing.eyebrow')}</p>
          <h2
            className="pricing__title fade-up"
            dangerouslySetInnerHTML={{ __html: t('landing.pricing.title') }}
          />
          <p className="pricing__subtitle fade-up">{t('landing.pricing.subtitle')}</p>

          <div className="pricing__grid">
            {/* Starter */}
            <div className="pricing__card fade-up">
              <div className="pricing__badge pricing__badge--green">
                {t('landing.pricing.starter.badge')}
              </div>
              <h3>{t('landing.pricing.starter.name')}</h3>
              <div className="pricing__price">
                <span className="pricing__amount">{t('landing.pricing.starter.price')}</span>
                <span className="pricing__period">{t('landing.pricing.starter.period')}</span>
              </div>
              <p className="pricing__savings">{t('landing.pricing.starter.savings')}</p>
              <ul className="pricing__features">
                <li><span className="mdi mdi-check" /> {t('landing.pricing.starter.f1')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.starter.f2')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.starter.f3')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.starter.f4')}</li>
              </ul>
              <Link to="/subscription" className="btn btn--outline" style={{ width: '100%' }}>{t('landing.pricing.starter.button')}</Link>
            </div>

            {/* Advocate */}
            <div className="pricing__card pricing__card--featured fade-up">
              <div className="pricing__badge pricing__badge--yellow">
                {t('landing.pricing.advocate.badge')}
              </div>
              <h3>{t('landing.pricing.advocate.name')}</h3>
              <div className="pricing__price">
                <span className="pricing__amount">{t('landing.pricing.advocate.price')}</span>
                <span className="pricing__period">{t('landing.pricing.advocate.period')}</span>
              </div>
              <p className="pricing__savings">{t('landing.pricing.advocate.savings')}</p>
              <ul className="pricing__features">
                <li><span className="mdi mdi-check" /> {t('landing.pricing.advocate.f1')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.advocate.f2')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.advocate.f3')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.advocate.f4')}</li>
              </ul>
              <Link to="/subscription" className="btn btn--primary" style={{ width: '100%' }}>{t('landing.pricing.advocate.button')}</Link>
            </div>

            {/* Professional */}
            <div className="pricing__card fade-up">
              <div className="pricing__badge pricing__badge--blue">
                {t('landing.pricing.professional.badge')}
              </div>
              <h3>{t('landing.pricing.professional.name')}</h3>
              <div className="pricing__price">
                <span className="pricing__amount">{t('landing.pricing.professional.price')}</span>
                <span className="pricing__period">{t('landing.pricing.professional.period')}</span>
              </div>
              <p className="pricing__savings">{t('landing.pricing.professional.savings')}</p>
              <ul className="pricing__features">
                <li><span className="mdi mdi-check" /> {t('landing.pricing.professional.f1')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.professional.f2')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.professional.f3')}</li>
                <li><span className="mdi mdi-check" /> {t('landing.pricing.professional.f4')}</li>
                {t('landing.pricing.professional.f5', '') && (
                  <li><span className="mdi mdi-check" /> {t('landing.pricing.professional.f5')}</li>
                )}
              </ul>
              <Link to="/subscription" className="btn btn--outline" style={{ width: '100%' }}>{t('landing.pricing.professional.button')}</Link>
            </div>
          </div>

          <p className="pricing__all-plans fade-up">
            <Link to="/subscription">{t('landing.pricing.allPlans')}</Link>
          </p>
        </section>

        {/* ========== 7. CLIENTS ========== */}
        <section className="clients-section">
          <div className="clients">
            <p className="clients__eyebrow">{t('landing.clients.eyebrow')}</p>
            <h2 className="clients__title fade-up">{t('landing.clients.title')}</h2>
            <p className="clients__subtitle fade-up">{t('landing.clients.subtitle')}</p>
            <div className="clients__cta fade-up">
              <a href="mailto:hello@beresol.eu?subject=Brubru%20-%20I%20need%20help!" className="btn--rainbow">{t('landing.clients.contactUs')}</a>
            </div>
            {/* Carousel — auto-scrolls right to left, pauses on hover, card flips to quote */}
            <div
              className="clients-carousel fade-up"
              style={{ marginTop: 'var(--spacing-2xl)' }}
              aria-label="Brubru clients carousel"
            >
              <div className="clients-carousel__track">
                {[...BRUBRU_CLIENTS, ...BRUBRU_CLIENTS].map((client, idx) => {
                  const lang = (i18n.language || 'en').slice(0, 2) as keyof ClientQuotes;
                  const quote = client.quotes[lang] || client.quotes.en;
                  return (
                    <a
                      key={`${client.id}-${idx}`}
                      href={client.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="clients-carousel__card"
                      aria-label={`${client.name}: open client website`}
                    >
                      <div className="clients-carousel__card-inner">
                        <div className="clients-carousel__face clients-carousel__face--front">
                          <img
                            src={client.logo}
                            alt={client.name}
                            className="clients-carousel__logo"
                            loading="lazy"
                          />
                        </div>
                        <div className="clients-carousel__face clients-carousel__face--back">
                          <p className="clients-carousel__quote">{quote}</p>
                          <p className="clients-carousel__attr">{client.name}</p>
                        </div>
                      </div>
                    </a>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        {/* ========== 8. CAROUSEL ========== */}
        <div className="carousel-wrapper">
          <CarouselSection />
        </div>

        {/* ========== 8b. MCP INTEGRATION ========== */}
        <section className="section mcp-section fade-up" style={{
          background: 'linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%)',
          padding: '80px 24px',
          textAlign: 'center',
        }}>
          <div style={{ maxWidth: '800px', margin: '0 auto' }}>
            <p style={{ color: '#0693e3', fontWeight: 600, fontSize: '0.9rem', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '12px' }}>
              For developers and RegTech partners
            </p>
            <h2 style={{ fontSize: '2rem', fontWeight: 700, color: '#111827', marginBottom: '16px' }}>
              The EU, structured. REST API and MCP server.
            </h2>
            <p style={{ color: '#6b7280', fontSize: '1.1rem', lineHeight: 1.7, marginBottom: '32px' }}>
              Brubru is a vertical EU data provider. The same 28,505 laws, 1,296 procedures,
              live consultation feedback, commissioner agendas, and legal-text intelligence
              that power the Brubru app are exposed as a paid <strong>REST API</strong> and as an{' '}
              <strong>MCP server</strong>. Brubru itself is the first user of its own API.
              Built for RegTech, law firms, public-affairs teams, and AI agents.
            </p>

            <div style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'center',
              flexWrap: 'wrap',
              marginBottom: '32px',
            }}>
              <a href="/api" style={{
                display: 'inline-flex', alignItems: 'center', gap: '8px',
                background: '#0693e3', color: '#fff', padding: '12px 22px',
                borderRadius: '4px', textDecoration: 'none', fontWeight: 700,
              }}>
                <span className="mdi mdi-api" /> Explore the API
              </a>
              <a href="/api/docs" style={{
                display: 'inline-flex', alignItems: 'center', gap: '8px',
                background: '#fff', color: '#0693e3', padding: '12px 22px',
                borderRadius: '4px', textDecoration: 'none', fontWeight: 700,
                border: '2px solid #0693e3',
              }}>
                <span className="mdi mdi-book-open-variant" /> API reference
              </a>
            </div>

            <p style={{ color: '#374151', fontWeight: 700, marginBottom: '12px', textAlign: 'left' }}>
              REST API endpoints (Professional subscription, 60 req/min):
            </p>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: '16px',
              textAlign: 'left',
              marginBottom: '32px',
            }}>
              {[
                { icon: 'mdi-bullhorn-variant', name: 'GET /api/v2/proprietary/brussels-lobbies', desc: 'Every Brussels-based EUTR org, ranked, with their own news' },
                { icon: 'mdi-scale-balance', name: 'GET /api/v2/legislative/eur-lex/laws', desc: '28,505 adopted EU laws, full-text + filters' },
                { icon: 'mdi-train', name: 'GET /api/v2/legislative/oeil/procedures', desc: '1,200+ legislative files in flight' },
                { icon: 'mdi-account-tie', name: 'GET /api/v2/commission/commissioners/{name}/agenda', desc: 'Live calendar for all 27 college members' },
                { icon: 'mdi-message-text', name: 'GET /api/v2/commission/consultations/.../feedback', desc: 'Live Have Your Say stakeholder input' },
                { icon: 'mdi-book-search', name: 'GET /api/v2/legislative/eur-lex/laws/{celex}/recital-article-map', desc: 'TF-IDF recital-article linker' },
              ].map((tool) => (
                <div key={tool.name} style={{
                  background: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  padding: '16px',
                }}>
                  <span className={`mdi ${tool.icon}`} style={{ color: '#0693e3', fontSize: '1.3rem', marginRight: '8px' }} />
                  <strong style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{tool.name}</strong>
                  <p style={{ color: '#6b7280', fontSize: '0.9rem', marginTop: '4px', marginBottom: 0 }}>{tool.desc}</p>
                </div>
              ))}
            </div>

            <p style={{ color: '#374151', fontWeight: 700, marginBottom: '12px', textAlign: 'left' }}>
              MCP server tools (compatible with Claude, GPT, Cursor, Windsurf):
            </p>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '16px',
              textAlign: 'left',
              marginBottom: '32px',
            }}>
              {[
                { icon: 'mdi-chat-question', name: 'ask_brubru', desc: 'Ask any EU policy question' },
                { icon: 'mdi-scale-balance', name: 'search_eu_legislation', desc: 'Search 28,505 EU laws' },
                { icon: 'mdi-book-open-variant', name: 'search_knowledge_guides', desc: '128 curated policy guides' },
                { icon: 'mdi-file-document-check', name: 'get_procedure_status', desc: 'Legislative procedure tracker' },
                { icon: 'mdi-calendar-clock', name: 'get_calendar_events', desc: 'EU institutional calendar' },
                { icon: 'mdi-library', name: 'search_eprs', desc: 'EP Research publications' },
              ].map((tool) => (
                <div key={tool.name} style={{
                  background: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  padding: '16px',
                }}>
                  <span className={`mdi ${tool.icon}`} style={{ color: '#9b51e0', fontSize: '1.3rem', marginRight: '8px' }} />
                  <strong style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{tool.name}</strong>
                  <p style={{ color: '#6b7280', fontSize: '0.9rem', marginTop: '4px', marginBottom: 0 }}>{tool.desc}</p>
                </div>
              ))}
            </div>

            <p style={{ color: '#9ca3af', fontSize: '0.85rem' }}>
              Same canonical pagination envelope across every endpoint. OpenAPI 3.1 spec at{' '}
              <a href="/api/v2/openapi.json" style={{ color: '#0693e3' }}>/api/v2/openapi.json</a>{' '}
              &mdash; importable into Postman in one click.
              <br />
              Interested in integrating? Contact <a href="mailto:hello@beresol.eu" style={{ color: '#0693e3' }}>hello@beresol.eu</a>
            </p>
          </div>
        </section>

        {/* ========== 9. ABOUT ========== */}
        <section className="about-section" id="about">
          <div className="about">
            <div className="fade-up">
              <p className="about__eyebrow">{t('landing.about.eyebrow')}</p>
              <h2
                className="about__title"
                dangerouslySetInnerHTML={{ __html: t('landing.about.title') }}
              />
              <p
                className="about__text"
                dangerouslySetInnerHTML={{ __html: t('landing.about.text1') }}
              />
              <p
                className="about__text"
                dangerouslySetInnerHTML={{ __html: t('landing.about.text2') }}
              />
              <div className="about__values">
                {ABOUT_VALUES.map((value) => (
                  <div key={value.titleKey} className="about__value">
                    <div className={`about__value-icon mdi ${value.icon}`} />
                    <h4>{t(`landing.about.${value.titleKey}`)}</h4>
                    <p>{t(`landing.about.${value.descKey}`)}</p>
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
                {t('landing.about.founderRole')}, <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">Beresol</a>
              </p>
              <p
                className="about__team-bio"
                dangerouslySetInnerHTML={{ __html: t('landing.about.founderBio') }}
              />
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
              {ctaWords.map((word, i) => (
                <span
                  key={i}
                  className="cta__word"
                  style={{ animationDelay: `${0.8 + i * 0.1}s` }}
                >
                  {word}
                </span>
              )).reduce<React.ReactNode[]>((acc, el, i) => (i === 0 ? [el] : [...acc, ' ', el]), [])}
            </h2>
            <p className="cta__text">{t('landing.cta.text')}</p>
            <Link to="/main" className="btn--rainbow btn--rainbow-outline">{t('landing.cta.button')}</Link>
          </div>
        </section>
      </main>

      {/* ========== FOOTER ========== */}
      <footer className="footer">
        <div className="footer__inner">
          <div className="footer__brand">
            <img src="/assets/beresol-logo.png" alt="Beresol" className="footer__logo" />
            <span
              className="footer__copy"
              dangerouslySetInnerHTML={{ __html: t('landing.footer.copyright') }}
            />
          </div>
          <div className="footer__links">
            <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">{t('landing.footer.aboutUs')}</a>
            <Link to="/privacy">{t('landing.footer.privacy')}</Link>
            <Link to="/terms">{t('landing.footer.terms')}</Link>
            <Link to="/cookies">{t('landing.footer.cookies')}</Link>
            <Link to="/contact">{t('landing.footer.contact')}</Link>
            <a
              href="https://www.instagram.com/beresolbv/"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Beresol on Instagram"
              className="footer__social"
            >
              <Icon path={mdiInstagram} size={0.9} />
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};
