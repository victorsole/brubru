// frontend/src/components/tenders/tender_profile_setup.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TenderProfile } from '../../pages/tenderator_page';
import { useAuth } from '../../hooks/use_auth';
import './tender_profile_setup.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// CPV top-level categories
const CPV_CATEGORIES = [
  { code: '03', name: 'Agricultural, farming, fishing, forestry' },
  { code: '09', name: 'Petroleum, fuel, electricity, energy' },
  { code: '14', name: 'Mining, basic metals' },
  { code: '15', name: 'Food, beverages, tobacco' },
  { code: '18', name: 'Clothing, footwear, luggage' },
  { code: '22', name: 'Printed matter, related products' },
  { code: '24', name: 'Chemical products' },
  { code: '30', name: 'Office and computing machinery' },
  { code: '31', name: 'Electrical machinery and apparatus' },
  { code: '32', name: 'Radio, television, communication' },
  { code: '33', name: 'Medical equipment, pharmaceuticals' },
  { code: '34', name: 'Transport equipment' },
  { code: '35', name: 'Security, fire-fighting, police' },
  { code: '38', name: 'Laboratory, optical, precision equipment' },
  { code: '39', name: 'Furniture, furnishings, domestic appliances' },
  { code: '42', name: 'Industrial machinery' },
  { code: '44', name: 'Construction structures and materials' },
  { code: '45', name: 'Construction work' },
  { code: '48', name: 'Software packages and information systems' },
  { code: '50', name: 'Repair and maintenance services' },
  { code: '55', name: 'Hotel, restaurant, retail trade services' },
  { code: '60', name: 'Transport services' },
  { code: '64', name: 'Postal and telecommunications services' },
  { code: '66', name: 'Financial and insurance services' },
  { code: '70', name: 'Real estate services' },
  { code: '71', name: 'Architectural, engineering, planning' },
  { code: '72', name: 'IT services, consulting, software' },
  { code: '73', name: 'Research and development services' },
  { code: '75', name: 'Public administration, defence, social security' },
  { code: '79', name: 'Business services: law, marketing, consulting' },
  { code: '80', name: 'Education and training services' },
  { code: '85', name: 'Health and social work services' },
  { code: '90', name: 'Sewage, refuse, cleaning, environmental services' },
  { code: '92', name: 'Recreational, cultural, sporting services' },
];

