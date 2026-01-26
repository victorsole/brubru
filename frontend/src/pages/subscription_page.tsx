// frontend/src/pages/subscription_page.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { CarouselSection } from '../components/carousel/carousel_section';
import { useSubscription } from '../hooks/use_subscription';
import './subscription_page.css';

export const SubscriptionPage = () => {
  const { t } = useTranslation();
  const { createCheckoutSession } = useSubscription();
  const [loading, setLoading] = useState<string | null>(null);

  const handleUpgrade = async (tier: 'yellow' | 'blue', period: 'monthly' | 'annual') => {
    const loadingKey = `${tier}-${period}`;
    setLoading(loadingKey);
    try {
      await createCheckoutSession(tier, period);
    } catch (err) {
      console.error('Checkout failed', err);
      alert('Failed to start checkout. Please try again.');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="subscription">
      {/* Hero Section */}
      <section className="subscription__hero">
        <video
          className="subscription__hero-video"
          autoPlay
          loop
          muted
          playsInline
        >
          <source src="/assets/jubelpark.mp4" type="video/mp4" />
        </video>
        <div className="subscription__hero-overlay"></div>
        <div className="subscription__hero-content">
          <img
            src="/assets/brubru_mainlogo.png"
            alt="Brubru Logo"
            className="subscription__hero-logo"
          />
          <h1 className="subscription__hero-title">{t('subscription.hero.title')}</h1>
          <p className="subscription__hero-subtitle">{t('subscription.hero.subtitle')}</p>
          <p className="subscription__hero-description">{t('subscription.hero.description')}</p>
        </div>
      </section>

      {/* Pricing Cards */}
      <section className="subscription__pricing">
        <div className="subscription__pricing-grid">
          {/* White Tier - Basic */}
          <div className="subscription__pricing-card">
            <div className="subscription__pricing-header">
              <div className="subscription__pricing-badge"><span className="mdi mdi-heart-outline"></span> WHITE</div>
              <h3 className="subscription__pricing-name">{t('subscription.white.name')}</h3>
              <div className="subscription__pricing-price">
                <span className="subscription__pricing-amount">{t('subscription.white.price')}</span>
                <span className="subscription__pricing-period">{t('subscription.white.period')}</span>
              </div>
              <p className="subscription__pricing-description">{t('subscription.white.description')}</p>
            </div>

            <ul className="subscription__pricing-features">
              <li><span className="mdi mdi-check"></span> {t('subscription.features.white.chat')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.white.amendments')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.white.searches')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.white.support')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.white.exports')}</li>
              <li><span className="mdi mdi-alert"></span> {t('subscription.features.white.watermark')}</li>
            </ul>

            <Link to="/signup" className="subscription__pricing-button button button-outline">
              {t('subscription.white.button')}
            </Link>
          </div>

          {/* Yellow Tier - Professional */}
          <div className="subscription__pricing-card subscription__pricing-card--featured">
            <div className="subscription__pricing-badge subscription__pricing-badge--popular">
              <span className="mdi mdi-heart subscription__pricing-badge-icon--yellow"></span> YELLOW • {t('subscription.yellow.popular').toUpperCase()}
            </div>
            <div className="subscription__pricing-header">
              <h3 className="subscription__pricing-name">{t('subscription.yellow.name')}</h3>
              <div className="subscription__pricing-price">
                <span className="subscription__pricing-amount">{t('subscription.yellow.price')}</span>
                <span className="subscription__pricing-period">{t('subscription.yellow.period')}</span>
              </div>
              <p className="subscription__pricing-savings">
                {t('subscription.yellow.annualPrice')} <span className="subscription__pricing-savings-amount">{t('subscription.yellow.annualSavings')}</span>
              </p>
              <p className="subscription__pricing-description">{t('subscription.yellow.description')}</p>
            </div>

            <ul className="subscription__pricing-features">
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.chat')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.amendments')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.searches')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.priority')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.watermark')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.exports')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.rss')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.personalization')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.yellow.support')}</li>
            </ul>

            <button
              onClick={() => handleUpgrade('yellow', 'monthly')}
              className="subscription__pricing-button button button-primary"
              disabled={loading === 'yellow-monthly'}
            >
              {loading === 'yellow-monthly' ? 'Loading...' : t('subscription.yellow.button')}
            </button>
          </div>

          {/* Blue Tier - Enterprise */}
          <div className="subscription__pricing-card">
            <div className="subscription__pricing-header">
              <div className="subscription__pricing-badge"><span className="mdi mdi-heart subscription__pricing-badge-icon--blue"></span> BLUE</div>
              <h3 className="subscription__pricing-name">{t('subscription.blue.name')}</h3>
              <div className="subscription__pricing-price">
                <span className="subscription__pricing-amount subscription__pricing-amount--custom">
                  {t('subscription.blue.price')}
                </span>
              </div>
              <p className="subscription__pricing-note">{t('subscription.blue.minUsers')}</p>
              <p className="subscription__pricing-description">{t('subscription.blue.description')}</p>
            </div>

            <ul className="subscription__pricing-features">
              <li><strong>{t('subscription.features.blue.everything')}</strong></li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.blue.multiUser')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.blue.customDomain')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.blue.whiteLabel')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.blue.sla')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.blue.training')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.blue.api')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.blue.preferences')}</li>
              <li><span className="mdi mdi-check"></span> {t('subscription.features.blue.support')}</li>
            </ul>

            <a
              href="mailto:helloberesol@gmail.com?subject=Brubru%20Blue%20-%20How%20Can%20I%20Get%20More%20Information%3F"
              className="subscription__pricing-button button button-outline"
            >
              {t('subscription.blue.button')}
            </a>
          </div>
        </div>
      </section>

      {/* Feature Comparison Table */}
      <section className="subscription__features">
        <h2 className="subscription__features-title">{t('subscription.features.title')}</h2>
        <p className="subscription__features-subtitle">{t('subscription.features.subtitle')}</p>

        <div className="subscription__features-table">
          <div className="subscription__features-header">
            <div className="subscription__features-col subscription__features-col--feature">Feature</div>
            <div className="subscription__features-col">Basic</div>
            <div className="subscription__features-col subscription__features-col--featured">Professional</div>
            <div className="subscription__features-col">Enterprise</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">AI Chat</div>
            <div className="subscription__features-col">Basic AI</div>
            <div className="subscription__features-col subscription__features-col--featured">Advanced AI</div>
            <div className="subscription__features-col">Premium AI</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">Amendments</div>
            <div className="subscription__features-col">5/month</div>
            <div className="subscription__features-col subscription__features-col--featured">Unlimited</div>
            <div className="subscription__features-col">Unlimited</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">Saved Searches</div>
            <div className="subscription__features-col">5</div>
            <div className="subscription__features-col subscription__features-col--featured">Unlimited</div>
            <div className="subscription__features-col">Unlimited</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">Export Formats</div>
            <div className="subscription__features-col">XML, HTML</div>
            <div className="subscription__features-col subscription__features-col--featured">All formats</div>
            <div className="subscription__features-col">All formats</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">Watermark</div>
            <div className="subscription__features-col">✓ Yes</div>
            <div className="subscription__features-col subscription__features-col--featured">✗ No</div>
            <div className="subscription__features-col">✗ No</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">RSS Alerts</div>
            <div className="subscription__features-col">—</div>
            <div className="subscription__features-col subscription__features-col--featured">✓</div>
            <div className="subscription__features-col">✓</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">Multi-user Teams</div>
            <div className="subscription__features-col">—</div>
            <div className="subscription__features-col subscription__features-col--featured">—</div>
            <div className="subscription__features-col">✓ 5+ users</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">Support</div>
            <div className="subscription__features-col">Community</div>
            <div className="subscription__features-col subscription__features-col--featured">Email (48h)</div>
            <div className="subscription__features-col">Dedicated (24h)</div>
          </div>

          <div className="subscription__features-row">
            <div className="subscription__features-col subscription__features-col--feature">Domain Specialisation</div>
            <div className="subscription__features-col">—</div>
            <div className="subscription__features-col subscription__features-col--featured">—</div>
            <div className="subscription__features-col">✓ Custom</div>
          </div>
        </div>
      </section>

      {/* Social Proof */}
      <section className="subscription__trust">
        <h2 className="subscription__trust-title">{t('subscription.trust.title')}</h2>
        <p className="subscription__trust-subtitle">{t('subscription.trust.subtitle')}</p>
        <div className="subscription__trust-logos">
          <a href="https://hellobo.eu" target="_blank" rel="noopener noreferrer">
            <img src="/assets/Bo_logo.png" alt="Bo" className="subscription__trust-logo" />
          </a>
          <a href="https://ferrmed.com" target="_blank" rel="noopener noreferrer">
            <img src="/assets/ferrmed.jpeg" alt="Ferrmed" className="subscription__trust-logo" />
          </a>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="subscription__faq">
        <h2 className="subscription__faq-title">{t('subscription.faq.title')}</h2>

        <div className="subscription__faq-list">
          <div className="subscription__faq-item">
            <h3 className="subscription__faq-question">{t('subscription.faq.q1')}</h3>
            <p className="subscription__faq-answer">{t('subscription.faq.a1')}</p>
          </div>

          <div className="subscription__faq-item">
            <h3 className="subscription__faq-question">{t('subscription.faq.q2')}</h3>
            <p className="subscription__faq-answer">{t('subscription.faq.a2')}</p>
          </div>

          <div className="subscription__faq-item">
            <h3 className="subscription__faq-question">{t('subscription.faq.q3')}</h3>
            <p className="subscription__faq-answer">{t('subscription.faq.a3')}</p>
          </div>

          <div className="subscription__faq-item">
            <h3 className="subscription__faq-question">{t('subscription.faq.q4')}</h3>
            <p className="subscription__faq-answer">{t('subscription.faq.a4')}</p>
          </div>

          <div className="subscription__faq-item">
            <h3 className="subscription__faq-question">{t('subscription.faq.q5')}</h3>
            <p className="subscription__faq-answer">{t('subscription.faq.a5')}</p>
          </div>

          <div className="subscription__faq-item">
            <h3 className="subscription__faq-question">{t('subscription.faq.q6')}</h3>
            <p className="subscription__faq-answer">{t('subscription.faq.a6')}</p>
          </div>
        </div>
      </section>

      {/* Carousel Section */}
      <CarouselSection />

      {/* CTA Section */}
      <section className="subscription__cta">
        <video
          className="subscription__cta-video"
          autoPlay
          muted
          loop
          playsInline
        >
          <source src="/assets/eu_flag.mp4" type="video/mp4" />
        </video>
        <div className="subscription__cta-overlay"></div>
        <div className="subscription__cta-content">
          <h2 className="subscription__cta-title">{t('subscription.cta.title')}</h2>
          <p className="subscription__cta-subtitle">{t('subscription.cta.subtitle')}</p>
          <div className="subscription__cta-actions">
            <Link to="/signup" className="button button-primary button-large">
              {t('subscription.cta.button')}
            </Link>
            <a
              href={`mailto:${t('subscription.blue.contactEmail')}`}
              className="subscription__cta-contact"
            >
              {t('subscription.cta.contact')}
            </a>
          </div>
        </div>
      </section>
    </div>
  );
};
