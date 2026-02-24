// frontend/src/pages/subscription_page.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { CarouselSection } from '../components/carousel/carousel_section';
import { useSubscription } from '../hooks/use_subscription';
import './subscription_page.css';

type BillingPeriod = 'monthly' | 'annual';

const BUNDLES = [
  { id: 'starter', plan: 'starter', color: 'green' },
  { id: 'advocate', plan: 'advocate', color: 'amber' },
  { id: 'professional', plan: 'professional', color: 'blue' },
] as const;

const MODULES = [
  { id: 'chat', plan: 'chat' },
  { id: 'bubble', plan: 'bubble' },
  { id: 'amendator', plan: 'amendator' },
  { id: 'comply', plan: 'comply' },
  { id: 'tenderator', plan: 'tenderator' },
] as const;

const FEATURE_ROWS = [
  'chat', 'amendments', 'rss', 'predictions', 'comply', 'tenderator', 'exports', 'support',
] as const;

export const SubscriptionPage = () => {
  const { t } = useTranslation();
  const { createCheckoutSession } = useSubscription();
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>('monthly');
  const [loading, setLoading] = useState<string | null>(null);

  const handleCheckout = async (plan: string) => {
    const loadingKey = `${plan}-${billingPeriod}`;
    setLoading(loadingKey);
    try {
      await createCheckoutSession(plan, billingPeriod);
    } catch (err) {
      console.error('Checkout failed', err);
      alert('Failed to start checkout. Please try again.');
    } finally {
      setLoading(null);
    }
  };

  const isAnnual = billingPeriod === 'annual';

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

      {/* Billing Toggle */}
      <section className="subscription__toggle-section">
        <div className="subscription__toggle">
          <button
            className={`subscription__toggle-btn${!isAnnual ? ' subscription__toggle-btn--active' : ''}`}
            onClick={() => setBillingPeriod('monthly')}
          >
            {t('subscription.toggle.monthly')}
          </button>
          <button
            className={`subscription__toggle-btn${isAnnual ? ' subscription__toggle-btn--active' : ''}`}
            onClick={() => setBillingPeriod('annual')}
          >
            {t('subscription.toggle.annual')}
            <span className="subscription__toggle-save">{t('subscription.toggle.saveTag')}</span>
          </button>
        </div>
      </section>

      {/* Bundles Section */}
      <section className="subscription__pricing">
        <h2 className="subscription__section-title">{t('subscription.bundles.title')}</h2>
        <p className="subscription__section-subtitle">{t('subscription.bundles.subtitle')}</p>

        <div className="subscription__pricing-grid subscription__pricing-grid--bundles">
          {BUNDLES.map((bundle) => {
            const isFeatured = bundle.id === 'advocate';
            const isProfessional = bundle.id === 'professional';
            const loadingKey = `${bundle.plan}-${billingPeriod}`;
            const price = isAnnual
              ? t(`subscription.${bundle.id}.priceAnnual`)
              : t(`subscription.${bundle.id}.priceMonthly`);

            return (
              <div
                key={bundle.id}
                className={`subscription__pricing-card${isFeatured ? ' subscription__pricing-card--featured' : ''}${isProfessional ? ' subscription__pricing-card--professional' : ''}`}
              >
                <div className={`subscription__pricing-badge subscription__pricing-badge--${bundle.color}`}>
                  {t(`subscription.${bundle.id}.badge`)}
                </div>
                <div className="subscription__pricing-header">
                  <h3 className="subscription__pricing-name">{t(`subscription.${bundle.id}.name`)}</h3>
                  <div className="subscription__pricing-price">
                    <span className="subscription__pricing-currency">&euro;</span>
                    <span className="subscription__pricing-amount">{price}</span>
                    <span className="subscription__pricing-period">/month</span>
                  </div>
                  {isAnnual && (
                    <p className="subscription__pricing-savings">
                      &euro;{t(`subscription.${bundle.id}.annualTotal`)}/year
                    </p>
                  )}
                  <p className="subscription__pricing-includes">{t(`subscription.${bundle.id}.includes`)}</p>
                  <p className="subscription__pricing-description">{t(`subscription.${bundle.id}.description`)}</p>
                </div>

                <ul className="subscription__pricing-features">
                  {['f1', 'f2', 'f3', 'f4', 'f5', 'f6'].map((fKey) => {
                    const val = t(`subscription.${bundle.id}.${fKey}`, '');
                    if (!val) return null;
                    return (
                      <li key={fKey}><span className="mdi mdi-check"></span> {val}</li>
                    );
                  })}
                </ul>

                <button
                  onClick={() => handleCheckout(bundle.plan)}
                  className={`subscription__pricing-button button ${isFeatured || isProfessional ? 'button-primary' : 'button-outline'}`}
                  disabled={loading === loadingKey}
                >
                  {loading === loadingKey ? 'Loading...' : t(`subscription.${bundle.id}.button`)}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* EP Plan Banner */}
      <section className="subscription__ep-banner">
        <div className="subscription__ep-banner-content">
          <div className="subscription__ep-banner-info">
            <div className="subscription__ep-banner-badge">{t('subscription.ep.badge')}</div>
            <h3 className="subscription__ep-banner-title">{t('subscription.ep.name')}</h3>
            <p className="subscription__ep-banner-description">{t('subscription.ep.description')}</p>
            <div className="subscription__ep-banner-features">
              {['f1', 'f2', 'f3', 'f4', 'f5'].map((fKey) => (
                <span key={fKey} className="subscription__ep-feature">
                  <span className="mdi mdi-check"></span> {t(`subscription.ep.${fKey}`)}
                </span>
              ))}
            </div>
            <p className="subscription__ep-banner-note">{t('subscription.ep.note')}</p>
          </div>
          <div className="subscription__ep-banner-pricing">
            <div className="subscription__pricing-price">
              <span className="subscription__pricing-currency">&euro;</span>
              <span className="subscription__pricing-amount">
                {isAnnual ? t('subscription.ep.priceAnnual') : t('subscription.ep.priceMonthly')}
              </span>
              <span className="subscription__pricing-period">/month</span>
            </div>
            {isAnnual && (
              <p className="subscription__pricing-savings">&euro;{t('subscription.ep.annualTotal')}/year</p>
            )}
            <button
              onClick={() => handleCheckout('ep')}
              className="subscription__pricing-button button button-primary"
              disabled={loading === `ep-${billingPeriod}`}
            >
              {loading === `ep-${billingPeriod}` ? 'Loading...' : t('subscription.ep.button')}
            </button>
          </div>
        </div>
      </section>

      {/* Individual Modules Section */}
      <section className="subscription__modules">
        <h2 className="subscription__section-title">{t('subscription.modules.title')}</h2>
        <p className="subscription__section-subtitle">{t('subscription.modules.subtitle')}</p>

        <div className="subscription__pricing-grid subscription__pricing-grid--modules">
          {MODULES.map((mod) => {
            const loadingKey = `${mod.plan}-${billingPeriod}`;
            return (
              <div key={mod.id} className="subscription__module-card">
                <h4 className="subscription__module-name">{t(`subscription.module.${mod.id}.name`)}</h4>
                <div className="subscription__module-price">
                  <span className="subscription__pricing-currency">&euro;</span>
                  <span className="subscription__pricing-amount subscription__pricing-amount--module">
                    {t(`subscription.module.${mod.id}.price`)}
                  </span>
                  <span className="subscription__pricing-period">/month</span>
                </div>
                <p className="subscription__module-description">{t(`subscription.module.${mod.id}.description`)}</p>
                <button
                  onClick={() => handleCheckout(mod.plan)}
                  className="subscription__pricing-button button button-outline"
                  disabled={loading === loadingKey}
                >
                  {loading === loadingKey ? 'Loading...' : 'Subscribe'}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* Feature Comparison Table */}
      <section className="subscription__features">
        <h2 className="subscription__features-title">{t('subscription.features.title')}</h2>
        <p className="subscription__features-subtitle">{t('subscription.features.subtitle')}</p>

        <div className="subscription__features-table">
          <div className="subscription__features-header">
            <div className="subscription__features-col subscription__features-col--feature">
              {t('subscription.features.columns.feature')}
            </div>
            <div className="subscription__features-col">
              {t('subscription.features.columns.free')}
            </div>
            <div className="subscription__features-col">
              {t('subscription.features.columns.starter')}
            </div>
            <div className="subscription__features-col subscription__features-col--featured">
              {t('subscription.features.columns.advocate')}
            </div>
            <div className="subscription__features-col">
              {t('subscription.features.columns.professional')}
            </div>
          </div>

          {FEATURE_ROWS.map((row) => (
            <div key={row} className="subscription__features-row">
              <div className="subscription__features-col subscription__features-col--feature">
                {t(`subscription.features.rows.${row}`)}
              </div>
              <div className="subscription__features-col">
                {t(`subscription.features.rows.${row}Free`)}
              </div>
              <div className="subscription__features-col">
                {t(`subscription.features.rows.${row}Starter`)}
              </div>
              <div className="subscription__features-col subscription__features-col--featured">
                {t(`subscription.features.rows.${row}Advocate`)}
              </div>
              <div className="subscription__features-col">
                {t(`subscription.features.rows.${row}Professional`)}
              </div>
            </div>
          ))}
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
          {['1', '2', '3', '4', '5', '6'].map((n) => (
            <div key={n} className="subscription__faq-item">
              <h3 className="subscription__faq-question">{t(`subscription.faq.q${n}`)}</h3>
              <p className="subscription__faq-answer">{t(`subscription.faq.a${n}`)}</p>
            </div>
          ))}
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
              href={`mailto:${t('subscription.contactEmail')}`}
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
