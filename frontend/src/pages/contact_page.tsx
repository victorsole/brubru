// frontend/src/pages/contact_page.tsx
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiInstagram } from '@mdi/js';
import './policy_pages.css';

export const ContactPage = () => {
  const { t } = useTranslation();

  return (
    <div className="policy-page">
      <div className="policy-page__container">
        <h1 className="policy-page__title">{t('contact.pageTitle')}</h1>

        <section className="policy-page__section">
          <h2>{t('contact.getInTouch')}</h2>
          <p>{t('contact.getInTouchBody')}</p>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.generalInquiries')}</h2>
          <div className="policy-page__contact-box">
            <p><strong>{t('contact.emailLabel')}</strong> <a href="mailto:hello@beresol.eu" className="policy-page__link">hello@beresol.eu</a></p>
            <p><strong>{t('contact.websiteLabel')}</strong> <a href="https://brubru.beresol.eu" target="_blank" rel="noopener noreferrer" className="policy-page__link">brubru.beresol.eu</a></p>
            <p><strong>{t('contact.companyLabel')}</strong> <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer" className="policy-page__link">Beresol BV</a></p>
            <p>
              <strong>Instagram:</strong>{' '}
              <a
                href="https://www.instagram.com/beresolbv/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Beresol on Instagram"
                className="policy-page__link policy-page__link--social"
              >
                <Icon path={mdiInstagram} size={0.85} style={{ verticalAlign: 'middle', marginRight: '0.35rem' }} />
                @beresolbv
              </a>
            </p>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.support')}</h2>

          <div className="policy-page__feature">
            <h3>{t('contact.whiteTitle')}</h3>
            <p>{t('contact.whiteBody')}</p>
          </div>

          <div className="policy-page__feature">
            <h3>{t('contact.starterTitle')}</h3>
            <p>{t('contact.starterBody')}</p>
          </div>

          <div className="policy-page__feature">
            <h3>{t('contact.proTitle')}</h3>
            <p>{t('contact.proBody')}</p>
          </div>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.salesTitle')}</h2>
          <p>{t('contact.salesBody')}</p>
          <p>
            <strong>{t('contact.salesContact')}</strong> <a href="mailto:hello@beresol.eu?subject=Enterprise%20Inquiry" className="policy-page__link">hello@beresol.eu</a>
          </p>
          <p className="policy-page__note">{t('contact.salesNote')}</p>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.partnershipsTitle')}</h2>
          <p>{t('contact.partnershipsBody')}</p>
          <p>
            <strong>{t('contact.partnershipsContact')}</strong> <a href="mailto:hello@beresol.eu?subject=Partnership%20Opportunity" className="policy-page__link">hello@beresol.eu</a>
          </p>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.pressTitle')}</h2>
          <p>{t('contact.pressBody')}</p>
          <p>
            <strong>{t('contact.pressContact')}</strong> <a href="mailto:hello@beresol.eu?subject=Press%20Inquiry" className="policy-page__link">hello@beresol.eu</a>
          </p>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.privacyTitle')}</h2>
          <p>{t('contact.privacyBody')}</p>
          <p>
            <strong>{t('contact.privacyContact')}</strong> <a href="mailto:hello@beresol.eu?subject=Privacy%20Inquiry" className="policy-page__link">hello@beresol.eu</a>
          </p>
          <p>
            {t('contact.privacyReview')} <a href="/privacy" className="policy-page__link">{t('contact.privacyPolicy')}</a>.
          </p>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.bugsTitle')}</h2>
          <p>{t('contact.bugsBody')}</p>
          <p>
            <strong>{t('contact.bugsContact')}</strong> <a href="mailto:hello@beresol.eu?subject=Bug%20Report" className="policy-page__link">hello@beresol.eu</a>
          </p>
          <p className="policy-page__note">{t('contact.bugsNote')}</p>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.addressTitle')}</h2>
          <p style={{ whiteSpace: 'pre-line' }}>
            <strong>{t('contact.addressLines')}</strong>
          </p>
          <p className="policy-page__note">{t('contact.addressNote')}</p>
        </section>

        <section className="policy-page__section">
          <h2>{t('contact.responseTitle')}</h2>
          <ul>
            <li>{t('contact.responseGeneral')}</li>
            <li>{t('contact.responseStarter')}</li>
            <li>{t('contact.responseProfessional')}</li>
            <li>{t('contact.responseEnterprise')}</li>
            <li>{t('contact.responsePrivacy')}</li>
          </ul>
        </section>

        <div className="policy-page__footer">
          <p>{t('contact.lastUpdated')}</p>
        </div>
      </div>
    </div>
  );
};
