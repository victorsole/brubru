// Feature preview page shown to unauthenticated users trying to access protected pages
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiChatProcessingOutline,
  mdiGlassMugVariant,
  mdiFileEditOutline,
  mdiScaleBalance,
  mdiPiggyBankOutline,
  mdiCheck,
  mdiRocketLaunchOutline,
  mdiShieldCheckOutline,
  mdiSpeedometer,
  mdiAccountGroupOutline,
  mdiFileDocumentOutline,
  mdiMagnify,
  mdiBellOutline,
  mdiChartLineVariant,
  mdiTextBoxSearchOutline,
  mdiXml,
  mdiClipboardTextOutline,
  mdiCurrencyEur
} from '@mdi/js';
import './feature_preview_page.css';

interface FeatureConfig {
  id: string;
  icon: string;
  color: string;
  colorValue: string;
  title: string;
  subtitle: string;
  description: string;
  screenshot: string;
  highlights: Array<{
    icon: string;
    title: string;
    description: string;
  }>;
}

const FEATURE_CONFIGS: Record<string, FeatureConfig> = {
  '/main': {
    id: 'main',
    icon: mdiChatProcessingOutline,
    color: 'blue',
    colorValue: '#0693e3',
    title: 'AI Policy Assistant',
    subtitle: 'Your EU legislation expert, available 24/7',
    description: 'Chat with an AI trained on EU law, procedures, institutions, and policy. Get instant answers about regulations, directives, MEPs, committees, and more.',
    screenshot: '/assets/brubru_mainlogo.png',
    highlights: [
      { icon: mdiMagnify, title: 'Smart Search', description: 'Search across thousands of EU laws and documents' },
      { icon: mdiAccountGroupOutline, title: 'MEP Profiles', description: 'Access detailed profiles of all Members of the European Parliament' },
      { icon: mdiFileDocumentOutline, title: 'Document Analysis', description: 'Upload and analyse legislative documents with AI assistance' },
      { icon: mdiSpeedometer, title: 'Instant Answers', description: 'Get accurate answers in seconds, not hours' }
    ]
  },
  '/my-eu-bubble': {
    id: 'my-eu-bubble',
    icon: mdiGlassMugVariant,
    color: 'purple',
    colorValue: '#9b51e0',
    title: 'My EU Bubble',
    subtitle: 'Your personalised EU policy dashboard',
    description: 'Track legislative files, monitor RSS feeds from EU institutions, and stay on top of policy developments that matter to you.',
    screenshot: '/assets/brubru_purple.png',
    highlights: [
      { icon: mdiBellOutline, title: 'Custom Alerts', description: 'Get notified when tracked files are updated' },
      { icon: mdiChartLineVariant, title: 'Legislative Train', description: 'Track proposals through the legislative process' },
      { icon: mdiTextBoxSearchOutline, title: 'RSS Aggregation', description: 'All EU institutional feeds in one place' },
      { icon: mdiFileDocumentOutline, title: 'Document Generator', description: 'Create position papers, briefings, and talking points' }
    ]
  },
  '/amendator': {
    id: 'amendator',
    icon: mdiFileEditOutline,
    color: 'green',
    colorValue: '#059669',
    title: 'Brubru Amendator',
    subtitle: 'Professional amendment drafting made simple',
    description: 'Draft legislative amendments with AI assistance. Export in multiple formats including Akoma Ntoso XML, Word, and PDF.',
    screenshot: '/assets/brubru_amendator.png',
    highlights: [
      { icon: mdiXml, title: 'Akoma Ntoso XML', description: 'Industry-standard legislative markup format' },
      { icon: mdiChatProcessingOutline, title: 'AI Suggestions', description: 'Get intelligent drafting recommendations' },
      { icon: mdiFileDocumentOutline, title: 'Multiple Exports', description: 'Export to Word, PDF, HTML, and XML' },
      { icon: mdiClipboardTextOutline, title: 'Template Library', description: 'Start from proven amendment templates' }
    ]
  },
  '/eulawcomply': {
    id: 'eulawcomply',
    icon: mdiScaleBalance,
    color: 'silver',
    colorValue: '#6b7280',
    title: 'EU Law Comply',
    subtitle: 'Compliance gap analysis powered by AI',
    description: 'Check your organisation\'s compliance with EU regulations. Identify gaps and get actionable recommendations.',
    screenshot: '/assets/brubru_eulawcomply.png',
    highlights: [
      { icon: mdiShieldCheckOutline, title: 'Gap Analysis', description: 'Identify compliance gaps automatically' },
      { icon: mdiFileDocumentOutline, title: 'Regulation Library', description: 'Access all major EU regulations and directives' },
      { icon: mdiChartLineVariant, title: 'Risk Assessment', description: 'Understand your compliance risk profile' },
      { icon: mdiClipboardTextOutline, title: 'Action Plans', description: 'Get step-by-step remediation guidance' }
    ]
  },
  '/tenderator': {
    id: 'tenderator',
    icon: mdiPiggyBankOutline,
    color: 'gold',
    colorValue: '#d97706',
    title: 'Tenderator',
    subtitle: 'EU tender matching and intelligence',
    description: 'Find EU funding opportunities that match your profile. Get AI-powered tender analysis and application assistance.',
    screenshot: '/assets/brubru_tenderator.png',
    highlights: [
      { icon: mdiCurrencyEur, title: 'Funding Finder', description: 'Discover EU grants and tenders matched to your needs' },
      { icon: mdiMagnify, title: 'Smart Matching', description: 'AI finds opportunities you might have missed' },
      { icon: mdiBellOutline, title: 'Deadline Alerts', description: 'Never miss an application deadline' },
      { icon: mdiFileDocumentOutline, title: 'Application Help', description: 'AI assistance for tender applications' }
    ]
  }
};

