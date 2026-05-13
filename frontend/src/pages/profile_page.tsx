// frontend/src/pages/profile_page.tsx
import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/use_auth';
import { useSubscription } from '../hooks/use_subscription';
import { Link } from 'react-router-dom';
import { PolicyPreferencesSelector } from '../components/profile/policy_preferences_selector';
import { BackgroundSelector } from '../components/profile/background_selector';
import { SectorsSelector } from '../components/profile/sectors_selector';
import { FeedbackForm } from '../components/feedback/feedback_form';
import { TrainerStarRing, TrainerShieldBadge, TrainerNameGlow } from '../components/shared/trainer_badge';
import Icon from '@mdi/react';
import {
  mdiViewDashboardOutline,
  mdiAccountOutline,
  mdiCreditCardOutline,
  mdiBookmarkMultipleOutline,
  mdiBriefcaseOutline,
  mdiImageOutline,
  mdiMessageTextOutline,
  mdiCogOutline,
  mdiShieldCrownOutline,
  mdiFileEditOutline,
  mdiApi,
  mdiCalendarClock,
  mdiStarOutline,
  mdiOpenInNew,
  mdiArrowUpBold,
  mdiCheck,
  mdiDeleteOutline,
  mdiLogout,
} from '@mdi/js';
import './profile_page.css';

type Section = 'overview' | 'personal' | 'billing' | 'policies' | 'sectors' | 'background' | 'feedback' | 'account';

interface NavItem {
  id: Section;
  label: string;
  icon: string;
}

const EU_COUNTRIES: { code: string; name: string }[] = [
  { code: 'AT', name: 'Austria' },
  { code: 'BE', name: 'Belgium' },
  { code: 'BG', name: 'Bulgaria' },
  { code: 'HR', name: 'Croatia' },
  { code: 'CY', name: 'Cyprus' },
  { code: 'CZ', name: 'Czech Republic' },
  { code: 'DK', name: 'Denmark' },
  { code: 'EE', name: 'Estonia' },
  { code: 'FI', name: 'Finland' },
  { code: 'FR', name: 'France' },
  { code: 'DE', name: 'Germany' },
  { code: 'GR', name: 'Greece' },
  { code: 'HU', name: 'Hungary' },
  { code: 'IE', name: 'Ireland' },
  { code: 'IT', name: 'Italy' },
  { code: 'LV', name: 'Latvia' },
  { code: 'LT', name: 'Lithuania' },
  { code: 'LU', name: 'Luxembourg' },
  { code: 'MT', name: 'Malta' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'PL', name: 'Poland' },
  { code: 'PT', name: 'Portugal' },
  { code: 'RO', name: 'Romania' },
  { code: 'SK', name: 'Slovakia' },
  { code: 'SI', name: 'Slovenia' },
  { code: 'ES', name: 'Spain' },
  { code: 'SE', name: 'Sweden' },
];

