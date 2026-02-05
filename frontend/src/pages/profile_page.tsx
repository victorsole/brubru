// frontend/src/pages/profile_page.tsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/use_auth';
import { useSubscription } from '../hooks/use_subscription';
import { Link } from 'react-router-dom';
import { PolicyPreferencesSelector } from '../components/profile/policy_preferences_selector';
import { BackgroundSelector } from '../components/profile/background_selector';
import { FeedbackForm } from '../components/feedback/feedback_form';
import './profile_page.css';

export const ProfilePage = () => {
  const { t } = useTranslation();
  const { user, updateProfile } = useAuth();
  const { usage, tiers, fetchUsage, fetchTiers } = useSubscription();

  const [formData, setFormData] = useState({
    full_name: user?.full_name || '',
    organization: user?.organization || '',
    country: user?.country || ''
  });
  const [policyInterests, setPolicyInterests] = useState<string[]>([]);
  const [backgroundPreference, setBackgroundPreference] = useState<string>('default');
  const [saved, setSaved] = useState(false);
  const [preferencesSaved, setPreferencesSaved] = useState(false);
  const [backgroundSaved, setBackgroundSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [preferencesLoading, setPreferencesLoading] = useState(false);
  const [backgroundLoading, setBackgroundLoading] = useState(false);

  useEffect(() => {
    // Parse policy interests from user object
    if (user?.policy_interests) {
      try {
        const interests = typeof user.policy_interests === 'string'
          ? JSON.parse(user.policy_interests)
          : user.policy_interests;
        setPolicyInterests(Array.isArray(interests) ? interests : []);
      } catch (e) {
        console.error('Failed to parse policy interests', e);
        setPolicyInterests([]);
      }
    }

    // Set background preference from user
    if (user?.background_preference) {
      setBackgroundPreference(user.background_preference);
    }
  }, [user]);

  useEffect(() => {
    fetchUsage();
    fetchTiers();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
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
      await updateProfile({
        policy_interests: JSON.stringify(policies)
      });
      setPreferencesSaved(true);
      setTimeout(() => setPreferencesSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update preferences', err);
    } finally {
      setPreferencesLoading(false);
    }
  };

  const handleBackgroundUpdate = async (background: string) => {
    setBackgroundPreference(background);
    setBackgroundLoading(true);

    try {
      await updateProfile({
        background_preference: background
      });
      setBackgroundSaved(true);
      setTimeout(() => setBackgroundSaved(false), 3000);
    } catch (err) {
      console.error('Failed to update background', err);
    } finally {
      setBackgroundLoading(false);
    }
  };

  const currentTier = tiers?.find(t => t.id === user?.subscription_tier);

  // Get background image URL if user has selected one
  const backgroundImage = user?.background_preference && user.background_preference !== 'default'
    ? `/assets/backgrounds/${user.background_preference}`
    : null;

  return (
    <div
      className="profile-page"
      style={backgroundImage ? {
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed'
      } : undefined}
    >
      <div className="profile-page__container">
        <h1>{t('profile.title')}</h1>

        {/* Admin Panel Button - Only for hello@beresol.eu */}
        {user?.email === 'hello@beresol.eu' && (
          <div className="profile-page__admin-section">
            <Link to="/admin" className="btn btn--primary btn--admin">
              <svg className="profile-page__admin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Admin Panel
            </Link>
          </div>
        )}

        {/* Subscription Status */}
        <section className="profile-page__section">
          <h2>{t('profile.subscription')}</h2>
          <div className="profile-page__subscription-card">
            <div className="profile-page__subscription-header">
              <span className={`profile-page__tier-badge profile-page__tier-badge--${user?.subscription_tier}`}>
                {currentTier?.name || 'White (Basic)'}
              </span>
              {user?.subscription_tier !== 'blue' && (
                <Link to="/#pricing" className="btn btn--small btn--primary">
                  {t('profile.upgrade')}
                </Link>
              )}
            </div>

            {/* Usage Stats */}
            {usage && (
              <div className="profile-page__usage">
                <div className="profile-page__usage-item">
                  <span>{t('profile.amendmentsMonth')}</span>
                  <strong>
                    {usage.amendments_used}
                    {usage.amendments_limit !== -1 && ` / ${usage.amendments_limit}`}
                    {usage.amendments_limit === -1 && ` (${t('profile.unlimited')})`}
                  </strong>
                </div>
                {usage.api_calls_limit > 0 && (
                  <div className="profile-page__usage-item">
                    <span>{t('profile.apiCalls')}</span>
                    <strong>
                      {usage.api_calls_used}
                      {usage.api_calls_limit !== -1 && ` / ${usage.api_calls_limit}`}
                      {usage.api_calls_limit === -1 && ` (${t('profile.unlimited')})`}
                    </strong>
                  </div>
                )}
                {user?.subscription_expires_at && (
                  <div className="profile-page__usage-item">
                    <span>{t('profile.renewsOn')}</span>
                    <strong>
                      {new Date(user.subscription_expires_at).toLocaleDateString('en-GB')}
                    </strong>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* Personal Information */}
        <section className="profile-page__section">
          <h2>{t('profile.personalInfo')}</h2>
          <form onSubmit={handleSubmit} className="profile-page__form">
            <div className="profile-page__field">
              <label htmlFor="email">{t('profile.email')}</label>
              <input
                id="email"
                type="email"
                value={user?.email || ''}
                disabled
              />
              <small>{t('profile.emailNote')}</small>
            </div>

            <div className="profile-page__field">
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

            <div className="profile-page__field">
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

            <div className="profile-page__field">
              <label htmlFor="country">{t('profile.country')}</label>
              <select
                id="country"
                name="country"
                value={formData.country}
                onChange={handleChange}
                disabled={loading}
              >
                <option value="">{t('profile.selectCountry')}</option>
                <option value="AT">Austria</option>
                <option value="BE">Belgium</option>
                <option value="BG">Bulgaria</option>
                <option value="HR">Croatia</option>
                <option value="CY">Cyprus</option>
                <option value="CZ">Czech Republic</option>
                <option value="DK">Denmark</option>
                <option value="EE">Estonia</option>
                <option value="FI">Finland</option>
                <option value="FR">France</option>
                <option value="DE">Germany</option>
                <option value="GR">Greece</option>
                <option value="HU">Hungary</option>
                <option value="IE">Ireland</option>
                <option value="IT">Italy</option>
                <option value="LV">Latvia</option>
                <option value="LT">Lithuania</option>
                <option value="LU">Luxembourg</option>
                <option value="MT">Malta</option>
                <option value="NL">Netherlands</option>
                <option value="PL">Poland</option>
                <option value="PT">Portugal</option>
                <option value="RO">Romania</option>
                <option value="SK">Slovakia</option>
                <option value="SI">Slovenia</option>
                <option value="ES">Spain</option>
                <option value="SE">Sweden</option>
              </select>
            </div>

            <div className="profile-page__actions">
              <button
                type="submit"
                className="btn btn--primary"
                disabled={loading}
              >
                {loading ? t('profile.saving') : t('profile.saveChanges')}
              </button>
              {saved && (
                <span className="profile-page__saved">✓ {t('profile.saved')}</span>
              )}
            </div>
          </form>
        </section>

        {/* Policy Interests */}
        <section className="profile-page__section">
          <div className="profile-page__section-header">
            <h2>{t('profile.policyInterests')}</h2>
            {preferencesLoading && (
              <span className="profile-page__loading">{t('profile.saving')}</span>
            )}
            {preferencesSaved && (
              <span className="profile-page__saved">✓ {t('profile.saved')}</span>
            )}
          </div>
          <p className="profile-page__section-description">
            {t('profile.policyDescription')}
          </p>
          <PolicyPreferencesSelector
            selectedPolicies={policyInterests}
            onUpdate={handlePreferencesUpdate}
          />
        </section>

        {/* Background Preference */}
        <section className="profile-page__section">
          <div className="profile-page__section-header">
            <h2>Page Background</h2>
            {backgroundLoading && (
              <span className="profile-page__loading">{t('profile.saving')}</span>
            )}
            {backgroundSaved && (
              <span className="profile-page__saved">✓ {t('profile.saved')}</span>
            )}
          </div>
          <p className="profile-page__section-description">
            Personalise your My EU Bubble and Profile pages with a beautiful European cityscape or landmark.
          </p>
          <BackgroundSelector
            selectedBackground={backgroundPreference}
            onSelect={handleBackgroundUpdate}
          />
        </section>

        {/* Feedback & Support */}
        <section className="profile-page__section">
          <h2>{t('profile.feedback')}</h2>
          <p className="profile-page__section-description">
            {t('profile.feedbackDescription')}
          </p>
          <FeedbackForm />
        </section>

        {/* Account Settings */}
        <section className="profile-page__section">
          <h2>{t('profile.accountSettings')}</h2>
          <div className="profile-page__account-info">
            <div className="profile-page__info-item">
              <span>{t('profile.accountCreated')}</span>
              <strong>{user?.created_at && new Date(user.created_at).toLocaleDateString('en-GB')}</strong>
            </div>
            <div className="profile-page__info-item">
              <span>{t('profile.lastLogin')}</span>
              <strong>{user?.last_login && new Date(user.last_login).toLocaleDateString('en-GB')}</strong>
            </div>
          </div>
          <div className="profile-page__danger-zone">
            <p className="profile-page__danger-text">
              {t('profile.deleteWarning')}
            </p>
            <button className="btn btn--danger btn--small">
              {t('profile.deleteAccount')}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
};