// Default config for pages without specific feature content
const DEFAULT_CONFIG: FeatureConfig = {
  id: 'default',
  icon: mdiRocketLaunchOutline,
  color: 'blue',
  colorValue: '#0693e3',
  title: 'Welcome to Brubru',
  subtitle: 'Your AI-powered EU policy assistant',
  description: 'Access powerful tools for EU legislation research, amendment drafting, and policy advocacy. Sign up to unlock all features.',
  screenshot: '/assets/brubru_nochips.png',
  highlights: [
    { icon: mdiChatProcessingOutline, title: 'AI Assistant', description: 'Chat with an EU policy expert' },
    { icon: mdiFileEditOutline, title: 'Amendment Drafting', description: 'Professional legislative tools' },
    { icon: mdiGlassMugVariant, title: 'Policy Dashboard', description: 'Track what matters to you' },
    { icon: mdiScaleBalance, title: 'Compliance Tools', description: 'Stay compliant with EU law' }
  ]
};

export const FeaturePreviewPage = () => {
  const location = useLocation();
  const { t } = useTranslation();

  // Get the appropriate feature config based on the current path
  const config = FEATURE_CONFIGS[location.pathname] || DEFAULT_CONFIG;

  return (
    <div className="feature-preview">
      {/* Animated background gradient */}
      <div
        className="feature-preview__bg"
        style={{ '--accent-color': config.colorValue } as React.CSSProperties}
      />

      {/* Main content */}
      <div className="feature-preview__container">
        {/* Header with logo */}
        <div className="feature-preview__header">
          <Link to="/" className="feature-preview__logo">
            <img src="/assets/brubru_mainlogo.png" alt="Brubru" />
          </Link>
        </div>

        {/* Hero section */}
        <div className="feature-preview__hero">
          <div className="feature-preview__hero-content">
            <div
              className={`feature-preview__icon-badge feature-preview__icon-badge--${config.color}`}
            >
              <Icon path={config.icon} size={1.5} />
            </div>

            <h1 className="feature-preview__title">{config.title}</h1>
            <p className="feature-preview__subtitle">{config.subtitle}</p>
            <p className="feature-preview__description">{config.description}</p>

            {/* CTA buttons */}
            <div className="feature-preview__cta">
              <Link to="/signup" className="feature-preview__btn feature-preview__btn--primary">
                <Icon path={mdiRocketLaunchOutline} size={0.9} />
                {t('featurePreview.startFreeTrial', 'Start Free Trial')}
              </Link>
              <Link to="/login" className="feature-preview__btn feature-preview__btn--secondary">
                {t('featurePreview.logIn', 'Log In')}
              </Link>
            </div>
          </div>

          {/* Screenshot preview with blur effect */}
          <div className="feature-preview__screenshot-wrapper">
            <div className="feature-preview__screenshot-blur" />
            <img
              src={config.screenshot}
              alt={`${config.title} preview`}
              className="feature-preview__screenshot"
            />
            <div className="feature-preview__screenshot-overlay">
              <div className="feature-preview__lock-badge">
                <Icon path={mdiShieldCheckOutline} size={1} />
                <span>{t('featurePreview.signUpToUnlock', 'Sign up to unlock')}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Feature highlights */}
        <div className="feature-preview__highlights">
          <h2 className="feature-preview__highlights-title">
            {t('featurePreview.whatYoullGet', "What you'll get")}
          </h2>
          <div className="feature-preview__highlights-grid">
            {config.highlights.map((highlight, index) => (
              <div
                key={index}
                className="feature-preview__highlight-card"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div
                  className={`feature-preview__highlight-icon feature-preview__highlight-icon--${config.color}`}
                >
                  <Icon path={highlight.icon} size={1} />
                </div>
                <h3>{highlight.title}</h3>
                <p>{highlight.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Trust indicators */}
        <div className="feature-preview__trust">
          <div className="feature-preview__trust-item">
            <Icon path={mdiCheck} size={0.8} />
            <span>{t('featurePreview.noCardRequired', 'No credit card required')}</span>
          </div>
          <div className="feature-preview__trust-item">
            <Icon path={mdiCheck} size={0.8} />
            <span>{t('featurePreview.freeTrialDays', '14-day free trial')}</span>
          </div>
          <div className="feature-preview__trust-item">
            <Icon path={mdiCheck} size={0.8} />
            <span>{t('featurePreview.cancelAnytime', 'Cancel anytime')}</span>
          </div>
        </div>

        {/* Bottom CTA */}
        <div className="feature-preview__bottom-cta">
          <p>{t('featurePreview.alreadyHaveAccount', 'Already have an account?')}</p>
          <Link to="/login" className="feature-preview__link">
            {t('featurePreview.logInHere', 'Log in here')}
          </Link>
        </div>

        {/* Footer */}
        <footer className="feature-preview__footer">
          <p>
            <a href="https://beresol.eu" target="_blank" rel="noopener noreferrer">
              Beresol BV
            </a>
            {' '}&copy; {new Date().getFullYear()}
          </p>
          <div className="feature-preview__footer-links">
            <Link to="/privacy">{t('footer.privacy', 'Privacy')}</Link>
            <Link to="/terms">{t('footer.terms', 'Terms')}</Link>
            <Link to="/contact">{t('footer.contact', 'Contact')}</Link>
          </div>
        </footer>
      </div>
    </div>
  );
};