export const ProfilePage = () => {
  const { t } = useTranslation();
  const { user, updateProfile, logout } = useAuth();
  const { usage, tiers, fetchUsage, fetchTiers, createPortalSession } = useSubscription();

  const [activeSection, setActiveSection] = useState<Section>('overview');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    full_name: user?.full_name || '',
    organization: user?.organization || '',
    country: user?.country || '',
    role_title: user?.role_title || '',
  });
  const [policyInterests, setPolicyInterests] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [backgroundPreference, setBackgroundPreference] = useState<string>('default');
  const [saved, setSaved] = useState(false);
  const [preferencesSaved, setPreferencesSaved] = useState(false);
  const [sectorsSaved, setSectorsSaved] = useState(false);
  const [backgroundSaved, setBackgroundSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [preferencesLoading, setPreferencesLoading] = useState(false);
  const [sectorsLoading, setSectorsLoading] = useState(false);
  const [backgroundLoading, setBackgroundLoading] = useState(false);

  useEffect(() => {
    if (user?.policy_interests) {
      try {
        const interests = typeof user.policy_interests === 'string'
          ? JSON.parse(user.policy_interests)
          : user.policy_interests;
        setPolicyInterests(Array.isArray(interests) ? interests : []);
      } catch {
        setPolicyInterests([]);
      }
    }
    if (user?.sectors) {
      const arr = Array.isArray(user.sectors) ? user.sectors : [];
      setSectors(arr);
    } else {
      setSectors([]);
    }
    if (user?.background_preference) {
      setBackgroundPreference(user.background_preference);
    }
    setFormData((prev) => ({
      ...prev,
      role_title: user?.role_title || prev.role_title,
    }));
  }, [user]);

  useEffect(() => {
    fetchUsage();
    fetchTiers();
  }, []);

  const currentTier = tiers?.find(t => t.id === user?.subscription_tier);

  const accountAge = useMemo(() => {
    if (!user?.created_at) return 0;
    const created = new Date(user.created_at);
    const now = new Date();
    return Math.floor((now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24));
  }, [user?.created_at]);

  const navItems: NavItem[] = [
    { id: 'overview', label: 'Overview', icon: mdiViewDashboardOutline },
    { id: 'personal', label: t('profile.personalInfo'), icon: mdiAccountOutline },
    { id: 'billing', label: 'Billing', icon: mdiCreditCardOutline },
    { id: 'policies', label: t('profile.policyInterests'), icon: mdiBookmarkMultipleOutline },
    { id: 'sectors', label: 'Sectors', icon: mdiBriefcaseOutline },
    { id: 'background', label: 'Background', icon: mdiImageOutline },
    { id: 'feedback', label: t('profile.feedback'), icon: mdiMessageTextOutline },
    { id: 'account', label: t('profile.accountSettings'), icon: mdiCogOutline },
  ];

  // Handlers
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await updateProfile(formData);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update profile', err);
    } finally {
      setLoading(false);
    }
  };

  const handlePreferencesUpdate = async (policies: string[]) => {
    setPolicyInterests(policies);
    setPreferencesLoading(true);
    try {
      await updateProfile({ policy_interests: JSON.stringify(policies) });
      setPreferencesSaved(true);
      setTimeout(() => setPreferencesSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update preferences', err);
    } finally {
      setPreferencesLoading(false);
    }
  };

  const handleSectorsUpdate = async (next: string[]) => {
    setSectors(next);
    setSectorsLoading(true);
    try {
      await updateProfile({ sectors: next });
      setSectorsSaved(true);
      setTimeout(() => setSectorsSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update sectors', err);
    } finally {
      setSectorsLoading(false);
    }
  };

  const handleBackgroundUpdate = async (background: string) => {
    setBackgroundPreference(background);
    setBackgroundLoading(true);
    try {
      await updateProfile({ background_preference: background });
      setBackgroundSaved(true);
      setTimeout(() => setBackgroundSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update background', err);
    } finally {
      setBackgroundLoading(false);
    }
  };

  const handleNavClick = (section: Section) => {
    setActiveSection(section);
    setMobileMenuOpen(false);
  };

  const userInitials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.email?.slice(0, 2).toUpperCase() || '??';

  const getUsagePercentage = (used: number, limit: number) => {
    if (limit === -1) return 0; // unlimited
    if (limit === 0) return 100;
    return Math.min(100, Math.round((used / limit) * 100));
  };

  const getProgressColour = (pct: number) => {
    if (pct >= 90) return 'red';
    if (pct >= 70) return 'amber';
    return 'green';
  };

  // ===== RENDER SECTIONS =====

  const renderOverview = () => (
    <>
      <div className="profile-dashboard__welcome">
        <h2 className="profile-dashboard__welcome-title">
          Welcome back, {user?.full_name?.split(' ')[0] || 'there'}
        </h2>
        <p className="profile-dashboard__welcome-text">
          Manage your profile, subscription, and policy preferences from your personal dashboard.
        </p>
      </div>

      <div className="profile-dashboard__stats">
        <div className="profile-dashboard__stat-card">
          <div className="profile-dashboard__stat-content">
            <p className="profile-dashboard__stat-label">Subscription</p>
            <p className="profile-dashboard__stat-value">
              <span className={`profile-dashboard__tier-badge profile-dashboard__tier-badge--${user?.subscription_tier || 'white'}`}>
                {user?.is_trainer ? 'Brubru Trainer' : (currentTier?.name || 'White (Basic)')}
              </span>
            </p>
          </div>
          <div className="profile-dashboard__stat-icon profile-dashboard__stat-icon--blue">
            <Icon path={mdiStarOutline} size={1} />
          </div>
        </div>

        <div className="profile-dashboard__stat-card">
          <div className="profile-dashboard__stat-content">
            <p className="profile-dashboard__stat-label">{t('profile.amendmentsMonth')}</p>
            <p className="profile-dashboard__stat-value">
              {usage?.amendments_used ?? 0}
              {usage?.amendments_limit !== -1 && <small style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}> / {usage?.amendments_limit}</small>}
            </p>
            {usage?.amendments_limit === -1 && (
              <span className="profile-dashboard__stat-badge profile-dashboard__stat-badge--green">
                {t('profile.unlimited')}
              </span>
            )}
          </div>
          <div className="profile-dashboard__stat-icon profile-dashboard__stat-icon--green">
            <Icon path={mdiFileEditOutline} size={1} />
          </div>
        </div>

        <div className="profile-dashboard__stat-card">
          <div className="profile-dashboard__stat-content">
            <p className="profile-dashboard__stat-label">{t('profile.apiCalls')}</p>
            <p className="profile-dashboard__stat-value">
              {usage?.api_calls_used ?? 0}
              {usage?.api_calls_limit !== -1 && <small style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}> / {usage?.api_calls_limit}</small>}
            </p>
            {usage?.api_calls_limit === -1 && (
              <span className="profile-dashboard__stat-badge profile-dashboard__stat-badge--purple">
                {t('profile.unlimited')}
              </span>
            )}
          </div>
          <div className="profile-dashboard__stat-icon profile-dashboard__stat-icon--purple">
            <Icon path={mdiApi} size={1} />
          </div>
        </div>

        <div className="profile-dashboard__stat-card">
          <div className="profile-dashboard__stat-content">
            <p className="profile-dashboard__stat-label">Member Since</p>
            <p className="profile-dashboard__stat-value">{accountAge}<small style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}> days</small></p>
            <span className="profile-dashboard__stat-badge profile-dashboard__stat-badge--amber">
              {user?.created_at ? new Date(user.created_at).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }) : ''}
            </span>
          </div>
          <div className="profile-dashboard__stat-icon profile-dashboard__stat-icon--amber">
            <Icon path={mdiCalendarClock} size={1} />
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="profile-dashboard__card">
        <div className="profile-dashboard__card-header">
          <h3 className="profile-dashboard__card-title">Quick Actions</h3>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            className="profile-dashboard__btn profile-dashboard__btn--secondary"
            onClick={() => setActiveSection('personal')}
          >
            <Icon path={mdiAccountOutline} size={0.8} />
            Edit Profile
          </button>
          <button
            className="profile-dashboard__btn profile-dashboard__btn--secondary"
            onClick={() => setActiveSection('billing')}
          >
            <Icon path={mdiCreditCardOutline} size={0.8} />
            Billing
          </button>
          <button
            className="profile-dashboard__btn profile-dashboard__btn--secondary"
            onClick={() => setActiveSection('policies')}
          >
            <Icon path={mdiBookmarkMultipleOutline} size={0.8} />
            Policy Interests ({policyInterests.length})
          </button>
          {user?.subscription_tier !== 'blue' && (
            <Link to="/#pricing" className="profile-dashboard__btn profile-dashboard__btn--upgrade">
              <Icon path={mdiArrowUpBold} size={0.8} />
              {t('profile.upgrade')}
            </Link>
          )}
        </div>
      </div>
    </>
  );

  const renderPersonalInfo = () => (
    <div className="profile-dashboard__card">
      <div className="profile-dashboard__card-header">
        <h3 className="profile-dashboard__card-title">{t('profile.personalInfo')}</h3>
        {saved && (
          <span className="profile-dashboard__saved">
            <Icon path={mdiCheck} size={0.7} /> {t('profile.saved')}
          </span>
        )}
      </div>
      <form onSubmit={handleSubmit} className="profile-dashboard__form">
        <div className="profile-dashboard__field">
          <label htmlFor="email">{t('profile.email')}</label>
          <input id="email" type="email" value={user?.email || ''} disabled />
          <small>{t('profile.emailNote')}</small>
        </div>

        <div className="profile-dashboard__field">
          <label htmlFor="full_name">{t('profile.fullName')}</label>
          <input
            id="full_name"
            name="full_name"
            type="text"
            value={formData.full_name}
            onChange={handleChange}
            disabled={loading}
          />
        </div>

        <div className="profile-dashboard__field">
          <label htmlFor="organization">{t('profile.organisation')}</label>
          <input
            id="organization"
            name="organization"
            type="text"
            value={formData.organization}
            onChange={handleChange}
            disabled={loading}
          />
        </div>

        <div className="profile-dashboard__field">
          <label htmlFor="role_title">Role / Title</label>
          <input
            id="role_title"
            name="role_title"
            type="text"
            value={formData.role_title}
            onChange={handleChange}
            disabled={loading}
            placeholder="e.g. Policy officer, In-house counsel, EU affairs consultant"
            maxLength={120}
          />
          <small>How you describe your professional role. Brubru tailors answers based on this.</small>
        </div>

        <div className="profile-dashboard__field">
          <label htmlFor="country">{t('profile.country')}</label>
          <select
            id="country"
            name="country"
            value={formData.country}
            onChange={handleChange}
            disabled={loading}
          >
            <option value="">{t('profile.selectCountry')}</option>
            {EU_COUNTRIES.map(c => (
              <option key={c.code} value={c.code}>{c.name}</option>
            ))}
          </select>
        </div>

        <div className="profile-dashboard__form-actions">
          <button
            type="submit"
            className="profile-dashboard__btn profile-dashboard__btn--primary"
            disabled={loading}
          >
            {loading ? t('profile.saving') : t('profile.saveChanges')}
          </button>
        </div>
      </form>
    </div>
  );

  const renderBilling = () => {
    const amendPct = usage ? getUsagePercentage(usage.amendments_used, usage.amendments_limit) : 0;
    const apiPct = usage ? getUsagePercentage(usage.api_calls_used, usage.api_calls_limit) : 0;

    return (
      <>
        {/* Tier card */}
        <div className={`profile-dashboard__billing-tier profile-dashboard__billing-tier--${user?.subscription_tier || 'white'}`}>
          <p className="profile-dashboard__billing-tier-name">{currentTier?.name || 'White (Basic)'}</p>
          <p className="profile-dashboard__billing-tier-price">
            {currentTier?.price_monthly === 0
              ? 'Free'
              : <>
                  {'\u20AC'}{currentTier?.price_monthly ?? 0}
                  <small> / month</small>
                </>
            }
          </p>
          <p className="profile-dashboard__billing-tier-desc">
            {currentTier?.description || 'Basic access to Brubru features'}
          </p>
        </div>

        {/* Usage */}
        <div className="profile-dashboard__card">
          <div className="profile-dashboard__card-header">
            <h3 className="profile-dashboard__card-title">Usage This Month</h3>
          </div>
          <div className="profile-dashboard__billing-usage">
            <div>
              <div className="profile-dashboard__billing-usage-item">
                <span className="profile-dashboard__billing-usage-label">{t('profile.amendmentsMonth')}</span>
                <span className="profile-dashboard__billing-usage-value">
                  {usage?.amendments_used ?? 0}
                  {usage?.amendments_limit !== -1
                    ? ` / ${usage?.amendments_limit}`
                    : ` (${t('profile.unlimited')})`
                  }
                </span>
              </div>
              {usage?.amendments_limit !== -1 && usage?.amendments_limit !== undefined && (
                <div className="profile-dashboard__billing-progress">
                  <div
                    className={`profile-dashboard__billing-progress-bar profile-dashboard__billing-progress-bar--${getProgressColour(amendPct)}`}
                    style={{ width: `${amendPct}%` }}
                  />
                </div>
              )}
            </div>

            {(usage?.api_calls_limit ?? 0) > 0 && (
              <div>
                <div className="profile-dashboard__billing-usage-item">
                  <span className="profile-dashboard__billing-usage-label">{t('profile.apiCalls')}</span>
                  <span className="profile-dashboard__billing-usage-value">
                    {usage?.api_calls_used ?? 0}
                    {usage?.api_calls_limit !== -1
                      ? ` / ${usage?.api_calls_limit}`
                      : ` (${t('profile.unlimited')})`
                    }
                  </span>
                </div>
                {usage?.api_calls_limit !== -1 && usage?.api_calls_limit !== undefined && (
                  <div className="profile-dashboard__billing-progress">
                    <div
                      className={`profile-dashboard__billing-progress-bar profile-dashboard__billing-progress-bar--${getProgressColour(apiPct)}`}
                      style={{ width: `${apiPct}%` }}
                    />
                  </div>
                )}
              </div>
            )}

            {user?.subscription_expires_at && (
              <div className="profile-dashboard__billing-usage-item">
                <span className="profile-dashboard__billing-usage-label">{t('profile.renewsOn')}</span>
                <span className="profile-dashboard__billing-usage-value">
                  {new Date(user.subscription_expires_at).toLocaleDateString('en-GB', {
                    day: 'numeric', month: 'long', year: 'numeric'
                  })}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Features */}
        {currentTier?.features && currentTier.features.length > 0 && (
          <div className="profile-dashboard__card">
            <div className="profile-dashboard__card-header">
              <h3 className="profile-dashboard__card-title">Included Features</h3>
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
              {currentTier.features.map((feature, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9375rem', color: 'var(--color-text)' }}>
                  <Icon path={mdiCheck} size={0.7} color="var(--color-success)" />
                  {feature}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="profile-dashboard__card">
          <div className="profile-dashboard__card-header">
            <h3 className="profile-dashboard__card-title">Manage Subscription</h3>
          </div>
          <div className="profile-dashboard__billing-actions">
            <button
              className="profile-dashboard__btn profile-dashboard__btn--secondary"
              onClick={() => createPortalSession()}
            >
              <Icon path={mdiOpenInNew} size={0.8} />
              Stripe Customer Portal
            </button>
            {user?.subscription_tier !== 'blue' && (
              <Link
                to="/#pricing"
                className="profile-dashboard__btn profile-dashboard__btn--upgrade"
              >
                <Icon path={mdiArrowUpBold} size={0.8} />
                {t('profile.upgrade')}
              </Link>
            )}
          </div>
        </div>
      </>
    );
  };

  const renderPolicies = () => (
    <div className="profile-dashboard__card">
      <div className="profile-dashboard__card-header">
        <h3 className="profile-dashboard__card-title">{t('profile.policyInterests')}</h3>
        <div>
          {preferencesLoading && (
            <span className="profile-dashboard__loading">{t('profile.saving')}</span>
          )}
          {preferencesSaved && (
            <span className="profile-dashboard__saved">
              <Icon path={mdiCheck} size={0.7} /> {t('profile.saved')}
            </span>
          )}
        </div>
      </div>
      <p className="profile-dashboard__card-description">
        {t('profile.policyDescription')}
      </p>
      <PolicyPreferencesSelector
        selectedPolicies={policyInterests}
        onUpdate={handlePreferencesUpdate}
      />
    </div>
  );

  const renderSectors = () => (
    <div className="profile-dashboard__card">
      <div className="profile-dashboard__card-header">
        <h3 className="profile-dashboard__card-title">Your sectors</h3>
        <div>
          {sectorsLoading && (
            <span className="profile-dashboard__loading">{t('profile.saving')}</span>
          )}
          {sectorsSaved && (
            <span className="profile-dashboard__saved">
              <Icon path={mdiCheck} size={0.7} /> {t('profile.saved')}
            </span>
          )}
        </div>
      </div>
      <p className="profile-dashboard__card-description">
        Pick the EU economic-activity sectors you work in. These power the
        Dashboard's Voice opportunities, Compliance signals, and New this
        week tiles.
      </p>
      <SectorsSelector selectedSectors={sectors} onUpdate={handleSectorsUpdate} />
    </div>
  );

  const renderBackground = () => (
    <div className="profile-dashboard__card">
      <div className="profile-dashboard__card-header">
        <h3 className="profile-dashboard__card-title">Page Background</h3>
        <div>
          {backgroundLoading && (
            <span className="profile-dashboard__loading">{t('profile.saving')}</span>
          )}
          {backgroundSaved && (
            <span className="profile-dashboard__saved">
              <Icon path={mdiCheck} size={0.7} /> {t('profile.saved')}
            </span>
          )}
        </div>
      </div>
      <p className="profile-dashboard__card-description">
        Personalise your My EU Bubble and Profile pages with a beautiful European cityscape or landmark.
      </p>
      <BackgroundSelector
        selectedBackground={backgroundPreference}
        onSelect={handleBackgroundUpdate}
      />
    </div>
  );

  const renderFeedback = () => (
    <div className="profile-dashboard__card">
      <div className="profile-dashboard__card-header">
        <h3 className="profile-dashboard__card-title">{t('profile.feedback')}</h3>
      </div>
      <p className="profile-dashboard__card-description">
        {t('profile.feedbackDescription')}
      </p>
      <FeedbackForm />
    </div>
  );

  const renderAccount = () => (
    <>
      <div className="profile-dashboard__card">
        <div className="profile-dashboard__card-header">
          <h3 className="profile-dashboard__card-title">{t('profile.accountSettings')}</h3>
        </div>
        <div className="profile-dashboard__account-info">
          <div className="profile-dashboard__account-item">
            <span>{t('profile.accountCreated')}</span>
            <strong>{user?.created_at && new Date(user.created_at).toLocaleDateString('en-GB', {
              day: 'numeric', month: 'long', year: 'numeric'
            })}</strong>
          </div>
          <div className="profile-dashboard__account-item">
            <span>{t('profile.lastLogin')}</span>
            <strong>{user?.last_login && new Date(user.last_login).toLocaleDateString('en-GB', {
              day: 'numeric', month: 'long', year: 'numeric'
            })}</strong>
          </div>
          <div className="profile-dashboard__account-item">
            <span>Email</span>
            <strong>{user?.email}</strong>
          </div>
          <div className="profile-dashboard__account-item">
            <span>Organisation</span>
            <strong>{user?.organization || 'Not set'}</strong>
          </div>
        </div>
      </div>

      <div className="profile-dashboard__card">
        <div className="profile-dashboard__card-header">
          <h3 className="profile-dashboard__card-title" style={{ color: 'var(--color-danger)' }}>Danger Zone</h3>
        </div>
        <div className="profile-dashboard__danger-zone">
          <p className="profile-dashboard__danger-text">
            {t('profile.deleteWarning')}
          </p>
          <button className="profile-dashboard__btn profile-dashboard__btn--danger">
            <Icon path={mdiDeleteOutline} size={0.8} />
            {t('profile.deleteAccount')}
          </button>
        </div>
      </div>
    </>
  );

  const sectionRenderers: Record<Section, () => React.ReactNode> = {
    overview: renderOverview,
    personal: renderPersonalInfo,
    billing: renderBilling,
    policies: renderPolicies,
    sectors: renderSectors,
    background: renderBackground,
    feedback: renderFeedback,
    account: renderAccount,
  };

  const sectionTitles: Record<Section, string> = {
    overview: 'Overview',
    personal: t('profile.personalInfo'),
    billing: 'Billing',
    policies: t('profile.policyInterests'),
    sectors: 'Sectors',
    background: 'Background',
    feedback: t('profile.feedback'),
    account: t('profile.accountSettings'),
  };

  const sectionSubtitles: Record<Section, string> = {
    overview: 'Your Brubru dashboard at a glance',
    personal: 'Update your name, role, organisation, and country',
    billing: 'Manage your subscription and billing',
    policies: 'Select the EU policy areas you follow',
    sectors: 'Pick your industry sectors so Brubru can personalise',
    background: 'Personalise your page backgrounds',
    feedback: 'Share your feedback and suggestions',
    account: 'Account details and settings',
  };

  return (
    <div className="profile-dashboard">
      {/* Mobile overlay */}
      <div
        className={`profile-dashboard__mobile-overlay ${mobileMenuOpen ? 'profile-dashboard__mobile-overlay--active' : ''}`}
        onClick={() => setMobileMenuOpen(false)}
      />

      {/* Sidebar */}
      <aside className={`profile-dashboard__sidebar ${mobileMenuOpen ? 'profile-dashboard__sidebar--open' : ''}`}>
        <div className="profile-dashboard__sidebar-header">
          {user?.is_trainer ? (
            <TrainerStarRing size={44}>
              <div className="profile-dashboard__avatar">{userInitials}</div>
            </TrainerStarRing>
          ) : (
            <div className="profile-dashboard__avatar">{userInitials}</div>
          )}
          <div className="profile-dashboard__user-info">
            <div className="profile-dashboard__user-name">
              {user?.is_trainer ? (
                <><TrainerNameGlow>{user?.full_name || 'User'}</TrainerNameGlow><TrainerShieldBadge size="md" /></>
              ) : (
                user?.full_name || 'User'
              )}
            </div>
            <div className="profile-dashboard__user-email">{user?.email}</div>
          </div>
        </div>

        <p className="profile-dashboard__nav-label">Dashboard</p>
        <ul className="profile-dashboard__nav">
          {navItems.map(item => (
            <li key={item.id}>
              <button
                className={`profile-dashboard__nav-item ${activeSection === item.id ? 'profile-dashboard__nav-item--active' : ''}`}
                onClick={() => handleNavClick(item.id)}
              >
                <Icon path={item.icon} size={0.85} className="profile-dashboard__nav-icon" />
                <span>{item.label}</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="profile-dashboard__sidebar-footer">
          {user?.email === 'hello@beresol.eu' && (
            <Link
              to="/admin"
              className="profile-dashboard__nav-item profile-dashboard__nav-item--admin"
              style={{ textDecoration: 'none' }}
            >
              <Icon path={mdiShieldCrownOutline} size={0.85} className="profile-dashboard__nav-icon" />
              <span>Admin Panel</span>
            </Link>
          )}
          <button
            className="profile-dashboard__nav-item profile-dashboard__nav-item--danger"
            onClick={logout}
          >
            <Icon path={mdiLogout} size={0.85} className="profile-dashboard__nav-icon" />
            <span>Log Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="profile-dashboard__main">
        {/* Mobile horizontal nav */}
        <div className="profile-dashboard__mobile-nav">
          {navItems.map(item => (
            <button
              key={item.id}
              className={`profile-dashboard__mobile-nav-item ${activeSection === item.id ? 'profile-dashboard__mobile-nav-item--active' : ''}`}
              onClick={() => handleNavClick(item.id)}
            >
              <Icon path={item.icon} size={0.65} />
              {item.label}
            </button>
          ))}
        </div>

        <div className="profile-dashboard__page-header">
          <h1 className="profile-dashboard__page-title">{sectionTitles[activeSection]}</h1>
          <p className="profile-dashboard__page-subtitle">{sectionSubtitles[activeSection]}</p>
        </div>

        {/* Render all sections, hide inactive ones to preserve component state */}
        {(Object.keys(sectionRenderers) as Section[]).map(section => (
          <div key={section} style={{ display: activeSection === section ? 'block' : 'none' }}>
            {sectionRenderers[section]()}
          </div>
        ))}
      </main>
    </div>
  );
};
