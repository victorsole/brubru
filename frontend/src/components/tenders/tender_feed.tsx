// frontend/src/components/tenders/tender_feed.tsx
import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { Tender, TenderMatch, TenderProfile } from '../../pages/tenderator_page';
import { useAuth } from '../../hooks/use_auth';
import './tender_feed.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// CPV sector mapping
const CPV_SECTORS: Record<string, string> = {
  '03': 'Agriculture & Food',
  '09': 'Petroleum & Fuel',
  '14': 'Mining & Minerals',
  '15': 'Food Products',
  '18': 'Clothing & Textiles',
  '22': 'Printed Matter',
  '24': 'Chemical Products',
  '30': 'Office Equipment',
  '31': 'Electrical Equipment',
  '32': 'Radio & TV Equipment',
  '33': 'Medical Equipment',
  '34': 'Transport Equipment',
  '35': 'Security Equipment',
  '37': 'Musical Instruments',
  '38': 'Laboratory Equipment',
  '39': 'Furniture',
  '42': 'Industrial Machinery',
  '43': 'Forestry Machinery',
  '44': 'Construction Materials',
  '45': 'Construction Works',
  '48': 'Software Products',
  '50': 'Repair Services',
  '51': 'Installation Services',
  '55': 'Hotel Services',
  '60': 'Transport Services',
  '63': 'Supporting Services',
  '64': 'Postal Services',
  '65': 'Utilities',
  '66': 'Financial Services',
  '70': 'Real Estate',
  '71': 'Architecture & Engineering',
  '72': 'IT Services',
  '73': 'R&D Services',
  '75': 'Public Admin',
  '76': 'Oil & Gas Services',
  '77': 'Agriculture Services',
  '79': 'Business Services',
  '80': 'Education Services',
  '85': 'Health Services',
  '90': 'Environmental Services',
  '92': 'Recreation Services',
  '98': 'Other Services',
};

interface TenderFeedProps {
  onSelectTender: (tender: Tender, match?: TenderMatch) => void;
  onViewChecklist: (tender: Tender) => void;
  userProfile: TenderProfile;
}

type FeedView = 'matches' | 'search' | 'saved';