const EU_COUNTRIES = [
  { code: 'AT', name: 'Austria' },
  { code: 'BE', name: 'Belgium' },
  { code: 'BG', name: 'Bulgaria' },
  { code: 'HR', name: 'Croatia' },
  { code: 'CY', name: 'Cyprus' },
  { code: 'CZ', name: 'Czechia' },
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

const PROCEDURE_TYPES = [
  { value: 'open', label: 'Open Procedure', description: 'Any interested operator can submit a tender' },
  { value: 'restricted', label: 'Restricted Procedure', description: 'Only invited candidates can submit tenders' },
  { value: 'competitive', label: 'Competitive Dialogue', description: 'For complex contracts requiring dialogue' },
  { value: 'negotiated', label: 'Negotiated Procedure', description: 'Contracting authority negotiates with operators' },
];

interface TenderProfileSetupProps {
  existingProfile: TenderProfile | null;
  onProfileSaved: (profile: TenderProfile) => void;
  onBack?: () => void;
}

export const TenderProfileSetup = ({ existingProfile, onProfileSaved, onBack }: TenderProfileSetupProps) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  // Form state
  const [companyName, setCompanyName] = useState(existingProfile?.company_name || '');
  const [companySize, setCompanySize] = useState(existingProfile?.company_size || 'small');
  const [annualTurnover, setAnnualTurnover] = useState(existingProfile?.annual_turnover?.toString() || '');
  const [employeeCount, setEmployeeCount] = useState(existingProfile?.employee_count?.toString() || '');
  const [selectedSectors, setSelectedSectors] = useState<string[]>(existingProfile?.cpv_categories || []);
  const [selectedCountries, setSelectedCountries] = useState<string[]>(existingProfile?.countries_of_interest || []);
  const [keywords, setKeywords] = useState<string>(existingProfile?.keywords?.join(', ') || '');
  const [maxTenderValue, setMaxTenderValue] = useState(existingProfile?.max_tender_value?.toString() || '');
  const [minTenderValue, setMinTenderValue] = useState(existingProfile?.min_tender_value?.toString() || '');
  const [minDeadlineDays, setMinDeadlineDays] = useState(existingProfile?.min_deadline_days?.toString() || '30');
  const [preferredProcedures, setPreferredProcedures] = useState<string[]>(existingProfile?.preferred_procedures || ['open']);
  const [notificationFrequency, setNotificationFrequency] = useState(existingProfile?.notification_frequency || 'weekly');

  const totalSteps = 4;

  // Phase-3 bridge: pre-fill CPV categories + keywords from the user's Policy
  // Interests (non-destructive — merges into whatever is already selected).
  const applyMyInterests = async () => {
    try {
      const r = await fetch(`${API_URL}/api/tenders/profile/suggested-from-interests`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) return;
      const d = await r.json();
      if (Array.isArray(d.cpv_categories) && d.cpv_categories.length) {
        setSelectedSectors((prev) => Array.from(new Set([...prev, ...d.cpv_categories])));
      }
      if (Array.isArray(d.keywords) && d.keywords.length) {
        setKeywords((prev) => {
          const existing = prev.split(',').map((k) => k.trim()).filter(Boolean);
          return Array.from(new Set([...existing, ...d.keywords])).join(', ');
        });
      }
    } catch { /* silent: leave the form as-is */ }
  };

  const toggleSector = (code: string) => {
    if (selectedSectors.includes(code)) {
      setSelectedSectors(selectedSectors.filter((s) => s !== code));
    } else {
      setSelectedSectors([...selectedSectors, code]);
    }
  };

  const toggleCountry = (code: string) => {
    if (selectedCountries.includes(code)) {
      setSelectedCountries(selectedCountries.filter((c) => c !== code));
    } else {
      setSelectedCountries([...selectedCountries, code]);
    }
  };

  const toggleProcedure = (value: string) => {
    if (preferredProcedures.includes(value)) {
      setPreferredProcedures(preferredProcedures.filter((p) => p !== value));
    } else {
      setPreferredProcedures([...preferredProcedures, value]);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1:
        return companyName.trim() !== '' && companySize !== '';
      case 2:
        return selectedSectors.length > 0;
      case 3:
        return selectedCountries.length > 0;
      case 4:
        return true;
      default:
        return false;
    }
  };

  const handleSubmit = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const isUpdate = existingProfile !== null;

      const payload = {
        company_name: companyName,
        company_size: companySize,
        annual_turnover: annualTurnover ? parseFloat(annualTurnover) : null,
        employee_count: employeeCount ? parseInt(employeeCount) : null,
        cpv_categories: selectedSectors,
        countries_of_interest: selectedCountries,
        keywords: keywords.split(',').map((k) => k.trim()).filter((k) => k),
        max_tender_value: maxTenderValue ? parseFloat(maxTenderValue) : null,
        min_tender_value: minTenderValue ? parseFloat(minTenderValue) : null,
        min_deadline_days: parseInt(minDeadlineDays) || 30,
        preferred_procedures: preferredProcedures,
        notification_frequency: notificationFrequency,
        is_active: true,
      };

      const response = await fetch(`${API_URL}/api/tenders/profile`, {
        method: isUpdate ? 'PUT' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save profile');
      }

      const savedProfile = await response.json();
      setSavedAt(new Date().toISOString());
      // Brief delay so the success state is visible before navigating away.
      setTimeout(() => {
        onProfileSaved(savedProfile);
      }, 800);
    } catch (err: any) {
      console.error('Failed to save profile:', err);
      setError(err.message || 'Failed to save profile');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="tender-profile-setup">
      {/* Header */}
      <div className="tender-profile-setup__header">
        {onBack && (
          <button className="tender-profile-setup__back" onClick={onBack}>
            <span className="mdi mdi-arrow-left"></span>
            {t('tenderator.profileSetup.backButton')}
          </button>
        )}
        <h2>
          <span className="mdi mdi-account-cog"></span>
          {existingProfile ? t('tenderator.profileSetup.editTitle') : t('tenderator.profileSetup.createTitle')}
        </h2>
        <p className="tender-profile-setup__subtitle">
          {t('tenderator.profileSetup.subtitle')}
        </p>
      </div>

      {/* Progress Indicator */}
      <div className="tender-profile-setup__progress">
        {[1, 2, 3, 4].map((s) => (
          <div
            key={s}
            className={`tender-profile-setup__progress-step ${s <= step ? 'tender-profile-setup__progress-step--active' : ''} ${s < step ? 'tender-profile-setup__progress-step--completed' : ''}`}
          >
            <div className="tender-profile-setup__progress-dot">
              {s < step ? <span className="mdi mdi-check"></span> : s}
            </div>
            <span className="tender-profile-setup__progress-label">
              {s === 1 && t('tenderator.profileSetup.stepLabels.company')}
              {s === 2 && t('tenderator.profileSetup.stepLabels.sectors')}
              {s === 3 && t('tenderator.profileSetup.stepLabels.countries')}
              {s === 4 && t('tenderator.profileSetup.stepLabels.preferences')}
            </span>
          </div>
        ))}
      </div>

      {/* Error Message */}
      {error && (
        <div className="tender-profile-setup__error">
          <span className="mdi mdi-alert-circle"></span>
          <span>{error}</span>
        </div>
      )}

      {/* Success Message */}
      {savedAt && !error && (
        <div className="tender-profile-setup__success" role="status">
          <span className="mdi mdi-check-circle" aria-hidden="true"></span>
          {t('tenderator.profileSetup.successMessage')}
        </div>
      )}

      {/* Step Content */}
      <div className="tender-profile-setup__content">
        {/* Step 1: Company Information */}
        {step === 1 && (
          <div className="tender-profile-setup__step">
            <h3>{t('tenderator.profileSetup.step1.title')}</h3>
            <p>{t('tenderator.profileSetup.step1.description')}</p>

            <div className="tender-profile-setup__form">
              <div className="tender-profile-setup__field">
                <label>{t('tenderator.profileSetup.step1.companyNameLabel')}</label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder={t('tenderator.profileSetup.step1.companyNamePlaceholder')}
                />
              </div>

              <div className="tender-profile-setup__field">
                <label>{t('tenderator.profileSetup.step1.companySizeLabel')}</label>
                <div className="tender-profile-setup__radio-group">
                  {[
                    { value: 'micro', label: t('tenderator.profileSetup.step1.sizeLabels.micro'), desc: t('tenderator.profileSetup.step1.sizeDesc.micro') },
                    { value: 'small', label: t('tenderator.profileSetup.step1.sizeLabels.small'), desc: t('tenderator.profileSetup.step1.sizeDesc.small') },
                    { value: 'medium', label: t('tenderator.profileSetup.step1.sizeLabels.medium'), desc: t('tenderator.profileSetup.step1.sizeDesc.medium') },
                  ].map((size) => (
                    <label
                      key={size.value}
                      className={`tender-profile-setup__radio-card ${companySize === size.value ? 'tender-profile-setup__radio-card--selected' : ''}`}
                    >
                      <input
                        type="radio"
                        name="companySize"
                        value={size.value}
                        checked={companySize === size.value}
                        onChange={(e) => setCompanySize(e.target.value)}
                      />
                      <span className="tender-profile-setup__radio-content">
                        <span className="tender-profile-setup__radio-label">{size.label}</span>
                        <span className="tender-profile-setup__radio-desc">{size.desc}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="tender-profile-setup__row">
                <div className="tender-profile-setup__field">
                  <label>{t('tenderator.profileSetup.step1.annualTurnoverLabel')}</label>
                  <input
                    type="number"
                    value={annualTurnover}
                    onChange={(e) => setAnnualTurnover(e.target.value)}
                    placeholder={t('tenderator.profileSetup.step1.annualTurnoverPlaceholder')}
                  />
                </div>
                <div className="tender-profile-setup__field">
                  <label>{t('tenderator.profileSetup.step1.employeeCountLabel')}</label>
                  <input
                    type="number"
                    value={employeeCount}
                    onChange={(e) => setEmployeeCount(e.target.value)}
                    placeholder={t('tenderator.profileSetup.step1.employeeCountPlaceholder')}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Sectors */}
        {step === 2 && (
          <div className="tender-profile-setup__step">
            <h3>{t('tenderator.profileSetup.step2.title')}</h3>
            <p>{t('tenderator.profileSetup.step2.description')}</p>

            <button
              type="button"
              className="tender-profile-setup__use-interests"
              onClick={applyMyInterests}
              title={t('tenderator.profileSetup.step2.useInterestsTooltip')}
            >
              <span className="mdi mdi-creation"></span> {t('tenderator.profileSetup.step2.useInterestsButton')}
            </button>

            <div className="tender-profile-setup__chips">
              {CPV_CATEGORIES.map((sector) => (
                <button
                  key={sector.code}
                  className={`tender-profile-setup__chip ${selectedSectors.includes(sector.code) ? 'tender-profile-setup__chip--selected' : ''}`}
                  onClick={() => toggleSector(sector.code)}
                >
                  {selectedSectors.includes(sector.code) && <span className="mdi mdi-check"></span>}
                  {sector.name}
                </button>
              ))}
            </div>

            <p className="tender-profile-setup__selection-count">
              {t('tenderator.profileSetup.step2.selectionCount', { count: selectedSectors.length })}
            </p>
          </div>
        )}

        {/* Step 3: Countries */}
        {step === 3 && (
          <div className="tender-profile-setup__step">
            <h3>{t('tenderator.profileSetup.step3.title')}</h3>
            <p>{t('tenderator.profileSetup.step3.description')}</p>

            <div className="tender-profile-setup__country-grid">
              {EU_COUNTRIES.map((country) => (
                <button
                  key={country.code}
                  className={`tender-profile-setup__country-btn ${selectedCountries.includes(country.code) ? 'tender-profile-setup__country-btn--selected' : ''}`}
                  onClick={() => toggleCountry(country.code)}
                >
                  <span className="tender-profile-setup__country-code">{country.code}</span>
                  <span className="tender-profile-setup__country-name">{country.name}</span>
                  {selectedCountries.includes(country.code) && (
                    <span className="mdi mdi-check tender-profile-setup__country-check"></span>
                  )}
                </button>
              ))}
            </div>

            <p className="tender-profile-setup__selection-count">
              {t('tenderator.profileSetup.step3.selectionCount', { count: selectedCountries.length })}
            </p>
          </div>
        )}

        {/* Step 4: Preferences */}
        {step === 4 && (
          <div className="tender-profile-setup__step">
            <h3>{t('tenderator.profileSetup.step4.title')}</h3>
            <p>{t('tenderator.profileSetup.step4.description')}</p>

            <div className="tender-profile-setup__form">
              <div className="tender-profile-setup__field">
                <label>{t('tenderator.profileSetup.step4.keywordsLabel')}</label>
                <input
                  type="text"
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                  placeholder={t('tenderator.profileSetup.step4.keywordsPlaceholder')}
                />
                <span className="tender-profile-setup__hint">
                  {t('tenderator.profileSetup.step4.keywordsHint')}
                </span>
              </div>

              <div className="tender-profile-setup__row">
                <div className="tender-profile-setup__field">
                  <label>{t('tenderator.profileSetup.step4.minTenderValueLabel')}</label>
                  <input
                    type="number"
                    value={minTenderValue}
                    onChange={(e) => setMinTenderValue(e.target.value)}
                    placeholder={t('tenderator.profileSetup.step4.minTenderValuePlaceholder')}
                  />
                </div>
                <div className="tender-profile-setup__field">
                  <label>{t('tenderator.profileSetup.step4.maxTenderValueLabel')}</label>
                  <input
                    type="number"
                    value={maxTenderValue}
                    onChange={(e) => setMaxTenderValue(e.target.value)}
                    placeholder={t('tenderator.profileSetup.step4.maxTenderValuePlaceholder')}
                  />
                </div>
              </div>

              <div className="tender-profile-setup__field">
                <label>{t('tenderator.profileSetup.step4.minDeadlineDaysLabel')}</label>
                <input
                  type="number"
                  value={minDeadlineDays}
                  onChange={(e) => setMinDeadlineDays(e.target.value)}
                  placeholder={t('tenderator.profileSetup.step4.minDeadlineDaysPlaceholder')}
                  min="7"
                  max="180"
                />
                <span className="tender-profile-setup__hint">
                  {t('tenderator.profileSetup.step4.minDeadlineDaysHint')}
                </span>
              </div>

              <div className="tender-profile-setup__field">
                <label>{t('tenderator.profileSetup.step4.procedureTypesLabel')}</label>
                <div className="tender-profile-setup__procedure-list">
                  {PROCEDURE_TYPES.map((proc) => (
                    <label
                      key={proc.value}
                      className={`tender-profile-setup__procedure ${preferredProcedures.includes(proc.value) ? 'tender-profile-setup__procedure--selected' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={preferredProcedures.includes(proc.value)}
                        onChange={() => toggleProcedure(proc.value)}
                      />
                      <span className="tender-profile-setup__procedure-content">
                        <span className="tender-profile-setup__procedure-label">{t(`tenderator.profileSetup.procedureTypes.${proc.value}.label`)}</span>
                        <span className="tender-profile-setup__procedure-desc">{t(`tenderator.profileSetup.procedureTypes.${proc.value}.description`)}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="tender-profile-setup__field">
                <label>{t('tenderator.profileSetup.step4.frequencyLabel')}</label>
                <select
                  value={notificationFrequency}
                  onChange={(e) => setNotificationFrequency(e.target.value)}
                >
                  <option value="daily">{t('tenderator.profileSetup.frequencies.daily')}</option>
                  <option value="weekly">{t('tenderator.profileSetup.frequencies.weekly')}</option>
                  <option value="biweekly">{t('tenderator.profileSetup.frequencies.biweekly')}</option>
                  <option value="instant">{t('tenderator.profileSetup.frequencies.instant')}</option>
                </select>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Navigation Buttons */}
      <div className="tender-profile-setup__nav">
        {step > 1 && (
          <button
            className="tender-profile-setup__nav-btn tender-profile-setup__nav-btn--secondary"
            onClick={() => setStep(step - 1)}
          >
            <span className="mdi mdi-chevron-left"></span>
            {t('tenderator.profileSetup.previousButton')}
          </button>
        )}

        {step < totalSteps ? (
          <button
            className="tender-profile-setup__nav-btn tender-profile-setup__nav-btn--primary"
            onClick={() => setStep(step + 1)}
            disabled={!canProceed()}
          >
            {t('tenderator.profileSetup.nextButton')}
            <span className="mdi mdi-chevron-right"></span>
          </button>
        ) : (
          <button
            className="tender-profile-setup__nav-btn tender-profile-setup__nav-btn--primary"
            onClick={handleSubmit}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <span className="mdi mdi-loading mdi-spin"></span>
                {t('tenderator.profileSetup.savingButton')}
              </>
            ) : (
              <>
                <span className="mdi mdi-check"></span>
                {existingProfile ? t('tenderator.profileSetup.saveChangesButton') : t('tenderator.profileSetup.createProfileButton')}
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};
