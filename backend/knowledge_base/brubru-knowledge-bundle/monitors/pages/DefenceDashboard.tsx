import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Shield, Percent, TrendingUp, Users, RefreshCw, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Header } from '@/components/Header';
import { MetricCard } from '@/components/defence/MetricCard';
import { DefenceSpendingChart } from '@/components/defence/DefenceSpendingChart';
import { CountryGrid } from '@/components/defence/CountryGrid';
import { DefenceNewsFeed } from '@/components/defence/DefenceNewsFeed';
import { LegislationTracker } from '@/components/defence/LegislationTracker';
import { DefenceFunding } from '@/components/defence/DefenceFunding';

import {
  getDefenceSpendingGDP,
  getDefenceSpendingTrends,
  getDefenceMetrics,
} from '@/services/eurostat';
import { fetchDefenceNews, getLegislationUpdates, getFallbackNews } from '@/services/defenceNews';
import { FeedbackSection } from '@/components/FeedbackSection';
import { SEO } from '@/components/SEO';
import { RelatedMonitorBanner, RelatedMonitorsSection } from '@/components/monitors';

export default function DefenceDashboard() {
  const [selectedCountry, setSelectedCountry] = useState<string | undefined>();

  // Scroll to top on mount
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  // Fetch defence metrics
  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['defenceMetrics'],
    queryFn: getDefenceMetrics,
    staleTime: 1000 * 60 * 60, // 1 hour
    retry: 2,
  });

  // Fetch country data
  const { data: countryData, isLoading: countryLoading } = useQuery({
    queryKey: ['defenceCountryData'],
    queryFn: () => getDefenceSpendingGDP(2015, 2023),
    staleTime: 1000 * 60 * 60,
    retry: 2,
  });

  // Fetch trend data
  const { data: trendData, isLoading: trendLoading } = useQuery({
    queryKey: ['defenceTrends'],
    queryFn: () => getDefenceSpendingTrends(2010, 2023),
    staleTime: 1000 * 60 * 60,
    retry: 2,
  });

  // Fetch news
  const {
    data: newsData,
    isLoading: newsLoading,
    refetch: refetchNews,
  } = useQuery({
    queryKey: ['defenceNews'],
    queryFn: () => fetchDefenceNews(10),
    staleTime: 1000 * 60 * 15, // 15 minutes
    retry: 1,
  });

  // Static legislation data
  const legislation = getLegislationUpdates();

  // Use fallback news if fetch fails
  const news = newsData && newsData.length > 0 ? newsData : getFallbackNews();

  return (
    <div className="min-h-screen bg-background">
      <SEO
        title="EU Defence Monitor - European Defence Spending & Policy Tracker"
        description="Real-time tracking of EU defence spending, military budgets, PESCO projects, and European security policy developments across all 27 member states."
        keywords="EU defence spending, European defence policy, PESCO, military budgets, NATO spending, European security, defence industry, EU member states defence"
        url="/defence"
      />
      <Header />

      <main className="container mx-auto px-4 py-8">
        {/* Back navigation */}
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>

        {/* Related Monitor Banner */}
        <RelatedMonitorBanner currentMonitor="defence" className="mb-6" />

        {/* Page Header */}
        <header className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              <Shield className="w-6 h-6 text-primary" />
            </div>
            <h1 className="text-3xl md:text-4xl font-bold text-secondary">
              EU Defence Monitor
            </h1>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Real-time tracking of European defence spending, legislation, and policy developments
          </p>
          {metrics?.lastUpdated && (
            <p className="text-sm text-muted-foreground mt-2 flex items-center justify-center gap-2">
              <RefreshCw className="w-3 h-3" />
              Data updated: {metrics.lastUpdated.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          )}
        </header>

        {/* Hero Metrics */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <MetricCard
            icon={Shield}
            value={metricsLoading ? '...' : `€${metrics?.totalExpenditure || 279}B`}
            label="EU Defence Expenditure 2023"
            trend={metrics ? { value: metrics.yearOverYearChange, isPositive: metrics.yearOverYearChange > 0 } : undefined}
            color="primary"
          />
          <MetricCard
            icon={Percent}
            value={metricsLoading ? '...' : `${metrics?.avgGdpPercentage || 1.3}%`}
            label="Average GDP Percentage"
            color="secondary"
          />
          <MetricCard
            icon={TrendingUp}
            value={metricsLoading ? '...' : `+${metrics?.yearOverYearChange || 12}%`}
            label="Year-over-Year Change"
            color="accent"
          />
          <MetricCard
            icon={Users}
            value={metricsLoading ? '...' : metrics?.pescoProjects || 74}
            label="Active PESCO Projects"
            color="primary"
          />
        </section>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          {/* Chart - 2/3 width on desktop */}
          <div className="lg:col-span-2 flex">
            <DefenceSpendingChart
              data={trendData || []}
              isLoading={trendLoading}
            />
          </div>

          {/* News Feed - 1/3 width on desktop */}
          <div className="lg:col-span-1 flex">
            <DefenceNewsFeed
              news={news}
              isLoading={newsLoading}
              onRefresh={() => refetchNews()}
            />
          </div>
        </div>

        {/* EU Defence Funding */}
        <section className="mb-12">
          <DefenceFunding />
        </section>

        {/* Country Grid */}
        <section className="mb-12">
          <CountryGrid
            countries={countryData || []}
            isLoading={countryLoading}
            onCountrySelect={setSelectedCountry}
            selectedCountry={selectedCountry}
          />
        </section>

        {/* Legislation Tracker */}
        <section className="mb-12">
          <LegislationTracker legislation={legislation} />
        </section>

        {/* Related Monitors Section */}
        <section className="mb-12">
          <RelatedMonitorsSection currentMonitor="defence" />
        </section>

        {/* Feedback Section */}
        <FeedbackSection
          contentType="monitor"
          contentTitle="EU Defence Monitor"
        />

        {/* Footer Attribution */}
        <footer className="text-center py-8 border-t border-border/50">
          <p className="text-sm text-muted-foreground">
            Data sources: Eurostat (COFOG GF02), EUR-Lex, European Defence Agency
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            Non-commercial use | SIPRI data attribution required
          </p>
        </footer>
      </main>
    </div>
  );
}