export const TenderFeed = ({ onSelectTender, onViewChecklist, userProfile: _userProfile }: TenderFeedProps) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [feedView, setFeedView] = useState<FeedView>('matches');
  const [matches, setMatches] = useState<TenderMatch[]>([]);
  const [searchResults, setSearchResults] = useState<Tender[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search/filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [countryFilter, setCountryFilter] = useState('');
  const [sectorFilter, setSectorFilter] = useState('');
  const [maxValue, setMaxValue] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState('open');

  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Countries list
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

  // Fetch user matches
  const fetchMatches = useCallback(async (savedOnly: boolean = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '20',
        saved_only: savedOnly.toString(),
      });

      const response = await fetch(`${API_URL}/api/tenders/matches?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (!response.ok) throw new Error('Failed to fetch matches');

      const data = await response.json();
      setMatches(data.matches);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError('Failed to load tender matches');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [page, token]);

  // Search tenders
  const searchTenders = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: '20',
        status: statusFilter,
      });

      if (searchQuery) params.append('query', searchQuery);
      if (countryFilter) params.append('countries', countryFilter);
      if (sectorFilter) params.append('cpv_codes', sectorFilter);
      if (maxValue) params.append('max_value', maxValue);

      const response = await fetch(`${API_URL}/api/tenders?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (!response.ok) throw new Error('Failed to search tenders');

      const data = await response.json();
      setSearchResults(data.tenders);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError('Failed to search tenders');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [page, searchQuery, countryFilter, sectorFilter, maxValue, statusFilter, token]);

  // Effect for fetching data based on view
  useEffect(() => {
    if (feedView === 'matches') {
      fetchMatches(false);
    } else if (feedView === 'saved') {
      fetchMatches(true);
    } else {
      searchTenders();
    }
  }, [feedView, page, fetchMatches, searchTenders]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [feedView, searchQuery, countryFilter, sectorFilter, maxValue, statusFilter]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    searchTenders();
  };

  const getSectorName = (cpvCode: string): string => {
    if (!cpvCode) return t('tenderator.feed.sectorUnknown');
    const prefix = cpvCode.substring(0, 2);
    return CPV_SECTORS[prefix] || t('tenderator.feed.sectorOther');
  };

  const formatValue = (value: number | null, currency: string): string => {
    if (!value) return t('tenderator.feed.notSpecified');
    return new Intl.NumberFormat('en-EU', {
      style: 'currency',
      currency: currency || 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return t('tenderator.feed.notSpecified');
    return new Date(dateStr).toLocaleDateString('en-EU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const getDaysUntilDeadline = (deadline: string | null): number | null => {
    if (!deadline) return null;
    const now = new Date();
    const deadlineDate = new Date(deadline);
    const diffTime = deadlineDate.getTime() - now.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  };

  const getDeadlineClass = (days: number | null): string => {
    if (days === null) return '';
    if (days <= 7) return 'tender-card__deadline--urgent';
    if (days <= 14) return 'tender-card__deadline--soon';
    return '';
  };

  const getScoreClass = (score: number): string => {
    if (score >= 70) return 'tender-card__score--high';
    if (score >= 40) return 'tender-card__score--medium';
    return 'tender-card__score--low';
  };

  return (
    <div className="tender-feed">
      {/* View Toggle */}
      <div className="tender-feed__view-toggle">
        <button
          className={`tender-feed__view-btn ${feedView === 'matches' ? 'tender-feed__view-btn--active' : ''}`}
          onClick={() => setFeedView('matches')}
        >
          <span className="mdi mdi-target"></span>
          {t('tenderator.feed.viewMyMatches')}
        </button>
        <button
          className={`tender-feed__view-btn ${feedView === 'saved' ? 'tender-feed__view-btn--active' : ''}`}
          onClick={() => setFeedView('saved')}
        >
          <span className="mdi mdi-bookmark"></span>
          {t('tenderator.feed.viewSaved')}
        </button>
        <button
          className={`tender-feed__view-btn ${feedView === 'search' ? 'tender-feed__view-btn--active' : ''}`}
          onClick={() => setFeedView('search')}
        >
          <span className="mdi mdi-magnify"></span>
          {t('tenderator.feed.viewSearchAll')}
        </button>
      </div>

      {/* Search Filters (only for search view) */}
      {feedView === 'search' && (
        <form className="tender-feed__filters" onSubmit={handleSearch}>
          <input
            type="text"
            className="tender-feed__search-input"
            placeholder={t('tenderator.feed.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <select
            className="tender-feed__filter-select"
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
          >
            <option value="">{t('tenderator.feed.allCountries')}</option>
            {EU_COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>{c.name}</option>
            ))}
          </select>
          <select
            className="tender-feed__filter-select"
            value={sectorFilter}
            onChange={(e) => setSectorFilter(e.target.value)}
          >
            <option value="">{t('tenderator.feed.allSectors')}</option>
            {Object.entries(CPV_SECTORS).map(([code, name]) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </select>
          <input
            type="number"
            className="tender-feed__value-input"
            placeholder={t('tenderator.feed.maxValuePlaceholder')}
            value={maxValue}
            onChange={(e) => setMaxValue(e.target.value)}
          />
          <select
            className="tender-feed__filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="open">{t('tenderator.feed.status.open')}</option>
            <option value="closed">{t('tenderator.feed.status.closed')}</option>
            <option value="awarded">{t('tenderator.feed.status.awarded')}</option>
          </select>
          <button type="submit" className="tender-feed__search-btn">
            <span className="mdi mdi-magnify"></span>
            {t('tenderator.feed.searchButton')}
          </button>
        </form>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="tender-feed__loading">
          <span className="mdi mdi-loading mdi-spin"></span>
          {t('tenderator.feed.loading')}
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="tender-feed__error">
          <span className="mdi mdi-alert-circle"></span>
          {error}
        </div>
      )}

      {/* Tender List */}
      {!isLoading && !error && (
        <>
          {feedView === 'search' ? (
            /* Search Results */
            <div className="tender-feed__list">
              {searchResults.length === 0 ? (
                <div className="tender-feed__empty">
                  <span className="mdi mdi-file-search-outline"></span>
                  <p>{t('tenderator.feed.noSearchResults')}</p>
                </div>
              ) : (
                searchResults.map((tender) => (
                  <TenderCard
                    key={tender.id}
                    tender={tender}
                    onSelect={() => onSelectTender(tender)}
                    onViewChecklist={() => onViewChecklist(tender)}
                    getSectorName={getSectorName}
                    formatValue={formatValue}
                    formatDate={formatDate}
                    getDaysUntilDeadline={getDaysUntilDeadline}
                    getDeadlineClass={getDeadlineClass}
                  />
                ))
              )}
            </div>
          ) : (
            /* Matches */
            <div className="tender-feed__list">
              {matches.length === 0 ? (
                <div className="tender-feed__empty">
                  <span className="mdi mdi-target"></span>
                  <p>
                    {feedView === 'saved'
                      ? t('tenderator.feed.noSavedTenders')
                      : t('tenderator.feed.noMatches')}
                  </p>
                </div>
              ) : (
                matches.map((match) => (
                  <TenderCard
                    key={match.id}
                    tender={match.tender}
                    match={match}
                    onSelect={() => onSelectTender(match.tender, match)}
                    onViewChecklist={() => onViewChecklist(match.tender)}
                    getSectorName={getSectorName}
                    formatValue={formatValue}
                    formatDate={formatDate}
                    getDaysUntilDeadline={getDaysUntilDeadline}
                    getDeadlineClass={getDeadlineClass}
                    getScoreClass={getScoreClass}
                  />
                ))
              )}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="tender-feed__pagination">
              <button
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                <span className="mdi mdi-chevron-left"></span>
                {t('tenderator.feed.previous')}
              </button>
              <span>{t('tenderator.feed.pageCounter', { current: page, total: totalPages })}</span>
              <button
                disabled={page === totalPages}
                onClick={() => setPage(page + 1)}
              >
                {t('tenderator.feed.next')}
                <span className="mdi mdi-chevron-right"></span>
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// Tender Card Component
interface TenderCardProps {
  tender: Tender;
  match?: TenderMatch;
  onSelect: () => void;
  onViewChecklist: () => void;
  getSectorName: (cpv: string) => string;
  formatValue: (value: number | null, currency: string) => string;
  formatDate: (date: string | null) => string;
  getDaysUntilDeadline: (deadline: string | null) => number | null;
  getDeadlineClass: (days: number | null) => string;
  getScoreClass?: (score: number) => string;
}

const TenderCard = ({
  tender,
  match,
  onSelect,
  onViewChecklist,
  getSectorName,
  formatValue,
  formatDate,
  getDaysUntilDeadline,
  getDeadlineClass,
  getScoreClass,
}: TenderCardProps) => {
  const { t } = useTranslation();
  const daysLeft = getDaysUntilDeadline(tender.submission_deadline);

  return (
    <div className={`tender-card ${match?.is_saved ? 'tender-card--saved' : ''}`}>
      <div className="tender-card__header">
        <div className="tender-card__badges">
          <span className="tender-card__country">{tender.buyer_country}</span>
          <span className="tender-card__sector">{getSectorName(tender.cpv_main)}</span>
          {tender.status === 'open' && (
            <span className="tender-card__status tender-card__status--open">{t('tenderator.feed.status.open')}</span>
          )}
        </div>
        {match && getScoreClass && (
          <div className={`tender-card__score ${getScoreClass(match.match_score)}`}>
            <span className="mdi mdi-target"></span>
            {Math.round(match.match_score)}%
          </div>
        )}
      </div>

      <h3 className="tender-card__title" onClick={onSelect}>{tender.title}</h3>

      <div className="tender-card__buyer">
        <span className="mdi mdi-domain"></span>
        {tender.buyer_name}
      </div>

      <div className="tender-card__details">
        <div className="tender-card__detail">
          <span className="mdi mdi-currency-eur"></span>
          <span>{formatValue(tender.estimated_value, tender.currency)}</span>
        </div>
        <div className={`tender-card__detail tender-card__deadline ${getDeadlineClass(daysLeft)}`}>
          <span className="mdi mdi-calendar-clock"></span>
          <span>
            {daysLeft !== null
              ? daysLeft > 0
                ? t('tenderator.feed.daysLeft', { days: daysLeft })
                : daysLeft === 0
                  ? t('tenderator.feed.dueToday')
                  : t('tenderator.feed.expired')
              : formatDate(tender.submission_deadline)}
          </span>
        </div>
        {tender.sme_suitability_score !== null && (
          <div className="tender-card__detail tender-card__sme-score">
            <span className="mdi mdi-account-check"></span>
            <span>{t('tenderator.feed.smeScore', { score: Math.round(tender.sme_suitability_score) })}</span>
          </div>
        )}
      </div>

      {match?.match_reasons && match.match_reasons.length > 0 && (
        <div className="tender-card__reasons">
          {match.match_reasons.slice(0, 3).map((reason, idx) => (
            <span key={idx} className="tender-card__reason">
              <span className="mdi mdi-check"></span>
              {reason}
            </span>
          ))}
        </div>
      )}

      <div className="tender-card__actions">
        <button className="tender-card__action-btn tender-card__action-btn--primary" onClick={onSelect}>
          <span className="mdi mdi-eye"></span>
          {t('tenderator.feed.viewDetails')}
        </button>
        <button className="tender-card__action-btn" onClick={onViewChecklist}>
          <span className="mdi mdi-clipboard-check"></span>
          {t('tenderator.feed.checklist')}
        </button>
        {tender.ted_url && (
          <a
            href={`https://ted.europa.eu/en/notice/${tender.publication_number}`}
            target="_blank"
            rel="noopener noreferrer"
            className="tender-card__action-btn"
          >
            <span className="mdi mdi-open-in-new"></span>
            {t('tenderator.feed.tedLink')}
          </a>
        )}
      </div>
    </div>
  );
};
